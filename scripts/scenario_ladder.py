"""A ladder of tiny, fast water scenarios with a clear pass condition.  Never a long run; one rung is 5 inhabitants for 40 ticks.

    python scripts/scenario_ladder.py --backend mock --out ladder_mock.json
    python scripts/scenario_ladder.py --backend lfm3 --revision <sha> --out ladder_lfm3.json          (needs a CUDA GPU; about 6 minutes per rung)

Operator fixture, stated openly: 5 adult inhabitants on a default map; every resource node is removed; ONE water node (40 units, renewable) is
placed `distance` tiles from the group; each inhabitant starts thirsty (60/100), carries no water and 3 food. Nothing tells anyone where the water is
except what they can see (`sight_range`). PASS for an inhabitant means they drank (a DRINK that lowered their thirst). Also recorded: who reached the
node, who gathered water, and when. A parsed TRAVEL_TO or GATHER_AT is only an intermediate result and is not counted as a pass.

Rungs (name, distance from the group, sight range): R0 at the group (8); R1 6 tiles, in sight (8); R2 16 tiles, in sight (32); R3 30 tiles, in
sight (32); R4 16 tiles, NOT in sight (8: exploration).  Without a GPU the lfm3 mode writes "unverified_no_gpu" and exits 2.  Counts and seconds only.
"""
import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from caitanya.engine import MockInferenceBackend, World  # noqa: E402
from caitanya.scheduler import find_path  # noqa: E402
from scale50_check import Timed, environment, percentile  # noqa: E402
from caitanya.inference import select_tools  # noqa: E402

RUNGS = {"R0": (0, 8), "R1": (6, 8), "R2": (16, 32), "R3": (30, 32), "R4": (16, 8)}
NODE_ID = "resource-water-fixture"      # default id of the fixture node; --node-id changes it (e.g. to the usual "resource-0001" style)
START_THIRST = 60.0


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def place_node(w, center, distance):
    """A walkable tile `distance` from the group's centre with a walkable route from it, found by a fixed scan (no random numbers)."""
    cfg = w.autonomy.scheduler
    cx, cz = center
    candidates = []
    for k in range(distance + 1):
        for sx, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            candidates.append((cx + sx * (distance - k), cz + sz * k))
    for x, z in dict.fromkeys(candidates):
        if 3 <= z < w.depth and 0 <= x < w.width and w.terrain_at(x, z)["walkable"]:
            if distance == 0 or find_path(w, center, (x, z), cfg.max_path_expansions, cfg.max_path_length):
                return x, z
    raise ValueError("no walkable site for the water node at that distance")


def build(args, backend, distance, sight):
    w = World(seed=args.seed, population=args.humans, width=128, depth=128, backend=backend, isvara_config={"enabled": False},
              sight_range=sight, founder_water=0)
    xs, zs = [a.x for a in w.agents.values()], [a.z for a in w.agents.values()]
    center = (round(sum(xs) / len(xs)), round(sum(zs) / len(zs)))
    spots = [(center[0] + dx, center[1] + dz) for r in range(0, 4) for dx in range(-r, r + 1) for dz in range(-r, r + 1) if max(abs(dx), abs(dz)) == r]
    spots = [q for q in spots if 3 <= q[1] < w.depth and 0 <= q[0] < w.width and w.terrain_at(*q)["walkable"]]
    for a, (x, z) in zip(w.agents.values(), spots):        # the group starts together (within 3 tiles of the centre), so "distance" means the same for all
        a.x, a.z = x, z
    w.resources.clear()
    node = place_node(w, center, distance)
    w.resources[args.node_id] = dict(id=args.node_id, x=node[0], z=node[1], kind="water", amount=40, capacity=40, renewable=True)
    for a in w.agents.values():
        a.thirst, a.inventory["water"], a.inventory["food"] = START_THIRST, 0, 3
    return w, node


class Diagnosed(Timed):
    """Timed, plus WHY a choice did or did not work (counts only, never text): was the chosen tool on offer, did GATHER_AT name the water node,
    was its amount in range, was the node in sight, did DRINK have water to drink."""

    def __init__(self, inner, node_id=NODE_ID):
        super().__init__(inner)
        self.node_id = node_id
        self.diag = {"chosen_not_offered": Counter(), "gather_at_names_the_water_node": 0, "gather_at_names_another_id": 0,
                     "gather_at_amount_out_of_range": 0, "gather_at_amount_missing_or_not_integer": 0, "decisions_with_the_node_in_sight": 0,
                     "decisions_with_the_node_adjacent_or_underfoot": 0, "drink_chosen_with_water_carried": 0, "drink_chosen_without_water": 0}

    def decide(self, observation):
        intent = super().decide(observation)
        d, me = self.diag, observation["self"]
        offered = {t["function"]["name"] for t in select_tools(observation)}
        if intent.action not in offered:
            d["chosen_not_offered"][intent.action] += 1
        node = next((n for n in observation["resources"] if n["id"] == self.node_id), None)
        d["decisions_with_the_node_in_sight"] += node is not None
        d["decisions_with_the_node_adjacent_or_underfoot"] += node is not None and manhattan((me["x"], me["z"]), (node["x"], node["z"])) <= 1
        if intent.action == "GATHER_AT":
            d["gather_at_names_the_water_node" if intent.parameters.get("resource_id") == self.node_id else "gather_at_names_another_id"] += 1
            amount = intent.parameters.get("amount")
            if type(amount) is not int:
                d["gather_at_amount_missing_or_not_integer"] += 1
            elif not 1 <= amount <= 8:
                d["gather_at_amount_out_of_range"] += 1
        elif intent.action == "DRINK":
            d["drink_chosen_with_water_carried" if me["inventory"].get("water", 0) > 0 else "drink_chosen_without_water"] += 1
        return intent


def run_rung(args, name, backend):
    distance, sight = RUNGS[name]
    timed = Diagnosed(backend, args.node_id)
    w, node = build(args, timed, distance, sight)
    ids = list(w.agents)
    start = {i: (w.agents[i].x, w.agents[i].z) for i in ids}
    start_dist = {i: manhattan(start[i], node) for i in ids}
    sees_at_start = sum(1 for i in ids if any(n["id"] == args.node_id for n in w.observe(i)["resources"]))
    first_reach, closest = {}, dict(start_dist)
    stopped, began = "completed", time.monotonic()
    for _ in range(args.ticks):
        if time.monotonic() - began > args.max_real_seconds:
            stopped = "stopped_at_wall_clock_limit"
            break
        w.step()
        for i in ids:
            d = manhattan((w.agents[i].x, w.agents[i].z), node)
            closest[i] = min(closest[i], d)
            if d == 0 and i not in first_reach:
                first_reach[i] = w.tick
        if timed.failure_rate() >= args.max_failure_rate:
            stopped = "stopped_at_failure_rate"
            break
    first_gather, first_drink = {}, {}
    for e in w.events:
        a = e.get("actor_id")
        if a not in w.agents:
            continue
        if e["type"] == "gather" and e["payload"].get("parameters", {}).get("resource_id") == args.node_id:
            first_gather.setdefault(a, e["world_tick"])
        elif e["type"] == "drink":
            st = e["payload"].get("confirmed_state", {})
            if st.get("after", {}).get("thirst", 0) < st.get("before", {}).get("thirst", 0):
                first_drink.setdefault(a, e["world_tick"])
    n = len(ids)
    med = lambda d: statistics.median(d.values()) if d else None
    return {
        "rung": name, "node_distance_from_group": distance, "sight_range": sight, "stop": stopped, "ticks_completed": w.tick,
        "humans": n, "node_in_sight_of_humans_at_start": sees_at_start,
        "start_distance_to_water_mean": round(statistics.mean(start_dist.values()), 2),
        "PASS_humans_who_drank": len(first_drink), "pass_fraction": round(len(first_drink) / n, 3),
        "humans_who_gathered_water": len(first_gather), "humans_who_reached_the_node": len(first_reach),
        "first_tick": {"reach_median": med(first_reach), "gather_median": med(first_gather), "drink_median": med(first_drink)},
        "closest_approach_mean": round(statistics.mean(closest.values()), 2),
        "thirst_mean": {"start": START_THIRST, "end": round(statistics.mean(w.agents[i].thirst for i in ids), 2)},
        "alive": sum(w.agents[i].alive for i in ids),
        "why": {**{k: (dict(sorted(v.items())) if isinstance(v, Counter) else v) for k, v in timed.diag.items()},
                "rejections_by_reason": dict(sorted(Counter("inference_failed" if str(r["reason"]).startswith("inference_failed") else str(r["reason"])[:60]
                                                            for r in w.rejections).items())),
                "water_node_units_left": w.resources[args.node_id]["amount"]},
        "decisions": {"calls": len(timed.seconds), "failures": sum(timed.failures.values()), "failure_categories": dict(sorted(timed.failures.items())),
                      "tool_choices": dict(sorted(timed.tools.items())), "seconds_per_call_p50": percentile(timed.seconds, .5),
                      "seconds_per_call_p95": percentile(timed.seconds, .95)},
        "real_seconds": round(time.monotonic() - began, 3),
    }


def run(args, backend=None):
    env = environment(args.backend)
    if args.backend == "lfm3" and not env["gpu"]:
        return {"status": "unverified_no_gpu", "detail": "No CUDA device: the water ladder with the real model was NOT run.", "requested": vars(args),
                "environment": env}, 2
    names = [r.strip() for r in args.rungs.split(",") if r.strip()]
    unknown = [r for r in names if r not in RUNGS]
    if unknown:
        raise SystemExit(f"unknown rungs {unknown}; choose from {sorted(RUNGS)}")
    if backend is None:
        if args.backend == "lfm3":
            from caitanya.inference import TransformersLFM3Backend
            backend = TransformersLFM3Backend(revision=args.revision)
        else:
            backend = MockInferenceBackend(use_tasks=True)
    results = [run_rung(args, name, backend) for name in names]
    return {"status": "completed" if all(r["stop"] == "completed" for r in results) else "partial",
            "label": ("REAL LFM3 on GPU, bounded water ladder" if args.backend == "lfm3" else "MOCK policy (CPU); checks the harness, not the model"),
            "environment": env, "model_id": getattr(backend, "model_id", None), "model_revision": getattr(backend, "model_revision", None),
            "requested": {k: v for k, v in vars(args).items() if k != "out"}, "results": results,
            "note": "Operator fixture (one water node, thirsty start, nothing else in the world). Pass = drank. One seed, no control."}, 0


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", choices=["mock", "lfm3"], default="mock")
    p.add_argument("--revision")
    p.add_argument("--seed", type=int, default=314159)
    p.add_argument("--humans", type=int, default=5)
    p.add_argument("--ticks", type=int, default=40)
    p.add_argument("--node-id", default=NODE_ID, help="id of the water node; the default is a descriptive fixture id, try e.g. resource-0001 (the usual style)")
    p.add_argument("--rungs", default="R0,R1,R2,R3,R4")
    p.add_argument("--max-real-seconds", type=float, default=600.0, help="hard cap per rung")
    p.add_argument("--max-failure-rate", type=float, default=0.4)
    p.add_argument("--out", required=True)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    record, code = run(args)
    Path(args.out).write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
