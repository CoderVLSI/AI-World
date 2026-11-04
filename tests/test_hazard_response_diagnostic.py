"""The hazard-response diagnostic's CPU mode (scripted stand-ins only) and its honest no-GPU record."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_cpu_mode_measures_staying_versus_leaving_and_writes_no_text(tmp_path):
    out = tmp_path / "r.json"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "hazard_response_diagnostic.py"), "--backend", "cpu", "--ticks", "40", "--out", str(out)],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[-500:]
    r = json.loads(out.read_text())
    idle, flee = r["idle_stand_in"], r["fleeing_stand_in"]
    assert idle["fixture"]["inhabitants_inside_at_start"] and idle["fixture"]["force"] == "wildfire" and idle["fixture"]["hazard_ticks"] == 36
    assert idle["left_count"] == 0 and set(idle["choices_while_inside"]) == {"WAIT"} and idle["move_choices_while_inside"] == 0
    assert min(idle["lowest_health"].values()) < 100 and min(idle["lowest_health"].values()) >= 1 and idle["alive"] == 5     # hurt, never killed
    assert flee["left_count"] >= 1 and flee["move_choices_while_inside"] >= 1 and flee["hazard_visible_in_observations"] > 0
    assert min(flee["lowest_health"].values()) >= min(idle["lowest_health"].values())              # leaving cannot be worse than staying
    assert idle["hazard_summary_recorded"] and idle["decision_failures"] == 0
    # v2: move directions and trajectories are recorded as numbers; the hint variant is a separate, labelled run
    assert idle["variant"] == "baseline" and idle["exit_hint_visible_in_observations"] == 0 and idle["moves_while_inside"]["total"] == 0
    hint = r["hint_following_stand_in"]
    assert hint["variant"] == "exit_hint" and hint["exit_hint_visible_in_observations"] > 0 and hint["left_count"] == hint["inside_count_at_start"]
    assert hint["moves_while_inside"]["inward"] == 0 and hint["moves_while_inside"]["outward"] == hint["moves_while_inside"]["total"] > 0
    assert flee["moves_while_inside"]["total"] == flee["moves_while_inside"]["outward"] + flee["moves_while_inside"]["inward"]
    assert flee["exit_hint_visible_in_observations"] == 0                                # the baseline never shows the hint
    # v3: the pain and direction-word variants are separate, labelled runs; malformed moves are counted
    pain, both = r["pain_following_stand_in"], r["pain_and_walk_stand_in"]
    assert pain["variant"] == "pain_signal" and both["variant"] == "pain_signal+walk_by_direction"
    assert pain["pain_signal_visible_in_observations"] > 0 and both["pain_signal_visible_in_observations"] > 0
    assert idle["pain_signal_visible_in_observations"] == 0 and hint["pain_signal_visible_in_observations"] == 0       # off unless asked for
    assert pain["left_count"] == pain["inside_count_at_start"] == both["left_count"]
    assert set(pain["choices_while_inside"]) == {"MOVE"} and set(both["choices_while_inside"]) == {"WALK"}           # WALK replaces MOVE
    assert all(e["malformed_moves_chosen_anywhere"] == 0 and e["moves_chosen_anywhere"] >= e["moves_while_inside"]["total"]
               for e in (idle, flee, hint, pain, both))
    trace = hint["distance_to_zone_edge_by_tick"]
    assert set(trace) == set(hint["fixture"]["inhabitants_inside_at_start"]) and all(len(v) == 40 and v[0] == 0 for v in trace.values())
    assert "SPEAK" not in json.dumps(r["fleeing_stand_in"]["choices_while_inside"]) and '"text"' not in out.read_text()      # choices are tool names only


def test_without_a_gpu_the_real_model_mode_says_so_and_runs_nothing(tmp_path):
    out = tmp_path / "r.json"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "hazard_response_diagnostic.py"), "--backend", "lfm3", "--out", str(out)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 2
    assert json.loads(out.read_text())["status"] == "unverified_no_gpu"
