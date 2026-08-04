from __future__ import annotations

from ak_engine.models.army_type import (
    ARMY_TYPE_BY_ORDINAL,
    ARMY_TYPE_DESIGNATION,
    ARMY_TYPE_NAME,
    MONSTROUS_ARMY_RACE,
    ArmyType,
)
from ak_engine.models.race import Race

# Phase 383: ARTILLERY/D_TURTLE have no confirmed full `atname` -- see
# module docstring.
_ARMY_TYPES_WITHOUT_CONFIRMED_NAME = {ArmyType.ARTILLERY, ArmyType.D_TURTLE}


def test_army_type_name_covers_every_army_type_except_the_two_unconfirmed_ones():
    assert set(ARMY_TYPE_NAME.keys()) == set(ArmyType) - _ARMY_TYPES_WITHOUT_CONFIRMED_NAME


def test_army_type_name_excludes_artillery_and_d_turtle():
    for army_type in _ARMY_TYPES_WITHOUT_CONFIRMED_NAME:
        assert army_type not in ARMY_TYPE_NAME


def test_army_type_designation_covers_every_army_type():
    assert set(ARMY_TYPE_DESIGNATION.keys()) == set(ArmyType)


def test_army_type_name_matches_prose_txt_marker_verbatim():
    # PROSE.TXT: '|: Army type name ("Legion", "Fleet" etc.)'.
    assert ARMY_TYPE_NAME[ArmyType.LEGION] == "Legion"
    assert ARMY_TYPE_NAME[ArmyType.FLEET] == "Fleet"
    assert ARMY_TYPE_NAME[ArmyType.LT_CAVALRY] == "Light Cavalry"
    assert ARMY_TYPE_NAME[ArmyType.WEREBEASTS] == "Were-Beasts"


def test_army_type_designation_verbatim_samples():
    # REPORTS.PAS's compact "Skel <desig>" skeletal-army line uses this
    # 9-char-max form instead of ARMY_TYPE_NAME's full name.
    assert ARMY_TYPE_DESIGNATION[ArmyType.LT_CAVALRY] == "Lt Cav"
    assert ARMY_TYPE_DESIGNATION[ArmyType.HVY_CAVALRY] == "Hvy Cav"
    assert ARMY_TYPE_DESIGNATION[ArmyType.CAMEL_CORPS] == "Camels"
    assert ARMY_TYPE_DESIGNATION[ArmyType.WARG_RIDERS] == "Wargs"
    assert ARMY_TYPE_DESIGNATION[ArmyType.WEREBEASTS] == "Weres"


def test_army_type_designation_whales_diverges_from_name():
    # CTBOTH.PAS's own atdesig table gives 'League' (from `whaleleague`),
    # not 'Whales', for this one entry -- a real quirk of the source, not
    # a transcription mistake.
    assert ARMY_TYPE_NAME[ArmyType.WHALES] == "Whales"
    assert ARMY_TYPE_DESIGNATION[ArmyType.WHALES] == "League"


# -- Phase 383: 9 more real army ordinals, 20-28 --


def test_army_type_by_ordinal_covers_the_nine_new_ordinals():
    assert ARMY_TYPE_BY_ORDINAL[20] == ArmyType.DINOSAURS
    assert ARMY_TYPE_BY_ORDINAL[21] == ArmyType.VAMPIRES
    assert ARMY_TYPE_BY_ORDINAL[22] == ArmyType.MARAUDERS
    assert ARMY_TYPE_BY_ORDINAL[23] == ArmyType.SHAMANS
    assert ARMY_TYPE_BY_ORDINAL[24] == ArmyType.CROSSBOW
    assert ARMY_TYPE_BY_ORDINAL[25] == ArmyType.JAVELINS
    assert ARMY_TYPE_BY_ORDINAL[26] == ArmyType.ARTILLERY
    assert ARMY_TYPE_BY_ORDINAL[27] == ArmyType.SPIDERS
    assert ARMY_TYPE_BY_ORDINAL[28] == ArmyType.D_TURTLE


def test_army_type_designation_covers_all_nine_new_types():
    assert ARMY_TYPE_DESIGNATION[ArmyType.DINOSAURS] == "Dinosaurs"
    assert ARMY_TYPE_DESIGNATION[ArmyType.VAMPIRES] == "Vampires"
    assert ARMY_TYPE_DESIGNATION[ArmyType.MARAUDERS] == "Marauders"
    assert ARMY_TYPE_DESIGNATION[ArmyType.SHAMANS] == "Shamans"
    assert ARMY_TYPE_DESIGNATION[ArmyType.CROSSBOW] == "Crossbow"
    assert ARMY_TYPE_DESIGNATION[ArmyType.JAVELINS] == "Javelins"
    assert ARMY_TYPE_DESIGNATION[ArmyType.ARTILLERY] == "Artil'ry"
    assert ARMY_TYPE_DESIGNATION[ArmyType.SPIDERS] == "Spiders"
    assert ARMY_TYPE_DESIGNATION[ArmyType.D_TURTLE] == "D-Turtle"


def test_monstrous_army_race_gains_only_vampires_not_dinosaurs():
    # `special_races` explicitly names Vampires but not Dinosaurs -- see
    # module docstring. Unconfirmed name-symmetry alone doesn't qualify.
    assert MONSTROUS_ARMY_RACE[ArmyType.VAMPIRES] == Race.VAMPISH
    assert ArmyType.DINOSAURS not in MONSTROUS_ARMY_RACE


def test_the_nine_new_army_types_have_no_rulebook_mechanics():
    from ak_engine.models.army_type import ARMY_TABLE, BASE_STRENGTH, NEMESIS

    for army_type in (
        ArmyType.DINOSAURS,
        ArmyType.VAMPIRES,
        ArmyType.MARAUDERS,
        ArmyType.SHAMANS,
        ArmyType.CROSSBOW,
        ArmyType.JAVELINS,
        ArmyType.ARTILLERY,
        ArmyType.SPIDERS,
        ArmyType.D_TURTLE,
    ):
        assert army_type not in ARMY_TABLE
        assert army_type not in BASE_STRENGTH
        assert army_type not in NEMESIS
