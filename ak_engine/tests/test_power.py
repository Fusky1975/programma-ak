from __future__ import annotations

from ak_engine.models.power import (
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
