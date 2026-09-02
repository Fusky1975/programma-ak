from __future__ import annotations

from unittest.mock import patch

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
from ak_engine.turn.contested_province import IllegalMoveFromContestedError
from ak_engine.turn.move_execution import (
    MARCH_ABILITY_BONUS,
    MARCH_MASTERY_ABILITY_BONUS,
    execute_move,
    is_flooded_province,
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


# -- Phase 630: record_kingdom_exploration()'s new leader_id -- the 6
# terrain-King royal-title MeritTally counters --------------------------


def test_record_kingdom_exploration_credits_the_matching_terrain_king_title():
    state = GameState()
    state.add_leader(LeaderState(1, 1, "Scout", TARGET))
    terrain_fields = (
        (Terrain.PLAINS, "plains_explorations"),
        (Terrain.DESERT, "desert_explorations"),
        (Terrain.JUNGLE, "jungle_explorations"),
        (Terrain.FOREST, "forest_explorations"),
        (Terrain.MTNS, "mountain_explorations"),
        (Terrain.SEA, "sea_explorations"),
    )
    for terrain, field in terrain_fields:
        province = ProvinceState(TARGET, terrain, Race.HUMAN, owner_kingdom_id=None)
        record_kingdom_exploration(province, kingdom_id=1, explorer_skill=1, partial=True, state=state, leader_id=1)
        assert getattr(state.leaders[1].merit_tally, field) == 1, field


def test_record_kingdom_exploration_without_leader_id_credits_no_title_merit():
    # None (every pre-Phase-630 caller) leaves prior behavior unchanged.
    state = GameState()
    state.add_leader(LeaderState(1, 1, "Scout", TARGET))
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)

    record_kingdom_exploration(province, kingdom_id=1, explorer_skill=1, partial=True, state=state)

    assert state.leaders[1].merit_tally.plains_explorations == 0


# -- Phase 660: record_kingdom_exploration()'s new terrain-King title
# doubling (the same titles' own real "effect_while_held" bonus) --------


def test_record_kingdom_exploration_doubles_the_rate_for_the_titles_current_holder():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Rangeria", Race.HUMAN, Alignment.NEUTRAL, TARGET))
    state.add_leader(LeaderState(1, 1, "Ranger", TARGET))
    state.leaders[1].merit_tally.plains_explorations = 4  # OFFICE_MIN_POINTS[PLAINS_KING]
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)

    result = record_kingdom_exploration(province, kingdom_id=1, explorer_skill=0, partial=False, state=state, leader_id=1)

    # Plains basic=50, skill 0 -> 50 undoubled; 100 with the title.
    assert result.new_percent == 100


def test_record_kingdom_exploration_does_not_double_for_a_non_holder():
    state = GameState()
    state.add_leader(LeaderState(1, 1, "Scout", TARGET))  # merit stays 0, below OFFICE_MIN_POINTS
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)

    result = record_kingdom_exploration(province, kingdom_id=1, explorer_skill=0, partial=False, state=state, leader_id=1)

    assert result.new_percent == 50


def test_record_kingdom_exploration_title_bonus_is_terrain_specific():
    # Holds Plains King, but this exploration is in Desert -- no bonus.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Rangeria", Race.HUMAN, Alignment.NEUTRAL, TARGET))
    state.add_leader(LeaderState(1, 1, "Ranger", TARGET))
    state.leaders[1].merit_tally.plains_explorations = 4
    province = ProvinceState(TARGET, Terrain.DESERT, Race.HUMAN, owner_kingdom_id=None)

    result = record_kingdom_exploration(province, kingdom_id=1, explorer_skill=0, partial=False, state=state, leader_id=1)

    assert result.new_percent == 25  # Desert basic=25, undoubled


def test_record_kingdom_exploration_without_state_or_leader_id_never_doubles():
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)
    result = record_kingdom_exploration(province, kingdom_id=1, explorer_skill=0, partial=False)
    assert result.new_percent == 50


def test_execute_move_credits_the_movers_own_terrain_king_title():
    state = base_state()
    state.add_leader(LeaderState(1, 1, "Scout", ORIGIN))
    state.provinces[TARGET].terrain = Terrain.PLAINS

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, explorer_skill=1)

    assert state.leaders[1].merit_tally.plains_explorations == 1


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


# -- Phase 634: MoveExecutionResult.wind_walking (Mystic Winds) ------------


def test_execute_move_wind_walking_true_when_movers_leader_is_under_mystic_winds():
    state = base_state()
    state.add_leader(LeaderState(1, 1, "Mage", ORIGIN))
    state.leaders[1].mystic_winds_active = True

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1)

    assert result.wind_walking is True


def test_execute_move_wind_walking_false_without_mystic_winds():
    state = base_state()
    state.add_leader(LeaderState(1, 1, "Mage", ORIGIN))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1)

    assert result.wind_walking is False


def test_execute_move_wind_walking_survives_a_battle_the_same_move_triggers():
    # Mirrors test_move_triggers_battle_and_conquest_relocates_the_attacker's
    # own scenario exactly, but the mover's own leader is under Mystic
    # Winds -- fight_battle() (called from inside this same execute_move()
    # call) clears LeaderState.mystic_winds_active once the battle
    # resolves, so if the flag were read *after* that call instead of
    # snapshotted before it, this would wrongly come back False.
    state = base_state()
    state.add_leader(LeaderState(1, 1, "Mage", ORIGIN))
    state.leaders[1].mystic_winds_active = True
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE
    state.armies[101].commanded_by = 1  # so fight_battle() sees leader 1 as genuinely involved
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99, 0.99])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, rng=rng)

    assert result.battle_report is not None
    assert result.wind_walking is True
    assert state.leaders[1].mystic_winds_active is False  # cleared by the battle, as expected
    assert result.new_location == TARGET
    assert state.armies[101].location == TARGET
    assert state.provinces[TARGET].owner_kingdom_id == 1
    # 1 base + 1 conquest = 2
    assert result.movement_points_spent == 2
    assert state.armies[101].movement_points == 1
    assert 201 in result.battle_report.retreated_army_ids
    assert state.armies[201].location == DEFENDER_HOME


def test_execute_move_wires_battle_carrier_destruction():
    # Phase 716: same real-battle fixture shape as the wind_walking test
    # right above -- proves execute_move()'s own real battle trigger
    # reaches turn/sea_transport.py apply_battle_carrier_destruction()
    # with the battle report's own real destroyed/disbanded/pursuit-
    # destroyed lists, mirroring the established "mock the shared
    # function, assert the call" convention (Phase 686).
    state = base_state()
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99, 0.99])

    with patch("ak_engine.turn.move_execution.apply_battle_carrier_destruction") as mock_cascade:
        result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.battle_report is not None
    mock_cascade.assert_called_once_with(
        state,
        result.battle_report.destroyed_army_ids,
        result.battle_report.disbanded_army_ids,
        result.battle_report.pursuit_destroyed_army_ids,
    )


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

    # Phase 718: a dedicated IllegalMoveFromContestedError, not a bare
    # ValueError -- distinguishes this real, narrated scenario from
    # this same function's own unrelated "no province data" ValueError.
    with pytest.raises(IllegalMoveFromContestedError):
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


# -- Phase 651: Illusory Fog's own movement surcharge --


def test_execute_move_deducts_illusory_fog_surcharge_for_air_unit_entering_fogged_province():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1  # no battle/conquest -- base cost stays 1
    state.provinces[TARGET].illusory_fog_active = True
    state.armies[101] = ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 1  # 3 - base(1) - fog(1)


def test_execute_move_deducts_illusory_fog_surcharge_for_air_unit_leaving_fogged_province():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.provinces[ORIGIN].illusory_fog_active = True  # fogged at the origin, not the destination
    state.armies[101] = ArmyState(101, 1, ArmyType.EAGLE_WING, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 1


def test_execute_move_no_illusory_fog_surcharge_for_an_ordinary_land_unit():
    # Non-regression/control: a non-air, non-Mystic-Winds unit is
    # entirely unaffected even when the destination is fogged.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.provinces[TARGET].illusory_fog_active = True

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 2  # 3 - base(1) only


def test_execute_move_illusory_fog_surcharge_applies_to_mystic_winds_affected_land_unit():
    # "All air units (Dragon Wings, Eagle Wings and those affected by
    # 'Mystic Winds' Spell)" -- an ordinary land army still pays the
    # surcharge if its own commander is currently under Mystic Winds.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.provinces[TARGET].illusory_fog_active = True
    state.armies[101].commanded_by = 1
    state.add_leader(LeaderState(1, kingdom_id=1, name="Windwalker", location=ORIGIN, mystic_winds_active=True))

    execute_move(state, kingdom_id=1, army_ids=[101], leader_id=1, target=TARGET)

    assert state.armies[101].movement_points == 1


def test_execute_move_no_illusory_fog_surcharge_when_neither_province_is_fogged():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 2


# -- Phase 693: AdvancedAbility.MARCH_THROUGH_FLOODS --


def test_is_flooded_province_true_only_for_a_flood_terrain_override():
    flooded = ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA)
    assert is_flooded_province(flooded) is True

    naturally_sea = ProvinceState(ORIGIN, Terrain.SEA, Race.HUMAN)
    assert is_flooded_province(naturally_sea) is False

    part_sea_reverted = ProvinceState(ORIGIN, Terrain.SEA, Race.HUMAN, terrain_override=Terrain.PLAINS)
    assert is_flooded_province(part_sea_reverted) is False

    untouched = ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN)
    assert is_flooded_province(untouched) is False


def test_execute_move_deducts_march_through_floods_surcharge_for_land_unit_entering_flooded_province():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1  # no battle/conquest -- base cost stays 1
    state.provinces[TARGET].terrain_override = Terrain.SEA

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_through_floods=True)

    assert state.armies[101].movement_points == 1  # 3 - base(1) - flood(1)


def test_execute_move_deducts_march_through_floods_surcharge_for_land_unit_leaving_flooded_province():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.provinces[ORIGIN].terrain_override = Terrain.SEA  # flooded at the origin, not the destination

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_through_floods=True)

    assert state.armies[101].movement_points == 1


def test_execute_move_no_march_through_floods_surcharge_without_the_ability():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.provinces[TARGET].terrain_override = Terrain.SEA

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 2  # 3 - base(1) only


def test_execute_move_no_march_through_floods_surcharge_for_a_sea_going_army():
    # The ability's own scope is land armies "entering or leaving" a
    # flooded province -- a naturally sea-going type has no reason to
    # need pontoon bridges/ferries at all.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.provinces[TARGET].terrain_override = Terrain.SEA
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_through_floods=True)

    assert state.armies[101].movement_points == 2


def test_execute_move_no_march_through_floods_surcharge_when_neither_province_is_flooded():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_through_floods=True)

    assert state.armies[101].movement_points == 2


def test_execute_move_no_march_through_floods_surcharge_for_a_naturally_sea_province():
    # A province that's naturally Sea (no Flood ever cast on it) doesn't
    # trigger the surcharge even with the ability -- is_flooded_province()
    # is False for it, matching this ability's own real "affected by the
    # Flood spell" scope, not "any Sea terrain."
    state = base_state()
    state.provinces[TARGET] = ProvinceState(TARGET, Terrain.SEA, Race.HUMAN, owner_kingdom_id=1)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_through_floods=True)

    assert state.armies[101].movement_points == 2


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
    # Phase 720: no longer "no Fleet cargo-capacity model" (Phase 714
    # built one) -- this call simply never requests auto_board, so the
    # Bowmen is never actually boarded, correctly reproducing the same
    # conservative denial for a mixed stack with no boarding attempted.
    state = _hug_state()
    state.add_army(ArmyState(102, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    execute_move(state, kingdom_id=1, army_ids=[101, 102], target=HUG_TARGET, has_naval_hug_coastline=True)

    assert state.armies[101].location != HUG_TARGET


def test_execute_move_naval_hug_coastline_grants_the_hop_when_the_fleet_can_carry_every_land_army():
    # Phase 720: SS106's own capacity-allocation rule, all-or-nothing --
    # the Bowmen (speed 2, infantry-eligible) fully boards the Fleet
    # (FLEET_INFANTRY_CAPACITY=2), so the whole group hops together.
    state = _hug_state()
    state.add_army(ArmyState(102, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    execute_move(state, kingdom_id=1, army_ids=[101, 102], target=HUG_TARGET, has_naval_hug_coastline=True, auto_board=True)

    assert state.armies[101].location == HUG_TARGET
    assert state.armies[102].location == HUG_TARGET
    assert state.armies[101].transported_by == 102


def test_execute_move_naval_hug_coastline_still_withheld_when_the_fleet_cannot_carry_every_land_army():
    # 3 Bowmen exceed FLEET_INFANTRY_CAPACITY=2 -- 2 board, 1 doesn't --
    # the all-or-nothing rule denies the shortcut to the entire group,
    # including the 2 that did board.
    state = _hug_state()
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(104, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    execute_move(
        state, kingdom_id=1, army_ids=[101, 102, 103, 104], target=HUG_TARGET, has_naval_hug_coastline=True, auto_board=True
    )

    assert state.armies[101].location != HUG_TARGET
    assert state.armies[102].location != HUG_TARGET
    assert state.armies[103].location != HUG_TARGET
    assert state.armies[104].location != HUG_TARGET


# -- Phase 715: Fleet/Whale cargo-capacity subsystem, Phase B -- auto_board --


def _transport_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Coastia", Race.HUMAN, Alignment.GOOD, ORIGIN))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    return state


def test_execute_move_auto_board_false_by_default_never_boards():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102], target=TARGET)

    assert result.boarded_army_ids == []
    assert state.armies[102].transported_by is None
    assert state.armies[102].movement_points == 2  # paid its own ordinary cost


def test_execute_move_auto_board_boards_eligible_land_army_and_it_rides_free():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True)

    assert result.boarded_army_ids == [102]
    assert state.armies[102].transported_by == 101
    assert state.armies[102].movement_points == 3  # unchanged -- rode along for free
    assert state.armies[101].movement_points == 2  # the Fleet itself paid the ordinary cost
    assert state.armies[102].location == TARGET  # traveled with the Fleet


def test_execute_move_auto_board_respects_fleet_infantry_capacity():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.AXEMEN, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(104, 1, ArmyType.PHALANX, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102, 103, 104], target=TARGET, auto_board=True)

    assert sorted(result.boarded_army_ids) == [102, 103]  # capacity 2, lowest army ids win
    assert state.armies[104].transported_by is None
    assert state.armies[104].movement_points == 2  # paid its own ordinary cost


def test_execute_move_auto_board_priority_favors_lower_speed_tier():
    # Werebeasts (speed 3) and Trolls (speed 2) are both infantry-
    # eligible; with only 1 slot left, the real AKGEN SS106 priority
    # ("speed 1 or 2 units first") means Trolls boards, not Werebeasts,
    # regardless of army-id order.
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))  # fills 1st slot
    state.add_army(ArmyState(103, 1, ArmyType.WEREBEASTS, Quality.AVERAGE, ORIGIN, movement_points=3))  # speed 3, lower army id
    state.add_army(ArmyState(104, 1, ArmyType.TROLLS, Quality.AVERAGE, ORIGIN, movement_points=3))  # speed 2, higher army id

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102, 103, 104], target=TARGET, auto_board=True)

    assert sorted(result.boarded_army_ids) == [102, 104]
    assert state.armies[103].transported_by is None


def test_execute_move_auto_board_mounted_and_infantry_are_mutually_exclusive():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.ELEPHANTS, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102, 103], target=TARGET, auto_board=True)

    assert result.boarded_army_ids == [102]  # mounted boards first (lower army id), fills the Fleet outright
    assert state.armies[103].transported_by is None


def test_execute_move_auto_board_missing_army_table_entry_does_not_crash():
    # Crossbow has no ARMY_TABLE entry at all (a real, pre-existing gap)
    # -- the priority sort must fall back safely, not raise KeyError.
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.CROSSBOW, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True)

    assert result.boarded_army_ids == [102]


def test_execute_move_auto_board_ent_refuses_without_druidic_transport():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.ENTS, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True)

    assert result.boarded_army_ids == []
    assert state.armies[102].transported_by is None


def test_execute_move_auto_board_ent_boards_with_druidic_transport():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.ENTS, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(
        state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True, caster_has_druidic_transport=True
    )

    assert result.boarded_army_ids == [102]
    assert state.armies[102].transported_by == 101


def test_execute_move_auto_board_whale_refuses_without_the_ability():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.WHALES, Quality.AVERAGE, ORIGIN, movement_points=4))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True)

    assert result.boarded_army_ids == []


def test_execute_move_auto_board_whale_boards_with_the_ability():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.WHALES, Quality.AVERAGE, ORIGIN, movement_points=4))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(
        state,
        kingdom_id=1,
        army_ids=[101, 102],
        target=TARGET,
        auto_board=True,
        caster_has_druidic_whale_transport=True,
    )

    assert result.boarded_army_ids == [102]
    assert state.armies[102].transported_by == 101


def test_execute_move_auto_board_dragon_wing_boards_one_infantry_unconditionally():
    # Phase 717: unlike Whales, no Advanced Ability gates this -- a
    # real base rule.
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN, movement_points=5))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True)

    assert result.boarded_army_ids == [102]
    assert state.armies[102].transported_by == 101
    assert state.armies[102].movement_points == 3  # rode along for free
    assert state.armies[102].location == TARGET


def test_execute_move_auto_board_dragon_wing_respects_1_unit_capacity():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN, movement_points=5))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.AXEMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101, 102, 103], target=TARGET, auto_board=True)

    assert result.boarded_army_ids == [102]
    assert state.armies[103].transported_by is None


def test_execute_move_disembarks_a_boarded_army_moving_without_its_carrier():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3, transported_by=101))

    execute_move(state, kingdom_id=1, army_ids=[102], target=TARGET)

    assert state.armies[102].transported_by is None
    assert state.armies[102].movement_points == 2  # paid its own ordinary cost, moving alone


def test_execute_move_leaves_cargo_behind_when_carrier_moves_without_it():
    state = _transport_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3, transported_by=101))

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[102].transported_by is None
    assert state.armies[102].location == ORIGIN  # left behind, not dragged along
