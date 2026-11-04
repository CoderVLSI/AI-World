"""Two opt-in experiments (both OFF by default): a pain signal (what hurt me and how much, never what to do) and moving by
direction word (WALK instead of MOVE). Scripted and stand-in backends only: nothing here says how a real model reacts."""
import contextlib
import json
import sys
import threading
import types
import pytest
from conftest import IdleBackend
from test_lfm_path import FakeModel, FakeTokenizer
from caitanya import forces, inference
from caitanya.autonomy import AutonomyConfig
from caitanya.engine import Intent, World, digest
from caitanya.forces import FORCES, HARM_WINDOW_TICKS

NAMES = [f.name.lower() for f in FORCES.values()]
CONFIG = AutonomyConfig.from_dict({"physiology": {"illness_per_day": 0}})


def pain_world(**kw):
    kw.setdefault("backend", IdleBackend())
    return World(population=3, root_mode="off", nature_forces=True, seed=5, hazard_pain_signal=kw.pop("pain", True), **kw)


# ------------------------------------------------------------------------------------------------------- pain signal
def test_pain_signal_is_off_by_default_and_leaves_no_trace():
    w = World(population=3, root_mode="off", nature_forces=True, seed=5, backend=IdleBackend())
    a = w.agents["agent-0000"]
    w.nature_forces.apply(w, "agni", a.x, a.z, 3)
    for _ in range(6):
        w.step()
    assert "recent_harm" not in w.observe("agent-0000") and "harm" not in w.nature_forces.data and not w.nature_forces.pain_signal
    assert "nature_hazard_pain_signal" not in w.manifest


def test_a_hurt_inhabitant_is_told_how_much_and_by_what_and_nobody_else_is():
    w = pain_world()
    a = w.agents["agent-0000"]
    for aid in ("agent-0001", "agent-0002"):
        w.agents[aid].x, w.agents[aid].z = (a.x + 40) % 64, (a.z + 40) % 64
    w.nature_forces.apply(w, "agni", a.x, a.z, 2)
    for _ in range(3):
        w.step()
    felt = w.observe("agent-0000")["recent_harm"]
    assert set(felt) == {"health_lost", "in_last_ticks", "from"} and felt["from"] == "wildfire" and felt["in_last_ticks"] == HARM_WINDOW_TICKS
    log = w.nature_forces.data["harm"]["agent-0000"]
    assert felt["health_lost"] == pytest.approx(sum(e[1] for e in log), abs=0.1) and felt["health_lost"] > 0
    assert "recent_harm" not in w.observe("agent-0001") and "recent_harm" not in w.observe("agent-0002")
    assert w.manifest["nature_hazard_pain_signal"] is True


def test_the_signal_fades_and_states_facts_only():
    w = pain_world()
    a = w.agents["agent-0000"]
    w.nature_forces.apply(w, "agni", a.x, a.z, 1)
    for _ in range(40):                                        # the 36-tick fire, then the window
        w.step()
    assert not w.nature_forces.data["hazards"]
    for _ in range(HARM_WINDOW_TICKS + 1):
        w.step()
    assert "recent_harm" not in w.observe("agent-0000") and "agent-0000" not in w.nature_forces.data["harm"]
    # while it lasts it is a fact about the past: no name, no advice
    w2 = pain_world()
    b = w2.agents["agent-0000"]
    w2.nature_forces.apply(w2, "rudra", b.x, b.z, 3)
    w2.step(); w2.step()
    text = json.dumps(w2.observe("agent-0000")["recent_harm"]).lower()
    assert all(n not in text for n in NAMES) and not any(word in text for word in ("flee", "escape", "leave", "run", "move", "danger", "avoid"))


def test_instant_pulses_hurt_too_and_heat_that_only_thirsts_does_not_count_as_injury():
    w = pain_world()
    a = w.agents["agent-0000"]
    w.nature_forces.apply(w, "indra", a.x, a.z, 3)             # lightning: instant injury
    assert w.observe("agent-0000")["recent_harm"]["from"] == "lightning"
    w2 = pain_world()
    b = w2.agents["agent-0000"]
    w2.nature_forces.apply(w2, "surya", b.x, b.z, 3)           # heatwave: thirst and energy, no injury
    for _ in range(3):
        w2.step()
    assert "recent_harm" not in w2.observe("agent-0000")


def test_pain_persists_through_checkpoint_and_old_saves_keep_it_off(tmp_path):
    w = pain_world()
    a = w.agents["agent-0000"]
    w.nature_forces.apply(w, "agni", a.x, a.z, 2)
    for _ in range(3):
        w.step()
    r = World.restore(w.checkpoint(tmp_path), backend=w.backend)
    assert r.observe("agent-0000")["recent_harm"] == w.observe("agent-0000")["recent_harm"]
    for _ in range(10):
        w.step(); r.step()
    assert digest(r.state()) == digest(w.state())
    old = forces.NatureForces({"version": forces.VERSION, "last_tick": 0, "recent": [], "counts": {}, "hazard_version": forces.HAZARD_VERSION,
                               "hazards": [], "next_hazard": 1})
    assert not old.pain_signal
    with pytest.raises(ValueError):
        World(population=2, hazard_pain_signal=True)           # needs nature_forces


# --------------------------------------------------------------------------------------------------------- WALK
def walk_world(**kw):
    kw.setdefault("backend", IdleBackend())
    return World(population=3, root_mode="off", seed=5, walk_by_direction=True, autonomy=CONFIG, **kw)


def free_direction(w, a):
    for word, (dx, dz) in (("east", (1, 0)), ("south", (0, 1)), ("west", (-1, 0)), ("north", (0, -1))):
        from caitanya.nature import geography
        if 0 <= a.x + dx < w.width and 3 <= a.z + dz < w.depth and geography(a.x + dx, a.z + dz, w.width, w.depth, w.seed)["walkable"]:
            return word, dx, dz
    raise AssertionError("no free neighbour")


def test_walk_is_off_by_default_and_move_is_the_tool_then():
    w = World(population=3, root_mode="off", seed=5, backend=IdleBackend())
    assert "WALK" not in w.registry and "walk_by_direction" not in w.manifest and "walk_by_direction" not in w.observe("agent-0000")
    names = {t["function"]["name"] for t in inference.select_tools(w.observe("agent-0000"))}
    assert "MOVE" in names and "WALK" not in names


def test_walk_replaces_move_in_the_offered_tools_and_matches_its_rules():
    w = walk_world()
    names = {t["function"]["name"] for t in inference.select_tools(w.observe("agent-0000"))}
    assert "WALK" in names and "MOVE" not in names
    a = w.agents["agent-0000"]
    word, dx, dz = free_direction(w, a)
    x, z, energy = a.x, a.z, a.energy
    ok, why = w.apply(Intent(a.id, 0, "WALK", {"direction": word}, ""))
    assert ok, why
    assert (a.x, a.z) == (x + dx, z + dz) and w.events[-1]["type"] == "walk" and w.events[-1]["source"] == "validated_action"
    cost = energy - a.energy
    b = World(population=3, root_mode="off", seed=5, backend=IdleBackend(), autonomy=CONFIG)       # the same step with MOVE costs the same
    ab = b.agents["agent-0000"]
    e0 = ab.energy
    assert b.apply(Intent(ab.id, 0, "MOVE", {"dx": dx, "dz": dz}, ""))[0] and e0 - ab.energy == cost > 0
    assert "confirmed_state" in w.events[-1]["payload"]


@pytest.mark.parametrize("params", [{"direction": "up"}, {"direction": 3}, {"direction": "north", "extra": 1}, {}, {"dx": 1, "dz": 0}])
def test_invalid_walks_change_nothing(params):
    w = walk_world()
    a = w.agents["agent-0000"]
    before = (a.x, a.z, a.energy)
    ok, why = w.apply(Intent(a.id, 0, "WALK", params, ""))
    assert not ok and (a.x, a.z, a.energy) == before


def test_walk_cannot_leave_the_map_or_enter_water_and_infants_cannot_walk():
    w = walk_world()
    a = w.agents["agent-0000"]
    a.x, a.z = 0, 10
    assert not w.apply(Intent(a.id, 0, "WALK", {"direction": "west"}, ""))[0] and a.x == 0
    from caitanya.nature import geography
    for x in range(w.width):                                   # find a land cell with water to its east
        if geography(x, 20, w.width, w.depth, w.seed)["walkable"] and not geography(x + 1, 20, w.width, w.depth, w.seed)["walkable"]:
            a.x, a.z = x, 20
            ok, why = w.apply(Intent(a.id, 0, "WALK", {"direction": "east"}, ""))
            assert not ok and "water" in why and (a.x, a.z) == (x, 20)
            break
    else:
        pytest.skip("no shoreline on row 20 for this seed")
    b = World(families=2, children_per_family=2, root_mode="off", seed=3, walk_by_direction=True, autonomy=CONFIG, backend=IdleBackend())
    infant = next(x for x in b.agents.values() if x.age_years_at_start < 3 and x.parent_ids)
    assert not b.apply(Intent(infant.id, 0, "WALK", {"direction": "north"}, ""))[0]


def test_walk_persists_and_the_mock_policy_walks_instead_of_moving(tmp_path):
    w = walk_world(backend=None)
    for _ in range(60):
        w.step()
    kinds = {e["type"] for e in w.events if e["source"] == "validated_action" and e.get("origin") != "mechanical_execution"}
    assert "walk" in kinds or "travel_to" in kinds or "gather_at" in kinds
    assert "move" not in kinds                                                     # no direct MOVE decisions in this mode
    r = World.restore(w.checkpoint(tmp_path), backend=w.backend)
    assert "WALK" in r.registry and r.walk_by_direction and "walk_by_direction" in r.observe("agent-0000")
    with pytest.raises(ValueError):
        World(population=2, autonomy="legacy", walk_by_direction=True)


@pytest.fixture
def backend(monkeypatch):
    torch = types.SimpleNamespace(inference_mode=lambda: contextlib.nullcontext(), cuda=types.SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", torch)
    b = object.__new__(inference.TransformersLFM3Backend)
    b.model_revision, b.device, b.max_new_tokens, b.max_seconds, b.max_prompt_tokens = "test-rev", "cpu", 224, 15, 6144
    b.lock, b.calls, b.failures, b.output_tokens, b.elapsed_seconds, b.last_request = threading.Lock(), 0, 0, 0, 0, {}
    b.metadata = {"device": "stand-in"}
    b.tokenizer = FakeTokenizer()
    b.model = FakeModel(lambda n: "<tool_call>\n<function=WALK>\n<parameter=direction>east</parameter>\n</function>\n</tool_call>")
    return b


def test_the_model_sees_walk_not_move_and_never_the_internal_marker(backend):
    w = World(population=3, root_mode="off", seed=5, walk_by_direction=True, autonomy=CONFIG, backend=backend)
    w.step()
    first = backend.tokenizer.prompts[0]
    assert "WALK" in first["tools"] and "MOVE" not in first["tools"]
    prompt = json.dumps(first["messages"])
    assert "walk_by_direction" not in prompt                                        # the marker only selects the tool
    walks = [e for e in w.events if e["type"] == "walk" and e["source"] == "validated_action"]
    assert walks and all(e["payload"]["parameters"] == {"direction": "east"} for e in walks)
    plain = World(population=3, root_mode="off", seed=5, autonomy=CONFIG, backend=backend)       # the default prompt is unchanged
    backend.tokenizer.prompts.clear()
    backend.model.reply = lambda n: "<tool_call>\n<function=REST_FOR>\n<parameter=hours>1</parameter>\n</function>\n</tool_call>"
    plain.step()
    assert "MOVE" in backend.tokenizer.prompts[0]["tools"] and "WALK" not in backend.tokenizer.prompts[0]["tools"]


def test_parse_walk_accepts_a_direction_and_rejects_anything_else():
    obs = {"self": {"id": "agent-0000"}, "tick": 1}
    ok = inference.parse_tool("<tool_call>\n<function=WALK>\n<parameter=direction>north</parameter>\n</function>\n</tool_call>", obs)
    assert ok.action == "WALK" and ok.parameters == {"direction": "north"}
    for bad in ("<tool_call>\n<function=WALK>\n</function>\n</tool_call>",
                "<tool_call>\n<function=WALK>\n<parameter=dx>1</parameter>\n</function>\n</tool_call>"):
        with pytest.raises(inference.InferenceFailure):
            inference.parse_tool(bad, obs)


def test_the_exit_hint_speaks_the_same_direction_words_and_still_leaves_the_zone():
    w = walk_world(nature_forces=True, hazard_exit_hint=True)
    a = w.agents["agent-0000"]
    a.x, a.z = 32, 32
    w.nature_forces.apply(w, "agni", 32, 32, 2)
    w.step()
    hz = w.nature_forces.data["hazards"][0]
    agent = w.agents["agent-0001"]
    step = {"east": (1, 0), "west": (-1, 0), "south": (0, 1), "north": (0, -1)}
    for ox in range(-hz["radius"], hz["radius"] + 1):
        for oz in range(-hz["radius"], hz["radius"] + 1):
            if abs(ox) + abs(oz) > hz["radius"]:
                continue
            agent.x, agent.z = 32 + ox, 32 + oz
            entry = w.nature_forces.observe_hazards(w, agent)[0]
            assert "leave_dx" not in entry and entry["leave_direction"] in step
            dx, dz = step[entry["leave_direction"]]
            px, pz = agent.x + dx * entry["steps_to_leave"], agent.z + dz * entry["steps_to_leave"]
            assert abs(px - 32) + abs(pz - 32) == hz["radius"] + 1


def test_cli_flags():
    from caitanya.server import build_parser
    args = build_parser().parse_args(["--nature-forces", "--hazard-pain-signal", "--walk-by-direction"])
    assert args.hazard_pain_signal and args.walk_by_direction
    args = build_parser().parse_args([])
    assert not args.hazard_pain_signal and not args.walk_by_direction
