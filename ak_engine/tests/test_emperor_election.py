"""Tests for turn/emperor_election.py -- see its module docstring for
the full rulebook [10.2] derivation this exercises.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.emperor_election import (
    ELECTION_REQUEST_THRESHOLD_PERCENT,
    _kingdom_office_vote_points,
    _kingdom_treasure_vote_points,
    alignment_victory_point_reduction_percent,
    can_request_election,
    election_threshold_percent,
    kingdom_election_vote_weight,
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
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 60)
    give_tax(state, 2, HexCoord(1, 1), 20)
    give_tax(state, 3, HexCoord(2, 2), 20)
    ballots = {1: 1, 2: 1, 3: 2}  # kingdom 1 gets 60+20=80 votes, kingdom 2 gets 20

    result = tally_emperor_vote(state, ballots)

    assert result.elected_emperor_kingdom_id == 1
    assert result.votes_by_candidate == {1: 80, 2: 20}
    assert result.total_votes_cast == 100


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

    result = tally_emperor_vote(state, ballots)

    assert result.votes_by_candidate == {2: 25, 3: 24}


def test_tally_emperor_vote_no_quorum_elects_nobody():
    state = make_state()
    give_tax(state, 1, HexCoord(0, 0), 50)
    give_tax(state, 2, HexCoord(1, 1), 50)
    ballots = {1: 1, 2: 2}

    result = tally_emperor_vote(state, ballots)

    assert result.elected_emperor_kingdom_id is None


def test_tally_emperor_vote_no_ballots_elects_nobody():
    state = make_state()

    result = tally_emperor_vote(state, {})

    assert result.elected_emperor_kingdom_id is None
    assert result.total_votes_cast == 0


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


def test_alignment_reduction_none_for_alignments_the_table_doesnt_cover():
    assert alignment_victory_point_reduction_percent(Alignment.ANTI_HOLY, Alignment.GOOD) is None
    assert alignment_victory_point_reduction_percent(Alignment.MECHANICAL, Alignment.GOOD) is None
    assert alignment_victory_point_reduction_percent(Alignment.SPECIAL, Alignment.GOOD) is None
