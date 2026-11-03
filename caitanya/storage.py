"""Run-directory storage helpers: segmented event journal and slim-checkpoint support.

Layout of a run directory (nothing here is ever deleted or rewritten in place):

    events-000000000.jsonl   closed journal segment holding events 0..k-1 (named by first event index)
    events-<k>.jsonl         next closed segment
    events.jsonl             the active, append-only journal (always the newest events)
    checkpoint-<tick>.json   full image (embeds every event) or slim image (references the journal)

A *slim* checkpoint stores `events_ref` (count + last event id) instead of the event list, so checkpoint size no
longer grows with run length. The events it refers to are read back from the journal files. Full checkpoints
from earlier versions still load unchanged.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ACTIVE = "events.jsonl"


def _index(line):
    return int(json.loads(line)["event_id"].removeprefix("evt-"))


def segments(directory):
    return sorted(Path(directory).glob("events-[0-9]*.jsonl"))


def journal_files(directory):
    """Closed segments in order, then the active journal."""
    directory = Path(directory)
    files = segments(directory)
    if (directory / ACTIVE).exists():
        files.append(directory / ACTIVE)
    return files


def has_history(directory):
    return any(p.stat().st_size for p in journal_files(directory))


def iter_lines(directory):
    """Every journal line in order. Stops at the first unterminated (partially written) line."""
    for path in journal_files(directory):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.endswith("\n"):
                    return
                yield line


def read_events(directory, count):
    """The first `count` events from the journal files; raises ValueError if they are not all present."""
    events = []
    if count == 0:
        return events
    for line in iter_lines(directory):
        try:
            index = _index(line)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("Corrupt journal record") from exc
        if index < len(events):
            continue  # tolerated overlap between files
        if index != len(events):
            raise ValueError("Journal event gap")
        events.append(json.loads(line))
        if len(events) == count:
            return events
    raise ValueError("journal does not cover the checkpoint's events")


def _first_index(path):
    with Path(path).open(encoding="utf-8") as handle:
        line = handle.readline()
    return _index(line) if line.endswith("\n") else None


def _count_lines(path):
    n = 0
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1 << 20):
            n += chunk.count(b"\n")
    return n


def _fsync_dir(directory):
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def ensure_covered(world, directory):
    """Make sure the journal files hold events 0..len(world.events)-1, writing a base segment for any missing
    prefix (e.g. a run resumed from a full checkpoint). Returns True when slim checkpoints are safe to use."""
    directory = Path(directory)
    total = len(world.events)
    covered = 0
    for path in journal_files(directory):
        first = _first_index(path)
        if first is None:
            continue
        if first > covered:
            if covered != 0 or first > total:
                return False
            _write_segment(directory, world.events[:first])
            covered = first
        covered = max(covered, first + _count_lines(path))
    if covered == 0 and total:
        _write_segment(directory, world.events)
        covered = total
    return covered == total


def _write_segment(directory, events):
    target = Path(directory) / "events-000000000.jsonl"
    if target.exists():
        raise ValueError("refusing to overwrite an existing journal segment")
    temporary = target.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    _fsync_dir(directory)


def rotate_journal(directory):
    """Close the active journal as a named segment (a rename; no data is copied, rewritten or removed).
    Call only after a slim checkpoint covering every event in the active journal has been written."""
    directory = Path(directory)
    active = directory / ACTIVE
    if not active.exists() or not active.stat().st_size:
        return None
    first = _first_index(active)
    if first is None:
        return None
    target = directory / f"events-{first:09}.jsonl"
    if target.exists():
        raise ValueError("refusing to overwrite an existing journal segment")
    os.replace(active, target)
    _fsync_dir(directory)
    return target


def run_bytes(directory):
    return sum(p.stat().st_size for p in Path(directory).iterdir() if p.is_file())
