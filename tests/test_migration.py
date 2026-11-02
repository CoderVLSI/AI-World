"""Schema versioning: a genuine v0.4.0 (schema 1) run must load, continue and recover unchanged."""
import copy
import json
import shutil
from pathlib import Path
import pytest
from caitanya.engine import World, digest, SUPPORTED_SCHEMAS

FIXTURE = Path(__file__).parent / "fixtures" / "v1_run"
NEW_TOP = {"autonomy", "scheduler", "objects", "next_object_id", "ledger"}
NEW_AGENT = {"task", "busy_until_tick", "illness", "ltm"}


def as_v1(state):
    """Project a schema-2 state back onto the schema-1 key set."""
    state = copy.deepcopy(state)
    state["schema_version"] = 1
    for key in NEW_TOP:
        state.pop(key)
    for agent in state["agents"].values():
        for key in NEW_AGENT:
            agent.pop(key)
    return state


@pytest.fixture
def run_dir(tmp_path):
    target = tmp_path / "v1"
    shutil.copytree(FIXTURE, target)
    return target


def expected():
    return json.loads((FIXTURE / "expected.json").read_text())


def test_fixture_is_genuinely_schema_one():
    body = json.loads(next(FIXTURE.glob("checkpoint-*.json")).read_text())["body"]
    assert body["state"]["schema_version"] == 1 and "scheduler" not in body["state"]
    assert body["state"]["manifest"]["engine_version"] == "0.4.0"


def test_old_checkpoint_loads_in_legacy_mode_and_reproduces_v040_bit_for_bit(run_dir):
    w = World.restore(next(run_dir.glob("checkpoint-*.json")))
    assert w.autonomy.legacy and w.tick == expected()["checkpoint_tick"]
    for _ in range(expected()["final_tick"] - w.tick):
        w.step()
    # Continuing under the new code must give exactly the state v0.4.0 recorded.
    assert digest(as_v1(w.state())) == expected()["final_state_digest"]


def test_old_journal_tail_recovers_and_the_chain_stays_replayable(run_dir):
    w = World.recover(run_dir)
    assert w.tick == expected()["final_tick"]
    assert digest(w._last_committed_state) == expected()["final_state_digest"]
    assert digest(as_v1(w.state())) == expected()["final_state_digest"]
    for _ in range(6):
        w.step()
    assert digest(w.replay(w.tick)) == digest(w._last_committed_state)   # old patches + new patches replay
    assert digest(w.replay(expected()["final_tick"])) == expected()["final_state_digest"]
    restored = World.restore(w.checkpoint(run_dir / "after"))
    assert restored.autonomy.legacy and digest(restored.state()) == digest(w.state())
    restored.step(), w.step()
    assert digest(restored.state()) == digest(w.state())


def test_migrated_world_keeps_legacy_cadence_not_the_new_scheduler(run_dir):
    w = World.restore(next(run_dir.glob("checkpoint-*.json")))
    assert w.tick % 3 == 0
    before = w.backend.calls
    w.step(), w.step(), w.step()
    assert w.backend.calls - before == len(w.agents)                        # one full round, on the third tick only
    assert not w.registry                                                   # no new actions in migrated runs


def test_unsupported_or_tampered_schemas_fail_safely(tmp_path):
    w = World()
    path = w.checkpoint(tmp_path)
    data = json.loads(path.read_text())
    data["body"]["state"]["schema_version"] = 99
    data["checksum"] = digest(data["body"])                                  # valid checksum, unsupported schema
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unsupported schema"):
        World.restore(path)
    data["body"]["state"]["tick"] = 5                                        # now tampered
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="checksum"):
        World.restore(path)
    assert SUPPORTED_SCHEMAS == (1, 2)


def test_new_checkpoints_are_schema_two_and_record_the_full_configuration(tmp_path):
    w = World()
    body = json.loads(w.checkpoint(tmp_path).read_text())["body"]
    assert body["state"]["schema_version"] == 2
    assert body["state"]["autonomy"]["scheduler"]["max_decisions_per_tick"] == 8
    assert body["state"]["manifest"]["engine_version"] == "0.5.0"
    assert body["state"]["manifest"]["autonomy"] == body["state"]["autonomy"]
