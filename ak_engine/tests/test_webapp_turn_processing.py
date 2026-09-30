"""Tests for webapp/turn_processing.py -- the upload/process turn cycle
(Phase 7 of the GM interface)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.webapp.turn_processing import (
    InvalidMoveFileError,
    load_turn_report,
    process_and_save_current_turn,
    processed_turn_numbers,
    remove_uploaded_move_file,
    save_uploaded_move_file,
    uploaded_move_files,
)
from ak_engine.worldgen.generate_new_game import KingSetup, generate_new_game
from ak_engine.worldgen.pascal_random import PascalRandom

# The repo's own real player move-submission sample (same fixture
# test_k1_moves_parser.py's own ALL_MOVE_FILES uses), read as bytes here
# to stand in for an "uploaded" file -- real, sourced content rather
# than a hand-built guess at the grammar.
_REAL_MOVE_FILE = (Path(__file__).resolve().parents[2] / "AK3__T1.K1").read_bytes()


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


def test_uploaded_move_files_on_a_fresh_dir_is_empty(tmp_path):
    assert uploaded_move_files(tmp_path, 1) == {}


def test_save_uploaded_move_file_makes_it_listable_by_its_real_kingdom_id(tmp_path):
    kingdom_id = save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", _REAL_MOVE_FILE)

    assert kingdom_id == 1
    files = uploaded_move_files(tmp_path, 1)
    assert list(files.keys()) == [1]
    assert files[1].name == "AK3__T1.K1"


def test_save_uploaded_move_file_with_garbage_content_raises_and_cleans_up(tmp_path):
    with pytest.raises(InvalidMoveFileError):
        save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", b"not a real move file at all")

    assert uploaded_move_files(tmp_path, 1) == {}


def test_save_uploaded_move_file_with_no_k_suffix_raises(tmp_path):
    with pytest.raises(InvalidMoveFileError):
        save_uploaded_move_file(tmp_path, 1, "not_a_move_file.txt", _REAL_MOVE_FILE)


def test_remove_uploaded_move_file_removes_it(tmp_path):
    save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", _REAL_MOVE_FILE)

    remove_uploaded_move_file(tmp_path, 1, 1)

    assert uploaded_move_files(tmp_path, 1) == {}


def test_uploaded_move_files_are_scoped_per_turn_number(tmp_path):
    save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", _REAL_MOVE_FILE)

    assert uploaded_move_files(tmp_path, 2) == {}


def test_process_and_save_current_turn_advances_turn_number_and_saves_reports(tmp_path):
    from ak_engine.webapp.games import create_game, game_dir, open_game

    meta = create_game(tmp_path, "Third Campaign")
    _, state = open_game(tmp_path, meta.slug)
    generated = _generated_state()
    state.kingdoms = generated.kingdoms
    state.leaders = generated.leaders
    state.provinces = generated.provinces
    state.armies = generated.armies
    state.features = generated.features
    state.board_width = generated.board_width
    state.board_height = generated.board_height

    outcome = process_and_save_current_turn(tmp_path, meta.slug, state, game_dir(tmp_path, meta.slug))

    assert state.turn_number == 2
    assert 1 in processed_turn_numbers(game_dir(tmp_path, meta.slug))
    report = load_turn_report(game_dir(tmp_path, meta.slug), 1, 1)
    assert report == outcome.letter_reports[1]

    _, reloaded = open_game(tmp_path, meta.slug)
    assert reloaded.turn_number == 2


def test_load_turn_report_missing_returns_none(tmp_path):
    assert load_turn_report(tmp_path, 1, 1) is None


def test_processed_turn_numbers_on_a_fresh_dir_is_empty(tmp_path):
    assert processed_turn_numbers(tmp_path) == []
