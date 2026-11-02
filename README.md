# CAITANYA — AI World

Experimental civilization simulation, version 0.3.0, with individual identities and memories, an optional shared LFM3 model, and a read-only 3D witness. Consciousness is not established.

## Run locally

Requires Python 3.11+. Run from the repository root:

```sh
python -m pip install -e ".[test]"
python -m pytest -q
python -m caitanya.server --population 5 --width 256 --depth 256 --run-dir runs/local
```

Open http://127.0.0.1:8000/viewer. The default is an explicitly labeled deterministic mock policy. For CUDA GPU inference, install `.[gpu]` and add `--backend lfm3`, using a separate run directory. Model weights download separately; pin the recorded revision with `--revision <sha>`. One model instance serializes bounded decisions using individual observations. Invalid calls execute no action; there is no silent mock fallback. This is separate from the Vedic Scholar chat.

## World and generations

Six biomes and fifteen representative resources support movement, gathering, eating, drinking, rest, local speech, writing, reading, revisions, primitive placement, gifts and teaching with provenance. Minerals are finite; renewable resources regenerate.

Agents have independent gender and biological sex, simplified anatomy, needs, age and lineage. Reproduction requires reciprocal adult parenting proposals, compatible reproductive roles, proximity, resources and health. Underage and close-family pairings are rejected. Gestation, birth, caregiving, growth and aging are simplified. Children have separate memories. No sexual scenes are simulated.

The baseline calendar advances ten minutes per tick. `--days-per-tick 1` enables a labeled accelerated experiment. Physiology is not scientifically calibrated. Pretrained language is not evidence of language evolving from scratch. There is no hidden divine or parent decision-maker.

## Persistence

Committed ticks append private structural deltas and checksums to an fsynced journal. Atomic checkpoints are written at startup, every 60 ticks and graceful shutdown. Recover with:

```sh
python -m caitanya.server --recover runs/local --run-dir runs/local
```

Model-backed recovery also requires `--backend lfm3` and the original revision. Recovery replays contiguous committed journal entries after a valid checkpoint. An uncommitted tick can be lost. Disk loss requires an external backup. At the 100 MB journal limit the worker checkpoints and pauses. Indefinite operation and automatic cloud backups are not implemented.

Public GET endpoints omit private memories and parenting proposals. Run histories are excluded from this repository. Use separate directories for distinct experiments. CLI arguments configure the server; config/default.json is descriptive and not automatically loaded.

## Colab

[Open the notebook](https://colab.research.google.com/github/CoderVLSI/AI-World/blob/main/notebooks/CAITANYA_Colab.ipynb). Colab runtimes are temporary: back up run directories before disconnecting. No weights or credentials are distributed here.

See [implementation status](IMPLEMENTATION_STATUS.md). Code and vendored Three.js are MIT licensed; dependencies and model weights retain their own licenses.
