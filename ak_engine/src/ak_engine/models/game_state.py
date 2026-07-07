"""Persistent, mutable game-state containers.

Every module through Phase 8 operates on caller-supplied snapshots (lists
of ``BattleUnit``, raw ``HexCoord``/``MapBounds`` parameters, etc.) -- none
of them remember anything across calls. This module is the first actual
session state: kingdoms, armies, and provinces that persist across turns
and battles, for ``turn/battle_orchestrator.py`` to read and mutate.

Intentionally minimal -- just enough to orchestrate a battle end-to-end.
Not a full game database: no leader/action-plan integration (Phase 1's
``models.kingdom.Kingdom`` is a parsed *move submission*, a different
concept from the persistent kingdom here), no diplomacy/treaty tracking
beyond a flat alliance set, no turn-history log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality


@dataclass(slots=True)
class KingdomState:
    kingdom_id: int
    name: str
    race: Race
    alignment: Alignment
    home_province: HexCoord
    treasury: int = 0


@dataclass(slots=True)
class ArmyState:
    army_id: int
    kingdom_id: int
    army_type: ArmyType
    quality: Quality
    location: HexCoord
    unhireable_this_turn: bool = False


@dataclass(slots=True)
class ProvinceState:
    coord: HexCoord
    terrain: Terrain
    race: Race
    owner_kingdom_id: int | None = None
    explored_percent: int = 0
    contested_by_kingdom_id: int | None = None


@dataclass(slots=True)
class GameState:
    turn_number: int = 1
    kingdoms: dict[int, KingdomState] = field(default_factory=dict)
    provinces: dict[HexCoord, ProvinceState] = field(default_factory=dict)
    armies: dict[int, ArmyState] = field(default_factory=dict)
    allied_kingdoms: set[frozenset[int]] = field(default_factory=set)

    def add_kingdom(self, kingdom: KingdomState) -> None:
        self.kingdoms[kingdom.kingdom_id] = kingdom

    def add_province(self, province: ProvinceState) -> None:
        self.provinces[province.coord] = province

    def add_army(self, army: ArmyState) -> None:
        self.armies[army.army_id] = army

    def remove_army(self, army_id: int) -> None:
        self.armies.pop(army_id, None)

    def armies_at(self, coord: HexCoord) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.location == coord]

    def is_allied(self, kingdom_a: int, kingdom_b: int) -> bool:
        if kingdom_a == kingdom_b:
            return True
        return frozenset({kingdom_a, kingdom_b}) in self.allied_kingdoms

    def friendly_provinces_for(self, kingdom_id: int) -> set[HexCoord]:
        """Provinces owned by ``kingdom_id`` or one of its allies."""

        return {
            province.coord
            for province in self.provinces.values()
            if province.owner_kingdom_id is not None and self.is_allied(province.owner_kingdom_id, kingdom_id)
        }
