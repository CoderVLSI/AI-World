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
