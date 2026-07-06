"""Per-leader action plan model.

A move file encodes, per leader, one or more "segments": an ``AP:``/``SP:``
header followed by up to five phases (``P0``..``P4``). The Pascal source
(``CTBOTH.PAS`` ``planrec``, lines 1586-1601) has matching ``planstart``/
``planend`` fields, which is almost certainly what the two ``AP:`` integers
mean. The meaning of ``SP:`` is not yet confirmed against the Pascal source
and is kept as a raw tuple pending further reverse-engineering.
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
    extra: list[int] = field(default_factory=list)


@dataclass(slots=True)
class PlanSegment:
    """One ``AP:``/``SP:``/``P0..P4`` group within a leader's move block."""

    plan_start: int
    plan_end: int
    sp: tuple[int, ...]
    phases: dict[str, PlanPhase] = field(default_factory=dict)


@dataclass(slots=True)
class ActionPlan:
    """Full set of move segments submitted for one leader in one turn."""

    leader_id: int
    segments: list[PlanSegment] = field(default_factory=list)
