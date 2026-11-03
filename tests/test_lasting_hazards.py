"""Lasting hazards: zones that keep acting for a while, are perceived as plain facts, are recorded with inhabitants' responses,
and are visible to Isvara only as recorded evidence. Mock/scripted backends; nothing here says how a real model reacts."""
import json
import math
import pytest
from conftest import IdleBackend
from test_isvara import Scripted
from caitanya import forces, isvara
from caitanya.engine import Intent, World, digest
from caitanya.forces import FORCES, HAZARDS, NatureForces
from caitanya.lifecycle import BiologyConfig

NAMES = [f.name.lower() for f in FORCES.values()]


def world(**kw):
    kw.setdefault("backend", IdleBackend())
    return World(population=kw.pop("population", 3), root_mode=kw.pop("root_mode", "off"), nature_forces=True, seed=kw.pop("seed", 5), **kw)


def spot(w, aid="agent-0000"):
    a = w.agents[aid]
    return a, a.x, a.z


def ended(w):
    return [e for e in w.events if e["type"] == "nature_hazard_ended"]


def test_a_hazard_lasts_acts_on_those_inside_and_ends_with_a_confirmed_summary():
    w = world()
    a, x, z = spot(w)
    for aid in ("agent-0001", "agent-0002"):
        w.agents[aid].x, w.agents[aid].z = (x + 40) % 64, (z + 40) % 64
    w.nature_forces.apply(w, "agni", x, z, 2)
    hz = w.nature_forces.data["hazards"][0]
    assert hz["end_tick"] - hz["start_tick"] == math.ceil(6 / w.nature_forces._hours_per_tick(w)) == 36
    for _ in range(40):
        w.step()
    assert not w.nature_forces.data["hazards"] and len(ended(w)) == 1
    summary = ended(w)[0]["payload"]
    inside = {e["agent_id"]: e for e in summary["exposed"]}
    assert set(inside) == {"agent-0000"} and "agent-0001" not in inside                  # only those inside are affected
    assert inside["agent-0000"]["ticks_inside"] == 36 and inside["agent-0000"]["inside_at_end"] and not inside["agent-0000"]["left_zone"]
    assert inside["agent-0000"]["injury"] == pytest.approx(2.0 * 2 * 6, abs=1e-3)        # 2 hp/h x strength 2 x 6 h, whatever the tick length
    assert ended(w)[0]["source"] == "environment_rule" and w.nature_forces.data["counts"]["hazard_agni"] == 1


def test_damage_per_simulated_hour_does_not_depend_on_the_clock_speed():
    totals = {}
    for dpt in (1 / 144, 1 / 24):
        w = world(biology=BiologyConfig(days_per_tick=dpt))
        a, x, z = spot(w)
        w.nature_forces.apply(w, "agni", x, z, 1)
        for _ in range(int(6 / (dpt * 24)) + 2):
            w.step()
        totals[dpt] = ended(w)[0]["payload"]["exposed"][0]["injury"]
    assert totals[1 / 144] == pytest.approx(totals[1 / 24], abs=1e-3) == pytest.approx(12.0, abs=1e-3)


def test_health_never_goes_below_one_and_the_dead_are_untouched():
    w = world()
    a, x, z = spot(w)
    a.health = 3
    dead = w.agents["agent-0001"]
    dead.alive, dead.health, dead.x, dead.z = False, 0, x, z
    w.nature_forces.apply(w, "agni", x, z, 3)
    for _ in range(40):
        w.step()
        assert a.health >= 1 or not a.alive
    assert dead.health == 0 and "agent-0001" not in {e["agent_id"] for e in ended(w)[0]["payload"]["exposed"]}


@pytest.mark.parametrize("key", sorted(HAZARDS))
def test_each_lasting_force_keeps_acting_and_the_others_stay_instant(key):
    w = world()
    a, x, z = spot(w)
    w.nature_forces.apply(w, key, x, z, 1)
    assert len(w.nature_forces.data["hazards"]) == 1
    for _ in range(int(HAZARDS[key]["hours"] * 6) + 2):
        w.step()
    assert not w.nature_forces.data["hazards"] and ended(w)[0]["payload"]["phenomenon"] == FORCES[key].phenomenon
    for other in set(FORCES) - set(HAZARDS):
        w2 = world()
        b, bx, bz = spot(w2)
        w2.nature_forces.apply(w2, other, bx, bz, 1)
        assert not w2.nature_forces.data["hazards"]


def test_persistence_checkpoint_restore_and_replay_through_a_hazard(tmp_path):
    w = world()
    a, x, z = spot(w)
    w.nature_forces.apply(w, "varuna", x, z, 2)
    for _ in range(10):
        w.step()
    restored = World.restore(w.checkpoint(tmp_path), backend=w.backend)
    assert restored.nature_forces.data["hazards"] == w.nature_forces.data["hazards"]
    for _ in range(20):
        w.step(); restored.step()
    assert digest(restored.state()) == digest(w.state()) and ended(restored) == ended(w)
    assert w.replay(w.tick)["nature_forces"]["hazards"] == w.nature_forces.data["hazards"]
    assert w.replay(12)["tick"] == 12


def test_inhabitants_see_plain_facts_without_names_schedules_or_other_peoples_outcomes():
    w = world()
    a, x, z = spot(w)
    near, far = w.agents["agent-0001"], w.agents["agent-0002"]
    near.x, near.z = min(63, x + 9), z            # radius 5 for strength 1: edge is 4 steps from here
    far.x, far.z = (x + 30) % 64, (z + 30) % 64
    w.nature_forces.apply(w, "agni", x, z, 1)
    for _ in range(2):
        w.step()
    seen = {aid: w.observe(aid)["environment_hazards"] for aid in w.agents}
    assert seen["agent-0000"][0]["inside"] is True and seen["agent-0000"][0]["distance_to_edge"] == 0
    assert seen["agent-0001"][0]["inside"] is False and 0 < seen["agent-0001"][0]["distance_to_edge"] <= forces.VIEW_RANGE
    assert seen["agent-0002"] == []                                                      # beyond what it can perceive
    blob = json.dumps(seen).lower() + json.dumps(w.observe("agent-0000")).lower()
    assert all(n not in blob for n in NAMES)
    assert not any(k in blob for k in ("end_tick", "planned_hours", "exposed", "injury", "duration", "ticks_left"))
    assert set(seen["agent-0000"][0]) == {"phenomenon", "x", "z", "radius", "strength", "distance_to_edge", "inside", "since_tick"}
    assert "environment_hazards" not in World(population=2).observe("agent-0000")        # nothing changes when the feature is off


def test_public_snapshot_and_live_show_zones_only():
    from caitanya.witness import live_view
    w = world()
    a, x, z = spot(w)
    w.nature_forces.apply(w, "surya", x, z, 1)
    for _ in range(3):
        w.step()
    pub = w.public()
    assert pub["environment_hazards"] and "exposed" not in json.dumps(pub["environment_hazards"]) and "end_tick" not in json.dumps(pub["environment_hazards"])
    assert "nature_forces" not in pub
    view = live_view(pub)
    assert set(view["environment_hazards"][0]) == {"phenomenon", "x", "z", "radius", "strength", "start_tick"}
    assert all(n not in json.dumps(view).lower() for n in NAMES)


def test_saves_from_before_lasting_hazards_keep_their_old_behaviour():
    old = {"version": forces.VERSION, "last_tick": 0, "recent": [], "counts": {}}            # Codex's original state shape
    nf = NatureForces(old)
    assert not nf.hazards_enabled
    w = world()
    w.nature_forces = nf
    a, x, z = spot(w)
    w.nature_forces.apply(w, "agni", x, z, 2)
    w.step()
    assert "hazards" not in w.nature_forces.data and "environment_hazards" not in w.observe("agent-0000") and "environment_hazards" not in w.public()
    with pytest.raises(ValueError):
        NatureForces({**old, "hazard_version": "other"})


class Flee(IdleBackend):
    """Scripted stand-in: walks away from a zone it is inside (never a model, and nothing like a claim about LFM3)."""
    def decide(self, observation):
        self.calls += 1
        a = observation["self"]
        zones = [h for h in observation.get("environment_hazards", []) if h["inside"]]
        if zones:
            blocked = {tuple(b) for b in observation.get("blocked", [])}
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (a["x"] + dx, a["z"] + dz) not in blocked:
                    return Intent(a["id"], observation["tick"], "MOVE", {"dx": dx, "dz": dz}, "")
        return Intent(a["id"], observation["tick"], "WAIT", {}, "")


def test_recorded_responses_reach_the_summary_and_isvara_but_only_as_evidence():
    def run(backend):
        w = World(population=3, root_mode="observe", nature_forces=True, seed=5, backend=backend,
                  isvara_config={"reflect_every_ticks": 45})
        a, x, z = spot(w)
        w.nature_forces.apply(w, "agni", x, z, 1)
        for _ in range(46):
            w.step()
        return w
    w = run(type("S", (Scripted, Flee), {})())
    summary = {e["agent_id"]: e for e in ended(w)[0]["payload"]["exposed"]}
    assert summary["agent-0000"]["left_zone"] is True and summary["agent-0000"]["ticks_inside"] < 30        # it walked out and was recorded as leaving
    ctx = w.backend.contexts[0]
    env_items = [i for i in ctx["evidence"] if i["kind"] == "environment"]
    assert any("lasting wildfire began" in i["detail"] for i in env_items)
    text = next(i["detail"] for i in env_items if "ended" in i["detail"])
    assert "wildfire" in text and "left the zone" in text and "inhabitants were exposed" in text
    ids = {e["event_id"] for e in w.events}
    assert all(i["id"] in ids for i in env_items)
    blob = json.dumps(ctx).lower()
    assert all(n not in blob for n in NAMES) and not any(k in blob for k in ("end_tick", "planned_hours", '"exposed"', "next_hazard"))
    assert ctx["environment"]["hazards_started"] == {"wildfire": 1} and ctx["environment"]["active_zones"] == []


def test_isvara_cannot_start_steer_or_schedule_environmental_events():
    evil = {"observations": "o", "conclusions": "c", "uncertainty": "u", "cites": "", "proposal": "start a flood on agent-0000 and make fire last forever"}
    def run(enabled):
        cfg = {"reflect_every_ticks": 8} if enabled else {"enabled": False}
        w = World(population=4, root_mode="observe", nature_forces=True, seed=9, backend=Scripted(evil), isvara_config=cfg)
        a, x, z = spot(w)
        w.nature_forces.apply(w, "rudra", x, z, 2)
        for _ in range(60):
            w.step()
        return w
    on, off = run(True), run(False)
    assert isvara.role_state(on)["totals"]["recorded"] >= 5 and isvara.role_state(on)["totals"]["proposals"] >= 5
    strip = lambda w: {k: v for k, v in w.state().items() if k not in ("root", "manifest")}
    assert digest(strip(on)) == digest(strip(off))                       # bit-identical world, hazards included
    assert on.nature_forces.state() == off.nature_forces.state()


@pytest.mark.parametrize("seed", [314159, 2, 3])
def test_survival_budget_a_month_of_hazards_does_not_wipe_out_a_mock_world(seed):
    w = World(seed=seed, population=5, wildlife_per_species=2, nature_forces=True, biology=BiologyConfig(days_per_tick=1 / 24))
    for _ in range(30 * 24):
        w.step()
    assert sum(a.alive for a in w.agents.values()) == 5 and not w.death_causes()
    started = sum(1 for e in w.events if e["type"] == "nature_hazard_started")
    assert started >= 1 and len(ended(w)) <= started


# ------------------------------------------------------------------ experiment: the geometric way out (off by default)
def hint_world(**kw):
    return World(population=2, root_mode="off", nature_forces=True, seed=5, backend=IdleBackend(), hazard_exit_hint=kw.pop("hint", True), **kw)


def test_the_exit_hint_is_off_by_default_and_changes_nothing_when_off():
    w = world()
    a, x, z = spot(w)
    w.nature_forces.apply(w, "agni", x, z, 2)
    w.step()
    entry = w.observe("agent-0000")["environment_hazards"][0]
    assert not any(k.startswith("leave") or k == "steps_to_leave" for k in entry) and not w.nature_forces.exit_hint
    assert "nature_hazard_exit_hint" not in w.manifest
    assert set(entry) == {"phenomenon", "x", "z", "radius", "strength", "distance_to_edge", "inside", "since_tick"}


def test_with_the_hint_only_those_inside_see_a_straight_way_out_and_it_always_works():
    w = hint_world()
    a, x, z = 0, 32, 32
    w.agents["agent-0000"].x, w.agents["agent-0000"].z = x, z
    w.nature_forces.apply(w, "agni", x, z, 2)                      # radius 6
    hz = w.nature_forces.data["hazards"][0]
    w.step()
    assert w.manifest["nature_hazard_exit_hint"] is True
    agent = w.agents["agent-0001"]
    checked = 0
    for ox in range(-hz["radius"] - 2, hz["radius"] + 3):
        for oz in range(-hz["radius"] - 2, hz["radius"] + 3):
            agent.x, agent.z = x + ox, z + oz
            seen = w.nature_forces.observe_hazards(w, agent)
            d = abs(ox) + abs(oz)
            if not seen:
                assert d - hz["radius"] > forces.VIEW_RANGE                       # too far to perceive at all
                continue
            entry = seen[0]
            if d > hz["radius"]:
                assert not entry["inside"] and "leave_dx" not in entry          # outside: no hint, nothing to leave
                continue
            assert entry["inside"] and abs(entry["leave_dx"]) + abs(entry["leave_dz"]) == 1
            assert entry["steps_to_leave"] == hz["radius"] - d + 1
            px, pz = agent.x, agent.z
            for step in range(entry["steps_to_leave"]):
                inside_before = abs(px - x) + abs(pz - z) <= hz["radius"]
                assert inside_before                                            # still inside until the last step is taken
                px, pz = px + entry["leave_dx"], pz + entry["leave_dz"]
            assert abs(px - x) + abs(pz - z) == hz["radius"] + 1                # exactly one step outside
            checked += 1
    assert checked == 2 * hz["radius"] ** 2 + 2 * hz["radius"] + 1                  # every cell of the zone was tried


def test_the_hint_adds_only_those_keys_and_no_names_and_persists(tmp_path):
    w = hint_world()
    a, x, z = spot(w)
    w.nature_forces.apply(w, "surya", x, z, 1)
    w.step()
    entry = w.observe("agent-0000")["environment_hazards"][0]
    assert set(entry) == {"phenomenon", "x", "z", "radius", "strength", "distance_to_edge", "inside", "since_tick", "leave_dx", "leave_dz", "steps_to_leave"}
    assert all(n not in json.dumps(entry).lower() for n in NAMES)
    r = World.restore(w.checkpoint(tmp_path), backend=w.backend)
    assert r.nature_forces.exit_hint and r.observe("agent-0000")["environment_hazards"] == w.observe("agent-0000")["environment_hazards"]
    old = NatureForces({"version": forces.VERSION, "last_tick": 0, "recent": [], "counts": {}, "hazard_version": forces.HAZARD_VERSION, "hazards": [], "next_hazard": 1})
    assert not old.exit_hint                                                           # saves from before the hint keep it off


def test_the_hint_is_validated_and_has_a_cli_flag():
    with pytest.raises(ValueError):
        World(population=2, hazard_exit_hint=True)                                      # needs nature_forces
    with pytest.raises(ValueError):
        World(population=2, nature_forces=True, hazard_exit_hint="yes")
    from caitanya.server import build_parser
    assert build_parser().parse_args(["--nature-forces", "--hazard-exit-hint"]).hazard_exit_hint is True
    assert build_parser().parse_args([]).hazard_exit_hint is False
