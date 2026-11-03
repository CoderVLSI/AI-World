"""Founding families: women, men and children from the first tick (opt-in); the default world is unchanged."""
import json
import pytest
from conftest import IdleBackend
from caitanya import genesis
from caitanya.engine import World, digest
from caitanya.genesis import GenesisError, GenesisPlan, default_plan
from caitanya.lifecycle import age, stage
from caitanya.server import build_parser, build_world


def fam(**kw):
    kw.setdefault("backend", IdleBackend())
    return World(families=kw.pop("families", 5), children_per_family=kw.pop("children_per_family", 2), seed=kw.pop("seed", 8), root_mode="off", **kw)


def test_default_plan_is_byte_identical_and_family_fields_stay_out_of_it():
    plan = default_plan(seed=1, population=3)
    assert "families" not in plan.to_dict() and plan.families == 0
    assert plan.digest() == GenesisPlan.from_dict(plan.to_dict()).digest()
    old = {k: v for k, v in plan.to_dict().items()}
    assert GenesisPlan.from_dict(old).families == 0                           # saves from before families still load


def test_households_have_a_woman_a_man_and_children_with_real_family_links():
    w = fam(families=6, children_per_family=3)
    assert len(w.agents) == 6 * 5 and w.next_agent_id == 30
    adults = [a for a in w.agents.values() if not a.parent_ids]
    kids = [a for a in w.agents.values() if a.parent_ids]
    assert len(adults) == 12 and len(kids) == 18
    assert sorted(a.biological_sex for a in adults).count("female") == 6 and [a.gender for a in adults].count("woman") == 6
    assert [a.gender for a in adults].count("man") == 6
    for k in kids:
        p1, p2 = (w.agents[i] for i in k.parent_ids)
        assert {p1.biological_sex, p2.biological_sex} == {"female", "male"} and k.guardian_ids == k.parent_ids
        assert (k.x, k.z) == (p1.x, p1.z) == (p2.x, p2.z) and k.generation == 1 and not k.adulthood_recorded
        assert 1 <= k.age_years_at_start < 17 and 140 <= k.adult_height_cm <= 205 and 50 < k.height_cm <= k.adult_height_cm
        assert k.reproductive_roles and k.lifespan_years >= 70
    assert {stage(w, a) for a in w.agents.values()} >= {"adult", "child"}


def test_infants_cannot_carry_or_act_and_older_children_start_supplied():
    w = World(families=40, children_per_family=3, seed=2, root_mode="off", backend=IdleBackend())
    infants = [a for a in w.agents.values() if a.parent_ids and age(w, a) < 3]
    older = [a for a in w.agents.values() if a.parent_ids and age(w, a) >= 3]
    assert infants and older
    assert all(sum(a.inventory.values()) == 0 for a in infants) and all(a.inventory["water"] == 3 for a in older)


def test_recorded_creation_and_plan_describe_the_families():
    w = fam(families=4, children_per_family=2)
    event = next(e for e in w.events if e["type"] == "genesis_founders_created")
    assert event["payload"]["families"] == 4 and event["payload"]["children"] == 8 and event["payload"]["founders"] == 16
    rec = w.root.data["genesis"]
    assert rec["generators"]["founders"] == "founders-v2" and rec["plan"]["families"] == 4
    assert GenesisPlan.from_dict(rec["plan"]).digest() == rec["plan_digest"]


def test_validation_and_determinism():
    with pytest.raises(GenesisError):
        default_plan(seed=1, population=7, families=3)                       # population must equal families x (2 + children)
    plan = default_plan(seed=1, population=12, families=3, children_per_family=2)
    import dataclasses
    with pytest.raises(GenesisError):
        dataclasses.replace(plan, generators=tuple(sorted({**dict(plan.generators), "founders": "founders-v1"}.items()))).validate()
    with pytest.raises(ValueError):
        World(families=-1)
    with pytest.raises(ValueError):
        World(families=2, children_per_family=99)
    a, b = fam(seed=3), fam(seed=3)
    assert digest(a.state()) == digest(b.state()) and digest(fam(seed=4).state()) != digest(a.state())
    assert World(population=7, seed=3, families=0).agents.keys() == World(population=7, seed=3).agents.keys()      # families=0 means off


def test_children_grow_in_the_simulation_and_adulthood_is_recorded():
    from caitanya.lifecycle import BiologyConfig
    w = fam(families=1, children_per_family=2, seed=6, biology=BiologyConfig(days_per_tick=1 / 4))
    kid = next(a for a in w.agents.values() if a.parent_ids)
    kid.age_years_at_start = 16                                            # fixture: an adolescent two years from adulthood
    kid.height_cm = round(50 + (kid.adult_height_cm - 50) * (16 / 18) ** .5)
    start = kid.height_cm
    for _ in range(int(2.5 * 365 * 4)):
        w.step()
        kid.hunger = kid.thirst = 0; kid.health = 100                      # keep this child alive (the idle stand-in never feeds anyone)
        if kid.adulthood_recorded:
            break
    assert kid.alive and kid.adulthood_recorded and kid.height_cm == kid.adult_height_cm > start
    assert any(e["type"] == "adulthood_reached" and e["actor_id"] == kid.id for e in w.events)


def test_checkpoint_replay_and_continuation_with_families(tmp_path):
    w = fam(families=3, children_per_family=2, seed=7)
    for _ in range(20):
        w.step()
    r = World.restore(w.checkpoint(tmp_path), backend=w.backend)
    for _ in range(15):
        w.step(); r.step()
    assert digest(r.state()) == digest(w.state()) and w.replay(10)["tick"] == 10


def test_children_are_cared_for_by_their_guardians_in_a_long_mock_run():
    w = World(families=6, children_per_family=2, seed=3, root_mode="off", wildlife_per_species=0)   # mock policy
    for _ in range(144 * 10):                                              # ten simulated days
        w.step()
    kids = [a for a in w.agents.values() if a.parent_ids]
    assert len(kids) == 12
    infants = [a for a in kids if a.age_years_at_start < 3]
    assert all(a.alive for a in infants) or not w.death_causes().get("starvation")      # recorded cause, never silent
    assert sum(a.alive for a in w.agents.values()) >= 20


def test_cli_builds_families_and_ignores_population():
    args = build_parser().parse_args(["--families", "10", "--children-per-family", "2", "--population", "5", "--width", "64", "--depth", "64"])
    w = build_world(args, build_parser(), IdleBackend())
    assert len(w.agents) == 40 and w.manifest["genesis"]["generators"]["founders"] == "founders-v2"
    assert build_parser().parse_args([]).families == 0
