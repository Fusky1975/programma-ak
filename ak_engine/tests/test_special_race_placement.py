from __future__ import annotations

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.movement import MapBounds
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_race_placement import (
    ATTEMPT_CAP,
    OLD_RULES_MULTIPLIER,
    NEW_RULES_MULTIPLIER,
    SPECIAL_RACE_ORDER,
    is_terrain_eligible,
    place_all_special_races,
    place_special_race,
    recompute_tax,
    special_race_count,
)


def _uniform_grid(width, height, terrain):
    return {HexCoord(x, y): terrain for x in range(width) for y in range(height)}


def test_special_race_count_matches_all_seven_confirmed_old_new_pairs():
    expected = {
        Race.EAGLES: (4, 12),
        Race.ENTISH: (3, 9),
        Race.MERMISH: (4, 12),
        Race.TROLLISH: (4, 12),
        Race.DRAGONS: (4, 12),
        Race.WHALES: (7, 21),
        Race.WEREFOLK: (3, 9),
    }
    for race, (old, new) in expected.items():
        assert special_race_count(race, OLD_RULES_MULTIPLIER) == old
        assert special_race_count(race, NEW_RULES_MULTIPLIER) == new


def test_terrain_eligibility_matches_the_confirmed_per_race_tables():
    rng = PascalRandom(seed=1)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.PLAINS)
    coord = HexCoord(2, 2)

    assert is_terrain_eligible(Race.EAGLES, Terrain.MTNS, coord, grid, bounds, rng)
    assert not is_terrain_eligible(Race.EAGLES, Terrain.PLAINS, coord, grid, bounds, rng)

    for terrain in (Terrain.JUNGLE, Terrain.FOREST):
        assert is_terrain_eligible(Race.ENTISH, terrain, coord, grid, bounds, rng)
    assert not is_terrain_eligible(Race.ENTISH, Terrain.DESERT, coord, grid, bounds, rng)

    for terrain in (Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS):
        assert is_terrain_eligible(Race.TROLLISH, terrain, coord, grid, bounds, rng)
    assert not is_terrain_eligible(Race.TROLLISH, Terrain.PLAINS, coord, grid, bounds, rng)

    for terrain in (Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS):
        assert is_terrain_eligible(Race.DRAGONS, terrain, coord, grid, bounds, rng)
    assert not is_terrain_eligible(Race.DRAGONS, Terrain.PLAINS, coord, grid, bounds, rng)

    for terrain in (Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS):
        assert is_terrain_eligible(Race.WEREFOLK, terrain, coord, grid, bounds, rng)
    assert not is_terrain_eligible(Race.WEREFOLK, Terrain.SEA, coord, grid, bounds, rng)

    assert is_terrain_eligible(Race.WHALES, Terrain.SEA, coord, grid, bounds, rng)
    assert not is_terrain_eligible(Race.WHALES, Terrain.PLAINS, coord, grid, bounds, rng)


def test_merman_is_always_eligible_on_sea():
    rng = PascalRandom(seed=2)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.SEA)
    coord = HexCoord(2, 2)
    for _ in range(50):
        assert is_terrain_eligible(Race.MERMISH, Terrain.SEA, coord, grid, bounds, rng)


def test_merman_jungle_requires_at_least_one_sea_neighbor():
    rng = PascalRandom(seed=3)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.JUNGLE)  # zero Sea neighbors anywhere
    coord = HexCoord(2, 2)
    for _ in range(50):
        assert not is_terrain_eligible(Race.MERMISH, Terrain.JUNGLE, coord, grid, bounds, rng)


def test_merman_jungle_rule_matches_coast_score_vs_irand_and_7():
    rng_a = PascalRandom(seed=4)
    rng_b = PascalRandom(seed=4)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.JUNGLE)
    coord = HexCoord(2, 2)
    from ak_engine.turn.movement import neighbors as _neighbors

    coastal_neighbors = _neighbors(coord, bounds)[:3]
    for n in coastal_neighbors:
        grid[n] = Terrain.SEA

    for _ in range(1000):
        actual = is_terrain_eligible(Race.MERMISH, Terrain.JUNGLE, coord, grid, bounds, rng_a)
        from ak_engine.worldgen.province_tax import coast_score as _coast_score

        expected = _coast_score(coord, grid, bounds) > (rng_b.irand() & 7)
        assert actual == expected


def test_place_special_race_rejects_king_homes():
    rng = PascalRandom(seed=5)
    bounds = MapBounds(3, 3)
    grid = _uniform_grid(3, 3, Terrain.MTNS)
    race_grid: dict[HexCoord, Race] = {}
    king_homes = frozenset({HexCoord(x, y) for x in range(3) for y in range(3)} - {HexCoord(1, 1)})
    result = place_special_race(Race.EAGLES, grid, race_grid, bounds, king_homes, rng)
    assert result == HexCoord(1, 1)


def test_place_special_race_rejects_provinces_already_carrying_a_special_race():
    rng = PascalRandom(seed=6)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.MTNS)
    occupied = HexCoord(2, 2)
    race_grid: dict[HexCoord, Race] = {occupied: Race.TROLLISH}
    king_homes: frozenset[HexCoord] = frozenset()
    for _ in range(20):
        result = place_special_race(Race.EAGLES, grid, race_grid, bounds, king_homes, rng)
        assert result is not None
        assert result != occupied
        del race_grid[result]  # free it up again for the next attempt in this loop


def test_place_special_race_rejects_neighbors_of_an_existing_special_race():
    rng = PascalRandom(seed=7)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.MTNS)
    race_grid: dict[HexCoord, Race] = {}
    king_homes: frozenset[HexCoord] = frozenset()
    center = HexCoord(2, 2)
    race_grid[center] = Race.TROLLISH
    from ak_engine.turn.movement import neighbors as _neighbors

    blocked = {center} | set(_neighbors(center, bounds))
    result = place_special_race(Race.EAGLES, grid, race_grid, bounds, king_homes, rng)
    assert result is not None
    assert result not in blocked


def test_place_special_race_returns_none_when_no_eligible_terrain_exists():
    rng = PascalRandom(seed=8)
    bounds = MapBounds(3, 3)
    grid = _uniform_grid(3, 3, Terrain.PLAINS)  # no Mountains anywhere
    race_grid: dict[HexCoord, Race] = {}
    king_homes: frozenset[HexCoord] = frozenset()
    result = place_special_race(Race.EAGLES, grid, race_grid, bounds, king_homes, rng)
    assert result is None


def test_place_all_special_races_follows_the_confirmed_call_order():
    assert SPECIAL_RACE_ORDER == (
        Race.EAGLES,
        Race.ENTISH,
        Race.MERMISH,
        Race.TROLLISH,
        Race.DRAGONS,
        Race.WHALES,
        Race.WEREFOLK,
    )


def test_place_all_special_races_places_up_to_each_races_confirmed_quota():
    rng = PascalRandom(seed=9)
    width, height = 18, 9
    bounds = MapBounds(width, height)
    grid: dict[HexCoord, Terrain] = {}
    for x in range(width):
        for y in range(height):
            grid[HexCoord(x, y)] = Terrain.MTNS if (x + y) % 3 == 0 else Terrain.SEA
    race_grid: dict[HexCoord, Race] = {}
    king_homes: frozenset[HexCoord] = frozenset()
    placements = place_all_special_races(grid, race_grid, bounds, king_homes, rng, new_rules=True)
    assert placements[Race.EAGLES]
    assert len(placements[Race.EAGLES]) <= special_race_count(Race.EAGLES, NEW_RULES_MULTIPLIER)
    for coord in placements[Race.EAGLES]:
        assert race_grid[coord] == Race.EAGLES


def test_recompute_tax_dispatches_to_true_sea_for_sea_terrain():
    rng = PascalRandom(seed=10)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.SEA)
    coord = HexCoord(2, 2)
    for _ in range(200):
        tax = recompute_tax(coord, Terrain.SEA, grid, bounds, bottom_y=4, rng=rng)
        assert 0 <= tax <= 6


def test_recompute_tax_dispatches_to_ordinary_land_for_land_terrain():
    rng = PascalRandom(seed=11)
    bounds = MapBounds(5, 5)
    grid = _uniform_grid(5, 5, Terrain.DESERT)
    coord = HexCoord(2, 2)
    for _ in range(200):
        tax = recompute_tax(coord, Terrain.DESERT, grid, bounds, bottom_y=4, rng=rng)
        assert 1 <= tax <= 2


def test_attempt_cap_is_the_confirmed_3000():
    assert ATTEMPT_CAP == 3000
