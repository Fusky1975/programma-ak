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
