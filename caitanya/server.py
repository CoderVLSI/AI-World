"""Only GET routes are exposed. Operator actions belong to the Python process."""
import argparse
import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .engine import World
from .nature import climate
from .lifecycle import BiologyConfig, stage

ROOT = Path(__file__).resolve().parent.parent

def create_app(world=None, run_dir="runs/local", live=True, interval=0.5, max_journal_bytes=100_000_000):
    world = world or World()
    directory = Path(run_dir)
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/"events.jsonl").exists() and (directory/"events.jsonl").stat().st_size and not world.events:
        raise ValueError("Existing run history: use --recover or choose a new --run-dir")
    # A tick-zero image makes even a pre-first-periodic-checkpoint crash recoverable.
    if not any(directory.glob("checkpoint-*.json")):world.checkpoint(directory)
    published=world.public()
    committed_count=len(world.events)
    stop=asyncio.Event()
    async def worker():
        nonlocal published,committed_count
        cursor = len(world.events)
        try:
            while not stop.is_set():
                await asyncio.sleep(interval)
                if stop.is_set():break
                if (directory/"events.jsonl").exists() and (directory/"events.jsonl").stat().st_size > max_journal_bytes:
                    world.status="PAUSED_RESOURCE_LIMIT"
                    published=world.public()
                    world.checkpoint(directory)
                    return
                # Inference runs off the event loop; witness polling stays responsive.
                await asyncio.to_thread(world.step)
                with (directory/"events.jsonl").open("a",encoding="utf-8") as f:
                    for event in world.events[cursor:]:
                        f.write(json.dumps(event,separators=(",",":"))+"\n")
                    f.flush(); os.fsync(f.fileno())
                cursor=len(world.events)
                published=world.public()
                committed_count=cursor
                if world.tick % 60 == 0: world.checkpoint(directory)
        finally:
            world.checkpoint(directory)

    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(worker()) if live else None
        yield
        if task:
            stop.set()
            await task
    app=FastAPI(title="CAITANYA read-only witness",lifespan=lifespan)
    app.state.world=world
    @app.get("/api/v1/health")
    def health(): return {"status":world.status,"schema_version":1,"mode":world.manifest["inference_backend"]}
    @app.get("/api/v1/world/snapshot")
    def snapshot(): return published
    @app.get("/api/v1/world/events")
    def events(after:int=0):
        if after < 0 or after > committed_count: raise HTTPException(400,"Invalid cursor")
        batch=world.events[after:min(after+200,committed_count)]
        return {"cursor":after+len(batch),"events":[{k:v for k,v in e.items() if k!="payload"} |
            {"payload":{} if e["type"]=="tick_committed" else e["payload"]} for e in batch]}
    @app.get("/api/v1/agents/{agent_id}")
    def agent(agent_id:str):
        a=published["agents"].get(agent_id)
        if a is None: raise HTTPException(404,"Unknown agent")
        return a
    @app.get("/api/v1/artifacts/{artifact_id}")
    def artifact(artifact_id:str):
        a=published["works"].get(artifact_id) or published["parts"].get(artifact_id)
        if a is None: raise HTTPException(404,"Unknown artifact")
        return a
    @app.get("/api/v1/history")
    def history(from_tick:int=0,to_tick:int=0):
        if from_tick != to_tick: raise HTTPException(400,"MVP replay returns one committed tick; use equal bounds")
        try:
            state=world.replay(from_tick)
            state["terrain"]=world.terrain
            biology=BiologyConfig(**state.get("biology",{}))
            state["climate"]=climate(from_tick,biology.days_per_tick)
            state.pop("rng_state")
            state.pop("root",None)
            for a in state["agents"].values():
                a.pop("memories");a.pop("parenting_proposals",None)
                a["age_years"]=round(a["age_years_at_start"]+(from_tick-a["born_tick"])*biology.days_per_tick/365,3)
            return state
        except ValueError as e: raise HTTPException(400,str(e))
    @app.get("/api/v1/metrics")
    def metrics(): return published["metrics"]
    @app.get("/api/v1/families")
    def families():
        return {"lineage":[{"id":a["id"],"parent_ids":a["parent_ids"],"guardian_ids":a["guardian_ids"],"generation":a["generation"],"alive":a["alive"]}
            for a in published["agents"].values()],"pregnancies":published["pregnancies"]}
    @app.get("/")
    @app.get("/viewer")
    def viewer(): return FileResponse(ROOT/"web"/"index.html")
    app.mount("/static",StaticFiles(directory=ROOT/"web"),name="static")
    return app

def main():
    import uvicorn
    p=argparse.ArgumentParser(); p.add_argument("--population",type=int,default=5)
    p.add_argument("--seed",type=int,default=314159); p.add_argument("--port",type=int,default=8000)
    p.add_argument("--width",type=int,default=256);p.add_argument("--depth",type=int,default=256)
    p.add_argument("--backend",choices=["mock","lfm3"],default="mock");p.add_argument("--revision")
    p.add_argument("--days-per-tick",type=float,default=1/144,help="World calendar rate; baseline ten minutes per tick. Accelerated experiments must be labeled.")
    p.add_argument("--resume"); p.add_argument("--run-dir",default="runs/local")
    p.add_argument("--recover",help="Restore newest valid image and replay its committed journal tail")
    args=p.parse_args()
    if args.backend=="lfm3":
        from .inference import TransformersLFM3Backend
        backend=TransformersLFM3Backend(revision=args.revision)
    else:backend=None
    if args.resume and args.recover:p.error("Choose either --resume or --recover")
    world=World.recover(args.recover,backend=backend) if args.recover else World.restore(args.resume,backend=backend) if args.resume else World(seed=args.seed,population=args.population,width=args.width,depth=args.depth,backend=backend,biology=BiologyConfig(days_per_tick=args.days_per_tick))
    uvicorn.run(create_app(world,args.run_dir),host="127.0.0.1",port=args.port)
if __name__=="__main__": main()
