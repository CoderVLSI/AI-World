"""The real-backend code path (prompt, tools, budget, parsing, attribution) with stand-ins for torch/tokenizer/model.

This verifies integration only.  It says nothing about LFM3's behaviour; real-model acceptance runs
need a GPU (see docs/EXPERIMENT_PROTOCOL.md).
"""
import contextlib
import hashlib
import json
import sys
import types
import pytest
from caitanya import inference
from caitanya.autonomy import AutonomyConfig
from caitanya.engine import World

CONFIG = AutonomyConfig.from_dict({"physiology": {"illness_per_day": 0}, "scheduler": {"max_decisions_per_tick": 3}})


class Ids:
    def __init__(self, n):
        self.shape = (1, n)

    def to(self, device):
        return self


class Inputs(dict):
    def __init__(self, n):
        super().__init__(input_ids=Ids(n))
        self.input_ids = self["input_ids"]

    def to(self, device):
        return self


class FakeTokenizer:
    eos_token_id = 0

    def __init__(self):
        self.prompts = []

    def apply_chat_template(self, messages, tools, tokenize, add_generation_prompt, enable_thinking):
        self.prompts.append({"messages": messages, "tools": [t["function"]["name"] for t in tools]})
        return json.dumps(messages) + json.dumps(tools)

    def __call__(self, prompt, return_tensors, add_special_tokens):
        return Inputs(len(prompt.split()) * 3)

    def decode(self, tokens, skip_special_tokens):
        return tokens[0]


class FakeModel:
    """One shared model object: counts calls and answers with a scripted tool call."""
    def __init__(self, reply):
        self.calls, self.reply = 0, reply

    def generate(self, **kwargs):
        self.calls += 1
        return [[0] * kwargs["input_ids"].shape[1] + [self.reply(self.calls)]]


@pytest.fixture
def backend(monkeypatch):
    torch = types.SimpleNamespace(inference_mode=lambda: contextlib.nullcontext(),
                                  cuda=types.SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", torch)
    b = object.__new__(inference.TransformersLFM3Backend)
    b.model_revision, b.device, b.max_new_tokens, b.max_seconds, b.max_prompt_tokens = "test-rev", "cpu", 224, 15, 6144
    import threading
    b.lock, b.calls, b.failures, b.output_tokens, b.elapsed_seconds, b.last_request = threading.Lock(), 0, 0, 0, 0, {}
    b.metadata = {"device": "stand-in"}
    b.tokenizer = FakeTokenizer()
    b.model = FakeModel(lambda n: "<tool_call>\n<function=REST_FOR>\n<parameter=hours>1</parameter>\n"
                                  "<parameter=reason>tired</parameter>\n</function>\n</tool_call>")
    return b


def test_decisions_flow_through_the_real_path_with_unchanged_prompt_and_attribution(backend):
    w = World(population=3, backend=backend, autonomy=CONFIG)
    for _ in range(4):
        w.step()
    assert backend.model.calls == backend.calls > 0                    # a single shared model instance
    first = backend.tokenizer.prompts[0]
    system = first["messages"][0]["content"]
    assert hashlib.sha256(system.encode()).hexdigest() == "e11f482d78ed8b1c226f45c93f7b29f169a7993d154777f61634e1d31f091b36"
    user = json.loads(first["messages"][1]["content"].split("\n", 1)[1])
    assert "ltm" not in json.dumps(user) and "brahman" not in json.dumps(user).lower() and "clock" in user
    assert "REST_FOR" in first["tools"] and "REPRODUCE" not in first["tools"] and len(first["tools"]) < 20
    starts = [e for e in w.events if e["type"] == "rest_for"]
    assert starts and all(e["origin"] == "lfm_decision" and e["model_request_id"] for e in starts)
    assert starts[0]["payload"]["parameters"] == {"hours": 1} and starts[0]["payload"]["reason_summary"] == "tired"
    totals = w.scheduler.report(w)["totals"]
    assert totals["lfm_decisions"] == backend.calls and totals["mock_decisions"] == 0 and totals["mechanical_steps"] > 0
    assert backend.metrics()["model_instances"] == 1


def test_oversized_prompts_and_malformed_output_fail_without_any_action(backend):
    backend.max_prompt_tokens = 10
    w = World(population=2, backend=backend, autonomy=CONFIG)
    for _ in range(3):
        w.step()
    assert backend.failures > 0 and backend.model.calls == 0
    assert not [e for e in w.events if e["source"] == "validated_action"]
    assert any(e["type"] == "inference_failed" for e in w.events)
    backend.max_prompt_tokens = 6144
    backend.model.reply = lambda n: "I would like to MOVE north"
    w2 = World(population=2, backend=backend, autonomy=CONFIG)
    w2.step()
    assert not [e for e in w2.events if e["source"] == "validated_action"] and backend.failures >= 3


def test_tools_offered_to_the_model_match_the_world_mode(backend):
    legacy = World(population=2, backend=backend, autonomy="legacy")
    for _ in range(3):
        legacy.step()
    assert backend.tokenizer.prompts and not {"TRAVEL_TO", "PICK", "REST_FOR"} & set(backend.tokenizer.prompts[0]["tools"])
