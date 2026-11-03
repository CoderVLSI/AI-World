"""Read-only prompt inspection or a bounded, instrumented real-model diagnostic.

Production prompts, tool schemas, parsing, generation settings and world rules are
not changed. Synthetic CPU parser probes are never labeled real inference.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.engine import World, digest
from caitanya import inference

REVISION = 'ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7'
INTENTIONS = ('TRAVEL_TO', 'GATHER_AT', 'REST_FOR')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def capture_request():
    """Stop the actual decide() method before its inference lock; no model loads."""
    class Captured(BaseException):
        pass
    backend = object.__new__(inference.TransformersLFM3Backend)
    backend.model_revision, backend.metadata = REVISION, {}
    world = World(population=5, width=128, depth=128, wildlife_per_species=6, backend=backend)
    result = {}

    def trace(frame, event, arg):
        if frame.f_code is not inference.TransformersLFM3Backend.decide.__code__:
            return None
        if event == 'line' and 'available' in frame.f_locals:
            local = frame.f_locals
            result.update(messages=local['messages'], tools=local['available'], observation=local['observation'])
            raise Captured()
        return trace

    previous_trace = sys.gettrace()
    previous_torch = sys.modules.get('torch')
    if previous_torch is None:
        sys.modules['torch'] = types.ModuleType('torch')  # import only; no tensor/inference call reached
    try:
        sys.settrace(trace)
        try:
            world.step()
        except Captured:
            pass
    finally:
        sys.settrace(previous_trace)
        if previous_torch is None:
            sys.modules.pop('torch', None)
    if not result:
        raise RuntimeError('Did not capture the real prompt-building path')
    return result


def parser_probes():
    """Synthetic XML input tests only; never count these as model choices."""
    results = []
    for action in INTENTIONS:
        world = World(population=5, width=128, depth=128, wildlife_per_species=6)
        a = world.agents['agent-0000']
        candidates = [{'hours': 1}] if action == 'REST_FOR' else (
            [{'x': a.x + dx, 'z': a.z + dz} for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if action == 'TRAVEL_TO' else
            [{'resource_id': n['id'], 'amount': 1} for n in world.observe(a.id)['resources'] if n['amount'] > 0])
        params = next((p for p in candidates if world.scheduler.plan(world, a, action, p)[0] is None), None)
        if params is None:
            raise RuntimeError('No legal synthetic fixture for ' + action)
        xml = '<tool_call><function=' + action + '>' + ''.join(
            f'<parameter={k}>{v}</parameter>' for k, v in params.items()) + '</function></tool_call>'
        intent = inference.parse_tool(xml, world.observe(a.id))
        accepted, reason = world.apply(intent, origin='synthetic_parser_probe')
        world.step()
        mechanical = sum(e.get('origin') == 'mechanical_execution' and e['source'] == 'validated_action'
                         for e in world.events)
        results.append(dict(classification='synthetic CPU parser probe, not model inference', tool=action,
                            xml=xml, parsed_action=intent.action, accepted=accepted, reason=reason,
                            mechanical_steps_after_one_tick=mechanical))
    return results


def cpu(out):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained('LiquidAI/LFM3-1.7B', revision=REVISION, trust_remote_code=True)
    request = capture_request()
    prompt = tokenizer.apply_chat_template(request['messages'], tools=request['tools'], tokenize=False,
        add_generation_prompt=True, enable_thinking=False) + '<tool_call>\n'
    metadata = dict(classification='synthetic CPU request capture; zero model inference calls',
        actor=request['observation']['self']['id'], tick=request['observation']['tick'], revision=REVISION,
        tool_names=[t['function']['name'] for t in request['tools']],
        system_sha256=hashlib.sha256(inference.system_message().encode()).hexdigest(),
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        prompt_tokens=len(tokenizer(prompt, add_special_tokens=False)['input_ids']), parser_probes=parser_probes())
    write_json(out / 'cpu_request.json', request)
    write_json(out / 'cpu_capture.json', metadata)
    (out / 'cpu_prompt.txt').write_text(prompt, encoding='utf-8')
    print('EXACT OFFERED TOOLS\n' + json.dumps(request['tools'], indent=2))
    print('EXACT RENDERED PROMPT\n' + prompt)
    print('CPU DIAGNOSTIC\n' + json.dumps(metadata, indent=2))


def historical(path):
    accepted, rejected, reasons, samples = Counter(), Counter(), {}, []
    with (Path(path) / 'events.jsonl').open(encoding='utf-8') as handle:
        for line in handle:
            e = json.loads(line)
            actor = e.get('actor_id')
            if e['source'] == 'validated_action' and e.get('origin') == 'lfm_decision':
                accepted[actor] += 1
            if e['type'] == 'intent_rejected':
                rejected[actor] += 1
                reasons.setdefault(actor, Counter())[e['payload']['reason']] += 1
                if actor == 'agent-0001' and len(samples) < 5:
                    samples.append(dict(event_id=e['event_id'], tick=e['world_tick'],
                        reason=e['payload']['reason'], request_id=e.get('model_request_id')))
    return dict(validated_by_agent=dict(accepted), rejected_by_agent=dict(rejected),
        rejection_reasons_by_agent={a: dict(c) for a, c in reasons.items()}, agent_0001_rejection_samples=samples,
        limitation='Historical rejection events omit attempted tool name and parameters; do not invent missing subjects.')


def gpu(out, ticks, seconds, historical_run):
    if not 1 <= ticks <= 50 or not 0 < seconds <= 600:
        raise ValueError('Diagnostic limits: 1–50 ticks and at most 600 simulation seconds')
    source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    backend = inference.TransformersLFM3Backend(revision=REVISION)
    world = World(population=5, width=128, depth=128, wildlife_per_species=6, backend=backend)
    original_select, original_decide = inference.select_tools, backend.decide
    original_decode, original_apply = backend.tokenizer.decode, world.apply
    picks, offers, raw_names, attempts = Counter(), Counter(), Counter(), []
    current = {}

    def observe_tools(observation):
        tools = original_select(observation)
        current['offered_tools'] = [t['function']['name'] for t in tools]
        offers.update(current['offered_tools'])
        a = observation['self']
        current['inspectable_subjects'] = (['inventory:' + k for k, v in a['inventory'].items() if v > 0]
            + [n['id'] for n in observation['resources'] if abs(n['x']-a['x'])+abs(n['z']-a['z']) <= 1]
            + [o['id'] for o in observation.get('objects', [])
               if o.get('held') or abs(o['x']-a['x'])+abs(o['z']-a['z']) <= 1])
        current['visible_resource_ids'] = [n['id'] for n in observation['resources']]
        return tools  # exact original objects, order, descriptions and parameters

    def observe_decode(*args, **kwargs):
        text = original_decode(*args, **kwargs)
        names = re.findall(r'<function=([A-Z_]+)>', text)
        raw_names.update(names)
        current['raw_tool_names'] = names
        return text  # original bytes are passed to the original parser

    def observe_decide(observation):
        current.clear()
        current.update(actor=observation['self']['id'], tick=observation['tick'])
        try:
            intent = original_decide(observation)
            picks[intent.action] += 1
            current['tool'] = intent.action
            # Public action references only; never export speech, reflections or memory text.
            current['parameters'] = {k: v for k, v in intent.parameters.items()
                if k in {'subject', 'resource_id', 'object_id', 'x', 'z', 'dx', 'dz', 'amount', 'hours', 'reconsider_hours'}
                and (k != 'subject' or intent.action == 'INSPECT')}
            return intent
        except inference.InferenceFailure as exc:
            current['parse_or_inference_error'] = str(exc)
            raise
        finally:
            current['request_id'] = backend.last_request.get('request_id')
            attempts.append(dict(current))

    def observe_apply(raw, **kwargs):
        outcome = original_apply(raw, **kwargs)
        if kwargs.get('request_id') and attempts and attempts[-1]['request_id'] == kwargs['request_id']:
            attempts[-1].update(accepted=outcome[0], validation_reason=outcome[1])
        return outcome

    inference.select_tools, backend.decide = observe_tools, observe_decide
    backend.tokenizer.decode, world.apply = observe_decode, observe_apply
    world.checkpoint(out)
    cursor, started = len(world.events), time.monotonic()
    try:
        with (out / 'events.jsonl').open('x', encoding='utf-8') as journal:
            for _ in range(ticks):
                world.step()
                for event in world.events[cursor:]:
                    journal.write(json.dumps(event, separators=(',', ':')) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
                cursor = len(world.events)
                write_json(out / 'diagnostic_progress.json', dict(tick=world.tick, calls=backend.calls,
                    picked_tools=dict(picks), real_seconds=time.monotonic()-started))
                if time.monotonic() - started >= seconds:
                    break
        world.checkpoint(out)
    finally:
        inference.select_tools, backend.decide = original_select, original_decide
        backend.tokenizer.decode, world.apply = original_decode, original_apply
    all_names = [t['function']['name'] for t in inference.TOOLS]
    record = dict(classification='short diagnostic, genuine real-model inference; not a civilization benchmark',
        commit_sha=source_sha, model_id=backend.model_id, model_revision=backend.model_revision,
        backend=type(backend).__name__, population=5, requested_max_ticks=ticks, completed_ticks=world.tick,
        requested_max_seconds=seconds, real_seconds=time.monotonic()-started, inference=backend.metrics(),
        tool_pick_counts={n: picks[n] for n in all_names}, tool_offer_counts={n: offers[n] for n in all_names},
        raw_tool_name_counts=dict(raw_names), attempts=attempts,
        scheduler=world.scheduler.report(world),
        validation_counts=dict(Counter(str(a.get('accepted', 'parse_failed')) for a in attempts)),
        protected_system_sha256=hashlib.sha256(inference.system_message().encode()).hexdigest())
    if historical_run:
        record['historical_stage_a'] = historical(historical_run)
    recovered = World.recover(out, backend=backend)
    record['recovery_equal'] = digest(world.state()) == digest(recovered.state())
    write_json(out / 'SHORT_DIAGNOSTIC.json', record)
    print(json.dumps({k:v for k,v in record.items() if k != 'attempts'}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['cpu', 'gpu'], required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--ticks', type=int, default=20)
    parser.add_argument('--max-seconds', type=float, default=300)
    parser.add_argument('--historical-run')
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=False)  # never reuse a directory or overwrite existing evidence
    if args.mode == 'cpu':
        cpu(out)
    else:
        gpu(out, args.ticks, args.max_seconds, args.historical_run)


if __name__ == '__main__':
    main()
