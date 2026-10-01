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

This module also builds the real "BIRTHRIGHT REPORT" title page (Phase
981) -- the real title page a brand-new King's own first report always
opens with, confirmed from 5 real ``SE3__T0.K*``/``SE0__T0.K0`` samples
the user supplied directly, every one of which starts this same way:
two blank lines, the title line, a blank line, "FOR", a blank line, the
King's own name in capitals, then (after more blank space and a "Quote
of the Week:" block this project already has fully sourced and ready,
``report/turn_report.py render_quote_of_the_week()`` -- see that
function's own docstring for why the caller supplies the index rather
than the unrecoverable real date-driven rotation) the rest of the
report proper.

**Centering, Phase 981**: the title/"FOR"/King-name lines are each
centered on a fixed 39-column width, confirmed from the one line every
sample agrees on byte-for-byte -- "FOR" (3 chars) is indented by exactly
18 spaces in all 5 samples, which only solves to `width=39` ((39-3+1)//2
== 18). The title line's own 1-space indent in 3 of 5 samples (the
4th has 0, read as the one corrupted/hand-retyped sample also showing a
misspelled King name, "Makumbu" for "Makumb") and 3 of 4 real King
names' own indents (`BRADIBO I`/`KWOTH`/`PROMETEO`, the 4th again being
that same corrupted sample) all independently confirm the same
`width=39`, left-biased rounding (``(pad + 1) // 2`` puts the extra
space on the left, not Python ``str.center()``'s own right-biased
default) -- see `_centered()` below.

**Not reproduced**: the real title page's own several additional lines
(player name/account number, postal billing, "Quote of the Week"'s own
surrounding vertical whitespace sized to fill most of a printed page)
are play-by-mail correspondence specific to the original paid service,
not game data, and aren't attempted here.
"""

from __future__ import annotations

import random

from ak_engine.models.game_state import GameState
from ak_engine.report.turn_report import compose_letter_report, render_quote_of_the_week

_BIRTHRIGHT_TITLE_LINE = "THE ADVENTURER-KINGS BIRTHRIGHT REPORT"
_BIRTHRIGHT_TITLE_WIDTH = 39
_QUOTE_OF_THE_WEEK_COUNT = 94


def _centered(text: str) -> str:
    pad = max(_BIRTHRIGHT_TITLE_WIDTH - len(text), 0)
    return " " * ((pad + 1) // 2) + text


def _king_name(state: GameState, kingdom_id: int) -> str | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return leader.name
    return None


def _birthright_title_lines(state: GameState, kingdom_id: int, rng: random.Random) -> list[str]:
    lines = ["", "", _centered(_BIRTHRIGHT_TITLE_LINE), "", _centered("FOR")]
    king_name = _king_name(state, kingdom_id)
    if king_name:
        lines.extend(["", _centered(king_name.upper())])
    lines.extend(["", ""])
    lines.extend(render_quote_of_the_week(rng.randrange(_QUOTE_OF_THE_WEEK_COUNT)))
    lines.extend(["", ""])
    return lines


def turn_zero_report(state: GameState, kingdom_id: int) -> list[str]:
    """This Kingdom's own letter report for the world as it currently
    stands, with no turn ever processed. Safe to call repeatedly (e.g.
    after the GM edits a province in the World Editor) -- it always
    reflects the live ``state``, nothing cached.

    Phase 981: now opens with the real Birthright title page (see the
    module docstring) and passes ``include_home_province_narrative=True``
    so the home-province neighbor paragraph renders too -- both gated to
    this Turn 0 report specifically, not any later turn's.
    """

    rng = random.Random()
    title_lines = _birthright_title_lines(state, kingdom_id, rng)
    body_lines = compose_letter_report(
        [],
        state,
        kingdom_id,
        rng,
        board_width=state.board_width,
        include_home_province_narrative=True,
    )
    return title_lines + body_lines
