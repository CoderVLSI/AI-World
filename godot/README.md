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
`F` focus on the people, `G` focus on the animals.

## Options (after `--`)
`--server=URL` `--poll=SECONDS` `--select=agent-0003` `--focus=agent-0003|<animal id>|animals` and, for automated checks, `--screenshot=out.png --wait=SECONDS`
(saves a frame after that many seconds of live data and quits).

## People who grow
Every person is built from primitives (`human.gd`) using the simulation's recorded `age_years`, `height_cm`, gender, skin tone and
clothing, so one person visibly grows: an infant's head is about a quarter of their height, a child's legs are short, an adolescent
is between, an adult is about 1/7.5, and an elder stoops and greys (`human_proportions.gd`; stage ages are tied to
`caitanya/lifecycle.py` by a test). Height always comes from the simulation; only the shape depends on age, and the shape is a
stylised display choice, not medical data. The body reshapes in place as `age_years` changes. Poses come from the same recorded-state
rule as everyone else (`animation_map.gd`): walk only when really moving, sit for a recent rest, and so on.

![the same two people at eight ages](../docs/images/human_growth.png)

(`OUT=pic.png xvfb-run -a godot --path godot --rendering-driver opengl3 --script res://tests/human_gallery.gd` reproduces the picture.)
By default everyone is drawn this way. `--humans=models` uses the fetched rigged models for adults only (a scaled adult model cannot
show a child's proportions, so children are always drawn procedurally).

## Animated characters (optional)
The viewer draws simple figures out of the box. To use animated, rigged people, fetch the models once (they are
third-party CC-BY assets and are **not stored in this repository**):

    SKETCHFAB_API_TOKEN=... python scripts/fetch_assets.py      # your own token; writes credits to godot/assets/ATTRIBUTIONS.md
    godot --headless --import --path godot                      # or just open the project once in the Godot editor

Animation follows what the simulation **recorded**, never a script (`animation_map.gd`, tested): real movement ->
walk; a recent `rest`/`rest_for`/`reflect` -> seated pose (shown as a neutral pose, deliberately not labelled with any
meaning); `speak`/`teach` -> talking; gathering, handling objects and experiments -> bending to work; anything else,
or no recorded action, -> idle. There is no running, fighting or hunting state because the simulation has no such
actions yet. A model lacking a clip for a state falls back to idle. The inspector shows the last recorded action.

Display choices (visual only): the gender label picks the model (the nonbinary and unspecified ones alternate by
agent number); `height_cm` scales the body; each model's measured size, clip names and seat height are in
`godot/assets/manifest.json`.

## What it shows today
Terrain and biomes from the simulation's own heightmap, day/night from the world clock, inhabitants (colour, build,
age), resources, objects, fires (with light) and each inhabitant's current plan. Wildlife is drawn when the server's
`/api/v1/live` carries a `wildlife` block (not yet verified visually: wildlife is not merged into `main`).

Contract: [docs/WITNESS_API.md](../docs/WITNESS_API.md). Tooling for development: `scripts/setup_godot_tools.sh`.

## Animals
Wildlife from `/api/v1/live` is drawn as low-poly animals, one silhouette per species (`animal_builder.gd`; deer
show antlers only when the recorded sex is male). Colour and sex come from the simulation. Size and shape are display
choices; insects are drawn larger than life so they can be seen. Poses come from `animal_motion.gd` and only from what
the simulation **recorded** (`resting`, `foraging`, `hunting`, `avoiding predator`, `grazing aquatic food`,
`swimming`, `flying`, `roaming`) plus real movement: legs swing only while the animal actually moves, a bird is
airborne only when recorded as flying, and an unknown action is an idle animal. A test cross-checks that list
against `fauna/ecology.py`. The picture above is reproducible: `OUT=pic.png xvfb-run -a godot --path godot --rendering-driver opengl3 --script res://tests/animal_gallery.gd`. Press `G` to focus the animals, or start with `--focus=<animal id>`.

![all species](../docs/images/animals_gallery.png)
