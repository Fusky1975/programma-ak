from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.thief_ability_level_schedule import (
    THIEF_TEMPLATE,
    build_thief_ability_level_schedule,
)

# SANAMEDUMP.md's own reconstructed gameno=3 table -- see
# tactical_ability_level_schedule.py's own module docstring for the
# confidence-level caveat shared by all 7 new categories.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.THIEF_MASTERY_I,
    6: AdvancedAbility.THIEF_BANDITRY,
    7: AdvancedAbility.THIEF_PIRACY,
    8: AdvancedAbility.THIEF_MASTERY_II,
    9: AdvancedAbility.THIEF_MASTERY_III,
    10: AdvancedAbility.THIEF_TREASURY_RAIDS,
}


def test_build_thief_ability_level_schedule_matches_sanamedump_gameno_3():
    assert build_thief_ability_level_schedule(3) == GAME_3_EXPECTED


def test_thief_template_has_six_slots_across_four_distinct_abilities():
    assert len(THIEF_TEMPLATE) == 6
    assert set(THIEF_TEMPLATE) == {
        AdvancedAbility.THIEF_BANDITRY,
        AdvancedAbility.THIEF_PIRACY,
        AdvancedAbility.THIEF_TREASURY_RAIDS,
        AdvancedAbility.THIEF_MASTERY_I,
        AdvancedAbility.THIEF_MASTERY_II,
        AdvancedAbility.THIEF_MASTERY_III,
    }
    # IV/V are correctly unused -- only 3 of the 5 sourced mastery
    # ordinals are needed for this real template's own 3 recurring slots.
    assert AdvancedAbility.THIEF_MASTERY_IV not in THIEF_TEMPLATE
    assert AdvancedAbility.THIEF_MASTERY_V not in THIEF_TEMPLATE


def test_build_thief_ability_level_schedule_covers_all_six_levels():
    result = build_thief_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) <= set(THIEF_TEMPLATE)


def test_build_thief_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_thief_ability_level_schedule(42) == build_thief_ability_level_schedule(42)


def test_build_thief_ability_level_schedule_differs_across_game_numbers():
    assert build_thief_ability_level_schedule(1) != build_thief_ability_level_schedule(2)
