from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import BlackmailClaim, GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.trade_decode import TradeRequest
from ak_engine.turn.trade_execution import (
    GOLD_GIVE_MAX_PERCENT,
    TradeExecutionResult,
    execute_curator_research,
    execute_give,
    execute_gold_give,
)

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
    # The 10% cap's own basis (2026-11-04) -- real play takes this
    # snapshot once at the start of every run_turn() call; these tests
    # call execute_gold_give()/execute_give() directly, so it's set here
    # to match giver_treasury exactly, simulating "this call is the
    # first Give of a fresh turn."
    state.kingdoms[GIVER_KINGDOM].treasury_at_turn_start = giver_treasury
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


def test_execute_gold_give_floor_allows_10_gold_when_10_percent_is_lower():
    # Bug fix, sourced directly from the user (2026-10-29), independently
    # confirmed in both RULES.AK and ADDEND.AK verbatim: "he may always
    # give out at least 10 gold if he has it in his treasury." 10% of
    # 50 is 5, but the King has 50 in treasury, so the real floor of 10
    # applies instead.
    state = _state(giver_treasury=50)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 10)

    assert result.applied is True
    assert state.kingdoms[GIVER_KINGDOM].treasury == 40


def test_execute_gold_give_floor_still_rejects_more_than_the_floor():
    state = _state(giver_treasury=50)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 11)

    assert result.applied is False
    assert "exceeds 10% treasury cap" in result.reason


def test_execute_gold_give_floor_never_exceeds_the_givers_real_treasury():
    # "if he has it in his treasury" -- with only 7 in treasury, the
    # King can't reach the 10-gold floor at all; the ordinary 10% cap
    # (0, floored) still applies.
    state = _state(giver_treasury=7)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 10)

    assert result.applied is False
    assert state.kingdoms[GIVER_KINGDOM].treasury == 7


def test_execute_gold_give_rejects_non_king_giver():
    state = _state(giver_is_king=False)

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 1)

    assert result.applied is False
    assert result.reason == "only a King may Give Gold"


# -- 2026-11-04: the 10% cap is a cumulative per-gameturn budget, based
# on a start-of-turn snapshot, not a fresh live-treasury allowance
# re-applied to each individual Give. --------------------------------


def test_execute_gold_give_a_second_give_this_turn_draws_from_the_same_budget():
    state = _state(giver_treasury=1000)  # budget for the turn: 100
    first = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 60)
    assert first.applied is True

    second = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 41)  # 60 + 41 > 100

    assert second.applied is False
    assert "exceeds 10% treasury cap" in second.reason
    # The first Give already went through -- only the second was rejected.
    assert state.kingdoms[GIVER_KINGDOM].treasury == 940
    assert state.kingdoms[GIVER_KINGDOM].gold_given_this_turn == 60


def test_execute_gold_give_a_second_give_within_the_remaining_budget_succeeds():
    state = _state(giver_treasury=1000)  # budget for the turn: 100
    execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 60)

    second = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 40)  # exactly the remaining 40

    assert second.applied is True
    assert state.kingdoms[GIVER_KINGDOM].treasury == 900
    assert state.kingdoms[GIVER_KINGDOM].gold_given_this_turn == 100


def test_execute_gold_give_cap_basis_is_the_turn_start_snapshot_not_live_treasury():
    # The King's live treasury has already dropped below what it was at
    # the start of the turn (e.g. spent on Recruit earlier this same
    # turn) -- the 10% cap still reads the real snapshot (1000), not the
    # smaller live value, so his remaining budget is still 100.
    state = _state(giver_treasury=1000)
    state.kingdoms[GIVER_KINGDOM].treasury = 150  # spent 850 elsewhere this turn

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 100)

    assert result.applied is True
    assert state.kingdoms[GIVER_KINGDOM].treasury == 50


def test_execute_gold_give_rejects_when_live_treasury_cannot_cover_it_despite_remaining_budget():
    # Same setup as above, but requesting more than what's physically
    # left on hand, even though it's still within the turn's own 10%
    # budget -- a check that was never reachable before this fix (the
    # old live-treasury-based cap could never exceed the live treasury).
    state = _state(giver_treasury=1000)
    state.kingdoms[GIVER_KINGDOM].treasury = 80  # spent 920 elsewhere this turn

    result = execute_gold_give(state, GIVER_LEADER, RECIPIENT_KINGDOM, 100)

    assert result.applied is False
    assert "exceeds 10% treasury cap" in result.reason
    assert state.kingdoms[GIVER_KINGDOM].treasury == 80
    assert state.kingdoms[GIVER_KINGDOM].gold_given_this_turn == 0


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


def test_execute_give_gold_path_allows_a_hero_recipient_of_a_different_kingdom():
    # Bug fix, sourced directly from the user (2026-10-29), independently
    # confirmed in both RULES.AK and ADDEND.AK verbatim: "giving it to
    # another player's character (King or Hero)" -- a Hero recipient of
    # a genuinely different Kingdom is just as valid as a King.
    state = _state_with_recipient(recipient_is_king=False)
    request = TradeRequest(obj=100, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is True
    assert result.gold_transferred == 100


def test_execute_give_gold_path_rejects_a_recipient_of_the_givers_own_kingdom():
    # Confirmed with the user: "another player's character" requires a
    # genuinely different Kingdom, not merely "not a King."
    state = _state_with_recipient(recipient_is_king=False)
    state.leaders[RECIPIENT_LEADER].kingdom_id = GIVER_KINGDOM
    request = TradeRequest(obj=100, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "gold Give recipient must belong to a different Kingdom"


def test_execute_give_gold_path_rejects_a_recipient_with_no_kingdom():
    state = _state_with_recipient(recipient_is_king=False)
    state.leaders[RECIPIENT_LEADER].kingdom_id = None
    request = TradeRequest(obj=100, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "gold Give recipient must belong to a different Kingdom"


def test_execute_give_gold_path_still_enforces_the_10_percent_cap():
    state = _state_with_recipient(giver_treasury=100)
    request = TradeRequest(obj=11, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert "exceeds 10% treasury cap" in result.reason


# -- Phase 713: AdvancedAbility.SPY_BLACKMAIL's own real "no co-location
# needed" payment exception --


def test_execute_give_pays_off_blackmail_without_co_location():
    state = _state_with_recipient(giver_treasury=1000, recipient_location=ELSEWHERE)
    claim = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=RECIPIENT_KINGDOM, amount=15)
    state.kingdoms[GIVER_KINGDOM].active_blackmail = claim
    state.add_leader(LeaderState(9, RECIPIENT_KINGDOM, "Spymaster", ELSEWHERE, unpaid_blackmail_penalty_exponent=2))
    request = TradeRequest(obj=15, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result == TradeExecutionResult(applied=True, gold_transferred=15)
    assert state.kingdoms[GIVER_KINGDOM].active_blackmail is None
    assert state.leaders[9].unpaid_blackmail_penalty_exponent == 0


def test_execute_give_paying_more_than_the_claim_still_clears_it():
    state = _state_with_recipient(giver_treasury=1000, recipient_location=ELSEWHERE)
    claim = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=RECIPIENT_KINGDOM, amount=15)
    state.kingdoms[GIVER_KINGDOM].active_blackmail = claim
    request = TradeRequest(obj=20, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is True
    assert state.kingdoms[GIVER_KINGDOM].active_blackmail is None


def test_execute_give_paying_less_than_the_claim_does_not_clear_it():
    state = _state_with_recipient(giver_treasury=1000, recipient_location=ELSEWHERE)
    claim = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=RECIPIENT_KINGDOM, amount=15)
    state.kingdoms[GIVER_KINGDOM].active_blackmail = claim
    request = TradeRequest(obj=5, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is True  # the gold transfer itself still succeeds
    assert state.kingdoms[GIVER_KINGDOM].active_blackmail is claim  # but doesn't satisfy the demand


def test_execute_give_non_co_located_still_refuses_without_an_active_claim():
    state = _state_with_recipient(giver_treasury=1000, recipient_location=ELSEWHERE)
    request = TradeRequest(obj=15, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "not co-located with recipient"


def test_execute_give_non_co_located_still_refuses_when_paying_a_different_kingdom():
    # An active claim exists, but it's owed to a THIRD kingdom, not the
    # recipient of this particular Give -- the bypass must not apply.
    state = _state_with_recipient(giver_treasury=1000, recipient_location=ELSEWHERE)
    state.kingdoms[GIVER_KINGDOM].active_blackmail = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=3, amount=15)
    request = TradeRequest(obj=15, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "not co-located with recipient"


def test_execute_give_co_located_unrelated_gold_give_is_unaffected_by_an_active_claim():
    state = _state_with_recipient(giver_treasury=1000)
    claim = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=RECIPIENT_KINGDOM, amount=15)
    state.kingdoms[GIVER_KINGDOM].active_blackmail = claim
    request = TradeRequest(obj=50, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result == TradeExecutionResult(applied=True, gold_transferred=50)
    # A co-located ordinary Give that happens to also clear a matching
    # claim is fine (indistinguishable from an intentional payment) --
    # only the amount/recipient match, not "was it really meant as one".
    assert state.kingdoms[GIVER_KINGDOM].active_blackmail is None


def test_execute_give_item_give_is_never_treated_as_a_blackmail_payment():
    state = _state_with_recipient(giver_treasury=1000, recipient_location=ELSEWHERE)
    claim = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=RECIPIENT_KINGDOM, amount=15)
    state.kingdoms[GIVER_KINGDOM].active_blackmail = claim
    item = state.add_item(Treasure.WAND_FIREBALL, GIVER_LEADER, charges=5)
    request = TradeRequest(obj=item.item_id, target_leader_id=RECIPIENT_LEADER, extra=[0, RECIPIENT_LEADER])

    result = execute_give(state, GIVER_LEADER, request)

    assert result.applied is False
    assert result.reason == "not co-located with recipient"
    assert state.kingdoms[GIVER_KINGDOM].active_blackmail is claim


# -- Phase 667: Office.CURATOR's own "research any item number" perk --


def test_execute_curator_research_reveals_the_treasure_of_an_owned_item():
    state = _state()
    item = state.add_item(Treasure.WAND_FIREBALL, GIVER_LEADER, charges=5)

    result = execute_curator_research(state, item.item_id)

    assert result.applied is True
    assert result.item_id == item.item_id
    assert result.treasure is Treasure.WAND_FIREBALL


def test_execute_curator_research_reveals_the_treasure_of_an_unowned_item():
    # "any item number in the world" -- a Feature-guarded item with no
    # owner still has a real ItemInstance, resolvable the same way.
    state = _state()
    item = state.add_item(Treasure.WAND_FIREBALL, None)

    result = execute_curator_research(state, item.item_id)

    assert result.applied is True
    assert result.treasure is Treasure.WAND_FIREBALL


def test_execute_curator_research_fails_for_an_item_number_that_does_not_exist():
    state = _state()

    result = execute_curator_research(state, 999)

    assert result.applied is False
    assert result.item_id == 999
    assert result.treasure is None
    assert result.reason == "no such item number exists in the world"
