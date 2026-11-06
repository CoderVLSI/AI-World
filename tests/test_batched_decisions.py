"""Opt-in batched decisions: several inhabitants decided in one generate call, collected in the scheduler's normal order.

No GPU or torch needed: a fake torch, tokenizer and model stand in. This tests the bookkeeping (cache, failures, fallback, counters,
scheduler hook), NOT whether batching is faster or gives the same text on a real model: that is for a measured GPU check."""
import contextlib
import sys
import threading
import types
import pytest
from caitanya import inference as inf
from caitanya.engine import Intent, World

TOOL_TEXT = "<function={name}>\n</function>\n</tool_call>"


class Row(list):
    def tolist(self):
        return list(self)

    def __getitem__(self, item):
        out = super().__getitem__(item)
        return Row(out) if isinstance(item, slice) else out


class Tensor:
    def __init__(self, rows):
        self.rows = [Row(r) for r in rows]
        self.shape = (len(self.rows), len(self.rows[0]) if self.rows else 0)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, i):
        return self.rows[i]


class Encoded(dict):
    def __init__(self, ids):
        super().__init__(input_ids=ids, attention_mask=ids)
        self.input_ids = ids

    def to(self, device):
        return self


class FakeTokenizer:
    eos_token_id = 0
    pad_token = "<pad>"
    padding_side = "right"

    def apply_chat_template(self, messages, tools=None, tokenize=False, add_generation_prompt=True, enable_thinking=False):
        return messages[1]["content"] + " TOOLS:" + ",".join(t["function"]["name"] for t in tools)

    def __call__(self, text, return_tensors=None, padding=False, add_special_tokens=False):
        texts = [text] if isinstance(text, str) else list(text)
        ids = [[ord(c) % 250 + 1 for c in t] for t in texts]
        if isinstance(text, str):
            return Encoded(Tensor(ids)) if return_tensors else types.SimpleNamespace(input_ids=ids[0])
        assert padding and self.padding_side == "left", "batched prompts must be left padded"
        width = max(len(r) for r in ids)
        padded = [[0] * (width - len(r)) + r for r in ids] if return_tensors else ids
        return Encoded(Tensor(padded)) if return_tensors else types.SimpleNamespace(input_ids=ids[0])

    def decode(self, tokens, skip_special_tokens=False):
        return "".join(chr(t) for t in (tokens.tolist() if hasattr(tokens, "tolist") else tokens) if t)


class FakeModel:
    def __init__(self):
        self.calls, self.fail_batches = [], False

    def generate(self, input_ids=None, attention_mask=None, **kw):
        self.calls.append(len(input_ids.rows))
        if self.fail_batches and len(input_ids.rows) > 1:
            raise RuntimeError("CUDA out of memory")
        outs = []
        for row in input_ids.rows:
            name = "WAIT" if sum(row) % 2 == 0 else "REST"
            outs.append(list(row) + [ord(c) for c in TOOL_TEXT.format(name=name)])
        width = max(len(o) for o in outs)
        return Tensor([o + [0] * (width - len(o)) for o in outs])


@pytest.fixture
def backend(monkeypatch):
    fake_torch = types.ModuleType("torch")
    fake_torch.inference_mode = contextlib.nullcontext
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    def make(batch_size=4, max_prompt_tokens=100_000):
        b = inf.TransformersLFM3Backend.__new__(inf.TransformersLFM3Backend)
        b.model_revision, b.device, b.max_new_tokens, b.max_seconds, b.max_prompt_tokens = "fake", "cpu", 8, 5, max_prompt_tokens
        b.lock, b.calls, b.failures, b.output_tokens, b.elapsed_seconds = threading.Lock(), 0, 0, 0, 0
        b.prompt_token_counts, b.prompt_budget_failures, b.last_request = [], 0, {}
        b.batch_size, b._prefetched, b.batches, b.batched_items, b.batch_seconds, b.batch_fallbacks = batch_size, {}, 0, 0, 0.0, 0
        b.tokenizer, b.model = FakeTokenizer(), FakeModel()
        return b
    return make


def observation(world, aid):
    return world.observe(aid)


@pytest.fixture
def world():
    from conftest import IdleBackend
    return World(seed=5, population=6, width=64, depth=64, backend=IdleBackend())


def test_a_batch_decides_everyone_once_and_decide_collects_each_result(backend, world):
    b = backend()
    ids = sorted(world.agents)[:4]
    b.prefetch([observation(world, i) for i in ids])
    assert b.model.calls == [4], "one generate call for four inhabitants"
    assert b.calls == 4 and b.batches == 1 and b.batched_items == 4 and b.failures == 0
    for i in ids:
        intent = b.decide(observation(world, i))
        assert isinstance(intent, Intent) and intent.agent_id == i and intent.action in {"WAIT", "REST"}
        assert b.last_request["actor_id"] == i
    assert b.model.calls == [4] and b.calls == 4, "collecting results made no further model call"
    assert b._prefetched == {}


def test_a_batch_of_one_gives_the_same_choice_as_the_ordinary_single_call(backend, world):
    b, single = backend(batch_size=4), backend(batch_size=1)
    for i in sorted(world.agents):
        obs = observation(world, i)
        b.prefetch([obs])
        batched = b.decide(observation(world, i))
        plain = single.decide(observation(world, i))
        assert (batched.action, batched.parameters) == (plain.action, plain.parameters), i


def test_batch_size_one_never_batches_and_decide_works_without_a_prefetch(backend, world):
    b = backend(batch_size=1)
    b.prefetch([observation(world, sorted(world.agents)[0])])
    assert b.model.calls == [] and b._prefetched == {}
    assert b.decide(observation(world, sorted(world.agents)[0])).action in {"WAIT", "REST"} and b.model.calls == [1]


def test_one_inhabitants_failure_does_not_fail_the_others(backend, world):
    """A prompt over the token budget fails alone; the other two in the same batch are decided normally."""
    b = backend()
    ids = sorted(world.agents)[:3]
    normal = observation(world, ids[0])
    _, messages, tools = b._prepare(normal)
    normal_len = len(b.tokenizer.apply_chat_template(messages, tools=tools)) + 20
    b.max_prompt_tokens = normal_len + 300
    big = observation(world, ids[1])
    big["self"]["memories"] = [{"tick": 1, "feedback": "x" * 400} for _ in range(8)]
    b.prefetch([observation(world, ids[0]), big, observation(world, ids[2])])
    assert b.decide(observation(world, ids[0])).agent_id == ids[0]
    with pytest.raises(inf.InferenceFailure, match="prompt budget exceeded"):
        b.decide(observation(world, ids[1]))
    assert b.decide(observation(world, ids[2])).agent_id == ids[2]
    assert b.prompt_budget_failures == 1 and b.failures == 1 and b.model.calls == [2], "the over-budget prompt never reached the model"


def test_an_unparseable_output_fails_only_that_inhabitant(backend, world, monkeypatch):
    b = backend()
    ids = sorted(world.agents)[:3]
    real_generate = b.model.generate

    def broken(**kw):
        out = real_generate(**kw)
        out.rows[1] = Row([0] * len(out.rows[1]))          # the second row produced nothing
        return out
    b.model.generate = broken
    b.prefetch([observation(world, i) for i in ids])
    assert b.decide(observation(world, ids[0])).agent_id == ids[0]
    with pytest.raises(inf.InferenceFailure):
        b.decide(observation(world, ids[1]))
    assert b.decide(observation(world, ids[2])).agent_id == ids[2]
    assert b.failures == 1
    assert sum(b.failure_detail["by_message"].values()) == 1, "a failed batch item is explained in failure_detail too"


def test_if_the_batch_cannot_run_every_inhabitant_is_retried_one_at_a_time(backend, world):
    b = backend()
    b.model.fail_batches = True                              # e.g. out of memory for more than one prompt
    ids = sorted(world.agents)[:3]
    b.prefetch([observation(world, i) for i in ids])
    assert b.model.calls == [3, 1, 1, 1] and b.batch_fallbacks == 1 and b.failures == 0
    assert [b.decide(observation(world, i)).agent_id for i in ids] == ids


def test_a_result_from_an_earlier_tick_is_never_used_and_leftovers_are_dropped(backend, world):
    b = backend()
    ids = sorted(world.agents)[:2]
    b.prefetch([observation(world, i) for i in ids])
    world.tick += 1
    assert b.decide(observation(world, ids[0])).agent_id == ids[0]
    assert b.model.calls == [2, 1], "a stale batched choice was ignored and the model was asked again"
    b.prefetch([observation(world, ids[0])])
    assert ids[1] not in b._prefetched, "leftovers from the previous tick were dropped"


def test_metrics_report_the_batching_and_the_batch_size_is_validated(backend, world):
    b = backend()
    b.prefetch([observation(world, i) for i in sorted(world.agents)[:3]])
    import torch  # the fake
    torch.cuda = types.SimpleNamespace(memory_allocated=lambda: 0, max_memory_allocated=lambda: 0)
    b.metadata, b.model_id = {}, "LiquidAI/LFM3-1.7B"
    b.root_metrics = lambda: {}
    m = b.metrics()["batching"]
    assert m["batch_size"] == 4 and m["batches"] == 1 and m["batched_items"] == 3 and m["batch_fallbacks"] == 0
    with pytest.raises(ValueError):
        inf.TransformersLFM3Backend(batch_size=0)
    with pytest.raises(ValueError):
        inf.TransformersLFM3Backend(batch_size=64)


# ------------------------------------------------------------------------------------------------ scheduler hook
class FakeBatching:
    """A 'real' backend (model id is not the mock's) that batches: records what the scheduler hands it."""
    model_id, model_revision, metadata = "fake/real-model", "fake", {}

    def __init__(self, batch_size):
        self.batch_size, self.calls = batch_size, 0
        self.prefetches, self.cache, self.uncached = [], {}, 0
        self.last_request = {}

    def prefetch(self, observations):
        self.prefetches.append([(o["self"]["id"], o["tick"]) for o in observations])
        for o in observations:
            self.cache[o["self"]["id"]] = (o["tick"], Intent(o["self"]["id"], o["tick"], "WAIT", {}, ""))

    def decide(self, observation):
        self.calls += 1
        hit = self.cache.pop(observation["self"]["id"], None)
        if hit is None or hit[0] != observation["tick"]:
            self.uncached += 1
            hit = (observation["tick"], Intent(observation["self"]["id"], observation["tick"], "WAIT", {}, ""))
        self.last_request = {"request_id": f"r-{self.calls}", "actor_id": observation["self"]["id"], "observed_tick": observation["tick"]}
        return hit[1]


def real_world(backend, population=20):
    return World(seed=5, population=population, width=64, depth=64, backend=backend, isvara_config={"enabled": False})


def test_the_scheduler_prefetches_the_inhabitants_it_will_ask_in_batches_from_one_snapshot():
    b = FakeBatching(batch_size=3)
    w = real_world(b)
    w.step()
    cap = w.autonomy.scheduler.max_decisions_per_tick
    assert w.scheduler.data["totals"]["lfm_decisions"] == cap
    asked = [i for call in b.prefetches for i, _ in call]
    assert len(asked) == cap and len(set(asked)) == cap and all(len(call) <= 3 for call in b.prefetches)
    assert [len(c) for c in b.prefetches] == [3, 3, 2]
    assert len({t for call in b.prefetches for _, t in call}) == 1, "one tick, one snapshot"
    assert b.uncached == 0, "every decision was collected from the batch"


def test_with_batch_size_one_the_scheduler_never_prefetches_and_nothing_changes():
    class Sequential(FakeBatching):
        def prefetch(self, observations):
            raise AssertionError("must not be called")
    b = Sequential(batch_size=1)
    w = real_world(b)
    for _ in range(3):
        w.step()
    assert b.calls == 3 * w.autonomy.scheduler.max_decisions_per_tick and b.uncached == b.calls


def test_the_per_tick_wall_clock_cap_stops_further_batches_from_starting():
    import time as _time

    class Slow(FakeBatching):
        def prefetch(self, observations):
            _time.sleep(0.02)
            super().prefetch(observations)
    from dataclasses import replace
    from caitanya.autonomy import AutonomyConfig
    base = AutonomyConfig()
    b = Slow(batch_size=2)
    w = World(seed=5, population=20, width=64, depth=64, backend=b, isvara_config={"enabled": False},
              autonomy=replace(base, scheduler=replace(base.scheduler, max_seconds_per_tick=0.001)))
    w.step()
    assert len(b.prefetches) == 1, "the first batch ran, the cap stopped the rest"


def test_a_world_with_a_mock_backend_is_untouched_by_the_hook():
    from caitanya.engine import MockInferenceBackend, digest
    a = World(seed=5, population=10, width=64, depth=64, backend=MockInferenceBackend(use_tasks=True))
    for _ in range(10):
        a.step()
    assert not hasattr(a.backend, "prefetch")
