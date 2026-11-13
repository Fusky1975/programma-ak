from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.race import Race
from ak_engine.turn.recruit import (
    FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT,
    IncompatibleRaceError,
    NonNativeTypeNotYetOwnedError,
    is_army_type_compatible_with_race,
    recruit_limit,
    resolve_recruit,
)


def test_mundane_army_type_compatible_with_any_humanoid_race():
    for race in (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH):
        assert is_army_type_compatible_with_race(ArmyType.BOWMEN, race)


def test_mundane_army_type_incompatible_with_monstrous_race():
    # Phase 929: user-confirmed directly -- "non è possibile" recruit a
    # humanoid-compatible type (e.g. Legion) in a monstrous province.
    assert not is_army_type_compatible_with_race(ArmyType.BOWMEN, Race.DRAGONS)


def test_monstrous_army_type_only_compatible_with_its_own_race():
    # Phase 929: user-confirmed directly -- "non è possibile reclutare
    # un'unità mostruosa in una provincia umanoide" (a King/Hero who has
    # a Dragon Wing army can't recruit Dragon Wings in a human province).
    assert is_army_type_compatible_with_race(ArmyType.DRAGON_WING, Race.DRAGONS)
    assert not is_army_type_compatible_with_race(ArmyType.DRAGON_WING, Race.HUMAN)
    assert not is_army_type_compatible_with_race(ArmyType.DRAGON_WING, Race.EAGLES)


def test_dinosaurs_only_compatible_with_elven_race():
    # Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS` -- "trainable only
    # by skilled Elven riders" -- narrower than the generic humanoid
    # fallback (Human/Dwarven/Orcish are humanoid too, but not eligible).
    assert is_army_type_compatible_with_race(ArmyType.DINOSAURS, Race.ELVEN)
    for race in (Race.HUMAN, Race.DWARVEN, Race.ORCISH, Race.DRAGONS, Race.EAGLES):
        assert not is_army_type_compatible_with_race(ArmyType.DINOSAURS, race)


def test_recruit_limit_is_normally_one():
    assert recruit_limit(ArmyType.BOWMEN, is_home_province=False, province_race=Race.HUMAN) == 1


def test_recruit_limit_doubles_in_home_province():
    assert recruit_limit(ArmyType.BOWMEN, is_home_province=True, province_race=Race.HUMAN) == 2


def test_garrison_gets_limit_of_two_in_any_humanoid_province_even_if_not_home():
    assert recruit_limit(ArmyType.GARRISON, is_home_province=False, province_race=Race.ELVEN) == 2


def test_garrison_limit_is_one_in_non_humanoid_non_home_province():
    assert recruit_limit(ArmyType.GARRISON, is_home_province=False, province_race=Race.DRAGONS) == 1


def test_former_home_province_now_allied_allows_four():
    assert (
        recruit_limit(
            ArmyType.BOWMEN,
            is_home_province=False,
            province_race=Race.HUMAN,
            is_former_home_province_now_allied=True,
        )
        == FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT
        == 4
    )


def test_former_home_province_now_allied_takes_priority_over_home_province_flag():
    # Mutually exclusive by construction in the caller, but the limit
    # function itself should still prefer the more specific case.
    assert (
        recruit_limit(
            ArmyType.BOWMEN,
            is_home_province=True,
            province_race=Race.HUMAN,
            is_former_home_province_now_allied=True,
        )
        == FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT
    )


def test_resolve_recruit_passes_through_former_home_province_flag():
    result = resolve_recruit(
        ArmyType.BOWMEN, Race.HUMAN,
        is_home_province=False, is_native_to_province=True,
        in_ally_territory=True, is_former_home_province_now_allied=True,
    )
    assert result.max_units == FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT


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
        is_home_province=False, is_native_to_province=False, commander_already_has_type=True,
    )
    assert result.gold_per_unit == 6
    assert result.is_double_cost is True


def test_resolve_recruit_non_native_without_an_existing_unit_is_not_recruitable():
    # RULES.AK [3.4], sourced directly from the user: a non-native type is
    # only recruitable at double cost if the commander already has another
    # unit of that type -- without that, it isn't recruitable at all.
    with pytest.raises(NonNativeTypeNotYetOwnedError):
        resolve_recruit(
            ArmyType.HVY_CAVALRY, Race.HUMAN,
            is_home_province=False, is_native_to_province=False,
        )


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


def test_resolve_recruit_raises_cleanly_for_an_army_type_with_no_rulebook_cost():
    # Bug fix (crash): Vampires/Marauders/Shamans/Crossbow/Javelins/
    # Artillery/Spiders/D_Turtle never appear in the rulebook's own Army
    # Type Table [6.3], so ARMY_TABLE has no entry for them -- an honest
    # sourcing gap. is_army_type_compatible_with_race() still lets them
    # through in any ordinary humanoid province (none has a
    # MONSTROUS_ARMY_RACE entry), so this used to crash with a bare,
    # unhandled KeyError on the `.pay` lookup instead of this clean,
    # already-handled IncompatibleRaceError.
    for army_type in (ArmyType.VAMPIRES, ArmyType.MARAUDERS, ArmyType.CROSSBOW):
        with pytest.raises(IncompatibleRaceError):
            resolve_recruit(
                army_type, Race.HUMAN,
                is_home_province=False, is_native_to_province=True,
            )


# -- Phase 1054 bug fix: hiring_existing_mercenary bypasses both
# IncompatibleRaceError and NonNativeTypeNotYetOwnedError --


def test_resolve_recruit_hiring_existing_mercenary_bypasses_incompatible_race():
    # RULES.AK [3.4]: "mercenaries can be Recruited in any province by
    # any character" -- a hireable mercenary of a race-incompatible type
    # must not be rejected by the same race-compatibility gate a populace
    # levy would hit.
    result = resolve_recruit(
        ArmyType.DRAGON_WING, Race.HUMAN,
        is_home_province=False, is_native_to_province=False, hiring_existing_mercenary=True,
    )
    assert result is not None


def test_resolve_recruit_hiring_existing_mercenary_bypasses_non_native_ownership():
    result = resolve_recruit(
        ArmyType.HVY_CAVALRY, Race.HUMAN,
        is_home_province=False, is_native_to_province=False, hiring_existing_mercenary=True,
    )
    # Still subject to the real non-native doubling -- the module's own
    # "doesn't distinguish hiring from levying on price" rule (Phase 16)
    # -- only the two eligibility exceptions are bypassed, not the cost.
    assert result.gold_per_unit == 6
    assert result.is_double_cost is True


def test_resolve_recruit_hiring_existing_mercenary_still_requires_a_rulebook_cost():
    # The missing-ARMY_TABLE-entry guard is unrelated to race/nativity --
    # it stays unconditional even for a mercenary hire, since there is
    # genuinely no cost data to charge by.
    with pytest.raises(IncompatibleRaceError):
        resolve_recruit(
            ArmyType.VAMPIRES, Race.HUMAN,
            is_home_province=False, is_native_to_province=True, hiring_existing_mercenary=True,
        )


# -- Phase 663: Chief of Staff's own -1 gold discount --


def test_resolve_recruit_chief_of_staff_discount_reduces_native_cost_by_1():
    result = resolve_recruit(
        ArmyType.HVY_CAVALRY, Race.HUMAN,
        is_home_province=False, is_native_to_province=True, chief_of_staff_discount=True,
    )
    assert result.gold_per_unit == 2  # base pay 3, minus 1


def test_resolve_recruit_chief_of_staff_discount_floors_at_zero_garrison_is_free():
    result = resolve_recruit(
        ArmyType.GARRISON, Race.HUMAN,
        is_home_province=False, is_native_to_province=True, chief_of_staff_discount=True,
    )
    assert result.gold_per_unit == 0


def test_resolve_recruit_chief_of_staff_discount_taken_before_non_native_doubling():
    # Real text: "the discount is taken before the recruitment cost is
    # doubled" -- (3-1)*2 == 4, not (3*2)-1 == 5.
    result = resolve_recruit(
        ArmyType.HVY_CAVALRY, Race.HUMAN,
        is_home_province=False, is_native_to_province=False, chief_of_staff_discount=True,
        commander_already_has_type=True,
    )
    assert result.gold_per_unit == 4


def test_resolve_recruit_chief_of_staff_discount_off_by_default():
    result = resolve_recruit(
        ArmyType.HVY_CAVALRY, Race.HUMAN,
        is_home_province=False, is_native_to_province=True,
    )
    assert result.gold_per_unit == 3
