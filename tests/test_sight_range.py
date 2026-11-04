"""sight_range (opt-in): how far an inhabitant sees resource nodes. Default 8 and invisible when off; a fact about the world, never advice."""
import pytest
from caitanya import inference as inf
from caitanya.engine import World, MockInferenceBackend, digest
from caitanya.server import build_parser
from conftest import IdleBackend


def far_world(sight):
    return World(seed=314159, width=256, depth=256, families=25, children_per_family=0, backend=IdleBackend(), terrain="geography-v2",
                 start_distance=24, sight_range=sight)


def sources_seen(w):
    return [sum(1 for n in w.observe(aid)["resources"] if n["kind"] in ("food", "water") and n["amount"] > 0) for aid in w.agents]


def test_default_sight_is_eight_tiles_and_the_default_world_is_unchanged():
    a = World(seed=5, population=6, width=64, depth=64, backend=IdleBackend())
    b = World(seed=5, population=6, width=64, depth=64, backend=IdleBackend(), sight_range=8)
    assert a.sight_range == 8 and digest(a.state()) == digest(b.state()) and "sight_range" not in a.manifest
    for aid in a.agents:
        me = a.agents[aid]
        assert all(abs(n["x"] - me.x) + abs(n["z"] - me.z) <= 8 for n in a.observe(aid)["resources"])


def test_a_longer_sight_shows_resource_nodes_that_far_away_and_only_those():
    w = far_world(32)
    me = next(iter(w.agents.values()))
    seen = w.observe(me.id)["resources"]
    assert seen and all(abs(n["x"] - me.x) + abs(n["z"] - me.z) <= 32 for n in seen)
    outside = [n for n in w.resources.values() if 8 < abs(n["x"] - me.x) + abs(n["z"] - me.z) <= 32]
    assert outside and {n["id"] for n in outside} <= {n["id"] for n in seen}
    assert not any(abs(n["x"] - me.x) + abs(n["z"] - me.z) > 32 for n in seen)


def test_the_far_start_founders_see_no_food_or_water_at_default_sight_but_nearly_all_do_with_a_longer_one():
    assert sum(1 for c in sources_seen(far_world(8)) if c) == 0
    assert sum(1 for c in sources_seen(far_world(32)) if c) >= 40


def test_what_the_model_is_shown_stays_bounded_nearest_first_and_offers_gathering_only_when_something_is_there():
    w = far_world(32)
    aid = next(a for a, c in zip(w.agents, sources_seen(w)) if c)
    o = w.observe(aid)
    me = o["self"]
    shown = inf.visible_resources(o["resources"], me)
    assert len(shown) <= 16 and shown == sorted(shown, key=lambda n: abs(n["x"] - me["x"]) + abs(n["z"] - me["z"]))
    assert "GATHER_AT" in [t["function"]["name"] for t in inf.select_tools(o)]


def test_it_survives_checkpoint_and_restore_and_other_worlds_stay_at_eight(tmp_path):
    w = far_world(32)
    restored = World.restore(w.checkpoint(tmp_path), backend=w.backend)
    assert restored.sight_range == 32 and digest(restored.state()) == digest(w.state())
    assert restored.observe(next(iter(restored.agents)))["resources"] == w.observe(next(iter(w.agents)))["resources"]
    plain = World(seed=5, population=3, width=64, depth=64, backend=IdleBackend())
    assert World.restore(plain.checkpoint(tmp_path / "p"), backend=plain.backend).sight_range == 8


def test_bad_values_are_refused_and_the_command_line_has_the_option():
    for bad in (7, 65, 0, -3, 8.0, "9"):
        with pytest.raises(ValueError):
            World(seed=5, population=3, width=64, depth=64, backend=IdleBackend(), sight_range=bad)
    assert build_parser().parse_args([]).sight_range == 8 and build_parser().parse_args(["--sight-range", "32"]).sight_range == 32


def test_a_mock_policy_walks_to_far_seen_sources_and_survives_a_thirsty_start():
    w = World(seed=314159, width=256, depth=256, families=25, children_per_family=0, backend=MockInferenceBackend(use_tasks=True),
              terrain="geography-v2", start_distance=24, founder_water=0, sight_range=32)
    start = {a.id: (a.x, a.z) for a in w.agents.values()}
    for _ in range(60):
        w.step()
    moved = sum(1 for a in w.agents.values() if abs(a.x - start[a.id][0]) + abs(a.z - start[a.id][1]) >= 8)
    assert moved >= 25 and all(a.alive for a in w.agents.values())
