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

# "Length of battle line (in #armies)" column of the rulebook's Terrain
# Table ([1.6]) -- resolves the battle-line-length-by-terrain gap flagged
# in ak_engine/README.md. The rulebook gives a range, not a fixed number,
# and doesn't say how the exact value is picked within it; callers should
# roll a value in this range (see turn/battle_line.roll_terrain_line_length_cap)
# rather than always using an endpoint.
TERRAIN_LINE_LENGTH_RANGE: dict[Terrain, tuple[int, int]] = {
    Terrain.PLAINS: (5, 10),
    Terrain.DESERT: (5, 10),
    Terrain.JUNGLE: (3, 6),
    Terrain.FOREST: (3, 6),
    Terrain.MTNS: (1, 3),
    Terrain.SEA: (5, 10),
}

# Display names (CTBOTH.PAS `tername`, the second definition at ~line 1219 --
# the one indexed by *this* module's own `terrain` enum order, distinct from
# an earlier `tername` at ~line 973 that belongs to an unrelated Russian-
# localization-only terrain scheme). Phase 220, following the same
# "RACE_NAME/ARMY_TYPE_NAME sourced display-name dict" precedent (Phases
# 87/90) already established elsewhere in this project.
TERRAIN_NAME: dict[Terrain, str] = {
    Terrain.PLAINS: "Plain",
    Terrain.DESERT: "Desert",
    Terrain.JUNGLE: "Jungle",
    Terrain.FOREST: "Forest",
    Terrain.MTNS: "Mountain",
    Terrain.SEA: "Sea",
    Terrain.NO_TERRAIN: "No Terrain",
}


@dataclass(frozen=True, slots=True)
class HexCoord:
    x: int
    y: int
