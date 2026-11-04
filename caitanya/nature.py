"""Seeded geography and explicit, simplified human anatomy. No generated biology claims."""
import math

RESOURCE_TYPES = {
    "food": (True, 8), "fruit": (True, 6), "grain": (True, 10),
    "water": (True, 40), "wood": (True, 16), "stone": (False, 24),
    "clay": (False, 20), "sand": (False, 30), "iron_ore": (False, 12),
    "copper_ore": (False, 10), "coal": (False, 14), "salt": (False, 10),
    "herbs": (True, 6), "plant_fiber": (True, 12), "fish": (True, 8),
}
EDIBLE = ("food", "fruit", "grain", "fish")

DEFAULT_GEOGRAPHY = "geography-v1"


def geography(x, z, width, depth, seed, version=DEFAULT_GEOGRAPHY):
    """Authoritative terrain for one tile, from the generator named by `version` (recorded in the world's genesis plan)."""
    try:
        generator = GEOGRAPHY_GENERATORS[version]
    except KeyError:
        raise ValueError(f"unknown geography generator {version!r}") from None
    return generator(x, z, width, depth, seed)


def _geography_v1(x, z, width, depth, seed):
    """geography-v1: continuous hills, one river, a lake and a coast. Frozen: worlds and checkpoints made with it must reproduce exactly."""
    phase = seed % 101 / 17
    river = width * .40 + math.sin(z / 19 + phase) * width * .065
    lake = ((x-width*.72)/(width*.10))**2 + ((z-depth*.65)/(depth*.13))**2
    water = z < 3 or abs(x-river) < 2.2 or lake < 1
    elevation = max(.2, 1.4 + 1.3*math.sin(x/17+phase)*math.cos(z/23) +
                    3.5*max(0, math.sin(x/39+z/29+phase))**3)
    if water: return dict(biome="water", elevation=-.25, walkable=False)
    if abs(x-river)<6 or lake<1.5: biome="wetland"
    elif elevation>4: biome="highland"
    elif math.sin(x/23+phase)+math.cos(z/26)>.5: biome="forest"
    elif math.sin(z/31-x/37)>.65: biome="dryland"
    else: biome="grassland"
    return dict(biome=biome,elevation=round(elevation,3),walkable=True)

from . import valley  # noqa: E402  (geography-v2 lives in its own module)

GEOGRAPHY_GENERATORS = {"geography-v1": _geography_v1, "geography-v2": valley.tile}


def founding_site(width, depth, seed, version, radius):
    """Centre of the founders' starting area for the given terrain generator."""
    if version == "geography-v2":
        return valley.founding_site(width, depth, seed, radius)
    return width // 4, depth // 2


def anatomy():
    parts = {name: {"health":100} for name in (
        "head","neck","torso","pelvis","left_upper_arm","right_upper_arm",
        "left_forearm","right_forearm","left_hand","right_hand",
        "left_thigh","right_thigh","left_lower_leg","right_lower_leg","left_foot","right_foot",
        "left_eye","right_eye","left_ear","right_ear","nose","mouth")}
    for side in ("left","right"):
        for digit in ("thumb","index","middle","ring","little"):
            parts[f"{side}_{digit}_finger"]={"health":100}
        for toe in range(1,6): parts[f"{side}_toe_{toe}"]={"health":100}
    return {"parts":parts,"systems":{"circulatory":100,"respiratory":100,"digestive":100,
        "nervous":100,"musculoskeletal":100,"immune":100},
        "simulation_detail":"simplified status model; not full organ physiology"}

def climate(tick,days_per_tick=1/144):
    elapsed=tick*days_per_tick;day=int(elapsed)
    return dict(hour=round((elapsed%1)*24,2),day=day,year=day//365,season=("spring","summer","autumn","winter")[(day//30)%4],
        weather=("clear","cloudy","rain")[day%3],temperature_c=round(17+7*math.sin(elapsed*2*math.pi-math.pi/2),1))
