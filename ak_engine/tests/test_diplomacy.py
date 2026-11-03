"""Tests for turn/diplomacy.py -- RULES.AK [8]'s Treat/Break Treat state
machine. See that module's own docstring for the exact rulebook quotes
each branch below is sourced from.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.diplomacy import advance_pending_diplomacy, apply_treat_orders, is_attackable_at

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


def test_mutual_treat_upgrades_neutral_to_allied_only_once_promoted_next_turn():
    # 2026-11-05: an ordinary (non-Druidic) mutual Treat resolves "alla
    # fine del turno" -- not yet visible to this turn's own combat.
    state = _state()
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert state.pending_treat_transitions[frozenset({1, 2})] == (
        DiplomaticRelation.NEUTRAL,
        DiplomaticRelation.ALLIED,
    )
    assert state.diplomacy_relation_change_notices == []

    advance_pending_diplomacy(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.is_allied(1, 2)
    assert state.diplomatic_relations_since[frozenset({1, 2})] == state.turn_number
    assert state.diplomacy_relation_change_notices == []  # no top-of-report notice for Treat


def test_mutual_treat_upgrades_enemy_to_neutral_one_step_at_a_time_only_once_promoted():
    state = _state()
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY  # still, this turn

    advance_pending_diplomacy(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_one_sided_treat_does_nothing_for_non_druidic_kingdoms():
    state = _state()
    state.treat_permissions.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_unilateral_break_treat_downgrades_one_step():
    # Breaker (kingdom 1) is Evil -- [8.3]'s own same-turn exception --
    # so the downgrade math below is exercised immediately, same as
    # before this module modeled the timing split at all. See
    # test_ordinary_unilateral_break_treat_is_deferred_to_next_turn
    # below for the now-different, non-Evil/Undead case.
    state = _state(alignment_a=Alignment.EVIL)
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert not state.is_allied(1, 2)


def test_unilateral_break_treat_from_neutral_reaches_enemy():
    state = _state(alignment_a=Alignment.EVIL)
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY


def test_mutual_break_treat_on_allies_jumps_straight_to_enemy():
    # Only one of the two breakers needs to be Evil/Undead for [8.3]'s
    # own same-turn exception to apply to the whole pair's transition --
    # see test_mutual_break_treat_is_deferred_when_neither_side_is_evil_
    # or_undead below for the all-ordinary case.
    state = _state(alignment_a=Alignment.EVIL)
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY


def test_break_treat_takes_precedence_over_a_simultaneous_treat_order():
    state = _state(alignment_b=Alignment.EVIL)
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.treat_permissions.add((1, 2))
    state.break_treat_orders.add((2, 1))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


def test_druidic_kingdom_one_sided_treat_forms_alliance_from_neutral_only_once_promoted():
    # 2026-11-05: confirmed with the user -- unlike the *mutual* Druidic
    # case below, this one-sided carve-out has no "prima dell'inizio del
    # turno" text of its own, so it stays deferred like an ordinary
    # Treat, not immediate.
    state = _state(alignment_a=Alignment.DRUID)
    state.treat_permissions.add((1, 2))
    apply_treat_orders(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL

    advance_pending_diplomacy(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.diplomacy_relation_change_notices == []


def test_druidic_one_sided_alliance_is_vetoed_by_a_same_turn_break_treat():
    # The veto ([8.2]: "a meno che questo non impartisca un ordine Break
    # Treat nello stesso turno") only blocks the alliance from forming --
    # it doesn't cancel Break Treat's own ordinary [8.3] downgrade effect,
    # which fires independently and takes the pair to Enemy here (one
    # step down from Neutral), not back to a no-op Neutral. Breaker
    # (kingdom 2) is Evil so this same-turn effect is exercised directly,
    # same as every other break-treat-math test in this file.
    state = _state(alignment_a=Alignment.DRUID, alignment_b=Alignment.EVIL)
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

    assert state.pending_treat_transitions[frozenset({1, 2})] == (
        DiplomaticRelation.ENEMY,
        DiplomaticRelation.NEUTRAL,
    )

    advance_pending_diplomacy(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL


# -- [8.3]'s own timing exception: Evil/Undead Break Treat alone is
# immediate; an ordinary King's own Break Treat is deferred to the
# start of next turn -- 2026-11-03 ------------------------------------


def test_ordinary_unilateral_break_treat_is_deferred_to_next_turn():
    state = _state()  # both kingdoms default to Alignment.GOOD
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)

    # Not yet visible to this turn's own combat...
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.is_allied(1, 2)
    # ...but queued for the start of next turn.
    assert state.pending_break_treat_transitions[frozenset({1, 2})] == (
        DiplomaticRelation.ALLIED,
        DiplomaticRelation.NEUTRAL,
    )
    assert state.diplomacy_relation_change_notices == []


def test_mutual_break_treat_is_deferred_when_neither_side_is_evil_or_undead():
    state = _state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.update({(1, 2), (2, 1)})
    apply_treat_orders(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.pending_break_treat_transitions[frozenset({1, 2})] == (
        DiplomaticRelation.ALLIED,
        DiplomaticRelation.ENEMY,
    )


def test_undead_breaker_is_also_immediate_not_just_evil():
    state = _state(alignment_a=Alignment.UNDEAD)
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ENEMY
    assert frozenset({1, 2}) not in state.pending_break_treat_transitions


def test_advance_pending_diplomacy_promotes_a_deferred_break_at_the_start_of_next_turn():
    state = _state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED  # still, this turn

    # Next turn's own orders are gone (turn-scoped reset, simulated
    # here directly) by the time advance_pending_diplomacy() runs.
    state.break_treat_orders = set()
    advance_pending_diplomacy(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert not state.is_allied(1, 2)
    assert frozenset({1, 2}) not in state.pending_break_treat_transitions
    assert state.diplomacy_relation_change_notices == [
        (1, 2, DiplomaticRelation.ALLIED, DiplomaticRelation.NEUTRAL)
    ]


def test_advance_pending_diplomacy_is_a_noop_with_nothing_pending():
    state = _state()
    advance_pending_diplomacy(state)
    assert state.pending_break_treat_transitions == {}
    assert state.diplomacy_relation_change_notices == []


def test_immediate_evil_break_treat_records_a_relation_change_notice():
    state = _state(alignment_a=Alignment.EVIL)
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomacy_relation_change_notices == [
        (1, 2, DiplomaticRelation.ALLIED, DiplomaticRelation.NEUTRAL)
    ]


def test_deferred_treat_transitions_never_record_a_relation_change_notice():
    # 2026-11-05: confirmed with the user -- unlike a Break Treat
    # promotion, a deferred Treat (ordinary mutual, or the Druidic
    # one-sided case) is shown only in the later turn's own DIPLOMACY
    # section, never announced at the top of that report.
    state = _state()
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    advance_pending_diplomacy(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.diplomacy_relation_change_notices == []


def test_mutual_druidic_treat_is_immediate_and_records_a_relation_change_notice():
    # 2026-11-05: confirmed with the user -- unlike an ordinary mutual
    # Treat, a *mutual* Treat with at least one Druidic party resolves
    # "prima dell'inizio del turno" and is announced the same prominent
    # way a Break Treat is.
    state = _state(alignment_a=Alignment.DRUID)
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED  # already, this turn
    assert frozenset({1, 2}) not in state.pending_treat_transitions
    assert state.diplomacy_relation_change_notices == [
        (1, 2, DiplomaticRelation.NEUTRAL, DiplomaticRelation.ALLIED)
    ]


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


def _triangle_state() -> GameState:
    # X (kingdom 1) allied to both Y (kingdom 2) and Z (kingdom 3), who
    # are enemies of each other. Province X_HOME belongs to X.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Xaria", Race.HUMAN, Alignment.GOOD, HOME_A))
    state.add_kingdom(KingdomState(2, "Yland", Race.HUMAN, Alignment.GOOD, HOME_B))
    state.add_kingdom(KingdomState(3, "Zantium", Race.HUMAN, Alignment.EVIL, HexCoord(2, 0)))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.allied_kingdoms.add(frozenset({1, 3}))
    state.diplomatic_relations[frozenset({2, 3})] = DiplomaticRelation.ENEMY
    return state


def test_is_attackable_at_ordinary_enemy_is_attackable():
    state = _triangle_state()
    province = ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2)
    assert is_attackable_at(state, defender_kingdom_id=2, attacker_kingdom_id=3, province=province) is True


def test_is_attackable_at_allied_defender_is_never_attackable():
    state = _triangle_state()
    province = ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)
    assert is_attackable_at(state, defender_kingdom_id=1, attacker_kingdom_id=2, province=province) is False


def test_is_attackable_at_shields_a_guest_kingdoms_army_on_allied_host_territory():
    # Y's forces, merely passing through/stationed in X's own territory,
    # cannot be attacked by Z even though Y and Z are enemies -- [8.1]'s
    # own "triangle" rule, since X (the territory owner) is Allied with
    # the attacker Z.
    state = _triangle_state()
    x_owned_province = ProvinceState(HOME_A, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1)
    assert is_attackable_at(state, defender_kingdom_id=2, attacker_kingdom_id=3, province=x_owned_province) is False


def test_is_attackable_at_does_not_shield_on_unowned_or_non_allied_territory():
    state = _triangle_state()
    wild_province = ProvinceState(HexCoord(9, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)
    assert is_attackable_at(state, defender_kingdom_id=2, attacker_kingdom_id=3, province=wild_province) is True
