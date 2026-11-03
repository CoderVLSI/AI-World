# Colab operations and ownership

Autonomy foundations are merged on main. Wildlife, the chronicle, evidence auditing and operations are integrated on `codex/wildlife-on-autonomy`. Core scheduling, physiology, materials and private memory remain unchanged. Reinstall with `python -m pip install -e ".[test,gpu]"` after fetching a new checkout.

Foundations requests up to 8 decisions per tick (tunable with `--decisions-per-tick`). A time-bounded real-model run therefore advances fewer ticks than the old legacy cadence. Record completed time and source SHA; historical notebook output does not prove a current run.

## Start a persistent real run

1. Open the repository notebook and select a GPU. L4 is preferred; record the GPU actually allocated.
2. Mount Drive. If Google authorization fails, stop: do not claim a persistent experiment or silently substitute /content storage.
3. Fetch main, record its full SHA, install dependencies and run tests before launching.
4. Run `python scripts/storage_preflight.py /content/drive/MyDrive/CAITANYA` from the checkout. This tests write/fsync/readback and refuses paths outside mounted MyDrive. A mounted-directory check cannot prove Google has remotely replicated every byte.
5. Launch exactly one simulation with `--backend lfm3`, a unique run directory, root mode, model revision and bounded tick/time budgets. Do not run an old simulation worker concurrently. Preserve its history before stopping it, if the runtime still exists.
6. Use the Google-authenticated Colab port proxy only. Do not enable Gradio share links, ngrok, an unauthenticated public tunnel or port forwarding. The FastAPI app binds to localhost and does not itself implement public authentication. If the proxy cannot be opened, keep the server private and report viewer verification blocked.
7. After at least one decision, run `python scripts/verify_deployment.py http://127.0.0.1:8003 --output <run-directory>/deployment-check.json`. A mock backend fails this probe. Per-agent verification still requires evidence.json event/request IDs.

## Recovery drill

Wait for the bounded worker to finish and its report/checkpoint to appear. Record the final tick, model revision, root mode and evidence checksum. Terminate the server gracefully, leaving the Drive directory intact. Start a new Python process with `--backend lfm3 --revision <original-sha> --recover <same-directory> --run-dir <same-directory>`. Confirm its initial snapshot matches the saved committed tick before advancing it. A full Colab runtime-replacement drill additionally requires reconnecting, remounting Drive, fetching the recorded source version and repeating recovery. Process recovery and runtime-replacement recovery are different acceptance tests.

## Failure handling

Drive OAuth `400 invalid_request`: leave experiment launch blocked; the account owner may need to reconnect authorization in Colab. Never collect or publish OAuth tokens. Expired output-frame login/cookie errors can coexist with working plain-text code execution; verify them separately. A runtime reset removes /content files and in-memory models. Notebook output is historical evidence and must not be mistaken for a currently active GPU process.

Only reviewed summaries, public authored works and sanitized evidence belong in GitHub. Keep journals, checkpoints, model reasoning, private memories, credentials and continuity registries in private persistent storage. Short runs cannot establish autonomous civilization, discovery or successful generations.
