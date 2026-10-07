"""Tests for turn/diplomacy.py -- RULES.AK [8]'s Treat/Break Treat state
machine. See that module's own docstring for the exact rulebook quotes
each branch below is sourced from.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.diplomacy import apply_treat_orders

HOME_A = HexCoord(0, 0)
HOME_B = HexCoord(1, 0)


def _state(alignment_a: Alignment = Alignment.GOOD, alignment_b: Alignment = Alignment.GOOD) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, alignment_a, HOME_A))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, alignment_b, HOME_B))
    return state


def test_all_kings_start_neutral():
    state = _state()
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_self_relation_is_always_allied():
    state = _state()
    assert state.diplomatic_relation(1, 1) is DiplomaticRelation.ALLIED


def test_mutual_treat_upgrades_neutral_to_allied():
    state = _state()
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.is_allied(1, 2)
    assert state.diplomatic_relations_since[frozenset({1, 2})] == state.turn_number


def test_mutual_treat_upgrades_enemy_to_neutral_one_step_at_a_time():
    state = _state()
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_one_sided_treat_does_nothing_for_non_druidic_kingdoms():
    state = _state()
    state.treat_permissions.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_unilateral_break_treat_downgrades_one_step():
    state = _state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert not state.is_allied(1, 2)


def test_unilateral_break_treat_from_neutral_reaches_enemy():
    state = _state()
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY


def test_mutual_break_treat_on_allies_jumps_straight_to_enemy():
    state = _state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY


def test_break_treat_takes_precedence_over_a_simultaneous_treat_order():
    state = _state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.treat_permissions.add((1, 2))
    state.break_treat_orders.add((2, 1))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_druidic_kingdom_one_sided_treat_forms_alliance_from_neutral():
    state = _state(alignment_a=Alignment.DRUID)
    state.treat_permissions.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED


def test_druidic_one_sided_alliance_is_vetoed_by_a_same_turn_break_treat():
    # The veto ([8.2]: "a meno che questo non impartisca un ordine Break
    # Treat nello stesso turno") only blocks the alliance from forming --
    # it doesn't cancel Break Treat's own ordinary [8.3] downgrade effect,
    # which fires independently and takes the pair to Enemy here (one
    # step down from Neutral), not back to a no-op Neutral.
    state = _state(alignment_a=Alignment.DRUID)
    state.treat_permissions.add((1, 2))
    state.break_treat_orders.add((2, 1))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY


def test_druidic_one_sided_treat_does_not_jump_straight_from_enemy():
    state = _state(alignment_a=Alignment.DRUID)
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY
    state.treat_permissions.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY


def test_druidic_mutual_treat_jumps_straight_from_enemy_to_allied():
    state = _state(alignment_a=Alignment.DRUID)
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED


def test_non_druidic_mutual_treat_does_not_jump_straight_from_enemy():
    state = _state()
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_no_orders_leaves_relation_and_timestamp_untouched():
    state = _state()
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert frozenset({1, 2}) not in state.diplomatic_relations
    assert frozenset({1, 2}) not in state.diplomatic_relations_since


def test_a_pair_already_allied_via_legacy_allied_kingdoms_is_not_retouched_by_a_noop_treat():
    # A pair already Allied without ever going through apply_treat_orders
    # (e.g. a GM-authored starting GameState) must not get a bogus
    # "became allied this turn" timestamp from a mutual Treat that
    # changes nothing -- see GameState.diplomatic_relation()'s own
    # "allied_kingdoms checked first" docstring note.
    state = _state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert frozenset({1, 2}) not in state.diplomatic_relations_since
