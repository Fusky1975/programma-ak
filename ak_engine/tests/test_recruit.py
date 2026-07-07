from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.race import Race
from ak_engine.turn.recruit import (
    IncompatibleRaceError,
    is_army_type_compatible_with_race,
    recruit_limit,
    resolve_recruit,
)


def test_mundane_army_type_compatible_with_any_humanoid_race():
    for race in (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH):
        assert is_army_type_compatible_with_race(ArmyType.BOWMEN, race)


def test_mundane_army_type_incompatible_with_monstrous_race():
    assert not is_army_type_compatible_with_race(ArmyType.BOWMEN, Race.DRAGONS)


def test_monstrous_army_type_only_compatible_with_its_own_race():
    assert is_army_type_compatible_with_race(ArmyType.DRAGON_WING, Race.DRAGONS)
    assert not is_army_type_compatible_with_race(ArmyType.DRAGON_WING, Race.HUMAN)
    assert not is_army_type_compatible_with_race(ArmyType.DRAGON_WING, Race.EAGLES)


def test_recruit_limit_is_normally_one():
    assert recruit_limit(ArmyType.BOWMEN, is_home_province=False, province_race=Race.HUMAN) == 1


def test_recruit_limit_doubles_in_home_province():
    assert recruit_limit(ArmyType.BOWMEN, is_home_province=True, province_race=Race.HUMAN) == 2


def test_garrison_gets_limit_of_two_in_any_humanoid_province_even_if_not_home():
    assert recruit_limit(ArmyType.GARRISON, is_home_province=False, province_race=Race.ELVEN) == 2


def test_garrison_limit_is_one_in_non_humanoid_non_home_province():
    assert recruit_limit(ArmyType.GARRISON, is_home_province=False, province_race=Race.DRAGONS) == 1


def test_resolve_recruit_native_cost_matches_army_table_pay():
    result = resolve_recruit(
        ArmyType.HVY_CAVALRY, Race.HUMAN,
        is_home_province=False, is_native_to_province=True,
    )
    assert result.gold_per_unit == 3
    assert result.is_double_cost is False
    assert result.ally_fee_per_unit == 0
    assert result.max_units == 1


def test_resolve_recruit_non_native_cost_is_doubled():
    result = resolve_recruit(
        ArmyType.HVY_CAVALRY, Race.HUMAN,
        is_home_province=False, is_native_to_province=False,
    )
    assert result.gold_per_unit == 6
    assert result.is_double_cost is True


def test_resolve_recruit_in_ally_territory_adds_flat_fee():
    result = resolve_recruit(
        ArmyType.BOWMEN, Race.HUMAN,
        is_home_province=False, is_native_to_province=True, in_ally_territory=True,
    )
    assert result.ally_fee_per_unit == 1


def test_resolve_recruit_raises_for_incompatible_race():
    with pytest.raises(IncompatibleRaceError):
        resolve_recruit(
            ArmyType.DRAGON_WING, Race.HUMAN,
            is_home_province=False, is_native_to_province=True,
        )
