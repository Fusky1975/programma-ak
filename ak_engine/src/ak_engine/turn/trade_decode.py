"""Decoding a Trade PlanPhase -- the rulebook's Give order ([3.18]/[5.7]).

**Naming mismatch, confirmed in the Pascal source**: ``CTBOTH.PAS``'s
``action`` enum (lines 98-102) names ordinal 14 ``Trade``, matching this
project's ``ActionCode.TRADE``, but its two-letter abbreviation table
(``actab``) gives it ``'GI'`` -- the same abbreviation the rulebook uses
for "Give (GI)" [3.18], and the turn-report message constant is literally
``_LTrade: Say('< gave the \\ to [.')`` (``SAY.PAS``). There is no
separate ``Give`` member in the Pascal ``action`` enum at all. So
``ActionCode.TRADE`` **is** the rulebook's Give order, just named
differently between the engine's internal enum and the player-facing
rulebook -- likely because a Give can optionally be a two-way exchange
("you may specify that the gift will be made only if the recipient Gives
you a specified magic item in the same phase" -- a *trade*, not just a
one-way give).

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

**This is, by a wide margin, the least-confirmed decode module in this
project so far** -- worth reading in full before trusting any field
name below:

- The rulebook's own final warning ("don't Give an amount of gold that
  equals a magic item I.D. number") implies the item-id and gold-amount
  cases share one field with **no separate type flag found anywhere** in
  the available source -- i.e. ``obj`` is genuinely overloaded, not just
  under-documented.
- ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan`` confirm Trade reads
  the standard ``(action, obj, tl)`` triple like every other action
  (``tl`` lands as this project's ``PlanPhase.extra[0]``, per this
  project's consistent parsing across every other decode module), *plus
  one additional* ``READ(miscfile, pexrec[m].n1)`` unique to Trade's
  ``CASE`` branch -- but the Pascal source has **no comment naming what
  n1 means**, unlike e.g. Hire's clearly-commented gold-offer field.
  Structurally, based on every other action in this project landing its
  extra numeric reads as trailing elements of ``PlanPhase.extra`` (in
  Pascal read order), ``n1`` most plausibly lands at ``extra[1]`` -- but
  this is an inference from pattern-matching other actions' behavior,
  not a confirmed mapping for Trade specifically.
- **Zero real Trade phases exist in any of the 10 sample
  ``AK3__T*.K1`` files** (unlike Hire, which had 10 real examples to
  validate against) -- so there is no empirical cross-check available,
  the way there was for every other decode module except Fire's.
- **The actual turn-execution engine isn't in the available Pascal
  source tree at all** (only plan read/write/report-text code is present
  -- no ``pexrec`` record declaration, no code that actually moves gold
  or items between characters was found), so even Pascal-level
  confirmation of the field semantics is unavailable, not just
  real-data confirmation.

Given all of the above, this module deliberately does **not** invent
named fields like "recipient_id" or "item_id" for the uncertain
positions -- doing so would misrepresent confidence this project doesn't
have. It exposes ``obj`` (confirmed by the rulebook to be *either* an
item id or a gold amount, ambiguous) and the raw ``extra`` list
unprocessed, so a caller can inspect ``extra[0]``/``extra[1]`` themselves
with full awareness that their meaning is a plausible inference, not a
sourced fact. **Decode-only** in the weakest possible sense: no attempt
is made to resolve which of item-give / gold-give / reciprocal-trade a
given phase represents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.plan import PlanPhase


@dataclass(slots=True)
class TradeRequest:
    obj: int  # rulebook [3.18]: an item id OR a gold amount -- no confirmed discriminator, see module docstring
    extra: list[int] = field(default_factory=list)  # raw, unconfirmed field positions -- see module docstring


def decode_trade_phase(phase: PlanPhase) -> TradeRequest:
    """Decode a Trade PlanPhase's ``obj``/``extra`` without interpreting them.

    See the module docstring for why this stays deliberately raw.
    """

    return TradeRequest(obj=phase.obj, extra=list(phase.extra))
