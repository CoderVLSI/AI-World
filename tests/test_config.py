"""Configuration is explicit, validated, strict and recorded; config/default.json is never auto-loaded."""
import json
from pathlib import Path
import pytest
from caitanya.autonomy import AutonomyConfig, load_experiment_file, PhysiologyConfig, SchedulerConfig
from caitanya.engine import World
from caitanya.server import build_parser, build_world

DEFAULT = Path(__file__).resolve().parent.parent / "config" / "default.json"


def parse(*argv):
    p = build_parser()
    return p.parse_args(list(argv)), p


def test_defaults_describe_the_foundations_mode_and_round_trip():
    config = AutonomyConfig()
    assert AutonomyConfig.from_dict(config.to_dict()) == config
    assert AutonomyConfig.from_dict(AutonomyConfig.legacy_mode().to_dict()) == AutonomyConfig.legacy_mode()
    assert config.scheduler.max_decisions_per_tick == 8 and not config.reflex.enabled and not config.legacy


@pytest.mark.parametrize("bad", [
    {"surprise": {}}, {"scheduler": {"nonsense": 1}}, {"scheduler": {"max_decisions_per_tick": 0}},
    {"scheduler": {"max_decisions_per_tick": True}}, {"physiology": {"hunger_per_hour": float("nan")}},
    {"physiology": {"hunger_per_hour": -1}}, {"physiology": {"illness_max_days": 1, "illness_min_days": 3}},
    {"memory": {"recall_items": 0}}, {"experiments": {"carry_limit_g": 5}}, {"mode": "other"}, {"reflex": []},
    {"mode": "legacy", "scheduler": {"mode": "budgeted"}}])
def test_invalid_or_unknown_configuration_is_rejected_never_ignored(bad):
    with pytest.raises(ValueError):
        AutonomyConfig.from_dict(bad)


def test_default_json_is_valid_but_not_automatically_loaded(tmp_path, monkeypatch):
    params, autonomy = load_experiment_file(DEFAULT)
    assert params["population"] == 50 and params["width"] == 256 and autonomy == AutonomyConfig()
    monkeypatch.chdir(DEFAULT.parent.parent)             # even with the file right there...
    assert len(World().agents) == 5                      # ...a plain World ignores it
    args, p = parse("--run-dir", str(tmp_path))
    assert len(build_world(args, p).agents) == 5         # ...and so does the CLI without --config


def test_config_flag_loads_the_file_and_command_line_overrides_it(tmp_path):
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps({"schema_version": 1, "world": {"width": 64, "depth": 64, "seed": 9},
                                "agents": {"initial_count": 7},
                                "autonomy": {"scheduler": {"max_decisions_per_tick": 3}, "reflex": {"enabled": True}}}))
    args, p = parse("--config", str(path))
    w = build_world(args, p)
    assert len(w.agents) == 7 and w.seed == 9 and w.width == 64
    assert w.autonomy.scheduler.max_decisions_per_tick == 3 and w.autonomy.reflex.enabled
    assert w.manifest["autonomy"]["scheduler"]["max_decisions_per_tick"] == 3          # recorded for the experiment
    args, p = parse("--config", str(path), "--population", "4", "--decisions-per-tick", "5")
    w = build_world(args, p)
    assert len(w.agents) == 4 and w.autonomy.scheduler.max_decisions_per_tick == 5
    args, p = parse("--legacy", "--population", "3")
    assert build_world(args, p).autonomy.legacy


@pytest.mark.parametrize("content", [{"schema_version": 2}, {"schema_version": 1, "bogus": 1},
                                     {"schema_version": 1, "world": {"gravity": 1}},
                                     {"schema_version": 1, "autonomy": {"scheduler": {"max_decisions_per_tick": 0}}}])
def test_bad_experiment_files_fail_loudly(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        load_experiment_file(path)


def test_recover_and_resume_remain_available(tmp_path):
    w = World()
    for _ in range(3):
        w.step()
    ck = w.checkpoint(tmp_path)
    args, p = parse("--resume", str(ck))
    assert build_world(args, p).tick == 3
    args, p = parse("--recover", str(tmp_path))
    assert build_world(args, p).tick == 3
    args, p = parse("--recover", str(tmp_path), "--resume", str(ck))
    with pytest.raises(SystemExit):
        build_world(args, p)


def test_checkpoint_interval_is_configurable_and_validated(tmp_path):
    import time
    from fastapi.testclient import TestClient
    from caitanya.server import create_app
    with pytest.raises(ValueError):
        create_app(World(), tmp_path / "bad", live=False, checkpoint_every=0)
    w = World(population=2)
    with TestClient(create_app(w, tmp_path / "run", interval=0.005, checkpoint_every=7)):
        deadline = time.time() + 20
        while w.tick < 16 and time.time() < deadline:
            time.sleep(0.05)
    ticks = sorted(int(p.stem.split("-")[1]) for p in (tmp_path / "run").glob("checkpoint-*.json"))
    assert 7 in ticks and 14 in ticks and 0 in ticks          # periodic ones, plus the tick-zero and shutdown images
    assert not any(t % 7 and t not in (0, w.tick) for t in ticks)
