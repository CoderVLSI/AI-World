# Plan: a river-valley map (geography-v2) — for approval, nothing built yet

## Why
You asked whether the map is big and rich enough for river-valley societies (Mesopotamia, the Indus valley) to ever develop.
Measured answer today: **no, and a bigger map does not fix it.**

* `caitanya/nature.py: geography()` is one pure function of `(x, z, width, depth, seed)`: **one** sine-wave river, **one** lake, a 3-tile coast.
* Biome shares at 128 / 256 / 512 tiles are almost the same (grassland 33 / 41 / 40 %, water 10 / 7 / 6 %, wetland 8 / 5 / 4 %).
  Doubling the size adds more of the same grassland, not more kinds of place.
* Water is not walkable, so a wide river is a wall unless something lets people cross.
* Resources are scattered per biome with no link to rivers (`genesis.py`), and animals are a fixed ~72 whatever the size.
* `geography()` is **not versioned**: genesis records `geography-v1` but 13 production call sites (engine, genesis, scheduler, witness,
  fauna) call the function directly, so a second map cannot be selected per world without touching all of them.

## What the map can and cannot do
A map only supplies conditions: water, fertile ground, flooding, dry land between valleys, distance. Whether people build farms, towns or
trade is left to them, exactly as before. Nothing here preprograms farming, irrigation, religion, recipes or a "civilisation".
Today the real model barely walks away from a fire, so nothing in this plan should be read as a promise that settlements appear.

## Design (geography-v2)
1. **Versioned dispatch (no behaviour change).** One helper `world.terrain_at(x, z)` chooses the generator from the version recorded in the
   genesis plan. All 13 call sites use it. Old worlds and checkpoints keep `geography-v1` byte for byte (the golden fixture
   `tests/fixtures/genesis_golden.json` must not change).
2. **Rivers.** Two main rivers that start in highlands and run to a coast, joining into a delta (Tigris/Euphrates-like), plus a few
   seasonal tributaries. Drawn from seeded polylines (computed once per map and cached), not per-tile trigonometry, so large maps stay fast.
3. **Floodplain.** A fertile band beside each river, wider than the channel, as a **new biome `floodplain`** appended to the biome list so
   existing indices do not move.
4. **Dry land between valleys.** A seeded aridity field makes steppe/desert (existing `dryland`) grow with distance from water, so valleys are
   places worth being in and the land between them is hard.
5. **Fords.** Shallow, walkable but costly crossings every so often so rivers divide land without making it unreachable.
6. **Coast and delta** at the river mouths instead of a 3-tile strip.
7. **Founders start on a floodplain** (today they spawn at a fixed point, `width//4, depth//2`).
8. **Scale with area.** Resource node count and wildlife count grow with land area (today wildlife is fixed). Species habitats are
   checked against the new biome.
9. **Viewers.** Palette entry for `floodplain` in Godot (`terrain_view.gd`) and the browser viewer; the biome list is already sent by the API.

## Floods and plants (separate, later, needs your approval)
* **Seasonal floods** can reuse the existing lasting-hazard machinery (`floodwater`, non-lethal, a physical zone). A flood that refreshes
  floodplain grain/herbs would be a world rule, not an instruction.
* **Cotton / jute / flax-like plants.** Today only `plant_fiber` exists. New raw plants would be natural resources placed by climate and
  biome (like fruit or fibre now), never a recipe. Question for you below.
* **Cultivation** (planting) is **not** part of this. `grain` is already a renewable gatherable node; any planting rule would have to be a
  physical rule (seed + soil + water + time) in its own reviewed PR.

## Delivery (small PRs, each tested, none merged without you)
| PR | Content | Done when |
|---|---|---|
| A | Versioned geography dispatch; v1 only | Golden fixture and full suite unchanged; a test fails if any module still calls the bare function |
| B | `geography-v2` generator, `floodplain` biome, caching | Same seed gives the same map; every land tile reachable from the founders' area; both rivers crossable; biome shares printed; 256 map builds in about the same time as v1 |
| C | Viewer palettes, terrain preview images, fauna habitats | Godot and browser screenshots; habitat test for every species on the new biome |
| D | Founders on the floodplain; resources and wildlife scale with area | Deterministic counts; measured tick time at 256 and 512 |
| E (approval first) | Seasonal floods and new fibre plants | Opt-in flag, off by default, non-lethal, tested |

v2 is selected only through the version recorded in the genesis plan (opt-in for new worlds); nothing existing changes.

## Honest limits
* Real LFM3 throughput, not map size, limits how many inhabitants can live at once; a larger valley with five people stays empty.
* One seed is one map. Reachability and shares will be checked over many seeds, but "looks like Mesopotamia" is a judgement, not a test.
* Rivers made from polylines are an approximation, not hydrology (no real flow, erosion or water table).

## Decisions (you said to do what I think is right; these are mine and can be changed)
1. **Shape:** two rivers joining at a delta with dry land between.
2. **Default size:** stays 256; larger maps remain available. The model's speed, not the map size, is the limit.
3. **Plant names:** neutral, property-based names, so no real-world technology is implied. Not built until PR E.
4. **Floods:** opt-in only, off by default. Not built until PR E.
5. **Independence:** the map never tells inhabitants what to do or what exists. They learn the land only through their own observations,
   and everything they decide to do about it (settle, farm, trade, name things) is theirs.

## Progress
* PR A (versioned dispatch, no behaviour change): #24.
