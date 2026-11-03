# Optional wildlife extension

Integration update: this checkout now also supports humans and animals in the same World. See [SHARED_WORLD.md](SHARED_WORLD.md). The standalone preview remains available alongside integrated foundations and legacy worlds.

This isolated branch adds twelve representative species: deer, rabbit, wild boar, wolf, fox, sparrow, crow, duck, owl, carp, butterfly and bee. These common-name groups are illustrative, not a complete taxonomic inventory. All behavior is lightweight deterministic simulation. No animal has an LLM instance, and no human receives new instructions, hunting knowledge or domestication knowledge.

From the checkout root, run `python -m fauna.preview`, then open http://127.0.0.1:8011/. This is an independent read-only ecology preview, explicitly labeled as disconnected from the civilization. It does not modify the running Colab experiment or other running processes. The preview creates a separate world for terrain/resources and does not step its human inhabitants or load a language model. Its state is temporary; do not present it as a persistent real-agent experiment.

## Implemented rules

- Habitat-validated one-cell movement; fish stay in water. Birds and insects use simplified flight within their permitted habitats, without altitude or migration physics.
- Herbivores/omnivores consume finite compatible world resource units; resource amounts cannot become negative. This can create competition with humans in integrated worlds.
- Predators pursue specified prey; nearby prey attempt escape. Confirmed predation removes the prey and creates a provenance event. Claims of realistic hunting success or calibrated food webs are not made.
- Carp consume an explicit bounded aquatic food stock with a declared regeneration rate; this is separate from the existing human fish resource. Fishing animals themselves is not implemented, so no fish-stock reconciliation is claimed.
- Animal mating requires nearby mature animals of the same species, sufficient energy and elapsed cooldown. Offspring have distinct IDs and recorded parents. A per-tick birth budget limits computation rather than imposing a fixed population ceiling. Gestation, eggs, nests, juvenile dependency and genetic inheritance are not modeled.
- Energy expenditure, maturation, reproductive cooldown and aging use simulated days. Species parameter values are illustrative experiment settings, not zoological measurements. Starvation and aging deaths remain possible. Insect entries represent simplified individuals, without colony behavior or pollination mechanics.

`Ecosystem.state()` serializes animals, RNG, events and aquatic food. Restore through `Ecosystem.restore()`. Deterministic continuation also requires the matching world resource/geography state; tests checkpoint both together. The optional layer is wired into both foundations and legacy tick loops, atomic world checkpoints, delta journals and read-only APIs. Nearby wildlife observations are capped at twelve living animals within eight cells. Existing checkpoints without fauna stay without fauna. Living carp remain separate from the human fish resource; fishing animals is not implemented.

The preview map shows habitat cells, live animals and per-species counts; selecting species or individuals reveals age, energy, health, parents and current behavior. Group filters distinguish mammals, birds, fish and insects. Its public routes are GET only. There is no spawn, kill or intervention control in the viewer.

Validation on 2026-11-02: the full suite passed 34 tests (30 existing, four wildlife tests). Checks cover all twelve species, habitat validity, deterministic continuation after matching world/ecology restoration, finite-resource feeding, recorded predation, bounded births, lineage, aging, starvation and read-only preview routes. Browser QA confirmed the live species census, bird filtering and owl inspection. JavaScript syntax checking passed. These are module tests and an isolated deterministic preview, not evidence of wildlife interacting with real AI inhabitants.
