"""Stylized animal ecology, not calibrated zoology. No language-model decisions."""
import copy
from dataclasses import asdict, dataclass
import random


SPECIES = {
    'deer': dict(name='Deer',group='mammal',icon='🦌',habitats=['forest','grassland','wetland'],food=['plant_fiber','herbs'],prey=[],maturity=180,life=4000,color='#d6b78a'),
    'rabbit': dict(name='Rabbit',group='mammal',icon='🐇',habitats=['forest','grassland'],food=['grain','herbs'],prey=[],maturity=90,life=1800,color='#ddd3bb'),
    'boar': dict(name='Wild boar',group='mammal',icon='🐗',habitats=['forest','wetland'],food=['fruit','grain','herbs'],prey=[],maturity=240,life=3500,color='#9e8273'),
    'wolf': dict(name='Wolf',group='mammal',icon='🐺',habitats=['forest','grassland','highland'],food=[],prey=['rabbit','deer'],maturity=300,life=3000,color='#a7b8bd'),
    'fox': dict(name='Fox',group='mammal',icon='🦊',habitats=['forest','grassland'],food=['fruit'],prey=['rabbit','sparrow'],maturity=240,life=2500,color='#e5a16b'),
    'sparrow': dict(name='Sparrow',group='bird',icon='🐦',habitats=['forest','grassland'],food=['grain'],prey=['bee','butterfly'],maturity=60,life=1000,color='#d0bb8c'),
    'crow': dict(name='Crow',group='bird',icon='🐦‍⬛',habitats=['forest','grassland','wetland'],food=['grain','fruit'],prey=['bee','butterfly'],maturity=180,life=3000,color='#7a8790'),
    'duck': dict(name='Duck',group='bird',icon='🦆',habitats=['water','wetland'],food=['grain','herbs'],prey=[],maturity=120,life=2200,color='#9cccab'),
    'owl': dict(name='Owl',group='bird',icon='🦉',habitats=['forest','grassland'],food=[],prey=['rabbit','sparrow'],maturity=180,life=2800,color='#c9b7a6'),
    'carp': dict(name='Carp',group='fish',icon='🐟',habitats=['water'],food=[],prey=[],maturity=180,life=3000,color='#94c9d6'),
    'butterfly': dict(name='Butterfly',group='insect',icon='🦋',habitats=['forest','grassland','wetland'],food=['herbs'],prey=[],maturity=4,life=60,color='#d2afe1'),
    'bee': dict(name='Bee',group='insect',icon='🐝',habitats=['forest','grassland','wetland'],food=['herbs'],prey=[],maturity=5,life=90,color='#e0cc78'),
}


# The floodplain biome (geography-v2) counts as grassland for every species that lives on grassland; v1 worlds never contain it.
for _species in SPECIES.values():
    if 'grassland' in _species['habitats'] and 'floodplain' not in _species['habitats']:
        _species['habitats'].append('floodplain')


@dataclass
class Animal:
    id: str
    species: str
    x: int
    z: int
    sex: str
    age_days: float
    energy: float = 75
    health: float = 100
    alive: bool = True
    action: str = 'resting'
    parent_ids: list = None
    next_birth_day: float = 0

    def __post_init__(self):
        if self.parent_ids is None:self.parent_ids=[]


class Ecosystem:
    def __init__(self,world,seed=2718,per_species=6,birth_budget=4,days_per_tick=1/24):
        if type(per_species) is not int or per_species<0 or type(birth_budget) is not int or birth_budget<1:
            raise ValueError('Invalid wildlife configuration')
        if type(days_per_tick) not in (int,float) or not 0<days_per_tick<=1:
            raise ValueError('Wildlife tick must be at most one simulated day')
        self.rng=random.Random(seed);self.animals={};self.events=[];self.tick=0;self.next_id=0
        self.birth_budget=birth_budget;self.days_per_tick=days_per_tick
        self.aquatic_food={f'{x},{z}':3.0 for x in range(world.width) for z in range(world.depth)
                           if world.terrain_at(x,z)['biome']=='water'}
        self.aquatic_capacity=3.0
        for species,definition in SPECIES.items():
            places=[(x,z) for x in range(world.width) for z in range(world.depth)
                    if self.allowed(world,species,x,z)]
            for i in range(per_species if places else 0):
                x,z=self.rng.choice(places)
                self.spawn(species,x,z,'female' if i%2==0 else 'male',definition['maturity']+self.rng.random()*10)

    def allowed(self,world,species,x,z):
        return 0<=x<world.width and 0<=z<world.depth and world.terrain_at(x,z)['biome'] in SPECIES[species]['habitats']

    def spawn(self,species,x,z,sex,age_days=0,parents=None):
        aid=f'animal-{self.next_id:06}';self.next_id+=1
        a=Animal(aid,species,x,z,sex,age_days,parent_ids=list(parents or []))
        self.animals[aid]=a;return a

    def emit(self,kind,a,**payload):
        self.events.append(dict(id=f'fauna-event-{len(self.events):08}',tick=self.tick,type=kind,animal_id=a.id,
                                species=a.species,source='deterministic_ecology',**payload))

    def step(self,world):
        self.tick+=1;days=self.days_per_tick;day=self.tick*days
        # Bounded primary productivity; stored separately from the human fish stock.
        for key,value in self.aquatic_food.items():self.aquatic_food[key]=min(self.aquatic_capacity,value+.1*days)
        living=[a for a in self.animals.values() if a.alive]
        births=0
        for a in living:
            if not a.alive:continue
            d=SPECIES[a.species];a.age_days+=days;a.energy=max(0,a.energy-8*days);a.action='resting'
            if a.age_days>=d['life'] or a.health<=0:
                a.alive=False;self.emit('death',a,cause='aging' if a.age_days>=d['life'] else 'starvation');continue
            threats=[b for b in living if b.alive and a.species in SPECIES[b.species]['prey'] and abs(b.x-a.x)+abs(b.z-a.z)<=5]
            choices=[(x,z) for x,z in [(a.x+1,a.z),(a.x-1,a.z),(a.x,a.z+1),(a.x,a.z-1)] if self.allowed(world,a.species,x,z)]
            if threats and choices:
                threat=min(threats,key=lambda b:abs(b.x-a.x)+abs(b.z-a.z))
                a.x,a.z=max(choices,key=lambda p:abs(p[0]-threat.x)+abs(p[1]-threat.z));a.action='avoiding predator'
            elif a.energy<85:
                prey=next((b for b in living if b.alive and b.species in d['prey'] and abs(b.x-a.x)+abs(b.z-a.z)<=1),None)
                nodes=[n for n in world.resources.values() if n['kind'] in d['food'] and n['amount']>=1]
                near=next((n for n in nodes if n['x']==a.x and n['z']==a.z),None)
                water_key=f'{a.x},{a.z}'
                if prey:
                    prey.alive=False;a.energy=min(100,a.energy+25);a.action='hunting';self.emit('predation',a,prey_id=prey.id,prey_species=prey.species)
                elif near:
                    near['amount']-=1;a.energy=min(100,a.energy+20);a.action='foraging';self.emit('feeding',a,resource_id=near['id'],resource=near['kind'],amount=1)
                elif a.species=='carp' and self.aquatic_food.get(water_key,0)>=1:
                    self.aquatic_food[water_key]-=1;a.energy=min(100,a.energy+20);a.action='grazing aquatic food';self.emit('aquatic_feeding',a,amount=1)
                elif choices:
                    targets=[(n['x'],n['z']) for n in nodes]+[(b.x,b.z) for b in living if b.alive and b.species in d['prey']]
                    if targets:
                        target=min(targets,key=lambda p:abs(p[0]-a.x)+abs(p[1]-a.z))
                        a.x,a.z=min(choices,key=lambda p:abs(p[0]-target[0])+abs(p[1]-target[1]))
                    else:a.x,a.z=self.rng.choice(choices)
                    a.action='swimming' if d['group']=='fish' else 'flying' if d['group'] in {'bird','insect'} else 'roaming'
            if a.energy==0:a.health=max(0,a.health-10*days)
            if a.health==0:
                a.alive=False;self.emit('death',a,cause='starvation');continue
            if a.sex=='female' and a.age_days>=d['maturity'] and a.energy>=70 and day>=a.next_birth_day and births<self.birth_budget:
                mate=next((b for b in living if b.alive and b.species==a.species and b.sex=='male' and b.age_days>=d['maturity'] and b.energy>=70 and abs(b.x-a.x)+abs(b.z-a.z)<=1 and day>=b.next_birth_day),None)
                if mate:
                    child=self.spawn(a.species,a.x,a.z,self.rng.choice(['female','male']),parents=[a.id,mate.id]);births+=1
                    for parent in (a,mate):parent.energy-=20;parent.next_birth_day=day+max(7,d['maturity']/2)
                    self.emit('birth',child,parent_ids=child.parent_ids)

    def state(self):
        # JSON-native RNG shape keeps direct replay equality after a process restart.
        # The on-disk representation is unchanged: JSON already encoded tuples as arrays.
        rng=self.rng.getstate()
        return copy.deepcopy(dict(version=1,tick=self.tick,next_id=self.next_id,animals={k:asdict(a) for k,a in self.animals.items()},
             events=self.events,aquatic_food=self.aquatic_food,rng_state=[rng[0],list(rng[1]),rng[2]],birth_budget=self.birth_budget,days_per_tick=self.days_per_tick))

    @classmethod
    def restore(cls,state):
        if state.get('version')!=1:raise ValueError('Unsupported wildlife state')
        obj=cls.__new__(cls);obj.tick=state['tick'];obj.next_id=state['next_id'];obj.birth_budget=state['birth_budget'];obj.days_per_tick=state['days_per_tick'];obj.aquatic_capacity=3.0
        obj.animals={k:Animal(**v) for k,v in state['animals'].items()};obj.events=copy.deepcopy(state['events']);obj.aquatic_food=copy.deepcopy(state['aquatic_food'])
        def tuples(v):return tuple(tuples(x) for x in v) if isinstance(v,(list,tuple)) else v
        obj.rng=random.Random();obj.rng.setstate(tuples(state['rng_state']));return obj

    def public(self):
        return dict(tick=self.tick,elapsed_days=self.tick*self.days_per_tick,species=SPECIES,animals=[asdict(a) for a in self.animals.values()],
                    events=self.events[-30:],counts={k:sum(a.alive and a.species==k for a in self.animals.values()) for k in SPECIES},
                    mode='ISOLATED DETERMINISTIC ECOLOGY PREVIEW — not connected to inhabitants')
