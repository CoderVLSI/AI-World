# Merge checklist - `feature/caitanya-autonomy-foundations` (v0.4.0 -> v0.5.0)

Branched from `main` @ `26be6300d56f8aaab026ace59b4d500592f9e91c`. While this work was in progress `main` advanced to
`dfb78d5` (root modes, bounded real-model workflow, evidence export); that commit was **merged into this branch** (a
merge commit; no history was rewritten or force-pushed) and the code adapted to it. Do not merge this branch before
the owner has reviewed it.

### What the merge with `dfb78d5` involved

* **Kept the owner's code as-is:** `caitanya/root.py` (root modes), `caitanya/experiment.py`, the Colab notebook, the
  `--root-mode/--max-ticks/--max-seconds/--report-dir` workflow, `metrics.jsonl`, GPU metrics. `git diff main --
  caitanya/root.py` is empty.
* **Name collision:** both sides added `tests/test_experiments.py`. The owner's file keeps its path; mine is now
  `tests/test_physics_experiments.py`.
* **`confirmed_state`** (before/after position, needs, inventory) is attached to every decision and direct action,
  including the new experiment, memory and intention actions, but **not** to routine mechanical path steps (tens of
  thousands per run; they are journaled with `task_id` instead).
* **Root registry gains `mode`** (upstream). The migration test projects it away; the default `crisis` is the v0.4.0
  behaviour, so schema-1 runs still reproduce v0.4.0 exactly.
* **Evidence export:** `summarize()` was re-verified with experiments and private memory in play
  (`tests/test_integration_main.py`): no hypothesis text, memory ids, `ltm` or root data appear in `evidence.json` or
  `REPORT.md`. `WRITE_FINDINGS` publishes only its title (the findings text is the public work).
* **Colab notebook runs unchanged** (flags verified), but it now asks up to 8 inhabitants per tick instead of 5 per
  3 ticks, so a `--max-seconds`-bounded real run completes fewer ticks. Lower `--decisions-per-tick` or raise
  `--max-seconds` in the launch cell when comparing with earlier runs.

## Verdict

**Ready for review; not ready to claim real-model results.** The mechanics are implemented and tested on CPU. LFM3
behaviour is unverified (no GPU was available). P4 (animals and ecology) is deferred.

## Implemented vs deferred

| Priority | Status |
|---|---|
| P0 scheduler, survival, clock consistency | implemented, tested, measured on mock policy |
| P1 open-ended experimentation | implemented, tested (including a randomized conservation fuzz) |
| P2 structured long-term memory | implemented, tested |
| P3 cross-generation transmission and witness observability | implemented, tested; viewer smoke-tested in headless Chromium |
| P4 animals and ecology | **deferred** (not started; the mandatory and important layers took priority) |
| Real-model Stages A/B/C | **not run** (no GPU); harness and protocol provided |

## Breaking changes

1. **New worlds default to `foundations` mode** (time-based needs, budgeted scheduler, experiments, memory). Use
   `autonomy='legacy'` (library) or `--legacy` (CLI) for the exact v0.4.0 dynamics.
2. **Ticks longer than 6 simulated hours are refused** in `foundations` mode (`ValueError`). `--days-per-tick 1` (the
   README's old accelerated example) now needs `--legacy`; use a smaller `--days-per-tick` otherwise.
3. **7 existing tests were pinned to `autonomy='legacy'`** (`tests/test_generations.py` fixture - a 365-day tick - and
   `test_fifty_identities_share_one_backend` - the 100-call cadence). Their assertions are unchanged. The six root
   tests are unchanged and pass in the new default mode.
4. **Observations** (the model's input) in `foundations` mode gain `clock`, `objects`, `recalled` and a compact
   `task`; need values are rounded integers. Legacy observations are unchanged.
5. **Events gain optional attribution fields** (`origin`, `task_id`, `model_request_id`) and new event types. Events
   emitted outside the new paths are byte-identical to v0.4.0.
6. **Public metrics gain** `deaths`, `scheduler`, `knowledge`, `autonomy_mode`; the public snapshot gains `objects`
   and per-agent `task`, `busy_until_tick`, `illness`; it still omits `ltm`, `memories` and the scheduler's per-agent
   records. New GET-only endpoints: `/api/v1/scheduler`, `/api/v1/knowledge`, `/api/v1/objects`.
7. **CLI additions:** `--config`, `--legacy`, `--decisions-per-tick`, `--checkpoint-every` (default unchanged, 60).
   `config/default.json` is still *not* loaded automatically; only a file named with `--config` is read, strictly
   (unknown keys are errors). Its schema gained an `autonomy` section.
8. **LFM tool list grew** from 17 to 41 tools (offered per situation) and the prompt-token cap is now a constructor
   argument (`max_prompt_tokens`, default 6144, was a fixed 4096). The system message text is unchanged.
9. `server.main()` was split into `build_parser()`/`build_world()` (behaviour preserved).

## Schema and migration

* State `schema_version` 1 -> **2**. New keys: `autonomy`, `scheduler`, `objects`, `next_object_id`, `ledger`; new
  agent fields: `task`, `busy_until_tick`, `illness`, `ltm` (all defaulted).
* Schema-1 checkpoints load in `legacy` mode (explicit, versioned, tested against a real v0.4.0 checkpoint + journal
  tail: `tests/fixtures/v1_run`). The first new tick's diff carries the added keys, so old and new patches replay as
  one chain (`World.replay` across the boundary is tested). Unsupported schemas fail with `unsupported schema`;
  checksum tampering fails with `checkpoint checksum mismatch`.
* Nothing is erased; old history and checkpoints are untouched. A schema-2 checkpoint cannot be read by v0.4.0 code.
* A migrated run stays in `legacy` mode permanently (it cannot "upgrade" mid-run without changing its dynamics).
  Existing running processes must be restarted with this version to use any of this.

## Verified invariants (all under test)

* `neutral-v4-inquiry` and the full system message match SHA-256 of the reference commit.
* No religion/doctrine/recipe words in tool descriptions; root and previous-life data never reach prompts, memory,
  snapshots, history or events; a newborn's memory is empty; continuity threads behave as before.
* `BrahmanAgent`, its ledger, `register`, `sustain` and `delegate` are unmodified (`git diff main -- caitanya/root.py`
  is empty). Its manifestation fired under the new physiology in a test as before.
* Resource/mass conservation across hundreds of randomized valid and invalid experiment actions; rejected actions
  mutate nothing.
* Determinism across seeds and restore; checkpoint/replay/journal recovery with intentions, objects and memory.

## Test results

`python -m pytest -q` -> **177 passed** (30 on `main` including the owner's 5 new tests + 147 new), about 60 s. See EXPERIMENT_RESULTS.md for the
measured mock runs. Reproduce:

```sh
python -m pip install -e ".[test]" && python -m pytest -q
python scripts/autonomy_benchmark.py --backend mock --population 5 --sim-days 30 --run-dir runs/bench5 --out m5.json
```

## Outstanding risks

1. **No real-model evidence.** The 1.7B model may handle 41 tools, intentions and experiments poorly; survival may
   fail for reasons the mock cannot show. Run Stages A/B before drawing conclusions.
2. **Persistence growth (measured).** About 67 KB of journal per tick at 50 inhabitants means the 100 MB journal limit
   pauses the worker after roughly 10 simulated days at baseline. Each periodic checkpoint embeds the whole event
   history: 1.4 GB of checkpoints for a 5-inhabitant, 30-day run. Existing behaviour, made more visible by richer
   events. Mitigations available now: `--checkpoint-every`, off-machine backups. Follow-ups (not done, they change
   the on-disk format): checkpoints without the full event list, journal segmenting, list-diff patches. Old
   checkpoints are never deleted automatically.
3. **Prompt size with a real tokenizer is unmeasured.** The offered tool list is filtered by situation and recall is
   capped (8 items / 1500 characters), but the budget (6144 tokens) was only checked with stand-ins.
4. **Wall-clock budget makes real runs non-reproducible** by design (which inhabitant is skipped when time runs out).
   Mock runs are fully deterministic.
5. **Accelerated clocks** reduce actions per simulated hour (tick > 6 h refused).
6. **The mock policy is test infrastructure**, now memory-guided in foundations mode; its survival numbers say
   nothing about LFM3.
7. **Dense code style** was preserved in files that existed before; new modules are more conventionally formatted.
   `engine.py` still mixes legacy and foundations paths.
8. **Operator access:** hidden state (root, memories, scheduler internals) is hidden from inhabitants and the public
   API, not from whoever owns the run directory.
9. **Public `reason` strings** attached to actions appear in the public event feed, as in v0.4.0.
10. Pre-existing and untouched: `lifecycle.py` / `server.py` unused imports; `Agent.adulthood_recorded` defaults true
    for founders.

## Reviewer commands

```sh
git diff main --stat
git diff main -- caitanya/root.py                              # expect no output
python -m pytest -q
python -m pytest -q tests/test_migration.py tests/test_root.py
python scripts/autonomy_benchmark.py --backend lfm3 --out /tmp/x.json   # without a GPU: writes an explicit 'unverified' record
```
