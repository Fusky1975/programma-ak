from __future__ import annotations

from ak_engine.models.enums import (
    CAST_SPELL_OPENING_COMPLETE_SPELLS,
    CAST_SPELL_OPENING_COMPLETE_TEMPLATE,
    CAST_SPELL_OPENING_CONTINUED_TEMPLATE,
    SPELL_CAST_ANNOUNCEMENT,
    Spell,
)


def test_spell_cast_announcement_covers_exactly_the_25_base_spell_ordinals():
    assert len(SPELL_CAST_ANNOUNCEMENT) == 25
    assert set(SPELL_CAST_ANNOUNCEMENT.keys()) == {s for s in Spell if s.value <= 24}


def test_spell_cast_announcement_excludes_secret_spells_and_nospell():
    for secret in (
        Spell.GATE_ANGEL,
        Spell.HEAL,
        Spell.SCAR_TERRAIN,
        Spell.GATE_DEMON,
        Spell.MYSTIC_WINDS,
        Spell.LAVA_POOL,
        Spell.LOCATE_OBJECT,
        Spell.AUGUR_COMBAT,
        Spell.ILLUS_FOG,
        Spell.ILLUS_HERO,
    ):
        assert secret not in SPELL_CAST_ANNOUNCEMENT
    assert Spell.NOSPELL not in SPELL_CAST_ANNOUNCEMENT


def test_spell_cast_announcement_verbatim_samples():
    assert (
        SPELL_CAST_ANNOUNCEMENT[Spell.RESURRECTION]
        == "[1 was resurrected by the spell cast by <2."
    )
    assert SPELL_CAST_ANNOUNCEMENT[Spell.SKELETAL_ARMY] == "^L= arose from the graves of the dead!"
    assert (
        SPELL_CAST_ANNOUNCEMENT[Spell.MIRROR_IMAGE]
        == " and an/Ra_second image/Rillusion of [ sprang/Rflashed into existence/Rbeing!"
    )


def test_spell_cast_announcement_ice_suspend_matches_confirmed_source():
    assert (
        SPELL_CAST_ANNOUNCEMENT[Spell.ICE_SUSPEND]
        == ", and a shell/Rcrust of {frigid }ice formed/Rthickened around [."
    )


def test_spell_cast_announcement_control_undead_is_verbatim_truncated():
    # SPNOTE.X2's own source ends mid-word with no continuation anywhere in
    # the file -- transcribed exactly as found, not silently completed.
    assert SPELL_CAST_ANNOUNCEMENT[Spell.CONTROL_UNDEAD].endswith("mercilessly and_")


def test_cast_spell_opening_templates():
    assert CAST_SPELL_OPENING_COMPLETE_TEMPLATE == "< cast a ~ spell."
    assert CAST_SPELL_OPENING_CONTINUED_TEMPLATE == "< cast a ~ spell and "


def test_cast_spell_opening_complete_spells_are_exactly_tornado_bless_plague():
    assert CAST_SPELL_OPENING_COMPLETE_SPELLS == {Spell.TORNADO, Spell.BLESS, Spell.PLAGUE}
    for spell in Spell:
        if spell.value > 24:
            continue
        expected = (
            CAST_SPELL_OPENING_COMPLETE_TEMPLATE
            if spell in CAST_SPELL_OPENING_COMPLETE_SPELLS
            else CAST_SPELL_OPENING_CONTINUED_TEMPLATE
        )
        assert expected in (
            CAST_SPELL_OPENING_COMPLETE_TEMPLATE,
            CAST_SPELL_OPENING_CONTINUED_TEMPLATE,
        )
