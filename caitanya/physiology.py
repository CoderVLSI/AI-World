"""Time-based physiology.

All rates are expressed per *simulated hour* and multiplied by the elapsed
simulated time of a tick (``days_per_tick * 24``).  Changing the tick length
therefore changes how many actions fit in an hour, never how fast bodies
consume resources per hour.

Illness uses a stateless hash of (seed, tick, agent, label) instead of the world
RNG so it neither perturbs nor depends on the existing random stream, and replays
reproduce it exactly.
"""
import hashlib
import math


def hours_per_tick(world):
    return world.biology.days_per_tick * 24


def unit_interval(seed, tick, label, key=""):
    """Deterministic value in [0, 1) derived only from its arguments."""
    raw = hashlib.sha256(f"{seed}|{tick}|{label}|{key}".encode()).digest()
    return int.from_bytes(raw[:8], "big") / 2 ** 64


def _round(value):
    return round(value, 6)


def need_scale(cfg, years):
    return cfg.infant_need_scale if years < 3 else cfg.child_need_scale if years < 13 else 1.0


def effort_cost(world, base_cost):
    """Energy spent by a physical action (legacy keeps the v0.4.0 cost)."""
    cfg = world.autonomy.physiology
    return base_cost if cfg.mode == "legacy_per_tick" else base_cost * cfg.effort_scale


def rest_gain(world):
    cfg = world.autonomy.physiology
    if cfg.mode == "legacy_per_tick":
        return 15
    return _round(cfg.rest_recovery_per_hour * hours_per_tick(world))


def advance(world):
    """Advance hunger, thirst, energy, illness and health by one tick of elapsed time."""
    from .lifecycle import age
    cfg = world.autonomy.physiology
    hours = hours_per_tick(world)
    for a in list(world.agents.values()):
        if not a.alive:
            continue
        scale = need_scale(cfg, age(world, a))
        a.hunger = _round(min(100, a.hunger + cfg.hunger_per_hour * hours * scale))
        a.thirst = _round(min(100, a.thirst + cfg.thirst_per_hour * hours * scale))
        fatigue = cfg.energy_decay_per_hour * hours * (1.5 if a.illness else 1.0)
        a.energy = _round(max(0, a.energy - fatigue))
        damage = {}
        if a.hunger >= 100:
            damage["starvation"] = cfg.starvation_damage_per_hour * hours
        if a.thirst >= 100:
            damage["dehydration"] = cfg.dehydration_damage_per_hour * hours
        _illness(world, cfg, a, hours, damage)
        total = sum(damage.values())
        if total:
            a.health = _round(max(0, a.health - total))
        elif (not a.illness and a.hunger < cfg.regen_need_ceiling
              and a.thirst < cfg.regen_need_ceiling and a.energy > 10 and a.health < 100):
            a.health = _round(min(100, a.health + cfg.regen_per_hour * hours))
        if a.health <= 0:
            a.alive = False
            cause = max(damage, key=damage.get) if damage else "unknown"
            world.emit("death", a.id, {"cause": cause}, "world_rule")


def _illness(world, cfg, a, hours, damage):
    if a.illness:
        if world.tick >= a.illness["until_tick"]:
            a.illness = None
            world.emit("illness_ended", a.id, {}, "world_rule")
        else:
            supported = a.hunger < 50 and a.thirst < 50 and a.energy > 20     # fed, hydrated and rested
            damage["illness"] = cfg.illness_damage_per_hour * hours * (cfg.illness_supported_scale if supported else 1.0)
        return
    stressed = a.hunger > 70 or a.thirst > 70 or a.health < 50
    chance = cfg.illness_per_day * hours / 24 * (cfg.illness_stress_multiplier if stressed else 1)
    if chance and unit_interval(world.seed, world.tick, a.id, "illness") < chance:
        span = cfg.illness_min_days + (cfg.illness_max_days - cfg.illness_min_days) * \
            unit_interval(world.seed, world.tick, a.id, "illness_length")
        a.illness = {"since_tick": world.tick, "until_tick": world.tick + max(1, math.ceil(span * 24 / hours))}
        world.emit("illness_started", a.id, {"stressed": stressed}, "world_rule")


def regrow(world):
    """Renewable resources regain one unit per ``regrowth_hours`` of elapsed time."""
    cfg = world.autonomy.physiology
    hours = hours_per_tick(world)
    now = math.floor(round(world.tick * hours / cfg.regrowth_hours, 9))
    before = math.floor(round((world.tick - 1) * hours / cfg.regrowth_hours, 9))
    intervals = now - before
    if intervals <= 0:
        return
    for node in world.resources.values():
        if node.get("renewable", True):
            node["amount"] = min(node["capacity"], node["amount"] + intervals)
    world.emit("resource_regrowth", None, {}, "world_rule")
