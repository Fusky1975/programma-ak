from __future__ import annotations

from ak_engine.models.enums import Ability, Spell
from ak_engine.models.treasure import (
    TREASURE_ABILITY_ITEM,
    TREASURE_BOOK_ABILITY,
    TREASURE_CATEGORY,
    TREASURE_LABEL,
    TREASURE_NAME,
    TREASURE_WAND_SPELL,
    USE_MI_TARGET_CATEGORIES,
    Treasure,
    TreasureCategory,
)


def test_treasure_enum_has_113_declared_values():
    assert len(Treasure) == 113
    assert sorted(t.value for t in Treasure) == list(range(113))
    assert Treasure.ABILITY_TACTICAL.value == 0
    assert Treasure.UNUSED_20.value == 112


def test_every_treasure_has_a_category():
    assert set(TREASURE_CATEGORY.keys()) == set(Treasure)


def test_category_group_sizes_match_the_pascal_declaration():
    counts: dict[TreasureCategory, int] = {}
    for category in TREASURE_CATEGORY.values():
        counts[category] = counts.get(category, 0) + 1
    assert counts == {
        TreasureCategory.ABILITY_ITEM: 15,
        TreasureCategory.SPELL_WAND: 20,
        TreasureCategory.COMBAT_WEAPON: 5,
        TreasureCategory.LEADERSHIP_WEAPON: 4,
        TreasureCategory.ANTI_MAGIC_AMULET: 5,
        TreasureCategory.MONSTER_COMMAND_ITEM: 3,
        TreasureCategory.SKILL_BOOK: 15,
        TreasureCategory.GOLD_HOARD: 3,
        TreasureCategory.QUEST_ITEM: 22,
        TreasureCategory.SENTINEL: 1,
        TreasureCategory.NAMED_UNIQUE: 6,
        TreasureCategory.UNUSED_EXTENSION: 14,
    }


def test_use_mi_target_categories_are_exactly_wands_and_books():
    assert USE_MI_TARGET_CATEGORIES == {TreasureCategory.SPELL_WAND, TreasureCategory.SKILL_BOOK}


def test_ability_item_maps_1to1_onto_ability_in_order():
    assert TREASURE_ABILITY_ITEM[Treasure.ABILITY_TACTICAL] is Ability.TACTICAL
    assert TREASURE_ABILITY_ITEM[Treasure.ABILITY_SAGE] is Ability.SAGE
    assert len(TREASURE_ABILITY_ITEM) == 15


def test_wand_spell_maps_1to1_onto_first_20_spell_ordinals():
    assert TREASURE_WAND_SPELL[Treasure.WAND_RESURRECTION] is Spell.RESURRECTION
    assert TREASURE_WAND_SPELL[Treasure.WAND_INVISIBILITY] is Spell.INVISIBILITY
    assert len(TREASURE_WAND_SPELL) == 20
    assert Spell.SPIRITWRACK not in TREASURE_WAND_SPELL.values()


def test_book_ability_maps_1to1_onto_ability_in_order():
    assert TREASURE_BOOK_ABILITY[Treasure.BOOK_TACTICAL] is Ability.TACTICAL
    assert TREASURE_BOOK_ABILITY[Treasure.BOOK_SAGE] is Ability.SAGE
    assert len(TREASURE_BOOK_ABILITY) == 15


def test_treasure_label_covers_ordinals_0_through_92_only():
    assert len(TREASURE_LABEL) == 93
    assert Treasure.ABILITY_TACTICAL in TREASURE_LABEL
    assert Treasure.NO_TREASURE in TREASURE_LABEL
    assert Treasure.NAMED_UNIQUE_CROWN_ROHAN not in TREASURE_LABEL
    assert Treasure.UNUSED_7 not in TREASURE_LABEL


def test_treasure_label_verbatim_samples():
    assert TREASURE_LABEL[Treasure.ABILITY_TACTICAL] == "+1 Tactical"
    assert TREASURE_LABEL[Treasure.WAND_RESURRECTION] == 'Cast "Resurrection" at skill-2'
    assert TREASURE_LABEL[Treasure.NO_TREASURE] == "no treasure"


def test_treasure_name_has_confirmed_gaps():
    # Confirmed real gaps in TREASURE.X2 itself, not extraction bugs -- see
    # models/treasure.py's own module docstring. MONSTER_AID_EAGLE (Phase
    # 196), MONSTER_AID_WHALE (Phase 197), and BOOK_TACTICAL (Phase 198)
    # were all filled from independent sources outside TREASURE.X2
    # (models/valhalla.py's own roster data, plus user-supplied
    # descriptions for the two Whale/Book items), so none of the three
    # is among the confirmed-missing ordinals anymore. Only the three
    # named uniques (94-96) remain genuinely unfilled.
    assert Treasure.NAMED_UNIQUE_AMULET_POWER not in TREASURE_NAME
    assert Treasure.NAMED_UNIQUE_SCEPTER_LIFE not in TREASURE_NAME
    assert Treasure.NAMED_UNIQUE_MAP_MARAUDERS not in TREASURE_NAME
    assert len(TREASURE_NAME) == 96


def test_treasure_name_verbatim_samples():
    assert TREASURE_NAME[Treasure.ABILITY_TACTICAL] == "Standard of Command"
    assert TREASURE_NAME[Treasure.WAND_RESURRECTION] == "Rod of Resurrection"
    assert TREASURE_NAME[Treasure.NAMED_UNIQUE_CROWN_ROHAN] == "Crown of Rohan"
    assert TREASURE_NAME[Treasure.MONSTER_AID_EAGLE] == "Feather of the Great Eagle"
    assert TREASURE_NAME[Treasure.MONSTER_AID_WHALE] == "Horn of Neptune"
    assert TREASURE_NAME[Treasure.BOOK_TACTICAL] == "Hannibal's Grimoire"


def test_named_uniques_have_no_pascal_obfuscation_and_no_treasab_label():
    # The six named uniques are the only ordinals whose Pascal identifiers
    # aren't obfuscated -- and TREASAB.X2 never covers them at all.
    for treasure in (
        Treasure.NAMED_UNIQUE_CROWN_ROHAN,
        Treasure.NAMED_UNIQUE_AMULET_POWER,
        Treasure.NAMED_UNIQUE_SCEPTER_LIFE,
        Treasure.NAMED_UNIQUE_MAP_MARAUDERS,
        Treasure.NAMED_UNIQUE_FANG_VAMPIRE,
        Treasure.NAMED_UNIQUE_HAMMER_POWER,
    ):
        assert treasure not in TREASURE_LABEL
