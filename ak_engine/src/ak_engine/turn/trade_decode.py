"""Decoding a Trade PlanPhase -- the rulebook's Give order ([3.18]/[5.7]).

**Naming mismatch, confirmed in the Pascal source**: ``CTBOTH.PAS``'s
``action`` enum (lines 98-102) names ordinal 14 ``Trade``, matching this
project's ``ActionCode.TRADE``, but its two-letter abbreviation table
(``actab``) gives it ``'GI'`` -- the same abbreviation the rulebook uses
for "Give (GI)" [3.18]. There is no separate ``Give`` member in the
Pascal ``action`` enum at all. So ``ActionCode.TRADE`` **is** the
rulebook's Give order, just named differently between the engine's
internal enum and the player-facing rulebook.

Rulebook [3.18] (``RULES.AK`` ~line 637), quoted in full:

    A character may Give a magic item to another character. List the ID
    number of the magic item and a co-located character who will
    receive it. The characters may belong to different kingdoms. If so,
    you may specify that the gift will be made only if the recipient
    Gives you a specified magic item in the same phase.
    You can give limited amounts of gold to other Kings. Only a King may
    use this "Give Gold" order. [...] A King may give out in a gameturn
    no more than 10% of the size of his treasury [...] Be careful that
    you don't "Give" an amount of gold that equals a magic item I.D.
    number carried by the King.

**Phase 133 correction -- both previously-unconfirmed fields are now
resolved**, from real domain knowledge the user supplied directly
(2026-07-13, not found anywhere in ``Programma Pascal.zip`` -- see
below for the independent Pascal-source cross-check), quoted in full:

    In caso di comando GI (Give) con numero di oro uguale a un oggetto
    che possiede un eroe (esempio: l'eroe #55 ha l'oggetto #3, se
    riceve l'ordine GI 3 to #77 passera l'oggetto #3 - se lo possiede -
    all'eroe #77, se non lo possiede passa 3 gold sempre che il suo
    reame abbia 30 gold nella tesoreria, altrimenti il comando fallisce
    e nel report viene scritto: "l'eroe #55 non aveva con se abbastanza
    oro da darti"), si passa l'oggetto e non l'oro. Il comando si usa
    cosi: GI (numero dell'oggetto o dell'oro) (numero d'ordine
    dell'eroe o del RE che si trova nella stessa provincia). Se l'eroe
    appartiene a un altro reame, l'oggetto passa di mano oppure, se si
    tratta di oro, questo passa nella stessa fase nella tesoreria
    dell'altro reame.

Two real fields, therefore:

- ``obj`` (``lobjects[m]``) is genuinely overloaded, exactly as the
  rulebook's own closing warning implied ("don't Give an amount of gold
  that equals a magic item I.D. number") -- but the disambiguation rule
  itself is now known: the engine checks whether the giver actually
  *possesses* an item with that ID. If so, that item is given (**"si
  passa l'oggetto e non l'oro"** -- "the item is given, not the gold" --
  item takes priority). If not, ``obj`` is instead treated as a gold
  amount, gated by [3.18]'s own already-sourced 10%-of-treasury cap
  (independently cross-validated by the user's own example: giving 3
  gold requires >= 30 in the treasury, i.e. exactly 3 = 30 * 10%).
- The **recipient** -- previously this project's single biggest Trade
  gap, "no confirmed recipient field... at all" -- is the *second*
  number in the ``GI <item_or_gold> <target>`` order syntax: the target
  character's own order/leader number, required to be co-located
  ("che si trova nella stessa provincia"). This lands as
  ``target_leader_id``, structurally confirmed against
  ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``: the standard
  ``(action, obj, tl)`` triple is read first (``tl`` -> this project's
  ``extra[0]``, the same convention every other action follows), and
  Trade's own ``CASE`` branch reads exactly *one* further value right
  after -- ``READ(miscfile,pexrec[m].n1)`` (reader, ~line 575) /
  ``WrN(pexrec[m].n1)`` (writer, ~line 126) -- which lands as
  ``extra[1]``. This is exactly the position this project's own earlier
  analysis had already flagged as "most plausible... but... not a
  confirmed mapping" -- the user's real-world description of the order
  syntax is what confirms it, not the Pascal source alone (the source
  proves *a* second field exists at that position; the user's
  description proves *what it means*).

Real, previously-unfound corroboration in the Pascal source itself:
``SAY.PAS`` (~lines 517-520) has the narrative templates for exactly
this mechanic -- ``_LTrade: Say('< gave the \\ to [.')`` (item given),
``_LGGive: Say('< gave/Rdonated to [ # gold from > treasury/Rown_funds.')``
(gold given), and, matching the user's own described failure case
almost verbatim, ``_LNHave: Say("< didn't have on hand the full # gold
requested, so ")`` (insufficient gold) -- found and rendered in
``report/turn_report.py``'s own Phase 133 addendum.

Given all of the above, this module now decodes ``target_leader_id``
directly (Phase 133), while ``obj``'s item-vs-gold resolution stays a
*runtime* decision (needs a real item-ownership check against
``GameState``, which this decode module -- operating on the raw
``PlanPhase`` alone -- has no access to) made by ``turn/
trade_execution.py execute_give()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.plan import PlanPhase


@dataclass(slots=True)
class TradeRequest:
    obj: int  # item id OR gold amount -- resolved at execution time via possession check (see module docstring)
    target_leader_id: int | None  # extra[1] ("n1") -- the co-located recipient's own leader id
    extra: list[int] = field(default_factory=list)  # raw extra list, kept for traceability


def decode_trade_phase(phase: PlanPhase) -> TradeRequest:
    """Decode a Trade PlanPhase's ``obj`` and recipient. See the module docstring for the
    item-vs-gold disambiguation rule, resolved at execution time, not here.
    """

    target_leader_id = phase.extra[1] if len(phase.extra) > 1 else None
    return TradeRequest(obj=phase.obj, target_leader_id=target_leader_id, extra=list(phase.extra))
