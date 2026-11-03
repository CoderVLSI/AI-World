"""Explicit scripted UI fixture, never a real AI run. python -m tests... is not needed."""
import tempfile
import uvicorn
from caitanya.engine import World
from caitanya.server import create_app

def main():
    world=World(population=5)
    world.manifest['ui_fixture']=True
    people=list(world.agents.values())
    people[2].parent_ids=[people[0].id,people[1].id];people[2].generation=1
    people[2].guardian_ids=[people[0].id];people[2].age_years_at_start=20
    people[3].parent_ids=[people[2].id];people[3].generation=2;people[3].age_years_at_start=4
    people[4].alive=False
    world.emit('birth',people[3].id,{'parent_ids':people[3].parent_ids},'test_fixture')
    world.emit('speak',people[0].id,{'parameters':{'text':'<img src=x onerror=alert(1)> This is scripted fixture speech.'}},'test_fixture')
    world.emit('write',people[2].id,{'work_id':'fixture-work','parameters':{'text':'Our first recorded observations — fixture text.'}},'test_fixture')
    world.emit('death',people[4].id,{'cause':'scripted fixture'},'test_fixture')
    world.initial_state=world.state()
    with tempfile.TemporaryDirectory() as directory:
        uvicorn.run(create_app(world,run_dir=directory,live=False),host='127.0.0.1',port=8010)

if __name__=='__main__':main()
