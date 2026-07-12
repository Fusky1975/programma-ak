from __future__ import annotations

from ak_engine.models.monster import Monster
from ak_engine.models.weapon import (
    MONSTER_MELEE_WEAPON,
    MONSTER_RANGED_WEAPON,
    WEAPON_HIT_VERB,
    WEAPON_NAME,
    Weapon,
)


def test_weapon_enum_has_29_declared_values():
    assert len(Weapon) == 29
    assert Weapon.TALONS.value == 0
    assert Weapon.NO_WEAP.value == 28


def test_weapon_name_covers_every_enum_value():
    assert set(WEAPON_NAME.keys()) == set(Weapon)


def test_weapon_hit_verb_covers_every_enum_value():
    assert set(WEAPON_HIT_VERB.keys()) == set(Weapon)


def test_weapon_confirmed_real_usage_bow_and_sword():
    # RUMORS.PAS literally references these two by name for the "$S"
    # attack-method marker (a character attacker's Fire Arrow vs. Melee).
    assert WEAPON_NAME[Weapon.BOW] == "arrow"
    assert WEAPON_HIT_VERB[Weapon.BOW] == "fired/Rshot"
    assert WEAPON_NAME[Weapon.SWORD] == "sword"
    assert WEAPON_HIT_VERB[Weapon.SWORD] == "swang/Rthrust at"


def test_weapon_name_no_weap_sentinel():
    assert WEAPON_NAME[Weapon.NO_WEAP] == "no weapon"
    assert WEAPON_HIT_VERB[Weapon.NO_WEAP] == "swang at"


def test_weapon_hit_verb_contains_live_choice_markers():
    # Confirmed prose templates, not plain text -- see module docstring.
    assert "/R" in WEAPON_HIT_VERB[Weapon.TALONS]


# -- Phase 94: CTME.PAS mtrweap/mtweap1 (closes weapon.py's own
# previously-documented "confirmed structural gap") --


def test_monster_ranged_weapon_covers_every_monster():
    assert set(MONSTER_RANGED_WEAPON.keys()) == set(Monster)


def test_monster_melee_weapon_covers_every_monster():
    assert set(MONSTER_MELEE_WEAPON.keys()) == set(Monster)


def test_monster_ranged_weapon_verbatim_samples():
    assert MONSTER_RANGED_WEAPON[Monster.R_DRAGON] == Weapon.FLAME_BREATH
    assert MONSTER_RANGED_WEAPON[Monster.GIANT] == Weapon.BOULDER
    assert MONSTER_RANGED_WEAPON[Monster.ARCHER] == Weapon.BOW
    assert MONSTER_RANGED_WEAPON[Monster.BASILISK] == Weapon.GAZE
    assert MONSTER_RANGED_WEAPON[Monster.BANSHEE] == Weapon.B_SCREAM


def test_monster_ranged_weapon_no_weap_is_the_common_case():
    # Most monsters have no ranged attack -- confirm this isn't an
    # accidental all-NO_WEAP dict by also checking a real minority exists.
    assert MONSTER_RANGED_WEAPON[Monster.ROC] == Weapon.NO_WEAP
    non_ranged = [m for m, w in MONSTER_RANGED_WEAPON.items() if w != Weapon.NO_WEAP]
    assert len(non_ranged) == 12


def test_monster_melee_weapon_verbatim_samples():
    assert MONSTER_MELEE_WEAPON[Monster.TITAN] == Weapon.SWORD
    assert MONSTER_MELEE_WEAPON[Monster.GIANT] == Weapon.CLUB
    assert MONSTER_MELEE_WEAPON[Monster.CHIMERA] == Weapon.CHIM_HEADS
    assert MONSTER_MELEE_WEAPON[Monster.MINOTAUR] == Weapon.AXE
    assert MONSTER_MELEE_WEAPON[Monster.GI_OCTOPUS] == Weapon.TENTACLES


def test_monster_melee_weapon_nomonster_sentinel_has_no_weapon():
    assert MONSTER_MELEE_WEAPON[Monster.NOMONSTER] == Weapon.NO_WEAP
    assert MONSTER_RANGED_WEAPON[Monster.NOMONSTER] == Weapon.NO_WEAP
