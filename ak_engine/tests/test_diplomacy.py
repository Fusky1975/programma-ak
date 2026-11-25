"""Tests for turn/diplomacy.py -- RULES.AK [8]'s Treat/Break Treat state
machine. See that module's own docstring for the exact rulebook quotes
each branch below is sourced from.
"""

from __future__ import annotations

import pytest

from _helpers import ScriptedRandom

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.kingdom import KingdomMoveHeader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.diplomacy import (
    advance_pending_diplomacy,
    alignment_distance,
    apply_diplomatic_fury,
    apply_treat_orders,
    is_attackable_at,
    set_relation,
    sync_treat_orders_from_kingdom_headers,
)

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


def test_set_relation_rejects_teamed():
    # Phase 1192 bug fix: TEAMED support is deliberately deferred (module
    # docstring) -- set_relation() must reject it itself, the shared
    # primitive, rather than relying on every caller to repeat the same
    # check (and silently writing it would only crash much later and far
    # less clearly, inside _downgrade()/_upgrade()).
    state = _state()

    with pytest.raises(ValueError):
        set_relation(state, 1, 2, DiplomaticRelation.TEAMED)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL  # untouched


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


# 2026-11-20 bug fix, user-confirmed via a live playtest ("Ho fatto fare un
# Treat a tutti e due i Re della partita. Sarebbero dovuti diventare
# alleati, ma non è successo nulla."): KingdomMoveHeader.allreq/.brreq were
# decoded and cross-validated (Phase 920) but never bridged into the two
# sets apply_treat_orders() actually reads -- see sync_treat_orders_from_
# kingdom_headers()'s own docstring.


def test_sync_treat_orders_reads_allreq_bit_as_a_directed_treat_permission():
    state = _state()
    header = KingdomMoveHeader(raw_fields=[27, 1 << 2, 0, 101, 1, 15, 1])  # allreq bit 2 -> Kingdom 2

    sync_treat_orders_from_kingdom_headers(state, {1: header})

    assert state.treat_permissions == {(1, 2)}
    assert state.break_treat_orders == set()


def test_sync_treat_orders_reads_brreq_bit_as_a_directed_break_treat_order():
    state = _state()
    header = KingdomMoveHeader(raw_fields=[27, 0, 1 << 2, 101, 1, 15, 1])  # brreq bit 2 -> Kingdom 2

    sync_treat_orders_from_kingdom_headers(state, {1: header})

    assert state.break_treat_orders == {(1, 2)}
    assert state.treat_permissions == set()


def test_sync_treat_orders_combines_both_kingdoms_own_requests():
    state = _state()
    header_1 = KingdomMoveHeader(raw_fields=[27, 1 << 2, 0, 101, 1, 15, 1])  # Kingdom 1 Treats toward 2
    header_2 = KingdomMoveHeader(raw_fields=[27, 1 << 1, 0, 101, 1, 15, 1])  # Kingdom 2 Treats toward 1

    sync_treat_orders_from_kingdom_headers(state, {1: header_1, 2: header_2})

    assert state.treat_permissions == {(1, 2), (2, 1)}


def test_sync_treat_orders_ignores_a_self_targeting_bit():
    # Defensive only -- no real sample has ever shown a Kingdom naming its
    # own id, but a self-pair would otherwise be silently dropped by
    # apply_treat_orders()'s own `a != b` filter anyway.
    state = _state()
    header = KingdomMoveHeader(raw_fields=[27, 1 << 1, 0, 101, 1, 15, 1])  # Kingdom 1 naming itself (bit 1)

    sync_treat_orders_from_kingdom_headers(state, {1: header})

    assert state.treat_permissions == set()


def test_sync_treat_orders_ignores_a_bit_naming_a_kingdom_not_in_the_game():
    state = _state()
    header = KingdomMoveHeader(raw_fields=[27, 1 << 9, 0, 101, 1, 15, 1])  # Kingdom 9 doesn't exist here

    sync_treat_orders_from_kingdom_headers(state, {1: header})

    assert state.treat_permissions == set()


def test_sync_treat_orders_then_apply_treat_orders_produces_a_real_pending_alliance():
    # The end-to-end bridge, not just the decode: once synced, a real
    # mutual Treat request behaves exactly like the GM-manual-entry path
    # already did -- deferred to next turn, same as test_mutual_treat_
    # upgrades_neutral_to_allied_only_once_promoted_next_turn above.
    state = _state()
    header_1 = KingdomMoveHeader(raw_fields=[27, 1 << 2, 0, 101, 1, 15, 1])
    header_2 = KingdomMoveHeader(raw_fields=[27, 1 << 1, 0, 101, 1, 15, 1])

    sync_treat_orders_from_kingdom_headers(state, {1: header_1, 2: header_2})
    apply_treat_orders(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert state.pending_treat_transitions[frozenset({1, 2})] == (
        DiplomaticRelation.NEUTRAL,
        DiplomaticRelation.ALLIED,
    )

    advance_pending_diplomacy(state)

    assert state.is_allied(1, 2)


# -- Furore Diplomatico (user ruling 2026-11-26) ---------------------------------


def _allied(alignment_a: Alignment, alignment_b: Alignment) -> GameState:
    state = _state(alignment_a, alignment_b)
    set_relation(state, 1, 2, DiplomaticRelation.ALLIED)
    return state


def test_alignment_distance_follows_the_rulebooks_order_of_kingdom_alignments():
    assert alignment_distance(_state(Alignment.DIVINE, Alignment.PAGAN), 1, 2) == 4  # the rulebook's own example
    assert alignment_distance(_state(Alignment.GOOD, Alignment.EVIL), 1, 2) == 4
    assert alignment_distance(_state(Alignment.DIVINE, Alignment.UNDEAD), 1, 2) == 6
    assert alignment_distance(_state(Alignment.GOOD, Alignment.NEUTRAL), 1, 2) == 2
    assert alignment_distance(_state(Alignment.GOOD, Alignment.MECHANICAL), 1, 2) is None


def test_the_furor_needs_allies_more_than_three_positions_apart_and_draws_nothing_otherwise():
    for state in (
        _allied(Alignment.GOOD, Alignment.PAGAN),  # 3 apart: not enough
        _state(Alignment.DIVINE, Alignment.PAGAN),  # far apart but not Allies
    ):
        apply_diplomatic_fury(state, ScriptedRandom([]))  # an empty script: any draw would fail
        assert state.pending_break_treat_transitions == {} and state.diplomacy_fury_notices == []


def test_a_furor_at_the_end_of_the_turn_is_parked_like_an_ordinary_break_treat():
    state = _allied(Alignment.DIVINE, Alignment.PAGAN)  # distance 4: 6% a turn, never mid-turn

    apply_diplomatic_fury(state, ScriptedRandom([0.05, 0.5]))  # triggers, one level

    pair = frozenset({1, 2})
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.pending_break_treat_transitions[pair] == (DiplomaticRelation.ALLIED, DiplomaticRelation.NEUTRAL)
    assert state.pending_fury_levels[pair] == 1
    assert state.diplomacy_fury_notices == []


def test_no_furor_when_the_roll_is_above_the_chance():
    state = _allied(Alignment.DIVINE, Alignment.PAGAN)

    apply_diplomatic_fury(state, ScriptedRandom([0.06]))

    assert state.pending_break_treat_transitions == {}


def test_a_furor_can_degrade_two_levels_to_war():
    state = _allied(Alignment.DIVINE, Alignment.PAGAN)

    apply_diplomatic_fury(state, ScriptedRandom([0.0, 0.29]))

    assert state.pending_break_treat_transitions[frozenset({1, 2})][1] is DiplomaticRelation.ENEMY
    assert state.pending_fury_levels[frozenset({1, 2})] == 2


def test_the_chance_grows_with_the_distance():
    for alignments, roll, expected in (
        ((Alignment.DIVINE, Alignment.EVIL), 0.11, True),  # distance 5: 12%
        ((Alignment.DIVINE, Alignment.EVIL), 0.12, False),
        ((Alignment.DIVINE, Alignment.UNDEAD), 0.19, True),  # distance 6: 20%
        ((Alignment.DIVINE, Alignment.UNDEAD), 0.20, False),
    ):
        state = _allied(*alignments)
        # triggered ones also roll levels (and, from distance 5, the timing: 0.99 = at the end of the turn)
        apply_diplomatic_fury(state, ScriptedRandom([roll, 0.5, 0.99]))
        assert bool(state.pending_break_treat_transitions) is expected


def test_a_marked_difference_can_blow_up_during_the_turn():
    state = _allied(Alignment.DIVINE, Alignment.UNDEAD)

    apply_diplomatic_fury(state, ScriptedRandom([0.0, 0.5, 0.19]))  # triggers, one level, mid-turn (< 20%)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL and not state.is_allied(1, 2)
    assert state.diplomacy_fury_notices == [(1, 2, 1)]
    assert state.pending_break_treat_transitions == {}


def test_only_a_marked_difference_gets_the_mid_turn_roll():
    state = _allied(Alignment.DIVINE, Alignment.PAGAN)  # distance 4: the script has no third draw

    apply_diplomatic_fury(state, ScriptedRandom([0.0, 0.5]))

    assert frozenset({1, 2}) in state.pending_break_treat_transitions


def test_a_pending_furor_is_narrated_as_a_furor_when_it_lands_next_turn():
    state = _allied(Alignment.DIVINE, Alignment.PAGAN)
    apply_diplomatic_fury(state, ScriptedRandom([0.0, 0.5]))

    advance_pending_diplomacy(state)

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert state.diplomacy_fury_notices == [(1, 2, 1)]
    assert state.diplomacy_relation_change_notices == []  # not a Break Treat
    assert state.pending_fury_levels == {}


def test_a_pair_with_a_break_treat_pending_gets_no_furor():
    state = _allied(Alignment.DIVINE, Alignment.PAGAN)
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)

    apply_diplomatic_fury(state, ScriptedRandom([]))  # no draw at all

    assert state.pending_fury_levels == {}


# -- the report notes of each order -----------------------------------------------


def test_orders_leave_a_note_for_their_issuer():
    state = _state()
    state.treat_permissions.update({(1, 2), (2, 1)})
    apply_treat_orders(state)
    assert sorted(state.diplomacy_order_notes) == [(1, 2, "accepted"), (2, 1, "accepted")]

    state = _state()
    state.treat_permissions.add((1, 2))  # not reciprocated
    apply_treat_orders(state)
    assert state.diplomacy_order_notes == [(1, 2, "refused")]

    state = _allied(Alignment.GOOD, Alignment.GOOD)
    state.treat_permissions.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomacy_order_notes == [(1, 2, "already_allied")]

    state = _allied(Alignment.GOOD, Alignment.GOOD)
    state.break_treat_orders.add((1, 2))
    state.treat_permissions.add((2, 1))  # the Break Treat wins: that Treat is refused
    apply_treat_orders(state)
    assert sorted(state.diplomacy_order_notes) == [(1, 2, "broken"), (2, 1, "refused")]


def test_a_break_treat_that_changes_nothing_leaves_no_note():
    state = _state()
    set_relation(state, 1, 2, DiplomaticRelation.ENEMY)  # already at war
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomacy_order_notes == []


def test_the_druids_one_sided_treat_is_accepted():
    state = _state(alignment_a=Alignment.DRUID)
    state.treat_permissions.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomacy_order_notes == [(1, 2, "accepted")]


def test_the_break_treat_issuer_is_remembered_for_the_notice():
    state = _state()
    set_relation(state, 1, 2, DiplomaticRelation.ALLIED)
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.pending_break_issuers[frozenset({1, 2})] == frozenset({1})
    state.diplomacy_notice_issuers = {}
    advance_pending_diplomacy(state)
    assert state.diplomacy_notice_issuers[frozenset({1, 2})] == frozenset({1})

    state = _state(alignment_a=Alignment.EVIL)  # immediate
    set_relation(state, 1, 2, DiplomaticRelation.ALLIED)
    state.break_treat_orders.add((1, 2))
    apply_treat_orders(state)
    assert state.diplomacy_notice_issuers[frozenset({1, 2})] == frozenset({1})
