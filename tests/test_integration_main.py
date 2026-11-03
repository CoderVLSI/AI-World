"""Integration with the owner's root modes and sanitized evidence export (merged from main)."""
import json
import pytest
from conftest import IdleBackend
from test_physics_experiments import lab, do, haft, dry_land, CONFIG
from test_memory import ScriptedExperimenter, inspect_stone
from caitanya.engine import World, Intent, digest
from caitanya.experiment import summarize


@pytest.mark.parametrize("mode", ["off", "observe", "crisis"])
def test_every_root_mode_runs_with_scheduler_experiments_memory_and_recovery(mode, tmp_path):
    w = World(population=4, backend=ScriptedExperimenter(), root_mode=mode, autonomy=CONFIG)
    for agent in w.agents.values():
        agent.inventory["stone"] = 3
    w.checkpoint(tmp_path)
    for _ in range(70):
        w.step()
    assert w.metrics()["knowledge"]["practical"] > 0
    assert bool(w.root.data["children"]) == (mode != "off")
    assert not w.root.data["manifestations"]                        # nobody was in crisis
    assert digest(w.replay(w.tick)) == digest(w.state())
    (tmp_path / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in w.events), encoding="utf-8")
    recovered = World.recover(tmp_path, backend=ScriptedExperimenter())
    assert digest(recovered.state()) == digest(w.state()) and recovered.root.data["mode"] == mode
    restored = World.restore(w.checkpoint(tmp_path / "c"), backend=ScriptedExperimenter())
    assert restored.root.data["mode"] == mode


def test_crisis_manifestation_still_happens_under_time_based_physiology():
    w = World(population=3, backend=IdleBackend(), root_mode="crisis", autonomy=CONFIG)
    for a in w.agents.values():
        a.hunger = 90
    w.step()
    assert len(w.root.data["manifestations"]) == 1
    assert len(World(population=3, backend=IdleBackend(), root_mode="observe", autonomy=CONFIG).root.data["manifestations"]) == 0


def test_confirmed_state_is_recorded_for_decisions_but_not_for_routine_mechanical_steps():
    w = World(population=3)
    for _ in range(30):
        w.step()
    decisions = [e for e in w.events if e["source"] == "validated_action" and e.get("origin") == "mock_policy"]
    mechanical = [e for e in w.events if e["source"] == "validated_action" and e.get("origin") == "mechanical_execution"]
    assert decisions and mechanical
    assert all("confirmed_state" in e["payload"] for e in decisions)
    assert not any("confirmed_state" in e["payload"] for e in mechanical)
    direct = World()
    direct.apply(Intent("agent-0000", 0, "REST"))
    state = direct.events[-1]["payload"]["confirmed_state"]
    assert set(state) == {"before", "after"} and state["after"]["energy"] >= state["before"]["energy"]


def test_evidence_export_stays_sanitized_with_experiments_and_private_memory(tmp_path):
    w, a = lab()
    dry_land(w)
    inspect_stone(w, a)
    do(w, a, "HYPOTHESIZE", statement="zxqv-private-hypothesis", subject="stone")
    do(w, a, "ASSESS", entry_id=a.ltm["hypotheses"][0]["id"], verdict="uncertain", evidence_id=a.ltm["practical"][0]["id"])
    do(w, a, "COMPARE", first="stone", second="wood")
    ids = ",".join(e["id"] for e in a.ltm["practical"][:2])
    do(w, a, "WRITE_FINDINGS", title="Observations of stone", entry_ids=ids)
    haft(w, a)
    for _ in range(3):
        w.step()
    result = summarize(w, tmp_path, {"commit_sha": "test"})
    text = (tmp_path / "evidence.json").read_text() + (tmp_path / "REPORT.md").read_text()
    assert "zxqv" not in text and '"ltm"' not in text and "continuity-" not in text and "brahman" not in text.lower()
    assert ids.split(",")[0] not in text                              # opaque private memory ids are not published either
    assert result["classification"] == "mock-or-test" and result["verified_real_agent_ids"] == []
    assert any(act["action"] == "strike" for act in result["actions"]) and result["works"]
