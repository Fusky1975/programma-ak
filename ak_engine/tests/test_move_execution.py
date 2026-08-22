from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.move_execution import (
    MARCH_ABILITY_BONUS,
    MARCH_MASTERY_ABILITY_BONUS,
    execute_move,
    march_movement_point_bonus,
    naval_movement_point_bonus,
    record_kingdom_exploration,
    reveal_adjacent_provinces,
)
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds

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


def test_uncontested_move_relocates_army_and_conquers_the_undefended_province():
    # Phase 410: TARGET is owned by kingdom 2 (an enemy) with no defenders
    # at all -- rulebook [7.7]'s own real uncontested-conquest case, which
    # now transfers ownership and costs the conquest's extra movement
    # point (1 base + 1 conquest = 2), not just an ordinary move.
    state = base_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.moved is True
    assert result.battle_report is None
    assert result.conquered is True
    assert state.provinces[TARGET].owner_kingdom_id == 1
    assert result.movement_points_spent == 2
    assert state.armies[101].location == TARGET
    assert state.armies[101].movement_points == 1


def test_uncontested_move_conquers_an_unowned_province_too():
    # [7.7]'s own real case covers "an enemy province", but this project's
    # own reading treats "unowned" the same way -- nobody already holds
    # it, so any army moving in unopposed takes it, matching the same
    # "own it the instant you're standing in it unopposed" principle a
    # battle-won conquest already implements.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = None

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.conquered is True
    assert state.provinces[TARGET].owner_kingdom_id == 1
    assert result.movement_points_spent == 2


def test_uncontested_move_does_not_conquer_allied_territory():
    state = base_state()
    state.allied_kingdoms.add(frozenset({1, 2}))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.conquered is False
    assert state.provinces[TARGET].owner_kingdom_id == 2
    assert result.movement_points_spent == 1


def test_leader_moving_alone_does_not_conquer():
    # A lone character brings no military unit -- [7.7]'s own framing
    # ("a military unit... enters an enemy province") never applies.
    state = base_state()
    state.add_leader(LeaderState(1, 1, "King", ORIGIN))

    result = execute_move(state, kingdom_id=1, army_ids=[], target=TARGET, leader_id=1)

    assert result.conquered is False
    assert state.provinces[TARGET].owner_kingdom_id == 2


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


def test_uncontested_move_exploration_honors_terrain_override():
    # Phase 168: a province Part Sea'd/Flooded to Sea (terrain_override) must
    # explore using Sea's own Basic Exploration Number (25), not the base
    # terrain's (Plains=50) -- effective_terrain() is the real current
    # terrain for every mechanics read, including this one.
    state = base_state()
    state.provinces[TARGET].terrain_override = Terrain.SEA

    result = execute_move(state, kingdom_id=1, army_ids=[101], explorer_skill=1, target=TARGET)

    # Sea basic exploration number 25, skill 1 -> full=50, halved (Move) = 25.
    assert result.exploration.new_percent == 25
    assert state.provinces[TARGET].explored_percent == 25


def test_execute_move_map_of_the_marauders_extends_partial_exploration_to_a_further_sea_hex():
    # Phase 541: AKGEN_reverse_engineering_report (4).md SS11 -- Map of the
    # Marauders' "+1 hex to sea vision" (a declared-original interpretation,
    # not reverse-engineered: this project has no hex-radius vision
    # concept for anything to hook a literal "+1 hex" into).
    state = base_state()
    further = HexCoord(3, 1)  # a further neighbor of TARGET, not ORIGIN
    state.provinces[TARGET].terrain_override = Terrain.SEA
    state.add_province(ProvinceState(further, Terrain.SEA, Race.HUMAN))
    state.add_leader(LeaderState(1, 1, "Marauder Captain", ORIGIN))
    state.add_item(Treasure.NAMED_UNIQUE_MAP_MARAUDERS, owner_leader_id=1)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, explorer_skill=1)

    assert state.provinces[TARGET].explored_percent_by_kingdom.get(1, 0) > 0
    assert state.provinces[further].explored_percent_by_kingdom.get(1, 0) > 0


def test_execute_move_without_the_map_does_not_extend_vision():
    # `further` is a real neighbor of TARGET, so Phase 623's own ordinary
    # adjacency-reveal still applies to it (a flat 1%, `KNOWN_PROVINCE_
    # MIN_PERCENT`) -- what this test actually checks is that the
    # *Marauders-specific* bonus (a much larger partial-exploration
    # percentage) doesn't also apply without the item.
    state = base_state()
    further = HexCoord(3, 1)
    state.provinces[TARGET].terrain_override = Terrain.SEA
    state.add_province(ProvinceState(further, Terrain.SEA, Race.HUMAN))
    state.add_leader(LeaderState(1, 1, "Ordinary Captain", ORIGIN))

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, explorer_skill=1)

    assert state.provinces[further].explored_percent_by_kingdom.get(1) == 1


def test_execute_move_map_of_the_marauders_does_nothing_on_land():
    # The bonus is sea-specific -- TARGET here stays its default Plains.
    # `further` still gets Phase 623's own ordinary adjacency-reveal
    # (flat 1%) from merely being TARGET's own real neighbor -- what
    # this test actually checks is that the item's own *extra* bonus
    # doesn't also apply on land.
    state = base_state()
    further = HexCoord(3, 1)
    state.add_province(ProvinceState(further, Terrain.SEA, Race.HUMAN))
    state.add_leader(LeaderState(1, 1, "Marauder Captain", ORIGIN))
    state.add_item(Treasure.NAMED_UNIQUE_MAP_MARAUDERS, owner_leader_id=1)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, explorer_skill=1)

    assert state.provinces[further].explored_percent_by_kingdom.get(1) == 1


def test_record_kingdom_exploration_seeds_from_that_kingdoms_own_prior_entry():
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2)
    province.explored_percent_by_kingdom[1] = 50  # kingdom 1 already at 50%

    exploration = record_kingdom_exploration(province, kingdom_id=1, explorer_skill=1, partial=True)

    # Plains=50, skill 1 -> 100, halved (partial) = 50 -> 50+50 = 100.
    assert exploration.new_percent == 100
    assert exploration.discovered_features == []
    assert province.explored_percent_by_kingdom[1] == 100
    # A different kingdom's own entry starts fresh from 0, independent of
    # kingdom 1's progress.
    other = record_kingdom_exploration(province, kingdom_id=2, explorer_skill=1, partial=True)
    assert other.new_percent == 50
    assert province.explored_percent_by_kingdom == {1: 100, 2: 50}


# -- Phase 623: reveal_adjacent_provinces() ("known provinces") -------------


def test_reveal_adjacent_provinces_sets_a_previously_unknown_neighbor_to_the_floor():
    state = base_state()
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)

    reveal_adjacent_provinces(state, state.provinces[TARGET], kingdom_id=1, bounds=bounds)

    assert state.provinces[DEFENDER_HOME].explored_percent_by_kingdom.get(1) == 1


def test_reveal_adjacent_provinces_never_lowers_an_already_better_known_neighbor():
    state = base_state()
    state.provinces[DEFENDER_HOME].explored_percent_by_kingdom[1] = 50
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)

    reveal_adjacent_provinces(state, state.provinces[TARGET], kingdom_id=1, bounds=bounds)

    assert state.provinces[DEFENDER_HOME].explored_percent_by_kingdom[1] == 50


def test_reveal_adjacent_provinces_skips_neighbors_with_no_real_province_data():
    state = base_state()
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    # No error even though most of TARGET's own geometric neighbors have
    # no ProvinceState entry at all in this small test world.

    reveal_adjacent_provinces(state, state.provinces[TARGET], kingdom_id=1, bounds=bounds)


def test_execute_move_reveals_a_real_neighbor_of_the_destination():
    state = base_state()
    state.add_leader(LeaderState(1, 1, "Scout", ORIGIN))

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, explorer_skill=1)

    # The entered province itself is known via the pre-existing partial-
    # exploration formula (always well above the floor for real terrain
    # numbers), and DEFENDER_HOME -- never entered, only adjacent to
    # TARGET -- is known too, via the new adjacency-reveal floor.
    assert state.provinces[TARGET].explored_percent_by_kingdom[1] > 1
    assert state.provinces[DEFENDER_HOME].explored_percent_by_kingdom.get(1) == 1


def test_record_kingdom_exploration_without_state_skips_discovery():
    # Phase 242: state=None (the default) is the pre-Phase-242 behavior --
    # no discovery roll at all, even if a feature happens to be present.
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2)
    record_kingdom_exploration(province, kingdom_id=1, explorer_skill=9, partial=False)
    # No assertion possible against a feature since none was ever created --
    # this just confirms the call succeeds without a state argument.


def test_record_kingdom_exploration_with_state_rolls_discovery():
    state = GameState()
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2)
    state.provinces[TARGET] = province
    feature = Feature(feature_id=1, coord=TARGET, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)

    # Plains=50, skill 9 -> 50*10=500 capped at 100 -> guaranteed discovery.
    exploration = record_kingdom_exploration(
        province, kingdom_id=1, explorer_skill=9, partial=False, state=state, rng=ScriptedRandom([0.99])
    )

    assert feature.discovery_level(1) == 3
    assert exploration.discovered_features == [feature]


# -- Phase 509: Find Mines wiring in record_kingdom_exploration --


def test_record_kingdom_exploration_find_mines_success_adds_gold_and_increments_attempts():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    province = ProvinceState(TARGET, Terrain.MTNS, Race.HUMAN, owner_kingdom_id=1)
    state.provinces[TARGET] = province

    record_kingdom_exploration(
        province,
        kingdom_id=1,
        explorer_skill=1,
        partial=False,
        state=state,
        rng=ScriptedRandom([0.0, 0.5]),
        has_find_mines=True,
    )

    assert province.mine_find_attempts == 1
    assert 1 <= province.mine_gold_bonus <= 3


def test_record_kingdom_exploration_find_mines_skipped_on_enemy_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 0)))
    province = ProvinceState(TARGET, Terrain.MTNS, Race.HUMAN, owner_kingdom_id=2)
    state.provinces[TARGET] = province

    record_kingdom_exploration(
        province,
        kingdom_id=1,
        explorer_skill=1,
        partial=False,
        state=state,
        rng=ScriptedRandom([0.0]),
        has_find_mines=True,
    )

    assert province.mine_find_attempts == 0
    assert province.mine_gold_bonus == 0


def test_record_kingdom_exploration_find_mines_allowed_on_neutral_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    province = ProvinceState(TARGET, Terrain.MTNS, Race.HUMAN, owner_kingdom_id=None)
    state.provinces[TARGET] = province

    record_kingdom_exploration(
        province,
        kingdom_id=1,
        explorer_skill=1,
        partial=False,
        state=state,
        rng=ScriptedRandom([0.0, 0.5]),
        has_find_mines=True,
    )

    assert province.mine_find_attempts == 1
    assert province.mine_gold_bonus >= 1


def test_record_kingdom_exploration_find_mines_disabled_by_default():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    province = ProvinceState(TARGET, Terrain.MTNS, Race.HUMAN, owner_kingdom_id=1)
    state.provinces[TARGET] = province

    record_kingdom_exploration(
        province, kingdom_id=1, explorer_skill=1, partial=False, state=state, rng=ScriptedRandom([0.0])
    )

    assert province.mine_find_attempts == 0
    assert province.mine_gold_bonus == 0


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
    # Phase 296: leading 0.9 accounts for the new terrain-line-length-cap
    # roll -- see that fixture's own Phase 296 note.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

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


def test_move_conquest_sea_surcharge_honors_terrain_override():
    # Phase 168: a province Part Sea'd to Sea (terrain_override) must incur
    # the sea-battle movement surcharge on conquest, even though its base
    # terrain is still Plains -- effective_terrain() is what movement_cost
    # actually reads now.
    state = base_state()
    state.provinces[TARGET].terrain_override = Terrain.SEA
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE
    # Phase 296: leading 0.9 accounts for the new terrain-line-length-cap
    # roll -- see no_luck_overwhelming_attacker_rng()'s own Phase 296 note.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.battle_report.conquered is True
    # 1 base + 1 conquest + 1 sea-battle surcharge = 3 (vs. 2 without override).
    assert result.movement_points_spent == 3
    assert state.armies[101].movement_points == 0


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
    # Phase 296: leading 0.9 accounts for the new terrain-line-length-cap
    # roll -- see no_luck_overwhelming_attacker_rng()'s own Phase 296 note.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.99, 0.99, 0.99, 0.99])

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

    # HexCoord(1, 2) is a real neighbor of ORIGIN (adjacent, not a chase
    # target) with no province data of its own in base_state().
    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[101], target=HexCoord(1, 2))


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


# --- Phase 85: non-adjacent Move chase (rulebook [3.1]) -----------------

# CHASE_ORIGIN's own closest neighbor toward FAR_TARGET is uniquely
# INTERMEDIATE (verified via turn/movement.py step_toward_non_adjacent_target
# directly); INTERMEDIATE is itself adjacent to FAR_TARGET, so a second hop
# from there reaches it. Distinct terrain from FAR_TARGET so exploration
# tests can tell which province was actually explored.
# Phase 314: INTERMEDIATE moved from (1,2) to (0,2) -- neighbors()'s own
# real-data-sourced parity fix (see turn/movement.py's docstring) changed
# which of CHASE_ORIGIN's neighbors is closest to FAR_TARGET.
CHASE_ORIGIN = HexCoord(1, 1)
INTERMEDIATE = HexCoord(0, 2)
FAR_TARGET = HexCoord(0, 3)


def chase_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(CHASE_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(INTERMEDIATE, Terrain.FOREST, Race.HUMAN, explored_percent=0))
    state.add_province(ProvinceState(FAR_TARGET, Terrain.PLAINS, Race.HUMAN, explored_percent=0))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, CHASE_ORIGIN, movement_points=3))
    return state


def test_chase_step_lands_on_intermediate_hex_not_final_target():
    state = chase_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=FAR_TARGET)

    assert result.moved is True
    assert result.new_location == INTERMEDIATE
    assert state.armies[101].location == INTERMEDIATE
    assert result.reached_target is False


def test_chase_step_resolves_exploration_against_the_intermediate_hex():
    state = chase_state()

    execute_move(state, kingdom_id=1, army_ids=[101], explorer_skill=1, target=FAR_TARGET)

    # INTERMEDIATE (Forest, basic exploration number 15) actually explored...
    assert state.provinces[INTERMEDIATE].explored_percent > 0
    # ...FAR_TARGET (the ultimate, not-yet-reached target) is untouched.
    assert state.provinces[FAR_TARGET].explored_percent == 0


def test_second_chase_step_reaches_the_target():
    state = chase_state()
    state.armies[101].location = INTERMEDIATE

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=FAR_TARGET)

    assert result.moved is True
    assert result.new_location == FAR_TARGET
    assert result.reached_target is True


def test_stopped_chasing_when_no_closer_neighbor_exists():
    # Mirrors turn/movement.py's own "stop chasing" test case: from (0,0),
    # every reachable neighbor is farther from (-5,-5) than (0,0) itself.
    state = GameState()
    origin = HexCoord(0, 0)
    unreachable_target = HexCoord(-5, -5)
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, origin))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, origin, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=unreachable_target)

    assert result.stopped_chasing is True
    assert result.moved is False
    assert result.exploration is None
    assert result.new_location is None
    assert state.armies[101].location == origin
    assert state.armies[101].movement_points == 3


def test_chase_step_breaks_ties_by_ownership_tier():
    # Mirrors turn/movement.py's own tie-break test case: from (5,5) toward
    # (5,0), (4,4) and (5,4) tie as the two strictly-closer candidates.
    state = GameState()
    origin = HexCoord(5, 5)
    target = HexCoord(5, 0)
    owned_candidate = HexCoord(4, 4)
    enemy_candidate = HexCoord(5, 4)
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, origin))
    state.add_kingdom(KingdomState(2, "Enemia", Race.HUMAN, Alignment.EVIL, enemy_candidate))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(owned_candidate, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(enemy_candidate, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, origin, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=target)

    assert result.new_location == owned_candidate


def test_chase_step_triggers_battle_on_an_enemy_occupied_intermediate_hex():
    state = chase_state()
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.EVIL, INTERMEDIATE))
    state.provinces[INTERMEDIATE].owner_kingdom_id = 2
    state.add_army(ArmyState(201, 2, ArmyType.AXEMEN, Quality.AVERAGE, INTERMEDIATE, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=FAR_TARGET, rng=ScriptedRandom([0.9] * 20))

    assert result.battle_report is not None


# -- Phase 521: March category (Cavalry/Infantry + Mastery tiers) --------


def test_march_movement_point_bonus_cavalry_at_the_minimum_band():
    assert march_movement_point_bonus(3, has_march_cavalry=True) == MARCH_ABILITY_BONUS


def test_march_movement_point_bonus_cavalry_below_the_band_is_zero():
    assert march_movement_point_bonus(2, has_march_cavalry=True) == 0


def test_march_movement_point_bonus_cavalry_mastery_is_the_total_not_additive():
    assert march_movement_point_bonus(3, has_march_cavalry_mastery=True) == MARCH_MASTERY_ABILITY_BONUS


def test_march_movement_point_bonus_infantry_band():
    assert march_movement_point_bonus(1, has_march_infantry=True) == MARCH_ABILITY_BONUS
    assert march_movement_point_bonus(2, has_march_infantry=True) == MARCH_ABILITY_BONUS


def test_march_movement_point_bonus_infantry_outside_the_band_is_zero():
    assert march_movement_point_bonus(0, has_march_infantry=True) == 0
    assert march_movement_point_bonus(3, has_march_infantry=True) == 0


def test_march_movement_point_bonus_infantry_mastery_is_the_total_not_additive():
    assert march_movement_point_bonus(2, has_march_infantry_mastery=True) == MARCH_MASTERY_ABILITY_BONUS


def test_march_movement_point_bonus_returns_0_without_any_ability():
    assert march_movement_point_bonus(3) == 0
    assert march_movement_point_bonus(1) == 0


def test_execute_move_grants_march_cavalry_bonus_before_deducting_cost():
    # Target already owned by the same kingdom -- no battle, no conquest,
    # so cost is the flat base (1). Army starts at 3 movement points
    # (Cavalry's own qualifying band), gets +1, then pays the move's own
    # cost of 1 -- net 3, not 2.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_cavalry=True)

    assert state.armies[101].movement_points == 3
    assert state.armies[101].march_bonus_applied_this_turn is True


def test_execute_move_does_not_regrant_march_bonus_within_the_same_turn():
    # Two Move orders in the same gameturn (there back to ORIGIN) --
    # the bonus is only ever granted once, on the first one.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101].movement_points = 5

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_cavalry=True)
    after_first_move = state.armies[101].movement_points
    execute_move(state, kingdom_id=1, army_ids=[101], target=ORIGIN, has_march_cavalry=True)

    # Second move only pays its own cost (1) -- no second +1 bonus.
    assert state.armies[101].movement_points == after_first_move - 1


def test_execute_move_gives_no_march_bonus_to_a_sea_army_type():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_cavalry=True)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].march_bonus_applied_this_turn is False


def test_execute_move_gives_no_march_bonus_without_the_ability():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].march_bonus_applied_this_turn is False


# -- Phase 523: Naval movement bonus (Whale League/Fleet/Mermen) --


def test_naval_movement_point_bonus_equals_the_skill_level():
    assert naval_movement_point_bonus(0) == 0
    assert naval_movement_point_bonus(1) == 1
    assert naval_movement_point_bonus(4) == 4
    assert naval_movement_point_bonus(9) == 9  # uncapped, unlike the battle-strength bonus


def test_naval_movement_point_bonus_clamps_negative_input_to_zero():
    assert naval_movement_point_bonus(-3) == 0


def test_execute_move_grants_naval_bonus_before_deducting_cost():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=2)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, naval_skill_level=3)

    # 2 (start) + 3 (bonus) - 1 (cost) == 4
    assert state.armies[101].movement_points == 4
    assert state.armies[101].naval_bonus_applied_this_turn is True


def test_execute_move_does_not_regrant_naval_bonus_within_the_same_turn():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=5)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, naval_skill_level=3)
    after_first_move = state.armies[101].movement_points
    execute_move(state, kingdom_id=1, army_ids=[101], target=ORIGIN, naval_skill_level=3)

    assert state.armies[101].movement_points == after_first_move - 1


def test_execute_move_gives_no_naval_bonus_to_a_land_army_type():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, naval_skill_level=3)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].naval_bonus_applied_this_turn is False


def test_execute_move_gives_no_naval_or_march_bonus_to_an_air_unit():
    # Phase 523 correction: Dragon Wing/Eagle Wing get a flat 0 from
    # either ability -- confirmed by the dossier's own compiled
    # MovementBonus dispatcher.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_cavalry=True, naval_skill_level=3)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].march_bonus_applied_this_turn is False
    assert state.armies[101].naval_bonus_applied_this_turn is False


def test_execute_move_gives_no_naval_bonus_without_skill():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].naval_bonus_applied_this_turn is False


# -- Phase 524: Naval Hug Coastline --

HUG_ORIGIN = HexCoord(1, 1)
HUG_SEA = HexCoord(1, 0)  # shared coastal neighbor of HUG_ORIGIN and HUG_TARGET
HUG_TARGET = HexCoord(2, 0)  # not adjacent to HUG_ORIGIN


def _hug_state(*, sea_terrain: bool = True) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Coastia", Race.HUMAN, Alignment.GOOD, HUG_ORIGIN))
    state.add_province(ProvinceState(HUG_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HUG_SEA, Terrain.SEA if sea_terrain else Terrain.PLAINS, Race.HUMAN))
    state.add_province(ProvinceState(HUG_TARGET, Terrain.PLAINS, Race.HUMAN))
    # Every other neighbor of HUG_ORIGIN needs real province data too, since
    # a withheld shortcut falls back to the ordinary chase step, which may
    # pick any of them as its own intermediate hex.
    for coord in (HexCoord(2, 1), HexCoord(1, 2), HexCoord(0, 2), HexCoord(0, 1), HexCoord(0, 0)):
        state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    return state


def test_execute_move_naval_hug_coastline_moves_directly_between_coastal_land_hexes():
    state = _hug_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=HUG_TARGET, has_naval_hug_coastline=True)

    assert result.moved is True
    assert result.reached_target is True
    assert state.armies[101].location == HUG_TARGET


def test_execute_move_without_the_ability_does_not_grant_the_coastal_shortcut():
    state = _hug_state()

    execute_move(state, kingdom_id=1, army_ids=[101], target=HUG_TARGET)

    assert state.armies[101].location != HUG_TARGET  # only a chase step, not a direct hop


def test_execute_move_naval_hug_coastline_withheld_when_no_shared_hex_is_actually_sea():
    state = _hug_state(sea_terrain=False)

    execute_move(state, kingdom_id=1, army_ids=[101], target=HUG_TARGET, has_naval_hug_coastline=True)

    assert state.armies[101].location != HUG_TARGET


def test_execute_move_naval_hug_coastline_withheld_when_a_sea_unit_travels_in_the_stack():
    # This project has no Fleet cargo-capacity model, so the shortcut is
    # conservatively withheld whenever a sea-going unit accompanies the
    # stack -- see _naval_hug_coastline_move_is_legal()'s own docstring.
    state = _hug_state()
    state.add_army(ArmyState(102, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    execute_move(state, kingdom_id=1, army_ids=[101, 102], target=HUG_TARGET, has_naval_hug_coastline=True)

    assert state.armies[101].location != HUG_TARGET
