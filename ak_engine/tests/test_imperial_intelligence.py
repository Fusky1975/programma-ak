from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.imperial_intelligence import (
    bordering_kingdoms,
    known_bordering_kingdom_tax_bases,
    known_bordering_kingdom_treasuries,
)
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.tax_base import compute_tax_base

BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)
HOME = HexCoord(5, 5)
KING_ID = 501


def _neighbor(index: int) -> HexCoord:
    return neighbors(HOME, BOUNDS)[index]


def _base_state(*, turn_number: int = 10) -> GameState:
    state = GameState()
    state.turn_number = turn_number
    state.add_kingdom(KingdomState(1, "Homeland", Race.HUMAN, Alignment.GOOD, HOME, treasury=500))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(KING_ID, 1, "King", HOME, is_king=True))
    return state


def _add_bordering_kingdom(state: GameState, kingdom_id: int, index: int, *, tax: int, treasury: int) -> HexCoord:
    coord = _neighbor(index)
    state.add_kingdom(KingdomState(kingdom_id, f"Kingdom{kingdom_id}", Race.HUMAN, Alignment.GOOD, coord, treasury=treasury))
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=kingdom_id, tax=tax))
    return coord


# -- bordering_kingdoms --------------------------------------------------


def test_bordering_kingdoms_finds_an_adjacent_owner():
    state = _base_state()
    _add_bordering_kingdom(state, 2, 0, tax=10, treasury=50)

    assert bordering_kingdoms(state, BOUNDS, 1) == {2}


def test_bordering_kingdoms_ignores_far_apart_owners():
    state = _base_state()
    state.add_kingdom(KingdomState(2, "Faraway", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))

    assert bordering_kingdoms(state, BOUNDS, 1) == set()


def test_bordering_kingdoms_ignores_unowned_neighbors():
    state = _base_state()
    coord = _neighbor(0)
    state.add_province(ProvinceState(coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=None))

    assert bordering_kingdoms(state, BOUNDS, 1) == set()


def test_bordering_kingdoms_reflects_current_ownership_not_historical_contact():
    # A province that changed hands away from a neighbor no longer counts,
    # even though kingdoms_met (the boolean ratchet) would still say yes.
    state = _base_state()
    coord = _add_bordering_kingdom(state, 2, 0, tax=10, treasury=50)
    state.provinces[coord].owner_kingdom_id = 3

    assert bordering_kingdoms(state, BOUNDS, 1) == {3}


# -- known_bordering_kingdom_tax_bases (World Emperor) -------------------


def test_known_bordering_kingdom_tax_bases_none_without_the_office():
    state = _base_state()
    _add_bordering_kingdom(state, 2, 0, tax=10, treasury=50)
    state.kingdoms_met_since[frozenset({1, 2})] = 5

    assert known_bordering_kingdom_tax_bases(state, BOUNDS, KING_ID) is None


def test_known_bordering_kingdom_tax_bases_excludes_a_kingdom_known_less_than_a_full_turn():
    state = _base_state(turn_number=10)
    state.emperor_kingdom_id = 1
    _add_bordering_kingdom(state, 2, 0, tax=10, treasury=50)
    state.kingdoms_met_since[frozenset({1, 2})] = 10  # met this same turn

    assert known_bordering_kingdom_tax_bases(state, BOUNDS, KING_ID) == {}


def test_known_bordering_kingdom_tax_bases_includes_a_bordering_kingdom_known_a_full_turn():
    state = _base_state(turn_number=10)
    state.emperor_kingdom_id = 1
    _add_bordering_kingdom(state, 2, 0, tax=10, treasury=50)
    state.kingdoms_met_since[frozenset({1, 2})] = 9

    result = known_bordering_kingdom_tax_bases(state, BOUNDS, KING_ID)

    assert result == {2: compute_tax_base(state, 2)}


def test_known_bordering_kingdom_tax_bases_excludes_a_non_bordering_known_kingdom():
    state = _base_state(turn_number=10)
    state.emperor_kingdom_id = 1
    state.add_kingdom(KingdomState(9, "Faraway", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0), treasury=999))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=9, tax=99))
    state.kingdoms_met_since[frozenset({1, 9})] = 1  # known a long time, but never bordering

    assert known_bordering_kingdom_tax_bases(state, BOUNDS, KING_ID) == {}


# -- known_bordering_kingdom_treasuries (Imperial Treasurer) -------------


def test_known_bordering_kingdom_treasuries_none_without_the_office():
    # Kingdom 1's own treasury (500, set by _base_state) makes its King the
    # world's sole Treasurer candidate -- querying a *different* leader
    # (kingdom 2's own, with a far smaller treasury) confirms the "not the
    # titleholder" branch, not just "nobody holds this office at all."
    state = _base_state()
    _add_bordering_kingdom(state, 2, 0, tax=10, treasury=50)
    other_leader_id = 999
    state.add_leader(LeaderState(other_leader_id, 2, "Other King", _neighbor(0), is_king=True))
    state.kingdoms_met_since[frozenset({1, 2})] = 5

    assert known_bordering_kingdom_treasuries(state, BOUNDS, other_leader_id) is None


def test_known_bordering_kingdom_treasuries_includes_a_bordering_kingdom_known_a_full_turn():
    state = _base_state(turn_number=10)
    _add_bordering_kingdom(state, 2, 0, tax=10, treasury=77)
    state.kingdoms_met_since[frozenset({1, 2})] = 9

    result = known_bordering_kingdom_treasuries(state, BOUNDS, KING_ID)

    assert result == {2: 77}
