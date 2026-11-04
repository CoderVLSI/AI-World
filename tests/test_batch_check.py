"""The batch check script's bookkeeping, with a fake backend (no GPU): sizes, matching against batch size 1, limits, honesty without a GPU."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from caitanya.engine import Intent

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("batch_check", ROOT / "scripts" / "batch_check.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["batch_check"] = mod
spec.loader.exec_module(mod)


class Fake:
    def __init__(self, differ_at_batch=None, oom_at=None):
        self.batch_size, self.differ_at_batch, self.oom_at, self.cache = 1, differ_at_batch, oom_at, {}

    def _intent(self, obs):
        i = int(obs["self"]["id"].split("-")[1])
        name = "WAIT" if i % 2 == 0 else "REST"
        if self.batch_size == self.differ_at_batch and i == 1:
            name = "SPEAK"
        return Intent(obs["self"]["id"], obs["tick"], name, {}, "")

    def prefetch(self, observations):
        if self.batch_size < 2:
            return
        if self.oom_at == self.batch_size:
            raise RuntimeError("CUDA out of memory")
        for o in observations:
            self.cache[o["self"]["id"]] = self._intent(o)

    def decide(self, obs):
        return self.cache.pop(obs["self"]["id"], None) or self._intent(obs)


def args(*extra):
    class A:
        sizes, max_real_seconds = [1, 2, 4], 600
    a = A()
    for k, v in extra:
        setattr(a, k, v)
    return a


def test_identical_choices_at_every_size_report_full_match_and_a_speedup_figure():
    obs = mod.collect_observations(8)
    r = mod.run(args(), Fake(), obs)
    assert [x["batch_size"] for x in r] == [1, 2, 4] and all(x["same_choice_fraction"] == 1.0 and x["failures"] == 0 for x in r)
    assert all("speedup_vs_batch_size_1" in x for x in r)


def test_a_different_choice_under_batching_is_counted_not_hidden():
    r = mod.run(args(), Fake(differ_at_batch=4), mod.collect_observations(8))
    assert r[0]["same_choice_fraction"] == 1.0 and r[1]["same_choice_fraction"] == 1.0
    assert r[2]["same_choice_as_batch_size_1"] == 7 and r[2]["same_choice_fraction"] == 0.875


def test_out_of_memory_stops_the_check_and_says_so():
    r = mod.run(args(), Fake(oom_at=2), mod.collect_observations(4))
    assert r[-1] == {"batch_size": 2, "stopped": "out_of_memory"} and len(r) == 2


def test_the_wall_clock_limit_stops_further_sizes():
    r = mod.run(args(("max_real_seconds", -1)), Fake(), mod.collect_observations(4))
    assert r == [{"batch_size": 1, "stopped": "wall_clock_limit"}]


def test_without_a_gpu_it_says_unverified_and_measures_nothing(tmp_path):
    out = tmp_path / "o.json"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "batch_check.py"), "--out", str(out)], capture_output=True, text=True)
    assert done.returncode == 2 and json.loads(out.read_text())["status"] == "unverified_no_gpu" and "results" not in json.loads(out.read_text())
