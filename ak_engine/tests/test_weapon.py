from __future__ import annotations

from ak_engine.models.weapon import WEAPON_HIT_VERB, WEAPON_NAME, Weapon


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
