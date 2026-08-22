"""Per-leader action plan model.

A move file encodes, per leader, one or more "segments": an ``AP:``/``SP:``
header followed by up to five phases (``P0``..``P4``). The Pascal source
(``CTBOTH.PAS`` ``planrec``, lines 1586-1601) has matching ``planstart``/
``planend`` fields, which is almost certainly what the two ``AP:`` integers
mean. The meaning of ``SP:`` is not yet confirmed against the Pascal source
and is kept as a raw tuple pending further reverse-engineering.

**Nested plans (Phase 18)**: per ``HostAK/TP/DEF2.PAS`` (~line 505, "IF m <
4 THEN R_HPLan(...)"), whenever a phase in position ``P0``-``P3`` (never
``P4``) causes a new character to join the kingdom this turn -- Hire
(rulebook [3.5]) is the confirmed case; the Charm/Resurrection spells do
the same per ``Read_More``, ~line 510 -- the move file immediately embeds
that character's own complete ``AP:``/``SP:``/``P<n>..P<m>`` plan in the
token stream, before the triggering phase's own segment continues with
its next label. ``PlanPhase.nested_plan`` holds that embedded
``ActionPlan``, parsed by ``parser/k1_moves.py``. Confirmed structurally
against real data: every one of the 10 sample ``AK3__T*.K1`` files has
exactly one top-level segment per leader (no genuine sibling AP: blocks
ever follow a ``P4`` phase) -- what earlier looked like "multi-segment
leaders" (``AK3__T3.K1``, ``AK3__T10.K1``) were this nesting,
mis-flattened by the parser before this fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.enums import ActionCode


@dataclass(slots=True)
class PlanPhase:
    """One ``P0``..``P4`` phase within a plan segment."""

    label: str
    action: ActionCode | int
    obj: int
    # Phase 618: widened from `list[int]` -- a Search phase's own `SAY`
    # tactic (`turn/search_decode.py`) carries a free-text argument, not
    # a numeric one (see `parser/k1_moves.py`'s own Phase 618 addendum
    # for how it's recovered). Every other action type still only ever
    # produces `int` elements here; each `turn/*_decode.py` decoder only
    # ever reads phases of its own action type, so this widening is safe
    # for every existing consumer.
    extra: list[int | str] = field(default_factory=list)
    # An embedded plan for a character who joined the kingdom this phase
    # (Hire, or a Charm/Resurrection Cast) -- see module docstring. None
    # for the overwhelming majority of phases, which don't trigger this.
    nested_plan: "ActionPlan | None" = None


@dataclass(slots=True)
class PlanSegment:
    """One ``AP:``/``SP:``/``P0..P4`` group within a leader's move block."""

    plan_start: int
    plan_end: int
    sp: tuple[int, ...]
    phases: dict[str, PlanPhase] = field(default_factory=dict)


@dataclass(slots=True)
class ActionPlan:
    """Full set of move segments submitted for one leader (or, when nested
    inside a ``PlanPhase``, one newly-joined character) in one turn.

    ``leader_id`` is a real id for a Hire-triggered nesting (Hire's own
    ``obj`` field *is* the target character's id, rulebook [3.5]) and for
    a Cast-triggered nesting specifically from Charm or Resurrection
    (Phase 23: the spell's own target, ``extra[0]``, is the character
    being charmed/resurrected -- see ``turn/cast_decode.py``). It's
    ``None`` for any other Cast that happens to structurally trigger
    nesting (no other spell is documented to do so, but the parser
    doesn't hard-code that -- see ``parser/k1_moves.py
    _maybe_parse_nested_plan``) or for any nesting this project simply
    has no owning-character id for.
    """

    leader_id: int | None
    segments: list[PlanSegment] = field(default_factory=list)
