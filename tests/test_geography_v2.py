"""geography-v2: two river valleys. Frozen output, believable shape, reachable land, opt-in, and nothing about v1 changes."""
import hashlib
import json
import time
from collections import Counter, deque
from pathlib import Path
import pytest
from caitanya import nature, valley
from caitanya.engine import World, MockInferenceBackend, digest
from caitanya.genesis import GenesisError, default_plan, GENERATOR_VERSIONS
from caitanya.server import build_parser
from caitanya.witness import BIOMES, terrain_grid
from conftest import IdleBackend

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((ROOT / "tests" / "fixtures" / "geography_v2_golden.json").read_text(encoding="utf-8"))
SEEDS = (314159, 1, 2, 3, 7, 99)


def shares(seed, n=256):
    m = valley.build(n, n, seed)
    c = Counter(valley.NAMES[b] for b in m.biome)
    return {k: v / (n * n) for k, v in c.items()}


def reachable_fraction(seed, n=256):
    m = valley.build(n, n, seed)
    land = [i for i in range(n * n) if m.walk[i]]
    cx, cz = valley.founding_site(n, n, seed, 8)
    start = cz * n + cx
    assert m.walk[start]
    seen, queue = {start}, deque([start])
    while queue:
        i = queue.popleft()
        x, z = i % n, i // n
        for a, b in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if 0 <= a < n and 0 <= b < n and m.walk[b * n + a] and b * n + a not in seen:
                seen.add(b * n + a)
                queue.append(b * n + a)
    return len(seen) / len(land)


def test_geography_v2_output_is_frozen_for_a_seed_and_independent_of_the_cache():
    for key, want in GOLDEN.items():
        seed, size = key.split(":")
        width, depth = (int(v) for v in size.split("x"))
        for attempt in range(2):
            valley.build.cache_clear()          # a second build from scratch must give the same land
            h = hashlib.sha256()
            for x in range(0, width, 2):
                for z in range(0, depth, 2):
                    h.update(json.dumps(nature.geography(x, z, width, depth, int(seed), "geography-v2"), sort_keys=True).encode())
            assert h.hexdigest() == want, (key, attempt)


def test_different_seeds_give_different_maps():
    a = [valley.build(128, 128, s).biome for s in (1, 2, 3)]
    assert len({bytes(x) for x in a}) == 3


def test_the_land_has_the_shape_of_two_river_valleys():
    for seed in SEEDS:
        s = shares(seed)
        assert 0.03 <= s["water"] <= 0.09, (seed, s)
        assert s["floodplain"] >= 0.08 and s["wetland"] >= 0.03, (seed, s)
        assert s["dryland"] >= 0.08 and s["forest"] >= 0.08 and s["grassland"] >= 0.12 and s["highland"] >= 0.03, (seed, s)
    m = valley.build(256, 256, 314159)
    top = Counter(m.biome[z * 256 + x] for z in range(236, 256) for x in range(256))
    bottom_sea = Counter(m.biome[z * 256 + x] for z in range(0, 2) for x in range(256))
    assert top[valley.HIGH] > 0.3 * 20 * 256, "highlands upstream (high z)"
    assert bottom_sea[valley.WATER] > 0.9 * 2 * 256, "the sea lies along the low-z edge"


def test_rivers_are_not_walls_all_land_is_reachable_from_the_founders_area():
    for seed in SEEDS:
        assert reachable_fraction(seed) >= 0.99, seed


def test_rivers_do_divide_the_land_water_is_not_walkable_and_fords_are():
    m = valley.build(256, 256, 314159)
    water = [i for i in range(256 * 256) if m.biome[i] == valley.WATER]
    assert water and not any(m.walk[i] for i in water)
    fords = [i for i in range(256 * 256) if m.biome[i] == valley.WETLAND and m.walk[i] and any(
        0 <= i + d < 256 * 256 and m.biome[i + d] == valley.WATER for d in (1, -1, 256, -256))]
    assert len(fords) >= 20, "shallow crossings exist"
    assert len(water) > 5 * len(fords) / 10


def bfs_distance(m, n, start, goal, limit):
    seen, queue = {start: 0}, deque([start])
    while queue:
        i = queue.popleft()
        if i == goal:
            return seen[i]
        if seen[i] >= limit:
            continue
        x, z = i % n, i // n
        for a, b in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            j = b * n + a
            if 0 <= a < n and 0 <= b < n and m.walk[j] and j not in seen:
                seen[j] = seen[i] + 1
                queue.append(j)
    return None


def test_the_trunk_river_blocks_a_straight_walk_but_can_be_crossed_at_a_ford_nearby():
    """Without fords the only way round is the long way past the headwaters, hundreds of tiles; with them it is a short detour."""
    n = 256
    for seed in SEEDS:
        m = valley.build(n, n, seed)
        row = 30
        water = [x for x in range(n) if m.biome[row * n + x] == valley.WATER]
        assert water, seed
        left, right = min(water) - 3, max(water) + 3
        assert all(m.walk[row * n + x] for x in (left, right)), seed
        assert not all(m.walk[row * n + x] for x in range(left, right + 1)), "a straight walk is blocked by water"
        d = bfs_distance(m, n, row * n + left, row * n + right, 150)
        assert d is not None and d <= 150, (seed, d)


def test_the_map_builds_quickly_and_outside_the_map_is_never_land():
    t = time.time()
    valley.build(256, 256, 424242)
    assert time.time() - t < 3.0
    assert nature.geography(-1, 5, 256, 256, 1, "geography-v2")["walkable"] is False
    assert nature.geography(256, 5, 256, 256, 1, "geography-v2")["walkable"] is False


def test_v2_is_opt_in_the_default_plan_still_names_v1_and_an_unknown_map_is_refused():
    assert dict(default_plan(5, 3).generators)["terrain"] == "geography-v1" == GENERATOR_VERSIONS["terrain"]
    assert dict(default_plan(5, 3, terrain="geography-v2").generators)["terrain"] == "geography-v2"
    assert "floodplain" in dict(default_plan(5, 3, terrain="geography-v2").biome_resources)
    assert "floodplain" not in dict(default_plan(5, 3).biome_resources)
    with pytest.raises(GenesisError):
        default_plan(5, 3, terrain="geography-v3")
    assert build_parser().parse_args([]).terrain == "geography-v1"
    assert build_parser().parse_args(["--terrain", "geography-v2"]).terrain == "geography-v2"


def test_a_v2_world_starts_its_founders_on_the_floodplain_and_places_resources_on_land():
    w = World(seed=5, width=256, depth=256, families=5, wildlife_per_species=2, terrain="geography-v2", backend=IdleBackend())
    assert w.geography_version == "geography-v2" and w.manifest["genesis"]["generators"]["terrain"] == "geography-v2"
    cx, cz = nature.founding_site(256, 256, 5, "geography-v2", 8)
    assert w.terrain_at(cx, cz)["biome"] == "floodplain"
    for a in w.agents.values():
        assert w.terrain_at(a.x, a.z)["walkable"] and abs(a.x - cx) <= 8 and abs(a.z - cz) <= 8
    table = dict(default_plan(5, 20, width=256, depth=256, families=5, terrain="geography-v2").biome_resources)
    for node in w.resources.values():
        tile = w.terrain_at(node["x"], node["z"])
        assert tile["walkable"]
        if not node["id"].startswith("spawn-"):         # the founders' starter food and water are placed beside them by design
            assert node["kind"] in table[tile["biome"]]
    assert any(w.terrain_at(n["x"], n["z"])["biome"] == "floodplain" for n in w.resources.values())
    animals = w.fauna.public()["animals"]
    assert animals and all(w.terrain_at(int(b["x"]), int(b["z"]))["walkable"] or w.terrain_at(int(b["x"]), int(b["z"]))["biome"] == "water" for b in animals)
    assert any(w.terrain_at(int(b["x"]), int(b["z"]))["biome"] == "floodplain" for b in animals), "animals live on the floodplain too"


def test_a_v2_world_is_deterministic_and_survives_checkpoint_and_restore(tmp_path):
    def run():
        w = World(seed=9, width=128, depth=128, families=3, terrain="geography-v2", backend=MockInferenceBackend(use_tasks=True))
        for _ in range(12):
            w.step()
        return w
    a, b = run(), run()
    assert digest(a.state()) == digest(b.state())
    restored = World.restore(a.checkpoint(tmp_path), backend=a.backend)
    assert restored.geography_version == "geography-v2" and digest(restored.state()) == digest(a.state())
    assert restored.terrain_at(40, 40) == a.terrain_at(40, 40)


def test_a_default_world_is_unchanged_by_the_existence_of_v2():
    w = World(seed=5, width=128, depth=128, population=4, backend=IdleBackend())
    assert w.geography_version == "geography-v1" and "floodplain" not in {t["biome"] for t in w.terrain}


def test_the_terrain_api_lists_the_new_biome_last_so_old_indices_never_move():
    assert BIOMES[:6] == ["water", "wetland", "grassland", "forest", "dryland", "highland"] and BIOMES[6] == "floodplain"
    w = World(seed=5, width=128, depth=128, families=2, terrain="geography-v2", backend=IdleBackend())
    grid = terrain_grid(w, 4)
    assert BIOMES.index("floodplain") in set(grid["biome"])
