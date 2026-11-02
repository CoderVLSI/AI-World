# Development history

## 2026-11-02 — autonomous experiment instrumentation

Inspected origin/main at 26be630 before changes. Preserved root supervision and lifecycle features. Added off/observe/crisis root modes, deterministic recovery tests, confirmed per-action state changes, successful inference counts and GPU metrics, bounded workers, metrics journals, sanitized evidence exports and a Drive-backed real-model Colab notebook. Live experiments and test results are recorded below after verification.

Previous commits: 3baa7e5 (initial world), 26be630 (root and continuity).

Validation: `python -m pytest -q` — 30 passed in 24.76 seconds. This is a CPU engine test suite, not real AI evidence. Tests cover all three root modes, exact replay and journal recovery, read-only witness endpoints and export privacy. Live Colab disconnected during Drive mounting; reconnection is being attempted. No new real-model experiment has yet been claimed.

## Colab operations branch

Implementation commit dfb78d59491b976286d0c0a7c5fb04c4e9306b69 is on main. Subsequent work is isolated on codex/colab-operations to avoid Claude's feature/caitanya-autonomy-foundations scope. Added a Drive storage preflight, a read-only deployment acceptance probe, operational recovery instructions and an evidence-backed incident report at experiments/2026-11-02-colab-reconnection/REPORT.md. No scheduler, physiology, materials, memory or root-policy changes are made on this operations branch.

Colab disconnected during Drive setup. Reconnection yielded an empty runtime; /content/caitanya_runs and the prior backend were absent. A later OAuth attempt returned Error 400 invalid_request. Therefore old raw journals were not backed up, and no latest-source five- or fifty-agent run or Drive recovery has been verified. Earlier notebook output is documented as historical partial evidence only.

Operations validation: `python -m pytest -q` — 32 passed in 15.97 seconds. New checks verify that storage preflight preserves existing files, refuses missing or out-of-Drive destinations, and that the deployment probe rejects a mock server while confirming read-only snapshot behavior and private-state filtering. `python -m compileall -q scripts` and `git diff --check` passed. No live-model result is inferred from these tests.

21:41 IST retry: refreshed Colab and repeated existing-account Drive sign-in. Mount failed after approximately 122 seconds. Independent code execution verified Drive unavailable and Tesla T4 available. No new AI experiment was started; details appended to the incident report.

Following the user's manual Drive repair, storage write/fsync/readback passed. Main dfb78d5 was fetched into a clean Colab checkout, its automated suite completed successfully, and a new real LFM3 process ran five agents for 30 ticks. Every identity has ten validated model-request-linked actions: 50 successful calls, zero failures/rejections, five survivors. Drive-backed recovery in a fresh process matched the saved public state exactly. Sanitized reports are under experiments/five-20261102T162454Z. This is a short activation/survival smoke test; no civilization milestone is claimed. A separate bounded fifty-agent run was launched afterward.

Fifty-agent benchmark completed 60 ticks with 100 successful validated model calls, two per identity, no inference failures/rejections and fifty survivors. Reports are under experiments/fifty-20261102T163129Z. No births, inventions or cultural milestones occurred. Private histories remain on Drive. Both sanitized exports were checked for action coverage and absence of private memory/root/reason-summary fields. No core simulation code was changed for these experiments.

Colab Restart session drill passed: notebook variables were cleared, the model was reloaded and the fifty-agent Drive world recovered at tick 60 with the same public-state hash. Root information remained hidden, viewer HTTP was 200 and snapshot POST was 405. A complete VM-replacement drill was not performed. The worker is budget-stopped after recovery. Colab's authenticated preview/output bridge still stalls, so browser rendering is not claimed. Local suite previously passed 32 tests; the fetched main suite also completed successfully in Colab before launching. Subsequent changes are evidence and documentation only.
