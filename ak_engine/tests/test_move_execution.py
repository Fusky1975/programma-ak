from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.move_execution import execute_move, record_kingdom_exploration

from _helpers import ScriptedRandom

ORIGIN = HexCoord(1, 1)
TARGET = HexCoord(2, 1)  # adjacent to ORIGIN on the odd-r grid
DEFENDER_HOME = HexCoord(2, 0)  # adjacent to TARGET, for defender retreat


def base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, DEFENDER_HOME))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, explored_percent=0))
    state.add_province(ProvinceState(DEFENDER_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))
    return state


def test_uncontested_move_relocates_army_and_spends_one_point():
    state = base_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.moved is True
    assert result.battle_report is None
    assert result.movement_points_spent == 1
    assert state.armies[101].location == TARGET
    assert state.armies[101].movement_points == 2


def test_uncontested_move_applies_partial_exploration():
    state = base_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], explorer_skill=1, target=TARGET)

    # Plains basic exploration number 50, skill 1 -> full=100, halved (Move) = 50.
    assert result.exploration.new_percent == 50
    assert state.provinces[TARGET].explored_percent == 50


def test_uncontested_move_also_records_the_movers_own_kingdom_exploration():
    # Phase 69: alongside the pre-existing shared explored_percent scalar,
    # the mover's own kingdom_id gets its own independent entry.
    state = base_state()

    execute_move(state, kingdom_id=1, army_ids=[101], explorer_skill=1, target=TARGET)

    assert state.provinces[TARGET].explored_percent_by_kingdom[1] == 50
    assert 2 not in state.provinces[TARGET].explored_percent_by_kingdom


def test_record_kingdom_exploration_seeds_from_that_kingdoms_own_prior_entry():
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2)
    province.explored_percent_by_kingdom[1] = 50  # kingdom 1 already at 50%

    new_percent = record_kingdom_exploration(province, kingdom_id=1, explorer_skill=1, partial=True)

    # Plains=50, skill 1 -> 100, halved (partial) = 50 -> 50+50 = 100.
    assert new_percent == 100
    assert province.explored_percent_by_kingdom[1] == 100
    # A different kingdom's own entry starts fresh from 0, independent of
    # kingdom 1's progress.
    other_percent = record_kingdom_exploration(province, kingdom_id=2, explorer_skill=1, partial=True)
    assert other_percent == 50
    assert province.explored_percent_by_kingdom == {1: 100, 2: 50}


def test_move_into_allied_territory_is_uncontested():
    state = base_state()
    state.add_army(ArmyState(201, 2, ArmyType.AXEMEN, Quality.AVERAGE, TARGET))
    state.allied_kingdoms.add(frozenset({1, 2}))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.battle_report is None
    assert state.armies[101].location == TARGET


def test_move_into_province_with_only_a_mercenary_band_is_uncontested():
    # A masterless mercenary isn't "an enemy" by default -- moving into a
    # province it occupies shouldn't force a battle.
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, TARGET))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.battle_report is None
    assert result.moved is True
    assert state.armies[101].location == TARGET
    assert state.armies[301].kingdom_id is None  # untouched


def test_move_triggers_battle_and_conquest_relocates_the_attacker():
    state = base_state()
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE
    # no luck for either side, decisive attacker win, no quality changes.
    # The 5th value (0.99) is the defender-clean-swept pursuit-attempt
    # roll -- >= the 75% cavalry chance, so the sole winning HVY_CAVALRY
    # unit declines to pursue and the retreating defender proceeds
    # unchanged (see test_battle_orchestrator.py's
    # no_luck_overwhelming_attacker_rng for the same pattern).
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.battle_report is not None
    assert result.battle_report.conquered is True
    assert result.moved is True
    assert result.new_location == TARGET
    assert state.armies[101].location == TARGET
    assert state.provinces[TARGET].owner_kingdom_id == 1
    # 1 base + 1 conquest = 2
    assert result.movement_points_spent == 2
    assert state.armies[101].movement_points == 1
    assert 201 in result.battle_report.retreated_army_ids
    assert state.armies[201].location == DEFENDER_HOME


def test_move_that_fails_to_conquer_leaves_attacker_at_origin():
    state = base_state()
    state.add_army(ArmyState(201, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET))
    # attacker is the weak BOWMEN/AVERAGE army from base_state(); force a
    # defender win with no luck events -- a clean sweep, so the attacker
    # retreats. The 5th value (0.99) is the attacker-clean-swept
    # pursuit-attempt roll -- >= the 75% cavalry chance, so the sole
    # winning HVY_CAVALRY (defender) unit declines to pursue and the
    # retreating attacker proceeds unchanged; the 6th is that retreat's
    # own quality-change roll; the 7th is the defender's own
    # winner_quality_roll.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.99, 0.99, 0.99, 0.99])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.moved is False
    assert result.new_location is None
    assert state.armies[101].location == ORIGIN
    # attacker wasn't clean-swept destroyer's info aside, no conquest -> cost 1
    assert result.movement_points_spent == 1


def test_raises_without_movement_points():
    state = base_state()
    state.armies[101].movement_points = 0

    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)


def test_raises_when_armies_do_not_share_origin():
    state = base_state()
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, DEFENDER_HOME, movement_points=3))

    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[101, 102], target=TARGET)


def test_raises_for_unknown_target_province():
    state = base_state()

    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[101], target=HexCoord(20, 10))


def test_leader_can_move_alone_and_relocates():
    state = base_state()
    state.add_leader(LeaderState(1, 1, "King", ORIGIN))

    result = execute_move(state, kingdom_id=1, army_ids=[], target=TARGET, leader_id=1)

    assert result.moved is True
    assert state.leaders[1].location == TARGET
    assert state.armies[101].location == ORIGIN  # not brought along, unaffected


def test_raises_with_no_armies_and_no_leader():
    state = base_state()

    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[], target=TARGET)


# --- Contested-province move validation (Phase 36, rulebook [7.6]) ------


def test_raises_moving_from_a_province_the_mover_is_contesting_to_an_enemy_province():
    state = base_state()
    state.provinces[ORIGIN].contested_by_kingdom_id = 1  # kingdom 1 is the mover

    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)  # TARGET is enemy-owned (kingdom 2)


def test_allowed_from_a_contested_province_to_a_non_enemy_province():
    state = base_state()
    state.provinces[ORIGIN].contested_by_kingdom_id = 1
    state.provinces[TARGET].owner_kingdom_id = 1  # the mover's own province, not an enemy's

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.moved is True
    assert state.armies[101].location == TARGET


def test_allowed_when_the_origin_is_contested_by_a_different_kingdom():
    # Only "the leader who invaded" is restricted -- a province contested
    # by someone else's ongoing invasion doesn't limit this mover.
    state = base_state()
    state.provinces[ORIGIN].contested_by_kingdom_id = 2

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.moved is True
    assert state.armies[101].location == TARGET


def test_allowed_from_a_merely_neutral_owned_province_to_an_enemy_province():
    # "You can, however, move from a province owned by a neutral
    # player-King to an enemy province" -- ORIGIN is owned by the mover's
    # own kingdom and isn't contested at all, so this is ordinary movement.
    state = base_state()
    assert state.provinces[ORIGIN].contested_by_kingdom_id is None

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.moved is True
    assert state.armies[101].location == TARGET
