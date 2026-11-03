"""P3: the witness stays read-only and sees progress without seeing private state."""
import json
from fastapi.testclient import TestClient
from test_physics_experiments import lab, do, haft, make_fire, dry_land
from test_memory import inspect_stone
from caitanya.engine import World
from caitanya.server import create_app

NEW_ENDPOINTS = ["/api/v1/scheduler", "/api/v1/knowledge", "/api/v1/objects"]


def test_new_endpoints_are_get_only_and_aggregate(tmp_path):
    w, a = lab()
    dry_land(w)
    inspect_stone(w, a)
    do(w, a, "HYPOTHESIZE", statement="zxqv-private", subject="stone")
    w.step()
    client = TestClient(create_app(w, tmp_path, live=False))
    for path in NEW_ENDPOINTS:
        assert client.get(path).status_code == 200
        for method in (client.post, client.put, client.delete, client.patch):
            assert method(path).status_code == 405, (path, method)
    knowledge = client.get("/api/v1/knowledge").json()
    assert knowledge["practical"] >= 3 and "zxqv" not in json.dumps(knowledge)
    assert client.get("/api/v1/scheduler").json()["totals"]["mock_decisions"] >= 0


def test_plans_attribution_objects_and_fires_are_observable(tmp_path):
    w = World(population=5)                                     # default mock with bounded intentions
    for _ in range(40):
        w.step()
    client = TestClient(create_app(w, tmp_path / "a", live=False))
    snapshot = client.get("/api/v1/world/snapshot").json()
    planning = [a for a in snapshot["agents"].values() if a["task"]]
    assert planning and all(a["task"]["selected_by"]["origin"] == "mock_policy" for a in planning)
    totals = client.get("/api/v1/scheduler").json()["totals"]
    assert totals["mechanical_steps"] > totals["mock_decisions"] > 0 and totals["lfm_decisions"] == 0
    events = client.get("/api/v1/world/events").json()["events"]
    assert any(e.get("origin") == "mechanical_execution" for e in events)

    w2, a = lab()
    make_fire(w2, a)
    client = TestClient(create_app(w2, tmp_path / "b", live=False))
    objects = client.get("/api/v1/objects").json()
    assert any(o["kind"] == "fire" for o in objects.values())
    assert any(e["type"] == "rub" and e["payload"]["result"] == "ignited"
               for e in client.get("/api/v1/world/events").json()["events"])


def test_public_surfaces_never_expose_root_memory_or_scheduler_internals(tmp_path):
    w, a = lab()
    inspect_stone(w, a)
    haft(w, a)
    for _ in range(3):
        w.step()
    client = TestClient(create_app(w, tmp_path, live=False))
    for path in ("/api/v1/world/snapshot", "/api/v1/history?from_tick=2&to_tick=2", "/api/v1/world/events",
                 f"/api/v1/agents/{a.id}", "/api/v1/families", "/api/v1/metrics", "/api/v1/objects"):
        text = client.get(path).text
        for secret in ('"root"', '"ltm"', '"memories"', "brahman", "continuity-", '"due_since"', '"last_seq"', '"parenting_proposals"'):
            assert secret not in text, (path, secret)
    assert client.get("/api/v1/agents/nobody").status_code == 404
