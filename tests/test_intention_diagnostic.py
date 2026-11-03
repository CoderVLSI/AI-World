import json

from caitanya import inference
from caitanya.engine import World
from scripts.intention_diagnostic import capture_request, parser_probes, historical


def test_capture_follows_actual_decide_without_loading_a_model():
    captured = capture_request()
    names = [t['function']['name'] for t in captured['tools']]
    assert captured['observation']['tick'] == 1
    assert captured['observation']['self']['id'] == 'agent-0000'
    assert set(('TRAVEL_TO', 'GATHER_AT', 'REST_FOR')) <= set(names)
    assert captured['messages'][0]['content'] == inference.system_message()
    assert captured['tools'] == inference.select_tools(captured['observation'])
    assert 'body' not in captured['observation']['self']


def test_all_intentions_parse_validate_and_execute_synthetic_mechanical_steps():
    probes = parser_probes()
    assert len(probes) == 3
    assert all(p['accepted'] and p['mechanical_steps_after_one_tick'] > 0 for p in probes)
    assert all(p['tool'] == p['parsed_action'] for p in probes)


def test_historical_read_is_nonmutating_and_does_not_guess_omitted_tool(tmp_path):
    events = [dict(source='validation', type='intent_rejected', actor_id='agent-0001',
                   payload={'reason':'unknown object'},event_id='evt-1',world_tick=5,model_request_id='request-1')]
    path = tmp_path / 'events.jsonl'
    path.write_text(''.join(json.dumps(e)+'\n' for e in events))
    before = path.read_bytes()
    result = historical(tmp_path)
    assert result['rejected_by_agent'] == {'agent-0001':1}
    assert result['rejection_reasons_by_agent']['agent-0001'] == {'unknown object':1}
    assert 'omit' in result['limitation']
    assert path.read_bytes() == before


def test_observed_bad_inspect_subjects_parse_but_fail_world_reference_validation():
    world = World(population=5, width=128, depth=128, wildlife_per_species=6)
    for subject in ('water: renewable', 'water: spawn-water-1'):
        xml = '<tool_call><function=INSPECT><parameter=subject>' + subject + '</parameter></function></tool_call>'
        intent = inference.parse_tool(xml, world.observe('agent-0001'))
        assert intent.parameters == {'subject': subject}
        assert world.apply(intent) == (False, 'unknown object')
