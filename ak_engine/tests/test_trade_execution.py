from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.trade_execution import GOLD_GIVE_MAX_PERCENT, TradeExecutionResult, execute_gold_give

GIVER_KINGDOM = 1
RECIPIENT_KINGDOM = 2
GIVER_LEADER = 1
HOME = HexCoord(3, 9)


def _state(*, giver_treasury: int = 1000, giver_is_king: bool = True) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(GIVER_KINGDOM, "Giver", Race.HUMAN, Alignment.GOOD, HOME, treasury=giver_treasury))
    state.add_kingdom(KingdomState(RECIPIENT_KINGDOM, "Recipient", Race.HUMAN, Alignment.GOOD, HOME, treasury=0))
    state.add_leader(LeaderState(GIVER_LEADER, GIVER_KINGDOM, "King", HOME, is_king=giver_is_king))
    return state


def test_execute_gold_give_moves_gold_within_the_10_percent_cap():
    state = _state(giver_treasury=1000)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 100)

    assert result == TradeExecutionResult(applied=True, gold_transferred=100)
    assert state.kingdoms[GIVER_KINGDOM].treasury == 900
    assert state.kingdoms[RECIPIENT_KINGDOM].treasury == 100


def test_execute_gold_give_rejects_amount_over_the_cap():
    state = _state(giver_treasury=1000)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 101)

    assert result.applied is False
    assert "exceeds 10% treasury cap" in result.reason
    assert state.kingdoms[GIVER_KINGDOM].treasury == 1000
    assert state.kingdoms[RECIPIENT_KINGDOM].treasury == 0


def test_execute_gold_give_cap_is_exactly_10_percent():
    assert GOLD_GIVE_MAX_PERCENT == 10
    state = _state(giver_treasury=250)  # 10% of 250 = 25 (integer floor)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 25)

    assert result.applied is True
    assert state.kingdoms[GIVER_KINGDOM].treasury == 225


def test_execute_gold_give_rejects_non_king_giver():
    state = _state(giver_is_king=False)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 1)

    assert result.applied is False
    assert result.reason == "only a King may Give Gold"


def test_execute_gold_give_rejects_non_positive_amount():
    state = _state()

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 0)

    assert result.applied is False
    assert result.reason == "gold amount must be positive"


def test_execute_gold_give_rejects_unknown_giver_leader():
    state = _state()

    result = execute_gold_give(state, 999, RECIPIENT_KINGDOM, 1)

    assert result.applied is False
    assert result.reason == "giver not found"


def test_execute_gold_give_rejects_unknown_recipient_kingdom():
    state = _state()

    result = execute_gold_give(state, GIVER_LEADER, 999, 1)

    assert result.applied is False
    assert result.reason == "kingdom not found"
