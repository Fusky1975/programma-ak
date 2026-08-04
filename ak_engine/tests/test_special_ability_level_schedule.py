from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.enums import Ability
from ak_engine.worldgen.special_ability_level_schedule import (
    LEVEL_SLOTS,
    MAGIC_ABILITY_TEMPLATE,
    MAGIC_COLLEGES,
    build_magic_ability_level_schedule,
)

# The real, complete worked example from the AKGEN reverse-engineering
# material's own `game_900_magic_schedule`, translated from its bare
# strings onto this project's own `AdvancedAbility` vocabulary (see
# module docstring's cross-check table for the name mapping used).
GAME_900_EXPECTED: dict[Ability, dict[int, AdvancedAbility]] = {
    Ability.WHITE: {
        5: AdvancedAbility.HOLY_PLACES,
        6: AdvancedAbility.WORDS_OF_HEALING_SPELL,
        7: AdvancedAbility.ENHANCED_HOLY_SYMBOL,
        8: AdvancedAbility.KNOW_ALIGNMENT_TALENT,
        9: AdvancedAbility.ENHANCED_RESURRECTION,
        10: AdvancedAbility.GATE_ANGEL_SPELL,
    },
    Ability.NECROMANCY: {
        5: AdvancedAbility.GATE_DEMON_SPELL,
        6: AdvancedAbility.DARK_PLACES,
        7: AdvancedAbility.WITCHSIGHT_TALENT,
        8: AdvancedAbility.ENHANCED_SKELETAL_UNITS,
        9: AdvancedAbility.SCAR_TERRAIN_SPELL,
        10: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS,
    },
    Ability.ELEMENTAL: {
        5: AdvancedAbility.LAVA_POOL_SPELL,
        6: AdvancedAbility.ELEMENTAL_PLACES,
        7: AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS,
        8: AdvancedAbility.MYSTIC_WINDS_SPELL,
        9: AdvancedAbility.ENHANCED_EARTHQUAKE,
        10: AdvancedAbility.MAKE_GEMS_TALENT,
    },
    Ability.PSYCHIC: {
        5: AdvancedAbility.AUGUR_COMBAT_SPELL,
        6: AdvancedAbility.PSYCHIC_PLACES,
        7: AdvancedAbility.SENSE_DANGER_TALENT,
        8: AdvancedAbility.ENHANCED_CHARM,
        9: AdvancedAbility.LOCATE_OBJECT_SPELL,
        10: AdvancedAbility.ENHANCED_CLAIRVOYANCE,
    },
    Ability.ILLUSION: {
        5: AdvancedAbility.ILLUSORY_HERO_SPELL,
        6: AdvancedAbility.ILLUSORY_PLACES,
        7: AdvancedAbility.DETECT_ILLUSIONS_TALENT,
        8: AdvancedAbility.ENHANCED_INVISIBILITY,
        9: AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN,
        10: AdvancedAbility.ILLUSORY_FOG_SPELL,
    },
}


def test_build_magic_ability_level_schedule_matches_the_real_game_900_example_exactly():
    assert build_magic_ability_level_schedule(900) == GAME_900_EXPECTED


def test_magic_ability_template_covers_all_five_colleges_with_six_items_each():
    assert set(MAGIC_ABILITY_TEMPLATE.keys()) == set(MAGIC_COLLEGES)
    for ability in MAGIC_COLLEGES:
        assert len(MAGIC_ABILITY_TEMPLATE[ability]) == 6
        assert len(set(MAGIC_ABILITY_TEMPLATE[ability])) == 6


def test_magic_colleges_are_exactly_the_five_real_magic_abilities():
    assert set(MAGIC_COLLEGES) == {
        Ability.WHITE,
        Ability.NECROMANCY,
        Ability.ELEMENTAL,
        Ability.PSYCHIC,
        Ability.ILLUSION,
    }


def test_build_magic_ability_level_schedule_covers_all_six_levels_per_college():
    result = build_magic_ability_level_schedule(1234)
    for ability in MAGIC_COLLEGES:
        assert set(result[ability].keys()) == set(LEVEL_SLOTS)
        assert set(result[ability].values()) == set(MAGIC_ABILITY_TEMPLATE[ability])


def test_build_magic_ability_level_schedule_is_deterministic_for_the_same_game_number():
    assert build_magic_ability_level_schedule(42) == build_magic_ability_level_schedule(42)


def test_build_magic_ability_level_schedule_differs_across_game_numbers():
    # Not a mathematical guarantee, but true for this sample and a useful
    # smoke check that game_number actually drives the outcome.
    assert build_magic_ability_level_schedule(1) != build_magic_ability_level_schedule(2)
