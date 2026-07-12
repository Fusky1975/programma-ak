from __future__ import annotations

from ak_engine.models.race import RACE_ADJECTIVE, RACE_NAME, Race


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
