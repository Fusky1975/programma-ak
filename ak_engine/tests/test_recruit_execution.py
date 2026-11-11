from __future__ import annotations

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.recruit_decode import RecruitRequest
from ak_engine.turn.recruit_execution import execute_recruit

LOCATION = HexCoord(3, 9)
LEADER_ID = 1


def build_state(*, treasury: int = 100, is_home_province: bool = False) -> GameState:
    state = GameState()
    home = LOCATION if is_home_province else HexCoord(0, 0)
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, home, treasury=treasury))
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", LOCATION))
    return state


def test_recruits_and_debits_exact_cost():
    state = build_state()
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])  # pay 2

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.total_gold_spent == 2
    assert state.kingdoms[1].treasury == 98
    new_army_id = result.recruited[0].army_id
    assert state.armies[new_army_id].army_type == ArmyType.BOWMEN
    assert state.armies[new_army_id].location == LOCATION
    assert state.armies[new_army_id].commanded_by is None
    # Bug fix, sourced directly from the user (2026-10-29), rulebook
    # [3.9]: a fresh levy can't be Pick Up'd the same turn it was
    # recruited -- turn/plan_dispatch.py _dispatch_pick_up()'s own
    # real consumer of this flag.
    assert state.armies[new_army_id].recruited_this_turn is True


def test_new_army_commanded_by_requested_leader():
    state = build_state()
    state.add_leader(LeaderState(2, 1, "Other Leader", LOCATION))
    request = RecruitRequest(leader_id=2, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert state.armies[result.recruited[0].army_id].commanded_by == 2


def test_recruit_falls_back_to_unled_when_requested_leader_does_not_exist():
    # Rulebook [3.4]: "Any character in the province may lead the
    # armies" -- a target leader id with no LeaderState at all can't
    # plausibly have issued this order, so command falls back to the
    # garrison instead of pointing at a nonexistent leader.
    state = build_state()
    request = RecruitRequest(leader_id=999, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert state.armies[result.recruited[0].army_id].commanded_by is None


def test_recruit_falls_back_to_unled_when_requested_leader_is_elsewhere():
    state = build_state()
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(2, 1, "Elsewhere Leader", HexCoord(5, 5)))
    request = RecruitRequest(leader_id=2, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert state.armies[result.recruited[0].army_id].commanded_by is None


def test_recruit_falls_back_to_unled_leaves_a_colocated_mercenary_unaffected_by_a_bad_target():
    # Same "nonexistent target -> garrison" fallback, exercised through
    # the mercenary-hiring branch instead of the fresh-levy branch.
    state = build_state()
    state.add_army(ArmyState(50, None, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=999, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is True
    assert state.armies[50].commanded_by is None


def test_per_type_limit_blocks_excess_within_one_request_non_home():
    state = build_state(is_home_province=False)
    # Normal (non-home) limit is 1 per type; request 2.
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN, ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.BOWMEN]


def test_home_province_allows_two_of_a_type():
    state = build_state(is_home_province=True)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN, ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 2
    assert result.limit_blocked == []


def test_limit_persists_across_separate_recruit_calls_same_turn():
    state = build_state(is_home_province=False)
    first = execute_recruit(
        state, kingdom_id=1, leader_id=LEADER_ID, request=RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])
    )
    second = execute_recruit(
        state, kingdom_id=1, leader_id=LEADER_ID, request=RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])
    )

    assert len(first.recruited) == 1
    assert len(second.recruited) == 0
    assert second.limit_blocked == [ArmyType.BOWMEN]


def test_insufficient_treasury_blocks_recruit():
    state = build_state(treasury=1)  # Bowmen cost 2
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.gold_blocked == [ArmyType.BOWMEN]
    assert state.kingdoms[1].treasury == 1  # untouched


def test_recruiting_in_ally_territory_credits_the_ally():
    state = build_state(treasury=100)
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0), treasury=0))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[LOCATION].owner_kingdom_id = 2
    state.treat_permissions.add((2, 1))  # owner (2) grants recruiter (1) permission
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])  # pay 2 + 1 ally fee

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 3
    assert state.kingdoms[1].treasury == 97
    assert state.kingdoms[2].treasury == 1
    assert result.recruited[0].ally_fee_paid == 1


def test_recruit_in_own_territory_reports_no_ally_fee():
    state = build_state(treasury=100)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].ally_fee_paid == 0


def test_recruiting_in_ally_territory_without_a_treat_order_is_blocked():
    # Rulebook [3.4]: "In order for you to Recruit in your ally's
    # territory, he MUST issue a 'Treat' order with you (even though
    # you may already be allied.)" -- being merely allied isn't enough.
    state = build_state(treasury=100)
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0), treasury=0))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[LOCATION].owner_kingdom_id = 2
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN, ArmyType.AXEMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.treat_blocked == [ArmyType.BOWMEN, ArmyType.AXEMEN]
    assert result.total_gold_spent == 0
    assert state.kingdoms[1].treasury == 100
    assert state.kingdoms[2].treasury == 0


def test_treat_permission_is_directional_the_other_way_round_does_not_count():
    state = build_state(treasury=100)
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0), treasury=0))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[LOCATION].owner_kingdom_id = 2
    state.treat_permissions.add((1, 2))  # wrong direction: recruiter granting himself
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.treat_blocked == [ArmyType.BOWMEN]


def test_treat_permission_not_required_in_own_territory():
    state = build_state(treasury=100)  # province owned by kingdom 1 itself
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.treat_blocked == []


def test_has_treat_permission_helper():
    state = GameState()

    assert state.has_treat_permission(2, 1) is False

    state.treat_permissions.add((2, 1))

    assert state.has_treat_permission(2, 1) is True
    assert state.has_treat_permission(1, 2) is False


def test_levy_blocked_in_a_hostile_non_allied_provinces_own_territory():
    # Phase 303 fix: RULES.AK [3.4], "You can Recruit armies from the
    # populace only if you own the province" -- a levy (no mercenary
    # present) in a province owned by an unallied kingdom used to
    # silently succeed; now it's blocked.
    state = build_state(treasury=100)
    state.add_kingdom(KingdomState(2, "Hostilia", Race.HUMAN, Alignment.EVIL, HexCoord(0, 0), treasury=0))
    state.provinces[LOCATION].owner_kingdom_id = 2  # not allied with kingdom 1
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.territory_blocked == [ArmyType.BOWMEN]
    assert result.total_gold_spent == 0
    assert state.kingdoms[1].treasury == 100  # untouched -- never debited


def test_levy_blocked_in_an_unclaimed_non_player_province():
    state = build_state(treasury=100)
    state.provinces[LOCATION].owner_kingdom_id = None
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.territory_blocked == [ArmyType.BOWMEN]
    assert state.kingdoms[1].treasury == 100


def test_mercenary_hire_still_works_in_hostile_territory_where_a_levy_would_be_blocked():
    # RULES.AK [3.4]'s own second half of the same sentence: "mercenaries
    # can be Recruited in any province by any character, even a King who
    # owns no provinces." The territory gate must never touch this path.
    state = build_state(treasury=100)
    state.add_kingdom(KingdomState(2, "Hostilia", Race.HUMAN, Alignment.EVIL, HexCoord(0, 0), treasury=0))
    state.provinces[LOCATION].owner_kingdom_id = 2
    state.add_army(ArmyState(50, None, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.recruited[0].hired is True
    assert result.territory_blocked == []
    assert state.armies[50].kingdom_id == 1


def test_former_home_province_now_allied_allows_four_units():
    # Rulebook [3.4]: "if you are recruiting in your former home
    # province which is now your ally's province, you can recruit 4
    # units" -- more generous than either the ordinary 1-per-type ally
    # territory limit or the ordinary 2-per-type home province limit.
    state = build_state(treasury=1000, is_home_province=True)
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(5, 5), treasury=0))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[LOCATION].owner_kingdom_id = 2  # an ally now holds it
    state.treat_permissions.add((2, 1))
    request = RecruitRequest(
        leader_id=None, army_types=[ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.BOWMEN]
    )

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 4
    assert result.limit_blocked == []


def test_former_home_province_now_allied_still_gated_by_treat_permission():
    state = build_state(treasury=1000, is_home_province=True)
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(5, 5), treasury=0))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[LOCATION].owner_kingdom_id = 2
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.treat_blocked == [ArmyType.BOWMEN]


def test_own_home_province_still_limited_to_two_when_self_owned():
    # Same location as the kingdom's home_province, but never lost to
    # anyone -- ordinary home-province bonus, not the 4-unit case.
    state = build_state(treasury=1000, is_home_province=True)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 2
    assert result.limit_blocked == [ArmyType.BOWMEN]


def test_incompatible_army_type_is_reported_not_recruited():
    state = build_state()
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DRAGON_WING])  # needs Dragons race

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.incompatible == [ArmyType.DRAGON_WING]
    assert state.kingdoms[1].treasury == 100  # untouched


def test_new_army_ids_do_not_collide_across_multiple_recruits():
    state = build_state(treasury=1000, is_home_province=True)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN, ArmyType.AXEMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    ids = [u.army_id for u in result.recruited]
    assert len(ids) == len(set(ids)) == 2


# -- Real per-province Mod_PAT native types (Phase 407) -------------------


def test_recruit_type_1_costs_single_when_mod_pat_known():
    state = build_state()
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.LEGION])  # pay 2

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].gold_paid == 2
    assert state.kingdoms[1].treasury == 98


def test_recruit_type_2_also_counts_as_native():
    state = build_state()
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    state.provinces[LOCATION].recruit_type_2 = ArmyType.BOWMEN
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])  # pay 2

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].gold_paid == 2


def test_race_compatible_but_unlisted_type_costs_double_when_mod_pat_known():
    state = build_state()
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    # Bowmen is humanoid-compatible (race-approximation would call it
    # "native"), but this province's own real Mod_PAT list only names
    # Legion -- still recruitable at double cost, provided the commander
    # already has another Bowmen unit (RULES.AK [3.4], sourced directly
    # from the user, 2026-10-28).
    state.add_army(ArmyState(900, 1, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, commanded_by=LEADER_ID))
    request = RecruitRequest(leader_id=LEADER_ID, army_types=[ArmyType.BOWMEN])  # pay 2 -> 4

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].gold_paid == 4
    assert result.recruited[0].army_type == ArmyType.BOWMEN


def test_race_compatible_but_unlisted_type_without_an_existing_unit_is_not_recruitable():
    # Same scenario as above, but the commander has no pre-existing
    # Bowmen unit -- the new ownership precondition blocks it outright,
    # rather than merely doubling the price.
    state = build_state()
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    request = RecruitRequest(leader_id=LEADER_ID, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.non_native_type_not_owned == [ArmyType.BOWMEN]


def test_garrison_recruitable_in_any_humanoid_province_with_real_slot_data():
    # Phase 1054 bug fix: Garrison is recruitable (2/turn, recruit_limit()'s
    # own real "any humanoid province, home or not" rule) in ANY humanoid
    # province -- it is never genuinely a listed slot type in real
    # per-province data (recruit_type_1/2 here are set to ordinary types,
    # never GARRISON), so without the Phase 1054 exemption, Garrison could
    # never satisfy is_native (slot-table membership) or
    # commander_already_has_type (a Garrison-targeted order has no
    # commander roster), making it permanently unrecruitable once real
    # slot data exists.
    state = build_state()
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    state.provinces[LOCATION].recruit_type_2 = ArmyType.BOWMEN
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.GARRISON])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.non_native_type_not_owned == []
    assert len(result.recruited) == 1
    assert result.recruited[0].army_type == ArmyType.GARRISON


def test_non_native_type_blocked_for_a_garrison_targeted_order():
    # A Garrison-targeted order (leader_id=None) has no commander roster
    # to check ownership against, so a non-native type can never pass
    # this precondition for it -- even with an existing Garrison-
    # commanded unit of that type already present.
    state = build_state()
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    state.add_army(ArmyState(900, 1, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, commanded_by=None))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.non_native_type_not_owned == [ArmyType.BOWMEN]


def test_non_native_type_ownership_check_is_re_evaluated_for_every_unit_in_the_request():
    # The ownership check is re-scanned fresh on every loop iteration
    # (not cached once up front) -- a single pre-existing Bowmen unit
    # from an earlier turn still satisfies the precondition for every
    # Bowmen unit requested in this one call, not just the first.
    # Home province: the per-turn limit for Bowmen is 2, so both units in
    # this one request can actually be recruited -- isolating the
    # ownership check from the separate per-type limit check.
    state = build_state(is_home_province=True)
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    state.provinces[LOCATION].recruit_type_2 = ArmyType.LEGION
    state.add_army(ArmyState(900, 1, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, commanded_by=LEADER_ID))
    request = RecruitRequest(leader_id=LEADER_ID, army_types=[ArmyType.BOWMEN, ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 2
    assert all(unit.army_type is ArmyType.BOWMEN for unit in result.recruited)


def test_mod_pat_unknown_falls_back_to_race_compatibility_single_cost():
    # No recruit_type_1 set (unbridged GameState) -- the pre-existing
    # approximation applies unchanged: any race-compatible type is
    # treated as native, single cost.
    state = build_state()
    assert state.provinces[LOCATION].recruit_type_1 is None
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.LEGION])  # pay 2

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].gold_paid == 2


def test_recruit_hires_colocated_mercenary_instead_of_levying_new_army():
    state = build_state()
    state.add_army(ArmyState(999, None, ArmyType.BOWMEN, Quality.VETERAN, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.recruited[0].army_id == 999
    assert result.recruited[0].hired is True
    assert result.total_gold_spent == 2  # same price as levying fresh
    assert state.armies[999].kingdom_id == 1
    assert state.armies[999].commanded_by is None
    assert state.armies[999].quality == Quality.VETERAN  # preserved, not reset to Average
    assert len(state.armies) == 1  # no new army created
    # Rulebook [3.9]'s own exception: a hired mercenary "already
    # existed, with its own id" -- exempt from the same-turn Pick Up
    # restriction, unlike a fresh levy.
    assert state.armies[999].recruited_this_turn is False
    # Bug fix (2026-10-25): a hired mercenary is no longer "available to
    # Recruit" -- see `ArmyState.is_mercenary`'s own docstring.
    assert state.armies[999].is_mercenary is False


def test_recruit_hires_a_race_incompatible_mercenary_in_any_province():
    # Phase 1054 bug fix: RULES.AK [3.4] "mercenaries can be Recruited in
    # any province by any character" -- resolve_recruit()'s own race-
    # compatibility gate used to run before the mercenary lookup, so a
    # race-incompatible mercenary (e.g. Ents, Race.ENTISH-locked) sitting
    # in an ordinary Human province was rejected via IncompatibleRaceError
    # before ever being discovered, even though a real, hireable
    # mercenary of that exact type was physically present.
    state = build_state()  # province race is Race.HUMAN
    state.add_army(ArmyState(999, None, ArmyType.ENTS, Quality.VETERAN, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.ENTS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.incompatible == []
    assert len(result.recruited) == 1
    assert result.recruited[0].army_id == 999
    assert result.recruited[0].hired is True


def test_recruit_hires_a_non_native_mercenary_without_requiring_prior_ownership():
    # Phase 1054 bug fix: same bug, the other exception -- a race-
    # compatible-but-unlisted mercenary used to be rejected via
    # NonNativeTypeNotYetOwnedError before the mercenary lookup ever ran,
    # even though the commander-ownership precondition that exception
    # encodes is only about levying from the populace, not about hiring
    # an army that already physically exists.
    state = build_state()
    state.provinces[LOCATION].recruit_type_1 = ArmyType.LEGION
    state.add_army(ArmyState(999, None, ArmyType.BOWMEN, Quality.VETERAN, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])  # not owned, not listed

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.non_native_type_not_owned == []
    assert len(result.recruited) == 1
    assert result.recruited[0].army_id == 999
    assert result.recruited[0].hired is True
    # Still subject to the real non-native doubling the module docstring's
    # own "doesn't distinguish hiring from levying on price" rule
    # (Phase 16) describes -- 2 base, doubled to 4.
    assert result.total_gold_spent == 4


def test_recruit_ignores_mercenary_below_average_quality():
    state = build_state()
    state.add_army(ArmyState(999, None, ArmyType.BOWMEN, Quality.GREEN, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is False
    assert state.armies[999].kingdom_id is None  # untouched, still a mercenary
    assert len(state.armies) == 2  # a fresh army was levied instead


def test_recruit_ignores_unhireable_mercenary():
    state = build_state()
    mercenary = ArmyState(999, None, ArmyType.BOWMEN, Quality.VETERAN, LOCATION, is_mercenary=True)
    mercenary.unhireable_this_turn = True
    state.add_army(mercenary)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is False
    assert state.armies[999].kingdom_id is None


def test_recruit_ignores_mercenary_of_a_different_type_or_location():
    state = build_state()
    state.add_army(ArmyState(998, None, ArmyType.AXEMEN, Quality.VETERAN, LOCATION, is_mercenary=True))  # wrong type
    state.add_army(ArmyState(997, None, ArmyType.BOWMEN, Quality.VETERAN, HexCoord(0, 0), is_mercenary=True))  # wrong place
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is False
    assert state.armies[998].kingdom_id is None
    assert state.armies[997].kingdom_id is None


# -- Wingman's own recruitment bonus (Phase 472) ---------------------------


def build_dragon_state(*, treasury: int = 1000) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0), treasury=treasury))
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.DRAGONS, owner_kingdom_id=1))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", LOCATION))
    return state


def test_no_wingman_bonus_by_default():
    state = build_dragon_state()
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DRAGON_WING, ArmyType.DRAGON_WING])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.DRAGON_WING]


def test_wingman_grants_one_extra_flying_unit():
    state = build_dragon_state()
    state.leaders[LEADER_ID].merit_tally.air_combat_merit = 5  # meets OFFICE_MIN_POINTS[Office.WINGMAN]
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DRAGON_WING, ArmyType.DRAGON_WING])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 2
    assert result.limit_blocked == []


def test_wingman_bonus_does_not_apply_to_a_non_flying_type():
    state = build_state(is_home_province=False)  # ordinary Human province
    state.leaders[LEADER_ID].merit_tally.air_combat_merit = 5
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN, ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.BOWMEN]


def test_wingman_bonus_does_not_rescue_a_race_incompatible_flying_type():
    state = build_state(is_home_province=False)  # Human province -- Dragons don't fit here
    state.leaders[LEADER_ID].merit_tally.air_combat_merit = 5
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DRAGON_WING])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.incompatible == [ArmyType.DRAGON_WING]


def test_wingman_bonus_only_applies_to_the_titleholder_not_a_different_leader():
    state = build_dragon_state()
    state.add_leader(LeaderState(2, 1, "Other Leader", LOCATION))
    state.leaders[2].merit_tally.air_combat_merit = 5  # leader 2 is Wingman, not the acting leader
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DRAGON_WING, ArmyType.DRAGON_WING])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.DRAGON_WING]


# -- Grand Marshal/Grand Admiral's own recruitment bonuses (Phase 488) -----


def test_no_marshal_or_admiral_bonus_by_default():
    state = build_state()
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.LEGION, ArmyType.LEGION])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.LEGION]


def test_marshal_grants_one_extra_land_unit():
    state = build_state()
    state.leaders[LEADER_ID].merit_tally.land_battles_won_points = 1  # meets OFFICE_MIN_POINTS[Office.MARSHAL]
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.LEGION, ArmyType.LEGION])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 2
    assert result.limit_blocked == []


def test_marshal_bonus_does_not_apply_to_a_flying_type():
    state = build_dragon_state()
    state.leaders[LEADER_ID].merit_tally.land_battles_won_points = 1
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DRAGON_WING, ArmyType.DRAGON_WING])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.DRAGON_WING]


def test_marshal_bonus_does_not_apply_to_a_naval_type():
    state = build_state()
    state.leaders[LEADER_ID].merit_tally.land_battles_won_points = 1
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.FLEET, ArmyType.FLEET])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.FLEET]


def test_admiral_grants_one_extra_naval_unit():
    state = build_state()
    state.leaders[LEADER_ID].merit_tally.naval_battles_won_points = 1  # meets OFFICE_MIN_POINTS[Office.ADMIRAL]
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.FLEET, ArmyType.FLEET])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 2
    assert result.limit_blocked == []


def test_admiral_bonus_does_not_apply_to_a_land_type():
    state = build_state()
    state.leaders[LEADER_ID].merit_tally.naval_battles_won_points = 1
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.LEGION, ArmyType.LEGION])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.LEGION]


def test_marshal_and_admiral_bonuses_only_apply_to_the_titleholder():
    state = build_state()
    state.add_leader(LeaderState(2, 1, "Other Leader", LOCATION))
    state.leaders[2].merit_tally.land_battles_won_points = 1
    state.leaders[2].merit_tally.naval_battles_won_points = 1
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.LEGION, ArmyType.LEGION])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.limit_blocked == [ArmyType.LEGION]


def test_same_leader_can_stack_marshal_and_admiral_bonuses_for_their_own_types():
    # Rulebook [10.1]: "uno stesso personaggio puo aggiudicarsene piu di
    # una" -- one leader may hold more than one Office at once.
    state = build_state()
    state.leaders[LEADER_ID].merit_tally.land_battles_won_points = 1
    state.leaders[LEADER_ID].merit_tally.naval_battles_won_points = 1
    request = RecruitRequest(
        leader_id=None, army_types=[ArmyType.LEGION, ArmyType.LEGION, ArmyType.FLEET, ArmyType.FLEET]
    )

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 4


# -- Chief of Staff's own -1 gold recruit discount (Phase 663) -------------


def test_no_chief_of_staff_discount_by_default():
    state = build_state()
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.HVY_CAVALRY])  # pay 3

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 3


def test_chief_of_staff_discounts_every_unit_recruited_by_the_titleholder():
    state = build_state()
    state.leaders[LEADER_ID].skills = SkillTable(raw_values=[0] * 30)
    state.leaders[LEADER_ID].skills.set_pair_for_ability(Ability.TACTICAL, 7, 7)  # OFFICE_MIN_POINTS[CHIEF_OF_STAFF]
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.HVY_CAVALRY])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 2


def test_chief_of_staff_discount_makes_garrison_free():
    state = build_state()
    state.leaders[LEADER_ID].skills = SkillTable(raw_values=[0] * 30)
    state.leaders[LEADER_ID].skills.set_pair_for_ability(Ability.TACTICAL, 7, 7)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.GARRISON])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 0


def test_chief_of_staff_discount_only_applies_to_the_titleholder_not_a_different_leader():
    state = build_state()
    state.add_leader(LeaderState(2, 1, "Other Leader", LOCATION))
    state.leaders[2].skills = SkillTable(raw_values=[0] * 30)
    state.leaders[2].skills.set_pair_for_ability(Ability.TACTICAL, 7, 7)  # leader 2 is Chief of Staff
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.HVY_CAVALRY])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 3


# -- Neutral King's own "recruit mercenaries for 1 gold" (Phase 663) -------


def build_neutral_king_state(*, treasury: int = 100) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=treasury))
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    leader = LeaderState(LEADER_ID, 1, "Test Leader", LOCATION, is_king=True)
    state.add_leader(leader)
    return state


def _grant_neutral_king_title(state: GameState) -> None:
    # tax=30 gives this King a real Tax_Base >= OFFICE_MIN_POINTS[Office.
    # NEUTRAL_KING] (25), so resolve_office_holder() actually resolves
    # him -- a Neutral-aligned Kingdom alone isn't enough on its own.
    state.provinces[LOCATION].tax = 30


def test_no_neutral_king_discount_by_default():
    # Neutral-aligned, but no real Tax_Base -- doesn't actually hold the
    # title yet, matching the same "alignment alone isn't enough"
    # distinction the merit-formula itself makes.
    state = build_neutral_king_state()
    state.add_army(ArmyState(999, None, ArmyType.BOWMEN, Quality.VETERAN, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 2  # ordinary levy price, mercenary or not


def test_neutral_king_hires_a_mercenary_for_1_gold():
    state = build_neutral_king_state()
    _grant_neutral_king_title(state)
    state.add_army(ArmyState(999, None, ArmyType.HVY_CAVALRY, Quality.VETERAN, LOCATION, is_mercenary=True))  # pay 3 normally
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.HVY_CAVALRY])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is True
    assert result.total_gold_spent == 1


def test_neutral_king_discount_does_not_apply_to_a_fresh_levy():
    # Real text names mercenaries specifically -- "maintenance costs
    # remain normal" implies the discount is about hiring an existing
    # army, not the whole recruiting-from-the-populace mechanic.
    state = build_neutral_king_state()
    _grant_neutral_king_title(state)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.HVY_CAVALRY])  # no mercenary present

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is False
    assert result.total_gold_spent == 3


def test_neutral_king_discount_still_adds_the_ally_fee_in_ally_territory():
    state = build_neutral_king_state()
    # A second, Testia-owned province supplies the real Tax_Base (LOCATION
    # itself gets reassigned to the ally below, so it can't supply it).
    state.add_province(ProvinceState(HexCoord(9, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(5, 5), treasury=0))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[LOCATION].owner_kingdom_id = 2
    state.treat_permissions.add((2, 1))
    state.add_army(ArmyState(999, None, ArmyType.HVY_CAVALRY, Quality.VETERAN, LOCATION, is_mercenary=True))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.HVY_CAVALRY])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 2  # 1 gold flat + 1 gold ally fee


# Phase 691: Dinosaur armies (`AdvancedAbility.DRUIDIC_DINOSAURS`).

DINOSAUR_LOCATION = HexCoord(4, 4)


def build_dinosaur_state(*, druid_skill: int = 0, has_ability: bool = True, province_race: Race = Race.ELVEN) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Elvenholm", Race.ELVEN, Alignment.GOOD, HexCoord(0, 0), treasury=100))
    state.add_province(ProvinceState(DINOSAUR_LOCATION, Terrain.PLAINS, province_race, owner_kingdom_id=1))
    raw = [0] * 30
    raw[Ability.DRUID.value * 2] = druid_skill
    advanced_abilities = {AdvancedAbility.DRUIDIC_DINOSAURS} if has_ability else set()
    state.add_leader(
        LeaderState(
            LEADER_ID,
            1,
            "Druid Leader",
            DINOSAUR_LOCATION,
            skills=SkillTable(raw_values=raw),
            advanced_abilities=advanced_abilities,
        )
    )
    return state


def test_dinosaur_recruit_succeeds_at_full_quality_with_druid_skill_5():
    state = build_dinosaur_state(druid_skill=5)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    new_army_id = result.recruited[0].army_id
    assert state.armies[new_army_id].quality == Quality.AVERAGE
    assert state.provinces[DINOSAUR_LOCATION].recruit_locked_this_turn is True


def test_dinosaur_recruit_below_druid_skill_5_starts_green():
    state = build_dinosaur_state(druid_skill=4)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    new_army_id = result.recruited[0].army_id
    assert state.armies[new_army_id].quality == Quality.GREEN


def test_dinosaur_recruit_without_advanced_ability_is_incompatible():
    state = build_dinosaur_state(druid_skill=5, has_ability=False)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.incompatible == [ArmyType.DINOSAURS]


def test_dinosaur_recruit_in_non_elven_province_is_incompatible():
    state = build_dinosaur_state(druid_skill=5, province_race=Race.HUMAN)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.incompatible == [ArmyType.DINOSAURS]


def test_second_dinosaur_recruit_request_same_turn_is_province_locked():
    state = build_dinosaur_state(druid_skill=5)
    first = execute_recruit(
        state, kingdom_id=1, leader_id=LEADER_ID, request=RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])
    )
    assert len(first.recruited) == 1

    second = execute_recruit(
        state, kingdom_id=1, leader_id=LEADER_ID, request=RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])
    )

    assert second.recruited == []
    assert second.province_locked == [ArmyType.BOWMEN]


def test_only_one_dinosaur_per_province_per_turn_via_province_lock_mid_request():
    state = build_dinosaur_state(druid_skill=5)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS, ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    # Regression: the 2nd Dinosaur is now blocked by the province lock
    # itself (re-checked every loop iteration), not the ordinary per-type
    # cap -- the first Dinosaur's own successful recruit sets the lock
    # immediately, mid-request, so it takes effect before the 2nd
    # army_type in the SAME request is even considered.
    assert len(result.recruited) == 1
    assert result.limit_blocked == []
    assert result.province_locked == [ArmyType.DINOSAURS]


def test_a_dinosaur_recruit_locks_out_a_different_army_type_in_the_same_request():
    # Regression for the real bug: a single Recruit order can list several
    # army types together (turn/recruit_decode.py's own ordinal list), so
    # "no further units may be recruited in the province that turn" must
    # take effect immediately once the Dinosaur recruit succeeds, not only
    # for a later, separate execute_recruit() call.
    state = build_dinosaur_state(druid_skill=5)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS, ArmyType.LT_CAVALRY])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.recruited[0].army_type is ArmyType.DINOSAURS
    assert result.province_locked == [ArmyType.LT_CAVALRY]


def build_dinosaur_state_with_slots(
    *, recruit_type_1: ArmyType | None, recruit_type_2: ArmyType | None = None
) -> GameState:
    # Phase 980: a province with *real* recruit-slot data (recruit_type_1
    # not None) -- the shape `ProvinceState` actually carries once bridged
    # from a real world file or generated via generate_new_game(), unlike
    # `build_dinosaur_state()` above, which leaves both slots at their
    # default None (no real per-province data to check the new gate
    # against at all -- see that fallback's own Phase 980 docstring note).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Elvenholm", Race.ELVEN, Alignment.GOOD, HexCoord(0, 0), treasury=100))
    state.add_province(
        ProvinceState(
            DINOSAUR_LOCATION,
            Terrain.PLAINS,
            Race.ELVEN,
            owner_kingdom_id=1,
            recruit_type_1=recruit_type_1,
            recruit_type_2=recruit_type_2,
        )
    )
    raw = [0] * 30
    raw[Ability.DRUID.value * 2] = 5
    state.add_leader(
        LeaderState(
            LEADER_ID,
            1,
            "Druid Leader",
            DINOSAUR_LOCATION,
            skills=SkillTable(raw_values=raw),
            advanced_abilities={AdvancedAbility.DRUIDIC_DINOSAURS},
        )
    )
    return state


def test_dinosaur_recruit_blocked_when_province_has_neither_elven_el_lc_nor_hc_slot():
    # Phase 980, user-confirmed: "only in place of elven EL, LC or HC" --
    # a province recruiting ordinary Bowmen/Axemen has neither qualifying
    # slot, so Dinosaurs can't be recruited there even with the ability
    # and sufficient Druid skill.
    state = build_dinosaur_state_with_slots(recruit_type_1=ArmyType.BOWMEN, recruit_type_2=ArmyType.AXEMEN)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.elven_slot_required == [ArmyType.DINOSAURS]


@pytest.mark.parametrize("qualifying_type", [ArmyType.ELEPHANTS, ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY])
def test_dinosaur_recruit_allowed_when_either_slot_is_elephants_lt_cavalry_or_hvy_cavalry(qualifying_type):
    # Checked in both slot positions -- the gate doesn't care which of the
    # province's two slots carries the qualifying type.
    state_first_slot = build_dinosaur_state_with_slots(recruit_type_1=qualifying_type, recruit_type_2=ArmyType.BOWMEN)
    result_first_slot = execute_recruit(
        state_first_slot, kingdom_id=1, leader_id=LEADER_ID, request=RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])
    )
    assert len(result_first_slot.recruited) == 1
    assert result_first_slot.elven_slot_required == []

    state_second_slot = build_dinosaur_state_with_slots(recruit_type_1=ArmyType.BOWMEN, recruit_type_2=qualifying_type)
    result_second_slot = execute_recruit(
        state_second_slot, kingdom_id=1, leader_id=LEADER_ID, request=RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])
    )
    assert len(result_second_slot.recruited) == 1
    assert result_second_slot.elven_slot_required == []


def test_dinosaur_recruit_via_real_slot_data_is_not_charged_double():
    # Phase 1054 bug fix: Dinosaurs' own complete cost is "Speed: 3; Pay:
    # 3" per AdvancedAbility.DRUIDIC_DINOSAURS's own real description --
    # no native/non-native doubling is mentioned anywhere in that sourced
    # text. Previously, since DINOSAURS can never itself be one of a
    # province's two real recruit_type_1/2 slots, is_native was always
    # False via this path, silently doubling the price to 6 even with
    # every real precondition (Elven province, ability, Druid skill 5,
    # qualifying Elephants/Lt Cavalry/Hvy Cavalry slot) satisfied.
    state = build_dinosaur_state_with_slots(recruit_type_1=ArmyType.ELEPHANTS, recruit_type_2=ArmyType.BOWMEN)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.recruited[0].gold_paid == 3
    assert result.total_gold_spent == 3


def test_dinosaur_recruit_slot_gate_is_skipped_when_province_has_no_real_slot_data():
    # build_dinosaur_state() (above) never sets recruit_type_1/2 (None,
    # None) -- the same "no real per-province data to check" fallback
    # is_native_to_province already uses, so the new gate must not block
    # every hand-built test fixture that predates it.
    state = build_dinosaur_state(druid_skill=5)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.DINOSAURS])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert len(result.recruited) == 1
    assert result.elven_slot_required == []


def test_execute_recruit_by_a_dead_leader_is_a_clean_no_op_not_a_crash():
    # Phase 825: a leader who died earlier this same turn can still have a
    # later-phase Recruit order dispatched for them (turn/plan_dispatch.py's
    # own per-phase loop has no leader-liveness gate of its own). Previously
    # this raised a real, unhandled KeyError from a bare state.leaders[
    # leader_id] lookup.
    state = build_state()
    del state.leaders[LEADER_ID]  # died in an earlier phase this same turn
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited == []
    assert result.limit_blocked == []
    assert result.gold_blocked == []
    assert result.incompatible == []
    assert result.treat_blocked == []
    assert result.territory_blocked == []
    assert result.province_locked == []
    assert result.total_gold_spent == 0
    assert state.kingdoms[1].treasury == 100  # untouched
    assert state.armies == {}  # nothing recruited
