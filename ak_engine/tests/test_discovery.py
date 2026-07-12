from __future__ import annotations

from ak_engine.models.discovery import DISCOVERY_NAME, Discovery


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
