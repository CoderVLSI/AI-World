"""Opt-in, formless environmental rules. Names are operator labels, not theology.

These are local instantaneous pulses, not fluid dynamics or conscious agents.
The separate RNG never consumes inhabitant/world inference randomness.
"""
from __future__ import annotations

import copy
import hashlib
import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Force:
    name: str
    phenomenon: str
    daily_rate: float
    resources: tuple = ()  # (resource type, signed units per strength)
    thirst: int = 0
    energy: int = 0
    injury: int = 0


# Deliberate simulation choices, not a canonical list of Vedic deities.
FORCES = {
    f.name.lower(): f for f in (
        Force("Agni", "wildfire", .08, (("wood", -2), ("plant_fiber", -1)), injury=2),
        Force("Vayu", "strong wind", .18, energy=-2),
        Force("Indra", "lightning", .06, (("wood", -1),), injury=3),
        Force("Varuna", "floodwater", .08, (("water", 2), ("grain", -1)), energy=-2),
        Force("Mitra", "calm weather", .20, energy=1),
        Force("Yama", "organic decay", .12, (("food", -1), ("fruit", -1), ("fish", -1))),
        Force("Surya", "heatwave", .12, (("water", -1),), thirst=3),
        Force("Soma", "cool interval", .18, thirst=-1),
        Force("Prithvi", "earth tremor", .03, energy=-2, injury=2),
        Force("Parjanya", "heavy rain", .18, (("water", 2),), energy=-1),
        Force("Rudra", "severe storm", .04, (("wood", -1),), energy=-3, injury=2),
        Force("Apas", "water replenishment", .15, (("water", 2),)),
        Force("Ushas", "mild morning interval", .20, energy=1),
        Force("Bhumi", "soil renewal", .10, (("grain", 1), ("herbs", 1), ("plant_fiber", 1))),
    )
}
VERSION = "formless-pulses-v1"


class NatureForces:
    """Saved operator configuration and recent physically observable effects."""

    def __init__(self, state=None):
        self.data = copy.deepcopy(state) if state is not None else {
            "version": VERSION, "last_tick": 0, "recent": [], "counts": {},
        }
        if self.data["version"] != VERSION:
            raise ValueError("unsupported nature forces version")

    def state(self):
        return copy.deepcopy(self.data)

    def advance(self, world):
        if world.tick <= self.data["last_tick"]:
            raise ValueError("nature forces must advance once per increasing tick")
        # Independent streams, stable across checkpoints and process restarts.
        for key, force in FORCES.items():
            hour = (world.tick * world.biology.days_per_tick % 1) * 24
            if key == "soma" and 6 <= hour < 18:
                continue
            if key == "ushas" and not 5 <= hour < 8:
                continue
            if key == "surya" and not 8 <= hour < 18:
                continue
            material = f"{VERSION}:{world.seed}:{world.tick}:{key}".encode()
            rng = random.Random(int.from_bytes(hashlib.sha256(material).digest(), "big"))
            probability = -math.expm1(-force.daily_rate * world.biology.days_per_tick)
            if rng.random() < probability:
                self.apply(world, key, rng.randrange(world.width), rng.randrange(world.depth), rng.randint(1, 3))
        self.data["last_tick"] = world.tick
        self.data["recent"] = [e for e in self.data["recent"] if world.tick-e["tick"] <= 6][-32:]

    def apply(self, world, key, x, z, strength=1):
        """Operator/test pulse; no inhabitant tool or HTTP mutation route exists.

        Effects are clipped to existing node capacity and human need bounds.
        Injury cannot directly kill: this first review version stops at 1 health.
        Every event includes actual before/after deltas, even if nothing was hit.
        """
        if key not in FORCES or type(strength) is not int or not 1 <= strength <= 3:
            raise ValueError("invalid nature force or strength")
        if type(x) is not int or type(z) is not int or not (0 <= x < world.width and 0 <= z < world.depth):
            raise ValueError("invalid force location")
        force = FORCES[key]
        radius = 4 + strength
        nearby = lambda item: abs(item["x"]-x)+abs(item["z"]-z) <= radius
        outcomes = []
        rates = dict(force.resources)
        for rid, node in sorted(world.resources.items()):
            delta = rates.get(node["kind"], 0)
            if delta and nearby(node):
                before = node["amount"]
                node["amount"] = max(0, min(node["capacity"], before+delta*strength))
                if before != node["amount"]:
                    outcomes.append({"resource_id": rid, "amount_before": before, "amount_after": node["amount"]})
        for aid, agent in sorted(world.agents.items()):
            if not agent.alive or not nearby({"x": agent.x, "z": agent.z}):
                continue
            before = {field: getattr(agent, field) for field in ("thirst", "energy", "health")}
            agent.thirst = max(0, min(100, agent.thirst + force.thirst*strength))
            agent.energy = max(0, min(100, agent.energy + force.energy*strength))
            if force.injury and agent.health > 0:
                agent.health = max(1, agent.health-force.injury*strength)
            after = {field: getattr(agent, field) for field in before}
            if before != after:
                outcomes.append({"agent_id": aid, "before": before, "after": after})
        summary = {"tick": world.tick, "phenomenon": force.phenomenon,
                   "x": x, "z": z, "radius": radius, "strength": strength}
        world.emit("nature_force", None, {**summary, "force": key, "outcomes": outcomes,
                   "rules_version": VERSION}, "environment_rule")
        self.data["counts"][key] = self.data["counts"].get(key, 0)+1
        self.data["recent"].append(summary)
        self.data["recent"] = self.data["recent"][-32:]

    def observe(self, world, agent):
        # Only local recent sensory effects; no names, cosmology, hidden controller,
        # future hazard schedules, or other inhabitants' outcomes.
        return [copy.deepcopy(e) for e in self.data["recent"]
                if world.tick-e["tick"] <= 6
                and abs(e["x"]-agent.x)+abs(e["z"]-agent.z) <= e["radius"]]
