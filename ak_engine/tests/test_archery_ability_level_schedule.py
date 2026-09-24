from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.archery_ability_level_schedule import (
    ARCHERY_TEMPLATE,
    build_archery_ability_level_schedule,
)

# SANAMEDUMP.md's own reconstructed gameno=3 table -- see
# tactical_ability_level_schedule.py's own module docstring for the
# confidence-level caveat shared by all 7 new categories.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.SHORT_RANGE_ARCHERY,
    6: AdvancedAbility.ARCHERY_FREE_ATTACK,
    7: AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY,
    8: AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY,
    9: AdvancedAbility.LONG_RANGE_ARCHERY,
    10: AdvancedAbility.ARCHERY_FREE_ATTACK,
}


def test_build_archery_ability_level_schedule_matches_sanamedump_gameno_3():
    assert build_archery_ability_level_schedule(3) == GAME_3_EXPECTED


def test_archery_template_has_six_slots_with_free_attack_repeated():
    assert len(ARCHERY_TEMPLATE) == 6
    assert set(ARCHERY_TEMPLATE) == {
        AdvancedAbility.ARCHERY_FREE_ATTACK,
        AdvancedAbility.SHORT_RANGE_ARCHERY,
        AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY,
        AdvancedAbility.LONG_RANGE_ARCHERY,
        AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY,
    }
    assert ARCHERY_TEMPLATE.count(AdvancedAbility.ARCHERY_FREE_ATTACK) == 2


def test_build_archery_ability_level_schedule_covers_all_six_levels():
    result = build_archery_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) <= set(ARCHERY_TEMPLATE)


def test_build_archery_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_archery_ability_level_schedule(42) == build_archery_ability_level_schedule(42)


def test_build_archery_ability_level_schedule_differs_across_game_numbers():
    assert build_archery_ability_level_schedule(1) != build_archery_ability_level_schedule(3)
