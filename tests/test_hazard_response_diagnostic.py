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
    assert "SPEAK" not in json.dumps(r["fleeing_stand_in"]["choices_while_inside"]) and '"text"' not in out.read_text()      # choices are tool names only


def test_without_a_gpu_the_real_model_mode_says_so_and_runs_nothing(tmp_path):
    out = tmp_path / "r.json"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "hazard_response_diagnostic.py"), "--backend", "lfm3", "--out", str(out)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 2
    assert json.loads(out.read_text())["status"] == "unverified_no_gpu"
