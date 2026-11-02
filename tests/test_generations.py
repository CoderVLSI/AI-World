"""Explicit test-harness proposals; these tests do not claim autonomous births."""
import pytest
from caitanya.engine import World, Intent, digest
from caitanya.lifecycle import BiologyConfig, age

def family_world():
    # Accelerated fixture clocks are recorded and never used as baseline biology.
    w=World(population=4,biology=BiologyConfig(days_per_tick=365,gestation_days=365,recovery_days=365))
    adults=list(w.agents.values())
    for i,a in enumerate(adults):
        a.x,a.z=adults[0].x,adults[0].z
        a.age_years_at_start=25;a.lifespan_years=95
        a.reproductive_roles=['gestate'] if i%2==0 else ['contribute']
        a.inventory['food']=20;a.inventory['water']=20
        a.gender=['nonbinary','woman','man','nonbinary'][i]
    return w,adults

def propose(w,a,b):return w.apply(Intent(a.id,w.tick,'REPRODUCE',{'target_id':b.id}))

def test_mutual_participation_resource_cost_and_withdrawal():
    w,adults=family_world();a,b=adults[:2]
    assert propose(w,a,b)[0] and not w.pregnancies and a.inventory['food']==20
    assert w.apply(Intent(a.id,0,'WITHDRAW_CONSENT',{'target_id':b.id}))[0]
    assert propose(w,b,a)[0] and not w.pregnancies
    assert propose(w,a,b)[0] and len(w.pregnancies)==1
    assert a.inventory['food']==18 and b.inventory['water']==18
    before=digest(w.state());assert not propose(w,a,b)[0];assert before==digest(w.state())

def test_age_resources_capability_and_close_kin_rejected_without_mutation():
    for mutate in [lambda a,b:setattr(a,'age_years_at_start',17),lambda a,b:a.inventory.update(food=0),
        lambda a,b:setattr(a,'reproductive_roles',['contribute']),lambda a,b:setattr(b,'parent_ids',[a.id]),
        lambda a,b:setattr(b,'x',a.x+10)]:
        w,adults=family_world();a,b=adults[:2];mutate(a,b);before=digest(w.state())
        assert not propose(w,a,b)[0] and before==digest(w.state())

def test_birth_growth_care_teaching_and_two_generations_resume(tmp_path):
    w,adults=family_world();a,b,c,d=adults
    a.memories.append({'secret':'not inherited'});a.knowledge.append({'topic':'private','text':'not automatically inherited'})
    for first,second in [(a,b),(c,d)]:assert propose(w,first,second)[0];assert propose(w,second,first)[0]
    w.step();children=[x for x in w.agents.values() if x.generation==1]
    assert len(children)==2 and len(w.agents)==6
    child=children[0];assert child.memories==[] and child.knowledge==[] and child.inventory['food']==0
    assert child.height_cm==50 and child.parent_ids==[b.id,a.id]
    child.hunger=50;child.thirst=50
    assert w.apply(Intent(a.id,w.tick,'CARE',{'target_id':child.id}))[0]
    assert child.hunger==20 and child.thirst==15
    assert not w.apply(Intent(child.id,w.tick,'REPRODUCE',{'target_id':c.id}))[0]
    restored=World.restore(w.checkpoint(tmp_path));assert digest(w.state())==digest(restored.state())
    for _ in range(3):w.step();restored.step()
    assert digest(w.state())==digest(restored.state()) and age(w,child)==3
    assert w.apply(Intent(a.id,w.tick,'TEACH',{'target_id':child.id,'topic':'field-note','text':'The food near the clearing can be gathered.'}))[0]
    assert child.knowledge[-1]['teacher_id']==a.id
    for _ in range(15):w.step()
    assert age(w,child)==18 and child.height_cm==child.adult_height_cm
    for i,kid in enumerate(children):
        kid.x,kid.z=a.x,a.z;kid.reproductive_roles=['gestate'] if i==0 else ['contribute']
        kid.health=100;kid.hunger=0;kid.thirst=0;kid.energy=100
        kid.inventory.update(food=8,water=8)
    assert propose(w,*children)[0] and propose(w,*children[::-1])[0]
    w.step()
    assert any(k.generation==2 for k in w.agents.values())
    assert sum(e['type']=='birth' for e in w.events)==3
    assert w.metrics()['highest_generation']==2

def test_authored_revisions_and_parental_care_conserve_resources():
    w,adults=family_world();a,b=adults[:2]
    assert w.apply(Intent(a.id,0,'WRITE',{'title':'Observations','text':'First observation.'}))[0]
    wid=next(iter(w.works))
    assert not w.apply(Intent(b.id,0,'REVISE',{'work_id':wid,'text':'Not mine.'}))[0]
    assert w.apply(Intent(a.id,0,'REVISE',{'work_id':wid,'text':'Revised observation.'}))[0]
    assert w.works[wid]['revision']==2 and w.works[wid]['history'][0]['text']=='First observation.'
    total=a.inventory['water']+b.inventory['water']
    assert w.apply(Intent(a.id,0,'GIVE',{'target_id':b.id,'resource':'water','amount':3}))[0]
    assert a.inventory['water']+b.inventory['water']==total

def test_aging_death_and_invalid_time_parameters():
    w,adults=family_world();adults[0].lifespan_years=26
    w.step();assert not adults[0].alive
    assert any(e['type']=='death' and e['payload']['cause']=='aging' for e in w.events)
    for value in [0,-1,float('nan'),float('inf')]:
        with pytest.raises(ValueError):BiologyConfig(days_per_tick=value)

def test_birth_scheduler_is_not_a_population_cap():
    w,adults=family_world()
    w.biology=BiologyConfig(days_per_tick=365,gestation_days=365,recovery_days=365,max_births_per_tick=1)
    for a,b in [(adults[0],adults[1]),(adults[2],adults[3])]:propose(w,a,b);propose(w,b,a)
    w.step();assert w.metrics()['births']==1 and len(w.pregnancies)==1
    w.step();assert w.metrics()['births']==2 and not w.pregnancies
    assert len(World(population=201).agents)==201

def test_delta_history_roundtrip_and_public_feed_hides_private_memory(tmp_path):
    from fastapi.testclient import TestClient
    from caitanya.server import create_app
    w=World();a=next(iter(w.agents.values()));a.memories.append({'secret':'private note'})
    for _ in range(30):w.step()
    assert 'patch' in w.events[-1]['payload'] and 'state' not in w.events[-1]['payload']
    assert digest(w.replay(30))==digest(w.state())
    restored=World.restore(w.checkpoint(tmp_path));w.step();restored.step()
    assert digest(w.events)==digest(restored.events)
    response=TestClient(create_app(w,tmp_path/'api',live=False)).get('/api/v1/world/events')
    assert 'private note' not in response.text and '"patch"' not in response.text
