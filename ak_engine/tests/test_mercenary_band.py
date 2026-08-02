from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import MapBounds, hex_distance
from ak_engine.worldgen.mercenary_band import (
    ARMY_STATE_HIRED,
    ARMY_STATE_MERCENARY,
    MAX_RADIUS,
    MAX_RETRIES,
    find_mercenary_recruit_type,
    hex_ring,
)
from ak_engine.worldgen.pascal_random import PascalRandom


def test_army_state_constants_match_the_confirmed_values():
    assert ARMY_STATE_HIRED == 1
    assert ARMY_STATE_MERCENARY == 2


def test_hex_ring_matches_hex_distance_for_every_returned_cell():
    bounds = MapBounds(9, 9)
    center = HexCoord(4, 4)
    for radius in range(1, MAX_RADIUS + 1):
        ring = hex_ring(center, radius, bounds)
        assert ring
        for coord in ring:
            assert hex_distance(center, coord) == radius


def test_hex_ring_includes_every_in_bounds_cell_at_that_distance():
    bounds = MapBounds(9, 9)
    center = HexCoord(4, 4)
    for radius in range(1, MAX_RADIUS + 1):
        ring = set(hex_ring(center, radius, bounds))
        brute_force = {
            HexCoord(x, y)
            for x in range(bounds.width)
            for y in range(bounds.height)
            if hex_distance(center, HexCoord(x, y)) == radius
        }
        assert ring == brute_force


def test_find_mercenary_recruit_type_finds_a_compatible_coordinate_at_each_radius():
    bounds = MapBounds(18, 9)
    home = HexCoord(9, 4)
    for radius in range(1, MAX_RADIUS + 1):
        rng = PascalRandom(seed=radius)
        target = hex_ring(home, radius, bounds)[0]

        def is_compatible(coord: HexCoord, _target=target) -> ArmyType | None:
            return ArmyType.LEGION if coord == _target else None

        result = find_mercenary_recruit_type(home, bounds, is_compatible, ArmyType.BOWMEN, rng)
        assert result == ArmyType.LEGION


def test_find_mercenary_recruit_type_falls_back_when_nothing_is_compatible():
    bounds = MapBounds(18, 9)
    home = HexCoord(9, 4)
    rng = PascalRandom(seed=1)
    result = find_mercenary_recruit_type(home, bounds, lambda coord: None, ArmyType.PHALANX, rng)
    assert result == ArmyType.PHALANX


def test_find_mercenary_recruit_type_respects_the_shared_retry_budget():
    bounds = MapBounds(18, 9)
    home = HexCoord(9, 4)
    rng = PascalRandom(seed=2)
    calls = 0

    def never_compatible(coord: HexCoord) -> ArmyType | None:
        nonlocal calls
        calls += 1
        return None

    result = find_mercenary_recruit_type(home, bounds, never_compatible, ArmyType.WHALES, rng)
    assert result == ArmyType.WHALES
    assert calls <= MAX_RETRIES


def test_max_retries_and_radius_are_the_confirmed_values():
    assert MAX_RETRIES == 100
    assert MAX_RADIUS == 6
