# Integrated foundations plus wildlife — original prefix, restart requested

Date: 2026-11-03. This is a preserved historical partial observation, **not a completed 30-day or fifty-agent result**.

Source: `64e33f3fee58ab2f6bead344dd794fb19953d606` (later branch commits currently change documentation only). Model: `LiquidAI/LFM3-1.7B`, revision `ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7`. Backend: `lfm3` / `TransformersLFM3Backend`, one shared instance on Tesla T4, CUDA. New private persistent Drive group: `CAITANYA/integration-20261103T065039Z`; earlier experiments were not overwritten.

Settings: seed 314159; 128×128 world; foundations, default scheduler budget 8, ten simulated minutes per tick; five initial humans, six initial animals per species. Wildlife is deterministic ecology, not model agents. Stage A requests 30 simulated days, with a 7,200-second simulation wall-clock ceiling and a 100 MB journal guard. Stage B requests fifty humans for two simulated days under the same limits and only starts after Stage A evidence verifies all five identities.

## Observed committed prefix

At tick 41 (0.2847 simulated days), the persistent progress record showed all five humans living, 205 successful inference calls, zero parse/inference failures, zero prompt-budget failures, 29 rejected decisions, and zero mechanical steps. Each inhabitant had 41 decision attempts; maximum scheduler wait was zero ticks. Recorded simulation time was 364.3 seconds, and the journal size was 1,906,391 bytes. These are prefix counters, not final throughput or survival results.

Actual tokenizer measurements across those 205 requests: minimum 1,938 tokens, maximum 2,877, total 528,924; configured cap 6,144. An earlier tick-six GPU measurement reported peak allocated memory 4,599,890,432 bytes. Final peak memory and checkpoint recovery remain pending.

The first journal inspection contained 128 validated real actions, distributed across all five identities: eat 15, inspect 27, speak 39, drink 15, wait 24, move 5, rest 3. This is an earlier prefix than the tick-41 counters above; the counts must not be combined. No writing, construction, reproduction, invention or philosophical discovery is established by that sample.

Examples from committed tick 1:

| Event | Inhabitant | Action | Model request |
| --- | --- | --- | --- |
| evt-000000006 | agent-0000 | eat | 49055f36-3442-4f21-8a16-9c2cf30c475a |
| evt-000000007 | agent-0001 | inspect | 2cd287d3-d87a-4d02-9a17-3fff86588c41 |
| evt-000000008 | agent-0002 | inspect | 491c6469-e7d4-4838-8f1d-117c49e052ce |
| evt-000000009 | agent-0003 | speak | b02dbd3a-d78b-444a-b0df-23a19d0951a5 |
| evt-000000010 | agent-0004 | speak | bb20e66c-f6d2-4514-a328-418e793824a8 |

These references establish five real-model identities in the observed prefix. Earlier legacy runs had ten and two validated actions per identity, and the fifty-agent legacy run had 80 eat actions out of 100; the integrated prefix has a different action mix. No inference about long-term autonomy follows from that difference.

## Pending

Final Stage A duration, recovery equality, evidence audit, deaths/births and causes, experiment outcomes, knowledge metrics, final resources; Stage B operation and results; runtime-replacement recovery for this new integrated run. The draft PR remains unmerged. Detailed journals/checkpoints/private memories stay on Drive, not GitHub.

## Recovery failure and restart decision

A separate recovery process at tick 120 returned schema 2 and fauna tick 120, with state checksum matching the committed event, but direct replay equality **false**. A diagnostic isolated the differing path to `fauna.rng_state`; no private RNG values were exported. Live tuples and JSON lists had equal canonical serialization but unequal Python types. The integration fix normalizes live fauna RNG state to JSON lists without changing the disk representation. The old prefix is retained; it is not a passed replay acceptance test. The original benchmark is being stopped to run the corrected source in a fresh group. No Stage B success is claimed for this group.

## Preserved endpoint and corrected-reader verification

The original prefix stopped at tick 155: 1.0763888889 simulated days, 1,346.750177039 measured simulation seconds, five living humans, zero births/deaths, generation zero. It recorded 775 successful calls, zero parse/inference or prompt-budget failures, 178 rejected decisions, zero mechanical steps/tasks, and 155 decision attempts per identity with zero maximum wait. Prompts measured 1,938–2,914 tokens (2,023,754 total); inference time 1,334.475 seconds and peak allocated GPU memory 4,730,549,760 bytes. The interrupted in-flight call is outside these committed-prefix counters.

A fresh process using corrected reader commit `ce517b5c5f6ca90e24c64302ed7e2a9db90806b8` recovered those same saved records at tick 155: committed checksum agreement **true**, exact replay equality **true**, fauna clock 155, schema 2. The verifier performed no inference or simulation advancement; this is not runtime-replacement recovery. See [machine-readable observations](../../docs/results/integration-original-prefix-recovery-20261103.json).

Knowledge counters reported 15 practical entries, six independently reproduced findings, zero hypotheses/cultural/procedural entries and zero transfers. These are implementation counters from repeated observations; they do not establish six inventions or philosophical discoveries. Original speech includes repetitive requests for direction. Stage A did not reach its requested 30 days. Stage B was not attempted in this group because the replay issue required a corrected-source restart. The replacement Stage A uses the remaining 5,850 seconds of its original 7,200-second allocation; simulated durations from the two fresh worlds must not be added as survival time.
