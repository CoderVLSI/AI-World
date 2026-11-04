"""Aggregate movement and resource summary of a FINISHED run folder (checkpoints + journal). Analysis only: no model, no GPU, nothing written
to the run folder, no text from the run is printed (counts, distances and reason labels only).

    python scripts/run_summary.py --run-dir /content/drive/MyDrive/CAITANYA/scale50-far-1 --out far_summary.json

Answers what the tool counts of a result file cannot: did anyone actually move, how far, did they get closer to food or water, how many accepted
walks (gather_at / mechanical move steps), how each task ended, and which sources were used up.  Works on any run made by the server or by
scripts/scale50_check.py --run-dir (a lone final checkpoint of a long run may not hold every event).
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.playback import Playback  # noqa: E402

SIGHT = 8


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nearest_source(pos, sources):
    return min((manhattan(pos, s) for s in sources), default=None)


def summarize(directory):
    pb = Playback(directory)
    start_world = pb.seek(0)
    start = {a.id: (a.x, a.z) for a in start_world.agents.values()}
    sources0 = [(n["x"], n["z"]) for n in start_world.resources.values() if n["kind"] in ("food", "water")]
    first_dist = {i: nearest_source(p, sources0) for i, p in start.items()}
    peak = {i: 0 for i in start}
    for t in range(1, pb.final_tick + 1):
        w = pb.seek(t)
        for a in w.agents.values():
            if a.id in peak:
                peak[a.id] = max(peak[a.id], manhattan((a.x, a.z), start[a.id]))
    end = pb.seek(pb.final_tick)
    humans = [a for a in end.agents.values() if a.id in start]
    final = {a.id: (a.x, a.z) for a in humans}
    moved = [manhattan(final[i], start[i]) for i in final]
    closer = [first_dist[i] - nearest_source(final[i], [(n["x"], n["z"]) for n in end.resources.values() if n["kind"] in ("food", "water")])
              for i in final if first_dist[i] is not None]
    by = Counter()
    for e in pb.events:
        origin = e.get("origin")
        if e["type"] in ("move", "gather_at", "gather", "rest", "rest_for", "travel_to", "walk") or e["type"].startswith("task_"):
            by[f'{e["type"]}:{origin or e.get("source")}'] += 1
    reasons = Counter()
    interrupts = Counter()
    for e in pb.events:
        if e["type"] == "intent_rejected":
            r = str(e["payload"].get("reason", ""))
            reasons["inference_failed" if r.startswith("inference_failed") else r[:60]] += 1
        elif e["type"] == "task_interrupted":
            interrupts[str(e["payload"].get("reason", ""))[:40]] += 1
    near0 = [n for n in start_world.resources.values() if any(manhattan((n["x"], n["z"]), p) <= SIGHT for p in start.values())]
    depleted = Counter(n["kind"] for n in end.resources.values() if n["amount"] <= 0)
    water_carried = sum(a.inventory.get("water", 0) for a in humans)
    return {
        "ticks": pb.final_tick, "humans": len(start),
        "displacement_from_start_tiles": {"final_mean": round(statistics.mean(moved), 2), "final_median": statistics.median(moved), "final_max": max(moved),
                                          "peak_max": max(peak.values()), "humans_moved_at_least_1": sum(1 for m in moved if m >= 1),
                                          "humans_peaked_at_least_8": sum(1 for m in peak.values() if m >= 8),
                                          "humans_peaked_at_least_16": sum(1 for m in peak.values() if m >= 16),
                                          "humans_peaked_at_least_24": sum(1 for m in peak.values() if m >= 24)},
        "distance_to_nearest_food_or_water": {"at_start_mean": round(statistics.mean(d for d in first_dist.values() if d is not None), 2),
                                              "closer_by_tiles_mean": round(statistics.mean(closer), 2) if closer else None,
                                              "humans_closer": sum(1 for c in closer if c > 0), "humans_farther": sum(1 for c in closer if c < 0)},
        "events_by_type_and_origin": dict(sorted(by.items())),
        "task_interrupt_reasons": dict(sorted(interrupts.items())),
        "rejections_by_reason": dict(sorted(reasons.items())),
        "needs_at_end": {"thirst_mean": round(statistics.mean(a.thirst for a in humans), 2), "thirst_max": round(max(a.thirst for a in humans), 2),
                         "hunger_mean": round(statistics.mean(a.hunger for a in humans), 2), "hunger_max": round(max(a.hunger for a in humans), 2),
                         "water_units_still_carried": water_carried, "alive": sum(a.alive for a in humans)},
        "sources_near_the_start_at_tick_0": {"nodes_within_sight_of_any_human": len(near0), "kinds": dict(sorted(Counter(n["kind"] for n in near0).items())),
                                             "depleted_nodes_at_end_by_kind": dict(sorted(depleted.items()))},
        "note": "Aggregate numbers only. Derived from the recorded run; nothing was re-simulated with a model.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    record = summarize(args.run_dir)
    Path(args.out).write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
