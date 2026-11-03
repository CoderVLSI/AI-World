# CAITANYA — implementation and experiment handoff

Updated 2026-11-03. The owner requested an immediate handoff instead of further long-running experiments. Do not automatically restart GPU work.

## Start here

- Repository: https://github.com/CoderVLSI/AI-World
- Existing draft PR: https://github.com/CoderVLSI/AI-World/pull/2 — OPEN, UNMERGED. Continue this PR; do not create a duplicate or merge it.
- Branch: `codex/wildlife-on-autonomy`.
- Verified integration base: `a38b935d2b71e455b38fdf1f6aff7e1d0f45895e` (main, autonomy foundations v0.5.0).
- Feature source merged into this branch: `27a9eb77739ab3aff94e9e5e061c12cb4d3c0e25` (`codex/animal-models`, containing wildlife, chronicle, evidence auditing and operations).
- Last pushed commit before this handoff document: `38414dffcc0344e5c6064b6ae0f5f0447afc60c1`. The handoff commit itself comes after this; resolve the branch HEAD rather than assuming this is final.
- Real corrected GPU code commit: `ce517b5c5f6ca90e24c64302ed7e2a9db90806b8`. Later commits record results/documentation and fix the storage-measurement script's dirty-worktree metadata; the active GPU checkout was not mutated.
- Windows worktree: `C:/Users/Admin/Documents/ChatGPT/CAITANYA-autonomy-integration`.
- Original workspace: `C:/Users/Admin/Documents/ChatGPT/New project`.

The software integration is implemented, pushed and CPU-tested. The extended real-model experiments are incomplete. Five real identities are verified; fifty real identities on this integrated code are NOT verified. No work was merged into main.

## What was implemented

1. Merged the animal-models history onto autonomy foundations, resolving the five conflicts in engine.py, server.py, viewer.js, HISTORY.md and IMPLEMENTATION_STATUS.md.
2. Preserved humans alongside twelve deterministic wildlife species, shared terrain/finite resources, species-specific procedural 3D animal models/animation, the animal census/gallery, and the human family tree/timeline/chronicle.
3. World accepts root_mode, autonomy and wildlife_per_species together. State remains schema 2 and preserves autonomy_hash, scheduler, materials/objects and legacy migration.
4. Added one wildlife hook to BOTH foundations and legacy step loops, after root sustain and before regrowth. Wildlife is explicitly deterministic_ecology, never model inference.
5. Wildlife observations are optional, limited to twelve living animals within eight cells. Worlds/checkpoints without fauna stay without fauna.
6. Preserved read-only APIs, execution/paused status, checkpoint_every, config/legacy/scheduler CLI options, human plan/busy/illness UI, wildlife endpoints and static mounts. Snapshot/history redact private data before exposing sanitized wildlife.
7. Evidence exports include origin/task_id. The offline auditor distinguishes mechanical task steps from decisions, requires prior same-actor intention provenance, rejects unknown task IDs, excludes mechanical steps from real-agent coverage, and rejects structured private fields. Real intentions require model request IDs; mock intentions remain labeled mock_policy.
8. Added actual tokenizer token counters and prompt-budget failure metrics without changing system prompts or tool wording.
9. Improved benchmark portability, explicit wildlife configuration, source SHA captured at startup, action samples/counts, storage limits, progress.json, checkpoint recovery/exact-replay results and cooperative SIGINT/SIGTERM stopping after a committed tick.
10. Updated packaging/notebook/operations/docs. Coarse legacy clocks clearly require wildlife-per-species 0. Added storage measurement tooling and sanitized experiment records.

### Important bug found and fixed

Independent recovery of real saved data matched the committed checksum but initially failed direct replay equality. Only fauna.rng_state differed: live tuples versus JSON lists. fauna/ecology.py now produces JSON-native RNG lists. This does NOT change the serialized JSON format. Regression tests now assert replay equality after recovery and restore in both modes and all three root modes. Corrected-reader recovery passed on both the preserved original run and newly written corrected-run data.

### Protected code and prompts

No changes relative to main in:
`caitanya/root.py`, `scheduler.py`, `physiology.py`, `experiments.py`, `materials.py`, `memory.py`, `autonomy.py`.

`tests/test_root.py` and `tests/test_migration.py` remain unchanged. No tests were weakened. The shared-herb wildlife test explicitly uses legacy mode to isolate animal consumption: foundations humans can gather on the same tick.

Pinned prompt version: neutral-v4-inquiry.
- FOUNDATION SHA-256: d367332c9f55577da748fe40a2acd83163e5a76a978231fda4ed2364c45793ee
- Full system message SHA-256: e11f482d78ed8b1c226f45c93f7b29f169a7993d154777f61634e1d31f091b36

No scripture, named deity, revelation, hunting/domestication recipe or prescribed philosophical outcome was added to inhabitant prompts/tools. Root implementation and privacy remain preserved.

## Actual validation

- `python -m pip install -e ".[test]"`: succeeded.
- Final full `python -m pytest -q`: **215 passed in 698.16 seconds**, after RNG normalization.
- `node --test tests/animal-models.test.mjs tests/chronicle.test.mjs`: **5 passed**.
- `node --check web/viewer.js`: passed.
- Targeted unchanged migration/root/physics suite: 52 passed.
- Wildlife/shared-world/integration-evidence suite after RNG fix: 16 passed.
- Inference-path tests: 3 passed; these use a fake model and are NOT GPU evidence.
- Both preserved historical legacy evidence files passed the updated auditor.
- Both autonomy modes and off/observe/crisis roots have checkpoint, recovery and replay coverage with fauna.
- Public endpoint tests check private LTM/memories/root/RNG absence and POST rejection. Public scheduler aggregate metrics are allowed; private scheduler records are not.

The first full run had one failure because token counters were uninitialized in a fixture bypassing __init__. It was fixed without weakening that fixture/test; subsequent full runs passed.

Local test output: runs/integration-validation-20261103/pytest-final.txt (ignored private/local run directory).

## Storage measurement

Clean measurement commit 617c63f9e7b527283b03ff9fe2553f1ca3bc4071; seed 314159; 128x128; 50 mock humans; 60 ticks each:
- Without wildlife: 2,131,438 journal bytes, 35,523.97 bytes/tick.
- Six animals per species: 3,182,236 bytes, 53,037.27 bytes/tick.
- Wildlife overhead: 49.30% in this sample.
- Linear projections to a decimal 100 MB guard: 19.55 / 13.09 simulated days. These are projections, NOT observed storage lifetimes.

The post-fix totals exactly match the earlier measurement, supporting unchanged saved format/size. Do not redesign persistence without a separate compatibility plan.

## Real GPU work — verified facts

Model: LiquidAI/LFM3-1.7B, text-only, revision ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7. Actual GPU: Tesla T4. One shared instance per run; backend explicitly lfm3; no mock fallback.

Colab notebook: https://colab.research.google.com/drive/13zJa2pJSeP_ERGauqZMzCfVoeaUCKHpX

Drive root: /content/drive/MyDrive/CAITANYA

### Original integrated prefix — preserved, stopped for replay fix

Group: integration-20261103T065039Z. Code: 64e33f3fee58ab2f6bead344dd794fb19953d606.
- 155 committed ticks = 1.0763889 simulated days; 1,346.75 measured simulation seconds.
- Five living humans; zero births/deaths; generation zero.
- 775 successful inference calls; zero parse/inference or prompt-budget failures.
- 178 rejected decisions; zero mechanical steps/tasks.
- Each identity had 155 decision attempts; maximum scheduler wait zero.
- Prompts: 1,938–2,914 tokens, cap 6,144. Peak allocated GPU memory: 4,730,549,760 bytes.
- All five identities have validated actions linked to actual request IDs; examples are in the report.
- Actions include eat, inspect, speak, drink, wait, move and rest. Rejections include unknown object, resource unavailable and resource out of reach.
- Speech repeatedly asks what to do next. Do not describe this as successful planning/collaboration. Inspection/reproduced-finding counters do not establish inventions.
- Corrected reader ce517b5 recovered the preserved tick-155 journal with checksum AND exact replay equality true. No model inference was performed by the recovery verifier.

### Corrected run — handoff stop requested

Group: integration-fixed-20261103T072124Z. Code: ce517b5c5f6ca90e24c64302ed7e2a9db90806b8.
- New world and new directory; never combine its survival duration with the original prefix.
- Stage A requested 30 simulated days with 5,850 simulation seconds remaining after the earlier debugging prefix. Stage B was conditional, population 50, two days, max 7,200 seconds.
- Last observed committed progress BEFORE handoff stop: tick 190, 1.3194 simulated days, 1,602.2 simulation seconds; five living humans, 950 successful calls, zero inference/prompt-budget failures, 248 rejected decisions, zero mechanical steps. Each identity had 190 attempts. Journal: 12,718,690 bytes. These are prefix counters, NOT necessarily the final stop report.
- A fresh process recovered this new run at tick 71 (checkpoint plus journal tail): checksum true, exact replay equality true, fauna tick 71, schema 2.
- At saved tick 180 all five had health 100, but carried no food/water. Thirst ranged approximately 41–61. Being alive at that point does not establish self-sustaining civilization.
- Owner requested handoff. The stage driver was terminated to prevent automatic Stage B launch, and the uniquely identified benchmark child was sent cooperative SIGTERM. Check stage_a.json for final stopped_by_operator results and the final checkpoint/report. Do not assume the last observed prefix is the final tick.
- No fifty-agent integrated GPU result exists yet. No 30-day real survival or generational/cultural claim is established.

### Private persistent files

Each group retains stage_a/events.jsonl, checkpoint-*.json, progress.json, process logs, launch metadata and recovery records. Completed corrected-stage shutdown also writes stage_a.json and stage_a/summary/evidence.json + REPORT.md. handoff-stop.json records why work stopped. Keep raw journals, checkpoints, private memories, tokens and model internals out of GitHub.

The corrected Colab source checkout is /content/CAITANYA-integration-fixed-ce517b5. Original checkout /content/CAITANYA-integration-20261103 was not mutated. The driver variable in the notebook is integration_process; group path is GROUP. Do NOT rerun the launch cell during handoff. No public tunnel was opened. A new live Three.js view for these benchmark processes was not exposed; read-only/privacy checks were automated CPU endpoint tests.

## Read these repository artifacts

- docs/INTEGRATION_REVIEW.md — A–H resolutions, code preservation, tests, debug history.
- HISTORY.md and AGENT_LOG.md.
- experiments/integration-20261103T065039Z/REPORT.md — preserved original prefix, actual samples and failure/fix.
- experiments/integration-fixed-20261103T072124Z/REPORT.md — corrected run prefix and fresh-process recovery proof; update with final stop result if available.
- docs/results/integration-original-prefix-recovery-20261103.json.
- docs/results/integration-mock-wildlife-cost-fixed-20261103.json.
- docs/SHARED_WORLD.md, FAUNA.md, COLAB_OPERATIONS.md, EVIDENCE_AUDIT.md.
- docs/AUTONOMY_ARCHITECTURE.md, MERGE_CHECKLIST.md, EXPERIMENT_PROTOCOL.md and EXPERIMENT_RESULTS.md.

Historical five/fifty reports dated Nov 2 use the OLD legacy scheduler. They are preserved historical evidence, not integrated fifty-agent verification.

## Remaining work, in useful order

1. Read the existing PR/diff and this handoff. Fetch origin and verify branch/main; never overwrite someone else's changes.
2. Confirm the corrected GPU benchmark stopped and Stage B did not launch. If Colab is accessible, collect its final sanitized stage_a.json/summary and update the corrected experiment report. If inaccessible, state that explicitly and retain the known prefix facts.
3. Update PR #2 description to reflect the final 215-test pass, replay repair and actual handoff-stop status. Current PR body may still describe the extended run as pending.
4. Review evidence privacy and action provenance, especially mechanical task IDs, model request coverage and historical-vs-current labels.
5. Owner review decides whether to merge. Do not merge or push main automatically.
6. Extended Stage A, integrated fifty-agent operation and full Colab runtime-replacement recovery remain incomplete. Do not resume long GPU experiments until the owner asks; provide a concrete remaining-work/budget summary first.

No inference batching, sparse aquatic persistence migration, hunting/domestication, model behavior fix or larger-map redesign was implemented in this integration assignment. Those are separate feature work. Do not silently change prompts to make behavior look better.

## Copy-paste prompt for Claude

You are taking over CAITANYA integration work. Read CAITANYA_HANDOFF.md in CoderVLSI/AI-World on branch codex/wildlife-on-autonomy, then inspect existing draft PR #2: https://github.com/CoderVLSI/AI-World/pull/2. Continue that PR; do not merge it or push main. The integration is implemented and pushed; 215 Python tests and five Node tests passed. Five genuine LFM3 identities are verified on T4, but extended and fifty-agent checks are incomplete. A wildlife RNG tuple/list replay bug was fixed and verified against actual saved journals. First confirm the handoff stop, collect the corrected run's final sanitized stop report if Colab is accessible, and update the experiment report/PR with exact verified facts. Preserve all data, protected root/autonomy code and the pinned neutral prompt. Do not fabricate results or launch more long GPU runs without a new owner request. Then provide a concise review, remaining blockers and whether this is ready for owner review. Do not spend hours monitoring: make a concrete bounded handoff/review and report clearly.
