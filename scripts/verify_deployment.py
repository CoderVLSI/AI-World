"""Read-only deployment acceptance probe. Never loads a model or edits the world."""
import argparse
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError


def probe(base_url):
    def get(path):
        with urlopen(base_url.rstrip('/')+path,timeout=15) as response:
            return json.load(response)
    health=get('/api/v1/health')
    snapshot=get('/api/v1/world/snapshot')
    metrics=get('/api/v1/metrics')
    manifest=snapshot['manifest']
    inference=metrics.get('inference',{})
    request=Request(base_url.rstrip('/')+'/api/v1/world/snapshot',data=b'{}',
                    headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(request,timeout=15) as response:post_status=response.status
    except HTTPError as exc:post_status=exc.code
    before=snapshot['tick']
    history=get(f'/api/v1/history?from_tick={before}&to_tick={before}')
    with urlopen(base_url.rstrip('/')+'/viewer',timeout=15) as response:viewer_status=response.status
    checks={
        'backend_is_lfm3':health.get('mode')=='TransformersLFM3Backend',
        'model_is_text_lfm3':manifest.get('model_id')=='LiquidAI/LFM3-1.7B',
        'revision_matches':bool(manifest.get('model_revision')) and manifest.get('model_revision')==inference.get('model_revision'),
        'single_model_instance':inference.get('model_instances')==1,
        'successful_inference_observed':inference.get('successful_inference_calls',0)>0,
        'snapshot_hides_root': 'root' not in snapshot,
        'history_hides_root':'root' not in history,
        'agents_hide_memories':all('memories' not in a and 'parenting_proposals' not in a for a in snapshot['agents'].values()),
        'snapshot_rejects_post':post_status==405,
        'viewer_available':viewer_status==200,
    }
    return {'checks':checks,'passed':all(checks.values()),'tick':before,
            'model_id':manifest.get('model_id'),'revision':manifest.get('model_revision'),
            'inference':inference,
            'limitations':['Successful calls do not establish a validated action for every inhabitant.',
                          'This probe does not establish Drive persistence or recovery after runtime replacement.',
                          'This probe checks the snapshot POST route, not every possible HTTP method.']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('base_url');p.add_argument('--output')
    args=p.parse_args()
    result=probe(args.base_url)
    text=json.dumps(result,indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text+'\n',encoding='utf-8')
    print(text)
    raise SystemExit(0 if result['passed'] else 1)
