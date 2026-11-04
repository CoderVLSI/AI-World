"""Only GET routes are exposed. Operator actions belong to the Python process."""
import argparse
import asyncio
import json
import os
import threading
import time
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from . import storage
from .engine import World, redact_private, SCHEMA_VERSION
from .nature import climate
from .autonomy import AutonomyConfig, load_experiment_file
from .lifecycle import BiologyConfig, stage
from .witness import terrain_grid, live_view, recent_speech

ROOT = Path(__file__).resolve().parent.parent
SCRUB_HOLD_SECONDS = 3.0      # playback: after a viewer asks for a tick, the automatic advance waits this long

def create_app(world=None, run_dir="runs/local", live=True, interval=0.5, max_journal_bytes=100_000_000, max_ticks=None, max_seconds=None, report_dir=None, checkpoint_every=60,
               segment_bytes=25_000_000, max_run_bytes=5_000_000_000, playback=None, loop=True):
    if type(checkpoint_every) is not int or checkpoint_every < 1:raise ValueError("checkpoint_every must be a positive integer")
    if playback is not None:
        # Read-only replay of a finished run: nothing is written, no model runs (see playback.py).
        world,live,directory,slim=playback.world,True,Path(playback.directory),False
    else:
        world = world or World()
        directory = Path(run_dir)
        directory.mkdir(parents=True,exist_ok=True)
        # A freshly created world sits at tick 0 (it already holds its genesis events); a recovered one does not.
        if storage.has_history(directory) and world.tick == 0:
            raise ValueError("Existing run history: use --recover or choose a new --run-dir")
        # A tick-zero image makes even a pre-first-periodic-checkpoint crash recoverable.
        if not any(directory.glob("checkpoint-*.json")):world.checkpoint(directory)
        # Slim checkpoints (constant size) are used when the journal files cover every event; otherwise full images.
        slim=storage.ensure_covered(world,directory)
    published=world.public()
    committed_count=len(world.events)
    stop=asyncio.Event()
    view_lock=threading.Lock()                   # playback only: the worker and a viewer asking for a tick both move the same replay
    scrub={'until':0.0,'speed':None}             # while a viewer is choosing ticks itself, the automatic advance waits
    execution={'running':False,'reason':'read_only' if not live else 'not_started'}
    async def playback_worker():
        nonlocal published,committed_count
        execution.update(running=True,reason='playback')
        while not stop.is_set():
            try:await asyncio.wait_for(stop.wait(),interval)     # a pause that ends at once when the server stops
            except asyncio.TimeoutError:pass
            if stop.is_set():break
            if time.monotonic()<scrub['until']:continue          # a viewer is driving the replay (see /api/v1/live?tick=)
            def advance():
                nonlocal published,committed_count
                with view_lock:
                    if not playback.advance(loop):return False
                    published=world.public();committed_count=len(world.events)
                    return True
            if not await asyncio.to_thread(advance):
                execution.update(running=False,reason='playback_finished')
                return
    async def worker():
        import time
        nonlocal published,committed_count
        started=time.monotonic();starting_tick=world.tick
        execution.update(running=True,reason=None)
        cursor = len(world.events)
        try:
            while not stop.is_set():
                await asyncio.sleep(interval)
                if stop.is_set():break
                if (max_ticks is not None and world.tick-starting_tick>=max_ticks) or (max_seconds is not None and time.monotonic()-started>=max_seconds):
                    execution['reason']='budget_reached'
                    return
                if (directory/"events.jsonl").exists() and (directory/"events.jsonl").stat().st_size > max_journal_bytes:
                    world.status="PAUSED_RESOURCE_LIMIT"
                    execution['reason']='journal_limit'
                    published=world.public()
                    world.checkpoint(directory,slim=slim)
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
                with (directory/"metrics.jsonl").open("a",encoding="utf-8") as f:
                    f.write(json.dumps(world.metrics(),separators=(",",":"))+"\n")
                if world.tick % checkpoint_every == 0:
                    world.checkpoint(directory,slim=slim)
                    if storage.run_bytes(directory)>max_run_bytes:
                        world.status="PAUSED_RESOURCE_LIMIT";execution['reason']='run_size_limit';return
                if slim and (directory/"events.jsonl").exists() and (directory/"events.jsonl").stat().st_size>=segment_bytes:
                    # Image first (covers every journaled event), then close the segment by renaming it.
                    world.checkpoint(directory,slim=True)
                    storage.rotate_journal(directory)
        except BaseException:
            execution['reason']='worker_error'
            raise
        finally:
            execution.update(running=False,reason=execution['reason'] or 'stopped')
            world.checkpoint(directory,slim=slim)
            if report_dir:
                from .experiment import summarize, source_revision
                from .engine import digest
                recovered=World.recover(directory,backend=world.backend)
                summarize(world,report_dir,{'date_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                    'commit_sha':source_revision(),'root_mode':world.root.data['mode'],
                    'acceptance':{'checkpoint_journal_recovery':digest(recovered.state())==digest(world.state()),
                                  'live_worker_stopped':True},
                    'journal_bytes':sum(p.stat().st_size for p in storage.journal_files(directory))})

    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(playback_worker() if playback is not None else worker()) if live else None
        yield
        if task:
            stop.set()
            await task
    app=FastAPI(title="CAITANYA read-only witness",lifespan=lifespan)
    app.state.world=world
    @app.get("/api/v1/health")
    def health(): return {"status":world.status,"schema_version":SCHEMA_VERSION,"mode":world.manifest["inference_backend"],"execution":dict(execution)}
    @app.get("/api/v1/genesis")
    def genesis_summary():
        """Counts and the deterministic creation record only: no reflection text, no proposals, no root state."""
        from . import isvara
        return isvara.public_summary(world)
    @app.get("/api/v1/world/snapshot")
    def snapshot(): return published | {'execution':dict(execution)}
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
            redact_private(state)
            if 'fauna' in state:
                from fauna.ecology import Ecosystem
                state['wildlife']=Ecosystem.restore(state.pop('fauna')).public()
                state['wildlife']['mode']='Integrated deterministic ecology — shared human world'
            for a in state["agents"].values():
                a["age_years"]=round(a["age_years_at_start"]+(from_tick-a["born_tick"])*biology.days_per_tick/365,3)
            return state
        except ValueError as e: raise HTTPException(400,str(e))
    @app.get("/api/v1/metrics")
    def metrics(): return published["metrics"]
    @app.get('/api/v1/wildlife')
    def wildlife():return published.get('wildlife',{'mode':'No wildlife recorded in this run','animals':[],'species':{},'counts':{},'events':[],'tick':published['tick'],'elapsed_days':0})
    @app.get('/api/v1/wildlife/terrain')
    def wildlife_terrain():return dict(width=world.width,depth=world.depth,terrain=world.terrain)
    @app.get("/api/v1/scheduler")
    def scheduler_report():
        """Decision budget, fairness and LFM-versus-mechanical attribution (measured counters)."""
        return published["metrics"].get("scheduler") or {}
    @app.get("/api/v1/knowledge")
    def knowledge():
        """Aggregate counts only; private memory contents are never published."""
        return published["metrics"].get("knowledge") or {}
    @app.get("/api/v1/objects")
    def objects(): return published.get("objects", {})
    terrain_cache={}
    @app.get("/api/v1/terrain")
    def terrain(step:int=2):
        """Static heightmap + biome grid for viewers (cache it; it depends only on the seed)."""
        if step not in terrain_cache:
            try:terrain_cache[step]=terrain_grid(world,step)
            except ValueError as e:raise HTTPException(400,str(e))
        return terrain_cache[step]
    @app.get("/api/v1/playback")
    def playback_info():
        """Whether this server is replaying a finished run, and how long it is (so a viewer can offer pause, speed and a scrub bar)."""
        if playback is None:return {"enabled":False}
        return {"enabled":True,"tick":playback.tick,"final_tick":playback.final_tick,"loop":bool(loop),"seconds_per_tick":interval}
    @app.get("/api/v1/live")
    def live_snapshot(tick:Optional[int]=None):   # not named `live`: that would shadow the create_app(live=...) flag
        """Light polling view for viewers: positions, plans, resources, objects, optional wildlife.
        With `?tick=N` (finished-run playback only) the same view as it was at the end of recorded tick N. It is a pure function of N:
        it only chooses which recorded moment to show, changes nothing in the run folder, and never makes a decision."""
        nonlocal published,committed_count
        if tick is not None:
            if playback is None:raise HTTPException(400,"tick is only available when watching a finished run (--playback)")
            with view_lock:
                try:playback.seek(tick)
                except ValueError as e:raise HTTPException(400,str(e))
                scrub['until']=time.monotonic()+SCRUB_HOLD_SECONDS
                published=world.public();committed_count=len(world.events)
                view=live_view(published)
                view["speech"]=recent_speech(world.events[:committed_count],published["tick"])
                return view
        view = live_view(published)
        view["speech"] = recent_speech(world.events[:committed_count], published["tick"])      # public speech only; thoughts carry no text
        return view
    @app.get("/api/v1/families")
    def families():
        return {"lineage":[{"id":a["id"],"parent_ids":a["parent_ids"],"guardian_ids":a["guardian_ids"],"generation":a["generation"],"alive":a["alive"]}
            for a in published["agents"].values()],"pregnancies":published["pregnancies"]}
    @app.get("/")
    @app.get("/viewer")
    def viewer(): return FileResponse(ROOT/"web"/"index.html")
    app.mount("/static",StaticFiles(directory=ROOT/"web"),name="static")
    app.mount('/fauna',StaticFiles(directory=ROOT/'fauna'/'web',html=True),name='fauna')
    return app

def build_parser():
    p=argparse.ArgumentParser(); p.add_argument("--population",type=int,default=5)
    p.add_argument("--seed",type=int,default=314159); p.add_argument("--port",type=int,default=8000)
    p.add_argument("--width",type=int,default=256);p.add_argument("--depth",type=int,default=256)
    p.add_argument("--backend",choices=["mock","lfm3"],default="mock");p.add_argument("--revision")
    p.add_argument("--root-mode",choices=["off","observe","crisis"],default="crisis")
    p.add_argument("--hazard-exit-hint",action="store_true",help="EXPERIMENT (off by default; needs --nature-forces): inhabitants inside a hazard zone are also told the geometric way out")
    p.add_argument("--nature-forces",action="store_true",help="Opt in to experimental formless environmental pulses for NEW worlds; recovery preserves the saved setting.")
    p.add_argument("--max-ticks",type=int);p.add_argument("--max-seconds",type=float)
    p.add_argument("--report-dir")
    p.add_argument('--wildlife-per-species',type=int,default=6,help='Initial animals per species for NEW worlds; 0 disables wildlife. Recovery preserves saved ecology.')
    p.add_argument("--days-per-tick",type=float,default=1/144,help="World calendar rate; baseline ten minutes per tick. Accelerated experiments must be labeled.")
    p.add_argument("--resume"); p.add_argument("--run-dir",default="runs/local")
    p.add_argument("--config",help="Experiment JSON (see config/default.json). Only a file named here is ever loaded.")
    p.add_argument("--legacy",action="store_true",help="Run the v0.4.0 per-tick physiology and fixed decision cadence")
    p.add_argument("--decisions-per-tick",type=int,help="Model calls allowed per tick (foundations mode)")
    p.add_argument("--checkpoint-every",type=int,default=60,help="Ticks between periodic checkpoints (slim images reference the journal; images are full only if the journal cannot cover the history)")
    p.add_argument("--segment-bytes",type=int,default=25_000_000,help="Close the active journal as a numbered segment after this many bytes")
    p.add_argument("--max-run-bytes",type=int,default=5_000_000_000,help="Pause (PAUSED_RESOURCE_LIMIT) when the run directory exceeds this size")
    p.add_argument("--families",type=int,default=0,help="Found the NEW world with this many households (a woman, a man and children); overrides --population")
    p.add_argument("--children-per-family",type=int,default=2)
    p.add_argument("--recover",help="Restore newest valid image and replay its committed journal tail")
    p.add_argument("--playback",help="Watch a FINISHED run folder read-only (no model, no GPU, nothing written); for example one made on Colab")
    p.add_argument("--speed",type=float,default=2.0,help="Playback ticks per second")
    p.add_argument("--no-loop",action="store_true",help="Stop at the end of the recorded run instead of starting over")
    return p

def build_world(args,p,backend=None):
    """Construct or restore the world. An experiment file is read only when --config names it."""
    if args.resume and args.recover:p.error("Choose either --resume or --recover")
    if args.recover or args.resume:
        return World.recover(args.recover,backend=backend) if args.recover else World.restore(args.resume,backend=backend)
    params,autonomy=load_experiment_file(args.config) if args.config else ({},AutonomyConfig())
    if args.legacy:autonomy=AutonomyConfig.legacy_mode()
    if args.decisions_per_tick:
        from dataclasses import replace
        autonomy=replace(autonomy,scheduler=replace(autonomy.scheduler,max_decisions_per_tick=args.decisions_per_tick))
    given=dict(seed=args.seed,population=args.population,width=args.width,depth=args.depth)
    explicit={k:v for k,v in given.items() if p.get_default(k)!=v}   # command line beats the file
    return World(**{**given,**params,**explicit},backend=backend,biology=BiologyConfig(days_per_tick=args.days_per_tick),autonomy=autonomy,root_mode=args.root_mode,wildlife_per_species=args.wildlife_per_species,nature_forces=args.nature_forces,families=args.families,children_per_family=args.children_per_family,hazard_exit_hint=args.hazard_exit_hint)

def main():
    import uvicorn
    p=build_parser();args=p.parse_args()
    if args.playback:
        if args.speed<=0:p.error("--speed must be positive")
        from .playback import Playback
        pb=Playback(args.playback)
        print(f"Playback of {args.playback}: {pb.final_tick} recorded ticks, model {pb.backend.model_id}. Read-only; no model is loaded.")
        uvicorn.run(create_app(playback=pb,interval=1/args.speed,loop=not args.no_loop),host="127.0.0.1",port=args.port)
        return
    if args.backend=="lfm3":
        from .inference import TransformersLFM3Backend
        backend=TransformersLFM3Backend(revision=args.revision)
    else:backend=None
    world=build_world(args,p,backend)
    uvicorn.run(create_app(world,args.run_dir,max_ticks=args.max_ticks,max_seconds=args.max_seconds,report_dir=args.report_dir,
                           checkpoint_every=args.checkpoint_every,segment_bytes=args.segment_bytes,max_run_bytes=args.max_run_bytes),host="127.0.0.1",port=args.port)
if __name__=="__main__": main()
