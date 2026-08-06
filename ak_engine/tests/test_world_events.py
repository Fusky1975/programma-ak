"""Tests for turn/world_events.py -- see its module docstring for the
rulebook [1.4] visibility rule this implements (Phase 231).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.world_events import S_ADV, S_IDIPL, is_visible_to, record_kingdom_contacts

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


# -- Phase 408: record_kingdom_contacts() / is_visible_to()'s event_lev
# diplomatic-contact clause (the one confirmed-live piece of Get_News --
# see module docstring) --


def test_record_kingdom_contacts_marks_adjacent_owners_as_met():
    state = make_state()
    neighbor_coord = neighbors(HOME, BOUNDS)[0]
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(neighbor_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))

    record_kingdom_contacts(state, BOUNDS)

    assert state.has_met(1, 2) is True


def test_record_kingdom_contacts_ignores_far_apart_owners():
    state = make_state()
    far_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(far_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))

    record_kingdom_contacts(state, BOUNDS)

    assert state.has_met(1, 2) is False


def test_record_kingdom_contacts_ignores_unowned_provinces():
    state = make_state()
    neighbor_coord = neighbors(HOME, BOUNDS)[0]
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(neighbor_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=None))

    record_kingdom_contacts(state, BOUNDS)

    assert state.kingdoms_met == set()


def test_record_kingdom_contacts_is_monotone_across_turns():
    # kkmet's own real update is `or`-in-place, never cleared -- a
    # kingdom that later loses the bordering province stays "met".
    state = make_state()
    neighbor_coord = neighbors(HOME, BOUNDS)[0]
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(neighbor_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))
    record_kingdom_contacts(state, BOUNDS)

    state.provinces[neighbor_coord].owner_kingdom_id = None
    record_kingdom_contacts(state, BOUNDS)

    assert state.has_met(1, 2) is True


def test_is_visible_to_event_lev_none_matches_pre_phase_408_behavior():
    state = make_state()
    far_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(far_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))
    state.kingdoms_met.add(frozenset({1, 2}))

    assert is_visible_to(state, 1, far_coord, BOUNDS) is False
    assert is_visible_to(state, 1, far_coord, BOUNDS, event_lev=None) is False


def test_is_visible_to_s_idipl_widens_visibility_via_diplomatic_contact():
    state = make_state()
    far_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(far_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))
    state.kingdoms_met.add(frozenset({1, 2}))

    assert is_visible_to(state, 1, far_coord, BOUNDS, event_lev=S_IDIPL) is True


def test_is_visible_to_s_idipl_still_false_without_diplomatic_contact():
    state = make_state()
    far_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(far_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))

    assert is_visible_to(state, 1, far_coord, BOUNDS, event_lev=S_IDIPL) is False


def test_is_visible_to_below_s_idipl_does_not_widen_via_diplomatic_contact():
    state = make_state()
    far_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(far_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=2))
    state.kingdoms_met.add(frozenset({1, 2}))

    assert is_visible_to(state, 1, far_coord, BOUNDS, event_lev=S_ADV) is False


def test_is_visible_to_s_idipl_widening_needs_a_known_province_owner():
    state = make_state()
    unowned_coord = HexCoord(0, 0)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(unowned_coord, Terrain.FOREST, Race.HUMAN, owner_kingdom_id=None))

    assert is_visible_to(state, 1, unowned_coord, BOUNDS, event_lev=S_IDIPL) is False
