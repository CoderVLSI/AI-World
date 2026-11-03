import time
from fastapi.testclient import TestClient
from caitanya.engine import World
from caitanya.server import create_app

def test_budget_pause_is_visible_without_changing_replay_state(tmp_path):
    world=World();app=create_app(world,run_dir=tmp_path,max_ticks=1,interval=.01)
    with TestClient(app) as client:
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            snapshot=client.get('/api/v1/world/snapshot').json()
            if snapshot['execution']['reason']=='budget_reached':break
            time.sleep(.01)
        assert snapshot['tick']==1
        assert snapshot['execution']=={'running':False,'reason':'budget_reached'}
        assert 'execution' not in world.state()
        assert world.replay(1)==world.state()

def test_read_only_worker_is_not_reported_as_live(tmp_path):
    with TestClient(create_app(World(),run_dir=tmp_path,live=False)) as client:
        assert client.get('/api/v1/health').json()['execution']=={'running':False,'reason':'read_only'}
