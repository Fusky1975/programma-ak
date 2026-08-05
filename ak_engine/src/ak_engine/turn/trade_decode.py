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

**Phase 397 -- the Trade->Cast rewrite for the 10 secret spells (25-34)
is now modeled.** ``cast_decode.py``'s own docstring previously called
this "deliberately not handled... no real Trade phase (let alone this
specific rewrite) exists in any sample file to validate against
regardless" -- true about empirical validation (still true: 0 real
Trade phases of any kind exist across all 10 ``AK3__T*.K1`` fixtures,
confirmed by direct enumeration), but not about the mechanism itself,
which turned out to be fully and precisely specified structurally once
``HostAK/TP/DEF2.PAS``'s ``R_HPlan`` procedure (~line 575) was read
directly:

    Trade: BEGIN
      READ(miscfile,pexrec[m].n1); GhostR(abbrev);
      IF tl = sldr THEN IF modprog THEN
        IF lobjects[m] >= 25 THEN IF lobjects[m] <= 34 THEN
          IF Has_SA(sldr,spdex[lobjects[m]]) THEN BEGIN
            lextra[m]:= 0;
            lactions[m]:= Cast;
           END;
      IF not abbrev THEN RS;
      pexrec[m].ertype:= Numbers;
     END;

Decoded, term by term:

- ``tl`` is not Trade-specific -- it's the *generic* per-action triple
  read for every action before the ``CASE`` dispatch
  (``READ(miscfile,la,lobjects[m],tl)``, ~line 550, immediately
  followed by ``lextra[m]:= tl``), the exact same field
  ``cast_decode.py`` already documents as ``extra[0]`` ("the spell's
  target"). So ``tl = sldr`` means: this project's own
  ``phase.extra[0] == leader_id`` -- the order is self-targeted.
- ``modprog`` -- the one term that looked like it might be an
  unresolved runtime flag -- is confirmed, directly in the source
  (``CTME.PAS:545: CONST modprog = true;``), to be a compile-time
  constant always equal to ``true`` in the shipped build. Not a
  blocker; the condition it gates always holds.
- ``lobjects[m]`` (``phase.obj``) in ``[25, 34]`` is exactly this
  project's own ``Spell`` secret-spell ordinal range (Phase 23/84).
- ``Has_SA(sldr, spdex[lobjects[m]])``: the caster must hold the
  Special/Advanced Ability ``spdex`` maps that spell ordinal to (see
  ``models/advanced_ability.py ADVANCED_ABILITY_GRANTS_SPELL``, whose
  10-entry inverse mapping already matches ``spdex``'s own
  ``(C_GA,C_WH,C_ST,C_GD,C_MW,C_LP,C_LO,C_AC,C_IF,C_IH)`` template
  order 1:1 by abbreviation). **Not modeled here** -- this project has
  no per-leader granted-``AdvancedAbility`` registry anywhere
  (``worldgen/special_ability_level_schedule.py`` reproduces the real
  per-game grant *schedule* but is wired to nothing; no
  ``GameState.game_number`` field exists to even select a schedule).
  This is not a new gap introduced by this rewrite: none of
  ``turn/cast_execution.py``'s own already-wired secret-spell handlers
  (Gate Angel, Scar Terrain, Mystic Winds, Locate Object, Illusory Fog)
  check ``AdvancedAbility`` possession either -- every one of them
  relies solely on the generic Action-spell ``skill >= 1`` gate in
  ``_roll_cast_success``. This rewrite is therefore purely structural
  (matching exactly what ``R_HPlan`` itself checks before ever
  reaching ``Has_SA``'s own effect, i.e. self-target + ordinal range);
  the resulting ``CastRequest``, once dispatched, is subject to that
  same pre-existing generic skill gate like every other Cast -- no
  stricter and no weaker than the rest of this project's own
  secret-spell modeling.
- ``lextra[m]:= 0``: the rewrite unconditionally **zeroes the
  resulting Cast's target field**, regardless of which of the 10
  secret spells it is -- even for Scar Terrain/Mystic Winds/Locate
  Object, which ``cast_decode.py`` documents as needing a real
  province/character/item target when cast the ordinary way. This is
  exactly what the source says, not a simplification of it: a
  Trade->Cast rewrite of one of those three will decode as a
  zero-target ``CastRequest`` and, faithfully, fail at execution the
  same way any other zero-target cast of a targeted spell would.
  Gate Angel (``NO_TARGET_SPELLS``) and Words of Healing/Heal are
  unaffected either way -- see ``ak_engine/turn/cast_decode.py``'s own
  target-shape frozensets for which of the 10 need a real target at
  all.

See ``rewrite_trade_as_secret_spell_cast()`` below.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.enums import Spell, spell_from_int
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.cast_decode import CastRequest

SECRET_SPELL_MIN = Spell.GATE_ANGEL  # 25
SECRET_SPELL_MAX = Spell.ILLUS_HERO  # 34


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


def rewrite_trade_as_secret_spell_cast(phase: PlanPhase, leader_id: int) -> CastRequest | None:
    """``DEF2.PAS R_HPlan``'s ``Trade:`` branch (Phase 397) -- see module docstring
    for the full decoded mechanic. Returns a zero-target ``CastRequest`` for
    ``phase.obj`` when the phase is self-targeted (``phase.extra[0] ==
    leader_id``) and ``phase.obj`` is one of the 10 secret-spell ordinals
    (25-34); ``None`` otherwise, meaning the phase decodes as an ordinary
    Trade (``decode_trade_phase``) instead.

    Deliberately does **not** check ``Has_SA`` (caster ability possession)
    -- see module docstring for why that's consistent with, not weaker
    than, every other secret-spell path already in this project.
    """

    if not phase.extra or phase.extra[0] != leader_id:
        return None
    if not (SECRET_SPELL_MIN <= phase.obj <= SECRET_SPELL_MAX):
        return None
    return CastRequest(spell=spell_from_int(phase.obj), target=0)
