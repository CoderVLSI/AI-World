import json
import pytest
from fastapi.testclient import TestClient
from caitanya.engine import World, digest
from caitanya.server import create_app


@pytest.mark.parametrize("mode", ["off", "observe", "crisis"])
def test_modes_replay_checkpoint_and_journal_recovery(mode, tmp_path):
    world=World(root_mode=mode)
    world.checkpoint(tmp_path)
    for a in world.agents.values(): a.hunger=90
    for _ in range(3): world.step()
    assert bool(world.root.data["manifestations"]) == (mode=="crisis")
    assert bool(world.root.data["children"]) == (mode!="off")
    assert world.replay(3)==world.state()
    (tmp_path/"events.jsonl").write_text(''.join(json.dumps(e)+'\n' for e in world.events),encoding='utf-8')
    recovered=World.recover(tmp_path)
    assert recovered.state()==world.state()
    restored=World.restore(world.checkpoint(tmp_path))
    restored.step();world.step();recovered.step()
    assert restored.state()==world.state()==recovered.state()
    client=TestClient(create_app(world,run_dir=tmp_path,live=False))
    before=digest(world.state())
    assert client.get('/viewer').status_code==200
    assert client.post('/api/v1/world/snapshot',json={}).status_code==405
    assert 'root' not in client.get('/api/v1/world/snapshot').json()
    assert 'root' not in client.get('/api/v1/history?from_tick=3&to_tick=3').json()
    assert digest(world.state())==before


def test_invalid_mode():
    with pytest.raises(ValueError):World(root_mode='revelation')


def test_export_omits_private_data_and_never_labels_mock_as_real(tmp_path):
    from caitanya.engine import Intent
    from caitanya.experiment import summarize
    w=World()
    w.apply(Intent('agent-0000',0,'REFLECT',{'text':'PRIVATE-REFLECTION'}))
    w.step()
    result=summarize(w,tmp_path,{'commit_sha':'test'})
    text=(tmp_path/'evidence.json').read_text()
    assert 'PRIVATE-REFLECTION' not in text
    assert 'continuity-' not in text and 'memories' not in text
    assert result['classification']=='mock-or-test'
    assert result['verified_real_agent_ids']==[]
