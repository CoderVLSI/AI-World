"""Authoritative state; all generated actions are untrusted data."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from .nature import RESOURCE_TYPES, EDIBLE, geography, anatomy, climate
from .lifecycle import BiologyConfig, age, stage, roles_for, validate_social, apply_social, advance_lifecycle, pairing_error
from .history import changes, apply_changes
from .root import BrahmanAgent
from .autonomy import AutonomyConfig, resolve
from . import physiology
from .scheduler import DecisionScheduler, TASK_ACTIONS, TASK_SPECS

SCHEMA_VERSION = 2
SUPPORTED_SCHEMAS = (1, 2)
ENGINE_VERSION = "0.5.0"
MOCK_MODEL_ID = "mock/deterministic-forager"
PROMPT_VERSION = "neutral-v4-inquiry"
FOUNDATION = """You are an inhabitant of your environment.
You can observe nearby things, remember events, communicate with others,
move, rest, gather materials, make objects, and learn from what happens.
You have limited time and resources. You cannot access hidden rules or
other inhabitants' private memories. Pursue your own changing practical
and intellectual interests. No particular conclusion is required.
Choose an available action. Do not claim success before confirmation."""

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

@dataclass
class Agent:
    id: str
    x: int
    z: int
    energy: int = 100
    hunger: int = 0
    health: int = 100
    born_tick: int = 0
    alive: bool = True
    inventory: dict = field(default_factory=lambda: {"food": 3, "wood": 0, "stone": 0})
    memories: list = field(default_factory=list)
    relationships: dict = field(default_factory=dict)
    goal: str = ""
    gender: str = "unspecified"
    biological_sex: str = "unspecified"
    age_years_at_start: int = 25
    height_cm: int = 170
    skin_tone: str = "#bd8c68"
    clothing_color: str = "#587d84"
    thirst: int = 0
    body: dict = field(default_factory=anatomy)
    adult_height_cm: int = 170
    reproductive_roles: list = field(default_factory=list)
    parent_ids: list = field(default_factory=list)
    guardian_ids: list = field(default_factory=list)
    generation: int = 0
    lifespan_years: float = 85
    adulthood_recorded: bool = True
    parenting_proposals: dict = field(default_factory=dict)
    reproduction_cooldown_until: float = 0
    knowledge: list = field(default_factory=list)
    skills: dict = field(default_factory=dict)
    task: dict = None                      # active bounded intention (schema v2)
    busy_until_tick: int = 0               # committed timed activity (schema v2)
    illness: dict = None
    ltm: dict = field(default_factory=dict)  # structured long-term memory (private)

@dataclass(frozen=True)
class Intent:
    agent_id: str
    observed_tick: int
    action: str
    parameters: dict = field(default_factory=dict)
    reason_summary: str = ""

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, dict) or set(raw) - {"agent_id", "observed_tick", "action", "parameters", "reason_summary"}:
            raise ValueError("invalid intent envelope")
        intent = cls(**raw)
        if type(intent.observed_tick) is not int or not isinstance(intent.parameters, dict):
            raise ValueError("invalid field type")
        if not isinstance(intent.reason_summary, str) or len(intent.reason_summary) > 300:
            raise ValueError("explanation too long")
        return intent

class MockInferenceBackend:
    """Explicit deterministic test policy, never represented as a real LLM."""
    model_id = MOCK_MODEL_ID
    model_revision = "1"
    calls = 0

    def __init__(self, use_tasks=False):
        # Explicitly labelled test policy: with use_tasks it exercises the multi-step
        # intention machinery. It is still a mock, never an LLM.
        self.use_tasks = bool(use_tasks)
        self.metadata = {"mock_options": {"use_tasks": self.use_tasks}}

    def decide(self, observation):
        self.calls += 1
        a = observation["self"]
        params = {}
        if a.get("thirst",0) >= 15 and a["inventory"].get("water",0):
            action = "DRINK"
        elif a["hunger"] >= 15 and any(a["inventory"].get(k,0) for k in EDIBLE):
            action = "EAT"
        elif a["energy"] < 35:
            action, params = ("REST_FOR", {"hours": 2}) if self.use_tasks else ("REST", params)
        else:
            wanted = {"water"} if a.get("thirst",0)>=12 and not a["inventory"].get("water",0) else set(EDIBLE) if a["hunger"]>=12 and not any(a["inventory"].get(k,0) for k in EDIBLE) else set(RESOURCE_TYPES)
            nodes = sorted((n for n in observation["resources"] if n["amount"] > 0 and n["kind"] in wanted and a["inventory"].get(n["kind"],0)<6),
                           key=lambda n: (abs(n["x"]-a["x"])+abs(n["z"]-a["z"]), n["id"]))
            if not nodes:
                action, params = ("REST_FOR", {"hours": 1}) if self.use_tasks else ("REST", params)
            else:
                n = nodes[0]
                if (n["x"], n["z"]) == (a["x"], a["z"]):
                    action, params = "GATHER", {"resource_id": n["id"]}
                elif self.use_tasks:
                    action, params = "GATHER_AT", {"resource_id": n["id"], "amount": 2}
                else:
                    dx, dz = n["x"]-a["x"], n["z"]-a["z"]
                    step = (1 if dx > 0 else -1, 0) if dx else (0, 1 if dz > 0 else -1)
                    choices=[step,(0,1),(1,0),(0,-1),(-1,0)]
                    blocked={tuple(p) for p in observation.get("blocked",[])}
                    choices=[s for s in choices if (a["x"]+s[0],a["z"]+s[1]) not in blocked]
                    if choices: action, params = "MOVE", {"dx":choices[0][0],"dz":choices[0][1]}
                    else: action="REST"
        return Intent(a["id"], observation["tick"], action, params, "deterministic mock policy")

def redact_private(state):
    """Remove everything an outside witness must never see (root, memories, RNG, scheduler internals)."""
    for key in ("rng_state", "root", "scheduler"):
        state.pop(key, None)
    for a in state["agents"].values():
        for key in ("memories", "parenting_proposals", "ltm"):
            a.pop(key, None)
    return state

class World:
    def __init__(self, seed=314159, population=5, width=64, depth=64, backend=None, biology=None, spawn_radius=8,
                 autonomy=None):
        if not (1 <= population and width >= 8 and depth >= 8):
            raise ValueError("invalid world dimensions or population")
        if type(spawn_radius) is not int or spawn_radius<1:raise ValueError("invalid starting radius")
        self.autonomy = resolve(autonomy)
        self.backend = backend or MockInferenceBackend(use_tasks=not self.autonomy.legacy)
        self.biology=biology or BiologyConfig()
        self._validate_clock()
        self.scheduler = DecisionScheduler(self.autonomy.scheduler)
        self.objects, self.next_object_id = {}, 0
        self.ledger = {"dispersed_g": 0.0, "atmosphere_g": 0.0}
        self._meta, self._selected_by = {}, None
        self._build_registry()
        self.pregnancies=[];self.next_agent_id=population;self.next_pregnancy_id=0
        self.rng = random.Random(seed)
        self.seed, self.width, self.depth, self.tick = seed, width, depth, 0
        self.status = "RUNNING"
        self.decision_cursor=0
        self.events, self.rejections, self.works, self.parts = [], [], {}, {}
        self.agents = {}
        self.resources = {}
        self.terrain = [dict(x=x,z=z,size=min(8,width-x,depth-z),**geography(x+4,z+4,width,depth,seed))
                        for x in range(0,width,8) for z in range(0,depth,8)]
        for i in range(max(120, population * 6, width*depth//40)):
            x, z = self.rng.randrange(width), self.rng.randrange(3, depth)
            tile=geography(x,z,width,depth,seed)
            if not tile["walkable"]: continue
            kinds={"forest":["wood","fruit","herbs","plant_fiber"],"highland":["stone","iron_ore","copper_ore","coal"],
                "wetland":["water","clay","fish","plant_fiber"],"dryland":["sand","salt","stone"],
                "grassland":["food","grain","herbs","water"]}[tile["biome"]]
            kind=self.rng.choice(kinds);renewable,capacity=RESOURCE_TYPES[kind]
            self.resources[f"resource-{i:04}"] = dict(id=f"resource-{i:04}", x=x, z=z,
                kind=kind, amount=capacity, capacity=capacity, renewable=renewable)
        # Initial nearby resources are ecology, not agent-authored events.
        cx,cz=width//4,depth//2
        spawn_points=[(x,z) for x in range(max(0,cx-spawn_radius),min(width,cx+spawn_radius+1))
            for z in range(max(3,cz-spawn_radius),min(depth,cz+spawn_radius+1)) if geography(x,z,width,depth,seed)["walkable"]]
        if not spawn_points:raise ValueError("Starting area has no walkable terrain")
        for i in range(population):
            x,z=self.rng.choice(spawn_points)
            aid = f"agent-{i:04}"
            self.agents[aid] = Agent(aid,x,z,gender=("woman","man","nonbinary")[i%3],
                biological_sex=self.rng.choices(["female","male","intersex"],[49,49,2])[0],age_years_at_start=self.rng.randrange(18,46),
                height_cm=self.rng.randrange(152,193),skin_tone=self.rng.choice(["#e4bc98","#bd8c68","#8d5c40","#573b2e"]),
                clothing_color=self.rng.choice(["#678b91","#b38e5b","#8e709d","#758f62"]))
            self.agents[aid].inventory.update({k:0 for k in RESOURCE_TYPES if k not in self.agents[aid].inventory})
            self.agents[aid].inventory["water"]=3
            self.agents[aid].adult_height_cm=self.agents[aid].height_cm
            self.agents[aid].reproductive_roles=roles_for(self.agents[aid].biological_sex)
            self.agents[aid].lifespan_years=self.rng.randint(70,95)
            rid = f"spawn-food-{i}"
            self.resources[rid] = dict(id=rid, x=x, z=z, kind="food", amount=8, capacity=8)
            rid=f"spawn-water-{i}"
            self.resources[rid]=dict(id=rid,x=x,z=z,kind="water",amount=40,capacity=40,renewable=True)
        self.manifest = dict(schema_version=1, world_seed=seed, model_id=self.backend.model_id,
            model_revision=self.backend.model_revision, prompt_version=PROMPT_VERSION,
            engine_version="0.3.0", inference_backend=type(self.backend).__name__,biology=asdict(self.biology),
            autonomy=self.autonomy.to_dict(),
            starting_radius=spawn_radius,
            configuration_hash=digest(dict(seed=seed, population=population, width=width, depth=depth,biology=asdict(self.biology),spawn_radius=spawn_radius)))
        self.manifest.update(getattr(self.backend,"metadata",{}))
        self.root = BrahmanAgent()
        self.root.register(self)
        self.manifest["engine_version"] = ENGINE_VERSION
        self.manifest["autonomy_hash"] = digest(self.autonomy.to_dict())
        self.initial_state = self.state()
        self._last_committed_state=copy.deepcopy(self.initial_state)

    @property
    def hours_per_tick(self):
        return physiology.hours_per_tick(self)

    @property
    def is_real_backend(self):
        return self.backend.model_id != MOCK_MODEL_ID

    def _validate_clock(self):
        if not self.autonomy.legacy and self.hours_per_tick > self.autonomy.physiology.max_tick_hours:
            raise ValueError(
                f"a tick of {self.hours_per_tick:.2f} h is too coarse for time-based physiology "
                f"(max {self.autonomy.physiology.max_tick_hours} h); use a smaller days_per_tick or autonomy='legacy'")

    def _build_registry(self):
        registry = {}
        if not self.autonomy.legacy:
            from .scheduler import task_registry
            registry.update(task_registry())
            if self.autonomy.experiments.enabled:
                from .experiments import registry as experiment_registry
                registry.update(experiment_registry(self))
            if self.autonomy.memory.enabled:
                from .memory import registry as memory_registry
                registry.update(memory_registry(self))
        self.registry = registry

    def state(self):
        rng=self.rng.getstate()
        return dict(schema_version=SCHEMA_VERSION, seed=self.seed, width=self.width, depth=self.depth, tick=self.tick,
            status=self.status, root=self.root.state(), agents={k: asdict(v) for k,v in self.agents.items()},
            autonomy=self.autonomy.to_dict(), scheduler=self.scheduler.state(), objects=copy.deepcopy(self.objects),
            next_object_id=self.next_object_id, ledger=dict(self.ledger),
            resources=copy.deepcopy(self.resources), works=copy.deepcopy(self.works),
            parts=copy.deepcopy(self.parts), manifest=copy.deepcopy(self.manifest), rng_state=[rng[0],list(rng[1]),rng[2]],decision_cursor=self.decision_cursor,
            biology=asdict(self.biology),pregnancies=copy.deepcopy(self.pregnancies),next_agent_id=self.next_agent_id,next_pregnancy_id=self.next_pregnancy_id)

    def public(self):
        state = redact_private(self.state())
        for a in state["agents"].values():
            a["age_years"]=round(age(self,self.agents[a["id"]]),3)
            a["life_stage"]=stage(self,self.agents[a["id"]])
        state["metrics"] = self.metrics()
        state["terrain"]=self.terrain
        state["climate"]=climate(self.tick,self.biology.days_per_tick)
        state["calendar"]={"elapsed_days":round(self.tick*self.biology.days_per_tick,4),"days_per_tick":self.biology.days_per_tick,
            "accelerated":self.biology.days_per_tick>1/144}
        state["resource_catalog"]={k:{"renewable":v[0]} for k,v in RESOURCE_TYPES.items()}
        return state

    def observe(self, aid):
        a = self.agents[aid]
        nearby = lambda o: abs(o["x"]-a.x)+abs(o["z"]-a.z) <= 8
        own=asdict(a);own.update(age_years=round(age(self,a),3),life_stage=stage(self,a))
        own["knowledge"]=own["knowledge"][-6:]
        own.pop("ltm",None);own.pop("task",None);ill=own.pop("illness",None);busy=own.pop("busy_until_tick",0)
        nearby_agents=[b for b in self.agents.values() if b.id!=aid and b.alive and nearby(asdict(b))]
        extra={}
        if not self.autonomy.legacy:
            for need in ("hunger","thirst","energy","health"):own[need]=round(own[need])
            own["unwell"]=bool(ill)
            own["busy_for_ticks"]=max(0,busy-self.tick)
            hours=self.hours_per_tick
            extra["clock"]=dict(hours_per_tick=round(hours,4),**{k:v for k,v in climate(self.tick,self.biology.days_per_tick).items() if k in("hour","day","season")})
            if a.task:own["task"]={k:a.task[k] for k in("id","kind","params","reconsider_tick","expires_tick")}|{"progress":a.task["progress"],"steps_remaining":max(0,len(a.task["path"])-a.task["step"])}
            if self.autonomy.experiments.enabled:
                from .experiments import observable_objects
                extra["objects"]=observable_objects(self,a)
            if self.autonomy.memory.enabled:
                from .memory import recall
                extra["recalled"]=recall(self,a)
        return dict(tick=self.tick, self=own, **extra, resources=[copy.deepcopy(n) for n in self.resources.values() if nearby(n)],
            climate=climate(self.tick,self.biology.days_per_tick),
            eligible_parenting_partners=[b.id for b in nearby_agents if pairing_error(self,a,b) is None],
            parenting_requests=[b.id for b in nearby_agents if b.parenting_proposals.get(aid,-1)>=self.tick*self.biology.days_per_tick],
            blocked=[[x,z] for x,z in [(a.x-1,a.z),(a.x+1,a.z),(a.x,a.z-1),(a.x,a.z+1)]
                     if not (0<=x<self.width and 0<=z<self.depth) or not geography(x,z,self.width,self.depth,self.seed)["walkable"]],
            others=[dict(id=b.id,x=b.x,z=b.z,age_years=round(age(self,b),3),life_stage=stage(self,b),
                gender=b.gender,health=b.health,hunger=b.hunger,thirst=b.thirst,parent_ids=b.parent_ids) for b in nearby_agents],
            works=[copy.deepcopy(w) for w in self.works.values() if nearby(w)])

    def reject(self, intent, reason):
        self.rejections.append(dict(tick=self.tick, actor_id=getattr(intent,"agent_id",None), reason=reason))
        self.emit("intent_rejected",getattr(intent,"agent_id",None),{"reason":str(reason)[:300]},"validation")
        return False, reason

    def apply(self, raw, origin=None, request_id=None, task_id=None, selected_by=None):
        """Validate and execute one intent.

        ``origin`` attributes the action: ``lfm_decision``, ``mock_policy``,
        ``mechanical_execution`` or ``survival_reflex``.  Direct callers (tests,
        operators) pass none and are journaled exactly as in v0.4.0.
        """
        self._meta = {k: v for k, v in (("origin", origin), ("model_request_id", request_id), ("task_id", task_id)) if v}
        self._selected_by = selected_by
        try:
            return self._apply(raw, origin)
        finally:
            self._meta, self._selected_by = {}, None

    def _spend_energy(self, a, base_cost):
        cost = physiology.effort_cost(self, base_cost)
        if a.energy < cost:
            return False
        a.energy = round(a.energy - cost, 6) if cost != int(cost) else a.energy - int(cost)
        return True

    def _apply(self, raw, origin):
        try:
            intent = raw if isinstance(raw, Intent) else Intent.parse(raw)
        except (ValueError, TypeError) as e:
            return self.reject(None, str(e))
        if not isinstance(intent.agent_id,str) or not isinstance(intent.action,str) or not isinstance(intent.parameters,dict):
            return self.reject(intent,"invalid field type")
        a = self.agents.get(intent.agent_id)
        if not a or not a.alive: return self.reject(intent, "actor unavailable")
        if intent.observed_tick != self.tick: return self.reject(intent, "stale observation")
        if a.busy_until_tick > self.tick: return self.reject(intent, "busy with an ongoing activity")
        p, action = intent.parameters, intent.action
        expected = {"MOVE":{"dx","dz"}, "GATHER":{"resource_id"}, "REST":set(), "EAT":set(), "DRINK":set(), "WAIT":set(),
                    "SPEAK":{"text"}, "WRITE":{"title","text"}, "READ":{"work_id"}, "PLACE":{"material","shape"},
                    "REPRODUCE":{"target_id"},"WITHDRAW_CONSENT":{"target_id"},"CARE":{"target_id"},
                    "GIVE":{"target_id","resource","amount"},"TEACH":{"target_id","topic","text"},"REVISE":{"work_id","text"},"REFLECT":{"text"}}
        spec = self.registry.get(action)
        if spec is not None:
            if not isinstance(action, str) or not spec.accepts(p): return self.reject(intent, "invalid action parameters")
        elif action not in expected or set(p) != expected[action]: return self.reject(intent, "invalid action parameters")
        years=age(self,a)
        if years<3 and action not in {"REST","WAIT","EAT","DRINK"}:return self.reject(intent,"infant cannot perform this action")
        if spec is not None:
            if years < spec.min_age: return self.reject(intent, "not old enough for this action")
            payload = dict(parameters=copy.deepcopy(p), reason_summary=intent.reason_summary)
            error = spec.run(self, a, p, payload)
            if error: return self.reject(intent, error)
            if spec.skill: a.skills[spec.skill] = a.skills.get(spec.skill, 0) + 1
            return self._finish(a, action, payload, origin)
        if years<6 and action=="GATHER":return self.reject(intent,"not old enough to gather independently")
        if years<12 and action=="PLACE":return self.reject(intent,"not old enough for construction")
        social_error=validate_social(self,a,action,p)
        if social_error:return self.reject(intent,social_error)
        # Complete validation before any authoritative mutation.
        if action == "MOVE":
            if any(type(p[k]) is not int for k in ("dx","dz")) or abs(p["dx"])+abs(p["dz"]) != 1:
                return self.reject(intent,"invalid movement")
            if not (0 <= a.x+p["dx"] < self.width and 3 <= a.z+p["dz"] < self.depth):
                return self.reject(intent,"blocked terrain")
            if not geography(a.x+p["dx"],a.z+p["dz"],self.width,self.depth,self.seed)["walkable"]:
                return self.reject(intent,"water requires a crossing")
        if action == "GATHER":
            if not isinstance(p["resource_id"],str): return self.reject(intent,"invalid resource id")
            n = self.resources.get(p["resource_id"])
            if not n or (n["x"],n["z"]) != (a.x,a.z) or n["amount"] <= 0: return self.reject(intent,"resource unavailable")
        if action == "EAT" and not any(a.inventory.get(k,0) for k in EDIBLE): return self.reject(intent,"no food")
        if action == "DRINK" and a.inventory.get("water",0)<1:return self.reject(intent,"no water")
        if action in {"SPEAK","WRITE","REFLECT"}:
            if any(not isinstance(v,str) for v in p.values()) or len(p["text"]) > 2000 or not p["text"].strip():
                return self.reject(intent,"invalid text")
            if action == "WRITE" and len(p["title"]) > 100: return self.reject(intent,"title too long")
        if action == "READ":
            if not isinstance(p["work_id"],str): return self.reject(intent,"invalid work id")
            w = self.works.get(p["work_id"])
            if not w or abs(w["x"]-a.x)+abs(w["z"]-a.z)>1: return self.reject(intent,"work not visible")
        if action == "PLACE":
            if p["material"] not in ("wood","stone") or p["shape"] not in ("block","slab","rod"):
                return self.reject(intent,"invalid primitive")
            if a.inventory[p["material"]] < 2: return self.reject(intent,"insufficient material")
            if any((part["x"],part["z"]) == (a.x,a.z) for part in self.parts.values()): return self.reject(intent,"placement collision")
        cost = 2 if action in ("MOVE","GATHER","PLACE","WRITE","REVISE","TEACH") else 0
        if not self._spend_energy(a, cost): return self.reject(intent,"insufficient energy")
        payload = dict(parameters=copy.deepcopy(p), reason_summary=intent.reason_summary)
        if action == "MOVE": a.x += p["dx"]; a.z += p["dz"]
        elif action == "GATHER": n["amount"] -= 1; a.inventory[n["kind"]] += 1
        elif action == "REST": a.energy = min(100,a.energy+physiology.rest_gain(self))
        elif action == "REFLECT":
            a.memories.append(dict(tick=self.tick, reflection=p["text"], verified=False))
            payload = {"outcome": "private_reflection_recorded"}
        elif action == "EAT":
            kind=next(k for k in EDIBLE if a.inventory.get(k,0)>0)
            a.inventory[kind]-=1; a.hunger=max(0,a.hunger-30)
        elif action == "DRINK":a.inventory["water"]-=1;a.thirst=max(0,a.thirst-35)
        elif action == "WRITE":
            wid = f"work-{len(self.works):06}"
            self.works[wid] = dict(id=wid, creator_agent_id=a.id, created_tick=self.tick, revision=1,
                x=a.x,z=a.z,title=p["title"],text=p["text"],history=[],provenance_event_id=f"evt-{len(self.events):09}")
            payload["work_id"] = wid
        elif action == "READ":
            payload["text"] = w["text"]
            a.knowledge.append({"topic":w["title"],"text":w["text"][:500],"work_id":w["id"],"revision":w["revision"],"learned_tick":self.tick})
            a.knowledge[:]=a.knowledge[-100:]
        elif action == "PLACE":
            a.inventory[p["material"]] -= 2
            pid = f"part-{len(self.parts):06}"
            self.parts[pid] = dict(id=pid,creator_agent_id=a.id,created_tick=self.tick,x=a.x,z=a.z,**p)
            payload["part_id"] = pid
        if action == "SPEAK":
            for b in self.agents.values():
                if b.id != a.id and b.alive and abs(b.x-a.x)+abs(b.z-a.z)<=5:
                    b.memories.append(dict(tick=self.tick, speaker=a.id,text=p["text"]))
                    b.memories[:] = b.memories[-40:]
        apply_social(self,a,action,p,payload)
        if action in {"MOVE","GATHER","PLACE","WRITE","REVISE","TEACH","CARE"}:
            skill={"MOVE":"travel","GATHER":"foraging","PLACE":"construction","WRITE":"writing","REVISE":"writing","TEACH":"teaching","CARE":"caregiving"}[action]
            a.skills[skill]=a.skills.get(skill,0)+1
        return self._finish(a, action, payload, origin, p)

    def _finish(self, a, action, payload, origin, params=None):
        """Common bookkeeping for every accepted action."""
        a.memories.append(dict(tick=self.tick, action=action, confirmed=True))
        a.memories[:] = a.memories[-40:]
        self.emit(action.lower(),a.id,payload,"validated_action")
        self.root.register(self)
        self.root.record(a.id, action, payload)
        if origin in ("lfm_decision", "mock_policy") and a.task and action not in TASK_ACTIONS:
            self.scheduler.supersede(self, a, "new_decision")
        if self.autonomy.memory.enabled:
            from .memory import after_action
            after_action(self, a, action, params if params is not None else payload.get("parameters", {}), payload)
        return True,"accepted"

    def emit(self, kind, actor, payload, source, **extra):
        event = dict(schema_version=1,event_id=f"evt-{len(self.events):09}", world_tick=self.tick,
            actor_id=actor,type=kind,payload=payload,source=source)
        event.update(self._meta)
        event.update({k: v for k, v in extra.items() if v})
        self.events.append(event)

    def step(self):
        if self.status != "RUNNING": return
        self.tick += 1
        if self.autonomy.legacy:
            self._step_legacy()
        else:
            self._step_foundations()
        # Private deltas preserve exact replay without duplicating static terrain,
        # anatomy and unchanged resources in every event.
        committed=self.state()
        self.emit("tick_committed",None,{"patch":changes(self._last_committed_state,committed),"state_checksum":digest(committed)},"world_rule")
        self._last_committed_state=committed

    def _step_foundations(self):
        """Time-based physiology, then lifecycle, then the budgeted scheduler."""
        physiology.advance(self)
        advance_lifecycle(self)
        self.root.sustain(self)
        physiology.regrow(self)
        if self.autonomy.experiments.enabled:
            from .experiments import advance_objects
            advance_objects(self)
        self.scheduler.run(self)

    def _step_legacy(self):
        """Verbatim v0.4.0 dynamics, used for ``autonomy='legacy'`` and migrated runs."""
        for a in self.agents.values():
            if not a.alive: continue
            a.hunger = min(100,a.hunger+1)
            a.thirst=min(100,a.thirst+1)
            if a.hunger == 100: a.health = max(0,a.health-2)
            if a.thirst == 100:a.health=max(0,a.health-3)
            if not a.health: a.alive=False; self.emit("death",a.id,{"cause":"scarcity"},"world_rule")
        advance_lifecycle(self)
        self.root.sustain(self)
        if self.tick % 12 == 0:
            for n in self.resources.values():
                if n.get("renewable",True):n["amount"] = min(n["capacity"],n["amount"]+1)
            self.emit("resource_regrowth",None,{},"world_rule")
        if self.tick % 3 == 0:
            ids=sorted(aid for aid,a in self.agents.items() if a.alive and age(self,a)>=3)
            real=self.is_real_backend
            limit=min(5,len(ids)) if real else len(ids)
            start=time.monotonic()
            for _ in range(limit):
                if real and time.monotonic()-start>=20:break
                aid=ids[self.decision_cursor%len(ids)];self.decision_cursor+=1
                try:
                    accepted,reason=self.apply(self.root.delegate(self,aid))
                    if real and accepted:
                        self.events[-1]["model_request_id"]=self.backend.last_request["request_id"]
                    self.agents[aid].memories.append(dict(tick=self.tick,feedback=reason,accepted=accepted))
                    self.agents[aid].memories[:]=self.agents[aid].memories[-40:]
                except Exception as exc:
                    self.reject(Intent(aid,self.tick,"WAIT"),"inference_failed: "+str(exc)[:200])
                    self.emit("inference_failed",aid,{"error":str(exc)[:200]},"inference_error")
                    self.agents[aid].memories.append(dict(tick=self.tick,feedback="No action executed; decision failed."))

    def metrics(self):
        return dict(tick=self.tick,population=sum(a.alive for a in self.agents.values()),
            pregnancies=len(self.pregnancies),births=sum(e["type"]=="birth" for e in self.events),
            highest_generation=max((a.generation for a in self.agents.values()),default=0),
            attempted=len(self.rejections)+sum(e["source"]=="validated_action" for e in self.events),
            rejected=len(self.rejections),events=len(self.events),backend=type(self.backend).__name__,
            inference=self.backend.metrics() if hasattr(self.backend,"metrics") else {"model_instances":0},
            deaths=self.death_causes(),scheduler=self.scheduler.report(self) if not self.autonomy.legacy else None,
            knowledge=self._knowledge_metrics(),
            autonomy_mode=self.autonomy.mode)

    def _knowledge_metrics(self):
        if self.autonomy.legacy or not self.autonomy.memory.enabled:return None
        from .memory import knowledge_metrics
        return knowledge_metrics(self)

    def death_causes(self):
        causes = {}
        for e in self.events:
            if e["type"] == "death":
                cause = e["payload"].get("cause", "unknown")
                causes[cause] = causes.get(cause, 0) + 1
        return causes

    def checkpoint(self, directory):
        directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
        body = dict(state=self.state(), initial_state=self.initial_state, events=self.events, rejections=self.rejections,
            last_committed_state=self._last_committed_state)
        envelope = dict(checksum=digest(body),body=body)
        target=directory/f"checkpoint-{self.tick:09}.json"
        temporary=target.with_suffix(".tmp")
        with temporary.open("w",encoding="utf-8") as f:
            f.write(canonical(envelope)); f.flush(); os.fsync(f.fileno())
        os.replace(temporary,target)
        return target

    @classmethod
    def restore(cls,path,backend=None):
        envelope=json.loads(Path(path).read_text(encoding="utf-8")); body=envelope["body"]
        if digest(body) != envelope["checksum"]: raise ValueError("checkpoint checksum mismatch")
        if body["state"]["schema_version"] not in SUPPORTED_SCHEMAS: raise ValueError("unsupported schema")
        options=body["state"]["manifest"].get("mock_options",{})
        obj=cls.__new__(cls); obj.backend=backend or MockInferenceBackend(use_tasks=options.get("use_tasks",False))
        obj.load_state(body["state"])
        if obj.backend.model_id != obj.manifest["model_id"] or obj.backend.model_revision != obj.manifest["model_revision"]:
            raise ValueError("restore backend does not match manifest")
        obj.events=body["events"]; obj.rejections=body["rejections"]; obj.initial_state=body["initial_state"]
        obj._last_committed_state=body.get("last_committed_state",copy.deepcopy(body["state"]))
        return obj

    def load_state(self,s):
        """Accepts schema 1 (v0.4.0) and 2 states. Schema 1 loads in legacy mode so its dynamics are unchanged."""
        if s.get("schema_version") not in SUPPORTED_SCHEMAS:raise ValueError("unsupported schema")
        self.autonomy=AutonomyConfig.from_dict(s["autonomy"]) if "autonomy" in s else AutonomyConfig.legacy_mode()
        self.scheduler=DecisionScheduler(self.autonomy.scheduler,s.get("scheduler"))
        self.objects=copy.deepcopy(s.get("objects",{}));self.next_object_id=s.get("next_object_id",0)
        self.ledger=dict(s.get("ledger",{"dispersed_g":0.0,"atmosphere_g":0.0}))
        self._meta,self._selected_by={},None
        self._build_registry()
        self.biology=BiologyConfig(**s.get("biology",{}));self.pregnancies=copy.deepcopy(s.get("pregnancies",[]))
        self.next_agent_id=s.get("next_agent_id",len(s["agents"]));self.next_pregnancy_id=s.get("next_pregnancy_id",0)
        self.decision_cursor=s.get("decision_cursor",0)
        for k in ("seed","width","depth","tick","status","resources","works","parts","manifest"):
            setattr(self,k,copy.deepcopy(s[k]))
        self.agents={k:Agent(**v) for k,v in s["agents"].items()}
        self.root=BrahmanAgent(s.get("root"))
        self.root.register(self)
        for aid,a in self.agents.items():
            if "reproductive_roles" not in s["agents"][aid]:a.reproductive_roles=roles_for(a.biological_sex)
            if "adult_height_cm" not in s["agents"][aid]:a.adult_height_cm=a.height_cm
        self.terrain=[dict(x=x,z=z,size=min(8,self.width-x,self.depth-z),**geography(x+4,z+4,self.width,self.depth,self.seed))
                      for x in range(0,self.width,8) for z in range(0,self.depth,8)]
        def tuples(v): return tuple(tuples(x) for x in v) if isinstance(v,(list,tuple)) else v
        self.rng=random.Random(); self.rng.setstate(tuples(s["rng_state"]))

    def replay(self,tick):
        if type(tick) is not int or not 0 <= tick <= self.tick: raise ValueError("invalid replay tick")
        if tick == 0: return copy.deepcopy(self.initial_state)
        state=copy.deepcopy(self.initial_state)
        for event in self.events:
            if event["type"]=="tick_committed":
                if "state" in event["payload"]:state=copy.deepcopy(event["payload"]["state"])
                else:apply_changes(state,event["payload"]["patch"])
                expected=event["payload"].get("state_checksum")
                if expected and digest(state)!=expected:raise ValueError("history state checksum mismatch")
                if event["world_tick"]==tick:return state
        raise ValueError("tick not committed")

    @classmethod
    def recover(cls,directory,backend=None):
        """Newest valid checkpoint plus only complete committed journal ticks."""
        directory=Path(directory);world=None;failures=[]
        for candidate in sorted(directory.glob("checkpoint-*.json"),reverse=True):
            try:
                world=cls.restore(candidate,backend=backend);break
            except (ValueError,KeyError,TypeError) as exc:failures.append(str(exc))
        if world is None:raise ValueError("No valid compatible checkpoint: "+"; ".join(failures[-3:]))
        journal=directory/"events.jsonl"
        if not journal.exists():return world
        expected=len(world.events);pending=[];state=copy.deepcopy(world._last_committed_state)
        with journal.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.endswith("\n"):break  # abrupt partial write is uncommitted
                try:
                    event=json.loads(line);index=int(event["event_id"].removeprefix("evt-"))
                except (ValueError,KeyError,TypeError) as exc:raise ValueError("Corrupt journal record") from exc
                if index<expected:continue
                if index!=expected+len(pending):raise ValueError("Journal event gap or duplicate")
                pending.append(event)
                if event["type"]!="tick_committed":continue
                candidate=copy.deepcopy(state)
                if "state" in event["payload"]:candidate=copy.deepcopy(event["payload"]["state"])
                else:apply_changes(candidate,event["payload"]["patch"])
                if candidate["tick"]!=state["tick"]+1:raise ValueError("Journal tick gap")
                checksum=event["payload"].get("state_checksum")
                if checksum and digest(candidate)!=checksum:raise ValueError("Journal state checksum mismatch")
                world.load_state(candidate);world._last_committed_state=copy.deepcopy(candidate)
                for record in pending:
                    if record["type"]=="intent_rejected":world.rejections.append({"tick":record["world_tick"],"actor_id":record["actor_id"],"reason":record["payload"]["reason"]})
                world.events.extend(pending);expected+=len(pending);pending=[];state=candidate
        return world
