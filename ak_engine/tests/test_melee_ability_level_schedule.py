from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.melee_ability_level_schedule import (
    MELEE_TEMPLATE,
    build_melee_ability_level_schedule,
)

# SANAMEDUMP.md's own reconstructed gameno=3 table -- see
# tactical_ability_level_schedule.py's own module docstring for the
# confidence-level caveat shared by all 7 new categories.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.MELEE_EVASION,
    6: AdvancedAbility.MELEE_MASTERY,
    7: AdvancedAbility.MELEE_MASTERY,
    8: AdvancedAbility.MELEE_CONTROL_TEMPER,
    9: AdvancedAbility.MELEE_MASTERY,
    10: AdvancedAbility.MELEE_HIT_POINTS,
}


def test_build_melee_ability_level_schedule_matches_sanamedump_gameno_3():
    assert build_melee_ability_level_schedule(3) == GAME_3_EXPECTED


def test_melee_template_has_six_slots_with_mastery_repeated_and_no_true_mastery():
    assert len(MELEE_TEMPLATE) == 6
    assert set(MELEE_TEMPLATE) == {
        AdvancedAbility.MELEE_EVASION,
        AdvancedAbility.MELEE_MASTERY,
        AdvancedAbility.MELEE_CONTROL_TEMPER,
        AdvancedAbility.MELEE_HIT_POINTS,
    }
    assert MELEE_TEMPLATE.count(AdvancedAbility.MELEE_MASTERY) == 3
    # Confirmed structurally unreachable (SANAMEDUMP.md's own analysis);
    # True Mastery's own distinct tagline never appears in this template.
    assert AdvancedAbility.MELEE_DUELLISTS_MEDAL not in MELEE_TEMPLATE
    assert AdvancedAbility.MELEE_TRUE_MASTERY not in MELEE_TEMPLATE


def test_build_melee_ability_level_schedule_covers_all_six_levels():
    result = build_melee_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) <= set(MELEE_TEMPLATE)


def test_build_melee_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_melee_ability_level_schedule(42) == build_melee_ability_level_schedule(42)


def test_build_melee_ability_level_schedule_differs_across_game_numbers():
    assert build_melee_ability_level_schedule(1) != build_melee_ability_level_schedule(2)
