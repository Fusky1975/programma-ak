from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import patch

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader, SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.orchestrator import process_turn as _process_turn_unfiltered
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.combat import Quality
from ak_engine.turn.emperor_election import ElectionCallOutcome

from _helpers import ScriptedRandom

BOARD_WIDTH = 10


def process_turn(*args, **kwargs):
    """Phase 756: neutralizes the automatic per-turn Valhalla visit's own
    real RNG consumption for this file's own orchestration-focused tests
    (office holders, elections, standings, missed deadlines -- none of
    them about Valhalla) -- same rationale/technique as `tests/test_turn_
    processor.py`'s own identical wrapper."""

    with patch("ak_engine.turn.turn_processor.finalize_ordinary_valhalla_visit", return_value=None):
        return _process_turn_unfiltered(*args, **kwargs)


def _wait_leader(leader_id: int, name: str) -> Leader:
    phase = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    return Leader(leader_id, name, ActionPlan(leader_id, [PlanSegment(0, 0, (), {"P0": phase})]))


def _practice_leader(leader_id: int, name: str, ability: Ability) -> Leader:
    phase = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=ability.value, extra=[0])
    return Leader(leader_id, name, ActionPlan(leader_id, [PlanSegment(0, 0, (), {"P0": phase})]))


def _kingdom(kingdom_number: int, king_name: str, leaders: list[Leader]) -> Kingdom:
    # Phase 574: kingdom.kingdom_id (what orchestrator.py/kingdom_bridge.py
    # actually key off now) is derived from source_filename's own trailing
    # .K<N> suffix, not header.kingdom_number -- so this fixture's filename
    # must carry the intended kingdom_number to keep them in sync. (The
    # `parse_k1_moves_file` mock returns this fixed Kingdom object
    # regardless of which Path each test passes to process_turn(), so
    # this filename -- not that Path -- is what actually determines
    # kingdom_id in every test in this file.)
    return Kingdom(
        source_filename=f"fake.K{kingdom_number}",
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
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0], choice_indices=[0]))

    # kingdom_bridge's own real, authoritative King-identification sync ran:
    # Arthur (name-matched to kingdom.king_name) stays is_king=True, Cedric
    # -- not the identified King in this file's own data -- gets corrected
    # to False even though the test fixture started him as True.
    assert state.leaders[10].kingdom_id == 1
    assert state.leaders[10].is_king is True
    assert state.leaders[20].is_king is False

    assert {r.leader_id for r in outcome.results} == {10, 20}
    assert isinstance(outcome.letter_reports[1], list)
    assert outcome.bridge_reports[1].not_found_leader_ids == []


def test_process_turn_report_has_the_original_programs_title_page_and_closing():
    state = _base_state()
    state.kingdoms[1].treasury = 1000
    state.leaders[20].skills = SkillTable(raw_values=[0] * 31)
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _practice_leader(20, "Cedric", Ability.MELEE)])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=random.Random(1))

    report = outcome.letter_reports[1]
    assert "ADVENTURER-KINGS:" in report[2]
    assert "  Quote of the Week:" in report
    assert "ACTION REPORT" in report
    assert "Here's what happened to Your Majesty this turn:" in report
    assert "LETTER REPORTS" in report
    assert any(line.startswith("From: ") and "Cedric" in line for line in report)
    assert "  Honored Sovereign, " in report
    assert any(line.startswith("  Thy humble servant,   ") for line in report)


def test_process_turn_narrates_a_real_practice_order():
    # 2026-11-20 bug fix, user-confirmed (live AK0 playtest): this is the
    # one real production compose_letter_report() call every played
    # turn goes through -- without ability_names, describe_turn_
    # results()'s own ActionCode.PRACTICE branch can never resolve an
    # ability_name and silently `continue`s past every single Practice
    # order, no matter the outcome. With both skill and aptitude at 0,
    # a solo Practice attempt's very first try always lands on "practiced
    # in vain" (the credit threshold needs many attempts to cross), a
    # deterministic outcome regardless of the real, unscripted RNG draws
    # below -- this test only needs to confirm the line exists at all,
    # and that it names the real practiced ability.
    state = _base_state()
    state.kingdoms[1].treasury = 1000  # avoid Cedric's own desertion/standby roll entirely -- unrelated to this test
    state.leaders[20].skills = SkillTable(raw_values=[0] * 31)
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _practice_leader(20, "Cedric", Ability.MELEE)])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=random.Random(1))

    report_text = "\n".join(outcome.letter_reports[1])
    assert "Cedric" in report_text and "Melee" in report_text and "practiced" in report_text


# -- Phase 676: commit_office_holders()/commit_army_office_holders() are
# now wired into process_turn(), right after the election/final-standings
# step -- see turn/office_holder.py's own extensively-tested suite for the
# stickiness tie-break logic itself; these two only prove the real call
# site actually fires.


def test_process_turn_commits_office_holders_for_the_next_turns_tie_break():
    state = _base_state()
    state.leaders[10].merit_tally.monster_hp_defeated = 10  # clears Office.DEFENDER's own OFFICE_MIN_POINTS
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0], choice_indices=[0]))

    assert state.office_holders[Office.DEFENDER] == 10


def test_process_turn_commits_army_office_holders_for_the_next_turns_tie_break():
    # No province is registered at the army's own location deliberately --
    # _base_state()'s own Kings (Arthur/Cedric) have no Druidic skill, and
    # a real province there would trigger rulebook [4.32]'s own Druidic-
    # shortfall penalty (king_druidic_shortfall_for(), only reachable when
    # a real, owned province exists) against this monstrous army type,
    # degrading it below the Crack/Elite eligibility floor -- an unrelated
    # mechanic this test isn't exercising (the same pitfall Phase 633/641
    # already documented and hit).
    state = _base_state()
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, HexCoord(0, 0)))
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0], choice_indices=[0]))

    assert state.army_office_holders[Office.AIR_FORCE] == 101


def test_process_turn_wires_record_kingdom_contacts_for_diplomacy_visibility():
    # Phase 872: turn/world_events.py record_kingdom_contacts() was
    # never wired into process_turn() at all -- GameState.kingdoms_met/
    # kingdoms_met_since stayed permanently empty in every real game,
    # silently starving World Emperor/Imperial Treasurer's own perks and
    # the DIPLOMACY report's alignment sentence (report/turn_report.py
    # describe_diplomacy_report()), all fed by this same state.
    state = _base_state()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.EVIL, HexCoord(1, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HexCoord(1, 0), Terrain.PLAINS, Race.ELVEN, owner_kingdom_id=2))
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        # Two kingdoms now have real financial state to process (unlike
        # every other test in this file, all single-kingdom) -- a real
        # rng.Random consumes freely instead of exhausting a short
        # ScriptedRandom script; this test only checks kingdoms_met
        # population, not any specific RNG-driven value.
        process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=random.Random(0))

    assert frozenset({1, 2}) in state.kingdoms_met
    assert frozenset({1, 2}) in state.kingdoms_met_since


def test_process_turn_skips_a_leader_with_no_matching_leaderstate():
    state = _base_state()
    kingdom = _kingdom(
        1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric"), _wait_leader(99, "Ghost")]
    )

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0], choice_indices=[0]))

    assert outcome.bridge_reports[1].not_found_leader_ids == [99]
    assert 99 not in {r.leader_id for r in outcome.results}


def test_process_turn_combines_multiple_kingdoms_orders_into_one_run_turn_call():
    state = _base_state()
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 0)))
    state.add_leader(LeaderState(30, kingdom_id=2, name="Baldric", location=HexCoord(1, 0), is_king=True))

    kingdom_a = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])
    kingdom_b = _kingdom(2, "Baldric", [_wait_leader(30, "Baldric")])

    # Phase 574: kingdom_id now comes from the file's own name (a.K1 -> 1,
    # b.K2 -> 2), not header.kingdom_number -- the path's own suffix must
    # match each fixture's intended kingdom_id.
    with patch("ak_engine.orchestrator.parse_k1_moves_file", side_effect=[kingdom_a, kingdom_b]):
        outcome = process_turn(
            state, [Path("a.K1"), Path("b.K2")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0], choice_indices=[0])
        )

    assert {r.leader_id for r in outcome.results} == {10, 20, 30}
    assert set(outcome.bridge_reports) == {1, 2}
    # Phase 608: every real Kingdom in state.kingdoms gets its own real
    # letter_reports entry, not one combined narrative -- and each is a
    # distinct list object, not the same one duplicated.
    assert set(outcome.letter_reports) == {1, 2}
    assert outcome.letter_reports[1] is not outcome.letter_reports[2]
    # STATE OF THE NATION is always present (describe_state_of_the_nation_
    # report()'s own docstring), unlike ACTION REPORT which is empty here
    # since WAIT produces no narratable content.
    assert "STATE OF THE NATION:" in outcome.letter_reports[1]
    assert "STATE OF THE NATION:" in outcome.letter_reports[2]


def test_process_turn_bridges_a_real_mutual_treat_order_into_a_real_alliance():
    # 2026-11-20 bug fix, user-confirmed via a live playtest ("Ho fatto
    # fare un Treat a tutti e due i Re della partita. Sarebbero dovuti
    # diventare alleati, ma non è successo nulla. Non c'è traccia di
    # questo nel report e lì c'è ancora scritto tra i regni c'è
    # neutralità."): each King's own real header.allreq bit was already
    # correctly decoded (models/kingdom.py) but never bridged into
    # state.treat_permissions, so apply_treat_orders() -- called from
    # inside run_turn() -- always saw an empty set and the Treat order
    # silently did nothing.
    state = _base_state()
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 0)))
    state.add_leader(LeaderState(30, kingdom_id=2, name="Baldric", location=HexCoord(1, 0), is_king=True))

    def _treating_kingdom(kingdom_number: int, king_name: str, leaders: list[Leader], allreq: int) -> Kingdom:
        return Kingdom(
            source_filename=f"fake.K{kingdom_number}",
            king_name=king_name,
            king_title=None,
            header=KingdomMoveHeader(raw_fields=[kingdom_number, allreq, 0, 101, 1, 15, 1]),
            skills=SkillTable(raw_values=[0] * 31),
            leaders=leaders,
        )

    kingdom_a = _treating_kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")], allreq=1 << 2)
    kingdom_b = _treating_kingdom(2, "Baldric", [_wait_leader(30, "Baldric")], allreq=1 << 1)

    with patch("ak_engine.orchestrator.parse_k1_moves_file", side_effect=[kingdom_a, kingdom_b]):
        process_turn(
            state, [Path("a.K1"), Path("b.K2")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0], choice_indices=[0])
        )

    # [8.2]'s own "alla fine del turno" timing: not yet visible to this
    # turn's own DIPLOMACY section or combat.
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert state.pending_treat_transitions[frozenset({1, 2})] == (
        DiplomaticRelation.NEUTRAL,
        DiplomaticRelation.ALLIED,
    )

    with patch("ak_engine.orchestrator.parse_k1_moves_file", side_effect=[kingdom_a, kingdom_b]):
        outcome = process_turn(
            state, [Path("a.K1"), Path("b.K2")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0], choice_indices=[0])
        )

    assert state.is_allied(1, 2)
    # DIPLOMACY's own "wisely allied" list now really names the other
    # King -- not just an internal is_allied() flip with no report trace.
    assert "  Baldric (#2)" in outcome.letter_reports[1]


def test_process_turn_resolves_a_queued_guild_assassination_after_battles():
    # Phase 614: state.pending_guild_target set here stands in for a real
    # turn/plan_dispatch.py _dispatch_fire() interception (covered in
    # isolation in test_plan_dispatch.py) -- this test's own job is only
    # to prove process_turn() actually calls resolve_pending_guild_
    # assassination() once after run_turn() and threads its outcome into
    # the right Kingdom's own letter_reports entry.
    state = _base_state()
    state.leaders[10].merit_tally.successful_assassinations = 2  # Arthur holds Office.ASSASSIN
    state.pending_guild_target = 20  # Cedric queued
    kingdom = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom):
        outcome = process_turn(
            state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0] * 20, choice_indices=[0] * 20)
        )

    assert state.pending_guild_target is None
    guild_results = [r for r in outcome.results if r.phase_label == "guild-assassination"]
    assert len(guild_results) == 1
    assert guild_results[0].leader_id == 20
    assert 20 not in state.leaders
    letter = outcome.letter_reports[1]
    assert any("stroll" in line or "assassin" in line for line in letter)


def test_process_turn_auto_fills_a_missed_deadline_kingdom_with_the_real_defend_wait_plan():
    # Phase 574: Defendia (kingdom 2) submits no order file this turn --
    # process_turn() now merges turn/turn_processor.py
    # build_missed_deadline_turn_leaders()'s own real REPORTS.PAS
    # Set_Defend auto-fill for it into the same run_turn() dispatch,
    # instead of silently leaving it out of the turn entirely.
    state = _base_state()
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 0)))
    state.add_leader(LeaderState(30, kingdom_id=2, name="Baldric", location=HexCoord(1, 0), is_king=True))

    kingdom_a = _kingdom(1, "Arthur", [_wait_leader(10, "Arthur"), _wait_leader(20, "Cedric")])

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=kingdom_a):
        outcome = process_turn(state, [Path("a.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0], choice_indices=[0]))

    # Baldric (kingdom 2's own King, no armies) got dispatched even though
    # his own kingdom submitted no order file this turn.
    assert 30 in {r.leader_id for r in outcome.results}
    # No order file ever arrived for kingdom 2, so it never got a real
    # bridge sync -- unchanged, pre-existing behavior this phase doesn't
    # touch.
    assert 2 not in outcome.bridge_reports
    # Phase 608: kingdom 2 still gets its own real letter, though -- every
    # Kingdom in state.kingdoms does, missed deadline or not, since it
    # still has a real LeaderState/PhaseDispatchResult after the auto-fill.
    assert set(outcome.letter_reports) == {1, 2}


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
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0], choice_indices=[0]))

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
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0], choice_indices=[0]))

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
        outcome = process_turn(state, [Path("fake.K1")], board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0], choice_indices=[0]))

    assert outcome.final_standings is not None
    assert outcome.final_standings.standings == (1,)
