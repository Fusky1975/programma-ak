from __future__ import annotations

from ak_engine.models.race import RACE_ADJECTIVE, RACE_FANATICISM_TITLE, RACE_NAME, Race


def test_race_name_covers_every_enum_value():
    assert set(RACE_NAME.keys()) == set(Race)


def test_race_adjective_covers_every_enum_value():
    assert set(RACE_ADJECTIVE.keys()) == set(Race)


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
