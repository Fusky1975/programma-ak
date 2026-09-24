from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.druid_ability_level_schedule import (
    DRUID_TEMPLATE,
    build_druid_ability_level_schedule,
)

# SANAMEDUMP.md's own reconstructed gameno=3 table -- see
# tactical_ability_level_schedule.py's own module docstring for the
# confidence-level caveat shared by all 7 new categories.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.DRUIDIC_HORSE_CONTROL,
    6: AdvancedAbility.DRUIDIC_WHALE_TRANSPORT,
    7: AdvancedAbility.DRUIDIC_TRANSPORT,
    8: AdvancedAbility.DRUIDIC_DINOSAURS,
    9: AdvancedAbility.DRUIDIC_TRADES,
    10: AdvancedAbility.DRUIDIC_ANIMAL_SPIES,
}


def test_build_druid_ability_level_schedule_matches_sanamedump_gameno_3():
    assert build_druid_ability_level_schedule(3) == GAME_3_EXPECTED


def test_druid_template_has_six_distinct_abilities():
    assert len(DRUID_TEMPLATE) == 6
    assert len(set(DRUID_TEMPLATE)) == 6
    assert set(DRUID_TEMPLATE) == {
        AdvancedAbility.DRUIDIC_ANIMAL_SPIES,
        AdvancedAbility.DRUIDIC_WHALE_TRANSPORT,
        AdvancedAbility.DRUIDIC_TRANSPORT,
        AdvancedAbility.DRUIDIC_HORSE_CONTROL,
        AdvancedAbility.DRUIDIC_DINOSAURS,
        AdvancedAbility.DRUIDIC_TRADES,
    }


def test_build_druid_ability_level_schedule_covers_all_six_levels():
    result = build_druid_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) == set(DRUID_TEMPLATE)


def test_build_druid_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_druid_ability_level_schedule(42) == build_druid_ability_level_schedule(42)


def test_build_druid_ability_level_schedule_differs_across_game_numbers():
    assert build_druid_ability_level_schedule(1) != build_druid_ability_level_schedule(2)
