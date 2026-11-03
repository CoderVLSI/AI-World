# Wildlife and operations on autonomy foundations

Base: main `a38b935d2b71e455b38fdf1f6aff7e1d0f45895e`. Feature history: `codex/animal-models` at `27a9eb7` (includes chronicle, evidence audit and Colab operations). Review branch: `codex/wildlife-on-autonomy`. Owner review is required before merging; main is not changed by this work.

## Integration decisions A–H

* A: resolved all five textual conflicts, retaining schema 2, autonomy configuration/hash, scheduler state, object/knowledge APIs, human plan/busy/illness display, execution status and animal rendering/endpoints. Public history redacts first, then converts fauna to sanitized wildlife.
* B: one wildlife hook runs after root sustain and before regrowth in both mode-specific step functions. Recovery/replay tests cover both modes and off/observe/crisis roots.
* C: the resource-consumption isolation test explicitly uses legacy mode because foundations humans can gather on that same tick; no assertion was weakened.
* D: observations include wildlife only when enabled and cap local living animals at twelve within eight cells. No prompt text or tool descriptions changed.
* E: evidence includes origin/task IDs; the auditor resolves mechanical steps to preceding intentions, rejects unknown/cross-actor tasks and excludes mechanical steps from model coverage. Mock decisions remain labeled mock; deterministic ecology is not exported as decisions.
* F: matched 50-human journal measurements and projections are in SHARED_WORLD.md and the sanitized JSON under docs/results. Aquatic state already uses the existing general delta journal. Disk format is unchanged. Benchmark runs stop at a decimal 100 MB journal budget and retain partial results.
* G: packaging includes fauna; reinstall after pulling. Coarse legacy clocks explicitly require `--wildlife-per-species 0`, with a clear error and regression test.
* H: updated wildlife/operations/status docs to describe foundations as merged and ecology as integrated. Time-bounded foundations runs use up to eight decisions per tick, unlike legacy's five every third tick.

## Core preservation and additional instrumentation

No changes to `root.py`, `scheduler.py`, `physiology.py`, `experiments.py`, `materials.py`, `memory.py` or `autonomy.py` relative to main. Migration/root tests remain unchanged. The pinned foundation and full system-prompt SHA checks remain unchanged. Engine edits only connect optional ecology and sanitize its public representation; server edits preserve the merged interface. `inference.py` adds real tokenizer counts and prompt-budget failure counters without changing prompt construction or inference settings. `experiment.py` adds public action provenance only. Benchmark changes add Windows portability, explicit wildlife configuration, source SHA, decision samples/counts, bounded storage, recovery and evidence auditing.

## Evidence limits

Earlier five/fifty T4 reports in experiments/ predate foundations plus wildlife. They are preserved as historical legacy evidence: ten and two validated actions per identity respectively, with 80 of 100 fifty-agent actions being eat. They do not verify this integration. New runs must use new Drive directories and the pinned revision `ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7`. Real-run results and remaining blockers are recorded separately from CPU/mock tests. No cultural discovery, human reproduction or long-term civilization claim follows from these short checks.
