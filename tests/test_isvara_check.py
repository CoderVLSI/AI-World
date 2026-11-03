"""The bounded Isvara check script: its tracing helps locate where two worlds first differ (mock only here)."""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("isvara_check", ROOT / "scripts" / "isvara_check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def trace(states, calls):
    return [{"tick": i + 1, "state": s, "inhabitant_calls": c} for i, (s, c) in enumerate(zip(states, calls))]


def test_divergence_reports_the_first_tick_that_differs_in_state_and_in_calls():
    a = trace(["a", "b", "c", "d"], [5, 5, 5, 5])
    assert check.divergence(a, a) == {"first_tick_state_differs": None, "first_tick_inhabitant_calls_differ": None, "ticks_compared": 4}
    b = trace(["a", "b", "X", "Y"], [5, 5, 4, 5])
    assert check.divergence(a, b) == {"first_tick_state_differs": 3, "first_tick_inhabitant_calls_differ": 3, "ticks_compared": 4}
    c = trace(["a", "b", "c", "Z"], [5, 5, 5, 5])
    assert check.divergence(a, c)["first_tick_state_differs"] == 4 and check.divergence(a, c)["first_tick_inhabitant_calls_differ"] is None
    assert check.divergence(a, a[:2])["ticks_compared"] == 2


def test_mock_run_with_control_twice_and_trace_writes_only_hashes_counts_and_seconds(tmp_path):
    out = tmp_path / "r.json"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "isvara_check.py"), "--backend", "mock", "--population", "4", "--ticks", "30",
                           "--reflect-every", "10", "--control", "--twice", "--trace", "--out", str(out)], capture_output=True, text=True, timeout=240)
    assert done.returncode == 0, done.stderr[-500:]
    r = json.loads(out.read_text())
    t = r["trace"]
    assert t["reflection_attempt_ticks"] == [10, 20, 30] and set(t["worlds"]) == {"off", "off_control", "on", "on_second"}
    assert all(len(v) == 30 for v in t["worlds"].values())
    assert all(re.fullmatch(r"[0-9a-f]{16}", x["state"]) and set(x) == {"tick", "state", "inhabitant_calls", "seconds", "reflection_seconds"}
               for v in t["worlds"].values() for x in v)
    # the mock is deterministic, and reflection must not change the world: no divergence anywhere
    assert all(d["first_tick_state_differs"] is None and d["first_tick_inhabitant_calls_differ"] is None for d in t["divergence"].values())
    assert set(t["divergence"]) == {"off_vs_off_control", "off_vs_on", "off_control_vs_on", "on_vs_on_second"}
    assert r["second_reflecting_world"]["physical_state_identical_to_first_reflecting_world"] is True
    assert r["control"]["physical_state_identical_between_the_two_reflection_off_worlds"] is True
    assert r["with_reflection"]["inhabitant_calls"] == r["without_reflection"]["inhabitant_calls"] > 0
    assert "observations" not in out.read_text() and "conclusions" not in out.read_text()      # no reflection text in the result file


def test_without_the_new_flags_the_output_is_unchanged_in_shape(tmp_path):
    out = tmp_path / "r.json"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "isvara_check.py"), "--backend", "mock", "--population", "3", "--ticks", "12",
                    "--reflect-every", "6", "--out", str(out)], capture_output=True, text=True, timeout=120, check=True)
    r = json.loads(out.read_text())
    assert "trace" not in r and "second_reflecting_world" not in r and "control" not in r
    assert r["extra_inference"]["root_calls"] == 2
