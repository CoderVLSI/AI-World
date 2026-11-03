# Witness API contract (for external viewers)

All routes are **GET only** (other methods return 405) and serve public, redacted data. Pinned by
`tests/test_witness_api.py`; change them deliberately.

## `GET /api/v1/terrain?step=N` (1-16, default 2) — `caitanya.terrain.v1`
Static for a given seed; fetch once and cache. Row-major (z rows, x columns), sampled every `step` tiles:
`seed, width, depth, step, columns, rows, biomes[], water_level, biome[] (indices into biomes), elevation[]`.
Invalid `step` -> 400. Values equal the simulation's own `geography()`.

## `GET /api/v1/live` — `caitanya.live.v1` (poll about once a second)
`tick, status, width, depth, climate{hour,day,season,weather,temperature_c}, calendar, summary{population,births,deaths,
autonomy_mode}, agents[], resources[], objects[]` and, only when the world has animals, `wildlife{species{}, animals[]}`.
- `agents[]`: `id, x, z, alive, gender, life_stage, generation, age_years, height_cm, skin_tone, clothing_color,
  parent_ids, hunger, thirst, energy, health, unwell, busy_until_tick` and, when it has an intention,
  `task{kind, params, chosen_by, steps_left}` (`chosen_by` is `lfm_decision` or `mock_policy`).
- `resources[]`: `id, x, z, kind, amount` (amount > 0 only). `objects[]`: unheld objects `id, kind, x, z, burning`.
- Never present: memories, hypotheses, scheduler internals, root/continuity data, RNG state.

Other useful routes: `/api/v1/world/events?after=N`, `/api/v1/history?from_tick=T&to_tick=T` (one committed tick),
`/api/v1/families`, `/api/v1/scheduler`, `/api/v1/knowledge`.
