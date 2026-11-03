"""Genesis: a deterministic, immutable, versioned plan executed exactly once per new world."""
import dataclasses
import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from caitanya import genesis, isvara
from caitanya.engine import World, digest
from caitanya.genesis import GenesisError, GenesisPlan, default_plan
from caitanya.server import create_app

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "genesis_golden.json").read_text())


def physical(w):
    s = w.state()
    return digest(dict(resources=s["resources"], agents=s["agents"], rng=s["rng_state"], terrain=w.terrain, fauna=s.get("fauna"), objects=s["objects"]))


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: json.dumps(c["kwargs"], sort_keys=True))
def test_same_seed_builds_the_same_world_as_before_genesis_existed(case):
    """Golden digests were recorded from the constructor that preceded genesis (see the fixture's origin in the PR)."""
    w = World(**case["kwargs"])
    assert physical(w) == case["initial"]
    assert w.rng.random() == case["next_random"]          # the RNG stream is left in exactly the same state
    w = World(**case["kwargs"])
    for _ in range(30):
        w.step()
    assert physical(w) == case["after_30_ticks"]


def test_creation_is_recorded_as_events_summary_and_manifest():
    w = World(seed=3, population=4, wildlife_per_species=2)
    assert [e["type"] for e in w.events[:6]] == ["genesis_plan_issued", "genesis_terrain_generated", "genesis_resources_placed",
                                                 "genesis_founders_created", "genesis_wildlife_placed", "genesis_completed"]
    assert all(e["source"] == "genesis" and e["world_tick"] == 0 for e in w.events[:6])
    record = w.root.data["genesis"]
    assert record["status"] == "completed" and record["issued_by"] == "isvara" and record["plan_digest"] == w.manifest["genesis"]["plan_digest"]
    assert record["summary"]["founders"] == 4 and record["summary"]["animals"] == len(w.fauna.animals) > 0
    assert record["generators"] == dict(genesis.GENERATOR_VERSIONS) == w.manifest["genesis"]["generators"]
    assert GenesisPlan.from_dict(record["plan"]).digest() == record["plan_digest"]
    # nothing in the creation record names a model, a belief or a recipe
    text = json.dumps([e["payload"] for e in w.events[:6]]).lower()
    assert not any(word in text for word in ("brahman", "isvara", "god", "temple", "religion"))


def test_plan_is_immutable_and_validated():
    plan = default_plan(seed=1, population=3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.seed = 2
    assert isinstance(plan.biome_resources, tuple) and all(isinstance(kinds, tuple) for _, kinds in plan.biome_resources)
    assert plan.digest() == GenesisPlan.from_dict(plan.to_dict()).digest() and plan.digest() != default_plan(seed=2, population=3).digest()
    bad = [dict(generators=(("terrain", "geography-v9"), ("resources", "scatter-v1"), ("founders", "founders-v1"), ("wildlife", "ecology-v1"))),
           dict(generators=(("terrain", "geography-v1"),)), dict(version="genesis-v2"), dict(population=0),
           dict(biome_resources=(("forest", ("wood",)),)), dict(biome_resources=tuple((b, ("unobtainium",)) for b, _ in plan.biome_resources)),
           dict(sex_weights=(0, 0, 0)), dict(wildlife_per_species=3, days_per_tick=2), dict(width=4)]
    for override in bad:
        with pytest.raises(GenesisError):
            dataclasses.replace(plan, **override).validate()
    with pytest.raises(GenesisError):
        GenesisPlan.from_dict({**plan.to_dict(), "invented_law": 1})


def test_genesis_runs_exactly_once_and_never_during_restore_recovery_or_replay(tmp_path, monkeypatch):
    w = World(seed=5, population=4)
    with pytest.raises(GenesisError):                                   # a built world cannot be built again
        genesis.execute(w, default_plan(seed=5, population=4))
    for _ in range(12):
        w.step()
    path = w.checkpoint(tmp_path)
    calls = []
    monkeypatch.setattr(genesis, "execute", lambda *a, **k: calls.append(1))
    restored = World.restore(path, backend=w.backend)
    restored.step()
    assert restored.replay(restored.tick)["tick"] == restored.tick and restored.replay(3)["tick"] == 3
    assert calls == []
    assert restored.root.data["genesis"] == w.root.data["genesis"]      # the record is carried, not recomputed
    assert restored.events[:6] == w.events[:6]


def test_recovery_through_the_server_journal_does_not_rerun_genesis(tmp_path, monkeypatch):
    w = World(seed=6, population=4)
    app = create_app(w, tmp_path, interval=0, max_ticks=15, checkpoint_every=5)
    with TestClient(app) as client:
        deadline = time.time() + 60
        while time.time() < deadline:
            e = client.get("/api/v1/health").json()["execution"]
            if not e["running"] and e["reason"] not in (None, "not_started"):
                break
            time.sleep(0.05)
    monkeypatch.setattr(genesis, "execute", lambda *a, **k: (_ for _ in ()).throw(AssertionError("genesis re-ran")))
    r = World.recover(tmp_path, backend=w.backend)
    assert digest(r.state()) == digest(w.state()) and r.events == w.events


def test_a_stored_world_is_refused_if_the_terrain_generator_changed(tmp_path, monkeypatch):
    w = World(seed=7, population=3)
    path = w.checkpoint(tmp_path)
    from caitanya import engine
    original = engine.geography
    monkeypatch.setattr(engine, "geography", lambda *a, **k: {**original(*a, **k), "elevation": 99})
    with pytest.raises(GenesisError, match="terrain generator no longer matches"):
        World.restore(path, backend=w.backend)


def test_genesis_does_not_depend_on_the_root_mode_or_on_reasoning():
    worlds = {m: World(seed=9, population=5, root_mode=m) for m in ("off", "observe", "crisis")}
    assert len({physical(w) for w in worlds.values()}) == 1
    assert len({w.root.data["genesis"]["plan_digest"] for w in worlds.values()}) == 1
    assert worlds["off"].root.data["genesis"]["issued_by"] == "genesis_default" and "isvara" not in worlds["off"].root.data
    assert worlds["observe"].root.data["genesis"]["issued_by"] == "isvara" and "isvara" in worlds["observe"].root.data
    legacy = World(seed=9, population=5, autonomy="legacy")
    assert legacy.root.data["genesis"]["status"] == "completed" and "isvara" not in legacy.root.data and physical(legacy) == physical(worlds["crisis"])


def test_schema_1_runs_without_a_genesis_record_still_load(tmp_path):
    """Worlds created before genesis existed carry no record; they load as before and never gain one."""
    from caitanya.engine import SCHEMA_VERSION
    w = World(seed=2, population=3, autonomy="legacy")
    state = w.state()
    state["root"].pop("genesis")
    state["schema_version"] = SCHEMA_VERSION
    old = World.__new__(World)
    old.backend = w.backend
    old.load_state(state)                                   # no verification possible, none attempted
    assert "genesis" not in old.root.data and not isvara.active(old)
    assert isvara.public_summary(old)["genesis"] is None
