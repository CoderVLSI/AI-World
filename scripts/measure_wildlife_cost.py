"""Matched CPU/mock journal measurements; no model-autonomy claims."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from caitanya.engine import World


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--ticks', type=int, default=60)
    args = parser.parse_args()
    output = Path(args.out)
    if output.exists():
        parser.error('Choose a new output path; measurements are never overwritten')
    measurements = []
    for animals in (0, 6):
        world = World(population=50, width=128, depth=128, wildlife_per_species=animals)
        total = 0
        start = time.monotonic()
        cursor = len(world.events)
        for _ in range(args.ticks):
            world.step()
            total += sum(len((json.dumps(e, separators=(',', ':')) + '\n').encode('utf-8')) for e in world.events[cursor:])
            cursor = len(world.events)
        per_tick = total / args.ticks
        measurements.append({'wildlife_per_species': animals, 'ticks': world.tick,
                             'population': 50, 'journal_bytes': total, 'bytes_per_tick': per_tick,
                             'measured_real_seconds': time.monotonic() - start,
                             'projected_days_to_100MB': 100_000_000 / per_tick * world.biology.days_per_tick})
    record = {'classification': 'CPU/mock cost measurement', 'commit_sha': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'working_tree_changes': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
        'seed': 314159, 'width': 128, 'depth': 128, 'measurements': measurements,
        'overhead_percent': (measurements[1]['journal_bytes'] / measurements[0]['journal_bytes'] - 1) * 100,
        'projection_note': 'Linear projection from measured ticks, not an observed storage lifetime. Disk format unchanged.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
