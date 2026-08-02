from __future__ import annotations

from collections import Counter

from ak_engine.models.map import Terrain
from ak_engine.worldgen.map_shape import (
    DEFAULT_CELL_COUNT,
    DEFAULT_KING_COUNT,
    LATITUDE_TERRAIN_WEIGHTS,
    band_for_row,
    draw_terrain,
    main_land_threshold,
    shape_goal,
)
from ak_engine.worldgen.pascal_random import PascalRandom


def test_shape_goal_matches_the_confirmed_87_96_range_for_the_default_map():
    rng = PascalRandom(seed=1)
    for _ in range(2000):
        goal = shape_goal(DEFAULT_CELL_COUNT, DEFAULT_KING_COUNT, rng)
        assert 87 <= goal <= 96


def test_shape_goal_covers_the_full_confirmed_range():
    rng = PascalRandom(seed=2)
    seen = {shape_goal(DEFAULT_CELL_COUNT, DEFAULT_KING_COUNT, rng) for _ in range(5000)}
    assert seen == set(range(87, 97))


def test_main_land_threshold_matches_the_confirmed_43_48_range():
    for goal in range(87, 97):
        threshold = main_land_threshold(goal)
        assert 43 <= threshold <= 48


def test_band_for_row_is_symmetric_around_map_center():
    bottom_y = 8
    assert band_for_row(0, bottom_y) == 0
    assert band_for_row(8, bottom_y) == 0
    assert band_for_row(4, bottom_y) == 4
    assert band_for_row(1, bottom_y) == 1
    assert band_for_row(7, bottom_y) == 1


def test_draw_terrain_distribution_matches_the_confirmed_latitude_weights():
    rng = PascalRandom(seed=99)
    n = 200_000
    for band, weights in LATITUDE_TERRAIN_WEIGHTS.items():
        counts = Counter(draw_terrain(band, rng) for _ in range(n))
        total = sum(weights.values())
        for terrain, weight in weights.items():
            expected_fraction = weight / total
            actual_fraction = counts.get(terrain, 0) / n
            assert abs(actual_fraction - expected_fraction) < 0.01, (band, terrain)


def test_draw_terrain_conditional_on_land_matches_the_source_conditional_percent_table():
    # Cross-check against the source's own separately-declared
    # conditional_percent_when_placing_land table (Sea excluded and
    # rescaled to 100) for band 0: Plains 20.0%, Forest 56.667%,
    # Mountains 23.333%.
    rng = PascalRandom(seed=123)
    n = 200_000
    land_counts: Counter[Terrain] = Counter()
    for _ in range(n):
        terrain = draw_terrain(0, rng)
        if terrain is not Terrain.SEA:
            land_counts[terrain] += 1
    land_total = sum(land_counts.values())
    assert abs(land_counts[Terrain.PLAINS] / land_total - 0.20) < 0.01
    assert abs(land_counts[Terrain.FOREST] / land_total - 0.56667) < 0.01
    assert abs(land_counts[Terrain.MTNS] / land_total - 0.23333) < 0.01
    assert land_counts[Terrain.DESERT] == 0
    assert land_counts[Terrain.JUNGLE] == 0


def test_draw_terrain_never_returns_a_weight_zero_terrain_for_its_band():
    rng = PascalRandom(seed=7)
    for _ in range(5000):
        # Band 0 has zero weight for Desert and Jungle.
        assert draw_terrain(0, rng) not in (Terrain.DESERT, Terrain.JUNGLE)
