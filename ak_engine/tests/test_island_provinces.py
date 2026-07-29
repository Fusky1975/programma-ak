from __future__ import annotations

import random

import pytest

from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.island_provinces import apply_island_provinces


def _state_with_provinces(*coords_and_terrain: tuple[HexCoord, Terrain]) -> GameState:
    state = GameState()
    for coord, terrain in coords_and_terrain:
        state.add_province(ProvinceState(coord, terrain, Race.HUMAN))
    return state


def test_apply_island_provinces_marks_exactly_the_requested_count():
    state = _state_with_provinces(
        (HexCoord(0, 0), Terrain.PLAINS),
        (HexCoord(1, 0), Terrain.DESERT),
        (HexCoord(2, 0), Terrain.FOREST),
    )

    chosen = apply_island_provinces(state, 2, rng=random.Random(0))

    assert len(chosen) == 2
    assert sum(1 for p in state.provinces.values() if p.is_island) == 2
    for coord in chosen:
        assert state.provinces[coord].is_island is True


def test_apply_island_provinces_excludes_sea_and_no_terrain():
    state = _state_with_provinces(
        (HexCoord(0, 0), Terrain.PLAINS),
        (HexCoord(1, 0), Terrain.SEA),
        (HexCoord(2, 0), Terrain.NO_TERRAIN),
    )

    chosen = apply_island_provinces(state, 1, rng=random.Random(0))

    assert chosen == [HexCoord(0, 0)]
    assert state.provinces[HexCoord(1, 0)].is_island is False
    assert state.provinces[HexCoord(2, 0)].is_island is False


def test_apply_island_provinces_excludes_already_marked_islands():
    state = _state_with_provinces(
        (HexCoord(0, 0), Terrain.PLAINS),
        (HexCoord(1, 0), Terrain.DESERT),
    )
    state.provinces[HexCoord(0, 0)].is_island = True

    chosen = apply_island_provinces(state, 1, rng=random.Random(0))

    assert chosen == [HexCoord(1, 0)]


def test_apply_island_provinces_raises_when_count_exceeds_eligible_provinces():
    state = _state_with_provinces((HexCoord(0, 0), Terrain.PLAINS))

    with pytest.raises(ValueError, match="only 1 eligible"):
        apply_island_provinces(state, 2, rng=random.Random(0))


def test_apply_island_provinces_raises_on_negative_count():
    state = _state_with_provinces((HexCoord(0, 0), Terrain.PLAINS))

    with pytest.raises(ValueError, match="must not be negative"):
        apply_island_provinces(state, -1, rng=random.Random(0))


def test_apply_island_provinces_zero_count_is_a_no_op():
    state = _state_with_provinces((HexCoord(0, 0), Terrain.PLAINS))

    chosen = apply_island_provinces(state, 0, rng=random.Random(0))

    assert chosen == []
    assert state.provinces[HexCoord(0, 0)].is_island is False


def test_apply_island_provinces_is_deterministic_given_the_same_seed():
    state_a = _state_with_provinces(
        (HexCoord(0, 0), Terrain.PLAINS),
        (HexCoord(1, 0), Terrain.DESERT),
        (HexCoord(2, 0), Terrain.FOREST),
        (HexCoord(3, 0), Terrain.MTNS),
    )
    state_b = _state_with_provinces(
        (HexCoord(0, 0), Terrain.PLAINS),
        (HexCoord(1, 0), Terrain.DESERT),
        (HexCoord(2, 0), Terrain.FOREST),
        (HexCoord(3, 0), Terrain.MTNS),
    )

    chosen_a = apply_island_provinces(state_a, 2, rng=random.Random(42))
    chosen_b = apply_island_provinces(state_b, 2, rng=random.Random(42))

    assert chosen_a == chosen_b
