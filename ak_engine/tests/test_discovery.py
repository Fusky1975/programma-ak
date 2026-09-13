from __future__ import annotations

from ak_engine.models.enums import Ability, Spell
from ak_engine.models.discovery import (
    DISCOVERY_ABILITY_BONUS,
    DISCOVERY_ANTISPELL_TARGET,
    DISCOVERY_DESCRIPTION,
    DISCOVERY_DISPLAY_VALUE,
    DISCOVERY_NAME,
    DISCOVERY_REVENUE_BONUS_PERCENT,
    DISCOVERY_SPREAD_CATEGORY,
    Discovery,
    describe_discovery_line,
    discovery_effect_description,
    sorted_kingdom_discoveries,
)


def test_discovery_has_64_declared_members():
    assert len(Discovery) == 64


def test_discovery_name_covers_every_discovery():
    assert set(DISCOVERY_NAME.keys()) == set(Discovery)


def test_discovery_name_verbatim_samples_from_each_group():
    # fix0..fix9 (ability bonus set 1)
    assert DISCOVERY_NAME[Discovery.LAND_SHIP] == "Land Ship"
    # wreck0..wreck9 (ability bonus set 2)
    assert DISCOVERY_NAME[Discovery.MEDITATION_INCENSE] == "Meditation Incense"
    # bild10..bild43 (anti-spell ward)
    assert DISCOVERY_NAME[Discovery.OSTEOPATHIC_GERM_WARFARE] == "Osteopathic Germ Warfare"
    # crunch0..crunch27 (revenue bonus)
    assert DISCOVERY_NAME[Discovery.VULCANIZED_RUBBER] == "Vulcanized Rubber"


def test_discovery_name_ordinal_boundaries_of_each_group():
    # REPORTS.PAS's own CASE statement groups the 64 members as
    # fix0..fix9 (0-9), wreck0..wreck9 (10-19), bild10..bild43 (20-35),
    # crunch0..crunch27 (36-63) -- confirming positional alignment holds
    # at every group boundary, not just the two endpoints.
    assert Discovery.LAND_SHIP.value == 0
    assert Discovery.MITHRIL_CHAINMAIL.value == 9
    assert Discovery.MEDITATION_INCENSE.value == 10
    assert Discovery.SCIENTIFIC_METHOD.value == 19
    assert Discovery.OSTEOPATHIC_GERM_WARFARE.value == 20
    assert Discovery.INFRARED_GOGGLES.value == 35
    assert Discovery.PEANUT_BUTTER_SANDWICH.value == 36
    assert Discovery.VULCANIZED_RUBBER.value == 63


# -- Phase 93: Discovery.txt (user-supplied design doc) --


def test_discovery_description_covers_every_discovery():
    assert set(DISCOVERY_DESCRIPTION.keys()) == set(Discovery)


def test_discovery_description_verbatim_samples():
    assert DISCOVERY_DESCRIPTION[Discovery.LAND_SHIP].startswith(
        "The Land Ship is a galley on wheels"
    )
    assert "raise your revenue by an average of 2%" in DISCOVERY_DESCRIPTION[Discovery.SPECTACLES]


def test_discovery_ability_bonus_covers_exactly_the_fix_and_wreck_groups():
    covered = set(DISCOVERY_ABILITY_BONUS.keys())
    expected = {Discovery(v) for v in range(0, 20)}
    assert covered == expected


def test_discovery_ability_bonus_matches_description_text_for_every_entry():
    # Doubly confirmed: DISCOVERY_ABILITY_BONUS is derived from CTBOTH.PAS's
    # own formula, but every DISCOVERY_DESCRIPTION paragraph in this group
    # names the same ability in plain English -- cross-check both agree.
    ability_words = {
        Ability.TACTICAL: "Tactical",
        Ability.MARCH: "March",
        Ability.NAVAL: "Naval",
        Ability.ARCHERY: "Archery",
        Ability.MELEE: "Melee",
        Ability.DRUID: "Druid",
        Ability.THIEF: "Thief",
        Ability.EXPLORER: "Explorer",
        Ability.SPY: "Spy",
        Ability.SAGE: "Sage",
    }
    for discovery, ability in DISCOVERY_ABILITY_BONUS.items():
        assert f"{ability_words[ability]} ability" in DISCOVERY_DESCRIPTION[discovery]


def test_discovery_antispell_target_covers_exactly_the_bild_group():
    covered = set(DISCOVERY_ANTISPELL_TARGET.keys())
    expected = {Discovery(v) for v in range(20, 36)}
    assert covered == expected


def test_discovery_antispell_target_verbatim_samples():
    assert DISCOVERY_ANTISPELL_TARGET[Discovery.OSTEOPATHIC_GERM_WARFARE] == Spell.SKELETAL_ARMY
    assert DISCOVERY_ANTISPELL_TARGET[Discovery.HIDDEN_TATTOOS] == Spell.KILL_ENEMY
    assert DISCOVERY_ANTISPELL_TARGET[Discovery.INFRARED_GOGGLES] == Spell.INVISIBILITY


def test_discovery_revenue_bonus_percent_covers_exactly_the_crunch_group():
    covered = set(DISCOVERY_REVENUE_BONUS_PERCENT.keys())
    expected = {Discovery(v) for v in range(36, 64)}
    assert covered == expected


def test_discovery_revenue_bonus_percent_cycles_1_2_3_4():
    values = [DISCOVERY_REVENUE_BONUS_PERCENT[Discovery(v)] for v in range(36, 64)]
    assert values == [1, 2, 3, 4] * 7


def test_discovery_revenue_bonus_percent_spectacles_discrepancy_is_documented():
    # CTBOTH.PAS's own formula gives 1% for SPECTACLES (crunch20), but
    # Discovery.txt's design-doc text says 2% -- this dict follows the
    # Pascal formula (the actual executable behavior), and the
    # discrepancy is called out explicitly rather than silently resolved.
    assert DISCOVERY_REVENUE_BONUS_PERCENT[Discovery.SPECTACLES] == 1
    assert "2%" in DISCOVERY_DESCRIPTION[Discovery.SPECTACLES]


def test_discovery_three_mechanics_dicts_partition_the_enum_without_overlap():
    ability_keys = set(DISCOVERY_ABILITY_BONUS)
    antispell_keys = set(DISCOVERY_ANTISPELL_TARGET)
    revenue_keys = set(DISCOVERY_REVENUE_BONUS_PERCENT)
    assert not (ability_keys & antispell_keys)
    assert not (ability_keys & revenue_keys)
    assert not (antispell_keys & revenue_keys)
    assert ability_keys | antispell_keys | revenue_keys == set(Discovery)


# -- Phase 268: DISCOVERY_DISPLAY_VALUE + report line composition ----------


def test_discovery_display_value_covers_every_discovery():
    assert set(DISCOVERY_DISPLAY_VALUE.keys()) == set(Discovery)


def test_discovery_display_value_verbatim_samples():
    # CTBOTH.PAS discval array, positional -- see module docstring.
    assert DISCOVERY_DISPLAY_VALUE[Discovery.LAND_SHIP] == 19
    assert DISCOVERY_DISPLAY_VALUE[Discovery.PONY_EXPRESS] == 20
    assert DISCOVERY_DISPLAY_VALUE[Discovery.PEANUT_BUTTER_SANDWICH] == 10
    assert DISCOVERY_DISPLAY_VALUE[Discovery.VULCANIZED_RUBBER] == 13


# -- Phase 795: DISCOVERY_SPREAD_CATEGORY (dspread) -- Desktop/DISCVAL.md --


def test_discovery_spread_category_covers_every_discovery_with_a_valid_value():
    assert set(DISCOVERY_SPREAD_CATEGORY.keys()) == set(Discovery)
    assert set(DISCOVERY_SPREAD_CATEGORY.values()) <= {1, 2, 3, 4}


def test_discovery_spread_category_verbatim_samples():
    # CTME.PAS dspread array, positional -- see module docstring.
    assert DISCOVERY_SPREAD_CATEGORY[Discovery.LAND_SHIP] == 1  # Batt
    assert DISCOVERY_SPREAD_CATEGORY[Discovery.PONY_EXPRESS] == 2  # Comm
    assert DISCOVERY_SPREAD_CATEGORY[Discovery.ANALYTICAL_PSYCHOLOGY] == 3  # Prof
    assert DISCOVERY_SPREAD_CATEGORY[Discovery.OSTEOPATHIC_GERM_WARFARE] == 4  # Form


def test_discovery_effect_description_ability_bonus():
    assert discovery_effect_description(Discovery.COMPASS) == "+1 skill in Exploring"


def test_discovery_effect_description_antispell():
    assert discovery_effect_description(Discovery.OSTEOPATHIC_GERM_WARFARE) == "Anti-spell: Skeletal Army"


def test_discovery_effect_description_revenue():
    assert discovery_effect_description(Discovery.PEANUT_BUTTER_SANDWICH) == "+1% revenue"


def test_describe_discovery_line_pads_name_to_25_characters():
    line = describe_discovery_line(Discovery.COMPASS)
    assert line == "  Compass" + " " * 18 + "(+1 skill in Exploring)"


def test_describe_discovery_line_handles_a_name_at_the_padding_boundary():
    # OSTEOPATHIC_GERM_WARFARE's name is 24 characters -- only 1 padding space.
    name = DISCOVERY_NAME[Discovery.OSTEOPATHIC_GERM_WARFARE]
    assert len(name) == 24
    line = describe_discovery_line(Discovery.OSTEOPATHIC_GERM_WARFARE)
    assert line == f"  {name} (Anti-spell: Skeletal Army)"


def test_sorted_kingdom_discoveries_orders_by_descending_display_value():
    discoveries = {Discovery.COMPASS, Discovery.PONY_EXPRESS, Discovery.PEANUT_BUTTER_SANDWICH}

    ordered = sorted_kingdom_discoveries(discoveries)

    assert ordered == [Discovery.PONY_EXPRESS, Discovery.PEANUT_BUTTER_SANDWICH, Discovery.COMPASS]


def test_sorted_kingdom_discoveries_breaks_ties_by_declaration_order():
    # LAND_SHIP and SCYTHED_CHARIOTS both have display value 19.
    ordered = sorted_kingdom_discoveries({Discovery.SCYTHED_CHARIOTS, Discovery.LAND_SHIP})

    assert ordered == [Discovery.LAND_SHIP, Discovery.SCYTHED_CHARIOTS]


def test_sorted_kingdom_discoveries_empty_set():
    assert sorted_kingdom_discoveries(set()) == []
