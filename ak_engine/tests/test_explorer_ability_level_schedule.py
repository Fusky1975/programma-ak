from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.explorer_ability_level_schedule import (
    EXPLORER_TEMPLATE,
    build_explorer_ability_level_schedule,
)

# The real worked examples from AKGEN_reverse_engineering_report (3).md
# Part IV section 48. GW3's own game_number=3 is independently confirmed
# via the local GW3__T1 world file's own parsed header; GW900 is taken
# literally from the dossier's own worked example (see module docstring).
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN,
    6: AdvancedAbility.EXPLORER_FIND_WATER,
    7: AdvancedAbility.EXPLORER_MILITARY_MAPS,
    8: AdvancedAbility.EXPLORERS_SOCIETY_MAPS,
    9: AdvancedAbility.EXPLORER_FIND_MINES,
    10: AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES,
}

GAME_900_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.EXPLORER_MILITARY_MAPS,
    6: AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN,
    7: AdvancedAbility.EXPLORER_FIND_MINES,
    8: AdvancedAbility.EXPLORERS_SOCIETY_MAPS,
    9: AdvancedAbility.EXPLORER_FIND_WATER,
    10: AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES,
}


def test_build_explorer_ability_level_schedule_matches_the_real_game_3_example_exactly():
    assert build_explorer_ability_level_schedule(3) == GAME_3_EXPECTED


def test_build_explorer_ability_level_schedule_matches_the_real_game_900_example_exactly():
    assert build_explorer_ability_level_schedule(900) == GAME_900_EXPECTED


def test_explorer_template_has_six_distinct_abilities():
    assert len(EXPLORER_TEMPLATE) == 6
    assert len(set(EXPLORER_TEMPLATE)) == 6
    assert set(EXPLORER_TEMPLATE) == {
        AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN,
        AdvancedAbility.EXPLORER_MILITARY_MAPS,
        AdvancedAbility.EXPLORERS_SOCIETY_MAPS,
        AdvancedAbility.EXPLORER_FIND_WATER,
        AdvancedAbility.EXPLORER_FIND_MINES,
        AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES,
    }


def test_build_explorer_ability_level_schedule_covers_all_six_levels():
    result = build_explorer_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) == set(EXPLORER_TEMPLATE)


def test_build_explorer_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_explorer_ability_level_schedule(42) == build_explorer_ability_level_schedule(42)


def test_build_explorer_ability_level_schedule_differs_across_game_numbers():
    # Not a mathematical guarantee, but true for this sample and a useful
    # smoke check that game_number actually drives the outcome.
    assert build_explorer_ability_level_schedule(1) != build_explorer_ability_level_schedule(2)
