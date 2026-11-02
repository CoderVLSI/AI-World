import json

from caitanya.engine import World, Intent, digest


def test_root_owns_delegation_without_disclosing_identity():
    world = World()
    assert len(world.root.data["children"]) == 5
    assert all(c["parent"] == "brahman" for c in world.root.data["children"].values())
    aid = next(iter(world.agents))
    assert "brahman" not in json.dumps(world.observe(aid)).lower()
    assert "root" not in world.public()
    intent = world.root.delegate(world, aid)
    assert intent.agent_id == aid
    assert world.apply(intent)[0]
    thread = world.root.data["children"][aid]["thread"]
    assert sum(world.root.data["threads"][thread]["action_counts"].values()) == 1


def test_continuity_is_private_and_does_not_transfer_memories():
    from caitanya.engine import Agent
    world = World()
    previous = world.agents["agent-0000"]
    previous.memories.append({"secret": "prior-life-belief"})
    world.apply(Intent(previous.id, world.tick, "WAIT"))
    previous.alive = False
    child = Agent("agent-0005", previous.x, previous.z, age_years_at_start=0)
    world.agents[child.id] = child
    world.next_agent_id = 6
    world.root.register(world)
    old = world.root.data["children"][previous.id]["thread"]
    assert world.root.data["children"][child.id]["thread"] == old
    assert world.root.data["threads"][old]["lives"] == [previous.id, child.id]
    assert child.memories == [] and child.knowledge == []
    assert "prior-life-belief" not in json.dumps(world.observe(child.id))


def test_form_is_bounded_and_subject_to_world_validation():
    world = World()
    for a in world.agents.values():
        a.hunger = 90
    world.root.sustain(world)
    assert len(world.agents) == 6
    form_id = world.root.data["manifestations"][0]["agent_id"]
    form = world.agents[form_id]
    assert world.root.data["children"][form_id]["parent"] == "brahman"
    assert not world.apply(Intent(form_id, 0, "MOVE", {"dx": 50, "dz": 0}))[0]
    assert "brahman" not in json.dumps(world.observe(form_id)).lower()
    for a in world.agents.values():
        a.thirst = 90
    world.root.sustain(world)
    assert len(world.agents) == 6


def test_reflection_is_private_and_root_survives_restore_replay(tmp_path):
    world = World()
    aid = "agent-0000"
    assert world.apply(Intent(aid, 0, "REFLECT", {"text": "What is experience?"}))[0]
    assert "What is experience?" not in json.dumps(world.events)
    assert "What is experience?" not in json.dumps(world.public())
    world.step()
    restored = World.restore(world.checkpoint(tmp_path))
    assert restored.root.state() == world.root.state()
    assert digest(world.replay(1)) == digest(world.state())
    world.step()
    restored.step()
    assert world.state() == restored.state()


def test_history_endpoint_does_not_expose_root(tmp_path):
    from fastapi.testclient import TestClient
    from caitanya.server import create_app
    world = World()
    client = TestClient(create_app(world, run_dir=tmp_path, live=False))
    assert "root" not in client.get("/api/v1/history?from_tick=0&to_tick=0").json()


def test_committed_journal_recovers_root_and_manifestation(tmp_path):
    world = World()
    world.checkpoint(tmp_path)
    for a in world.agents.values():
        a.hunger = 90
    world.step()
    (tmp_path / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in world.events), encoding="utf-8")
    recovered = World.recover(tmp_path)
    assert recovered.state() == world.state()
    assert len(recovered.root.data["manifestations"]) == 1
