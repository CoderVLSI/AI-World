"""P0: fair budgeted scheduling, LFM-versus-mechanical attribution, bounded and cancelable intentions."""
import copy
import math
import pytest
from conftest import FakeLFM, IdleBackend
from caitanya import engine as engine_module
from caitanya.autonomy import AutonomyConfig
from caitanya.engine import World, Intent, digest, MockInferenceBackend
from caitanya.scheduler import find_path


def make(n, backend=None, budget=8, **scheduler):
    config = AutonomyConfig.from_dict({"scheduler": {"max_decisions_per_tick": budget, **scheduler}})
    return World(population=n, backend=backend or IdleBackend(), autonomy=config)


def reachable_resource(w, a, low=4, high=12):
    for node in sorted(w.resources.values(), key=lambda n: n["id"]):
        distance = abs(node["x"] - a.x) + abs(node["z"] - a.z)
        if low <= distance <= high and node["amount"] > 0 and \
                find_path(w, (a.x, a.z), (node["x"], node["z"]), 5000, 150):
            return node
    raise AssertionError("fixture world has no suitable resource")


# ---------------------------------------------------------------- fairness
def test_five_inhabitants_each_decide_every_tick_when_budget_allows():
    w = make(5)
    for _ in range(30):
        w.step()
    report = w.scheduler.report(w)
    assert report["decisions_per_agent"] == {"min": 30, "max": 30, "mean": 30}
    assert report["max_wait_ticks"] == 0 and report["mean_decision_interval_ticks"]["max"] == 1


def test_fifty_inhabitants_share_a_budget_fairly_with_bounded_waiting():
    w = make(50, budget=8)
    for _ in range(105):
        w.step()
    report = w.scheduler.report(w)
    assert w.backend.calls == 8 * 105
    spread = report["decisions_per_agent"]
    assert spread["max"] - spread["min"] <= 1, spread          # strict rotation
    assert report["max_wait_ticks"] <= math.ceil(50 / 8)       # bounded waiting
    assert report["max_interval_ticks"] <= math.ceil(50 / 8) + 1
    assert report["totals"]["budget_exhausted_ticks"] > 0      # demand really exceeded the budget


def test_extreme_overload_still_serves_everyone():
    w = make(50, budget=1)
    for _ in range(150):
        w.step()
    report = w.scheduler.report(w)
    assert report["decisions_per_agent"]["min"] >= 2
    assert report["max_wait_ticks"] <= 50


def test_priority_order_overdue_then_interrupted_then_normal():
    w = make(6)
    ids = sorted(w.agents)
    w.apply(Intent(ids[1], 0, "REST_FOR", {"hours": 4}))      # has a task, so only a wake makes it due
    w.scheduler.record(ids[1])["wake"] = "health_deteriorated"
    w.tick = 200
    w.scheduler.record(ids[2])["due_since"] = 0                # waited far beyond max_wait_ticks
    queue = w.scheduler._due(w)
    order = [aid for *_, aid in queue]
    assert order[0] == ids[2] and order[1] == ids[1]
    assert {q[0] for q in queue} == {0, 1, 2}


def test_budget_is_configurable_and_recorded_in_manifest():
    w = make(10, budget=3)
    w.step()
    assert w.backend.calls == 3
    assert w.manifest["autonomy"]["scheduler"]["max_decisions_per_tick"] == 3
    assert len(w.manifest["autonomy_hash"]) == 64


# ------------------------------------------------- LFM versus mechanical
def test_mechanical_steps_are_never_counted_as_decisions():
    w = World(population=5)                                    # default mock uses bounded intentions
    for _ in range(150):
        w.step()
    totals = w.scheduler.report(w)["totals"]
    assert totals["mock_decisions"] == w.backend.calls and totals["lfm_decisions"] == 0
    assert totals["mechanical_steps"] > totals["mock_decisions"]
    mech = [e for e in w.events if e.get("origin") == "mechanical_execution" and e["source"] == "validated_action"]
    assert len(mech) == totals["mechanical_steps"]
    assert all(e.get("task_id") and "model_request_id" not in e for e in mech)
    started = [e for e in w.events if e["type"] in ("gather_at", "rest_for", "travel_to")]
    assert started and all(e["origin"] == "mock_policy" and e["payload"]["task_id"] for e in started)


def test_lfm_decisions_are_attributed_and_mock_is_never_labelled_lfm():
    def chooser(obs):
        me = obs["self"]
        nodes = [n for n in obs["resources"] if n["amount"] > 0 and (n["x"], n["z"]) != (me["x"], me["z"])]
        if not nodes:
            return Intent(me["id"], obs["tick"], "WAIT", {}, "")
        n = min(nodes, key=lambda n: (abs(n["x"] - me["x"]) + abs(n["z"] - me["z"]), n["id"]))
        return Intent(me["id"], obs["tick"], "GATHER_AT", {"resource_id": n["id"], "amount": 1}, "need supplies")
    backend = FakeLFM(chooser)
    w = World(population=3, backend=backend)
    for _ in range(20):
        w.step()
    totals = w.scheduler.report(w)["totals"]
    assert totals["lfm_decisions"] == backend.calls > 0 and totals["mock_decisions"] == 0
    decisions = [e for e in w.events if e["type"] == "gather_at"]
    assert decisions and all(e["origin"] == "lfm_decision" and e["model_request_id"].startswith("req-") for e in decisions)
    assert totals["mechanical_steps"] > 0
    for _ in range(10):
        if any(a.task for a in w.agents.values()):
            break
        w.step()
    task_agent = next(a for a in w.agents.values() if a.task)
    assert task_agent.task["selected_by"]["origin"] == "lfm_decision"
    assert all(e.get("origin") != "lfm_decision" for e in w.events if e.get("origin") == "mechanical_execution")


def test_model_failure_never_substitutes_a_mock_decision():
    backend = FakeLFM(fail_for={"agent-0000"})
    w = World(population=3, backend=backend)
    start = (w.agents["agent-0000"].x, w.agents["agent-0000"].z)
    for _ in range(30):
        w.step()
    mine = [e for e in w.events if e["actor_id"] == "agent-0000"]
    assert {e["type"] for e in mine} <= {"intent_rejected", "inference_failed"}
    assert (w.agents["agent-0000"].x, w.agents["agent-0000"].z) == start
    failures = sum(e["type"] == "inference_failed" and e["actor_id"] == "agent-0000" for e in w.events)
    assert 2 <= failures <= 5                                  # exponential-ish backoff, not a tight loop
    assert w.backend is backend and w.scheduler.report(w)["totals"]["failed_decisions"] >= failures
    assert w.scheduler.record("agent-0001")["decisions"] >= 25  # other inhabitants are unaffected


# --------------------------------------------- bounded and obsolete plans
def start_gather(w, aid="agent-0000", amount=2):
    a = w.agents[aid]
    node = reachable_resource(w, a)
    assert w.apply(Intent(aid, w.tick, "GATHER_AT", {"resource_id": node["id"], "amount": amount}))[0]
    return a, node


def test_gather_at_executes_mechanically_then_completes():
    w = make(3)
    a, node = start_gather(w, amount=2)
    assert a.task and a.task["kind"] == "GATHER_AT"
    before = a.inventory[node["kind"]]
    for _ in range(40):
        w.step()
        if not a.task:
            break
    assert a.task is None
    assert a.inventory[node["kind"]] == before + 2
    assert any(e["type"] == "task_completed" for e in w.events)


def test_vanished_resource_interrupts_and_triggers_priority_redecision():
    w = make(3)
    a, node = start_gather(w)
    w.step()
    node["amount"] = 0
    calls = w.backend.calls
    w.step()
    assert a.task is None
    interrupted = [e for e in w.events if e["type"] == "task_interrupted"]
    assert interrupted[-1]["payload"]["reason"] == "resource_unavailable"
    assert w.scheduler.report(w)["totals"]["tasks_interrupted"]["resource_unavailable"] == 1
    w.step()
    assert w.backend.calls > calls and w.scheduler.record(a.id)["wake"] is None  # asked again


def test_blocked_route_replans_a_bounded_number_of_times_then_stops(monkeypatch):
    w = make(3)
    a, node = start_gather(w)
    next_tile = tuple(a.task["path"][0])
    real = engine_module.geography
    monkeypatch.setattr(engine_module, "geography",
                        lambda x, z, *rest: dict(real(x, z, *rest), walkable=False) if (x, z) == next_tile else real(x, z, *rest))
    for _ in range(6):
        w.step()
    assert a.task is None
    reasons = [e["payload"]["reason"] for e in w.events if e["type"] == "task_interrupted"]
    assert reasons and reasons[0].startswith("path_blocked")


@pytest.mark.parametrize("mutate,reason", [
    (lambda w, a: setattr(a, "health", a.health - 30), "health_deteriorated"),
    (lambda w, a: setattr(a, "thirst", 90), "thirst_critical"),
    (lambda w, a: setattr(a, "hunger", 90), "hunger_critical"),
    (lambda w, a: setattr(a, "illness", {"since_tick": 0, "until_tick": 999}), "illness_started"),
    (lambda w, a: a.task.update(expires_tick=w.tick), "time_limit"),
])
def test_material_change_ends_the_intention(mutate, reason):
    w = make(3)
    a = w.agents["agent-0000"]
    assert w.apply(Intent(a.id, w.tick, "REST_FOR", {"hours": 8}))[0]
    mutate(w, a)
    w.step()
    assert a.task is None
    assert [e["payload"]["reason"] for e in w.events if e["type"] == "task_interrupted"][-1] == reason


def test_already_critical_need_does_not_cause_interrupt_thrashing():
    w = make(3)
    a = w.agents["agent-0000"]
    a.thirst = 92
    assert w.apply(Intent(a.id, w.tick, "REST_FOR", {"hours": 2}))[0]
    for _ in range(3):
        w.step()
    assert not any(e["type"] == "task_interrupted" and e["payload"]["reason"] == "thirst_critical" for e in w.events)


def test_no_intention_outlives_its_bound():
    w = World(population=12)
    for _ in range(250):
        w.step()
    cap = w.autonomy.scheduler.max_task_ticks
    began = {e["payload"]["task_id"]: e["world_tick"] for e in w.events
             if e["type"] in ("gather_at", "rest_for", "travel_to")}
    ended = {e["payload"]["task_id"]: e["world_tick"] for e in w.events if e["type"].startswith("task_")}
    assert began and ended
    assert all(ended[t] - began[t] <= cap for t in ended)
    assert all(a.task is None or w.tick - a.task["created_tick"] <= cap for a in w.agents.values())


def test_explicit_cancel_and_supersede():
    w = make(3)
    a = w.agents["agent-0000"]
    assert w.apply(Intent(a.id, w.tick, "REST_FOR", {"hours": 4}))[0]
    assert w.apply(Intent(a.id, w.tick, "CANCEL_TASK", {}))[0] and a.task is None
    assert not w.apply(Intent(a.id, w.tick, "CANCEL_TASK", {}))[0]         # nothing to cancel
    assert w.apply(Intent(a.id, w.tick, "REST_FOR", {"hours": 4}))[0]
    assert w.apply(Intent(a.id, w.tick, "REST_FOR", {"hours": 2}))[0]       # replaces, journaling the first
    types = [e["type"] for e in w.events]
    assert "task_cancelled" in types and "task_superseded" in types
    totals = w.scheduler.report(w)["totals"]
    assert totals["tasks_cancelled"] == 1 and totals["tasks_superseded"] == 1


def test_a_decision_made_while_a_task_runs_supersedes_it():
    w = make(3)
    a = w.agents["agent-0000"]
    w.apply(Intent(a.id, w.tick, "REST_FOR", {"hours": 12}))
    a.task["reconsider_tick"] = w.tick + 1
    w.step()
    w.step()
    assert a.task is None and any(e["type"] == "task_superseded" for e in w.events)


def test_invalid_intentions_are_rejected_without_mutation():
    w = make(3)
    a = w.agents["agent-0000"]
    bad = [("TRAVEL_TO", {"x": -5, "z": 20}), ("TRAVEL_TO", {"x": 10.5, "z": 20}), ("TRAVEL_TO", {"x": 10}),
           ("TRAVEL_TO", {"x": 10, "z": 10, "code": "x"}), ("TRAVEL_TO", {"x": a.x, "z": a.z}),
           ("TRAVEL_TO", {"x": 10, "z": 1}), ("GATHER_AT", {"resource_id": "missing", "amount": 1}),
           ("GATHER_AT", {"resource_id": "resource-0000", "amount": 0}),
           ("GATHER_AT", {"resource_id": "resource-0000", "amount": 99}),
           ("REST_FOR", {"hours": 0}), ("REST_FOR", {"hours": 13}), ("REST_FOR", {"hours": "5"}),
           ("TRAVEL_TO", {"x": 5, "z": 5, "reconsider_hours": 0}), ("CANCEL_TASK", {})]
    before = digest(w.state())
    for action, params in bad:
        assert not w.apply(Intent(a.id, w.tick, action, params))[0], (action, params)
    assert digest(w.state()) == before


def test_legacy_worlds_reject_the_new_actions():
    w = World(autonomy="legacy")
    assert not w.apply(Intent("agent-0000", 0, "REST_FOR", {"hours": 2}))[0]


def test_survival_reflex_is_off_by_default_and_attributed_when_enabled():
    w = make(3)
    a = w.agents["agent-0000"]
    a.thirst = 95
    w.step()
    assert a.inventory["water"] == 3 and w.scheduler.report(w)["totals"]["reflex_interventions"] == 0
    config = AutonomyConfig.from_dict({"reflex": {"enabled": True, "drink_at": 90}})
    w = World(population=3, backend=IdleBackend(), autonomy=config)
    w.agents["agent-0000"].thirst = 95
    w.step()
    drinks = [e for e in w.events if e["type"] == "drink"]
    assert w.agents["agent-0000"].inventory["water"] == 2
    assert drinks and drinks[0]["origin"] == "survival_reflex"
    assert w.scheduler.report(w)["totals"]["reflex_interventions"] == 1
    assert w.scheduler.report(w)["totals"]["mock_decisions"] == w.backend.calls  # reflex is not a decision


# ------------------------------------------- durability and determinism
def test_scheduler_state_survives_checkpoint_replay_and_journal_recovery(tmp_path):
    w = World(population=8)
    for _ in range(45):
        w.step()
    assert any(a.task for a in w.agents.values())              # checkpoint lands mid-intention
    restored = World.restore(w.checkpoint(tmp_path / "ck"))
    assert restored.scheduler.state() == w.scheduler.state()
    for _ in range(40):
        w.step()
        restored.step()
    assert digest(w.state()) == digest(restored.state())
    assert digest(w.events) == digest(restored.events)
    assert digest(w.replay(w.tick)) == digest(w.state())
    assert digest(w.replay(45)) == digest(World.restore(next((tmp_path / "ck").glob("*.json"))).state())

    base = World(population=8)
    base.checkpoint(tmp_path / "jr")
    for _ in range(30):
        base.step()
    (tmp_path / "jr" / "events.jsonl").write_text(
        "".join(__import__("json").dumps(e) + "\n" for e in base.events), encoding="utf-8")
    recovered = World.recover(tmp_path / "jr")
    assert digest(recovered.state()) == digest(base.state())
    assert recovered.scheduler.state() == base.scheduler.state()
    recovered.step()
    base.step()
    assert digest(recovered.state()) == digest(base.state())


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_runs_are_deterministic_across_seeds(seed):
    a, b = World(seed=seed, population=6), World(seed=seed, population=6)
    for _ in range(80):
        a.step()
        b.step()
    assert digest(a.events) == digest(b.events) and digest(a.state()) == digest(b.state())
