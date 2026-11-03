"""Isolates the decision bottleneck without needing a GPU.

A deterministic forager policy is *labelled as a real model* so the engine applies the same
constraints it applies to LFM3 (legacy: at most 5 decisions every 3 ticks).  The policy is
identical across rows, so differences come only from scheduling and physiology.  This is a
mechanics comparison, NOT evidence about LFM3's behaviour.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.autonomy import AutonomyConfig  # noqa: E402
from caitanya.engine import MockInferenceBackend, World  # noqa: E402


class LabelledForager(MockInferenceBackend):
    model_id = "mock-labelled-as-real/forager"
    model_revision = "1"

    def __init__(self, use_tasks):
        super().__init__(use_tasks=use_tasks)
        self.last_request = {}

    def decide(self, observation):
        intent = super().decide(observation)
        self.last_request = {"request_id": f"r{self.calls}"}
        return intent


def run(label, population, ticks, autonomy, use_tasks):
    w = World(population=population, width=128, depth=128, backend=LabelledForager(use_tasks), autonomy=autonomy)
    for _ in range(ticks):
        w.step()
    m = w.metrics()
    if w.autonomy.legacy:
        decisions = w.backend.calls
        per_agent = round(decisions / population, 1)
        interval = round(ticks / max(per_agent, 1e-9), 1)
        wait = None
    else:
        report = m["scheduler"]
        decisions = report["totals"]["mock_decisions"] + report["totals"]["lfm_decisions"]
        per_agent = report["decisions_per_agent"]["mean"]
        interval = report["mean_decision_interval_ticks"]["mean"]
        wait = report["max_wait_ticks"]
    actions = sum(e["source"] == "validated_action" and e["type"] in ("move", "gather", "rest", "eat", "drink", "wait")
                  for e in w.events)
    return {"configuration": label, "validated_basic_actions_per_agent": round(actions / population, 1), "population": population, "ticks": ticks, "living": m["population"],
            "deaths": m["deaths"], "model_decisions": decisions, "mean_decisions_per_agent": per_agent,
            "mean_ticks_between_decisions": interval, "max_wait_ticks": wait}


if __name__ == "__main__":
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 432
    rows = []
    for n in (5, 50):
        rows.append(run("v0.4.0 legacy (5 decisions / 3 ticks, per-tick needs)", n, ticks, AutonomyConfig.legacy_mode(), False))
        legacy_clock_only = AutonomyConfig.from_dict({"scheduler": {"max_decisions_per_tick": 2}})
        rows.append(run("foundations, single-step actions, 2 decisions/tick", n, ticks, legacy_clock_only, False))
        rows.append(run("foundations, bounded intentions, 2 decisions/tick", n, ticks, legacy_clock_only, True))
    print(json.dumps(rows, indent=1))
