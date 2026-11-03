# Corrected integrated LFM3 experiment — stopped for owner handoff

Date: 2026-11-03. Source `ce517b5c5f6ca90e24c64302ed7e2a9db90806b8`; model `LiquidAI/LFM3-1.7B`, revision `ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7`; one shared instance, Tesla T4, backend `lfm3`. Seed 314159, 128×128, ten simulated minutes per tick, foundations mode, default eight-decision budget, root mode crisis, six initial animals per species. Animal activity is deterministic ecology, not inference.

This is a **new** persistent Drive group, separate from the retained debugging prefix `integration-20261103T065039Z`. Stage A requests five humans for 30 simulated days with 5,850 simulation seconds remaining from the original 7,200-second allocation. Stage B requests fifty humans for two days with a 7,200-second ceiling, only after Stage A verifies five real identities and recovery/replay. The 100 MB journal guard also applies. Durations from fresh worlds must not be added as continuous survival.

## Observed prefix and recovery

At tick 60 (0.4167 simulated days), all five humans were living; 300 successful model calls, zero parse/inference or prompt-budget failures, 49 rejected decisions, zero mechanical steps. Each inhabitant had 60 decision attempts. Recorded simulation time was 508.7 seconds, maximum prompt 2,914 tokens, journal size 2,956,765 bytes. These are **prefix counters**, not final run results.

A separate process recovered checkpoint plus journal data at tick 71: state checksum agreement true; exact replay equality true; schema 2; fauna clock 71. The verifier loaded no model and made no decisions or world steps. This is fresh-process data recovery, not a Colab runtime-replacement drill. See [the verification record](fresh-process-prefix-recovery.json).

## Pending

Final Stage A time, population, births/deaths, decision mix, experiment/knowledge metrics, resource consumption and audit; actual fifty-agent operation and results; runtime-replacement recovery for this group. No 30-day survival, invention, human reproduction or philosophical/cultural discovery is claimed. Journals, checkpoints and private memories stay in Drive. The read-only witness and privacy were checked by the CPU endpoint tests; a new live Three.js view for these benchmark processes has not been exposed.

## Final owner-requested handoff stop — verified

The benchmark is stopped and the driver terminated; Stage B did not launch. The final report exists on Drive with status `stopped_by_operator`: **199 committed ticks, 1.382 simulated days, 1,677.83 simulation seconds, five living humans, zero births/deaths, 995 successful calls, zero inference/prompt-budget failures**. The evidence audit passed with five verified identities, 729 validated request-linked actions and zero mechanical steps. Final checkpoint recovery and exact replay equality both passed. Fresh-process prefix recovery separately passed at tick 71. This is not a full Colab runtime-replacement drill.

Validated actions per identity: agent-0000 197; agent-0001 17; agent-0002 121; agent-0003 197; agent-0004 197. Fair scheduling of attempts did not give equal validated success. Action mix: speak 507, inspect 125, eat 26, wait 24, drink 21, gather 17, move 6, rest 3. No invention, writing, human reproduction or philosophical discovery is established. The 995 successful parses minus 729 validated actions leaves 266 nonvalidated attempts; successful inference is not successful world action.

Measured prompts: 1,938–2,914 tokens, 2,584,433 total, 6,144 cap. Inference time 1,660.972 seconds, 13.15 output tokens/second. Peak GPU allocation 4,511.4 MB, max RSS 4,404.9 MB; journal 13,398,662 bytes and checkpoints 38,132,470 bytes. Full final data: Drive group integration-fixed-20261103T072124Z/stage_a.json; selected sanitized fields are committed under docs/results/integration-stage-a-handoff-final-20261103.json.

No model benchmark remains running and no automatic fifty-agent launch remains armed. The Colab notebook/runtime may still be connected, but the model subprocess has exited. Do not resume experiments unless the owner requests it. Long Stage A, integrated fifty-agent operation and full runtime-replacement recovery remain incomplete. The software integration is ready for owner review with those explicit experimental limits; the full experimental phase is not complete.
