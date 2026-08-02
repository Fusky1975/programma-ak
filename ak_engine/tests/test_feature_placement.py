from __future__ import annotations

from ak_engine.models.feature import FeatureType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.movement import MapBounds
from ak_engine.worldgen.feature_generation import feature_count, first_2k_home_index
from ak_engine.worldgen.feature_placement import place_all_features, place_feature
from ak_engine.worldgen.pascal_random import PascalRandom

# UND_CAVERN/MAELSTROM are always Sea-compatible; SUNK_CITY ("Sunken
# City") can also land on Sea via its own confirmed 50/50 Desert/Sea rule.
SEA_COMPATIBLE_TYPES = {FeatureType.UND_CAVERN, FeatureType.MAELSTROM, FeatureType.SUNK_CITY}


def _uniform_grid(width, height, terrain):
    return {HexCoord(x, y): terrain for x in range(width) for y in range(height)}


def test_place_feature_first_2k_uses_the_confirmed_king_home_coordinate():
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.PLAINS)
    king_homes = [HexCoord(0, 0), HexCoord(1, 1)]
    king_count = 2
    rng = PascalRandom(seed=1)
    for feature_index in range(2 * king_count):
        placement = place_feature(feature_index, king_homes, king_count, grid, bounds, rng)
        expected_home_index = first_2k_home_index(feature_index, king_count)
        assert placement.coord == king_homes[expected_home_index]
        assert placement.feature_index == feature_index


def test_place_feature_first_2k_retries_until_terrain_compatible():
    # King Home is Sea -- only UND_CAVERN/MAELSTROM/SUNK_CITY can ever be
    # Sea-compatible, so the rejection loop must retry (re-proposing
    # monster+type) until one of those comes up.
    bounds = MapBounds(3, 3)
    grid = _uniform_grid(3, 3, Terrain.PLAINS)
    king_homes = [HexCoord(1, 1)]
    grid[king_homes[0]] = Terrain.SEA
    king_count = 1
    rng = PascalRandom(seed=2)
    placement = place_feature(0, king_homes, king_count, grid, bounds, rng)
    assert placement.coord == king_homes[0]
    assert placement.feature_type in SEA_COMPATIBLE_TYPES


def test_place_feature_later_placement_never_lands_on_a_king_home():
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.PLAINS)
    king_homes = [HexCoord(0, 0), HexCoord(1, 1)]
    king_count = 2
    rng = PascalRandom(seed=3)
    for feature_index in range(2 * king_count, 2 * king_count + 20):
        placement = place_feature(feature_index, king_homes, king_count, grid, bounds, rng)
        assert placement.coord not in king_homes


def test_place_all_features_produces_exactly_the_confirmed_count():
    bounds = MapBounds(18, 9)
    grid = _uniform_grid(18, 9, Terrain.PLAINS)
    king_homes = [HexCoord(x, 0) for x in range(10)]
    for home in king_homes:
        grid[home] = Terrain.PLAINS
    king_count = 10
    rng = PascalRandom(seed=4)
    placements = place_all_features(king_homes, king_count, grid, bounds, rng, gamevers=1)
    assert len(placements) == feature_count(1) == 128
    assert [p.feature_index for p in placements] == list(range(128))


def test_place_all_features_later_placements_never_use_a_king_home():
    bounds = MapBounds(18, 9)
    grid = _uniform_grid(18, 9, Terrain.PLAINS)
    king_homes = [HexCoord(x, 0) for x in range(10)]
    king_count = 10
    rng = PascalRandom(seed=5)
    placements = place_all_features(king_homes, king_count, grid, bounds, rng, gamevers=4)
    assert len(placements) == feature_count(4) == 230
    later = [p for p in placements if p.feature_index >= 2 * king_count]
    assert later
    for placement in later:
        assert placement.coord not in king_homes
