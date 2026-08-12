from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
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
    state.add_army(ArmyState(50, None, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))
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
    state.add_army(ArmyState(50, None, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))
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
    # Legion -- still recruitable, just at double cost.
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])  # pay 2 -> 4

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].gold_paid == 4
    assert result.recruited[0].army_type == ArmyType.BOWMEN


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
    state.add_army(ArmyState(999, None, ArmyType.BOWMEN, Quality.VETERAN, LOCATION))
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


def test_recruit_ignores_mercenary_below_average_quality():
    state = build_state()
    state.add_army(ArmyState(999, None, ArmyType.BOWMEN, Quality.GREEN, LOCATION))
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is False
    assert state.armies[999].kingdom_id is None  # untouched, still a mercenary
    assert len(state.armies) == 2  # a fresh army was levied instead


def test_recruit_ignores_unhireable_mercenary():
    state = build_state()
    mercenary = ArmyState(999, None, ArmyType.BOWMEN, Quality.VETERAN, LOCATION)
    mercenary.unhireable_this_turn = True
    state.add_army(mercenary)
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.recruited[0].hired is False
    assert state.armies[999].kingdom_id is None


def test_recruit_ignores_mercenary_of_a_different_type_or_location():
    state = build_state()
    state.add_army(ArmyState(998, None, ArmyType.AXEMEN, Quality.VETERAN, LOCATION))  # wrong type
    state.add_army(ArmyState(997, None, ArmyType.BOWMEN, Quality.VETERAN, HexCoord(0, 0)))  # wrong place
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
