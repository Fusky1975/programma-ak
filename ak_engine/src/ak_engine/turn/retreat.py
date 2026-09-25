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
