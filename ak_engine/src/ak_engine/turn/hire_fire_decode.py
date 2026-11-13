"""Decoding Hire/Fire PlanPhases (rulebook [3.5] Hire Hero, [3.7] Fire Hero).

Hire and Fire are a **different concept from Recruit's "hiring" of a
mercenary army** (rulebook [3.4]): Hire/Fire operate on independent
*characters* (Heroes) joining or leaving a kingdom's service as a new
leader, not on armies. See ``models/game_state.py``'s nullable
``LeaderState.kingdom_id`` (Phase 17), the leader-side counterpart to
Phase 16's ``ArmyState.kingdom_id``.

Sourced from ``HostAK/TP/CTBOTH.PAS:98-102`` (the ``action`` enum: ``Hire``
= ordinal 5, ``Fire`` = ordinal 6, matching this project's
``ActionCode``) and ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``:

- **Hire**: ``obj`` is the target Hero's character id, and ``lextra[m]``
  (this project's ``PlanPhase.extra[0]``) is the gold offer -- rulebook
  [3.5]: "The character offers a payment of 1-4 gold to the Hero."
  Validated against real data: all 10 real HIRE phases across the sample
  ``AK3__T*.K1`` files have ``extra[0]`` in ``{1, 2, 3, 4}``, matching
  exactly.
- **Fire**: ``obj`` is the target Hero's character id. Unlike every other
  action in ``R_HPlan``/``W_HPlan``, Fire has **no ``CASE`` branch at
  all** -- it reads/writes only the bare ``(action, obj, extra)`` triple,
  no extra list. **Zero real FIRE phases exist in the 10 sample
  ``AK3__T*.K1`` files**, so this is inferred from the Pascal structure
  alone, not independently confirmed by real data the way Hire's decoding
  is.

**A structural complication this module itself does NOT handle**: when a
Hire phase isn't a segment's last phase (``m < 4``), the Pascal
writer/reader immediately embeds a full nested plan block for the
newly-hired Hero's own future orders, spliced into the token stream right
after the Hire phase's triple (``DEF2.PAS``'s ``Read_HPlan``/``W_HPlan``,
called from inside the ``Hire`` ``CASE`` branch when ``m < 4``). This
module only decodes a single already-parsed ``PlanPhase``'s own
``obj``/``extra`` -- the recursion itself is ``parser/k1_moves.py``'s own
job, via ``_maybe_parse_nested_plan()`` and ``PlanPhase.nested_plan``
(fixed in Phase 18, dispatched in Phase 32; see ``models/plan.py``'s own
"Nested plans (Phase 18)" docstring addendum).
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.plan import PlanPhase
from ak_engine.turn.decode_utils import phase_extra0


@dataclass(slots=True)
class HireRequest:
    hero_id: int  # phase.obj -- the target Hero's character id
    gold_offer: int  # phase.extra[0] -- rulebook [3.5]: 1-4 gold


@dataclass(slots=True)
class FireRequest:
    hero_id: int  # phase.obj -- the target Hero's character id


def decode_hire_phase(phase: PlanPhase) -> HireRequest:
    """Decode a Hire PlanPhase's target Hero id and gold offer."""

    return HireRequest(hero_id=phase.obj, gold_offer=phase_extra0(phase))


def decode_fire_phase(phase: PlanPhase) -> FireRequest:
    """Decode a Fire PlanPhase's target Hero id."""

    return FireRequest(hero_id=phase.obj)
