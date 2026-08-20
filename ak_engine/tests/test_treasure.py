from __future__ import annotations

from ak_engine.models.enums import Ability, Spell
from ak_engine.models.treasure import (
    TREASURE_ABILITY_ITEM,
    TREASURE_BOOK_ABILITY,
    TREASURE_CATEGORY,
    TREASURE_DESCRIPTION,
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


def test_treasure_name_covers_all_99_real_ordinals():
    # Phase 580 correction: the six ordinals (50-52, 94-96) Phase 77
    # originally believed TREASURE.X2 genuinely skipped turned out to be
    # a Phase-77-era incomplete copy of the file, not a real gap -- a
    # byte-faithful independent reconstruction has all six. See models/
    # treasure.py's own module docstring for the full account. Only the
    # 14 unused extension slots (99-112) and NAMED_UNIQUE_CROWN_ROHAN's
    # own siblings beyond ordinal 98 are excluded, same as before.
    covered = {t for t in Treasure if t.value <= 98}
    assert set(TREASURE_NAME.keys()) == covered
    assert len(TREASURE_NAME) == 99


def test_treasure_name_verbatim_samples():
    assert TREASURE_NAME[Treasure.ABILITY_TACTICAL] == "Standard of Command"
    assert TREASURE_NAME[Treasure.WAND_RESURRECTION] == "Rod of Resurrection"
    assert TREASURE_NAME[Treasure.NAMED_UNIQUE_CROWN_ROHAN] == "Crown of Rohan"
    assert TREASURE_NAME[Treasure.MONSTER_AID_EAGLE] == "Feather of the Great Eagle"
    assert TREASURE_NAME[Treasure.MONSTER_AID_WHALE] == "Horn of Neptune"
    assert TREASURE_NAME[Treasure.BOOK_TACTICAL] == "Hannibal's Grimoire"
    assert TREASURE_NAME[Treasure.NAMED_UNIQUE_AMULET_POWER] == "Amulet of Power"
    assert TREASURE_NAME[Treasure.NAMED_UNIQUE_SCEPTER_LIFE] == "Scepter of Life"
    assert TREASURE_NAME[Treasure.NAMED_UNIQUE_MAP_MARAUDERS] == "Map of the Marauders"


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


# -- Phase 580: TREASURE.X2 full flavor text --


def test_treasure_description_covers_all_99_real_ordinals():
    covered = {t for t in Treasure if t.value <= 98}
    assert set(TREASURE_DESCRIPTION.keys()) == covered
    assert len(TREASURE_DESCRIPTION) == 99


def test_treasure_description_verbatim_samples():
    assert TREASURE_DESCRIPTION[Treasure.ABILITY_TACTICAL] == (
        "The Standard of Command raises your Tactical ability by one level while "
        "it is in your possession.  A skill level of 0 would rise to skill level 1."
    )
    assert TREASURE_DESCRIPTION[Treasure.NO_TREASURE] == "No treasure."


def test_treasure_description_confirms_the_previously_disputed_ordinals():
    # The three Phase-196/197/198 names (sourced from valhalla.py/the
    # user, not TREASURE.X2 at the time) and the three previously-
    # nameless named uniques are all present here now -- see module
    # docstring's own Phase 580 correction.
    assert "Feather of the Great Eagle" in TREASURE_DESCRIPTION[Treasure.MONSTER_AID_EAGLE]
    assert "Horn of Neptune" in TREASURE_DESCRIPTION[Treasure.MONSTER_AID_WHALE]
    assert "Hannibal's Grimoire" in TREASURE_DESCRIPTION[Treasure.BOOK_TACTICAL]
    assert "Amulet of Power" in TREASURE_DESCRIPTION[Treasure.NAMED_UNIQUE_AMULET_POWER]
    assert "Scepter of Life" in TREASURE_DESCRIPTION[Treasure.NAMED_UNIQUE_SCEPTER_LIFE]
    assert "Map of the Marauders" in TREASURE_DESCRIPTION[Treasure.NAMED_UNIQUE_MAP_MARAUDERS]


def test_treasure_description_preserves_the_sources_own_typos():
    # Confirmed real in the byte-faithful source, matching TREASURE_NAME's
    # own already-established "keep verbatim" convention.
    assert "Seamansip" in TREASURE_DESCRIPTION[Treasure.ABILITY_NAVAL]
    assert "GOds Quest" in TREASURE_DESCRIPTION[Treasure.QUEST_GODS_QUEST]


def test_treasure_description_quest_and_hoard_items_say_not_a_magic_item():
    # Real, specific per-ordinal text, not generic filler -- confirmed by
    # its own alignment with TREASURE_NAME's already-established names
    # for every one of these ordinals (gold hoards and quest items).
    assert TREASURE_DESCRIPTION[Treasure.GOLD_HOARD_LARGE] == "the Hoard is not a magic item."
    assert TREASURE_DESCRIPTION[Treasure.QUEST_SNOWBALL] == "The Snowball is not a magic item."
