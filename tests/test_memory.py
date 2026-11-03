"""P2/P3: structured long-term memory, evidence status, revision, and cross-generational transmission."""
import json
import pytest
from conftest import IdleBackend
from test_physics_experiments import lab, do, pick, comp, make_fire, haft, CONFIG, dry_land
from caitanya import memory as mem
from caitanya.autonomy import AutonomyConfig
from caitanya.engine import World, Agent, Intent, digest
from caitanya.lifecycle import BiologyConfig, age
from caitanya.nature import RESOURCE_TYPES


def result_only(payload):
    """Payload without the confirmed-state evidence block added to every action (positions and needs only)."""
    return {k: v for k, v in payload.items() if k != "confirmed_state"}


def entry(a, category, **match):
    return next((e for e in a.ltm[category] if all(e.get(k) == v for k, v in match.items())), None)


def inspect_stone(w, a):
    oid = pick(w, a, "stone")
    ok, why, payload = do(w, a, "INSPECT", subject=oid)
    assert ok, why
    return payload


def neighbours(w, *agents):
    base = agents[0]
    for other in agents[1:]:
        other.x, other.z = base.x, base.z


# ------------------------------------------------------------- formation
def test_experiments_form_episodic_practical_and_procedural_memory():
    w, a = lab()
    dry_land(w)
    inspect_stone(w, a)
    hardness = entry(a, "practical", subject="stone", property="hardness")
    assert hardness["value"] == 6.5 and hardness["status"] == "observed" and hardness["origins"][0]["type"] == mem.OWN
    assert hardness["origins"][0]["event"].startswith("evt-")
    assert any("inspect" in e["text"] for e in a.ltm["episodic"])
    payload, _ = make_fire(w, a)
    assert payload["result"] == "ignited"
    steps = a.ltm["procedural"][-1]["steps"]
    assert steps[-1]["action"] == "RUB" and "obj-" not in json.dumps(a.ltm["procedural"])   # generalised, no ids
    assert entry(a, "episodic", importance=0.9)                                              # ignition was memorable


def test_repetition_corroborates_and_disagreement_is_recorded_as_variability():
    w, a = lab()
    for _ in range(3):
        inspect_stone(w, a)
    hardness = entry(a, "practical", subject="stone", property="hardness")
    assert hardness["status"] == "corroborated" and hardness["count"] == 3 and hardness["confidence"] > 0.75
    mem.learn_fact(w, a, {"subject": "stone", "property": "hardness", "value": 1.0}, {"type": mem.OWN, "tick": 1})
    assert entry(a, "practical", subject="stone", property="hardness")["status"] == "variable"
    assert entry(a, "practical", subject="stone", property="hardness")["revisions"]
    for outcome in ("chipped", "fractured", "fractured"):
        mem.learn_fact(w, a, {"subject": "s", "property": "strike_outcome", "value": outcome, "conditions": {"force": 4}},
                       {"type": mem.OWN, "tick": 1})
    e = entry(a, "practical", subject="s")
    assert e["status"] == "variable" and e["outcomes"] == {"chipped": 1, "fractured": 2} and e["value"] == "fractured"


def test_spatial_memory_recalls_where_water_was_seen():
    w, a = lab()
    a.thirst = 60
    mem.note_surroundings(w, a)
    sites = a.ltm["places"]["water"]
    a.x += 30
    w.resources = {k: v for k, v in w.resources.items() if v["kind"] != "water"}
    recalled = mem.recall(w, a)
    place = next(r for r in recalled if r["kind"] == "place")
    assert f"x={sites[0][0]}, z={sites[0][1]}" in place["text"] and "water" in place["text"]


def test_spatial_memory_forgets_sites_seen_to_be_empty_but_keeps_unseen_ones():
    w, a = lab()
    a.thirst = 60
    mem.note_surroundings(w, a)
    here = tuple(a.ltm["places"]["water"][0][:2])
    far = (a.x + 40, a.z)
    a.ltm["places"]["water"].append([far[0], far[1], 30, 0])                 # remembered, but far out of sight
    for node in w.resources.values():
        if node["kind"] == "water" and (node["x"], node["z"]) == here:
            node["amount"] = 0                                                  # emptied while the inhabitant watches
    mem.note_surroundings(w, a)
    sites = {tuple(s[:2]) for s in a.ltm["places"].get("water", [])}
    assert here not in sites and far in sites


# -------------------------------------------------------------- retrieval
def test_retrieval_is_relevant_deterministic_and_bounded():
    w, a = lab(stone=2)
    dry_land(w)
    w.resources = {k: v for k, v in w.resources.items() if k.startswith("spawn-")}
    for i in range(5):
        mem.learn_fact(w, a, {"subject": f"zorblax{i}", "property": "glow", "value": i}, {"type": mem.OWN, "tick": 0})
    mem.learn_fact(w, a, {"subject": "stone", "property": "hardness", "value": 6.5}, {"type": mem.OWN, "tick": 0})
    first, second = mem.recall(w, a), mem.recall(w, a)
    assert first == second and first[0]["text"].startswith("stone")
    # a flood of memories cannot grow the prompt
    for i in range(500):
        mem.learn_fact(w, a, {"subject": f"thing{i}", "property": "p", "value": i}, {"type": mem.OWN, "tick": i})
    cfg = w.autonomy.memory
    recalled = mem.recall(w, a)
    assert len(recalled) <= cfg.recall_items
    assert sum(len(r["text"]) for r in recalled) <= cfg.recall_chars
    assert len(a.ltm["practical"]) <= cfg.practical_limit
    observation = json.dumps(w.observe(a.id))
    assert len(observation) < 14000


def test_limits_evict_the_least_valuable_entries_first():
    config = AutonomyConfig.from_dict({"memory": {"practical_limit": 5}, "physiology": {"illness_per_day": 0}})
    w = World(population=2, backend=IdleBackend(), autonomy=config)
    a = w.agents["agent-0000"]
    for i in range(12):
        e = mem.learn_fact(w, a, {"subject": f"item{i}", "property": "p", "value": i}, {"type": mem.OWN, "tick": i})
        e["importance"] = 0.95 if i == 0 else 0.2
    kept = {e["subject"] for e in a.ltm["practical"]}
    assert len(kept) == 5 and "item0" in kept                      # high importance survives


# ----------------------------------------------- hypotheses and evidence
def test_hypotheses_are_private_unverified_and_need_matching_evidence():
    w, a = lab()
    dry_land(w)
    inspect_stone(w, a)
    ok, why, payload = do(w, a, "HYPOTHESIZE", statement="zxqv-private-idea: dull pieces make sharp ones", subject="stone")
    assert ok, why
    assert "zxqv" not in json.dumps(w.events) and "zxqv" not in json.dumps(w.public()) and result_only(payload) == {"result": "hypothesis_recorded"}
    hyp = a.ltm["hypotheses"][0]
    assert hyp["status"] == "unverified" and hyp["confidence"] == 0.3
    evidence = entry(a, "practical", subject="stone", property="hardness")
    assert do(w, a, "ASSESS", entry_id=hyp["id"], verdict="supported", evidence_id=evidence["id"])[0]
    assert hyp["status"] == "supported" and hyp["confidence"] == 0.5 and hyp["evidence"] == [evidence["id"]]
    for _ in range(4):
        do(w, a, "ASSESS", entry_id=hyp["id"], verdict="supported", evidence_id=evidence["id"])
    assert hyp["confidence"] == 0.8                                  # never certainty
    assert do(w, a, "ASSESS", entry_id=hyp["id"], verdict="contradicted", evidence_id=evidence["id"])[0]
    assert hyp["status"] == "contradicted" and hyp["confidence"] < 0.4 and hyp["revisions"][-1]["to"] == "contradicted"
    assert len(hyp["revisions"]) >= 2                                # the earlier belief remains traceable


def test_assessment_rejects_missing_unrelated_or_foreign_evidence():
    w, a = lab()
    inspect_stone(w, a)
    do(w, a, "INSPECT", subject="inventory:herbs")
    hyp = do(w, a, "HYPOTHESIZE", statement="glorp", subject="quartz")[0] and a.ltm["hypotheses"][0]
    before = digest(w.state())
    herbs = entry(a, "practical", subject="herbs", property="hardness")
    for params in (dict(entry_id="m-999999", verdict="supported", evidence_id=herbs["id"]),
                   dict(entry_id=hyp["id"], verdict="supported", evidence_id="m-999999"),
                   dict(entry_id=hyp["id"], verdict="supported", evidence_id=hyp["id"]),
                   dict(entry_id=hyp["id"], verdict="supported", evidence_id=herbs["id"]),
                   dict(entry_id=hyp["id"], verdict="proven", evidence_id=herbs["id"])):
        assert not do(w, a, "ASSESS", **params)[0], params
    assert digest(w.state()) == before
    other = w.agents["agent-0001"]
    mem.learn_fact(w, other, {"subject": "quartz", "property": "p", "value": 1}, {"type": mem.OWN, "tick": 0})
    foreign = other.ltm["practical"][0]["id"]
    assert not do(w, a, "ASSESS", entry_id=hyp["id"], verdict="supported", evidence_id=foreign)[0] or foreign in {e["id"] for e in a.ltm["practical"]}


def test_compare_returns_private_side_by_side_recall():
    w, a = lab()
    inspect_stone(w, a)
    do(w, a, "INSPECT", subject="inventory:wood")
    ok, _, payload = do(w, a, "COMPARE", first="stone", second="wood")
    assert ok and result_only(payload) == {"result": "compared", "entries": 6}
    rows = next(m for m in reversed(a.memories) if "comparison" in m)["comparison"]
    assert rows["stone"][0]["property"] in ("hardness", "density", "flexibility") and rows["wood"]
    assert not do(w, a, "COMPARE", first="", second="wood")[0]


# ------------------------------------------------- isolation and privacy
def test_memories_are_private_between_inhabitants_and_hidden_from_every_public_surface(tmp_path):
    from fastapi.testclient import TestClient
    from caitanya.server import create_app
    w, a = lab()
    b = w.agents["agent-0001"]
    b.x, b.z = a.x + 15, a.z
    inspect_stone(w, a)
    do(w, a, "HYPOTHESIZE", statement="zxqv-secret", subject="stone")
    assert not b.ltm or not b.ltm["practical"]
    assert "zxqv" not in json.dumps(w.observe(b.id)) and "ltm" not in w.observe(a.id)["self"]
    w.step()
    client = TestClient(create_app(w, tmp_path, live=False))
    for path in ("/api/v1/world/snapshot", "/api/v1/world/events", "/api/v1/history?from_tick=1&to_tick=1",
                 f"/api/v1/agents/{a.id}"):
        text = client.get(path).text
        assert "zxqv" not in text and '"ltm"' not in text and "brahman" not in text.lower(), path


def test_no_root_or_previous_life_information_is_ever_stored_or_recalled():
    w, a = lab()
    a.memories.append({"secret": "prior-life-belief"})
    inspect_stone(w, a)
    a.alive = False
    child = Agent("agent-0005", a.x, a.z, age_years_at_start=0)
    w.agents[child.id] = child
    w.next_agent_id = 6
    w.root.register(w)
    assert w.root.data["children"][child.id]["thread"] == w.root.data["children"][a.id]["thread"]   # continuity intact
    assert child.ltm == {} and child.memories == []
    blob = json.dumps(w.observe(child.id)) + json.dumps(mem.recall(w, child))
    assert "prior-life-belief" not in blob and "hardness" not in blob and "inspect" not in blob
    stored = json.dumps([x.ltm for x in w.agents.values()]).lower()
    for word in ("brahman", "continuity", "reincarnat", "karma", "veda"):
        assert word not in stored


def test_a_real_birth_starts_with_an_empty_memory_while_parents_keep_theirs():
    biology = BiologyConfig(days_per_tick=0.25, gestation_days=1, recovery_days=30)
    w = World(population=2, backend=IdleBackend(), biology=biology, autonomy=CONFIG)
    a, b = w.agents["agent-0000"], w.agents["agent-0001"]
    b.x, b.z = a.x, a.z
    a.reproductive_roles, b.reproductive_roles = ["gestate"], ["contribute"]
    for p in (a, b):
        p.inventory.update(food=12, water=12, stone=2)
        p.age_years_at_start = 25
    inspect_stone(w, a)
    assert w.apply(Intent(a.id, w.tick, "REPRODUCE", {"target_id": b.id}))[0]
    assert w.apply(Intent(b.id, w.tick, "REPRODUCE", {"target_id": a.id}))[0]
    for _ in range(6):
        w.step()
    child = next(x for x in w.agents.values() if x.generation == 1)
    assert child.ltm == {} and child.memories == [] and child.knowledge == []
    assert a.ltm["practical"]                                     # the parent still remembers


# ------------------------------------------------- witnessing and sharing
def test_nearby_inhabitants_witness_experiments_with_lower_confidence_and_provenance():
    w, a = lab()
    near, far = w.agents["agent-0001"], w.agents["agent-0002"]
    near.x, near.z = a.x + 1, a.z
    far.x, far.z = a.x + 12, a.z
    inspect_stone(w, a)
    seen = entry(near, "practical", subject="stone", property="hardness")
    own = entry(a, "practical", subject="stone", property="hardness")
    assert seen["origins"][0] == {"type": mem.WITNESSED, "source_agent": a.id, "event": own["origins"][0]["event"], "tick": w.tick}
    assert seen["confidence"] < own["confidence"] and seen["independent"] is False
    assert not far.ltm or not far.ltm["practical"]
    assert near.ltm["relationships"][a.id]["watched_experiments"] == 1


def test_shared_knowledge_is_a_claim_not_a_fact_until_the_receiver_tests_it():
    w, a = lab()
    b = w.agents["agent-0001"]
    b.x, b.z = a.x + 1, a.z
    b.inventory["stone"] = 2
    inspect_stone(w, a)
    true_claim = entry(a, "practical", subject="stone", property="hardness")
    b.ltm.clear()                                       # b only heard about it: forget the demonstration
    ok, why, payload = do(w, a, "SHARE_KNOWLEDGE", target_id=b.id, entry_id=true_claim["id"])
    assert ok, why
    heard = entry(b, "cultural", subject="stone", property="hardness")
    assert heard["status"] == "unverified" and heard["confidence"] <= 0.4 and heard["origin"]["source_agent"] == a.id
    assert not b.ltm["practical"] and payload["recipient_status"] == "unverified"
    inspect_stone(w, b)
    assert heard["status"] == "corroborated" and heard["revisions"][-1]["to"] == "corroborated"
    # a mistaken claim is revised once the receiver's own experience disagrees
    true_claim["value"] = 1.5
    c = w.agents["agent-0002"]
    c.x, c.z = a.x, a.z
    c.inventory["stone"] = 1
    assert do(w, a, "SHARE_KNOWLEDGE", target_id=c.id, entry_id=true_claim["id"])[0]
    wrong = entry(c, "cultural", subject="stone", property="hardness")
    c.ltm["practical"].clear()
    c.ltm["practical"] = c.ltm["practical"]
    inspect_stone(w, c)
    assert wrong["status"] == "contradicted" and wrong["confidence"] < 0.15 and wrong["revisions"][-1]["from"] == "unverified"


def test_sharing_validation_and_chain_of_transmission():
    w, a = lab()
    b, c = w.agents["agent-0001"], w.agents["agent-0002"]
    b.x, b.z, c.x, c.z = a.x, a.z, a.x, a.z
    inspect_stone(w, a)
    e = entry(a, "practical", subject="stone", property="hardness")
    before = digest(w.state())
    for params in (dict(target_id=b.id, entry_id="m-999999"), dict(target_id="nobody", entry_id=e["id"]),
                   dict(target_id=a.id, entry_id=e["id"]),
                   dict(target_id=b.id, entry_id=a.ltm["episodic"][0]["id"])):
        assert not do(w, a, "SHARE_KNOWLEDGE", **params)[0], params
    assert digest(w.state()) == before
    b.ltm.clear(); c.ltm.clear()
    assert do(w, a, "SHARE_KNOWLEDGE", target_id=b.id, entry_id=e["id"])[0]
    relayed = entry(b, "cultural", subject="stone", property="hardness")
    assert do(w, b, "SHARE_KNOWLEDGE", target_id=c.id, entry_id=relayed["id"])[0]
    second_hand = entry(c, "cultural", subject="stone", property="hardness")
    assert second_hand["origin"]["chain"] == [a.id, b.id] and second_hand["confidence"] < relayed["confidence"]
    c.x += 10
    assert not do(w, b, "SHARE_KNOWLEDGE", target_id=c.id, entry_id=relayed["id"])[0]


def test_free_text_teaching_is_recorded_as_unverified_hearsay_with_provenance():
    w, a = lab()
    b = w.agents["agent-0001"]
    b.x, b.z = a.x, a.z
    assert do(w, a, "TEACH", target_id=b.id, topic="stone", text="Pale stone breaks keenly.")[0]
    claim = b.ltm["cultural"][0]
    assert claim["status"] == "unverified" and claim["origin"] == {"type": mem.HEARSAY, "source_agent": a.id, "chain": [a.id], "tick": w.tick}
    assert b.ltm["relationships"][a.id]["taught_by"] == 1


def test_findings_written_by_one_generation_are_read_as_claims_by_the_next():
    w, a = lab()
    dry_land(w)
    child = Agent("agent-0007", a.x + 20, a.z, born_tick=0, age_years_at_start=0, generation=1, parent_ids=[a.id],
                  guardian_ids=[a.id], inventory={k: 0 for k in RESOURCE_TYPES}, adulthood_recorded=False)
    child.born_tick = w.tick - int(7 * 365 / w.biology.days_per_tick)            # seven years old
    child.inventory["stone"] = 2
    w.agents[child.id] = child
    w.next_agent_id = 8
    w.root.register(w)
    assert 6.9 < age(w, child) < 7.1
    inspect_stone(w, a)
    do(w, a, "HYPOTHESIZE", statement="zxqv-not-written", subject="stone")
    ids = [e["id"] for e in a.ltm["practical"]][:2]
    ok, why, payload = do(w, a, "WRITE_FINDINGS", title="What stone is like", entry_ids=",".join(ids))
    assert ok, why
    work = w.works[payload["work_id"]]
    assert len(work["claims"]) == 2 and "zxqv" not in json.dumps(work)
    a.alive = False                                                              # the author is gone
    child.x, child.z = work["x"], work["z"]
    assert w.apply(Intent(child.id, w.tick, "READ", {"work_id": work["id"]}))[0]
    claims = child.ltm["cultural"]
    assert len(claims) == 2 and all(c["status"] == "unverified" and c["origin"]["type"] == mem.WRITTEN
                                    and c["origin"]["author"] == a.id and c["origin"]["work_id"] == work["id"] for c in claims)
    assert not child.ltm["practical"] and not any("hypothes" in c["text"] for c in claims)
    inspect_stone(w, child)
    assert entry(child, "cultural", subject="stone", property="hardness")["status"] == "corroborated"
    assert entry(child, "cultural", subject="stone", property="hardness")["origin"]["author"] == a.id
    assert not child.ltm["hypotheses"] and all("zxqv" not in json.dumps(x) for x in (child.ltm, child.memories))


def test_findings_writing_validates_entries_and_energy():
    w, a = lab()
    inspect_stone(w, a)
    structured = a.ltm["practical"][0]["id"]
    episodic = a.ltm["episodic"][0]["id"]
    for params in (dict(title="t", entry_ids="m-9"), dict(title="", entry_ids=structured), dict(title="t", entry_ids=episodic),
                   dict(title="t", entry_ids=f"{structured},{structured}"), dict(title="t", entry_ids=",".join(["a"] * 6))):
        assert not do(w, a, "WRITE_FINDINGS", **params)[0], params


# ------------------------------------------------------- metrics, persistence
def test_knowledge_metrics_count_only_independent_reproduction():
    w, a = lab()
    b = w.agents["agent-0001"]
    b.x, b.z = a.x + 20, a.z
    b.inventory["stone"] = 1
    assert mem.knowledge_metrics(w)["independently_reproduced_findings"] == 0
    inspect_stone(w, a)
    assert mem.knowledge_metrics(w)["independently_reproduced_findings"] == 0
    inspect_stone(w, b)
    assert mem.knowledge_metrics(w)["independently_reproduced_findings"] == 3     # hardness, density, flexibility
    assert w.metrics()["knowledge"]["practical"] >= 6


def test_memory_survives_checkpoint_replay_and_journal_recovery(tmp_path):
    w, a = lab()
    w.checkpoint(tmp_path / "j")
    inspect_stone(w, a)
    do(w, a, "HYPOTHESIZE", statement="persisting idea", subject="stone")
    b = w.agents["agent-0001"]
    b.x, b.z = a.x, a.z
    do(w, a, "SHARE_KNOWLEDGE", target_id=b.id, entry_id=a.ltm["practical"][0]["id"])
    for _ in range(8):
        w.step()
    restored = World.restore(w.checkpoint(tmp_path / "c"), backend=IdleBackend())
    assert restored.agents[a.id].ltm == a.ltm and restored.agents[b.id].ltm == b.ltm
    for _ in range(5):
        w.step()
        restored.step()
    assert digest(restored.state()) == digest(w.state()) and digest(w.replay(w.tick)) == digest(w.state())
    (tmp_path / "j" / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in w.events), encoding="utf-8")
    recovered = World.recover(tmp_path / "j", backend=IdleBackend())
    assert recovered.agents[a.id].ltm == a.ltm and digest(recovered.state()) == digest(w.state())


class ScriptedExperimenter(IdleBackend):
    """Scripted (not an LLM): handles objects and examines them, so memory forms through the scheduler."""
    def decide(self, observation):
        self.calls += 1
        me, objs = observation["self"], observation.get("objects", [])
        held = [o for o in objs if o.get("held")]
        if not held and me["inventory"].get("stone", 0):
            action, params = "PICK", {"kind": "stone"}
        elif held:
            action, params = "INSPECT", {"subject": held[0]["id"]}
        else:
            action, params = "WAIT", {}
        return Intent(me["id"], observation["tick"], action, params, "")


def test_memory_works_through_the_scheduler_and_prompts_stay_bounded():
    w = World(population=4, backend=ScriptedExperimenter(), autonomy=CONFIG)
    for agent in w.agents.values():
        agent.inventory["stone"] = 3
    sizes = []
    for _ in range(60):
        w.step()
        sizes.append(len(json.dumps(w.observe("agent-0000"))))
    report = w.metrics()
    assert report["knowledge"]["practical"] > 0 and report["knowledge"]["recalls"] == w.scheduler.report(w)["totals"]["mock_decisions"]
    assert report["knowledge"]["recalled_items"] > 0
    assert max(sizes) < 14000                      # bounded no matter how long the run
    twin = World(population=4, backend=ScriptedExperimenter(), autonomy=CONFIG)
    for agent in twin.agents.values():
        agent.inventory["stone"] = 3
    for _ in range(60):
        twin.step()
    assert digest(twin.state()) == digest(w.state())
