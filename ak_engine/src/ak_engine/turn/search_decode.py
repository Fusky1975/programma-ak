"""Decoding a Search PlanPhase (rulebook [3.3] Search Feature).

Search is structurally unlike Explore ([3.2], ``turn/exploration.py``):
Explore is an untargeted, deterministic percentage roll over the
mover's *own* province, revealing that a feature exists. Search targets
one *already-known* feature by number (possibly in a province the
searcher doesn't own, or hasn't even Explored, if a rumor gave up its
number -- rulebook: "A character may Search a feature... if they know
the location and feature number") and immediately triggers a personal
**Encounter** against that feature's guardian monster (rulebook [5.0]),
resolved via a player-supplied **Encounter Plan**: an ordered list of
combat tactics (Cast, Use Item, Talk, Say, Give, Fulfill, Steal, Shoot,
Melee, Flee, Beg, Scout -- [5.1]-[5.8]).

Sourced from ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``:

- ``obj`` (``lobjects[m]``) is the target feature's number.
- ``tl`` (this project's ``PlanPhase.extra[0]``) is read but has **no**
  ``CASE``-specific use anywhere in ``R_HPlan``/``W_HPlan`` for Search
  (unlike Hire's gold offer) -- and every one of the 12 real Search
  phases across the 10 sample ``AK3__T*.K1`` files has it as ``0``. Kept
  as a raw, unconfirmed field, same convention as Recruit's own
  always-``0`` ``extra[0]`` (see ``turn/recruit_decode.py``).
- The remainder of ``extra`` is a ``-1``-terminated **tactic list**
  (``R_List(..., Tac_Bytes, ...)``): each entry is a ``Maneuver``
  ordinal, and only ``CAST``, ``USE_MI``, and ``GIVE`` are followed by a
  sub-object (a spell id, magic-item id, or gift-item id respectively --
  ``CTBOTH.PAS``'s ``maneuver`` enum / ``W_List``'s ``Tac_Bytes`` mode).

Validated against real data: all 12 real Search phases across the 10
sample files decode to a clean, fully-consumed tactic list (no leftover
or misaligned tokens), using only ``Maneuver`` ordinals ``CAST``(0),
``STEAL``(7), ``SHOOT``(8), ``MELEE``(9), ``FLEE``(10), and ``SCOUT``(13)
-- every real Search order ends in ``Melee`` and/or ``Scout``.

**This module only decodes the request -- it does not resolve a Search's
outcome.** Doing so needs a personal, non-army Encounter/combat resolver
(distinct from ``turn/combat.py``'s battle math, which is for armies)
that this project doesn't have yet, plus the treasure/monster/rumor
content-generation system flagged as out of scope since Explore's own
docstring. A Cast/Use_MI tactic's sub-object is also kept as a raw int:
this project has no decoded spell-id or magic-item-id table yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.enums import Maneuver, maneuver_from_int
from ak_engine.models.plan import PlanPhase

_TACTICS_WITH_SUB_OBJECT = frozenset({Maneuver.CAST, Maneuver.USE_MI, Maneuver.GIVE})


@dataclass(slots=True)
class SearchTactic:
    maneuver: Maneuver | int
    sub_object: int | None = None  # spell/item id -- only set for CAST/USE_MI/GIVE


@dataclass(slots=True)
class SearchRequest:
    feature_id: int  # phase.obj
    unconfirmed_extra0: int  # phase.extra[0] ("tl") -- always 0 in every real sample
    tactics: list[SearchTactic] = field(default_factory=list)


def decode_search_phase(phase: PlanPhase) -> SearchRequest:
    """Decode a Search PlanPhase's target feature and Encounter Plan tactics."""

    values = list(phase.extra)
    extra0 = values[0] if values else 0

    tokens = values[1:]
    if tokens and tokens[-1] == -1:
        tokens = tokens[:-1]

    tactics: list[SearchTactic] = []
    i = 0
    while i < len(tokens):
        maneuver = maneuver_from_int(tokens[i])
        i += 1
        sub_object = None
        if maneuver in _TACTICS_WITH_SUB_OBJECT and i < len(tokens):
            sub_object = tokens[i]
            i += 1
        tactics.append(SearchTactic(maneuver=maneuver, sub_object=sub_object))

    return SearchRequest(feature_id=phase.obj, unconfirmed_extra0=extra0, tactics=tactics)
