"""Bounded GPU check of batched decisions: speed, memory and whether batching changes what the model says.  Never a long run.

    python scripts/batch_check.py --revision <sha> --observations 24 --sizes 1,2,4,8 --out batch_lfm3.json

Takes the same fixed observations (from a mock 50-human world after 25 ticks; nothing here is a behavioural result) and decides them
at each batch size with the one shared model: size 1 is today's sequential path. For every size it records seconds per decision, peak GPU
memory, failures, and how many parsed choices (tool and parameters) equal the size-1 choices.  Batching with greedy decoding and left
padding is NOT assumed to give identical text; that is what "match" measures.  Hard limits: --max-real-seconds in total and a stop at the
first out-of-memory error.  Without a GPU it writes "unverified_no_gpu" and exits 2.  Only counts, categories and seconds are written.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.engine import MockInferenceBackend, World  # noqa: E402


def collect_observations(count, seed=314159):
    w = World(seed=seed, width=256, depth=256, families=25, children_per_family=0, wildlife_per_species=6,
              backend=MockInferenceBackend(use_tasks=True), isvara_config={"enabled": False})
    for _ in range(25):
        w.step()
    return [w.observe(aid) for aid in sorted(w.agents)[:count]]


def choice(intent):
    return (intent.action, json.dumps(intent.parameters, sort_keys=True))


def gpu_peak_reset():
    try:
        import torch
        torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def gpu_peak():
    try:
        import torch
        return int(torch.cuda.max_memory_allocated())
    except Exception:
        return None


def run(args, backend, observations):
    started, results, baseline = time.monotonic(), [], None
    for size in args.sizes:
        if time.monotonic() - started > args.max_real_seconds:
            results.append({"batch_size": size, "stopped": "wall_clock_limit"})
            break
        backend.batch_size = size
        gpu_peak_reset()
        choices, failures, t0 = [], 0, time.monotonic()
        try:
            for i in range(0, len(observations), size):
                chunk = observations[i:i + size]
                backend.prefetch(chunk)                       # a no-op when size is 1
                for obs in chunk:
                    try:
                        choices.append(choice(backend.decide(obs)))
                    except Exception:
                        failures += 1
                        choices.append(None)
        except Exception as exc:
            results.append({"batch_size": size, "stopped": "out_of_memory" if "out of memory" in str(exc).lower() else "error"})
            break
        seconds = time.monotonic() - t0
        if baseline is None:
            baseline = choices
        same = sum(1 for a, b in zip(choices, baseline) if a is not None and a == b)
        results.append({"batch_size": size, "decisions": len(observations), "failures": failures, "seconds_total": round(seconds, 3),
                        "seconds_per_decision": round(seconds / len(observations), 4), "gpu_peak_allocated_bytes": gpu_peak(),
                        "same_choice_as_batch_size_1": same, "same_choice_fraction": round(same / len(observations), 4),
                        "tool_choices": {t: sum(1 for c in choices if c and c[0] == t) for t in sorted({c[0] for c in choices if c})}})
    base = next((r for r in results if r.get("batch_size") == 1 and "seconds_per_decision" in r), None)
    for r in results:
        if base and "seconds_per_decision" in r:
            r["speedup_vs_batch_size_1"] = round(base["seconds_per_decision"] / max(1e-9, r["seconds_per_decision"]), 3)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--revision")
    p.add_argument("--observations", type=int, default=24)
    p.add_argument("--sizes", type=lambda s: [int(x) for x in s.split(",")], default=[1, 2, 4, 8])
    p.add_argument("--max-real-seconds", type=float, default=600.0)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    gpu = None
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        pass
    if not gpu:
        record = {"status": "unverified_no_gpu", "detail": "No CUDA device: batched decisions with the real model were NOT measured.", "requested": vars(args)}
        Path(args.out).write_text(json.dumps(record, indent=2))
        print(json.dumps(record, indent=2))
        return 2
    from caitanya.inference import TransformersLFM3Backend
    backend = TransformersLFM3Backend(revision=args.revision, batch_size=max(args.sizes))
    observations = collect_observations(args.observations)
    record = {"status": "completed", "label": "REAL LFM3 on GPU, bounded batch check (fixed mock-world observations; not a behavioural result)",
              "gpu": gpu, "model_id": backend.model_id, "model_revision": backend.model_revision, "requested": vars(args),
              "results": run(args, backend, observations)}
    Path(args.out).write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
