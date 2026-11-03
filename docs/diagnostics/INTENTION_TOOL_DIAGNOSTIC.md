# Intention-tool and agent-0001 diagnostic

Date: 2026-11-03. This is a short diagnostic, not a civilization benchmark. No production code, system prompt, tool definition/description, model generation parameter, root code or existing experiment data was changed. New branch: codex/intention-tool-diagnostic; base main 7dafeef (PR #2 already merged). Draft PR: https://github.com/CoderVLSI/AI-World/pull/3.

## Plain-language finding

The intention machinery is available and working. The real model simply did not select it in this measured sample. TRAVEL_TO, GATHER_AT and REST_FOR reached the model on every one of 100 requests, but appeared zero times in both decoded tool names and parsed choices. No inference/parsing errors occurred. Synthetic CPU probes show all three parse, validate and execute mechanical steps. Therefore the zero count is not explained by those tools being missing, filtered out, too large for the prompt, or rejected by the parser.

This observation does not establish why the model prefers other actions. Overlap with simpler MOVE/REST and inconsistent descriptions of automatic continuation are plausible contributors, not demonstrated causal explanations. No description A/B test was run, and no description changes were applied. Do not conclude that the model can never choose intentions.

Zero mechanical steps alone also does not prove zero attempted intentions: an intention could have been rejected or selected at the final tick. Stage A's rejection records omit attempted tool names/parameters. The new diagnostic records pre-validation choices to remove that uncertainty for this new run.

## Exact CPU tools and prompt

The diagnostic intercepts the actual TransformersLFM3Backend.decide method after its existing observation preprocessing/select_tools, before inference. It uses a synthetic fresh world matching Stage A settings, first scheduler request, agent-0000 at tick 1. It then renders with the real pinned LFM3 tokenizer on CPU. No weights load and zero model inference calls occur in this CPU capture.

Exact initial ordered list (15): REFLECT, MOVE, GATHER, REST, EAT, DRINK, WAIT, SPEAK, WRITE, TRAVEL_TO, GATHER_AT, REST_FOR, PICK, INSPECT, HYPOTHESIZE. This is the initial captured list; later requests can offer additional memory tools as state changes.

- [Exact rendered prompt](intention-tools-cpu-20261103/cpu_prompt.txt), including system text, all tool descriptions/schemas, observation and assistant tool-call prefix.
- [Exact messages/tools/observation](intention-tools-cpu-20261103/cpu_request.json).
- [Token count, ordered names and synthetic parser probes](intention-tools-cpu-20261103/cpu_capture.json).

The captured prompt is 2,268 tokens. Full system SHA-256 remains e11f482d78ed8b1c226f45c93f7b29f169a7993d154777f61634e1d31f091b36. Full rendered synthetic prompt SHA-256: ab0e5a9eca6971ccdfbd8dd51df8302fda16a0ff5927fcb79443a159a9f85b35.

Current descriptions, unchanged:

- TRAVEL_TO: "Start walking to the grid position x,z along a walkable route. Steps run without new decisions and the walk ends if circumstances change. Optionally say why and after how many hours you want to reconsider."
- GATHER_AT: "Walk to an observed resource and gather up to the given number of units there. Ends early if the resource is gone or circumstances change."
- REST_FOR: "Rest for the given number of hours; ends early if circumstances change."

The parser recognizes uppercase names with underscores; x/z, resource_id/amount and hours are accepted. Optional reason is removed into the intent's reason summary; it is not required. Each synthetic probe produced one mechanical step after its first following tick. These are scripted CPU tests, not model decisions.

## One short GPU diagnostic

Code: 14acb7c486556e3f11ef58240fcd5e45360138ce. Model: LiquidAI/LFM3-1.7B, revision ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7. GPU: Tesla T4, one shared model instance, actual TransformersLFM3Backend. Foundations defaults: seed 314159, five humans, 128x128, wildlife six/species, ten simulated minutes/tick. The production generation settings were not tuned: greedy generation, max_new_tokens 224, max_time 15 seconds/call, repetition_penalty 1.1, prompt cap 6,144.

New private Drive directory: /content/drive/MyDrive/CAITANYA/intention-short-diagnostic-20261103T092244Z. Full private world checkpoints/journal remain there; no old run directory was reused. The full sanitized request-choice diagnostic is SHORT_DIAGNOSTIC.json. It records offered tools, decoded tool names, parsed choices, safe public ID/coordinate parameters, and world validation outcomes; no speech/reflection text, raw model output or private memory text is exported.

Budget: at most 20 ticks (less than the owner's 50-tick ceiling), five agents, 300 simulation-second cap. Actual: 20 ticks, 155.990875925 simulation seconds, 100 successful inference calls, zero parse/inference failures, zero prompt-budget failures. Prompts 1,938–2,824 tokens. Ninety-six actions validated; four were rejected. Recovery digest equality passed. The diagnostic exited with code 0 and no follow-on experiment is scheduled.

| Tool | Model selections | Requests offering it |
| --- | ---: | ---: |
| SPEAK | 29 | 60 |
| WAIT | 24 | 100 |
| INSPECT | 18 | 100 |
| EAT | 11 | 79 |
| DRINK | 9 | 69 |
| MOVE | 5 | 100 |
| REST | 3 | 100 |
| GATHER | 1 | 87 |
| TRAVEL_TO | 0 | 100 |
| GATHER_AT | 0 | 100 |
| REST_FOR | 0 | 100 |

All other registered tools had zero selections. The [new short-diagnostic JSON](intention-tools-short-20261103.json) contains every tool's selection and offer count, including zero/unavailable cases. Raw decoded tool-name counts equal parsed counts, so intentions were not silently lost in parsing. Scheduler totals: 100 LFM decisions, zero mock decisions, zero tasks started and zero mechanical steps. Each agent received 20 requests, with zero maximum queue wait. This is a small observational run, not a causal intervention or proof of long-term autonomy.

## Why agent-0001 had only 17 validated Stage A actions

The old journal was read, not modified. All five agents had 199 parsed decision attempts. Their outcomes were:

| Agent | Validated | Rejected | Recorded rejection reasons |
| --- | ---: | ---: | --- |
| agent-0000 | 197 | 2 | resource unavailable: 2 |
| agent-0001 | 17 | 182 | unknown object: 179; resource out of reach: 3 |
| agent-0002 | 121 | 78 | unknown object: 78 |
| agent-0003 | 197 | 2 | resource unavailable: 2 |
| agent-0004 | 197 | 2 | resource unavailable: 2 |

It was a validation problem, not fewer scheduling opportunities or inference failures. Agent-0001's first historical rejection is evt-000000133 at tick 18; the next two are evt-000000140/tick19 and evt-000000146/tick20.

The new unmodified-policy diagnostic independently reproduces its first 17 accepted requests followed by these three rejected requests:

| Tick | Chosen call | World result |
| --- | --- | --- |
| 18 | INSPECT(subject="water: renewable") | unknown object |
| 19 | INSPECT(subject="water: spawn-water-1") | unknown object |
| 20 | INSPECT(subject="water: renewable") | unknown object |

Those strings are not resource/object IDs and are not the supported inventory:<material> form. The XML parses successfully, but the world looks for the exact string and finds no matching object. At these diagnostic positions, the visible, reachable inspection subject was resource-0375; spawn-water-1 remained visible but was not within inspection reach. This also distinguishes visibility (eight-cell observation radius) from inspection reach (one Manhattan step).

The current INSPECT description says "a nearby resource id" without stating the one-step reach; its availability filter permits the tool when any resource is observed, including farther resources. This interface is underspecified. The model also invents prefixed subjects instead of copying exact IDs. Repeated generic "unknown object" feedback did not prevent the loop in Stage A. The historical journal proves the reason counts; it does not retain the exact subject of all 182 old rejections. The new trace demonstrates the mechanism, but we do not claim to have recovered missing historical parameters.

## Proposed changes — NOT applied; require owner approval

1. Clarify INSPECT's description: subject must be an exact accessible object ID, exact observed resource ID within one Manhattan step, or inventory:<material> for a carried material. State explicitly that material names/descriptive prefixes are not resource IDs. Consider exposing observation-derived valid subject references in a future schema, but keep that as a separate approved change.
2. Make GATHER_AT and REST_FOR descriptions as explicit as TRAVEL_TO about starting an ongoing task that executes automatically on later ticks between decisions, and its interruption/cancellation limits. Example proposed wording:
   - GATHER_AT: "Start an ongoing task: walk to the exact observed resource ID and gather up to amount units. Movement and gathering continue automatically on subsequent ticks between decisions until complete, interrupted or cancelled."
   - REST_FOR: "Start an ongoing rest task for hours simulated hours. Rest steps continue automatically on subsequent ticks between decisions until complete, interrupted or cancelled."
3. If approved, test one description change at a time against the unchanged baseline with the same bounded settings. Do not force intentions, remove primitive alternatives, change needs, increase budgets or relabel rejected actions to improve the score.

The inspection-interface mismatch is demonstrated. A description-only fix for intention nonuse is not demonstrated and must not be advertised as proven. No proposed change has been applied to runtime descriptions, schemas, prompts, parsing or validation.

## Verification and limits

Seven targeted CPU tests passed: four diagnostic tests plus three existing inference-path tests. They cover actual request capture, all three intention parser/validator/executor paths, read-only historical counting, invalid INSPECT references, unchanged system hash and real-backend integration using explicitly labeled stand-ins. The real GPU run above supplies the model evidence; the CPU tests do not.

Only new diagnostic code/tests/artifacts are added by this PR. git diff against main has no production caitanya changes; root.py and neutral-v4-inquiry remain byte-identical. Existing experiment files were not written. No parameter tuning, model upgrade, forced tool selection, description change, long GPU run or merge occurred.

Result transfer verification: the canonical selected-summary SHA-256 is `0321314cc4f1b259803328f88583d6773d9f45a87e8c68b96b66398887c4ef3a`, matching the newly persisted SHORT_DIAGNOSTIC_SUMMARY.json in Drive. This verifies the committed summary matches that run. The full per-request diagnostic remains in the new Drive directory. The summary is not the standalone evidence.json audit schema.
