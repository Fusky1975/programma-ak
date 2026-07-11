from __future__ import annotations

import pytest

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.movement import (
    NORMAL_MAP_BOUNDS,
    HexOwnershipTier,
    MapBounds,
    NonAdjacentMoveError,
    hex_distance,
    is_adjacent,
    neighbors,
    resolve_move,
    step_toward_non_adjacent_target,
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


# -- hex_distance (Phase 51, used by turn/spy_table.py's Pursue formula) --


def test_hex_distance_to_self_is_zero():
    assert hex_distance(HexCoord(5, 5), HexCoord(5, 5)) == 0


@pytest.mark.parametrize(
    "x,y",
    [(x, y) for x in range(1, NORMAL_MAP_BOUNDS[0] - 1) for y in range(1, NORMAL_MAP_BOUNDS[1] - 1)],
)
def test_hex_distance_to_every_neighbor_is_one(x, y):
    origin = HexCoord(x, y)
    for neighbor in neighbors(origin, BOUNDS):
        assert hex_distance(origin, neighbor) == 1


def test_hex_distance_is_symmetric():
    a, b = HexCoord(2, 3), HexCoord(9, 11)
    assert hex_distance(a, b) == hex_distance(b, a)


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (HexCoord(5, 5), HexCoord(7, 5), 2),  # same row, 2 columns over
        (HexCoord(0, 0), HexCoord(5, 0), 5),  # same row, 5 columns over
        (HexCoord(0, 0), HexCoord(0, 10), 10),  # same column, straight down
    ],
)
def test_hex_distance_known_multi_hex_cases(a, b, expected):
    assert hex_distance(a, b) == expected


def _all_neutral(_coord: HexCoord) -> HexOwnershipTier:
    return HexOwnershipTier.NEUTRAL


def test_step_toward_non_adjacent_target_returns_current_when_already_there():
    target = HexCoord(5, 0)
    assert step_toward_non_adjacent_target(target, target, BOUNDS, _all_neutral) == target


def test_step_toward_non_adjacent_target_picks_the_single_closer_neighbor():
    # From (0,0) toward (5,0): only (1,0) is strictly closer than (0,0)'s own
    # distance-5; (0,0)'s other neighbor, (0,1), is distance 5 -- not closer.
    result = step_toward_non_adjacent_target(HexCoord(0, 0), HexCoord(5, 0), BOUNDS, _all_neutral)
    assert result == HexCoord(1, 0)


def test_step_toward_non_adjacent_target_stops_chasing_when_no_neighbor_is_closer():
    # From (0,0), both reachable neighbors are farther from (-5,-5) than
    # (0,0) itself is -- rulebook [3.1]: "stop chasing... if he can't find
    # a legal way to move closer to it in one phase."
    result = step_toward_non_adjacent_target(HexCoord(0, 0), HexCoord(-5, -5), BOUNDS, _all_neutral)
    assert result is None


def test_step_toward_non_adjacent_target_breaks_ties_by_ownership_tier():
    # From (5,5) toward (5,0): (6,4) and (5,4) tie at distance 4, both
    # strictly closer than (5,5)'s own distance-5.
    current, target = HexCoord(5, 5), HexCoord(5, 0)
    tied_candidates = {HexCoord(6, 4), HexCoord(5, 4)}

    def prefer_6_4(coord: HexCoord) -> HexOwnershipTier:
        return HexOwnershipTier.OWNED_OR_ALLIED if coord == HexCoord(6, 4) else HexOwnershipTier.NEUTRAL

    def prefer_5_4(coord: HexCoord) -> HexOwnershipTier:
        return HexOwnershipTier.OWNED_OR_ALLIED if coord == HexCoord(5, 4) else HexOwnershipTier.NEUTRAL

    assert step_toward_non_adjacent_target(current, target, BOUNDS, prefer_6_4) == HexCoord(6, 4)
    assert step_toward_non_adjacent_target(current, target, BOUNDS, prefer_5_4) == HexCoord(5, 4)
    # sanity: both really are the tied, strictly-closer candidate set
    assert {
        c for c in neighbors(current, BOUNDS) if hex_distance(c, target) < hex_distance(current, target)
    } == tied_candidates


def test_hex_ownership_tier_priority_order_matches_rulebook_31():
    assert (
        HexOwnershipTier.OWNED_OR_ALLIED
        < HexOwnershipTier.ENEMY
        < HexOwnershipTier.HERO_OWNED
        < HexOwnershipTier.NEUTRAL
    )
