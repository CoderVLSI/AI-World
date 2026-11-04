"""The 50-human systems check: bounded, honest about what it did not run, never writes model text."""
import importlib.util
import json
import sys
from pathlib import Path
import pytest
from caitanya.engine import Intent

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("scale50_check", ROOT / "scripts" / "scale50_check.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["scale50_check"] = mod
spec.loader.exec_module(mod)


def args(tmp_path, *extra):
    return mod.build_parser().parse_args(["--out", str(tmp_path / "out.json"), *extra])


def test_mock_run_reports_fifty_coherent_humans_with_wildlife_counted_separately(tmp_path):
    record, code = mod.run(args(tmp_path, "--ticks", "6", "--run-dir", str(tmp_path / "run")))
    assert code == 0 and record["status"] == "completed" and record["stop"] == "completed"
    ident = record["identity"]
    assert ident["humans"] == ident["unique_ids"] == 50 and ident["genders"] == {"man": 25, "woman": 25} and ident["separate_memory_objects"]
    assert ident["animals_alive_outside_the_human_count"] == 72
    assert record["humans_vs_wildlife"]["wildlife_model_calls"] == 0 and record["humans_vs_wildlife"]["human_decisions_model"] == 0
    assert record["scheduling"]["decisions_per_tick_cap"] == 8 and record["decisions"]["calls"] > 0
    assert record["restore_check"]["restored_state_equals_live"] and record["restore_check"]["restore_made_no_model_calls"]
    assert "MOCK" in record["label"]


def test_the_record_contains_counts_and_categories_never_text(tmp_path):
    record, _ = mod.run(args(tmp_path, "--ticks", "3"))
    blob = json.dumps(record)
    for key in ("memories", "feedback", "<tool_call>", "<function="):
        assert key not in blob


def test_without_a_gpu_the_real_model_mode_says_so_and_estimates_nothing(tmp_path):
    record, code = mod.run(args(tmp_path, "--backend", "lfm3"))
    if record["environment"]["gpu"] is None:
        assert code == 2 and record["status"] == "unverified_no_gpu" and "decisions" not in record


def test_a_failing_backend_stops_the_run_early_and_failures_are_categorised(tmp_path):
    class Failing:
        model_id, model_revision, metadata = "fake", "fake", {"mock_options": {"use_tasks": True}}
        calls = 0

        def decide(self, observation):
            self.calls += 1
            raise RuntimeError("expected exactly one complete tool call")
    record, code = mod.run(args(tmp_path, "--ticks", "30", "--max-failure-rate", "0.5"), backend=Failing())
    assert code == 0 and record["stop"] == "stopped_at_failure_rate" and record["status"] == "partial"
    assert record["decisions"]["failure_categories"] == {"no_single_complete_tool_call": record["decisions"]["failures"]}
    assert record["ticks_completed"] < 30


def test_the_wall_clock_and_event_byte_limits_stop_the_run(tmp_path):
    record, _ = mod.run(args(tmp_path, "--ticks", "30", "--max-real-seconds", "0"))
    assert record["stop"] == "stopped_at_wall_clock_limit" and record["ticks_completed"] == 0
    record, _ = mod.run(args(tmp_path, "--ticks", "30", "--max-run-mb", "0.01"))
    assert record["stop"] == "stopped_at_event_bytes" and record["ticks_completed"] < 30


def test_a_non_empty_run_directory_is_refused(tmp_path):
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "keep.txt").write_text("x")
    with pytest.raises(SystemExit):
        mod.run(args(tmp_path, "--run-dir", str(tmp_path / "run")))


def test_failure_categories_cover_the_parser_errors_and_gpu_oom():
    for text, label in (("prompt budget exceeded", "prompt_budget"), ("CUDA out of memory", "gpu_out_of_memory"), ("unknown tool", "unknown_tool"),
                        ("something new", "other")):
        assert mod.failure_category(RuntimeError(text)) == label
    assert mod.jain([5, 5, 5]) == 1.0 and mod.jain([]) is None


def test_the_terrain_option_selects_the_river_valley_map_and_the_founders_stand_on_land(tmp_path):
    record, code = mod.run(args(tmp_path, "--ticks", "3", "--terrain", "geography-v2"))
    assert code == 0 and record["terrain"] == "geography-v2" and record["identity"]["humans"] == 50
    default, _ = mod.run(args(tmp_path, "--ticks", "1"))
    assert default["terrain"] == "geography-v1"
