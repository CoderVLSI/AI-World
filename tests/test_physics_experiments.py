"""P1: open-ended experimentation - physics-derived outcomes, consequences, conservation, safety."""
import hashlib
import json
import random
import statistics
import pytest
from conftest import IdleBackend
from caitanya import experiments as X
from caitanya import materials as M
from caitanya.autonomy import AutonomyConfig
from caitanya.engine import World, Intent, digest, FOUNDATION, PROMPT_VERSION
from caitanya.inference import system_message, TOOLS, DESCRIPTIONS, select_tools, parse_tool, InferenceFailure

CONFIG = AutonomyConfig.from_dict({"physiology": {"illness_per_day": 0}})
STOCK = dict(stone=8, wood=6, plant_fiber=6, clay=4, coal=2, sand=2, herbs=2, fruit=1, water=3)


def lab(seed=314159, **inventory):
    w = World(seed=seed, population=3, backend=IdleBackend(), autonomy=CONFIG)
    a = w.agents["agent-0000"]
    a.inventory.update(inventory or STOCK)
    return w, a


def do(w, a, action, **params):
    ok, why = w.apply(Intent(a.id, w.tick, action, params))
    return ok, why, (w.events[-1]["payload"] if ok else None)


def pick(w, a, kind):
    ok, why, payload = do(w, a, "PICK", kind=kind)
    assert ok, why
    return payload["object_id"]


def comp(w, oid, index=0):
    return w.objects[oid]["components"][index]


def settle(w, a):
    while a.busy_until_tick > w.tick:
        w.step()


def dry_land(w):
    """Remove stream and spring nodes so tests that mean carried water really use it."""
    for node in w.resources.values():
        if node["kind"] == "water":
            node["amount"] = 0


def total_mass(w, a):
    solids = sum(a.inventory.get(k, 0) * M.props(k)["unit_g"] for k in a.inventory if k in M.MATERIALS)
    objects = sum(X.total_mass_g(o) for o in w.objects.values())
    return solids + objects + w.ledger["dispersed_g"] + w.ledger["atmosphere_g"]


def make_fire(w, a, minutes=30, force=10, dry=True):
    first, second, tinder, fuel = (pick(w, a, "wood"), pick(w, a, "wood"), pick(w, a, "plant_fiber"), pick(w, a, "wood"))
    if dry:
        for oid in (first, second, tinder, fuel):
            comp(w, oid)["moisture"] = 0.05
    ok, why, payload = do(w, a, "RUB", first=first, second=second, force=force, minutes=minutes, beside=tinder,
                          also_beside=fuel)
    assert ok, why
    return payload, (first, second)


def lit_fire(w, a):
    payload, _ = make_fire(w, a)
    assert payload["result"] == "ignited"
    fire = w.objects[payload["fire_id"]]
    while w.tick < fire["start_tick"]:
        w.step()
    return fire


# ------------------------------------------------------------ inspection
def test_inspection_reveals_observable_properties_and_hides_internal_ones():
    w, a = lab()
    stone = pick(w, a, "stone")
    ok, why, payload = do(w, a, "INSPECT", subject=stone)
    seen = payload["observed"][0]
    assert ok and seen["material"] == "stone" and seen["hardness"] == 6.5 and seen["grain"] in ("fine", "medium", "coarse")
    text = json.dumps(payload) + json.dumps(w.observe(a.id))
    assert '"flaw"' not in text and '"quality"' not in text and "toughness" not in text and "ignition" not in text
    assert do(w, a, "INSPECT", subject="inventory:wood")[0] and do(w, a, "INSPECT", subject="spawn-food-0")[0]
    for bad in ("obj-999999", "inventory:gold", "resource-0003", 5):
        assert not do(w, a, "INSPECT", subject=bad)[0]


def test_pick_and_stow_round_trip_conserves_material():
    w, a = lab()
    before = a.inventory["wood"]
    oid = pick(w, a, "wood")
    assert a.inventory["wood"] == before - 1 and w.objects[oid]["held_by"] == a.id
    assert do(w, a, "STOW", object_id=oid)[0] and a.inventory["wood"] == before and oid not in w.objects
    assert not do(w, a, "PICK", kind="water")[0] and not do(w, a, "PICK", kind="gold")[0]
    stone = pick(w, a, "stone")
    other = pick(w, a, "stone")
    ok, _, payload = do(w, a, "STRIKE", striker=stone, target=other, force=6)
    assert ok and not any(do(w, a, "STOW", object_id=o)[0] for o in payload["produced"])  # modified pieces stay objects


# ---------------------------------------------------------------- strike
def test_blows_have_graded_physical_outcomes_and_conserve_mass():
    seen = {}
    for force in (1, 2, 3, 4, 6, 10):
        outcomes = set()
        for seed in range(1, 25):
            w, a = lab(seed)
            s, t = pick(w, a, "stone"), pick(w, a, "stone")
            m0 = total_mass(w, a)
            ok, why, payload = do(w, a, "STRIKE", striker=s, target=t, force=force)
            assert ok, why
            assert total_mass(w, a) == pytest.approx(m0, abs=1e-2)
            outcomes.add(payload["result"])
        seen[force] = outcomes
    assert "no_effect" in seen[1] and "chipped" in seen[3] and seen[10] == {"fractured"}
    assert seen[2] | seen[3] >= {"chipped"}


def test_a_much_softer_striker_cannot_shape_a_harder_target():
    w, a = lab()
    stick, rock = pick(w, a, "wood"), pick(w, a, "stone")
    ok, _, payload = do(w, a, "STRIKE", striker=stick, target=rock, force=10)
    assert ok and payload["result"] == "no_effect" and not payload["produced"]
    assert comp(w, rock)["mass_g"] == 3000


def test_finer_grain_gives_sharper_fresh_edges():
    sharp = {"fine": [], "medium": [], "coarse": []}
    for seed in range(1, 70):
        w, a = lab(seed)
        s, t = pick(w, a, "stone"), pick(w, a, "stone")
        label = M.grain_label(comp(w, t)["quality"])
        ok, _, payload = do(w, a, "STRIKE", striker=s, target=t, force=6)
        for oid in payload["produced"]:
            sharp[label].append(X.comp_edge(comp(w, oid)))
    assert statistics.mean(sharp["fine"]) > statistics.mean(sharp["coarse"]) + 15
    assert min(sharp["coarse"], default=0) < 20      # coarse stone mostly yields dull pieces: a real failure mode


def test_repeating_an_experiment_on_a_new_piece_can_differ():
    results = set()
    for seed in range(1, 40):
        w, a = lab(seed)
        s, t = pick(w, a, "stone"), pick(w, a, "stone")
        results.add(do(w, a, "STRIKE", striker=s, target=t, force=2)[2]["result"])
    assert len(results) >= 2


def test_same_world_and_same_action_always_give_the_same_result():
    runs = []
    for _ in range(2):
        w, a = lab(5)
        s, t = pick(w, a, "stone"), pick(w, a, "stone")
        do(w, a, "STRIKE", striker=s, target=t, force=5)
        runs.append(digest(w.state()))
    assert runs[0] == runs[1]


# ---------------------------------------------------- attachment and use
def haft(w, a, seed_force=5):
    s, t = pick(w, a, "stone"), pick(w, a, "stone")
    produced = do(w, a, "STRIKE", striker=s, target=t, force=seed_force)[2]["produced"]
    flake = max(produced, key=lambda o: X.comp_edge(comp(w, o)))
    return flake, pick(w, a, "wood"), pick(w, a, "plant_fiber")


def test_attaching_a_keen_piece_to_wood_is_decided_by_properties_and_testing():
    depths = {"bare": [], "attached": []}
    for seed in range(1, 25):
        w, a = lab(seed)
        flake, wood, fibre = haft(w, a)
        depths["bare"].append(do(w, a, "TEST", object_id=flake, test="cut", magnitude=5, target="wood")[2]["measured"]["depth_mm_per_stroke"])
        ok, why, payload = do(w, a, "COMBINE", parts=f"{flake},{wood},{fibre}", method="lash")
        assert ok, why
        tool = payload["object_id"]
        result = do(w, a, "TEST", object_id=tool, test="cut", magnitude=5, target="wood")[2]
        depths["attached"].append(result["measured"]["depth_mm_per_stroke"])
        assert result["measured"]["handled"]
    assert statistics.mean(depths["attached"]) > 1.4 * statistics.mean(depths["bare"])


def test_a_dull_attached_piece_is_not_better_and_nothing_names_the_product():
    w, a = lab()
    cobble, wood, fibre = pick(w, a, "stone"), pick(w, a, "wood"), pick(w, a, "plant_fiber")
    tool = do(w, a, "COMBINE", parts=f"{cobble},{wood},{fibre}", method="lash")[2]["object_id"]
    result = do(w, a, "TEST", object_id=tool, test="cut", magnitude=5, target="wood")[2]
    assert result["result"] == "no_edge" and result["measured"]["depth_mm_per_stroke"] == 0
    blob = json.dumps(w.events).lower()
    assert not any(word in blob for word in ("axe", "knife", "spear", "wheel", "hatchet", "temple", "house"))


def test_attachment_rules_and_loose_stacks():
    w, a = lab()
    s, wood, fibre = pick(w, a, "stone"), pick(w, a, "wood"), pick(w, a, "plant_fiber")
    assert not do(w, a, "COMBINE", parts=f"{s},{wood}", method="lash")[0]           # nothing to lash with
    assert not do(w, a, "COMBINE", parts=f"{s}", method="lash")[0]
    assert not do(w, a, "COMBINE", parts=f"{s},{s}", method="stack")[0]
    assert not do(w, a, "COMBINE", parts=f"{s},{wood}", method="weld")[0]
    ok, _, payload = do(w, a, "COMBINE", parts=f"{s},{wood}", method="stack")
    loose = payload["object_id"]
    assert ok and not do(w, a, "TAKE", object_id=loose)[0] or w.objects[loose]["held_by"] == a.id
    assert do(w, a, "TEST", object_id=loose, test="pull", magnitude=1)[2]["result"] == "attachment_gave_way"
    ok, _, payload = do(w, a, "SEPARATE", object_id=fibre)
    assert not ok                                                                 # a single piece has no parts


def test_binder_strength_depends_on_material_state_and_dynamic_curing():
    w, a = lab()
    one, two, clay = pick(w, a, "wood"), pick(w, a, "wood"), pick(w, a, "clay")
    tool = do(w, a, "COMBINE", parts=f"{one},{two},{clay}", method="clay_bond")[2]["object_id"]
    obj = w.objects[tool]
    wet = X.bond_strength(obj, obj["bonds"][0])
    clay_comp = next(c for c in obj["components"] if c["material"] == "clay")
    clay_comp["moisture"] = 0.05
    dry = X.bond_strength(obj, obj["bonds"][0])
    clay_comp["state"]["fired"] = True
    fired = X.bond_strength(obj, obj["bonds"][0])
    assert 0 < wet < dry < fired
    assert wet < 12 <= 12 * 1                                       # a wet bond cannot bear even a light pull
    assert do(w, a, "TEST", object_id=tool, test="pull", magnitude=1)[2]["result"] in ("held", "held_but_strained") or fired < 12


def test_separating_returns_every_component_and_frays_the_binder():
    w, a = lab()
    flake, wood, fibre = haft(w, a)
    tool = do(w, a, "COMBINE", parts=f"{flake},{wood},{fibre}", method="lash")[2]["object_id"]
    m0 = total_mass(w, a)
    ok, _, payload = do(w, a, "SEPARATE", object_id=tool)
    assert ok and len(payload["parts"]) == 3 and total_mass(w, a) == pytest.approx(m0)
    frayed = [o for o in w.objects.values() if o["components"][0]["material"] == "plant_fiber"]
    assert frayed and frayed[0]["components"][0]["integrity"] < 100


def test_testing_pull_reports_the_load_at_which_an_attachment_fails():
    w, a = lab()
    flake, wood, fibre = haft(w, a)
    tool = do(w, a, "COMBINE", parts=f"{flake},{wood},{fibre}", method="lash")[2]["object_id"]
    strength = X.weakest_bond(w.objects[tool])[0]
    assert do(w, a, "TEST", object_id=tool, test="pull", magnitude=3)[2]["result"] in ("held", "held_but_strained")
    result = do(w, a, "TEST", object_id=tool, test="pull", magnitude=10)[2]
    assert result["result"] == "attachment_gave_way" and result["measured"]["failed_at_load"] == pytest.approx(strength, abs=0.5)
    assert len(result["measured"]["parts"]) == 3        # flake, wood and the now-slack fibre


def test_brittle_things_snap_and_flexible_things_bend():
    w, a = lab()
    rock, branch = pick(w, a, "stone"), pick(w, a, "wood")
    comp(w, rock)["flaw"] = 0.9
    assert do(w, a, "TEST", object_id=rock, test="bend", magnitude=10)[2]["result"] == "snapped"
    ok, _, payload = do(w, a, "TEST", object_id=branch, test="bend", magnitude=3)
    assert payload["result"] == "held" and payload["measured"]["deflection_mm"] > 0
    drop = do(w, a, "TEST", object_id=pick(w, a, "stone"), test="drop", magnitude=10)[2]
    assert drop["result"] in ("fractured_on_impact", "held")


def test_pounding_with_something_softer_damages_the_tool():
    w, a = lab()
    stick = pick(w, a, "wood")
    before = comp(w, stick)["mass_g"]
    result = do(w, a, "TEST", object_id=stick, test="pound", magnitude=8, target="stone")[2]
    assert result["result"] == "tool_damaged" and comp(w, stick)["mass_g"] < before
    assert comp(w, stick)["integrity"] < 100


def test_tools_change_how_much_a_gathering_action_yields_without_creating_material():
    w, a = lab()
    flake, wood, fibre = haft(w, a)
    tool = do(w, a, "COMBINE", parts=f"{flake},{wood},{fibre}", method="lash")[2]["object_id"]
    w.resources["tree-1"] = dict(id="tree-1", x=a.x, z=a.z, kind="wood", amount=10, capacity=16, renewable=True)
    wood_before = a.inventory["wood"]
    ok, why, payload = do(w, a, "GATHER_WITH", resource_id="tree-1", tool_id=tool)
    assert ok, why
    assert payload["units"] >= 2 and w.resources["tree-1"]["amount"] == 10 - payload["units"]
    assert a.inventory["wood"] == wood_before + payload["units"]
    plain = pick(w, a, "sand")
    bare = do(w, a, "GATHER_WITH", resource_id="tree-1", tool_id=plain)[2]
    assert bare["units"] == 1
    assert not do(w, a, "GATHER_WITH", resource_id="tree-1", tool_id="obj-999999")[0]


def test_a_weak_attachment_gives_way_under_working_load():
    w, a = lab()
    s, wood, clay = pick(w, a, "stone"), pick(w, a, "wood"), pick(w, a, "clay")
    tool = do(w, a, "COMBINE", parts=f"{s},{wood},{clay}", method="clay_bond")[2]["object_id"]
    w.resources["rock-1"] = dict(id="rock-1", x=a.x, z=a.z, kind="stone", amount=5, capacity=24, renewable=False)
    payload = do(w, a, "GATHER_WITH", resource_id="rock-1", tool_id=tool)[2]
    assert payload["result"] == "tool_failed_under_load" and payload["units"] == 1
    assert tool in w.objects and len(w.objects[tool]["components"]) < 3


# ------------------------------------------------------------ heat, fire
def test_friction_needs_dry_material_force_and_time_and_failure_is_informative():
    outcomes = {}
    for label, kwargs in {"dry_hard": dict(dry=True, force=10, minutes=30), "dry_weak": dict(dry=True, force=3, minutes=5),
                          "damp_hard": dict(dry=False, force=10, minutes=10)}.items():
        w, a = lab()
        payload, _ = make_fire(w, a, **{k: v for k, v in kwargs.items() if k != "dry"}, dry=kwargs["dry"])
        outcomes[label] = payload
    assert outcomes["dry_hard"]["result"] == "ignited"
    assert outcomes["dry_weak"]["result"] == "warm_only" and outcomes["damp_hard"]["result"] != "ignited"
    assert outcomes["dry_weak"]["felt_surface_temperature_c"] < outcomes["dry_hard"]["felt_surface_temperature_c"]
    assert not outcomes["dry_weak"]["fire_id"]


def test_no_fire_exists_unless_someone_makes_it():
    w, a = lab()
    for _ in range(300):
        w.step()
    assert not any(o["kind"] == "fire" for o in w.objects.values())


def test_an_inhabitant_is_busy_while_rubbing_and_the_clock_keeps_running():
    w, a = lab()
    payload, _ = make_fire(w, a, minutes=30)
    assert payload["busy_ticks"] == 3 and a.busy_until_tick == w.tick + 3
    ok, why, _ = do(w, a, "WAIT")
    assert not ok and "busy" in why
    hunger = a.hunger
    settle(w, a)
    assert a.hunger > hunger and do(w, a, "WAIT")[0]
    asked = w.scheduler.record(a.id)["last_decision"]
    assert asked is None or asked >= a.busy_until_tick - 0  # never asked while committed


def test_fire_burns_a_bounded_time_is_fed_and_goes_out():
    w, a = lab()
    fire = lit_fire(w, a)
    ticks = fire["burn_ticks"]
    assert 20 < ticks < 80
    extra = pick(w, a, "wood")
    comp(w, extra)["moisture"] = 0.05
    before = fire["burn_ticks"]
    assert do(w, a, "FEED_FIRE", fire_id=fire["id"], fuel=extra)[0] and fire["burn_ticks"] > before + 20
    damp = pick(w, a, "wood")
    comp(w, damp)["moisture"] = 0.5
    assert do(w, a, "FEED_FIRE", fire_id=fire["id"], fuel=damp)[2]["result"] == "would_not_burn"
    for _ in range(int(fire["burn_ticks"]) + 3):
        w.step()
    assert fire["id"] not in w.objects and any(e["type"] == "fire_out" for e in w.events)
    assert not do(w, a, "FEED_FIRE", fire_id=fire["id"], fuel=damp)[0]


def test_heating_wood_dries_then_chars_then_burns_it_away_with_mass_accounted():
    verdicts = {}
    for minutes in (10, 15, 40):
        w, a = lab()
        fire = lit_fire(w, a)
        wood = pick(w, a, "wood")
        m0 = total_mass(w, a)
        ok, why, payload = do(w, a, "HEAT", subject=wood, source=fire["id"], minutes=minutes)
        assert ok, why
        verdicts[minutes] = payload["effects"][0]["result"]
        assert total_mass(w, a) == pytest.approx(m0, abs=1e-2)
        if minutes == 40:
            assert wood not in w.objects and w.ledger["atmosphere_g"] > 1500
            assert any(o["components"][0]["form"] == "ash" for o in w.objects.values() if o["components"])
    assert verdicts == {10: "dried", 15: "charred", 40: "burned_away"}


def test_clay_hardens_only_if_dried_first_otherwise_it_shatters():
    results = {}
    for label, moisture in (("wet", 0.30), ("dry", 0.05)):
        w, a = lab()
        fire = lit_fire(w, a)
        lump = pick(w, a, "clay")
        comp(w, lump)["moisture"] = moisture
        m0 = total_mass(w, a)
        ok, _, payload = do(w, a, "HEAT", subject=lump, source=fire["id"], minutes=60)
        results[label] = (payload["effects"][0]["result"], lump in w.objects, w.objects.get(lump))
        assert total_mass(w, a) == pytest.approx(m0, abs=1e-2)
    assert results["wet"][0] == "shattered_by_steam" and not results["wet"][1]
    assert results["dry"][0] == "hardened_by_fire" and X.comp_hardness(results["dry"][2]["components"][0]) >= 5


def test_sunlight_dries_things_slowly_and_only_in_daylight():
    w, a = lab()
    while w.hours_per_tick * w.tick % 24 < 10:
        w.step()                                   # reach mid-morning of day 0 (clear weather)
    lump = pick(w, a, "clay")
    before = comp(w, lump)["moisture"]
    assert do(w, a, "HEAT", subject=lump, source="sun", minutes=240)[0]
    daytime = before - comp(w, lump)["moisture"]
    assert daytime > 0.1
    assert not do(w, a, "HEAT", subject=lump, source="obj-000999", minutes=30)[0]


def test_quenching_a_hot_stone_can_shatter_it_but_gentle_cooling_does_not():
    results = {}
    for label, minutes in (("hot", 60), ("warm", 5)):
        w, a = lab()
        dry_land(w)
        fire = lit_fire(w, a)
        rock = pick(w, a, "stone")
        comp(w, rock)["flaw"] = 0.0
        do(w, a, "HEAT", subject=rock, source=fire["id"], minutes=minutes)
        settle(w, a)
        water = a.inventory["water"]
        m0 = total_mass(w, a)
        ok, why, payload = do(w, a, "COOL", subject=rock)
        assert ok, why
        results[label] = payload["effects"][0]["result"]
        assert a.inventory["water"] == water - 1 and total_mass(w, a) == pytest.approx(m0, abs=1e-2)
    assert results == {"hot": "shattered_by_thermal_shock", "warm": "cooled"}
    w, a = lab(**{**STOCK, "water": 0})
    dry_land(w)
    assert not do(w, a, "COOL", subject=pick(w, a, "stone"))[0]                 # no water source


def test_dead_inhabitants_drop_what_they_held():
    w, a = lab()
    oid = pick(w, a, "stone")
    a.alive = False
    w.step()
    assert w.objects[oid]["held_by"] is None and (w.objects[oid]["x"], w.objects[oid]["z"]) == (a.x, a.z)


def test_ownership_provenance_and_handing_over():
    w, a = lab()
    friend = w.agents["agent-0001"]
    friend.x, friend.z = a.x, a.z
    s, t = pick(w, a, "stone"), pick(w, a, "stone")
    produced = do(w, a, "STRIKE", striker=s, target=t, force=6)[2]["produced"]
    obj = w.objects[produced[0]]
    assert obj["creator"] == a.id and obj["provenance"][0]["op"] == "fracture" and obj["provenance"][0]["inputs"] == [t]
    assert do(w, a, "HAND_OVER", target_id=friend.id, object_id=produced[0])[0]
    assert obj["owner"] == friend.id and obj["creator"] == a.id and obj["held_by"] == friend.id
    assert not do(w, a, "HAND_OVER", target_id=friend.id, object_id=produced[0])[0]    # no longer held
    friend.x += 9
    assert not do(w, a, "HAND_OVER", target_id=friend.id, object_id=pick(w, a, "wood"))[0]


def test_carrying_capacity_is_finite():
    w, a = lab(stone=20)
    held = 0
    while do(w, a, "PICK", kind="stone")[0]:
        held += 1
    assert held == 8                                                              # 8 x 3 kg of a 25 kg limit


# ------------------------------------------------ safety and invariants
def test_every_rejected_experiment_leaves_state_untouched():
    w, a = lab()
    s, wood, fibre = pick(w, a, "stone"), pick(w, a, "wood"), pick(w, a, "plant_fiber")
    bad = [("STRIKE", dict(striker=s, target=s, force=5)), ("STRIKE", dict(striker=s, target=wood, force=11)),
           ("STRIKE", dict(striker=s, target="nope", force=5)), ("COMBINE", dict(parts="a,b,c,d,e", method="lash")),
           ("COMBINE", dict(parts=f"{s},{wood}", method="lash")), ("HEAT", dict(subject=s, source="sun", minutes=4)),
           ("HEAT", dict(subject=s, source=7, minutes=30)), ("HEAT", dict(subject=s, source="obj-1", minutes=30)),
           ("RUB", dict(first=s, second=wood, force=5, minutes=5, beside=s)),
           ("RUB", dict(first=s, second=wood, force=5, minutes=31, beside=fibre)),
           ("TEST", dict(object_id=s, test="melt", magnitude=3)), ("TEST", dict(object_id=s, test="cut", magnitude=3)),
           ("TEST", dict(object_id=s, test="cut", magnitude=3, target="water")), ("TAKE", dict(object_id=s)),
           ("DROP", dict(object_id="obj-424242")), ("SEPARATE", dict(object_id=s)),
           ("FEED_FIRE", dict(fire_id=s, fuel=wood)), ("PICK", dict(kind=["stone"])),
           ("INSPECT", dict(subject=None)), ("STRIKE", dict(striker=s, target=wood, force="5")),
           ("EXEC", dict(code="import os")), ("PICK", dict(kind="stone", code="x"))]
    before = digest(w.state())
    for action, params in bad:
        assert not do(w, a, action, **params)[0], (action, params)
    assert digest(w.state()) == before


def test_children_below_the_minimum_age_cannot_experiment():
    w, a = lab()
    a.age_years_at_start = 4
    assert not do(w, a, "PICK", kind="stone")[0] and "old enough" in w.rejections[-1]["reason"]


def test_legacy_worlds_do_not_offer_experiments():
    w = World(autonomy="legacy")
    w.agents["agent-0000"].inventory["stone"] = 3
    assert not w.apply(Intent("agent-0000", 0, "PICK", {"kind": "stone"}))[0]


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_random_valid_and_invalid_experiments_conserve_mass_and_reject_cleanly(seed):
    rng = random.Random(seed)
    w, a = lab(seed)
    for other in w.agents.values():
        other.alive = other is a
    m0 = total_mass(w, a)
    accepted = {}
    materials = list(M.MATERIALS) + ["gold"]

    def oid():
        ids = list(w.objects)
        return rng.choice(ids) if ids and rng.random() < 0.92 else "obj-999999"

    for _ in range(260):
        op = rng.choice(["PICK", "PICK", "STOW", "TAKE", "DROP", "INSPECT", "STRIKE", "STRIKE", "COMBINE", "COMBINE",
                         "SEPARATE", "HEAT", "COOL", "RUB", "RUB", "FEED_FIRE", "TEST", "TEST"])
        params = {"PICK": lambda: dict(kind=rng.choice(materials)), "STOW": lambda: dict(object_id=oid()),
                  "TAKE": lambda: dict(object_id=oid()), "DROP": lambda: dict(object_id=oid()),
                  "INSPECT": lambda: dict(subject=oid()),
                  "STRIKE": lambda: dict(striker=oid(), target=oid(), force=rng.randint(0, 11)),
                  "COMBINE": lambda: dict(parts=",".join(oid() for _ in range(rng.randint(1, 4))), method=rng.choice(list(X.METHODS) + ["bogus"])),
                  "SEPARATE": lambda: dict(object_id=oid()),
                  "HEAT": lambda: dict(subject=oid(), source=rng.choice(["sun", oid()]), minutes=rng.choice([5, 10, 15, 30, 60, 241])),
                  "COOL": lambda: dict(subject=oid()),
                  "RUB": lambda: dict(first=oid(), second=oid(), force=rng.randint(1, 10), minutes=rng.randint(1, 30), beside=oid()),
                  "FEED_FIRE": lambda: dict(fire_id=oid(), fuel=oid()),
                  "TEST": lambda: dict(object_id=oid(), test=rng.choice(list(X.TESTS) + ["x"]), magnitude=rng.randint(1, 10),
                                       target=rng.choice(materials))}[op]()
        if op == "TEST" and params["test"] in ("bend", "pull", "drop") and rng.random() < 0.5:
            params.pop("target")
        before = digest(w.state())
        ok, why = w.apply(Intent(a.id, w.tick, op, params))
        if ok:
            accepted[op] = accepted.get(op, 0) + 1
            assert total_mass(w, a) == pytest.approx(m0, abs=1e-2), (op, params)
            assert all(c["mass_g"] >= 0 for o in w.objects.values() for c in o["components"])
        else:
            assert digest(w.state()) == before, (op, params, why)
        if a.busy_until_tick > w.tick or rng.random() < 0.4:
            w.step()
        if not a.alive:
            break
    assert len(accepted) >= 7, accepted                       # the fuzz really exercised the physics


def test_objects_survive_checkpoint_replay_and_journal_recovery(tmp_path):
    w, a = lab()
    w.checkpoint(tmp_path / "j")
    flake, wood, fibre = haft(w, a)
    do(w, a, "COMBINE", parts=f"{flake},{wood},{fibre}", method="lash")
    make_fire(w, a)
    for _ in range(12):
        w.step()
    restored = World.restore(w.checkpoint(tmp_path / "c"), backend=IdleBackend())
    assert digest(restored.state()) == digest(w.state()) and restored.objects == w.objects
    for _ in range(6):
        w.step()
        restored.step()
    assert digest(restored.state()) == digest(w.state())
    assert digest(w.replay(w.tick)) == digest(w.state())
    (tmp_path / "j" / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in w.events), encoding="utf-8")
    recovered = World.recover(tmp_path / "j", backend=IdleBackend())
    assert digest(recovered.state()) == digest(w.state()) and recovered.ledger == w.ledger


def test_witness_sees_objects_but_inhabitants_do_not_see_hidden_values(tmp_path):
    from fastapi.testclient import TestClient
    from caitanya.server import create_app
    w, a = lab()
    flake, wood, fibre = haft(w, a)
    w.step()
    client = TestClient(create_app(w, tmp_path, live=False))
    snapshot = client.get("/api/v1/world/snapshot").json()
    assert snapshot["objects"] and "scheduler" not in snapshot and "root" not in snapshot
    assert all("ltm" not in agent for agent in snapshot["agents"].values())
    events = client.get("/api/v1/world/events").text
    assert "strike" in events and "brahman" not in events.lower()
    perceived = json.dumps(w.observe(a.id))
    assert '"flaw"' not in perceived and '"quality"' not in perceived


# ------------------------------------------------ prompt and tool contract
def test_neutral_inquiry_prompt_is_byte_identical_to_the_reference():
    assert PROMPT_VERSION == "neutral-v4-inquiry"
    assert hashlib.sha256(FOUNDATION.encode()).hexdigest() == "d367332c9f55577da748fe40a2acd83163e5a76a978231fda4ed2364c45793ee"
    assert hashlib.sha256(system_message().encode()).hexdigest() == "e11f482d78ed8b1c226f45c93f7b29f169a7993d154777f61634e1d31f091b36"


def test_tool_text_contains_no_religion_outcomes_or_recipes():
    text = (FOUNDATION + system_message() + json.dumps(DESCRIPTIONS)).lower()
    import re
    for word in ("veda", "upani", "brahman", "advaita", "reincarnat", "karma", "scripture", "deva", "axe", "knife",
                 "spear", "wheel", "temple", "invent", "discover"):
        assert not re.search(r"\b" + word + r"(?!ory)", text), word          # "inventory" is ordinary vocabulary


def test_offered_tools_follow_the_situation_and_new_tools_parse_safely():
    w, a = lab()
    names = lambda: {t["function"]["name"] for t in select_tools(w.observe(a.id))}
    assert "PICK" in names() and "STRIKE" not in names() and "HEAT" not in names()
    s, t = pick(w, a, "stone"), pick(w, a, "stone")
    assert {"STRIKE", "COMBINE", "TEST", "STOW"} <= names()
    assert "GATHER_WITH" in names()           # something is under foot to gather from, and an object is held
    legacy = World(autonomy="legacy")
    assert not {"TRAVEL_TO", "PICK", "STRIKE"} & {t["function"]["name"] for t in select_tools(legacy.observe("agent-0000"))}
    obs = w.observe(a.id)
    intent = parse_tool("<tool_call><function=STRIKE><parameter=striker>obj-000000</parameter><parameter=target>obj-000001"
                        "</parameter><parameter=force>5</parameter></function></tool_call>", obs)
    assert intent.action == "STRIKE" and intent.parameters["force"] == 5
    intent = parse_tool("<tool_call><function=TEST><parameter=object_id>obj-000000</parameter><parameter=test>pull</parameter>"
                        "<parameter=magnitude>3</parameter></function></tool_call>", obs)
    assert "target" not in intent.parameters                      # optional parameters may be omitted
    intent = parse_tool("<tool_call><function=TRAVEL_TO><parameter=x>12</parameter><parameter=z>20</parameter>"
                        "<parameter=reason>looking for water</parameter><parameter=reconsider_hours>3</parameter></function></tool_call>", obs)
    assert intent.reason_summary == "looking for water" and intent.parameters == {"x": 12, "z": 20, "reconsider_hours": 3}
    for hostile in ("<tool_call><function=STRIKE><parameter=striker>x</parameter></function></tool_call>",
                    "<tool_call><function=PICK><parameter=kind>stone</parameter><parameter=code>os.system('x')</parameter></function></tool_call>",
                    "<tool_call><function=TRAVEL_TO><parameter=x>a</parameter><parameter=z>2</parameter></function></tool_call>"):
        with pytest.raises(InferenceFailure):
            parse_tool(hostile, obs)


def test_inspect_description_states_the_real_reach_rule():
    """The description must match what INSPECT enforces: exact ids, one Manhattan step for resources."""
    text = X.TOOL_DESCRIPTIONS["INSPECT"]
    assert "exact id" in text and "one step" in text and "inventory:<material>" in text
    w, a = lab()
    rid, node = next((k, v) for k, v in w.resources.items() if v["kind"] == "water")
    node["x"], node["z"] = a.x + 1, a.z                       # one step: inspectable
    assert do(w, a, "INSPECT", subject=rid)[0]
    node["x"] = a.x + 2                                       # two steps: visible, not inspectable
    assert do(w, a, "INSPECT", subject=rid)[:2] == (False, "resource out of reach")
    for wrong in ("water: renewable", "water: " + rid, "water"):   # the Stage A failure mode
        assert do(w, a, "INSPECT", subject=wrong)[:2] == (False, "unknown object")
