"""Turn 0 letter reports (Phase 6): a plain snapshot of the just-generated
world, rendered via the same real report composer every later turn uses
(``report/turn_report.py compose_letter_report()``) but with an empty
``results`` list (no ``PhaseDispatchResult`` -- no orders have ever been
processed yet) and no ``run_turn()``/``process_turn()`` call, so
``state.turn_number`` never advances.

This is deliberately NOT the same path a later turn uses.
``process_turn(state, [])`` (zero move files) was tried first and
rejected: it actually runs a full turn's own random events/dispatch
(``state.turn_number`` 1 -> 2, e.g. a real "visited by a Hero from
Valhalla" random event) despite there being no orders to process at all
-- correct for "a turn with nobody submitting a move," wrong for a report
meant to show only the world's own just-generated starting state, before
any turn has run.

Each Kingdom's own report already includes real PROVINCES/CHARACTERS/
ARMIES sections describing everything that Kingdom currently owns --
serving, per the GM interface plan's own explicit v1 scope decision, as
this project's stand-in for the real (still unreverse-engineered) binary
XK export a player's own separate map program would otherwise consume.
The report screen says so explicitly rather than silently presenting one
as the other.
"""

from __future__ import annotations

import random

from ak_engine.models.game_state import GameState
from ak_engine.report.turn_report import compose_letter_report


def turn_zero_report(state: GameState, kingdom_id: int) -> list[str]:
    """This Kingdom's own letter report for the world as it currently
    stands, with no turn ever processed. Safe to call repeatedly (e.g.
    after the GM edits a province in the World Editor) -- it always
    reflects the live ``state``, nothing cached.
    """

    return compose_letter_report([], state, kingdom_id, random.Random(), board_width=state.board_width)
