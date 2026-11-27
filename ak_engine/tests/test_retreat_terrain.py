"""A retreat is a movement and obeys the terrain rules ([7.4]; user rulings 2026-11-24): infantry cannot
retreat into the sea without Fleets, a Fleet defeated on land can only retreat into the sea, and a land
army may retreat by sea aboard a retreating Fleet of the same commander."""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.battle_orchestrator import _plan_retreat_destinations
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import MapBounds, neighbors

FIELD = HexCoord(5, 4)
BOUNDS = MapBounds(30, 15)
_NEIGHBORS = neighbors(FIELD, BOUNDS)
SEA_NEIGHBOR = _NEIGHBORS[0]  # chosen first by find_retreat_destination's neighbor order
LAND_NEIGHBOR = _NEIGHBORS[1]


def _state(*, sea: bool = True, land: bool = True, field_terrain: Terrain = Terrain.PLAINS) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, field_terrain, Race.HUMAN, owner_kingdom_id=2))
    if sea:
        state.add_province(ProvinceState(SEA_NEIGHBOR, Terrain.SEA, Race.HUMAN, owner_kingdom_id=2))
    if land:
        state.add_province(ProvinceState(LAND_NEIGHBOR, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    return state


def _army(state: GameState, army_id: int, army_type: ArmyType, *, commander: int | None = None) -> ArmyState:
    army = ArmyState(army_id, 2, army_type, Quality.AVERAGE, FIELD, commanded_by=commander)
    state.add_army(army)
    return army


def _plan(state: GameState, *armies: ArmyState) -> dict[int, HexCoord | None]:
    return _plan_retreat_destinations(list(armies), state, BOUNDS, FIELD, attacker_origin=None).destinations


def test_infantry_does_not_retreat_into_the_sea():
    state = _state(land=False)
    infantry = _army(state, 1, ArmyType.BOWMEN)

    assert _plan(state, infantry) == {1: None}


def test_infantry_skips_a_sea_neighbor_and_retreats_to_the_land_one():
    state = _state()  # the sea neighbor comes first in neighbor order
    infantry = _army(state, 1, ArmyType.BOWMEN)

    assert _plan(state, infantry) == {1: LAND_NEIGHBOR}


def test_a_fleet_defeated_on_land_cannot_retreat_to_another_land_province():
    state = _state(sea=False)
    fleet = _army(state, 1, ArmyType.FLEET)

    assert _plan(state, fleet) == {1: None}


def test_a_fleet_defeated_on_land_retreats_into_the_sea():
    state = _state()
    fleet = _army(state, 1, ArmyType.FLEET)

    assert _plan(state, fleet) == {1: SEA_NEIGHBOR}


def test_a_fleet_defeated_at_sea_may_retreat_onto_land():
    state = _state(sea=False, field_terrain=Terrain.SEA)
    fleet = _army(state, 1, ArmyType.FLEET)

    assert _plan(state, fleet) == {1: LAND_NEIGHBOR}


def test_an_ent_never_retreats_into_the_sea():
    state = _state(land=False)
    ent = _army(state, 1, ArmyType.ENTS)

    assert _plan(state, ent) == {1: None}


def test_a_land_army_retreats_by_sea_aboard_a_fleet_of_the_same_commander():
    state = _state(land=False)
    state.add_leader(LeaderState(7, 2, "Admiral", FIELD))
    fleet = _army(state, 1, ArmyType.FLEET, commander=7)
    infantry = _army(state, 2, ArmyType.BOWMEN, commander=7)

    plan = _plan(state, infantry, fleet)

    assert plan == {1: SEA_NEIGHBOR, 2: SEA_NEIGHBOR}
    assert infantry.transported_by == 1


def test_a_fleet_of_another_commander_does_not_carry_the_infantry():
    state = _state(land=False)
    state.add_leader(LeaderState(7, 2, "Admiral", FIELD))
    state.add_leader(LeaderState(8, 2, "General", FIELD))
    fleet = _army(state, 1, ArmyType.FLEET, commander=7)
    infantry = _army(state, 2, ArmyType.BOWMEN, commander=8)

    plan = _plan(state, infantry, fleet)

    assert plan == {1: SEA_NEIGHBOR, 2: None}
    assert infantry.transported_by is None


def test_a_fleet_carries_only_what_fits_aboard():
    state = _state(land=False)
    state.add_leader(LeaderState(7, 2, "Admiral", FIELD))
    fleet = _army(state, 1, ArmyType.FLEET, commander=7)
    first, second, third = (_army(state, n, ArmyType.BOWMEN, commander=7) for n in (2, 3, 4))

    plan = _plan(state, first, second, third, fleet)

    assert plan[1] == SEA_NEIGHBOR
    assert [plan[2], plan[3], plan[4]].count(SEA_NEIGHBOR) == 2  # a Fleet carries two infantry units
    assert [plan[2], plan[3], plan[4]].count(None) == 1


def test_a_fleet_with_no_sea_to_go_to_leaves_its_cargo_behind():
    state = _state(sea=False)
    state.add_leader(LeaderState(7, 2, "Admiral", FIELD))
    fleet = _army(state, 1, ArmyType.FLEET, commander=7)
    infantry = _army(state, 2, ArmyType.BOWMEN, commander=7)

    plan = _plan(state, fleet, infantry)

    assert plan[1] is None
    assert plan[2] == LAND_NEIGHBOR  # the infantry simply walks away over land
    assert infantry.transported_by is None


# -- the commander retreats with his armies (user ruling 2026-11-24) --


def _full_plan(state: GameState, *armies: ArmyState, attacker_origin: HexCoord | None = None):
    return _plan_retreat_destinations(list(armies), state, BOUNDS, FIELD, attacker_origin=attacker_origin)


def test_the_commander_retreats_with_his_armies():
    state = _state()
    state.add_leader(LeaderState(7, 2, "General", FIELD))
    infantry = _army(state, 1, ArmyType.BOWMEN, commander=7)

    plan = _full_plan(state, infantry)

    assert plan.destinations == {1: LAND_NEIGHBOR}
    assert plan.leader_destinations == {7: LAND_NEIGHBOR}
    assert plan.commander_after == {}  # he keeps his commander


def test_the_commander_goes_by_sea_aboard_his_fleet():
    state = _state(land=False)
    state.add_leader(LeaderState(7, 2, "Admiral", FIELD))
    fleet = _army(state, 1, ArmyType.FLEET, commander=7)
    infantry = _army(state, 2, ArmyType.BOWMEN, commander=7)

    plan = _full_plan(state, fleet, infantry)

    assert plan.leader_destinations == {7: SEA_NEIGHBOR}
    assert infantry.transported_by == 1


def test_a_commander_with_no_legal_destination_stays_put():
    state = _state(land=False)
    state.add_leader(LeaderState(7, 2, "General", FIELD))
    infantry = _army(state, 1, ArmyType.BOWMEN, commander=7)

    plan = _full_plan(state, infantry)

    assert plan.destinations == {1: None}
    assert plan.leader_destinations == {}


def test_an_army_that_cannot_follow_its_commander_goes_alone_without_him():
    state = _state(sea=False)
    state.add_leader(LeaderState(7, 2, "Admiral", FIELD))
    fleet = _army(state, 1, ArmyType.FLEET, commander=7)
    infantry = _army(state, 2, ArmyType.BOWMEN, commander=7)

    plan = _full_plan(state, fleet, infantry)

    assert plan.leader_destinations == {7: LAND_NEIGHBOR}  # he follows the infantry over land
    assert plan.destinations == {1: None, 2: LAND_NEIGHBOR}
    assert plan.commander_after[1] is None


def test_an_attacker_retreats_to_the_province_it_invaded_from_and_the_commander_with_it():
    origin = _NEIGHBORS[2]
    state = _state()
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_leader(LeaderState(7, 2, "General", origin))
    # An attacker's army still stands in its province of origin while the battle is resolved.
    army = ArmyState(1, 2, ArmyType.BOWMEN, Quality.AVERAGE, origin, commanded_by=7)
    state.add_army(army)

    plan = _full_plan(state, army, attacker_origin=origin)

    assert plan.destinations == {1: origin}  # not LAND_NEIGHBOR, which comes first among the field's neighbours
    assert plan.leader_destinations == {7: origin}


def test_the_armies_of_a_dead_commander_retreat_with_another_hero_of_the_kingdom():
    state = _state()
    state.add_leader(LeaderState(8, 2, "Hero", FIELD))
    state.add_leader(LeaderState(9, 3, "Foreign hero", FIELD))
    infantry = _army(state, 1, ArmyType.BOWMEN, commander=99)  # 99 is dead

    plan = _full_plan(state, infantry)

    assert plan.destinations == {1: LAND_NEIGHBOR}
    assert plan.leader_destinations == {8: LAND_NEIGHBOR}
    assert plan.commander_after == {1: 8}


def test_the_armies_of_a_dead_commander_prefer_the_king_then_a_leader_already_retreating():
    state = _state()
    hero = LeaderState(8, 2, "Hero", FIELD)
    king = LeaderState(5, 2, "King", FIELD, is_king=True)
    state.add_leader(hero)
    state.add_leader(king)
    orphan = _army(state, 1, ArmyType.BOWMEN, commander=99)

    assert _full_plan(state, orphan).commander_after == {1: 5}

    state2 = _state()
    state2.add_leader(LeaderState(8, 2, "Hero", FIELD))
    state2.add_leader(LeaderState(5, 2, "King", FIELD, is_king=True))
    led = _army(state2, 2, ArmyType.BOWMEN, commander=8)
    orphan2 = _army(state2, 1, ArmyType.BOWMEN, commander=99)

    plan = _full_plan(state2, led, orphan2)

    assert plan.commander_after == {1: 8}  # joins the hero who is already leading a contingent away
    assert plan.leader_destinations == {8: LAND_NEIGHBOR}


def test_the_armies_of_a_dead_commander_with_no_hero_retreat_to_the_garrison_of_an_adjacent_province():
    state = _state()
    state.add_leader(LeaderState(9, 3, "Foreign hero", FIELD))
    infantry = _army(state, 1, ArmyType.BOWMEN, commander=99)

    plan = _full_plan(state, infantry)

    assert plan.destinations == {1: LAND_NEIGHBOR}
    assert plan.leader_destinations == {}
    assert plan.commander_after == {1: None}  # unled: the Garrison Commander of that province


def test_the_armies_of_a_dead_commander_with_nowhere_to_go_have_no_destination():
    state = _state(land=False)
    infantry = _army(state, 1, ArmyType.BOWMEN, commander=99)

    assert _full_plan(state, infantry).destinations == {1: None}


def test_a_commander_none_of_whose_armies_can_retreat_flees_alone_to_a_land_province():
    state = _state(sea=False)
    state.add_leader(LeaderState(7, 2, "Admiral", FIELD))
    fleet = _army(state, 1, ArmyType.FLEET, commander=7)  # a Fleet cannot go from land to land

    plan = _full_plan(state, fleet)

    assert plan.destinations == {1: None}
    assert plan.leader_destinations == {7: LAND_NEIGHBOR}
    assert plan.leaders_alone == {7}


def test_a_commander_with_no_legal_province_at_all_stays():
    state = _state(land=False)
    state.add_leader(LeaderState(7, 2, "General", FIELD))
    infantry = _army(state, 1, ArmyType.BOWMEN, commander=7)

    assert _full_plan(state, infantry).leader_destinations == {}


def test_an_unled_garrison_retreats_with_a_hero_standing_with_it():
    state = _state()
    state.add_leader(LeaderState(8, 2, "Hero", FIELD))
    garrison = _army(state, 1, ArmyType.GARRISON)

    plan = _full_plan(state, garrison)

    assert plan.destinations == {1: LAND_NEIGHBOR}
    assert plan.leader_destinations == {8: LAND_NEIGHBOR}
    assert plan.commander_after == {1: 8}


def test_a_mercenary_band_does_not_follow_an_independent_hero():
    state = _state()
    state.add_leader(LeaderState(8, None, "Wandering hero", FIELD))
    band = ArmyState(1, None, ArmyType.BOWMEN, Quality.AVERAGE, FIELD)
    state.add_army(band)

    assert _full_plan(state, band).leader_destinations == {}


def test_a_defeated_free_hero_stays_where_he_fell_until_the_turn_is_over():
    # User ruling 2026-11-27: an independent Hero beaten in a battle does not run off at once -- he can still be
    # Charmed or met later in the same turn, and only then may decide to wander. His armies retreat without him.
    state = _state()
    state.add_leader(LeaderState(7, None, "Drago", FIELD))
    infantry = _army(state, 1, ArmyType.BOWMEN, commander=7)

    plan = _full_plan(state, infantry)

    assert plan.leader_destinations == {}
    assert plan.leaders_alone == set()
    assert plan.commander_after[1] is None
