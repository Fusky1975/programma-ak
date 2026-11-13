"""Full spatial map assembly (Phase 354): ``AKGEN.EXE``'s ``place_map``.

Phase 353 (``map_shape.py``) implemented the pieces of ``place_map``
that the source gives as exact formulas or exact tables (``shape_goal``,
``main_land_threshold``, the latitude-weighted terrain draw) and left
the *spatial* assembly -- which cells become land, in what order, by
what rule -- as a deliberately undone gap, because the source only
describes it narratively:

    "place 3 random land seeds",
    "add random sea cells until main_land_threshold",
    "perform 2*king_count additional land attempts",
    "iteratively fill enclosed sea holes using six hex neighbors",
    "for bottom_y=8 regenerate if land_count exceeds 90"

**This phase turns that narrative into a concrete, runnable algorithm,
at the user's explicit request, with the explicit understanding that
it is a project-original realization of the source's own steps, not a
recovery of the exact disassembled routine** -- if the real
cell-selection logic is ever recovered (the disassembly addresses are
already known: ``place_map`` 0006:41FB, ``random_branch_flat``
0x45E6), it should replace this module rather than coexist with it.
Every *value* used (the 3-seed count, the ``2*king_count`` attempt
count, the ``final_land_hard_max=90``/``bottom_y=8`` regenerate gate,
the six-hex-neighbor hole rule, the latitude terrain weights) comes
directly from the confirmed source data -- only the specific
cell-selection procedure realizing each step is this project's own
choice, made as literally and minimally as each step's own wording
allows:

- **"place 3 random land seeds"**: repeatedly pick a uniformly random
  cell (via ``PascalRandom.irand() % width`` / ``% height``) until 3
  distinct Sea cells have been converted to land -- resampling past an
  already-land cell (never "spending" a seed on a repeat).
- **"add random sea cells until main_land_threshold"**: repeatedly
  pick a uniformly random cell; if it's Sea, convert it to land;
  repeat until the land count reaches ``main_land_threshold``. Read as
  "randomly draw from the cells that are [still] sea" -- rather than
  literally adding *more* sea to an all-sea map, which the initial
  state already is and the surrounding steps make no sense under.
- **"perform 2*king_count additional land attempts"**: exactly
  ``2*king_count`` more single random-cell draws, each converting that
  cell to land only if it's currently Sea -- deliberately *not*
  guaranteed to add ``2*king_count`` new land cells (some "attempts"
  land on cells that are already land and do nothing), matching the
  word "attempts" as read against step 2's "until" (a guaranteed
  count).
- **"iteratively fill enclosed sea holes using six hex neighbors"**: a
  breadth-first flood fill from every edge Sea cell across this
  project's own already-validated 6-neighbor hex adjacency
  (``ak_engine.turn.movement.neighbors``, itself real-data-confirmed
  as of Phase 314); any Sea cell the flood never reaches is
  "enclosed" and becomes land. One BFS pass finds every hole in a
  single traversal (filling a hole cannot create a new one), matching
  "iteratively" as describing a queue-driven per-cell process rather
  than requiring repeated whole-map passes.
- **"for bottom_y=8 regenerate if land_count exceeds 90"**: after the
  steps above, if the map height is the confirmed-default 9 rows
  (``bottom_y = height - 1 = 8``) and the resulting land count exceeds
  ``final_land_hard_max = 90``, discard the whole grid and start over
  from a fresh all-Sea state, drawing further values from the same RNG
  stream. No comparable cap is confirmed for other map sizes, so the
  check is skipped for any other ``height`` rather than guessing one.

Every land cell's specific terrain (Plains/Desert/Jungle/Forest/
Mountains, never Sea) is drawn via ``map_shape``'s own
``LATITUDE_TERRAIN_WEIGHTS`` with Sea excluded and the remainder kept
in proportion -- Phase 353 already proved this reproduces the source's
own separate ``conditional_percent_when_placing_land`` table exactly,
so no new terrain data is introduced here.

**Verification**: a 500-map Monte Carlo at the confirmed default size
(18x9, 10 kings) never exceeded the 90-cell cap even once (land counts
ranged 51-68), so the regenerate branch is exercised only defensively
here, not routinely -- consistent with the source's own framing of 90
as a rare hard cap rather than a typical outcome. What's tested:
determinism (same seed -> same map), every generated cell landing in
the 6 real (non-Sea) terrain types, and that the BFS hole-fill leaves
zero enclosed Sea cells behind (every remaining Sea cell reaches the
map edge through other Sea cells).

**Phase 986 correction** -- that 51-68 land Monte Carlo range (31-42%
land, 58-69% Sea) was pointed out directly by the user as producing
far too much Sea once actually played. Parsing a real played game's own
world file (``parser/gw_world.py`` against a real ``GW3__T1``, the
confirmed-default 18x9/10-king shape) found 112 of its 162 cells are
land (SEA=50, 30.9%) -- not just far above this module's own spatial
realization, but above even ``shape_goal``'s disassembly-"confirmed
exact" [87, 96] range. So the narrow range is real, but something about
how the real EXE spends "2*king_count additional land attempts" and
fills holes grows land far more aggressively than this project's literal
reading of those two narrative steps manages to. Rather than keep
guessing at that missing mechanism, and at the user's explicit choice
("recalibrate on the real GW3 data") over keeping the disassembly
formula's own narrower, still-short-of-real-data range, ``generate_map``
now grows land to whichever is larger of ``main_land_threshold`` and a
new ``REAL_LAND_FRACTION``-based target (112/162, applied
proportionally to other board sizes since no other real sample exists
to check it against), and the old ``FINAL_LAND_HARD_MAX = 90`` hard cap
-- now routinely *below* the expected result -- is likewise scaled up
by the same real ratio (see ``_land_hard_max``) rather than kept
verbatim, which would make every default-size generation loop forever.
"""

from __future__ import annotations

from collections import deque

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.worldgen.map_shape import (
    DEFAULT_KING_COUNT,
    LATITUDE_TERRAIN_WEIGHTS,
    band_for_row,
    main_land_threshold,
    shape_goal,
)
from ak_engine.worldgen.pascal_random import PascalRandom

DEFAULT_WIDTH = 18
DEFAULT_HEIGHT = 9
FINAL_LAND_HARD_MAX = 90
SEED_LAND_COUNT = 3

# Phase 986: real ratio of land to total cells, measured directly from a
# real played game's own world file (112 land / 162 cells, 18x9/10-king
# default shape -- see the module docstring's "Phase 986 correction").
# Project-original recalibration, chosen by the user over the disassembly-
# sourced (but still short-of-real-data) `shape_goal`/`main_land_threshold`
# narrative -- NOT itself from the AKGEN disassembly.
REAL_LAND_FRACTION = 112 / 162

# The fraction `_grow_to_threshold` itself is aimed at -- deliberately
# *lower* than `REAL_LAND_FRACTION`, because the pipeline's own later
# steps ("2*king_count additional land attempts" + the hole-fill pass)
# add more land on top, and do so increasingly aggressively the denser
# the map already is (fewer remaining Sea cells means more of them end
# up enclosed and so get filled too). Simulating the full pipeline
# (`_place_land_seeds` -> `_grow_to_threshold` -> `_additional_land_
# attempts` -> `_fill_enclosed_sea_holes`) at the confirmed default
# 18x9/10-king shape across 100+ runs and several seeds found a growth
# target of 92/162 (not 112/162) is what makes the *pipeline's own
# final output* average to the real 112/162 -- this constant, not
# `REAL_LAND_FRACTION`, is what `generate_map` actually grows toward.
# Calibrated only against the one real sample this project has (10
# kings); not re-validated for other king counts, where "2*king_count"
# additional attempts would add land at a different rate.
GROWTH_TARGET_FRACTION = 92 / 162


def _land_hard_max(cell_count: int) -> int:
    """The regenerate-trigger cap, scaled to the Phase 986 real land ratio.

    The source's own disassembly-confirmed cap (``FINAL_LAND_HARD_MAX =
    90``) guarded against the old, narrower narrative-only land target;
    a real 112-land game already exceeds it, so kept verbatim it would
    make every default-size `generate_map` call regenerate forever. This
    keeps it as a floor (for any non-default board the real ratio wasn't
    checked against) but raises it with the same margin above the real
    target, so it still catches genuine runaway generation (near-total
    land) without rejecting the now-expected ~69% result.
    """

    return max(FINAL_LAND_HARD_MAX, round(cell_count * 0.9))

_LAND_ONLY_WEIGHTS: dict[int, dict[Terrain, int]] = {
    band: {terrain: weight for terrain, weight in weights.items() if terrain is not Terrain.SEA}
    for band, weights in LATITUDE_TERRAIN_WEIGHTS.items()
}


def draw_land_terrain(band: int, rng: PascalRandom) -> Terrain:
    """Weighted non-Sea terrain draw -- the source's own ``conditional_percent_when_placing_land``."""

    weights = _LAND_ONLY_WEIGHTS[band]
    total = sum(weights.values())
    roll = rng.irand() % total
    cumulative = 0
    for terrain, weight in weights.items():
        cumulative += weight
        if roll < cumulative:
            return terrain
    return next(iter(weights))


def _random_cell(rng: PascalRandom, width: int, height: int) -> HexCoord:
    return HexCoord(rng.irand() % width, rng.irand() % height)


def _place_land_seeds(
    grid: dict[HexCoord, Terrain], rng: PascalRandom, width: int, height: int, bottom_y: int
) -> None:
    placed = 0
    attempts = 0
    max_attempts = SEED_LAND_COUNT * 200
    while placed < SEED_LAND_COUNT and attempts < max_attempts:
        attempts += 1
        coord = _random_cell(rng, width, height)
        if grid[coord] is Terrain.SEA:
            grid[coord] = draw_land_terrain(band_for_row(coord.y, bottom_y), rng)
            placed += 1


def _grow_to_threshold(
    grid: dict[HexCoord, Terrain],
    rng: PascalRandom,
    width: int,
    height: int,
    bottom_y: int,
    threshold: int,
) -> None:
    land_count = sum(1 for t in grid.values() if t is not Terrain.SEA)
    attempts = 0
    max_attempts = width * height * 50
    while land_count < threshold and attempts < max_attempts:
        attempts += 1
        coord = _random_cell(rng, width, height)
        if grid[coord] is Terrain.SEA:
            grid[coord] = draw_land_terrain(band_for_row(coord.y, bottom_y), rng)
            land_count += 1


def _additional_land_attempts(
    grid: dict[HexCoord, Terrain],
    rng: PascalRandom,
    width: int,
    height: int,
    bottom_y: int,
    attempt_count: int,
) -> None:
    for _ in range(attempt_count):
        coord = _random_cell(rng, width, height)
        if grid[coord] is Terrain.SEA:
            grid[coord] = draw_land_terrain(band_for_row(coord.y, bottom_y), rng)


def _fill_enclosed_sea_holes(
    grid: dict[HexCoord, Terrain], bounds: MapBounds, rng: PascalRandom, bottom_y: int
) -> None:
    open_sea: set[HexCoord] = set()
    queue: deque[HexCoord] = deque()
    for coord, terrain in grid.items():
        is_edge = coord.x in (0, bounds.width - 1) or coord.y in (0, bounds.height - 1)
        if terrain is Terrain.SEA and is_edge:
            open_sea.add(coord)
            queue.append(coord)
    while queue:
        current = queue.popleft()
        for neighbor in neighbors(current, bounds):
            if grid[neighbor] is Terrain.SEA and neighbor not in open_sea:
                open_sea.add(neighbor)
                queue.append(neighbor)
    for coord, terrain in grid.items():
        if terrain is Terrain.SEA and coord not in open_sea:
            grid[coord] = draw_land_terrain(band_for_row(coord.y, bottom_y), rng)


def generate_map(
    rng: PascalRandom,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    king_count: int = DEFAULT_KING_COUNT,
    max_regenerations: int = 100,
) -> dict[HexCoord, Terrain]:
    """Run the full ``place_map`` pipeline once, regenerating on the source's own hard cap."""

    bottom_y = height - 1
    cell_count = width * height
    bounds = MapBounds(width, height)

    for _ in range(max_regenerations):
        grid: dict[HexCoord, Terrain] = {
            HexCoord(x, y): Terrain.SEA for x in range(width) for y in range(height)
        }
        goal = shape_goal(cell_count, king_count, rng)
        narrative_threshold = main_land_threshold(goal)
        growth_target = round(GROWTH_TARGET_FRACTION * cell_count)
        threshold = max(narrative_threshold, growth_target)

        _place_land_seeds(grid, rng, width, height, bottom_y)
        _grow_to_threshold(grid, rng, width, height, bottom_y, threshold)
        _additional_land_attempts(grid, rng, width, height, bottom_y, 2 * king_count)
        _fill_enclosed_sea_holes(grid, bounds, rng, bottom_y)

        land_count = sum(1 for t in grid.values() if t is not Terrain.SEA)
        if height == DEFAULT_HEIGHT and land_count > _land_hard_max(cell_count):
            continue
        return grid

    raise RuntimeError("place_map did not converge within max_regenerations attempts")
