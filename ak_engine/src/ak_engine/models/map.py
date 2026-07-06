"""Map/terrain model.

The terrain enum and per-terrain "Basic Exploration Number" are transcribed
from ``HostAK/TP/CTBOTH.PAS`` (``terrain`` enum and ``terexp`` const table,
around line 1210), which matches the "Terrain Table" referenced by the
rulebook's Explore rule (``RULES.AK`` [3.2]). Extension terrains (SWAMP,
LAVA, ET1-5) from the same source enum are omitted here: no game data or
rulebook text references them, so they're left out rather than guessed.

Hex adjacency is NOT sourced from the original program: the code that
computed it lived in the missing main turn-processor and isn't in the
available units. ``ak_engine.turn.movement`` reconstructs a standard
offset-coordinate hex grid from the rulebook's textual description alone;
see that module's docstring for the explicit assumption being made.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Terrain(Enum):
    PLAINS = 0
    DESERT = 1
    JUNGLE = 2
    FOREST = 3
    MTNS = 4
    SEA = 5
    NO_TERRAIN = 6


# "Basic Exploration Number" per terrain (CTBOTH.PAS `terexp`), used by the
# rulebook's Explore action formula: Basic Exploration Number x (Explorer
# skill + 1) % of the province. See ak_engine.turn.exploration.resolve_explore.
TERRAIN_EXPLORATION_NUMBER: dict[Terrain, int] = {
    Terrain.PLAINS: 50,
    Terrain.DESERT: 25,
    Terrain.JUNGLE: 10,
    Terrain.FOREST: 15,
    Terrain.MTNS: 15,
    Terrain.SEA: 25,
    Terrain.NO_TERRAIN: 0,
}


@dataclass(frozen=True, slots=True)
class HexCoord:
    x: int
    y: int


@dataclass(slots=True)
class Feature:
    coord: HexCoord
    terrain: Terrain
    owner_kingdom: int | None = None
    explored_percent: int = 0
