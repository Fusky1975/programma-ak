from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.naval_ability_level_schedule import (
    NAVAL_TEMPLATE,
    build_naval_ability_level_schedule,
)

# The real worked examples from AKGEN_reverse_engineering_report (3).md
# SS105, empirically verified (see module docstring) -- both GW3 and
# GW900's own full 6-level results match this module's own cumulative/
# 32000 algorithm exactly.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.NAVAL_LONG_DEFEND,
    6: AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    7: AdvancedAbility.NAVAL_COMBINED_ARMS,
    8: AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    9: AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    10: AdvancedAbility.NAVAL_HUG_COASTLINE,
}

GAME_900_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.NAVAL_LONG_DEFEND,
    6: AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    7: AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    8: AdvancedAbility.NAVAL_COMBINED_ARMS,
    9: AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    10: AdvancedAbility.NAVAL_HUG_COASTLINE,
}


def test_build_naval_ability_level_schedule_matches_the_real_game_3_example_exactly():
    assert build_naval_ability_level_schedule(3) == GAME_3_EXPECTED


def test_build_naval_ability_level_schedule_matches_the_real_game_900_example_exactly():
    assert build_naval_ability_level_schedule(900) == GAME_900_EXPECTED


def test_naval_template_has_six_slots_over_four_distinct_abilities():
    assert len(NAVAL_TEMPLATE) == 6
    assert set(NAVAL_TEMPLATE) == {
        AdvancedAbility.NAVAL_LONG_DEFEND,
        AdvancedAbility.NAVAL_MASTERY_GREAT_15,
        AdvancedAbility.NAVAL_COMBINED_ARMS,
        AdvancedAbility.NAVAL_HUG_COASTLINE,
    }
    assert NAVAL_TEMPLATE.count(AdvancedAbility.NAVAL_MASTERY_GREAT_15) == 3


def test_build_naval_ability_level_schedule_covers_all_six_levels():
    result = build_naval_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) <= set(NAVAL_TEMPLATE)


def test_build_naval_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_naval_ability_level_schedule(42) == build_naval_ability_level_schedule(42)


def test_build_naval_ability_level_schedule_differs_across_game_numbers():
    # Not a mathematical guarantee, but true for this sample and a useful
    # smoke check that game_number actually drives the outcome.
    assert build_naval_ability_level_schedule(1) != build_naval_ability_level_schedule(2)
