# Experiment protocol

How to measure the autonomy foundations, what each kind of run can and cannot show, and what must never be claimed.
Actual measurements are in [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md).

## Rules for every run

1. **Report what completed.** The harness records the ticks and simulated days actually reached, the real elapsed time
   and whether the run `completed` or `stopped_at_wall_clock_limit`. Never quote the intended duration as the result.
2. **Never fabricate or extrapolate.** No estimated births, inventions, survival times or throughput. A stage that was
   not run is `unverified`, and the harness writes that record itself when there is no GPU.
3. **Label the policy.** Mock results (`MockInferenceBackend`, scripted test policies) prove determinism, invariants
   and scheduling mechanics. They say nothing about LFM3 autonomy, and a mock never counts as an LFM decision.
4. **New run directory per experiment.** The harness refuses a non-empty `--run-dir`; existing data is never touched.
5. **Record the configuration.** The full autonomy configuration, seed, model id and revision, dependency versions
   and device are in the output and in the run manifest. Pin `--revision <sha>` for real runs.
6. **A "discovery" is a measured reproduction**, not a judgement: a finding recorded as an *own observation* by at
   least two different inhabitants (`knowledge.independently_reproduced_findings`). Witnessed or second-hand
   knowledge does not count, and no metric asserts that a belief is true.

## Automated tests (CPU, no model)

```sh
python -m pip install -e ".[test]"
python -m pytest -q
```

| Area | Where |
|---|---|
| Scheduler fairness (5 and 50), bounded waiting, priorities | `tests/test_scheduler.py` |
| Decision/mechanical attribution, failures without mock fallback | `tests/test_scheduler.py`, `tests/test_lfm_path.py` |
| Obsolete or blocked plans end; invalid intentions rejected without mutation | `tests/test_scheduler.py` |
| Time-based survival at two speeds (10 min and 1 h ticks) and three seeds; scarcity, illness, infant care | `tests/test_physiology.py` |
| Experiments, meaningful failure, conservation fuzz, invalid-action safety | `tests/test_experiments.py` |
| Memory persistence, retrieval bounds, isolation, evidence status, revision | `tests/test_memory.py` |
| Cross-generational transmission with provenance | `tests/test_memory.py` |
| Checkpoint, replay, journal recovery, schema migration from a real v0.4.0 run | `tests/test_recovery.py`, `tests/test_migration.py`, `tests/test_scheduler.py`, `tests/test_experiments.py`, `tests/test_memory.py` |
| Root privacy, continuity and manifestation (unchanged v0.4.0 tests) | `tests/test_root.py`, `tests/test_memory.py` |
| Prompt unchanged (SHA-256 against the reference commit), no religion/recipe words in tool text | `tests/test_experiments.py` |
| Read-only witness and new endpoints | `tests/test_witness.py` |
| Explicit configuration, `--config`, default.json never auto-loaded | `tests/test_config.py` |

## CPU/mock benchmarks (determinism, scheduling, cost)

```sh
python scripts/autonomy_benchmark.py --backend mock --population 5  --sim-days 30 --out m5.json
python scripts/autonomy_benchmark.py --backend mock --population 5  --sim-days 30 --days-per-tick 0.0416666667 --out m5_fast.json
python scripts/autonomy_benchmark.py --backend mock --population 50 --sim-days 7 --max-real-seconds 900 --out m50.json
python scripts/scheduler_comparison.py 432 > comparison.json
```

`scheduler_comparison.py` labels a deterministic forager as a real model so the legacy 5-decisions-per-3-ticks cap
applies, and compares legacy, single-step foundations and bounded intentions with identical policy logic. It
isolates the *mechanism*; it is not evidence about LFM3.

## Real-model stages (require a CUDA GPU)

Use a separate run directory, install `.[gpu]`, pin the revision recorded in the manifest, and keep the model weights
out of the repository.

```sh
python scripts/autonomy_benchmark.py --backend lfm3 --revision <sha> --population 5  --sim-days 30 --max-real-seconds 7200 --out stage_a.json   # Stage A
python scripts/autonomy_benchmark.py --backend lfm3 --revision <sha> --population 50 --sim-days 2  --max-real-seconds 7200 --out stage_b.json   # Stage B
```

Stage C (longer, generational runs) uses the server with `--recover`-capable checkpoints and off-machine backups:

```sh
python -m caitanya.server --backend lfm3 --revision <sha> --population 50 --run-dir runs/stage_c --checkpoint-every 240
```

### Measurements collected (JSON field)

living inhabitants (`living`), births / pregnancies / deaths and causes (`births`, `pregnancies_active`,
`deaths_by_cause`), model calls and latency (`inference`), decisions per agent and fairness (`scheduler`:
`decisions_per_agent`, `mean_decision_interval_ticks`, `max_wait_ticks`, `max_interval_ticks`), model failures and
rejected actions (`scheduler.totals.failed_decisions`, `rejected_actions`), reflex interventions
(`scheduler.totals.reflex_interventions`), experiments and outcomes (`experiments`, `fires_ever_lit`, `objects`),
verified findings, memory retrievals and knowledge transfers (`knowledge`), CPU / RAM / GPU / journal / checkpoint
usage (`resources`), simulated versus real time (`completed_sim_days`, `real_seconds`, `ticks_per_real_second`),
and attribution (`validated_actions_by_origin`, `scheduler.totals.lfm_decisions` vs `mechanical_steps`).

### Pre-stated acceptance criteria

These are criteria for *reading* a real run, not predictions:

* **Mechanics (must hold):** `max_wait_ticks` within the stated bound; no model call counted for a mechanical step
  (`lfm_decisions` equals model calls minus failures); zero `mock_decisions`; failures produce no action;
  checkpoint/recover of the run reproduces the final state digest.
* **Survival (reported, not required):** living inhabitants, deaths and causes at the end. Scarcity and death are
  allowed outcomes. Report them; do not tune parameters to hide them.
* **Experimentation (reported):** which experiments the model attempted, their outcomes, and reproduced findings.
  Zero is a valid result for a 1.7B model; do not substitute a scripted policy.
* **Autonomy claims:** none are made from mock or scripted runs.

If the GPU run cannot complete, report the completed ticks and the reason (e.g. out of memory, wall-clock limit),
keep the partial JSON, and state that the stage is incomplete.
