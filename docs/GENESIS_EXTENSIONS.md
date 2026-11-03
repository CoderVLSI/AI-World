# Phase B extension points (designed, NOT implemented)

Phase A added only the hooks below. None of the Phase B systems exist yet, and none may be mixed into the genesis PR.

## 1. Gradual improvement of procedural geography, climate, water and physics
* **Hook:** each stage names a generator version in the plan (`GenesisPlan.generators`) and `SUPPORTED_GENERATORS` lists what
  this code can build. A new generator ships as a new id (`geography-v2`), registered next to the old one; old worlds keep
  naming `geography-v1` and keep deriving the same terrain. `genesis.verify_recorded` refuses to load a world whose recorded
  terrain digest no longer matches, so nothing can change an existing world silently.
* **Needed later:** a registry mapping `(stage, version)` to a callable instead of the single inline implementation; a
  per-stage digest (resources, water network); a migration note per generator version. `nature.geography` is currently a pure
  function called from many places; a v2 must be selected through the world's recorded version, not a global.

## 2. Universal Jiva identity registry (humans and animals)
* **Hook:** `BrahmanAgent.data["children"]/["threads"]` already maps agent ids to continuity threads. The animals have their own
  ids (`animal-000123`) in `fauna`. A registry would give every body a `jiva_id` and a thread, with `embodiment` (species,
  body plan) as data; no memories, skills or rewards transfer (the existing rule).
* **Not decided:** whether a thread may move between species (rebirth) and by what *recorded* rule. Any such rule must be a
  deterministic world rule (like births), not a model decision.

## 3. Species-appropriate adaptive animal intelligence
* **Hook:** the animals' `action` strings are the only recorded behaviour; the viewer and tests already key off them.
* **Design:** a per-species policy interface (`decide(observation) -> action`) with a deterministic baseline (today's
  ecology) and optional learned or model-backed policies. Intelligence must depend on embodiment (senses, memory span, group
  size), be budgeted separately from the inhabitants' decisions, and never share the inhabitants' model context.

## 4. Fourteen nature-force intelligences
* **Hook:** the Isvara context builder shows how a role gets evidence-only context, its own schedule and counters, validated
  output and advisory-only results. A nature force would reuse that pattern but, to affect the world, would have to act only
  through a *validated* world-rule interface (bounded magnitudes, recorded events, deterministic given its recorded decision),
  never by editing state. The list of fourteen, their domains and bounds are not specified in this repository yet.
* **Cost:** fourteen reasoning schedules need a shared budget and a round-robin so none starves the inhabitants.

## 5. Optional visible manifestations of Isvara
* **Hook:** the existing bounded `crisis` manifestation (an ordinary embodied agent under the same rules) is untouched.
* **Rule for later:** a manifestation is an embodied jiva-like body with the standard action validation; no privileged
  revelation, no resource creation, recorded as a world event, and optional per run.
