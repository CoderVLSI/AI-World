"""Read-only playback of a finished run: no model, nothing written, the same public API, any tick reproducible."""
import hashlib
import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from conftest import FakeLFM, IdleBackend
from caitanya import playback as pb
from caitanya.engine import Intent, World, digest
from caitanya.server import create_app, build_parser


def make_run(directory, ticks=30, backend=None, **world_kw):
    w = World(seed=4, population=4, wildlife_per_species=2, backend=backend or IdleBackend(), **world_kw)
    app = create_app(w, directory, interval=0, max_ticks=ticks, checkpoint_every=7, segment_bytes=40_000)
    with TestClient(app) as client:
        deadline = time.time() + 120
        while time.time() < deadline:
            e = client.get("/api/v1/health").json()["execution"]
            if not e["running"] and e["reason"] not in (None, "not_started"):
                break
            time.sleep(0.05)
    return w


def same(view, recorded):
    """The viewed world equals the recorded one; the only intended difference is the status label PLAYBACK."""
    return digest({**view.state(), "status": recorded["status"]}) == digest(recorded)


def listing(directory):
    return {p.name: (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(Path(directory).iterdir()) if p.is_file()}


def test_every_tick_of_a_recorded_run_is_reproduced_forward_and_backward(tmp_path):
    w = make_run(tmp_path)
    play = pb.Playback(tmp_path)
    assert play.final_tick == w.tick == 30
    for t in (0, 1, 2, 9, 17, 30, 12, 3, 30, 0, 25):               # forward, backward and jumps
        view = play.seek(t)
        assert same(view, w.replay(t)), t
        assert view.tick == t and view.status == "PLAYBACK"
    assert play.seek(30).metrics()["events"] == len(w.events)
    assert play.seek(10).metrics()["events"] == play.tick_end[10] < len(w.events)
    with pytest.raises(ValueError):
        play.seek(31)


def test_a_run_made_with_a_real_labelled_model_plays_back_without_that_model(tmp_path):
    class Real(FakeLFM):
        def decide(self, observation):
            self.calls += 1
            self.last_request = {"request_id": f"req-{self.calls}", "actor_id": observation["self"]["id"]}
            return Intent(observation["self"]["id"], observation["tick"], "WAIT", {}, "")
    w = make_run(tmp_path, ticks=15, backend=Real())
    assert w.manifest["model_id"] == "fake/real-model"
    play = pb.Playback(tmp_path)                                           # no backend is passed or needed
    assert play.backend.model_id == "fake/real-model" and play.backend.calls == 0
    for _ in range(40):
        play.advance()
    assert play.backend.calls == 0                                         # playback never asked anything to decide
    with pytest.raises(RuntimeError):
        play.backend.decide({})


def test_playback_writes_nothing_to_the_run_folder_and_serves_the_normal_read_only_api(tmp_path):
    w = make_run(tmp_path, ticks=20)
    before = listing(tmp_path)
    play = pb.Playback(tmp_path)
    app = create_app(playback=play, interval=0.01, loop=False)
    with TestClient(app) as client:
        deadline = time.time() + 60
        while time.time() < deadline:
            if client.get("/api/v1/health").json()["execution"]["reason"] == "playback_finished":
                break
            time.sleep(0.05)
        health = client.get("/api/v1/health").json()
        live = client.get("/api/v1/live").json()
        terrain = client.get("/api/v1/terrain?step=4").json()
        snap = client.get("/api/v1/world/snapshot").json()
        assert client.post("/api/v1/world/snapshot", json={}).status_code == 405
        events = client.get("/api/v1/world/events?after=0").json()
    assert health["status"] == "PLAYBACK" and health["execution"]["reason"] == "playback_finished"
    assert live["tick"] == 20 and len(live["agents"]) == 4 and live["wildlife"]["animals"]
    assert terrain["seed"] == 4 and snap["tick"] == 20 and events["events"]
    assert "root" not in snap and all("memories" not in a and "ltm" not in a for a in snap["agents"].values())     # still redacted
    assert listing(tmp_path) == before                                    # nothing was written, touched or created


def test_playback_loops_and_moves_forward_through_the_recorded_ticks(tmp_path):
    make_run(tmp_path, ticks=6)
    play = pb.Playback(tmp_path)
    app = create_app(playback=play, interval=0.01, loop=True)
    seen = set()
    with TestClient(app) as client:
        deadline = time.time() + 30
        while time.time() < deadline and len(seen) < 7:
            seen.add(client.get("/api/v1/live").json()["tick"])
            time.sleep(0.01)
        assert client.get("/api/v1/health").json()["execution"]["reason"] == "playback"
    assert seen == set(range(7)) or seen >= {0, 1, 2, 3, 4, 5, 6}


def test_not_a_run_folder_is_refused_and_the_cli_has_the_options(tmp_path):
    with pytest.raises(ValueError, match="not a run folder"):
        pb.Playback(tmp_path)
    args = build_parser().parse_args(["--playback", "x", "--speed", "4", "--no-loop"])
    assert args.playback == "x" and args.speed == 4 and args.no_loop
    assert build_parser().parse_args([]).playback is None


def test_environmental_zones_appear_at_the_recorded_ticks(tmp_path):
    w = World(seed=4, population=3, nature_forces=True, backend=IdleBackend(), root_mode="off")
    a = w.agents["agent-0000"]
    w.nature_forces.apply(w, "agni", a.x, a.z, 1)
    app = create_app(w, tmp_path, interval=0, max_ticks=10, checkpoint_every=5)
    with TestClient(app) as client:
        deadline = time.time() + 60
        while time.time() < deadline:
            e = client.get("/api/v1/health").json()["execution"]
            if not e["running"] and e["reason"] not in (None, "not_started"):
                break
            time.sleep(0.05)
    play = pb.Playback(tmp_path)
    assert play.seek(10).public()["environment_effects"] == w.public()["environment_effects"]
    assert same(play.seek(5), w.replay(5))
