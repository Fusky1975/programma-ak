"""Tests for webapp/kingdom_delete.py -- Phase 1028, deleting a Kingdom
from the GM world editor. See that module's own docstring for exactly
which collections are cascaded and why each one is a real crash risk
(or confirmed not one) if left dangling."""

from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.combat import Quality
from ak_engine.webapp.kingdom_delete import KingdomHasEmperorError, delete_kingdom


def _state_with_two_kingdoms():
    state = GameState()
    for kingdom_id, name in ((1, "K1"), (2, "K2")):
        state.add_kingdom(
            KingdomState(kingdom_id, name, Race.HUMAN, Alignment.NEUTRAL, HexCoord(kingdom_id, 0), treasury=10)
        )
        state.add_leader(
            LeaderState(kingdom_id, kingdom_id=kingdom_id, name=name, location=HexCoord(kingdom_id, 0), is_king=True)
        )
    return state


def test_delete_kingdom_removes_the_kingdom_its_king_and_its_heroes():
    state = _state_with_two_kingdoms()
    state.add_leader(LeaderState(10, kingdom_id=1, name="Hero of K1", location=HexCoord(1, 0)))
    state.add_leader(LeaderState(11, kingdom_id=2, name="Hero of K2", location=HexCoord(2, 0)))

    delete_kingdom(state, 1)

    assert 1 not in state.kingdoms
    assert 1 not in state.leaders  # the King
    assert 10 not in state.leaders  # K1's Hero
    assert 11 in state.leaders  # K2's own Hero is untouched
    assert 2 in state.kingdoms


def test_delete_kingdom_removes_its_armies_only():
    state = _state_with_two_kingdoms()
    state.add_army(ArmyState(army_id=100, kingdom_id=1, army_type=ArmyType.LEGION, quality=Quality.AVERAGE, location=HexCoord(1, 0)))
    state.add_army(ArmyState(army_id=101, kingdom_id=2, army_type=ArmyType.LEGION, quality=Quality.AVERAGE, location=HexCoord(2, 0)))
    state.add_army(ArmyState(army_id=102, kingdom_id=None, army_type=ArmyType.LEGION, quality=Quality.AVERAGE, location=HexCoord(5, 5)))

    delete_kingdom(state, 1)

    assert 100 not in state.armies
    assert 101 in state.armies
    assert 102 in state.armies  # an unowned mercenary army is untouched


def test_delete_kingdom_releases_its_provinces_to_unowned():
    state = _state_with_two_kingdoms()
    state.add_province(ProvinceState(coord=HexCoord(1, 0), terrain=Terrain.PLAINS, race=Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(coord=HexCoord(2, 0), terrain=Terrain.PLAINS, race=Race.HUMAN, owner_kingdom_id=2))

    delete_kingdom(state, 1)

    assert state.provinces[HexCoord(1, 0)].owner_kingdom_id is None
    assert state.provinces[HexCoord(2, 0)].owner_kingdom_id == 2


def test_delete_kingdom_clears_contested_state_pointing_at_it():
    state = _state_with_two_kingdoms()
    state.add_province(
        ProvinceState(
            coord=HexCoord(1, 0),
            terrain=Terrain.PLAINS,
            race=Race.HUMAN,
            owner_kingdom_id=2,
            contested_by_kingdom_id=1,
            contested_from_coord=HexCoord(0, 0),
        )
    )

    delete_kingdom(state, 1)

    province = state.provinces[HexCoord(1, 0)]
    assert province.contested_by_kingdom_id is None
    assert province.contested_from_coord is None
    assert province.owner_kingdom_id == 2  # K2's own ownership is untouched


def test_delete_kingdom_drops_its_exploration_and_discovery_entries():
    state = _state_with_two_kingdoms()
    state.add_province(
        ProvinceState(
            coord=HexCoord(5, 5),
            terrain=Terrain.PLAINS,
            race=Race.HUMAN,
            explored_percent_by_kingdom={1: 50, 2: 20},
        )
    )
    state.add_feature(Feature(feature_id=1, coord=HexCoord(5, 5), kind=FeatureType.TEMPLE, discovered_by_kingdom={1: 3, 2: 1}))

    delete_kingdom(state, 1)

    assert 1 not in state.provinces[HexCoord(5, 5)].explored_percent_by_kingdom
    assert state.provinces[HexCoord(5, 5)].explored_percent_by_kingdom[2] == 20
    assert 1 not in state.features[1].discovered_by_kingdom
    assert state.features[1].discovered_by_kingdom[2] == 1


def test_delete_kingdom_cleans_every_pairwise_diplomacy_collection():
    state = _state_with_two_kingdoms()
    state.add_kingdom(KingdomState(3, "K3", Race.HUMAN, Alignment.NEUTRAL, HexCoord(3, 0)))
    state.add_leader(LeaderState(3, kingdom_id=3, name="K3", location=HexCoord(3, 0), is_king=True))

    state.allied_kingdoms = {frozenset({1, 2}), frozenset({2, 3})}
    state.diplomatic_relations = {frozenset({1, 2}): DiplomaticRelation.ALLIED, frozenset({2, 3}): DiplomaticRelation.NEUTRAL}
    state.diplomatic_relations_since = {frozenset({1, 2}): 3, frozenset({2, 3}): 5}
    state.kingdoms_met = {frozenset({1, 2}), frozenset({2, 3})}
    state.kingdoms_met_since = {frozenset({1, 2}): 1, frozenset({2, 3}): 2}
    state.treat_permissions = {(1, 2), (2, 3)}
    state.break_treat_orders = {(1, 2), (3, 2)}

    delete_kingdom(state, 1)

    assert state.allied_kingdoms == {frozenset({2, 3})}
    assert state.diplomatic_relations == {frozenset({2, 3}): DiplomaticRelation.NEUTRAL}
    assert state.diplomatic_relations_since == {frozenset({2, 3}): 5}
    assert state.kingdoms_met == {frozenset({2, 3})}
    assert state.kingdoms_met_since == {frozenset({2, 3}): 2}
    assert state.treat_permissions == {(2, 3)}
    assert state.break_treat_orders == {(3, 2)}


def test_delete_kingdom_refuses_the_crowned_emperor():
    state = _state_with_two_kingdoms()
    state.emperor_kingdom_id = 1

    with pytest.raises(KingdomHasEmperorError):
        delete_kingdom(state, 1)

    assert 1 in state.kingdoms
    assert 1 in state.leaders
