"""Executing Trade/Give (rulebook [3.18]/[5.7]) -- Phase 132, extended Phases 133 and 140.

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

**Phase 140 -- the item-vs-gold disambiguation is now real.**
``models/item.py ItemInstance``/``GameState.items`` (Phase 140) gives
this project the per-leader item-ownership registry the previous
paragraph's gap depended on, sourced from ``RUMORS.PAS``'s ``Add_Tr``
and the ``treaslist``/``trowner``/``trcharges`` triple -- see that
module's own docstring. ``execute_give()`` now checks
``state.items.get(request.obj)`` directly: if that instance exists and
its ``owner_leader_id`` really is the giver, the item is transferred
via ``GameState.transfer_item()`` ("si passa l'oggetto e non l'oro" --
the item path takes priority, and per the user's own description
**crosses kingdoms freely with no King requirement on either side**,
unlike the gold path below). If ``obj`` doesn't resolve to an owned
item, ``request.obj`` falls through to the gold path exactly as
before.

**When the gold path resolves, this module enforces the recipient side
of [3.18]**: "You can give limited amounts of gold to *other Kings*" --
not just "only a King may give," but the recipient must be a King too.
``execute_gold_give()`` already checked the giver; ``execute_give()``
adds the recipient check plus the co-location requirement the user's
own description of the ``GI <item_or_gold> <target>`` order syntax
confirms ("che si trova nella stessa provincia").

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
) -> TradeExecutionResult:
    """Resolve a real Trade (Give) order end-to-end (Phase 133, item path closed Phase 140).

    ``request.obj`` is checked against ``GameState.items`` first: if it
    resolves to an instance the giver actually owns, that item is
    transferred and the gold path is never considered ("si passa
    l'oggetto e non l'oro" -- item takes priority). Otherwise ``obj`` is
    treated as a gold amount and the recipient's own King status plus
    [3.18]'s 10% cap are enforced, exactly as before Phase 140.
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

    item = state.items.get(request.obj)
    if item is not None and item.owner_leader_id == giver_leader_id:
        # "si passa l'oggetto e non l'oro" -- item takes priority when
        # actually possessed, no King status or same-kingdom requirement
        # on either side (unlike the gold path below): "Se l'eroe
        # appartiene a un altro reame, l'oggetto passa di mano."
        state.transfer_item(request.obj, request.target_leader_id)
        return TradeExecutionResult(applied=True, item_transferred=True)

    if not recipient.is_king:
        # "You can give limited amounts of gold to other Kings" --
        # the recipient, not just the giver, must be a King.
        return TradeExecutionResult(applied=False, reason="gold Give recipient must be a King")

    if recipient.kingdom_id is None:
        return TradeExecutionResult(applied=False, reason="recipient has no kingdom")

    return execute_gold_give(state, giver_leader_id, recipient.kingdom_id, request.obj)
