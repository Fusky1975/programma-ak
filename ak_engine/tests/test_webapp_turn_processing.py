"""Tests for webapp/turn_processing.py -- the upload/process turn cycle
(Phase 7 of the GM interface)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.parser.xk_world import parse_xk_world
from ak_engine.turn.plan_dispatch import PhaseDispatchResult
from ak_engine.webapp.turn_processing import (
    InvalidMoveFileError,
    format_turn_processing_log,
    load_turn_processing_log,
    load_turn_report,
    load_turn_xk_file,
    process_and_save_current_turn,
    processed_turn_numbers,
    remove_uploaded_move_file,
    save_turn_processing_log,
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
    assert uploaded_move_files(tmp_path, 1, {1}) == {}


def test_save_uploaded_move_file_makes_it_listable_by_its_real_kingdom_id(tmp_path):
    kingdom_id = save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", _REAL_MOVE_FILE, {1})

    assert kingdom_id == 1
    files = uploaded_move_files(tmp_path, 1, {1})
    assert list(files.keys()) == [1]
    assert files[1].name == "AK3__T1.K1"


def test_save_uploaded_move_file_with_garbage_content_raises_and_cleans_up(tmp_path):
    with pytest.raises(InvalidMoveFileError):
        save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", b"not a real move file at all", {1})

    assert uploaded_move_files(tmp_path, 1, {1}) == {}


def test_save_uploaded_move_file_with_no_k_suffix_raises(tmp_path):
    with pytest.raises(InvalidMoveFileError):
        save_uploaded_move_file(tmp_path, 1, "not_a_move_file.txt", _REAL_MOVE_FILE, {1})


def test_save_uploaded_move_file_for_a_kingdom_not_in_this_game_raises_and_cleans_up(tmp_path):
    # A copy of a real sample renamed to an unrelated .K99 suffix parses
    # cleanly on its own -- only the valid_kingdom_ids check catches it.
    # Without this, process_turn()'s own sync_leaders_from_kingdom() would
    # trust the stray number and reassign a real leader's kingdom_id to
    # a Kingdom that doesn't exist in this game.
    with pytest.raises(InvalidMoveFileError):
        save_uploaded_move_file(tmp_path, 1, "AK3__T1.K99", _REAL_MOVE_FILE, {1, 2})


def test_save_uploaded_move_file_rejects_a_path_traversal_filename(tmp_path):
    # Bug fix: `filename` is the raw, client-supplied multipart upload
    # name -- unsanitized, this used to write straight through pathlib's
    # `/` join, landing outside the uploads directory entirely whenever
    # the name contained ".." components. secure_filename() strips the
    # traversal, so the upload still succeeds (its own content is a
    # real move file), but lands safely inside the real uploads
    # directory -- never at the escaped, outside path.
    outside = tmp_path / "outside.K1"

    kingdom_id = save_uploaded_move_file(tmp_path, 1, "../outside.K1", _REAL_MOVE_FILE, {1})

    assert kingdom_id == 1
    assert not outside.exists()
    files = uploaded_move_files(tmp_path, 1, {1})
    assert files[1].parent == tmp_path / "moves" / "turn_1"


def test_save_uploaded_move_file_rejects_a_filename_that_sanitizes_to_nothing(tmp_path):
    with pytest.raises(InvalidMoveFileError):
        save_uploaded_move_file(tmp_path, 1, "..", _REAL_MOVE_FILE, {1})

    assert uploaded_move_files(tmp_path, 1, {1, 2, 99}) == {}


def test_save_uploaded_move_file_removes_a_stale_upload_under_a_different_filename(tmp_path):
    # Bug fix: a GM resubmitting a corrected move file keeps the
    # filename their player exported -- not something the GM controls
    # -- so a resubmission can easily land under a different filename
    # than the first upload. This used to leave BOTH files on disk for
    # the same kingdom_id, and uploaded_move_files()'s own sorted-
    # iterdir dict build would then pick whichever name sorts
    # alphabetically last, not the actually-most-recent upload.
    save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", _REAL_MOVE_FILE, {1})

    save_uploaded_move_file(tmp_path, 1, "ZZZ_resubmit.K1", _REAL_MOVE_FILE, {1})

    directory = tmp_path / "moves" / "turn_1"
    assert [p.name for p in directory.iterdir()] == ["ZZZ_resubmit.K1"]
    files = uploaded_move_files(tmp_path, 1, {1})
    assert files[1].name == "ZZZ_resubmit.K1"


def test_remove_uploaded_move_file_removes_it(tmp_path):
    save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", _REAL_MOVE_FILE, {1})

    remove_uploaded_move_file(tmp_path, 1, 1, {1})

    assert uploaded_move_files(tmp_path, 1, {1}) == {}


def test_uploaded_move_files_are_scoped_per_turn_number(tmp_path):
    save_uploaded_move_file(tmp_path, 1, "AK3__T1.K1", _REAL_MOVE_FILE, {1})

    assert uploaded_move_files(tmp_path, 2, {1}) == {}


def test_uploaded_move_files_filters_out_a_kingdom_not_in_this_game(tmp_path):
    # Simulates a file that reached disk some other way (e.g. a GM editing
    # the folder directly) rather than through save_uploaded_move_file()'s
    # own guard -- the listing itself must still never surface it.
    moves_dir = tmp_path / "moves" / "turn_1"
    moves_dir.mkdir(parents=True)
    (moves_dir / "AK3__T1.K99").write_bytes(_REAL_MOVE_FILE)

    assert uploaded_move_files(tmp_path, 1, {1, 2}) == {}


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


def test_process_and_save_current_turn_also_saves_real_xk_files(tmp_path):
    # Phase 1026: the real binary counterpart to the text letter, saved
    # the same way and at the same point, since an older turn's own
    # GameState isn't kept around once a later turn has been processed.
    from ak_engine.webapp.games import create_game, game_dir, open_game

    meta = create_game(tmp_path, "XK Campaign")
    _, state = open_game(tmp_path, meta.slug)
    generated = _generated_state()
    state.kingdoms = generated.kingdoms
    state.leaders = generated.leaders
    state.provinces = generated.provinces
    state.armies = generated.armies
    state.features = generated.features
    state.board_width = generated.board_width
    state.board_height = generated.board_height

    process_and_save_current_turn(tmp_path, meta.slug, state, game_dir(tmp_path, meta.slug))

    data = load_turn_xk_file(game_dir(tmp_path, meta.slug), 1, 1)
    assert data is not None
    import pathlib
    import tempfile

    path = pathlib.Path(tempfile.mktemp())
    try:
        path.write_bytes(data)
        world = parse_xk_world(path)
    finally:
        path.unlink(missing_ok=True)
    assert world.header.kingdom_id == 1


def test_process_and_save_current_turn_survives_an_out_of_range_account_number(tmp_path):
    # Bug fix: KingdomState.account_number has no range check in the GM
    # web editor (kingdom_status_save, app.py), but write_xk_world()
    # writes it with struct.pack("<h", ...) -- out of -32768..32767
    # raises struct.error, not ValueError, which save_turn_xk_files()
    # used to let through uncaught, crashing process_and_save_current_
    # turn() *before* save_game() ran and leaving state.pkl stale
    # against the turn reports already written for this same turn.
    from ak_engine.webapp.games import create_game, game_dir, open_game

    meta = create_game(tmp_path, "Out Of Range Campaign")
    _, state = open_game(tmp_path, meta.slug)
    generated = _generated_state()
    state.kingdoms = generated.kingdoms
    state.leaders = generated.leaders
    state.provinces = generated.provinces
    state.armies = generated.armies
    state.features = generated.features
    state.board_width = generated.board_width
    state.board_height = generated.board_height
    state.kingdoms[1].account_number = 999999  # past a signed 16-bit field's own range

    process_and_save_current_turn(tmp_path, meta.slug, state, game_dir(tmp_path, meta.slug))

    # Kingdom 1's own .xk file is skipped (the same honest "can't encode
    # this Kingdom" convention XKExportError already used), but the turn
    # still advances and the state still saves -- no uncaught crash, no
    # stale state.pkl.
    assert load_turn_xk_file(game_dir(tmp_path, meta.slug), 1, 1) is None
    _, reloaded = open_game(tmp_path, meta.slug)
    assert reloaded.turn_number == 2


def test_load_turn_xk_file_missing_returns_none(tmp_path):
    assert load_turn_xk_file(tmp_path, 1, 1) is None


def test_load_turn_report_missing_returns_none(tmp_path):
    assert load_turn_report(tmp_path, 1, 1) is None


def test_processed_turn_numbers_on_a_fresh_dir_is_empty(tmp_path):
    assert processed_turn_numbers(tmp_path) == []


def test_format_turn_processing_log_with_no_results_says_so():
    state = _generated_state()
    lines = format_turn_processing_log([], state)
    assert any("No orders were dispatched" in line for line in lines)


def test_format_turn_processing_log_reports_ok_and_error_lines():
    state = _generated_state()
    leader_id = next(iter(state.leaders))
    results = [
        PhaseDispatchResult(
            leader_id=leader_id, segment_index=0, phase_label="P0", action=ActionCode.LMOVE, result=None, error=None
        ),
        PhaseDispatchResult(
            leader_id=leader_id,
            segment_index=1,
            phase_label="P1",
            action=ActionCode.CHALLENGE,
            result=None,
            error=ValueError("no target"),
        ),
    ]

    lines = format_turn_processing_log(results, state)

    ok_line = next(line for line in lines if "LMOVE" in line)
    assert ok_line.endswith(": OK")
    error_line = next(line for line in lines if "CHALLENGE" in line)
    assert "ERROR: no target" in error_line


def test_format_turn_processing_log_falls_back_to_dead_leaders():
    state = _generated_state()
    leader_id = next(iter(state.leaders))
    leader = state.leaders[leader_id]
    state.remove_leader(leader_id)
    assert leader_id in state.dead_leaders

    results = [
        PhaseDispatchResult(leader_id=leader_id, segment_index=0, phase_label="P0", action=ActionCode.LMOVE, result=None, error=None)
    ]

    lines = format_turn_processing_log(results, state)

    assert any(leader.name in line for line in lines)


def test_save_and_load_turn_processing_log_round_trips(tmp_path):
    state = _generated_state()
    leader_id = next(iter(state.leaders))
    results = [
        PhaseDispatchResult(leader_id=leader_id, segment_index=0, phase_label="P0", action=ActionCode.LMOVE, result=None, error=None)
    ]

    save_turn_processing_log(tmp_path, 1, results, state)
    lines = load_turn_processing_log(tmp_path, 1)

    assert lines is not None
    assert any("LMOVE" in line for line in lines)


def test_load_turn_processing_log_missing_returns_none(tmp_path):
    assert load_turn_processing_log(tmp_path, 1) is None


def test_process_and_save_current_turn_also_saves_a_processing_log(tmp_path):
    from ak_engine.webapp.games import create_game, game_dir, open_game

    meta = create_game(tmp_path, "Processing Log Campaign")
    _, state = open_game(tmp_path, meta.slug)
    generated = _generated_state()
    state.kingdoms = generated.kingdoms
    state.leaders = generated.leaders
    state.provinces = generated.provinces
    state.armies = generated.armies
    state.features = generated.features
    state.board_width = generated.board_width
    state.board_height = generated.board_height

    process_and_save_current_turn(tmp_path, meta.slug, state, game_dir(tmp_path, meta.slug))

    lines = load_turn_processing_log(game_dir(tmp_path, meta.slug), 1)
    assert lines is not None


def test_the_processing_log_says_why_a_cast_had_no_effect():
    from ak_engine.models.enums import Spell
    from ak_engine.turn.cast_decode import CastRequest
    from ak_engine.turn.cast_execution import CastExecutionResult

    state = _generated_state()
    leader_id = next(iter(state.leaders))
    request = CastRequest(spell=Spell.CHARM, target=59)
    results = [
        PhaseDispatchResult(leader_id, 0, "P2", ActionCode.CAST, CastExecutionResult(request, applied=True), None),
        PhaseDispatchResult(
            leader_id, 0, "P3", ActionCode.CAST, CastExecutionResult(request, applied=False, reason="not co-located"), None
        ),
        PhaseDispatchResult(
            leader_id, 0, "P4", ActionCode.CAST, CastExecutionResult(request, applied=False, reason="spell failed"), None
        ),
    ]

    lines = format_turn_processing_log(results, state)

    applied = next(line for line in lines if "/ P2 /" in line)
    not_there = next(line for line in lines if "/ P3 /" in line)
    fizzled = next(line for line in lines if "/ P4 /" in line)
    assert applied.endswith(": OK")
    assert not_there.endswith(": OK (had no effect -- CHARM on #59: not co-located)")
    assert fizzled.endswith(": OK (had no effect -- CHARM on #59: spell failed)")


def test_the_processing_log_shows_the_chance_and_the_dice_of_a_cast():
    from ak_engine.models.enums import Spell
    from ak_engine.turn.cast_decode import CastRequest
    from ak_engine.turn.cast_execution import CastExecutionResult, CastRoll

    state = _generated_state()
    leader_id = next(iter(state.leaders))
    request = CastRequest(spell=Spell.CHARM, target=59)
    results = [
        PhaseDispatchResult(
            leader_id, 0, "P2", ActionCode.CAST,
            CastExecutionResult(request, applied=False, reason="spell failed", cast_roll=CastRoll(0.6, 0.78)), None,
        ),
        PhaseDispatchResult(
            leader_id, 0, "P3", ActionCode.CAST,
            CastExecutionResult(request, applied=True, cast_roll=CastRoll(0.6, 0.41)), None,
        ),
    ]

    lines = format_turn_processing_log(results, state)

    failed = next(line for line in lines if "/ P2 /" in line)
    worked = next(line for line in lines if "/ P3 /" in line)
    assert failed.endswith(": OK (had no effect -- CHARM on #59: spell failed prob. 60% rolled 78)")
    assert worked.endswith(": OK (CHARM on #59: prob. 60% rolled 41)")


def test_the_gm_log_shows_the_alignment_an_undead_kings_charm_bent():
    from ak_engine.models.alignment import Alignment
    from ak_engine.models.enums import Spell
    from ak_engine.turn.cast_decode import CastRequest
    from ak_engine.turn.cast_execution import CastExecutionResult, CastRoll
    from ak_engine.webapp.turn_processing import _order_outcome_note

    result = CastExecutionResult(
        CastRequest(spell=Spell.CHARM, target=61), applied=True, cast_roll=CastRoll(0.6, 0.08),
        alignment_changed=(Alignment.EVIL, Alignment.UNDEAD),
    )

    assert _order_outcome_note(result) == " (CHARM on #61: prob. 60% rolled 8; alignment Evil -> Undead)"
