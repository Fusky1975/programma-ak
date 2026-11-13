"""Tests for turn/blackmail.py -- see its module docstring for the full,
AKGEN_advanced_ability-text-plus-AKPROSE-choice-080/090-sourced mechanic
these exercise.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import BlackmailClaim, GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.blackmail import (
    advance_blackmail_claims,
    blackmail_demand_amount,
    blackmail_detection_chance,
    maybe_detect_blackmail,
    resolve_unpaid_blackmail,
)

from _helpers import ScriptedRandom

HOME = HexCoord(0, 0)


def test_blackmail_detection_chance_baseline_at_neutral():
    assert blackmail_detection_chance(Alignment.NEUTRAL) == 0.20


def test_blackmail_detection_chance_lower_for_good_alignment():
    assert blackmail_detection_chance(Alignment.DIVINE) < 0.20


def test_blackmail_detection_chance_higher_for_evil_alignment():
    assert blackmail_detection_chance(Alignment.UNDEAD) > 0.20


def test_blackmail_detection_chance_floor_and_ceiling():
    # Mechanical/Special sit outside the real Heavenly..Undead spectrum
    # and are clamped in at the Undead end (ordinal 7).
    assert blackmail_detection_chance(Alignment.SPECIAL) == blackmail_detection_chance(Alignment.UNDEAD)
    assert blackmail_detection_chance(Alignment.UNDEAD) == 0.32


def test_blackmail_demand_amount_baseline():
    assert blackmail_demand_amount(Alignment.NEUTRAL, target_treasury=0, spy_exponent=0) == 15


def test_blackmail_demand_amount_richer_king_pays_more():
    assert blackmail_demand_amount(Alignment.NEUTRAL, target_treasury=500, spy_exponent=0) == 20


def test_blackmail_demand_amount_evil_king_pays_less():
    assert blackmail_demand_amount(Alignment.UNDEAD, target_treasury=0, spy_exponent=0) < 15


def test_blackmail_demand_amount_good_king_gets_no_reduction():
    # The ability text only ever describes a reduction for evil-tending
    # kings -- a good-tending king pays the ordinary baseline, not more.
    assert blackmail_demand_amount(Alignment.DIVINE, target_treasury=0, spy_exponent=0) == 15


def test_blackmail_demand_amount_never_drops_below_1_after_halving():
    # BLACKMAIL_DEMAND_FLOOR (5) applies to the pre-halving base; the
    # final `max(1, ...)` is what actually binds once the exponent has
    # halved a small base down toward (or below) zero.
    assert blackmail_demand_amount(Alignment.UNDEAD, target_treasury=0, spy_exponent=5) == 1


def test_blackmail_demand_amount_halves_per_unpaid_exponent():
    base = blackmail_demand_amount(Alignment.NEUTRAL, target_treasury=0, spy_exponent=0)
    once = blackmail_demand_amount(Alignment.NEUTRAL, target_treasury=0, spy_exponent=1)
    twice = blackmail_demand_amount(Alignment.NEUTRAL, target_treasury=0, spy_exponent=2)
    assert once == round(base / 2)
    assert twice == round(base / 4)


def _state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Spydom", Race.HUMAN, Alignment.NEUTRAL, HOME))
    state.add_kingdom(KingdomState(2, "Targetia", Race.HUMAN, Alignment.NEUTRAL, HOME, treasury=100))
    return state


def _spy(exponent: int = 0) -> LeaderState:
    return LeaderState(1, kingdom_id=1, name="Spymaster", location=HOME, unpaid_blackmail_penalty_exponent=exponent)


def _king(kingdom_id: int = 2) -> LeaderState:
    return LeaderState(2, kingdom_id=kingdom_id, name="King Bob", location=HOME, is_king=True)


def test_advance_blackmail_claims_promotes_pending_to_active():
    state = _state()
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].pending_blackmail = claim

    advance_blackmail_claims(state)

    assert state.kingdoms[2].pending_blackmail is None
    assert state.kingdoms[2].active_blackmail is claim


def test_advance_blackmail_claims_leaves_active_alone_when_no_pending():
    state = _state()
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].active_blackmail = claim

    advance_blackmail_claims(state)

    assert state.kingdoms[2].active_blackmail is claim
    assert state.kingdoms[2].pending_blackmail is None


def test_maybe_detect_blackmail_refuses_non_king_target():
    state = _state()
    spy = _spy()
    target = LeaderState(2, kingdom_id=2, name="Hero", location=HOME, is_king=False)

    assert maybe_detect_blackmail(state, spy, target, ScriptedRandom([])) is None


def test_maybe_detect_blackmail_refuses_same_kingdom_target():
    state = _state()
    spy = LeaderState(1, kingdom_id=2, name="Spymaster", location=HOME)
    target = _king()

    assert maybe_detect_blackmail(state, spy, target, ScriptedRandom([])) is None


def test_maybe_detect_blackmail_refuses_kingdomless_trailer():
    state = _state()
    spy = LeaderState(1, kingdom_id=None, name="Wandering Spy", location=HOME)
    target = _king()

    assert maybe_detect_blackmail(state, spy, target, ScriptedRandom([])) is None


def test_maybe_detect_blackmail_refuses_when_a_pending_claim_already_exists():
    state = _state()
    state.kingdoms[2].pending_blackmail = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=3, amount=10)
    spy = _spy()
    target = _king()

    assert maybe_detect_blackmail(state, spy, target, ScriptedRandom([])) is None


def test_maybe_detect_blackmail_refuses_when_an_active_claim_already_exists():
    state = _state()
    state.kingdoms[2].active_blackmail = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=3, amount=10)
    spy = _spy()
    target = _king()

    assert maybe_detect_blackmail(state, spy, target, ScriptedRandom([])) is None


def test_maybe_detect_blackmail_failed_roll_returns_none_and_creates_no_claim():
    state = _state()
    spy = _spy()
    target = _king()

    result = maybe_detect_blackmail(state, spy, target, ScriptedRandom([0.99]))

    assert result is None
    assert state.kingdoms[2].pending_blackmail is None


def test_maybe_detect_blackmail_success_creates_pending_claim():
    state = _state()
    spy = _spy()
    target = _king()

    result = maybe_detect_blackmail(state, spy, target, ScriptedRandom([0.0]))

    assert result is not None
    assert result.spy_leader_id == 1
    assert result.spy_kingdom_id == 1
    assert result.amount == blackmail_demand_amount(Alignment.NEUTRAL, 100, 0)
    assert state.kingdoms[2].pending_blackmail is result


def test_resolve_unpaid_blackmail_returns_zero_with_no_active_claim():
    state = _state()

    assert resolve_unpaid_blackmail(state, 2) == 0


def test_resolve_unpaid_blackmail_applies_penalty_and_increments_exponent_and_clears():
    state = _state()
    state.add_leader(_spy())
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].active_blackmail = claim

    penalty = resolve_unpaid_blackmail(state, 2)

    assert penalty == 45
    assert state.kingdoms[2].active_blackmail is None
    assert state.leaders[1].unpaid_blackmail_penalty_exponent == 1


def test_resolve_unpaid_blackmail_survives_a_dead_spy():
    state = _state()
    claim = BlackmailClaim(spy_leader_id=999, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].active_blackmail = claim

    penalty = resolve_unpaid_blackmail(state, 2)

    assert penalty == 45
    assert state.kingdoms[2].active_blackmail is None


def test_resolve_unpaid_blackmail_still_increments_the_exponent_for_an_archived_spy():
    # Phase 1192 bug fix: a spy who died earlier the same turn (e.g. in
    # combat) is moved by GameState.remove_leader() into dead_leaders,
    # not destroyed -- the escalation must still land on that archived
    # LeaderState for a future Resurrection to see it.
    state = _state()
    state.add_leader(_spy())
    state.remove_leader(1)
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].active_blackmail = claim

    penalty = resolve_unpaid_blackmail(state, 2)

    assert penalty == 45
    assert 1 not in state.leaders
    assert state.dead_leaders[1].unpaid_blackmail_penalty_exponent == 1
