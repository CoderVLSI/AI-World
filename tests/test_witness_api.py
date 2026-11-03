"""Contract for external viewers (Godot etc.): terrain grid and live view are read-only, stable, and public-only."""
import json
import pytest
from fastapi.testclient import TestClient
from caitanya.engine import World
from caitanya.nature import geography
from caitanya.server import create_app
from caitanya.witness import BIOMES, SCHEMA_LIVE, SCHEMA_TERRAIN, live_view, terrain_grid

LIVE_AGENT_KEYS = {"id", "x", "z", "alive", "gender", "life_stage", "generation", "age_years", "height_cm", "skin_tone",
                   "clothing_color", "parent_ids", "hunger", "thirst", "energy", "health", "unwell", "busy_until_tick"}


@pytest.fixture
def client(tmp_path):
    w = World(population=6, width=64, depth=64)
    for _ in range(25):
        w.step()
    return TestClient(create_app(w, tmp_path, live=False)), w


def test_terrain_grid_matches_the_simulations_own_geography(client):
    c, w = client
    t = c.get("/api/v1/terrain?step=4").json()
    assert t["schema"] == SCHEMA_TERRAIN and t["step"] == 4 and t["biomes"] == BIOMES
    assert t["columns"] == 16 and t["rows"] == 16 and len(t["biome"]) == len(t["elevation"]) == 256
    for index in (0, 37, 100, 255):                       # row-major: z rows, x columns
        x, z = (index % t["columns"]) * 4, (index // t["columns"]) * 4
        g = geography(x, z, w.width, w.depth, w.seed)
        assert BIOMES[t["biome"][index]] == g["biome"] and t["elevation"][index] == round(g["elevation"], 3)
    assert t == c.get("/api/v1/terrain?step=4").json()      # static, deterministic
    assert t["seed"] == w.seed and t["water_level"] < min(e for e, b in zip(t["elevation"], t["biome"]) if b != 0)


@pytest.mark.parametrize("step", [0, -1, 17, 1000])
def test_invalid_terrain_steps_are_rejected(client, step):
    c, _ = client
    assert c.get(f"/api/v1/terrain?step={step}").status_code == 400
    assert c.get("/api/v1/terrain?step=abc").status_code == 422
    with pytest.raises(ValueError):
        terrain_grid(World(width=64, depth=64), step)


def test_live_view_has_the_contract_fields_and_is_much_smaller_than_the_snapshot(client):
    c, w = client
    live = c.get("/api/v1/live").json()
    assert live["schema"] == SCHEMA_LIVE and live["tick"] == w.tick == 25 and live["width"] == 64
    assert len(live["agents"]) == 6 and LIVE_AGENT_KEYS <= set(live["agents"][0])
    assert all({"id", "x", "z", "kind", "amount"} == set(r) and r["amount"] > 0 for r in live["resources"])
    assert live["summary"]["population"] == 6 and live["climate"]["hour"] is not None and live["calendar"]
    assert len(c.get("/api/v1/live").content) < len(c.get("/api/v1/world/snapshot").content)
    planning = [a for a in live["agents"] if "task" in a]
    assert planning and set(planning[0]["task"]) == {"kind", "params", "chosen_by", "steps_left"}


def test_live_and_terrain_are_get_only_and_leak_nothing_private(client):
    c, _ = client
    for path in ("/api/v1/live", "/api/v1/terrain"):
        for method in (c.post, c.put, c.delete, c.patch):
            assert method(path).status_code == 405, (path, method)
        text = c.get(path).text
        for secret in ('"root"', '"ltm"', '"memories"', "brahman", "continuity-", '"rng_state"', '"parenting_proposals"',
                       '"scheduler"', "reason_summary"):
            assert secret not in text, (path, secret)


def test_live_view_includes_fires_and_optional_wildlife_only_when_present():
    base = {"tick": 5, "status": "RUNNING", "width": 8, "depth": 8, "agents": {}, "resources": {},
            "objects": {"obj-1": {"id": "obj-1", "kind": "fire", "x": 2, "z": 3, "start_tick": 3, "held_by": None},
                        "obj-2": {"id": "obj-2", "kind": "piece", "x": 1, "z": 1, "held_by": "agent-0000"}}}
    view = live_view(base)
    assert view["objects"] == [{"id": "obj-1", "kind": "fire", "x": 2, "z": 3, "burning": True}]   # held objects are omitted
    assert "wildlife" not in view
    base["wildlife"] = {"species": {"deer": {"name": "Deer", "group": "mammal", "color": "#d6b78a", "icon": "x"}},
                        "animals": [{"id": "a1", "species": "deer", "x": 1, "z": 2, "action": "grazing", "sex": "female", "alive": True},
                                    {"id": "a2", "species": "deer", "x": 3, "z": 3, "alive": False}], "rng_state": "secret"}
    view = live_view(base)
    assert [a["id"] for a in view["wildlife"]["animals"]] == ["a1"] and "rng_state" not in json.dumps(view)
    assert "icon" not in view["wildlife"]["species"]["deer"]


def test_a_read_only_app_never_starts_the_worker_even_when_its_lifespan_runs(tmp_path):
    """Regression: an endpoint function named `live` once shadowed the live=False flag, so a 'read-only' app stepped the world."""
    import time
    w = World(population=3, width=64, depth=64)
    with TestClient(create_app(w, tmp_path, live=False, interval=0.01)) as c:       # `with` runs startup/shutdown
        time.sleep(0.5)
        assert c.get("/api/v1/health").json()["status"] == "RUNNING"
        assert c.get("/api/v1/live").json()["tick"] == 0
    assert w.tick == 0


def test_the_godot_client_can_only_issue_get_requests():
    """The witness must stay read-only: no Godot script may use any HTTP method other than the default GET."""
    import re
    from pathlib import Path
    scripts = list((Path(__file__).resolve().parent.parent / "godot").glob("*.gd"))
    assert scripts
    for path in scripts:
        text = path.read_text()
        assert not re.search(r"METHOD_(POST|PUT|DELETE|PATCH|HEAD|OPTIONS)", text), path
        assert not re.search(r"request_raw|HTTPClient|WebSocket|ENetMultiplayer|PacketPeer", text), path
        for call in re.findall(r"\.request\(([^)]*)\)", text):
            assert "," not in call, f"{path.name}: request() with extra arguments could set a method or body: {call}"
