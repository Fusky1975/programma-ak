"""Decoding Disband/Leave/Pick_Up PlanPhases (rulebook [3.6], [3.8], [3.9]).

Sourced from ``HostAK/TP/DEF2.PAS``'s ``Read_HPlan`` (~line 590): all
three actions share one branch, reading a ``-1``-terminated army-id list
in "AN_Bytes" mode into ``PlanPhase.extra`` (after ``extra[0]``). For
LEAVE specifically, the Pascal comments confirm ``extra[0]`` is a target
leader id ("IF lactions[m] = Leave THEN lextra[m]:= noleader" -- defaulted
only for LEAVE, in old-format files), matching the rulebook: "you may
leave your armies to garrison the province, or give them to another
leader". ``obj`` is always ``0`` in every real sample for all three
actions; its meaning, if any, is unconfirmed.

Validated against real data: every LEAVE phase across all 10
``AK3__T*.K1`` files decodes to a target leader id (or
``NO_LEADER_SENTINEL``) followed by either a specific army-id list or a
lone ``255``, read here as ``ALL_ARMIES_SENTINEL`` -- matching the
rulebook's "(LE)ave All" / "(DI)sband All" / "(PI)ck Up All" keywords.
Only one real DISBAND example exists in the sample data, and **no**
PICK_UP examples at all, so DISBAND/PICK_UP decoding follows the same
structure by inference from the shared Pascal code path, not independent
confirmation the way LEAVE's is.

This module only decodes the request -- it does not apply it to
``GameState``. See ``turn/plan_dispatch.py`` for why: Disband would need
a way to represent an unowned mercenary army (``ArmyState.kingdom_id``
isn't nullable), and Leave/Pick_Up would need a leader-to-army command
model this project doesn't have yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.army_type import NO_LEADER_SENTINEL
from ak_engine.models.plan import PlanPhase

ALL_ARMIES_SENTINEL = 255


@dataclass(slots=True)
class ArmyListRequest:
    """Decoded Disband/Leave/Pick_Up target: a leader (meaningful for Leave only) and army ids."""

    target_leader_id: int | None  # None means NO_LEADER_SENTINEL was given
    army_ids: list[int] = field(default_factory=list)
    all_armies: bool = False  # True if the list was the lone ALL_ARMIES_SENTINEL


def decode_army_list_phase(phase: PlanPhase) -> ArmyListRequest:
    """Decode a Disband/Leave/Pick_Up PlanPhase's target leader and army list."""

    values = list(phase.extra)
    if not values:
        return ArmyListRequest(target_leader_id=None, army_ids=[], all_armies=False)

    leader_raw = values[0]
    target_leader_id = None if leader_raw == NO_LEADER_SENTINEL else leader_raw

    ids = values[1:]
    if ids and ids[-1] == -1:
        ids = ids[:-1]

    if ids == [ALL_ARMIES_SENTINEL]:
        return ArmyListRequest(target_leader_id=target_leader_id, army_ids=[], all_armies=True)

    return ArmyListRequest(target_leader_id=target_leader_id, army_ids=ids, all_armies=False)
