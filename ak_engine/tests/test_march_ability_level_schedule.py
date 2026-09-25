from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.march_ability_level_schedule import (
    MARCH_TEMPLATE,
    build_march_ability_level_schedule,
)

# The real, sourced level order (Phase 357/768) -- fixed, not per-game,
# since March's own real build is the identity mapping `slot := j` (see
# march_ability_level_schedule.py's own module docstring).
EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.MARCH_THROUGH_FLOODS,
    6: AdvancedAbility.MARCH_CAVALRY,
    7: AdvancedAbility.MARCH_INFANTRY,
    8: AdvancedAbility.MARCH_CAVALRY_MASTERY,
    9: AdvancedAbility.MARCH_INFANTRY_MASTERY,
    10: AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY,
}


def test_build_march_ability_level_schedule_matches_the_real_sourced_order():
    assert build_march_ability_level_schedule(3) == EXPECTED


def test_march_template_has_six_distinct_abilities():
    assert len(MARCH_TEMPLATE) == 6
    assert len(set(MARCH_TEMPLATE)) == 6
    assert set(MARCH_TEMPLATE) == {
        AdvancedAbility.MARCH_THROUGH_FLOODS,
        AdvancedAbility.MARCH_CAVALRY,
        AdvancedAbility.MARCH_INFANTRY,
        AdvancedAbility.MARCH_CAVALRY_MASTERY,
        AdvancedAbility.MARCH_INFANTRY_MASTERY,
        AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY,
    }


def test_build_march_ability_level_schedule_covers_all_six_levels():
    result = build_march_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) == set(MARCH_TEMPLATE)


def test_build_march_ability_level_schedule_never_varies_by_game_number():
    # Unlike every sibling schedule, March's own real build consumes no
    # IRand at all -- the level assignment is identical in every game.
    assert build_march_ability_level_schedule(1) == build_march_ability_level_schedule(2)
    assert build_march_ability_level_schedule(42) == build_march_ability_level_schedule(900)
