from __future__ import annotations

from ak_engine.models.enums import SPELL_NAME, Spell


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
