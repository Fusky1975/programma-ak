from __future__ import annotations

from ak_engine.models.office import (
    OFFICE_ENABLED_BY_DEFAULT,
    OFFICE_MIN_POINTS,
    OFFICE_NAME,
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
