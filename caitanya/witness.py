"""Read-only data shaped for external viewers (Godot, Three.js, anything that can GET JSON).

Nothing here reads private state: ``live_view`` works only from the already-redacted public
snapshot, and ``terrain_grid`` is a pure function of the seed. Neither can change the world.
"""
from .nature import geography

SCHEMA_TERRAIN = "caitanya.terrain.v1"
SCHEMA_LIVE = "caitanya.live.v1"
BIOMES = ["water", "wetland", "grassland", "forest", "dryland", "highland"]
WATER_LEVEL = -0.25
MAX_STEP = 16
_AGENT_KEYS = ("id", "x", "z", "alive", "gender", "life_stage", "generation", "age_years", "height_cm",
               "skin_tone", "clothing_color", "parent_ids")


def terrain_grid(world, step=2):
    """Heightmap and biomes sampled every ``step`` tiles (row-major: z rows, x columns).

    Static for a given seed, so viewers can fetch it once and cache it.
    """
    if type(step) is not int or not 1 <= step <= MAX_STEP:
        raise ValueError(f"step must be an integer from 1 to {MAX_STEP}")
    xs, zs = range(0, world.width, step), range(0, world.depth, step)
    biome, elevation = [], []
    for z in zs:
        for x in xs:
            g = geography(x, z, world.width, world.depth, world.seed)
            biome.append(BIOMES.index(g["biome"]))
            elevation.append(round(g["elevation"], 3))
    return {"schema": SCHEMA_TERRAIN, "seed": world.seed, "width": world.width, "depth": world.depth,
            "step": step, "columns": len(xs), "rows": len(zs), "biomes": BIOMES, "water_level": WATER_LEVEL,
            "biome": biome, "elevation": elevation}


def _agent(a, last_action=None):
    out = {k: a.get(k) for k in _AGENT_KEYS}
    out["last_action"] = last_action       # {type, tick, origin} of its most recent recorded action, or None
    for need in ("hunger", "thirst", "energy", "health"):
        out[need] = round(a.get(need, 0))
    out["unwell"] = bool(a.get("illness"))
    out["busy_until_tick"] = a.get("busy_until_tick", 0)
    task = a.get("task")
    if task:
        out["task"] = {"kind": task["kind"], "params": task.get("params", {}),
                       "chosen_by": (task.get("selected_by") or {}).get("origin"),
                       "steps_left": max(0, len(task.get("path", [])) - task.get("step", 0))}
    return out


def live_view(snapshot):
    """A small, polling-friendly view of the public snapshot (positions, plans, resources, objects)."""
    objects = [{"id": o["id"], "kind": o["kind"], "x": o["x"], "z": o["z"],
                "burning": o["kind"] == "fire" and snapshot["tick"] >= o.get("start_tick", 0)}
               for o in snapshot.get("objects", {}).values() if not o.get("held_by")]
    view = {"schema": SCHEMA_LIVE, "tick": snapshot["tick"], "status": snapshot["status"],
            "width": snapshot["width"], "depth": snapshot["depth"], "climate": snapshot.get("climate"),
            "calendar": snapshot.get("calendar"),
            "agents": [_agent(a, snapshot.get("last_actions", {}).get(a["id"])) for a in snapshot["agents"].values()],
            "resources": [{"id": n["id"], "x": n["x"], "z": n["z"], "kind": n["kind"], "amount": n["amount"]}
                          for n in snapshot["resources"].values() if n["amount"] > 0],
            "objects": objects}
    metrics = snapshot.get("metrics") or {}
    view["summary"] = {"population": metrics.get("population"), "births": metrics.get("births"),
                       "deaths": metrics.get("deaths"), "autonomy_mode": metrics.get("autonomy_mode")}
    wildlife = snapshot.get("wildlife")
    if wildlife:  # optional layer (present only when the world has animals)
        view["wildlife"] = {"species": {k: {"name": v.get("name"), "group": v.get("group"), "color": v.get("color")}
                                        for k, v in wildlife.get("species", {}).items()},
                            "animals": [{k: b.get(k) for k in ("id", "species", "x", "z", "action", "sex", "alive")}
                                        for b in wildlife.get("animals", []) if b.get("alive")]}
    return view
