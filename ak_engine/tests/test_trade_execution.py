from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.trade_decode import TradeRequest
from ak_engine.turn.trade_execution import GOLD_GIVE_MAX_PERCENT, TradeExecutionResult, execute_give, execute_gold_give

GIVER_KINGDOM = 1
RECIPIENT_KINGDOM = 2
GIVER_LEADER = 1
RECIPIENT_LEADER = 2
HOME = HexCoord(3, 9)
ELSEWHERE = HexCoord(9, 9)


def _state(*, giver_treasury: int = 1000, giver_is_king: bool = True) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(GIVER_KINGDOM, "Giver", Race.HUMAN, Alignment.GOOD, HOME, treasury=giver_treasury))
    state.add_kingdom(KingdomState(RECIPIENT_KINGDOM, "Recipient", Race.HUMAN, Alignment.GOOD, HOME, treasury=0))
    state.add_leader(LeaderState(GIVER_LEADER, GIVER_KINGDOM, "King", HOME, is_king=giver_is_king))
    return state


def _state_with_recipient(
    *, giver_treasury: int = 1000, recipient_is_king: bool = True, recipient_location: HexCoord = HOME
) -> GameState:
    state = _state(giver_treasury=giver_treasury)
    state.add_leader(
        LeaderState(RECIPIENT_LEADER, RECIPIENT_KINGDOM, "Recipient King", recipient_location, is_king=recipient_is_king)
    )
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


# -- execute_give() (Phase 133: real recipient now decoded) --


def test_execute_give_gold_path_succeeds_between_co_located_kings():
    state = _state_with_recipient(giver_treasury=1000)
    request = TradeRequest(obj=100, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result == TradeExecutionResult(applied=True, gold_transferred=100)
    assert state.kingdoms[GIVER_KINGDOM].treasury == 900
    assert state.kingdoms[RECIPIENT_KINGDOM].treasury == 100


def test_execute_give_item_path_transfers_a_genuinely_owned_item():
    # "si passa l'oggetto e non l'oro" -- item takes priority whenever the
    # giver genuinely owns an item with that id (Phase 140).
    state = _state_with_recipient()
    item = state.add_item(Treasure.WAND_FIREBALL, GIVER_LEADER, charges=5)
    request = TradeRequest(obj=item.item_id, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result == TradeExecutionResult(applied=True, item_transferred=True, item=item)
    assert state.items[item.item_id].owner_leader_id == RECIPIENT_LEADER
    assert state.kingdoms[GIVER_KINGDOM].treasury == 1000  # untouched -- item path, not gold


def test_execute_give_item_path_ignores_an_item_the_giver_doesnt_own():
    # obj resolves to a real item instance, but a *different* leader owns
    # it -- falls through to the gold path instead of transferring.
    state = _state_with_recipient()
    item = state.add_item(Treasure.WAND_FIREBALL, RECIPIENT_LEADER, charges=5)
    request = TradeRequest(obj=item.item_id, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result == TradeExecutionResult(applied=True, gold_transferred=item.item_id)
    assert state.items[item.item_id].owner_leader_id == RECIPIENT_LEADER  # untouched


# -- Phase 547: Valhalla visitor's own fixed item can't be Given away --


def test_execute_give_rejects_the_valhalla_visitors_own_fixed_item():
    state = _state_with_recipient()
    item = state.add_item(Treasure.WAND_FIREBALL, VALHALLA_VISITOR_LEADER_ID, charges=5)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, GIVER_KINGDOM, "Visitor", HOME, valhalla_fixed_item_id=item.item_id))
    request = TradeRequest(obj=item.item_id, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, VALHALLA_VISITOR_LEADER_ID, request)

    assert result.applied is False
    assert result.reason == "the Valhalla visitor's own fixed item cannot be given away"
    assert state.items[item.item_id].owner_leader_id == VALHALLA_VISITOR_LEADER_ID  # untouched


def test_execute_give_allows_the_valhalla_visitor_to_give_away_a_different_item():
    # The block is scoped to the one tracked fixed-item id -- anything
    # else the visitor happens to hold (e.g. Search loot) is an ordinary Give.
    state = _state_with_recipient()
    fixed_item = state.add_item(Treasure.WAND_FIREBALL, VALHALLA_VISITOR_LEADER_ID, charges=5)
    other_item = state.add_item(Treasure.ABILITY_MELEE, VALHALLA_VISITOR_LEADER_ID)
    state.add_leader(
        LeaderState(VALHALLA_VISITOR_LEADER_ID, GIVER_KINGDOM, "Visitor", HOME, valhalla_fixed_item_id=fixed_item.item_id)
    )
    request = TradeRequest(obj=other_item.item_id, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, VALHALLA_VISITOR_LEADER_ID, request)

    assert result.applied is True
    assert result.item_transferred is True
    assert state.items[other_item.item_id].owner_leader_id == RECIPIENT_LEADER


def test_execute_give_item_path_crosses_kingdoms_with_no_king_requirement():
    # The user's own description: "Se l'eroe appartiene a un altro reame,
    # l'oggetto passa di mano" -- no King status needed on either side for
    # the item path, unlike the gold path.
    state = _state_with_recipient(recipient_is_king=False)
    state.leaders[GIVER_LEADER].is_king = False
    item = state.add_item(Treasure.WAND_FIREBALL, GIVER_LEADER)
    request = TradeRequest(obj=item.item_id, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result == TradeExecutionResult(applied=True, item_transferred=True, item=item)
    assert state.items[item.item_id].owner_leader_id == RECIPIENT_LEADER


def test_execute_give_no_recipient_decoded():
    state = _state_with_recipient()
    request = TradeRequest(obj=100, target_leader_id=None, extra=[0])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "no recipient decoded"


def test_execute_give_recipient_not_found():
    state = _state()  # no recipient leader registered
    request = TradeRequest(obj=100, target_leader_id=999, extra=[0, 999])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "recipient not found"


def test_execute_give_giver_not_found():
    state = _state_with_recipient()
    request = TradeRequest(obj=100, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, 999, request)

    assert result.applied is False
    assert result.reason == "giver not found"


def test_execute_give_rejects_not_co_located():
    state = _state_with_recipient(recipient_location=ELSEWHERE)
    request = TradeRequest(obj=100, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "not co-located with recipient"


def test_execute_give_rejects_non_king_recipient():
    # "You can give limited amounts of gold to other Kings" -- the
    # recipient, not just the giver, must be a King.
    state = _state_with_recipient(recipient_is_king=False)
    request = TradeRequest(obj=100, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "gold Give recipient must be a King"


def test_execute_give_gold_path_still_enforces_the_10_percent_cap():
    state = _state_with_recipient(giver_treasury=100)
    request = TradeRequest(obj=11, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert "exceeds 10% treasury cap" in result.reason
