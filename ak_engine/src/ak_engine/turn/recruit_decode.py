"""Decoding a Recruit PlanPhase (rulebook [3.4]).

Sourced from ``HostAK/TP/DEF2.PAS``'s ``Read_HPlan`` (around line 598):
for a Recruit action, the object field (``lobjects[m]``) is a leader id
("Any character in the province may lead the armies, or they can be
placed under the garrison commander" -- ``NO_LEADER_SENTINEL`` for the
latter), and the requested army types are a separate, ``-1``-terminated
list read in "AT_Bytes" mode, appearing in this project's parser as the
tail of ``PlanPhase.extra`` (after ``extra[0]``, whose value is always
``0`` in every sample seen and whose meaning is otherwise unconfirmed).

Validated against real data: every ``AK3__T*.K1`` Recruit phase's
army-type ordinals decode to a known ``ArmyType`` with no out-of-range
values (see ``models.army_type.ARMY_TYPE_BY_ORDINAL``'s docstring).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.army_type import ARMY_TYPE_BY_ORDINAL, NO_LEADER_SENTINEL, ArmyType
from ak_engine.models.plan import PlanPhase


@dataclass(slots=True)
class RecruitRequest:
    leader_id: int | None  # None means "no specific leader" (NO_LEADER_SENTINEL)
    army_types: list[ArmyType] = field(default_factory=list)
    unmapped_ordinals: list[int] = field(default_factory=list)  # values with no known ArmyType


def decode_recruit_phase(phase: PlanPhase) -> RecruitRequest:
    """Decode a Recruit PlanPhase's target leader and requested army types."""

    leader_id = None if phase.obj == NO_LEADER_SENTINEL else phase.obj

    ordinals = list(phase.extra[1:])  # extra[0] is the unconfirmed always-0 field
    if ordinals and ordinals[-1] == -1:
        ordinals = ordinals[:-1]

    army_types: list[ArmyType] = []
    unmapped: list[int] = []
    for ordinal in ordinals:
        army_type = ARMY_TYPE_BY_ORDINAL.get(ordinal)
        if army_type is None:
            unmapped.append(ordinal)
        else:
            army_types.append(army_type)

    return RecruitRequest(leader_id=leader_id, army_types=army_types, unmapped_ordinals=unmapped)
