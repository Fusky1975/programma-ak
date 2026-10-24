from __future__ import annotations

import random

from ak_engine.models.enums import (
    CAST_SPELL_OPENING_COMPLETE_SPELLS,
    CAST_SPELL_OPENING_COMPLETE_TEMPLATE,
    CAST_SPELL_OPENING_CONTINUED_TEMPLATE,
    SPELL_CAST_ANNOUNCEMENT,
    SPELL_NAME,
    Spell,
)
from ak_engine.report.turn_report import render_cast_announcement

# render_cast_announcement()'s own _CAST_ANNOUNCEMENT_TARGET_SPELLS/
# _CAST_ANNOUNCEMENT_PROVINCE_SPELLS/_CAST_ANNOUNCEMENT_ARMY_LIST_SPELLS/
# _CAST_ANNOUNCEMENT_FEATURE_SPELLS/Spell.ILLUS_TERRAIN's own required
# kwargs, so every eligible spell below can actually be rendered.
_TARGET_SPELLS = {Spell.KILL_ENEMY, Spell.RESURRECTION, Spell.ILLUS_ARMIES, Spell.ORATORY, Spell.CHARM, Spell.CLAIRVOYANCE}
_PROVINCE_SPELLS = {
    Spell.PART_SEA, Spell.BLESS, Spell.EARTHQUAKE, Spell.FLOOD, Spell.TORNADO, Spell.PLAGUE,
    Spell.ILLUS_TERRAIN, Spell.HIDE_FEATURE,
}
_ARMY_LIST_SPELLS = {Spell.FLOOD, Spell.TORNADO, Spell.PLAGUE, Spell.SKELETAL_ARMY}
# Resurrection/Oratory/Clairvoyance get no shared opening clause at all
# (render_cast_announcement()'s own _CAST_ANNOUNCEMENT_NO_OPENING_SPELLS) --
# already covered by their own dedicated tests in test_turn_report.py
# (test_render_cast_announcement_resurrection_reuses_caster_and_target_
# markers/oratory_has_no_double_cast_clause/clairvoyance_has_no_double_
# cast_clause), so this file's own loop below skips them rather than
# re-deriving that separate exception here too.
_NO_OPENING_SPELLS = {Spell.RESURRECTION, Spell.ORATORY, Spell.CLAIRVOYANCE}


def _render_kwargs_for(spell: Spell) -> dict:
    kwargs: dict = {}
    if spell in _TARGET_SPELLS:
        kwargs["target_name"] = "Borin"
    if spell in _PROVINCE_SPELLS:
        kwargs["province_name"] = "Province"
    if spell is Spell.ILLUS_TERRAIN:
        kwargs["terrain_name"] = "Plains"
    if spell in _ARMY_LIST_SPELLS:
        kwargs["army_names"] = ["1st Legion"]
    if spell is Spell.HIDE_FEATURE:
        kwargs["feature_name"] = "a Cave"
    return kwargs


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
    # Bug fix: the loop below used to compute `expected` as whichever of
    # the two template constants the real dispatch condition names, then
    # assert `expected in (both constants)` -- true no matter what the
    # dispatch condition actually is, or what either template contains.
    # It never called render_cast_announcement() (the real production
    # dispatch, turn_report.py) at all, so a regression that inverted or
    # dropped the `spell in CAST_SPELL_OPENING_COMPLETE_SPELLS` check
    # would have slipped through undetected. Now calls the real function
    # for every eligible spell and checks its actual rendered prefix.
    assert CAST_SPELL_OPENING_COMPLETE_SPELLS == {Spell.TORNADO, Spell.BLESS, Spell.PLAGUE}
    for spell in Spell:
        if spell.value > 24 or spell not in SPELL_CAST_ANNOUNCEMENT or spell in _NO_OPENING_SPELLS:
            continue
        result = render_cast_announcement(spell, "Aldric", random.Random(0), **_render_kwargs_for(spell))
        opening_prefix = f"Aldric cast a {SPELL_NAME[spell]} spell"
        if spell in CAST_SPELL_OPENING_COMPLETE_SPELLS:
            assert result.startswith(opening_prefix + "."), (spell, result)
        else:
            assert result.startswith(opening_prefix + " and "), (spell, result)
