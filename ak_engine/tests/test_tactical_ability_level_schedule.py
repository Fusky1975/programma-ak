from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.tactical_ability_level_schedule import (
    TACTICAL_TEMPLATE,
    build_tactical_ability_level_schedule,
)

# SANAMEDUMP.md's own reconstructed gameno=3 table ("Tabella ricostruita
# per gameno=3") -- unlike Naval/Explorer's own dual GW3/GW900 real
# anchors, this is the *document's own* prediction (internally
# consistent with its own cumulative/32000 algorithm), not yet
# cross-checked against an independent real save file. See
# tactical_ability_level_schedule.py's own module docstring for the
# full confidence-level caveat.
GAME_3_EXPECTED: dict[int, AdvancedAbility] = {
    5: AdvancedAbility.TACTICAL_WARGAMES_MASTERY,
    6: AdvancedAbility.TACTICAL_MASTERY_15,
    7: AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN,
    8: AdvancedAbility.TACTICAL_MASTERY_15,
    9: AdvancedAbility.TACTICAL_COMBINED_ARMS,
    10: AdvancedAbility.TACTICAL_MASTERY_15,
}


def test_build_tactical_ability_level_schedule_matches_sanamedump_gameno_3():
    assert build_tactical_ability_level_schedule(3) == GAME_3_EXPECTED


def test_tactical_template_has_six_slots_with_the_15_percent_tier_repeated():
    assert len(TACTICAL_TEMPLATE) == 6
    assert set(TACTICAL_TEMPLATE) == {
        AdvancedAbility.TACTICAL_WARGAMES_MASTERY,
        AdvancedAbility.TACTICAL_MASTERY_15,
        AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN,
        AdvancedAbility.TACTICAL_COMBINED_ARMS,
    }
    assert TACTICAL_TEMPLATE.count(AdvancedAbility.TACTICAL_MASTERY_15) == 3
    # Confirmed structurally unreachable by SANAMEDUMP.md's own analysis.
    assert AdvancedAbility.TACTICAL_MASTERY_10 not in TACTICAL_TEMPLATE
    assert AdvancedAbility.TACTICAL_MASTERY_20 not in TACTICAL_TEMPLATE


def test_build_tactical_ability_level_schedule_covers_all_six_levels():
    result = build_tactical_ability_level_schedule(1234)
    assert set(result.keys()) == {5, 6, 7, 8, 9, 10}
    assert set(result.values()) <= set(TACTICAL_TEMPLATE)


def test_build_tactical_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_tactical_ability_level_schedule(42) == build_tactical_ability_level_schedule(42)


def test_build_tactical_ability_level_schedule_differs_across_game_numbers():
    assert build_tactical_ability_level_schedule(1) != build_tactical_ability_level_schedule(2)
