from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.feature import FeatureType
from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.world_generation import (
    AQUATIC_MONSTERS,
    FEATURE_TYPE_CANDIDATE_MONSTERS,
    LAND_DOUBLE_FEATURE_CHANCE,
    LAND_FEATURE_CHANCE,
    LAND_FEATURE_TYPES,
    LAND_MONSTER_POOL,
    SEA_FEATURE_CHANCE,
    SEA_FEATURE_TYPES,
    TREASURE_POOL,
    generate_world_features,
)

from _helpers import ScriptedRandom


def test_land_and_sea_feature_types_partition_all_real_types():
    all_real_types = set(FeatureType) - {FeatureType.NOFTYPE}
    assert set(LAND_FEATURE_TYPES) | set(SEA_FEATURE_TYPES) == all_real_types
    assert set(LAND_FEATURE_TYPES).isdisjoint(SEA_FEATURE_TYPES)


def test_sea_feature_types_are_always_covered_by_candidates():
    for ftype in SEA_FEATURE_TYPES:
        assert ftype in FEATURE_TYPE_CANDIDATE_MONSTERS
        assert set(FEATURE_TYPE_CANDIDATE_MONSTERS[ftype]) <= set(AQUATIC_MONSTERS)


def test_land_monster_pool_excludes_aquatic_and_nomonster():
    assert set(LAND_MONSTER_POOL).isdisjoint(AQUATIC_MONSTERS)
    assert Monster.NOMONSTER not in LAND_MONSTER_POOL
    assert len(LAND_MONSTER_POOL) == 55


def test_treasure_pool_covers_all_113_members():
    assert len(TREASURE_POOL) == 113
    assert set(TREASURE_POOL) == set(Treasure)


def _province(coord: HexCoord, terrain: Terrain) -> ProvinceState:
    return ProvinceState(coord=coord, terrain=terrain, race=Race.HUMAN)


def test_generate_world_features_skips_no_terrain():
    state = GameState()
    coord = HexCoord(1, 1)
    state.provinces[coord] = _province(coord, Terrain.NO_TERRAIN)
    created = generate_world_features(state, random.Random(0))
    assert created == []
    assert state.features == {}


def test_generate_world_features_land_success_creates_one_feature():
    state = GameState()
    coord = HexCoord(1, 1)
    state.provinces[coord] = _province(coord, Terrain.PLAINS)
    # rng.random() sequence: land-roll (< 0.60 -> success), double-roll (>= 0.20 -> no
    # second). Each successful _create_feature() consumes 3 rng.choice() calls (feature
    # type, guardian, treasure). choice_indices=[0,0,0] picks Monster.R_DRAGON as
    # guardian, a single-option species (100% Evil), so roll_monster_alignment()
    # (Phase 246) consumes zero further rng.random() calls -- no third value needed.
    rng = ScriptedRandom([0.1, 0.5], choice_indices=[0, 0, 0])
    created = generate_world_features(state, rng)
    assert len(created) == 1
    assert created[0].coord == coord
    assert created[0].kind in LAND_FEATURE_TYPES
    assert created[0].guardian_monster not in AQUATIC_MONSTERS
    assert created[0].treasure in TREASURE_POOL
    assert created[0].guardian_alignment is Alignment.EVIL


def test_generate_world_features_guardian_alignment_rolled_for_multi_option_species():
    # Monster.GI_OCTOPUS (SEA_FEATURE_TYPES[0]'s first candidate) has a
    # 50/50 Neutral/Evil distribution (Mostri.md) -- the roll actually drives which
    # one lands, proving Phase 246's wiring isn't a no-op.
    low_coord, high_coord = HexCoord(7, 7), HexCoord(8, 8)

    state_low = GameState()
    state_low.provinces[low_coord] = _province(low_coord, Terrain.SEA)
    rng_low = ScriptedRandom([0.05, 0.1], choice_indices=[0, 0, 0])
    created_low = generate_world_features(state_low, rng_low)
    assert created_low[0].guardian_alignment is Alignment.NEUTRAL

    state_high = GameState()
    state_high.provinces[high_coord] = _province(high_coord, Terrain.SEA)
    rng_high = ScriptedRandom([0.05, 0.9], choice_indices=[0, 0, 0])
    created_high = generate_world_features(state_high, rng_high)
    assert created_high[0].guardian_alignment is Alignment.EVIL


def test_generate_world_features_land_double_feature():
    state = GameState()
    coord = HexCoord(2, 2)
    state.provinces[coord] = _province(coord, Terrain.PLAINS)
    # land-roll succeeds, double-roll succeeds -> two features created, each
    # consuming 3 rng.choice() calls.
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0, 0, 0, 0, 0, 0])
    created = generate_world_features(state, rng)
    assert len(created) == 2
    assert all(f.coord == coord for f in created)


def test_generate_world_features_land_failure_creates_nothing():
    state = GameState()
    coord = HexCoord(3, 3)
    state.provinces[coord] = _province(coord, Terrain.PLAINS)
    rng = ScriptedRandom([LAND_FEATURE_CHANCE])  # exactly at the boundary -> fails (strict <)
    created = generate_world_features(state, rng)
    assert created == []


def test_generate_world_features_sea_success_uses_aquatic_guardian():
    state = GameState()
    coord = HexCoord(5, 5)
    state.provinces[coord] = _province(coord, Terrain.SEA)
    # Second rng.random() value feeds roll_monster_alignment() (Phase 246) --
    # choice_indices=[0,0,0] picks Monster.GI_OCTOPUS (2 alignment options,
    # so it consumes one roll, unlike the land tests' R_DRAGON pick below).
    rng = ScriptedRandom([0.05, 0.1], choice_indices=[0, 0, 0])
    created = generate_world_features(state, rng)
    assert len(created) == 1
    assert created[0].kind in SEA_FEATURE_TYPES
    assert created[0].guardian_monster in AQUATIC_MONSTERS
    assert created[0].guardian_alignment is not None


def test_generate_world_features_sea_failure_creates_nothing():
    state = GameState()
    coord = HexCoord(6, 6)
    state.provinces[coord] = _province(coord, Terrain.SEA)
    rng = ScriptedRandom([SEA_FEATURE_CHANCE])  # exactly at the boundary -> fails (strict <)
    created = generate_world_features(state, rng)
    assert created == []


def test_generate_world_features_assigns_sequential_feature_ids():
    state = GameState()
    coord1, coord2 = HexCoord(1, 1), HexCoord(2, 2)
    state.provinces[coord1] = _province(coord1, Terrain.PLAINS)
    state.provinces[coord2] = _province(coord2, Terrain.PLAINS)
    rng = ScriptedRandom([0.1, 0.5, 0.1, 0.5], choice_indices=[0, 0, 0, 0, 0, 0])
    created = generate_world_features(state, rng)
    assert len(created) == 2
    assert {f.feature_id for f in created} == {1, 2}
