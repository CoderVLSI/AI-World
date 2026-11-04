"""run_summary: movement and resource numbers from a finished run, read-only and text-free."""
import importlib.util
import json
import sys
from pathlib import Path
from conftest import IdleBackend
from test_playback import make_run, listing
from caitanya.engine import MockInferenceBackend

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("run_summary", ROOT / "scripts" / "run_summary.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["run_summary"] = mod
spec.loader.exec_module(mod)


def test_a_walking_run_shows_displacement_walks_and_progress_toward_sources_and_writes_nothing(tmp_path):
    from caitanya.engine import World
    from caitanya.server import create_app
    from fastapi.testclient import TestClient
    import time
    w = World(seed=5, width=128, depth=128, families=6, children_per_family=0, terrain="geography-v2", backend=MockInferenceBackend(use_tasks=True))
    with TestClient(create_app(w, tmp_path, interval=0, max_ticks=40, checkpoint_every=10, segment_bytes=200_000)) as c:
        end = time.time() + 120
        while time.time() < end:
            e = c.get("/api/v1/health").json()["execution"]
            if not e["running"] and e["reason"] not in (None, "not_started"):
                break
            time.sleep(0.05)
    before = listing(tmp_path)
    r = mod.summarize(tmp_path)
    assert listing(tmp_path) == before, "the run folder is never written"
    assert r["ticks"] == 40 and r["humans"] == 12
    d = r["displacement_from_start_tiles"]
    assert d["peak_max"] >= d["final_max"] >= 0 and d["humans_peaked_at_least_8"] >= d["humans_peaked_at_least_16"]
    assert r["events_by_type_and_origin"].get("move:mechanical_execution", 0) > 0 or r["events_by_type_and_origin"].get("move:validated_action", 0) > 0
    assert "alive" in r["needs_at_end"]
    near = r["sources_near_the_start_at_tick_0"]
    assert sum(near["of_these_depleted_at_end_by_kind"].values()) <= near["nodes_within_sight_of_any_human"]
    assert sum(near["of_these_depleted_at_end_by_kind"].values()) <= sum(r["depleted_nodes_at_end_by_kind_whole_map"].values()), \
        "near-start depletion is a part of whole-map depletion, labelled as such"
    blob = json.dumps(r)
    for word in ("memories", "<tool_call>", "feedback"):
        assert word not in blob


def test_an_idle_run_shows_nobody_moved(tmp_path):
    make_run(tmp_path, ticks=10, backend=IdleBackend())
    r = mod.summarize(tmp_path)
    assert r["displacement_from_start_tiles"]["peak_max"] == 0 and r["displacement_from_start_tiles"]["humans_moved_at_least_1"] == 0
