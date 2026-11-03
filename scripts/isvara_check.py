"""Bounded check of Isvara reasoning cost and integrity.  Never a long run.

Mock (CPU; measures only the bookkeeping, says nothing about LFM3):
    python scripts/isvara_check.py --backend mock --population 5 --ticks 200 --reflect-every 20 --out isvara_mock.json

Real LFM3 on a CUDA GPU (e.g. a Colab T4; one shared model instance serves inhabitants and the Isvara role).
Keep it small: the defaults are 5 inhabitants, 60 ticks, a reflection every 20 ticks. Add --control to measure run-to-run variation.
    python scripts/isvara_check.py --backend lfm3 --revision <sha> --run-dir /content/drive/MyDrive/CAITANYA/isvara-check-1 --out isvara_lfm3.json

Without a GPU the lfm3 mode writes an explicit "unverified_no_gpu" record and exits 2.  Nothing is estimated or
extrapolated.  Reflection text is private to the run directory and is never written to the output file.
"""
import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya import isvara  # noqa: E402
from caitanya.engine import MockInferenceBackend, World, digest  # noqa: E402


def environment(name):
    info = {"python": platform.python_version(), "platform": platform.platform(), "backend": name, "gpu": None}
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return info


def gpu_peak_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / 2 ** 20, 1)
    except Exception:
        pass
    return None


def reset_gpu_peak():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def physical(w):
    s = w.state()
    return digest(dict(agents=s["agents"], resources=s["resources"], rng=s["rng_state"], objects=s["objects"], fauna=s.get("fauna"), tick=s["tick"]))


def run_world(args, backend, reflect):
    reset_gpu_peak()
    config = ({"reflect_every_ticks": args.reflect_every, "max_new_tokens": args.max_new_tokens, "keep_raw_head_chars": args.keep_failure_samples}
              if reflect else {"enabled": False})
    w = World(seed=args.seed, population=args.population, backend=backend, isvara_config=config, wildlife_per_species=args.wildlife_per_species)
    started, stopped = time.monotonic(), "completed"
    for _ in range(args.ticks):
        if time.monotonic() - started > args.max_real_seconds:
            stopped = "stopped_at_wall_clock_limit"
            break
        w.step()
    return w, {"stop": stopped, "ticks_completed": w.tick, "real_seconds": round(time.monotonic() - started, 3), "gpu_peak_mb": gpu_peak_mb()}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", choices=["mock", "lfm3"], default="mock")
    p.add_argument("--revision")
    p.add_argument("--seed", type=int, default=314159)
    p.add_argument("--population", type=int, default=5)
    p.add_argument("--wildlife-per-species", type=int, default=0)
    p.add_argument("--ticks", type=int, default=60)
    p.add_argument("--reflect-every", type=int, default=20)
    p.add_argument("--max-new-tokens", type=int, default=320)
    p.add_argument("--max-real-seconds", type=float, default=600.0, help="hard cap per world")
    p.add_argument("--control", action="store_true", help="also run a second reflections-OFF world, to measure how much two identical "
                   "runs differ on their own (real models are not perfectly repeatable); adds one more world of wall time")
    p.add_argument("--keep-failure-samples", type=int, default=0, metavar="N",
                   help="keep the first N characters (max 500) of a failed output in the PRIVATE checkpoint only, never in the result file")
    p.add_argument("--run-dir", help="NEW directory for the checkpoint of the reflecting world (refused if it exists and is not empty)")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    env = environment(args.backend)
    if args.backend == "lfm3" and not env["gpu"]:
        record = {"status": "unverified_no_gpu", "detail": "No CUDA device: Isvara reasoning with the real model was NOT run.",
                  "requested": vars(args), "environment": env}
        Path(args.out).write_text(json.dumps(record, indent=2))
        print(json.dumps(record, indent=2))
        return 2
    if args.run_dir:
        d = Path(args.run_dir)
        if d.exists() and any(d.iterdir()):
            raise SystemExit("refusing to reuse a non-empty run directory")
    if args.backend == "lfm3":
        from caitanya.inference import TransformersLFM3Backend
        backend = TransformersLFM3Backend(revision=args.revision)
    else:
        backend = MockInferenceBackend(use_tasks=True)
    base, base_m = run_world(args, backend, reflect=False)                      # same backend object, reflections off
    base_calls = backend.calls
    base2 = None
    if args.control:
        base2, base2_m = run_world(args, backend, reflect=False)                # control: identical settings, reflections off again
    on_calls_before = backend.calls
    on, on_m = run_world(args, backend, reflect=True)                           # one shared model, reflections on
    st = isvara.role_state(on)
    refl = list(st["reflections"].values())
    root = backend.root_metrics() if hasattr(backend, "root_metrics") else {"calls": getattr(backend, "root_calls", 0)}
    human_calls_on = backend.calls - on_calls_before
    failures, failure_detail = {}, []
    for e in on.events:
        if e["type"] == "root_reflection_failed":                       # labels and counts only; never model text
            failures[e["payload"]["category"]] = failures.get(e["payload"]["category"], 0) + 1
            failure_detail.append({"tick": e["world_tick"], **{k: e["payload"][k] for k in ("category", "output_tokens", "hit_token_limit",
                                                                                           "tool_calls_found", "prompt_tokens") if k in e["payload"]}})
    record = {
        "status": "completed" if on_m["stop"] == "completed" and base_m["stop"] == "completed" else "partial",
        "label": ("REAL LFM3 on GPU" if args.backend == "lfm3" else "MOCK template (CPU); measures bookkeeping only, not model behaviour"),
        "environment": env, "model_id": backend.model_id, "model_revision": backend.model_revision,
        "requested": {k: v for k, v in vars(args).items() if k not in ("out",)},
        "without_reflection": base_m | {"inhabitant_calls": base_calls},
        "with_reflection": on_m | {"inhabitant_calls": human_calls_on},
        "extra_inference": {"root_calls": st["totals"]["attempts"], "recorded": st["totals"]["recorded"], "failures": st["totals"]["failures"],
                            "root_calls_as_fraction_of_inhabitant_calls": round(st["totals"]["attempts"] / max(1, human_calls_on), 4),
                            "added_wall_seconds_total": round(on_m["real_seconds"] - base_m["real_seconds"], 3),
                            "backend_root_metrics": root},
        "reflection_quality_counts": {"reflections": len(refl), "with_valid_citations": sum(1 for r in refl if r["cites"]),
                                      "uncited": sum(1 for r in refl if r["uncited"]), "uncertainty_stated": sum(1 for r in refl if r["uncertainty_stated"]),
                                      "dropped_citations": sum(r["dropped_cites"] for r in refl), "proposals_stored_unapplied": st["totals"]["proposals"]},
        "physical_state_identical_with_and_without_reflection": physical(base) == physical(on),
        "failure_categories": dict(sorted(failures.items())),
        "failures_detail": failure_detail,
        "note_on_physical_state": "A real model need not be perfectly repeatable. Without --control this field alone cannot say whether a difference "
                                  "comes from reflection or from run-to-run variation; with --control compare the two fields below.",
    }
    if base2 is not None:
        record["control"] = {"second_world_without_reflection": base2_m,
                             "physical_state_identical_between_the_two_reflection_off_worlds": physical(base) == physical(base2),
                             "reading": "If this is false, the real model differs from run to run by itself, so a difference with reflection on "
                                        "is not evidence that reflection changed the world."}
    if args.run_dir:
        path = on.checkpoint(args.run_dir)
        calls_before = root.get("calls", 0)
        restored = World.restore(path, backend=backend)
        after = backend.root_metrics()["calls"] if hasattr(backend, "root_metrics") else getattr(backend, "root_calls", 0)
        record["restore_check"] = {"restored_reflections_equal": isvara.role_state(restored)["reflections"] == st["reflections"],
                                   "restore_made_no_model_calls": after == calls_before, "checkpoint": str(path)}
    Path(args.out).write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
