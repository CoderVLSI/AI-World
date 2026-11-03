import copy
import json

import pytest

from caitanya.engine import World, digest, FOUNDATION
from caitanya.forces import FORCES, NatureForces
from caitanya.lifecycle import BiologyConfig


def world(**kwargs):
    return World(population=2, root_mode=kwargs.pop("root_mode", "off"), nature_forces=True, **kwargs)


def test_exact_fourteen_and_default_unchanged():
    assert set(FORCES) == {"agni", "vayu", "indra", "varuna", "mitra", "yama", "surya",
                           "soma", "prithvi", "parjanya", "rudra", "apas", "ushas", "bhumi"}
    a, b = World(), World(nature_forces=False)
    for _ in range(8):
        a.step(); b.step()
    assert a.state() == b.state()
    assert "nature_forces" not in a.state()
    assert not any(e["type"] == "nature_force" for e in a.events)
    assert World(nature_forces=True).manifest["configuration_hash"] != World().manifest["configuration_hash"]


@pytest.mark.parametrize("key", FORCES)
def test_each_force_has_bounded_confirmed_outcome_and_neutral_observation(key):
    w = world()
    a = w.agents["agent-0000"]
    a.thirst, a.energy, a.health = 50, 50, 50
    w.resources = {kind: dict(id=kind, kind=kind, amount=10, capacity=20, x=a.x, z=a.z)
                   for kind in ("water", "wood", "plant_fiber", "grain", "herbs", "food", "fruit", "fish")}
    rng_before = w.rng.getstate()
    w.nature_forces.apply(w, key, a.x, a.z, 3)
    e = w.events[-1]
    assert e["source"] == "environment_rule" and e["payload"]["outcomes"]
    assert e["payload"]["force"] == key
    assert 1 <= a.health <= 100 and 0 <= a.energy <= 100 and 0 <= a.thirst <= 100
    assert all(0 <= n["amount"] <= n["capacity"] for n in w.resources.values())
    obs = w.observe(a.id)["environment_effects"]
    assert len(obs) == 1 and "force" not in obs[0]
    assert "outcomes" not in obs[0] and "nature_forces" not in w.public()
    assert all(f.name not in json.dumps(obs) for f in FORCES.values())
    assert w.rng.getstate() == rng_before
    assert "Agni" not in FOUNDATION  # no belief or deity in the model instructions


def test_locality_capacity_dead_agents_and_no_revival():
    w = world(width=64, depth=64)
    a, b = w.agents.values()
    a.x = a.z = 0; b.x = b.z = 63
    b_before = copy.deepcopy(vars(b))
    a.health = 0
    w.nature_forces.apply(w, "indra", 0, 0, 3)
    assert a.health == 0 and vars(b) == b_before
    a.alive = False; a.thirst = 50
    w.nature_forces.apply(w, "surya", 0, 0, 3)
    assert a.thirst == 50
    assert not w.nature_forces.observe(w, b)


@pytest.mark.parametrize("root_mode", ["off", "observe", "crisis"])
def test_replay_checkpoint_and_future_schedule_match(tmp_path, root_mode):
    kwargs = dict(biology=BiologyConfig(days_per_tick=1), autonomy="legacy")
    a, b = world(root_mode=root_mode, **kwargs), world(root_mode=root_mode, **kwargs)
    for _ in range(12):
        a.step(); b.step()
    assert a.nature_forces.data["counts"]  # exercise actual seeded automatic pulses
    assert a.state() == b.state()
    assert digest(a.replay(a.tick)) == digest(a.state())
    restored = World.restore(a.checkpoint(tmp_path))
    assert restored.state() == a.state()
    for _ in range(10):
        a.step(); restored.step()
    assert a.state() == restored.state()
    assert a.events == restored.events
    assert digest(a.replay(a.tick)) == digest(a.state())


def test_old_checkpoint_stays_off(tmp_path):
    w = World()
    assert World.restore(w.checkpoint(tmp_path)).nature_forces is None


def test_validation_duplicate_tick_and_recent_expiry():
    w = world()
    for args in [("unknown", 0, 0, 1), ("agni", -1, 0, 1), ("agni", 0, 0, 9)]:
        with pytest.raises(ValueError):
            w.nature_forces.apply(w, *args)
    with pytest.raises(ValueError):
        NatureForces({"version": "future"})
    a = next(iter(w.agents.values()))
    w.nature_forces.apply(w, "agni", a.x, a.z)
    w.tick = 7
    assert not w.nature_forces.observe(w, a)
    w.nature_forces.advance(w)
    with pytest.raises(ValueError):
        w.nature_forces.advance(w)


def test_cli_opt_in():
    from caitanya.server import build_parser, build_world
    p = build_parser()
    args = p.parse_args(["--nature-forces", "--wildlife-per-species", "0"])
    assert build_world(args, p).nature_forces is not None


def test_witness_exposes_only_neutral_effects_and_stays_read_only(tmp_path):
    from fastapi.testclient import TestClient
    from caitanya.server import create_app
    w = world()
    a = next(iter(w.agents.values()))
    w.nature_forces.apply(w, "agni", a.x, a.z)
    with TestClient(create_app(w, run_dir=tmp_path, live=False)) as client:
        result = client.get("/api/v1/live")
        assert result.status_code == 200
        effects = result.json()["environment_effects"]
        assert effects[0]["phenomenon"] == "wildfire"
        assert "force" not in effects[0] and "outcomes" not in effects[0]
        assert client.post("/api/v1/live", json={"force": "agni"}).status_code == 405


@pytest.mark.parametrize("hour,expected", [(1, {"soma"}), (6, {"ushas"}), (12, {"surya"})])
def test_time_gated_forces_respect_world_clock(monkeypatch, hour, expected):
    from dataclasses import replace
    # Guarantee occurrence conditional on its window; this does not tune live rules.
    for key in ("soma", "surya", "ushas"):
        monkeypatch.setitem(FORCES, key, replace(FORCES[key], daily_rate=1e9))
    w = world(biology=BiologyConfig(days_per_tick=1/24), autonomy="legacy")
    w.tick = hour
    w.nature_forces.advance(w)
    assert set(w.nature_forces.data["counts"]) & {"soma", "surya", "ushas"} == expected
