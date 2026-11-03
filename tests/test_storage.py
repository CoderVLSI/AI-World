"""Segmented journal + slim checkpoints: constant-size images, lossless rotation, exact recovery."""
import json
import pytest
from caitanya import storage
from caitanya.engine import World, digest
from caitanya.server import create_app
from fastapi.testclient import TestClient


def run(world, directory, ticks, **kw):
    """Drive the real server worker for exactly `ticks` ticks."""
    import time
    app = create_app(world, directory, interval=0, max_ticks=ticks, checkpoint_every=kw.pop("checkpoint_every", 5), **kw)
    with TestClient(app) as client:
        deadline = time.time() + 120
        while time.time() < deadline:
            execution = client.get("/api/v1/health").json()["execution"]
            if not execution["running"] and execution["reason"] not in (None, "not_started"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("worker did not finish")
    return app.state.world


def test_slim_checkpoint_is_constant_size_and_recovers_exactly(tmp_path):
    w = World(seed=3, population=5)
    w = run(w, tmp_path, 40, segment_bytes=10**9)
    slims = sorted(tmp_path.glob("checkpoint-*.json"))
    sizes = [p.stat().st_size for p in slims[1:]]
    assert len(sizes) >= 4
    assert max(sizes) < 1.5 * min(sizes)               # not growing with history
    body = json.loads(slims[-1].read_text())["body"]
    assert "events" not in body and body["events_ref"]["count"] == len(w.events)
    recovered = World.recover(tmp_path, backend=w.backend)
    assert digest(recovered.state()) == digest(w.state())
    assert recovered.events == w.events


def test_rotation_keeps_every_event_and_recovery_is_exact(tmp_path):
    w = run(World(seed=4, population=5), tmp_path, 60, segment_bytes=60_000)
    assert len(storage.segments(tmp_path)) >= 2          # the journal rolled over instead of hitting a limit
    assert w.status != "PAUSED_RESOURCE_LIMIT"
    on_disk = storage.read_events(tmp_path, len(w.events))
    assert on_disk == w.events                           # nothing lost, nothing duplicated
    recovered = World.recover(tmp_path, backend=w.backend)
    assert digest(recovered.state()) == digest(w.state())
    # an older checkpoint whose tail lies in closed segments still recovers to the same state
    newest = sorted(tmp_path.glob("checkpoint-*.json"))[-1]
    newest.rename(newest.with_suffix(".moved"))
    older = World.recover(tmp_path, backend=w.backend)
    assert digest(older.state()) == digest(w.state())


def test_old_full_checkpoint_resumes_into_slim_run(tmp_path):
    first = tmp_path / "a"
    w = run(World(seed=5, population=5), first, 12, segment_bytes=10**9)
    full = w.checkpoint(tmp_path / "full")                 # legacy-format self-contained image, no journal beside it
    resumed = World.restore(full, backend=w.backend)
    target = tmp_path / "b"
    target.mkdir()
    assert storage.ensure_covered(resumed, target)         # base segment written for the missing prefix
    assert storage.read_events(target, len(resumed.events)) == resumed.events


def test_existing_history_is_still_protected_after_rotation(tmp_path):
    run(World(seed=6, population=5), tmp_path, 30, segment_bytes=40_000)
    assert storage.has_history(tmp_path)
    with pytest.raises(ValueError, match="Existing run history"):
        create_app(World(seed=6, population=5), tmp_path)


def test_run_size_limit_pauses_instead_of_filling_the_disk(tmp_path):
    w = run(World(seed=7, population=5), tmp_path, 60, segment_bytes=10**9, max_run_bytes=200_000)
    assert w.status == "PAUSED_RESOURCE_LIMIT" and w.tick < 60
    assert World.recover(tmp_path, backend=w.backend).tick == w.tick


def test_truncated_journal_makes_slim_checkpoint_unusable_not_wrong(tmp_path):
    w = run(World(seed=8, population=5), tmp_path, 20, segment_bytes=10**9)
    (tmp_path / "events.jsonl").write_text("")
    newest = sorted(tmp_path.glob("checkpoint-*.json"))[-1]
    with pytest.raises(ValueError):
        World.restore(newest, backend=w.backend)
