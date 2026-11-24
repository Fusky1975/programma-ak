from __future__ import annotations

import random
from unittest.mock import ANY, patch

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.battle_orchestrator import BattleReport
from ak_engine.turn.battle_resolution import BattleResult
from ak_engine.turn.combat import Quality
from ak_engine.turn.contested_province import IllegalMoveFromContestedError
from ak_engine.turn.move_execution import (
    MARCH_ABILITY_BONUS,
    MARCH_MASTERY_ABILITY_BONUS,
    MARCH_TRUE_MASTERY_ABILITY_BONUS,
    MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS,
    TransportIllegalMoveError,
    execute_move,
    find_transport_illegality,
    is_flooded_province,
    march_movement_point_bonus,
    march_table_extra_movement,
    naval_movement_point_bonus,
    record_kingdom_exploration,
    apply_pending_mercenary_follows,
    resolve_wandering_mercenary_following,
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


def _sea_state(naval_target_owner: int | None = None) -> GameState:
    state = base_state()
    state.provinces[TARGET] = ProvinceState(TARGET, Terrain.SEA, Race.HUMAN, owner_kingdom_id=naval_target_owner, explored_percent=0)
    state.armies.pop(101)
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=2))
    return state


def test_a_fleet_entering_an_undefended_sea_province_pays_no_extra_movement_point():
    # Rulebook [7.7]/[11.1]: at sea the extra point is owed "only if a
    # battle takes place" -- the province is still taken, but the move costs
    # the ordinary single point.
    state = _sea_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.moved is True
    assert result.battle_report is None
    assert result.conquered is True
    assert state.provinces[TARGET].owner_kingdom_id == 1
    assert result.movement_points_spent == 1
    assert state.armies[101].movement_points == 1


def test_a_move_into_an_undefended_land_province_still_pays_the_conquest_point():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = None

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.conquered is True
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
    # Phase 769: MARCH.md section 12's own `CountArmies(leader) <= 0`
    # dispatcher condition -- the real report-layer consumer.
    assert result.moved_without_armies is True


def test_execute_move_stale_army_id_raises_a_clean_value_error():
    # Phase 1044 bug fix: direct dict subscripting used to crash with an
    # unhandled KeyError for a stale army_id (e.g. an army an earlier
    # phase this same turn already destroyed in battle) instead of the
    # same kind of clean, caught ValueError this function already raises
    # for every other bad-input case just below (all-must-move-together,
    # no movement points left).
    state = base_state()

    with pytest.raises(ValueError, match="no such army"):
        execute_move(state, kingdom_id=1, army_ids=[101, 999], target=TARGET)


def test_moving_with_armies_is_not_moved_without_armies():
    state = base_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.moved_without_armies is False


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
    # Phase 1044 bug fix: the extra hex used to update only the
    # per-kingdom tracker above, leaving the shared scalar stale --
    # models/game_state.py's own module docstring names every write
    # site that updates explored_percent_by_kingdom as also updating
    # this scalar together, the same way the entered TARGET hex already
    # does two lines above this block's own real call site.
    assert state.provinces[further].explored_percent == state.provinces[further].explored_percent_by_kingdom[1]


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


# -- Phase 1038: record_kingdom_exploration() also grows the Kingdom's own
# KingdomState.map_primary_region_columns the first time a province crosses
# the "known" floor --------------------------------------------------------


def test_record_kingdom_exploration_grows_the_primary_region_on_first_crossing_the_known_floor():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Rangeria", Race.HUMAN, Alignment.NEUTRAL, TARGET))
    state.kingdoms[1].map_primary_region_columns = {TARGET.x}
    neighbor = HexCoord(TARGET.x + 1, TARGET.y)
    province = ProvinceState(neighbor, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)

    record_kingdom_exploration(province, kingdom_id=1, explorer_skill=1, partial=False, state=state)

    assert neighbor.x in state.kingdoms[1].map_primary_region_columns


def test_record_kingdom_exploration_without_state_does_not_touch_the_primary_region():
    province = ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None)

    record_kingdom_exploration(province, kingdom_id=1, explorer_skill=1, partial=False)

    # No crash, and nothing to assert on -- there is no KingdomState at
    # all in this call, which must stay the documented no-op case.


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


def test_reveal_adjacent_provinces_grows_the_primary_region_for_a_newly_known_neighbor():
    # Phase 1038. TARGET=(2,1) is on an odd row, whose own real offset
    # table includes (+1, 0) -- (3,1) is a genuine geometric neighbor in
    # a different column from TARGET's own, unlike DEFENDER_HOME (same
    # column by construction), so this actually exercises cross-column
    # adjacency growth, not just a same-column no-op.
    state = base_state()
    far_column_neighbor = HexCoord(3, 1)
    state.add_province(ProvinceState(far_column_neighbor, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))
    state.kingdoms[1].map_primary_region_columns = {TARGET.x}
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)

    reveal_adjacent_provinces(state, state.provinces[TARGET], kingdom_id=1, bounds=bounds)

    assert far_column_neighbor.x in state.kingdoms[1].map_primary_region_columns


def test_reveal_adjacent_provinces_skips_neighbors_with_no_real_province_data():
    state = base_state()
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    # No error even though most of TARGET's own geometric neighbors have
    # no ProvinceState entry at all in this small test world -- and the
    # one real neighbor that does exist, DEFENDER_HOME, still gets its
    # floor set despite the others being skipped.

    reveal_adjacent_provinces(state, state.provinces[TARGET], kingdom_id=1, bounds=bounds)

    assert state.provinces[DEFENDER_HOME].explored_percent_by_kingdom.get(1) == 1


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
    result = record_kingdom_exploration(province, kingdom_id=1, explorer_skill=9, partial=False)
    assert result.new_percent == 100  # Plains basic=50, doubled by max skill 9
    assert result.discovered_features == []


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
    # province it occupies shouldn't force a battle. No leader_id here --
    # Phase 754's own "Wandering Mercenaries" following is gated on a
    # real general, so it's never even considered for this call.
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, TARGET, is_mercenary=True))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.battle_report is None
    assert result.moved is True
    assert state.armies[101].location == TARGET
    assert state.armies[301].kingdom_id is None  # untouched
    assert result.followed_mercenary_army_ids == []


def test_move_into_province_defended_only_by_an_independent_heros_own_army_is_contested():
    # 2026-11-19 bug fix, user-confirmed via a real GW3 world file
    # cross-check: an independent Hero's own personally-led army (e.g. a
    # wandering Hero ruling and defending a province) has kingdom_id=
    # None too, same as a masterless mercenary band -- but unlike one,
    # it's a real combatant and must still trigger a battle. Confirmed
    # directly against GW3__T1's own Melantheus (leader_id 30): his own
    # army there has kingdom_id=None, is_mercenary=False -- exactly this
    # shape -- and SE3__T1.K1's own matching battle report shows a real
    # fought battle with troop deployment, not an uncontested move.
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, TARGET, is_mercenary=False, commanded_by=30))

    with patch("ak_engine.turn.move_execution.fight_battle") as mock_fight_battle:
        mock_fight_battle.return_value = BattleReport(battle_result=BattleResult(), conquered=False)
        result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=ScriptedRandom([]))

    assert mock_fight_battle.called
    assert result.battle_report is not None


# -- Phase 754: ADDEND.AK [3.6] "Wandering Mercenaries", real mechanism ----
# (`Desktop/MOVE.md` corrects Phase 746's own coin-flip/destination design:
# the real routine scans the ORIGIN the general departs, is deterministic
# given real gates, and never changes the mercenary's own ownership.)


def test_resolve_wandering_mercenary_following_success():
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))

    followed = resolve_wandering_mercenary_following(
        state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET]
    )

    assert followed == [301]
    # 2026-11-21: the relocation is queued, not applied, until the end of
    # the turn -- the decision and the movement-point cost are immediate.
    assert state.armies[301].location == ORIGIN
    assert state.pending_mercenary_follows == [(301, TARGET)]
    assert state.armies[301].movement_points == 1
    assert state.armies[301].kingdom_id is None
    assert state.armies[301].commanded_by is None


def test_resolve_wandering_mercenary_following_refuses_without_movement_points():
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, is_mercenary=True))  # movement_points=0 default

    followed = resolve_wandering_mercenary_following(
        state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET]
    )

    assert followed == []
    assert state.armies[301].location == ORIGIN


def test_resolve_wandering_mercenary_following_refuses_an_illegal_transport_hop():
    # A Fleet can never hop directly from one land province to another --
    # `find_transport_illegality()` (Phase 737) reused directly, the same
    # real gate any ordinary army making this hop would face.
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))

    followed = resolve_wandering_mercenary_following(
        state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET]
    )

    assert followed == []
    assert state.armies[301].location == ORIGIN


def test_resolve_wandering_mercenary_following_processes_every_eligible_army_in_sorted_order():
    state = base_state()
    state.add_army(ArmyState(302, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))

    followed = resolve_wandering_mercenary_following(
        state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET]
    )

    assert followed == [301, 302]
    apply_pending_mercenary_follows(state)
    assert state.armies[301].location == TARGET
    assert state.armies[302].location == TARGET


def test_resolve_wandering_mercenary_following_ignores_non_mercenary_armies():
    state = base_state()
    state.add_army(ArmyState(301, 2, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2))  # owned by kingdom 2

    followed = resolve_wandering_mercenary_following(
        state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET]
    )

    assert followed == []
    assert state.armies[301].location == ORIGIN


def test_resolve_wandering_mercenary_following_with_none_present():
    state = base_state()

    followed = resolve_wandering_mercenary_following(
        state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET]
    )

    assert followed == []


def test_execute_move_a_mercenary_left_at_the_origin_follows_the_general():
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=10)

    assert result.followed_mercenary_army_ids == [301]
    # Queued, not moved: it relocates only at the end of the turn.
    assert state.armies[301].location == ORIGIN
    apply_pending_mercenary_follows(state)
    assert state.armies[301].location == TARGET
    assert state.armies[301].kingdom_id is None
    assert state.armies[301].commanded_by is None


def test_execute_move_a_mercenary_left_at_the_destination_does_not_follow():
    # The real mechanism scans the ORIGIN the general departs, not the
    # destination he arrives at (Phase 754's own core correction) -- a
    # mercenary already standing at the destination is simply unaffected.
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, TARGET, movement_points=2, is_mercenary=True))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=10)

    assert result.followed_mercenary_army_ids == []
    assert state.armies[301].location == TARGET
    assert state.armies[301].kingdom_id is None


def test_execute_move_leader_alone_does_not_trigger_wandering_mercenary_following():
    # Phase 754's own second correction: "the general's mere presence is
    # not enough" -- at least one army of his own main contingent must
    # still have positive movement points. An armyless leader has none.
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))

    result = execute_move(state, kingdom_id=1, army_ids=[], target=TARGET, leader_id=10)

    assert result.followed_mercenary_army_ids == []
    assert state.armies[301].location == ORIGIN


def test_execute_move_failed_conquest_does_not_trigger_wandering_mercenary_following():
    # moved=False (repelled -- a clean defender win, attacker retreats to
    # origin) -- the general never genuinely departed the origin, so
    # nothing follows him. Mirrors test_move_that_fails_to_conquer_
    # leaves_attacker_at_origin's own exact fixture/script, plus a
    # co-located mercenary army at the origin and a leader.
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))
    state.add_army(ArmyState(201, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET))
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))
    # Phase 906: turn/pursuit.py's own real, byte-confirmed mechanism
    # always runs once the attacker is clean swept (no "decline" roll
    # left) -- one extra .choice() draw (the sole retreating target) plus
    # enough placeholder .random() draws for its own r01/multiplier
    # consumption, whatever the eventual outcome (irrelevant here).
    rng = ScriptedRandom([0.9] * 11, choice_indices=[0])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=10, rng=rng)

    assert result.moved is False
    assert result.followed_mercenary_army_ids == []
    assert state.armies[301].location == ORIGIN


# -- Phase 754: `Desktop/MOVE.md` section 21.3 -- foreign Illusory Fog entry --


def test_execute_move_into_a_foreign_fogged_province_flags_the_entry():
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))
    state.provinces[TARGET].illusory_fog_active = True

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=10)

    assert result.entered_foreign_illusory_fog is True


def test_execute_move_into_a_foreign_unfogged_province_does_not_flag_the_entry():
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=10)

    assert result.entered_foreign_illusory_fog is False


def test_execute_move_into_ones_own_fogged_province_does_not_flag_the_entry():
    # The real trigger only fires when the leader's own Kingdom differs
    # from the destination's real owner -- entering a fogged province
    # you already own isn't "foreign territory."
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))
    state.provinces[TARGET].owner_kingdom_id = 1
    state.provinces[TARGET].illusory_fog_active = True

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=10)

    assert result.entered_foreign_illusory_fog is False


def test_execute_move_without_a_leader_id_does_not_flag_a_fogged_entry():
    # No real leader on record to attribute the observation to.
    state = base_state()
    state.provinces[TARGET].illusory_fog_active = True

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.entered_foreign_illusory_fog is False


def test_execute_move_failed_conquest_does_not_flag_a_fogged_entry():
    state = base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=ORIGIN))
    state.provinces[TARGET].illusory_fog_active = True
    state.add_army(ArmyState(201, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET))
    # Phase 906: see test_execute_move_failed_conquest_does_not_trigger_
    # wandering_mercenary_following's own identical Phase 906 note.
    rng = ScriptedRandom([0.9] * 11, choice_indices=[0])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=10, rng=rng)

    assert result.moved is False
    assert result.entered_foreign_illusory_fog is False


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
    # roll -- see that fixture's own Phase 296 note. Phase 744: 2 more
    # leading 0.9s account for the per-army Fanaticism roll (attacker is
    # GOOD, 40% chance; defender is NEUTRAL, 0% -- 0.9 avoids both).
    # Phase 906: turn/pursuit.py's own real mechanism deterministically
    # catches and destroys the retreating GARRISON (its own quality-down
    # strength floors at 0) -- three placeholder draws (r01, pursuer/
    # target multipliers) plus one .choice() draw for the sole target,
    # replacing the old "decline to pursue" roll.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.5, 0.5, 0.5, 0.99], choice_indices=[0])

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
    # Phase 906: Chariots, not Garrison -- Garrison's own pursuit speed
    # (1) is always caught (and, given its strength gap against an ELITE
    # Heavy Cavalry pursuer, always destroyed) by pursuit, which would
    # leave no army left to retreat at all. Chariots' own speed (3,
    # matching the pursuer's) guarantees an escape instead -- see
    # test_battle_orchestrator.py no_luck_overwhelming_attacker_rng()'s
    # own Phase 906 note.
    state.add_army(ArmyState(201, 2, ArmyType.CHARIOTS, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE
    state.armies[101].commanded_by = 1  # so fight_battle() sees leader 1 as genuinely involved
    # Phase 930: `commanded_by=1` above now also makes leader 1 a real
    # Supreme Commander, so `use_real_duel_combat=True` (this project's
    # own production default as of Phase 930) triggers a genuine duel
    # here -- an unbounded, variable number of `rng.random()` draws
    # (melee rounds until someone's hit points reach 0), unlike every
    # other draw in this fixture. A real, seeded `random.Random` replaces
    # the previous exact-count `ScriptedRandom` sequence for exactly this
    # reason; none of this test's own assertions depend on the duel's
    # outcome (only on wind_walking/conquest/retreat, all decided by the
    # deterministic strength gap regardless) -- seed 0 empirically
    # verified to satisfy every assertion below, the same "pick a real
    # seed, verify it" convention Phase 744 already used for a sibling
    # case.
    rng = random.Random(0)

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
    # Phase 744: 2 leading 0.9s account for the per-army Fanaticism roll.
    # Phase 906: turn/pursuit.py's own real mechanism deterministically
    # catches and destroys the retreating GARRISON -- three placeholder
    # draws (r01, pursuer/target multipliers) plus one .choice() draw.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99, 0.99], choice_indices=[0])

    with patch("ak_engine.turn.move_execution.apply_battle_carrier_destruction") as mock_cascade:
        result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.battle_report is not None
    mock_cascade.assert_called_once()
    call_args, call_kwargs = mock_cascade.call_args
    assert call_args == (
        state,
        result.battle_report.destroyed_army_ids,
        result.battle_report.disbanded_army_ids,
        result.battle_report.pursuit_destroyed_army_ids,
    )
    assert call_kwargs["coord"] == TARGET
    assert 101 in call_kwargs["army_types_before_battle"]


def test_move_conquest_sea_surcharge_honors_terrain_override():
    # Phase 168: a province Part Sea'd to Sea (terrain_override) still
    # incurs the (single) battle/conquest movement surcharge, even
    # though its base terrain is still Plains -- effective_terrain() is
    # what movement_cost actually reads now.
    #
    # Phase 915: Regolamento AK.txt [7.7]'s own full text ties the sea
    # surcharge back to the same single land one ("Come avviene nelle
    # province di terra..."), user-confirmed -- conquering via a won
    # battle never stacks a second, sea-specific point on top; the cost
    # is the same 2 (1 base + 1) whether or not the province is Sea.
    state = base_state()
    state.provinces[TARGET].terrain_override = Terrain.SEA
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE
    # Phase 296: leading 0.9 accounts for the new terrain-line-length-cap
    # roll -- see no_luck_overwhelming_attacker_rng()'s own Phase 296 note.
    # Phase 744: 2 more leading 0.9s account for the per-army Fanaticism roll.
    # Phase 906: turn/pursuit.py's own real mechanism deterministically
    # catches and destroys the retreating GARRISON -- three placeholder
    # draws (r01, pursuer/target multipliers) plus one .choice() draw.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99, 0.99], choice_indices=[0])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.battle_report.conquered is True
    # 1 base + 1 (battle/conquest, never stacked) = 2, terrain-independent.
    assert result.movement_points_spent == 2
    assert state.armies[101].movement_points == 1


def test_move_that_fails_to_conquer_leaves_attacker_at_origin():
    state = base_state()
    state.add_army(ArmyState(201, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET))
    # attacker is the weak BOWMEN/AVERAGE army from base_state(); force a
    # defender win with no luck events -- a clean sweep, so the attacker
    # retreats.
    # Phase 296: leading 0.9 accounts for the new terrain-line-length-cap
    # roll -- see no_luck_overwhelming_attacker_rng()'s own Phase 296 note.
    # Phase 744: 2 more leading 0.9s account for the per-army Fanaticism roll
    # (7 leading draws total here: terrain cap + 4 luck + 2 fanaticism).
    # Phase 906: turn/pursuit.py's own real mechanism always runs (no
    # "decline" roll left) -- the front-line Heavy Cavalry defender's own
    # catch test against this Bowmen retreater (`r01() + 2 > 2`) needs
    # r01()=0 to fail, guaranteeing the escape this test is about; one
    # .choice() draw for the sole retreating target, then the defender's
    # own winner_quality_roll.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.0, 0.99, 0.99], choice_indices=[0])

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.moved is False
    assert result.new_location is None
    assert state.armies[101].location == ORIGIN
    # Phase 915, user-confirmed: a battle merely taking place -- won or
    # lost -- owes the extra movement point (Regolamento AK.txt [7.7]'s
    # own "Come avviene nelle province di terra..." text). No conquest
    # here, but a real battle was fought, so cost is still 1 base + 1.
    assert result.movement_points_spent == 2


def test_execute_move_threads_apply_fanaticism_true_into_the_real_battle():
    # Phase 744: execute_move()'s own real battle trigger now opts real
    # production battles into Fanaticism -- proven by mocking roll_
    # fanaticism() directly (which also means it never touches rng
    # itself, so the pre-Phase-744 unpadded script still applies).
    state = base_state()
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE
    # Phase 906: turn/pursuit.py's own real mechanism deterministically
    # catches and destroys the retreating GARRISON -- three placeholder
    # draws (r01, pursuer/target multipliers) plus one .choice() draw.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99, 0.99], choice_indices=[0])

    with patch("ak_engine.turn.battle_orchestrator.roll_fanaticism", return_value=False) as mock_roll:
        result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=rng)

    assert result.battle_report is not None
    mock_roll.assert_any_call(Alignment.GOOD, rng)  # attacker, kingdom 1 (Attackia)
    mock_roll.assert_any_call(Alignment.NEUTRAL, rng)  # defender, kingdom 2 (Defendia)


def test_execute_move_threads_use_real_duel_combat_true_into_the_real_battle():
    # Phase 930: user-confirmed directly (rulebook [5.10]) that a Supreme
    # Commander duel has no separate formula -- it's ordinary personal
    # combat resolved against each side's own real Special Encounter
    # Plan, the same engine Search/Challenge/Pursue already use. That
    # engine (`turn/encounter.py`/`turn/challenge_execution.py`) has been
    # fully built and reachable via `use_real_duel_combat` since Phase
    # 49/669/675 -- only the real production call sites never flipped it
    # on. execute_move()'s own real battle trigger now does, mirroring
    # the "mock the shared function, assert the call kwarg" convention
    # Phase 744 already used for `apply_fanaticism`.
    state = base_state()
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    state.armies[101].army_type = ArmyType.HVY_CAVALRY
    state.armies[101].quality = Quality.ELITE

    with patch("ak_engine.turn.move_execution.fight_battle") as mock_fight_battle:
        mock_fight_battle.return_value = BattleReport(battle_result=BattleResult(), conquered=False)
        execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=ScriptedRandom([]))

    assert mock_fight_battle.call_args.kwargs["use_real_duel_combat"] is True
    assert mock_fight_battle.call_args.kwargs["apply_fanaticism"] is True


def test_raises_without_movement_points():
    state = base_state()
    state.armies[101].movement_points = 0

    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)


def test_does_not_raise_when_the_march_table_bonus_alone_covers_it():
    # Bug fix, user-confirmed (2026-11-18): "quando un'armata ha anche
    # solo una unita che ha finito il movimento, giustamente si ferma"
    # -- but march_table_extra_movement()/naval_movement_point_bonus()
    # are a flat function of the leader's own skill level and the
    # army's own catalog speed, never of its current movement_points,
    # so an army truly down to 0 can still have real movement due once
    # that still-unclaimed bonus is counted. BOWMEN's own catalog speed
    # (2, the SLOW column) gives march_skill_level=2 a +1 bonus
    # (march_table_extra_movement(2, 2) == 1) -- enough, on its own, to
    # cover army 101's own 0 current movement_points.
    state = base_state()
    state.armies[101].movement_points = 0

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, march_skill_level=2)

    assert result.moved is True


def test_still_raises_without_movement_points_when_no_bonus_is_due():
    # Same 0-movement-points army as above, but with no march skill at
    # all (the default) -- march_table_extra_movement(0, ...) is 0, so
    # there's genuinely nothing left to cover it and the group still
    # correctly can't move.
    state = base_state()
    state.armies[101].movement_points = 0

    with pytest.raises(ValueError):
        execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, march_skill_level=0)


def test_does_not_raise_when_the_naval_bonus_alone_covers_it():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=0)

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, naval_skill_level=1)

    assert result.moved is True


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


def test_stopped_chasing_leader_alone_reports_moved_without_armies():
    # Phase 1044 bug fix: this early return used to omit
    # moved_without_armies entirely, silently defaulting it to False
    # even for a genuinely armyless leader -- report/turn_report.py's
    # own documented MARCH.md section 12 consumer needs the real value
    # here too, not just on the function's final, successful-move return.
    state = GameState()
    origin = HexCoord(0, 0)
    unreachable_target = HexCoord(-5, -5)
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, origin))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, 1, "King", origin))

    result = execute_move(state, kingdom_id=1, army_ids=[], target=unreachable_target, leader_id=1)

    assert result.stopped_chasing is True
    assert result.moved is False
    assert result.moved_without_armies is True


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

    # Phase 906: turn/pursuit.py's own real mechanism always runs once a
    # side is clean swept -- pad with a generous, outcome-irrelevant
    # supply of .choice()/.random() draws (this test only cares that a
    # battle happened at all).
    result = execute_move(
        state, kingdom_id=1, army_ids=[101], target=FAR_TARGET,
        rng=ScriptedRandom([0.9] * 30, choice_indices=[0, 0, 0, 0, 0]),
    )

    assert result.battle_report is not None


# -- Phase 521: March category (Cavalry/Infantry + Mastery tiers) --------


def test_march_movement_point_bonus_cavalry_at_the_minimum_band():
    assert march_movement_point_bonus(3, has_march_cavalry=True) == MARCH_ABILITY_BONUS


def test_march_movement_point_bonus_cavalry_below_the_band_is_zero():
    assert march_movement_point_bonus(2, has_march_cavalry=True) == 0


def test_march_movement_point_bonus_cavalry_mastery_is_the_total_not_additive():
    assert march_movement_point_bonus(3, has_march_cavalry_mastery=True) == MARCH_MASTERY_ABILITY_BONUS


def test_march_movement_point_bonus_cavalry_true_mastery_is_the_total_not_additive():
    # Phase 768: the real 3rd stacking tier -- +3 total, not +1 on top
    # of Mastery's own +2.
    assert march_movement_point_bonus(3, has_march_cavalry_true_mastery=True) == MARCH_TRUE_MASTERY_ABILITY_BONUS


def test_march_movement_point_bonus_cavalry_true_mastery_takes_precedence():
    # Mirrors turn/encounter.py melee_mastery_damage_bonus()'s own
    # "True Mastery checked first" defensive ordering -- a leader only
    # ever holds one Advanced Ability per category in practice, but the
    # precedence must still be correct if more than one flag is set.
    assert (
        march_movement_point_bonus(3, has_march_cavalry=True, has_march_cavalry_mastery=True, has_march_cavalry_true_mastery=True)
        == MARCH_TRUE_MASTERY_ABILITY_BONUS
    )


def test_march_movement_point_bonus_cavalry_true_mastery_below_the_band_is_zero():
    assert march_movement_point_bonus(2, has_march_cavalry_true_mastery=True) == 0


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


def test_execute_move_grants_march_cavalry_true_mastery_bonus():
    # Phase 768: end-to-end -- +3 (True Mastery) on top of the move's
    # own base cost, mirroring test_execute_move_grants_march_cavalry_
    # bonus_before_deducting_cost()'s own shape exactly.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101].army_type = ArmyType.HVY_CAVALRY

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_cavalry_true_mastery=True)

    assert state.armies[101].movement_points == 3 + MARCH_TRUE_MASTERY_ABILITY_BONUS - 1


def test_execute_move_gives_no_march_bonus_without_the_ability():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].march_bonus_applied_this_turn is False


# -- Phase 768: Move-triggered March/Naval experience credit ---------------


def _state_with_leader_and_army(army_type: ArmyType = ArmyType.BOWMEN) -> GameState:
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1  # no battle/conquest -- moved is True either way
    state.add_leader(LeaderState(1, 1, "Mover", ORIGIN))
    state.armies[101].army_type = army_type
    state.armies[101].commanded_by = 1
    return state


def test_execute_move_credits_march_experience_for_a_land_move():
    state = _state_with_leader_and_army()

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(
            state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, rng=ScriptedRandom([0.5, 0.5])
        )

    mock_add_experience.assert_called_once_with(state.leaders[1], Ability.MARCH, MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS, ANY)


def test_execute_move_credits_naval_experience_when_the_destination_is_sea():
    state = _state_with_leader_and_army(ArmyType.FLEET)
    state.provinces[TARGET].terrain = Terrain.SEA

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(
            state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, rng=ScriptedRandom([0.5, 0.5])
        )

    mock_add_experience.assert_called_once_with(state.leaders[1], Ability.NAVAL, MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS, ANY)


def test_execute_move_credits_naval_experience_when_the_origin_is_sea():
    state = _state_with_leader_and_army(ArmyType.FLEET)
    state.provinces[ORIGIN].terrain = Terrain.SEA
    state.armies[101].location = ORIGIN

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(
            state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, rng=ScriptedRandom([0.5, 0.5])
        )

    mock_add_experience.assert_called_once_with(state.leaders[1], Ability.NAVAL, MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS, ANY)


def test_execute_move_credits_nothing_for_a_majority_air_force():
    # 2 Dragon Wings out of 3 armies -> 2*2 >= 3 -- excluded, matching
    # the same test this module's own _LFly narration branch uses.
    state = _state_with_leader_and_army(ArmyType.DRAGON_WING)
    state.add_army(ArmyState(102, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN, movement_points=3, commanded_by=1))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3, commanded_by=1))

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(
            state, kingdom_id=1, army_ids=[101, 102, 103], target=TARGET, leader_id=1, rng=ScriptedRandom([])
        )

    mock_add_experience.assert_not_called()


def test_execute_move_credits_experience_for_a_minority_air_mixed_force():
    # 1 Dragon Wing out of 3 -> 2*1 &lt; 3 -- not majority-air, so the roll
    # still fires (for the mover as a whole, using the land/Sea terrain
    # check -- neither terrain here is Sea, so March).
    state = _state_with_leader_and_army(ArmyType.DRAGON_WING)
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3, commanded_by=1))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3, commanded_by=1))

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(
            state, kingdom_id=1, army_ids=[101, 102, 103], target=TARGET, leader_id=1, rng=ScriptedRandom([0.5, 0.5])
        )

    mock_add_experience.assert_called_once_with(state.leaders[1], Ability.MARCH, MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS, ANY)


def test_execute_move_credits_nothing_for_a_majority_air_transportable_force():
    # Phase 1044 bug fix: this function's own Phase 768 docstring
    # addendum states the exclusion covers "a majority-air-or-air-
    # transportable force," but air_count used to count only armies
    # whose own army_type is literally an air type, never a land army
    # currently boarded on one -- 1 Dragon Wing carrying 2 boarded
    # Bowmen (a wholly airlifted force) used to compute air_count=1
    # against len(armies)=3 (2*1 < 3 -- treated as an ordinary,
    # XP-eligible ground march), contradicting the documented exclusion.
    state = _state_with_leader_and_army(ArmyType.DRAGON_WING)
    state.add_army(
        ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3, commanded_by=1, transported_by=101)
    )
    state.add_army(
        ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3, commanded_by=1, transported_by=101)
    )

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(
            state, kingdom_id=1, army_ids=[101, 102, 103], target=TARGET, leader_id=1, rng=ScriptedRandom([])
        )

    mock_add_experience.assert_not_called()


def test_execute_move_credits_nothing_when_the_leader_is_armyless():
    state = _state_with_leader_and_army()

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(state, kingdom_id=1, army_ids=[], target=TARGET, leader_id=1, rng=ScriptedRandom([]))

    mock_add_experience.assert_not_called()


def test_execute_move_credits_nothing_without_a_leader():
    state = _state_with_leader_and_army()

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=ScriptedRandom([]))

    mock_add_experience.assert_not_called()


def test_execute_move_credits_nothing_when_a_chase_step_stops_without_moving():
    # Mirrors test_stopped_chasing_when_no_closer_neighbor_exists()'s own
    # fixture shape exactly (only the origin province registered, so no
    # candidate neighbor is ever geometrically closer to the far target)
    # plus a real leader/army. moved=False -- the gate on `moved` must
    # exclude this case.
    state = GameState()
    isolated_origin = HexCoord(0, 0)
    unreachable_target = HexCoord(-5, -5)
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, isolated_origin))
    state.add_province(ProvinceState(isolated_origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, 1, "Mover", isolated_origin))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, isolated_origin, movement_points=3, commanded_by=1))

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        result = execute_move(
            state, kingdom_id=1, army_ids=[101], target=unreachable_target, leader_id=1, rng=ScriptedRandom([])
        )

    assert result.stopped_chasing is True
    assert result.moved is False
    mock_add_experience.assert_not_called()


# -- Phase 787: Naval Advanced Ability level schedule + runtime wiring -----


def test_execute_move_grants_a_naval_advanced_ability_when_the_real_credit_crosses_a_level():
    # game_number defaults to 1 -- build_naval_ability_level_schedule(1)
    # maps level 5 to NAVAL_LONG_DEFEND (confirmed directly).
    state = _state_with_leader_and_army(ArmyType.FLEET)
    state.provinces[TARGET].terrain = Terrain.SEA
    leader = state.leaders[1]
    leader.skills = SkillTable([0] * 30)
    leader.skills.set_pair_for_ability(Ability.NAVAL, 4, 5)  # aptitude >= target skill -- gate always succeeds
    leader.experience_credit = 95

    # gain = round(10*(1+0.9-0.0)) = 19 -> new_credit = 114 >= 100 -> skill rises
    result = execute_move(
        state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, rng=ScriptedRandom([0.9, 0.0, 0.5])
    )

    # Phase 1189 bug fix: the rise itself is deferred to next phase (same
    # [3.13]-equivalent rule add_experience() now shares with Practice) --
    # not yet written into the real skill table.
    assert leader.pending_skill_advancement == {Ability.NAVAL: (5, 5)}
    assert leader.skills.pair_for_ability(Ability.NAVAL) == (4, 5)
    assert result.naval_advanced_ability_granted is AdvancedAbility.NAVAL_LONG_DEFEND
    assert AdvancedAbility.NAVAL_LONG_DEFEND in leader.advanced_abilities


def test_execute_move_grants_nothing_when_the_naval_credit_does_not_cross_a_level():
    state = _state_with_leader_and_army(ArmyType.FLEET)
    state.provinces[TARGET].terrain = Terrain.SEA
    leader = state.leaders[1]

    # gain = round(10*(1+0.5-0.5)) = 10 -> new_credit = 10, well below 100
    result = execute_move(
        state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, rng=ScriptedRandom([0.5, 0.5])
    )

    assert result.naval_advanced_ability_granted is None
    assert leader.advanced_abilities == set()


def test_execute_move_a_march_credit_never_grants_a_naval_advanced_ability():
    # A land move (no Sea terrain) credits Ability.MARCH, never NAVAL --
    # even when the same scripted rise-crossing sequence is used, no
    # Naval grant should ever be attempted. Phase 901: it now correctly
    # grants March's own real AdvancedAbility instead of nothing.
    state = _state_with_leader_and_army()
    leader = state.leaders[1]
    leader.skills = SkillTable([0] * 30)
    leader.skills.set_pair_for_ability(Ability.MARCH, 4, 5)
    leader.experience_credit = 95

    result = execute_move(
        state, kingdom_id=1, army_ids=[101], target=TARGET, leader_id=1, rng=ScriptedRandom([0.9, 0.0, 0.5])
    )

    # Phase 1189 bug fix: deferred to next phase, same as the Naval case above.
    assert leader.pending_skill_advancement == {Ability.MARCH: (5, 5)}
    assert leader.skills.pair_for_ability(Ability.MARCH) == (4, 5)
    assert result.naval_advanced_ability_granted is None
    assert result.march_advanced_ability_granted is AdvancedAbility.MARCH_THROUGH_FLOODS
    assert leader.advanced_abilities == {AdvancedAbility.MARCH_THROUGH_FLOODS}


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

    execute_move(
        state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_cavalry=True, naval_skill_level=3, march_skill_level=4
    )

    assert state.armies[101].movement_points == 2
    assert state.armies[101].march_bonus_applied_this_turn is False
    assert state.armies[101].naval_bonus_applied_this_turn is False
    assert state.armies[101].march_table_bonus_applied_this_turn is False


def test_execute_move_gives_no_naval_bonus_without_skill():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].naval_bonus_applied_this_turn is False


# -- Phase 764: [4.12] MARCH TABLE's own raw-skill-level movement bonus --


def test_march_table_extra_movement_slow_column():
    assert march_table_extra_movement(0, army_speed=2) == 0
    assert march_table_extra_movement(1, army_speed=2) == 0
    assert march_table_extra_movement(2, army_speed=2) == 1
    assert march_table_extra_movement(3, army_speed=2) == 1
    assert march_table_extra_movement(4, army_speed=2) == 2


def test_march_table_extra_movement_fast_column():
    assert march_table_extra_movement(0, army_speed=3) == 0
    assert march_table_extra_movement(1, army_speed=3) == 1
    assert march_table_extra_movement(2, army_speed=3) == 1
    assert march_table_extra_movement(3, army_speed=3) == 2
    assert march_table_extra_movement(4, army_speed=3) == 2


def test_march_table_extra_movement_clamps_above_the_known_range():
    assert march_table_extra_movement(9, army_speed=2) == march_table_extra_movement(4, army_speed=2)
    assert march_table_extra_movement(9, army_speed=3) == march_table_extra_movement(4, army_speed=3)


def test_march_table_extra_movement_clamps_negative_input_to_zero():
    assert march_table_extra_movement(-3, army_speed=2) == 0


def test_execute_move_grants_march_table_bonus_before_deducting_cost():
    # Bowmen (speed 2, base_state()'s own default army) -- Speed 1-2
    # column, level 2 gives +1.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, march_skill_level=2)

    # 3 (start) + 1 (bonus) - 1 (cost) == 3
    assert state.armies[101].movement_points == 3
    assert state.armies[101].march_table_bonus_applied_this_turn is True


def test_execute_move_march_table_bonus_uses_the_fast_column_for_speed_3_plus():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, ORIGIN, movement_points=3)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, march_skill_level=1)

    # 3 (start) + 1 (fast-column bonus at level 1) - 1 (cost) == 3
    assert state.armies[101].movement_points == 3
    assert state.armies[101].march_table_bonus_applied_this_turn is True


def test_execute_move_gives_no_march_table_bonus_at_skill_level_0():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, march_skill_level=0)

    assert state.armies[101].movement_points == 2
    assert state.armies[101].march_table_bonus_applied_this_turn is False


def test_execute_move_gives_no_march_table_bonus_to_a_sea_army_type():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=2)

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, march_skill_level=4)

    assert state.armies[101].march_table_bonus_applied_this_turn is False


def test_execute_move_does_not_regrant_march_table_bonus_within_the_same_turn():
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1

    execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, march_skill_level=2)
    after_first_move = state.armies[101].movement_points
    execute_move(state, kingdom_id=1, army_ids=[101], target=ORIGIN, march_skill_level=2)

    assert state.armies[101].movement_points == after_first_move - 1


def test_execute_move_march_table_bonus_stacks_with_the_advanced_ability_bonus():
    # Bowmen at exactly 1 movement point (Infantry's own qualifying band
    # for march_movement_point_bonus()) plus a real march_skill_level --
    # both distinct, separately-sourced bonuses apply to the same move.
    state = base_state()
    state.provinces[TARGET].owner_kingdom_id = 1
    state.armies[101] = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=1)

    execute_move(
        state, kingdom_id=1, army_ids=[101], target=TARGET, has_march_infantry=True, march_skill_level=4
    )

    # 1 (start) + 1 (Infantry Advanced Ability) + 2 (table, level 4, slow column) - 1 (cost) == 3
    assert state.armies[101].movement_points == 3
    assert state.armies[101].march_bonus_applied_this_turn is True
    assert state.armies[101].march_table_bonus_applied_this_turn is True


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


def test_execute_move_naval_hug_coastline_splits_unboarded_stragglers_when_the_fleet_cannot_carry_every_land_army():
    # Phase 763: 3 Bowmen exceed FLEET_INFANTRY_CAPACITY=2 -- 2 board (101,
    # 102, lowest army ids first), 1 doesn't (103). The boarded pair plus
    # the Fleet itself take the coastal shortcut together; the unboarded
    # straggler travels separately, by the ordinary route (a chase step,
    # since HUG_TARGET isn't adjacent to HUG_ORIGIN) -- this supersedes the
    # old, pre-Phase-763 all-or-nothing denial of the whole group.
    state = _hug_state()
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(104, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    result = execute_move(
        state, kingdom_id=1, army_ids=[101, 102, 103, 104], target=HUG_TARGET, has_naval_hug_coastline=True, auto_board=True
    )

    assert state.armies[101].location == HUG_TARGET
    assert state.armies[102].location == HUG_TARGET
    assert state.armies[104].location == HUG_TARGET
    assert state.armies[103].location != HUG_TARGET

    assert result.straggler_result is not None
    assert result.straggler_result.moved is True
    assert result.straggler_result.reached_target is False


def test_execute_move_naval_hug_coastline_split_leader_travels_with_the_hop_group():
    # Phase 763: the acting leader is modeled as staying with the boarded/
    # carrier portion of a split -- a documented modeling choice, not a
    # sourced fact -- so the leader's own location ends up at HUG_TARGET
    # even though one accompanying army (103, exceeding FLEET_INFANTRY_
    # CAPACITY=2) is left behind as a straggler.
    state = _hug_state()
    state.add_leader(LeaderState(1, 1, "General", HUG_ORIGIN))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(104, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    execute_move(
        state,
        kingdom_id=1,
        army_ids=[101, 102, 103, 104],
        target=HUG_TARGET,
        leader_id=1,
        has_naval_hug_coastline=True,
        auto_board=True,
    )

    assert state.armies[101].location == HUG_TARGET
    assert state.armies[102].location == HUG_TARGET
    assert state.armies[104].location == HUG_TARGET
    assert state.leaders[1].location == HUG_TARGET
    assert state.armies[103].location != HUG_TARGET


def test_execute_move_naval_hug_coastline_no_split_when_no_stragglers_remain():
    # Non-regression: a fully-boarded mixed group (Phase 720's own
    # already-tested case) never populates straggler_result at all.
    state = _hug_state()
    state.add_army(ArmyState(102, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    result = execute_move(
        state, kingdom_id=1, army_ids=[101, 102], target=HUG_TARGET, has_naval_hug_coastline=True, auto_board=True
    )

    assert result.straggler_result is None
    assert state.armies[101].location == HUG_TARGET
    assert state.armies[102].location == HUG_TARGET


def test_execute_move_straggler_recursive_call_does_not_double_credit_move_experience():
    # Phase 768: the Phase 763 straggler recursive call passes
    # leader_id=None -- naturally excluded from the new Move-experience
    # credit, so the one outer, real leader-driven call is the only one
    # that ever fires it, even though execute_move() runs twice here.
    state = _hug_state()
    state.add_leader(LeaderState(1, 1, "General", HUG_ORIGIN))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(104, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        result = execute_move(
            state,
            kingdom_id=1,
            army_ids=[101, 102, 103, 104],
            target=HUG_TARGET,
            leader_id=1,
            has_naval_hug_coastline=True,
            auto_board=True,
            rng=ScriptedRandom([0.5, 0.5]),
        )

    assert result.straggler_result is not None  # confirms the recursive call really ran
    # Both HUG_ORIGIN and HUG_TARGET are land (Plains) -- the shared
    # coastal Sea hex is a separate, third coordinate, never the actual
    # origin/destination checked here -- so this credits March, not Naval.
    mock_add_experience.assert_called_once_with(state.leaders[1], Ability.MARCH, MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS, ANY)


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


# -- Phase 737: find_transport_illegality() -- the real sea-transport movement-legality gate --


def _sea_province(coord: HexCoord) -> ProvinceState:
    return ProvinceState(coord, Terrain.SEA, Race.HUMAN)


def _land_province(coord: HexCoord) -> ProvinceState:
    return ProvinceState(coord, Terrain.PLAINS, Race.HUMAN)


def _flooded_province(coord: HexCoord) -> ProvinceState:
    return ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA)


def _part_sea_province(coord: HexCoord) -> ProvinceState:
    return ProvinceState(coord, Terrain.SEA, Race.HUMAN, terrain_override=Terrain.PLAINS)


def test_find_transport_illegality_land_army_into_sea_without_carrier():
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([army], [1], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason == "insufficient_water_transport"


def test_find_transport_illegality_land_army_boarded_onto_a_same_move_fleet():
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)
    bowmen = ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, transported_by=1)
    reason = find_transport_illegality([fleet, bowmen], [1, 2], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_land_army_boarded_onto_a_carrier_not_in_this_move():
    # transported_by is set, but the carrier's own id isn't part of
    # army_ids for this call -- not legally aboard for THIS hop.
    bowmen = ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, transported_by=99)
    reason = find_transport_illegality([bowmen], [2], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason == "insufficient_water_transport"


def test_find_transport_illegality_fleet_hopping_land_to_land():
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([fleet], [1], _land_province(ORIGIN), _land_province(TARGET))
    assert reason == "naval_land_hop"


def test_find_transport_illegality_fleet_hopping_land_to_land_excused_by_hug_coastline():
    # Phase 819 bug fix: a real, already-verified Naval Hug Coastline hop
    # (both endpoints land, per _naval_hug_coastline_move_is_legal()) is
    # exactly the one land-to-land Fleet/Whale crossing the ability is
    # meant to allow -- is_hug_coastline_hop=True must excuse it, unlike
    # an ordinary, unassisted land-to-land Fleet hop (the test right
    # above, which stays illegal with the default False).
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality(
        [fleet], [1], _land_province(ORIGIN), _land_province(TARGET), is_hug_coastline_hop=True
    )
    assert reason is None


def test_find_transport_illegality_fleet_entering_or_leaving_land_is_fine():
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)
    assert find_transport_illegality([fleet], [1], _land_province(ORIGIN), _sea_province(TARGET)) is None
    assert find_transport_illegality([fleet], [1], _sea_province(ORIGIN), _land_province(TARGET)) is None


def test_find_transport_illegality_whales_treated_identically_to_fleet():
    # User-confirmed: trust the rulebook, not ILLMOVE_TEMPLATE[2] --
    # Whales and Fleet both may enter/exit land freely.
    whales = ArmyState(1, 1, ArmyType.WHALES, Quality.AVERAGE, ORIGIN)
    assert find_transport_illegality([whales], [1], _land_province(ORIGIN), _sea_province(TARGET)) is None
    reason = find_transport_illegality([whales], [1], _land_province(ORIGIN), _land_province(TARGET))
    assert reason == "naval_land_hop"


def test_find_transport_illegality_ent_into_sea_without_transport():
    ent = ArmyState(1, 1, ArmyType.ENTS, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([ent], [1], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason == "ent_shoreline"


def test_find_transport_illegality_ent_boarded_via_druidic_transport():
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)
    ent = ArmyState(2, 1, ArmyType.ENTS, Quality.AVERAGE, ORIGIN, transported_by=1)
    reason = find_transport_illegality([fleet, ent], [1, 2], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_ent_may_cross_a_part_sea_province():
    ent = ArmyState(1, 1, ArmyType.ENTS, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([ent], [1], _land_province(ORIGIN), _part_sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_dinosaur_into_sea_without_transport():
    dinosaur = ArmyState(1, 1, ArmyType.DINOSAURS, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([dinosaur], [1], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason == "dinosaur_shoreline"


def test_find_transport_illegality_dinosaur_boarded_via_druidic_transport():
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)
    dinosaur = ArmyState(2, 1, ArmyType.DINOSAURS, Quality.AVERAGE, ORIGIN, transported_by=1)
    reason = find_transport_illegality([fleet, dinosaur], [1, 2], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_mermen_moves_like_a_fleet_sea_to_land():
    # 2026-11-20 bug fix, user-confirmed via a live playtest: "I Tritoni
    # muovono come le Flotte" -- an ordinary Sea->Land hop needs no Part
    # Sea/air-transport exception at all, exactly like a Fleet/Whale.
    mermen = ArmyState(1, 1, ArmyType.MERMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([mermen], [1], _sea_province(ORIGIN), _land_province(TARGET))
    assert reason is None


def test_find_transport_illegality_mermen_moves_like_a_fleet_land_to_sea():
    mermen = ArmyState(1, 1, ArmyType.MERMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([mermen], [1], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_mermen_land_to_land_still_illegal():
    # The one real Mermen restriction left, mirroring Fleet/Whale's own
    # "naval_land_hop" -- neither endpoint is Sea or Part-Sea.
    mermen = ArmyState(1, 1, ArmyType.MERMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([mermen], [1], _land_province(ORIGIN), _land_province(TARGET))
    assert reason == "mermen_air_transport"


def test_find_transport_illegality_mermen_may_cross_a_part_sea_province():
    mermen = ArmyState(1, 1, ArmyType.MERMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([mermen], [1], _sea_province(ORIGIN), _part_sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_mermen_moving_between_sea_provinces():
    mermen = ArmyState(1, 1, ArmyType.MERMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([mermen], [1], _sea_province(ORIGIN), _sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_mermen_carried_by_an_air_carrier_onto_land():
    dragon = ArmyState(1, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN)
    mermen = ArmyState(2, 1, ArmyType.MERMEN, Quality.AVERAGE, ORIGIN, transported_by=1)
    reason = find_transport_illegality([dragon, mermen], [1, 2], _sea_province(ORIGIN), _land_province(TARGET))
    assert reason is None


def test_find_transport_illegality_air_unit_never_restricted():
    dragon = ArmyState(1, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN)
    assert find_transport_illegality([dragon], [1], _land_province(ORIGIN), _land_province(TARGET)) is None
    assert find_transport_illegality([dragon], [1], _land_province(ORIGIN), _sea_province(TARGET)) is None


def test_find_transport_illegality_mixed_group_the_illegal_army_wins():
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)  # legal on its own (land->sea)
    bowmen = ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN)  # unassisted -- illegal
    reason = find_transport_illegality([fleet, bowmen], [1, 2], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason == "insufficient_water_transport"


def test_find_transport_illegality_all_legal_mixed_group():
    fleet = ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN)
    bowmen = ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, transported_by=1)
    reason = find_transport_illegality([fleet, bowmen], [1, 2], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason is None


def test_find_transport_illegality_march_through_floods_excuses_a_real_flood():
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality(
        [bowmen], [1], _land_province(ORIGIN), _flooded_province(TARGET), has_march_through_floods=True
    )
    assert reason is None


def test_find_transport_illegality_march_through_floods_does_not_excuse_natural_sea():
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality(
        [bowmen], [1], _land_province(ORIGIN), _sea_province(TARGET), has_march_through_floods=True
    )
    assert reason == "insufficient_water_transport"


# -- Phase 888: Discovery.FLOOD_DAMS's own per-army rest-of-turn exemption --


def test_find_transport_illegality_flood_dams_exempt_army_may_enter_the_flooded_province():
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, flood_dams_exempt_at=TARGET)
    reason = find_transport_illegality([bowmen], [1], _land_province(ORIGIN), _flooded_province(TARGET))
    assert reason is None


def test_find_transport_illegality_flood_dams_exempt_army_may_leave_the_flooded_province():
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, flood_dams_exempt_at=ORIGIN)
    reason = find_transport_illegality([bowmen], [1], _flooded_province(ORIGIN), _land_province(TARGET))
    assert reason is None


def test_find_transport_illegality_without_flood_dams_exemption_still_blocks_a_flooded_province():
    # Non-regression: an army that never paid this turn's Flood Dams
    # toll (the default, ``None``) is still refused exactly as before --
    # e.g. one that arrives at the province later in the same turn.
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([bowmen], [1], _land_province(ORIGIN), _flooded_province(TARGET))
    assert reason == "insufficient_water_transport"


def test_find_transport_illegality_flood_dams_exemption_is_scoped_to_its_own_coord():
    # An exemption earned at a *different* Flooded province this same
    # turn doesn't carry over to this one.
    other_coord = HexCoord(9, 9)
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, flood_dams_exempt_at=other_coord)
    reason = find_transport_illegality([bowmen], [1], _land_province(ORIGIN), _flooded_province(TARGET))
    assert reason == "insufficient_water_transport"


def test_find_transport_illegality_flood_dams_exemption_does_not_excuse_natural_sea():
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, flood_dams_exempt_at=TARGET)
    reason = find_transport_illegality([bowmen], [1], _land_province(ORIGIN), _sea_province(TARGET))
    assert reason == "insufficient_water_transport"


def test_find_transport_illegality_no_origin_province_treated_as_no_terrain():
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN)
    reason = find_transport_illegality([bowmen], [1], None, _land_province(TARGET))
    assert reason == "insufficient_water_transport"


# -- Phase 737: execute_move()'s own enforce_transport_legality parameter --


def _sea_transport_legality_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Coastia", Race.HUMAN, Alignment.GOOD, ORIGIN))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.SEA, Race.HUMAN, owner_kingdom_id=1))
    return state


def test_execute_move_default_still_permits_an_unassisted_sea_crossing():
    # Non-breaking check: enforce_transport_legality defaults False, so
    # every pre-Phase-737 caller (including every other feature's own
    # existing test fixture) is completely unaffected.
    state = _sea_transport_legality_state()
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET)

    assert result.moved is True
    assert state.armies[101].location == TARGET


def test_execute_move_enforced_raises_for_an_unassisted_sea_crossing():
    state = _sea_transport_legality_state()
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    with pytest.raises(TransportIllegalMoveError) as excinfo:
        execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, enforce_transport_legality=True)

    assert excinfo.value.reason == "insufficient_water_transport"
    assert excinfo.value.origin_coord == ORIGIN
    assert excinfo.value.destination_coord == TARGET
    assert state.armies[101].location == ORIGIN  # never moved


def test_execute_move_enforced_permits_a_flood_dams_exempt_army_to_leave_a_flooded_province():
    # Phase 888: an army Discovery.FLOOD_DAMS already charged this
    # turn's one-time toll to (turn/cast_execution.py _execute_flood())
    # is excused from the ongoing rest-of-turn block for that exact
    # province, reaching all the way through the real enforced dispatch
    # path -- not just the unit-level find_transport_illegality() check.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Coastia", Race.HUMAN, Alignment.GOOD, TARGET))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, terrain_override=Terrain.SEA))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, TARGET, movement_points=3, flood_dams_exempt_at=TARGET))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=ORIGIN, enforce_transport_legality=True)

    assert result.moved is True
    assert state.armies[101].location == ORIGIN


def test_execute_move_enforced_still_blocks_a_non_exempt_army_leaving_the_same_flooded_province():
    # Non-regression companion: without the exemption, the identical
    # province still blocks an ordinary land army exactly as before.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Coastia", Race.HUMAN, Alignment.GOOD, TARGET))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, terrain_override=Terrain.SEA))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, TARGET, movement_points=3))

    with pytest.raises(TransportIllegalMoveError) as excinfo:
        execute_move(state, kingdom_id=1, army_ids=[101], target=ORIGIN, enforce_transport_legality=True)

    assert excinfo.value.reason == "insufficient_water_transport"
    assert state.armies[101].location == TARGET  # never moved


def test_execute_move_enforced_permits_a_real_boarded_crossing():
    state = _sea_transport_legality_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(
        state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True, enforce_transport_legality=True
    )

    assert result.moved is True
    assert state.armies[102].transported_by == 101


def test_execute_move_enforced_transport_illegality_leaves_no_partial_auto_boarding():
    # Phase 1045 bug fix regression: before the fix, _auto_board_
    # transport_group() committed real boarding for every candidate that
    # fit *before* find_transport_illegality() ever ran, so a stack with
    # more land armies than the Fleet had capacity for ended up with the
    # ones that DID fit boarded for real even though the whole move was
    # refused right after (turn/plan_dispatch.py run_leader_plan() catches
    # TransportIllegalMoveError per-phase with no rollback). FLEET_
    # INFANTRY_CAPACITY is 2 -- of 3 Bowmen-type candidates (102, 103,
    # 104), the lowest two would have fit and (pre-fix) really boarded.
    state = _sea_transport_legality_state()
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.AXEMEN, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(104, 1, ArmyType.PHALANX, Quality.AVERAGE, ORIGIN, movement_points=3))

    with pytest.raises(TransportIllegalMoveError) as excinfo:
        execute_move(
            state,
            kingdom_id=1,
            army_ids=[101, 102, 103, 104],
            target=TARGET,
            auto_board=True,
            enforce_transport_legality=True,
        )

    assert excinfo.value.reason == "insufficient_water_transport"
    for army_id in (101, 102, 103, 104):
        assert state.armies[army_id].transported_by is None
        assert state.armies[army_id].location == ORIGIN


def test_execute_move_enforced_permits_a_real_naval_hug_coastline_hop():
    # Phase 819 bug fix: turn/plan_dispatch.py's own real LMOVE dispatch
    # already passes enforce_transport_legality=True unconditionally
    # (Phase 737) alongside a real has_naval_hug_coastline=True for any
    # leader holding the ability (Phase 524) -- before this fix, a pure
    # Fleet making exactly this real, already-legal hop was always
    # blocked outright with "naval_land_hop", since neither endpoint of
    # a Hug Coastline hop is ever Terrain.SEA by construction. No
    # existing test ever combined the two flags to catch this.
    state = _hug_state()
    state.armies[101].army_type = ArmyType.FLEET

    result = execute_move(
        state,
        kingdom_id=1,
        army_ids=[101],
        target=HUG_TARGET,
        has_naval_hug_coastline=True,
        enforce_transport_legality=True,
    )

    assert result.moved is True
    assert state.armies[101].location == HUG_TARGET


def test_execute_move_enforced_permits_a_mixed_naval_hug_coastline_hop():
    # The mixed carrier-plus-boarded-cargo case (Phase 720) is equally
    # affected: the Fleet itself, not just its cargo, must clear the
    # transport-legality gate for the same real hop.
    state = _hug_state()
    state.add_army(ArmyState(102, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    result = execute_move(
        state,
        kingdom_id=1,
        army_ids=[101, 102],
        target=HUG_TARGET,
        has_naval_hug_coastline=True,
        auto_board=True,
        enforce_transport_legality=True,
    )

    assert result.moved is True
    assert state.armies[101].location == HUG_TARGET
    assert state.armies[102].location == HUG_TARGET
    assert state.armies[101].transported_by == 102


def test_execute_move_contested_origin_raises_before_committing_auto_board_or_straggler_split():
    # Phase 1045 bug fix regression -- the originally-deferred Batch 3
    # finding: before the fix, a mixed Fleet/land-army stack ordered via
    # Naval Hug Coastline from an origin the mover's own kingdom is
    # contesting toward a non-adjacent, enemy-owned target still
    # committed real mutation -- auto-boarding (101, 102) AND the
    # unboarded straggler's (103) own real recursive execute_move()
    # sub-move -- *before* the contested-province check ran and raised
    # IllegalMoveFromContestedError. turn/plan_dispatch.py run_leader_
    # plan() catches that exception per-phase with no rollback, so the
    # refused LMOVE used to still leave the rest of the turn boarded/
    # relocated as if it had gone through.
    state = _hug_state()
    state.add_kingdom(KingdomState(2, "Enemia", Race.HUMAN, Alignment.EVIL, HexCoord(5, 5)))
    state.provinces[HUG_ORIGIN].contested_by_kingdom_id = 1  # kingdom 1 is the mover
    state.provinces[HUG_TARGET].owner_kingdom_id = 2  # enemy-owned
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))
    state.add_army(ArmyState(104, 1, ArmyType.FLEET, Quality.AVERAGE, HUG_ORIGIN, movement_points=3))

    with pytest.raises(IllegalMoveFromContestedError):
        execute_move(
            state,
            kingdom_id=1,
            army_ids=[101, 102, 103, 104],
            target=HUG_TARGET,
            has_naval_hug_coastline=True,
            auto_board=True,
        )

    # Zero mutation: nobody boarded (not even the two, 101/102, that
    # would have fit the Fleet), and the would-be straggler (103) never
    # ran its own real recursive move.
    for army_id in (101, 102, 103, 104):
        assert state.armies[army_id].transported_by is None
        assert state.armies[army_id].location == HUG_ORIGIN


def test_execute_move_enforced_checks_the_real_chase_step_not_the_ultimate_target():
    # A 2-hex chase: FURTHER isn't adjacent to ORIGIN, so this call only
    # ever resolves the real single-hex hop toward it (through TARGET,
    # a Sea province) -- the gate must check that real hop, not the
    # eventual, further destination.
    state = _sea_transport_legality_state()
    further = HexCoord(3, 1)
    state.provinces[further] = ProvinceState(further, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1)
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    with pytest.raises(TransportIllegalMoveError) as excinfo:
        execute_move(state, kingdom_id=1, army_ids=[101], target=further, enforce_transport_legality=True)

    assert excinfo.value.origin_coord == ORIGIN
    assert excinfo.value.destination_coord == TARGET  # the real hop, not `further`


def test_execute_move_enforced_permits_a_mermen_carried_by_a_real_air_carrier():
    # Phase 738 closes the loop Phase 737 left open: can_board() now
    # accepts Mermen as air-carrier cargo, so this real, sourced
    # legality exemption is reachable via real automatic boarding, not
    # just directly-constructed state.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Coastia", Race.HUMAN, Alignment.GOOD, ORIGIN))
    state.add_province(ProvinceState(ORIGIN, Terrain.SEA, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, ORIGIN, movement_points=3))
    state.add_army(ArmyState(102, 1, ArmyType.MERMEN, Quality.AVERAGE, ORIGIN, movement_points=3))

    result = execute_move(
        state, kingdom_id=1, army_ids=[101, 102], target=TARGET, auto_board=True, enforce_transport_legality=True
    )

    assert result.moved is True
    assert state.armies[102].transported_by == 101


def test_army_move_is_blocked_into_an_explicitly_neutral_kingdoms_province():
    # RULES.AK [8.1]: a Neutral relation blocks an army's own move order
    # into the other Kingdom's territory -- the unit stays put, no battle.
    state = base_state()
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.NEUTRAL

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.moved is False
    assert result.battle_report is None
    assert result.blocked_by_neutral_relations is True
    assert result.stopped_chasing is True
    assert state.armies[101].location == ORIGIN
    assert state.armies[101].movement_points == 3


def test_lone_character_passes_freely_into_an_explicitly_neutral_kingdoms_province():
    state = base_state()
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.NEUTRAL
    state.add_leader(LeaderState(10, kingdom_id=1, name="Scout", location=ORIGIN))

    result = execute_move(state, kingdom_id=1, army_ids=[], target=TARGET, leader_id=10, rng=None)

    assert result.blocked_by_neutral_relations is False
    assert state.leaders[10].location == TARGET


def test_army_move_is_not_blocked_when_the_pair_has_no_explicit_relation_recorded():
    # A pair this project's own diplomacy logic has never touched keeps
    # today's pre-existing (attackable) behavior -- see the call site's
    # own comment for why this is deliberately narrower than
    # GameState.diplomatic_relation()'s own lenient "missing = Neutral"
    # default.
    state = base_state()

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.blocked_by_neutral_relations is False
    assert result.moved is True


def test_army_move_is_not_blocked_when_the_pair_is_explicitly_allied():
    state = base_state()
    state.allied_kingdoms.add(frozenset({1, 2}))

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.blocked_by_neutral_relations is False


def test_army_move_is_not_blocked_when_the_pair_is_explicitly_enemy():
    state = base_state()
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.blocked_by_neutral_relations is False


def test_triangle_guest_army_on_allied_host_territory_is_not_attacked():
    # [8.1]'s own "triangle" case: kingdom 1 (the mover/attacker, "Z")
    # moves into TARGET, owned by kingdom 3 ("X"), who is Allied with
    # kingdom 1 -- kingdom 2's ("Y") army is merely a guest there, and is
    # Enemy with kingdom 1, but X's own hospitality shields it: no battle.
    state = base_state()
    state.add_kingdom(KingdomState(3, "Xaria", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.provinces[TARGET].owner_kingdom_id = 3
    state.allied_kingdoms.add(frozenset({1, 3}))  # mover (1) allied with the host (3)
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))  # Y's guest army

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.moved is True
    assert result.battle_report is None
    assert state.armies[201].location == TARGET  # Y's army untouched


def test_apply_pending_mercenary_follows_relocates_at_the_end_and_clears_the_queue():
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))
    resolve_wandering_mercenary_following(state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET])

    moved = apply_pending_mercenary_follows(state)

    assert moved == [(301, ORIGIN, TARGET)]
    assert state.armies[301].location == TARGET
    assert state.pending_mercenary_follows == []


def test_apply_pending_mercenary_follows_skips_a_mercenary_hired_in_the_meantime():
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=2, is_mercenary=True))
    resolve_wandering_mercenary_following(state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET])
    state.armies[301].is_mercenary = False
    state.armies[301].kingdom_id = 1

    assert apply_pending_mercenary_follows(state) == []
    assert state.armies[301].location == ORIGIN


def test_a_second_general_departing_does_not_queue_the_same_mercenary_again():
    state = base_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, ORIGIN, movement_points=3, is_mercenary=True))
    first = resolve_wandering_mercenary_following(state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET])
    second = resolve_wandering_mercenary_following(state, ORIGIN, TARGET, state.provinces[ORIGIN], state.provinces[TARGET])

    assert first == [301]
    assert second == []
    assert state.pending_mercenary_follows == [(301, TARGET)]


# -- Mystic Winds: the led armies "move as an air unit" while the spell lasts --


def test_find_transport_illegality_wind_walking_army_crosses_the_sea_like_an_air_unit():
    legion = ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, ORIGIN)

    assert find_transport_illegality([legion], [1], _land_province(ORIGIN), _sea_province(TARGET)) == "insufficient_water_transport"
    assert (
        find_transport_illegality(
            [legion], [1], _land_province(ORIGIN), _sea_province(TARGET), wind_walking_army_ids=frozenset({1})
        )
        is None
    )


def test_find_transport_illegality_wind_walking_frees_dinosaurs_and_ents_from_the_shoreline():
    for army_type in (ArmyType.DINOSAURS, ArmyType.ENTS):
        army = ArmyState(1, 1, army_type, Quality.AVERAGE, ORIGIN)
        assert (
            find_transport_illegality(
                [army], [1], _land_province(ORIGIN), _sea_province(TARGET), wind_walking_army_ids=frozenset({1})
            )
            is None
        )


def test_find_transport_illegality_wind_walking_only_frees_the_listed_armies():
    flying = ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, ORIGIN)
    grounded = ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN)

    reason = find_transport_illegality(
        [flying, grounded],
        [1, 2],
        _land_province(ORIGIN),
        _sea_province(TARGET),
        wind_walking_army_ids=frozenset({1}),
    )

    assert reason == "insufficient_water_transport"


def test_execute_move_under_mystic_winds_crosses_the_sea_without_a_fleet():
    state = _sea_transport_legality_state()
    state.add_leader(LeaderState(1, 1, "Mage", ORIGIN, mystic_winds_active=True))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=5, commanded_by=1))

    result = execute_move(
        state, kingdom_id=1, army_ids=[101], leader_id=1, target=TARGET, enforce_transport_legality=True
    )

    assert result.moved is True
    assert state.armies[101].location == TARGET
    assert state.armies[101].transported_by is None  # nothing boarded: it flew on its own movement points


def test_execute_move_without_mystic_winds_still_needs_the_fleet():
    state = _sea_transport_legality_state()
    state.add_leader(LeaderState(1, 1, "Mage", ORIGIN))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=5, commanded_by=1))

    with pytest.raises(TransportIllegalMoveError):
        execute_move(state, kingdom_id=1, army_ids=[101], leader_id=1, target=TARGET, enforce_transport_legality=True)


def test_under_mystic_winds_a_fleet_and_its_would_be_cargo_each_move_alone():
    state = _sea_transport_legality_state()
    state.add_leader(LeaderState(1, 1, "Mage", ORIGIN, mystic_winds_active=True))
    state.add_army(ArmyState(101, 1, ArmyType.FLEET, Quality.AVERAGE, ORIGIN, movement_points=5, commanded_by=1))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=5, commanded_by=1))

    execute_move(
        state, kingdom_id=1, army_ids=[101, 102], leader_id=1, target=TARGET, auto_board=True, enforce_transport_legality=True
    )

    assert state.armies[102].transported_by is None  # no fleet transport takes place


# -- [11.1]: Fleets pay the extra movement point only for a battle --


def _landing_state(army_type: ArmyType, *, defended: bool = False) -> GameState:
    state = base_state()
    state.armies.clear()
    state.provinces[ORIGIN].terrain = Terrain.SEA
    state.add_army(ArmyState(101, 1, army_type, Quality.AVERAGE, ORIGIN, movement_points=3))
    if defended:
        state.add_army(ArmyState(201, 2, ArmyType.BOWMEN, Quality.GREEN, TARGET, movement_points=2))
    return state


@pytest.mark.parametrize("fleet_type", [ArmyType.FLEET, ArmyType.MERMEN])
def test_a_fleet_landing_on_an_undefended_enemy_province_pays_only_the_ordinary_point(fleet_type):
    state = _landing_state(fleet_type)

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.conquered is True
    assert state.armies[101].movement_points == 2  # 3 - 1: no conquest surcharge
    assert result.movement_points_spent == 1


def test_land_units_still_pay_the_conquest_point_for_the_same_landing():
    state = base_state()  # Bowmen walking into an undefended enemy province
    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=None)

    assert result.conquered is True
    assert state.armies[101].movement_points == 1  # 3 - 2


def test_a_fleet_that_fights_a_battle_pays_the_extra_point():
    state = _landing_state(ArmyType.FLEET, defended=True)

    result = execute_move(state, kingdom_id=1, army_ids=[101], target=TARGET, rng=random.Random(1))

    assert result.battle_report is not None
    assert 101 not in state.armies or state.armies[101].movement_points == 1  # 3 - 1 - 1
