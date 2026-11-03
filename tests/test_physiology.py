"""P0: time-based physiology, consistent clocks, survival invariants, caregiving."""
import pytest
from conftest import IdleBackend
from caitanya.autonomy import AutonomyConfig
from caitanya.engine import World, Agent, Intent, digest
from caitanya.lifecycle import BiologyConfig, age
from caitanya.nature import RESOURCE_TYPES
from caitanya.physiology import unit_interval

BASELINE, HOURLY = 1 / 144, 1 / 24           # ten-minute and one-hour ticks


def idle_world(speed, n=4, seed=314159, **physiology):
    config = AutonomyConfig.from_dict({"physiology": physiology} if physiology else {})
    return World(seed=seed, population=n, backend=IdleBackend(), biology=BiologyConfig(days_per_tick=speed), autonomy=config)


def run_hours(w, hours):
    for _ in range(round(hours / w.hours_per_tick)):
        w.step()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_needs_depend_on_elapsed_time_not_tick_count(seed):
    slow, fast = idle_world(BASELINE, seed=seed, illness_per_day=0), idle_world(HOURLY, seed=seed, illness_per_day=0)
    run_hours(slow, 24), run_hours(fast, 24)
    assert slow.tick == 144 and fast.tick == 24
    for aid in slow.agents:
        a, b = slow.agents[aid], fast.agents[aid]
        assert a.hunger == pytest.approx(b.hunger, abs=1e-3) and a.hunger == pytest.approx(100 / 120 * 24, abs=1e-3)
        assert a.thirst == pytest.approx(b.thirst, abs=1e-3) and a.thirst == pytest.approx(100 / 48 * 24, abs=1e-3)
        assert a.energy == pytest.approx(b.energy, abs=1e-3)


def test_rest_and_effort_use_the_same_hourly_scale_at_both_speeds():
    results = []
    for speed in (BASELINE, HOURLY):
        w = idle_world(speed, illness_per_day=0)
        a = w.agents["agent-0000"]
        a.energy = 10
        for _ in range(round(1 / w.hours_per_tick)):
            assert w.apply(Intent(a.id, w.tick, "REST", {}))[0]
            w.step()
        results.append(a.energy)
    assert results[0] == pytest.approx(results[1], abs=1e-2) and results[0] == pytest.approx(10 + 12 - 1, abs=0.1)
    w = idle_world(BASELINE)
    a = w.agents["agent-0000"]
    before = a.energy
    assert w.apply(Intent(a.id, w.tick, "WRITE", {"title": "t", "text": "x"}))[0]
    assert before - a.energy == pytest.approx(0.5)                # 25% of the legacy cost of 2


def test_coarse_ticks_are_refused_rather_than_silently_changing_physiology():
    with pytest.raises(ValueError, match="too coarse"):
        World(biology=BiologyConfig(days_per_tick=1))
    World(biology=BiologyConfig(days_per_tick=0.25))               # 6 h is the documented ceiling
    World(biology=BiologyConfig(days_per_tick=365), autonomy="legacy")  # legacy fixtures remain possible


@pytest.mark.parametrize("speed", [BASELINE, HOURLY])
@pytest.mark.parametrize("seed", [1, 2])
def test_no_artificial_starvation_with_ordinary_starting_provisions(speed, seed):
    w = idle_world(speed, n=6, seed=seed, illness_per_day=0)
    run_hours(w, 44)                    # thirst reaches 100 only after 48 simulated hours
    assert all(a.alive for a in w.agents.values())
    assert all(0 <= a.hunger <= 100 and 0 <= a.thirst <= 100 and 0 <= a.energy <= 100 for a in w.agents.values())


@pytest.mark.parametrize("speed", [BASELINE, HOURLY])
def test_scarcity_and_death_remain_possible_and_are_attributed(speed):
    w = idle_world(speed, n=5, illness_per_day=0)
    founders = list(w.agents)
    run_hours(w, 24 * 4)
    deaths = [e for e in w.events if e["type"] == "death" and e["actor_id"] in founders]
    assert len(deaths) == 5 and all(not w.agents[i].alive for i in founders)    # no immortality
    assert {d["payload"]["cause"] for d in deaths} == {"dehydration"}
    assert all(w.agents[i].health == 0 for i in founders)
    # the existing bounded root policy reacted to the universal crisis with one ordinary body
    assert len(w.root.data["manifestations"]) == 1


def test_needs_can_be_met_and_health_recovers():
    w = idle_world(BASELINE, illness_per_day=0)
    a = w.agents["agent-0000"]
    a.health, a.hunger, a.thirst = 60, 10, 10
    run_hours(w, 12)                    # healing stops once thirst passes the regeneration ceiling (~19 h)
    assert a.health == pytest.approx(60 + 0.75 * 12, abs=0.1)
    a.thirst = 100
    before = a.health
    run_hours(w, 1)
    assert before - a.health == pytest.approx(5.0, abs=0.1)        # dehydration damage per hour


def test_no_resources_appear_from_nothing():
    w = idle_world(BASELINE, illness_per_day=0)
    totals = lambda: {k: sum(a.inventory.get(k, 0) for a in w.agents.values()) for k in RESOURCE_TYPES}
    before = totals()
    run_hours(w, 24)
    assert totals() == before


def test_regrowth_tracks_elapsed_time_across_speeds():
    for speed in (BASELINE, HOURLY):
        w = idle_world(speed)
        node = next(n for n in w.resources.values() if n.get("renewable", True) and n["capacity"] > 1)
        node["amount"] = 0
        run_hours(w, 12)
        assert node["amount"] == 2                                 # one unit per 6 simulated hours


def test_illness_is_deterministic_independent_of_the_world_rng_and_can_kill():
    a, b = idle_world(BASELINE, seed=7, illness_per_day=1.0), idle_world(BASELINE, seed=7, illness_per_day=1.0)
    for _ in range(300):
        b.rng.random()                                              # unrelated RNG consumption
        a.step(), b.step()
    sick = [e["actor_id"] for e in a.events if e["type"] == "illness_started"]
    assert sick and sick == [e["actor_id"] for e in b.events if e["type"] == "illness_started"]
    assert unit_interval(1, 2, "agent-0000", "x") == unit_interval(1, 2, "agent-0000", "x")
    weak = idle_world(BASELINE, illness_per_day=0, illness_damage_per_hour=6)
    sick = weak.agents["agent-0000"]
    sick.health, sick.thirst, sick.illness = 30, 80, {"since_tick": 0, "until_tick": 10 ** 6}
    run_hours(weak, 8)                                              # unsupported (thirsty): full damage
    assert not sick.alive
    assert [e["payload"]["cause"] for e in weak.events if e["type"] == "death"] == ["illness"]


def test_basic_care_makes_a_long_illness_survivable_but_neglect_does_not():
    outcome = {}
    for label, cared in (("cared", True), ("neglected", False)):
        w = idle_world(BASELINE, n=2, illness_per_day=0)
        a = w.agents["agent-0000"]
        a.illness = {"since_tick": 0, "until_tick": 5 * 144}       # five simulated days of illness
        for _ in range(5 * 144):
            if cared:
                a.hunger = a.thirst = 10                              # fed and hydrated each tick
                a.energy = max(a.energy, 60)                          # and resting
            w.step()
        outcome[label] = (a.alive, a.health)
    assert outcome["cared"][0] and outcome["cared"][1] > 20
    assert not outcome["neglected"][0]


def newborn(w, parent, x, z):
    child = Agent("agent-9000", x, z, born_tick=w.tick, age_years_at_start=0, height_cm=50, adult_height_cm=170,
                  parent_ids=[parent.id], guardian_ids=[parent.id], generation=1, adulthood_recorded=False,
                  inventory={k: 0 for k in RESOURCE_TYPES})
    w.agents[child.id] = child
    w.next_agent_id = 9001
    w.root.register(w)
    return child


class Caregiver(IdleBackend):
    """Scripted test policy: cares for any needy child within reach. Not an LLM."""
    def decide(self, observation):
        self.calls += 1
        me = observation["self"]
        for other in observation["others"]:
            if other["age_years"] < 3 and max(other["hunger"], other["thirst"]) >= 40 and me["inventory"]["water"] > 0:
                return Intent(me["id"], observation["tick"], "CARE", {"target_id": other["id"]}, "")
        return Intent(me["id"], observation["tick"], "WAIT", {}, "")


@pytest.mark.parametrize("speed", [BASELINE, HOURLY])
def test_infants_survive_with_workable_caregiving_and_die_without(speed):
    outcomes = {}
    for label, backend in (("cared", Caregiver()), ("neglected", IdleBackend())):
        config = AutonomyConfig.from_dict({"physiology": {"illness_per_day": 0}})
        w = World(population=2, backend=backend, biology=BiologyConfig(days_per_tick=speed), autonomy=config)
        parent = w.agents["agent-0000"]
        parent.inventory.update(food=30, water=30)
        w.agents["agent-0001"].x, w.agents["agent-0001"].z = parent.x + 20, parent.z   # leave the pair alone
        child = newborn(w, parent, parent.x, parent.z)
        run_hours(w, 24 * 6)
        outcomes[label] = (child.alive, age(w, child) >= 3 or True, w.scheduler.record(parent.id)["wake"])
        outcomes[label + "_death"] = [e for e in w.events if e["type"] == "death" and e["actor_id"] == child.id]
    assert outcomes["cared"][0] and not outcomes["cared_death"]
    assert not outcomes["neglected"][0] and outcomes["neglected_death"][0]["payload"]["cause"] in ("dehydration", "starvation")


def test_guardians_are_prompted_to_reconsider_when_a_dependent_is_needy():
    w = idle_world(BASELINE, n=2, illness_per_day=0)
    parent = w.agents["agent-0000"]
    assert w.apply(Intent(parent.id, 0, "REST_FOR", {"hours": 12}))[0]
    child = newborn(w, parent, parent.x, parent.z)
    child.thirst = 75
    w.step()
    assert any(e["type"] == "task_superseded" for e in w.events)   # woke, re-asked, and replaced the rest
    assert w.scheduler.report(w)["totals"]["tasks_superseded"] == 1
