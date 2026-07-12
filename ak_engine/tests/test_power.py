from __future__ import annotations

from ak_engine.models.enums import Spell
from ak_engine.models.power import (
    CAST_SPELL_FEATURE_DESCRIPTION,
    MCOND_TEMPLATE,
    PCOND_TEMPLATE,
    POWER_CONDITION_NAME,
    POWER_CONDITION_REJECTION_INTRO,
    POWER_CONDITION_REJECTION_MESSAGE,
    POWER_DESCRIPTION,
    POWER_NAME,
    Power,
    PowerCondition,
)


def test_power_has_25_declared_members():
    assert len(Power) == 25


def test_power_condition_has_7_declared_members():
    assert len(PowerCondition) == 7


def test_power_name_covers_every_power():
    assert set(POWER_NAME.keys()) == set(Power)


def test_power_condition_name_covers_every_condition():
    assert set(POWER_CONDITION_NAME.keys()) == set(PowerCondition)


def test_power_name_verbatim_samples():
    assert POWER_NAME[Power.PNONE] == "Nothing"
    assert POWER_NAME[Power.NEW_SEX] == "Change Sex"
    assert POWER_NAME[Power.CAST_SPELL] == "Cast "
    assert POWER_NAME[Power.CHANCE] == "Chance"


def test_power_condition_name_verbatim_samples():
    assert POWER_CONDITION_NAME[PowerCondition.PAY_UP] == "g"
    assert POWER_CONDITION_NAME[PowerCondition.NEED_KING] == "King"
    assert POWER_CONDITION_NAME[PowerCondition.DRAIN_COURAGE] == "-Cour."


def test_power_condition_pc_none_is_empty_string():
    # YAK.PAS's own coname table gives PCNone the empty string, not a
    # missing value -- no condition text needed when there's no condition.
    assert POWER_CONDITION_NAME[PowerCondition.PC_NONE] == ""


# -- Phase 97: MCOND.X2/PCOND.X2 --


def test_mcond_template_covers_every_condition():
    assert set(MCOND_TEMPLATE.keys()) == set(PowerCondition)


def test_pcond_template_covers_every_condition():
    assert set(PCOND_TEMPLATE.keys()) == set(PowerCondition)


def test_mcond_and_pcond_share_the_same_pc_none_text():
    assert MCOND_TEMPLATE[PowerCondition.PC_NONE] == "(No condition here.)"
    assert PCOND_TEMPLATE[PowerCondition.PC_NONE] == "(No condition here.)"


def test_mcond_template_verbatim_sample():
    assert MCOND_TEMPLATE[PowerCondition.NEED_KING] == (
        "Greetings/Rwelcome, my Kingly/RRoyal friend/Rguest.You honor me by "
        "your coming/Rpresence."
    )


def test_pcond_template_verbatim_sample():
    assert PCOND_TEMPLATE[PowerCondition.NEED_KING] == "Only a King may use the power of the $\\."


def test_pcond_template_contains_the_magic_feature_marker():
    # $\ (models/magic_feature.py's own confirmed PROSE.TXT marker) shows
    # up across most PCOND_TEMPLATE entries -- the condition is always
    # about *this* magic feature.
    assert "$\\" in PCOND_TEMPLATE[PowerCondition.PAY_UP]
    assert "$\\" in PCOND_TEMPLATE[PowerCondition.SAME_ALIGN]


# -- Phase 98: FPDESC.X2/SPDESC.X2 --


def test_power_description_covers_every_power():
    assert set(POWER_DESCRIPTION.keys()) == set(Power)


def test_power_description_verbatim_samples():
    assert POWER_DESCRIPTION[Power.PNONE] == "This feature has no power."
    assert POWER_DESCRIPTION[Power.CAST_SPELL] == "The $\\ gives you the magic power to cast ^A ~ spell."
    assert POWER_DESCRIPTION[Power.CHANCE].startswith("The effects of the $\\ are both good and bad!")


def test_cast_spell_feature_description_covers_spells_first_25_ordinals():
    expected = {Spell(v) for v in range(25)}
    assert set(CAST_SPELL_FEATURE_DESCRIPTION.keys()) == expected


def test_cast_spell_feature_description_verbatim_samples():
    assert CAST_SPELL_FEATURE_DESCRIPTION[Spell.BLESS] == "The Bless spell will take effect on this province."
    assert CAST_SPELL_FEATURE_DESCRIPTION[Spell.FLOOD] == "The Flood spell will take effect on this province."


def test_cast_spell_feature_description_illegal_spells_are_marked():
    # 11 of the 25 spells can never actually be granted as a Search
    # Feature's Cast-Spell power -- the game's own source marks them,
    # kept verbatim rather than filtered out.
    illegal = [Spell.RESURRECTION, Spell.HAND_OF_DEATH, Spell.FIREBALL, Spell.CHARM,
               Spell.PSYCHIC_BLAST, Spell.INVISIBILITY, Spell.SPIRITWRACK,
               Spell.CONTROL_UNDEAD, Spell.ICE_SUSPEND, Spell.TELEK_STORM, Spell.MIRROR_IMAGE]
    assert len(illegal) == 11
    for spell in illegal:
        assert "Illegal" in CAST_SPELL_FEATURE_DESCRIPTION[spell]
    legal_sample = set(CAST_SPELL_FEATURE_DESCRIPTION) - set(illegal)
    assert all("Illegal" not in CAST_SPELL_FEATURE_DESCRIPTION[s] for s in legal_sample)


# -- Phase 101: SAY.PAS _NoMeet (inline, not .X2-sourced) --


def test_power_condition_rejection_message_covers_exactly_three_conditions():
    assert set(POWER_CONDITION_REJECTION_MESSAGE.keys()) == {
        PowerCondition.SAME_ALIGN,
        PowerCondition.NEED_KING,
        PowerCondition.G_TURN,
    }


def test_power_condition_rejection_message_excludes_conditions_with_no_case():
    for condition in (PowerCondition.PC_NONE, PowerCondition.PAY_UP,
                       PowerCondition.DRAIN_SKILL, PowerCondition.DRAIN_COURAGE):
        assert condition not in POWER_CONDITION_REJECTION_MESSAGE


def test_power_condition_rejection_message_verbatim_samples():
    assert POWER_CONDITION_REJECTION_MESSAGE[PowerCondition.SAME_ALIGN] == "You are not $o, so begone/Rgo_away!"
    assert POWER_CONDITION_REJECTION_MESSAGE[PowerCondition.G_TURN] == (
        "The power has already been used this turn, so go away!"
    )


def test_power_condition_rejection_intro_verbatim():
    assert POWER_CONDITION_REJECTION_INTRO == "You don't meet the conditions for using the $\\."
