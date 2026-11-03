# Implementation status — 0.5.0

Integration branch `codex/wildlife-on-autonomy`, based on main a38b935. This is what is genuinely implemented, what is measured, and what is not. See [docs/MERGE_CHECKLIST.md](docs/MERGE_CHECKLIST.md) for breaking changes and risks and [docs/EXPERIMENT_RESULTS.md](docs/EXPERIMENT_RESULTS.md) for measurements.

## Implemented (CPU-tested; integration validation recorded in docs/INTEGRATION_REVIEW.md)

* **Scheduler (P0):** fair FIFO decision scheduler with a per-tick budget, priority for overdue and interrupted inhabitants, measured waiting and intervals, failure back-off without mock fallback, durable state. Bounded, validated, cancelable intentions (`TRAVEL_TO`, `GATHER_AT`, `REST_FOR`, `CANCEL_TASK`) executed mechanically and attributed separately from model decisions. Optional, default-off, journaled survival reflex.
* **Physiology (P0):** needs, energy, health, illness, regrowth and effort driven by elapsed simulated hours; two-speed and three-seed tests; attributed deaths; guardians prompted to reconsider when dependants are needy; explicit validated configuration recorded in the manifest.
* **Experimentation (P1):** material physics and fifteen object actions (inspect, handle, strike, attach, separate, heat, cool, rub, feed fire, load-test, use as a tool, hand over); mass conserved; meaningful failure; no recipes or named inventions; randomized conservation/rejection fuzz.
* **Memory (P2):** bounded private structured memory with deterministic retrieval, evidence status, revision, persistence and isolation; newborns start empty.
* **Transmission and witness (P3):** witnessing, sharing, teaching and written findings with provenance chains and unverified-claim handling; read-only plan/attribution/object/knowledge views in the Three.js witness and three GET-only endpoints.
* **Compatibility:** schema 2 with explicit migration of schema-1 checkpoints to `legacy` mode (verified bit-for-bit against a real v0.4.0 run); `--legacy`; explicit `--config` (never auto-loaded); the `neutral-v4-inquiry` prompt and the Brahman root, continuity, ledger and manifestation code are unchanged by this branch; `main`'s root modes, bounded workers and evidence export are merged and integration-tested.

* **Animals and ecology:** optional deterministic layer integrated in foundations and legacy; twelve species, shared finite resources, bounded local observations, persistence and read-only witness. Animal behavior is not LLM inference.

## Measured (mock policy only)

5 inhabitants for 30 simulated days (and at one-hour ticks for three seeds) and 50 inhabitants for 7 days all completed with every inhabitant alive; the mock does not experiment or reproduce, so these runs validate mechanics and cost, not autonomy. With 50 inhabitants nobody waited more than 6 ticks for a decision. Under v0.4.0 rules, 50 mock inhabitants died within 3 simulated days.

## Not implemented / not verified

* **Real LFM3 integrated prefix verified:** five identities on T4, source 64e33f3, 155 committed ticks (1.076 simulated days), 775 successful calls and no inference/prompt-budget failures. Restart replay exposed a wildlife RNG tuple/list mismatch; corrected reader ce517b5 recovers the preserved data with exact replay equality. A corrected-source long Stage A and fifty-human Stage B remain pending; generational operation is unverified. See the integration report. No civilization, reproduction, invention or discovery is established.
* **Persistence:** matched short 50-human mock measurements are 35.5 KB/tick without wildlife and 53.0 KB/tick with it. Growth is workload-dependent and checkpoints embed history; linear storage projections are not long-run guarantees. See docs/SHARED_WORLD.md. No automatic off-machine backups, public authentication or permanent Colab hosting.
* Simplified physiology and materials (no metallurgy, containers, spoilage or movement-blocking structures); no calibrated genetics or evolution; no advanced institutions.
