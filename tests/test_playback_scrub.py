"""Playback controls for viewers: ask for a recorded tick (GET only), with a pure, read-only result."""
import time
import pytest
from fastapi.testclient import TestClient
from caitanya import server
from caitanya import playback as pb
from caitanya.engine import World
from caitanya.server import create_app
from caitanya.witness import live_view, recent_speech
from conftest import IdleBackend
from test_playback import make_run, listing


def expected(reference, t):
    """What the viewer should get for tick t, built through a separate replay object (whose ticks test_playback.py proves exact)."""
    view = reference.seek(t)
    pub = view.public()
    out = live_view(pub)
    out["speech"] = recent_speech(view.events, pub["tick"])
    return out


def test_playback_info_describes_the_recorded_run_and_a_live_server_says_it_is_not_playback(tmp_path):
    make_run(tmp_path, ticks=8)
    with TestClient(create_app(playback=pb.Playback(tmp_path), interval=1000)) as client:
        info = client.get("/api/v1/playback").json()
    assert info["enabled"] is True and info["final_tick"] == 8 and info["loop"] is True and info["tick"] == 0
    with TestClient(create_app(World(seed=1, population=2, backend=IdleBackend()), tmp_path / "live", live=False)) as client:
        assert client.get("/api/v1/playback").json() == {"enabled": False}


def test_a_requested_tick_shows_exactly_that_recorded_moment_in_any_order(tmp_path):
    make_run(tmp_path, ticks=12)
    reference = pb.Playback(tmp_path)
    with TestClient(create_app(playback=pb.Playback(tmp_path), interval=1000)) as client:
        for t in (5, 0, 12, 3, 3, 11, 1):                     # forward, backward, repeated and jumping
            got = client.get(f"/api/v1/live?tick={t}").json()
            assert got["tick"] == t
            assert got == expected(reference, t), t


def test_bad_ticks_are_refused_and_a_live_server_refuses_the_parameter(tmp_path):
    make_run(tmp_path, ticks=5)
    with TestClient(create_app(playback=pb.Playback(tmp_path), interval=1000)) as client:
        for bad in ("6", "-1", "abc"):
            assert client.get(f"/api/v1/live?tick={bad}").status_code in (400, 422), bad
        assert client.get("/api/v1/live?tick=5").status_code == 200
    with TestClient(create_app(World(seed=1, population=2, backend=IdleBackend()), tmp_path / "live2", live=False)) as client:
        assert client.get("/api/v1/live?tick=1").status_code == 400
        assert client.get("/api/v1/live").status_code == 200


def test_scrubbing_writes_nothing_and_only_get_exists(tmp_path):
    make_run(tmp_path, ticks=6)
    before = listing(tmp_path)
    with TestClient(create_app(playback=pb.Playback(tmp_path), interval=1000)) as client:
        for t in (3, 0, 6):
            client.get(f"/api/v1/live?tick={t}")
        assert client.post("/api/v1/live?tick=2").status_code in (404, 405)
    assert listing(tmp_path) == before


def test_the_automatic_advance_waits_while_a_viewer_chooses_ticks_then_resumes(tmp_path, monkeypatch):
    make_run(tmp_path, ticks=20)
    monkeypatch.setattr(server, "SCRUB_HOLD_SECONDS", 0.6)
    with TestClient(create_app(playback=pb.Playback(tmp_path), interval=0.02, loop=True)) as client:
        assert client.get("/api/v1/live?tick=7").json()["tick"] == 7
        held = set()
        end = time.time() + 0.4
        while time.time() < end:                            # inside the hold the replay stays where the viewer put it
            held.add(client.get("/api/v1/live").json()["tick"])
            time.sleep(0.02)
        assert held == {7}
        deadline = time.time() + 10
        moved = False
        while time.time() < deadline and not moved:         # after the hold the automatic playback carries on
            moved = client.get("/api/v1/live").json()["tick"] != 7
            time.sleep(0.05)
        assert moved
