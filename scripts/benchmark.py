"""CPU mock benchmark. Does not report GPU throughput."""
import argparse
import json
import time
from caitanya.engine import World,digest
p=argparse.ArgumentParser();p.add_argument('--ticks',type=int,default=120);p.add_argument('--population',type=int,default=5)
args=p.parse_args();w=World(population=args.population);start=time.perf_counter()
for _ in range(args.ticks):w.step()
elapsed=time.perf_counter()-start
path=w.checkpoint('runs/benchmark')
print(json.dumps(dict(**w.metrics(),elapsed_seconds=elapsed,ticks_per_second=args.ticks/elapsed,
    event_digest=digest(w.events),checkpoint=str(path),model_id=w.backend.model_id),indent=2))
