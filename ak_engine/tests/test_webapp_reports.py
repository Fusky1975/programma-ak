"""Tests for webapp/reports.py -- the Turn 0 letter report (Phase 6 of
the GM interface)."""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.webapp.reports import turn_zero_report
from ak_engine.worldgen.generate_new_game import KingSetup, generate_new_game
from ak_engine.worldgen.pascal_random import PascalRandom


def _generated_state():
    state = GameState()
    for kingdom_id, race in ((1, Race.HUMAN), (2, Race.ELVEN)):
        state.add_kingdom(KingdomState(kingdom_id, f"K{kingdom_id}", race, Alignment.NEUTRAL, HexCoord(0, 0)))
        state.add_leader(
            LeaderState(kingdom_id, kingdom_id=kingdom_id, name=f"K{kingdom_id}", location=HexCoord(0, 0), is_king=True, race=race)
        )
    kings = [KingSetup(leader_id=1, race=Race.HUMAN, home_coord=None), KingSetup(leader_id=2, race=Race.ELVEN, home_coord=None)]
    generate_new_game(PascalRandom(1), state, kings, width=18, height=9)
    return state


def test_turn_zero_report_does_not_advance_the_turn_number():
    state = _generated_state()
    assert state.turn_number == 1

    turn_zero_report(state, 1)

    assert state.turn_number == 1


def test_turn_zero_report_has_no_action_report_section():
    # No orders have ever been processed -- there's nothing to report on
    # in ACTION REPORT, unlike process_turn(state, []), which runs a real
    # turn's own random events despite zero move files.
    state = _generated_state()

    lines = turn_zero_report(state, 1)

    assert "ACTION REPORT" not in lines


def test_turn_zero_report_includes_the_provinces_section():
    state = _generated_state()

    lines = turn_zero_report(state, 1)

    assert any("PROVINCES" in line for line in lines)


def test_turn_zero_report_reflects_a_world_editor_change():
    state = _generated_state()
    home = state.leaders[1].location
    state.provinces[home].name = "Edited Capital"

    lines = turn_zero_report(state, 1)

    assert any("Edited Capital" in line for line in lines)


def test_turn_zero_report_is_per_kingdom():
    state = _generated_state()

    lines_1 = turn_zero_report(state, 1)
    lines_2 = turn_zero_report(state, 2)

    assert lines_1 != lines_2
