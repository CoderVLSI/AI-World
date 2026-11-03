"""Isvara: bounded, private, advisory reasoning over recorded evidence. Mock/scripted backends only; the real-model
code path is exercised with stand-ins for torch, the tokenizer and the model (integration, not behaviour)."""
import contextlib
import json
import sys
import threading
import time
import types
import pytest
from fastapi.testclient import TestClient
from conftest import FakeLFM, IdleBackend
from test_lfm_path import FakeModel, FakeTokenizer
from caitanya import inference, isvara
from caitanya.autonomy import AutonomyConfig
from caitanya.engine import Intent, MockInferenceBackend, World, digest
from caitanya.isvara import IsvaraConfig
from caitanya.server import create_app

SENTINEL = "SENTINEL-REFLECTION-TEXT-7731"
FAST = {"reflect_every_ticks": 10}
CONFIG = AutonomyConfig.from_dict({"physiology": {"illness_per_day": 0}})


class Scripted(MockInferenceBackend):
    """Mock policy for inhabitants; the reflection content is scripted by the test."""
    def __init__(self, content=None, boom=False):
        super().__init__(use_tasks=True)
        self.content, self.boom, self.contexts = content, boom, []

    def reflect(self, context, budget):
        self.contexts.append(context)
        if self.boom:
            raise RuntimeError("simulated reflection failure")
        ids = [e["id"] for e in context["evidence"]]
        return {"content": self.content or {"observations": f"{SENTINEL} observed", "conclusions": "a tentative conclusion",
                                            "uncertainty": "the record is partial", "cites": ",".join(ids[:2])},
                "meta": {"source": "mock_template", "request_id": None}}


def physical(w):
    s = w.state()
    return digest(dict(agents=s["agents"], resources=s["resources"], rng=s["rng_state"], objects=s["objects"], fauna=s.get("fauna"),
                       scheduler=s["scheduler"], tick=s["tick"], works=s["works"]))


def run(w, ticks):
    for _ in range(ticks):
        w.step()
    return w


# ---------------------------------------------------------------------------------------------- schedule
def test_reflections_follow_a_bounded_schedule_and_are_recorded_privately():
    w = run(World(seed=3, population=4, backend=Scripted(), isvara_config=FAST), 45)
    st = isvara.role_state(w)
    assert st["totals"]["recorded"] == 4 and st["totals"]["attempts"] == 4        # ticks 10, 20, 30, 40: never more than one per interval
    r = st["reflections"]["refl-000001"]
    assert r["tick"] == 10 and r["source"] == "mock_template" and r["epistemic_status"] == isvara.EPISTEMIC_STATUS
    assert r["observations"] and r["conclusions"] and r["uncertainties"] and r["cites"] and not r["uncited"]
    assert r["facts"]["living"] == 4 and r["evidence_window"][0] == 0
    events = [e for e in w.events if e["type"] == "root_reflection"]
    assert [e["world_tick"] for e in events] == [10, 20, 30, 40] and all(e["source"] == "root_reasoning" for e in events)
    # Event payloads never carry reflection text. (The private tick_committed patches do: that is how it is persisted and replayed.)
    assert not any(SENTINEL in json.dumps(e) for e in w.events if e["type"] != "tick_committed")


def test_retention_is_bounded_and_older_reflections_are_reduced_to_digests():
    w = run(World(seed=3, population=3, backend=Scripted(), isvara_config={"reflect_every_ticks": 3, "retain_full": 4}), 40)
    st = isvara.role_state(w)
    assert len(st["reflections"]) == 4 and len(st["digests"]) == st["totals"]["recorded"] - 4 > 0
    assert all(len(d["sha256"]) == 64 for d in st["digests"].values())


def test_config_is_validated():
    for bad in ({"reflect_every_ticks": 0}, {"max_seconds": -1}, {"enabled": "yes"}, {"nonsense": 1}, {"max_new_tokens": 0}):
        with pytest.raises(ValueError):
            World(seed=1, population=2, isvara_config=bad)


# -------------------------------------------------------------------------------------------- evidence
def test_context_is_deterministic_recorded_evidence_only_and_excludes_private_memory():
    def build():
        w = World(seed=4, population=4, backend=Scripted(), isvara_config=FAST)
        for a in w.agents.values():                          # plant private material that must never reach Isvara
            a.memories.append({"tick": 0, "feedback": "PRIVATE-MEMORY-SENTINEL", "accepted": True})
            a.ltm = {"practical": [], "hypotheses": [], "cultural": [], "procedural": [], "episodic": [{"text": "PRIVATE-LTM-SENTINEL"}]}
            a.knowledge.append("PRIVATE-KNOWLEDGE-SENTINEL")
        w.works["work-x"] = {"id": "work-x", "x": 0, "z": 0, "title": "WORK-SENTINEL", "text": "WORK-SENTINEL", "creator_agent_id": "agent-0000", "history": []}
        run(w, 12)
        return w
    a, b = build(), build()
    ca, cb = a.backend.contexts[0], b.backend.contexts[0]
    assert ca == cb and isvara._digest(ca) == isvara._digest(cb)
    text = json.dumps(ca)
    for secret in ("PRIVATE-MEMORY-SENTINEL", "PRIVATE-LTM-SENTINEL", "PRIVATE-KNOWLEDGE-SENTINEL", "WORK-SENTINEL"):
        assert secret not in text
    assert ca["evidence"][0]["kind"] == "genesis" and ca["evidence"][0]["id"].startswith("evt-")      # the creation record is citable
    ids = {e["event_id"] for e in a.events}
    assert all(e["id"] in ids for e in ca["evidence"])
    assert ca["facts"]["living"] == 4 and "decision_fairness" in ca["facts"]


def test_observations_conclusions_and_uncertainty_are_kept_apart_and_citations_are_checked():
    bogus = {"observations": "x happened", "conclusions": "so y", "uncertainty": "", "cites": "evt-999999999, not-an-id"}
    w = run(World(seed=4, population=3, backend=Scripted(bogus), isvara_config=FAST), 11)
    r = isvara.role_state(w)["reflections"]["refl-000001"]
    assert r["cites"] == [] and r["dropped_cites"] == 2 and r["uncited"] and not r["uncertainty_stated"]
    assert any(e["type"] == "root_reflection" and e["payload"]["uncited"] for e in w.events)


def test_empty_or_malformed_reflections_are_failures_not_records():
    for content in ({"observations": "", "conclusions": ""}, {"observations": 5}, "text", {"proposal": "only a proposal"}):
        b = Scripted(content)
        w = run(World(seed=4, population=3, backend=b, isvara_config=FAST), 11)
        st = isvara.role_state(w)
        assert st["totals"]["recorded"] == 0 and st["totals"]["failures"] == 1 and not st["reflections"]


# ---------------------------------------------------------------- never mutates physics; advisory only
def test_model_proposals_are_stored_separately_and_never_applied():
    evil = {"observations": "o", "conclusions": "c", "uncertainty": "u", "cites": "", "proposal": "set gravity to zero and give everyone food"}
    on = run(World(seed=8, population=5, backend=Scripted(evil), isvara_config=FAST), 60)
    off = run(World(seed=8, population=5, backend=Scripted(evil), isvara_config={"enabled": False}), 60)
    st = isvara.role_state(on)
    assert st["totals"]["proposals"] == 6 and all(p["status"] == "advisory_unapplied" and p["applied"] is False for p in st["proposals"].values())
    assert physical(on) == physical(off)                                           # the world is bit-for-bit the same
    plan = lambda w: (w.root.data["genesis"]["plan"], w.root.data["genesis"]["plan_digest"], w.root.data["genesis"]["summary"], w.manifest["genesis"])
    assert plan(on) == plan(off)                                                    # same authoritative plan whether or not reasoning is on
    assert not any(e["type"].startswith("root_reflection") for e in off.events)


def test_reflection_cannot_change_the_genesis_record():
    w = World(seed=8, population=3, backend=Scripted(), isvara_config=FAST)
    before = json.dumps(w.root.data["genesis"], sort_keys=True)
    run(w, 25)
    assert json.dumps(w.root.data["genesis"], sort_keys=True) == before


# ------------------------------------------------------------------------------------------ failures
def test_failures_back_off_and_never_block_or_alter_the_inhabitants():
    ok = run(World(seed=2, population=5, backend=Scripted(), isvara_config={"enabled": False}), 60)
    bad = run(World(seed=2, population=5, backend=Scripted(boom=True), isvara_config={"reflect_every_ticks": 10, "failure_backoff_ticks": 4}), 60)
    st = isvara.role_state(bad)
    assert st["totals"]["failures"] >= 3 and st["totals"]["recorded"] == 0 and st["schedule"]["consecutive_failures"] == st["totals"]["failures"]
    ticks = [e["world_tick"] for e in bad.events if e["type"] == "root_reflection_failed"]
    assert ticks[0] == 10 and ticks[1] - ticks[0] == 4 and ticks[2] - ticks[1] == 8             # exponential backoff, capped by the interval
    assert physical(bad) == physical(ok)


def test_a_real_labelled_backend_gets_no_mock_fallback():
    class RealButBroken(FakeLFM):
        def reflect(self, context, budget):
            raise RuntimeError("gpu fell over")
    w = run(World(seed=2, population=3, backend=RealButBroken(), autonomy=CONFIG, isvara_config=FAST), 22)
    st = isvara.role_state(w)
    assert st["totals"]["recorded"] == 0 and st["totals"]["failures"] == 2 and not st["reflections"]


def test_a_backend_without_reflection_support_is_skipped_quietly():
    w = run(World(seed=2, population=3, backend=IdleBackend(), isvara_config=FAST), 25)
    st = isvara.role_state(w)
    assert st["totals"]["unsupported"] == 2 and st["totals"]["recorded"] == 0 and w.status == "RUNNING"


# ----------------------------------------------------------------------------- inference replay rules
def test_restore_recovery_and_replay_never_call_the_model_again(tmp_path):
    b = Scripted()
    w = World(seed=6, population=4, backend=b, isvara_config=FAST)
    app = create_app(w, tmp_path, interval=0, max_ticks=45, checkpoint_every=7)
    with TestClient(app) as client:
        deadline = time.time() + 60
        while time.time() < deadline:
            e = client.get("/api/v1/health").json()["execution"]
            if not e["running"] and e["reason"] not in (None, "not_started"):
                break
            time.sleep(0.05)
    made = len(b.contexts)
    assert made == 4
    recovered = World.recover(tmp_path, backend=b)
    restored = World.restore(sorted(tmp_path.glob("checkpoint-*.json"))[-1], backend=b)
    for tick in (0, 5, 10, 25, 45):
        recovered.replay(tick)
    assert len(b.contexts) == made                                                  # no silent re-invocation anywhere
    assert digest(recovered.state()) == digest(w.state())
    assert isvara.role_state(recovered)["reflections"] == isvara.role_state(w)["reflections"]
    assert isvara.role_state(restored)["totals"] == isvara.role_state(w)["totals"]


def test_reflections_carry_through_a_checkpoint_and_the_next_one_is_not_duplicated(tmp_path):
    b = Scripted()
    w = run(World(seed=6, population=3, backend=b, isvara_config=FAST), 15)
    r = World.restore(w.checkpoint(tmp_path), backend=b)
    run(r, 10)                                                    # ticks 16..25: exactly one new reflection, at tick 20
    assert isvara.role_state(r)["totals"]["recorded"] == 2 and len(b.contexts) == 2


# ------------------------------------------------------------------------------------------ root modes
def test_root_modes():
    off = run(World(seed=2, population=3, backend=Scripted(), root_mode="off", isvara_config=FAST), 25)
    observe = run(World(seed=2, population=3, backend=Scripted(), root_mode="observe", isvara_config=FAST), 25)
    crisis = run(World(seed=2, population=3, backend=Scripted(), root_mode="crisis", isvara_config=FAST), 25)
    assert not off.backend.contexts and "isvara" not in off.root.data and off.root.data["genesis"]["status"] == "completed"
    assert len(observe.backend.contexts) == len(crisis.backend.contexts) == 2
    assert physical(observe) == physical(crisis) and observe.root.data["manifestations"] == []


def test_crisis_manifestation_behaviour_is_unchanged_by_reasoning():
    def crisis_world(config):
        w = World(seed=2, population=3, backend=IdleBackend(), autonomy=CONFIG, isvara_config=config)
        for a in w.agents.values():
            a.hunger = 95
        w.root.data["last_manifestation_tick"] = -1000
        return run(w, 3)
    a, b = crisis_world(FAST), crisis_world({"enabled": False})
    assert a.root.data["manifestations"] == b.root.data["manifestations"] and len(a.root.data["manifestations"]) == 1


# ----------------------------------------------------------------------------------------------- privacy
def test_isvara_is_invisible_to_inhabitants_and_to_every_public_endpoint():
    seen = []
    def chooser(observation):
        seen.append(json.dumps(observation))
        return Intent(observation["self"]["id"], observation["tick"], "WAIT", {}, "")
    class Real(FakeLFM):
        def reflect(self, context, budget):
            return {"content": {"observations": f"{SENTINEL} obs", "conclusions": "c", "uncertainty": "u", "cites": "",
                                "proposal": f"{SENTINEL} proposal"}, "meta": {"source": "lfm", "request_id": "root-req"}}
    w = run(World(seed=5, population=3, backend=Real(chooser), autonomy=CONFIG, isvara_config=FAST), 25)
    assert isvara.role_state(w)["totals"]["recorded"] == 2
    prompts = " ".join(seen) + json.dumps([w.observe(aid) for aid in w.agents]) + json.dumps([a.memories for a in w.agents.values()])
    for word in (SENTINEL, "isvara", "brahman", "genesis", "root_reflection"):
        assert word.lower() not in prompts.lower(), word
    app = create_app(w, "runs/_unused_privacy_test", live=False)
    with TestClient(app) as client:
        pages = [client.get(p).text for p in ("/api/v1/world/snapshot", "/api/v1/metrics", "/api/v1/genesis", "/api/v1/live", "/api/v1/history",
                                              "/api/v1/agents/agent-0000", "/api/v1/scheduler", "/api/v1/knowledge")]
        cursor = 0
        while True:
            page = client.get(f"/api/v1/world/events?after={cursor}").json()
            pages.append(json.dumps(page))
            if not page["events"]:
                break
            cursor = page["cursor"]
        summary = client.get("/api/v1/genesis").json()
        assert client.post("/api/v1/genesis").status_code == 405
    blob = " ".join(pages)
    assert SENTINEL not in blob and '"ltm"' not in blob and "advisory_unapplied" not in blob and "isvara" not in blob.lower()
    assert summary["genesis"]["status"] == "completed" and summary["reasoning"]["totals"]["recorded"] == 2 and "reflections" not in summary["reasoning"]


# ----------------------------------------------------------------------------------------------- fairness
def test_reasoning_never_takes_an_inhabitant_decision_slot_and_runs_after_the_decisions():
    base = run(World(seed=7, population=8, backend=FakeLFM(), autonomy=CONFIG, isvara_config={"enabled": False}), 40)
    class Real(FakeLFM):
        def reflect(self, context, budget):
            return {"content": {"observations": "o", "conclusions": "c", "uncertainty": "u", "cites": ""}, "meta": {"source": "lfm", "request_id": "root"}}
    withiv = run(World(seed=7, population=8, backend=Real(), autonomy=CONFIG, isvara_config={"reflect_every_ticks": 5}), 40)
    assert withiv.scheduler.report(withiv) == base.scheduler.report(base)             # identical fairness and counts
    assert withiv.backend.calls == base.backend.calls                                 # same number of inhabitant decisions
    assert withiv.scheduler.data["totals"]["lfm_decisions"] == withiv.backend.calls   # attribution untouched by reflection calls
    for tick in (5, 10, 15):
        same = [i for i, e in enumerate(withiv.events) if e["world_tick"] == tick]
        refl = next(i for i in same if withiv.events[i]["type"] == "root_reflection")
        assert all(withiv.events[i]["source"] != "validated_action" for i in same if i > refl)


# ------------------------------------------------------- the shared real backend path (stand-ins only)
REFLECTION_REPLY = ("<tool_call>\n<function=RECORD_REFLECTION>\n<parameter=observations>Counts changed.</parameter>\n"
                    "<parameter=conclusions>Nothing is established.</parameter>\n<parameter=uncertainty>Cause unknown.</parameter>\n"
                    "<parameter=cites>{cite}</parameter>\n<parameter=proposal>advisory only</parameter>\n</function>\n</tool_call>")
HUMAN_REPLY = "<tool_call>\n<function=REST_FOR>\n<parameter=hours>1</parameter>\n</function>\n</tool_call>"


@pytest.fixture
def backend(monkeypatch):
    torch = types.SimpleNamespace(inference_mode=lambda: contextlib.nullcontext(), cuda=types.SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", torch)
    b = object.__new__(inference.TransformersLFM3Backend)
    b.model_revision, b.device, b.max_new_tokens, b.max_seconds, b.max_prompt_tokens = "test-rev", "cpu", 224, 15, 6144
    b.lock, b.calls, b.failures, b.output_tokens, b.elapsed_seconds, b.last_request = threading.Lock(), 0, 0, 0, 0, {}
    b.metadata = {"device": "stand-in"}
    b.tokenizer = FakeTokenizer()
    b.cite = "evt-000000004"
    b.model = FakeModel(lambda n: REFLECTION_REPLY.format(cite=b.cite) if b.tokenizer.prompts[-1]["tools"] == ["RECORD_REFLECTION"] else HUMAN_REPLY)
    return b


def test_one_shared_model_serves_inhabitants_and_isvara_with_isolated_contexts(backend):
    w = run(World(population=3, seed=3, backend=backend, autonomy=CONFIG, isvara_config={"reflect_every_ticks": 4}), 9)
    prompts = backend.tokenizer.prompts
    root = [p for p in prompts if p["tools"] == ["RECORD_REFLECTION"]]
    human = [p for p in prompts if p["tools"] != ["RECORD_REFLECTION"]]
    assert len(root) == 2 and len(human) == backend.calls > 0
    assert backend.model.calls == len(root) + len(human)                              # one model object served both
    assert all(p["messages"][0]["content"] == isvara.ISVARA_SYSTEM for p in root)
    assert all(p["messages"][0]["content"] == inference.system_message() for p in human)       # inhabitants' prompt is unchanged
    text = json.dumps(human).lower()
    assert "isvara" not in text and "reflection" not in text.replace('"reflect"', "") and "supervisory" not in text and "evidence" not in text
    m = backend.root_metrics()
    assert m["calls"] == 2 and m["failures"] == 0 and m["model_instances"] == 1 and m["prompt_tokens"]["max"] > 0
    assert backend.calls == w.scheduler.data["totals"]["lfm_decisions"] + w.scheduler.data["totals"]["failed_decisions"]
    r = isvara.role_state(w)["reflections"]["refl-000001"]
    assert r["source"] == "lfm" and r["cites"] == ["evt-000000004"] and r["request_id"] and w.root.data["isvara"]["totals"]["proposals"] == 2
    assert backend.last_request["request_id"] != r["request_id"]                      # reflection never overwrites attribution of a decision


def test_real_path_failures_are_contained(backend):
    backend.model.reply = lambda n: "no tool call at all" if backend.tokenizer.prompts[-1]["tools"] == ["RECORD_REFLECTION"] else HUMAN_REPLY
    w = run(World(population=3, seed=3, backend=backend, autonomy=CONFIG, isvara_config={"reflect_every_ticks": 4}), 6)
    st = isvara.role_state(w)
    assert st["totals"]["failures"] == 1 and st["totals"]["recorded"] == 0
    assert backend.root_metrics()["failures"] == 1 and backend.failures == 0           # inhabitant failure counters untouched
    tiny = run(World(population=3, seed=3, backend=backend, autonomy=CONFIG, isvara_config={"reflect_every_ticks": 4, "max_prompt_tokens": 1}), 6)
    assert isvara.role_state(tiny)["totals"]["failures"] == 1 and backend.root_metrics()["prompt_budget_failures"] == 1


def test_reflection_parser_rejects_anything_but_one_complete_call():
    ok = isvara.parse_reflection(REFLECTION_REPLY.format(cite="evt-000000001"))
    assert set(ok) == {"observations", "conclusions", "uncertainty", "cites", "proposal"}
    for bad in ("", REFLECTION_REPLY.format(cite="x") * 2, REFLECTION_REPLY.format(cite="x").replace("RECORD_REFLECTION", "MOVE"),
                REFLECTION_REPLY.format(cite="x").replace("<parameter=cites>x</parameter>", "<parameter=cites>x</parameter><parameter=cites>y</parameter>"),
                REFLECTION_REPLY.format(cite="x").replace("<parameter=proposal>", "<parameter=law>"),
                REFLECTION_REPLY.format(cite="x").replace("Counts changed.", "z" * 2000), "<tool_call>x" + "a" * 17000):
        with pytest.raises(ValueError):
            isvara.parse_reflection(bad)
    assert "RECORD_REFLECTION" not in {t["function"]["name"] for t in inference.TOOLS}   # inhabitants can never be offered it
