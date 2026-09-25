from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.spy_ability_level_schedule import (
    SPY_TEMPLATE,
    build_spy_ability_level_schedule,
)

# SANAMEDUMP.md's own reconstructed gameno=3 table -- see
# tactical_ability_level_schedule.py's own module docstring for the
# confidence-level caveat shared by all 7 new categories.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.SPY_BLACKMAIL,
    6: AdvancedAbility.SPY_SUPER_SLEUTH,
    7: AdvancedAbility.SPY_EXPANDED_SPYING,
    8: AdvancedAbility.SPY_BRAINWASH,
    9: AdvancedAbility.SPY_ASSASSINATE,
    10: AdvancedAbility.SPY_DOUBLE_AGENT,
}


def test_build_spy_ability_level_schedule_matches_sanamedump_gameno_3():
    assert build_spy_ability_level_schedule(3) == GAME_3_EXPECTED


def test_spy_template_has_six_distinct_abilities():
    assert len(SPY_TEMPLATE) == 6
    assert len(set(SPY_TEMPLATE)) == 6
    assert set(SPY_TEMPLATE) == {
        AdvancedAbility.SPY_BLACKMAIL,
        AdvancedAbility.SPY_DOUBLE_AGENT,
        AdvancedAbility.SPY_SUPER_SLEUTH,
        AdvancedAbility.SPY_EXPANDED_SPYING,
        AdvancedAbility.SPY_BRAINWASH,
        AdvancedAbility.SPY_ASSASSINATE,
    }


def test_build_spy_ability_level_schedule_covers_all_six_levels():
    result = build_spy_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) == set(SPY_TEMPLATE)


def test_build_spy_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_spy_ability_level_schedule(42) == build_spy_ability_level_schedule(42)


def test_build_spy_ability_level_schedule_differs_across_game_numbers():
    assert build_spy_ability_level_schedule(1) != build_spy_ability_level_schedule(2)
