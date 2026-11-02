import pytest
from caitanya.engine import Intent


class IdleBackend:
    """Mock-labelled backend that always waits; isolates scheduler behaviour from any policy."""
    model_id = "mock/deterministic-forager"
    model_revision = "1"
    metadata = {"mock_options": {"use_tasks": True}}

    def __init__(self):
        self.calls = 0

    def decide(self, observation):
        self.calls += 1
        a = observation["self"]
        return Intent(a["id"], observation["tick"], "WAIT", {}, "idle test policy")


class FakeLFM:
    """Stands in for a real model: a different model_id makes the engine treat it as real.

    Used to test attribution and failure handling.  It proves nothing about LFM3 quality.
    """
    model_id = "fake/real-model"
    model_revision = "test"

    def __init__(self, chooser=None, fail_for=()):
        self.calls, self.chooser, self.fail_for = 0, chooser, set(fail_for)
        self.last_request = {}

    def decide(self, observation):
        self.calls += 1
        a = observation["self"]
        self.last_request = {"request_id": f"req-{self.calls:06}", "actor_id": a["id"]}
        if a["id"] in self.fail_for:
            raise RuntimeError("simulated model failure")
        if self.chooser:
            return self.chooser(observation)
        return Intent(a["id"], observation["tick"], "WAIT", {}, "")


@pytest.fixture
def idle():
    return IdleBackend()
