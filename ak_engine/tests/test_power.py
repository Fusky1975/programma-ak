from __future__ import annotations

from ak_engine.models.power import (
    MCOND_TEMPLATE,
    PCOND_TEMPLATE,
    POWER_CONDITION_NAME,
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
