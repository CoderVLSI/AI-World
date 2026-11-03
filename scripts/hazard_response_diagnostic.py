"""Do inhabitants react to a lasting hazard? A bounded diagnostic; it never instructs, forces or scores a response.

Fixture (explicit, not a natural event): five inhabitants start together and a lasting wildfire zone is placed over them by the
operator at tick 0. Everything else is default. The report counts what each inhabitant CHOSE (parsed tool names only), where it was,
and what the world recorded. A scripted stand-in on CPU shows what the machinery measures; it is not a model result.

    python scripts/hazard_response_diagnostic.py --backend cpu --out hazard_cpu.json
    python scripts/hazard_response_diagnostic.py --backend lfm3 --revision <sha> --ticks 40 --max-real-seconds 900 --out hazard_lfm3.json

lfm3 needs a CUDA GPU (otherwise an explicit "unverified_no_gpu" record is written). Reflection/model text is never written.
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.engine import Intent, MOCK_MODEL_ID, MockInferenceBackend, World  # noqa: E402

FORCE, STRENGTH = "agni", 3          # a wildfire, radius 7, six simulated hours, up to 6 hp per hour inside (never below 1 hp)
TRACKED = ("MOVE", "TRAVEL_TO", "GATHER_AT", "REST_FOR", "SPEAK", "WAIT", "REST", "EAT", "DRINK")


class IdleStandIn:
    model_id, model_revision, metadata = MOCK_MODEL_ID, "scripted-idle-v1", {"mock_options": {"use_tasks": True}}

    def __init__(self):
        self.calls = 0

    def decide(self, observation):
        self.calls += 1
        a = observation["self"]
        return Intent(a["id"], observation["tick"], "WAIT", {}, "")


class FleeStandIn(IdleStandIn):
    model_revision = "scripted-flee-v1"

    def __init__(self):
        super().__init__()
        self.heading = {}

    def decide(self, observation):
        a = observation["self"]
        if any(h["inside"] for h in observation.get("environment_hazards", [])):
            self.calls += 1
            blocked = {tuple(b) for b in observation.get("blocked", [])}
            order = [self.heading.get(a["id"], (1, 0)), (1, 0), (-1, 0), (0, 1), (0, -1)]
            for dx, dz in order:
                if (a["x"] + dx, a["z"] + dz) not in blocked:
                    self.heading[a["id"]] = (dx, dz)
                    return Intent(a["id"], observation["tick"], "MOVE", {"dx": dx, "dz": dz}, "")
        return super().decide(observation)


class Recorder:
    """Wraps a backend and counts the parsed choice of each decision with the chooser's zone status. Text is never kept."""
    def __init__(self, inner, world_ref):
        self.inner, self.world_ref = inner, world_ref
        self.choices, self.failures = [], 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def decide(self, observation):
        inside = any(h["inside"] for h in observation.get("environment_hazards", []))
        offered = [h["phenomenon"] for h in observation.get("environment_hazards", [])]
        try:
            intent = self.inner.decide(observation)
        except Exception:
            self.failures += 1
            raise
        self.choices.append({"tick": observation["tick"], "agent": observation["self"]["id"], "tool": intent.action, "inside": inside,
                             "hazard_visible": bool(offered), "health": observation["self"]["health"]})
        return intent


def run(backend, ticks, max_seconds, seed=314159):
    holder = {}
    rec = Recorder(backend, holder)
    w = World(seed=seed, population=5, width=128, depth=128, wildlife_per_species=6, nature_forces=True, backend=rec)
    holder["w"] = w
    xs, zs = [a.x for a in w.agents.values()], [a.z for a in w.agents.values()]
    cx, cz = round(sum(xs) / 5), round(sum(zs) / 5)
    w.nature_forces.apply(w, FORCE, cx, cz, STRENGTH)           # the operator's fixture pulse (not a natural event)
    hz = w.nature_forces.data["hazards"][0]
    inside0 = [a.id for a in w.agents.values() if abs(a.x - hz["x"]) + abs(a.z - hz["z"]) <= hz["radius"]]
    first_out, minhp, started, stop = {}, {a: 100 for a in w.agents}, time.monotonic(), "completed"
    for _ in range(ticks):
        if time.monotonic() - started > max_seconds:
            stop = "stopped_at_wall_clock_limit"
            break
        w.step()
        for a in w.agents.values():
            minhp[a.id] = min(minhp[a.id], a.health)
            outside = abs(a.x - hz["x"]) + abs(a.z - hz["z"]) > hz["radius"]
            if a.id in inside0 and outside and a.id not in first_out:
                first_out[a.id] = w.tick
    end = [e["payload"] for e in w.events if e["type"] == "nature_hazard_ended"]
    by = {k: Counter() for k in ("inside", "outside")}
    for c in rec.choices:
        by["inside" if c["inside"] else "outside"][c["tool"]] += 1
    return {"stop": stop, "ticks_completed": w.tick, "real_seconds": round(time.monotonic() - started, 3),
            "fixture": {"force": "wildfire", "strength": STRENGTH, "radius": hz["radius"], "center": [hz["x"], hz["z"]],
                        "hazard_ticks": hz["end_tick"] - hz["start_tick"], "inhabitants_inside_at_start": inside0},
            "choices_while_inside": dict(sorted(by["inside"].items())), "choices_while_outside": dict(sorted(by["outside"].items())),
            "decisions": len(rec.choices), "decision_failures": rec.failures,
            "inhabitants_who_left_the_zone": {a: t for a, t in sorted(first_out.items())},
            "left_count": len(first_out), "inside_count_at_start": len(inside0),
            "lowest_health": minhp, "alive": sum(a.alive for a in w.agents.values()),
            "hazard_summary_recorded": bool(end), "move_choices_while_inside": by["inside"].get("MOVE", 0),
            "hazard_visible_in_observations": sum(1 for c in rec.choices if c["hazard_visible"])}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", choices=["cpu", "lfm3"], default="cpu")
    p.add_argument("--revision")
    p.add_argument("--ticks", type=int, default=40)
    p.add_argument("--max-real-seconds", type=float, default=900.0)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    if args.backend == "cpu":
        record = {"status": "completed", "label": "SCRIPTED stand-ins on CPU: shows what is measured; says nothing about any model",
                  "idle_stand_in": run(IdleStandIn(), args.ticks, args.max_real_seconds),
                  "fleeing_stand_in": run(FleeStandIn(), args.ticks, args.max_real_seconds)}
    else:
        gpu = None
        try:
            import torch
            gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        except Exception:
            pass
        if not gpu:
            record = {"status": "unverified_no_gpu", "detail": "No CUDA device: the real-model episode was NOT run.", "requested": vars(args)}
            Path(args.out).write_text(json.dumps(record, indent=2))
            print(json.dumps(record, indent=2))
            return 2
        from caitanya.inference import TransformersLFM3Backend
        backend = TransformersLFM3Backend(revision=args.revision)
        record = {"status": "completed", "label": "REAL LFM3 on GPU, ONE bounded episode; no follow-on", "gpu": gpu,
                  "model_id": backend.model_id, "model_revision": backend.model_revision, "requested": vars(args),
                  "episode": run(backend, args.ticks, args.max_real_seconds),
                  "inference": {k: v for k, v in backend.metrics().items() if k in ("model_calls", "parse_or_inference_failures", "gpu_peak_allocated_bytes",
                                                                                   "inference_seconds", "prompt_tokens")}}
    Path(args.out).write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
