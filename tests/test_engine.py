import copy
import json
from fastapi.testclient import TestClient
from caitanya.engine import World,Intent,digest,FOUNDATION
from caitanya.server import create_app

def test_deterministic_120_ticks_and_resume(tmp_path):
    a,b=World(),World()
    expected_100=None
    for _ in range(120):
        a.step();b.step()
        if a.tick==100:expected_100=a.state()
    assert digest(a.events)==digest(b.events)
    restored=World.restore(a.checkpoint(tmp_path))
    assert digest(a.state())==digest(restored.state())
    for _ in range(20): a.step();restored.step()
    assert digest(a.events)==digest(restored.events)
    assert digest(a.replay(100))==digest(expected_100)
    assert any(e['type']=='move' for e in a.events)
    assert any(e['type']=='gather' for e in a.events)
    assert any(e['type']=='resource_regrowth' for e in a.events)
    assert all(v>=0 for x in a.agents.values() for v in x.inventory.values())

def test_invalid_actions_do_not_mutate():
    w=World();aid=next(iter(w.agents));before=digest(w.state())
    for intent in [Intent(aid,0,'MOVE',{'dx':999,'dz':0}),Intent(aid,0,'GATHER',{'resource_id':'missing'}),
                   Intent(aid,0,'PLACE',{'material':'wood','shape':'block'}),Intent(aid,99,'REST'),
                   {'agent_id':aid,'observed_tick':0,'action':'EXEC','parameters':{'code':'evil'}}]:
        assert not w.apply(intent)[0]
        assert digest(w.state())==before
    assert not w.apply({'agent_id':[],'observed_tick':0,'action':[],'parameters':{}})[0]
    assert digest(w.state())==before

def test_memory_isolation_authorship_and_building():
    w=World();a,b=list(w.agents.values())[:2];b.x,b.z=a.x,a.z
    assert w.apply(Intent(a.id,0,'WRITE',{'title':'A note','text':'The nearby food was useful.'}))[0]
    assert not b.memories
    wid=next(iter(w.works));assert w.works[wid]['creator_agent_id']==a.id
    assert w.apply(Intent(b.id,0,'READ',{'work_id':wid}))[0]
    a.inventory['wood']=4
    assert w.apply(Intent(a.id,0,'PLACE',{'material':'wood','shape':'rod'}))[0]
    before=digest(w.state())
    assert not w.apply(Intent(a.id,0,'PLACE',{'material':'wood','shape':'rod'}))[0]
    assert before==digest(w.state())
    observation=w.observe(a.id)
    assert all('memories' not in other for other in observation['others'])

def test_corruption_detected(tmp_path):
    w=World();p=w.checkpoint(tmp_path);data=json.loads(p.read_text());data['body']['state']['tick']=999;p.write_text(json.dumps(data))
    import pytest
    with pytest.raises(ValueError,match='checksum'):World.restore(p)

def test_read_only_api_and_replay(tmp_path):
    w=World();w.step();client=TestClient(create_app(w,tmp_path,live=False))
    for path in ['/api/v1/health','/api/v1/world/snapshot','/api/v1/world/events','/api/v1/metrics','/api/v1/history?from_tick=1&to_tick=1']:
        assert client.get(path).status_code==200
        assert client.post(path,json={}).status_code==405
    assert client.get('/api/v1/agents/not-found').status_code==404
    assert all('memories' not in a for a in client.get('/api/v1/world/snapshot').json()['agents'].values())
    before=digest(w.state());client.get('/api/v1/history?from_tick=0&to_tick=0');assert digest(w.state())==before
    assert client.get('/api/v1/world/events?after=-1').status_code==400

def test_fifty_identities_share_one_backend():
    w=World(population=50)
    backend=w.backend
    for _ in range(6):w.step()
    assert len(w.agents)==50 and w.backend is backend and backend.calls==100
    assert 'Vedic' not in FOUNDATION and 'worship' not in FOUNDATION
