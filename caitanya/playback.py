"""Read-only playback of a finished run, with no model and no GPU.

A run folder (checkpoints plus the event journal) holds every committed tick as a state patch. Playback restores the newest
checkpoint with a stand-in backend that can never make a decision, then walks the recorded patches forward one tick at a time, so
any viewer of the normal read-only witness API (Godot, the browser viewer) can watch a run that was made elsewhere, for example
on a Colab GPU, on a computer with no GPU and little disk space.

Nothing is simulated and nothing is written: the run folder is only read, and no inference ever happens. The public API still hides
everything private (root state, memories, scheduler internals), exactly as for a live run.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .engine import World
from .history import apply_changes


class PlaybackBackend:
    """Carries the recorded model identity so a checkpoint restores; it cannot decide anything."""

    def __init__(self, model_id, model_revision, metadata=None):
        self.model_id, self.model_revision, self.metadata = model_id, model_revision, dict(metadata or {})
        self.calls = 0

    def decide(self, observation):
        raise RuntimeError("playback never makes decisions")


def _identity(directory):
    images = sorted(Path(directory).glob("checkpoint-*.json"))
    if not images:
        raise ValueError(f"no checkpoint in {directory}: this is not a run folder")
    manifest = json.loads(images[-1].read_text(encoding="utf-8"))["body"]["state"]["manifest"]
    meta = {k: manifest[k] for k in ("mock_options",) if k in manifest}
    return PlaybackBackend(manifest["model_id"], manifest["model_revision"], meta)


class Playback:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.backend = _identity(self.directory)
        self.world = World.recover(self.directory, backend=self.backend)
        self.events = self.world.events
        self.initial = self.world.initial_state
        self.final_tick = self.world.tick
        self.tick_end = {e["world_tick"]: i + 1 for i, e in enumerate(self.events) if e["type"] == "tick_committed"}
        first = min(self.tick_end.values(), default=len(self.events) + 1) - 1
        self.tick_end[0] = first             # tick 0: the creation events only
        self.state = copy.deepcopy(self.initial)
        self.tick = 0
        self.shown_events = 0
        self.seek(0)

    def seek(self, tick):
        """Show the world as it was at the end of `tick` (0 = creation). Moving forward applies patches; backward rebuilds."""
        if type(tick) is not int or not 0 <= tick <= self.final_tick:
            raise ValueError("tick outside the recorded run")
        w = self.world
        if tick < self.tick:
            self.state, self.tick, self.shown_events = copy.deepcopy(self.initial), 0, 0
            w.events = []
            w._rebuild_counts()
        for e in self.events[self.tick_end.get(self.tick, 0):self.tick_end[tick]]:
            if e["type"] == "tick_committed":
                if "state" in e["payload"]:
                    self.state = copy.deepcopy(e["payload"]["state"])
                else:
                    apply_changes(self.state, e["payload"]["patch"])
        self.tick = tick
        w.load_state(copy.deepcopy(self.state))
        end = self.tick_end[tick]
        w.events = self.events[:end]
        for e in self.events[self.shown_events:end]:
            w._count(e)
        self.shown_events = end
        w.status = "PLAYBACK"
        return w

    def advance(self, loop=True):
        """One recorded tick forward. Returns False when the run is finished and not looping."""
        if self.tick < self.final_tick:
            self.seek(self.tick + 1)
            return True
        if loop:
            self.seek(0)
            return True
        return False
