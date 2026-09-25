"""Retreat and disbandment (rulebook [7.4]).

"If the defeated army has little hope of winning a second battle, it will
retreat into an adjacent friendly province. If retreat is impossible,
Green and Depleted units will be disbanded into the population, while
Average and better units may disband into mercenaries, usually marching
a few provinces away from their attackers at the end of the turn. You can
not hire them that gameturn... If the attacker was forced to retreat, his
armies must retreat into the same province they invaded from, or a
province adjacent to the province they invaded from."

Deciding *whether* a defeated army retreats at all ("little hope of
winning a second battle") depends on factors [7.5] lists only
qualitatively (capital status, wealth, retreat path, etc.) with no
formula -- that decision is left to the caller. This module only answers
"where can it go".

**Phase 900**: this module used to also answer "what happens if it
can't" (``RetreatResult``/``resolve_retreat()``), but that higher-level
orchestration was confirmed dead, superseded code -- a zero-caller sweep
(grepped both `resolve_retreat(` and the bare name `resolve_retreat`
across all of `src/`) found no real caller anywhere outside its own
definition and its own dedicated unit tests. `turn/battle_orchestrator.py
_retreat_or_disband()` is the real production orchestrator (multiple
call sites, all wired since well before this project reached its current
phase count): it already reimplements the identical GREEN/DEPLETED-
disband-vs-Average+-mercenary split directly against live `GameState`/
`ArmyState` (quality changes, `unhireable_this_turn`, battle-death
recording, an `avoid_elimination` carve-out), richer than the
`RetreatResult` snapshot this module's own version returned. Removed
outright, along with its own 2 dedicated tests; `find_retreat_
destination()`/`attacker_retreat_candidates()` below are untouched --
both are still real, tested, and actively used by `battle_orchestrator.py`
directly.
"""

from __future__ import annotations

from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import MapBounds, neighbors


def find_retreat_destination(current: HexCoord, bounds: MapBounds, friendly_provinces: set[HexCoord]) -> HexCoord | None:
    """First adjacent province the retreating side owns/is friendly with, or None."""

    for candidate in neighbors(current, bounds):
        if candidate in friendly_provinces:
            return candidate
    return None


def attacker_retreat_candidates(invaded_from: HexCoord, bounds: MapBounds) -> list[HexCoord]:
    """Valid destinations for an attacker forced to retreat: the province it
    invaded from, or one adjacent to that province."""

    return [invaded_from, *neighbors(invaded_from, bounds)]


def select_attacker_retreat_destination(
    invaded_from: HexCoord,
    current: HexCoord,
    bounds: MapBounds,
    friendly_provinces: set[HexCoord],
) -> HexCoord | None:
    """The real destination for an attacker forced to retreat (rulebook
    [7.4], "his armies must retreat into the same province they invaded
    from, or a province adjacent to the province they invaded from"):
    the first candidate from ``attacker_retreat_candidates`` -- the
    invaded-from province itself, then its neighbors, in that fixed
    order -- that is actually in ``friendly_provinces`` *and* isn't
    ``current`` itself, falling back to ``find_retreat_destination``
    from ``current`` (the just-vacated battlefield) if none of them are.
    ``current`` is excluded unconditionally here, regardless of what
    ``friendly_provinces`` contains -- see point 2 below for why a
    caller can't be trusted to always remember to exclude it upstream.

    **Phase 912**: `battle_orchestrator.py` used to consume
    ``attacker_retreat_candidates`` by always taking candidate ``[0]``
    (``invaded_from`` itself) with no validity check at all. Two real
    gaps that left open, not just an unsourced tie-break preference
    among equally-valid candidates:

    1. If a third Kingdom captured ``invaded_from`` earlier the same
       turn (a real possibility -- nothing prevents another Kingdom's
       own conquest from landing on a Kingdom's home province the same
       turn its army is off invading elsewhere), "retreating" there
       handed the army straight to an enemy instead of actually
       retreating.
    2. ``invaded_from`` and ``current`` (the battlefield) are adjacent
       by definition -- the army marched from one to the other -- so
       ``current`` was always structurally present in
       ``neighbors(invaded_from, ...)``'s own candidate list. Nothing
       excluded it, so the battlefield the army is fleeing *from* could
       itself be picked as its own "valid" retreat destination.

    Gap 1 is closed the same way the ``attacker_origin is None`` branch
    already handled friendliness: filter every candidate against a real
    ``friendly_provinces`` set (which the caller builds the same way in
    both branches) before accepting one. Gap 2 is closed unconditionally
    inside this function itself, rather than trusted to every call
    site's own ``friendly_provinces`` construction -- ``current`` is
    never a valid destination regardless of its ownership, since it's
    the province the army is retreating *from*, not to. Neither is a
    new, invented tie-break rule among several equally-good
    rulebook-sanctioned choices (the rulebook still names no "best" one,
    and none is invented here either) -- both apply a validity standard
    this project's own general retreat path already used elsewhere, to
    the one path that hadn't been.
    """

    for candidate in attacker_retreat_candidates(invaded_from, bounds):
        if candidate != current and candidate in friendly_provinces:
            return candidate
    return find_retreat_destination(current, bounds, friendly_provinces)
