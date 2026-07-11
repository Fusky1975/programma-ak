from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality

HOME = HexCoord(0, 0)
FIELD = HexCoord(1, 1)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.AXEMEN, Quality.AVERAGE, FIELD))
    return state


def test_add_leader_and_leaders_at():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", FIELD))
    state.add_leader(LeaderState(2, 2, "Rival", HOME))
    assert {leader.leader_id for leader in state.leaders_at(FIELD)} == {1}
    assert state.leaders_at(HexCoord(9, 9)) == []


def test_armies_commanded_by_filters_correctly():
    state = make_state()
    state.armies[101].commanded_by = 1
    assert [army.army_id for army in state.armies_commanded_by(1)] == [101]
    assert state.armies_commanded_by(2) == []


def test_army_defaults_to_unled():
    state = make_state()
    assert state.armies[101].commanded_by is None


def test_armies_at_returns_only_armies_in_that_province():
    state = make_state()
    assert {a.army_id for a in state.armies_at(FIELD)} == {101, 201}
    assert state.armies_at(HOME) == []


def test_remove_army_drops_it():
    state = make_state()
    state.remove_army(101)
    assert 101 not in state.armies
    assert {a.army_id for a in state.armies_at(FIELD)} == {201}


def test_is_allied_true_for_same_kingdom():
    state = make_state()
    assert state.is_allied(1, 1) is True


def test_is_allied_false_without_alliance():
    state = make_state()
    assert state.is_allied(1, 2) is False


def test_is_allied_true_when_alliance_recorded():
    state = make_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    assert state.is_allied(1, 2) is True
    assert state.is_allied(2, 1) is True


def test_friendly_provinces_for_includes_owned_and_allied():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    assert state.friendly_provinces_for(1) == {HOME}
    state.allied_kingdoms.add(frozenset({1, 2}))
    assert state.friendly_provinces_for(1) == {HOME, FIELD}


def test_mercenaries_at_returns_only_ownerless_armies_at_that_location():
    state = make_state()
    state.add_army(ArmyState(301, None, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    assert {a.army_id for a in state.mercenaries_at(FIELD)} == {301}
    assert state.mercenaries_at(HOME) == []


def test_is_allied_none_kingdom_id_is_allied_with_nobody():
    state = make_state()
    assert state.is_allied(None, 1) is False
    assert state.is_allied(1, None) is False
    assert state.is_allied(None, None) is False


def test_independent_heroes_at_returns_only_ownerless_leaders_at_that_location():
    state = make_state()
    state.add_leader(LeaderState(50, None, "Wandering Hero", FIELD))
    state.add_leader(LeaderState(51, 1, "Employed Leader", FIELD))
    assert {leader.leader_id for leader in state.independent_heroes_at(FIELD)} == {50}
    assert state.independent_heroes_at(HOME) == []


def test_add_feature_and_features_at():
    state = make_state()
    state.add_feature(Feature(feature_id=1, coord=FIELD, kind=FeatureType.DUNGEON, guardian_monster=Monster.TROLL))
    state.add_feature(Feature(feature_id=2, coord=HOME, kind=FeatureType.TOMB))
    assert {f.feature_id for f in state.features_at(FIELD)} == {1}
    assert state.features_at(HexCoord(9, 9)) == []


def test_features_at_returns_multiple_features_sharing_a_coordinate():
    state = make_state()
    state.add_feature(Feature(feature_id=1, coord=FIELD, kind=FeatureType.DUNGEON))
    state.add_feature(Feature(feature_id=2, coord=FIELD, kind=FeatureType.TOMB))
    assert {f.feature_id for f in state.features_at(FIELD)} == {1, 2}
