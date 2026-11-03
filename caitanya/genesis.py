"""Genesis: a deterministic, versioned plan through which a world is created once.

Genesis is neutral infrastructure. It is plain code: no model is consulted, nothing here depends on the root
operating mode, and the same plan always builds the same world. The plan is an immutable value; it is validated
before anything is built; the build runs exactly once per new world (the completion marker lives in the private
root state, so restoring or replaying a world can never repeat it).

The physical algorithms here are the ones that existed inline in ``World.__init__`` (terrain from
``nature.geography``, the resource scatter, the founders). They consume the world RNG in the same order, so a
given seed produces the same world as before genesis existed (pinned by ``tests/fixtures/genesis_golden.json``).

Extension points (see docs/GENESIS.md): every stage is identified by a generator version recorded in the plan. A
future generator ships under a new version id; plans naming a version this code does not know are refused, and a
stored world whose recorded terrain digest no longer matches the code is refused instead of silently changing.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields

GENESIS_VERSION = "genesis-v1"
GENERATOR_VERSIONS = {"terrain": "geography-v1", "resources": "scatter-v1", "founders": "founders-v1", "wildlife": "ecology-v1"}
SUPPORTED_GENERATORS = {stage: (version,) for stage, version in GENERATOR_VERSIONS.items()}
SUPPORTED_GENERATORS["founders"] = ("founders-v1", "founders-v2")     # v2: founding families (women, men and children); opt-in
FAMILY_FIELDS = ("families", "children_per_family", "parent_age_range", "child_age_range")

_BIOME_RESOURCES = (("forest", ("wood", "fruit", "herbs", "plant_fiber")), ("highland", ("stone", "iron_ore", "copper_ore", "coal")),
                    ("wetland", ("water", "clay", "fish", "plant_fiber")), ("dryland", ("sand", "salt", "stone")),
                    ("grassland", ("food", "grain", "herbs", "water")))


class GenesisError(ValueError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class GenesisPlan:
    """Immutable description of how one world is created. Every value that shapes the build is here."""
    seed: int
    population: int
    width: int = 64
    depth: int = 64
    spawn_radius: int = 8
    version: str = GENESIS_VERSION
    generators: tuple = tuple(sorted(GENERATOR_VERSIONS.items()))
    min_resources: int = 120
    resources_per_inhabitant: int = 6
    area_per_resource: int = 40
    biome_resources: tuple = _BIOME_RESOURCES
    genders: tuple = ("woman", "man", "nonbinary")
    sex_weights: tuple = (49, 49, 2)
    age_range: tuple = (18, 46)
    height_range_cm: tuple = (152, 193)
    lifespan_range: tuple = (70, 95)
    skin_tones: tuple = ("#e4bc98", "#bd8c68", "#8d5c40", "#573b2e")
    clothing_colors: tuple = ("#678b91", "#b38e5b", "#8e709d", "#758f62")
    founder_water: int = 3
    spawn_food_units: int = 8
    spawn_water_units: int = 40
    wildlife_per_species: int = 0
    days_per_tick: float = 1 / 144
    # Founding families (generator founders-v2, opt-in): `families` households of one woman, one man and `children_per_family` children.
    # With families == 0 these fields are ignored and are NOT serialized, so a default plan is byte-identical to before.
    families: int = 0
    children_per_family: int = 2
    parent_age_range: tuple = (20, 41)
    child_age_range: tuple = (1, 17)

    # -- validation -------------------------------------------------------------------------------------
    def validate(self):
        from .nature import RESOURCE_TYPES
        def integer(name, low, high=None):
            v = getattr(self, name)
            if type(v) is not int or v < low or (high is not None and v > high):
                raise GenesisError(f"invalid {name}")
        if self.version != GENESIS_VERSION:
            raise GenesisError(f"unsupported genesis version {self.version!r}")
        integer("seed", -(2 ** 63), 2 ** 63)
        integer("population", 1, 10_000)
        integer("width", 8, 4096)
        integer("depth", 8, 4096)
        integer("spawn_radius", 1, 4096)
        integer("min_resources", 0, 1_000_000)
        integer("resources_per_inhabitant", 0, 10_000)
        integer("area_per_resource", 1, 1_000_000)
        integer("founder_water", 0, 1000)
        integer("spawn_food_units", 0, 1000)
        integer("spawn_water_units", 0, 1000)
        integer("wildlife_per_species", 0, 1000)
        if type(self.days_per_tick) not in (int, float) or not 0 < self.days_per_tick <= 1000:
            raise GenesisError("invalid days_per_tick")
        if self.wildlife_per_species and self.days_per_tick > 1:
            raise GenesisError("wildlife requires days_per_tick <= 1")
        integer("families", 0, 100_000)
        integer("children_per_family", 0, 12)
        for name in ("parent_age_range", "child_age_range"):
            low, high = getattr(self, name)
            if type(low) is not int or type(high) is not int or not 0 <= low < high <= 120:
                raise GenesisError(f"invalid {name}")
        if self.families and self.population != self.families * (2 + self.children_per_family):
            raise GenesisError("population must equal families x (2 + children_per_family)")
        generators = dict(self.generators)
        if self.families and generators.get("founders") != "founders-v2":
            raise GenesisError("founding families need generator founders-v2")
        if not self.families and generators.get("founders") == "founders-v2":
            raise GenesisError("founders-v2 is for founding families")
        if set(generators) != set(SUPPORTED_GENERATORS):
            raise GenesisError("plan must name a generator version for every stage")
        for stage, version in generators.items():
            if version not in SUPPORTED_GENERATORS[stage]:
                raise GenesisError(f"unsupported {stage} generator {version!r}")
        biomes = dict(self.biome_resources)
        if set(biomes) != {b for b, _ in _BIOME_RESOURCES}:
            raise GenesisError("biome table must cover exactly the known biomes")
        for biome, kinds in biomes.items():
            if not kinds or any(k not in RESOURCE_TYPES for k in kinds):
                raise GenesisError(f"unknown resource kind in biome {biome}")
        if len(self.genders) < 1 or len(self.sex_weights) != 3 or any(type(w) is not int or w < 0 for w in self.sex_weights) or not sum(self.sex_weights):
            raise GenesisError("invalid founder traits")
        for name in ("age_range", "height_range_cm", "lifespan_range"):
            low, high = getattr(self, name)
            if type(low) is not int or type(high) is not int or not 0 <= low < high:
                raise GenesisError(f"invalid {name}")
        if not self.skin_tones or not self.clothing_colors:
            raise GenesisError("founder palettes must not be empty")
        return self

    @property
    def resource_count(self):
        return max(self.min_resources, self.population * self.resources_per_inhabitant,
                   self.width * self.depth // self.area_per_resource)

    # -- serialization ----------------------------------------------------------------------------------
    def to_dict(self):
        def plain(v):
            return [plain(x) for x in v] if isinstance(v, (tuple, list)) else v
        return {f.name: plain(getattr(self, f.name)) for f in fields(self) if self.families or f.name not in FAMILY_FIELDS}

    @classmethod
    def from_dict(cls, data):
        def tup(v):
            return tuple(tup(x) for x in v) if isinstance(v, (list, tuple)) else v
        known = {f.name for f in fields(cls)}
        if set(data) - known:
            raise GenesisError("unknown genesis plan field")
        return cls(**{k: tup(v) for k, v in data.items()}).validate()

    def digest(self):
        return hashlib.sha256(_canonical(self.to_dict()).encode()).hexdigest()


def default_plan(seed, population, width=64, depth=64, spawn_radius=8, wildlife_per_species=0, days_per_tick=1 / 144,
                 families=0, children_per_family=2):
    """The plan that reproduces the pre-genesis world construction exactly (families=0), or one with founding families."""
    extra = {}
    if families:
        extra = dict(families=families, children_per_family=children_per_family,
                     generators=tuple(sorted({**GENERATOR_VERSIONS, "founders": "founders-v2"}.items())))
    return GenesisPlan(seed=seed, population=population, width=width, depth=depth, spawn_radius=spawn_radius,
                       wildlife_per_species=wildlife_per_species, days_per_tick=days_per_tick, **extra).validate()


def terrain_digest(world_terrain):
    return hashlib.sha256(_canonical(world_terrain).encode()).hexdigest()


def is_executed(root_data):
    return bool((root_data or {}).get("genesis", {}).get("status") == "completed")


def execute(world, plan, issued_by="genesis_default"):
    """Build the physical world from the plan. Runs once; never during restore, recovery or replay.

    Consumes ``world.rng`` in exactly the order of the original constructor. Records the plan, generator versions,
    creation events and a world summary in the private root state; the events (source ``genesis``) carry only
    physical counts.
    """
    from .engine import Agent
    from .lifecycle import roles_for
    from .nature import RESOURCE_TYPES, geography
    plan.validate()
    if is_executed(world.root.data):
        raise GenesisError("genesis has already run for this world")
    if (plan.seed, plan.width, plan.depth) != (world.seed, world.width, world.depth) or world.agents or world.resources:
        raise GenesisError("plan does not match the empty world being created")
    width, depth, seed, rng = plan.width, plan.depth, plan.seed, world.rng
    world.emit("genesis_plan_issued", None, {"version": plan.version, "plan_digest": plan.digest(),
                                             "issuer": "root_role" if issued_by != "genesis_default" else "default",
                                             "generators": dict(plan.generators)}, "genesis")   # role names stay in private root state
    # 1. terrain (a pure function of the seed; the stored list is a coarse index of it)
    world.terrain = [dict(x=x, z=z, size=min(8, width - x, depth - z), **geography(x + 4, z + 4, width, depth, seed))
                     for x in range(0, width, 8) for z in range(0, depth, 8)]
    biome_tiles = {}
    for tile in world.terrain:
        biome_tiles[tile["biome"]] = biome_tiles.get(tile["biome"], 0) + 1
    t_digest = terrain_digest(world.terrain)
    world.emit("genesis_terrain_generated", None, {"generator": dict(plan.generators)["terrain"], "tiles": len(world.terrain),
                                                   "biome_tiles": dict(sorted(biome_tiles.items())), "terrain_digest": t_digest}, "genesis")
    # 2. resources
    table = dict(plan.biome_resources)
    for i in range(plan.resource_count):
        x, z = rng.randrange(width), rng.randrange(3, depth)
        tile = geography(x, z, width, depth, seed)
        if not tile["walkable"]:
            continue
        kind = rng.choice(list(table[tile["biome"]]))
        renewable, capacity = RESOURCE_TYPES[kind]
        world.resources[f"resource-{i:04}"] = dict(id=f"resource-{i:04}", x=x, z=z, kind=kind, amount=capacity,
                                                   capacity=capacity, renewable=renewable)
    by_kind = {}
    for node in world.resources.values():
        by_kind[node["kind"]] = by_kind.get(node["kind"], 0) + 1
    world.emit("genesis_resources_placed", None, {"generator": dict(plan.generators)["resources"], "nodes": len(world.resources),
                                                  "by_kind": dict(sorted(by_kind.items()))}, "genesis")
    # 3. founders and their starting supplies (initial nearby resources are ecology, not agent-authored events)
    cx, cz = width // 4, depth // 2
    r = plan.spawn_radius
    spawn_points = [(x, z) for x in range(max(0, cx - r), min(width, cx + r + 1))
                    for z in range(max(3, cz - r), min(depth, cz + r + 1)) if geography(x, z, width, depth, seed)["walkable"]]
    if not spawn_points:
        raise ValueError("Starting area has no walkable terrain")
    if plan.families:
        _found_families(world, plan, spawn_points)
    else:
        for i in range(plan.population):
            x, z = rng.choice(spawn_points)
            aid = f"agent-{i:04}"
            agent = Agent(aid, x, z, gender=plan.genders[i % len(plan.genders)],
                          biological_sex=rng.choices(["female", "male", "intersex"], list(plan.sex_weights))[0],
                          age_years_at_start=rng.randrange(*plan.age_range), height_cm=rng.randrange(*plan.height_range_cm),
                          skin_tone=rng.choice(list(plan.skin_tones)), clothing_color=rng.choice(list(plan.clothing_colors)))
            world.agents[aid] = agent
            agent.inventory.update({k: 0 for k in RESOURCE_TYPES if k not in agent.inventory})
            agent.inventory["water"] = plan.founder_water
            agent.adult_height_cm = agent.height_cm
            agent.reproductive_roles = roles_for(agent.biological_sex)
            agent.lifespan_years = rng.randint(*plan.lifespan_range)
            rid = f"spawn-food-{i}"
            world.resources[rid] = dict(id=rid, x=x, z=z, kind="food", amount=plan.spawn_food_units, capacity=plan.spawn_food_units)
            rid = f"spawn-water-{i}"
            world.resources[rid] = dict(id=rid, x=x, z=z, kind="water", amount=plan.spawn_water_units,
                                        capacity=plan.spawn_water_units, renewable=True)
    world.emit("genesis_founders_created", None, {"generator": dict(plan.generators)["founders"], "founders": plan.population,
               **({"families": plan.families, "children": plan.families * plan.children_per_family} if plan.families else {})}, "genesis")
    # 4. wildlife (own RNG seeded from the world seed; independent of the world RNG)
    animals = 0
    if plan.wildlife_per_species:
        from fauna.ecology import Ecosystem
        world.fauna = Ecosystem(world, seed=seed + 2718, per_species=plan.wildlife_per_species, days_per_tick=plan.days_per_tick)
        world.manifest["wildlife"] = {"version": 1, "initial_per_species": plan.wildlife_per_species, "days_per_tick": plan.days_per_tick}
        animals = len(world.fauna.animals)
        world.emit("genesis_wildlife_placed", None, {"generator": dict(plan.generators)["wildlife"], "animals": animals}, "genesis")
    summary = {"terrain_digest": t_digest, "biome_tiles": dict(sorted(biome_tiles.items())), "resource_nodes": len(world.resources),
               "resources_by_kind": dict(sorted(by_kind.items())), "founders": plan.population, "animals": animals}
    world.root.data["genesis"] = {"status": "completed", "version": plan.version, "plan": plan.to_dict(),
                                  "plan_digest": plan.digest(), "issued_by": issued_by, "generators": dict(plan.generators),
                                  "completed_tick": 0, "summary": summary}
    world.emit("genesis_completed", None, {"plan_digest": plan.digest(), "summary": summary}, "genesis")
    return summary


def _found_families(world, plan, spawn_points):
    """Founders-v2: each household is one woman, one man and children, living together; deterministic from the world RNG.

    Children carry real family links (parents, guardians, generation 1) so the existing caregiving, growth and family-tree rules apply;
    infants (under 3) cannot act and depend on their guardians, exactly like children born in the world."""
    from .engine import Agent
    from .lifecycle import roles_for
    from .nature import RESOURCE_TYPES
    rng = world.rng
    n = 0

    def supplies(agent, i, x, z):
        world.agents[agent.id] = agent
        agent.inventory.update({k: 0 for k in RESOURCE_TYPES if k not in agent.inventory})
        agent.inventory["water"] = plan.founder_water
        rid = f"spawn-food-{i}"
        world.resources[rid] = dict(id=rid, x=x, z=z, kind="food", amount=plan.spawn_food_units, capacity=plan.spawn_food_units)
        rid = f"spawn-water-{i}"
        world.resources[rid] = dict(id=rid, x=x, z=z, kind="water", amount=plan.spawn_water_units, capacity=plan.spawn_water_units, renewable=True)

    for _ in range(plan.families):
        x, z = rng.choice(spawn_points)
        parents = []
        for sex, gender in (("female", "woman"), ("male", "man")):
            aid = f"agent-{n:04}"
            a = Agent(aid, x, z, gender=gender, biological_sex=sex, age_years_at_start=rng.randrange(*plan.parent_age_range),
                      height_cm=rng.randrange(*plan.height_range_cm), skin_tone=rng.choice(list(plan.skin_tones)),
                      clothing_color=rng.choice(list(plan.clothing_colors)))
            a.adult_height_cm = a.height_cm
            a.reproductive_roles = roles_for(sex)
            a.lifespan_years = rng.randint(*plan.lifespan_range)
            supplies(a, n, x, z)
            parents.append(a)
            n += 1
        for _c in range(plan.children_per_family):
            aid = f"agent-{n:04}"
            years = rng.randrange(*plan.child_age_range)
            sex = rng.choices(["female", "male", "intersex"], list(plan.sex_weights))[0]
            adult = max(140, min(205, round(sum(p.adult_height_cm for p in parents) / 2) + rng.randint(-7, 7)))
            a = Agent(aid, x, z, gender="unspecified", biological_sex=sex, age_years_at_start=years,
                      height_cm=round(50 + (adult - 50) * min(1, years / 18) ** .5), adult_height_cm=adult,
                      skin_tone=rng.choice(parents).skin_tone, clothing_color=rng.choice(list(plan.clothing_colors)),
                      parent_ids=[p.id for p in parents], guardian_ids=[p.id for p in parents], generation=1, adulthood_recorded=False)
            a.reproductive_roles = roles_for(sex)
            a.lifespan_years = rng.randint(*plan.lifespan_range)
            supplies(a, n, x, z)
            if years < 3:                       # infants cannot act or carry: they depend on their guardians
                a.inventory.update({k: 0 for k in a.inventory})
            n += 1


def verify_recorded(world):
    """On restore: a world created by genesis must still derive the same terrain from the same code."""
    record = world.root.data.get("genesis")
    if not record or record.get("status") != "completed":
        return
    if record["summary"]["terrain_digest"] != terrain_digest(world.terrain):
        raise GenesisError("terrain generator no longer matches the one recorded at genesis "
                           f"({dict(record['generators']).get('terrain')}); refusing to load a changed world")
