from __future__ import annotations

from ak_engine.models.army_type import ARMY_TYPE_DESIGNATION, ARMY_TYPE_NAME, ArmyType


def test_army_type_name_covers_every_army_type():
    assert set(ARMY_TYPE_NAME.keys()) == set(ArmyType)


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
