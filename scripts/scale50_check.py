"""Bounded systems check for ~50 human inhabitants.  Never a long run; it measures throughput and integrity, not behaviour.

Mock (CPU; measures only the bookkeeping, says nothing about LFM3):
    python scripts/scale50_check.py --backend mock --ticks 24 --out scale50_mock.json

Real LFM3 on a CUDA GPU (e.g. a Colab T4).  One shared model instance, sequential decisions exactly as the engine does them today:
    python scripts/scale50_check.py --backend lfm3 --revision <sha> --ticks 24 --max-real-seconds 900 \
        --run-dir /content/drive/MyDrive/CAITANYA/scale50-1 --out scale50_lfm3.json

Setup: `--couples` households of one woman and one man, all adults (founders-v2, no children), so every person decides and every identity
is coherent.  Wildlife (default 6 per species = 72 animals, deterministic rules, no model) is reported separately and is NOT part of the
human count.  Isvara reflections and nature forces are off so only decision throughput is measured.  The default map and prompts are untouched.

Stops early (and says why) on: the wall-clock cap, a rolling failure rate at or above --max-failure-rate over the last 40 calls, or the
recorded event bytes passing --max-run-mb.  Without a GPU the lfm3 mode writes an explicit "unverified_no_gpu" record and exits 2;
nothing is estimated.  Only counts, categories and seconds are written: never model text.
"""
import argparse
import json
import platform
import statistics
import sys
import time
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.engine import MockInferenceBackend, World, digest  # noqa: E402

FAILURE_WORDS = (("expected exactly one complete tool call", "no_single_complete_tool_call"), ("prompt budget exceeded", "prompt_budget"),
                 ("unknown tool", "unknown_tool"), ("unknown or duplicate parameter", "bad_parameter"), ("integer expected", "bad_integer"),
                 ("invalid tool parameters", "invalid_parameters"), ("exceeds limit", "too_long"), ("out of memory", "gpu_out_of_memory"))


def failure_category(exc):
    text = str(exc).lower()
    return next((label for needle, label in FAILURE_WORDS if needle in text), "other")


def environment(name):
    info = {"python": platform.python_version(), "platform": platform.platform(), "backend": name, "gpu": None}
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return info


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 4)


class Timed:
    """Wraps a backend: times every decision, counts parsed tool names and failure categories, keeps a rolling failure window."""

    def __init__(self, inner):
        self.inner = inner
        self.seconds, self.tools, self.failures = [], Counter(), Counter()
        self.batch_seconds, self.batch_sizes = [], []
        self.window = deque(maxlen=40)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def decide(self, observation):
        started = time.monotonic()
        try:
            intent = self.inner.decide(observation)
        except Exception as exc:
            self.failures[failure_category(exc)] += 1
            self.window.append(1)
            self.seconds.append(time.monotonic() - started)
            raise
        self.seconds.append(time.monotonic() - started)
        self.tools[intent.action] += 1
        self.window.append(0)
        return intent

    def prefetch(self, observations):
        """Only reached when the inner backend batches (the scheduler checks `batch_size` first); times each batch."""
        started = time.monotonic()
        self.inner.prefetch(observations)
        self.batch_seconds.append(time.monotonic() - started)
        self.batch_sizes.append(len(observations))

    def failure_rate(self):
        return sum(self.window) / len(self.window) if len(self.window) == self.window.maxlen else 0.0


def jain(values):
    values = list(values)
    return round(sum(values) ** 2 / (len(values) * sum(v * v for v in values)), 4) if values and any(values) else None


def run(args, backend=None):
    env = environment(args.backend)
    if args.backend == "lfm3" and not env["gpu"]:
        return {"status": "unverified_no_gpu", "detail": "No CUDA device: the 50-human check with the real model was NOT run.",
                "requested": vars(args), "environment": env}, 2
    if args.run_dir and Path(args.run_dir).exists() and any(Path(args.run_dir).iterdir()):
        raise SystemExit("refusing to reuse a non-empty run directory")
    if backend is None:
        if args.backend == "lfm3":
            from caitanya.inference import TransformersLFM3Backend
            backend = TransformersLFM3Backend(revision=args.revision, batch_size=args.batch_size)
        else:
            backend = MockInferenceBackend(use_tasks=True)
    timed = Timed(backend)
    created = time.monotonic()
    w = World(seed=args.seed, width=args.width, depth=args.depth, families=args.couples, children_per_family=0,
              wildlife_per_species=args.wildlife_per_species, backend=timed, isvara_config={"enabled": False}, terrain=args.terrain, start_distance=args.start_distance, founder_water=args.founder_water, sight_range=args.sight_range)
    create_seconds = round(time.monotonic() - created, 3)
    humans = list(w.agents.values())
    identity = {"humans": len(humans), "unique_ids": len({a.id for a in humans}), "genders": dict(sorted(Counter(a.gender for a in humans).items())),
                "separate_memory_objects": len({id(a.memories) for a in humans}) == len(humans),
                "animals_alive_outside_the_human_count": sum(1 for b in w.fauna.animals.values() if b.alive) if w.fauna else 0}
    started, stop, tick_seconds = time.monotonic(), "completed", []
    event_bytes = 0
    seen_events = len(w.events)
    for _ in range(args.ticks):
        if time.monotonic() - started > args.max_real_seconds:
            stop = "stopped_at_wall_clock_limit"
            break
        t0 = time.monotonic()
        w.step()
        tick_seconds.append(time.monotonic() - t0)
        for e in w.events[seen_events:]:
            event_bytes += len(json.dumps(e, separators=(",", ":")))
        seen_events = len(w.events)
        if timed.failure_rate() >= args.max_failure_rate:
            stop = "stopped_at_failure_rate"
            break
        if event_bytes > args.max_run_mb * 1_000_000:
            stop = "stopped_at_event_bytes"
            break
    real_seconds = round(time.monotonic() - started, 3)
    report = w.scheduler.report(w)
    per_agent = {a.id: w.scheduler.record(a.id)["decisions"] for a in humans}
    reasons = Counter()
    for r in w.rejections:
        reason = str(r["reason"])
        reasons["inference_failed" if reason.startswith("inference_failed") else reason[:60]] += 1
    calls = len(timed.seconds)
    metrics = backend.metrics() if hasattr(backend, "metrics") else {}
    prompt_counts = list(getattr(backend, "prompt_token_counts", []) or [])
    record = {
        "status": "completed" if stop == "completed" else "partial", "stop": stop,
        "label": ("REAL LFM3 on GPU, sequential decisions, ONE bounded run" if args.backend == "lfm3"
                  else "MOCK policy (CPU); measures bookkeeping only, not model behaviour"),
        "environment": env, "model_id": getattr(backend, "model_id", None), "model_revision": getattr(backend, "model_revision", None),
        "requested": {k: v for k, v in vars(args).items() if k != "out"},
        "identity": identity, "terrain": w.geography_version, "start_distance": args.start_distance, "founder_water": args.founder_water, "sight_range": args.sight_range, "world_creation_seconds": create_seconds,
        "ticks_completed": w.tick, "real_seconds": real_seconds,
        "decisions": {"calls": calls, "failures": sum(timed.failures.values()), "failure_categories": dict(sorted(timed.failures.items())),
                      "tool_choices": dict(sorted(timed.tools.items())),
                      "seconds_per_call": {"mean": round(statistics.mean(timed.seconds), 4) if timed.seconds else None,
                                           "p50": percentile(timed.seconds, .5), "p95": percentile(timed.seconds, .95), "max": percentile(timed.seconds, 1.0)}},
        "per_tick_seconds": {"mean": round(statistics.mean(tick_seconds), 4) if tick_seconds else None, "p95": percentile(tick_seconds, .95),
                             "max": percentile(tick_seconds, 1.0)},
        "scheduling": {"decisions_per_human": {"min": min(per_agent.values(), default=0), "max": max(per_agent.values(), default=0),
                                               "jain_fairness_index": jain(per_agent.values())},
                       "mean_decision_interval_ticks": report.get("mean_decision_interval_ticks"),
                       "max_wait_ticks": report.get("max_wait_ticks"), "max_interval_ticks": report.get("max_interval_ticks"),
                       "budget_exhausted_ticks": report["totals"]["budget_exhausted_ticks"], "max_queue": report["totals"]["max_queue"],
                       "decisions_per_tick_cap": w.autonomy.scheduler.max_decisions_per_tick,
                       "seconds_per_tick_cap": w.autonomy.scheduler.max_seconds_per_tick},
        "rejections_by_reason": dict(sorted(reasons.items())),
        "humans_vs_wildlife": {"human_decisions_model": report["totals"]["lfm_decisions"], "human_decisions_mock": report["totals"]["mock_decisions"],
                               "wildlife_events_deterministic_rules": len(w.fauna.events) if w.fauna else 0, "wildlife_model_calls": 0},
        "outcomes": {"alive": sum(a.alive for a in humans), "deaths": len(humans) - sum(a.alive for a in humans),
                     "lowest_health": min((a.health for a in humans), default=None)},
        "recorded_event_bytes": event_bytes, "events": len(w.events),
        "prompt_tokens": ({"p50": percentile(prompt_counts, .5), "p95": percentile(prompt_counts, .95), "max": max(prompt_counts, default=0),
                           "cap": metrics.get("prompt_tokens", {}).get("cap"), "budget_failures": metrics.get("prompt_budget_failures")}
                          if prompt_counts else None),
        "gpu_peak_allocated_bytes": metrics.get("gpu_peak_allocated_bytes"),
        "failure_detail": metrics.get("failure_detail"),
        "batching": {"batch_size": args.batch_size, "batches": len(timed.batch_sizes), "batch_sizes": dict(sorted(Counter(timed.batch_sizes).items())),
                     "seconds_per_batch": {"mean": round(statistics.mean(timed.batch_seconds), 4) if timed.batch_seconds else None,
                                           "p95": percentile(timed.batch_seconds, .95), "max": percentile(timed.batch_seconds, 1.0)},
                     "model_seconds_per_decision": round(sum(timed.batch_seconds) / max(1, sum(timed.batch_sizes)), 4) if timed.batch_sizes else None,
                     "backend": metrics.get("batching"),
                     "reading": "With batching, decide() only collects a result, so seconds_per_call is not the model time; use the batch figures."},
        "note": "Systems check, not a behavioural result: each human gets only a handful of decisions in a bounded run.",
    }
    if args.run_dir:
        path = w.checkpoint(args.run_dir)
        before = calls
        restored = World.restore(path, backend=timed)
        record["restore_check"] = {"restored_state_equals_live": digest(restored.state()) == digest(w.state()),
                                   "restore_made_no_model_calls": len(timed.seconds) == before, "checkpoint": str(path)}
    return record, 0


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", choices=["mock", "lfm3"], default="mock")
    p.add_argument("--revision")
    p.add_argument("--seed", type=int, default=314159)
    p.add_argument("--couples", type=int, default=25, help="households of one woman and one man (2 humans each); 25 gives 50 humans")
    p.add_argument("--width", type=int, default=256)
    p.add_argument("--depth", type=int, default=256)
    p.add_argument("--terrain", choices=["geography-v1", "geography-v2"], default="geography-v1", help="map generator; geography-v2 = two river valleys")
    p.add_argument("--sight-range", type=int, default=8, help="tiles at which resource nodes are seen (default 8; farther is an experiment)")
    p.add_argument("--founder-water", type=int, default=3, help="units of water each founder carries (default 3; 0 = thirsty sooner)")
    p.add_argument("--start-distance", type=int, default=0, help="far start: no food or water under the founders; nearest source this many tiles away (0 = off)")
    p.add_argument("--batch-size", type=int, default=1, help="EXPERIMENT (default 1 = sequential, as always): decide this many inhabitants per generate call (lfm3 only)")
    p.add_argument("--wildlife-per-species", type=int, default=6)
    p.add_argument("--ticks", type=int, default=24)
    p.add_argument("--max-real-seconds", type=float, default=900.0, help="hard wall-clock cap")
    p.add_argument("--max-failure-rate", type=float, default=0.2, help="stop when this fraction of the last 40 calls failed")
    p.add_argument("--max-run-mb", type=float, default=200.0, help="stop when the recorded event bytes pass this")
    p.add_argument("--run-dir", help="NEW directory for a final checkpoint and restore check (refused if it exists and is not empty)")
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
