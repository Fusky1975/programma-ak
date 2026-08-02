"""Map shape-goal and latitude-weighted terrain draw (Phase 353).

Second phase of the ``AKGEN.EXE`` world-generation sub-plan (see Phase
352's ``pascal_random.py`` for the RNG this builds on). Source:
``world_generation.random_terrain`` in the AKGEN disassembly JSON
(routines ``place_map`` 0006:41FB, ``terrain_picker`` 0B57:92BA,
``latitude_mapper`` 0B57:9461).

**Confirmed exactly** and implemented here:

- ``shape_goal_formula``: ``(cell_count div 2) + king_count +
  (king_count div 2) - (IRand mod king_count)``. Verified against the
  source's own declared default (18x9 map, ``cell_count=162``,
  ``king_count=10``): ``81 + 10 + 5 - [0..9]`` = ``[87, 96]``, exactly
  matching the source's own ``shape_goal_min``/``shape_goal_max``.
- ``main_land_threshold = shape_goal div 2``. For ``[87, 96]`` this
  gives ``[43, 48]``, exactly matching the source's own
  ``main_land_threshold_min``/``main_land_threshold_max``.
- ``default_latitude_weights_before_sea_rejection``: for each of 5
  latitude bands, a 0..100 weight per terrain (Plains/Desert/Jungle/
  Forest/Mountains/Sea) the real ``terrain_picker`` draws from.
  Cross-checked against the source's own *separate*
  ``conditional_percent_when_placing_land`` table (the same weights
  with Sea excluded and rescaled to 100): e.g. band 0's land weights
  (6+0+0+17+7=30) rescale to Plains 20.0%/Forest 56.667%/Mountains
  23.333%, exactly matching that table's own declared numbers for
  every band -- confirming both tables describe the same underlying
  distribution rather than being independent, reconcilable data.
- ``band_formula_default_map``: ``min(y, bottom_y - y)`` maps a map
  row to one of the 5 latitude bands (symmetric north/south).

**Terrain enum note**: the source's own ``terrain_enum`` has 9
members (0=Plains .. 6=noterr, plus 7=Swamp, 8=Lava) where this
project's existing ``ak_engine.models.map.Terrain`` has 7 (0..6) --
another exact cross-validation for the members it does have. Swamp
and Lava are deliberately *not* added here: they never appear in any
of the ``random_terrain`` weight tables above (every band's weights
cover only Plains/Desert/Jungle/Forest/Mountains/Sea), so they are
unreachable through this generator and are presumably reserved for
the fixed Europe/Earth maps this project doesn't parse -- extending
the enum is left out of scope rather than guessed at.

**What's deliberately NOT implemented here**: the full spatial
``place_map`` pipeline (place 3 random land seeds, add random sea
cells until ``main_land_threshold``, ``2*king_count`` additional land
attempts, iterative six-hex-neighbor sea-hole filling, regeneration if
``bottom_y=8`` and land count exceeds ``final_land_hard_max=90``).
The source describes these as a narrative sequence of steps, not
exact reproducible algorithms (which cells are chosen, in what order,
how "add until threshold" picks a cell) -- implementing that fully
would require inventing unsourced spatial-selection logic, which this
project avoids. Only the two fully-specified, verifiable formulas
(the shape-goal/threshold counts) and the terrain-per-cell weighted
draw (independent of *which* cells get chosen) are implemented.
"""

from __future__ import annotations

from ak_engine.models.map import Terrain
from ak_engine.worldgen.pascal_random import PascalRandom

DEFAULT_CELL_COUNT = 162
DEFAULT_KING_COUNT = 10

# band -> {Terrain: weight}, weights sum to 100 per band.
LATITUDE_TERRAIN_WEIGHTS: dict[int, dict[Terrain, int]] = {
    0: {
        Terrain.PLAINS: 6,
        Terrain.DESERT: 0,
        Terrain.JUNGLE: 0,
        Terrain.FOREST: 17,
        Terrain.MTNS: 7,
        Terrain.SEA: 70,
    },
    1: {
        Terrain.PLAINS: 8,
        Terrain.DESERT: 5,
        Terrain.JUNGLE: 0,
        Terrain.FOREST: 10,
        Terrain.MTNS: 7,
        Terrain.SEA: 70,
    },
    2: {
        Terrain.PLAINS: 7,
        Terrain.DESERT: 13,
        Terrain.JUNGLE: 0,
        Terrain.FOREST: 3,
        Terrain.MTNS: 7,
        Terrain.SEA: 70,
    },
    3: {
        Terrain.PLAINS: 7,
        Terrain.DESERT: 5,
        Terrain.JUNGLE: 11,
        Terrain.FOREST: 0,
        Terrain.MTNS: 7,
        Terrain.SEA: 70,
    },
    4: {
        Terrain.PLAINS: 5,
        Terrain.DESERT: 3,
        Terrain.JUNGLE: 15,
        Terrain.FOREST: 0,
        Terrain.MTNS: 7,
        Terrain.SEA: 70,
    },
}


def shape_goal(cell_count: int, king_count: int, rng: PascalRandom) -> int:
    """``(cell_count div 2) + king_count + (king_count div 2) - (IRand mod king_count)``."""

    return (cell_count // 2) + king_count + (king_count // 2) - (rng.irand() % king_count)


def main_land_threshold(goal: int) -> int:
    """``shape_goal div 2``."""

    return goal // 2


def band_for_row(y: int, bottom_y: int) -> int:
    """``min(y, bottom_y - y)`` -- symmetric latitude band index for map row ``y``."""

    return min(y, bottom_y - y)


def draw_terrain(band: int, rng: PascalRandom) -> Terrain:
    """Weighted terrain draw for one map cell in the given latitude band."""

    weights = LATITUDE_TERRAIN_WEIGHTS[band]
    total = sum(weights.values())
    roll = rng.irand() % total
    cumulative = 0
    for terrain, weight in weights.items():
        cumulative += weight
        if roll < cumulative:
            return terrain
    return Terrain.SEA
