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

from werkzeug.utils import secure_filename

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.orchestrator import TurnOutcome, process_turn
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.parser.xk_world_writer import write_xk_world
from ak_engine.turn.plan_dispatch import PhaseDispatchResult
from ak_engine.webapp.games import save_game
from ak_engine.webapp.xk_reports import XKExportError, build_xk_worlds_for_all_kingdoms

MOVES_DIRNAME = "moves"
REPORTS_DIRNAME = "reports"
PROCESSING_LOG_FILENAME = "processing_log.txt"


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

    # Bug fix: `filename` is the client-supplied multipart upload name,
    # verbatim -- unsanitized, a crafted name like "../../etc/evil.K1"
    # joins right past `directory` (confirmed directly: `path.write_
    # bytes()` below then writes outside the uploads folder entirely).
    # secure_filename() strips path separators and ".." components; a
    # name that sanitizes away to nothing is rejected outright rather
    # than silently writing to `directory` itself.
    safe_filename = secure_filename(filename)
    if not safe_filename:
        raise InvalidMoveFileError(f"{filename!r} is not a usable filename")
    directory = turn_moves_dir(one_game_dir, turn_number)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / safe_filename
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
    # Bug fix: a GM resubmitting a corrected move file under a different
    # filename than their first upload (the filename comes from the
    # player's own exported file, not something the GM controls) used
    # to leave the earlier file on disk too -- uploaded_move_files()'s
    # own docstring assumes at most one upload per kingdom_id, but its
    # sorted-iterdir dict build would then pick whichever filename sorts
    # alphabetically last, not the most recent upload, and remove_
    # uploaded_move_file() would only ever delete that one survivor,
    # leaving the other to resurface as "the" upload on the next call.
    # Any other on-disk file that still parses to this same kingdom_id
    # is now superseded by this fresh upload and removed.
    for other_path in directory.iterdir():
        if other_path == path or not other_path.is_file():
            continue
        try:
            other_kingdom_id = parse_k1_moves_file(other_path).kingdom_id
        except (K1ParseError, ValueError, IndexError):
            continue
        if other_kingdom_id == kingdom_id:
            other_path.unlink(missing_ok=True)
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


def _processing_log_leader_label(state: GameState, leader_id: int) -> tuple[str, str]:
    """``(kingdom_label, leader_label)`` for one ``PhaseDispatchResult.
    leader_id`` -- looked up against ``state`` *after* this same turn's
    own ``run_turn()`` call already ran, so a leader who died in an
    earlier phase this same turn (e.g. lost a Challenge) is looked up in
    ``state.dead_leaders`` instead (``GameState.remove_leader()``'s own
    graveyard), the same fallback this project's other post-turn
    composers already use rather than showing a bare, unexplained id.
    """

    leader = state.leaders.get(leader_id) or state.dead_leaders.get(leader_id)
    if leader is None:
        return "?", f"Leader #{leader_id}"
    kingdom = state.kingdoms.get(leader.kingdom_id)
    kingdom_label = kingdom.name if kingdom is not None else f"Kingdom #{leader.kingdom_id}"
    return kingdom_label, f"{leader.name} (#{leader_id})"


def _order_outcome_note(result: object) -> str:
    """For the GM's log: an order that was carried out but did nothing -- a Cast with ``applied`` false -- says why (the
    spell, its target and the reason), which the players' own reports tell only as "bungled it"."""

    if getattr(result, "applied", None) is not False:
        return ""
    request = getattr(result, "request", None)
    spell = getattr(request, "spell", None)
    target = getattr(request, "target", None)
    what = getattr(spell, "name", None)
    detail = f" -- {what}" if what else ""
    if what and target is not None:
        detail += f" on #{target}"
    reason = getattr(result, "reason", None)
    return f" (had no effect{detail}: {reason})" if reason else f" (had no effect{detail})"


def format_turn_processing_log(results: list[PhaseDispatchResult], state: GameState) -> list[str]:
    """2026-11-18 (user-requested): one line per real ``run_turn()``
    dispatch attempt (every ``PhaseDispatchResult``, in the exact order
    ``run_turn()`` itself produced them -- phase by phase across every
    leader, not grouped), naming the Kingdom, leader, phase, and real
    ``ActionCode`` ordered -- "OK" when it resolved cleanly, or the real
    exception message otherwise.

    This is the one place a GM can now see *every* order's own real
    success/failure, including the ones a processed turn's own letter
    report never narrates at all -- an order whose own dispatch raised
    (caught only by ``plan_dispatch.py run_leader_plan()``'s own
    intentionally-broad per-phase handler, recorded as ``error`` and
    otherwise discarded) used to vanish completely, with nothing
    anywhere to show it was even attempted (the exact gap the user's
    own "MOVE doesn't work, and nothing is reported" complaint traced
    back to). Bare ``ActionCode.name`` here, not this interface's own
    curated, order-sheet-style ``ACTION_NAME`` (``webapp/app.py``) --
    this is an internal diagnostic log for the GM, not player-facing
    report prose, and importing ``ACTION_NAME`` here would pull this
    module into a circular dependency on ``app.py``, which already
    imports *this* module's own save/load functions.
    """

    lines = [
        "This is a diagnostic log, for the GM only -- it is not part of any Kingdom's own letter report.",
        "One line per order this turn actually tried to dispatch, in the order it was dispatched.",
        "",
    ]
    if not results:
        lines.append("No orders were dispatched this turn (no Kingdom had a real move file, or no leader had any).")
        return lines
    for entry in results:
        kingdom_label, leader_label = _processing_log_leader_label(state, entry.leader_id)
        action_label = entry.action.name if isinstance(entry.action, ActionCode) else "(none)"
        status = "OK" if entry.error is None else f"ERROR: {entry.error}"
        if entry.error is None:
            status += _order_outcome_note(entry.result)
        lines.append(f"{kingdom_label} / {leader_label} / {entry.phase_label} / {action_label}: {status}")
    return lines


def save_turn_processing_log(one_game_dir: Path, turn_number: int, results: list[PhaseDispatchResult], state: GameState) -> None:
    directory = turn_reports_dir(one_game_dir, turn_number)
    directory.mkdir(parents=True, exist_ok=True)
    lines = format_turn_processing_log(results, state)
    (directory / PROCESSING_LOG_FILENAME).write_text("\n".join(lines), encoding="utf-8")


def load_turn_processing_log(one_game_dir: Path, turn_number: int) -> list[str] | None:
    """``None`` if this turn was never processed (or was processed before
    this feature existed -- an older saved turn simply has no log file
    on disk)."""

    path = turn_reports_dir(one_game_dir, turn_number) / PROCESSING_LOG_FILENAME
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

    **2026-11-18 (user-requested)**: also saves ``format_turn_processing_
    log()``'s own real per-order success/failure diagnostic, the same
    way and for the same reason as the letter reports/XK files above --
    ``state`` is only ever this exact post-turn snapshot right here, so
    a later "view" request can't recompute it from scratch.
    """

    processed_turn_number = state.turn_number
    order_file_paths = list(
        uploaded_move_files(one_game_dir, processed_turn_number, state.kingdoms.keys()).values()
    )
    outcome = process_turn(state, order_file_paths)
    save_turn_reports(one_game_dir, processed_turn_number, outcome.letter_reports)
    save_turn_xk_files(one_game_dir, processed_turn_number, state)
    save_turn_processing_log(one_game_dir, processed_turn_number, outcome.results, state)
    save_game(root, slug, state)
    return outcome
