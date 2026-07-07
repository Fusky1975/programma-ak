from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
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
    request = RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN])  # pay 2 + 1 ally fee

    result = execute_recruit(state, kingdom_id=1, leader_id=LEADER_ID, request=request)

    assert result.total_gold_spent == 3
    assert state.kingdoms[1].treasury == 97
    assert state.kingdoms[2].treasury == 1


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
