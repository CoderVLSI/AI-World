# Fourteen formless nature forces — review branch

This opt-in prototype adds environmental consequences to the shared human world.
It does not create deity characters, agents, bodies, personalities, worship,
revelations, or hidden instructions. These fourteen names and their assignments
are the operator's chosen simulation vocabulary, **not a canonical religious list**.
The root and the neutral-v4-inquiry instructions are unchanged. These forces are
deterministic world rules, not Liquid model decisions or conscious sub-agents.

## Enable only in a new experimental world

```powershell
python -m caitanya.server --nature-forces --run-dir runs/nature-review --max-ticks 144
```

This command uses the server's default mock inhabitant backend. It is a CPU
software demonstration, not a real-model experiment. No GPU run was made for this
feature. Choose an unused run directory. Without `--nature-forces`, existing
behavior and saved state remain unchanged. `World(nature_forces=True)` is the
Python equivalent. Recovery preserves the checkpoint setting; CLI flags do not
toggle forces in an existing run. Old checkpoints remain off.

## Implemented effects

Each occurrence is one instantaneous local pulse, radius 5–7 cells, strength 1–3.
Resource units and physiology values are abstract simulation units.

| Internal name | Observable phenomenon | Consequences per strength unit | Base occurrence rate per world-day |
|---|---|---|---:|
| Agni | Wildfire | Wood −2, plant fiber −1, health −2 | 0.08 |
| Vayu | Strong wind | Energy −2 | 0.18 |
| Indra | Lightning | Wood −1, health −3 | 0.06 |
| Varuna | Floodwater | Water +2, grain −1, energy −2 | 0.08 |
| Mitra | Calm weather | Energy +1 | 0.20 |
| Yama | Organic decay | Food, fruit, fish −1 each | 0.12 |
| Surya | Heatwave | Water −1, thirst +3; hours 08–18 only | 0.12 |
| Soma | Cool interval | Thirst −1; hours 18–06 only | 0.18 |
| Prithvi | Earth tremor | Energy −2, health −2 | 0.03 |
| Parjanya | Heavy rain | Water +2, energy −1 | 0.18 |
| Rudra | Severe storm | Wood −1, energy −3, health −2 | 0.04 |
| Apas | Water replenishment | Water +2 | 0.15 |
| Ushas | Mild morning interval | Energy +1; hours 05–08 only | 0.20 |
| Bhumi | Soil renewal | Grain, herbs, plant fiber +1 each | 0.10 |

Rates are starting simulation design choices, not empirical climate estimates.
The per-tick occurrence probability is `1-exp(-rate*days_per_tick)`; gated forces
can only occur in their listed time window, so their effective daily rates are
lower. A force has at most one pulse per tick. Location is sampled across the
whole map, independent of agents; an occurrence can miss everyone and everything.
No milestone, discovery, death, or philosophical conclusion is scheduled.

Effects only change existing resource nodes and living humans within the radius.
Amounts stay between zero and node capacity. Thirst and energy stay in 0–100;
injury does not directly reduce positive health below 1 in this review version.
It cannot resurrect a dead agent or create resource nodes. Yama represents
resource decay here, not moral judgment or a controller of human deaths.

## Evidence, observation, and persistence

Each pulse emits a `nature_force` event with `source=environment_rule`, a rules
version, location, strength, internal force key, and actual before/after outcomes.
An empty outcomes list means no recorded state changed. It is never labeled as
an inhabitant decision. Internal keys are for operators and future review.

Inhabitants receive only nearby recent sensory descriptions under
`environment_effects`. They receive no force names, future events, root identity,
or other inhabitants' private outcomes. Observations last at most six ticks.
The public world snapshot and `/api/v1/live` expose recent sensory effects, not
force controller state. There is no new HTTP mutation route or inhabitant tool
for summoning them. Godot can ignore this optional field until visuals are added.

The subsystem has its own hash-derived random streams keyed by world seed,
tick, rules version, and force key. It does not consume the world's RNG or call
the model. Pulses occur before physiology and inhabitant decisions, so those
decisions can observe and respond to the consequences. Effects and subsystem
state enter the existing committed state patches and checkpoints. Tests verify
replay and continuation across restoration, including matching future pulses.

## Scope and review notes for Claude

Implemented: opt-in engine/CLI integration; all fourteen distinct rules; bounded
local human/resource effects; neutral observations; event provenance; recovery;
CPU tests. Human inhabitants and wildlife remain in the same world.

Not implemented: persistent fire or flood fields, fluid or wind simulation,
terrain deformation, structural damage, shelter protection, weather-dependent
hazard probabilities, wildlife-specific injuries, Godot particles or sounds,
continuous climate overrides, or conscious/personified deity agents. Cooling,
soil renewal and calm recovery are deliberately abstract need/resource modifiers.
Existing climate remains a separate baseline model. Large timesteps have at most
one pulse per force per tick and do not approximate a full sub-tick event process.

Before any later merge, review hazard rates against survival budgets, overlapping
climate/ecology rules, the nonfatal injury cap, observation duration under different
clock rates, and how the Godot witness should display these events. Personification
would be a separate later design change; nothing here makes that inference.

Validation commands: `python -m pytest tests/test_nature_forces.py -q` and
`python -m pytest -q`. Actual results are recorded in the draft PR.

On 2026-11-03, the final targeted nature-force and witness suite passed 29 tests.
The broad suite, started before the final edge-case test additions, finished with
300 passed, 1 failed, and 1 skipped in 584.20 seconds. Its sole failure was the
unchanged Godot attribution test reading UTF-8 punctuation with Windows' default
cp1252 encoding. The attribution content matches `main` and its generator when
decoded as UTF-8. Re-running the Godot asset suite with `PYTHONUTF8=1` gave 6 passed
and 1 skipped (no local Godot binary). No unrelated asset or test was changed.
`git diff --check` and Python compilation of the new module passed.


## Lasting hazards (`lasting-hazards-v1`, added after review)

Pulses alone were too mild to matter (a 30-day mock check: 0-4 inhabitants affected, nobody harmed). Four forces now also leave a **zone that
keeps acting**: Agni (wildfire, 6 h), Varuna (floodwater, 12 h), Surya (heatwave, 8 h) and Rudra (severe storm, 4 h). The other ten stay
instantaneous. The instant pulse is unchanged (existing tests untouched); the zone starts acting from the next tick.

* **Rules.** Per simulated hour at strength 1: Agni injury 2.0 and energy -1.0; Varuna injury 0.5 and energy -2.0; Surya thirst +3.0 and
  energy -0.5; Rudra injury 1.0 and energy -3.0, multiplied by strength (1-3) and by the tick length. Radius is 4 + strength (Manhattan).
  Damage per hour does not depend on the clock speed (tested at 10-minute and 1-hour ticks); only the number of ticks a zone lasts does.
* **Bounded.** Injury can lower health to 1 but never below, needs are clipped to 0-100, the dead are untouched. This first version is
  deliberately **non-lethal**; lethal hazards need an explicit owner decision.
* **What inhabitants perceive** (`environment_hazards` in their observation, only for zones whose edge is within 8 steps): the
  phenomenon, centre, radius, strength, `distance_to_edge`, `inside`, and `since_tick`. Nothing about how long it will last, no force
  name, no instruction and no other inhabitant's outcome. Their own health and needs are already in their observation.
* **What is recorded** (public events, source `environment_rule`): `nature_hazard_started` and `nature_hazard_ended`. The end event lists,
  for every inhabitant exposed, ticks inside, injury/energy/thirst changes, whether it was still inside at the end and whether it left
  the zone. That is a plain record of how inhabitants responded; nothing scores or rewards a response.
* **Persistence.** Zones and exposure live in the checkpointed `nature_forces` state and replay through the normal patches. Saves made
  before this version have no `hazard_version` and keep the original pulse-only behaviour.
* **Public API.** `environment_hazards` (phenomenon, centre, radius, strength, start tick) in the snapshot and `/api/v1/live`; no exposure
  records, no end ticks.

### Isvara and environmental events
Isvara's reflection context now includes environmental events as recorded evidence: pulses that hit inhabitants, "a lasting wildfire began
at (x,z)", and "the lasting wildfire ended after N ticks: k inhabitants were exposed, j left the zone, m were still inside". It also gets
an `environment` fact block (counts by phenomenon, current zones). It sees phenomena, never a force's internal name, a planned duration
or a future schedule. This is an *indirect* awareness: Isvara can reason about what happened and how inhabitants were recorded to
respond, in its private advisory reflections. It cannot start, steer, lengthen or schedule anything: a test runs the same world with
and without an adversarial proposing Isvara and requires a bit-identical world, hazards included.

### Not yet implemented (next)
Shelter as discoverable physics (for example terrain or built cover reducing exposure), lethal hazards, spreading fire or moving
floods, wildlife injury, and Godot visuals for zones (the live API already carries them).

### Does a model react? Not known
`scripts/hazard_response_diagnostic.py` places a wildfire zone over five inhabitants and counts what each *chose* (parsed tool names
only) while inside and outside, who left, and lowest health. On the CPU, scripted stand-ins show the measurement: an idle stand-in stays
and loses health (62.5 lowest in the saved run, never killed); a fleeing stand-in leaves in a few ticks (about 86-90 lowest). **No real-model
result exists yet.** To run one episode on a GPU (about 5-15 minutes on a T4, never a long run):
`python scripts/hazard_response_diagnostic.py --backend lfm3 --revision ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7 --ticks 40 --max-real-seconds 900 --out hazard_lfm3.json`


### Result of the first real run, and an experiment on the geometric way out
The first real-model episode (draft PR #15, T4, 40 ticks, 5 inhabitants, wildfire over 3 of them): the hazard was visible in 138 of 170
observations, yet **0 of 3 left the zone**. They chose MOVE 15 times, SPEAK 29, WAIT 12, REFLECT 9 and DRINK/EAT 10 while inside, and the three
exposed lost the same health as an idle stand-in (62.5 lowest); nobody died (health floors at 1). So they could see the danger and did
move, but not out. The directions of those moves were not recorded, so it is unknown whether they were random.

The diagnostic now also records, as numbers only: every MOVE chosen inside the zone (classified outward or inward by its effect on the
distance from the zone's centre, with the (dx, dz) steps) and each exposed inhabitant's distance to the zone edge for every tick.

**Experiment, OFF by default (`--hazard-exit-hint`, `World(..., hazard_exit_hint=True)`, needs `--nature-forces`):** an inhabitant *inside* a
zone also sees `leave_dx`, `leave_dz` (the single step that leads straight away from the zone's centre) and `steps_to_leave` (how many such steps
leave it). It is a geometric fact, not terrain-aware (the `blocked` list still shows adjacent obstacles), it is not shown to anyone outside
the zone, and it is not an instruction or a goal. It does come close to helping, which is why it is an explicit, labelled variant:
a test proves the stated way out really leaves the zone from every cell of it, and the setting is recorded in the manifest.

How to run the comparison (one change at a time, same fixture and revision, one bounded episode each, never tuned):
`python scripts/hazard_response_diagnostic.py --backend lfm3 --revision ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7 --ticks 40 --max-real-seconds 900 --out baseline.json`
`python scripts/hazard_response_diagnostic.py --backend lfm3 --revision ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7 --exit-hint --ticks 40 --max-real-seconds 900 --out hint.json`
Read it as: did anyone leave (and after how many ticks), how many inside MOVEs were outward vs inward, and the lowest health. A baseline with
mostly random MOVE directions and a hint run where the same model follows the stated way out would say the missing piece is the geometry,
not the willingness to move; if the hint run still stays, the problem is elsewhere. Scripted CPU stand-ins show what is measured (saved in
`docs/results/hazard-response-cpu-standins-v2-20261103.json`): they say nothing about any model.
