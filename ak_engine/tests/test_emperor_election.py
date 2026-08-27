"""Tests for turn/emperor_election.py -- see its module docstring for
the full rulebook [10.2] derivation this exercises.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import VOTE_TURN_SENTINEL, KingdomMoveHeader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.emperor_election import (
    ELECTION_REQUEST_THRESHOLD_PERCENT,
    ElectionCallOutcome,
    ElectionResult,
    _alignment_auto_trigger,
    _election_callers_weight,
    _highest_vote_weight_kingdom,
    _kingdom_office_vote_points,
    _kingdom_treasure_vote_points,
    alignment_bloc_vote_weights,
    alignment_victory_point_reduction_percent,
    can_request_election,
    election_threshold_percent,
    evaluate_election_call,
    kingdom_election_vote_weight,
    process_election_turn,
    resolve_emperor_election,
    tally_emperor_vote,
)

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_kingdom(KingdomState(3, "Otherland", Race.HUMAN, Alignment.EVIL, HexCoord(2, 2)))
    return state


def give_tax(state: GameState, kingdom_id: int, coord: HexCoord, tax: int) -> None:
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=kingdom_id, tax=tax))


def _header(kprevgold: int = 15) -> KingdomMoveHeader:
    # A generic real-shaped header (Phase 464 field order) whose only
    # varying field for these tests is kprevgold -- the Vote field.
    return KingdomMoveHeader(raw_fields=[27, 1, 0, 101, 1, kprevgold, 1])


# -- can_request_election ----------------------------------------------


def test_can_request_election_single_king_above_threshold():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 56)
    give_tax(state, 2, HexCoord(1, 1), 22)
    give_tax(state, 3, HexCoord(2, 2), 22)

    assert can_request_election(state, 1, current_turn=5) is True


def test_can_request_election_single_king_below_threshold():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 50)
    give_tax(state, 2, HexCoord(1, 1), 25)
    give_tax(state, 3, HexCoord(2, 2), 25)

    assert can_request_election(state, 1, current_turn=5) is False


def test_can_request_election_exactly_at_threshold_is_not_enough():
    # ">55%", strictly greater -- exactly 55% must not qualify.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 55)
    give_tax(state, 2, HexCoord(1, 1), 45)

    assert can_request_election(state, 1, current_turn=5) is False


def test_can_request_election_via_alliance_combined_total():
    state = make_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    give_tax(state, 1, HexCoord(0, 0), 30)
    give_tax(state, 2, HexCoord(1, 1), 30)
    give_tax(state, 3, HexCoord(2, 2), 40)

    assert can_request_election(state, 1, current_turn=5) is True
    # Neither ally alone clears the threshold.
    assert 30 * 100 <= ELECTION_REQUEST_THRESHOLD_PERCENT * 100


def test_can_request_election_alliance_is_transitive():
    state = make_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.allied_kingdoms.add(frozenset({2, 3}))
    give_tax(state, 1, HexCoord(0, 0), 20)
    give_tax(state, 2, HexCoord(1, 1), 20)
    give_tax(state, 3, HexCoord(2, 2), 20)

    # 1-2-3 form one connected alliance component -- 60/60 = 100% > 55%.
    assert can_request_election(state, 1, current_turn=5) is True


def test_can_request_election_false_with_zero_world_tax_base():
    state = make_state()

    assert can_request_election(state, 1, current_turn=5) is False


def test_can_request_election_blocked_by_consecutive_turn_ban():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 90)
    give_tax(state, 2, HexCoord(1, 1), 10)
    state.last_emperor_vote_turn = 4

    # A request at turn 4 would schedule a vote at turn 5 == last+1 -- banned.
    assert can_request_election(state, 1, current_turn=4) is False
    # A request at turn 5 schedules a vote at turn 6 -- allowed.
    assert can_request_election(state, 1, current_turn=5) is True


# -- election_threshold_percent (Phase 377) ------------------------------


def test_election_threshold_percent_flat_before_turn_25():
    assert election_threshold_percent(1) == 55
    assert election_threshold_percent(24) == 55


def test_election_threshold_percent_erodes_from_turn_25():
    # AKGEN_embedded_catalogs.json.txt: "falls by 5 percentage points per
    # turn ... to 25% on turn 30".
    assert election_threshold_percent(25) == 50
    assert election_threshold_percent(26) == 45
    assert election_threshold_percent(27) == 40
    assert election_threshold_percent(28) == 35
    assert election_threshold_percent(29) == 30
    assert election_threshold_percent(30) == 25


def test_election_threshold_percent_floors_at_25_after_turn_30():
    assert election_threshold_percent(31) == 25
    assert election_threshold_percent(100) == 25


def test_can_request_election_uses_the_eroded_threshold_at_a_late_turn():
    # 40% would fail the flat 55% threshold but clears the real, eroded
    # turn-30 threshold (25%).
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 40)
    give_tax(state, 2, HexCoord(1, 1), 60)

    assert can_request_election(state, 1, current_turn=5) is False
    assert can_request_election(state, 1, current_turn=30) is True


# -- kingdom_election_vote_weight (Phase 450: real vote weight) ----------


def test_kingdom_election_vote_weight_is_just_tax_base_with_nothing_else():
    state = make_state()
    give_tax(state, 1, HOME, 40)

    assert kingdom_election_vote_weight(state, 1) == 40


def test_kingdom_office_vote_points_sums_held_offices_own_value():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.kingdoms[1].treasury = 10  # wins Office.TREASURER (OFFICE_VALUE == 10)

    assert _kingdom_office_vote_points(state, 1) == 10


def test_kingdom_office_vote_points_ignores_other_kingdoms_offices():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.kingdoms[1].treasury = 10

    assert _kingdom_office_vote_points(state, 2) == 0


def test_kingdom_treasure_vote_points_counts_only_the_real_legendary_set():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)  # Holy Sword -- in the real trvic=1 set
    state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=1)  # not in it

    assert _kingdom_treasure_vote_points(state, 1) == 1


def test_kingdom_treasure_vote_points_ignores_unowned_and_other_kingdoms_items():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.add_leader(LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True))
    state.add_item(Treasure.WEAPON_1, owner_leader_id=2)
    state.add_item(Treasure.WEAPON_2, owner_leader_id=None)

    assert _kingdom_treasure_vote_points(state, 1) == 0


def test_kingdom_election_vote_weight_combines_all_three_terms():
    # Tax kept below every alignment-King title's own OFFICE_MIN_POINTS
    # (25) so Treasurer is the *only* office this lone King wins --
    # otherwise a Good-aligned King with enough Tax_Base also
    # auto-wins Office.GOOD_KING for free (no other Good King exists to
    # compete with), which would make this test's arithmetic depend on
    # that unrelated mechanic instead of the one under test here.
    state = make_state()
    give_tax(state, 1, HOME, 10)
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.kingdoms[1].treasury = 10  # +10 office points (Treasurer)
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)  # +1 treasure point

    # 10 (Tax_Base) + 5*10 (office) + 5*1 (treasure) == 65
    assert kingdom_election_vote_weight(state, 1) == 65


# -- tally_emperor_vote / resolve_emperor_election -----------------------


def test_tally_emperor_vote_clear_majority_wins():
    # Phase 451: the win check short-circuits the instant a running share
    # exceeds 50% of V_world, matching the real engine's own early-exit --
    # voter 1 (Kingdom 1's own 60 weight, scanned first in ascending
    # Kingdom-ID order) alone already exceeds 60/100 == 60%, so kingdom
    # 2's own ballot is never even reached/tallied.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 60)
    give_tax(state, 2, HexCoord(1, 1), 20)
    give_tax(state, 3, HexCoord(2, 2), 20)
    ballots = {1: 1, 2: 1, 3: 2}

    result = tally_emperor_vote(state, ballots, current_turn=5)

    assert result.elected_emperor_kingdom_id == 1
    assert result.votes_by_candidate == {1: 60}
    assert result.total_votes_cast == 100  # Phase 451: this is V_world, not the sum of tallied ballots
    assert result.ballots == ballots  # Phase 656: no longer discarded after tallying


def test_tally_emperor_vote_weighs_office_and_treasure_holdings_too():
    # Kingdom 2 has less Tax_Base than Kingdom 3, but holds a legendary
    # item that closes the gap: 20 + 5*1 == 25 > Kingdom 3's bare 24.
    # Kingdom 2's own tax is kept below 25 (Office.NEUTRAL_KING's own
    # OFFICE_MIN_POINTS) so the lone King here doesn't also auto-win that
    # title for free -- see test_kingdom_election_vote_weight_combines_
    # all_three_terms's own comment for why that would confound this
    # test's arithmetic.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 60)
    give_tax(state, 2, HexCoord(1, 1), 20)
    give_tax(state, 3, HexCoord(2, 2), 24)
    state.add_leader(LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True))
    state.add_item(Treasure.WEAPON_1, owner_leader_id=2)
    ballots = {2: 2, 3: 3}

    result = tally_emperor_vote(state, ballots, current_turn=5)

    assert result.votes_by_candidate == {2: 25, 3: 24}


def test_tally_emperor_vote_no_quorum_elects_nobody():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 50)
    give_tax(state, 2, HexCoord(1, 1), 50)
    ballots = {1: 1, 2: 2}

    result = tally_emperor_vote(state, ballots, current_turn=5)

    assert result.elected_emperor_kingdom_id is None


def test_tally_emperor_vote_no_ballots_elects_nobody():
    state = make_state()

    result = tally_emperor_vote(state, {}, current_turn=5)

    assert result.elected_emperor_kingdom_id is None
    assert result.total_votes_cast == 0
    assert result.ballots == {}  # Phase 656: the world_total<=0 early return has no real ballots to show


# -- Phase 451: real win condition (world denominator + decaying threshold) --


def test_tally_emperor_vote_early_win_counts_abstainers_in_the_denominator():
    # Kingdom 3 abstains but still owns Tax_Base -- proving the real
    # denominator is V_world (every Kingdom's own vote weight, including
    # non-voters), not the sum of expressed ballots: 80/100 == 80% still
    # clears >50% even with the abstainer's own 20 counted against it.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 70)
    give_tax(state, 2, HexCoord(1, 1), 10)
    give_tax(state, 3, HexCoord(2, 2), 20)  # abstains
    ballots = {1: 1, 2: 1}

    result = tally_emperor_vote(state, ballots, current_turn=5)

    assert result.elected_emperor_kingdom_id == 1
    assert result.total_votes_cast == 100


def test_tally_emperor_vote_world_denominator_can_block_a_win_expressed_votes_alone_would_grant():
    # Kingdom 1 gets 100% of *expressed* ballots (50 out of 50 cast), but
    # Kingdom 3's own large abstaining Tax_Base dilutes the real V_world
    # denominator enough that the share never even reaches the turn-5
    # 55% decayed threshold, let alone 50%: 50/110 == 45.4%.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 40)
    give_tax(state, 2, HexCoord(1, 1), 10)
    give_tax(state, 3, HexCoord(2, 2), 60)  # abstains, but still counts toward V_world
    ballots = {1: 1, 2: 1}

    result = tally_emperor_vote(state, ballots, current_turn=5)

    assert result.elected_emperor_kingdom_id is None


def test_tally_emperor_vote_wins_below_50_percent_via_the_decayed_threshold_at_a_late_turn():
    # Share is only 30% of V_world -- well below the outright-win 50%,
    # and below the flat 55% threshold too, but turn 30's own decayed R
    # (25%, election_threshold_percent's own floor) is low enough.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 30)
    give_tax(state, 2, HexCoord(1, 1), 20)  # abstains
    give_tax(state, 3, HexCoord(2, 2), 50)  # abstains
    ballots = {1: 1}

    result_early = tally_emperor_vote(state, ballots, current_turn=5)
    result_late = tally_emperor_vote(state, ballots, current_turn=30)

    assert result_early.elected_emperor_kingdom_id is None  # 30% < 55% at turn 5
    assert result_late.elected_emperor_kingdom_id == 1  # 30% >= 25% at turn 30
    assert result_late.ballots == ballots  # Phase 656: no longer discarded after tallying


def test_tally_emperor_vote_tie_broken_by_ascending_voter_scan_order():
    # Two candidates end up with the exact same share (25% each) of
    # V_world at turn 30 (R == 25%, so both qualify) -- the real engine's
    # own "first to reach the eventual best share while scanning voters
    # in Kingdom-ID order" tie-break means candidate 3 wins: voter 1
    # (ascending order) reaches 25% before voter 2 does.
    state = GameState()
    for kingdom_id, alignment in ((1, Alignment.GOOD), (2, Alignment.NEUTRAL), (3, Alignment.EVIL), (4, Alignment.PAGAN)):
        state.add_kingdom(KingdomState(kingdom_id, f"K{kingdom_id}", Race.HUMAN, alignment, HexCoord(kingdom_id, 0)))
        give_tax(state, kingdom_id, HexCoord(kingdom_id, 0), 25)
    ballots = {1: 3, 2: 4}  # voter 1 -> candidate 3, voter 2 -> candidate 4, both weight 25

    result = tally_emperor_vote(state, ballots, current_turn=30)

    assert result.votes_by_candidate == {3: 25, 4: 25}
    assert result.elected_emperor_kingdom_id == 3


def test_tally_emperor_vote_below_decayed_threshold_for_everyone_elects_nobody():
    # Three-way split, none reaching even turn 5's own 55% threshold.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 34)
    give_tax(state, 2, HexCoord(1, 1), 33)
    give_tax(state, 3, HexCoord(2, 2), 33)
    ballots = {1: 1, 2: 2, 3: 3}

    result = tally_emperor_vote(state, ballots, current_turn=5)

    assert result.elected_emperor_kingdom_id is None


def test_resolve_emperor_election_records_winner_and_vote_turn():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 60)
    give_tax(state, 2, HexCoord(1, 1), 40)

    result = resolve_emperor_election(state, {1: 1, 2: 1}, vote_turn=6)

    assert result.elected_emperor_kingdom_id == 1
    assert state.emperor_kingdom_id == 1
    assert state.last_emperor_vote_turn == 6


def test_resolve_emperor_election_failed_vote_does_not_clear_standing_emperor():
    state = make_state()
    state.emperor_kingdom_id = 1
    give_tax(state, 1, HexCoord(0, 0), 50)
    give_tax(state, 2, HexCoord(1, 1), 50)

    result = resolve_emperor_election(state, {1: 1, 2: 2}, vote_turn=7)

    assert result.elected_emperor_kingdom_id is None
    assert state.emperor_kingdom_id == 1  # unchanged
    assert state.last_emperor_vote_turn == 7  # a vote was still held


# -- alignment_victory_point_reduction_percent ---------------------------


def test_alignment_reduction_matches_the_rulebooks_own_worked_example():
    # "un Re Pagano perde il 45% dei suoi Punti Vittoria se viene eletto
    # Imperatore un Re Buono (15% x 3)."
    assert alignment_victory_point_reduction_percent(Alignment.PAGAN, Alignment.GOOD) == 45


def test_alignment_reduction_zero_at_distance_zero():
    assert alignment_victory_point_reduction_percent(Alignment.GOOD, Alignment.GOOD) == 0


def test_alignment_reduction_covers_alignments_outside_the_original_seven():
    # Phase 558: unified with turn/victory_points.py's own real,
    # disassembly-sourced OUTLOOK_REDUCTION/capped-distance formula --
    # these three no longer return None (the previous, now-removed
    # ALIGNMENT_VP_REDUCTION_PER_STEP's own confirmed gap). Anti-Holy(6)/
    # Mechanical(8)/Special(9) all cap to ordinal 6 before differencing
    # against Good(1): distance 5, Anti-Holy's/Mechanical's/Special's own
    # 20%-per-step row -> 20 x 5 = 100%.
    assert alignment_victory_point_reduction_percent(Alignment.ANTI_HOLY, Alignment.GOOD) == 100
    assert alignment_victory_point_reduction_percent(Alignment.MECHANICAL, Alignment.GOOD) == 100
    assert alignment_victory_point_reduction_percent(Alignment.SPECIAL, Alignment.GOOD) == 100


def test_alignment_reduction_undead_distance_is_capped_at_hellish():
    # Phase 558: the real formula caps BOTH alignments' own ordinals at
    # Hellish's (Anti-Holy's) own position before differencing -- Undead
    # (real ordinal 7) reads as if it were at 6 for this purpose. Evil
    # (ordinal 5, uncapped) as Emperor: distance |min(7,6)-min(5,6)| =
    # |6-5| = 1, not the uncapped |7-5| = 2 the old formula gave --
    # Undead's own 20%-per-step row -> 20 x 1 = 20%, not 40%.
    assert alignment_victory_point_reduction_percent(Alignment.UNDEAD, Alignment.EVIL) == 20


def test_alignment_reduction_divine_undead_still_saturates_at_100_percent():
    # The rulebook's own worked example -- reproduces identically whether
    # or not the distance is capped, since it already overshoots 100%
    # either way (real capped distance 6 x 20% = 120%, capped at 100%).
    assert alignment_victory_point_reduction_percent(Alignment.UNDEAD, Alignment.DIVINE) == 100


# -- Phase 465: evaluate_election_call() and its helpers -----------------


def test_highest_vote_weight_kingdom_picks_strictly_greater():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 30)
    give_tax(state, 2, HexCoord(1, 1), 50)
    give_tax(state, 3, HexCoord(2, 2), 20)

    assert _highest_vote_weight_kingdom(state) == (2, 50)


def test_highest_vote_weight_kingdom_ties_keep_lowest_id():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 40)
    give_tax(state, 2, HexCoord(1, 1), 40)
    give_tax(state, 3, HexCoord(2, 2), 10)

    assert _highest_vote_weight_kingdom(state) == (1, 40)


def test_election_callers_weight_sums_only_the_given_kingdoms():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 10)
    give_tax(state, 2, HexCoord(1, 1), 20)
    give_tax(state, 3, HexCoord(2, 2), 30)

    assert _election_callers_weight(state, {1, 3}) == 40


def test_election_callers_weight_ignores_unknown_kingdom_ids():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 10)

    assert _election_callers_weight(state, {1, 999}) == 10


def test_alignment_bloc_vote_weights_buckets_by_kingdom_alignment():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 10)  # GOOD
    give_tax(state, 2, HexCoord(1, 1), 20)  # NEUTRAL
    give_tax(state, 3, HexCoord(2, 2), 5)  # EVIL

    weights = alignment_bloc_vote_weights(state)

    assert weights[Alignment.GOOD] == 10
    assert weights[Alignment.NEUTRAL] == 20
    assert weights[Alignment.EVIL] == 5
    assert weights[Alignment.DIVINE] == 0
    assert Alignment.MECHANICAL not in weights
    assert Alignment.SPECIAL not in weights


def test_alignment_auto_trigger_overwrites_not_first_or_highest_share():
    # Report SS13.6: a qualifying Alignment OVERWRITES a running sentinel
    # while scanning in ALIGNMENT_ORDINAL order -- the *last* qualifier
    # wins, not the first reached and not the highest share. GOOD (30%,
    # ordinal 1) has the highest share of the three but is scanned first;
    # NEUTRAL (25%, ordinal 3) and EVIL (35%, ordinal 5) both also
    # qualify and are scanned later, so EVIL (scanned last) wins even
    # though its own share isn't the highest.
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 40)  # GOOD, 40%
    give_tax(state, 2, HexCoord(1, 1), 25)  # NEUTRAL, 25%
    give_tax(state, 3, HexCoord(2, 2), 35)  # EVIL, 35%

    assert _alignment_auto_trigger(state, current_turn=30, world_total=100) == Alignment.EVIL


def test_alignment_auto_trigger_none_when_nobody_qualifies():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 34)
    give_tax(state, 2, HexCoord(1, 1), 33)
    give_tax(state, 3, HexCoord(2, 2), 33)

    # current_turn=5 -> R=55%; no single Alignment bucket reaches it.
    assert _alignment_auto_trigger(state, current_turn=5, world_total=100) is None


def test_evaluate_election_call_immediate_coronation_skips_the_vote():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 60)
    give_tax(state, 2, HexCoord(1, 1), 20)
    give_tax(state, 3, HexCoord(2, 2), 20)

    outcome = evaluate_election_call(state, requesting_kingdom_ids=set(), current_turn=5)

    assert outcome.immediate_coronation_kingdom_id == 1
    assert outcome.callers_qualify is False
    assert outcome.alignment_trigger is None
    assert outcome.election_scheduled_next_turn is False


def test_evaluate_election_call_callers_trigger_next_turns_election():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 30)
    give_tax(state, 2, HexCoord(1, 1), 30)
    give_tax(state, 3, HexCoord(2, 2), 40)

    outcome = evaluate_election_call(state, requesting_kingdom_ids={1, 2}, current_turn=5)

    assert outcome.immediate_coronation_kingdom_id is None
    assert outcome.callers_qualify is True
    assert outcome.alignment_trigger is None
    assert outcome.election_scheduled_next_turn is True


def test_evaluate_election_call_alignment_bloc_alone_triggers_next_turns_election():
    # Every individual Kingdom stays below the (turn-30-decayed) 25%
    # threshold, so nobody is crowned immediately and nobody "requested"
    # anything -- but the two GOOD Kingdoms combined (40%) clear it,
    # scheduling next turn's election through the alignment path alone.
    state = GameState()
    state.add_kingdom(KingdomState(1, "A", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "B", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_kingdom(KingdomState(3, "C", Race.HUMAN, Alignment.EVIL, HexCoord(2, 2)))
    state.add_kingdom(KingdomState(4, "D", Race.HUMAN, Alignment.PAGAN, HexCoord(3, 3)))
    state.add_kingdom(KingdomState(5, "E", Race.HUMAN, Alignment.GOOD, HexCoord(4, 4)))
    for kid, coord in [(1, HOME), (2, HexCoord(1, 1)), (3, HexCoord(2, 2)), (4, HexCoord(3, 3)), (5, HexCoord(4, 4))]:
        give_tax(state, kid, coord, 20)

    outcome = evaluate_election_call(state, requesting_kingdom_ids=set(), current_turn=30)

    assert outcome.immediate_coronation_kingdom_id is None
    assert outcome.callers_qualify is False
    assert outcome.alignment_trigger == Alignment.GOOD
    assert outcome.election_scheduled_next_turn is True


def test_evaluate_election_call_nothing_qualifies():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 30)
    give_tax(state, 2, HexCoord(1, 1), 30)
    give_tax(state, 3, HexCoord(2, 2), 40)

    outcome = evaluate_election_call(state, requesting_kingdom_ids=set(), current_turn=5)

    assert outcome.immediate_coronation_kingdom_id is None
    assert outcome.callers_qualify is False
    assert outcome.alignment_trigger is None
    assert outcome.election_scheduled_next_turn is False


def test_evaluate_election_call_no_kingdoms_is_a_safe_no_op():
    state = GameState()

    outcome = evaluate_election_call(state, requesting_kingdom_ids=set(), current_turn=5)

    assert outcome.world_total == 0
    assert outcome.immediate_coronation_kingdom_id is None
    assert outcome.election_scheduled_next_turn is False


# -- Phase 466: process_election_turn() -----------------------------------


def test_process_election_turn_immediate_coronation_updates_state():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 60)
    give_tax(state, 2, HexCoord(1, 1), 20)
    give_tax(state, 3, HexCoord(2, 2), 20)
    headers = {1: _header(), 2: _header(), 3: _header()}

    outcome = process_election_turn(state, headers, current_turn=5)

    assert isinstance(outcome, ElectionCallOutcome)
    assert outcome.immediate_coronation_kingdom_id == 1
    assert state.emperor_kingdom_id == 1
    assert state.last_emperor_vote_turn == 5
    assert state.election_pending_turn is None


def test_process_election_turn_callers_schedule_next_turns_vote():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 30)
    give_tax(state, 2, HexCoord(1, 1), 30)
    give_tax(state, 3, HexCoord(2, 2), 40)
    headers = {1: _header(VOTE_TURN_SENTINEL), 2: _header(VOTE_TURN_SENTINEL), 3: _header()}

    outcome = process_election_turn(state, headers, current_turn=5)

    assert isinstance(outcome, ElectionCallOutcome)
    assert outcome.election_scheduled_next_turn is True
    assert state.election_pending_turn == 6
    assert state.emperor_kingdom_id is None


def test_process_election_turn_tallies_a_pending_votes_own_ballots():
    state = make_state()
    state.election_pending_turn = 6
    give_tax(state, 1, HexCoord(0, 0), 60)
    give_tax(state, 2, HexCoord(1, 1), 40)
    headers = {1: _header(kprevgold=1), 2: _header(kprevgold=1)}  # both vote for Kingdom 1

    result = process_election_turn(state, headers, current_turn=6)

    assert isinstance(result, ElectionResult)
    assert result.elected_emperor_kingdom_id == 1
    assert state.emperor_kingdom_id == 1
    assert state.election_pending_turn is None


def test_process_election_turn_treats_an_invalid_candidate_as_abstention():
    state = make_state()
    state.election_pending_turn = 6
    give_tax(state, 1, HexCoord(0, 0), 30)
    give_tax(state, 2, HexCoord(1, 1), 30)
    give_tax(state, 3, HexCoord(2, 2), 40)
    # Kingdom 1's own "candidate" (999) isn't a real Kingdom id -> abstains.
    headers = {1: _header(kprevgold=999), 2: _header(kprevgold=1), 3: _header(kprevgold=1)}

    result = process_election_turn(state, headers, current_turn=6)

    assert result.votes_by_candidate == {1: 70}  # only Kingdoms 2 (30) + 3 (40) counted
    assert result.elected_emperor_kingdom_id == 1  # 70/100 > 50%
    assert state.election_pending_turn is None
