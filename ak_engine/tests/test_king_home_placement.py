from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.movement import MapBounds
from ak_engine.worldgen.king_home_placement import (
    MIN_HOME_DISTANCE,
    choose_king_home,
    eligible_home_coords,
    king_is_naval,
    second_recruit_slot,
)
from ak_engine.worldgen.pascal_random import PascalRandom


def _skills_with_naval(level: int) -> SkillTable:
    table = SkillTable(raw_values=[0] * 31)
    table.set_pair_for_ability(Ability.NAVAL, level, 0)
    return table


def test_king_is_naval_reads_a_nonzero_naval_skill_level():
    assert king_is_naval(None) is False
    assert king_is_naval(_skills_with_naval(0)) is False
    assert king_is_naval(_skills_with_naval(1)) is True


def _flat_grid(width: int, height: int, terrain: Terrain) -> dict[HexCoord, Terrain]:
    return {HexCoord(x, y): terrain for x in range(width) for y in range(height)}


def _flat_race_grid(grid: dict[HexCoord, Terrain], race: Race) -> dict[HexCoord, Race]:
    return {coord: race for coord in grid}


def test_eligible_home_coords_excludes_sea_and_desert_and_non_humanoid_race():
    grid = {
        HexCoord(0, 0): Terrain.PLAINS,
        HexCoord(1, 0): Terrain.SEA,
        HexCoord(2, 0): Terrain.DESERT,
        HexCoord(3, 0): Terrain.JUNGLE,
    }
    race_grid = {coord: Race.HUMAN for coord in grid}
    race_grid[HexCoord(3, 0)] = Race.TROLLISH  # non-humanoid -- excluded regardless of terrain
    bounds = MapBounds(4, 1)

    candidates = eligible_home_coords(grid, race_grid, bounds, [], naval=False)

    assert candidates == [HexCoord(0, 0)]


def test_eligible_home_coords_enforces_the_minimum_distance():
    grid = _flat_grid(10, 1, Terrain.PLAINS)
    race_grid = _flat_race_grid(grid, Race.HUMAN)
    bounds = MapBounds(10, 1)
    taken = [HexCoord(5, 0)]

    candidates = eligible_home_coords(grid, race_grid, bounds, taken, naval=False)

    for coord in candidates:
        assert abs(coord.x - 5) >= MIN_HOME_DISTANCE


def test_eligible_home_coords_naval_requires_a_sea_neighbor():
    grid = {
        HexCoord(0, 0): Terrain.PLAINS,  # no sea neighbor
        HexCoord(5, 0): Terrain.PLAINS,
        HexCoord(6, 0): Terrain.SEA,
    }
    race_grid = {HexCoord(0, 0): Race.HUMAN, HexCoord(5, 0): Race.HUMAN, HexCoord(6, 0): Race.HUMAN}
    bounds = MapBounds(10, 1)

    candidates = eligible_home_coords(grid, race_grid, bounds, [], naval=True)

    assert candidates == [HexCoord(5, 0)]


def test_choose_king_home_raises_when_nothing_is_eligible():
    grid = {HexCoord(0, 0): Terrain.SEA}
    race_grid = {HexCoord(0, 0): Race.HUMAN}
    bounds = MapBounds(1, 1)

    with pytest.raises(ValueError):
        choose_king_home(grid, race_grid, bounds, [], PascalRandom(seed=1), naval=False)


# 2026-11-20 bug fix, user-confirmed from their own real-game play
# experience: a King's Home province always has exactly one Rich
# (tax >= RICH_PROVINCE_MIN_TAX) neighbor.


def test_eligible_home_coords_tax_grid_requires_exactly_one_rich_neighbor():
    grid = _flat_grid(5, 1, Terrain.PLAINS)
    race_grid = _flat_race_grid(grid, Race.HUMAN)
    bounds = MapBounds(5, 1)
    # HexCoord(0,0)'s only neighbor within this tiny strip is (1,0);
    # HexCoord(2,0) has two neighbors, (1,0) and (3,0).
    tax_grid = {
        HexCoord(0, 0): 1,
        HexCoord(1, 0): 7,  # Rich
        HexCoord(2, 0): 1,
        HexCoord(3, 0): 7,  # Rich
        HexCoord(4, 0): 1,
    }

    candidates = eligible_home_coords(grid, race_grid, bounds, [], naval=False, tax_grid=tax_grid)

    # (0,0): one Rich neighbor (1,0) -> eligible.
    # (2,0): two Rich neighbors (1,0) and (3,0) -> not exactly one, excluded.
    # (4,0): one Rich neighbor (3,0) -> eligible.
    assert set(candidates) == {HexCoord(0, 0), HexCoord(4, 0)}


def test_eligible_home_coords_tax_grid_excludes_a_coord_with_no_rich_neighbor():
    grid = _flat_grid(3, 1, Terrain.PLAINS)
    race_grid = _flat_race_grid(grid, Race.HUMAN)
    bounds = MapBounds(3, 1)
    tax_grid = {HexCoord(0, 0): 1, HexCoord(1, 0): 1, HexCoord(2, 0): 1}  # nobody Rich

    candidates = eligible_home_coords(grid, race_grid, bounds, [], naval=False, tax_grid=tax_grid)

    assert candidates == []


def test_eligible_home_coords_without_tax_grid_keeps_prior_behavior():
    # No tax_grid passed -- the new constraint must not apply at all.
    grid = _flat_grid(3, 1, Terrain.PLAINS)
    race_grid = _flat_race_grid(grid, Race.HUMAN)
    bounds = MapBounds(3, 1)

    candidates = eligible_home_coords(grid, race_grid, bounds, [], naval=False)

    assert set(candidates) == {HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0)}


def test_choose_king_home_prefers_a_rich_neighbor_candidate():
    grid = _flat_grid(5, 1, Terrain.PLAINS)
    race_grid = _flat_race_grid(grid, Race.HUMAN)
    bounds = MapBounds(5, 1)
    tax_grid = {
        HexCoord(0, 0): 1,
        HexCoord(1, 0): 7,  # Rich
        HexCoord(2, 0): 1,
        HexCoord(3, 0): 1,
        HexCoord(4, 0): 1,
    }

    # (0,0) and (2,0) each have exactly one Rich neighbor, (1,0) itself
    # -- (0,0)'s only neighbor is (1,0); (2,0)'s neighbors are (1,0)
    # [Rich] and (3,0) [not]. (1,0)/(3,0)/(4,0) each have zero Rich
    # neighbors of their own.
    for seed in range(1, 10):
        home = choose_king_home(grid, race_grid, bounds, [], PascalRandom(seed=seed), naval=False, tax_grid=tax_grid)
        assert home in {HexCoord(0, 0), HexCoord(2, 0)}


def test_choose_king_home_falls_back_when_no_rich_neighbor_candidate_exists():
    # user-confirmed fallback: relax the Rich-neighbor rule rather than
    # fail world generation outright when nothing satisfies it.
    grid = _flat_grid(3, 1, Terrain.PLAINS)
    race_grid = _flat_race_grid(grid, Race.HUMAN)
    bounds = MapBounds(3, 1)
    tax_grid = {HexCoord(0, 0): 1, HexCoord(1, 0): 1, HexCoord(2, 0): 1}  # nobody Rich

    home = choose_king_home(grid, race_grid, bounds, [], PascalRandom(seed=1), naval=False, tax_grid=tax_grid)

    assert home in grid


def test_second_recruit_slot_naval_is_always_fleet():
    rng = PascalRandom(seed=1)
    for terrain in (Terrain.PLAINS, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS):
        assert second_recruit_slot(terrain, rng, naval=True) is ArmyType.FLEET


def test_second_recruit_slot_jungle_is_always_elephants():
    rng = PascalRandom(seed=1)
    assert second_recruit_slot(Terrain.JUNGLE, rng, naval=False) is ArmyType.ELEPHANTS


def test_second_recruit_slot_other_land_terrains_draw_from_cavalry_or_chariots():
    rng = PascalRandom(seed=1)
    seen = {second_recruit_slot(Terrain.PLAINS, rng, naval=False) for _ in range(50)}
    assert seen <= {ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY, ArmyType.CHARIOTS}


def test_second_recruit_slot_orcish_king_is_always_warg_riders_regardless_of_terrain():
    # Bug fix: sourced directly from the user's own observed bug report
    # (a freshly-created Orc King's Home province had no Warg Riders
    # among its two recruit types) -- an Orcish King's second recruit
    # slot must always be Warg Riders, overriding the ordinary terrain-
    # based draw (even Jungle's own Elephants rule) for every terrain.
    rng = PascalRandom(seed=1)
    for terrain in (Terrain.PLAINS, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS):
        assert second_recruit_slot(terrain, rng, naval=False, king_race=Race.ORCISH) is ArmyType.WARG_RIDERS


def test_second_recruit_slot_orcish_king_naval_still_gets_fleet():
    # A King's own chosen Naval talent is a deliberate build choice
    # independent of race -- takes priority over the Orcish override.
    rng = PascalRandom(seed=1)
    assert second_recruit_slot(Terrain.PLAINS, rng, naval=True, king_race=Race.ORCISH) is ArmyType.FLEET


def test_second_recruit_slot_non_orcish_king_race_unaffected():
    rng = PascalRandom(seed=1)
    assert second_recruit_slot(Terrain.JUNGLE, rng, naval=False, king_race=Race.HUMAN) is ArmyType.ELEPHANTS


# -- User 2026-11-27: every King starts with a Rich and a Prosperous province next to his Home --------------------------

from ak_engine.worldgen.king_home_placement import (  # noqa: E402
    PROSPEROUS_TAX_RANGE,
    RICH_TAX_RANGE,
    ensure_home_wealth,
)


def _land_around(home: HexCoord, taxes: list[int], *, terrain: Terrain = Terrain.PLAINS):
    """A home with its neighbours' taxes set in order; everything else sea."""

    from ak_engine.turn.movement import neighbors

    bounds = MapBounds(12, 12)
    grid = {HexCoord(x, y): Terrain.SEA for x in range(12) for y in range(12)}
    grid[home] = Terrain.PLAINS
    tax_grid = {coord: 0 for coord in grid}
    around = neighbors(home, bounds)
    for coord, tax in zip(around, taxes):
        grid[coord] = terrain
        tax_grid[coord] = tax
    return grid, tax_grid, bounds, around


def _wealth(home, grid, tax_grid, bounds):
    from ak_engine.worldgen.king_home_placement import _neighbor_wealth

    return _neighbor_wealth(home, grid, tax_grid, bounds)


def test_a_home_already_blessed_with_both_is_left_alone():
    home = HexCoord(5, 5)
    grid, tax_grid, bounds, around = _land_around(home, [8, 4, 1, 1])
    before = dict(tax_grid)

    unsatisfied = ensure_home_wealth([home], grid, tax_grid, bounds, PascalRandom(1))

    assert unsatisfied == [] and tax_grid == before


def test_a_poor_neighbourhood_gets_a_rich_and_a_prosperous_province_without_touching_the_rest():
    home = HexCoord(5, 5)
    grid, tax_grid, bounds, around = _land_around(home, [1, 2, 0, 1])
    before = dict(tax_grid)

    unsatisfied = ensure_home_wealth([home], grid, tax_grid, bounds, PascalRandom(1))

    rich, prosperous = _wealth(home, grid, tax_grid, bounds)
    assert unsatisfied == [] and rich >= 1 and prosperous >= 1
    changed = [coord for coord in tax_grid if tax_grid[coord] != before[coord]]
    assert len(changed) == 2 and all(coord in around for coord in changed)
    assert any(RICH_TAX_RANGE[0] <= tax_grid[c] <= RICH_TAX_RANGE[1] for c in changed)
    assert any(PROSPEROUS_TAX_RANGE[0] <= tax_grid[c] <= PROSPEROUS_TAX_RANGE[1] for c in changed)


def test_the_repair_never_spends_the_only_prosperous_province_to_make_a_rich_one():
    home = HexCoord(5, 5)
    grid, tax_grid, bounds, around = _land_around(home, [6, 2, 1, 1])  # a Prosperous 6, the rest poor

    ensure_home_wealth([home], grid, tax_grid, bounds, PascalRandom(1))

    rich, prosperous = _wealth(home, grid, tax_grid, bounds)
    assert rich >= 1 and prosperous >= 1
    assert tax_grid[around[0]] == 6  # the Prosperous neighbour stayed what it was


def test_two_rich_neighbours_and_nothing_else_lower_one_to_prosperous():
    home = HexCoord(5, 5)
    grid, tax_grid, bounds, around = _land_around(home, [9, 8])

    unsatisfied = ensure_home_wealth([home], grid, tax_grid, bounds, PascalRandom(1))

    rich, prosperous = _wealth(home, grid, tax_grid, bounds)
    assert unsatisfied == [] and rich == 1 and prosperous == 1


def test_the_sea_around_serves_before_a_special_race_province_is_touched():
    home = HexCoord(5, 5)
    grid, tax_grid, bounds, around = _land_around(home, [1, 1])
    protected = frozenset(around[:2])  # the two land neighbours are special-race provinces

    unsatisfied = ensure_home_wealth([home], grid, tax_grid, bounds, PascalRandom(1), protected=protected)

    assert unsatisfied == []
    assert tax_grid[around[0]] == 1 and tax_grid[around[1]] == 1 and tax_grid[home] == 0
    assert any(tax_grid[c] >= 7 for c in around[2:]) and any(3 <= tax_grid[c] < 7 for c in around[2:])


def test_a_special_race_province_is_touched_only_as_a_last_resort():
    home = HexCoord(5, 5)
    grid, tax_grid, bounds, around = _land_around(home, [1, 1])

    unsatisfied = ensure_home_wealth([home], grid, tax_grid, bounds, PascalRandom(1), protected=frozenset(around))

    rich, prosperous = _wealth(home, grid, tax_grid, bounds)
    assert unsatisfied == [] and rich >= 1 and prosperous >= 1
    assert tax_grid[home] == 0  # a Home is never changed


def test_a_home_that_cannot_be_settled_is_reported():
    home = HexCoord(5, 5)
    grid = {home: Terrain.PLAINS}
    tax_grid = {home: 0}

    assert ensure_home_wealth([home], grid, tax_grid, MapBounds(12, 12), PascalRandom(1)) == [home]


def test_choose_king_home_prefers_a_home_with_both_a_rich_and_a_prosperous_neighbour():
    from ak_engine.turn.movement import neighbors

    bounds = MapBounds(30, 6)
    grid = {HexCoord(x, y): Terrain.PLAINS for x in range(30) for y in range(6)}
    race_grid = {coord: Race.HUMAN for coord in grid}
    tax_grid = {coord: 1 for coord in grid}
    lucky = HexCoord(15, 3)  # the neighbourhood we make rich and prosperous
    around = neighbors(lucky, bounds)
    tax_grid[around[0]] = 8
    tax_grid[around[1]] = 5

    for seed in range(1, 12):
        chosen = choose_king_home(grid, race_grid, bounds, [], PascalRandom(seed), naval=False, tax_grid=tax_grid)
        rich, prosperous = _wealth(chosen, grid, tax_grid, bounds)
        assert rich >= 1 and prosperous >= 1, (seed, chosen)
