"""Tests for turn/leader_visibility.py -- see its module docstring and
LDRNEAR.md (Desktop/PROGRAMMA AK/LDRNEAR.md, Phase 636) for the full
sourced derivation.
"""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.leader_visibility import known_mercenary, leader_location_known_to_kingdom, leader_near
from ak_engine.turn.movement import hex_distance_wrapped

HOME = HexCoord(5, 4)


def _leader(leader_id: int, kingdom_id: int | None, coord: HexCoord, *, is_king: bool = False) -> LeaderState:
    return LeaderState(leader_id, kingdom_id, f"Leader{leader_id}", coord, is_king=is_king)


def _province(coord: HexCoord, *, owner: int | None) -> ProvinceState:
    return ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=owner)


# -- hex_distance_wrapped() -- LDRNEAR.md section 11's own worked vectors --


def test_hex_distance_wrapped_same_cell_is_zero():
    assert hex_distance_wrapped(HexCoord(5, 4), HexCoord(5, 4)) == 0


def test_hex_distance_wrapped_six_even_row_neighbors_are_one():
    # Bug fix: this used to list (4,3)/(4,5) here and treat (6,5) as the
    # non-adjacent case below -- the pre-Phase-314 "guessed" offset
    # convention's own neighbor set for an even row, never updated when
    # that phase corrected the parity to the real, confirmed-from-game-
    # data convention (see movement.py's own Phase 314 docstring and
    # hex_distance_wrapped()'s own Bug fix note). HOME=(5,4) is an even
    # row, so its real neighbors (movement.neighbors(), unchanged by
    # this fix) are (5,3)/(6,3)/(4,4)/(6,4)/(5,5)/(6,5).
    for coord in [
        HexCoord(5, 3), HexCoord(6, 3), HexCoord(4, 4),
        HexCoord(6, 4), HexCoord(5, 5), HexCoord(6, 5),
    ]:
        assert hex_distance_wrapped(HOME, coord) == 1


def test_hex_distance_wrapped_non_adjacent_diagonal_is_two():
    # (7, 4) is two real steps east of HOME (via the real neighbor (6, 4)),
    # genuinely distance 2 -- see the test above's own Bug fix note for why
    # the old (6, 5) example here was wrong (it is a real distance-1 neighbor).
    assert hex_distance_wrapped(HOME, HexCoord(7, 4)) == 2


def test_hex_distance_wrapped_horizontal_wraparound():
    assert hex_distance_wrapped(HexCoord(0, 4), HexCoord(17, 4), board_width=18) == 1


# -- leader_near() -- Ldr_Near --


def test_leader_near_same_coord_radius_zero():
    state = GameState()
    state.add_leader(_leader(1, 1, HOME))
    assert leader_near(state, 1, HOME, 0) is True


def test_leader_near_one_hex_away_needs_radius_one():
    state = GameState()
    state.add_leader(_leader(1, 1, HexCoord(6, 4)))
    assert leader_near(state, 1, HOME, 0) is False
    assert leader_near(state, 1, HOME, 1) is True


def test_leader_near_ignores_a_different_kingdoms_leader():
    state = GameState()
    state.add_leader(_leader(1, 2, HOME))
    assert leader_near(state, 1, HOME, 0) is False


def test_leader_near_ignores_a_kingdomless_hero():
    state = GameState()
    state.add_leader(_leader(1, None, HOME))
    assert leader_near(state, 1, HOME, 0) is False


def test_leader_near_counts_a_dead_loyal_leader():
    state = GameState()
    state.add_leader(_leader(1, 1, HOME))
    state.remove_leader(1)
    assert 1 not in state.leaders
    assert 1 in state.dead_leaders
    assert leader_near(state, 1, HOME, 0) is True


def test_leader_near_false_with_no_loyal_leaders_anywhere():
    state = GameState()
    assert leader_near(state, 1, HOME, 5) is False


# -- leader_location_known_to_kingdom() -- Known_Loc(ln,kng,0,advrep=true) --


def test_known_loc_false_for_the_viewers_own_leader():
    state = GameState()
    state.add_leader(_leader(1, 1, HOME))
    assert leader_location_known_to_kingdom(state, 1, 1, orig_turn=1) is False


def test_known_loc_false_for_a_king_on_his_own_throne():
    state = GameState()
    state.provinces[HOME] = _province(HOME, owner=2)
    state.add_leader(_leader(2, 2, HOME, is_king=True))
    assert leader_location_known_to_kingdom(state, 2, 1, orig_turn=1) is False


def test_known_loc_true_when_viewer_owns_the_targets_province():
    state = GameState()
    state.provinces[HOME] = _province(HOME, owner=1)
    state.add_leader(_leader(2, 2, HOME))
    assert leader_location_known_to_kingdom(state, 2, 1, orig_turn=1) is True


def test_known_loc_true_with_a_loyal_leader_present_and_the_mod5_gate_open():
    state = GameState()
    state.provinces[HOME] = _province(HOME, owner=2)
    state.add_leader(_leader(2, 2, HOME))
    state.add_leader(_leader(10, 1, HOME))
    # target_leader_id=2, orig_turn chosen so (2+orig_turn) % 5 <= 1
    assert (2 + 3) % 5 <= 1
    assert leader_location_known_to_kingdom(state, 2, 1, orig_turn=3) is True


def test_known_loc_false_when_the_mod5_gate_is_closed_even_with_a_loyal_leader_present():
    state = GameState()
    state.provinces[HOME] = _province(HOME, owner=2)
    state.add_leader(_leader(2, 2, HOME))
    state.add_leader(_leader(10, 1, HOME))
    # target_leader_id=2, orig_turn chosen so (2+orig_turn) % 5 > 1
    assert (2 + 0) % 5 > 1
    assert leader_location_known_to_kingdom(state, 2, 1, orig_turn=0) is False


def test_known_loc_resolves_a_dead_target_via_dead_leaders():
    state = GameState()
    state.provinces[HOME] = _province(HOME, owner=1)
    state.add_leader(_leader(2, 2, HOME))
    state.remove_leader(2)
    assert 2 in state.dead_leaders
    assert leader_location_known_to_kingdom(state, 2, 1, orig_turn=1) is True


def test_known_loc_false_for_an_unknown_leader_id():
    state = GameState()
    assert leader_location_known_to_kingdom(state, 999, 1, orig_turn=1) is False


# -- known_mercenary() -- Known_Merc(an,kng) --


def _mercenary(army_id: int, coord: HexCoord) -> ArmyState:
    return ArmyState(army_id, None, ArmyType.BOWMEN, Quality.AVERAGE, coord)


def test_known_mercenary_true_in_an_owned_province():
    state = GameState()
    state.provinces[HOME] = _province(HOME, owner=1)
    mercenary = _mercenary(9, HOME)
    assert known_mercenary(state, mercenary, 1) is True


def test_known_mercenary_true_with_a_loyal_leader_within_one_hex():
    state = GameState()
    adjacent = HexCoord(6, 4)
    state.provinces[adjacent] = _province(adjacent, owner=None)
    state.add_leader(_leader(1, 1, HOME))
    mercenary = _mercenary(9, adjacent)
    assert known_mercenary(state, mercenary, 1) is True


def test_known_mercenary_false_beyond_one_hex():
    state = GameState()
    far = HexCoord(8, 4)
    state.provinces[far] = _province(far, owner=None)
    state.add_leader(_leader(1, 1, HOME))
    mercenary = _mercenary(9, far)
    assert known_mercenary(state, mercenary, 1) is False


def test_known_mercenary_false_for_an_owned_army():
    state = GameState()
    state.provinces[HOME] = _province(HOME, owner=1)
    owned_army = ArmyState(9, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME)
    assert known_mercenary(state, owned_army, 1) is False
