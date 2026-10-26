"""Tests for webapp/moves_compose.py -- the GM webapp's "compose moves"
editor's own form-to-Kingdom logic. Move (``ActionCode.LMOVE``) is the
first action to get its own dedicated syntax (a province-name dropdown
instead of the raw, encoded Object field) -- see that module's own
docstring for the ``turn/plan_dispatch.py``-sourced confirmation that
Move reads only ``obj`` (never ``extra``).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.webapp.moves_compose import (
    InvalidComposedMovesError,
    build_composed_kingdom,
    parse_phase_inputs,
    province_options,
)

BOARD_WIDTH = 6
BOARD_HEIGHT = 4
HOME = HexCoord(1, 1)
KING_ID = 1


def _state() -> GameState:
    state = GameState()
    state.board_width = BOARD_WIDTH
    state.board_height = BOARD_HEIGHT
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(
        LeaderState(
            leader_id=KING_ID,
            kingdom_id=1,
            name="Aldric",
            location=HOME,
            is_king=True,
            skills=SkillTable(raw_values=[0] * 30 + [3]),
        )
    )
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.add_province(ProvinceState(HexCoord(3, 2), Terrain.FOREST, Race.HUMAN, name=None))
    return state


def _all_defend_form(leader_id: int) -> dict[str, str]:
    form = {}
    for n in range(5):
        form[f"action_{leader_id}_{n}"] = str(int(ActionCode.DEFEND))
        form[f"obj_{leader_id}_{n}"] = "0"
        form[f"extra_{leader_id}_{n}"] = ""
    return form


def test_province_options_names_a_named_province_and_falls_back_for_an_unnamed_one():
    # Bug fix, sourced directly from the user (2026-10-26): the label
    # also carries the province's own real "#<N>" order number (the
    # same x*100+y convention real reports already show, e.g. "Mongu
    # (#305)") "come nell'AK originale" -- not just name/coordinates.
    state = _state()
    options = province_options(state)
    assert ("1,1", "Numenor (1, 1) #0101") in options
    assert ("3,2", "(3, 2) #0302") in options


def test_province_options_sorted_in_map_reading_order():
    state = _state()
    options = province_options(state)
    values = [value for value, _ in options]
    assert values.index("1,1") < values.index("3,2")  # row 1 before row 2


def test_move_phase_reads_its_own_dropdown_not_the_generic_object_field():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_2"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_2"] = "3,2"
    form[f"obj_{KING_ID}_2"] = "999"  # must be ignored for a Move phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    move_phase = phases[2]
    assert move_phase.action is ActionCode.LMOVE
    assert decode_hex_number(move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)
    assert move_phase.extra == []


def test_move_phase_without_a_chosen_destination_is_rejected():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = ""

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Move destination" in str(exc)


def test_non_move_phase_is_unaffected_by_the_move_destination_field():
    form = _all_defend_form(KING_ID)
    form[f"obj_{KING_ID}_1"] = "42"
    form[f"extra_{KING_ID}_1"] = "1, 2 3"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    assert phases[1].action is ActionCode.DEFEND
    assert phases[1].obj == 42
    assert phases[1].extra == [1, 2, 3]


def test_build_composed_kingdom_round_trips_a_move_order_to_the_real_target_coord():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = "3,2"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert decode_hex_number(phase0.obj, state.board_width) == HexCoord(3, 2)
