from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.sage_ability_level_schedule import (
    SAGE_TEMPLATE,
    build_sage_ability_level_schedule,
)

# SANAMEDUMP.md's own reconstructed gameno=3 table -- see
# tactical_ability_level_schedule.py's own module docstring for the
# confidence-level caveat shared by all 7 new categories. Sage's own
# raw content is degenerate (the identical row for all 6 slots -- see
# sage_ability_level_schedule.py's own module docstring), so this
# fixture mainly exercises which ordinal lands on which level, not
# distinguishable real content.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.SUPER_SAGE_II,
    6: AdvancedAbility.SUPER_SAGE_I,
    7: AdvancedAbility.SUPER_SAGE_III,
    8: AdvancedAbility.SUPER_SAGE_IV,
    9: AdvancedAbility.SUPER_SAGE_V,
    10: AdvancedAbility.SUPER_SAGE_I,
}


def test_build_sage_ability_level_schedule_matches_sanamedump_gameno_3():
    assert build_sage_ability_level_schedule(3) == GAME_3_EXPECTED


def test_sage_template_has_six_slots_over_five_distinct_ordinals():
    assert len(SAGE_TEMPLATE) == 6
    assert set(SAGE_TEMPLATE) == {
        AdvancedAbility.SUPER_SAGE_I,
        AdvancedAbility.SUPER_SAGE_II,
        AdvancedAbility.SUPER_SAGE_III,
        AdvancedAbility.SUPER_SAGE_IV,
        AdvancedAbility.SUPER_SAGE_V,
    }
    assert SAGE_TEMPLATE.count(AdvancedAbility.SUPER_SAGE_I) == 2


def test_build_sage_ability_level_schedule_covers_all_six_levels():
    result = build_sage_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) <= set(SAGE_TEMPLATE)


def test_build_sage_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_sage_ability_level_schedule(42) == build_sage_ability_level_schedule(42)


def test_build_sage_ability_level_schedule_differs_across_game_numbers():
    assert build_sage_ability_level_schedule(1) != build_sage_ability_level_schedule(2)
