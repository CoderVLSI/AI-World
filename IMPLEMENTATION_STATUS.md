# Implementation status — 0.5.0

Branch `feature/caitanya-autonomy-foundations`. This is what is genuinely implemented, what is measured, and what is not. See [docs/MERGE_CHECKLIST.md](docs/MERGE_CHECKLIST.md) for breaking changes and risks and [docs/EXPERIMENT_RESULTS.md](docs/EXPERIMENT_RESULTS.md) for measurements.

## Implemented (CPU-tested; 166 tests)

* **Scheduler (P0):** fair FIFO decision scheduler with a per-tick budget, priority for overdue and interrupted inhabitants, measured waiting and intervals, failure back-off without mock fallback, durable state. Bounded, validated, cancelable intentions (`TRAVEL_TO`, `GATHER_AT`, `REST_FOR`, `CANCEL_TASK`) executed mechanically and attributed separately from model decisions. Optional, default-off, journaled survival reflex.
* **Physiology (P0):** needs, energy, health, illness, regrowth and effort driven by elapsed simulated hours; two-speed and three-seed tests; attributed deaths; guardians prompted to reconsider when dependants are needy; explicit validated configuration recorded in the manifest.
* **Experimentation (P1):** material physics and fifteen object actions (inspect, handle, strike, attach, separate, heat, cool, rub, feed fire, load-test, use as a tool, hand over); mass conserved; meaningful failure; no recipes or named inventions; randomized conservation/rejection fuzz.
* **Memory (P2):** bounded private structured memory with deterministic retrieval, evidence status, revision, persistence and isolation; newborns start empty.
* **Transmission and witness (P3):** witnessing, sharing, teaching and written findings with provenance chains and unverified-claim handling; read-only plan/attribution/object/knowledge views in the Three.js witness and three GET-only endpoints.
* **Compatibility:** schema 2 with explicit migration of schema-1 checkpoints to `legacy` mode (verified bit-for-bit against a real v0.4.0 run); `--legacy`; explicit `--config` (never auto-loaded); the `neutral-v4-inquiry` prompt and the Brahman root, continuity, ledger and manifestation code are unchanged.

## Measured (mock policy only)

5 inhabitants for 30 simulated days (and at one-hour ticks for three seeds) and 50 inhabitants for 7 days all completed with every inhabitant alive; the mock does not experiment or reproduce, so these runs validate mechanics and cost, not autonomy. With 50 inhabitants nobody waited more than 6 ticks for a decision. Under v0.4.0 rules, 50 mock inhabitants died within 3 simulated days.

## Not implemented / not verified

* **Animals and ecology (P4): deferred.**
* **No real-model run.** Stage A (5 inhabitants, 30 days), Stage B (50 inhabitants) and Stage C (generational) were not run for lack of a GPU; the harness records them as `unverified`. No autonomous civilization, reproduction, invention or discovery is claimed, and no consciousness or divine agency is established.
* Persistence growth: about 63 KB of journal per tick at 50 inhabitants and quadratic checkpoint growth; the 100 MB journal limit is reached after roughly 11 simulated days at that population. No automatic off-machine backups, no authentication for public deployment, no permanent Colab hosting.
* Simplified physiology and materials (no metallurgy, containers, spoilage or movement-blocking structures); no calibrated genetics or evolution; no advanced institutions.
