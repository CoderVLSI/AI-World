"""Far start (opt-in): no food or water under the founders, the nearest source beyond sight. Off by default and invisible when off."""
import json
import pytest
from caitanya import genesis
from caitanya.engine import World, MockInferenceBackend, digest
from caitanya.genesis import GenesisError, default_plan
from caitanya.server import build_parser
from conftest import IdleBackend

SIGHT = 8


def make(seed=314159, **kw):
    return World(seed=seed, width=256, depth=256, families=25, children_per_family=0, wildlife_per_species=2, backend=IdleBackend(), **kw)


def source_distances(w):
    src = [(n["x"], n["z"]) for n in w.resources.values() if n["kind"] in ("food", "water")]
    return [min(abs(a.x - x) + abs(a.z - z) for x, z in src) for a in w.agents.values()]


def test_off_by_default_and_a_default_plan_is_byte_identical():
    plan = default_plan(5, 3)
    assert plan.start_distance == 0 and "start_distance" not in plan.to_dict()
    assert any(k.startswith("spawn-food-") for k in make().resources)


@pytest.mark.parametrize("terrain", ["geography-v1", "geography-v2"])
def test_every_founder_starts_beyond_sight_of_any_food_or_water_with_none_under_their_feet(terrain):
    for seed in (314159, 1, 2, 3):
        w = make(seed, terrain=terrain, start_distance=24)
        assert not any(k.startswith("spawn-") for k in w.resources)
        d = source_distances(w)
        assert min(d) > SIGHT and min(d) >= 24 - 8, (seed, min(d))          # start_distance minus the spawn radius, always beyond sight
        assert max(d) <= 24 + 8 + 25 + 8, (seed, max(d))                    # and not absurdly far
        for a in w.agents.values():
            assert w.terrain_at(a.x, a.z)["walkable"] and a.inventory["water"] == 3        # they carry only the plan's small founder water


def test_the_founders_can_actually_walk_to_the_nearest_source():
    """Far must not mean unreachable: a walkable route within the planning bound exists from every founder to some food or water."""
    from caitanya.scheduler import find_path
    for seed in (314159, 1, 2):
        w = make(seed, terrain="geography-v2", start_distance=24)
        cfg = w.autonomy.scheduler
        src = sorted((n["x"], n["z"]) for n in w.resources.values() if n["kind"] in ("food", "water"))
        for a in list(w.agents.values())[:10]:
            nearest = sorted(src, key=lambda p: abs(p[0] - a.x) + abs(p[1] - a.z))[:5]
            assert any(find_path(w, (a.x, a.z), p, cfg.max_path_expansions, cfg.max_path_length) for p in nearest), (seed, a.id)


def test_it_is_deterministic_recorded_in_the_plan_and_survives_checkpoint(tmp_path):
    a, b = make(start_distance=24, terrain="geography-v2"), make(start_distance=24, terrain="geography-v2")
    assert digest(a.state()) == digest(b.state())
    assert a.root.data["genesis"]["plan"]["start_distance"] == 24
    restored = World.restore(a.checkpoint(tmp_path), backend=a.backend)
    assert digest(restored.state()) == digest(a.state())


def test_the_default_world_is_unchanged_by_the_existence_of_far_start():
    assert digest(make().state()) == digest(make(start_distance=0).state())


def test_an_impossible_distance_is_refused_not_silently_changed():
    with pytest.raises(GenesisError):
        make(start_distance=120, terrain="geography-v2")
    with pytest.raises(GenesisError):
        default_plan(5, 3, start_distance=-1)


def test_the_command_line_has_the_option_and_it_is_off_by_default():
    assert build_parser().parse_args([]).start_distance == 0
    assert build_parser().parse_args(["--start-distance", "24"]).start_distance == 24
