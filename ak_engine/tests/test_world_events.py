"""Tests for turn/world_events.py -- see its module docstring for the
rulebook [1.4] visibility rule this implements (Phase 231).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.world_events import is_visible_to

HOME = HexCoord(5, 5)
BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    return state


def test_is_visible_to_own_province():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))

    assert is_visible_to(state, 1, HOME, BOUNDS) is True


def test_is_visible_to_adjacent_province():
    state = make_state()
    neighbor_coord = neighbors(HOME, BOUNDS)[0]
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(neighbor_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))

    assert is_visible_to(state, 1, neighbor_coord, BOUNDS) is True


def test_is_visible_to_false_for_a_far_away_unowned_province():
    state = make_state()
    far_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(far_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))

    assert is_visible_to(state, 1, far_coord, BOUNDS) is False


def test_is_visible_to_false_for_a_province_this_kingdom_does_not_know():
    state = make_state()
    far_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(far_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))

    assert is_visible_to(state, 1, far_coord, BOUNDS) is False


def test_is_visible_to_false_for_an_unrecorded_coordinate():
    state = make_state()

    assert is_visible_to(state, 1, HexCoord(20, 10), BOUNDS) is False
