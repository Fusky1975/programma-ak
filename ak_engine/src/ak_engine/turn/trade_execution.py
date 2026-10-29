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
of [3.18]**. ``execute_gold_give()`` already checked the giver;
``execute_give()`` adds the recipient check plus the co-location
requirement the user's own description of the ``GI <item_or_gold>
<target>`` order syntax confirms ("che si trova nella stessa
provincia"). **Stale as of 2026-10-29** -- this paragraph used to say
the recipient "must be a King too," over-reading the English rule's
own "You can give limited amounts of gold to other Kings" as a
recipient restriction; the fuller RULES.AK/ADDEND.AK text (and the
user's own fuller Italian text) both independently give the real,
complete rule: "giving it to another player's character (King or
Hero)" -- a Hero recipient is equally valid, the only real requirement
being a genuinely different Kingdom (confirmed with the user), not
King status.

**Real, previously-unrendered SAY.PAS corroboration** (found while
verifying the user's description against the Pascal source, ~lines
517-520): ``_LGGive`` (a successful gold Give) and ``_LNHave`` ("<
didn't have on hand the full # gold requested, so ...", matching the
user's own described failure almost verbatim) are now rendered in
``report/turn_report.py``'s own Phase 133 addendum.

**Phase 214 -- closes `report/turn_report.py describe_give()`'s own
item-name gap, and wires TRADE into `describe_turn_results()`.**
`TradeExecutionResult` gains two fields: `item` (the real
`ItemInstance` that moved -- this function already resolves it, just
never kept it) and `request` (stamped by `plan_dispatch.py`'s own
`_dispatch_trade()`, same convention as `PursueExecutionResult
.request`'s Phase 213 note). This project's own "no item-instance
display-name synthesis" gap `describe_give()`'s docstring names turns
out to already be closed one level up: `models/treasure.py
TREASURE_NAME` maps every `Treasure` type (`item.treasure`) to a real
display name -- the only thing missing was *which* item moved, not how
to name it.

**2026-10-29 -- two further bug fixes, sourced directly from the user's
own fuller Italian rulebook text, independently confirmed in both
RULES.AK and ADDEND.AK verbatim.** (1) ``GOLD_GIVE_MINIMUM_FLOOR``: "he
may always give out at least 10 gold if he has it in his treasury" --
the 10% cap now has a real floor of 10 gold, raised only up to what the
King actually has (``execute_gold_give()``). (2) The gold-recipient
check in ``execute_give()`` now allows a Hero, not just a King --
"giving it to another player's character (King or Hero)" -- the
previous reading's "recipient must be a King" over-read the shorter
English excerpt; still requires a genuinely different Kingdom
(confirmed with the user), not King status. **Deliberately NOT fixed
this round, per the user's own explicit choice**: the 10% cap still
uses the giver's *live* treasury at the moment of this specific Give,
not a "treasury at the start of the gameturn" snapshot RULES.AK/
ADDEND.AK both also specify -- no such snapshot exists anywhere in
``GameState``/``KingdomState`` today, and adding one was explicitly
deferred. **Also deliberately NOT implemented**: the real, sourced
conditional/barter Give mechanic ("the gift will be made only if the
recipient Gives you a specified magic item in the same phase") --
confirmed structurally to need no third wire field (``turn/trade_
decode.py``'s own ``TradeRequest`` already models both real fields),
but real cross-leader, same-phase reciprocity-checking execution logic
that doesn't exist anywhere in ``turn/plan_dispatch.py``/``turn/
turn_processor.py`` today -- a structural gap in the same family as
Leave's own deferred Initiative-ordering gap, out of scope for this
round per the user's own explicit choice.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.game_state import GameState
from ak_engine.models.item import ItemInstance
from ak_engine.models.treasure import Treasure
from ak_engine.turn.trade_decode import TradeRequest

# Rulebook [3.18]: "no more than 10% of the size of his treasury."
GOLD_GIVE_MAX_PERCENT = 10

# Sourced directly from the user (2026-10-29), independently confirmed
# in both RULES.AK and ADDEND.AK, verbatim: "(although he may always
# give out at least 10 gold if he has it in his treasury.)" -- a real
# floor on the 10% cap above, not just a round number.
GOLD_GIVE_MINIMUM_FLOOR = 10


@dataclass(slots=True)
class TradeExecutionResult:
    applied: bool
    reason: str | None = None
    gold_transferred: int = 0
    item_transferred: bool = False
    # Phase 214: the real transferred ItemInstance, so a caller
    # (report/turn_report.py describe_turn_results()) can resolve an
    # item_name via models/treasure.py TREASURE_NAME -- this project's
    # own item-instance display-name gap turned out to already be
    # closed at the Treasure-type level, only the identity of *which*
    # item moved was ever missing. None unless item_transferred is True.
    item: ItemInstance | None = None
    # Phase 214: the originating request, so a caller can resolve the
    # recipient's own display name and (for the insufficient-gold
    # failure narrative) the originally-requested gold amount. Set by
    # plan_dispatch.py's own _dispatch_trade(), not by execute_give()
    # itself -- same convention/reasoning as PursueExecutionResult
    # .request's own Phase 213 note.
    request: TradeRequest | None = None


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
    # Bug fix, sourced directly from the user (2026-10-29): "può
    # tuttavia sempre dare per lo meno 10 pezzi d'oro purché disponga
    # effettivamente di questa somma" -- the 10% cap has a real floor
    # of GOLD_GIVE_MINIMUM_FLOOR, but only ever raised up to what the
    # King actually has (never invented above his real treasury).
    if cap < GOLD_GIVE_MINIMUM_FLOOR and giver_kingdom.treasury >= GOLD_GIVE_MINIMUM_FLOOR:
        cap = GOLD_GIVE_MINIMUM_FLOOR
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
    treated as a gold amount and the recipient's own different-Kingdom
    requirement plus [3.18]'s 10% cap (with its own real minimum floor,
    see ``execute_gold_give()``'s own 2026-10-29 addendum) are enforced.

    **Phase 713 -- `AdvancedAbility.SPY_BLACKMAIL`'s own real, sourced
    exception**: the AKPROSE-recovered demand message states directly
    that a victim king paying off a blackmail claim does so via an
    ordinary gold Give order, and "the money will be automatically
    transferred without any need for the kings to be in the same
    province." When a King is paying off his own Kingdom's real
    ``KingdomState.active_blackmail`` claim, to the exact blackmailer's
    own Kingdom, the co-location check below is waived for that one
    transfer -- everything else (10% treasury cap, recipient-must-be-
    a-different-Kingdom) still applies unchanged. A successful payment
    of at least the claimed amount clears the claim and resets the spy's own
    ``LeaderState.unpaid_blackmail_penalty_exponent``. See ``turn/
    blackmail.py``'s own module docstring for the full mechanic.
    """

    giver = state.leaders.get(giver_leader_id)
    if giver is None:
        return TradeExecutionResult(applied=False, reason="giver not found")

    if request.target_leader_id is None:
        return TradeExecutionResult(applied=False, reason="no recipient decoded")

    recipient = state.leaders.get(request.target_leader_id)
    if recipient is None:
        return TradeExecutionResult(applied=False, reason="recipient not found")

    item = state.items.get(request.obj)
    is_item_transfer = item is not None and item.owner_leader_id == giver_leader_id
    giver_kingdom = state.kingdoms.get(giver.kingdom_id) if giver.kingdom_id is not None and giver.is_king else None
    blackmail_claim = giver_kingdom.active_blackmail if giver_kingdom is not None else None
    paying_off_blackmail = (
        not is_item_transfer
        and blackmail_claim is not None
        and recipient.is_king
        and recipient.kingdom_id == blackmail_claim.spy_kingdom_id
    )

    if giver.location != recipient.location and not paying_off_blackmail:
        # The user's own description of the order syntax: "(numero
        # d'ordine dell'eroe o del RE) che si trova nella stessa
        # provincia" -- the recipient must be co-located with the giver.
        return TradeExecutionResult(applied=False, reason="not co-located with recipient")

    # Phase 547 -- VALHALLA.txt: "You can do anything you want with the
    # magic item Vahlalla visitor came with, but the item will leave at
    # the end of Vahlalla visitor stay" -- the visitor's own fixed item
    # specifically (tracked at spawn, LeaderState.valhalla_fixed_item_id)
    # can never be Given away; every other item they might separately
    # acquire (e.g. via Search) is unaffected.
    if giver.valhalla_fixed_item_id is not None and request.obj == giver.valhalla_fixed_item_id:
        return TradeExecutionResult(applied=False, reason="the Valhalla visitor's own fixed item cannot be given away")

    if is_item_transfer:
        # "si passa l'oggetto e non l'oro" -- item takes priority when
        # actually possessed, no King status or same-kingdom requirement
        # on either side (unlike the gold path below): "Se l'eroe
        # appartiene a un altro reame, l'oggetto passa di mano."
        state.transfer_item(request.obj, request.target_leader_id)
        return TradeExecutionResult(applied=True, item_transferred=True, item=item)

    # Bug fix, sourced directly from the user (2026-10-29), independently
    # confirmed in both RULES.AK and ADDEND.AK, verbatim: "giving it to
    # another player's character (King or Hero)" -- the earlier reading
    # ("recipient must be a King") over-read the English rule's own
    # "You can give ... to other Kings" as a recipient restriction, when
    # the fuller text clarifies a Hero recipient is equally valid. Still
    # "another player's" -- confirmed with the user as requiring a
    # genuinely different Kingdom, not merely "not a King."
    if recipient.kingdom_id is None or recipient.kingdom_id == giver.kingdom_id:
        return TradeExecutionResult(
            applied=False, reason="gold Give recipient must belong to a different Kingdom"
        )

    result = execute_gold_give(state, giver_leader_id, recipient.kingdom_id, request.obj)
    if paying_off_blackmail and result.applied and result.gold_transferred >= blackmail_claim.amount:
        giver_kingdom.active_blackmail = None
        spy = state.leaders.get(blackmail_claim.spy_leader_id)
        if spy is not None:
            spy.unpaid_blackmail_penalty_exponent = 0
    return result


@dataclass(slots=True)
class CuratorResearchResult:
    """Office.CURATOR's own real perk (Phase 667, ``models/office.py
    OFFICE_TITLE_DESCRIPTION``): "The Guild will research any item
    number in the world for <2, telling all about its magical
    function." Same ``request`` convention as ``TradeExecutionResult``
    -- stamped by ``plan_dispatch.py``'s own ``_dispatch_trade()``.
    """

    applied: bool
    item_id: int
    treasure: Treasure | None = None
    reason: str | None = None
    request: TradeRequest | None = None


def execute_curator_research(state: GameState, item_id: int) -> CuratorResearchResult:
    """"< can research items only by item number, not by magic item type."
    ``item_id`` resolves against the real, world-wide ``GameState.items``
    registry -- an item guarded by a Feature or owned by a foreign
    Kingdom still has a real ``ItemInstance`` there (``owner_leader_id``
    is simply ``None`` for the unowned case), matching "any item number
    in the world," not just an item the researcher personally holds.
    ``item_id`` with no matching ``ItemInstance`` at all fails outright
    -- no fallback guess at what an unassigned number might mean.

    Triggered by a self-targeting Give order (the titleholder's own
    "order to give the magic item number to himself") -- see ``turn/
    plan_dispatch.py _dispatch_trade()``'s own Phase 667 addendum for
    why this bypasses ``execute_give()`` entirely rather than layering
    on top of it: a self-Give naming an item the titleholder doesn't
    own would otherwise misroute into the gold-Give path (`obj`
    reinterpreted as a gold amount, gated on the giver/recipient --
    here, the same person -- being a King), which has nothing to do
    with what this order actually means for a Curator.
    """

    item = state.items.get(item_id)
    if item is None:
        return CuratorResearchResult(applied=False, item_id=item_id, reason="no such item number exists in the world")
    return CuratorResearchResult(applied=True, item_id=item_id, treasure=item.treasure)
