# Observed agent behavior

Only evidence-backed observations belong here. Mock tests are not real AI experiments.

## Earlier Colab run (before this phase)

Runtime inspection on 2026-11-02 found a pre-root generational run at tick 719 with zero survivors, zero births and generation zero. Its cumulative shared backend counters also include earlier experiments, so they cannot be attributed to that run. This is a survival failure, not evidence of civilization. Raw histories will be preserved before source replacement. New experiments will receive independent run directories and model-process counters.

Update: Colab disconnected before those histories could be preserved. Reconnection showed that the prior runtime's model and /content/caitanya_runs directory were gone. Drive OAuth subsequently failed. No new agent actions were verified. See [the operational incident report](experiments/2026-11-02-colab-reconnection/REPORT.md). Do not interpret historical notebook outputs as a currently running civilization.

## Five-agent real run — five-20261102T162454Z

After the user repaired Drive authorization, a write/fsync/readback check passed. The latest main source (dfb78d59491b976286d0c0a7c5fb04c4e9306b69) ran explicitly with --backend lfm3 on a Tesla T4, using one LiquidAI/LFM3-1.7B instance pinned to ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7. Root mode was observe, with no crisis intervention. This was a 30-tick baseline-calendar smoke test, approximately five simulated hours, not a long-term civilization test.

All five inhabitants completed ten validated model actions each. Totals: 14 EAT, 12 DRINK, 12 SPEAK, 11 WAIT and one REST. Fifty inference calls succeeded with no inference failures or rejected actions. Population remained five; there were no births, deaths, writings or constructed objects. Inference took 56.015 seconds for 718 output tokens (12.82 tokens/second); peak model-process GPU allocation was 4,032,325,120 bytes. These timings exclude model loading.

Examples: agent-0000 ate at evt-000000002; agent-0001 waited at evt-000000003. At evt-000000027, agent-0000 said: "I see you've been eating several times already (at ticks 3, 6, 9). Your hunger is low (3) but thirst is high (12). Consider drinking some water and maybe resting if needed." This is public model-authored speech, not verified knowledge of another's private experience. Some speech adopts an assistant-like perspective or claims help that no corresponding transfer action confirms. It is not evidence of cooperation or discovery.

Histories and metrics are stored privately on Drive. A fresh server process recovered tick 30 with an identical public-state hash; internal checkpoint/journal recovery also passed. This is process-restart evidence, not yet a full Colab-runtime-replacement drill. The witness returned HTTP 200, rejected snapshot POST with 405 and omitted root state/private memories. Colab's browser output-frame/proxy rendering remained unreliable.

[Full report and event references](experiments/five-20261102T162454Z/REPORT.md) · [Sanitized action evidence](experiments/five-20261102T162454Z/evidence.json) · [Fresh-process recovery comparison](experiments/five-20261102T162454Z/fresh-process-recovery.json).

## Fifty-agent real benchmark — fifty-20261102T163129Z

The same pinned text model and source ran a separate world with fifty initial inhabitants and one model instance, in observe mode. The worker completed 60 ticks (approximately ten simulated hours) within a 240-second worker budget. Every identity agent-0000 through agent-0049 completed two validated model actions. Totals: 80 EAT, 17 WAIT and three DRINK; 100 successful model calls, zero inference failures and zero rejected actions. All fifty survived. There were no births, pregnancies, deaths, constructions or written works, and no philosophical development is evidenced.

Inference produced 720 tokens over 87.472 seconds (8.23 tokens/second), excluding loading. Peak model-process GPU allocation was 4,389,524,480 bytes. The private journal occupied 443,521 bytes. This establishes bounded fifty-identity operation, not a sustainable civilization or adequate long-term decision frequency. The sparse decision schedule remains a limitation assigned to Claude's foundations work.

[Full benchmark report](experiments/fifty-20261102T163129Z/REPORT.md) · [All 100 sanitized actions and request IDs](experiments/fifty-20261102T163129Z/evidence.json).

Persistence follow-up: after stopping the completed benchmark, Colab's Restart session cleared notebook variables. A fresh model-backed server recovered the same tick-60 world from Drive with an identical public-state hash. See [runtime recovery evidence](experiments/fifty-20261102T163129Z/runtime-recovery-check.json). This is a kernel/session restart drill; complete VM replacement remains untested. The recovered worker has a zero-tick budget and is not making further model calls. Browser preview rendering remains a separate unresolved issue; no unauthenticated public viewer was exposed.
