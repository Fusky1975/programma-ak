"""Real XK binary file export (Phase 1026) -- wires the XK encoder
(``parser/xk_world_builder.py``/``parser/xk_world_writer.py``) into the
GM web interface. This closes the explicit v1 scope decision ``webapp/
reports.py``'s own module docstring used to record ("serving... as this
project's stand-in for the real (still unreverse-engineered) binary XK
export"): that decoding work is done now, so the interface offers the
real file alongside the text letter report, not instead of it -- a
player's own separate map program still wants the real binary, and
nothing about the existing text-letter flow changes.
"""

from __future__ import annotations

import struct

from ak_engine.models.game_state import GameState
from ak_engine.parser.xk_world import XKWorld
from ak_engine.parser.xk_world_builder import build_xk_world_for_kingdom
from ak_engine.parser.xk_world_writer import write_xk_world


class XKExportError(Exception):
    """Raised when this Kingdom's own current ``GameState`` can't be
    encoded as a real XK file -- e.g. a GM-edited leader_id/coordinate
    collides with the format's own ``0xFE`` list-end sentinel (see
    ``xk_world_writer.py``'s own guard asserts). Surfaced to the GM as a
    plain error message, never a crash.
    """


def build_xk_worlds_for_all_kingdoms(state: GameState) -> dict[int, XKWorld]:
    """Builds every Kingdom's own ``XKWorld`` together for the same
    turn, each one after the first supplying the previous as ``sibling``
    (see ``build_xk_world_for_kingdom``'s own docstring) so the
    confirmed shared/turn-level byte blocks this engine can't derive for
    a single Kingdom alone are copied across Kingdoms instead of
    zero-filled.
    """

    worlds: dict[int, XKWorld] = {}
    sibling: XKWorld | None = None
    for kingdom_id in sorted(state.kingdoms):
        world = build_xk_world_for_kingdom(state, kingdom_id, sibling=sibling)
        worlds[kingdom_id] = world
        sibling = world
    return worlds


def build_xk_file_for_kingdom(state: GameState, kingdom_id: int) -> bytes:
    """One Kingdom's own real XK file, as bytes ready to write or send.

    Raises ``XKExportError`` (never the writer's own bare ``ValueError``)
    if this Kingdom's current data can't be encoded -- a GM-facing route
    should catch this and show a plain error message instead of crashing.
    """

    worlds = build_xk_worlds_for_all_kingdoms(state)
    try:
        return write_xk_world(worlds[kingdom_id])
    except (ValueError, struct.error) as exc:
        # Bug fix: a GM-set value with no range check in the web editor
        # (treasury/account_number, a province's tax, an army's own
        # coordinate, ...) outside what its real field's own byte width
        # can hold raises struct.error from the underlying struct.pack()
        # call, not ValueError -- caught here too, the same way webapp/
        # turn_processing.py save_turn_xk_files() already does for the
        # turn-by-turn export, so this turn-0 preview/download path
        # shows the same honest "couldn't build the XK file" message
        # instead of crashing with an unhandled 500.
        raise XKExportError(str(exc)) from exc
