"""GM-facing Treat/Break Treat order submission (Phase 1027).

``turn/diplomacy.py``'s own module docstring, and ``GameState.treat_
permissions``/``break_treat_orders``'s own field docstrings
(``models/game_state.py``), both explicitly anticipated this and left it
unfilled: there is no real move-file shape for a Treat/Break Treat order
("no real order-file shape ever seen... populated directly by the
caller"), and -- confirmed directly, a grep of every production call site
-- nothing in this project has ever actually populated either field
outside of a test fixture. The full Fase 2 diplomacy engine (``turn/
diplomacy.py apply_treat_orders()``, wired into ``run_turn()`` since
Phase 1026) was therefore unreachable from the GM web interface: a real
GM playing a real game had no way to ever issue one of these orders.

This module is the "caller" those docstrings were waiting for: a per-turn
screen (``webapp/templates/turns_diplomacy.html``) where the GM enters,
for each ordered Kingdom pair, a directed Treat or Break Treat order on
behalf of each King -- exactly the directed ``(issuer, target)`` signal
``treat_permissions``/``break_treat_orders`` already expect, not a new
format invented here.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState


class InvalidDiplomacyOrderError(Exception):
    """Raised when a submitted order names a pair that isn't two
    distinct, real Kingdoms of this game."""


def set_turn_diplomacy_orders(
    state: GameState, treat_pairs: set[tuple[int, int]], break_pairs: set[tuple[int, int]]
) -> None:
    """Replaces this turn's own pending orders wholesale with exactly
    what the GM's form submitted this call -- the same "the whole form is
    the source of truth" convention ``titles_save()`` already uses for
    ``enabled_optional_offices``. Both fields are already turn-scoped
    (``turn/turn_processor.py _replenish_turn_scoped_state()`` clears
    them at the end of every ``run_turn()`` call), so there is never a
    previous turn's own order left to merge with -- a wholesale replace
    is correct, not merely convenient.
    """

    valid_ids = set(state.kingdoms)
    for pairs in (treat_pairs, break_pairs):
        for issuer, target in pairs:
            if issuer == target or issuer not in valid_ids or target not in valid_ids:
                raise InvalidDiplomacyOrderError(
                    f"({issuer}, {target}) isn't a valid ordered pair of two distinct Kingdoms in this game"
                )
    state.treat_permissions = set(treat_pairs)
    state.break_treat_orders = set(break_pairs)
