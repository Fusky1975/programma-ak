from __future__ import annotations

from collections import Counter

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.movement import MapBounds
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.province_tax import (
    HOME_OVERRIDE_TAX,
    NOTERR_TAX,
    ORDINARY_LAND_MAX,
    coast_score,
    compute_edge_score,
    ordinary_land_tax,
    true_sea_tax,
)


def test_home_override_and_noterr_are_the_confirmed_fixed_values():
    assert HOME_OVERRIDE_TAX == 10
    assert NOTERR_TAX == 0


def test_ordinary_land_tax_stays_within_1_to_m_for_every_terrain():
    rng = PascalRandom(seed=1)
    for terrain, max_tax in ORDINARY_LAND_MAX.items():
        for _ in range(3000):
            tax = ordinary_land_tax(terrain, rng)
            assert 1 <= tax <= max_tax


def test_low_floor_removes_tax_one_for_plains_forest_mountains():
    rng = PascalRandom(seed=2)
    for terrain in (Terrain.PLAINS, Terrain.FOREST, Terrain.MTNS):
        results = {ordinary_land_tax(terrain, rng) for _ in range(3000)}
        assert 1 not in results


def test_low_floor_leaves_tax_one_possible_for_desert_and_jungle():
    rng = PascalRandom(seed=3)
    for terrain in (Terrain.DESERT, Terrain.JUNGLE):
        results = {ordinary_land_tax(terrain, rng) for _ in range(3000)}
        assert 1 in results


def test_coast_score_counts_sea_neighbors_only():
    bounds = MapBounds(5, 5)
    grid = {HexCoord(x, y): Terrain.PLAINS for x in range(5) for y in range(5)}
    center = HexCoord(2, 2)
    from ak_engine.turn.movement import neighbors

    all_neighbors = neighbors(center, bounds)
    for n in all_neighbors[:2]:
        grid[n] = Terrain.SEA
    assert coast_score(center, grid, bounds) == 2


def test_compute_edge_score_matches_coast_on_non_edge_rows():
    rng = PascalRandom(seed=4)
    assert compute_edge_score(3, False, rng) == 3
    assert compute_edge_score(0, False, rng) == 0


def test_compute_edge_score_scales_on_edge_rows():
    rng = PascalRandom(seed=5)
    for _ in range(1000):
        value = compute_edge_score(6, True, rng)
        assert 0 <= value <= 8


def test_true_sea_tax_high_coast_matches_the_combined_worked_probability():
    # 10% branch contributes 1/5 chance of landing on 1; 90% branch is a
    # direct IRand<7000 Bernoulli(7000/32768) for tax==1.
    expected_p_one = 0.10 * (1 / 5) + 0.90 * (7000 / 32768)
    rng = PascalRandom(seed=6)
    n = 200_000
    ones = sum(1 for _ in range(n) if true_sea_tax(7, rng) == 1)
    assert abs(ones / n - expected_p_one) < 0.01


def test_true_sea_tax_stays_within_0_to_6_off_high_coast():
    rng = PascalRandom(seed=7)
    for _ in range(5000):
        tax = true_sea_tax(2, rng)
        assert 0 <= tax <= 6


def test_true_sea_tax_low_coast_matches_independent_reimplementation():
    edge_score = 3
    n = 50_000

    def reference(rng: PascalRandom) -> int:
        if rng.random() < 0.10:
            return int(5 * rng.random())
        u1 = rng.random()
        u2 = rng.random()
        return min(6, int(1.8 * (7 - edge_score) * u1 * u2))

    rng_a = PascalRandom(seed=8)
    rng_b = PascalRandom(seed=8)
    actual = Counter(true_sea_tax(edge_score, rng_a) for _ in range(n))
    expected = Counter(reference(rng_b) for _ in range(n))
    assert actual == expected
