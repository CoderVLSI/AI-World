import copy
import json

import pytest

from caitanya.engine import World
from caitanya.experiment import summarize
from caitanya.server import build_parser, build_world
from scripts.audit_evidence import audit
from fastapi.testclient import TestClient
from caitanya.server import create_app


def test_foundations_export_audits_mechanical_tasks_without_private_state(tmp_path):
    world = World(population=5, wildlife_per_species=1)
    for _ in range(60):
        world.step()
    evidence = summarize(world, tmp_path, {'commit_sha': 'a' * 40})
    result = audit(evidence)
    assert result['passed'], result['errors']
    mechanical = [a for a in evidence['actions'] if a['origin'] == 'mechanical_execution']
    assert mechanical
    assert result['summary']['mechanical_steps'] == len(mechanical)
    assert evidence['verified_real_agent_ids'] == []
    assert all(not a['model_request_id'] and a['task_id'] for a in mechanical)
    assert all(not a['action'].startswith('wildlife_') for a in evidence['actions'])
    assert any(e['source'] == 'deterministic_ecology' for e in world.events)
    broken = copy.deepcopy(evidence)
    next(a for a in broken['actions'] if a['origin'] == 'mechanical_execution')['task_id'] = 'unknown'
    assert not audit(broken)['passed']
    encoded = json.dumps(evidence)
    assert all('"' + key + '"' not in encoded for key in ('ltm', 'memories', 'scheduler', 'root', 'rng_state'))


def test_coarse_legacy_clock_requires_explicitly_disabling_wildlife():
    parser = build_parser()
    args = parser.parse_args(['--legacy', '--days-per-tick', '365'])
    with pytest.raises(ValueError, match='wildlife-per-species 0'):
        build_world(args, parser)
    args = parser.parse_args(['--legacy', '--days-per-tick', '365', '--wildlife-per-species', '0'])
    assert build_world(args, parser).fauna is None


def test_wildlife_observations_are_bounded_and_optional():
    assert 'wildlife' not in World().observe('agent-0000')
    world = World(wildlife_per_species=4)
    human = world.agents['agent-0000']
    for animal in world.fauna.animals.values():
        animal.x, animal.z = human.x, human.z
    observation = world.observe(human.id)['wildlife']
    assert len(observation) == 12
    assert all(set(a) == {'id', 'species', 'x', 'z', 'behavior'} for a in observation)


def test_public_endpoints_hide_private_state_with_fauna(tmp_path):
    world = World(wildlife_per_species=1)
    world.step()
    client = TestClient(create_app(world, run_dir=tmp_path, live=False))

    def check(value):
        if isinstance(value, dict):
            assert not ({'ltm', 'memories', 'parenting_proposals', 'root', 'rng_state'} & value.keys())
            # A public scheduler metrics aggregate is allowed; private agent records are not.
            assert not ('agents' in value and 'totals' in value)
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    for path in ('world/snapshot', 'world/events', 'agents/agent-0000', 'history?from_tick=1&to_tick=1',
                 'wildlife', 'scheduler', 'knowledge', 'objects', 'families', 'metrics'):
        response = client.get('/api/v1/' + path)
        assert response.status_code == 200
        check(response.json())
        assert client.post('/api/v1/' + path, json={}).status_code == 405
