from __future__ import annotations

import pytest

from ak_engine.turn.spy_table import pursue_catch_up_chance


def test_same_kingdom_is_always_100_percent_regardless_of_everything_else():
    chance = pursue_catch_up_chance(0, target_leads_army=True, distance_provinces=10, same_kingdom=True)
    assert chance == 1.0


def test_same_province_distance_zero_is_treated_as_guaranteed():
    chance = pursue_catch_up_chance(0, target_leads_army=False, distance_provinces=0, same_kingdom=False)
    assert chance == 1.0


@pytest.mark.parametrize(
    "level,expected_base",
    [(0, 0.50), (1, 1.00), (2, 1.50), (3, 2.00), (4, 2.50)],
)
def test_base_chance_by_spy_level_at_distance_one(level, expected_base):
    chance = pursue_catch_up_chance(level, target_leads_army=False, distance_provinces=1, same_kingdom=False)
    assert chance == pytest.approx(min(expected_base, 1.0))


def test_spy_skill_is_clamped_to_the_tables_0_4_range():
    over = pursue_catch_up_chance(99, target_leads_army=False, distance_provinces=1, same_kingdom=False)
    at_max = pursue_catch_up_chance(4, target_leads_army=False, distance_provinces=1, same_kingdom=False)
    assert over == at_max

    under = pursue_catch_up_chance(-5, target_leads_army=False, distance_provinces=1, same_kingdom=False)
    at_min = pursue_catch_up_chance(0, target_leads_army=False, distance_provinces=1, same_kingdom=False)
    assert under == at_min


def test_target_leading_an_army_doubles_the_base_chance():
    without_army = pursue_catch_up_chance(0, target_leads_army=False, distance_provinces=1, same_kingdom=False)
    with_army = pursue_catch_up_chance(0, target_leads_army=True, distance_provinces=1, same_kingdom=False)
    assert with_army == pytest.approx(without_army * 2)


def test_chance_is_divided_by_distance_in_provinces():
    at_one = pursue_catch_up_chance(1, target_leads_army=False, distance_provinces=1, same_kingdom=False)
    at_two = pursue_catch_up_chance(1, target_leads_army=False, distance_provinces=2, same_kingdom=False)
    assert at_two == pytest.approx(at_one / 2)


def test_chance_is_capped_at_100_percent():
    chance = pursue_catch_up_chance(4, target_leads_army=True, distance_provinces=1, same_kingdom=False)
    assert chance == 1.0  # raw formula would be 500%
