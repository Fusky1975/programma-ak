"""Hire Hero's required-pay formula -- Phase 162.

**Confirmed absent from the surviving Pascal source** (Phase 161,
``turn/plan_dispatch.py``'s own note): `LCost`, the one identifier tied
to a Hero's required/per-turn pay, is called but never *defined* in any
of the 13 available ``.PAS`` files. No exact formula survives to
transcribe. This module instead implements a formula the user
explicitly asked this project to design (2026-07-15), built from two
real, authoritative sources rather than guessed from nothing:

1. **The player's manual** (``Regolamento AK.txt``-class source, quoted
   directly by the user, not this project's own invention): "Il soldo
   richiesto varia in base al maggiore o minore gradimento che l'Eroe
   nutre nei confronti di un determinato Reame... Può tornare utile che
   l'Eroe abbia lo stesso Temperamento... e sia di analogo Allineamento
   del Re. In rare occasioni un Re può assoldare Eroi con un
   Allineamento distante più di due posizioni dal proprio (ad esempio
   un Re Buono generalmente non può assoldare un Eroe Pagano)." The
   user's own instruction narrowed the algorithm's real inputs to
   exactly two -- alignment distance and temperament match -- leaving
   race out of the formula even though the manual also mentions it
   ("può tornare utile"); `LeaderState` has no `.race` field to source
   race from anyway.
2. **One hard, real data point**: "a Good King generally cannot hire a
   Pagan Hero" is only true, using the real Pascal ``outlook`` ordinal
   sequence (``models/alignment.py ALIGNMENT_ORDINAL``, not this
   project's own ``Alignment`` declaration order), at distance
   ``|1 - 4| = 3``. This anchors the formula's top bucket.

**The formula** (``required_pay()``): an integer 1-5, matching the
user's own explicit range (the Hire action can offer at most 4 gold;
5 means the Hero is unhireable except via Charm or after being killed
and Resurrected -- the user's own stated constraint, not modeled here
since Charm/Resurrection already exist as separate mechanics
elsewhere in this project, ``turn/cast_execution.py``).

    base_pay = {0: 1, 1: 2, 2: 3}.get(align_distance, 5)
    pay = base_pay + (1 if align_distance >= 1 and not same_temper else 0)
    pay = min(5, pay)

Distance 0/1/2 sets a base of 1/2/3 gold; distance >=3 jumps straight
to 5 regardless of temper, deliberately skipping 4, so the real anchor
case (distance 3) reproduces exactly as "generally cannot hire" (5
gold, above the 4-gold offer ceiling) rather than merely "expensive."

**Phase 163 revises temper's own weight** (user feedback, 2026-07-15:
"il temperamento deve contare meno della differenza di allineamento...
direi della metà" -- temperament must count for less than alignment
distance, about half). Phase 162's original formula added a flat +1
for a temper mismatch unconditionally, giving it the exact same
per-step weight as one full alignment-distance step -- not "half" of
anything. Since a Hero's temper is a boolean match/mismatch (not
itself a distance with intermediate steps), there is no fractional
gold to charge for "half a step"; instead, temper is demoted to a
*secondary amplifier* that only matters when some alignment friction
already exists (``align_distance >= 1``) -- a temper mismatch never
raises the price on its own when alignment already matches exactly
(``align_distance == 0``). This halves temper's practical influence
in the cleanest available integer-gold sense: it now affects 2 of the
3 non-unhireable distance brackets instead of all 3, and even then
only by the same +1 as before, rather than trying to approximate a
literal "0.5 gold" through rounding tricks. A King's own real
alignment/temper (``KingdomState.alignment`` for alignment; there is
no ``KingdomState.temper``, only per-leader ``LeaderState.temper``, so
the King's own ``LeaderState`` is looked up separately -- see
``turn/plan_dispatch.py``'s own King-lookup idiom,
``battle_orchestrator.py``'s ``is_king`` search) are compared against
the Hero's own ``LeaderState.alignment``/``.temper``.

**Missing data defaults to the most permissive outcome** (distance 0,
matching temper -- pay 1), the same convention this project already
uses for ``skills``/``birth_x``/etc.: a Hero or King with no recorded
alignment/temper isn't penalized for data this project simply hasn't
populated yet.
"""

from __future__ import annotations

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.game_state import LeaderState

_BASE_PAY_BY_DISTANCE: dict[int, int] = {0: 1, 1: 2, 2: 3}
_UNHIREABLE_PAY = 5


def _alignment_distance(hero_alignment: Alignment | None, king_alignment: Alignment | None) -> int:
    if hero_alignment is None or king_alignment is None:
        return 0
    return abs(ALIGNMENT_ORDINAL[hero_alignment] - ALIGNMENT_ORDINAL[king_alignment])


def required_pay(hero: LeaderState, king: LeaderState | None) -> int:
    """The gold-per-annum a Hero requires to enter a King's service.

    ``king`` is the kingdom's own ``LeaderState`` with ``is_king=True``
    (``None`` if no King is currently recorded for the kingdom, e.g. an
    interregnum this project doesn't model separately -- treated as
    "no data," the same permissive default as a missing alignment or
    temper below).
    """

    hero_alignment = hero.alignment
    king_alignment = king.alignment if king is not None else None
    distance = _alignment_distance(hero_alignment, king_alignment)
    if distance >= 3:
        return _UNHIREABLE_PAY

    hero_temper = hero.temper
    king_temper = king.temper if king is not None else None
    same_temper = hero_temper is None or king_temper is None or hero_temper is king_temper

    base_pay = _BASE_PAY_BY_DISTANCE[distance]
    # Temper only amplifies existing alignment friction (Phase 163) --
    # a mismatch alone, with matching alignment, never raises the price.
    penalty = 1 if distance >= 1 and not same_temper else 0
    return min(_UNHIREABLE_PAY, base_pay + penalty)
