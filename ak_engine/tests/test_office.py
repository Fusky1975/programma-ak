from __future__ import annotations

from ak_engine.models.office import (
    GANG_TEMPLATE,
    OFFICE_ENABLED_BY_DEFAULT,
    OFFICE_MIN_POINTS,
    OFFICE_NAME,
    OFFICE_PERK_DESCRIPTION,
    OFFICE_TITLE_DESCRIPTION,
    OFFICE_TITLE_KNOWLEDGE,
    OFFICE_VALUE,
    Office,
)


def test_office_enum_has_52_declared_values():
    assert len(Office) == 52
    assert Office.EMPEROR.value == 0
    assert Office.NO_TITLE.value == 51


def test_office_name_covers_every_enum_value():
    assert set(OFFICE_NAME.keys()) == set(Office)


def test_office_name_matches_prose_txt_examples_verbatim():
    # PROSE.TXT: "$O: Office name ('World Emperor', 'Arch-Mage Palatine', etc.)"
    assert OFFICE_NAME[Office.EMPEROR] == "World Emperor"
    assert OFFICE_NAME[Office.MAGE] == "Arch-Mage Palatine"


def test_office_name_other_verbatim_samples():
    assert OFFICE_NAME[Office.NO_OFFICE] == "no office"
    assert OFFICE_NAME[Office.NO_TITLE] == "no title"
    assert OFFICE_NAME[Office.DRAGON_LORD] == "Dragon Lord"
    assert OFFICE_NAME[Office.BRAVEST] == "Bravest of the Brave"


def test_office_min_points_covers_every_enum_value():
    assert set(OFFICE_MIN_POINTS.keys()) == set(Office)


def test_office_min_points_verbatim_samples():
    assert OFFICE_MIN_POINTS[Office.EMPEROR] == 1
    assert OFFICE_MIN_POINTS[Office.NO_OFFICE] == 0
    assert OFFICE_MIN_POINTS[Office.DIPLOMAT] == 50
    assert OFFICE_MIN_POINTS[Office.HUMAN_KING] == 15


def test_office_value_covers_every_enum_value():
    assert set(OFFICE_VALUE.keys()) == set(Office)


def test_office_value_verbatim_samples():
    assert OFFICE_VALUE[Office.EMPEROR] == 20
    assert OFFICE_VALUE[Office.NO_TITLE] == 0


def test_office_enabled_by_default_covers_every_enum_value():
    assert set(OFFICE_ENABLED_BY_DEFAULT.keys()) == set(Office)


def test_office_enabled_by_default_verbatim_samples():
    assert OFFICE_ENABLED_BY_DEFAULT[Office.EMPEROR] is True
    assert OFFICE_ENABLED_BY_DEFAULT[Office.NO_OFFICE] is False
    assert OFFICE_ENABLED_BY_DEFAULT[Office.ILLUS_MAGE] is False


# -- Phase 102: GANG.X2 --


def test_gang_template_covers_exactly_the_9_confirmed_offices():
    assert set(GANG_TEMPLATE.keys()) == {
        Office.DIVINE_KING,
        Office.GOOD_KING,
        Office.DRUID_KING,
        Office.NEUTRAL_KING,
        Office.PAGAN_KING,
        Office.EVIL_KING,
        Office.NECRO_MAGE,
        Office.UNDEAD_KING,
        Office.DUELLIST,
    }


def test_gang_template_verbatim_samples():
    assert "Thunderbird" in GANG_TEMPLATE[Office.DIVINE_KING]
    assert "League of Pagan Clerics" in GANG_TEMPLATE[Office.PAGAN_KING]
    assert GANG_TEMPLATE[Office.DUELLIST].endswith(
        "with their feats_of_derring-do/Runbelievable_panache."
    )


def test_gang_template_necro_mage_is_blank():
    # Not an alignment "king" title -- a real gap in the source, sitting
    # right between EVIL_KING and UNDEAD_KING's own confirmed content.
    assert GANG_TEMPLATE[Office.NECRO_MAGE] == ""


def test_gang_template_excludes_the_unconfirmed_middle_stretch():
    # PLAINS_KING..ASSASSIN sits between UNDEAD_KING and DUELLIST in the
    # source file too, but isn't asserted here as confirmed blank data.
    assert Office.PLAINS_KING not in GANG_TEMPLATE
    assert Office.ASSASSIN not in GANG_TEMPLATE


# -- Phase 103: IONAME.X2 --


def test_office_perk_description_covers_every_office_gaplessly():
    assert set(OFFICE_PERK_DESCRIPTION.keys()) == set(Office)


def test_office_perk_description_no_office_and_no_title_are_blank():
    assert OFFICE_PERK_DESCRIPTION[Office.NO_OFFICE] == ""
    assert OFFICE_PERK_DESCRIPTION[Office.NO_TITLE] == ""


def test_office_perk_description_verbatim_samples():
    assert OFFICE_PERK_DESCRIPTION[Office.EMPEROR] == "Know Tax Bases"
    assert OFFICE_PERK_DESCRIPTION[Office.MARSHAL] == "Recruit Extra Land Unit"
    assert OFFICE_PERK_DESCRIPTION[Office.HUMAN_KING] == "20% Human Fanaticism"
    assert OFFICE_PERK_DESCRIPTION[Office.PLAINS_KING] == "Double Plains Exploration Rate"


def test_office_perk_description_necro_mage_has_real_content():
    # The one blank gap in GANG_TEMPLATE's own confirmed range -- no
    # contradiction, NECRO_MAGE is a real Office with its own real perk
    # here, GANG.X2 is just a separate, sparser file.
    assert OFFICE_PERK_DESCRIPTION[Office.NECRO_MAGE] == "Imp Familiar, 25% Magic Resistance"


def test_office_perk_description_titles_cross_confirm_gang_template():
    # GANG_TEMPLATE's own DUELLIST entry mentions "Imperial Musketeers" --
    # IONAME.X2's own DUELLIST title is "CAPTAIN OF THE IMPERIAL
    # MUSKETEERS", independently confirming the same Office mapping.
    assert "Imperial Musketeers" in GANG_TEMPLATE[Office.DUELLIST]
    assert OFFICE_PERK_DESCRIPTION[Office.DUELLIST] == "1 Fanatical Unit"


# -- Phase 578: TITLE.X2 / TITKNOW.X2 --


def test_office_title_description_covers_every_office_gaplessly():
    assert set(OFFICE_TITLE_DESCRIPTION.keys()) == set(Office)


def test_office_title_knowledge_covers_every_office_gaplessly():
    assert set(OFFICE_TITLE_KNOWLEDGE.keys()) == set(Office)


def test_office_title_description_no_office_and_no_title():
    assert OFFICE_TITLE_DESCRIPTION[Office.NO_OFFICE] == "(No Office)"
    assert OFFICE_TITLE_DESCRIPTION[Office.NO_TITLE] == ""


def test_office_title_knowledge_no_office_and_no_title():
    assert OFFICE_TITLE_KNOWLEDGE[Office.NO_OFFICE] == "(No Office)"
    assert OFFICE_TITLE_KNOWLEDGE[Office.NO_TITLE] == ""


def test_office_title_description_verbatim_sample():
    assert OFFICE_TITLE_DESCRIPTION[Office.EMPEROR] == (
        'An ethereal Emerald Crown appeared on <\'s head, and a booming voice heard only by <2 ordained '
        '"This is the Crown of the Emperors of the Ancient Dynasty which ruled this world thousands of '
        "years ago.It is yours for as long as you are the best hope to become the next World Emperor, "
        "and can be given to no other.The Crown will give you the ability to know the strength of all "
        'your rivals in your quest for Empire".(This information will be shown in your Diplomacy report '
        "in future gameturns).Only the tax bases of kings bordering your kingdom that you have known for "
        "at least one full turn will be shown."
    )


def test_office_title_knowledge_verbatim_sample():
    assert OFFICE_TITLE_KNOWLEDGE[Office.HUMAN_KING] == (
        'The title of "Savior of Humankind" is reserved for the character who has best protected the '
        "Human race and led them to martial glory."
    )


def test_office_title_description_preserves_the_sources_own_missing_spaces():
    # Confirmed real in the byte-faithful source, not a transcription
    # accident -- see this dict's own module docstring addendum.
    assert "ago.It" in OFFICE_TITLE_DESCRIPTION[Office.EMPEROR]
    assert "gameturns).Only" in OFFICE_TITLE_DESCRIPTION[Office.EMPEROR]


def test_office_title_description_and_knowledge_titles_cross_confirm_gang_template():
    # Same DUELLIST cross-check as OFFICE_PERK_DESCRIPTION's own test
    # above, now against the two new catalogs.
    assert "Imperial Musketeers" in OFFICE_TITLE_DESCRIPTION[Office.DUELLIST]
    assert OFFICE_TITLE_KNOWLEDGE[Office.DUELLIST] == (
        'The title of "Captain of the Imperial Musketeers" is awarded to the best duellist in the world.'
    )
