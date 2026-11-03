"""Non-graphic, simplified generational rules. These are experiment parameters, not medical models."""
from dataclasses import dataclass, asdict
from .nature import EDIBLE, RESOURCE_TYPES

@dataclass(frozen=True)
class BiologyConfig:
    days_per_tick: float = 1 / 144
    adulthood_years: float = 18
    gestation_days: float = 280
    recovery_days: float = 365
    proposal_lifetime_days: float = 7
    max_births_per_tick: int = 3

    def __post_init__(self):
        import math
        if not all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in
                   (self.days_per_tick,self.adulthood_years,self.gestation_days,self.recovery_days,self.proposal_lifetime_days)):
            raise ValueError("Biology intervals must be finite and positive")
        if self.adulthood_years < 18 or type(self.max_births_per_tick) is not int or self.max_births_per_tick<1:
            raise ValueError("Invalid adulthood or birth scheduling configuration")

def age(world, a):
    return a.age_years_at_start + (world.tick-a.born_tick)*world.biology.days_per_tick/365

def stage(world,a):
    years=age(world,a)
    return "infant" if years<3 else "child" if years<13 else "adolescent" if years<world.biology.adulthood_years else "adult" if years<65 else "elder"

def food_count(a): return sum(a.inventory.get(k,0) for k in EDIBLE)

def consume_food(a, amount):
    for kind in EDIBLE:
        used=min(amount,a.inventory.get(kind,0));a.inventory[kind]-=used;amount-=used
        if not amount:return
    raise RuntimeError("Food must be validated before consumption")

def nearby(a,b,distance=2): return abs(a.x-b.x)+abs(a.z-b.z)<=distance

def roles_for(sex):
    # Capability is explicit and independent of gender. Intersex capability is
    # left unspecified rather than inventing a uniform reproductive physiology.
    return ["gestate"] if sex=="female" else ["contribute"] if sex=="male" else []

def close_kin(world,a,b):
    pa,pb=set(a.parent_ids),set(b.parent_ids)
    if a.id in pb or b.id in pa or pa & pb:return True
    grandparents=lambda parents:{pid for parent in parents if parent in world.agents for pid in world.agents[parent].parent_ids}
    return a.id in grandparents(pb) or b.id in grandparents(pa)

def gestator_for(a,b):
    if "gestate" in a.reproductive_roles and "contribute" in b.reproductive_roles:return a
    if "gestate" in b.reproductive_roles and "contribute" in a.reproductive_roles:return b

def pairing_error(world,a,b):
    if not b or a.id==b.id or not b.alive or not nearby(a,b):return "partner unavailable or not nearby"
    if any(age(world,p)<world.biology.adulthood_years for p in (a,b)):return "both participants must be adults"
    if close_kin(world,a,b):return "close relatives cannot reproduce"
    gestator=gestator_for(a,b)
    if gestator is None:return "no compatible reproductive capabilities"
    if age(world,gestator)>50:return "outside simulated gestational age range"
    day=world.tick*world.biology.days_per_tick
    if any(p.health<70 or p.hunger>40 or p.thirst>40 or p.energy<40 for p in (a,b)):return "participants need recovery first"
    if any(food_count(p)<4 or p.inventory.get("water",0)<4 for p in (a,b)):return "insufficient family food and water reserves"
    if any(p.reproduction_cooldown_until>day for p in (a,b)):return "parent recovery interval active"
    if any(gestator.id==p["gestator_id"] for p in world.pregnancies):return "pregnancy already active"

def validate_social(world,a,action,p):
    if action in {"REPRODUCE","WITHDRAW_CONSENT","CARE","TEACH","GIVE"}:
        if not isinstance(p.get("target_id"),str):return "invalid target id"
        if action=="WITHDRAW_CONSENT":return None
        b=world.agents.get(p["target_id"])
        if not b or not b.alive or b.id==a.id or not nearby(a,b):return "target unavailable or not nearby"
        if action=="REPRODUCE":return pairing_error(world,a,b)
        if action=="CARE":
            if age(world,a)<world.biology.adulthood_years:return "caregiver must be adult"
            if age(world,b)>=world.biology.adulthood_years:return "CARE is for dependent children; use GIVE for adults"
            if food_count(a)<1 or a.inventory.get("water",0)<1 or a.energy<3:return "care requires food, water and energy"
        if action=="TEACH":
            if not all(isinstance(p.get(k),str) and p[k].strip() for k in ("topic","text")):return "invalid teaching text"
            if len(p["topic"])>80 or len(p["text"])>500:return "teaching exceeds text budget"
            if age(world,a)<3 or age(world,b)<3:return "learner and teacher must be old enough for symbolic learning"
        if action=="GIVE":
            if not isinstance(p.get("resource"),str) or p["resource"] not in RESOURCE_TYPES:return "unknown resource"
            if type(p.get("amount")) is not int or not 1<=p["amount"]<=20:return "invalid transfer quantity"
            if a.inventory.get(p["resource"],0)<p["amount"]:return "insufficient inventory"
    if action=="REVISE":
        if not isinstance(p["work_id"],str):return "invalid work id"
        work=world.works.get(p["work_id"])
        if not work or work["creator_agent_id"]!=a.id or abs(work["x"]-a.x)+abs(work["z"]-a.z)>1:return "only nearby authored work can be revised"
        if not isinstance(p["text"],str) or not p["text"].strip() or len(p["text"])>2000:return "invalid revision"

def apply_social(world,a,action,p,payload):
    b=world.agents.get(p.get("target_id"))
    day=world.tick*world.biology.days_per_tick
    if action=="WITHDRAW_CONSENT":
        a.parenting_proposals.pop(p["target_id"],None);payload["outcome"]="proposal_withdrawn"
    elif action=="REPRODUCE":
        a.parenting_proposals[b.id]=day+world.biology.proposal_lifetime_days
        if b.parenting_proposals.get(a.id,-1)>=day:
            g=gestator_for(a,b)
            pregnancy={"id":f"pregnancy-{world.next_pregnancy_id:06}","parent_ids":[a.id,b.id],"gestator_id":g.id,
                "conception_tick":world.tick,"due_day":day+world.biology.gestation_days}
            world.next_pregnancy_id+=1;world.pregnancies.append(pregnancy)
            for parent in (a,b):
                consume_food(parent,2);parent.inventory["water"]-=2;parent.energy-=10
                parent.reproduction_cooldown_until=pregnancy["due_day"]+world.biology.recovery_days
                parent.parenting_proposals.pop(a.id,None);parent.parenting_proposals.pop(b.id,None)
            payload.update(outcome="pregnancy_started",pregnancy_id=pregnancy["id"],due_day=pregnancy["due_day"])
        else:payload["outcome"]="proposal_recorded_waiting_for_mutual_participation"
    elif action=="CARE":
        consume_food(a,1);a.inventory["water"]-=1;a.energy-=3
        b.hunger=max(0,b.hunger-30);b.thirst=max(0,b.thirst-35);b.energy=min(100,b.energy+5)
        if a.id not in b.guardian_ids:b.guardian_ids.append(a.id)
        b.memories.append({"tick":world.tick,"caregiver_id":a.id,"event":"received_care"})
        payload["outcome"]="child_fed_and_hydrated"
    elif action=="GIVE":
        a.inventory[p["resource"]]-=p["amount"];b.inventory[p["resource"]]=b.inventory.get(p["resource"],0)+p["amount"]
        payload["outcome"]="inventory_transferred"
    elif action=="TEACH":
        record={"topic":p["topic"],"text":p["text"],"teacher_id":a.id,"learned_tick":world.tick,
                "provenance_event_id":f"evt-{len(world.events):09}"}
        b.knowledge.append(record);b.knowledge[:]=b.knowledge[-100:]
        b.memories.append({"tick":world.tick,"teacher_id":a.id,"topic":p["topic"]})
        payload["outcome"]="teaching_recorded_not_verified_as_truth"
    elif action=="REVISE":
        work=world.works[p["work_id"]]
        work.setdefault("history",[]).append({"revision":work["revision"],"text":work["text"],"tick":world.tick})
        work["text"]=p["text"];work["revision"]+=1
        payload["revision"]=work["revision"]
    if b is not None:b.memories[:]=b.memories[-40:]

def advance_lifecycle(world):
    from .engine import Agent
    day=world.tick*world.biology.days_per_tick
    for a in list(world.agents.values()):
        a.parenting_proposals={k:v for k,v in a.parenting_proposals.items() if v>=day}
        if not a.alive:continue
        years=age(world,a)
        if years>=a.lifespan_years:
            a.alive=False;world.emit("death",a.id,{"cause":"aging","age_years":years},"world_rule")
            continue
        if a.age_years_at_start<world.biology.adulthood_years:     # newborns and founding children grow toward adult height
            a.height_cm=round(50+(a.adult_height_cm-50)*min(1,years/world.biology.adulthood_years)**.5)
        if years>=world.biology.adulthood_years and not a.adulthood_recorded:
            a.adulthood_recorded=True
            world.emit("adulthood_reached",a.id,{"age_years":years,"generation":a.generation},"world_rule")
    births=0
    for pregnancy in list(world.pregnancies):
        g=world.agents[pregnancy["gestator_id"]]
        if not g.alive:
            world.pregnancies.remove(pregnancy)
            world.emit("pregnancy_lost",g.id,{"pregnancy_id":pregnancy["id"],"cause":"gestator_died"},"world_rule")
            continue
        if pregnancy["due_day"]>day or births>=world.biology.max_births_per_tick:continue
        parents=[world.agents[aid] for aid in pregnancy["parent_ids"]]
        aid=f"agent-{world.next_agent_id:04}";world.next_agent_id+=1
        sex=world.rng.choices(["female","male","intersex"],[49,49,2])[0]
        height=max(140,min(205,round(sum(p.adult_height_cm for p in parents)/2)+world.rng.randint(-7,7)))
        child=Agent(aid,g.x,g.z,born_tick=world.tick,age_years_at_start=0,height_cm=50,adult_height_cm=height,
            gender="unspecified",biological_sex=sex,reproductive_roles=roles_for(sex),
            parent_ids=list(pregnancy["parent_ids"]),guardian_ids=list(pregnancy["parent_ids"]),
            generation=max(p.generation for p in parents)+1,adulthood_recorded=False,
            lifespan_years=world.rng.randint(70,95),skin_tone=world.rng.choice(parents).skin_tone,
            clothing_color=world.rng.choice(parents).clothing_color,
            inventory={kind:0 for kind in RESOURCE_TYPES})
        world.agents[aid]=child;g.energy=max(0,g.energy-20)
        world.pregnancies.remove(pregnancy);births+=1
        world.emit("birth",aid,{"parent_ids":child.parent_ids,"gestator_id":g.id,"generation":child.generation,
            "pregnancy_id":pregnancy["id"],"inherited_traits":{"adult_height_cm":height,"skin_tone":child.skin_tone}},"world_rule")
        for parent in parents:
            parent.memories.append({"tick":world.tick,"event":"child_born","child_id":aid})
            parent.memories[:]=parent.memories[-40:]
