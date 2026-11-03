"""Fixed far-water fixture; scripted CPU comparison or ONE hard-capped GPU episode.

Only diagnostic setup changes: positions, initial thirst/carried water, water
nodes and an explicitly seeded prior observation. Production rules are inherited.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.engine import World, Intent, MOCK_MODEL_ID, digest
from caitanya.memory import note_surroundings
from caitanya.nature import geography, RESOURCE_TYPES
from scripts import intention_diagnostic as baseline

START = (8, 24)
WATER = (23, 24)
WATER_ID = 'resource-9999'
FOCAL = 'agent-0000'
TRACKED = ('TRAVEL_TO', 'GATHER_AT', 'REST_FOR', 'MOVE')


def save(path, data):
    path.write_bytes((json.dumps(data, indent=2, sort_keys=True) + '\n').encode())


class FarWaterWorld(World):
    """Scenario initialization only; no step/observe/apply/rule overrides."""
    def __init__(self, **kwargs):
        super().__init__(**(dict(population=5, width=128, depth=128, wildlife_per_species=6) | kwargs))
        assert len(self.agents) == 5 and self.seed == 314159
        assert all(geography(x, 24, self.width, self.depth, self.seed)['walkable'] for x in range(8, 24))
        self.resources = {k:v for k,v in self.resources.items() if v['kind'] != 'water'}
        capacity = RESOURCE_TYPES['water'][1]
        self.resources[WATER_ID] = dict(id=WATER_ID, x=WATER[0], z=WATER[1], kind='water',
                                       amount=capacity, capacity=capacity, renewable=True)
        for a in self.agents.values():
            a.inventory['water'] = 0
            a.thirst = 90 if a.id == FOCAL else 0
            # Explicit synthetic prehistory: normal memory code observes an actual
            # node while at it. No invented navigation instruction or tool preference.
            a.x, a.z = WATER
            note_surroundings(self, a)
            a.x, a.z = START
        self.manifest['diagnostic_scenario'] = 'far-water-known-location-v1'
        self.initial_state = self.state()
        self._last_committed_state = copy.deepcopy(self.initial_state)
        self.fixture_fingerprint = digest({k:v for k,v in self.state().items() if k != 'manifest'})


def fixture_metadata(world):
    obs = world.observe(FOCAL)
    nearest_terrain = min(abs(x-START[0])+abs(z-START[1])
        for x in range(world.width) for z in range(world.depth)
        if geography(x,z,world.width,world.depth,world.seed)['biome'] == 'water')
    return dict(version='far-water-known-location-v1', seed=world.seed, population=5,
        focal_agent=FOCAL, start=list(START), water=list(WATER), water_id=WATER_ID,
        nearest_water_resource_distance=min(abs(n['x']-START[0])+abs(n['z']-START[1])
            for n in world.resources.values() if n['kind']=='water' and n['amount']>0),
        nearest_natural_water_terrain_distance=nearest_terrain,
        initial_focal_thirst=90, other_agents_initial_thirst=0, all_initial_carried_water=0,
        initial_water_visible=any(n['kind']=='water' for n in obs['resources']),
        knowledge='Explicit fixture prehistory: normal note_surroundings at water, then relocated to start; not a discovery.',
        focal_recalled_places=[r['text'] for r in obs['recalled'] if r['kind']=='place'],
        root_mode=world.root.data['mode'], autonomy=world.autonomy.to_dict(),
        fixture_fingerprint=world.fixture_fingerprint)


class ScriptedWaterPolicy:
    model_id = MOCK_MODEL_ID
    model_revision = 'scripted-far-water-v1'
    def __init__(self, strategy):
        self.strategy, self.calls = strategy, Counter()

    def decide(self, obs):
        a = obs['self']
        self.calls[a['id']] += 1
        action, params = 'WAIT', {}
        if a['id'] == FOCAL:
            if a['inventory']['water']:
                action = 'DRINK'
            else:
                local = next((n for n in obs['resources'] if n['kind']=='water' and n['amount']>0
                              and (n['x'],n['z'])==(a['x'],a['z'])), None)
                if local:
                    action, params = 'GATHER', {'resource_id':local['id']}
                else:
                    place = next(r['text'] for r in obs['recalled'] if r['kind']=='place' and r['text'].startswith('water '))
                    x,z = map(int, re.search(r'x=(\d+), z=(\d+)',place).groups())
                    if self.strategy == 'TRAVEL_TO':
                        action, params = 'TRAVEL_TO', {'x':x,'z':z}
                    else:
                        dx = (x>a['x'])-(x<a['x'])
                        dz = 0 if dx else (z>a['z'])-(z<a['z'])
                        assert [a['x']+dx,a['z']+dz] not in obs['blocked']
                        action, params = 'MOVE', {'dx':dx,'dz':dz}
        return Intent(a['id'],obs['tick'],action,params)


def outcome(world):
    a = world.agents[FOCAL]
    events = [e for e in world.events if e['source']=='validated_action' and e['actor_id']==FOCAL]
    picks = Counter(e['type'].upper() for e in events if e.get('origin')!='mechanical_execution')
    mechanical = Counter(e['type'].upper() for e in events if e.get('origin')=='mechanical_execution')
    drank = next((e['world_tick'] for e in events if e['type']=='drink'), None)
    gathered = next((e['world_tick'] for e in events if e['type']=='gather'
                     and e['payload']['parameters']['resource_id']==WATER_ID), None)
    x,z = START
    arrived = None
    for e in events:
        if e['type']=='move':
            p=e['payload']['parameters'];x+=p['dx'];z+=p['dz']
            if (x,z)==WATER and arrived is None:arrived=e['world_tick']
    return dict(completed_ticks=world.tick, population_end=len(world.agents), living=sum(a.alive for a in world.agents.values()),
        focal_position=[a.x,a.z], focal_health=a.health, focal_thirst=a.thirst,
        focal_carried_water=a.inventory['water'], final_distance_to_water=abs(a.x-WATER[0])+abs(a.z-WATER[1]),
        focal_first_arrival_tick=arrived, focal_first_water_gather_tick=gathered, focal_first_drink_tick=drank,
        focal_validated_choice_counts=dict(picks), focal_mechanical_action_counts=dict(mechanical),
        root_arrivals=len(world.root.data['manifestations']))


def cpu(out):
    results = []
    for strategy in ('TRAVEL_TO','MOVE'):
        policy=ScriptedWaterPolicy(strategy)
        world=FarWaterWorld(backend=policy)
        fixture=fixture_metadata(world)
        for _ in range(50):
            world.step()
            if outcome(world)['focal_first_drink_tick'] is not None:break
        results.append(dict(classification='scripted CPU stand-in; zero real inference calls', strategy=strategy,
            fixture=fixture, scripted_calls_by_agent=dict(policy.calls), outcome=outcome(world)))
    save(out/'CPU_COMPARISON.json',results)
    print(json.dumps(results,indent=2))


def worker(out, ticks):
    out.mkdir(exist_ok=False)
    live=[]
    class RecordedScenario(FarWaterWorld):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            live.append(self)
            save(out/'FIXTURE.json',fixture_metadata(self))
    original = baseline.World
    try:
        baseline.World = RecordedScenario  # diagnostic factory only; production World is untouched
        baseline.gpu(out,ticks,250,None)  # reserve 50 s for init/finalization inside the hard 300 s supervisor
    finally:
        baseline.World = original
    world=live[0]
    raw=json.loads((out/'SHORT_DIAGNOSTIC.json').read_text())
    focal=[a for a in raw['attempts'] if a['actor']==FOCAL]
    summary=dict(classification='short far-water diagnostic; genuine real-model inference, not a civilization benchmark',
        commit_sha=raw['commit_sha'], model_id=raw['model_id'], model_revision=raw['model_revision'],
        hardware=raw['inference']['hardware'], hard_process_cap_seconds=300, sampling_cap_seconds=250,
        max_ticks=ticks, real_seconds=raw['real_seconds'], inference=raw['inference'],
        fixture=fixture_metadata(FarWaterWorld()), outcome=outcome(world),
        tracked_pick_counts={n:raw['tool_pick_counts'][n] for n in TRACKED},
        all_nonzero_pick_counts={n:v for n,v in raw['tool_pick_counts'].items() if v},
        tracked_offer_counts={n:raw['tool_offer_counts'][n] for n in TRACKED},
        focal_pick_counts=dict(Counter(a['tool'] for a in focal if 'tool' in a)),
        focal_requests=len(focal), focal_accepted=sum(a.get('accepted') is True for a in focal),
        focal_water_visible_requests=sum(WATER_ID in a.get('visible_resource_ids',[]) for a in focal),
        intention_attempts=[{k:a[k] for k in ('actor','tick','tool','parameters','accepted','validation_reason') if k in a}
            for a in raw['attempts'] if a.get('tool') in TRACKED[:3]],
        validation_counts=raw['validation_counts'], recovery_equal=raw['recovery_equal'],
        system_sha256=raw['protected_system_sha256'])
    save(out/'FAR_WATER_SUMMARY.json',summary)
    print('FAR_WATER_FINAL',json.dumps(summary))
    print('FAR_WATER_SUMMARY_SHA256',hashlib.sha256((out/'FAR_WATER_SUMMARY.json').read_bytes()).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['cpu','gpu','gpu-worker'],required=True)
    p.add_argument('--out-dir',required=True)
    p.add_argument('--ticks',type=int,default=50)
    args=p.parse_args()
    if not 1<=args.ticks<=50:p.error('At most 50 ticks')
    out=Path(args.out_dir);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():p.error('Never reuse an existing output directory')
    if args.mode=='cpu':
        out.mkdir();cpu(out)
    elif args.mode=='gpu-worker':
        worker(out,args.ticks)
    else:
        command=[sys.executable,str(Path(__file__).resolve()),'--mode','gpu-worker','--out-dir',str(out),'--ticks',str(args.ticks)]
        log=out.with_suffix('.log')
        with log.open('x') as handle:
            try:
                result=subprocess.run(command,stdout=handle,stderr=subprocess.STDOUT,timeout=300)
                status=dict(status='worker_exited',returncode=result.returncode,hard_cap_seconds=300,follow_on_runs=0)
            except subprocess.TimeoutExpired:
                status=dict(status='hard_300_second_cap_worker_killed',hard_cap_seconds=300,follow_on_runs=0,
                            note='Only committed journal ticks/progress may be used; do not invent a final result.')
        if out.exists():save(out/'SUPERVISOR.json',status)
        print(json.dumps(status))


if __name__=='__main__':main()
