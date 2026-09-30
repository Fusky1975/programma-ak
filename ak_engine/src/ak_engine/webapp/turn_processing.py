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

from pathlib import Path

from ak_engine.models.game_state import GameState
from ak_engine.orchestrator import TurnOutcome, process_turn
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.webapp.games import save_game

MOVES_DIRNAME = "moves"
REPORTS_DIRNAME = "reports"


class InvalidMoveFileError(Exception):
    """Raised when an uploaded file doesn't parse as a real move file at
    all, or its own filename doesn't end in a valid ``.K<N>`` suffix."""


def turn_moves_dir(one_game_dir: Path, turn_number: int) -> Path:
    return one_game_dir / MOVES_DIRNAME / f"turn_{turn_number}"


def uploaded_move_files(one_game_dir: Path, turn_number: int) -> dict[int, Path]:
    """``kingdom_id`` -> the uploaded move file for this turn, for every
    upload currently on disk that still parses. A replaced/stale upload
    that no longer parses simply doesn't appear -- callers never need to
    special-case it.
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
        files[kingdom_id] = path
    return files


def save_uploaded_move_file(one_game_dir: Path, turn_number: int, filename: str, content: bytes) -> int:
    """Saves one uploaded move file under its own real filename (required
    -- ``Kingdom.kingdom_id`` is parsed from it, not from content) and
    returns the Kingdom id it parsed to. Raises ``InvalidMoveFileError``,
    removing the bad file again, if it doesn't parse as a real move file
    with a valid ``.K<N>`` suffix.
    """

    directory = turn_moves_dir(one_game_dir, turn_number)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_bytes(content)
    try:
        kingdom = parse_k1_moves_file(path)
        return kingdom.kingdom_id
    except (K1ParseError, ValueError, IndexError) as exc:
        path.unlink(missing_ok=True)
        raise InvalidMoveFileError(str(exc)) from exc


def remove_uploaded_move_file(one_game_dir: Path, turn_number: int, kingdom_id: int) -> None:
    for kingdom_id_on_disk, path in uploaded_move_files(one_game_dir, turn_number).items():
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
    ``state.turn_number``, then persists both the resulting letter
    reports (under this same turn's own number -- ``TurnOutcome.
    letter_reports`` describes the turn that was *just* processed, not
    the incremented ``state.turn_number`` ``process_turn()`` leaves
    behind) and the updated ``state`` itself. Unlike ``webapp/reports.py
    turn_zero_report()``, a processed turn's own report can't be safely
    regenerated later on demand -- it reflects one real, RNG-driven
    ``run_turn()`` dispatch that already happened and mutated ``state``
    permanently -- so it's saved to disk immediately, right here, rather
    than left for a later "view" request to recompute.

    A Kingdom with no uploaded file this turn is not an error:
    ``process_turn()`` already gives it the real rulebook-mandated
    missed-deadline Defend/Wait auto-fill, so the GM can process a turn
    with only some Kingdoms having submitted, matching real GM discretion
    over deadlines.
    """

    processed_turn_number = state.turn_number
    order_file_paths = list(uploaded_move_files(one_game_dir, processed_turn_number).values())
    outcome = process_turn(state, order_file_paths)
    save_turn_reports(one_game_dir, processed_turn_number, outcome.letter_reports)
    save_game(root, slug, state)
    return outcome
