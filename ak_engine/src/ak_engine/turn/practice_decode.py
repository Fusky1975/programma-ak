"""Decoding a Practice PlanPhase (rulebook [3.13] Practice Ability).

Sourced from ``HostAK/TP/CTBOTH.PAS`` (``action`` enum: ``Practice`` =
ordinal 12, matching this project's ``ActionCode.PRACTICE``) and
``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``: Practice has **no**
``CASE``-specific branch at all (unlike Search/Trade/Hire/Recruit/etc.),
so it's read/written as the bare generic ``(action, obj, extra)`` triple
with no extra payload:

- ``obj`` (``lobjects[m]``) is the ``Ability`` ordinal (0-14) being
  practiced -- maps directly onto this project's existing ``Ability``
  enum, no new decoding needed.
- ``extra`` carries no meaning for Practice -- confirmed by real data:
  all 189 real Practice phases across the 10 sample ``AK3__T*.K1`` files
  have ``extra == [0]``, none higher, none a list.

Rulebook [3.13], summarized (quoted in full in ``README.md``): practicing
an ability with another co-located character practicing the *same*
ability in the *same phase* raises the lower-skilled character(s) by 1
level (or a 10% chance each if tied); practicing alone is a flat 5%
chance. The rise chance is halved for each level beyond the character's
aptitude, and a blocked rise has its own (skill-level-dependent) chance
of raising aptitude instead. None of this percentage machinery is
decoded or resolved here -- see the module-level "not yet implemented"
note below.

**Two special-cased abilities, per the rulebook, worth flagging even at
decode time** (real data confirms both are actually practiced -- SAGE
140/189 times, no real TACTICAL example in this sample but documented
nonetheless):

- **Tactical** (rulebook [6.1]): practicing Tactical does **not** raise
  the leader's own skill via [3.13] at all -- it trains the leader's
  *armies* instead, rolling each army's quality tier upward (e.g.
  Green->Average 25%, Crack->Elite 0.2%) if a higher-quality army is
  present to "train and inspire" it. A completely different mechanic
  from every other ability.
- **Sage** (rulebook [4.31]): practicing Sage additionally rolls an
  independent ~5%-per-level chance of a "device discovery", on top of
  (not instead of) the normal [3.13] skill-rise roll.

**Decode-only, itself** -- this module only turns a raw ``PlanPhase``
into a ``PracticeRequest``. **Stale as of Phase 44/46/167** -- this
paragraph used to say resolving what a Practice phase actually *does*
needed three things this project didn't have yet: a per-leader
``SkillTable`` in persistent ``GameState`` (``LeaderState.skills``, a
fresh all-zero table created on demand for a Hero with none recorded),
province-level grouping of every co-located character's same-phase
action (``turn/turn_processor.py``'s own ``practice_groups`` detection,
Phase 46, routing 2+ co-located same-ability practicers through
``turn/practice_execution.py execute_practice_group()``), and the
dice-roll procedure itself (``turn/practice_execution.py``'s own
skill/aptitude-rise tables, Tactical/Naval's [6.1] army-training
mechanic, and Sage's own independent device-discovery roll,
``_roll_sage_device_discovery()`` -- see that module's own docstring
for the full, since-disassembly-confirmed formulas). All of it has
existed for a long time; only this decode step stayed this narrow.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.plan import PlanPhase


@dataclass(slots=True)
class PracticeRequest:
    ability: Ability | int  # phase.obj -- an out-of-range value is kept raw rather than raising


def decode_practice_phase(phase: PlanPhase) -> PracticeRequest:
    """Decode a Practice PlanPhase's target ability."""

    try:
        ability: Ability | int = Ability(phase.obj)
    except ValueError:
        ability = phase.obj
    return PracticeRequest(ability=ability)
