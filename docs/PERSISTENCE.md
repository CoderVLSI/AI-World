# Persistence: segmented journal and slim checkpoints

Fixes the two growth problems recorded in MERGE_CHECKLIST (risk 2) and CAITANYA_HANDOFF.md.

## What changed
* **Journal segments.** When the active `events.jsonl` reaches `--segment-bytes` (default 25 MB) the server writes a
  checkpoint and then *renames* the file to `events-<first event index>.jsonl`. Nothing is copied, rewritten or deleted.
  A new `events.jsonl` starts. Recovery reads the closed segments and then the active file.
* **Slim checkpoints.** Instead of embedding every event, a checkpoint stores `events_ref` (count and last event id)
  and the events are read back from the journal files. Checkpoint size no longer grows with run length. Full
  checkpoints from earlier versions still load unchanged; `World.checkpoint(dir)` still writes a full image unless
  `slim=True` is requested (the server does this when the journal covers every event).
* **Resuming old runs.** If a run is resumed from a full checkpoint whose history is not in the journal, the missing
  prefix is written once as `events-000000000.jsonl`; an existing file is never overwritten.
* **Guards.** The `max_journal_bytes` (100 MB) pause on the *active* journal is unchanged, but rotation keeps the
  active file far below it. A new `--max-run-bytes` (default 5 GB, whole run directory) pauses with
  `PAUSED_RESOURCE_LIMIT` / `run_size_limit`. The "existing run history" refusal now also considers segments.
* The on-disk event and state formats are unchanged. A slim checkpoint cannot be restored if journal files are missing
  (it fails with a clear error and recovery falls back to an older checkpoint).

## Measured (CPU, mock policy, 50 inhabitants, 1,700 ticks; docs/results/persistence-mock-50x1700-20261103.json)
| | before (7 days = 1,008 ticks, EXPERIMENT_RESULTS) | now (1,700 ticks) |
|---|---|---|
| Run reaches tick 1,700 | would pause near tick 1,490 | yes (journal 115 MB in 4 closed segments + active) |
| Checkpoints, total | 611 MB (cumulative copies of history) | 30.4 MB (34 images, newest 0.95 MB) |
| Recovery | - | state and all events equal the live run |

## Not solved / not claimed
* The journal is still about 67 KB per tick at 50 inhabitants; a 30-day run is roughly 290 MB of journal. It no longer
  stops, but it is large. List-diff patches or compression would shrink it and were not done.
* The whole event list is still held in memory, and `GET /api/v1/world/events` still serves from it.
* Restoring a slim checkpoint re-reads the whole journal (seconds to a minute for hundreds of MB).
* `scripts/autonomy_benchmark.py` keeps its own single-file journal and 100 MB guard; it was not changed.
* Real-model behaviour is unaffected and unverified.
