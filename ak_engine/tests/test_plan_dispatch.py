from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import patch

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.office import Office
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.army_list_decode import ArmyListRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.move_execution import MoveExecutionResult, TransportIllegalMoveError
from ak_engine.turn.office_holder import OfficeHolder
from ak_engine.turn.plan_dispatch import (
    ArmyListExecutionResult,
    FireExecutionResult,
    HireExecutionResult,
    NoOpResult,
    UnsupportedActionError,
    _is_undead_king,
    _resolve_nested_plan_leader_id,
    dispatch_phase,
    run_leader_plan,
)
from ak_engine.turn.aspy_defend_decode import DefendRequest
from ak_engine.turn.aspy_execution import SpyReport
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult
from ak_engine.turn.challenge_execution import ChallengeExecutionResult
from ak_engine.turn.practice_execution import PracticeExecutionResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.random_encounter_execution import RandomEncounterResult
from ak_engine.turn.recruit_execution import RecruitExecutionResult
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.trade_execution import CuratorResearchResult, TradeExecutionResult
from ak_engine.turn.trail_execution import TrailExecutionResult
from ak_engine.turn.use_mi_execution import UseMIExecutionResult

from _helpers import ScriptedRandom

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
BOARD_WIDTH = 10
LEADER_ID = 1


def _state_with_army(
    location: HexCoord, target_terrains: dict[HexCoord, Terrain], *, treasury: int = 100
) -> tuple[GameState, int]:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, location, treasury=treasury))
    # The Give Gold 10% cap's own basis (2026-11-04) -- a real run_turn()
    # call snapshots this at the very start of the turn; direct
    # dispatch_phase() callers like this helper simulate "this call is
    # the first Give of a fresh turn" by matching it to treasury.
    state.kingdoms[1].treasury_at_turn_start = treasury
    state.add_province(ProvinceState(location, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    for coord, terrain in target_terrains.items():
        state.add_province(ProvinceState(coord, terrain, Race.HUMAN))
    # is_king=True: most tests using this helper predate Phase 40's
    # King-vs-Hero co-location enforcement and were never about testing
    # that restriction -- treating this shared leader as the King
    # preserves their original intent. Tests that specifically exercise
    # Hero co-location build their own LeaderState with is_king=False.
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", location, is_king=True))
    army_id = 1
    state.add_army(
        ArmyState(army_id, 1, ArmyType.BOWMEN, Quality.AVERAGE, location, movement_points=5, commanded_by=LEADER_ID)
    )
    return state, army_id


def test_dispatch_lmove_decodes_hex_number_and_moves():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)  # hex number 94, adjacent to origin on the odd-r grid
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert isinstance(result, MoveExecutionResult)
    assert result.moved is True
    assert state.armies[army_id].location == target
    assert state.leaders[LEADER_ID].location == target


def test_dispatch_lmove_derives_army_ids_from_leader_command():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.moved is True
    assert state.armies[army_id].location == target


def test_dispatch_lmove_leader_can_move_alone_without_triggering_battle():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {})
    state.add_province(ProvinceState(target, Terrain.PLAINS, Race.HUMAN))
    # An enemy army occupies the target, but the leader brings none of
    # their own -- rulebook [3.1]: combat only occurs if the mover has an army.
    state.add_army(ArmyState(99, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, target))
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert result.moved is True
    assert result.battle_report is None
    assert state.leaders[LEADER_ID].location == target
    assert state.armies[army_id].location == origin  # left behind, wasn't brought along


def test_dispatch_lmove_senses_magic_items_for_the_arch_mage():
    # Phase 490: Office.MAGE's own "Sense Magic Items in Province" perk
    # (CARICHE E ABLITA.txt) -- another leader's own Spell Wand, sitting
    # in the province the Arch-Mage just moved into, is sensed.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=LEADER_ID)  # meets OFFICE_MIN_POINTS[Office.MAGE]
    other_leader = LeaderState(99, 2, "Other", target)
    state.add_leader(other_leader)
    sensed_item = state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=99)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert result.moved is True
    assert result.sensed_magic_items == [sensed_item.treasure]


def test_dispatch_lmove_sensed_magic_items_is_none_without_the_office():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    other_leader = LeaderState(99, 2, "Other", target)
    state.add_leader(other_leader)
    state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=99)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert result.moved is True
    assert result.sensed_magic_items is None


def test_dispatch_lmove_wires_difficult_terrain_from_the_leaders_own_advanced_ability():
    # Phase 507: the same real per-leader signal reaches Move's own
    # partial-exploration side effect too -- Plains(50)+10=60, halved
    # (partial=True) to 30, times (skill 0 + 1) = 30%, not the base 25%.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=0
    )

    assert state.provinces[target].explored_percent == 30


def test_dispatch_explore_uses_leader_location():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=1
    )

    assert result.new_percent == 100  # Plains(50) * (skill 1 + 1) = 100
    assert state.provinces[location].explored_percent == 100
    # Phase 630: Ranger of the Plains (Office.PLAINS_KING) merit.
    assert state.leaders[LEADER_ID].merit_tally.plains_explorations == 1


def test_dispatch_explore_reveal_adjacent_provinces_uses_the_real_board_size():
    # Phase 780: dispatch_phase()'s own EXPLORE branch used to hardcode
    # MapBounds(*NORMAL_MAP_BOUNDS) (30, 15) for reveal_adjacent_
    # provinces() regardless of the real board_width this function
    # already receives -- now it reads state.board_width/.board_height
    # (via dispatch_phase()'s own board_width=None fallback) whenever
    # board_width isn't explicitly overridden by the caller.
    #
    # neighbors() never wraps around -- it drops a candidate outright
    # once it falls outside MapBounds.contains() -- so a deliberately
    # tiny board_width makes a real, in-range-under-the-old-wrong-30-
    # width "neighbor" fall correctly out of bounds instead.
    location = HexCoord(2, 4)
    state, army_id = _state_with_army(location, {HexCoord(1, 4): Terrain.PLAINS, HexCoord(3, 4): Terrain.DESERT})
    state.board_width = 3  # location.x == board_width - 1: the true right edge
    state.board_height = 15
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], explorer_skill=1)

    # (1, 4) is a real, in-bounds neighbor under the small board -> revealed.
    assert state.provinces[HexCoord(1, 4)].known_to_kingdom(1)
    # (3, 4) would only be "in bounds" under the old, wrong (30, 15)
    # default -- under the real board_width=3 it's genuinely off the
    # map, so it must NOT be revealed.
    assert not state.provinces[HexCoord(3, 4)].known_to_kingdom(1)


def test_dispatch_explore_wires_difficult_terrain_from_the_leaders_own_advanced_ability():
    # Phase 507: dispatch_phase() derives has_difficult_terrain from the
    # acting leader's own real AdvancedAbility possession -- Plains(50)
    # + 10 = 60, times (skill 0 + 1) = 60%, not the base 50%.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=0
    )

    assert result.new_percent == 60


def test_dispatch_explore_wires_military_maps_from_the_leaders_own_advanced_ability():
    # Phase 507: Military Maps raises the cap 100->200, letting a
    # heavily-explored province keep gaining beyond the ordinary cap.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.EXPLORER_MILITARY_MAPS)
    state.provinces[location].explored_percent = 150
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=4
    )

    assert result.new_percent == 200


def test_dispatch_explore_wires_find_mines_from_the_leaders_own_advanced_ability():
    # Phase 509: dispatch_phase() derives has_find_mines the same way as
    # Military Maps/Difficult Terrain -- Mountains gives a real chance to
    # roll a mine on the leader's own (kingdom_id-owned) province.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.provinces[location].terrain = Terrain.MTNS
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.EXPLORER_FIND_MINES)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=ScriptedRandom([0.0, 0.5]),
    )

    assert state.provinces[location].mine_find_attempts == 1
    assert 1 <= state.provinces[location].mine_gold_bonus <= 3


def test_dispatch_explore_does_not_roll_find_mines_without_the_advanced_ability():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.provinces[location].terrain = Terrain.MTNS
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=ScriptedRandom([0.0]),
    )

    assert state.provinces[location].mine_find_attempts == 0
    assert state.provinces[location].mine_gold_bonus == 0


def test_dispatch_lmove_wires_march_cavalry_from_the_leaders_own_advanced_ability():
    # Phase 521: dispatch_phase() derives has_march_cavalry the same way
    # as Military Maps/Difficult Terrain/Find Mines -- a 3+ movement-point
    # land army gets AdvancedAbility.MARCH_CAVALRY's own bonus applied
    # before this move's own cost is deducted.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.MARCH_CAVALRY)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert state.armies[army_id].march_bonus_applied_this_turn is True


def test_dispatch_lmove_wires_march_cavalry_true_mastery_from_the_leaders_own_advanced_ability():
    # Phase 768: same real-possession pattern as MARCH_CAVALRY's own
    # sibling test above, for Cavalry's own 3rd stacking tier -- the
    # army's own movement pool (5, already >= the Cavalry band) gets a
    # full +3, not the +1/+2 a lower tier would grant.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert state.armies[army_id].march_bonus_applied_this_turn is True
    # 5 (start) + 3 (Cavalry True Mastery) - 2 (base move + uncontested
    # conquest) == 6.
    assert state.armies[army_id].movement_points == 6


def test_dispatch_lmove_wires_march_through_floods_from_the_leaders_own_advanced_ability():
    # Phase 693: dispatch_phase() derives has_march_through_floods the
    # same real-possession pattern as the other March members -- a land
    # army entering a Flood-affected province pays the extra movement
    # point deduction.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    state.provinces[target].owner_kingdom_id = 1  # no conquest -- base cost stays 1
    state.provinces[target].terrain_override = Terrain.SEA
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.MARCH_THROUGH_FLOODS)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert state.armies[army_id].movement_points == 3  # 5 - base(1) - flood(1)


def test_dispatch_lmove_wires_naval_skill_level_from_the_leaders_own_naval_ability():
    # Phase 523: dispatch_phase() derives naval_skill_level from the
    # leader's own real effective_skill_level(Ability.NAVAL) -- a Fleet
    # gets the bonus applied before this move's own cost is deducted.
    # Phase 737: target is Sea, not Plains -- a Fleet can enter/exit a
    # land province on its own, but not hop directly land-to-land.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.SEA})
    state.armies[army_id] = ArmyState(
        army_id, 1, ArmyType.FLEET, Quality.AVERAGE, origin, movement_points=5, commanded_by=LEADER_ID
    )
    raw_values = [0] * 30
    raw_values[Ability.NAVAL.value * 2] = 3  # skill level 3
    state.leaders[LEADER_ID].skills = SkillTable(raw_values=raw_values)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert state.armies[army_id].naval_bonus_applied_this_turn is True


def test_dispatch_lmove_wires_march_skill_level_from_the_leaders_own_march_ability():
    # Phase 764: dispatch_phase() derives march_skill_level from the
    # leader's own real effective_skill_level(Ability.MARCH) -- a land
    # army gets [4.12] MARCH TABLE's own raw-skill-level bonus applied
    # before this move's own cost is deducted.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    state.armies[army_id] = ArmyState(
        army_id, 1, ArmyType.BOWMEN, Quality.AVERAGE, origin, movement_points=5, commanded_by=LEADER_ID
    )
    raw_values = [0] * 30
    raw_values[Ability.MARCH.value * 2] = 2  # skill level 2 -- Speed 1-2 column gives +1
    state.leaders[LEADER_ID].skills = SkillTable(raw_values=raw_values)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert state.armies[army_id].march_table_bonus_applied_this_turn is True


def test_dispatch_lmove_enforces_transport_legality():
    # Phase 737: dispatch_phase()'s own real LMOVE branch passes
    # enforce_transport_legality=True into execute_move() -- an
    # unassisted land army crossing onto Sea terrain is refused here,
    # unlike a direct execute_move() call (which defaults to False and
    # would let this same crossing through, see test_move_execution.py).
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.SEA})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    with pytest.raises(TransportIllegalMoveError):
        dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)


def test_dispatch_explore_wires_society_maps_from_the_leaders_own_advanced_ability():
    # Phase 510: dispatch_phase() derives has_find_mines/-society-maps
    # the same way as Military Maps/Difficult Terrain -- 0-2 maps
    # revealed to the acting kingdom on a real EXPLORE action.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    for i in range(5):
        state.add_province(ProvinceState(HexCoord(i, 20), Terrain.PLAINS, Race.HUMAN))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.EXPLORERS_SOCIETY_MAPS)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert 0 <= len(result.society_maps_revealed) <= 2


def test_dispatch_lmove_does_not_wire_society_maps():
    # Phase 510: deliberately EXPLORE-only -- Society Maps' own two
    # rulebook triggers are "Practices Exploration" and "Explores a
    # province," not Move's partial-exploration side effect.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    for i in range(5):
        state.add_province(ProvinceState(HexCoord(i, 20), Terrain.PLAINS, Race.HUMAN))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.EXPLORERS_SOCIETY_MAPS)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    for coord in (HexCoord(i, 20) for i in range(5)):
        assert 1 not in state.provinces[coord].explored_percent_by_kingdom


def test_dispatch_explore_does_not_reveal_society_maps_without_the_advanced_ability():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    for i in range(5):
        state.add_province(ProvinceState(HexCoord(i, 20), Terrain.PLAINS, Race.HUMAN))
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert result.society_maps_revealed == []


def test_dispatch_explore_also_records_the_kingdoms_own_exploration():
    # Phase 69: alongside the pre-existing shared explored_percent scalar.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=1
    )

    assert state.provinces[location].explored_percent_by_kingdom[1] == 100


def test_dispatch_explore_also_rolls_feature_discovery():
    # Phase 242: EXPLORE dispatch now also rolls discover_features() for
    # any feature already present in the province.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=1, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    # Plains(50) * (skill 1 + 1) = 100% -- guaranteed discovery.
    result = dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert feature.discovery_level(1) == 3
    # Phase 245: the dispatch result now surfaces which features were
    # just discovered, closing the "rolled but thrown away" gap so a
    # report layer can narrate them (describe_feature_discovery()).
    assert result.discovered_features == [feature]


def test_dispatch_explore_credits_chancellor_merit_when_first_to_discover():
    # Phase 256: nobody else has discovered this feature yet, so the
    # acting leader's own Chancellor Merit Point tally is credited.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=1, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert state.leaders[LEADER_ID].merit_tally.features_discovered_first == 1


def test_dispatch_explore_does_not_credit_merit_when_another_kingdom_already_found_it():
    # Phase 256: a rival kingdom's own entry already sits in
    # Feature.discovered_by_kingdom -- this kingdom wasn't first, so no
    # Merit Point credit, even though it does discover the feature too.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=1, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    feature.discovered_by_kingdom[2] = 3
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert feature.discovery_level(1) == 3  # this kingdom did discover it...
    assert state.leaders[LEADER_ID].merit_tally.features_discovered_first == 0  # ...but wasn't first


def test_dispatch_lmove_also_rolls_rumor_generation_for_a_nearby_feature():
    # Phase 243: LMOVE is one of the 7 rumor-eligible order types (20%
    # chance). A feature 1 hex away from the mover's own pre-move
    # location is eligible (distance 0 -- the destination itself --
    # would just be found by Explore, not rumored about).
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)  # adjacent to origin
    nearby = HexCoord(2, 9)  # 1 hex from origin, distinct from target
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS, nearby: Terrain.PLAINS})
    feature = Feature(feature_id=1, coord=nearby, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    # trigger roll 0.0 < 0.20 -> succeeds; candidate choice index 0; content
    # roll (guardian-only feature) is skipped; is_true roll 0.0 -> True.
    # Phase 768: trailing 0.5, 0.5 account for execute_move()'s own
    # Move-triggered March/Naval experience credit, consumed inside
    # execute_move() -- called by dispatch_phase() *after* its own
    # rumor-generation hook already rolled the two values above.
    rng = ScriptedRandom([0.0, 0.0, 0.5, 0.5], choice_indices=[0])
    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, rng=rng
    )

    assert len(state.rumors) == 1
    rumor = next(iter(state.rumors.values()))
    assert rumor.feature_id == feature.feature_id
    assert rumor.kingdom_id == 1


def test_dispatch_lmove_without_nearby_features_generates_no_rumor():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert state.rumors == {}


def test_dispatch_search_reports_feature_not_found():
    # Phase 132: SEARCH now actually executes -- with no feature 20
    # registered in GameState, execute_search() reports why rather than
    # merely decoding the request (see turn/search_execution.py).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 0, 11, 0, 22, 0, 7, 9, 13, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SearchExecutionResult)
    assert result.accepted is False
    assert result.reason == "feature not found"


def test_dispatch_search_stamps_the_request_onto_the_result():
    # Phase 213: same reasoning as test_dispatch_pursue_stamps_the_request_onto_the_result.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 0, 11, 0, 22, 0, 7, 9, 13, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.feature_id == 20


def test_dispatch_search_resolves_real_melee_combat_against_a_sourced_guardian():
    # A feature guarded by a Monster with real MONSTER_STATS + a Melee
    # tactic in the Encounter Plan resolves a real duel via turn/
    # encounter.py (Phase 132).
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_feature(Feature(feature_id=20, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 9, -1])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, SearchExecutionResult)
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner in ("leader", "monster")


def test_dispatch_search_leader_victory_marks_feature_looted():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=20, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    # Give the leader a strong Melee skill so a low-variance rng favors them.
    state.leaders[LEADER_ID].skills = None
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 9, -1])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(1)
    )

    assert result.combat_resolved is True
    if result.winner == "leader":
        assert feature.looted is True
        assert LEADER_ID in state.leaders
    else:
        # Phase 259: this leader is a King (see _state_with_army's own
        # comment) -- a King's death owes a Royal Heir under the same
        # leader_id rather than leaving the Kingdom leaderless, but not
        # installed until install_pending_royal_heirs() runs (2026-11-18
        # bug fix, user-confirmed).
        assert LEADER_ID in state.dead_leaders
        assert LEADER_ID not in state.leaders
        state.install_pending_royal_heirs()
        assert state.leaders[LEADER_ID].is_royal_heir is True


def test_real_move_file_leader_search_phase_dispatches():
    # Leader 42 ("Garin") in AK3__T10.K1 has a real Search phase (P2):
    # "P2 : 2 20 0 0 11 0 22 0 7 9 13 -1" -> Search feature 20. No
    # feature 20 is registered in this bare test GameState (world
    # generation isn't modeled -- see models/feature.py), so execution
    # honestly reports it can't find the target.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T10.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 42)
    search_phase = leader.plan.segments[0].phases["P2"]
    assert search_phase.action == ActionCode.SEARCH

    state, army_id = _state_with_army(HexCoord(3, 9), {})

    result = dispatch_phase(search_phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SearchExecutionResult)
    assert result.accepted is False
    assert result.reason == "feature not found"


def test_dispatch_trade_reports_recipient_not_found():
    # Phase 133: TRADE now actually executes via execute_give() -- with
    # no leader 3 registered, it reports why rather than merely
    # decoding the request (see turn/trade_execution.py).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=42, extra=[0, 3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)
    assert result.applied is False
    assert result.reason == "recipient not found"


def test_dispatch_trade_gold_give_succeeds_between_two_co_located_kings():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {}, treasury=1000)
    recipient_id = 2
    state.add_kingdom(KingdomState(2, "Recipient", Race.HUMAN, Alignment.GOOD, location, treasury=0))
    state.add_leader(LeaderState(recipient_id, 2, "Recipient King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=100, extra=[0, recipient_id])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)
    assert result.applied is True
    assert result.gold_transferred == 100
    assert state.kingdoms[1].treasury == 900
    assert state.kingdoms[2].treasury == 100


def test_dispatch_trade_stamps_the_request_onto_the_result():
    # Phase 214: same reasoning as test_dispatch_pursue_stamps_the_request_onto_the_result.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {}, treasury=1000)
    recipient_id = 2
    state.add_kingdom(KingdomState(2, "Recipient", Race.HUMAN, Alignment.GOOD, location, treasury=0))
    state.add_leader(LeaderState(recipient_id, 2, "Recipient King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=100, extra=[0, recipient_id])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.target_leader_id == recipient_id


def test_dispatch_trade_self_targeted_secret_spell_ordinal_rewrites_to_cast():
    # Phase 397: DEF2.PAS's own Trade branch reclassifies a self-targeted
    # Give of a secret-spell ordinal (25-34) into a Cast -- see
    # turn/trade_decode.py's module docstring. Gate Angel is a
    # NO_TARGET_SPELLS member, so the rewrite's own forced target=0
    # doesn't get in its way here.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[LEADER_ID, 3])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, CastExecutionResult)
    assert result.request.spell == Spell.GATE_ANGEL
    assert result.request.target == 0


def test_dispatch_trade_self_targeted_secret_spell_zeroes_a_normally_targeted_spells_target():
    # Scar Terrain ordinarily needs a real province target -- the Trade->Cast
    # rewrite forces target=0 regardless (DEF2.PAS: lextra[m] := 0), so it
    # faithfully fails at execution rather than being "fixed" to keep working.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.SCAR_TERRAIN), extra=[LEADER_ID, 3])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, CastExecutionResult)
    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_dispatch_trade_self_targeted_secret_spell_rewrite_by_a_dead_leader_is_a_clean_refusal():
    # Phase 1046 bug fix: this Trade->Cast rewrite call site is the
    # second of the two real places that called execute_cast() with no
    # acting-leader liveness check (the other being _dispatch_cast()
    # itself) -- see execute_cast()'s own Phase 1046 addendum. A leader
    # who died earlier this same turn but still has a later-phase Trade
    # order rewritten into a secret-spell Cast used to reach a bare
    # state.leaders[leader_id] lookup inside one of Cast's own _execute_*
    # handlers and raise an unhandled KeyError.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    del state.leaders[LEADER_ID]  # died in an earlier phase this same turn
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[LEADER_ID, 3])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, CastExecutionResult)
    assert result.applied is False
    assert result.reason == "acting leader not found"


def test_dispatch_trade_ordinary_give_of_a_secret_spell_ordinal_is_not_rewritten():
    # Same obj range, but not self-targeted (extra[0] != leader_id) -- an
    # ordinary Give to leader 3 of "item/gold 25", not a Cast rewrite.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {}, treasury=1000)
    recipient_id = 3
    state.add_kingdom(KingdomState(2, "Recipient", Race.HUMAN, Alignment.GOOD, location, treasury=0))
    state.add_leader(LeaderState(recipient_id, 2, "Recipient King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[0, recipient_id])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)


def test_dispatch_trade_self_targeted_ordinary_gold_amount_is_not_rewritten():
    # Self-targeted, but obj (24) is below the secret-spell range -- an
    # ordinary (if unusual) self-Give, not a rewrite trigger.
    state, army_id = _state_with_army(HexCoord(3, 9), {}, treasury=1000)
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=24, extra=[LEADER_ID, LEADER_ID])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)


def test_dispatch_trade_curator_titleholder_self_give_researches_the_item():
    # Phase 667: Office.CURATOR -- "the character must have an order to
    # give the magic item number to himself." obj (200) is well outside
    # the secret-spell range (25-34), so the Phase 397 rewrite above
    # doesn't fire -- this reaches _dispatch_trade()'s own new routing.
    state, army_id = _state_with_army(HexCoord(3, 9), {}, treasury=1000)
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=LEADER_ID)
    state.add_item(Treasure.BOOK_WHITE, owner_leader_id=LEADER_ID)
    state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=LEADER_ID)  # meets OFFICE_MIN_POINTS[Office.CURATOR]
    researched = state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=None)  # unowned -- "any item in the world"
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=researched.item_id, extra=[LEADER_ID, LEADER_ID])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, CuratorResearchResult)
    assert result.applied is True
    assert result.treasure is Treasure.AMULET_ANTI_ELEMENTAL
    assert result.request is not None
    assert result.request.target_leader_id == LEADER_ID


def test_dispatch_trade_self_give_without_the_curator_title_is_not_rewritten():
    # Same self-targeted shape, but the leader doesn't hold the title --
    # falls through to the ordinary (if unusual) self-Give path.
    state, army_id = _state_with_army(HexCoord(3, 9), {}, treasury=1000)
    item = state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=None)
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=item.item_id, extra=[LEADER_ID, LEADER_ID])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)


def test_dispatch_practice_executes_and_mutates_leader_skills():
    # Phase 44: PRACTICE now actually executes (always resolved as solo
    # practice -- see turn/practice_execution.py's module docstring).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=14, extra=[0])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, PracticeExecutionResult)
    assert result.ability == Ability.SAGE
    assert result.not_implemented_for_ability is False
    # LEADER_ID had no skills recorded -- execute_practice attaches a
    # fresh all-zero SkillTable and rolls against it.
    assert state.leaders[LEADER_ID].skills is not None
    assert state.leaders[LEADER_ID].skills.pair_for_ability(Ability.SAGE) == (result.new_skill, result.new_aptitude)


def test_real_move_file_leader_practice_phase_dispatches():
    # Leader 1 (the King) in AK3__T1.K1 has real Practice phases (P0-P2):
    # "P0 : 12 6 0" -> Practice Necromancy.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)
    practice_phase = leader.plan.segments[0].phases["P0"]
    assert practice_phase.action == ActionCode.PRACTICE

    state, army_id = _state_with_army(HexCoord(3, 9), {})

    result = dispatch_phase(
        practice_phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, PracticeExecutionResult)
    assert result.ability == Ability.NECROMANCY


def test_dispatch_wait_no_action_move_abort_are_bare_noops():
    state, army_id = _state_with_army(HexCoord(3, 9), {})

    for action in (ActionCode.WAIT, ActionCode.NO_ACTION, ActionCode.MOVE_ABORT):
        phase = PlanPhase(label="P0", action=action, obj=0, extra=[])

        result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

        assert result == NoOpResult(action=action)

    # Genuinely inert: nothing about the state changed.
    assert state.armies[army_id].location == HexCoord(3, 9)
    assert state.kingdoms[1].treasury == 100


def test_dispatch_cast_holy_symbol_is_not_executed():
    # Holy_Symbol is one of the ten Personal-Combat-only spells -- see
    # cast_execution.py's module docstring for why those have no
    # Action-Cast dispatch branch (unlike Hide_Feature/Clairvoyance,
    # which gained real execution in Phase 193).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.CAST, obj=int(Spell.HOLY_SYMBOL), extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, CastExecutionResult)
    assert result.request.spell == Spell.HOLY_SYMBOL
    assert result.applied is False
    assert result.reason == "spell effect not modeled"


def test_dispatch_cast_charm_assigns_colocated_target_to_casters_kingdom():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(78, None, "Wandering Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.CAST, obj=12, extra=[78])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, CastExecutionResult)
    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_real_move_file_leader_cast_phase_dispatches():
    # Leader 1 (the King) in AK3__T10.K1 has a real Cast phase (P1):
    # "P1 : 9 12 78" -> Cast Charm targeting character 78.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T10.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)
    cast_phase = leader.plan.segments[0].phases["P1"]
    assert cast_phase.action == ActionCode.CAST

    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(78, None, "Wandering Hero", location))

    result = dispatch_phase(cast_phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, CastExecutionResult)
    assert result.request.spell == Spell.CHARM
    assert result.request.target == 78
    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_dispatch_use_mi_reports_an_unowned_item_id():
    # Phase 141: USE_MI now actually executes -- an item id nobody in
    # this GameState.items registry actually owns fails cleanly instead
    # of just handing back the raw decoded request.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=31, extra=[97])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, UseMIExecutionResult)
    assert result.applied is False
    assert result.reason == "item not found"


def test_dispatch_use_mi_reads_a_real_skill_book():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    item = state.add_item(Treasure.BOOK_MELEE, owner_leader_id=LEADER_ID)
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=item.item_id, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, UseMIExecutionResult)
    assert result.applied is True
    assert result.ability_boosted is Ability.MELEE
    assert item.item_id not in state.items


def test_dispatch_challenge_executes_and_reports_target_not_found():
    # Phase 54: CHALLENGE now dispatches to execute_challenge, not just
    # decode_challenge_phase -- target 88 doesn't exist in this fixture.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.CHALLENGE, obj=88, extra=[0, 9, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ChallengeExecutionResult)
    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_dispatch_challenge_executes_a_real_encounter_when_target_exists():
    # Challenger is an armyless Hero (not the shared King fixture leader),
    # so is_encounter_accepted's "Heroes... can always be Encountered by
    # other Heroes" branch applies deterministically (no rng consumed for
    # acceptance) -- only the resulting duel's winner is left to chance.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_kingdom(KingdomState(2, "Otheria", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_leader(LeaderState(LEADER_ID, kingdom_id=1, name="Challenger", location=HexCoord(3, 9)))
    state.add_leader(LeaderState(88, kingdom_id=2, name="Target", location=HexCoord(3, 9)))
    phase = PlanPhase(label="P0", action=ActionCode.CHALLENGE, obj=88, extra=[0, 9, -1])  # tactic 9 = Melee

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ChallengeExecutionResult)
    assert result.accepted is True
    assert result.combat_occurred is True


def test_dispatch_pursue_executes_and_reports_target_not_found():
    # Phase 54: PURSUE now dispatches to execute_pursue, not just
    # decode_pursue_phase -- target 88 doesn't exist in this fixture.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=88, extra=[0, 9, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, PursueExecutionResult)
    assert result.caught_up is False
    assert result.reason == "pursuer or target not found"


def test_dispatch_pursue_stamps_the_request_onto_the_result():
    # Phase 213: report/turn_report.py describe_turn_results() needs the
    # target's own id to resolve a display name -- the dispatcher (not
    # execute_pursue() itself) stamps it.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=88, extra=[0, 9, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.target_character_id == 88


def test_dispatch_pursue_wires_spy_super_sleuth_from_the_leaders_own_advanced_ability():
    # Phase 695: dispatch_phase() derives has_spy_super_sleuth the same
    # real-possession pattern as every other AdvancedAbility flag -- a
    # far-away, different-Kingdom target (a near-certain-fail catch-up
    # roll) still catches up unconditionally with the ability. Both
    # sides armyless -- [3.16]'s own "leads an army" match requirement
    # would otherwise reject the order via a different, unrelated path.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_kingdom(KingdomState(2, "Fleeland", Race.HUMAN, Alignment.GOOD, HexCoord(20, 9)))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", HexCoord(3, 9)))
    state.add_leader(LeaderState(88, kingdom_id=2, name="Target", location=HexCoord(20, 9)))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.SPY_SUPER_SLEUTH)
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=88, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.caught_up is True
    assert result.guessed_distance is not None


def test_dispatch_aspy_executes_and_reports_the_casters_own_province():
    # Phase 62: ASPY now dispatches to execute_aspy, not just
    # decode_aspy_phase -- the report is always for the caster's own
    # current province, per rulebook [3.14] ("a character may only Spy
    # on a province he is actually in"), regardless of the raw obj value.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SpyReport)
    assert result.province == HexCoord(3, 9)
    assert result.owner_kingdom_id == 1
    assert result.is_capital is True


def test_dispatch_aspy_without_know_alignment_talent_estimates_imperfectly():
    # Phase 495: without AdvancedAbility.KNOW_ALIGNMENT_TALENT, the
    # caster's own estimate is nudged by the real REPORTS.PAS Align_Est
    # parity formula, not the spotted leader's own true alignment --
    # deterministic given both ids (no RNG involved), see intelligence_
    # estimate.py's own module docstring. Agent (LEADER_ID=1, odd) vs. a
    # spotted leader with an even id -> nudge = true_ordinal + 0 - 1,
    # landing on Alignment.DRUID (ordinal 2) for a true Alignment.NEUTRAL
    # (ordinal 3) target.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_kingdom(KingdomState(2, "Spied", Race.HUMAN, Alignment.NEUTRAL, HexCoord(3, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Spotted", location=HexCoord(3, 9)))
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SpyReport)
    spotted = result.spotted_characters[0]
    assert spotted.leader_id == 2
    assert spotted.estimated_alignment is Alignment.DRUID


def test_dispatch_aspy_with_know_alignment_talent_reports_the_true_alignment():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.KNOW_ALIGNMENT_TALENT)
    state.add_kingdom(KingdomState(2, "Spied", Race.HUMAN, Alignment.NEUTRAL, HexCoord(3, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Spotted", location=HexCoord(3, 9)))
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SpyReport)
    spotted = result.spotted_characters[0]
    assert spotted.leader_id == 2
    assert spotted.estimated_alignment is Alignment.NEUTRAL


def test_dispatch_aspy_psychic_mage_holder_reports_perfect_temper_too():
    # Phase 660: Office.PSYCHIC_MAGE's own real "knows their exact
    # alignment and temper" title text -- unlike KNOW_ALIGNMENT_TALENT
    # (alignment only), this also grants perfect *temper* detection, so
    # this test checks temper specifically to prove the new wiring
    # (not just an alignment path already covered by the two tests above).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.leaders[LEADER_ID].merit_tally.psychic_spell_casts = 20  # OFFICE_MIN_POINTS[PSYCHIC_MAGE]
    state.add_kingdom(KingdomState(2, "Spied", Race.HUMAN, Alignment.NEUTRAL, HexCoord(3, 9)))
    spotted_leader = LeaderState(2, kingdom_id=2, name="Spotted", location=HexCoord(3, 9))
    spotted_leader.temper = Temper.BRAVE
    state.add_leader(spotted_leader)
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SpyReport)
    spotted = result.spotted_characters[0]
    assert spotted.estimated_alignment is Alignment.NEUTRAL
    assert spotted.estimated_temper is Temper.BRAVE


def test_dispatch_aspy_without_psychic_mage_title_estimates_temper_imperfectly():
    # Deterministic REPORTS.PAS Temper_Est nudge (no RNG): target_id=3,
    # agent_birth_x=0 (the default), true Temper.BRAVE -> nudged to
    # Temper.BERSERK, proving the estimate is genuinely imperfect here
    # (not every target id happens to diverge from its own true value).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_kingdom(KingdomState(2, "Spied", Race.HUMAN, Alignment.NEUTRAL, HexCoord(3, 9)))
    spotted_leader = LeaderState(3, kingdom_id=2, name="Spotted", location=HexCoord(3, 9))
    spotted_leader.temper = Temper.BRAVE
    state.add_leader(spotted_leader)
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    spotted = result.spotted_characters[0]
    assert spotted.estimated_temper is Temper.BERSERK


def test_dispatch_aspy_wires_druidic_animal_spies_from_the_leaders_own_advanced_ability():
    # Phase 694: dispatch_phase() derives caster_has_druidic_animal_spies
    # the same real-possession pattern as KNOW_ALIGNMENT_TALENT/PSYCHIC_
    # MAGE above -- an adjacent province's own military forces are only
    # reported when the caster holds the Advanced Ability.
    origin = HexCoord(3, 9)
    neighbor = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {neighbor: Terrain.FOREST})
    state.add_army(ArmyState(99, 2, ArmyType.AXEMEN, Quality.AVERAGE, neighbor))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.DRUIDIC_ANIMAL_SPIES)
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert neighbor in result.adjacent_military_forces
    assert len(result.adjacent_military_forces[neighbor]) == 1


def test_dispatch_aspy_wires_spy_expanded_spying_from_the_leaders_own_advanced_ability():
    # Phase 705: dispatch_phase() derives caster_has_spy_expanded_spying
    # the same real-possession pattern as Druidic Animal Spies above --
    # a Feature's own discovery level, as known to the province's real
    # owner, is only reported when the caster holds the Advanced Ability.
    origin = HexCoord(3, 9)
    state, army_id = _state_with_army(origin, {})  # origin's own owner_kingdom_id is 1
    state.add_feature(Feature(1, origin, FeatureType.TOWER, discovered_by_kingdom={1: 3}))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.SPY_EXPANDED_SPYING)
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.features_known_to_owner == {1: 3}


def test_dispatch_defend_is_decode_only():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DEFEND, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, DefendRequest)
    assert result.target_province == 304


def test_dispatch_trail_executes_and_reports_target_not_found():
    # Phase 54: TRAIL now dispatches to execute_trail, not just
    # decode_trail_phase -- target 88 doesn't exist in this fixture.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TrailExecutionResult)
    assert result.spied_on is False
    assert result.reason == "trailer or target not found"


def test_dispatch_trail_stamps_the_request_onto_the_result():
    # Phase 213: same reasoning as test_dispatch_pursue_stamps_the_request_onto_the_result.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.target_character_id == 88


def test_dispatch_trail_wires_spy_super_sleuth_from_the_leaders_own_advanced_ability():
    # [3.17]'s own no-army restriction means the trailer can't be the
    # shared army-commanding leader _state_with_army() builds -- a
    # fresh, armyless leader is needed here instead.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_kingdom(KingdomState(2, "Fleeland", Race.HUMAN, Alignment.GOOD, HexCoord(20, 9)))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", HexCoord(3, 9)))
    state.add_leader(LeaderState(88, kingdom_id=2, name="Target", location=HexCoord(20, 9)))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.SPY_SUPER_SLEUTH)
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.spied_on is True
    assert result.guessed_distance is not None


def test_dispatch_trail_wires_spy_expanded_spying_from_the_leaders_own_advanced_ability():
    # [3.17]'s own no-army restriction means the trailer can't be the
    # shared army-commanding leader _state_with_army() builds -- a
    # fresh, armyless leader is needed here instead, same as the Spy
    # Super Sleuth dispatch test above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_kingdom(KingdomState(2, "Fleeland", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", HexCoord(3, 9)))
    state.add_leader(LeaderState(88, kingdom_id=2, name="Target", location=HexCoord(3, 9)))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.SPY_EXPANDED_SPYING)
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    with patch(
        "ak_engine.turn.trail_execution.resolve_all_office_holders",
        return_value={Office.CHANCELLOR: OfficeHolder(leader_id=88, merit_points=10)},
    ):
        result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.spied_on is True
    assert result.offices_held == (Office.CHANCELLOR,)


def test_dispatch_trail_wires_spy_blackmail_from_the_leaders_own_advanced_ability():
    # Same fixture shape as the Spy Super Sleuth/Expanded Spying
    # dispatch tests above -- a fresh, armyless leader ([3.17]'s own
    # no-army restriction), target is a King of a different Kingdom.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_kingdom(KingdomState(2, "Fleeland", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", HexCoord(3, 9)))
    state.add_leader(LeaderState(88, kingdom_id=2, name="King Target", location=HexCoord(3, 9), is_king=True))
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.SPY_BLACKMAIL)
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.5, 0.5, 0.0])
    )

    assert result.spied_on is True
    assert result.blackmail_claim is not None
    assert state.kingdoms[2].pending_blackmail is result.blackmail_claim


def test_dispatch_succ_trail_is_deliberately_unsupported():
    # ActionCode.SUCC_TRAIL is intentionally excluded from
    # SUPPORTED_ACTIONS -- see plan_dispatch.py's module docstring: no
    # writer, no assignment site anywhere in the available Pascal
    # source, no rulebook order, never observed in real data. This test
    # guards against a future edit silently "completing" it without
    # revisiting that reasoning.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.SUCC_TRAIL, obj=88, extra=[0])

    try:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)
        assert False, "expected UnsupportedActionError"
    except UnsupportedActionError:
        pass


def test_dispatch_recruit_executes_debits_treasury_and_creates_armies():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    # Real example from AK3__T1.K1 leader 72: recruit under leader 1,
    # two Bowmen (pay 2 each) and one Warg Riders (pay 3) = 7 gold.
    phase = PlanPhase(label="P3", action=ActionCode.RECRUIT, obj=1, extra=[0, 1, 1, 10, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert isinstance(result, RecruitExecutionResult)
    assert [u.army_type for u in result.recruited] == [ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.WARG_RIDERS]
    assert result.total_gold_spent == 7
    assert state.kingdoms[1].treasury == 93
    assert all(state.armies[u.army_id].commanded_by == 1 for u in result.recruited)
    assert all(state.armies[u.army_id].location == location for u in result.recruited)
    assert all(state.armies[u.army_id].quality == Quality.AVERAGE for u in result.recruited)


def test_dispatch_unsupported_action_raises():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.SUCC_TRAIL, obj=6, extra=[0])

    try:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)
        assert False, "expected UnsupportedActionError"
    except UnsupportedActionError:
        pass


def test_dispatch_leave_transfers_command_to_target_leader():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(2, 1, "Other Leader", HexCoord(3, 9)))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ArmyListExecutionResult)
    assert result.succeeded == [army_id]
    assert state.armies[army_id].commanded_by == 2


def test_dispatch_leave_all_transfers_every_commanded_army_and_clears_to_garrison():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by is None


def test_dispatch_leave_in_allied_province_transfers_kingdom_ownership():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[HexCoord(3, 9)].owner_kingdom_id = 2  # an ally's province
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id == 2


# -- Bug fixes, sourced directly from the user (2026-10-29), designing
# Leave's own move-composer UI: ownership/co-location gate on a
# specific army-id list, the Garrison-to-Hero "novità" pass-along, the
# alliance gate on a named target leader, and the second (target-
# leader-based) Kingdom-transfer trigger. ----------------------------


def test_dispatch_leave_specific_army_not_commanded_by_acting_leader_is_skipped():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(2, 1, "Other Leader", location))
    state.armies[army_id].commanded_by = 2  # not this leader's own army
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].commanded_by == 2  # untouched


def test_dispatch_leave_can_pass_a_colocated_garrison_commanded_army_to_another_hero():
    # The rulebook's own "novità": a Hero merely co-located with (not
    # personally commanding) a Garrison-commanded army of his own
    # Kingdom can still pass it along to another Hero.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None  # Garrison-commanded
    state.add_leader(LeaderState(2, 1, "Other Leader", location))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert state.armies[army_id].commanded_by == 2


def test_dispatch_leave_all_includes_a_colocated_garrison_commanded_army():
    # 2026-11-20 bug fix, user-confirmed via a live playtest ("LEAVE
    # ALL non ha dato alcuna unità dal garrison commander al Re
    # Vitello"): a Hero with nothing personally commanded, but
    # co-located with a Garrison-commanded army of his own Kingdom,
    # must still get it from LEAVE ALL -- the same army the specific-
    # list case right above this already allows by number.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None  # Garrison-commanded, nothing personally commanded
    state.add_leader(LeaderState(2, 1, "Other Leader", location))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, 255, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert state.armies[army_id].commanded_by == 2


def test_dispatch_leave_all_excludes_a_noncolocated_garrison_commanded_army():
    state, army_id = _state_with_army(HexCoord(3, 9), {HexCoord(4, 9): Terrain.PLAINS})
    state.armies[army_id].commanded_by = None
    state.armies[army_id].location = HexCoord(4, 9)  # not co-located with the acting leader
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, 255, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == []
    assert state.armies[army_id].commanded_by is None


def test_dispatch_leave_all_excludes_a_colocated_garrison_commanded_army_of_a_different_kingdom():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None
    state.armies[army_id].kingdom_id = 2  # a different Kingdom's own Garrison-commanded army
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, 255, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == []
    assert state.armies[army_id].commanded_by is None


def test_dispatch_leave_a_noncolocated_garrison_commanded_army_is_skipped():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].commanded_by = None
    state.leaders[LEADER_ID].location = HexCoord(9, 9)  # not co-located with the army
    state.add_leader(LeaderState(2, 1, "Other Leader", HexCoord(9, 9)))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].commanded_by is None


def test_dispatch_leave_a_colocated_garrison_commanded_army_of_a_different_kingdom_is_skipped():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None
    state.armies[army_id].kingdom_id = 2  # a different Kingdom's idle garrison unit
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(3, 1, "Other Leader", location))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[3, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].commanded_by is None


def test_dispatch_leave_to_a_hostile_leader_is_rejected():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(2, 2, "Hostile Hero", location))  # not allied with Kingdom 1
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].commanded_by == LEADER_ID  # untouched


def test_dispatch_leave_to_an_unknown_leader_id_is_rejected():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[999, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_leave_to_an_allied_kingdoms_hero_transfers_the_armys_kingdom():
    # "Un'unità lasciata a un generale... di un altro Reame diventa di
    # proprietà di quest'ultimo" -- independent of who owns the
    # province the army is standing in (still Kingdom 1's own here).
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_leader(LeaderState(2, 2, "Allied Hero", location))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert state.armies[army_id].commanded_by == 2
    assert state.armies[army_id].kingdom_id == 2


def test_dispatch_leave_to_a_same_kingdoms_hero_does_not_change_kingdom_id():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(2, 1, "Other Leader", HexCoord(3, 9)))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id == 1


# -- Phase 647: Skeletal Army "digs its own grave" on Leave/reassign --


def test_is_undead_king_none_leader_id():
    state, _ = _state_with_army(HexCoord(3, 9), {})
    assert _is_undead_king(state, None) is False


def test_is_undead_king_unknown_leader_id():
    state, _ = _state_with_army(HexCoord(3, 9), {})
    assert _is_undead_king(state, 999) is False


def test_is_undead_king_hero_not_a_king():
    state, _ = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(2, 1, "Not the King", HexCoord(3, 9)))
    assert _is_undead_king(state, 2) is False


def test_is_undead_king_king_of_non_undead_kingdom():
    state, _ = _state_with_army(HexCoord(3, 9), {})  # LEADER_ID is King of a Good kingdom
    assert _is_undead_king(state, LEADER_ID) is False


def test_is_undead_king_true_for_king_of_undead_kingdom():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Nekrotia", Race.HUMAN, Alignment.UNDEAD, HexCoord(3, 9)))
    state.add_leader(LeaderState(1, 1, "Lich King", HexCoord(3, 9), is_king=True))
    assert _is_undead_king(state, 1) is True


def test_dispatch_leave_skeletal_army_abandoned_uncommanded_digs_its_own_grave():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].is_skeletal = True
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == []
    assert result.skeletal_army_lost == [(army_id, ArmyType.BOWMEN)]
    assert army_id not in state.armies


def test_dispatch_leave_skeletal_army_handed_to_non_undead_king_digs_its_own_grave():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].is_skeletal = True
    state.add_leader(LeaderState(2, 1, "Ordinary Hero", HexCoord(3, 9)))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == []
    assert result.skeletal_army_lost == [(army_id, ArmyType.BOWMEN)]
    assert army_id not in state.armies


def test_dispatch_leave_skeletal_army_handed_to_undead_king_survives():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].is_skeletal = True
    state.add_kingdom(KingdomState(2, "Nekrotia", Race.HUMAN, Alignment.UNDEAD, HexCoord(3, 9)))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_leader(LeaderState(2, 2, "Lich King", HexCoord(3, 9), is_king=True))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert result.skeletal_army_lost == []
    assert state.armies[army_id].commanded_by == 2
    assert state.armies[army_id].is_skeletal is True


def test_dispatch_leave_ordinary_army_unaffected_by_skeletal_rule():
    # Non-regression: an ordinary (non-skeletal) army left uncommanded
    # is untouched by the new check.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert result.skeletal_army_lost == []
    assert state.armies[army_id].commanded_by is None


# -- Phase 690: AdvancedAbility.ENHANCED_SKELETAL_UNITS's own exemption --


def test_dispatch_leave_skeletal_army_abandoned_uncommanded_survives_with_enhanced_skeletal_units():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].is_skeletal = True
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_SKELETAL_UNITS)
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert result.skeletal_army_lost == []
    assert state.armies[army_id].commanded_by is None
    assert state.armies[army_id].is_skeletal is True


def test_dispatch_leave_skeletal_army_handed_to_non_undead_king_survives_with_enhanced_skeletal_units():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].is_skeletal = True
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_SKELETAL_UNITS)
    state.add_leader(LeaderState(2, 1, "Ordinary Hero", HexCoord(3, 9)))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert result.skeletal_army_lost == []
    assert state.armies[army_id].commanded_by == 2


# -- Phase 821: a leader who already died earlier this same turn can't
# still execute a Leave/Pick_Up order queued for a later phase --


def test_dispatch_leave_by_a_dead_leader_is_a_clean_no_op():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    del state.leaders[LEADER_ID]  # died in an earlier phase this same turn
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, 255, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == []
    assert result.skeletal_army_lost == []
    assert state.armies[army_id].commanded_by == LEADER_ID  # untouched, not reassigned


def test_dispatch_leave_by_a_dead_leader_does_not_crash_on_a_skeletal_army():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].is_skeletal = True
    del state.leaders[LEADER_ID]  # died in an earlier phase this same turn
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, 255, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == []
    assert result.skeletal_army_lost == []
    assert army_id in state.armies  # not dug its own grave -- the order never ran at all


def test_dispatch_pick_up_by_a_dead_leader_does_not_crash():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None  # unled, at the leader's own location
    del state.leaders[LEADER_ID]  # died in an earlier phase this same turn
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert result.succeeded == []
    assert state.armies[army_id].commanded_by is None


def test_dispatch_explore_by_a_dead_leader_is_a_clean_no_op():
    # Phase 1041 bug fix -- the EXPLORE branch used to do a bare
    # state.leaders[leader_id] lookup instead of reusing the already-
    # fetched, None-checked `leader` variable computed a few lines up
    # for rumor generation -- missing the "acting leader may have died
    # earlier in the same turn" guard LEAVE/PICK_UP/DISBAND/HIRE/FIRE
    # all already got (each via .get() + a clean no-op). A leader who
    # died earlier this turn but still has a stale EXPLORE queued for a
    # later phase used to raise an uncaught KeyError here instead.
    state, _army_id = _state_with_army(HexCoord(3, 9), {})
    del state.leaders[LEADER_ID]  # died in an earlier phase this same turn
    phase = PlanPhase(label="P3", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert result == NoOpResult(action=ActionCode.EXPLORE)


def test_dispatch_pick_up_attaches_colocated_army():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None  # unled, at the leader's location
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_pick_up_ignores_army_in_a_different_province():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].location = HexCoord(9, 9)
    state.armies[army_id].commanded_by = None
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by is None


def test_dispatch_pick_up_all_only_attaches_unled_armies():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None
    state.add_leader(LeaderState(2, 1, "Other Leader", location))
    state.add_army(ArmyState(2, 1, ArmyType.AXEMEN, Quality.AVERAGE, location, commanded_by=2))
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by == LEADER_ID  # was unled -> picked up
    assert state.armies[2].commanded_by == 2  # already led by someone else -> untouched


# -- Bug fixes, sourced directly from the user (2026-10-29), designing
# Pick Up's own move-composer UI: a specific army-id list can take over
# a co-located army actively commanded by anyone, but only within the
# acting leader's own Kingdom; and a freshly-levied (non-mercenary)
# army can't be picked up the same turn it was recruited. ------------


def test_dispatch_pick_up_specific_list_can_take_over_a_colocated_armys_own_kingdom_army():
    # The user's own explicit choice: unlike Leave/Disband, a specific
    # Pick Up list may reassign an army away from another co-located
    # Hero of the SAME Kingdom (reorganizing one's own forces) -- no
    # "must be unled" restriction for the specific-list path.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(2, 1, "Other Leader", location))
    state.armies[army_id].commanded_by = 2
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_pick_up_specific_list_skips_a_different_kingdoms_colocated_army():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.armies[army_id].kingdom_id = 2
    state.armies[army_id].commanded_by = None
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].commanded_by is None


def test_dispatch_pick_up_all_skips_a_different_kingdoms_unled_colocated_army():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.armies[army_id].kingdom_id = 2
    state.armies[army_id].commanded_by = None
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by is None


def test_dispatch_pick_up_skips_an_army_recruited_this_same_turn():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None
    state.armies[army_id].recruited_this_turn = True
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].commanded_by is None


def test_dispatch_pick_up_allows_a_mercenary_recruited_this_same_turn():
    # Rulebook [3.9]'s own exception: a hired mercenary already existed
    # with a real id before this turn, so it's exempt from the
    # same-turn restriction even though `recruited_this_turn` happens
    # to be set (a fresh levy and a mercenary hire share one Recruit
    # code path -- see `turn/recruit_execution.py`, which never sets
    # this flag for an actual mercenary hire; this test instead directly
    # confirms the dispatcher's own exemption for `is_mercenary` armies,
    # independent of how that combination could arise).
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None
    state.armies[army_id].recruited_this_turn = True
    state.armies[army_id].is_mercenary = True
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.succeeded == [army_id]
    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_disband_releases_army_into_mercenary_status():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ArmyListExecutionResult)
    assert result.request.army_ids == [army_id]
    assert result.succeeded == [army_id]
    assert army_id in state.armies  # not removed -- still exists as an unowned mercenary
    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None
    # Bug fix, sourced directly from the user (2026-10-29): rulebook
    # [3.6]'s own "i suoi soldati si trasformano in mercenari" -- the
    # disbanded army must actually carry the real `is_mercenary` flag
    # the rest of the engine keys "hireable mercenary band" on
    # (`GameState.mercenaries_at()`), not just a cleared kingdom/
    # commander.
    assert state.armies[army_id].is_mercenary is True


def test_dispatch_disband_all_releases_every_commanded_army():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_hire_assigns_independent_hero_and_debits_treasury():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, None, "Wandering Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, HireExecutionResult)
    assert result.hired is True
    assert state.leaders[32].kingdom_id == 1
    # Neither the Hero nor Testia's King has a recorded alignment/temper,
    # so no penalty terms fire -- the real formula's own deterministic
    # bias for this exact King/Hero leader-id pair (1/32) still prices at
    # 2, not the raw 3-gold offer (turn/hire_pay.py's own module
    # docstring covers why this bias term exists at all).
    assert state.kingdoms[1].treasury == 98
    assert result.minimum_gold == 2


def test_dispatch_hire_fails_when_hero_not_colocated():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, None, "Wandering Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "not co-located"
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_by_a_dead_leader_is_a_clean_refusal_not_a_crash():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, None, "Wandering Hero", location))
    del state.leaders[LEADER_ID]  # died in an earlier phase this same turn
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, HireExecutionResult)
    assert result.hired is False
    assert result.reason == "not co-located"
    assert state.leaders[32].kingdom_id is None  # untouched
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_fails_when_hero_already_employed():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, 2, "Rival's Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "hero already in service"
    assert state.leaders[32].kingdom_id == 2  # untouched


# --- Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT -------------------------


def test_dispatch_hire_double_agent_appears_hired_by_a_foreign_king_without_changing_real_employer():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    spy = LeaderState(32, 2, "Double Agent", location, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    state.add_leader(spy)
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is True
    assert state.leaders[32].kingdom_id == 2  # real employer never changes
    assert state.leaders[32].double_agent_hired_by_kingdom_id == 1
    assert state.leaders[32].hire_turn == 0  # no real hire took place -- unchanged
    assert state.kingdoms[1].treasury == 98  # the foreign king's own gold really is spent


def test_dispatch_hire_double_agent_without_the_ability_still_refuses():
    # Non-regression: an ordinary employed Hero (no SPY_DOUBLE_AGENT)
    # is unaffected by the new bypass -- same as the existing "already
    # in service" test above, just re-confirmed alongside the new
    # ability-gated behavior.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, 2, "Rival's Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "hero already in service"
    assert state.leaders[32].double_agent_hired_by_kingdom_id is None


def test_dispatch_hire_double_agent_own_kingdom_reissuing_hire_still_refuses():
    # A Double Agent's own real Kingdom re-issuing a Hire order against
    # its own already-employed Spy is not a "foreign" hire -- falls
    # through to the ordinary refusal, not the bypass.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    spy = LeaderState(32, 1, "Double Agent", location)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    state.add_leader(spy)
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "hero already in service"
    assert state.leaders[32].double_agent_hired_by_kingdom_id is None


def test_dispatch_hire_double_agent_still_refused_on_insufficient_treasury():
    # The Double Agent bypass only skips the "already in service" gate
    # -- every other real check (here, treasury) still applies exactly
    # as an ordinary hire would, matching "the hiring will appear to be
    # successful" (a genuine success, not a freebie).
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {}, treasury=0)
    spy = LeaderState(32, 2, "Double Agent", location, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    state.add_leader(spy)
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "insufficient treasury"
    assert state.leaders[32].kingdom_id == 2
    assert state.leaders[32].double_agent_hired_by_kingdom_id is None


def test_dispatch_hire_fails_on_insufficient_treasury():
    location = HexCoord(3, 9)
    # required_pay() defaults to 1 (no alignment/temper recorded on
    # either side, Phase 162) -- treasury must be below *that*, not
    # merely below the gold_offer, to genuinely exercise this path.
    state, army_id = _state_with_army(location, {}, treasury=0)
    state.add_leader(LeaderState(32, None, "Wandering Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "insufficient treasury"
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 0  # untouched


# --- Hire's real required-pay formula (Phase 162) -------------------------


def test_dispatch_hire_refuses_a_hero_with_too_wide_an_alignment_gap():
    # Testia's King (_state_with_army) has no recorded alignment/temper,
    # so give him one explicitly here: GOOD vs the Hero's PAGAN is real
    # ordinal distance 3 -- "a Good King generally cannot hire a Pagan
    # Hero" (the user's own rulebook-quoted anchor case). Scripted rng
    # deliberately fails the Phase 264 "rare exception" roll (>= 0.15),
    # so this test still exercises the ordinary refusal path only.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.PAGAN))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[4])  # max legal offer

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.99])
    )

    assert result.hired is False
    assert result.reason == "alignment gap too wide"
    assert result.minimum_gold == 5
    assert result.rare_alignment_exception is False
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_rare_exception_succeeds_at_the_offer_ceiling():
    # Phase 264: same wide alignment gap, but the "rare exception" roll
    # (user-specified 15% chance) succeeds this time -- pay drops to the
    # Hire ceiling (4), and a max offer covers it.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.PAGAN))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[4])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0])
    )

    assert result.hired is True
    assert result.minimum_gold == 4
    assert result.rare_alignment_exception is True
    assert state.leaders[32].kingdom_id == 1
    assert state.kingdoms[1].treasury == 96


def test_dispatch_hire_rare_exception_success_still_needs_the_offer_ceiling():
    # The bypass lowers the price to 4, not to nothing -- an offer below
    # that still isn't enough, even when the rare roll itself succeeds.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.PAGAN))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])  # below the ceiling

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0])
    )

    assert result.hired is False
    assert result.reason == "offer below required pay"
    assert result.minimum_gold == 4
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_counter_offers_when_offer_is_below_required_pay():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    # DRUID is real ordinal distance 1 from GOOD -- align_penalty=1, plus
    # this King/Hero leader-id pair's own bias -- required pay 3.
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.DRUID))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[1])  # below the required 3

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "offer below required pay"
    assert result.minimum_gold == 3
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_succeeds_and_charges_only_the_required_pay_not_the_offer():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.GOOD))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[4])  # offers more than required

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is True
    assert result.minimum_gold == 2
    assert state.leaders[32].kingdom_id == 1
    assert state.leaders[32].hire_turn == state.turn_number
    assert state.kingdoms[1].treasury == 98  # only the required 2, not the offered 4


def test_dispatch_fire_releases_hero_to_independent():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, FireExecutionResult)
    assert result.request.hero_id == 32
    assert result.fired is True
    assert state.leaders[32].kingdom_id is None


def test_dispatch_fire_unknown_hero_id_reports_the_real_failure():
    # Phase 143: previously a silent no-op with no signal at all --
    # now an honest fired=False/reason.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=999, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request.hero_id == 999
    assert result.fired is False
    assert result.reason == "hero not found"


# --- King/Hero distinction (Phase 40) ------------------------------------


def test_dispatch_disband_by_a_hero_skips_a_noncolocated_army():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(50, 1, "A Hero", HexCoord(9, 9), is_king=False))  # not co-located with army_id
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=50, army_ids=[], board_width=BOARD_WIDTH)

    # Rulebook [3.6]: "A character can Disband an army only if he is in
    # the same province." -- left untouched, still owned and led.
    assert state.armies[army_id].kingdom_id == 1
    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_disband_by_a_hero_succeeds_when_colocated():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(50, 1, "A Hero", location, is_king=False))
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=50, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_disband_by_a_king_bypasses_colocation():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(50, 1, "The King", HexCoord(9, 9), is_king=True))  # not co-located, but a King
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=50, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_disband_by_a_king_skips_a_different_kingdoms_army_even_though_colocation_is_bypassed():
    # Bug fix, sourced directly from the user (2026-10-29): the fuller
    # rulebook [3.6] text names "qualsiasi unità militare del regno" --
    # a King's own co-location bypass was never meant to also bypass
    # the Kingdom boundary. Co-located here specifically to isolate
    # the Kingdom check from the co-location one.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(50, 2, "A Different King", location, is_king=True))
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=2, leader_id=50, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].kingdom_id == 1  # untouched -- a different Kingdom's army
    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_disband_by_a_colocated_hero_skips_a_different_kingdoms_army():
    # Same Kingdom-boundary fix as above, for an ordinary (non-King)
    # Hero: co-location alone was never meant to be sufficient either.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(50, 2, "A Foreign Hero", location, is_king=False))
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=2, leader_id=50, board_width=BOARD_WIDTH)

    assert result.skipped == [army_id]
    assert state.armies[army_id].kingdom_id == 1
    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_fire_by_a_hero_fails_when_not_colocated():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", HexCoord(9, 9)))
    state.add_leader(LeaderState(50, 1, "Acting Hero", HexCoord(1, 1), is_king=False))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=50, board_width=BOARD_WIDTH)

    # Rulebook [3.7]: "A character can Fire a Hero only if he is in the
    # same province." -- not co-located, so the Hero stays employed.
    assert result.fired is False
    assert result.reason == "not co-located"
    assert state.leaders[32].kingdom_id == 1


def test_dispatch_fire_by_a_hero_succeeds_when_colocated():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", location))
    state.add_leader(LeaderState(50, 1, "Acting Hero", location, is_king=False))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=50, board_width=BOARD_WIDTH)

    assert result.fired is True
    assert state.leaders[32].kingdom_id is None


def test_dispatch_fire_by_a_king_bypasses_colocation():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    # LEADER_ID (from _state_with_army) is a King, not co-located with 32.
    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)
    assert result.fired is True

    assert state.leaders[32].kingdom_id is None


def test_dispatch_fire_cannot_fire_a_king_even_a_colocated_one_of_the_same_kingdom():
    # Bug fix, sourced directly from the user (2026-11-01): symmetric
    # with Hire's own explicit "can't Hire a King" guard. Same Kingdom
    # and co-located, so this isolates the King check from the
    # Kingdom-ownership/co-location ones.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, 1, "Another King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.fired is False
    assert result.reason == "cannot fire a King"
    assert state.leaders[32].kingdom_id == 1


def test_dispatch_fire_by_a_king_skips_a_different_kingdoms_hero_even_though_colocation_is_bypassed():
    # Bug fix, sourced directly from the user (2026-11-01), same shape
    # as Disband's own King-co-location-bypass-isn't-a-Kingdom-bypass
    # correction, applied here after the user reconsidered an initial
    # too-hasty analogy and asked for it explicitly anyway, despite the
    # pasted [3.7] text itself not naming a Kingdom restriction.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(32, 2, "A Different Kingdom's Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    # LEADER_ID (from _state_with_army) is a King, not co-located with 32.
    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.fired is False
    assert result.reason == "not this Kingdom's Hero"
    assert state.leaders[32].kingdom_id == 2  # untouched


def test_dispatch_fire_self_fire_always_succeeds():
    # Rulebook [3.7]: "Un Eroe può sempre congedare sé stesso" -- a
    # Hero's own kingdom_id trivially matches itself, and he's always
    # co-located with himself, so no explicit self-fire branch is
    # needed; confirmed here as its own dedicated test (previously
    # untested in this suite).
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(50, 1, "A Hero", location, is_king=False))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=50, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=50, board_width=BOARD_WIDTH)

    assert result.fired is True
    assert state.leaders[50].kingdom_id is None


# --- Grandfather of Assassins FI interception (Phase 614) -------------------


def test_dispatch_fire_by_the_titleholder_against_a_foreign_hero_queues_a_guild_attempt():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.leaders[LEADER_ID].merit_tally.successful_assassinations = 2  # meets OFFICE_MIN_POINTS[Office.ASSASSIN]
    state.add_kingdom(KingdomState(2, "Targetia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(32, 2, "Foreign Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, FireExecutionResult)
    assert result.fired is False
    assert result.guild_assassination_queued is True
    assert state.pending_guild_target == 32
    # No ordinary Fire happened -- the target's own kingdom is untouched.
    assert state.leaders[32].kingdom_id == 2


def test_dispatch_fire_by_the_titleholder_against_own_kingdom_stays_an_ordinary_fire():
    # The manual's own note: firing your own character keeps the two
    # LKing()s equal, so no interception happens.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.leaders[LEADER_ID].merit_tally.successful_assassinations = 2
    state.add_leader(LeaderState(32, 1, "Own Kingdom's Hero", HexCoord(3, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.guild_assassination_queued is False
    assert result.fired is True
    assert state.pending_guild_target is None
    assert state.leaders[32].kingdom_id is None


def test_dispatch_fire_by_the_titleholder_against_a_foreign_king_is_refused():
    # A King is never a valid Guild target (the interception's own
    # "not hero.is_king" precondition), and -- bug fix, sourced directly
    # from the user (2026-11-01) -- is never a valid ordinary Fire
    # target either, falling through to the explicit "cannot fire a
    # King" guard before co-location/Kingdom-ownership is even checked.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.leaders[LEADER_ID].merit_tally.successful_assassinations = 2
    state.add_kingdom(KingdomState(2, "Targetia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(32, 2, "Foreign King", HexCoord(9, 9), is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.guild_assassination_queued is False
    assert state.pending_guild_target is None
    assert result.fired is False
    assert result.reason == "cannot fire a King"
    assert state.leaders[32].kingdom_id == 2  # untouched


def test_dispatch_fire_by_a_non_titleholder_against_a_foreign_hero_is_refused():
    # Bug fix, sourced directly from the user (2026-11-01): an ordinary
    # Fire (no Assassin title held) now requires the target to belong
    # to the firer's own Kingdom, even though LEADER_ID is a King and
    # so bypasses the co-location requirement -- the King's own bypass
    # is for co-location only, same correction already applied to
    # Disband's own King-co-location bypass.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    # LEADER_ID never earned the title (successful_assassinations stays 0).
    state.add_kingdom(KingdomState(2, "Targetia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(32, 2, "Foreign Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.guild_assassination_queued is False
    assert state.pending_guild_target is None
    assert result.fired is False
    assert result.reason == "not this Kingdom's Hero"
    assert state.leaders[32].kingdom_id == 2  # untouched


def test_dispatch_hire_cannot_hire_a_king():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    # A King without a kingdom_id (e.g. deposed) -- proves this is a real,
    # explicit check, not just an accidental side effect of the
    # "already in service" check below it.
    state.add_leader(LeaderState(32, None, "A Rival King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "cannot hire a King"
    assert state.leaders[32].kingdom_id is None  # untouched
    assert state.kingdoms[1].treasury == 100  # untouched


def test_real_move_file_leader_hire_phase_dispatches():
    # Leader 18 ("Guerin") in AK3__T2.K1 has a real Hire phase (P1):
    # "P1 : 5 32 3" -> Hire hero 32, offer 3 gold.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T2.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    hire_phase = leader.plan.segments[0].phases["P1"]
    assert hire_phase.action == ActionCode.HIRE

    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(18, 1, "Guerin", location))
    state.add_leader(LeaderState(32, None, "Wandering Hero", location))

    result = dispatch_phase(hire_phase, state, kingdom_id=1, leader_id=18, board_width=BOARD_WIDTH)

    assert isinstance(result, HireExecutionResult)
    assert result.hired is True
    assert state.leaders[32].kingdom_id == 1


def test_run_leader_plan_records_errors_and_continues():
    origin = HexCoord(3, 9)
    mid = HexCoord(4, 9)
    end = HexCoord(4, 10)
    state, army_id = _state_with_army(origin, {mid: Terrain.PLAINS, end: Terrain.PLAINS})

    leader = Leader(
        leader_id=LEADER_ID,
        name="Test Leader",
        plan=ActionPlan(
            leader_id=LEADER_ID,
            segments=[
                PlanSegment(
                    plan_start=0,
                    plan_end=4,
                    sp=(),
                    phases={
                        "P0": PlanPhase("P0", ActionCode.SUCC_TRAIL, 6, [0]),
                        "P1": PlanPhase("P1", ActionCode.SUCC_TRAIL, 6, [0]),
                        "P2": PlanPhase("P2", ActionCode.SUCC_TRAIL, 6, [0]),
                        "P3": PlanPhase("P3", ActionCode.LMOVE, 94, [0]),
                        "P4": PlanPhase("P4", ActionCode.LMOVE, 104, [0]),
                    },
                )
            ],
        ),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert [r.phase_label for r in results] == ["P0", "P1", "P2", "P3", "P4"]
    assert all(isinstance(r.error, UnsupportedActionError) for r in results[:3])
    assert results[3].error is None
    assert results[4].error is None
    assert state.armies[army_id].location == end


# -- Phase 708: random-encounter hook --


def _wanderer_leader_and_state() -> tuple[Leader, GameState]:
    origin = HexCoord(3, 9)
    state = GameState()
    state.turn_number = 2
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, origin))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(LEADER_ID, 1, "Wanderer", origin))
    leader = Leader(
        leader_id=LEADER_ID,
        name="Wanderer",
        plan=ActionPlan(
            leader_id=LEADER_ID,
            segments=[PlanSegment(plan_start=0, plan_end=0, sp=(), phases={"P0": PlanPhase("P0", ActionCode.LMOVE, 0)})],
        ),
    )
    return leader, state


def test_run_leader_plan_appends_a_random_encounter_result_when_one_fires():
    leader, state = _wanderer_leader_and_state()
    origin = state.leaders[LEADER_ID].location

    scripted_result = RandomEncounterResult(LEADER_ID, origin, terrain_roll_succeeded=True)
    with patch("ak_engine.turn.plan_dispatch.dispatch_phase", return_value=NoOpResult(action=ActionCode.LMOVE)), patch(
        "ak_engine.turn.plan_dispatch.dispatch_random_encounter_after_phase", return_value=scripted_result
    ):
        results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert [r.phase_label for r in results] == ["P0", "P0"]
    sentinel = results[1]
    assert sentinel.segment_index == -1
    assert sentinel.action is None
    assert sentinel.result is scripted_result


def test_run_leader_plan_appends_nothing_when_no_random_encounter_fires():
    leader, state = _wanderer_leader_and_state()

    with patch("ak_engine.turn.plan_dispatch.dispatch_phase", return_value=NoOpResult(action=ActionCode.LMOVE)), patch(
        "ak_engine.turn.plan_dispatch.dispatch_random_encounter_after_phase", return_value=None
    ):
        results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert [r.phase_label for r in results] == ["P0"]


def test_run_leader_plan_skips_the_random_encounter_hook_when_rng_is_none():
    leader, state = _wanderer_leader_and_state()

    with patch("ak_engine.turn.plan_dispatch.dispatch_phase", return_value=NoOpResult(action=ActionCode.LMOVE)), patch(
        "ak_engine.turn.plan_dispatch.dispatch_random_encounter_after_phase"
    ) as mock_dispatch:
        results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    mock_dispatch.assert_not_called()
    assert [r.phase_label for r in results] == ["P0"]


# -- Phase 766: Naval Hug Coastline stragglers sentinel --


def test_run_leader_plan_appends_a_straggler_sentinel_when_a_hug_coastline_move_splits():
    leader, state = _wanderer_leader_and_state()
    straggler_result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1, new_location=HexCoord(9, 9)
    )
    scripted_result = MoveExecutionResult(
        moved=True,
        battle_report=None,
        exploration=None,
        movement_points_spent=1,
        new_location=HexCoord(4, 9),
        straggler_result=straggler_result,
    )

    with patch("ak_engine.turn.plan_dispatch.dispatch_phase", return_value=scripted_result), patch(
        "ak_engine.turn.plan_dispatch.dispatch_random_encounter_after_phase", return_value=None
    ):
        results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert [r.phase_label for r in results] == ["P0", "P0"]
    sentinel = results[1]
    assert sentinel.segment_index == -1
    assert sentinel.action is None
    assert sentinel.result is straggler_result


def test_run_leader_plan_appends_no_straggler_sentinel_for_an_ordinary_move():
    leader, state = _wanderer_leader_and_state()
    scripted_result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1, new_location=HexCoord(4, 9)
    )

    with patch("ak_engine.turn.plan_dispatch.dispatch_phase", return_value=scripted_result), patch(
        "ak_engine.turn.plan_dispatch.dispatch_random_encounter_after_phase", return_value=None
    ):
        results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert [r.phase_label for r in results] == ["P0"]


# -- Phase 547: Valhalla visitor phase/Practice cap --


def _valhalla_leader_plan(*actions: ActionCode) -> Leader:
    phases = {
        label: PlanPhase(label, action, 0, [])
        for label, action in zip(("P0", "P1", "P2", "P3", "P4"), actions)
    }
    return Leader(
        leader_id=VALHALLA_VISITOR_LEADER_ID,
        name="Visitor",
        plan=ActionPlan(leader_id=VALHALLA_VISITOR_LEADER_ID, segments=[PlanSegment(0, 4, (), phases=phases)]),
    )


def test_run_leader_plan_caps_valhalla_visitor_phases_beyond_the_allowed_count():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(
        LeaderState(
            VALHALLA_VISITOR_LEADER_ID,
            1,
            "Visitor",
            location,
            valhalla_active_turn=state.turn_number,
            valhalla_allowed_phase_count=2,
        )
    )
    leader = _valhalla_leader_plan(
        ActionCode.DEFEND, ActionCode.DEFEND, ActionCode.DEFEND, ActionCode.DEFEND
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert isinstance(results[0].result, DefendRequest)
    assert isinstance(results[1].result, DefendRequest)
    assert results[2].result == NoOpResult(action=ActionCode.DEFEND)
    assert results[3].result == NoOpResult(action=ActionCode.DEFEND)


def test_run_leader_plan_does_not_count_wait_toward_the_valhalla_visitor_cap():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(
        LeaderState(
            VALHALLA_VISITOR_LEADER_ID,
            1,
            "Visitor",
            location,
            valhalla_active_turn=state.turn_number,
            valhalla_allowed_phase_count=1,
        )
    )
    leader = _valhalla_leader_plan(ActionCode.WAIT, ActionCode.DEFEND, ActionCode.DEFEND)

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert isinstance(results[0].result, NoOpResult)  # a genuine Wait, not the cap
    assert isinstance(results[1].result, DefendRequest)  # first real phase -- within budget
    assert results[2].result == NoOpResult(action=ActionCode.DEFEND)  # second -- over budget


def test_run_leader_plan_caps_a_second_practice_even_within_the_phase_budget():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(
        LeaderState(
            VALHALLA_VISITOR_LEADER_ID,
            1,
            "Visitor",
            location,
            skills=SkillTable(raw_values=[0] * 30),
            valhalla_active_turn=state.turn_number,
            valhalla_allowed_phase_count=3,  # plenty of budget -- only the Practice cap should bite
        )
    )
    leader = _valhalla_leader_plan(ActionCode.PRACTICE, ActionCode.PRACTICE)

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert results[0].result != NoOpResult(action=ActionCode.PRACTICE)  # first Practice actually dispatched
    assert results[1].result == NoOpResult(action=ActionCode.PRACTICE)  # second -- Practice cap, not phase budget


def test_run_leader_plan_leaves_the_visitor_uncapped_outside_their_active_turn():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(
        LeaderState(
            VALHALLA_VISITOR_LEADER_ID,
            1,
            "Visitor",
            location,
            valhalla_active_turn=state.turn_number + 1,  # not yet their turn
            valhalla_allowed_phase_count=1,
        )
    )
    leader = _valhalla_leader_plan(ActionCode.DEFEND, ActionCode.DEFEND, ActionCode.DEFEND)

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert all(isinstance(r.result, DefendRequest) for r in results)


def test_real_move_file_leader_plan_dispatches_its_lmoves():
    # End-to-end: parse a real player move-submission file (Phase 1's
    # parser), take a leader with genuine LMOVE phases, and dispatch them
    # against a synthetic GameState built around the decoded coordinates.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)

    segment = leader.plan.segments[0]
    lmove_targets = [
        phase.obj for label in ("P0", "P1", "P2", "P3", "P4")
        if (phase := segment.phases.get(label)) is not None and phase.action == ActionCode.LMOVE
    ]
    assert lmove_targets, "expected leader 1 in AK3__T1.K1 to have at least one real LMOVE phase"

    from ak_engine.turn.hex_numbering import decode_hex_number

    coords = [decode_hex_number(obj, BOARD_WIDTH) for obj in lmove_targets]
    origin = HexCoord(coords[0].x - 1, coords[0].y)  # a starting point adjacent to the first target

    state, army_id = _state_with_army(origin, {c: Terrain.PLAINS for c in coords})

    results = run_leader_plan(leader, state, kingdom_id=1, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert len(results) == 5  # P0-P4 all present in this fixture's first segment
    lmove_results = [r for r in results if r.action == ActionCode.LMOVE]
    assert lmove_results
    assert all(r.error is None for r in lmove_results)


def test_real_move_file_leader_recruit_phase_dispatches():
    # Leader 72 ("Teleko") in AK3__T1.K1 has a real Recruit phase (P3):
    # "P3 : 3 1 0 1 1 10 -1" -> recruit 2 Bowmen + 1 Warg Riders under leader 1.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 72)
    recruit_phase = leader.plan.segments[0].phases["P3"]
    assert recruit_phase.action == ActionCode.RECRUIT

    state, army_id = _state_with_army(HexCoord(3, 9), {})

    result = dispatch_phase(
        recruit_phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH
    )

    assert isinstance(result, RecruitExecutionResult)
    assert [u.army_type for u in result.recruited] == [ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.WARG_RIDERS]


def test_real_move_file_leader_leave_phase_dispatches():
    # Leader 18 ("Guerin") in AK3__T1.K1 has a real Leave phase (P3):
    # "P3 : 7 0 1 108 109 110 -1" -> leave armies 108/109/110 to leader 1.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    leave_phase = leader.plan.segments[0].phases["P3"]
    assert leave_phase.action == ActionCode.LEAVE

    state, army_id = _state_with_army(HexCoord(3, 9), {})
    for army_id_moved in (108, 109, 110):
        state.add_army(ArmyState(army_id_moved, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=18))
    state.add_leader(LeaderState(18, 1, "Guerin", HexCoord(3, 9)))

    result = dispatch_phase(leave_phase, state, kingdom_id=1, leader_id=18, army_ids=[], board_width=BOARD_WIDTH)

    assert isinstance(result, ArmyListExecutionResult)
    assert result.request.target_leader_id == 1
    assert result.request.army_ids == [108, 109, 110]
    assert result.succeeded == [108, 109, 110]
    assert all(state.armies[aid].commanded_by == 1 for aid in (108, 109, 110))


# --- Nested-plan dispatch (Phase 32) -------------------------------------


def test_successful_hire_dispatches_the_hired_characters_own_plan():
    location = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, _ = _state_with_army(location, {target: Terrain.PLAINS})
    state.add_leader(LeaderState(50, None, "Wandering Hero", location))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(plan_start=1, plan_end=1, sp=(), phases={"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Hirer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": hire_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    hirer_results = [r for r in results if r.leader_id == LEADER_ID]
    nested_results = [r for r in results if r.leader_id == 50]
    assert len(hirer_results) == 1
    assert hirer_results[0].result.hired is True
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P1"
    assert nested_results[0].error is None
    assert state.leaders[50].location == target


def test_failed_hire_does_not_dispatch_the_nested_plan():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    # Hero 50 already in another kingdom's service -> Hire fails.
    state.add_leader(LeaderState(50, 2, "Enemy's Hero", location))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Hirer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": hire_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1
    assert results[0].result.hired is False
    assert not any(r.leader_id == 50 for r in results)


def test_successful_charm_dispatches_the_charmed_characters_own_plan():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Wandering Hero", location))

    charm_phase = PlanPhase(
        label="P0",
        action=ActionCode.CAST,
        obj=int(Spell.CHARM),
        extra=[50],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.PRACTICE, 14, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Charmer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": charm_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    nested_results = [r for r in results if r.leader_id == 50]
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P1"
    assert nested_results[0].error is None
    assert isinstance(nested_results[0].result, PracticeExecutionResult)
    assert state.leaders[50].kingdom_id == 1


def test_resurrections_own_nested_plan_never_dispatches_without_a_dead_leader():
    # Resurrection has real embedded plans in sample data (see AK3__T6.K1)
    # and is executed as of Phase 59, but only for a target actually
    # archived in state.dead_leaders (see cast_execution.py). Here the
    # target is a plain, living LeaderState instead -- not what
    # Resurrection looks for -- so it still can't apply, and
    # _nested_plan_triggered still never fires.
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Would-be Revived", location))

    resurrection_phase = PlanPhase(
        label="P0",
        action=ActionCode.CAST,
        obj=int(Spell.RESURRECTION),
        extra=[50],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Necromancer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": resurrection_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1
    assert results[0].result.applied is False
    assert not any(r.leader_id == 50 for r in results)


def test_successful_charm_wand_use_mi_dispatches_the_charmed_characters_own_plan():
    # Phase 1039: the same nesting as an ordinary Cast of Charm, but
    # triggered by Use_MI-ing a Cologne of Charming wand instead.
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Wandering Hero", location))
    item = state.add_item(Treasure.WAND_CHARM, owner_leader_id=LEADER_ID, charges=1)

    charm_phase = PlanPhase(
        label="P0",
        action=ActionCode.USE_MI,
        obj=item.item_id,
        extra=[50],
        # The real parser can never resolve this at parse time for a
        # Use_MI phase (see use_mi_decode.py's own docstring) -- always
        # None, same as every other wand's own nested_plan would be.
        nested_plan=ActionPlan(
            leader_id=None,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.PRACTICE, 14, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Charmer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": charm_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    charmer_results = [r for r in results if r.leader_id == LEADER_ID]
    nested_results = [r for r in results if r.leader_id == 50]
    assert len(charmer_results) == 1
    assert charmer_results[0].result.applied is True
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P1"
    assert nested_results[0].error is None
    assert isinstance(nested_results[0].result, PracticeExecutionResult)
    assert state.leaders[50].kingdom_id == 1
    assert item.charges == 0  # the wand's own charge was spent


def test_resurrection_wand_use_mi_never_dispatches_without_a_dead_leader():
    # Mirrors test_resurrections_own_nested_plan_never_dispatches_without_
    # a_dead_leader() above, but via a Rod of Resurrection wand -- the
    # target is a plain, living LeaderState, not archived in
    # state.dead_leaders, so execute_cast() still refuses regardless of
    # the embedded plan.
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Would-be Revived", location))
    item = state.add_item(Treasure.WAND_RESURRECTION, owner_leader_id=LEADER_ID, charges=1)

    resurrection_phase = PlanPhase(
        label="P0",
        action=ActionCode.USE_MI,
        obj=item.item_id,
        extra=[50],
        nested_plan=ActionPlan(
            leader_id=None,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Necromancer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": resurrection_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1
    assert results[0].result.applied is False
    assert not any(r.leader_id == 50 for r in results)
    assert item.charges == 1  # not spent -- the cast never actually applied


def test_resolve_nested_plan_leader_id_ignores_a_use_mi_wand_that_isnt_charm_or_resurrection():
    # Direct unit check of the new split: _nested_plan_triggered() only
    # checks "did the Use_MI apply at all," so a structurally-nested
    # plan tagging along some other wand (e.g. Fireball) must still be
    # refused here, by spell, not just left to applied=True.
    fireball_request = CastRequest(spell=Spell.FIREBALL, target=0)
    cast_result = CastExecutionResult(request=fireball_request, applied=True)
    use_mi_result = UseMIExecutionResult(applied=True, cast_result=cast_result)
    nested_plan = ActionPlan(leader_id=None, segments=[])

    resolved = _resolve_nested_plan_leader_id(ActionCode.USE_MI, nested_plan, use_mi_result)

    assert resolved is None


def test_resolve_nested_plan_leader_id_reads_the_use_mi_cast_results_own_target():
    charm_request = CastRequest(spell=Spell.CHARM, target=77)
    cast_result = CastExecutionResult(request=charm_request, applied=True)
    use_mi_result = UseMIExecutionResult(applied=True, cast_result=cast_result)
    nested_plan = ActionPlan(leader_id=None, segments=[])

    resolved = _resolve_nested_plan_leader_id(ActionCode.USE_MI, nested_plan, use_mi_result)

    assert resolved == 77


def test_nested_plan_skipped_when_target_has_no_existing_leaderstate():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Wandering Hero", location))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        # A different character (999) is who the file says joined -- but
        # nothing in `state` ever created a LeaderState for them.
        nested_plan=ActionPlan(
            leader_id=999,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Hirer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": hire_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1  # no crash, no phantom nested results
    assert results[0].result.hired is True


def test_real_move_file_hire_dispatches_the_hired_heros_nested_lmove():
    # Leader 58 ("Elmer") in AK3__T5.K1 has a real Hire phase (P3):
    # "P3 : 5 38 4" -> Hire hero 38, offer 4 gold, with hero 38's own
    # nested plan embedded right after it: a single P4 LMOVE to hex 115.
    # Dispatched in isolation (not Elmer's whole real plan) so his own
    # earlier real LMOVE phases (which this synthetic state doesn't have
    # provinces for) can't move him away before the Hire phase runs.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T5.K1")
    real_leader = next(leader for leader in kingdom.leaders if leader.leader_id == 58)
    hire_phase = real_leader.plan.segments[0].phases["P3"]
    assert hire_phase.action == ActionCode.HIRE
    assert hire_phase.nested_plan.leader_id == 38

    from ak_engine.turn.hex_numbering import decode_hex_number

    target = decode_hex_number(hire_phase.nested_plan.segments[0].phases["P4"].obj, BOARD_WIDTH)
    origin = HexCoord(target.x - 1, target.y)  # adjacent starting point, same pattern as the LMOVE test above

    state, _ = _state_with_army(origin, {target: Terrain.PLAINS})
    state.add_leader(LeaderState(58, 1, "Elmer", origin))
    state.add_leader(LeaderState(38, None, "Wandering Hero", origin))

    leader = Leader(
        leader_id=58,
        name="Elmer",
        plan=ActionPlan(leader_id=58, segments=[PlanSegment(3, 3, (), {"P3": hire_phase})]),
    )
    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    nested_results = [r for r in results if r.leader_id == 38]
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P4"
    assert nested_results[0].error is None
    assert state.leaders[38].location == target


def test_real_move_file_charm_dispatches_the_charmed_heros_nested_practice():
    # Leader 1 (the King) in AK3__T2.K1 has a real Cast phase (P2):
    # "P2 : 9 12 30" -> Cast Charm targeting character 30, whose own
    # nested plan (P3/P4 Practice) is embedded right after it. Dispatched
    # in isolation (not the King's whole real plan), same reason as the
    # Hire test above -- his own earlier real LMOVE phase would otherwise
    # move him off this synthetic state's single province.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T2.K1")
    real_leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)
    charm_phase = real_leader.plan.segments[0].phases["P2"]
    assert charm_phase.action == ActionCode.CAST
    assert charm_phase.nested_plan.leader_id == 30

    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(1, 1, "Uga-Buga Makumb", location))
    state.add_leader(LeaderState(30, None, "Wandering Hero", location))

    leader = Leader(
        leader_id=1,
        name="Uga-Buga Makumb",
        plan=ActionPlan(leader_id=1, segments=[PlanSegment(2, 2, (), {"P2": charm_phase})]),
    )
    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    nested_results = [r for r in results if r.leader_id == 30]
    assert [r.phase_label for r in nested_results] == ["P3", "P4"]
    assert all(r.error is None for r in nested_results)
    assert all(isinstance(r.result, PracticeExecutionResult) for r in nested_results)
    assert state.leaders[30].kingdom_id == 1


def test_real_move_file_resurrections_nested_plan_never_dispatches_without_a_dead_leader():
    # Leader 18 ("Guerin") in AK3__T6.K1 has a real Cast phase (P3):
    # "P3 : 9 0 22" -> Cast Resurrection targeting character 22, whose
    # own nested plan (a real P4 Recruit) is embedded right after it --
    # confirming Resurrection's nested plans are real data, not just a
    # theoretical case. As of Phase 59 Resurrection is executed, but only
    # for a target actually archived in state.dead_leaders -- see
    # cast_execution.py; a real successful revival's own nested-plan
    # dispatch is covered separately in test_cast_execution.py /
    # test_plan_dispatch.py's newer Resurrection tests.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T6.K1")
    real_leader = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    resurrection_phase = real_leader.plan.segments[0].phases["P3"]
    assert resurrection_phase.action == ActionCode.CAST
    assert resurrection_phase.nested_plan.leader_id == 22

    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(18, 1, "Guerin", location))
    # No LeaderState 22, and no state.dead_leaders[22] either -- nothing
    # for Resurrection to revive, so nested dispatch never gets that far.

    leader = Leader(
        leader_id=18,
        name="Guerin",
        plan=ActionPlan(leader_id=18, segments=[PlanSegment(3, 3, (), {"P3": resurrection_phase})]),
    )
    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1
    assert results[0].result.applied is False
    assert not any(r.leader_id == 22 for r in results)


def test_dispatch_lmove_auto_boards_an_ent_when_the_leader_holds_druidic_transport():
    # Phase 715: dispatch_phase()'s own real LMOVE branch passes
    # auto_board=True plus both Druidic ability flags into execute_move()
    # for real -- an Ent (needs DRUIDIC_TRANSPORT, per turn/sea_
    # transport.py can_board()) boards a co-located Fleet, both
    # commanded by the same leader. _state_with_army()'s own default
    # Bowmen army (army_id 1) is left uncommanded here so it isn't part
    # of this move -- only the Fleet and the Ent are. Phase 737: target
    # is Sea, not Plains -- the Fleet's own crossing must itself be
    # legal (can't hop land-to-land), independent of what it carries.
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)  # adjacent to origin on the odd-r grid
    state, _bowmen_id = _state_with_army(origin, {target: Terrain.SEA})
    state.armies[_bowmen_id].commanded_by = None
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.DRUIDIC_TRANSPORT)
    fleet_id, ent_id = 2, 3
    state.add_army(ArmyState(fleet_id, 1, ArmyType.FLEET, Quality.AVERAGE, origin, movement_points=3, commanded_by=LEADER_ID))
    state.add_army(ArmyState(ent_id, 1, ArmyType.ENTS, Quality.AVERAGE, origin, movement_points=1, commanded_by=LEADER_ID))
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert ent_id in result.boarded_army_ids
    assert state.armies[ent_id].transported_by == fleet_id
    assert state.armies[ent_id].location == target
