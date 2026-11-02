import copy
import pytest
from caitanya.engine import World,Intent,digest
from caitanya.nature import geography,RESOURCE_TYPES
from caitanya.inference import parse_tool,InferenceFailure

def test_human_traits_and_larger_ecology(tmp_path):
    w=World(width=256,depth=256)
    assert len(w.terrain)==1024
    assert len({t['biome'] for t in w.terrain})==6
    assert set(RESOURCE_TYPES)=={n['kind'] for n in w.resources.values()}
    assert {a.gender for a in w.agents.values()}=={'woman','man','nonbinary'}
    for a in w.agents.values():
        assert len(a.body['parts'])==42 and 'digestive' in a.body['systems']
        assert geography(a.x,a.z,w.width,w.depth,w.seed)['walkable']
    a=next(iter(w.agents.values()));a.thirst=50
    assert w.apply(Intent(a.id,0,'DRINK'))[0] and a.thirst==15
    restored=World.restore(w.checkpoint(tmp_path))
    assert digest(w.state())==digest(restored.state())

def test_minerals_do_not_regrow_and_water_blocks_movement():
    w=World();mineral=next(n for n in w.resources.values() if not n.get('renewable',True))
    mineral['amount']=0
    for _ in range(12):w.step()
    assert mineral['amount']==0
    a=next(iter(w.agents.values()))
    edge=next((x,z,dx,dz) for x in range(1,w.width-1) for z in range(4,w.depth-1)
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]
        if geography(x,z,w.width,w.depth,w.seed)['walkable'] and not geography(x+dx,z+dz,w.width,w.depth,w.seed)['walkable'])
    a.x,a.z,dx,dz=edge;before=digest(w.state())
    assert not w.apply(Intent(a.id,w.tick,'MOVE',{'dx':dx,'dz':dz}))[0]
    assert digest(w.state())==before

def test_official_xml_tool_parsing_and_spoof_rejection():
    obs=World().observe('agent-0000')
    intent=parse_tool('<tool_call><function=MOVE><parameter=dx>1</parameter><parameter=dz>0</parameter></function></tool_call>',obs)
    assert intent.agent_id=='agent-0000' and intent.parameters=={'dx':1,'dz':0}
    for text in ['{"action":"MOVE"}', '<tool_call><function=EXEC></function></tool_call>',
        '<tool_call><function=MOVE><parameter=dx>__import__("os")</parameter><parameter=dz>0</parameter></function></tool_call>',
        '<tool_call><function=REST><parameter=agent_id>other</parameter></function></tool_call>']:
        with pytest.raises(InferenceFailure):parse_tool(text,obs)

def test_inference_failure_never_uses_mock_fallback():
    class Failed:
        model_id='unavailable-model';model_revision='test'
        def decide(self,observation):raise InferenceFailure('offline')
    w=World(backend=Failed())
    before={k:(a.x,a.z,copy.deepcopy(a.inventory)) for k,a in w.agents.items()}
    for _ in range(3):w.step()
    assert len(w.rejections)==5
    assert all((a.x,a.z,a.inventory)==before[k] for k,a in w.agents.items())
    assert all(e['source']!='validated_action' for e in w.events)
