import copy
import pytest
from scripts.audit_evidence import audit


def sample():
    return {'metadata': {'commit_sha': 'a'*40}, 'model_revision': 'b'*40,
            'classification': 'real-model', 'backend': 'TransformersLFM3Backend',
            'model_id': 'LiquidAI/LFM3-1.7B', 'tick_range': [0, 3],
            'inference': {'model_id': 'LiquidAI/LFM3-1.7B', 'model_revision': 'b'*40,
                          'model_instances': 1, 'model_calls': 1,
                          'successful_inference_calls': 1, 'parse_or_inference_failures': 0},
            'actions': [{'event_id': 'evt-000000002', 'tick': 3, 'actor': 'agent-0000',
                         'action': 'wait', 'model_request_id': 'request-1',
                         'confirmed_state': {'before': {}, 'after': {}}}],
            'verified_real_agent_ids': ['agent-0000'],
            'per_agent_validated_model_actions': {'agent-0000': 1}, 'action_counts': {'wait': 1}}


def test_consistent_evidence_is_unchanged():
    data=sample(); before=copy.deepcopy(data)
    assert audit(data)['passed'] and data==before


@pytest.mark.parametrize('mutation', [
    lambda e:e.update(backend='MockInferenceBackend'),
    lambda e:e.update(verified_real_agent_ids=['agent-9999']),
    lambda e:e['inference'].update(successful_inference_calls=9),
    lambda e:e['actions'][0].update(model_request_id=None),
    lambda e:e['actions'][0].update(tick=100),
    lambda e:e['actions'][0].update(confirmed_state={}),
    lambda e:e.update(action_counts={'eat': 1}),
    lambda e:e['metadata'].update(root={'threads': []}),
    lambda e:e['metadata'].update(api_key='redacted-fixture'),
    lambda e:e['actions'][0].update(action='reflect',parameters={'text':'private'}),
    lambda e:e['actions'].append(copy.deepcopy(e['actions'][0])),
    lambda e:e.update(tick_range=[False,3]),
    lambda e:e['inference'].update(model_calls=float('nan')),
    lambda e:e.update(actions='invalid'),
    lambda e:e.update(metadata=[]),
])
def test_inconsistent_or_private_evidence_fails(mutation):
    data=sample(); mutation(data)
    assert not audit(data)['passed']


def test_recovered_session_counter_is_warning_not_false_failure():
    data=sample();data['inference'].update(model_calls=0,successful_inference_calls=0)
    result=audit(data)
    assert result['passed']
    assert any('session' in w for w in result['warnings'])


def test_real_intention_and_mechanical_steps_have_distinct_provenance():
    data = sample()
    data['actions'][0].update(action='travel_to', origin='lfm_decision', task_id='task-1')
    data['actions'].append({'event_id': 'evt-000000003', 'tick': 3, 'actor': 'agent-0000',
                            'action': 'move', 'origin': 'mechanical_execution', 'task_id': 'task-1'})
    data['action_counts'] = {'travel_to': 1, 'move': 1}
    result = audit(data)
    assert result['passed'], result['errors']
    assert result['summary']['mechanical_steps'] == 1
    assert result['summary']['unique_model_requests'] == 1
    data['actions'][1]['task_id'] = 'unknown'
    assert not audit(data)['passed']
