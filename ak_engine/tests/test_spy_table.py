from __future__ import annotations

import pytest

from ak_engine.turn.spy_table import estimate_reported_value, margin_of_error_fraction, pursue_catch_up_chance

from _helpers import ScriptedRandom


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


# -- Phase 265: "Margin of Error of Spy Reports" -----------------------------


@pytest.mark.parametrize(
    "level,expected_margin",
    [(0, 0.70), (1, 0.55), (2, 0.40), (3, 0.28), (4, 0.15)],
)
def test_margin_of_error_fraction_by_spy_level(level, expected_margin):
    assert margin_of_error_fraction(level) == pytest.approx(expected_margin)


def test_margin_of_error_fraction_is_clamped_to_the_tables_0_4_range():
    assert margin_of_error_fraction(99) == margin_of_error_fraction(4)
    assert margin_of_error_fraction(-5) == margin_of_error_fraction(0)


def test_estimate_reported_value_at_zero_offset_returns_the_true_value():
    # rng.random()=0.5 lands uniform(-margin, margin) at exactly 0.
    assert estimate_reported_value(100, 0, ScriptedRandom([0.5])) == 100


def test_estimate_reported_value_at_maximum_positive_offset():
    # Spy skill 0 -> 70% margin; rng.random()=1.0 -> +70% offset.
    assert estimate_reported_value(100, 0, ScriptedRandom([1.0])) == 170


def test_estimate_reported_value_at_maximum_negative_offset():
    # rng.random()=0.0 -> -70% offset.
    assert estimate_reported_value(100, 0, ScriptedRandom([0.0])) == 30


def test_estimate_reported_value_floors_at_zero_not_negative():
    assert estimate_reported_value(10, 0, ScriptedRandom([0.0])) == 3  # round(10*0.30) == 3, still positive
    assert estimate_reported_value(1, 0, ScriptedRandom([0.0])) == 0  # round(1*0.30) == 0, the actual floor case


def test_estimate_reported_value_margin_shrinks_at_higher_spy_skill():
    low_skill = estimate_reported_value(100, 0, ScriptedRandom([1.0]))
    high_skill = estimate_reported_value(100, 4, ScriptedRandom([1.0]))
    assert high_skill < low_skill
    assert high_skill == 115
