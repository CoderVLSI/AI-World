from scripts.far_water_diagnostic import FarWaterWorld, ScriptedWaterPolicy, fixture_metadata, outcome, WATER_ID, FOCAL
from caitanya.inference import select_tools


def test_far_water_fixture_is_distant_known_walkable_and_unmodified_defaults():
    world=FarWaterWorld()
    data=fixture_metadata(world)
    assert data['nearest_water_resource_distance']==15
    assert data['nearest_natural_water_terrain_distance']>=15
    assert not data['initial_water_visible']
    assert data['initial_focal_thirst']==90
    assert all(a.inventory['water']==0 for a in world.agents.values())
    assert any('water was seen at x=23, z=24' in text for text in data['focal_recalled_places'])
    assert len([n for n in world.resources.values() if n['kind']=='water'])==1
    assert world.autonomy.reflex.enabled is False
    assert world.root.data['mode']=='crisis'
    assert {'TRAVEL_TO','REST_FOR'} <= {t['function']['name'] for t in select_tools(world.observe(FOCAL))}


def run(strategy):
    policy=ScriptedWaterPolicy(strategy)
    world=FarWaterWorld(backend=policy)
    fingerprint=world.fixture_fingerprint
    for _ in range(50):
        world.step()
        if outcome(world)['focal_first_drink_tick'] is not None:break
    return world,policy,fingerprint


def test_travel_to_versus_repeated_move_in_identical_fixture():
    travel,tp,th=run('TRAVEL_TO')
    move,mp,mh=run('MOVE')
    assert th==mh
    to,mo=outcome(travel),outcome(move)
    assert to['focal_position']==mo['focal_position']==[23,24]
    assert to['focal_first_drink_tick']==18
    assert mo['focal_first_drink_tick']==17
    assert tp.calls[FOCAL]==3 and mp.calls[FOCAL]==17
    assert to['focal_validated_choice_counts']['TRAVEL_TO']==1
    assert to['focal_mechanical_action_counts']['MOVE']==15
    assert mo['focal_validated_choice_counts']['MOVE']==15
    assert mo['focal_mechanical_action_counts']=={}
    assert to['root_arrivals']==mo['root_arrivals']==0
    assert to['population_end']==mo['population_end']==5
