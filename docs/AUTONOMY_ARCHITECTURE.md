# Autonomy architecture (v0.5.0)

This document describes how decisions are scheduled, how time and bodies work, how inhabitants experiment, and how
they remember and transmit what they learn. Every number below is a configurable, documented experiment parameter
(`caitanya/autonomy.py`), recorded in the run manifest. None is calibrated to science, and none was tuned to keep a
population alive; the measured consequences are in [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md).

Nothing in this layer gives an inhabitant a goal, a discovery, a belief or a religious concept. The
`neutral-v4-inquiry` system prompt is byte-for-byte unchanged (a test pins its SHA-256 against the reference
commit), and the private Brahman root, continuity threads, ledger and manifestation policy are untouched.

## 1. Modes and schema versions

| Mode | Used for | Behaviour |
|---|---|---|
| `foundations` (default for new worlds) | new experiments | time-based physiology, budgeted scheduler, intentions, experiments, memory |
| `legacy` | schema-1 checkpoints, `--legacy`, regression fixtures | the exact v0.4.0 dynamics (+1 need per tick, decisions every third tick) |

State `schema_version` is now **2**. Schema 1 loads (`SUPPORTED_SCHEMAS = (1, 2)`) in `legacy` mode so a running
experiment's dynamics do not change underneath it. A genuine v0.4.0 checkpoint and journal tail are committed as a
fixture (`tests/fixtures/v1_run`); the tests show that continuing it under the new code reproduces v0.4.0's recorded
state digest bit-for-bit, and that its journal tail recovers. Unsupported schemas fail with `unsupported schema`.

## 2. Time and physiology (`physiology.py`)

A tick lasts `days_per_tick * 24` simulated hours (baseline: 10 minutes). All rates are **per simulated hour** and are
multiplied by the tick length, so changing speed changes how many actions fit in an hour, never how fast bodies
consume resources per hour. Ticks longer than `max_tick_hours` (6 h) are refused rather than silently distorting
physiology. In an accelerated run an inhabitant therefore gets fewer actions per simulated hour; that is a real
consequence, not a bug.

| Parameter | Default | Meaning |
|---|---|---|
| `hunger_per_hour` | 100/120 | starving after 5 days without food |
| `thirst_per_hour` | 100/48 | dehydrated after 2 days without water |
| `energy_decay_per_hour` | 1.0 | passive fatigue; `REST` restores `rest_recovery_per_hour` = 12 |
| `effort_scale` | 0.25 | multiplier on the legacy per-action energy cost |
| `starvation_/dehydration_damage_per_hour` | 3 / 5 | health lost per hour at need 100 |
| `regen_per_hour` | 0.75 | healing while hunger and thirst are below 50 and energy above 10 |
| `infant_/child_need_scale` | 0.7 / 0.85 | simplified: smaller bodies consume less |
| `illness_per_day` | 0.01 (x3 when depleted) | deterministic hash of (seed, tick, agent), not the world RNG |
| `illness_damage_per_hour` | 1.2 (x0.4 while fed, hydrated and rested) | illness lasts 2-5 days; neglect is lethal, basic care is survivable |
| `regrowth_hours` | 6 | renewable nodes regain one unit per interval of elapsed time |

Aging, pregnancy (`due_day`) and childhood already used elapsed days and are unchanged. No resource is created from
nothing; death is attributed (`starvation`, `dehydration`, `illness`, `aging`). Minerals stay finite.

Caregiving: infants (under 3) cannot act. A guardian within 12 tiles whose dependant reaches a need of 60 is
prompted to *reconsider* (its running intention is re-evaluated with interrupt priority); the controller never
chooses to feed the child. `CARE` is unchanged.

An optional **survival reflex** (`reflex.enabled`, default **off**) drinks or eats carried supplies once a need passes
a threshold. Each intervention is journaled with `origin: survival_reflex` and counted; it is never counted as a
decision.

## 3. Decisions versus mechanical execution (`scheduler.py`)

* **Decision** - the shared model is called once and chooses what to attempt, why (`reason`, optional) and when to be
  asked again (`reconsider_hours`, optional). Only this calls the model and increments the decision counters.
* **Mechanical execution** - once an *intention* is accepted, deterministic code performs its individual steps through
  the same validated `World.apply` path. Steps are journaled with `origin: mechanical_execution` and the `task_id`,
  and are never counted as decisions.

Intentions (all validated, bounded, interruptible): `TRAVEL_TO x z`, `GATHER_AT resource amount (1-8)`,
`REST_FOR hours (1-12)`, `CANCEL_TASK`. Routes come from a deterministic A\* search (`max_path_length` 150,
`max_path_expansions` 8000). The scheduler never invents an objective.

**Interruption.** Before every mechanical step an intention is checked and ended (reason recorded, inhabitant woken
with interrupt priority) when: the target resource is gone; the route is blocked (at most 2 re-plans); health falls by
15 or drops below 40; a need *crosses* 85 (a need that was already critical when the intention began does not cause
thrashing); illness begins; or `max_task_ticks` (72) is reached. A new accepted decision supersedes the intention.

**Fair scheduling.** Each tick the scheduler selects due inhabitants and spends up to `max_decisions_per_tick` (8)
model calls, stopping early at `max_seconds_per_tick` (20 s, real backends only; a skipped inhabitant stays due).
Order: (0) waited at least `max_wait_ticks`; (1) woken by an interrupt; (2) everyone else; within a class by longest
wait, then *least recently served* (this makes the rotation a true FIFO; breaking ties by id produced a measurably
uneven rotation during development), then need urgency. Idle inhabitants are due `min_decision_gap_ticks` after their
last decision; inhabitants with an intention are due when woken or at their chosen reconsideration time. Bounded
waiting is measured, not assumed: `max_wait_ticks`, per-agent interval sums and maxima, decisions per agent.

**Failures.** A failed model call (error, timeout, bad tool call) executes nothing, journals `inference_failed`, and
delays that inhabitant (6 ticks x failure streak up to 4). There is no mock fallback.

**Durability.** Scheduler state and every inhabitant's task live in the checkpointed state and journal patches, so
checkpoint, replay and recovery resume mid-intention (tested).

## 4. Experimentation (`materials.py`, `experiments.py`)

Materials have hardness, toughness, tensile strength, flexibility, fracture behaviour, ignition/char points, thermal
mass, friction and moisture. A picked unit becomes an *object* with components; each component gets a hidden quality
(grain) and flaw drawn from a deterministic hash, so repeating an experiment on a new piece can differ. Inhabitants can
observe grain, cracks, mass, hardness, density, flexibility, moisture, temperature and edge keenness (`INSPECT`);
tensile strength, ignition points, flaws and attachment strength are only learned by testing.

| Action | Physics (simplified) |
|---|---|
| `PICK` `STOW` `TAKE` `DROP` `HAND_OVER` | handling; 25 kg carrying limit; ownership and provenance |
| `STRIKE striker target force` | impact = force x sqrt(striker mass) x efficiency(hardness ratio) against toughness, flaw and moisture: no effect, a chip (flake) or a fracture into 2-4 pieces; fresh-edge sharpness depends on grain, so fine stone breaks keen and coarse stone dull; a softer striker wears |
| `COMBINE parts method` | `lash` (needs a loose plant-fibre piece), `clay_bond` (needs a clay piece; strength depends on wet/dry/fired state over time), `stack` (loose); strength depends on binder, size fit and jitter |
| `SEPARATE` | disassembly; untied binders fray |
| `HEAT subject source minutes` | Newtonian heating in a fire or sunlight: drying, charring, burning to ash, clay hardening if dried first (otherwise steam shattering), flawed stone cracking; the inhabitant is committed for the duration |
| `COOL subject` | quench with carried or local water: thermal shock can shatter hot stone or fired clay |
| `RUB first second force minutes beside` | friction heating = 14 x force x sqrt(minutes) x friction x dryness; ignition needs a flammable object beside it whose ignition point is reached; otherwise "warm" or "smouldering" |
| `FEED_FIRE` | adds fuel (damp fuel yields little); fires burn a bounded time, are shortened by rain, and go out |
| `TEST bend\|pull\|drop\|cut\|pound` | applies a load; reports measured results; attachments give way at their real strength; edges wear; tools can be damaged |
| `GATHER_WITH resource tool` | yield 1-3 per effort from a tool's *performance* (edge, handle attachment, mass, hardness) for the resource's motion; weak attachments fail under load |

**No recipes.** A flake lashed to wood outperforms a bare flake only because the lashed object has a handle that
multiplies cutting performance in the physics; a dull cobble lashed to wood measures as having no edge. Nothing
names or rewards an axe, spear, wheel, fire technology, house or temple, and a test searches the journal for such
words. Fire exists only if an inhabitant creates the conditions; nothing ignites spontaneously.

**Conservation.** Mass moves between inventory, objects, and an explicit ledger (`dispersed_g` dust and water used,
`atmosphere_g` combustion and volatiles). A randomized test applies hundreds of valid and invalid actions and checks
the total is conserved after every accepted action and that every rejected action leaves state byte-identical.

**Safety.** All parameters are validated before any mutation, no generated text is executed, and rejected actions
mutate nothing. Not modelled: smelting, containers and liquids, spoilage, structures that block movement, tool
durability beyond edge/integrity wear.

## 5. Memory and learning (`memory.py`)

Per-inhabitant, private, bounded, checkpointed; no extra model instances. Categories: **episodic**, **practical**
(structured `subject / property / value / conditions` findings), **hypotheses**, **relationships** (counters),
**procedural** (generalised action sequences that produced a measured result; no object ids), **cultural** (claims
from others) and **places** (where resources were seen; a site seen to be empty is forgotten).

* *Evidence status.* Own observations are `observed`, then `corroborated` when repeated consistently or `variable`
  when they disagree (numeric samples and categorical outcome counts are kept, so natural variation is not mistaken
  for contradiction). Witnessed demonstrations enter at lower confidence and do not count as independent.
* *Speculation.* `HYPOTHESIZE` stores an explanation as `unverified`. `ASSESS` revises it as
  supported/contradicted/uncertain only when it cites *different, related* evidence from the inhabitant's own memory;
  confidence never exceeds 0.8; each change is kept as a revision. Hypothesis text never enters the public journal.
* *Retrieval.* Deterministic scoring of tag overlap with the current situation (nearby resources, carried and held
  materials, nearby inhabitants, needs, current intention), importance, confidence, recency and status, capped at 8
  items / 1500 characters, so the prompt stays bounded however long a run is.
* *Limits.* Per-category caps evict the lowest-retention entry.

**Transmission.** Inhabitants within 2 tiles *witness* experiments; `SHARE_KNOWLEDGE`, `TEACH` and `WRITE_FINDINGS` +
`READ` pass findings on as `unverified` claims keeping their origin and chain (`[author, relay, ...]`). A claim
becomes `corroborated` or `contradicted` when the receiver's own experience about the same thing arrives, with the
revision recorded. A written work outlives its author. A newborn's memory is empty, and nothing from a previous
life, the root registry, or any scripture is ever stored (tested).

## 6. Information boundaries

Memories, hypotheses, scheduler internals and the root never appear in prompts, snapshots, history or events (the
event feed carries world-observable physical results, intentions, attribution and counters). The new read-only
endpoints `/api/v1/scheduler`, `/api/v1/knowledge` and `/api/v1/objects` are GET-only aggregates. The witness can
observe plans, attribution, objects, fires, experiments and findings counts, and cannot issue commands.

## 7. Persistence cost (measured)

Per tick at 50 inhabitants the journal averages about 67 KB (physiology values change every tick for every body);
each checkpoint embeds the full event history, so total checkpoint size grows quadratically with run length. See
[MERGE_CHECKLIST.md](MERGE_CHECKLIST.md) for the consequences and mitigations (`--checkpoint-every`).
