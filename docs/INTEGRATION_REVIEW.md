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

## Validation recorded on 2026-11-03

`python -m pip install -e ".[test]"` succeeded. Full rerun: `python -m pytest -q` — 214 passed in 629.43 seconds. An additional endpoint-privacy test added after collection passed in the separate four-test integration-evidence run. Targeted migration/root/physics suite: 52 passed, with migration/root files unchanged. Evidence/shared-world suite: 29 passed. Real inference-path stub tests: 3 passed (these use a fake model and are not real inference). Node animal/chronicle tests: 5 passed; viewer syntax check passed. Both historical legacy evidence audits passed. Initial full run: 209 passed, one failed due to token-counter initialization in a fixture that bypasses construction; fixed without modifying that test. Pinned prompt hashes match main.

The three-tick CPU/mock benchmark smoke completed with five living humans, zero births/deaths, equal checkpoint recovery and a passing evidence audit. It is not real AI evidence. New T4 stages use code commit `64e33f3fee58ab2f6bead344dd794fb19953d606`; results are pending.

## Restart replay issue discovered with real saved data

The independent fresh-process verifier at tick 120 matched the committed checksum but direct replay equality was false. A values-free diagnostic isolated `fauna.rng_state`: live tuples versus JSON lists. `fauna/ecology.py` now emits JSON-native RNG lists; serialized JSON bytes/formats remain unchanged. Additional recovered/restored replay assertions cover both autonomy modes and all root modes; 16 wildlife/integration tests passed. No protected core file changed. The original GPU prefix is retained as valid decision evidence but is not labeled a successful exact-replay check. It is being stopped for a corrected-source rerun in a new directory. Benchmark source SHA is now captured at startup and SIGINT/SIGTERM request a stop after the current committed tick.
