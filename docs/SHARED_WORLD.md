# Humans and wildlife in one world

This integration connects the optional wildlife module to the existing human simulation, rather than only combining repository branches. It preserves human identities, memories, bodies, root privacy, model scheduling and prompts. No Claude feature branch was available on the remote when this work began; no Claude branch is modified or merged here.

New CLI runs start six animals per species by default:

```sh
python -m caitanya.server --population 5 --wildlife-per-species 6 --port 8012 --run-dir runs/shared-world
```

That command uses explicitly labeled mock human decisions. Add `--backend lfm3 --revision <model-sha>` on a compatible GPU for real inference. This combined feature has not yet been verified with real LFM3 inference. Do not describe the earlier five/fifty-agent GPU benchmarks as integrated wildlife experiments.

The main `/viewer` displays human bodies and animal sprites together. The Animal census link opens `/fauna/`, reading the same world's wildlife and terrain through GET-only endpoints. Family tree and timeline links use that same human world. Wildlife is not a separate running population in these integrated pages.

Each authoritative world tick advances wildlife by the same simulated-day interval used by human biology. Wildlife consumes the world's actual resource nodes, so compatible food competes with human use. Nearby living wildlife is added to individual human observations without supplying hunting, farming, worship or domestication instructions. Wildlife events are explicitly sourced as deterministic_ecology; they are not counted as language-model decisions. Predators currently target other animal species, not humans. No hunting/domestication actions or reconciliation of living carp with the legacy fish resource have been added.

Animals, aquatic food, animal lineage, ecological events and their separate RNG are included in the existing private world checkpoint/delta journal. Recovery and exact committed-tick replay restore humans and animals together. Public snapshots and historical endpoints expose a sanitized wildlife view without RNG state; root state remains private. The wildlife calendar currently accepts at most one simulated day per tick. Use `--wildlife-per-species 0` for accelerated steps larger than a day until explicit ecological substeps are implemented.

Legacy checkpoints retain their original world: they do not silently acquire animals or lose humans. Recovering a pre-wildlife run ignores the new-world wildlife default and leaves its data unchanged. Introducing animals into a saved real run needs an explicit, recorded migration; this branch does not perform one automatically. Direct Python World() creation retains the legacy no-wildlife default; pass wildlife_per_species explicitly.

Validation: shared-world tests check matching clocks, observation locality, consumption of shared resources, forward ecology event provenance, exact replay, checkpoint restoration, post-checkpoint journal recovery, hidden private state and GET-only wildlife routes. The combined local smoke run reached tick 60 with five humans and 76 living animals across twelve species; four animal births occurred under deterministic rules. This is a CPU/mock integration preview, not evidence of model-directed reproduction or emergent civilization.
