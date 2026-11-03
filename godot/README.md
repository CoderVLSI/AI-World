# CAITANYA witness client (Godot 4.4)

A **read-only** 3D viewer. It fetches the world's terrain once (`/api/v1/terrain`), then polls `/api/v1/live`
about once a second and smooths movement between updates. It sends only HTTP GET requests; a test fails if any
script in this folder ever uses another method. It cannot command, feed or influence inhabitants.

## Run it
1. Start a simulation (mock policy, no GPU needed):
   `python -m caitanya.server --population 12 --port 8000 --run-dir runs/local`
2. Open this folder in Godot 4.4 (Compatibility renderer, works on laptops without a GPU), press Play, or:
   `godot --path godot -- --server=http://127.0.0.1:8000`

To watch a finished run, restore it locally (`python -m caitanya.server --recover <run folder>`) and point Godot at it.
Keep the server on `localhost` (or reach it through SSH port-forwarding / a private network): the app has no login.

## Controls
right-drag orbit, wheel zoom, WASD or shift+left-drag pan, click a person to inspect (needs, plan and who chose it),
`F` focus on the people.

## Options (after `--`)
`--server=URL` `--poll=SECONDS` `--select=agent-0003` and, for automated checks, `--screenshot=out.png --wait=SECONDS`
(saves a frame after that many seconds of live data and quits).

## What it shows today
Terrain and biomes from the simulation's own heightmap, day/night from the world clock, inhabitants (colour, build,
age), resources, objects, fires (with light) and each inhabitant's current plan. Wildlife is drawn when the server's
`/api/v1/live` carries a `wildlife` block (not yet verified visually: wildlife is not merged into `main`).

Contract: [docs/WITNESS_API.md](../docs/WITNESS_API.md). Tooling for development: `scripts/setup_godot_tools.sh`.
