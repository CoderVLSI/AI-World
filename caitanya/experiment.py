"""Evidence exports from committed events only; never export private memories."""
import collections
import json
import subprocess
from pathlib import Path


def source_revision():
    return subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()


def summarize(world, directory, metadata):
    """Caller must stop the worker first. Metrics are session scoped unless noted."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    commits=[e for e in world.events if e['type']=='tick_committed']
    last=commits[-1]['world_tick'] if commits else 0
    events=[e for e in world.events if e['world_tick']<=last and e['type']!='tick_committed']
    actions=[e for e in events if e['source']=='validated_action']
    public_actions=[dict(event_id=e['event_id'],tick=e['world_tick'],actor=e['actor_id'],
        action=e['type'],model_request_id=e.get('model_request_id'),origin=e.get('origin','direct'),
        task_id=e.get('task_id',e['payload'].get('task_id')),
        parameters={} if e['type']=='reflect' else e['payload'].get('parameters',{}),
        outcome=e['payload'].get('outcome'),confirmed_state=e['payload'].get('confirmed_state',{})) for e in actions]
    counts=collections.Counter(e['actor_id'] for e in actions if e.get('model_request_id') and e.get('origin')!='mechanical_execution')
    real=world.manifest['model_id']=='LiquidAI/LFM3-1.7B' and type(world.backend).__name__=='TransformersLFM3Backend'
    evidence={'metadata':metadata,'model_id':world.manifest['model_id'],
        'model_revision':world.manifest['model_revision'],'backend':type(world.backend).__name__,
        'classification':'real-model' if real else 'mock-or-test',
        'tick_range':[0,last],'starting_population':len(world.initial_state['agents']),
        'ending_population':sum(a.alive for a in world.agents.values()),
        'births':sum(e['type']=='birth' for e in events),'deaths':sum(e['type']=='death' for e in events),
        'highest_generation':max(a.generation for a in world.agents.values()),
        'root_mode':world.root.data['mode'],'seed':world.seed,'width':world.width,'depth':world.depth,
        'biology':world.manifest['biology'],'inference':world.backend.metrics() if hasattr(world.backend,'metrics') else {},
        'verified_real_agent_ids':sorted(counts) if real else [],'per_agent_validated_model_actions':dict(counts),
        'action_counts':dict(collections.Counter(e['type'] for e in actions)),
        'failure_events':[{'event_id':e['event_id'],'tick':e['world_tick'],'type':e['type'],
                           'reason':e['payload'].get('reason',e['payload'].get('error'))}
                          for e in events if e['type'] in {'intent_rejected','inference_failed'}],
        'actions':public_actions,'works':list(world.works.values()),'objects':list(world.parts.values())}
    # These exports include public authored content, never reflection text/reason summaries,
    # observations, root threads, parenting proposals, private memories or raw model output.
    (directory/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    lines=['# Experiment report', '',f"Classification: **{evidence['classification']}**.",
           '', '## Configuration and results','', '```json',json.dumps({k:v for k,v in evidence.items()
             if k not in {'actions','works','objects','failure_events'}},indent=2),'```','',
           '## Recorded actions','', 'Each row references a validated event. Private reflection contents are omitted.','']
    for event in public_actions:
        lines.append('- '+json.dumps(event,ensure_ascii=True))
    lines+=['','## Authored works and construction','','```json',json.dumps({'works':evidence['works'],'objects':evidence['objects']},indent=2),'```',
            '','## Failures','','```json',json.dumps(evidence['failure_events'],indent=2),'```','',
            '## Interpretation','',
            'No cultural or philosophical milestone is inferred automatically. Inspect original public text and event provenance before making a claim. A short benchmark does not establish survival, collaboration or civilization. Model pretraining confounds independent-discovery claims.','',
            '## Acceptance checks','',json.dumps(metadata.get('acceptance',{}),indent=2)]
    (directory/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return evidence


