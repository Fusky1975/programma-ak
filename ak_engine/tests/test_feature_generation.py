from __future__ import annotations

from collections import Counter

from ak_engine.models.feature import FeatureType
from ak_engine.models.map import Terrain
from ak_engine.models.monster import Monster
from ak_engine.worldgen.feature_generation import (
    LAND_TERRAINS,
    MFEAT_RANGE,
    SUNKEN_CITY_TERRAIN_CHOICES,
    feature_count,
    first_2k_home_index,
    is_terrain_compatible,
    propose_feature_type,
    propose_monster,
)
from ak_engine.worldgen.pascal_random import PascalRandom


def test_feature_count_matches_the_confirmed_gamevers_rule():
    assert feature_count(1) == 128
    assert feature_count(3) == 128
    assert feature_count(4) == 230
    assert feature_count(10) == 230


def test_propose_monster_stays_within_the_60_real_species():
    rng = PascalRandom(seed=1)
    for _ in range(5000):
        monster = propose_monster(rng)
        assert monster is not Monster.NOMONSTER
        assert 0 <= monster.value <= 59


def test_propose_monster_is_roughly_uniform_over_all_60_species():
    rng = PascalRandom(seed=2)
    n = 120_000
    counts = Counter(propose_monster(rng) for _ in range(n))
    assert len(counts) == 60
    expected = n / 60
    for count in counts.values():
        assert abs(count - expected) / expected < 0.25


def test_mfeat_range_covers_every_real_monster():
    for monster in Monster:
        if monster is Monster.NOMONSTER:
            continue
        assert monster in MFEAT_RANGE


def test_propose_feature_type_stays_within_each_monsters_confirmed_range():
    rng = PascalRandom(seed=3)
    for monster, (first, last) in MFEAT_RANGE.items():
        for _ in range(200):
            result = propose_feature_type(monster, rng)
            assert first.value <= result.value <= last.value


def test_propose_feature_type_covers_the_full_range_given_enough_draws():
    rng = PascalRandom(seed=4)
    first, last = MFEAT_RANGE[Monster.MINOTAUR]  # MAZE..LABYRINTH, a small 2-wide range
    results = {propose_feature_type(Monster.MINOTAUR, rng) for _ in range(500)}
    assert results == {FeatureType(v) for v in range(first.value, last.value + 1)}


def test_is_terrain_compatible_matches_the_confirmed_any_land_types():
    rng = PascalRandom(seed=5)
    for terrain in LAND_TERRAINS:
        assert is_terrain_compatible(FeatureType.PYRAMID, terrain, rng)
    assert not is_terrain_compatible(FeatureType.PYRAMID, Terrain.SEA, rng)


def test_is_terrain_compatible_gates_specific_land_terrains_correctly():
    rng = PascalRandom(seed=6)
    assert is_terrain_compatible(FeatureType.DES_RUINS, Terrain.DESERT, rng)
    assert not is_terrain_compatible(FeatureType.DES_RUINS, Terrain.PLAINS, rng)
    assert is_terrain_compatible(FeatureType.LOST_CITY, Terrain.JUNGLE, rng)
    assert not is_terrain_compatible(FeatureType.LOST_CITY, Terrain.FOREST, rng)
    assert is_terrain_compatible(FeatureType.HOLLOW_TREE, Terrain.FOREST, rng)
    assert is_terrain_compatible(FeatureType.HANG_VALLEY, Terrain.MTNS, rng)


def test_is_terrain_compatible_magic_pool_and_loch_are_land_not_sea():
    # The Phase 359 correction: Phase 242 guessed Magic Pool was Sea-only.
    rng = PascalRandom(seed=7)
    for terrain in LAND_TERRAINS:
        assert is_terrain_compatible(FeatureType.MAG_POOL, terrain, rng)
        assert is_terrain_compatible(FeatureType.LOCH, terrain, rng)
    assert not is_terrain_compatible(FeatureType.MAG_POOL, Terrain.SEA, rng)


def test_is_terrain_compatible_undersea_cavern_and_maelstrom_are_sea_only():
    rng = PascalRandom(seed=8)
    assert is_terrain_compatible(FeatureType.UND_CAVERN, Terrain.SEA, rng)
    assert is_terrain_compatible(FeatureType.MAELSTROM, Terrain.SEA, rng)
    for terrain in LAND_TERRAINS:
        assert not is_terrain_compatible(FeatureType.UND_CAVERN, terrain, rng)
        assert not is_terrain_compatible(FeatureType.MAELSTROM, terrain, rng)


def test_is_terrain_compatible_sunken_city_splits_roughly_50_50():
    rng = PascalRandom(seed=9)
    n = 20_000
    desert_hits = sum(
        1 for _ in range(n) if is_terrain_compatible(FeatureType.SUNK_CITY, Terrain.DESERT, rng)
    )
    sea_hits = sum(1 for _ in range(n) if is_terrain_compatible(FeatureType.SUNK_CITY, Terrain.SEA, rng))
    assert abs(desert_hits / n - 0.5) < 0.03
    assert abs(sea_hits / n - 0.5) < 0.03
    assert set(SUNKEN_CITY_TERRAIN_CHOICES) == {Terrain.DESERT, Terrain.SEA}


def test_first_2k_home_index_matches_the_confirmed_two_bands():
    king_count = 10
    for feature_index in range(king_count):
        assert first_2k_home_index(feature_index, king_count) == feature_index
    for feature_index in range(king_count, 2 * king_count):
        assert first_2k_home_index(feature_index, king_count) == (feature_index + 5) % king_count
