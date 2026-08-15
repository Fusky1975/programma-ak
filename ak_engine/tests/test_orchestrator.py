from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader, SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.orchestrator import process_turn
from ak_engine.turn.emperor_election import ElectionCallOutcome

from _helpers import ScriptedRandom

BOARD_WIDTH = 10


def _wait_leader(leader_id: int, name: str) -> Leader:
    phase = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    return Leader(leader_id, name, ActionPlan(leader_id, [PlanSegment(0, 0, (), {"P0": phase})]))


def _kingdom(kingdom_number: int, king_name: str, leaders: list[Leader]) -> Kingdom:
    return Kingdom(
        source_filename="fake.K1",
        king_name=king_name,
        king_title=None,
        header=KingdomMoveHeader(raw_fields=[kingdom_number, 1, 0, 101, 1, 15, 1]),
        skills=SkillTable(raw_values=[0] * 31),
        leaders=leaders,
    )


def _base_state() -> GameState:
    # Cedric starts is_king=True here but kingdom_bridge's own real King-
    # identification sync (see test_process_turn_syncs_bridges_dispatches_
    # and_narrates's own comment) corrects him to False once process_turn()
    # runs -- from that point on he's a real, kingdom_id=1 Hero. With this
    # kingdom's own zero-default treasury, turn/expenses.py's Phase 527
    # desertion/standby mechanic now rolls once for him at every run_turn()
    # call below, hence every `ScriptedRandom([], choice_indices=[0])` in
    # this file's own process_turn() calls (index 0 is an arbitrary,
    # deterministic pick -- no test here asserts Cedric's own post-turn
    # desertion outcome, only the orchestration wiring these tests exist
    # to cover).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Arthur", location=HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Cedric", location=HexCoord(0, 0), is_king=True))
    return state


def test_process_turn_syncs_bridges_dispatches_and_narrates():
    state = _base_state()
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([], choice_indices=[0]))

    # kingdom_bridge's own real, authoritative King-identification sync ran:
    # Arthur (name-matched to kingdom.king_name) stays is_king=True, Cedric
    # -- not the identified King in this file's own data -- gets corrected
    # to False even though the test fixture started him as True.
    assert state.leaders[10].kingdom_id == 1
    assert state.leaders[10].is_king is True
    assert state.leaders[20].is_king is False

    assert {r.leader_id for r in outcome.results} == {10, 20}
    assert isinstance(outcome.report_lines, list)
    assert outcome.bridge_reports[1].not_found_leader_ids == []


def test_process_turn_skips_a_leader_with_no_matching_leaderstate():
    state = _base_state()
    kingdom = _kingdom(
        1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric"), _wait_leader(99, "Ghost")]
    )

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([], choice_indices=[0]))

    assert outcome.bridge_reports[1].not_found_leader_ids == [99]
    assert 99 not in {r.leader_id for r in outcome.results}


def test_process_turn_combines_multiple_kingdoms_orders_into_one_run_turn_call():
    state = _base_state()
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 0)))
    state.add_leader(LeaderState(30, kingdom_id=2, name="Baldric", location=HexCoord(1, 0), is_king=True))

    kingdom_a = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])
    kingdom_b = _kingdom(2, "Baldric", [_wait_leader(30, "Baldric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", side_effect=[kingdom_a, kingdom_b]):
        outcome = process_turn(
            state, [Path("a.K1"), Path("b.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([], choice_indices=[0])
        )

    assert {r.leader_id for r in outcome.results} == {10, 20, 30}
    assert set(outcome.bridge_reports) == {1, 2}


def test_process_turn_wires_the_emperor_election_evaluation():
    # Phase 466: process_turn() now runs turn/emperor_election.py
    # process_election_turn() every turn, in the report's own SS13.1
    # sequence (after the five phases, before report generation). No
    # Kingdom here owns any taxed province, so V_world is 0 and nothing
    # gets crowned/scheduled -- this just proves the wiring itself runs
    # and surfaces its result on TurnOutcome, without needing a full
    # tax-base scenario (already covered at the unit level in
    # test_emperor_election.py).
    state = _base_state()
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([], choice_indices=[0]))

    assert isinstance(outcome.election_outcome, ElectionCallOutcome)
    assert outcome.election_outcome.world_total == 0
    assert state.emperor_kingdom_id is None
    assert state.election_pending_turn is None


def test_process_turn_final_standings_is_none_before_any_emperor_exists():
    # Phase 476: the ordinary case -- no Emperor yet in this fixture (see
    # test_process_turn_wires_the_emperor_election_evaluation above), so
    # compose_final_standings_report() has nothing to report.
    state = _base_state()
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([], choice_indices=[0]))

    assert outcome.final_standings is None


def test_process_turn_wires_final_standings_once_an_emperor_exists():
    # Phase 476: SS14.1 -- coronation and the first "unified world"
    # standings land in the same post-turn. Pre-seed an Emperor (as if
    # crowned on an earlier turn) and confirm process_turn() surfaces the
    # real snapshot, matching what calling compose_final_standings_report()
    # directly would produce.
    state = _base_state()
    state.emperor_kingdom_id = 1
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([], choice_indices=[0]))

    assert outcome.final_standings is not None
    assert outcome.final_standings.standings == (1,)
