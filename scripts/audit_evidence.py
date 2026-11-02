"""Offline consistency/privacy audit; does not prove that inference really occurred."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

PRIVATE_KEYS = {'memories', 'parenting_proposals', 'reason_summary', 'root',
                'threads', 'raw_model_output', 'access_token', 'refresh_token',
                'api_key', 'password', 'authorization', 'private_key'}


def audit(data):
    errors = []
    warnings = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def inspect(value, path='$'):
        if isinstance(value, dict):
            for key, child in value.items():
                require(key.lower() not in PRIVATE_KEYS, f'Private field at {path}.{key}')
                inspect(child, f'{path}.{key}')
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, f'{path}[{index}]')
        elif isinstance(value, float):
            require(math.isfinite(value), f'Nonfinite number at {path}')

    if not isinstance(data, dict):
        return {'passed': False, 'errors': ['Evidence must be an object'], 'warnings': []}
    inspect(data)
    metadata = data.get('metadata', {})
    inference = data.get('inference', {})
    require(isinstance(metadata, dict), 'metadata must be an object')
    require(isinstance(inference, dict), 'inference must be an object')
    if not isinstance(metadata, dict) or not isinstance(inference, dict):
        return {'passed': False, 'errors': errors, 'warnings': warnings}
    require(bool(re.fullmatch(r'[0-9a-f]{40}', str(metadata.get('commit_sha', '')))), 'Missing full source SHA')
    require(bool(re.fullmatch(r'[0-9a-f]{40}', str(data.get('model_revision', '')))), 'Missing full model revision')
    ticks = data.get('tick_range')
    valid_ticks = isinstance(ticks, list) and len(ticks) == 2 and all(type(t) is int for t in ticks) and 0 <= ticks[0] <= ticks[1]
    require(valid_ticks, 'Invalid tick range')
    real = data.get('classification') == 'real-model'
    if real:
        require(data.get('backend') == 'TransformersLFM3Backend', 'Real label with incompatible backend')
        require(data.get('model_id') == 'LiquidAI/LFM3-1.7B', 'Real label with wrong model')
        require(inference.get('model_id') == data.get('model_id'), 'Inference model ID mismatch')
        require(inference.get('model_revision') == data.get('model_revision'), 'Inference revision mismatch')
        require(inference.get('model_instances') == 1, 'Expected one shared model instance')
    actions = data.get('actions', [])
    if not isinstance(actions, list):
        return {'passed': False, 'errors': errors + ['actions must be a list'], 'warnings': warnings}
    events, requests, counts, kinds = set(), set(), Counter(), Counter()
    for action in actions:
        if not isinstance(action, dict):
            errors.append('Action must be an object')
            continue
        eid = action.get('event_id')
        require(isinstance(eid, str) and eid.startswith('evt-'), 'Missing action event reference')
        require(isinstance(eid, str) and eid not in events, 'Duplicate or invalid event reference')
        if isinstance(eid, str): events.add(eid)
        tick = action.get('tick')
        require(type(tick) is int and valid_ticks and ticks[0] <= tick <= ticks[1], 'Action outside committed tick range')
        actor, kind = action.get('actor'), action.get('action')
        require(isinstance(actor, str) and bool(actor), 'Invalid actor')
        require(isinstance(kind, str) and bool(kind), 'Invalid action name')
        if isinstance(kind, str): kinds[kind] += 1
        request = action.get('model_request_id')
        if request:
            require(isinstance(request, str) and request not in requests, 'Duplicate or invalid model request ID')
            if isinstance(request, str): requests.add(request)
            if isinstance(actor, str): counts[actor] += 1
        if real:
            require(bool(request), 'Real action lacks a model request ID')
        state = action.get('confirmed_state')
        require(isinstance(state, dict) and all(isinstance(state.get(k), dict) for k in ('before', 'after')), 'Action lacks confirmed before/after state')
        if kind == 'reflect':
            require(action.get('parameters') == {}, 'Private reflection parameters exported')
    expected_ids = sorted(counts) if real else []
    require(data.get('verified_real_agent_ids') == expected_ids, 'Claimed real-agent coverage differs from evidence')
    require(data.get('per_agent_validated_model_actions') == dict(counts), 'Per-agent counts differ from evidence')
    require(data.get('action_counts') == dict(kinds), 'Action totals differ from evidence')
    for key in ('model_calls', 'successful_inference_calls', 'parse_or_inference_failures'):
        require(type(inference.get(key)) is int and inference[key] >= 0, f'Invalid inference counter: {key}')
    if all(type(inference.get(k)) is int for k in ('model_calls', 'successful_inference_calls', 'parse_or_inference_failures')):
        require(inference['model_calls'] == inference['successful_inference_calls'] + inference['parse_or_inference_failures'], 'Inference counters do not reconcile')
        if len(requests) > inference['successful_inference_calls']:
            warnings.append('Action history exceeds session inference count; verify recovery/session boundaries')
    failures = data.get('failure_events', [])
    if failures: warnings.append('Run contains recorded failures; inspect their event references')
    if any(not isinstance(a, dict) for a in actions): warnings.append('Malformed action entries present')
    warnings.append('Consistency checks cannot authenticate model execution or detect every secret inside free text. Review public authored text before publishing.')
    return {'passed': not errors, 'errors': errors, 'warnings': warnings,
            'summary': {'classification': data.get('classification'), 'verified_agents': len(expected_ids),
                        'validated_actions': len(actions), 'unique_model_requests': len(requests),
                        'minimum_actions_per_agent': min(counts.values(), default=0),
                        'maximum_actions_per_agent': max(counts.values(), default=0), 'tick_range': ticks}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    raw = args.evidence.read_bytes()
    try:
        result = audit(json.loads(raw))
    except (ValueError, TypeError, RecursionError) as exc:
        result = {'passed': False, 'errors': [f'Invalid evidence: {exc}'], 'warnings': []}
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        if args.output.resolve() == args.evidence.resolve():
            parser.error('Output must not overwrite input evidence')
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
