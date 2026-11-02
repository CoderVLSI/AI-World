# CAITANYA — AI World

Experimental civilization simulation, version 0.4.0, with a persistent Brahman root agent, individual sub-agent identities and memories, an optional shared LFM3 model, and a read-only 3D witness. Consciousness is not established.

## Run locally

Requires Python 3.11+. Run from the repository root:

```sh
python -m pip install -e ".[test]"
python -m pytest -q
python -m caitanya.server --population 5 --width 256 --depth 256 --run-dir runs/local
```

Open http://127.0.0.1:8000/viewer. The default is an explicitly labeled deterministic mock policy. For CUDA GPU inference, install `.[gpu]` and add `--backend lfm3`, using a separate run directory. Model weights download separately; pin the recorded revision with `--revision <sha>`. One model instance serializes bounded decisions using individual observations. Invalid calls execute no action; there is no silent mock fallback. This is separate from the Vedic Scholar chat.

## World and generations

Shared-world integration: new CLI worlds now include humans and twelve wildlife species together. Both populations share the clock, terrain and finite resources; nearby animals are visible in human observations. The main witness renders both, with links to the same world's animal census and family timeline. Set `--wildlife-per-species 0` to disable ecology in a new run. Existing checkpoints remain unchanged. See [shared-world setup and limits](docs/SHARED_WORLD.md). The combined feature is tested with mock humans; the older real-model benchmark reports predate this integration.

Six biomes and fifteen representative resources support movement, gathering, eating, drinking, rest, local speech, writing, reading, revisions, primitive placement, gifts and teaching with provenance. Minerals are finite; renewable resources regenerate.

Agents have independent gender and biological sex, simplified anatomy, needs, age and lineage. Reproduction requires reciprocal adult parenting proposals, compatible reproductive roles, proximity, resources and health. Underage and close-family pairings are rejected. Gestation, birth, caregiving, growth and aging are simplified. Children have separate memories. No sexual scenes are simulated.

The baseline calendar advances ten minutes per tick. `--days-per-tick 1` enables a labeled accelerated experiment. Physiology is not scientifically calibrated. Pretrained language is not evidence of language evolving from scratch.

## Root agent, continuity and inquiry

`BrahmanAgent` is the private persistent root of the simulation. Its scope is the whole world state, including inhabitants, ecology and objects; it delegates each inhabitant decision through that individual's observations to the shared inference backend. It uses a bounded deterministic supervisory policy, not a second language model or an infinite consciousness. Individual decisions remain local. This implementation is a computational interpretation of the requested cosmology, not a claim about religious truth.

The root is formless by default. If every living inhabitant has hunger or thirst of at least 85, it may create an ordinary adult body near an inhabitant, with a practical helping goal and standard initial provisions. There can be only one living manifestation and at least 1,000 ticks between arrivals. The body uses normal inference, needs and action validation; it cannot rewrite minds or bypass world rules. This policy does not guarantee successful preservation. Its arrival is visible; its underlying identity is not disclosed.

All inhabitants are privately registered as children of the root. Biological parentage remains separate. When a later newborn is registered, it receives the first available deceased continuity thread in stable identifier order, or a new thread if none is available. Personal memories, skills, status and beliefs do not transfer. A private ledger retains action counts and confirmed social outcomes across lives. This is factual causal continuity called karma in the design, without a moral score, punishment, reward or determination of birth conditions.

The REFLECT action records private, unverified reflection. No scripture, revelation, Brahman identity, root registry or prior-life ledger is placed in inhabitant prompts. An inhabitant may form any interpretation or none. No realization classifier or scripted discovery exists. The pretrained model can already know religious concepts, so their appearance cannot establish independent discovery.

Root state is included in private checksummed checkpoints and replay deltas, and omitted from witness snapshots and historical responses. This is a simulation information boundary, not security against the operator who owns the source and run files. Older checkpoints gain a root registry when loaded; they cannot reconstruct continuity that was never recorded. Existing running processes must be restarted with this version to use these mechanics.

## Persistence

Committed ticks append private structural deltas and checksums to an fsynced journal. Atomic checkpoints are written at startup, every 60 ticks and graceful shutdown. Recover with:

```sh
python -m caitanya.server --recover runs/local --run-dir runs/local
```

Model-backed recovery also requires `--backend lfm3` and the original revision. Recovery replays contiguous committed journal entries after a valid checkpoint. An uncommitted tick can be lost. Disk loss requires an external backup. At the 100 MB journal limit the worker checkpoints and pauses. Indefinite operation and automatic cloud backups are not implemented.

Public GET endpoints omit private memories and parenting proposals. Run histories are excluded from this repository. Use separate directories for distinct experiments. CLI arguments configure the server; config/default.json is descriptive and not automatically loaded.

## Colab

The notebook fetches and prints the latest main SHA, installs GPU dependencies, explicitly launches `--backend lfm3`, saves raw histories under Google Drive/MyDrive/CAITANYA, checks the backend and read-only routes, and uses Colab's authenticated viewer proxy. It never launches a public tunnel. An existing run ID triggers recovery using its original model revision and root mode. Keep the run ID across runtime restarts. Google Drive mounting requires account consent and may fail or time out; startup must fail rather than silently switch to ephemeral storage.

Use `--root-mode off` for a neutral baseline (no root records or intervention), `observe` for private records without intervention, or `crisis` for existing bounded intervention. Crisis remains the backwards-compatible default. Modes are private checkpoint configuration and are not supplied to inhabitants. On recovery the stored mode wins; use a new run for a different mode.

`--max-ticks 30 --max-seconds 180 --report-dir <summary-directory>` bounds a worker and produces an event-backed REPORT.md and evidence.json after it stops. A request already started may exceed the cooperative time budget. The server remains available as a read-only witness after the worker stops. Metrics are written per committed tick to metrics.jsonl. Inference counts are scoped to a model process; a recovered process starts new counters, while event IDs and validated action history continue. Reports distinguish successfully parsed calls from validated actions. Only identities with validated actions linked to model request IDs count as verified real agents.

Review sanitized reports before publishing them. They include public speech/writings and confirmed action state changes, but exclude private memories, reflection text, model reasoning and root continuity records. No automatic cultural-discovery detector is used. The model's official tool format is documented in the [Liquid AI model card](https://huggingface.co/LiquidAI/LFM3-1.7B).

[Open the notebook](https://colab.research.google.com/github/CoderVLSI/AI-World/blob/main/notebooks/CAITANYA_Colab.ipynb). Colab runtimes are temporary: back up run directories before disconnecting. No weights or credentials are distributed here.

See [implementation status](IMPLEMENTATION_STATUS.md). Code and vendored Three.js are MIT licensed; dependencies and model weights retain their own licenses.
