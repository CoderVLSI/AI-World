import copy
import json
from fastapi.testclient import TestClient
from caitanya.engine import World
from fauna.ecology import Ecosystem,SPECIES
from fauna.preview import create_preview

def test_species_habitats_and_deterministic_restore(tmp_path):
    world=World(width=64,depth=64);eco=Ecosystem(world,per_species=2)
    assert len(eco.animals)==24
    assert {d['group'] for d in SPECIES.values()}=={'mammal','bird','fish','insect'}
    for _ in range(12):eco.step(world)
    clone=World.restore(world.checkpoint(tmp_path))
    restored=Ecosystem.restore(json.loads(json.dumps(eco.state())))
    for _ in range(12):eco.step(world);restored.step(clone)
    assert eco.state()==restored.state()
    assert world.resources==clone.resources
    assert all(eco.allowed(world,a.species,a.x,a.z) for a in eco.animals.values())
    assert all(n['amount']>=0 for n in world.resources.values())

def test_feeding_conserves_resources_and_predation_is_recorded():
    world=World();eco=Ecosystem(world,per_species=0)
    resource=next(n for n in world.resources.values() if n['kind']=='herbs' and eco.allowed(world,'rabbit',n['x'],n['z']))
    rabbit=eco.spawn('rabbit',resource['x'],resource['z'],'male',200);rabbit.energy=50
    before=resource['amount'];eco.step(world)
    assert resource['amount']==before-1
    assert eco.events[-1]['type']=='feeding'
    wolf=eco.spawn('wolf',rabbit.x,rabbit.z,'male',400);wolf.energy=40
    # Place prey into the same tile after the escape pass: ordering tests a validated predation outcome.
    eco.animals={wolf.id:wolf,rabbit.id:rabbit};eco.step(world)
    assert not rabbit.alive
    assert any(e['type']=='predation' and e['prey_id']==rabbit.id for e in eco.events)

def test_animal_births_are_budgeted_and_aging_and_starvation_exist():
    world=World();eco=Ecosystem(world,per_species=0,birth_budget=1)
    x,z=next((x,z) for x in range(world.width) for z in range(world.depth) if eco.allowed(world,'rabbit',x,z))
    for sex in ['female','female','male']:eco.spawn('rabbit',x,z,sex,200).energy=100
    eco.step(world)
    assert sum(e['type']=='birth' for e in eco.events)==1
    child=next(a for a in eco.animals.values() if a.parent_ids)
    assert len(child.parent_ids)==2 and child.age_days==0
    elder=eco.spawn('rabbit',x,z,'male',SPECIES['rabbit']['life'])
    eco.step(world);assert not elder.alive
    hungry=eco.spawn('rabbit',x,z,'male',200);hungry.energy=0;hungry.health=.1
    world.resources={};eco.step(world);assert not hungry.alive

def test_preview_is_read_only_and_discloses_its_independent_mode():
    client=TestClient(create_preview())
    assert client.get('/').status_code==200
    data=client.get('/api/wildlife').json()
    assert len(data['species'])==12 and 'not connected' in data['mode']
    assert client.post('/api/wildlife',json={}).status_code==405
    assert 'root' not in data
