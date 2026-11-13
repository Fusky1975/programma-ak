from __future__ import annotations

from ak_engine.models.army_type import (
    ARMY_TYPE_BY_ORDINAL,
    ARMY_TYPE_DESIGNATION,
    ARMY_TYPE_NAME,
    MONSTROUS_ARMY_RACE,
    SEA_ARMY_TYPES,
    ArmyType,
    is_land_army,
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


# -- Phase 521: land/sea classification (AdvancedAbility.MARCH_CAVALRY/_INFANTRY) --


def test_is_land_army_excludes_the_three_sea_going_types():
    for army_type in (ArmyType.FLEET, ArmyType.WHALES, ArmyType.MERMEN):
        assert army_type in SEA_ARMY_TYPES
        assert is_land_army(army_type) is False


def test_is_land_army_includes_ordinary_infantry_and_cavalry():
    assert is_land_army(ArmyType.BOWMEN) is True
    assert is_land_army(ArmyType.HVY_CAVALRY) is True


def test_is_land_army_excludes_air_wings_too():
    # Phase 523 correction: AKGEN_reverse_engineering_report (3).md SS97/
    # SS99 confirms the compiled MovementBonus dispatcher gives Dragon
    # Wing/Eagle Wing a flat 0 from March or Naval -- superseding Phase
    # 521's "no source narrows the wording" assumption.
    assert is_land_army(ArmyType.DRAGON_WING) is False
    assert is_land_army(ArmyType.EAGLE_WING) is False


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


def test_monstrous_army_race_gains_vampires_and_dinosaurs():
    # `special_races` explicitly names Vampires -- see module docstring.
    assert MONSTROUS_ARMY_RACE[ArmyType.VAMPIRES] == Race.VAMPISH
    # Phase 980: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real
    # description -- "Race: Saurian" -- a real display/combat race,
    # distinct from the separate Elven *recruiting* gate
    # (`turn/recruit.py _ELVEN_ONLY_ARMY_TYPES`).
    assert MONSTROUS_ARMY_RACE[ArmyType.DINOSAURS] == Race.SAURIAN


def test_the_eight_remaining_new_army_types_have_no_rulebook_mechanics():
    from ak_engine.models.army_type import ARMY_TABLE, BASE_STRENGTH, NEMESIS

    for army_type in (
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


def test_dinosaurs_have_phase_691_rulebook_mechanics_but_no_base_strength():
    # Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real
    # description resolves ARMY_TABLE/NEMESIS, but Strength stays
    # variable (5-10, rolled per-battle), same as Elephants.
    from ak_engine.models.army_type import ARMY_TABLE, BASE_STRENGTH, NEMESIS, ArmyTypeStats
    from ak_engine.models.map import Terrain

    assert ArmyType.DINOSAURS in ARMY_TABLE
    assert ARMY_TABLE[ArmyType.DINOSAURS] == ArmyTypeStats(3, 3, (), (Terrain.SEA,))
    assert NEMESIS[ArmyType.DINOSAURS] == frozenset({ArmyType.PHALANX})
    assert ArmyType.DINOSAURS not in BASE_STRENGTH
    assert MONSTROUS_ARMY_RACE[ArmyType.DINOSAURS] == Race.SAURIAN


def test_beasts_matches_the_rulebooks_own_direct_definition():
    # Phase 928: Regolamento AK.txt line 3062, right after the Army Type
    # Table's own Nemesis column -- "Per Beasts si intendono Cammelli,
    # Elefanti, Bestie Mannare, Warg, Aquile e Draghi." (user-supplied
    # verbatim quote) -- six real table members, plus Dinosaurs via the
    # separate, already-sourced AdvancedAbility.DRUIDIC_DINOSAURS
    # confirmation (Phase 691). Replaces the old {Elephants, Camel Corps,
    # Dinosaurs} name-symmetry guess Phase 913 could only confirm as a
    # dead end, not resolve.
    from ak_engine.models.army_type import BEASTS

    assert BEASTS == frozenset(
        {
            ArmyType.CAMEL_CORPS,
            ArmyType.ELEPHANTS,
            ArmyType.WEREBEASTS,
            ArmyType.WARG_RIDERS,
            ArmyType.EAGLE_WING,
            ArmyType.DRAGON_WING,
            ArmyType.DINOSAURS,
        }
    )


def test_beasts_are_the_nemesis_of_every_cavalry_and_chariot_type():
    # Phase 928: "I cavalli ne hanno una gran paura" ("Horses are greatly
    # afraid of them") -- Lt/Hvy Cavalry and Chariots (the table's own
    # three Nemesis: Beasts entries, Regolomento AK.txt lines 2977-2982)
    # are all weak against the full corrected 7-member set, not just the
    # 2 previously modeled.
    from ak_engine.models.army_type import BEASTS, NEMESIS

    for cavalry_type in (ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY):
        assert BEASTS <= NEMESIS[cavalry_type]
        assert ArmyType.CHARIOTS in NEMESIS[cavalry_type]
    assert NEMESIS[ArmyType.CHARIOTS] == BEASTS
