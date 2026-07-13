from __future__ import annotations

from ak_engine.models.army_naming import RACE_SHORT_TAG, make_army_name, ordinal_suffix
from ak_engine.models.army_type import ArmyType
from ak_engine.models.race import Race


def test_ordinal_suffix_matches_rulebook_examples():
    assert ordinal_suffix(231) == "231st"
    assert ordinal_suffix(34) == "34th"
    assert ordinal_suffix(145) == "145th"


def test_ordinal_suffix_1_2_3_4():
    assert ordinal_suffix(1) == "1st"
    assert ordinal_suffix(2) == "2nd"
    assert ordinal_suffix(3) == "3rd"
    assert ordinal_suffix(4) == "4th"


def test_ordinal_suffix_has_no_11_12_13_exception():
    # Real host-engine (non-Moderator) Make_Des quirk -- see module docstring.
    assert ordinal_suffix(11) == "11st"
    assert ordinal_suffix(12) == "12nd"
    assert ordinal_suffix(13) == "13rd"


def test_make_army_name_matches_rulebook_example_bowmen():
    assert make_army_name(231, ArmyType.BOWMEN, Race.HUMAN) == "231st Bowmen"


def test_make_army_name_matches_rulebook_example_legion():
    assert make_army_name(34, ArmyType.LEGION, Race.HUMAN) == "34th Legion"


def test_make_army_name_matches_rulebook_example_fleet():
    assert make_army_name(145, ArmyType.GARRISON, Race.HUMAN) == "145th Garrison"


def test_make_army_name_adds_short_race_tag_for_non_human():
    assert make_army_name(5, ArmyType.BOWMEN, Race.ELVEN) == "5th Elf Bowmen"
    assert make_army_name(6, ArmyType.AXEMEN, Race.DWARVEN) == "6th Dwf Axemen"
    assert make_army_name(7, ArmyType.PHALANX, Race.ORCISH) == "7th Orc Phalanx"


def test_make_army_name_omits_tag_for_races_with_no_short_tag():
    # Non-Human but RACE_SHORT_TAG is empty for these -- no tag inserted.
    assert make_army_name(8, ArmyType.BOWMEN, Race.DRAGONS) == "8th Bowmen"
    assert make_army_name(9, ArmyType.BOWMEN, Race.WHALES) == "9th Bowmen"


def test_make_army_name_omits_tag_for_rohan_confirmed_source_oddity():
    # RACE_SHORT_TAG[Race.ROHAN] is empty due to the confirmed rab3
    # off-by-one -- see module docstring.
    assert make_army_name(10, ArmyType.BOWMEN, Race.ROHAN) == "10th Bowmen"


def test_race_short_tag_positional_values():
    assert RACE_SHORT_TAG[Race.HUMAN] == ""
    assert RACE_SHORT_TAG[Race.ELVEN] == "Elf"
    assert RACE_SHORT_TAG[Race.DWARVEN] == "Dwf"
    assert RACE_SHORT_TAG[Race.ORCISH] == "Orc"
    assert RACE_SHORT_TAG[Race.ROHAN] == ""


def test_race_short_tag_covers_every_race():
    assert set(RACE_SHORT_TAG.keys()) == set(Race)
