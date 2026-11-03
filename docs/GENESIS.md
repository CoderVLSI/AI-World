# Genesis, Brahman and the Isvara role (Phase A)

*Computational representations inspired by Vedanta. Nothing here claims that software, a record or a language
model has subjective experience, and no model output is treated as evidence that it does.*

## Roles

| Name | What it is in code | What it can do |
|---|---|---|
| **Brahman** | `BrahmanAgent` (`root.py`, unchanged): the persistent, private root identity and its registry of continuity threads | exists before the world; `off` / `observe` / `crisis` modes behave exactly as before |
| **Isvara** | `caitanya/isvara.py`: Brahman's creative and governing *role* in the same private root state, not a separate agent | issues the genesis plan; keeps a bounded, private record of reflections on recorded evidence |
| **Genesis** | `caitanya/genesis.py`: an immutable, versioned `GenesisPlan` and the one-time `execute` | builds terrain index, resources, founders and (optionally) wildlife deterministically |
| **Universe** | the engine: stable physical rules | unchanged |
| **Jivas** | inhabitants (continuity threads in the root registry) | unchanged; independent; no knowledge of any of the above |

## Order of creation

1. `World.__init__` creates Brahman (`BrahmanAgent(mode)`).
2. `isvara.issue_plan(...)` makes and validates the plan. With reasoning on, the Isvara role is initialised in the private
   root state first and is recorded as the issuer; with reasoning off (root mode `off`, a legacy clock, or
   `isvara_config={"enabled": false}`) the **identical** plan is issued by `genesis_default`. Genesis never depends on a model.
3. `genesis.execute(world, plan)` builds the world once and records it.
4. `root.register(world)` and the usual manifest, exactly as before.

`execute` refuses to run twice (`root.genesis.status == "completed"` lives in the checkpointed private root state).
`restore`, `recover` and `replay` never call it (tested by making `execute` raise).

## The plan (`GenesisPlan`)
A frozen dataclass of tuples: version, seed, size, spawn radius, the resource-count formula, the biome-to-resource table,
founder traits and ranges, starting supplies, `wildlife_per_species`, `days_per_tick`, and one **generator version per stage**
(`terrain geography-v1`, `resources scatter-v1`, `founders founders-v1`, `wildlife ecology-v1`). `validate()` rejects unknown
versions, unknown fields, impossible values, and tables naming unknown resources. `digest()` is its SHA-256.
Language-model output can never reach it: the plan is made before any inference and is never edited.

## Seed compatibility
The pre-genesis constructor was moved into `genesis.execute` without changing the order in which `world.rng` is used.
`tests/fixtures/genesis_golden.json` holds digests recorded **from the old constructor** for eight configurations (sizes,
wildlife, spawn radius, root mode `off`, legacy). The tests check the initial world, the RNG state afterwards, and the world
30 ticks later. All match. A stored world also records a digest of its terrain; on restore a changed generator is refused
(`terrain generator no longer matches`) instead of silently altering an old world.

## What is recorded
* **Private root state** (checkpointed, replayed through the normal `tick_committed` patches, never public): the plan, its
  digest, who issued it, generator versions, the world summary (terrain digest, biome tiles, resource counts, founders,
  animals); and for the Isvara role: its config, schedule, reflections, proposals, digests of pruned reflections, totals.
* **Public events** (source `genesis`, tick 0, physical counts only, no role names): `genesis_plan_issued`,
  `genesis_terrain_generated`, `genesis_resources_placed`, `genesis_founders_created`, `genesis_wildlife_placed`,
  `genesis_completed`. Later: `root_reflection` / `root_reflection_failed` (source `root_reasoning`) carry only ids, counts
  and flags - never text.
* **Manifest** (public): `genesis = {version, plan_digest, generators}`.
* `GET /api/v1/genesis` (read-only): the creation record and reasoning *counts*. No reflection text, no proposals.

## Isvara reasoning
* **One shared model.** `TransformersLFM3Backend.reflect(context, budget)` uses the same loaded model and lock as the
  inhabitants (`model_instances: 1`). It has its own system message (`ISVARA_SYSTEM`), its own single tool
  (`RECORD_REFLECTION`, never offered to inhabitants), its own parser, budget and counters (`metrics()["root_reasoning"]`).
  It does not touch `calls`, `failures` or `last_request`, so inhabitant attribution (`lfm_decisions == model calls - failures`)
  is unchanged.
* **Bounded schedule.** At most one call per `reflect_every_ticks` (default 432 = 3 simulated days at 10-minute ticks), run
  after that tick's inhabitant decisions, never in a decision slot. Limits: `max_new_tokens` 320, `max_seconds` 20,
  `max_prompt_tokens` 3072, `retain_full` 24 reflections (older ones are reduced to a SHA-256 in state; the journal keeps the text).
* **Context = recorded evidence only.** Aggregate facts (living, deaths by cause, births, resource totals, wildlife counts,
  knowledge *counts*, decision fairness), event-id-addressed evidence items (the creation record, deaths, births, arrivals, the
  first recorded occurrence of each action kind), and its own two latest notes. Never inhabitant memories, long-term memory,
  hypotheses, speech or written text (tested with planted sentinels).
* **Observation, conclusion, uncertainty.** A reflection stores them separately; cited ids are checked against the ids
  actually offered (unknown ids are dropped and counted); `uncited`, `no_evidence_offered` and `uncertainty_stated` flags are
  recorded; every record carries `epistemic_status` stating it is model-generated text and not evidence of experience.
* **Advisory only.** A proposal is stored as `advisory_unapplied`. No code reads it. A test runs the same world with and
  without an adversarial proposing backend and requires bit-identical physical state.
* **Failures.** Any error, malformed output or budget overrun is recorded (`root_reflection_failed`), retried with
  exponential backoff capped at the interval, and never blocks or changes inhabitants. A real backend never falls back to the
  mock template. A backend without `reflect` is skipped quietly.
* **No silent re-inference.** Reflections are part of the checkpointed state; restore, recovery and replay apply recorded state
  and never call a model (test counts calls across checkpoint, journal recovery and replays).
* **Modes.** `off`: no reasoning, genesis still recorded. `observe` and `crisis`: reasoning on; `crisis` keeps the unchanged
  bounded manifestation rule. Reasoning is also off for legacy clocks and for worlds without the role (older checkpoints).

## Compatibility notes
* New worlds carry 5-6 extra events at tick 0 and `root.genesis` (+ `root.isvara` when reasoning is on) in the private root
  state. Public snapshots still omit `root` entirely.
* Anything that assumed a fresh world has no events must use `tick == 0`. The server's "existing run history" refusal
  does (this was a real regression found by the tests and fixed).
* Schema 1 checkpoints and any world without `root.genesis` load and run as before; they gain neither genesis nor reasoning.
* `World(..., isvara_config=...)` is new and optional. Metrics gain `genesis`; `inference` gains `root_reasoning` for the real
  backend. Existing keys are unchanged. The inhabitants' prompt, tools and observations are unchanged.
* With the mock backend, reflections run by default in `observe`/`crisis` using a labelled template (`source: mock_template`).
  Disable with `isvara_config={"enabled": false}`.

## Measured (mock; CPU; this sandbox) - `docs/results/isvara-mock-*.json`
* 5 inhabitants + wildlife, 400 ticks, a reflection every 40: 10 extra "calls" (2.3% of the 434 inhabitant calls);
  identical physical state with and without reflections; wall time 2.5 s vs 3.9 s in the noisy two-world comparison (a
  reflection is tens of milliseconds of bookkeeping); restore from the checkpoint reproduced the reflections with no model call.
* 50 inhabitants, 150 ticks, every 30: 5 reflections (0.4% of calls); physical state identical.
* Journal: a reflection adds about the record's size (1-2 KB of `tick_committed` patch) once per interval.

## Real LFM3 results so far
**First bounded T4 check (draft PR #7, main ce8e1dd, 5 inhabitants, 60 ticks, a reflection every 20): 0 of 3 reflections were valid.**
All three attempts used the full 320-token output limit and failed with `expected exactly one complete RECORD_REFLECTION call`
(read from the run's private events; no model text). What that check did establish with the real model: one shared model, no extra
GPU memory (peak 4,693 MB with and without reflections), about 13 s per attempt, about 8% more wall time, failures contained
(285 inhabitant calls in both worlds), restore made no model calls. It did *not* establish that the model can write a reflection.
The recorded physical-state difference between the two worlds is unexplained (see `--control` below).

**Format revision (this change; CPU-tested only, NOT yet run on a GPU):**
* Failures are now diagnosable without keeping any model text: category (`no_tool_call`, `incomplete_call`, `extra_calls`,
  `wrong_tool`, `bad_parameters`, `text_too_long`, `missing_parameters`, `output_too_long`, `invalid_content`, `prompt_budget`,
  `backend_error`), output tokens, whether the token limit was hit, tool calls found. Optional `keep_raw_head_chars` (default 0, max 500)
  keeps the first N characters of a failed output in the *private* root state only (last 3), never in events, endpoints or result files.
* Generation for reflections stops at the first complete call (`stop_strings=["</tool_call>"]`) and uses no repetition penalty (citing an
  id means copying tokens from the prompt). Inhabitant generation is untouched (tested).
* Shorter ask: one sentence per field; field limits 400/300/300/200/150 characters (was 1200/1200/1200/400/300); context 2,805 -> 1,541
  characters in the comparable case (5 inhabitants, wildlife, 60 ticks): flat compact facts, one earlier note instead of two.
* `scripts/isvara_check.py --control` adds a second reflections-off world so run-to-run variation can be told apart from any effect of
  reflection; the result file now lists failure categories and per-failure counts.

Still unverified with the real model: whether this revision yields valid reflections, how often they cite real ids, and their quality.
Run `python scripts/isvara_check.py --backend lfm3 --revision <sha> --control --keep-failure-samples 300 --run-dir <NEW dir> --out <file>`
(5 inhabitants, 60 ticks, three worlds, roughly 25 minutes on a T4); keep the private run folder out of git.
