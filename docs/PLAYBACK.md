# Watching a finished run (playback)

Playback replays a run folder read-only, with **no model, no GPU and nothing written**, so any viewer of the normal witness API
(the Godot viewer, the browser viewer) can watch a run that was made elsewhere, for example on a Colab GPU, on a computer with
no GPU and little disk space. It is not a live view and it never simulates anything: it walks the recorded state patches tick by tick.

## Steps
1. **Get the run folder.** The Colab notebook writes it to `MyDrive/CAITANYA/<RUN_ID>` (for example `five-20261103T161619Z`). In Drive,
   right-click that folder, Download, and unzip it somewhere. It must contain `checkpoint-*.json` (and usually `events*.jsonl`).
   Copy it; never edit or delete the original. It contains private data (memories, root state); keep it out of GitHub.
2. **Start playback** (the project's Python environment, no GPU packages needed):
   `python -m caitanya.server --playback <run folder> --port 8002 --speed 2`
   - `--speed` is recorded ticks per second (default 2). The run loops by default; add `--no-loop` to stop at its last tick.
3. **Watch.** Godot: `Godot... --path <repo>\godot -- --server=http://127.0.0.1:8002`. Browser viewer: `http://127.0.0.1:8002`.
   The status reads `PLAYBACK`.

## Pause, speed and scrub (Godot)
`GET /api/v1/playback` says whether the server is replaying a run (`enabled`, `tick`, `final_tick`, `loop`). `GET /api/v1/live?tick=N`
returns the normal live view as it was at the end of recorded tick N (a pure function of N; out-of-range gives 400; a live server refuses
the parameter). The Godot viewer uses it for a scrub bar, pause (`space`), step (`←`/`→`), speed (`[` `]`) and `Home`/`End`.
While a viewer is choosing ticks this way, the server's own automatic advance waits 3 seconds after each request, so two viewers on
one playback server share one position: use one server per viewer if you need them independent. The browser viewer is unaffected.

## What is guaranteed (tested)
* Every tick is reproduced exactly: the viewed state at any tick (forward, backward or jumping) equals the recorded state for that
  tick; the only intended difference is the status label `PLAYBACK`.
* The run folder is never written to (a test compares every file before and after).
* No decision is ever requested: a run made with a real-labelled model plays back with a stand-in that can only raise an error.
* The public API is unchanged and still redacted (no root state, memories or scheduler internals); `POST` is refused.

## Limits
* It shows the recorded run only; it cannot step beyond its last tick.
* Large runs hold their whole history in memory; very long runs may need a few hundred MB.
* The folder must be a whole run folder from `--run-dir` (checkpoints plus journal). A lone checkpoint of a long run may not hold
  every event if it is a slim one.
