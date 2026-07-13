"""Executing Trade/Give (rulebook [3.18]/[5.7]) -- Phase 132, extended Phase 133.

**Phase 133 -- the recipient gap is closed.** ``turn/trade_decode.py``'s
own docstring now documents, in full, the real domain knowledge the
user supplied directly (2026-07-13) that resolves both of this
project's previously-unconfirmed Trade fields: ``obj`` is disambiguated
by checking whether the giver actually *possesses* an item with that
ID (if so, the item is given; if not, ``obj`` is treated as a gold
amount), and the recipient is ``TradeRequest.target_leader_id``
(``extra[1]``/``n1``), required to be co-located with the giver. This
module's own Phase 132 predecessor (``execute_gold_give()``, kept
below as the low-level treasury-mutation primitive) could only
implement the 10%-cap rule in isolation, taking the recipient as a
caller-supplied parameter because nothing decoded one. ``execute_give()``
is the new, higher-level entry point that consumes a real
``TradeRequest`` end-to-end.

**The item-vs-gold *disambiguation* is still not something this module
can evaluate on its own**: doing so needs to know whether the giver
*actually holds* an item with id ``obj``, and this project has no
per-leader item-ownership registry at all (``models/item.py`` is still
"a stub for a future phase, not populated by the move parser," Phase
1) -- a second, independent structural gap on top of the
now-closed recipient one. ``execute_give()`` therefore takes
``giver_possesses_item`` as an explicit parameter rather than guessing:
it defaults to ``False`` (documented: since this project can never
positively confirm possession, every real call necessarily falls
through to the gold path, which is the only one this project can
actually execute against ``GameState``) but stays overridable for a
future caller once an item-ownership model exists.

**When the gold path resolves, this module now also enforces the
recipient side of [3.18]**: "You can give limited amounts of gold to
*other Kings*" -- not just "only a King may give," but the recipient
must be a King too. ``execute_gold_give()`` already checked the giver;
``execute_give()`` adds the recipient check plus the co-location
requirement the user's own description of the ``GI <item_or_gold>
<target>`` order syntax confirms ("che si trova nella stessa
provincia").

**Real, previously-unrendered SAY.PAS corroboration** (found while
verifying the user's description against the Pascal source, ~lines
517-520): ``_LGGive`` (a successful gold Give) and ``_LNHave`` ("<
didn't have on hand the full # gold requested, so ...", matching the
user's own described failure almost verbatim) are now rendered in
``report/turn_report.py``'s own Phase 133 addendum.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.game_state import GameState
from ak_engine.turn.trade_decode import TradeRequest

# Rulebook [3.18]: "no more than 10% of the size of his treasury."
GOLD_GIVE_MAX_PERCENT = 10


@dataclass(slots=True)
class TradeExecutionResult:
    applied: bool
    reason: str | None = None
    gold_transferred: int = 0
    item_transferred: bool = False


def execute_gold_give(
    state: GameState,
    giver_leader_id: int,
    recipient_kingdom_id: int,
    gold_amount: int,
) -> TradeExecutionResult:
    """Move gold from a King's own kingdom treasury to another kingdom's, enforcing
    rulebook [3.18]'s 10%-of-treasury cap and the giver-must-be-a-King
    rule. Low-level primitive -- prefer ``execute_give()`` for a real,
    decoded ``TradeRequest`` (it additionally enforces co-location and
    that the *recipient* is a King too). Kept separately since a future
    caller may know a real recipient kingdom without going through a
    full ``TradeRequest`` (e.g. a hand-built scenario).
    """

    giver = state.leaders.get(giver_leader_id)
    if giver is None:
        return TradeExecutionResult(applied=False, reason="giver not found")
    if not giver.is_king:
        # "Only a King may use this 'Give Gold' order."
        return TradeExecutionResult(applied=False, reason="only a King may Give Gold")
    if giver.kingdom_id is None:
        return TradeExecutionResult(applied=False, reason="giver has no kingdom")

    giver_kingdom = state.kingdoms.get(giver.kingdom_id)
    recipient_kingdom = state.kingdoms.get(recipient_kingdom_id)
    if giver_kingdom is None or recipient_kingdom is None:
        return TradeExecutionResult(applied=False, reason="kingdom not found")

    if gold_amount <= 0:
        return TradeExecutionResult(applied=False, reason="gold amount must be positive")

    cap = giver_kingdom.treasury * GOLD_GIVE_MAX_PERCENT // 100
    if gold_amount > cap:
        # Matches SAY.PAS's own _LNHave narrative: "< didn't have on
        # hand the full # gold requested" -- see module/turn_report.py
        # docstrings.
        return TradeExecutionResult(applied=False, reason=f"exceeds 10% treasury cap ({cap})")

    giver_kingdom.treasury -= gold_amount
    recipient_kingdom.treasury += gold_amount
    return TradeExecutionResult(applied=True, gold_transferred=gold_amount)


def execute_give(
    state: GameState,
    giver_leader_id: int,
    request: TradeRequest,
    *,
    giver_possesses_item: bool = False,
) -> TradeExecutionResult:
    """Resolve a real Trade (Give) order end-to-end (Phase 133).

    ``giver_possesses_item`` defaults to ``False`` since this project
    has no item-ownership registry to check for real -- see module
    docstring. When ``True`` (a future caller's own responsibility to
    determine), the item path is reported as accepted-but-unmodeled
    (no registry to actually move the item in); when ``False`` (the
    only case this project can act on today), ``request.obj`` is
    treated as a gold amount and the recipient's own King status plus
    [3.18]'s 10% cap are enforced.
    """

    giver = state.leaders.get(giver_leader_id)
    if giver is None:
        return TradeExecutionResult(applied=False, reason="giver not found")

    if request.target_leader_id is None:
        return TradeExecutionResult(applied=False, reason="no recipient decoded")

    recipient = state.leaders.get(request.target_leader_id)
    if recipient is None:
        return TradeExecutionResult(applied=False, reason="recipient not found")

    if giver.location != recipient.location:
        # The user's own description of the order syntax: "(numero
        # d'ordine dell'eroe o del RE) che si trova nella stessa
        # provincia" -- the recipient must be co-located with the giver.
        return TradeExecutionResult(applied=False, reason="not co-located with recipient")

    if giver_possesses_item:
        # "si passa l'oggetto e non l'oro" -- item takes priority when
        # actually possessed. No item-ownership registry exists to
        # actually move it (models/item.py stub) -- honestly unmodeled,
        # not silently treated as a no-op success.
        return TradeExecutionResult(applied=False, reason="item transfer not modeled -- no item-ownership registry exists")

    if not recipient.is_king:
        # "You can give limited amounts of gold to other Kings" --
        # the recipient, not just the giver, must be a King.
        return TradeExecutionResult(applied=False, reason="gold Give recipient must be a King")

    if recipient.kingdom_id is None:
        return TradeExecutionResult(applied=False, reason="recipient has no kingdom")

    return execute_gold_give(state, giver_leader_id, recipient.kingdom_id, request.obj)
