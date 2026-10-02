from __future__ import annotations

from collections import deque

from ak_engine.models.map import Terrain
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.place_map import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    REAL_LAND_FRACTION,
    _land_hard_max,
    draw_land_terrain,
    generate_map,
)

LAND_TERRAINS = {Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS}


def _land_count(grid):
    return sum(1 for t in grid.values() if t is not Terrain.SEA)


def test_generate_map_covers_every_cell_of_the_default_18x9_grid():
    rng = PascalRandom(seed=1)
    grid = generate_map(rng)
    assert len(grid) == DEFAULT_WIDTH * DEFAULT_HEIGHT
    for x in range(DEFAULT_WIDTH):
        for y in range(DEFAULT_HEIGHT):
            assert (x, y) in {(c.x, c.y) for c in grid}


def test_generate_map_never_produces_unreachable_terrain_types():
    rng = PascalRandom(seed=2)
    grid = generate_map(rng)
    for terrain in grid.values():
        assert terrain is Terrain.SEA or terrain in LAND_TERRAINS


def test_generate_map_never_exceeds_the_recalibrated_land_hard_cap_at_default_size():
    rng = PascalRandom(seed=3)
    cap = _land_hard_max(DEFAULT_WIDTH * DEFAULT_HEIGHT)
    for _ in range(20):
        grid = generate_map(rng)
        assert _land_count(grid) <= cap


def test_generate_map_lands_close_to_the_real_gw3_ratio_at_default_size():
    # Phase 986: the user confirmed too much Sea was being generated; real
    # played-game data (GW3__T1, same 18x9/10-king default shape) showed
    # 112/162 land (69.1%), so a freshly generated default map should land
    # in that neighborhood rather than the old 31-42% Monte Carlo range.
    rng = PascalRandom(seed=8)
    land_counts = [_land_count(generate_map(rng)) for _ in range(20)]
    average_fraction = (sum(land_counts) / len(land_counts)) / (DEFAULT_WIDTH * DEFAULT_HEIGHT)
    assert abs(average_fraction - REAL_LAND_FRACTION) < 0.1


def test_generate_map_leaves_no_enclosed_sea_holes():
    rng = PascalRandom(seed=4)
    grid = generate_map(rng)
    bounds = MapBounds(DEFAULT_WIDTH, DEFAULT_HEIGHT)
    open_sea = set()
    queue = deque()
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
        if terrain is Terrain.SEA:
            assert coord in open_sea, f"enclosed sea hole left at {coord}"


def test_generate_map_is_deterministic_for_a_given_seed():
    grid_a = generate_map(PascalRandom(seed=555))
    grid_b = generate_map(PascalRandom(seed=555))
    assert grid_a == grid_b


def test_generate_map_produces_some_land_and_some_sea():
    rng = PascalRandom(seed=6)
    grid = generate_map(rng)
    terrains = set(grid.values())
    assert Terrain.SEA in terrains
    assert terrains & LAND_TERRAINS


def test_draw_land_terrain_never_returns_sea():
    rng = PascalRandom(seed=7)
    for band in range(5):
        for _ in range(2000):
            assert draw_land_terrain(band, rng) is not Terrain.SEA
