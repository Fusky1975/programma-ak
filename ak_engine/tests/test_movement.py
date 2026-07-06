from __future__ import annotations

import pytest

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.movement import (
    NORMAL_MAP_BOUNDS,
    MapBounds,
    NonAdjacentMoveError,
    is_adjacent,
    neighbors,
    resolve_move,
)

BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def test_interior_hex_has_six_neighbors():
    assert len(neighbors(HexCoord(5, 5), BOUNDS)) == 6


def test_corner_hex_neighbors_are_bounds_filtered():
    result = neighbors(HexCoord(0, 0), BOUNDS)
    assert all(BOUNDS.contains(c) for c in result)
    assert len(result) < 6


@pytest.mark.parametrize(
    "x,y",
    [(x, y) for x in range(NORMAL_MAP_BOUNDS[0]) for y in range(NORMAL_MAP_BOUNDS[1])],
)
def test_adjacency_is_symmetric_across_the_whole_map(x, y):
    origin = HexCoord(x, y)
    for neighbor in neighbors(origin, BOUNDS):
        assert origin in neighbors(neighbor, BOUNDS)


def test_is_adjacent_matches_neighbors():
    origin = HexCoord(5, 5)
    for neighbor in neighbors(origin, BOUNDS):
        assert is_adjacent(origin, neighbor, BOUNDS)
    assert not is_adjacent(origin, HexCoord(20, 10), BOUNDS)


def test_resolve_move_to_adjacent_hex():
    origin = HexCoord(5, 5)
    target = neighbors(origin, BOUNDS)[0]

    result = resolve_move(
        origin, target, BOUNDS,
        target_terrain=Terrain.PLAINS, target_explored_percent=0, explorer_skill=0,
    )

    assert result.new_coord == target
    assert result.battle_expected is False
    # Plains (50) x (skill 0 + 1) halved for the Move side effect = 25.
    assert result.exploration.new_percent == 25
    assert result.exploration.fully_explored is False


def test_resolve_move_flags_expected_battle_when_target_is_enemy_occupied():
    origin = HexCoord(5, 5)
    target = neighbors(origin, BOUNDS)[0]

    result = resolve_move(
        origin, target, BOUNDS,
        target_terrain=Terrain.PLAINS, target_explored_percent=0, explorer_skill=0,
        occupied_by_enemy=True,
    )

    assert result.battle_expected is True


def test_resolve_move_to_non_adjacent_hex_raises():
    origin = HexCoord(5, 5)
    far_away = HexCoord(20, 10)

    with pytest.raises(NonAdjacentMoveError):
        resolve_move(
            origin, far_away, BOUNDS,
            target_terrain=Terrain.PLAINS, target_explored_percent=0, explorer_skill=0,
        )
