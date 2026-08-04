from __future__ import annotations

from ak_engine.models.race import (
    RACE_ADJECTIVE,
    RACE_FANATICISM_TITLE,
    RACE_NAME,
    RACE_PLURAL_NAME,
    Race,
)

# Phase 383: Race.DROW/LIZARDMAN/GOBLIN have no confirmed singular `rname`
# source, so RACE_NAME deliberately excludes them -- see module docstring.
_RACES_WITHOUT_CONFIRMED_SINGULAR_NAME = {Race.DROW, Race.LIZARDMAN, Race.GOBLIN}


def test_race_name_covers_every_enum_value_except_the_three_unconfirmed_ones():
    assert set(RACE_NAME.keys()) == set(Race) - _RACES_WITHOUT_CONFIRMED_SINGULAR_NAME


def test_race_name_excludes_drow_lizardman_goblin():
    for race in _RACES_WITHOUT_CONFIRMED_SINGULAR_NAME:
        assert race not in RACE_NAME


def test_race_adjective_covers_every_enum_value():
    assert set(RACE_ADJECTIVE.keys()) == set(Race)


def test_race_adjective_covers_the_three_new_races():
    assert RACE_ADJECTIVE[Race.DROW] == "Drow"
    assert RACE_ADJECTIVE[Race.LIZARDMAN] == "Lizardman"
    assert RACE_ADJECTIVE[Race.GOBLIN] == "Goblin"


def test_race_plural_name_covers_every_enum_value():
    assert set(RACE_PLURAL_NAME.keys()) == set(Race)


def test_race_plural_name_verbatim_samples():
    assert RACE_PLURAL_NAME[Race.HUMAN] == "Humans"
    assert RACE_PLURAL_NAME[Race.DROW] == "Drow Elves"
    assert RACE_PLURAL_NAME[Race.LIZARDMAN] == "Lizardmen"
    assert RACE_PLURAL_NAME[Race.GOBLIN] == "Goblins"


def test_race_plural_name_is_not_always_a_regular_pluralization_of_race_name():
    # WEREFOLK/ROHAN prove RACE_PLURAL_NAME is an independently sourced
    # table, not derivable from RACE_NAME by simple English pluralization.
    assert RACE_NAME[Race.WEREFOLK] == "Were"
    assert RACE_PLURAL_NAME[Race.WEREFOLK] == "Werefolk"
    assert RACE_NAME[Race.ROHAN] == "Rohan"
    assert RACE_PLURAL_NAME[Race.ROHAN] == "Riders"


def test_race_adjective_matches_prose_txt_examples_verbatim():
    # PROSE.TXT: "$R: Race name ('Elven', 'Dwarven' etc.)"
    assert RACE_ADJECTIVE[Race.ELVEN] == "Elven"
    assert RACE_ADJECTIVE[Race.DWARVEN] == "Dwarven"


def test_race_name_verbatim_samples():
    assert RACE_NAME[Race.HUMAN] == "Human"
    assert RACE_NAME[Race.DRAGONS] == "Dragon"
    assert RACE_NAME[Race.NO_RACE] == "no race"


def test_race_adjective_non_obvious_samples():
    # These diverge meaningfully from RACE_NAME's plain noun form.
    assert RACE_ADJECTIVE[Race.DRAGONS] == "serpentine"
    assert RACE_ADJECTIVE[Race.EAGLES] == "feather-brained"
    assert RACE_ADJECTIVE[Race.SAURIAN] == "Saurian"


# -- Phase 100: RACE.X2 --


def test_race_fanaticism_title_covers_the_first_13_ordinals():
    expected = {Race(v) for v in range(13)}
    assert set(RACE_FANATICISM_TITLE.keys()) == expected


def test_race_fanaticism_title_verbatim_samples():
    assert RACE_FANATICISM_TITLE[Race.DWARVEN].endswith("King Under the Mountain.")
    assert RACE_FANATICISM_TITLE[Race.MERMISH].endswith("Holy King of Atlantis.")
    assert RACE_FANATICISM_TITLE[Race.ENTISH].endswith("Tsar of the Trees.")


def test_race_fanaticism_title_no_race_and_saurian_are_blank():
    # No "king" Office exists for either -- a real fact, not a missing value.
    assert RACE_FANATICISM_TITLE[Race.NO_RACE] == ""
    assert RACE_FANATICISM_TITLE[Race.SAURIAN] == ""


def test_race_fanaticism_title_excludes_vampish_and_rohan():
    # Outside RACE.X2's own declared 13-choice range.
    assert Race.VAMPISH not in RACE_FANATICISM_TITLE
    assert Race.ROHAN not in RACE_FANATICISM_TITLE


# -- Phase 383: 3 more real races from the AKGEN tables.races catalog --


def test_race_enum_gains_drow_lizardman_goblin_at_ordinals_15_to_17():
    assert Race.DROW.value == 15
    assert Race.LIZARDMAN.value == 16
    assert Race.GOBLIN.value == 17


def test_race_fanaticism_title_excludes_the_three_new_races_too():
    # RACE.X2's own declared range is still only ordinals 0-12.
    assert Race.DROW not in RACE_FANATICISM_TITLE
    assert Race.LIZARDMAN not in RACE_FANATICISM_TITLE
    assert Race.GOBLIN not in RACE_FANATICISM_TITLE
