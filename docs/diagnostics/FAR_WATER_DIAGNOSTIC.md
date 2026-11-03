# Far-water diagnostic

This is a diagnostic-only experiment. Production caitanya files, neutral-v4-inquiry, tool definitions/descriptions, physics, scheduler, memory implementation and model generation settings are unchanged. Base main: fd692d9 (PR #3 merged). Branch: codex/far-water-diagnostic. Draft PR: https://github.com/CoderVLSI/AI-World/pull/5.

## Fixed scenario, specified before real inference

Five agents start together at (8,24). Focal agent agent-0000 starts at thirst 90/100; the other four retain default thirst zero. Every agent has zero carried water. All fresh-world water nodes are replaced with one standard-capacity water resource, resource-9999 at (23,24). Its distance is 15 Manhattan cells and the straight 15-step route is walkable. The nearest natural water terrain is 22 cells away. Other seeded resources, food, health/energy, geography seed 314159, 128x128 dimensions, six wildlife per species and all engine configuration remain unchanged defaults.

Water at distance 15 is outside the normal eight-cell view. To test known-location navigation rather than blind discovery, fixture initialization briefly places each agent at the actual water node and invokes the existing note_surroundings function, then places them at the start. The focal agent therefore recalls: "water was seen at x=23, z=24, 0 ticks ago (amount 40)". This is explicit seeded fixture prehistory, not an autonomous discovery, instruction to use a particular tool, or memory from an existing run. No prompts or observation methods are overridden.

Initial water is not in the visible resource list. Recall supplies coordinates, not a privileged resource ID. The model can choose TRAVEL_TO using those coordinates; it can see the water resource ID normally after approaching within eight cells. GATHER_AT may initially be offered for other local resources, but its selection does not automatically mean water-seeking.

The default root mode remains crisis and the default survival reflex remains disabled. Only one agent is highly thirsty, so the fixture does not start with the entire population in the root's universal-need crisis condition. No threshold or physiology rate was changed. All five real agents remain free to choose their actions; their CPU stand-ins are deliberately scripted.

The initial full-state fingerprint excluding backend manifest is a338d14b3293272747af6e9b662dc386e0b1935e4b9e88a3b4d91520e8d28cd4. Both CPU strategies use that identical fingerprint; the GPU fixture fingerprint will be checked against it.

## CPU scripted comparison — not real inference

Both policies use the ordinary recalled water location and visible resource IDs. They do not receive an oracle location unavailable to the real model. The four nonfocal CPU agents simply WAIT so this comparison isolates execution mechanics. These CPU decisions are explicitly mock_policy, not LFM decisions.

| Focal strategy | Focal scripted decisions | Automatic walking steps | Arrival tick | First drink tick |
| --- | ---: | ---: | ---: | ---: |
| TRAVEL_TO, then GATHER, DRINK | 3 | 15 | 16 | 18 |
| Fifteen MOVE calls, then GATHER, DRINK | 17 | 0 | 15 | 17 |

TRAVEL_TO does not teleport or walk faster. It costs an initial decision tick, then walks one cell per tick without new decisions; repeated MOVE starts walking on its first decision. The benefit here is fewer decision calls, with one extra simulated tick to drink. Both finish at (23,24), health 100, five agents alive, zero root arrivals. Their final thirst values are approximately 61.25 and 60.90, reflecting the extra tick rather than altered need rates.

[CPU results](far-water-cpu-20261103/CPU_COMPARISON.json). Nine targeted tests passed (two new scenario tests plus the seven previous diagnostic/inference-path tests); the two new tests were also rerun successfully after the metadata change. Tests check distance, visibility, recalled knowledge, unchanged default reflex/root settings, identical initial fingerprints, movement/decision counts, arrival/hydration and population.

## Single bounded real-model episode

Source: c537c20637a291d184811ffa7725c627f7089be1. New private Drive directory: /content/drive/MyDrive/CAITANYA/far-water-short-20261103T101003Z. Actual GPU preflight: Tesla T4. Pinned model: LiquidAI/LFM3-1.7B, revision ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7, one shared instance, no fallback.

One episode only: five agents, at most 50 ticks. The supervisor has a hard 300-second worker timeout, including worker/model startup. The sampling loop uses 250 seconds to reserve 50 for initialization/finalization; this is a budget guard, not a change to model/simulation settings. Normal full-tick completion can exceed the sampling threshold, while the external timeout enforces the 300-second ceiling. On timeout, only committed journal/progress data may be reported. No automatic follow-on or rerun exists.

Generation remains the production default: greedy, max_new_tokens224, max_time15 seconds/call, repetition_penalty1.1, prompt cap6144. All five agents use genuine inference; the CPU stand-in is not used in the GPU episode. Instrumentation reuses the existing diagnostic observer without modifying returned tool lists, decoded output, prompts or world-action results.

## Actual T4 result

The supervisor recorded worker_exited, returncode0, hard_cap_seconds300 and follow_on_runs0. Sampling stopped at 18 ticks after 251.9610289580014 simulation seconds, before the 50-tick maximum. The worker finished normally within its300-second process timeout. No follow-on run or rerun started.

There were 68 inference calls: 64 successfully parsed and 4 parse/inference failures. Fifty-nine actions validated, five were rejected, and four produced no parsed action. Prompt sizes were 2349–4204 tokens, below the unchanged 6144 cap; there were zero prompt-budget failures. Peak allocated GPU memory was 6,003,445,248 bytes. Recovery digest equality passed.

| Requested tool | Parsed selections, all five agents | Parsed selections, focal agent | Requests offering tool |
| --- | ---: | ---: | ---: |
| TRAVEL_TO | 0 | 0 | 68 |
| GATHER_AT | 0 | 0 | 68 |
| REST_FOR | 0 | 0 | 68 |
| MOVE | 5 | 1 | 68 |

All nonzero parsed tool choices: SPEAK 31, TEACH 16, WAIT 10, MOVE 5, EAT 2. There were no parsed intention calls. These are parsed-selection counts; the four failed calls must not be silently counted as WAIT or assumed to contain no attempted intention. Their individual error messages/raw declared tool names were not retrieved before browser control became unavailable. The combined failure count is recorded, not hidden or relabeled.

The focal agent received 13 requests, produced 12 parsed choices, and had 11 validated actions. Its parsed choices were SPEAK 7, WAIT 2, EAT 1, MOVE 1 and TEACH 1. The teaching attempt did not validate. Its one movement ended at (8,23), farther from the remembered water at (23,24): 16 cells away rather than the initial 15. Its final thirst was 96.249996, health 100 and carried water 0. It never reached the water, gathered water or drank during this episode. There were no focal mechanical steps, no root arrivals, and all five agents remained alive.

**Plain-language conclusion:** the scripted comparison demonstrates that the existing travel intention can cover the route using far fewer decision calls. In this bounded real-model episode, the model mainly talked/taught/waited instead of acting on the remembered water location. It failed to obtain water. This is an observed outcome, not evidence that the model can never navigate or use intentions. The episode ended on the time budget at 18 ticks, not 50. No extra trial was used to improve the outcome.

The GPU summary reports the same fixture fingerprint as both CPU policies. The known-location memory is explicitly seeded fixture prehistory, not a claimed discovery. All five agents are co-located, so social tools are available; the four nonfocal CPU stand-ins WAIT, while all five real agents choose freely. Therefore the CPU comparison isolates mechanics and is not a prediction that the model should follow the same strategy.

## Saved evidence and integrity

- [Exact real diagnostic summary](far-water-short-20261103.json).
- [Summary checksum](far-water-short-20261103.json.sha256).
- Private Drive: far-water-short-20261103T101003Z/FAR_WATER_SUMMARY.json, FIXTURE.json, SHORT_DIAGNOSTIC.json, SUPERVISOR.json, events.jsonl, checkpoints and logs.

The committed GPU summary SHA-256 is 10f27b1abe7acc4b9ba2b01f00ab748793cf09b8d5389cba5089110fa073f352, matching the saved Drive summary byte-for-byte. The full per-request diagnostic and raw journals remain in the new Drive folder. Existing runs were not overwritten. An additional read-only details query was submitted to inspect the four failures and compare FIXTURE.json directly, but its output was not retrieved after browser control became unavailable. The primary final summary, checksum, counts, outcome and supervisor result above had already been retrieved and verified. No new GPU run is needed to inspect those saved details.

Production files, tool descriptions and the prompt remain unchanged. This PR adds only diagnostic setup/tests and new artifacts; it does not merge, tune settings, force model choices, remove social tools or change failure handling.
