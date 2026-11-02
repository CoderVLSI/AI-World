# Development history

## 2026-11-02 — autonomous experiment instrumentation

Inspected origin/main at 26be630 before changes. Preserved root supervision and lifecycle features. Added off/observe/crisis root modes, deterministic recovery tests, confirmed per-action state changes, successful inference counts and GPU metrics, bounded workers, metrics journals, sanitized evidence exports and a Drive-backed real-model Colab notebook. Live experiments and test results are recorded below after verification.

Previous commits: 3baa7e5 (initial world), 26be630 (root and continuity).

Validation: `python -m pytest -q` — 30 passed in 24.76 seconds. This is a CPU engine test suite, not real AI evidence. Tests cover all three root modes, exact replay and journal recovery, read-only witness endpoints and export privacy. Live Colab disconnected during Drive mounting; reconnection is being attempted. No new real-model experiment has yet been claimed.
