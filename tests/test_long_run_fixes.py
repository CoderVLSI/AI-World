"""Three small fixes found in the 200-tick far-start run: used-up nodes are not shown, an over-long optional reason is cut, failures are explained."""
import threading
import pytest
from caitanya import inference as inf
from caitanya.engine import World, MockInferenceBackend, digest
from caitanya.genesis import default_plan
from caitanya.server import build_parser
from conftest import IdleBackend


def call(name, body):
    return f"<tool_call>\n<function={name}>\n{body}\n</function>\n</tool_call>"


@pytest.fixture
def obs():
    w = World(seed=5, population=3, width=64, depth=64, backend=IdleBackend())
    return w, w.observe(sorted(w.agents)[0])


def test_an_over_long_reason_is_cut_to_the_limit_instead_of_losing_the_decision(obs):
    _, o = obs
    text = call("TRAVEL_TO", "<parameter=x>\n10\n</parameter>\n<parameter=z>\n12\n</parameter>\n<parameter=reason>\n" + "r" * 450 + "\n</parameter>")
    intent = inf.parse_tool(text, o)
    assert intent.action == "TRAVEL_TO" and intent.parameters == {"x": 10, "z": 12} and len(intent.reason_summary) == 300


def test_other_over_long_text_still_fails_and_the_message_names_only_the_parameter(obs):
    _, o = obs
    with pytest.raises(inf.InferenceFailure, match="text exceeds limit: topic"):
        inf.parse_tool(call("TEACH", "<parameter=target_id>\nagent-0001\n</parameter>\n<parameter=topic>\n" + "t" * 81 + "\n</parameter>\n<parameter=text>\nx\n</parameter>"), o)
    with pytest.raises(inf.InferenceFailure, match="text exceeds limit: text"):
        inf.parse_tool(call("SPEAK", "<parameter=text>\n" + "s" * 2001 + "\n</parameter>"), o)
    assert inf.parse_tool(call("SPEAK", "<parameter=text>\n" + "s" * 2000 + "\n</parameter>"), o).action == "SPEAK"


def backend_for_prepare():
    b = inf.TransformersLFM3Backend.__new__(inf.TransformersLFM3Backend)
    b.lock = threading.Lock()
    return b


def test_used_up_nodes_are_not_shown_to_the_model_and_the_nearest_with_units_are_kept(obs):
    _, o = obs
    me = o["self"]
    nodes = [{"id": f"resource-{i}", "x": me["x"] + (i % 7), "z": me["z"] + (i // 7), "kind": "wood", "amount": 0 if i % 3 == 0 else 5} for i in range(30)]
    shown = inf.visible_resources(nodes, me)
    assert len(shown) == 16 and all(n["amount"] > 0 for n in shown)
    assert shown == sorted(shown, key=lambda n: abs(n["x"] - me["x"]) + abs(n["z"] - me["z"]))
    nearest_with_units = sorted((n for n in nodes if n["amount"] > 0), key=lambda n: abs(n["x"] - me["x"]) + abs(n["z"] - me["z"]))[:16]
    assert shown == nearest_with_units, "a used-up node does not use up one of the sixteen places"
    assert inf.visible_resources([dict(n, amount=0) for n in nodes], me) == []
    assert "GATHER_AT" not in [t["function"]["name"] for t in inf.select_tools(dict(o, resources=[dict(n, amount=0) for n in nodes][:0]))]


def test_failures_are_explained_with_counts_only(obs):
    b = backend_for_prepare()
    b.max_new_tokens = 224
    b._note_failure(inf.InferenceFailure("expected exactly one complete tool call"), 224)
    b._note_failure(inf.InferenceFailure("text exceeds limit: reason"), 90)
    b._note_failure(inf.InferenceFailure("text exceeds limit: reason"), None)
    b._note_failure(RuntimeError("CUDA out of memory secret-looking text"), None)
    d = b.failure_detail
    assert d["hit_token_limit"] == 1
    assert d["by_message"] == {"expected exactly one complete tool call": 1, "text exceeds limit": 2, "RuntimeError": 1}


def test_founder_water_is_an_option_and_the_default_plan_is_unchanged():
    assert dict(default_plan(5, 3).to_dict())["founder_water"] == 3 and default_plan(5, 3).digest() == default_plan(5, 3, founder_water=3).digest()
    dry = World(seed=5, population=4, width=64, depth=64, backend=IdleBackend(), founder_water=0)
    assert {a.inventory["water"] for a in dry.agents.values()} == {0} and dry.root.data["genesis"]["plan"]["founder_water"] == 0
    normal = World(seed=5, population=4, width=64, depth=64, backend=IdleBackend())
    assert {a.inventory["water"] for a in normal.agents.values()} == {3}
    assert build_parser().parse_args([]).founder_water == 3 and build_parser().parse_args(["--founder-water", "0"]).founder_water == 0
    with pytest.raises(Exception):
        World(seed=5, population=4, width=64, depth=64, backend=IdleBackend(), founder_water=-1)
