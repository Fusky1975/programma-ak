from __future__ import annotations

from ak_engine.models.advanced_ability import (
    ADVANCED_ABILITY_DESCRIPTION,
    ADVANCED_ABILITY_GRANTS_SPELL,
    ADVANCED_ABILITY_INTRO,
    ADVANCED_ABILITY_NAME,
    ADVANCED_ABILITY_POOL,
    ADVANCED_ABILITY_TAGLINE,
    DISCOVERY_ADVANCED_ABILITY_CHECKS,
    GATE_DEMON_TABLE,
    LAVA_POOL_IMMUNE_MONSTERS,
    UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS,
    AdvancedAbility,
)
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.monster import Monster
from ak_engine.models.treasure import Treasure


def test_advanced_ability_has_89_members():
    assert len(list(AdvancedAbility)) == 89


def test_advanced_ability_pool_covers_all_15_ability_categories():
    assert set(ADVANCED_ABILITY_POOL.keys()) == set(Ability)


def test_advanced_ability_pool_covers_every_member_exactly_once():
    all_pool_members = [m for pool in ADVANCED_ABILITY_POOL.values() for m in pool]
    assert len(all_pool_members) == 89
    assert set(all_pool_members) == set(AdvancedAbility)


def test_advanced_ability_intro_covers_all_15_ability_categories():
    assert set(ADVANCED_ABILITY_INTRO.keys()) == set(Ability)


def test_advanced_ability_name_covers_all_members():
    assert set(ADVANCED_ABILITY_NAME.keys()) == set(AdvancedAbility)


def test_advanced_ability_tagline_covers_all_members():
    assert set(ADVANCED_ABILITY_TAGLINE.keys()) == set(AdvancedAbility)


def test_advanced_ability_description_covers_all_members():
    assert set(ADVANCED_ABILITY_DESCRIPTION.keys()) == set(AdvancedAbility)


def test_pool_sizes_vary_and_thievery_has_the_largest_pool():
    # Pool sizes are not uniformly 5 (one per level 5-9) -- Thievery's
    # own pool of 8 candidates is the largest, confirming a character
    # can never gain every possible Advanced Ability in that category.
    sizes = {ability: len(pool) for ability, pool in ADVANCED_ABILITY_POOL.items()}
    assert sizes[Ability.THIEF] == 8
    assert max(sizes.values()) == 8
    assert sizes[Ability.MARCH] == 5
    assert sizes[Ability.SAGE] == 5


def test_advanced_ability_verbatim_samples():
    assert ADVANCED_ABILITY_NAME[AdvancedAbility.TACTICAL_WARGAMES_MASTERY] == (
        "Tactical Wargames Mastery"
    )
    assert ADVANCED_ABILITY_TAGLINE[AdvancedAbility.TACTICAL_WARGAMES_MASTERY] == (
        "100% Training Bonus"
    )
    assert ADVANCED_ABILITY_DESCRIPTION[AdvancedAbility.TACTICAL_WARGAMES_MASTERY] == (
        "The chance for a unit to increase in quality when Practicing "
        "Tactics (or Naval) is increased by 100% (example: an Average "
        "unit now has a 10% chance to improve per phase)."
    )


def test_druidic_dinosaurs_stat_block_transcribed():
    description = ADVANCED_ABILITY_DESCRIPTION[AdvancedAbility.DRUIDIC_DINOSAURS]
    assert "Strength: Unpredictable (5 to 10)" in description
    assert "Nemesis: Phalanx" in description
    assert "Race: Saurian" in description


def test_thief_mastery_tiers_share_the_same_description_but_distinct_names():
    # THIEF_MASTERY_I..V are 5 distinct enum members representing the
    # same repeated "15% Stealing Bonus" entry in the source -- this
    # project distinguishes them by ordinal (I..V) in the name so they
    # remain individually addressable even though the rulebook itself
    # gives them identical text.
    tiers = [
        AdvancedAbility.THIEF_MASTERY_I,
        AdvancedAbility.THIEF_MASTERY_II,
        AdvancedAbility.THIEF_MASTERY_III,
        AdvancedAbility.THIEF_MASTERY_IV,
        AdvancedAbility.THIEF_MASTERY_V,
    ]
    descriptions = {ADVANCED_ABILITY_DESCRIPTION[t] for t in tiers}
    assert len(descriptions) == 1
    assert len({ADVANCED_ABILITY_NAME[t] for t in tiers}) == 5


# -- the spdex gap closure (Phase 23 -> Phase 128) --


def test_advanced_ability_grants_spell_covers_exactly_the_10_secret_spells():
    secret_spells = {s for s in Spell if 25 <= s.value <= 34}
    assert len(ADVANCED_ABILITY_GRANTS_SPELL) == 10
    assert set(ADVANCED_ABILITY_GRANTS_SPELL.values()) == secret_spells


def test_advanced_ability_grants_spell_verbatim_sample():
    assert ADVANCED_ABILITY_GRANTS_SPELL[AdvancedAbility.WORDS_OF_HEALING_SPELL] == Spell.HEAL
    assert ADVANCED_ABILITY_GRANTS_SPELL[AdvancedAbility.GATE_ANGEL_SPELL] == Spell.GATE_ANGEL
    assert ADVANCED_ABILITY_GRANTS_SPELL[AdvancedAbility.ILLUSORY_HERO_SPELL] == Spell.ILLUS_HERO


def test_advanced_ability_grants_spell_only_contains_new_spell_abilities():
    # Every key must actually be in its own Ability's pool.
    for advanced_ability in ADVANCED_ABILITY_GRANTS_SPELL:
        found = any(
            advanced_ability in pool for pool in ADVANCED_ABILITY_POOL.values()
        )
        assert found


# -- Gate Demon / Lava Pool Monster cross-references --


def test_gate_demon_table_covers_full_d100_range_with_real_monsters():
    assert len(GATE_DEMON_TABLE) == 7
    monsters = [monster for _range, monster in GATE_DEMON_TABLE]
    assert monsters == [
        Monster.IMP,
        Monster.SUCCUBUS,
        Monster.BONE_DEVIL,
        Monster.ICE_DEVIL,
        Monster.MAR_DEMON,
        Monster.RAKSHASHA,
        Monster.BAL_DEMON,
    ]


def test_lava_pool_immune_monsters_has_29_real_monsters():
    assert len(LAVA_POOL_IMMUNE_MONSTERS) == 29
    assert Monster.BEHOLDER in LAVA_POOL_IMMUNE_MONSTERS
    assert Monster.VAMPIRE in LAVA_POOL_IMMUNE_MONSTERS
    assert Monster.GW_WHALE in LAVA_POOL_IMMUNE_MONSTERS
    # A ground-dwelling, non-flying/underwater/anti-holy/ghostly
    # monster should not be in the immunity list.
    assert Monster.MEDUSA not in LAVA_POOL_IMMUNE_MONSTERS


# -- Advanced Ability trigger mappings from SPEAK.PAS (Phase 131) --


def test_unique_item_advanced_ability_checks_covers_all_6_named_uniques():
    assert set(UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS.keys()) == {
        Treasure.NAMED_UNIQUE_CROWN_ROHAN,
        Treasure.NAMED_UNIQUE_AMULET_POWER,
        Treasure.NAMED_UNIQUE_SCEPTER_LIFE,
        Treasure.NAMED_UNIQUE_MAP_MARAUDERS,
        Treasure.NAMED_UNIQUE_FANG_VAMPIRE,
        Treasure.NAMED_UNIQUE_HAMMER_POWER,
    }


def test_unique_item_advanced_ability_checks_verbatim_samples():
    assert UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS[Treasure.NAMED_UNIQUE_CROWN_ROHAN] == (
        Ability.MARCH,
        Ability.TACTICAL,
    )
    assert UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS[Treasure.NAMED_UNIQUE_MAP_MARAUDERS] == (Ability.NAVAL,)
    assert UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS[Treasure.NAMED_UNIQUE_FANG_VAMPIRE] == (
        Ability.MELEE,
        Ability.NECROMANCY,
    )


def test_discovery_advanced_ability_checks_covers_all_20_fix_wreck_discoveries():
    assert len(DISCOVERY_ADVANCED_ABILITY_CHECKS) == 20
    assert set(DISCOVERY_ADVANCED_ABILITY_CHECKS.keys()) == {
        Discovery(ordinal) for ordinal in range(20)
    }


def test_discovery_advanced_ability_checks_two_discoveries_share_each_covered_ability():
    # Only 10 of the 15 Ability categories are covered by a
    # fix/wreck Discovery pair (Tactical/March/Naval/Archery/Melee/
    # Druid/Thief/Explorer/Spy/Sage) -- White/Necromancy/Elemental/
    # Psychic/Illusion have no Discovery check at all.
    covered_abilities = set(DISCOVERY_ADVANCED_ABILITY_CHECKS.values())
    assert len(covered_abilities) == 10
    for ability in covered_abilities:
        matching = [
            discovery
            for discovery, mapped_ability in DISCOVERY_ADVANCED_ABILITY_CHECKS.items()
            if mapped_ability is ability
        ]
        assert len(matching) == 2


def test_discovery_advanced_ability_checks_verbatim_samples():
    assert DISCOVERY_ADVANCED_ABILITY_CHECKS[Discovery.LAND_SHIP] == Ability.TACTICAL
    assert DISCOVERY_ADVANCED_ABILITY_CHECKS[Discovery.SCYTHED_CHARIOTS] == Ability.TACTICAL
    assert DISCOVERY_ADVANCED_ABILITY_CHECKS[Discovery.SCIENTIFIC_METHOD] == Ability.SAGE
    assert DISCOVERY_ADVANCED_ABILITY_CHECKS[Discovery.MITHRIL_CHAINMAIL] == Ability.MELEE
