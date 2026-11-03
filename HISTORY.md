# Development history

## 2026-11-02 — autonomous experiment instrumentation

Inspected origin/main at 26be630 before changes. Preserved root supervision and lifecycle features. Added off/observe/crisis root modes, deterministic recovery tests, confirmed per-action state changes, successful inference counts and GPU metrics, bounded workers, metrics journals, sanitized evidence exports and a Drive-backed real-model Colab notebook. Live experiments and test results are recorded below after verification.

Previous commits: 3baa7e5 (initial world), 26be630 (root and continuity).

Validation: `python -m pytest -q` — 30 passed in 24.76 seconds. This is a CPU engine test suite, not real AI evidence. Tests cover all three root modes, exact replay and journal recovery, read-only witness endpoints and export privacy. Live Colab disconnected during Drive mounting; reconnection is being attempted. No new real-model experiment has yet been claimed.

## 2026-11-03 — autonomy foundations (feature/caitanya-autonomy-foundations)

Branched from 26be630, then merged origin/main (dfb78d5: root modes, bounded workers, evidence export) without rewriting history. Added a fair budgeted decision scheduler with bounded mechanical intentions, time-based physiology, open-ended physical experimentation, structured long-term memory and knowledge transmission, schema 2 with migration of schema-1 runs to legacy mode, read-only witness views, an explicit `--config` loader and CPU benchmarks. The neutral-v4-inquiry prompt and the root, continuity and manifestation code are unchanged. Animals and ecology are deferred.

Validation: `python -m pytest -q` — CPU engine tests only; see docs/EXPERIMENT_RESULTS.md. No real-model (LFM3) run was possible in the authoring environment (no GPU); Stages A/B/C are recorded as unverified. Mock-policy benchmark runs validate mechanics and cost, not autonomy.
