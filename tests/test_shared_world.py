import json
from fastapi.testclient import TestClient
from caitanya.engine import World, digest
from caitanya.server import create_app

def test_humans_and_animals_share_state_time_and_recovery(tmp_path):
    world=World(population=5,wildlife_per_species=2)
    assert len(world.agents)==5 and len(world.fauna.animals)==24
    world.checkpoint(tmp_path)
    for _ in range(6):world.step()
    assert world.fauna.tick==world.tick
    assert world.fauna.days_per_tick==world.biology.days_per_tick
    (tmp_path/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in world.events),encoding='utf-8')
    recovered=World.recover(tmp_path)
    restored=World.restore(world.checkpoint(tmp_path))
    assert world.state()==world.replay(6)==recovered.state()==restored.state()
    for w in (world,recovered,restored):w.step()
    assert world.state()==recovered.state()==restored.state()
    public=world.public()
    assert len(public['agents'])==5 and len(public['wildlife']['animals'])>=24
    assert 'fauna' not in public and 'rng_state' not in public['wildlife'] and 'root' not in public
    client=TestClient(create_app(world,run_dir=tmp_path,live=False))
    historical=client.get('/api/v1/history?from_tick=6&to_tick=6').json()
    assert 'wildlife' in historical and 'fauna' not in historical
    assert client.post('/api/v1/world/snapshot',json={}).status_code==405
    assert client.get('/fauna/').status_code==200
    assert client.get('/api/v1/wildlife').json()['tick']==world.tick
    assert client.post('/api/v1/wildlife',json={}).status_code==405

def test_animals_are_local_observations_and_consume_shared_resources():
    world=World(wildlife_per_species=1)
    human=world.agents['agent-0000']
    animal=next(a for a in world.fauna.animals.values() if a.species=='rabbit')
    human.x,human.z=animal.x,animal.z
    world.resources['shared-herbs']={'id':'shared-herbs','x':animal.x,'z':animal.z,'kind':'herbs','amount':2,'capacity':2,'renewable':False}
    animal.energy=40
    assert any(b['id']==animal.id for b in world.observe(human.id)['wildlife'])
    world.step()
    assert world.resources['shared-herbs']['amount']==1
    assert any(e['type']=='wildlife_feeding' and e['payload'].get('resource_id')=='shared-herbs' for e in world.events)
    assert all(a.alive for a in world.agents.values())

def test_legacy_checkpoint_does_not_silently_gain_animals(tmp_path):
    old=World();old.step();saved=old.checkpoint(tmp_path)
    restored=World.restore(saved)
    assert restored.fauna is None and 'fauna' not in restored.state()
    assert digest(old.state())==digest(restored.state())
