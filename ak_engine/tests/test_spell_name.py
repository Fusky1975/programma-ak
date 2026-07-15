from __future__ import annotations

from ak_engine.models.enums import SPELL_ABBREVIATION, SPELL_BY_ABBREVIATION, SPELL_NAME, Spell


def test_spell_name_covers_exactly_the_35_real_spell_ordinals():
    assert len(SPELL_NAME) == 35
    assert set(SPELL_NAME.keys()) == {s for s in Spell if s.value <= 34}


def test_spell_name_excludes_nospell_due_to_confirmed_table_misalignment():
    assert Spell.NOSPELL not in SPELL_NAME


def test_spell_name_verbatim_samples():
    assert SPELL_NAME[Spell.RESURRECTION] == "Resurrection"
    assert SPELL_NAME[Spell.MIRROR_IMAGE] == "Mirror-Image Phantasm"
    assert SPELL_NAME[Spell.ILLUS_ARMIES] == "Phantasmal Armies"


def test_spell_name_secret_spell_samples():
    # These 10 (ordinals 25-34) were previously only ever cited by their
    # Pascal identifier in this project -- spname gives their real display
    # names for the first time.
    assert SPELL_NAME[Spell.GATE_ANGEL] == "Gate Angel"
    assert SPELL_NAME[Spell.HEAL] == "Words of Healing"
    assert SPELL_NAME[Spell.ILLUS_HERO] == "Illusory Hero"


# -- SPELL_ABBREVIATION / SPELL_BY_ABBREVIATION (Phase 178, CTBOTH.PAS spab) --


def test_spell_abbreviation_covers_exactly_the_35_real_spell_ordinals():
    assert len(SPELL_ABBREVIATION) == 35
    assert set(SPELL_ABBREVIATION.keys()) == {s for s in Spell if s.value <= 34}


def test_spell_abbreviation_excludes_nospell_due_to_confirmed_table_misalignment():
    assert Spell.NOSPELL not in SPELL_ABBREVIATION


def test_spell_abbreviation_verbatim_samples_from_monster_encounter_plans():
    # Every one of these 11 tokens is exactly what Desktop/Piani speciali
    # d'incontro dei mostri.txt's own CA-XX notation uses.
    assert SPELL_ABBREVIATION[Spell.HAND_OF_DEATH] == "HA"
    assert SPELL_ABBREVIATION[Spell.TELEK_STORM] == "TE"
    assert SPELL_ABBREVIATION[Spell.PSYCHIC_BLAST] == "PS"
    assert SPELL_ABBREVIATION[Spell.HOLY_SYMBOL] == "HO"
    assert SPELL_ABBREVIATION[Spell.INVISIBILITY] == "IN"
    assert SPELL_ABBREVIATION[Spell.MIRROR_IMAGE] == "MI"
    assert SPELL_ABBREVIATION[Spell.ICE_SUSPEND] == "IC"
    assert SPELL_ABBREVIATION[Spell.FIREBALL] == "FI"
    assert SPELL_ABBREVIATION[Spell.SPIRITWRACK] == "SP"
    assert SPELL_ABBREVIATION[Spell.CHARM] == "CH"
    assert SPELL_ABBREVIATION[Spell.CONTROL_UNDEAD] == "CO"


def test_spell_by_abbreviation_is_the_exact_inverse():
    assert len(SPELL_BY_ABBREVIATION) == 35
    for spell, abbreviation in SPELL_ABBREVIATION.items():
        assert SPELL_BY_ABBREVIATION[abbreviation] is spell
