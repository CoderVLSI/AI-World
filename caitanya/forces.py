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
HAZARD_VERSION = "lasting-hazards-v1"
# Lasting hazards: a pulse of these forces also leaves a zone that keeps acting for `hours` simulated hours. Effects are PER HOUR at
# strength 1 (scaled by strength and by the tick length), so the clock speed changes how many ticks a hazard lasts, not how harmful an
# hour is. Injury can reduce health to 1 but never below: a first, deliberately non-lethal version (lethal hazards need owner approval).
HAZARDS = {
    "agni": dict(hours=6, injury=2.0, energy=-1.0),
    "varuna": dict(hours=12, injury=.5, energy=-2.0),
    "surya": dict(hours=8, thirst=3.0, energy=-.5),
    "rudra": dict(hours=4, injury=1.0, energy=-3.0),
}
VIEW_RANGE = 8      # an inhabitant perceives a hazard whose edge is within this many steps (same as other observations)


class NatureForces:
    """Saved operator configuration and recent physically observable effects."""

    def __init__(self, state=None):
        self.data = copy.deepcopy(state) if state is not None else {
            "version": VERSION, "last_tick": 0, "recent": [], "counts": {},
            "hazard_version": HAZARD_VERSION, "hazards": [], "next_hazard": 1,
        }
        if self.data["version"] != VERSION:
            raise ValueError("unsupported nature forces version")
        if "hazard_version" in self.data and self.data["hazard_version"] != HAZARD_VERSION:
            raise ValueError("unsupported lasting hazards version")

    @property
    def hazards_enabled(self):
        """Saves made before lasting hazards existed keep their original pulse-only behaviour."""
        return "hazard_version" in self.data

    def state(self):
        return copy.deepcopy(self.data)

    def advance(self, world):
        if world.tick <= self.data["last_tick"]:
            raise ValueError("nature forces must advance once per increasing tick")
        if self.hazards_enabled:
            self._act_hazards(world)
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
                agent.health = min(agent.health, max(1, agent.health-force.injury*strength))
            after = {field: getattr(agent, field) for field in before}
            if before != after:
                outcomes.append({"agent_id": aid, "before": before, "after": after})
        if self.hazards_enabled and key in HAZARDS:      # before the pulse event, so the pulse stays the latest event of an apply()
            self._start_hazard(world, key, x, z, strength, radius)
        summary = {"tick": world.tick, "phenomenon": force.phenomenon,
                   "x": x, "z": z, "radius": radius, "strength": strength}
        world.emit("nature_force", None, {**summary, "force": key, "outcomes": outcomes,
                   "rules_version": VERSION}, "environment_rule")
        self.data["counts"][key] = self.data["counts"].get(key, 0)+1
        self.data["recent"].append(summary)
        self.data["recent"] = self.data["recent"][-32:]

    # ------------------------------------------------------------------ lasting hazards
    def _hours_per_tick(self, world):
        return world.biology.days_per_tick * 24

    def _start_hazard(self, world, key, x, z, strength, radius):
        spec = HAZARDS[key]
        ticks = max(1, math.ceil(spec["hours"] / self._hours_per_tick(world)))
        hazard = {"id": f"hazard-{self.data['next_hazard']:06}", "force": key, "phenomenon": FORCES[key].phenomenon, "x": x, "z": z,
                  "radius": radius, "strength": strength, "start_tick": world.tick, "end_tick": world.tick+ticks, "exposed": {}}
        self.data["next_hazard"] += 1
        self.data["hazards"].append(hazard)
        world.emit("nature_hazard_started", None, {"hazard_id": hazard["id"], "force": key, "phenomenon": hazard["phenomenon"], "x": x, "z": z,
                   "radius": radius, "strength": strength, "planned_hours": spec["hours"], "rules_version": HAZARD_VERSION}, "environment_rule")

    def _act_hazards(self, world):
        """Each tick, every living inhabitant inside an active zone takes that hour-fraction of its effects; leaving ends it."""
        hours = self._hours_per_tick(world)
        still = []
        for hz in self.data["hazards"]:
            if hz["start_tick"] >= world.tick:       # created this tick: its instant pulse already applied
                still.append(hz)
                continue
            spec = HAZARDS[hz["force"]]
            inside = set()
            for aid, agent in sorted(world.agents.items()):
                if not agent.alive or abs(agent.x-hz["x"])+abs(agent.z-hz["z"]) > hz["radius"]:
                    continue
                inside.add(aid)
                rec = hz["exposed"].setdefault(aid, {"ticks": 0, "injury": 0.0, "energy": 0.0, "thirst": 0.0, "left": False})
                rec["ticks"] += 1
                scale = hz["strength"]*hours
                agent.thirst = max(0, min(100, agent.thirst + spec.get("thirst", 0)*scale))
                before_energy = agent.energy
                agent.energy = max(0, min(100, agent.energy + spec.get("energy", 0)*scale))
                rec["energy"] = round(rec["energy"] + (agent.energy-before_energy), 6)
                if spec.get("injury") and agent.health > 0:
                    before_hp = agent.health
                    agent.health = min(agent.health, max(1, round(agent.health - spec["injury"]*scale, 6)))
                    rec["injury"] = round(rec["injury"] + (before_hp-agent.health), 6)
                rec["thirst"] = round(rec["thirst"] + spec.get("thirst", 0)*scale, 6)
            for aid, rec in hz["exposed"].items():
                if aid not in inside:
                    rec["left"] = True       # recorded response: it is outside the zone now
            hz["inside_now"] = sorted(inside)
            if world.tick >= hz["end_tick"]:
                world.emit("nature_hazard_ended", None, {"hazard_id": hz["id"], "force": hz["force"], "phenomenon": hz["phenomenon"],
                           "ticks_active": hz["end_tick"]-hz["start_tick"], "rules_version": HAZARD_VERSION,
                           "exposed": [{"agent_id": aid, "ticks_inside": r["ticks"], "injury": r["injury"], "energy": r["energy"],
                                        "thirst": r["thirst"], "inside_at_end": aid in inside, "left_zone": r["left"]}
                                       for aid, r in sorted(hz["exposed"].items())]}, "environment_rule")
                self.data["counts"]["hazard_"+hz["force"]] = self.data["counts"].get("hazard_"+hz["force"], 0)+1
            else:
                still.append(hz)
        self.data["hazards"] = still

    def active_hazards(self):
        return [h for h in self.data.get("hazards", [])]

    def observe_hazards(self, world, agent):
        """Plain current facts about zones near an inhabitant: what, where, how far, whether it is inside. No names, no duration."""
        out = []
        for h in self.data.get("hazards", []):
            edge = max(0, abs(agent.x-h["x"])+abs(agent.z-h["z"]) - h["radius"])
            if edge <= VIEW_RANGE:
                out.append({"phenomenon": h["phenomenon"], "x": h["x"], "z": h["z"], "radius": h["radius"], "strength": h["strength"],
                            "distance_to_edge": edge, "inside": edge == 0, "since_tick": h["start_tick"]})
        return out

    def observe(self, world, agent):
        # Only local recent sensory effects; no names, cosmology, hidden controller,
        # future hazard schedules, or other inhabitants' outcomes.
        return [copy.deepcopy(e) for e in self.data["recent"]
                if world.tick-e["tick"] <= 6
                and abs(e["x"]-agent.x)+abs(e["z"]-agent.z) <= e["radius"]]
