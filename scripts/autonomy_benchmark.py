"""Measured run of the autonomy foundations.  Reports what actually completed.

Examples
--------
CPU/mock determinism and scheduling (does NOT show model autonomy):
    python scripts/autonomy_benchmark.py --backend mock --population 5 --sim-days 30 --out results.json

Real LFM3 stages (needs a CUDA GPU; otherwise an explicit "unverified" record is written):
    python scripts/autonomy_benchmark.py --backend lfm3 --population 5 --sim-days 30 --max-real-seconds 3600 --out stage_a.json
    python scripts/autonomy_benchmark.py --backend lfm3 --population 50 --sim-days 2 --max-real-seconds 3600 --out stage_b.json

Nothing here estimates or extrapolates: a run that stops at the wall-clock limit
reports the simulated time it really reached.
"""
import argparse
import collections
import json
import math
import os
import platform
import subprocess
try:
    import resource
except ImportError:  # Windows has no POSIX resource module.
    resource = None
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.autonomy import AutonomyConfig, load_experiment_file  # noqa: E402
from caitanya.engine import World, digest  # noqa: E402
from caitanya.lifecycle import BiologyConfig  # noqa: E402

EXPERIMENT_EVENTS = {"inspect", "strike", "combine", "separate", "heat", "cool", "rub", "feed_fire", "test",
                     "gather_with", "pick", "stow", "take", "drop", "hand_over"}


def environment(backend_name):
    info = {"python": platform.python_version(), "platform": platform.platform(), "cpus": os.cpu_count(),
            "gpu": None, "backend": backend_name}
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return info


def gpu_memory_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / 2 ** 20, 1)
    except Exception:
        pass
    return None


def build_backend(name, revision):
    if name == "mock":
        return None
    from caitanya.inference import TransformersLFM3Backend
    return TransformersLFM3Backend(revision=revision)


def summarize(world, started, real_seconds, run_dir, args, cpu_start):
    events = world.events
    births = sum(e["type"] == "birth" for e in events)
    experiment = collections.Counter(f"{e['type']}:{e['payload'].get('result')}" for e in events
                                     if e["type"] in EXPERIMENT_EVENTS and e["source"] == "validated_action")
    rejected = collections.Counter(r["reason"].split(":")[0][:60] for r in world.rejections)
    by_origin = collections.Counter(e.get("origin", "direct") for e in events if e["source"] == "validated_action")
    journal = run_dir / "events.jsonl"
    checkpoints = sorted(run_dir.glob("checkpoint-*.json"))
    metrics = world.metrics()
    ru = resource.getrusage(resource.RUSAGE_SELF) if resource else None
    sim_days = world.tick * world.biology.days_per_tick
    return {
        "status": "completed" if sim_days >= args.sim_days else "stopped_at_wall_clock_limit",
        "requested_sim_days": args.sim_days, "completed_ticks": world.tick, "completed_sim_days": round(sim_days, 3),
        "real_seconds": round(real_seconds, 2), "ticks_per_real_second": round(world.tick / max(real_seconds, 1e-9), 2),
        "seed": world.seed, "population_start": args.population, "days_per_tick": world.biology.days_per_tick,
        "autonomy": world.autonomy.to_dict(), "backend": world.manifest["model_id"],
        "model_revision": world.manifest["model_revision"],
        "commit_sha": subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        "wildlife_per_species": args.wildlife_per_species,
        "action_counts": dict(collections.Counter(e['type'] for e in events if e['source']=='validated_action')),
        "validated_decisions_per_agent": dict(collections.Counter(e['actor_id'] for e in events
            if e['source']=='validated_action' and e.get('origin')=='lfm_decision' and e.get('model_request_id'))),
        "sample_decisions": [dict(event_id=e['event_id'],tick=e['world_tick'],actor=e['actor_id'],action=e['type'],
            model_request_id=e.get('model_request_id'),outcome=e['payload'].get('outcome')) for e in events
            if e['source']=='validated_action' and e.get('origin')=='lfm_decision'][:10],
        "living": metrics["population"], "pregnancies_active": metrics["pregnancies"], "births": births,
        "highest_generation": metrics["highest_generation"], "deaths_by_cause": metrics["deaths"],
        "scheduler": metrics["scheduler"], "inference": metrics["inference"],
        "validated_actions_by_origin": dict(by_origin),
        "rejected_actions": {"total": len(world.rejections), "by_reason": dict(rejected.most_common(12))},
        "experiments": dict(experiment), "objects": sum(o["kind"] != "fire" for o in world.objects.values()),
        "root_manifestations": len(world.root.data["manifestations"]),
        "fires_ever_lit": sum(e["type"] == "rub" and e["payload"].get("result") == "ignited" for e in events),
        "knowledge": metrics["knowledge"], "material_ledger_g": dict(world.ledger),
        "resources": {"cpu_seconds": round(time.process_time() - cpu_start, 2), "max_rss_mb": round(ru.ru_maxrss / 1024, 1) if ru else None,
                      "gpu_max_allocated_mb": gpu_memory_mb(),
                      "journal_bytes": journal.stat().st_size if journal.exists() else 0,
                      "checkpoint_bytes_total": sum(p.stat().st_size for p in checkpoints)},
        "environment": environment(args.backend),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", choices=["mock", "lfm3"], default="mock")
    p.add_argument("--revision")
    p.add_argument("--population", type=int, default=5)
    p.add_argument("--sim-days", type=float, default=30)
    p.add_argument("--max-real-seconds", type=float, default=0, help="stop early after this long (0 = no limit)")
    p.add_argument("--seed", type=int, default=314159)
    p.add_argument("--width", type=int, default=128)
    p.add_argument("--depth", type=int, default=128)
    p.add_argument("--days-per-tick", type=float, default=1 / 144)
    p.add_argument("--decisions-per-tick", type=int)
    p.add_argument("--config")
    p.add_argument("--legacy", action="store_true")
    p.add_argument("--wildlife-per-species", type=int, default=6)
    p.add_argument("--run-dir", default="runs/benchmark")
    p.add_argument("--out", required=True)
    p.add_argument("--max-journal-bytes", type=int, default=100_000_000)
    args = p.parse_args()
    if Path(args.out).exists():
        p.error('Output already exists; choose a new --out path')

    env = environment(args.backend)
    if args.backend == "lfm3" and not env["gpu"]:
        record = {"status": "unverified_no_gpu", "detail": "No CUDA device: real-model acceptance was NOT run.",
                  "requested": vars(args), "environment": env}
        Path(args.out).write_text(json.dumps(record, indent=2))
        print(json.dumps(record, indent=2))
        return 2

    params, autonomy = load_experiment_file(args.config) if args.config else ({}, AutonomyConfig())
    if args.legacy:
        autonomy = AutonomyConfig.legacy_mode()
    if args.decisions_per_tick:
        from dataclasses import replace
        autonomy = replace(autonomy, scheduler=replace(autonomy.scheduler, max_decisions_per_tick=args.decisions_per_tick))
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if any(run_dir.iterdir()):
        sys.exit(f"{run_dir} is not empty; existing run data is never overwritten. Choose a new --run-dir.")
    world = World(seed=args.seed, population=args.population, width=args.width, depth=args.depth,
                  backend=build_backend(args.backend, args.revision), autonomy=autonomy,wildlife_per_species=args.wildlife_per_species,
                  biology=BiologyConfig(days_per_tick=args.days_per_tick))
    world.checkpoint(run_dir)
    cursor = len(world.events)
    started, cpu_start = time.monotonic(), time.process_time()
    target_ticks = math.ceil(args.sim_days / world.biology.days_per_tick - 1e-6)
    stop_reason = None
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as journal:
        while world.tick < target_ticks:
            world.step()
            for event in world.events[cursor:]:
                journal.write(json.dumps(event, separators=(",", ":")) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            cursor = len(world.events)
            # Public counters only: useful if a runtime ends before the final report.
            (run_dir / 'progress.json').write_text(json.dumps({'completed_ticks': world.tick,
                'completed_sim_days': world.tick * world.biology.days_per_tick,
                'real_seconds': time.monotonic() - started, 'metrics': world.metrics()}, indent=2), encoding='utf-8')
            if world.tick % 60 == 0:
                world.checkpoint(run_dir)
            if args.max_real_seconds and time.monotonic() - started >= args.max_real_seconds:
                break
            if journal.tell() >= args.max_journal_bytes:
                stop_reason = 'stopped_at_journal_limit'
                break
    world.checkpoint(run_dir)
    record = summarize(world, started, time.monotonic() - started, run_dir, args, cpu_start)
    if stop_reason:
        record['status'] = stop_reason
    recovered = World.recover(run_dir, backend=world.backend)
    record['checkpoint_recovery'] = {'equal': digest(world.state()) == digest(recovered.state()), 'tick': recovered.tick,
                                     'scope': 'same-process restore; runtime restart is a separate check'}
    from caitanya.experiment import summarize as export_evidence
    from scripts.audit_evidence import audit
    evidence = export_evidence(world, run_dir / 'summary', {'commit_sha': record['commit_sha']})
    record['evidence_audit'] = audit(evidence)
    Path(args.out).write_text(json.dumps(record, indent=2))
    print(json.dumps({k: record[k] for k in ("status", "completed_ticks", "completed_sim_days", "real_seconds",
                                              "living", "births", "deaths_by_cause")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
