# Experiment results (v0.5.0 development run)

Everything here was measured by the commands in [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md); raw JSON is in
[`results/`](results/). Environment: Linux, Python 3.13, 4 CPUs, 15 GB RAM, **no GPU, no torch installed**.

## Headline

* **Real-model acceptance is UNVERIFIED.** No run with `LiquidAI/LFM3-1.7B` was possible in this environment. Stage A
  (5 inhabitants, 30 simulated days), Stage B (50 inhabitants) and Stage C (generational) were **not run**. The
  harness wrote explicit `unverified_no_gpu` records
  ([A](results/lfm3_stage_a_UNVERIFIED_no_gpu.json), [B](results/lfm3_stage_b_UNVERIFIED_no_gpu.json)). Nothing
  below says anything about how LFM3 behaves, survives, experiments or learns.
* Everything below used the deterministic **mock policy** (a forager that never experiments, reproduces or
  speaks). It validates the scheduler, physiology, persistence and cost, not autonomy.
* The real backend code path (prompt assembly, tool selection, token budget, parsing, attribution) is exercised in
  `tests/test_lfm_path.py` with stand-ins for torch, the tokenizer and the model. This verifies integration only.

## Automated tests

`python -m pytest -q` -> **166 passed** in about 55 s. 25 are the original v0.4.0 tests (the root tests are
unchanged; 7 legacy-coupled tests construct `autonomy='legacy'` explicitly, see MERGE_CHECKLIST). 141 are new:
scheduler 27, physiology 19, experiments 40, memory 21, witness 3, config 21, migration 6, real-backend path 3,
recovery +1.

## Mock runs, completed durations (all reached the requested simulated time)

All inhabitants survived; there were no births (the mock never pursues reproduction), no experiments and therefore no
findings. Needs are time-based (see ARCHITECTURE); the mock had 8 model calls per tick available.

| Run | Sim. time reached | Real time | Living at end | Deaths | Model-labelled decisions | Mechanical steps | Intentions started / completed | Interruptions |
|---|---|---|---|---|---|---|---|---|
| 5 inhabitants, 10-min ticks | 30.0 d (4320 ticks) | 75.8 s (57 ticks/s) | 5 / 5 | none | 4,269 | 17,331 | 2,884 / 2,878 | illness 3 |
| 5 inh., 1-h ticks, seed 314159 | 30.0 d (720) | 9.5 s | 5 / 5 | none | 2,309 | 1,291 | 1,088 / 1,085 | illness 2 |
| 5 inh., 1-h ticks, seed 2 | 30.0 d (720) | 9.5 s | 5 / 5 | none | 2,324 | 1,276 | 1,009 / 1,006 | none |
| 5 inh., 1-h ticks, seed 3 | 30.0 d (720) | 9.8 s | 5 / 5 | none | 2,416 | 1,184 | 1,051 / 1,049 | resource gone 1 |
| 50 inhabitants, 10-min ticks | 7.0 d (1008 ticks) | 76.7 s (13 ticks/s) | 50 / 50 | none | 8,023 | 29,292 | 5,085 / 4,784 | resource gone 272 |

"Decisions" are mock-policy decisions (`mock_decisions`); `lfm_decisions` is 0 in every row. Zero model failures, zero
rejected actions and zero mechanical rejections in every run.

### Fairness (measured)

| Run | Decisions per inhabitant (min / mean / max) | Mean ticks between decisions | Max wait for service | Max interval |
|---|---|---|---|---|
| 5 inh., 30 d | 848 / 853.8 / 857 | 5.06 | 0 ticks | 11 ticks |
| 50 inh., 7 d | 153 / 160.5 / 167 | 6.28 (6.04-6.61) | **6 ticks** | 17 ticks |

With 50 inhabitants and 8 calls per tick the budget was exhausted on 966 of 1008 ticks (demand exceeded supply) and
nobody waited more than 6 ticks (one hour). The fairness bound `ceil(50/8) = 7` held; strict-rotation spread is also
asserted in the tests.

### Cost (measured)

| Run | CPU | Peak RAM | Journal | Checkpoints (sum, 60-tick cadence) |
|---|---|---|---|---|
| 5 inh., 30 d | 71 s | 263 MB | 36.6 MB | 1,347 MB |
| 5 inh., 30 d, 1-h ticks | 9 s | ~100 MB | ~13 MB | ~84 MB |
| 50 inh., 7 d | 74 s | 436 MB | 63.4 MB (about 63 KB/tick) | 572 MB |

GPU memory: not measured (no GPU). **Risks seen here:** at 50 inhabitants the 100 MB journal limit would pause the
worker after roughly 1,580 ticks (about 11 simulated days at baseline), and each checkpoint embeds the whole event
history, so total checkpoint size grows quadratically (1.3 GB for a 5-inhabitant, 30-day run). These are persistence
design properties that already existed; the new systems make events more frequent. Mitigations and the follow-up are
in MERGE_CHECKLIST.

## The original bottleneck, isolated (mechanics only)

`scheduler_comparison.py`, 432 ticks (3 simulated days). A deterministic forager is *labelled as a real model* so
the same constraints apply as to LFM3 (legacy: at most 5 decisions every 3 ticks).

| Inhabitants | Configuration | Living at end | Decisions / inhabitant | Mean ticks between decisions | Basic actions executed / inhabitant |
|---|---|---|---|---|---|
| 5 | v0.4.0 legacy | 5 | 144 | 3.0 | 144 |
| 5 | foundations, single-step, 2 calls/tick | 5 | 172.8 | 2.5 | 172.8 |
| 5 | foundations, bounded intentions, 2 calls/tick | 5 | 88.6 | 4.9 | 359.2 |
| 50 | v0.4.0 legacy | **1** (the 50 inhabitants died of "scarcity"; the survivor is the root's single manifested body) | 8.5 | 50.8 | 8.5 |
| 50 | foundations, single-step, 2 calls/tick | 50 | 17.3 | 25.0 | 17.3 |
| 50 | foundations, bounded intentions, 2 calls/tick | 50 | 17.3 | 25.0 | 21.2 |

Reading it honestly: with 50 inhabitants the v0.4.0 rules could not keep anyone alive (one decision per ~51 ticks
against one need point per tick). Under the new rules all 50 live even at a quarter of the legacy call rate. This row
combines two changes (time-based needs and the scheduler), so it demonstrates the fix, not the effect of either alone.
Bounded intentions multiply executed actions by 2.1x for 5 inhabitants (fewer decisions, more actions), but only by
1.2x at 50 because the mock's plans are short and the budget is the limit. How much intentions help depends on how
long a plan the real model chooses, which is unmeasured.

## Problems that measurement and testing found (and were fixed)

1. **Stale spatial memory** killed the mock population: all five inhabitants stood on a depleted water node that
   their memory still listed. Memory now forgets sites it sees to be empty (test added). Survivors of 5 after 30
   days: 1-2 before; 3 after this fix alone (the other two then died of illness, see 2); 5 after both fixes.
2. **Illness had no counterplay** (1.2 hp/h for 2-5 days exceeds 100 hp). Damage is now reduced while fed, hydrated and
   rested; neglect is still lethal (test).
3. **Journal bloat:** routine path steps rewrote each inhabitant's whole short-term memory list; 81 of 107 MB for the
   50-inhabitant run. Mechanical steps no longer write short-term memory (107 -> 63 MB).
4. **Uneven scheduling rotation** from an id tie-break; now least-recently-served first (spread 1).
5. **Objects cooled in air while the inhabitant held them in a fire;** components are now pinned for the activity.
6. **Water from a stream node was ledgered as lost mass** (conservation error found by the fuzz test).
7. **Metrics rescanned the whole event history every tick;** now incremental counters.

## Not verified / not claimed

* LFM3 behaviour at any scale: survival, intention choice, experimentation, tool-call success rate, latency, GPU
  memory, tokens per second, prompt sizes with a real tokenizer, and the effect of the larger tool list (the model
  is offered a situation-filtered subset of the 41 tools, 14 at the start of a default world, but prompt sizes were
  not measured with a real tokenizer).
* Any experiment, discovery, hypothesis, teaching or written findings by a *model*. The mock does none; the tests drive
  those mechanisms with scripted actions, which prove the mechanisms work, not that inhabitants will use them.
* Births, generations and population growth in a model run. The lifecycle works in tests (a real birth occurs with
  scripted proposals); no autonomous reproduction is claimed.
* Runs longer than 30 simulated days (5 inhabitants) or 7 days (50), journal behaviour past 100 MB, and indefinite
  operation.
* **P4 (animals and ecology) was not implemented.** It is deferred; no wildlife exists in this release.

## Limitations of the models themselves

Physiology, material physics and memory dynamics are simplified experiment parameters with no calibration. Fire exists
only by friction; there is no metallurgy, container, spoilage, shelter or structure that blocks movement.
Accelerated clocks reduce actions per simulated hour (a tick above 6 h is refused). Retrieval and evidence status are
bookkeeping: they do not decide whether a belief is true.
