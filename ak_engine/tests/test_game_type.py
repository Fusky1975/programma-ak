from __future__ import annotations

from ak_engine.models.game_type import EARTH_EMPIRE_DESCRIPTION, EUROPE_KINGDOM_DESCRIPTION, GameType


# -- Phase 586: EARTH.X2/EUROPE.X2 --


def test_earth_empire_description_covers_all_31_declared_choices():
    assert len(EARTH_EMPIRE_DESCRIPTION) == 31
    assert set(EARTH_EMPIRE_DESCRIPTION.keys()) == set(range(1, 32))


def test_europe_kingdom_description_covers_all_12_declared_choices():
    assert len(EUROPE_KINGDOM_DESCRIPTION) == 12
    assert set(EUROPE_KINGDOM_DESCRIPTION.keys()) == set(range(1, 13))


def test_earth_empire_description_verbatim_sample():
    assert EARTH_EMPIRE_DESCRIPTION[1] == (
        "Your empire in the Earth Variant game is the Roman Empire, which arose "
        "in about the fourth century BC, and was dismembered around 400-475 by "
        "invading barbarians, although the eastern half lasted until 1454 AD, "
        "and some remnants lasted until 1805 AD, when the Holy Roman Empire was "
        "officially dissolved.The Romans had a fine tactical system, held "
        "gladiatorial events with well-trained fighters, and had a fine system "
        "of roads throughout the empire."
    )


def test_earth_empire_description_choice_23_is_new_atlantis_not_a_duplicate():
    assert "New Atlantis" in EARTH_EMPIRE_DESCRIPTION[23]
    assert "Francis Bacon" in EARTH_EMPIRE_DESCRIPTION[23]


def test_earth_empire_description_reserve_slots_are_atlantis_duplicates():
    # AKMAN.TXT's own confirmed 22-28 King range for a real Earth Variant
    # setup means only ordinals 0-27 (choices 1-28) are ever reachable;
    # choices 29-31 are a real but unreachable reserve, each a literal
    # duplicate of choice 22's own "Lost Empire of Atlantis" text.
    for choice in (24, 25, 26, 27, 28, 29, 30, 31):
        assert EARTH_EMPIRE_DESCRIPTION[choice] == EARTH_EMPIRE_DESCRIPTION[22]
        assert "Lost Empire of Atlantis" in EARTH_EMPIRE_DESCRIPTION[choice]


def test_europe_kingdom_description_verbatim_sample():
    assert EUROPE_KINGDOM_DESCRIPTION[1] == (
        "Your kingdom in the European game is the Caliphate of Cordoba, in "
        "southern Spain.In the 11th century, it was a great center of learning "
        "with the largest city in the world (Cordoba).This gives you a bonus "
        "of plus 2 Sage to all your characters."
    )


def test_game_type_earth_and_europe_members_exist():
    # Confirmed real, Phase 342 -- these two dicts are their own real
    # flavor text, closing a previously-unfilled gap.
    assert GameType.EARTH.value == 3
    assert GameType.EUROPE.value == 2
