"""The water ladder harness: a fixed, honest fixture, a clear pass condition, bounded, text-free. (Mock policy: this tests the harness, not the model.)"""
import importlib.util
import json
import sys
from pathlib import Path
import pytest
from conftest import IdleBackend

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("scenario_ladder", ROOT / "scripts" / "scenario_ladder.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["scenario_ladder"] = mod
spec.loader.exec_module(mod)


def args(tmp_path, *extra):
    return mod.build_parser().parse_args(["--out", str(tmp_path / "o.json"), *extra])


def test_the_fixture_has_one_water_node_at_the_requested_distance_and_a_thirsty_group_that_starts_together(tmp_path):
    for name, (distance, sight) in mod.RUNGS.items():
        a = args(tmp_path)
        w, node = mod.build(a, IdleBackend(), distance, sight)
        assert list(w.resources) == [mod.NODE_ID] and w.resources[mod.NODE_ID]["kind"] == "water" and w.resources[mod.NODE_ID]["amount"] == 40
        humans = list(w.agents.values())
        assert len(humans) == 5 and all(h.thirst == 60 and h.inventory["water"] == 0 for h in humans)
        d = [mod.manhattan((h.x, h.z), node) for h in humans]
        assert max(abs(x - distance) for x in d) <= 6 and w.terrain_at(*node)["walkable"], (name, d)
        in_sight = sum(1 for h in humans if any(n["id"] == mod.NODE_ID for n in w.observe(h.id)["resources"]))
        assert (in_sight == 0) if name == "R4" else (in_sight == 5), (name, in_sight)


def test_a_policy_that_does_nothing_passes_no_rung_and_nobody_is_counted_for_choosing_a_tool(tmp_path):
    record, code = mod.run(args(tmp_path, "--ticks", "6", "--rungs", "R0,R2"), backend=IdleBackend())
    assert code == 0 and [r["PASS_humans_who_drank"] for r in record["results"]] == [0, 0]
    assert all(r["humans_who_reached_the_node"] == 0 or r["rung"] == "R0" for r in record["results"])


def test_the_mock_policy_passes_the_rungs_where_the_water_is_in_sight_and_not_the_unseen_one(tmp_path):
    record, _ = mod.run(args(tmp_path, "--ticks", "40", "--rungs", "R0,R1,R2,R4"))
    by = {r["rung"]: r for r in record["results"]}
    assert by["R0"]["pass_fraction"] == 1.0 and by["R1"]["pass_fraction"] == 1.0 and by["R2"]["pass_fraction"] == 1.0
    assert by["R4"]["PASS_humans_who_drank"] == 0 and by["R4"]["node_in_sight_of_humans_at_start"] == 0
    for r in by.values():
        assert r["humans_who_gathered_water"] >= r["PASS_humans_who_drank"] and r["thirst_mean"]["end"] <= 60 + 1 or r["rung"] == "R4"


def test_the_record_has_counts_only_and_without_a_gpu_the_real_model_is_reported_unverified(tmp_path):
    record, _ = mod.run(args(tmp_path, "--ticks", "3", "--rungs", "R1"))
    blob = json.dumps(record)
    for word in ("memories", "feedback", "<tool_call>", "<function="):
        assert word not in blob
    nogpu, code = mod.run(args(tmp_path, "--backend", "lfm3"))
    if nogpu["environment"]["gpu"] is None:
        assert code == 2 and nogpu["status"] == "unverified_no_gpu" and "results" not in nogpu


def test_limits_stop_a_rung_and_unknown_rungs_are_refused(tmp_path):
    record, _ = mod.run(args(tmp_path, "--ticks", "30", "--rungs", "R0", "--max-real-seconds", "0"))
    assert record["results"][0]["stop"] == "stopped_at_wall_clock_limit" and record["status"] == "partial"
    with pytest.raises(SystemExit):
        mod.run(args(tmp_path, "--rungs", "R9"))


class Scripted:
    """Stand-in 'model' that makes the mistakes we want the ladder to explain."""
    model_id, model_revision, metadata = "fake/real", "fake", {}

    def __init__(self, behaviour):
        self.behaviour, self.calls, self.last_request = behaviour, 0, {"request_id": "r"}

    def decide(self, observation):
        from caitanya.engine import Intent
        self.calls += 1
        me = observation["self"]
        if self.behaviour == "wrong_id":
            return Intent(me["id"], observation["tick"], "GATHER_AT", {"resource_id": "resource-0001", "amount": 2}, "")
        if self.behaviour == "big_amount":
            return Intent(me["id"], observation["tick"], "GATHER_AT", {"resource_id": mod.NODE_ID, "amount": 20}, "")
        if self.behaviour == "drink_dry":
            return Intent(me["id"], observation["tick"], "DRINK", {}, "")
        return Intent(me["id"], observation["tick"], "WAIT", {}, "")


def test_the_ladder_explains_why_a_choice_did_not_work(tmp_path):
    def why(behaviour):
        record, _ = mod.run(args(tmp_path, "--ticks", "4", "--rungs", "R0"), backend=Scripted(behaviour))
        return record["results"][0]["why"], record["results"][0]
    w, r = why("wrong_id")
    assert w["gather_at_names_another_id"] > 0 and w["gather_at_names_the_water_node"] == 0 and r["PASS_humans_who_drank"] == 0
    assert w["rejections_by_reason"].get("resource unavailable", 0) > 0
    w, _ = why("big_amount")
    assert w["gather_at_names_the_water_node"] > 0 and w["gather_at_amount_out_of_range"] > 0 and w["rejections_by_reason"].get("invalid amount", 0) > 0
    w, _ = why("drink_dry")
    assert w["chosen_not_offered"].get("DRINK", 0) > 0 and w["drink_chosen_without_water"] > 0 and w["drink_chosen_with_water_carried"] == 0
    w, _ = why("wait")
    assert w["decisions_with_the_node_in_sight"] > 0 and w["water_node_units_left"] == 40


def test_the_node_id_can_be_changed_and_the_scripted_tests_follow_it(tmp_path):
    record, _ = mod.run(args(tmp_path, "--ticks", "25", "--rungs", "R1", "--node-id", "resource-0001"))
    assert record["requested"]["node_id"] == "resource-0001" and record["results"][0]["PASS_humans_who_drank"] == 5
