# Corrected integrated LFM3 experiment — in progress

Date: 2026-11-03. Source `ce517b5c5f6ca90e24c64302ed7e2a9db90806b8`; model `LiquidAI/LFM3-1.7B`, revision `ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7`; one shared instance, Tesla T4, backend `lfm3`. Seed 314159, 128×128, ten simulated minutes per tick, foundations mode, default eight-decision budget, root mode crisis, six initial animals per species. Animal activity is deterministic ecology, not inference.

This is a **new** persistent Drive group, separate from the retained debugging prefix `integration-20261103T065039Z`. Stage A requests five humans for 30 simulated days with 5,850 simulation seconds remaining from the original 7,200-second allocation. Stage B requests fifty humans for two days with a 7,200-second ceiling, only after Stage A verifies five real identities and recovery/replay. The 100 MB journal guard also applies. Durations from fresh worlds must not be added as continuous survival.

## Observed prefix and recovery

At tick 60 (0.4167 simulated days), all five humans were living; 300 successful model calls, zero parse/inference or prompt-budget failures, 49 rejected decisions, zero mechanical steps. Each inhabitant had 60 decision attempts. Recorded simulation time was 508.7 seconds, maximum prompt 2,914 tokens, journal size 2,956,765 bytes. These are **prefix counters**, not final run results.

A separate process recovered checkpoint plus journal data at tick 71: state checksum agreement true; exact replay equality true; schema 2; fauna clock 71. The verifier loaded no model and made no decisions or world steps. This is fresh-process data recovery, not a Colab runtime-replacement drill. See [the verification record](fresh-process-prefix-recovery.json).

## Pending

Final Stage A time, population, births/deaths, decision mix, experiment/knowledge metrics, resource consumption and audit; actual fifty-agent operation and results; runtime-replacement recovery for this group. No 30-day survival, invention, human reproduction or philosophical/cultural discovery is claimed. Journals, checkpoints and private memories stay in Drive. The read-only witness and privacy were checked by the CPU endpoint tests; a new live Three.js view for these benchmark processes has not been exposed.
