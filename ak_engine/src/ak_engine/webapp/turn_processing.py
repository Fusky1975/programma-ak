"""Turn processing cycle (Phase 7, the plan's final phase): the GM
uploads each Kingdom's real move-submission file for the current turn --
preserving its own filename, since ``Kingdom.kingdom_id`` (``models/
kingdom.py``) is parsed from that file's own trailing ``.K<N>`` suffix,
not its content -- then a single command runs ``orchestrator.
process_turn()`` against every upload at once, producing the next turn's
own real letter reports and advancing ``state.turn_number``. The same
upload/process cycle then repeats for the following turn, reusing this
same screen, until the game ends.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Collection

from ak_engine.models.game_state import GameState
from ak_engine.orchestrator import TurnOutcome, process_turn
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.parser.xk_world_writer import write_xk_world
from ak_engine.webapp.games import save_game
from ak_engine.webapp.xk_reports import XKExportError, build_xk_worlds_for_all_kingdoms

MOVES_DIRNAME = "moves"
REPORTS_DIRNAME = "reports"


class InvalidMoveFileError(Exception):
    """Raised when an uploaded file doesn't parse as a real move file at
    all, or its own filename doesn't end in a valid ``.K<N>`` suffix."""


def turn_moves_dir(one_game_dir: Path, turn_number: int) -> Path:
    return one_game_dir / MOVES_DIRNAME / f"turn_{turn_number}"


def uploaded_move_files(
    one_game_dir: Path, turn_number: int, valid_kingdom_ids: Collection[int]
) -> dict[int, Path]:
    """``kingdom_id`` -> the uploaded move file for this turn, for every
    upload currently on disk that still parses *and* names a real Kingdom
    of this game (``valid_kingdom_ids``, normally ``state.kingdoms.keys()``).
    A replaced/stale upload that no longer parses, or a file whose own
    ``.K<N>`` suffix doesn't match any Kingdom in this game -- e.g. hand-
    edited or dropped into the folder outside the upload form -- simply
    doesn't appear, the same "never surface a bad file" guarantee
    ``save_uploaded_move_file()`` already gives the normal upload path.
    Without this check, ``process_turn()``'s own ``sync_leaders_from_
    kingdom()`` would trust the stray file's ``.K<N>`` number as a real
    Kingdom id and reassign a real leader's ``kingdom_id`` to it --
    confirmed directly: a copy of a real sample renamed to a nonexistent
    ``.K99`` parses cleanly and would silently move that leader out of
    their real Kingdom.
    """

    directory = turn_moves_dir(one_game_dir, turn_number)
    if not directory.is_dir():
        return {}
    files: dict[int, Path] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        try:
            kingdom = parse_k1_moves_file(path)
            kingdom_id = kingdom.kingdom_id
        except (K1ParseError, ValueError, IndexError):
            continue
        if kingdom_id not in valid_kingdom_ids:
            continue
        files[kingdom_id] = path
    return files


def save_uploaded_move_file(
    one_game_dir: Path, turn_number: int, filename: str, content: bytes, valid_kingdom_ids: Collection[int]
) -> int:
    """Saves one uploaded move file under its own real filename (required
    -- ``Kingdom.kingdom_id`` is parsed from it, not from content) and
    returns the Kingdom id it parsed to. Raises ``InvalidMoveFileError``,
    removing the bad file again, if it doesn't parse as a real move file
    with a valid ``.K<N>`` suffix, or if that ``.K<N>`` doesn't name any
    real Kingdom in this game (``valid_kingdom_ids``) -- see
    ``uploaded_move_files()``'s own docstring for exactly what silently
    trusting an unchecked Kingdom id would do downstream.
    """

    directory = turn_moves_dir(one_game_dir, turn_number)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_bytes(content)
    try:
        kingdom = parse_k1_moves_file(path)
        kingdom_id = kingdom.kingdom_id
    except (K1ParseError, ValueError, IndexError) as exc:
        path.unlink(missing_ok=True)
        raise InvalidMoveFileError(str(exc)) from exc
    if kingdom_id not in valid_kingdom_ids:
        path.unlink(missing_ok=True)
        raise InvalidMoveFileError(
            f"this file's own .K{kingdom_id} suffix doesn't match any Kingdom in this game"
        )
    return kingdom_id


def remove_uploaded_move_file(
    one_game_dir: Path, turn_number: int, kingdom_id: int, valid_kingdom_ids: Collection[int]
) -> None:
    for kingdom_id_on_disk, path in uploaded_move_files(one_game_dir, turn_number, valid_kingdom_ids).items():
        if kingdom_id_on_disk == kingdom_id:
            path.unlink(missing_ok=True)
            return


def turn_reports_dir(one_game_dir: Path, turn_number: int) -> Path:
    return one_game_dir / REPORTS_DIRNAME / f"turn_{turn_number}"


def save_turn_reports(one_game_dir: Path, turn_number: int, letter_reports: dict[int, list[str]]) -> None:
    directory = turn_reports_dir(one_game_dir, turn_number)
    directory.mkdir(parents=True, exist_ok=True)
    for kingdom_id, lines in letter_reports.items():
        (directory / f"{kingdom_id}.txt").write_text("\n".join(lines), encoding="utf-8")


def load_turn_report(one_game_dir: Path, turn_number: int, kingdom_id: int) -> list[str] | None:
    """``None`` if this turn was never processed, or had no saved report
    for this Kingdom (shouldn't happen for a real processed turn, but a
    caller showing a "report not found" message is safer than a crash).
    """

    path = turn_reports_dir(one_game_dir, turn_number) / f"{kingdom_id}.txt"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").splitlines()


def save_turn_xk_files(one_game_dir: Path, turn_number: int, state: GameState) -> None:
    """Phase 1026 -- the real binary counterpart to ``save_turn_reports()``
    above, saved the same way and for the same reason: a processed turn's
    own ``GameState`` isn't kept around once a *later* turn has been
    processed (``state.pkl`` holds only the current/live snapshot), so an
    older turn's own XK file can't be rebuilt on demand -- it has to be
    written now, while ``state`` still reflects this exact turn. Builds
    every Kingdom together (``build_xk_worlds_for_all_kingdoms()``) so
    each one's own shared/turn-level byte blocks can copy a sibling
    Kingdom's instead of zero-filling. A Kingdom whose own data can't be
    encoded (``XKExportError``) is simply skipped here -- the text letter
    (already saved) still exists for the GM either way.
    """

    directory = turn_reports_dir(one_game_dir, turn_number)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        worlds = build_xk_worlds_for_all_kingdoms(state)
    except XKExportError:
        return
    for kingdom_id, world in worlds.items():
        try:
            data = write_xk_world(world)
        except (ValueError, struct.error):
            # A GM-set value (e.g. KingdomState.account_number/treasury,
            # edited with no range check in the web editor) outside what
            # a real field's own byte width can hold raises struct.error
            # from the underlying struct.pack() call, not ValueError --
            # caught here too so this Kingdom is skipped the same honest
            # way an XKExportError already is above, instead of crashing
            # process_and_save_current_turn() before save_game() runs
            # and leaving state.pkl stale against the turn reports (and
            # any sibling Kingdoms' own .xk files) already written for
            # this same turn.
            continue
        (directory / f"{kingdom_id}.xk").write_bytes(data)


def load_turn_xk_file(one_game_dir: Path, turn_number: int, kingdom_id: int) -> bytes | None:
    """``None`` if this turn's own XK file was never saved for this
    Kingdom (never processed, or ``save_turn_xk_files()`` skipped it --
    see that function's own docstring)."""

    path = turn_reports_dir(one_game_dir, turn_number) / f"{kingdom_id}.xk"
    if not path.is_file():
        return None
    return path.read_bytes()


def processed_turn_numbers(one_game_dir: Path) -> list[int]:
    """Every turn number with at least one saved report, oldest first."""

    directory = one_game_dir / REPORTS_DIRNAME
    if not directory.is_dir():
        return []
    numbers: list[int] = []
    for entry in directory.iterdir():
        if entry.is_dir() and entry.name.startswith("turn_"):
            try:
                numbers.append(int(entry.name.removeprefix("turn_")))
            except ValueError:
                continue
    return sorted(numbers)


def process_and_save_current_turn(root: Path, slug: str, state: GameState, one_game_dir: Path) -> TurnOutcome:
    """Runs ``process_turn()`` against every move file uploaded for
    ``state.turn_number``, then persists the resulting letter reports
    AND each Kingdom's own real XK file (Phase 1026, ``save_turn_xk_
    files()``) under this same turn's own number -- ``TurnOutcome.
    letter_reports`` describes the turn that was *just* processed, not
    the incremented ``state.turn_number`` ``process_turn()`` leaves
    behind) and the updated ``state`` itself. Unlike ``webapp/reports.py
    turn_zero_report()``, a processed turn's own report can't be safely
    regenerated later on demand -- it reflects one real, RNG-driven
    ``run_turn()`` dispatch that already happened and mutated ``state``
    permanently -- so it's saved to disk immediately, right here, rather
    than left for a later "view"/"download" request to recompute.

    A Kingdom with no uploaded file this turn is not an error:
    ``process_turn()`` already gives it the real rulebook-mandated
    missed-deadline Defend/Wait auto-fill, so the GM can process a turn
    with only some Kingdoms having submitted, matching real GM discretion
    over deadlines.
    """

    processed_turn_number = state.turn_number
    order_file_paths = list(
        uploaded_move_files(one_game_dir, processed_turn_number, state.kingdoms.keys()).values()
    )
    outcome = process_turn(state, order_file_paths)
    save_turn_reports(one_game_dir, processed_turn_number, outcome.letter_reports)
    save_turn_xk_files(one_game_dir, processed_turn_number, state)
    save_game(root, slug, state)
    return outcome
