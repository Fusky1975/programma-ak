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
"where can it go" and "what happens if it can't".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.map import HexCoord
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import MapBounds, neighbors

NON_IMPROVING_QUALITIES = frozenset({Quality.GREEN, Quality.DEPLETED})


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


@dataclass(slots=True)
class RetreatResult:
    destination: HexCoord | None
    retreating_units: list[BattleUnit] = field(default_factory=list)
    disbanded_units: list[BattleUnit] = field(default_factory=list)  # lost, into the population
    mercenary_units: list[BattleUnit] = field(default_factory=list)  # unhireable this gameturn


def resolve_retreat(
    units: list[tuple[BattleUnit, Quality]],
    current: HexCoord,
    bounds: MapBounds,
    friendly_provinces: set[HexCoord],
) -> RetreatResult:
    """Retreat to a friendly neighbor if one exists; otherwise disband/mercenary by quality."""

    destination = find_retreat_destination(current, bounds, friendly_provinces)
    if destination is not None:
        return RetreatResult(destination=destination, retreating_units=[unit for unit, _ in units])

    disbanded = [unit for unit, quality in units if quality in NON_IMPROVING_QUALITIES]
    mercenaries = [unit for unit, quality in units if quality not in NON_IMPROVING_QUALITIES]
    return RetreatResult(destination=None, disbanded_units=disbanded, mercenary_units=mercenaries)
