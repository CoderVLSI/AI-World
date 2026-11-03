"""Versioned, validated configuration for the autonomy foundations.

Two modes exist:

* ``foundations`` (default for new worlds): time-based physiology, a budgeted
  decision scheduler with bounded multi-step intentions, experimentation and
  structured long-term memory.
* ``legacy``: the exact v0.4.0 behaviour (per-tick physiology, fixed decision
  cadence). Old checkpoints load in this mode so their dynamics do not change
  underneath a running experiment.

Every parameter below is recorded in the experiment manifest.  Values are
documented defaults, not tuned to keep a population alive; see
docs/AUTONOMY_ARCHITECTURE.md for their rationale.
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path

CONFIG_SCHEMA_VERSION = 1


def _num(value, name, low=None, high=None, integer=False):
    kind = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, kind) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite {'integer' if integer else 'number'}")
    if low is not None and value < low:
        raise ValueError(f"{name} must be >= {low}")
    if high is not None and value > high:
        raise ValueError(f"{name} must be <= {high}")


@dataclass(frozen=True)
class PhysiologyConfig:
    """Rates are per simulated hour on the 0-100 need scales.

    ``legacy_per_tick`` reproduces v0.4.0 (hunger and thirst +1 per tick).
    """
    mode: str = "time_based"
    hunger_per_hour: float = 100 / 120      # empty -> starving in 5 days without food
    thirst_per_hour: float = 100 / 48       # empty -> dehydrated in 2 days without water
    energy_decay_per_hour: float = 1.0      # passive fatigue while awake
    rest_recovery_per_hour: float = 12.0    # REST restores this much per simulated hour
    effort_scale: float = 0.25              # multiplier on the legacy per-action energy cost
    starvation_damage_per_hour: float = 3.0  # health lost per hour at hunger 100
    dehydration_damage_per_hour: float = 5.0  # health lost per hour at thirst 100
    regen_per_hour: float = 0.75            # health regained per hour when well supplied
    regen_need_ceiling: float = 50.0        # hunger and thirst must both be below this to heal
    infant_need_scale: float = 0.7          # simplified: smaller bodies need less per hour
    child_need_scale: float = 0.85
    illness_per_day: float = 0.01           # baseline chance of falling ill per simulated day
    illness_stress_multiplier: float = 3.0  # applied when depleted or injured
    illness_min_days: float = 2.0
    illness_max_days: float = 5.0
    illness_damage_per_hour: float = 1.2
    illness_supported_scale: float = 0.4    # damage multiplier while fed, hydrated and rested (basic care)
    regrowth_hours: float = 6.0             # renewable resources regain one unit per interval
    max_tick_hours: float = 6.0             # coarser ticks cannot support per-tick actions

    def __post_init__(self):
        if self.mode not in ("time_based", "legacy_per_tick"):
            raise ValueError("unknown physiology mode")
        for name in ("hunger_per_hour", "thirst_per_hour", "rest_recovery_per_hour",
                     "regrowth_hours", "max_tick_hours", "illness_min_days"):
            _num(getattr(self, name), name, 1e-9)
        for name in ("energy_decay_per_hour", "effort_scale", "starvation_damage_per_hour",
                     "dehydration_damage_per_hour", "regen_per_hour", "illness_damage_per_hour",
                     "illness_per_day"):
            _num(getattr(self, name), name, 0)
        _num(self.regen_need_ceiling, "regen_need_ceiling", 0, 100)
        _num(self.infant_need_scale, "infant_need_scale", 0.1, 2)
        _num(self.child_need_scale, "child_need_scale", 0.1, 2)
        _num(self.illness_stress_multiplier, "illness_stress_multiplier", 1)
        _num(self.illness_supported_scale, "illness_supported_scale", 0, 1)
        _num(self.illness_per_day, "illness_per_day", 0, 1)
        if self.illness_max_days < self.illness_min_days:
            raise ValueError("illness_max_days must be >= illness_min_days")


@dataclass(frozen=True)
class SchedulerConfig:
    """Budgeted, fair decision scheduling.  ``mode='legacy'`` is the v0.4.0 cadence."""
    mode: str = "budgeted"
    max_decisions_per_tick: int = 8       # model calls allowed per tick
    max_seconds_per_tick: float = 20.0    # wall-clock cap; applies to real backends only
    max_wait_ticks: int = 36              # waiting beyond this makes an agent top priority
    min_decision_gap_ticks: int = 1       # idle agents may decide again after this many ticks
    default_reconsider_ticks: int = 18    # used when the model names no reconsideration time
    max_task_ticks: int = 72              # hard upper bound on any single intention
    max_path_length: int = 150            # longest route a task may plan
    max_path_expansions: int = 8000       # search budget for a route
    failure_backoff_ticks: int = 6        # delay after a failed model call (scaled by streak)
    critical_need: float = 85.0           # crossing this interrupts a running task
    health_drop_interrupt: float = 15.0   # losing this much health interrupts a task
    dependent_alert_need: float = 60.0    # dependants this needy prompt a guardian to reconsider
    wake_cooldown_ticks: int = 6

    def __post_init__(self):
        if self.mode not in ("budgeted", "legacy"):
            raise ValueError("unknown scheduler mode")
        _num(self.max_decisions_per_tick, "max_decisions_per_tick", 1, integer=True)
        _num(self.max_seconds_per_tick, "max_seconds_per_tick", 0.001)
        for name in ("max_wait_ticks", "min_decision_gap_ticks", "default_reconsider_ticks",
                     "max_task_ticks", "max_path_length", "max_path_expansions",
                     "failure_backoff_ticks", "wake_cooldown_ticks"):
            _num(getattr(self, name), name, 1, integer=True)
        _num(self.critical_need, "critical_need", 1, 100)
        _num(self.health_drop_interrupt, "health_drop_interrupt", 1, 100)
        _num(self.dependent_alert_need, "dependent_alert_need", 1, 100)


@dataclass(frozen=True)
class ReflexConfig:
    """Optional survival reflex.  Disabled by default; never counted as reasoning.

    When enabled it consumes carried water or food once a need passes the
    threshold.  Every intervention is journaled with origin ``survival_reflex``.
    """
    enabled: bool = False
    drink_at: float = 90.0
    eat_at: float = 90.0

    def __post_init__(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("reflex.enabled must be boolean")
        _num(self.drink_at, "drink_at", 1, 100)
        _num(self.eat_at, "eat_at", 1, 100)


@dataclass(frozen=True)
class MemoryConfig:
    """Bounded structured long-term memory (no extra model instances)."""
    enabled: bool = True
    recall_items: int = 8
    recall_chars: int = 1500
    episodic_limit: int = 100
    practical_limit: int = 100
    hypothesis_limit: int = 30
    cultural_limit: int = 100
    procedural_limit: int = 20
    relationship_limit: int = 50
    witness_distance: int = 2             # inhabitants this close to an experiment observe it

    def __post_init__(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("memory.enabled must be boolean")
        for name in ("recall_items", "recall_chars", "episodic_limit", "practical_limit",
                     "hypothesis_limit", "cultural_limit", "procedural_limit",
                     "relationship_limit", "witness_distance"):
            _num(getattr(self, name), name, 1, integer=True)


@dataclass(frozen=True)
class ExperimentConfig:
    enabled: bool = True
    carry_limit_g: int = 25000            # total mass an inhabitant can hold as objects
    min_age_years: float = 6.0
    max_components: int = 6

    def __post_init__(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("experiments.enabled must be boolean")
        _num(self.carry_limit_g, "carry_limit_g", 100, integer=True)
        _num(self.min_age_years, "min_age_years", 0)
        _num(self.max_components, "max_components", 2, 12, integer=True)


@dataclass(frozen=True)
class AutonomyConfig:
    mode: str = "foundations"
    physiology: PhysiologyConfig = field(default_factory=PhysiologyConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    reflex: ReflexConfig = field(default_factory=ReflexConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    experiments: ExperimentConfig = field(default_factory=ExperimentConfig)

    def __post_init__(self):
        if self.mode not in ("foundations", "legacy"):
            raise ValueError("unknown autonomy mode")
        if self.mode == "legacy":
            if self.physiology.mode != "legacy_per_tick" or self.scheduler.mode != "legacy":
                raise ValueError("legacy autonomy requires legacy physiology and scheduler")
        elif self.physiology.mode != "time_based" or self.scheduler.mode != "budgeted":
            raise ValueError("foundations autonomy requires time-based physiology and budgeted scheduler")

    @property
    def legacy(self):
        return self.mode == "legacy"

    @classmethod
    def legacy_mode(cls):
        return cls(mode="legacy", physiology=PhysiologyConfig(mode="legacy_per_tick"),
                   scheduler=SchedulerConfig(mode="legacy"), reflex=ReflexConfig(),
                   memory=MemoryConfig(enabled=False), experiments=ExperimentConfig(enabled=False))

    @classmethod
    def from_dict(cls, data):
        """Strict: unknown sections or keys are errors, never silently ignored."""
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("autonomy configuration must be an object")
        mode = data.get("mode", "foundations")
        base = cls.legacy_mode() if mode == "legacy" else cls()
        sections = {"physiology": PhysiologyConfig, "scheduler": SchedulerConfig, "reflex": ReflexConfig,
                    "memory": MemoryConfig, "experiments": ExperimentConfig}
        unknown = set(data) - set(sections) - {"mode"}
        if unknown:
            raise ValueError("unknown autonomy sections: " + ", ".join(sorted(unknown)))
        built = {}
        for name, klass in sections.items():
            current = getattr(base, name)
            overrides = data.get(name, {})
            if not isinstance(overrides, dict):
                raise ValueError(f"{name} must be an object")
            bad = set(overrides) - {f.name for f in fields(klass)}
            if bad:
                raise ValueError(f"unknown {name} keys: " + ", ".join(sorted(bad)))
            built[name] = klass(**{**asdict(current), **overrides})
        return cls(mode=mode, **built)

    def to_dict(self):
        return asdict(self)


def resolve(autonomy):
    """Accept None, a mode name, a mapping or an ``AutonomyConfig``."""
    if autonomy is None:
        return AutonomyConfig()
    if isinstance(autonomy, AutonomyConfig):
        return autonomy
    if autonomy == "legacy":
        return AutonomyConfig.legacy_mode()
    if autonomy == "foundations":
        return AutonomyConfig()
    return AutonomyConfig.from_dict(autonomy)


def load_experiment_file(path):
    """Explicitly load an experiment file passed with ``--config``.

    ``config/default.json`` is descriptive documentation and is *not* loaded
    automatically; only a file named on the command line is ever read.
    Returns ``(world_parameters, AutonomyConfig)``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError("unsupported configuration schema_version")
    allowed = {"schema_version", "world", "agents", "model", "runtime", "viewer", "autonomy"}
    if set(data) - allowed:
        raise ValueError("unknown configuration sections: " + ", ".join(sorted(set(data) - allowed)))
    world = data.get("world", {})
    if set(world) - {"width", "depth", "seed"}:
        raise ValueError("unknown world keys")
    params = dict(world)
    agents = data.get("agents", {})
    if set(agents) - {"initial_count", "development_count", "decision_interval_ticks"}:
        raise ValueError("unknown agents keys")
    if "initial_count" in agents:
        params["population"] = agents["initial_count"]
    return params, AutonomyConfig.from_dict(data.get("autonomy"))
