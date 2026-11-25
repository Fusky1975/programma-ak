from __future__ import annotations

import random
from unittest.mock import MagicMock, patch

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, NO_LEADER_SENTINEL, ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, ActionCode, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.models.valhalla import VALHALLA_ROSTER, VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.battle_orchestrator import BattleReport, MultiAttackerBattle
from ak_engine.turn.battle_resolution import BattleResult
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.move_execution import MoveExecutionResult, TransportIllegalMoveError
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.contested_province import IllegalMoveFromContestedError
from ak_engine.turn.movement import neighbors as _neighbors
from ak_engine.turn.army_list_decode import ALL_ARMIES_SENTINEL
from ak_engine.turn.aspy_execution import SpyReport
from ak_engine.turn.patrol_execution import PatrolExecutionResult
from ak_engine.turn.plan_dispatch import NoOpResult, PhaseDispatchResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.random_encounter_execution import RandomEncounterResult
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.defend_execution import DefendCoverage, defend_coverage_area
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.turn_processor import (
    MultiAttackerMoveResult,
    TurnLeader,
    _ActiveMoveChase,
    _ActivePursuit,
    _apply_defend_reinforcements,
    _apply_werebeast_transformations,
    _collect_phase_entries,
    _continue_active_move_chases,
    _continue_active_pursuits,
    _main_dispatch_result,
    _register_move_chase_continuation,
    _register_pursuit_continuation,
    _replenish_turn_scoped_state,
    build_missed_deadline_turn_leaders,
    run_turn as _run_turn_unfiltered,
)

from _helpers import ScriptedRandom


def run_turn(*args, **kwargs):
    """Phase 756: the automatic per-turn Valhalla visit is now truly
    unconditional (fires whenever no Gate Angel cast claimed this turn's
    one visit, which is every pre-existing fixture in this file, since
    none of them cast it) -- an orthogonal, always-on mechanic that would
    otherwise force every one of this file's ~90 `run_turn()` call sites
    to individually account for an unrelated new "valhalla-visit"
    sentinel *and* its own real RNG consumption (which would shift the
    exact scripted-value sequence every `ScriptedRandom`-based test in
    this file relies on, for a mechanic none of them are about).
    Neutralized here by default via a scoped monkey-patch to a no-op;
    tests that specifically exercise the automatic visit itself call
    `_run_turn_unfiltered` directly instead (see the dedicated Phase 756
    section near the bottom of this file).
    """

    with patch("ak_engine.turn.turn_processor.finalize_ordinary_valhalla_visit", return_value=None):
        return _run_turn_unfiltered(*args, **kwargs)

BOARD_WIDTH = 10
ORIGIN = HexCoord(1, 1)
ORIGIN2 = HexCoord(3, 1)  # also adjacent to TARGET, distinct from ORIGIN
TARGET = HexCoord(2, 1)  # adjacent to both ORIGIN and ORIGIN2 on the odd-r grid


def _lmove_phase(label: str, target: HexCoord) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.LMOVE, obj=encode_hex_number(target, BOARD_WIDTH), extra=[0])


def _leader_with_phase(leader_id: int, name: str, label: str, phase: PlanPhase) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(leader_id=leader_id, segments=[PlanSegment(0, 0, (), {label: phase})]),
    )


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, TARGET))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(ORIGIN2, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    return state


def test_run_turn_dispatches_phase_by_phase_not_leader_by_leader():
    # If this were leader-by-leader (run_leader_plan called once per
    # leader in sequence), leader 10's P1 would appear before leader
    # 20's P0 in the results. Phase-by-phase means both P0s come first.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=HexCoord(6, 6)))

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    leader_a = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0, "P1": p1})]))
    leader_b = Leader(20, "B", ActionPlan(20, [PlanSegment(0, 1, (), {"P0": p0, "P1": p1})]))

    results = run_turn([TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH)

    assert [(r.phase_label, r.leader_id) for r in results] == [
        ("P0", 10),
        ("P0", 20),
        ("P1", 10),
        ("P1", 20),
    ]


# -- Phase 669: per-leader Special Encounter Plan, populated before phase 0 --


def test_run_turn_decodes_the_real_sp_block_before_phase_0():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    # Real SP: wire format (Phase 659): "10 -1" = [Flee], matching a
    # real hand-decoded sample from turn/sep_decode.py's own docstring.
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (10, -1), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.leaders[10].special_encounter_plan == (SearchTactic(Maneuver.FLEE),)


# -- Phase 670: monster-raid guardian maturation only from Fall (P3) onward,
# and apply_turn_revenue() now runs off the real per-turn rng --------------


def _empty_plan_leader(leader_id: int, name: str) -> Leader:
    return Leader(leader_id, name, ActionPlan(leader_id, [PlanSegment(0, 0, (), {})]))


def test_run_turn_ages_feature_guardians_only_from_fall_phase_index_3_onward():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_feature(
        Feature(
            feature_id=1,
            coord=coord,
            kind=FeatureType.DUNGEON,
            guardian_monster=Monster.CHIMERA,
            guardian_alignment=Alignment.NEUTRAL,
            guardian_state=MonsterEngagementState.CALM,
        )
    )
    leader = _empty_plan_leader(10, "A")

    # Exactly 3 draws expected: P3's 3%-hit (0.02) + Worldly-threshold
    # pick (0.1) transitions Calm -> Mercenary; P4's 3%-miss (0.5)
    # consumes only one more. If maturation ran during P0/P1/P2 too, this
    # exact-length script would either desync the CALM->MERCENARY
    # transition's own timing or raise IndexError on an unexpected extra
    # draw -- either way the assertion below would fail.
    rng = ScriptedRandom([0.02, 0.1, 0.5, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert state.features[1].guardian_state is MonsterEngagementState.MERCENARY


def test_run_turn_apply_turn_revenue_consumes_the_real_shared_rng():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=700))
    state.add_feature(
        Feature(
            feature_id=1,
            coord=coord,
            kind=FeatureType.DUNGEON,
            # Gr. Dragon: Temper.COWARDLY (25% raid-activity chance) --
            # avoids interaction with the maturation rolls below (its
            # own guardian_alignment doesn't matter once already BOLD).
            guardian_monster=Monster.GR_DRAGON,
            guardian_state=MonsterEngagementState.BOLD,
        )
    )
    leader = _empty_plan_leader(10, "A")

    # P3/P4 maturation rolls (3%-miss each, no threshold consumed) +
    # the raid activity check (>= 0.25 -> inactive). If `apply_turn_
    # revenue()` used its own fresh `random.Random()` instead of this
    # same shared `rng`, this script would be left with one unconsumed
    # element at the end.
    rng = ScriptedRandom([0.5, 0.5, 0.9, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert rng._randoms == []
    assert state.turn_raid_events == []
    assert state.kingdoms[1].treasury == 700


def test_run_turn_dissolves_illusory_terrain_once_per_real_turn_not_per_phase():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(
        ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, illusory_terrain=Terrain.SEA)
    )
    leader = _empty_plan_leader(10, "A")

    # Exactly one draw expected: the illusory-terrain dissolve roll for
    # this province's single entry. If the roll ran once per phase (5x)
    # instead of once per real turn, this exact-length script would
    # raise IndexError on the second draw.
    rng = ScriptedRandom([0.1, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert rng._randoms == []
    assert state.provinces[coord].illusory_terrain is None


def test_run_turn_leaves_illusory_terrain_untouched_on_a_scripted_miss():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(
        ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, illusory_terrain=Terrain.SEA)
    )
    leader = _empty_plan_leader(10, "A")

    rng = ScriptedRandom([0.9, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert rng._randoms == []
    assert state.provinces[coord].illusory_terrain is Terrain.SEA


# -- Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT's own end-of-turn intel grant


def test_run_turn_grants_a_double_agent_report_when_apparently_hired_and_in_the_hiring_kingdoms_own_territory():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    spy = LeaderState(20, 1, "Double Agent", coord, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    spy.double_agent_hired_by_kingdom_id = 2
    state.add_leader(spy)
    leader = _empty_plan_leader(10, "A")

    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    matching = [r for r in results if r.phase_label == "double-agent-report"]
    assert len(matching) == 1
    assert matching[0].leader_id == 20
    assert isinstance(matching[0].result, SpyReport)
    assert state.leaders[20].double_agent_hired_by_kingdom_id is None


def test_run_turn_grants_no_double_agent_report_when_the_province_is_not_the_hiring_kingdoms_own():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    # Owned by a third Kingdom, not the hiring Kingdom (2).
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=3))
    spy = LeaderState(20, 1, "Double Agent", coord, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    spy.double_agent_hired_by_kingdom_id = 2
    state.add_leader(spy)
    leader = _empty_plan_leader(10, "A")

    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert not [r for r in results if r.phase_label == "double-agent-report"]
    assert state.leaders[20].double_agent_hired_by_kingdom_id is None


def test_run_turn_double_agent_isolates_one_spys_exception_from_the_others():
    # Bug fix: an exception resolving one Double Agent spy's report used
    # to propagate straight out of run_turn(), discarding every already-
    # computed PhaseDispatchResult for every other kingdom/leader
    # processed earlier this same call -- the same per-leader isolation
    # convention run_leader_plan()'s own per-phase try/except already
    # established elsewhere in this module.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    broken_spy = LeaderState(20, 1, "Broken Spy", coord, race=Race.HUMAN)
    broken_spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    broken_spy.double_agent_hired_by_kingdom_id = 2
    good_spy = LeaderState(21, 1, "Good Spy", coord, race=Race.HUMAN)
    good_spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    good_spy.double_agent_hired_by_kingdom_id = 2
    state.add_leader(broken_spy)
    state.add_leader(good_spy)
    leader = _empty_plan_leader(10, "A")

    from ak_engine.turn.turn_processor import execute_aspy as real_execute_aspy

    def flaky_execute_aspy(state, leader_id, *args, **kwargs):
        if leader_id == 20:
            raise ValueError("boom")
        return real_execute_aspy(state, leader_id, *args, **kwargs)

    with patch("ak_engine.turn.turn_processor.execute_aspy", side_effect=flaky_execute_aspy):
        results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    matching = {r.leader_id: r for r in results if r.phase_label == "double-agent-report"}
    assert matching[20].error is not None
    assert matching[21].error is None
    assert isinstance(matching[21].result, SpyReport)
    assert state.leaders[20].double_agent_hired_by_kingdom_id is None
    assert state.leaders[21].double_agent_hired_by_kingdom_id is None


def test_run_turn_no_hire_this_turn_grants_no_report_and_draws_no_extra_rng():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    spy = LeaderState(20, 1, "Double Agent", coord, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    state.add_leader(spy)  # double_agent_hired_by_kingdom_id stays None -- not hired this turn
    leader = _empty_plan_leader(10, "A")

    rng = ScriptedRandom([0.0])
    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert not [r for r in results if r.phase_label == "double-agent-report"]


def test_run_turn_empty_sp_block_leaves_special_encounter_plan_empty():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.leaders[10].special_encounter_plan == ()


def test_run_turn_leaves_an_absent_leaders_own_special_encounter_plan_untouched():
    # A leader not included in this call's own turn_leaders (e.g. never
    # dispatched this turn for whatever reason) keeps whatever real SEP
    # they already had recorded, rather than being reset to empty.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    absent_leader = LeaderState(20, kingdom_id=1, name="B", location=HexCoord(6, 6))
    absent_leader.special_encounter_plan = (SearchTactic(Maneuver.MELEE),)
    state.add_leader(absent_leader)
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.leaders[20].special_encounter_plan == (SearchTactic(Maneuver.MELEE),)


def test_run_turn_single_attacker_lmove_resolves_as_ordinary_solo_battle():
    # Non-breaking check: exactly one leader targeting the enemy
    # province still resolves through the ordinary single-attacker path
    # (execute_move -> MoveExecutionResult), same as run_leader_plan
    # alone would produce -- no Multiple Contingents grouping possible
    # with only one attacker.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))

    results = run_turn([TurnLeader(leader_a, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert len(results) == 1
    assert results[0].error is None
    assert isinstance(results[0].result, MoveExecutionResult)


def test_run_turn_groups_same_phase_same_target_lmoves_into_one_multi_attacker_battle():
    state = _base_state()
    # Phase 307: same-origin (distance 0) union is only guaranteed (100%)
    # at March level 2+ -- level 0's own 80% left this test's real,
    # unscripted `random.Random(0)` sequence sensitive to a threshold
    # that shifted once the real MARCH TABLE replaced the old flat 85%.
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert len(results) == 2
    assert all(r.error is None for r in results)
    assert all(isinstance(r.result, MultiAttackerMoveResult) for r in results)
    # Same battle object for both -- they really did unite into one fight,
    # not two coincidentally-identical ones.
    battle_ids = {id(r.result.battle) for r in results}
    assert len(battle_ids) == 1
    assert sorted(results[0].result.battle.leader_ids) == [10, 20]


def test_run_turn_multi_attacker_lmove_rejects_a_mover_with_no_movement_points():
    # Phase 1041 bug fix -- this function's own separate movement logic
    # (it never calls execute_move()) never had the single-attacker
    # path's own movement-points gate (move_execution.py execute_move():
    # "an army with no movement points left this gameturn can't move",
    # raised *before* the move proceeds). find_transport_illegality()
    # is a pure terrain/transport legality check and never looks at
    # movement points either, so an army already at 0 used to be let
    # into the battle and then have `movement_points -= cost` applied
    # unconditionally, driving it further negative with no recorded
    # error. Leader 30's own army starts at 0 movement points; leaders
    # 10/20 still unite normally (2 parties is still >= 2), proving the
    # fix rejects only the offending mover rather than breaking the
    # whole group.
    state = _base_state()
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    # Leader 30 has no March skill: an army with 0 points left and no extra-move bonus due can't move
    # (a March skill would owe it bonus points, which are computed when it moves).
    state.add_leader(LeaderState(30, kingdom_id=1, name="C", location=ORIGIN))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))
    state.add_army(ArmyState(103, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=0, commanded_by=30))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))
    leader_c = _leader_with_phase(30, "C", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1), TurnLeader(leader_c, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(0),
    )

    by_leader = {r.leader_id: r for r in results}
    assert isinstance(by_leader[10].result, MultiAttackerMoveResult)
    assert isinstance(by_leader[20].result, MultiAttackerMoveResult)
    assert by_leader[30].result is None
    # Without the fix, leader 30 would have joined the battle instead
    # (a MultiAttackerMoveResult, same as 10/20) and had `movement_points
    # -= cost` applied unconditionally, driving its already-0 movement
    # points negative with no recorded error at all.
    assert isinstance(by_leader[30].error, ValueError)


def _united_invasion_state(march_level: int) -> GameState:
    state = _base_state()
    skills = _skills_with(Ability.MARCH, march_level, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=skills))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=skills))
    # Bowmen: speed 2, so the Speed 1-2 column of the March Table applies.
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.ELITE, ORIGIN, movement_points=2, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.ELITE, ORIGIN, movement_points=2, commanded_by=20))
    return state


def _run_united_invasion(state: GameState):
    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))
    # run_turn() resets every army's movement points at its end; keep the end-of-phase values visible.
    with patch("ak_engine.turn.turn_processor._replenish_turn_scoped_state"):
        return run_turn(
            [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
        )


@patch("ak_engine.turn.battle_orchestrator._resolve_duel_death", new=lambda *args, **kwargs: None)  # incidental duel: keep the commander alive
def test_run_turn_united_invasion_grants_the_march_table_movement_bonus():
    # Level 2 owes a Speed 1-2 army one extra move; the lone-invader path always granted it, the united
    # path never did.
    state = _united_invasion_state(march_level=2)

    results = _run_united_invasion(state)

    assert all(isinstance(r.result, MultiAttackerMoveResult) for r in results)
    for army_id in (101, 102):
        army = state.armies.get(army_id)
        if army is not None:  # an army can fall in the battle itself
            assert army.march_table_bonus_granted == 1
            cost = next(r.result.movement_points_spent for r in results)
            assert army.movement_points == 2 + 1 - cost


def test_run_turn_united_invasion_without_march_skill_grants_no_bonus():
    state = _united_invasion_state(march_level=0)

    _run_united_invasion(state)

    assert all(army.march_table_bonus_granted == 0 for army in state.armies.values())


def test_run_turn_united_invasion_credits_move_march_experience():
    state = _united_invasion_state(march_level=2)

    with patch("ak_engine.turn.move_execution.add_experience") as mock_add_experience:
        mock_add_experience.return_value = MagicMock(skill_rose=False)
        _run_united_invasion(state)

    credited = {(call.args[0].leader_id, call.args[1]) for call in mock_add_experience.call_args_list}
    assert credited <= {(10, Ability.MARCH), (20, Ability.MARCH)}
    assert credited, "a conquering united invasion earns March experience like a lone one"


def test_run_turn_multi_attacker_lmove_threads_apply_fanaticism_true():
    # Phase 744: the multi-attacker-LMOVE dispatch's own real
    # fight_multi_attacker_battle() call now opts real production
    # battles into Fanaticism -- mirrors the "mock the shared function,
    # assert the call kwarg" convention already used for execute_move()/
    # execute_pursue()'s own equivalent Phase 744 tests.
    state = _base_state()
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    stub_report = BattleReport(battle_result=BattleResult(), conquered=False)
    stub_battle = MultiAttackerBattle(leader_ids=[10, 20], report=stub_report)
    with patch("ak_engine.turn.turn_processor.fight_multi_attacker_battle") as mock_fight:
        mock_fight.return_value = [stub_battle]
        run_turn([TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    mock_fight.assert_called_once()
    assert mock_fight.call_args.kwargs["apply_fanaticism"] is True
    # Phase 930: same call now also opts into real duel combat -- see
    # test_execute_pursue_threads_apply_fanaticism_true_into_the_real_
    # battle's own Phase 930 note for the full rationale.
    assert mock_fight.call_args.kwargs["use_real_duel_combat"] is True


def test_run_turn_multi_attacker_lmove_reports_illegal_move_from_contested():
    # Phase 718: _dispatch_multi_attacker_lmove()'s own real is_illegal_
    # move_from_contested() check, mirroring test_move_execution.py's
    # own single-mover equivalent.
    state = _base_state()
    state.provinces[ORIGIN].contested_by_kingdom_id = 1
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert len(results) == 2
    assert all(isinstance(r.error, IllegalMoveFromContestedError) for r in results)


def test_run_turn_multi_attacker_lmove_reports_transport_illegal_move():
    # Phase 737: _dispatch_multi_attacker_lmove() has its own separate
    # movement logic (never calls execute_move()) and needs its own
    # copy of find_transport_illegality() -- an unassisted land army
    # moving onto Sea terrain is refused here too, mirroring test_move_
    # execution.py's own single-mover equivalent.
    state = _base_state()
    state.provinces[TARGET].terrain = Terrain.SEA
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert len(results) == 2
    assert all(isinstance(r.error, TransportIllegalMoveError) for r in results)
    assert all(r.error.reason == "insufficient_water_transport" for r in results)


@patch("ak_engine.turn.battle_orchestrator._resolve_duel_death", new=lambda *args, **kwargs: None)  # incidental duel: keep the commander alive
def test_run_turn_multi_attacker_lmove_records_each_movers_own_kingdom_exploration():
    # Phase 69: two *different* (allied) kingdoms uniting into one Multiple
    # Contingents battle each still get their own independent
    # explored_percent_by_kingdom entry -- unlike the pre-existing shared
    # explored_percent scalar, where only the last mover in the loop wins.
    state = _base_state()
    state.add_kingdom(KingdomState(3, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.allied_kingdoms.add(frozenset({1, 3}))
    # Same origin as each other (unlike the "peaceful mover" fixture's
    # ORIGIN/ORIGIN2 split) so Multiple Contingents' own grouping unites
    # them into one battle instead of two sequential ones -- the latter
    # would exhaust the lone defender on the first pass (a separate,
    # already-documented fight_multi_attacker_battle() edge case, not
    # something this test is about).
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(30, kingdom_id=3, name="C", location=ORIGIN))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(103, 3, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=5, commanded_by=30))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_c = _leader_with_phase(30, "C", "P0", _lmove_phase("P0", TARGET))

    run_turn([TurnLeader(leader_a, 1), TurnLeader(leader_c, 3)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    explored = state.provinces[TARGET].explored_percent_by_kingdom
    assert explored.get(1, 0) > 0
    assert explored.get(3, 0) > 0
    # Phase 630: each mover's own Ranger of the Plains merit (TARGET is
    # Plains terrain, per _base_state()), not just one shared credit.
    assert state.leaders[10].merit_tally.plains_explorations == 1
    assert state.leaders[30].merit_tally.plains_explorations == 1


def test_run_turn_multi_attacker_lmove_collapsing_to_one_survivor_credits_exploration_once():
    # Bug fix: when a candidate multi-attacker group collapses to fewer
    # than 2 surviving parties (here, leader B's own move is illegal from
    # a contested origin, leaving only leader A), the sole survivor used
    # to have record_kingdom_exploration()/reveal_adjacent_provinces()
    # already applied once inside _dispatch_multi_attacker_lmove()'s own
    # validation loop -- and then a *second* time via the ordinary
    # _dispatch_single() -> execute_move() pipeline it falls back to,
    # double-crediting the same real move. Leader A starts at ORIGIN
    # (uncontested); leader B starts at ORIGIN2, which is contested by
    # kingdom 1 itself, making B's own move to the enemy-owned TARGET
    # illegal and excluding B from `parties` entirely -- leaving exactly
    # one survivor (A), the collapse case this bug fix targets.
    state = _base_state()
    state.provinces[ORIGIN2].contested_by_kingdom_id = 1
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN2, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN2, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert len(results) == 2
    assert any(isinstance(r.error, IllegalMoveFromContestedError) for r in results)
    # Credited exactly once, via leader A's own single real execute_move()
    # call -- not twice (once from the abandoned preview, once for real).
    assert state.leaders[10].merit_tally.plains_explorations == 1


def test_run_turn_peaceful_mover_unaffected_by_a_lone_attacker_targeting_the_same_hex():
    # Kingdom 3 is allied with both the attacker's kingdom (1) and the
    # defender's kingdom (2), so its own mover always sees only allied
    # forces at TARGET regardless of who ends up holding it after the
    # attacker's own battle resolves -- an unambiguous "peaceful" case.
    state = _base_state()
    state.add_kingdom(KingdomState(3, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.allied_kingdoms.add(frozenset({1, 3}))
    state.allied_kingdoms.add(frozenset({2, 3}))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(30, kingdom_id=3, name="C", location=ORIGIN2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(103, 3, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN2, movement_points=5, commanded_by=30))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_c = _leader_with_phase(30, "C", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_c, 3)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    by_leader = {r.leader_id: r for r in results}
    # Only one genuine attacker (A) -- not enough to unite, so both
    # dispatch through the ordinary single-mover path.
    assert isinstance(by_leader[10].result, MoveExecutionResult)
    assert isinstance(by_leader[30].result, MoveExecutionResult)
    assert by_leader[30].result.battle_report is None  # peaceful entry, no fight at all
    assert by_leader[30].result.moved is True


def test_run_turn_shielded_allied_territory_mover_does_not_join_the_multi_attacker_group():
    # Phase 1044 bug fix: Kingdom 3 owns TARGET and is Allied with
    # Kingdom 1 -- turn/diplomacy.py is_attackable_at()'s own [8.1]
    # triangle rule shields Kingdom 4's own unallied army there from
    # Kingdom 1 entirely, even though 1 and 4 aren't allied with each
    # other. Kingdom 2 (unallied with both 3 and 4) genuinely does see a
    # legitimate target there. Before the fix, _sees_nonallied_defender
    # only checked "not allied with the defender" and ignored the
    # shield, wrongly counting Kingdom 1's own mover as "attacking" too
    # and pulling it into Multiple Contingents machinery alongside
    # Kingdom 2's genuine attacker.
    state = _base_state()
    state.add_kingdom(KingdomState(3, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_kingdom(KingdomState(4, "Drifteria", Race.HUMAN, Alignment.EVIL, HexCoord(8, 8)))
    state.allied_kingdoms.add(frozenset({1, 3}))
    state.provinces[TARGET].owner_kingdom_id = 3
    state.armies[201].kingdom_id = 4  # the defending army now belongs to the shielded-from kingdom
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN2, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 2)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    by_leader = {r.leader_id: r for r in results}
    # Kingdom 1's own mover is fully shielded (TARGET is Allied-owned)
    # -- only one genuine attacker (Kingdom 2) remains, below the
    # 2-mover Multiple Contingents threshold, so both dispatch through
    # the ordinary single-mover path instead of being united.
    assert isinstance(by_leader[10].result, MoveExecutionResult)
    assert isinstance(by_leader[20].result, MoveExecutionResult)


def test_run_turn_excludes_an_illegal_contested_mover_but_still_groups_the_rest():
    state = _base_state()
    # Phase 307: guarantees B/C's own same-origin union (see the sibling
    # test's own Phase 307 note above for why).
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN2, skills=march_4))
    state.add_leader(LeaderState(30, kingdom_id=1, name="C", location=ORIGIN2, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN2, movement_points=5, commanded_by=20))
    state.add_army(ArmyState(103, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN2, movement_points=5, commanded_by=30))
    # ORIGIN is contested by kingdom 1 itself -- illegal to move from
    # there to the (enemy-owned) TARGET province. B and C move from the
    # uncontested ORIGIN2 instead.
    state.provinces[ORIGIN].contested_by_kingdom_id = 1

    leaders = [
        _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET)),
        _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET)),
        _leader_with_phase(30, "C", "P0", _lmove_phase("P0", TARGET)),
    ]
    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 1), TurnLeader(leaders[2], 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(0),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].error is not None
    assert by_leader[10].result is None
    assert isinstance(by_leader[20].result, MultiAttackerMoveResult)
    assert isinstance(by_leader[30].result, MultiAttackerMoveResult)
    assert sorted(by_leader[20].result.battle.leader_ids) == [20, 30]


def test_run_turn_nested_plan_dispatch_still_works_through_the_wrapper():
    # _dispatch_single wraps a single phase in a throwaway ActionPlan and
    # calls the existing run_leader_plan -- confirms that wrapping
    # doesn't break Hire's own nested-plan dispatch (Phase 32).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=100))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hirer", location=HexCoord(3, 9)))
    state.add_leader(LeaderState(50, kingdom_id=None, name="Wandering Hero", location=HexCoord(3, 9)))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.WAIT, 0, [0])})],
        ),
    )
    hirer = _leader_with_phase(1, "Hirer", "P0", hire_phase)

    results = run_turn([TurnLeader(hirer, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    hirer_results = [r for r in results if r.leader_id == 1]
    nested_results = [r for r in results if r.leader_id == 50]
    assert len(hirer_results) == 1
    assert hirer_results[0].result.hired is True
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P1"
    assert nested_results[0].error is None
    assert state.leaders[50].kingdom_id == 1


# --- Practice multi-character coordination (Phase 46) ---------------------


def _practice_phase(label: str, ability: Ability) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.PRACTICE, obj=ability.value, extra=[0])


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _practice_state(*leader_ids: int, skills_by_id: dict[int, SkillTable] | None = None) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    skills_by_id = skills_by_id or {}
    for leader_id in leader_ids:
        state.add_leader(
            LeaderState(leader_id, kingdom_id=1, name=f"L{leader_id}", location=ORIGIN, skills=skills_by_id.get(leader_id))
        )
    return state


def test_run_turn_groups_co_located_same_ability_practicers():
    state = _practice_state(
        10,
        20,
        skills_by_id={
            10: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            20: _skills_with(Ability.NECROMANCY, skill=4, aptitude=9),
        },
    )
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.NECROMANCY))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.01, 0.0])
    )

    by_leader = {r.leader_id: r for r in results}
    # Lower-skill leader 10 gets the guaranteed (subject to aptitude) roll;
    # leader 20 (already higher) gets nothing this phase -- only reachable
    # if they were actually grouped together, not resolved independently.
    assert by_leader[10].result.skill_rose is True
    assert by_leader[10].result.new_skill == 2
    assert by_leader[20].result.skill_rose is False
    assert by_leader[20].result.new_skill == 4


def test_run_turn_pools_armies_for_co_located_tactical_practicers():
    # Phase 304 end-to-end: two co-located leaders both ordering Practice
    # Tactical get grouped by run_turn()'s own same-ability/same-location
    # rule (Phase 46) exactly like any other ability, and now actually
    # resolve through the [6.1] army-pooling mechanic instead of
    # silently training nobody. Leader 10's own Green army has no
    # higher-tier army under 10's own command -- only leader 20's pooled
    # Veteran army makes it trainable.
    state = _practice_state(10, 20)
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.GREEN, ORIGIN, commanded_by=10))
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.VETERAN, ORIGIN, commanded_by=20))
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.TACTICAL))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.TACTICAL))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0] + [0.99] * 40)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].result.not_implemented_for_ability is False
    assert by_leader[10].result.trained_army_ids == (1,)
    assert by_leader[20].result.trained_army_ids == ()
    assert state.armies[1].quality is Quality.AVERAGE
    assert state.armies[2].quality is Quality.VETERAN  # untouched


def test_run_turn_does_not_group_different_abilities_even_when_co_located():
    state = _practice_state(
        10,
        20,
        skills_by_id={
            10: _skills_with(Ability.NECROMANCY, skill=0, aptitude=9),
            20: _skills_with(Ability.SAGE, skill=0, aptitude=9),
        },
    )
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.SAGE))

    # 0.07 is above the 5% solo chance (correct, independent behavior) but
    # below the 10% tied-group chance -- if these were incorrectly grouped
    # by location alone (ignoring ability), both would succeed instead.
    # A third value pads leader_b's own Sage device-discovery roll (Phase
    # 171) -- moot here since skill=0 gives it a 0% chance regardless.
    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.07, 0.07, 0.9, 0.0]),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].result.skill_rose is False
    assert by_leader[20].result.skill_rose is False


def test_run_turn_does_not_group_same_ability_at_different_locations():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.NECROMANCY, 0, 9))
    )
    state.add_leader(
        LeaderState(20, kingdom_id=1, name="B", location=ORIGIN2, skills=_skills_with(Ability.NECROMANCY, 0, 9))
    )
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.NECROMANCY))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.07, 0.07, 0.0]),
    )

    by_leader = {r.leader_id: r for r in results}
    # Solo (5%) chance for both, not the tied-group (10%) chance.
    assert by_leader[10].result.skill_rose is False
    assert by_leader[20].result.skill_rose is False


def test_run_turn_groups_three_co_located_same_ability_practicers():
    state = _practice_state(
        10,
        20,
        30,
        skills_by_id={
            10: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            20: _skills_with(Ability.NECROMANCY, skill=4, aptitude=9),
            30: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
        },
    )
    leaders = [
        _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY)),
        _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.NECROMANCY)),
        _leader_with_phase(30, "C", "P0", _practice_phase("P0", Ability.NECROMANCY)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 1), TurnLeader(leaders[2], 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.01, 0.01, 0.0]),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].result.skill_rose is True
    assert by_leader[20].result.skill_rose is False
    assert by_leader[30].result.skill_rose is True


def test_run_turn_practice_rise_takes_effect_only_from_the_next_turn_when_earned_in_p4():
    # [3.13]: "L'avanzamento avrà effetto fin dalla fase successiva" -- a
    # rise earned in this turn's own last phase (P4) has no "next phase"
    # left within this same run_turn() call, so it must still be pending,
    # not yet written into the real skill table, once run_turn() returns.
    state = _practice_state(10, skills_by_id={10: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9)})
    state.leaders[10].experience_credit = 96  # +5 solo gain crosses the 100 threshold, guaranteeing the rise
    leader = _leader_with_phase(10, "A", "P4", _practice_phase("P4", Ability.NECROMANCY))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert state.leaders[10].pending_skill_advancement == {Ability.NECROMANCY: (2, 9)}
    assert state.leaders[10].skills.pair_for_ability(Ability.NECROMANCY) == (1, 9)

    # The next turn's own P0 (its phase loop's first statement, before
    # anything else that phase dispatches) commits it -- carried across
    # the turn boundary exactly like a real rise would be.
    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert state.leaders[10].pending_skill_advancement == {}
    assert state.leaders[10].skills.pair_for_ability(Ability.NECROMANCY) == (2, 9)


# -- Initiative-based phase ordering (RULES.AK [3], 2026-11-03) -----------
# See turn_processor.py _order_phase_entries_by_initiative()'s own
# docstring for the full rulebook quotes this section exercises.


def _wait_phase(label: str) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.WAIT, obj=0, extra=[0])


def _defend_phase(label: str) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.DEFEND, obj=0, extra=[0])


def _leave_phase(label: str, target_leader_id: int, army_ids: tuple[int, ...] = (101,)) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.LEAVE, obj=0, extra=[target_leader_id, *army_ids, -1])


def _pick_up_phase(label: str, *, army_ids: tuple[int, ...] = (), all_armies: bool = False) -> PlanPhase:
    # target_leader_id is meaningless for Pick_Up (army_list_decode.py's
    # own docstring) -- NO_LEADER_SENTINEL in extra[0] regardless.
    ids = [ALL_ARMIES_SENTINEL] if all_armies else [*army_ids, -1]
    return PlanPhase(label=label, action=ActionCode.PICK_UP, obj=0, extra=[NO_LEADER_SENTINEL, *ids])


def _recruit_phase(label: str, target_leader_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.RECRUIT, obj=target_leader_id, extra=[0, -1])


def _trade_phase(label: str, target_leader_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.TRADE, obj=1, extra=[0, target_leader_id])


def _cast_phase(label: str, spell: Spell, target: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.CAST, obj=spell.value, extra=[target])


def _ordering_state(initiative_by_leader_id: dict[int, int], *, kingdom_id: int = 1) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(kingdom_id, "Testia", Race.HUMAN, Alignment.NEUTRAL, ORIGIN))
    for leader_id, march_skill in initiative_by_leader_id.items():
        # MARCH's own 3x weight (turn/initiative.py) makes the resulting
        # Initiative score (3 * march_skill) easy to reason about here.
        skills = _skills_with(Ability.MARCH, march_skill, march_skill) if march_skill else None
        state.add_leader(LeaderState(leader_id, kingdom_id, f"L{leader_id}", ORIGIN, skills=skills))
    return state


def _turn_leaders(*entries: tuple[int, int, str, PlanPhase]) -> list[TurnLeader]:
    """Each entry is ``(leader_id, kingdom_id, label, phase)``, in the
    exact order they should appear in ``turn_leaders`` (this project's
    own K1-file-arrival "numero d'ordine").
    """

    return [
        TurnLeader(_leader_with_phase(leader_id, f"L{leader_id}", label, phase), kingdom_id)
        for leader_id, kingdom_id, label, phase in entries
    ]


def test_collect_phase_entries_orders_by_initiative_descending():
    state = _ordering_state({10: 1, 11: 3})  # leader 10: Initiative 3, leader 11: Initiative 9
    turn_leaders = _turn_leaders(
        (10, 1, "P0", _wait_phase("P0")),
        (11, 1, "P0", _wait_phase("P0")),
    )

    entries = _collect_phase_entries(turn_leaders, "P0", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [11, 10]


def test_collect_phase_entries_ties_broken_by_k1_arrival_order():
    state = _ordering_state({10: 0, 11: 0})  # both Initiative 0 -- a real tie
    turn_leaders = _turn_leaders(
        (10, 1, "P0", _wait_phase("P0")),
        (11, 1, "P0", _wait_phase("P0")),
    )

    entries = _collect_phase_entries(turn_leaders, "P0", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [10, 11]


def test_collect_phase_entries_defend_always_sorts_last_despite_higher_initiative():
    state = _ordering_state({10: 5, 11: 0})  # leader 10: Initiative 15, leader 11: Initiative 0
    turn_leaders = _turn_leaders(
        (10, 1, "P0", _defend_phase("P0")),
        (11, 1, "P0", _wait_phase("P0")),
    )

    entries = _collect_phase_entries(turn_leaders, "P0", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [11, 10]


def test_collect_phase_entries_leave_target_waits_despite_higher_initiative():
    # The rulebook's own worked example: Hero #13 (lower Initiative)
    # Leaves to Hero #14 (higher Initiative) -- #14's own same-phase
    # action waits for #13's Leave, reversing the ordinary Initiative
    # order.
    state = _ordering_state({13: 1, 14: 3})  # #13: Initiative 3, #14: Initiative 9
    turn_leaders = _turn_leaders(
        (13, 1, "P2", _leave_phase("P2", target_leader_id=14)),
        (14, 1, "P2", _wait_phase("P2")),
    )

    entries = _collect_phase_entries(turn_leaders, "P2", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [13, 14]


def test_collect_phase_entries_pick_up_all_armies_waits_for_an_untargeted_leave_at_its_location():
    # Backlog #7 / RULES.AK [3]'s own "Prendere Unità Militari" case:
    # Hero #13 (lower Initiative) Leaves an army to the Garrison
    # Commander (no named target) right where Hero #14 (higher
    # Initiative) has queued a "Pick Up all unled armies" order -- #14's
    # own Pick_Up waits for #13's Leave, the same reversal the ordinary
    # named-target case already gets.
    state = _ordering_state({13: 1, 14: 3})  # #13: Initiative 3, #14: Initiative 9
    state.add_army(ArmyState(301, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, commanded_by=13))
    turn_leaders = _turn_leaders(
        (13, 1, "P2", _leave_phase("P2", target_leader_id=NO_LEADER_SENTINEL, army_ids=(301,))),
        (14, 1, "P2", _pick_up_phase("P2", all_armies=True)),
    )

    entries = _collect_phase_entries(turn_leaders, "P2", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [13, 14]


def test_collect_phase_entries_pick_up_specific_army_id_creates_no_dependency():
    # Only the all_armies Pick_Up form is timing-sensitive -- naming a
    # specific army id never checks commanded_by in plan_dispatch.py
    # _dispatch_pick_up(), so ordinary Initiative order applies
    # unchanged, same as any other unrelated same-phase pair.
    state = _ordering_state({13: 1, 14: 3})
    state.add_army(ArmyState(301, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, commanded_by=13))
    turn_leaders = _turn_leaders(
        (13, 1, "P2", _leave_phase("P2", target_leader_id=NO_LEADER_SENTINEL, army_ids=(301,))),
        (14, 1, "P2", _pick_up_phase("P2", army_ids=(301,))),
    )

    entries = _collect_phase_entries(turn_leaders, "P2", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [14, 13]


def test_collect_phase_entries_pick_up_all_armies_ignores_an_untargeted_leave_of_a_foreign_kingdom():
    # _dispatch_pick_up()'s own per-army check is an exact Kingdom
    # match, not _same_side()'s looser ally-inclusive reading -- a
    # Pick_Up(all_armies) order never actually claims an allied-but-
    # foreign Kingdom's dropped army, so no dependency should form
    # for one either.
    state = _ordering_state({13: 1}, kingdom_id=1)
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.NEUTRAL, ORIGIN))
    state.add_leader(LeaderState(14, 2, "L14", ORIGIN, skills=_skills_with(Ability.MARCH, 3, 3)))
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ALLIED
    state.add_army(ArmyState(301, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, commanded_by=13))
    turn_leaders = _turn_leaders(
        (13, 1, "P2", _leave_phase("P2", target_leader_id=NO_LEADER_SENTINEL, army_ids=(301,))),
        (14, 2, "P2", _pick_up_phase("P2", all_armies=True)),
    )

    entries = _collect_phase_entries(turn_leaders, "P2", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [14, 13]


def test_collect_phase_entries_recruit_for_another_waits_despite_higher_initiative():
    state = _ordering_state({20: 0, 21: 3})
    turn_leaders = _turn_leaders(
        (20, 1, "P1", _recruit_phase("P1", target_leader_id=21)),
        (21, 1, "P1", _wait_phase("P1")),
    )

    entries = _collect_phase_entries(turn_leaders, "P1", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [20, 21]


def test_collect_phase_entries_the_owner_of_the_territory_recruits_before_his_ally():
    # [3.4]: "in any given phase, the owner of the territory has the right to recruit there before you do."
    state = _ordering_state({60: 3, 61: 0}, kingdom_id=1)  # the guest (60) has far higher Initiative
    state.add_kingdom(KingdomState(2, "Hostia", Race.HUMAN, Alignment.GOOD, ORIGIN))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.leaders[61].kingdom_id = 2
    turn_leaders = _turn_leaders(
        (60, 1, "P1", _recruit_phase("P1", target_leader_id=60)),
        (61, 2, "P1", _recruit_phase("P1", target_leader_id=61)),
    )

    entries = _collect_phase_entries(turn_leaders, "P1", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [61, 60]


def test_collect_phase_entries_give_waits_despite_higher_initiative():
    state = _ordering_state({30: 0, 31: 3})
    turn_leaders = _turn_leaders(
        (30, 1, "P3", _trade_phase("P3", target_leader_id=31)),
        (31, 1, "P3", _wait_phase("P3")),
    )

    entries = _collect_phase_entries(turn_leaders, "P3", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [30, 31]


def test_collect_phase_entries_favorable_cast_waits_despite_higher_initiative():
    state = _ordering_state({40: 0, 41: 3})
    turn_leaders = _turn_leaders(
        (40, 1, "P0", _cast_phase("P0", Spell.ORATORY, target=41)),
        (41, 1, "P0", _wait_phase("P0")),
    )

    entries = _collect_phase_entries(turn_leaders, "P0", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [40, 41]


def test_collect_phase_entries_hostile_cast_on_an_enemy_kingdom_creates_no_dependency():
    state = _ordering_state({40: 0}, kingdom_id=1)
    state.add_kingdom(KingdomState(2, "Enemia", Race.HUMAN, Alignment.EVIL, HexCoord(5, 5)))
    state.add_leader(LeaderState(50, 2, "L50", HexCoord(5, 5), skills=_skills_with(Ability.MARCH, 3, 3)))
    turn_leaders = _turn_leaders(
        (40, 1, "P0", _cast_phase("P0", Spell.KILL_ENEMY, target=50)),
        (50, 2, "P0", _wait_phase("P0")),
    )

    entries = _collect_phase_entries(turn_leaders, "P0", state)

    # No same-side relationship -- ordinary Initiative order applies, the
    # higher-Initiative leader 50 goes first, unaffected by leader 40's
    # own Cast naming them as a target.
    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [50, 40]


def test_collect_phase_entries_dependency_target_idle_this_phase_creates_no_dependency():
    state = _ordering_state({13: 1, 14: 3})
    # Leader 14 has no entry at all this phase (idle) -- nothing to wait for.
    turn_leaders = _turn_leaders((13, 1, "P2", _leave_phase("P2", target_leader_id=14)))

    entries = _collect_phase_entries(turn_leaders, "P2", state)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [13]


def test_collect_phase_entries_mutual_give_cycle_does_not_crash():
    # Never sourced, never seen in real play -- must degrade gracefully
    # (some deterministic order), not crash or loop forever.
    state = _ordering_state({60: 0, 61: 0})
    turn_leaders = _turn_leaders(
        (60, 1, "P0", _trade_phase("P0", target_leader_id=61)),
        (61, 1, "P0", _trade_phase("P0", target_leader_id=60)),
    )

    entries = _collect_phase_entries(turn_leaders, "P0", state)

    assert {tl.leader.leader_id for tl, _segment_index, _phase in entries} == {60, 61}


@patch("ak_engine.turn.battle_orchestrator._resolve_duel_death", new=lambda *args, **kwargs: None)  # incidental duel: keep the commander alive
def test_run_turn_leave_target_waits_for_the_leave_despite_higher_initiative():
    # End-to-end through a real run_turn() call, not just the ordering
    # helper directly: Hero #14's own P2 Move must not dispatch before
    # Hero #13's own P2 Leave has actually transferred the army.
    state = _base_state()
    state.add_leader(LeaderState(13, 1, "Benefactor", ORIGIN, skills=_skills_with(Ability.MARCH, 1, 1)))
    state.add_leader(LeaderState(14, 1, "Beneficiary", ORIGIN, skills=_skills_with(Ability.MARCH, 3, 3)))
    state.add_army(ArmyState(301, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=3))

    leader_13 = Leader(13, "Benefactor", ActionPlan(13, [PlanSegment(0, 0, (), {"P2": _leave_phase("P2", 14, (301,))})]))
    leader_14 = Leader(
        14, "Beneficiary", ActionPlan(14, [PlanSegment(0, 0, (), {"P2": _lmove_phase("P2", ORIGIN2)})])
    )
    turn_leaders = [TurnLeader(leader_13, 1), TurnLeader(leader_14, 1)]

    run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(1))

    # The Move dispatched after command had already transferred, so the
    # army moved under Hero #14's own command, not left behind.
    assert state.armies[301].commanded_by == 14
    assert state.armies[301].location == ORIGIN2


def test_run_turn_pick_up_all_armies_claims_an_untargeted_leaves_army_in_the_same_phase():
    # Backlog #7, end-to-end: Hero #14 (higher Initiative)'s own "Pick
    # Up all unled armies" must not dispatch before Hero #13's own P2
    # Leave (no named target -- dropped to the Garrison Commander) has
    # actually made army 301 unled, or it never gets the chance to
    # claim it this phase at all.
    state = _base_state()
    state.add_leader(LeaderState(13, 1, "Benefactor", ORIGIN, skills=_skills_with(Ability.MARCH, 1, 1)))
    state.add_leader(LeaderState(14, 1, "Beneficiary", ORIGIN, skills=_skills_with(Ability.MARCH, 3, 3)))
    state.add_army(ArmyState(301, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, commanded_by=13))

    leader_13 = Leader(
        13,
        "Benefactor",
        ActionPlan(13, [PlanSegment(0, 0, (), {"P2": _leave_phase("P2", NO_LEADER_SENTINEL, (301,))})]),
    )
    leader_14 = Leader(
        14, "Beneficiary", ActionPlan(14, [PlanSegment(0, 0, (), {"P2": _pick_up_phase("P2", all_armies=True)})])
    )
    turn_leaders = [TurnLeader(leader_13, 1), TurnLeader(leader_14, 1)]

    run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.armies[301].commanded_by == 14


# -- Contested-province forced rebattle (Phase 55) -------------------------


def test_run_turn_forces_a_rebattle_before_the_next_phase_when_contested():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    forced = [r for r in results if r.phase_label == "forced-rebattle"]
    assert len(forced) == 1
    assert forced[0].segment_index == -1
    assert forced[0].action is None
    assert forced[0].result is not None  # a real BattleReport


def test_run_turn_deducts_movement_points_for_the_forced_rebattle():
    # Phase 573: run_turn() now replenishes every army's own movement
    # points at the very end (real per-turn housekeeping this project
    # never had before), so a post-run_turn() movement_points reading no
    # longer reflects mid-turn deductions -- checking for the
    # "forced-rebattle" PhaseDispatchResult itself (the same signal
    # test_run_turn_does_not_force_a_rebattle_once_movement_points_run_out
    # already uses, just for presence instead of absence) is the direct,
    # still-valid way to confirm the rebattle/deduction logic engaged.
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] != []


def test_run_turn_forced_rebattle_wires_battle_carrier_destruction():
    # Phase 716: same real-battle fixture as the test above, proving the
    # forced-rebattle continuation's own real fight_battle() call
    # reaches turn/sea_transport.py apply_battle_carrier_destruction()
    # (Phase 686's own "mock the shared function, assert the call"
    # convention).
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    with patch("ak_engine.turn.turn_processor.apply_battle_carrier_destruction") as mock_cascade:
        run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    mock_cascade.assert_called_once()


def test_run_turn_does_not_force_a_rebattle_once_movement_points_run_out():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=0))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


# -- Plague spread (Phase 233) ----------------------------------------------


def test_run_turn_spreads_plague_to_adjacent_provinces_at_phase_boundaries():
    state = _base_state()
    state.provinces[TARGET].plague_active = True

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    # Deterministic under this fixed seed -- see turn/plague_spread.py's
    # own module docstring for the mechanic (rulebook [4.25.3]) this
    # exercises via run_turn()'s own per-phase-boundary dispatch. The
    # plague lasts only for the turn it spreads in: nothing stays afflicted
    # once run_turn() ends.
    assert state.provinces[ORIGIN].plague_active is False
    assert state.provinces[TARGET].plague_active is False

    # Phase 234: each newly-infected coordinate is also surfaced as its
    # own PhaseDispatchResult, the same sentinel convention
    # "forced-rebattle" already uses, so report/turn_report.py's own
    # record_plague_spread_world_events() can find it in run_turn()'s
    # return value.
    spread = [r for r in results if r.phase_label == "plague-spread"]
    assert [r.result for r in spread] == [ORIGIN]
    assert spread[0].leader_id == 0
    assert spread[0].segment_index == -1
    assert spread[0].action is None
    assert state.provinces[ORIGIN2].plague_active is False


def test_run_turn_does_not_force_a_rebattle_when_no_defender_remains():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))
    del state.armies[201]  # the defender fixture army -- nothing left to fight

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


def test_run_turn_forced_rebattle_retreat_uses_the_original_invasion_origin():
    # Phase 409: without ProvinceState.contested_from_coord, this rebattle
    # had no origin to pass to fight_battle(), so a clean-swept attacker
    # fell back to the wrong (defender-style, nearest-friendly-neighbor-
    # of-TARGET) rule instead of the real rulebook [7.4] one. FAR_ORIGIN
    # is deliberately not adjacent to TARGET at all, so the old fallback
    # could never have produced it -- only reading contested_from_coord
    # can. seed=1 is a decisive defender win (GREEN attacker vs. ELITE
    # defender) found by search.
    #
    # Phase 906: the attacker's own army is Chariots, not Garrison as
    # before -- turn/pursuit.py's own real, byte-confirmed mechanism now
    # deterministically catches (and, given Garrison's own quality-down
    # strength floor of 0, always destroys) a retreating Garrison against
    # a front-line Heavy Cavalry pursuer, regardless of any random draw,
    # which would leave this test with no surviving army to retreat at
    # all. Chariots' own pursuit speed (3, matching the pursuer's own)
    # makes a front-line Heavy Cavalry's catch test (`r01() + 2 > 3`)
    # impossible for either value of `r01()` -- a guaranteed escape,
    # independent of the seed.
    far_origin = HexCoord(8, 8)
    state = _base_state()
    state.add_province(ProvinceState(far_origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.kingdoms[1].treasury = 100  # an unpaid army may desert ([9.2]); not what this test is about
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.provinces[TARGET].contested_from_coord = far_origin
    state.add_army(ArmyState(101, 1, ArmyType.CHARIOTS, Quality.GREEN, TARGET, movement_points=3))
    state.armies[201].quality = Quality.ELITE
    state.armies[201].army_type = ArmyType.HVY_CAVALRY

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert 101 in state.armies
    assert state.armies[101].location == far_origin


def test_run_turn_ignores_a_province_with_no_contested_flag():
    state = _base_state()  # TARGET's contested_by_kingdom_id defaults to None
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


# -- Mutual Challenge/Pursue detection (Phase 56) ---------------------------


def _encounter_phase(label: str, action: ActionCode, target_id: int, *, melee: bool) -> PlanPhase:
    tactic = 9 if melee else 3  # Maneuver.MELEE / Maneuver.TALK ordinals
    return PlanPhase(label=label, action=action, obj=target_id, extra=[0, tactic, -1])


def test_run_turn_resolves_a_mutual_challenge_as_a_single_shared_encounter():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9)))
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN, skills=_skills_with(Ability.MELEE, 0, 9)))
    leaders = [
        _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)),
        _leader_with_phase(20, "B", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 10, melee=True)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
    )

    by_leader = {r.leader_id: r for r in results}
    assert set(by_leader) == {10, 20}
    # Single shared resolution: both dispatch entries point at the exact
    # same result object, not two independently-fought duels.
    assert by_leader[10].result is by_leader[20].result
    assert by_leader[10].result.accepted is True
    assert by_leader[10].result.combat_occurred is True
    assert by_leader[10].result.winner_leader_id == 10  # lower id -> challenger, higher skill -> wins
    assert 20 not in state.leaders
    assert 10 in state.leaders


def test_run_turn_mutual_encounter_keeps_the_king_as_target_regardless_of_leader_id():
    # King has the *lower* leader_id -- a naive "lower id is always
    # challenger" tiebreak would wrongly make the King the challenger here,
    # routing through the King-challenger 50% evade roll instead of the
    # King-target's guaranteed mutual acceptance ([3.12]).
    state = _base_state()
    state.add_leader(
        LeaderState(5, kingdom_id=1, name="King", location=ORIGIN, is_king=True, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    state.add_leader(
        LeaderState(20, kingdom_id=2, name="Hero", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    leaders = [
        _leader_with_phase(5, "King", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)),
        _leader_with_phase(20, "Hero", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 5, melee=True)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[5].result is by_leader[20].result
    assert by_leader[5].result.accepted is True  # guaranteed, no 50% roll -- King stayed the target
    assert by_leader[5].result.winner_leader_id == 20  # the Hero (challenger), higher melee skill
    # Phase 259: a King's death installs a Royal Heir under the same
    # leader_id rather than leaving the Kingdom leaderless.
    assert 5 in state.dead_leaders
    assert state.leaders[5].is_royal_heir is True


def test_run_turn_mutual_pursue_threads_the_initiators_own_spy_super_sleuth():
    # Phase 1041 bug fix -- the ordinary single-leader path
    # (plan_dispatch.py's own `_dispatch_pursue()`) always computes and
    # passes `has_spy_super_sleuth`; `_dispatch_mutual_encounter()` used
    # to silently omit it on its own `execute_pursue(..., mutual_
    # encounter=True)` call, defaulting to `False` regardless of
    # whether the initiator actually holds the ability -- losing both
    # the "catch-up roll is bypassed, success is automatic" guarantee
    # and the resulting `guessed_distance`.
    state = _base_state()
    state.add_leader(
        LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, advanced_abilities={AdvancedAbility.SPY_SUPER_SLEUTH})
    )
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN))
    leaders = [
        _leader_with_phase(10, "A", "P0", _pursue_phase("P0", 20)),
        _leader_with_phase(20, "B", "P0", _pursue_phase("P0", 10)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        # A's own guessed_distance perturbation (`rng.choice((-1, 0, 1))`,
        # index 1 -> offset 0), then add_experience()'s own two `.random()`
        # draws, then a generous buffer for the end-of-turn revenue draws
        # (one per Kingdom).
        rng=ScriptedRandom([0.0] * 20, choice_indices=[1]),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].result is by_leader[20].result
    result = by_leader[10].result
    assert result.caught_up is True
    # Without the fix, has_spy_super_sleuth silently defaults to False
    # here: the catch-up roll would need a real rng.random() draw this
    # test's own script doesn't provide for it (it would raise
    # IndexError, not just leave guessed_distance unset), and
    # guessed_distance would stay None even if it somehow still caught up.
    assert result.guessed_distance == 0  # co-located (distance 0) + a 0 offset


def test_run_turn_mutual_encounter_exception_does_not_crash_the_whole_turn():
    # Phase 1041 bug fix -- the three cross-leader group-dispatch call
    # sites (multi-attacker LMOVE, multi-character Practice, and this
    # one, mutual Challenge/Pursue) used to have none of the per-phase
    # try/except isolation every ordinary single-leader phase gets via
    # run_leader_plan()'s own broad `except Exception`. An exception
    # here used to propagate straight out of run_turn(), discarding
    # every already-computed PhaseDispatchResult for every other
    # kingdom/leader processed earlier this same call -- reproduced here
    # for the mutual-encounter call site; the identical fix covers the
    # other two (_dispatch_multi_attacker_lmove/_dispatch_multi_practice)
    # the same way.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN))
    state.add_leader(LeaderState(30, kingdom_id=1, name="Bystander", location=ORIGIN))
    bystander_wait = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leaders = [
        _leader_with_phase(10, "A", "P0", _pursue_phase("P0", 20)),
        _leader_with_phase(20, "B", "P0", _pursue_phase("P0", 10)),
        _leader_with_phase(30, "Bystander", "P0", bystander_wait),
    ]

    with patch("ak_engine.turn.turn_processor._dispatch_mutual_encounter", side_effect=RuntimeError("boom")):
        results = run_turn(
            [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2), TurnLeader(leaders[2], 1)],
            state,
            board_width=BOARD_WIDTH,
            rng=random.Random(0),
        )

    by_leader = {r.leader_id: r for r in results}
    # The bystander's own, completely unrelated dispatch still ran and
    # is still reported -- the crash in the mutual pair's own dispatch
    # didn't discard it.
    assert by_leader[30].action is ActionCode.WAIT
    assert by_leader[30].error is None
    # Both leaders in the crashed mutual pair are recorded with the real
    # exception instead of propagating it out of run_turn() itself.
    assert isinstance(by_leader[10].error, RuntimeError)
    assert isinstance(by_leader[20].error, RuntimeError)


def test_run_turn_multi_attacker_lmove_exception_does_not_crash_the_whole_turn():
    # Phase 1041 bug fix -- see test_run_turn_mutual_encounter_exception_
    # does_not_crash_the_whole_turn's own docstring: this is that same
    # fix's own multi-attacker-LMOVE call site, exercised directly
    # instead of relying on the mutual-encounter test to stand in for
    # all three identically-shaped try/except blocks.
    state = _base_state()
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(30, kingdom_id=1, name="Bystander", location=ORIGIN2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))
    bystander_wait = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader_c = _leader_with_phase(30, "Bystander", "P0", bystander_wait)

    with patch("ak_engine.turn.turn_processor._dispatch_multi_attacker_lmove", side_effect=RuntimeError("boom")):
        results = run_turn(
            [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1), TurnLeader(leader_c, 1)],
            state,
            board_width=BOARD_WIDTH,
            rng=random.Random(0),
        )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[30].action is ActionCode.WAIT
    assert by_leader[30].error is None
    assert isinstance(by_leader[10].error, RuntimeError)
    assert isinstance(by_leader[20].error, RuntimeError)


def test_run_turn_multi_practice_exception_does_not_crash_the_whole_turn():
    # Phase 1041 bug fix -- see test_run_turn_mutual_encounter_exception_
    # does_not_crash_the_whole_turn's own docstring: this is that same
    # fix's own multi-practice call site, exercised directly instead of
    # relying on the mutual-encounter test to stand in for all three
    # identically-shaped try/except blocks.
    state = _practice_state(
        10,
        20,
        skills_by_id={
            10: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            20: _skills_with(Ability.NECROMANCY, skill=4, aptitude=9),
        },
    )
    state.add_leader(LeaderState(30, kingdom_id=1, name="Bystander", location=ORIGIN2))
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.NECROMANCY))
    bystander_wait = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader_c = _leader_with_phase(30, "Bystander", "P0", bystander_wait)

    with patch("ak_engine.turn.turn_processor._dispatch_multi_practice", side_effect=RuntimeError("boom")):
        results = run_turn(
            [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1), TurnLeader(leader_c, 1)],
            state,
            board_width=BOARD_WIDTH,
            rng=ScriptedRandom([0.01, 0.0]),
        )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[30].action is ActionCode.WAIT
    assert by_leader[30].error is None
    assert isinstance(by_leader[10].error, RuntimeError)
    assert isinstance(by_leader[20].error, RuntimeError)
    assert by_leader[10].result is None
    assert by_leader[20].result is None


def test_run_turn_one_sided_challenge_dispatches_normally_not_as_mutual():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=2, name="King", location=ORIGIN, is_king=True))
    leaders = [
        _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)),
        # B has no reciprocal order this phase at all -- not a mutual pair.
        _leader_with_phase(20, "King", "P1", _encounter_phase("P1", ActionCode.CHALLENGE, 10, melee=True)),
    ]

    # P1's own King-challenges-a-Hero roll ("evade encounters from Kings
    # 50% of the time") also fires this turn -- 0.9 misses it (refused,
    # no combat, matching pre-Phase-747 behavior, where this exact draw
    # ran out of an empty script and errored silently inside that one
    # phase's own dispatch, rather than proceeding). Phase 747 then adds
    # one more unconditional `rng.random()` draw per kingdom (2 here).
    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.9, 0.0, 0.0]),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    a_result = by_label[(10, "P0")].result
    assert a_result.accepted is False
    assert a_result.reason == "encounter refused"  # mutual_encounter defaults False, King target refuses


def test_run_turn_self_targeting_pursue_is_not_misdetected_as_mutual():
    # Also the Phase 71 correct-path check: a self-targeting Pursue is a
    # Patrol declaration, not an ordinary Pursue dispatch -- with no
    # other leader around to intercept, it produces no dispatch result
    # at all (rule (d): "no current threat" -> nothing to report), not
    # the nonsensical self-battle the old (pre-Phase-71) dispatch path
    # would have produced.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    leader = _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.PURSUE, 10, melee=False))

    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0, 0.0]))

    assert results == []


def test_run_turn_same_kingdom_pursue_from_the_same_province_acts_after_its_target():
    # [3.16] (2026-11-01, never cross-checked before this round): "Se il
    # personaggio ne insegue o pedina un altro che appartiene al proprio
    # Reame ed entrambi partono dalla stessa provincia, l'inseguitore
    # eseguirà l'azione dopo l'inseguito." Both leaders are Kingdom 1,
    # both start at ORIGIN; the Pursued's own P0 moves it to TARGET
    # (adjacent). Dispatched in the "wrong" order (Pursuer first, as the
    # TurnLeader list below deliberately lists it), the pre-fix behavior
    # would have the Pursuer catch up while the Pursued is still at
    # ORIGIN (a same-Kingdom catch-up chance is always 1.0, so this
    # always resolves this same phase) and relocate there -- a no-op,
    # since ORIGIN is where the Pursuer already is -- only for the
    # Pursued to then move away to TARGET, leaving them *not* co-located
    # despite a reported "caught up." The fix reorders dispatch so the
    # Pursuer only ever sees the Pursued's own already-resolved P0
    # location.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="Pursuer", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Pursued", location=ORIGIN))
    pursuer = _leader_with_phase(10, "Pursuer", "P0", PlanPhase(label="P0", action=ActionCode.PURSUE, obj=20, extra=[0, -1]))
    pursued = _leader_with_phase(20, "Pursued", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(pursuer, 1), TurnLeader(pursued, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.0] * 10),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    pursue_result = by_label[(10, "P0")].result
    assert pursue_result.caught_up is True
    assert state.leaders[10].location == TARGET
    assert state.leaders[20].location == TARGET
    assert state.leaders[10].location == state.leaders[20].location


# -- Defend reactive reinforcement (Phase 57) -------------------------------


_BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)
DEFEND_HOME = HexCoord(5, 5)
COVERED = _neighbors(DEFEND_HOME, _BOUNDS)[0]
ANOTHER_COVERED = _neighbors(DEFEND_HOME, _BOUNDS)[1]
ATTACKER_ORIGIN = next(n for n in _neighbors(COVERED, _BOUNDS) if n != DEFEND_HOME)
SECOND_ATTACKER_ORIGIN = next(n for n in _neighbors(ANOTHER_COVERED, _BOUNDS) if n != DEFEND_HOME)


def _defend_phase(label: str) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.DEFEND, obj=0, extra=[0])


def _defend_state() -> GameState:
    state = GameState()
    # Both treasuries can pay for the armies: an unpaid army may now desert ([9.2]), which this fixture is not about.
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, ATTACKER_ORIGIN, treasury=100))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, DEFEND_HOME, treasury=100))
    state.add_province(ProvinceState(DEFEND_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(COVERED, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(ANOTHER_COVERED, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(SECOND_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(100, kingdom_id=2, name="Defender", location=DEFEND_HOME))
    # movement_points=2 -- the real cost of one reinforcement hop
    # (movement_cost_for_move(battle_occurred=True)); run_turn()'s own
    # replenishment only happens at the very end of the turn, so a
    # fixture-constructed army keeps exactly what it's given here for
    # this whole call.
    state.add_army(ArmyState(901, 2, ArmyType.GARRISON, Quality.GREEN, DEFEND_HOME, commanded_by=100, movement_points=2))
    return state


def _attacker(leader_id: int, army_id: int, origin: HexCoord, target: HexCoord, label: str) -> Leader:
    return _leader_with_phase(leader_id, "Attacker", label, _lmove_phase(label, target))


@patch("ak_engine.turn.battle_orchestrator._resolve_duel_death", new=lambda *args, **kwargs: None)  # incidental duel: keep the commander alive
def test_run_turn_defend_reinforces_an_invaded_covered_province_next_phase():
    state = _defend_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    # The defender's leader (and, before the battle, the garrison itself)
    # physically converges on the invaded province -- otherwise a
    # province with zero standing defenders wouldn't trigger a battle at
    # all (move_execution.py's own occupied_by_enemy check). The garrison
    # may not have survived the battle itself, so only the leader's own
    # post-battle position (leaders aren't removed by an ordinary army
    # battle) is asserted directly.
    assert state.leaders[100].location == COVERED

    by_leader = {r.leader_id: r for r in results}
    move_result = by_leader[200].result
    assert isinstance(move_result, MoveExecutionResult)
    assert move_result.battle_report is not None  # a battle happened -- reinforcement worked


def test_run_turn_defend_does_not_relocate_without_an_invasion():
    state = _defend_state()
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))

    run_turn([TurnLeader(defender, 2)], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.armies[901].location == DEFEND_HOME
    assert state.leaders[100].location == DEFEND_HOME


def test_run_turn_defend_does_not_reinforce_a_province_it_does_not_own():
    state = _defend_state()
    state.provinces[COVERED].owner_kingdom_id = 3  # a third, unrelated Kingdom's ground
    state.add_kingdom(KingdomState(3, "Neutralia", Race.HUMAN, Alignment.NEUTRAL, COVERED))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")

    run_turn([TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(3))

    assert state.armies[901].location == DEFEND_HOME  # never relocated


def test_run_turn_defend_is_consumed_after_its_first_reinforcement():
    state = _defend_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")
    second_attacker = _attacker(300, 903, SECOND_ATTACKER_ORIGIN, ANOTHER_COVERED, "P2")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1), TurnLeader(second_attacker, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(11),
    )

    # Committed to the first (P1) invasion -- never covers the second (P2)
    # one, which walks in uncontested (battle_report is None).
    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is not None
    assert by_leader[300].result.battle_report is None


# -- Defend reinforcement: terrain/transport + Movement Points (2026-11-01) --


def test_run_turn_defend_does_not_reinforce_with_insufficient_movement_points():
    # [3.15]: "un'unità che ha speso tutti i suoi Punti Movimento non
    # può più reagire" -- movement_points=1 is one short of the real
    # cost (movement_cost_for_move(battle_occurred=True) == 2).
    state = _defend_state()
    state.armies[901].movement_points = 1
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None  # never reinforced -- walks in uncontested
    assert state.armies[901].location == DEFEND_HOME


def _defend_run(state: GameState, seed: int = 9):
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    # Evenly matched Elite armies, so the reacting army has a fair chance to survive and be inspected.
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    state.armies[901].quality = Quality.ELITE
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")
    # run_turn() resets every army's movement points at its end; keep the end-of-phase values visible.
    with patch("ak_engine.turn.turn_processor._replenish_turn_scoped_state"):
        return run_turn(
            [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(seed)
        )


def test_run_turn_defend_win_pursuit_survives_an_invader_whose_armies_retreated_away():
    # The defending general wins and pursues the invader, but the invader's beaten armies retreated to
    # another province, leaving him behind: the pursuit used to ask fight_battle() for a battle with no
    # defenders and abort the whole turn with a ValueError.
    for seed in (5, 6):
        state = _defend_state()
        _defend_run(state, seed=seed)  # must not raise


def test_run_turn_defend_march_bonus_lets_a_slow_army_react():
    # Garrison speed 1 with 1 point left is one short of the reaction's cost (2) -- but a general with
    # March 2 owes a Speed 1-2 army one extra move when it moves, so it can react.
    state = _defend_state()
    state.leaders[100].skills = _skills_with(Ability.MARCH, 2, 9)
    state.armies[901].movement_points = 1

    results = _defend_run(state)

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is not None  # the Garrison reacted: a real battle
    assert state.armies[901].march_table_bonus_granted == 1


def test_run_turn_defend_without_march_skill_a_slow_army_still_cannot_react():
    state = _defend_state()
    state.armies[901].movement_points = 1

    results = _defend_run(state)

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None
    assert state.armies[901].location == DEFEND_HOME
    assert state.armies[901].march_table_bonus_granted == 0


def test_run_turn_defend_reaction_pays_its_movement_cost():
    # [3.15]: "questi movimenti costano Punti Movimento". The reaction used to be checked but never paid.
    state = _defend_state()  # Garrison with exactly the 2 points a reaction costs

    _defend_run(state)

    assert state.armies[901].movement_points == 0


def test_run_turn_defend_does_not_reinforce_a_fleet_across_a_land_to_land_hop():
    # [3.15]'s own Fleet/Archers example: a Fleet can't hop directly
    # between two land provinces (find_transport_illegality()'s own
    # "naval_land_hop"). DEFEND_HOME and COVERED are both Terrain.PLAINS
    # in _defend_state()'s own fixture.
    state = _defend_state()
    state.armies[901] = ArmyState(901, 2, ArmyType.FLEET, Quality.GREEN, DEFEND_HOME, commanded_by=100, movement_points=2)
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None  # never reinforced -- walks in uncontested
    assert state.armies[901].location == DEFEND_HOME


# -- Defend reinforcement: "intelligent" splitting (2026-11-01) -------------

HOME_ATTACKER_ORIGIN = next(n for n in _neighbors(DEFEND_HOME, _BOUNDS) if n not in (COVERED, ANOTHER_COVERED))


def _defend_split_state() -> GameState:
    state = _defend_state()
    state.add_province(ProvinceState(HOME_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    # Two equally-strong HVY_CAVALRY/ELITE armies (strength 20 apiece,
    # BASE_STRENGTH[HVY_CAVALRY]=4 * int(Quality.ELITE)=5) replace the
    # single starting Garrison.
    del state.armies[901]
    state.add_army(ArmyState(911, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, DEFEND_HOME, commanded_by=100, movement_points=2))
    state.add_army(ArmyState(912, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, DEFEND_HOME, commanded_by=100, movement_points=2))
    return state


def test_apply_defend_reinforcements_sends_only_part_of_its_force_when_home_is_also_invaded():
    # [3.15]'s own example: invaded at home AND at an adjacent covered
    # province. A single BOWMEN/AVERAGE invader (strength 4) at each
    # location is weak enough that either one of the defender's two
    # HVY_CAVALRY/ELITE armies (strength 20 apiece) alone clears the 50%
    # win_probability floor -- so only one is sent, the other stays home.
    # Calls _apply_defend_reinforcements() directly (not via run_turn())
    # so this test only exercises the splitting decision itself, not the
    # real battle's own random outcome or any follow-on pursuit a win
    # might separately register.
    state = _defend_split_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.BOWMEN, Quality.AVERAGE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    state.add_leader(LeaderState(400, kingdom_id=1, name="HomeAttacker", location=HOME_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(904, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME_ATTACKER_ORIGIN, commanded_by=400, movement_points=3)
    )
    attacker_leader = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")
    home_attacker_leader = _attacker(400, 904, HOME_ATTACKER_ORIGIN, DEFEND_HOME, "P1")
    entries = [
        (TurnLeader(attacker_leader, 1), 0, _lmove_phase("P1", COVERED)),
        (TurnLeader(home_attacker_leader, 1), 0, _lmove_phase("P1", DEFEND_HOME)),
    ]
    move_targets = {0: COVERED, 1: DEFEND_HOME}
    active_defends = {100: DefendCoverage(origin=DEFEND_HOME, area=defend_coverage_area(DEFEND_HOME, _BOUNDS, radius=1))}

    reinforced = _apply_defend_reinforcements(active_defends, move_targets, entries, state)

    assert reinforced[100].target == COVERED
    locations = {state.armies[911].location, state.armies[912].location}
    assert locations == {COVERED, DEFEND_HOME}  # exactly one army went, one stayed


def test_run_turn_defend_stays_home_when_splitting_would_leave_it_undefended():
    # Same home-also-invaded shape, but the covered province's own
    # invader is now overwhelming (5x DRAGON_WING/ELITE, strength 150)
    # -- no subset of the defender's own force ever clears 50% against
    # it, so [3.15]'s "in caso contrario rimarrà a difendere la
    # provincia" applies: nobody is sent, both armies stay home.
    state = _defend_split_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    for i in range(5):
        state.add_army(
            ArmyState(920 + i, 1, ArmyType.DRAGON_WING, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
        )
    state.add_leader(LeaderState(400, kingdom_id=1, name="HomeAttacker", location=HOME_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(904, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME_ATTACKER_ORIGIN, commanded_by=400, movement_points=3)
    )
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 920, ATTACKER_ORIGIN, COVERED, "P1")
    home_attacker = _attacker(400, 904, HOME_ATTACKER_ORIGIN, DEFEND_HOME, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1), TurnLeader(home_attacker, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(7),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None  # never reinforced -- walks in uncontested
    assert state.armies[911].location == DEFEND_HOME
    assert state.armies[912].location == DEFEND_HOME


def test_apply_defend_reinforcements_helps_the_single_biggest_simultaneous_threat():
    # Two covered provinces invaded in the *same* phase, no competing
    # threat at home -- [3.15]'s own "andrà in aiuto di una provincia
    # adiacente" (singular) picks the stronger of the two invading
    # forces (5x DRAGON_WING/ELITE at COVERED vs. 1x BOWMEN/AVERAGE at
    # ANOTHER_COVERED), not whichever was merely encountered first.
    # Called directly, same reasoning as the split tests above.
    state = _defend_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    for i in range(5):
        state.add_army(
            ArmyState(920 + i, 1, ArmyType.DRAGON_WING, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
        )
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.BOWMEN, Quality.AVERAGE, SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )
    attacker_leader = _attacker(200, 920, ATTACKER_ORIGIN, COVERED, "P1")
    second_attacker_leader = _attacker(300, 903, SECOND_ATTACKER_ORIGIN, ANOTHER_COVERED, "P1")
    # The weaker invasion (ANOTHER_COVERED) is declared/indexed *first* on
    # purpose -- a naive "whichever is encountered first" selection would
    # pick the wrong, weaker one; only a real strength comparison lands
    # on COVERED here.
    entries = [
        (TurnLeader(second_attacker_leader, 1), 0, _lmove_phase("P1", ANOTHER_COVERED)),
        (TurnLeader(attacker_leader, 1), 0, _lmove_phase("P1", COVERED)),
    ]
    move_targets = {0: ANOTHER_COVERED, 1: COVERED}
    active_defends = {100: DefendCoverage(origin=DEFEND_HOME, area=defend_coverage_area(DEFEND_HOME, _BOUNDS, radius=1))}

    reinforced = _apply_defend_reinforcements(active_defends, move_targets, entries, state)

    assert reinforced[100].target == COVERED
    assert state.armies[901].location == COVERED


# -- Defend cancellation (Phase 67) -----------------------------------------


def _two_phase_leader(leader_id: int, name: str, phase0: PlanPhase, phase1: PlanPhase) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(
            leader_id=leader_id, segments=[PlanSegment(0, 1, (), {phase0.label: phase0, phase1.label: phase1})]
        ),
    )


def _invading_attacker() -> tuple[LeaderState, ArmyState, Leader]:
    leader_state = LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN)
    army_state = ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    leader = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P2")
    return leader_state, army_state, leader


def test_run_turn_defend_is_cancelled_by_a_later_move_order():
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _lmove_phase("P1", ANOTHER_COVERED))

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None  # cancelled -- walks in uncontested


def test_run_turn_defend_is_cancelled_by_a_later_pursue_order():
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    pursue_phase = PlanPhase(label="P1", action=ActionCode.PURSUE, obj=999, extra=[-1])
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), pursue_phase)

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None


def test_run_turn_defend_is_cancelled_by_a_later_trail_order():
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    trail_phase = PlanPhase(label="P1", action=ActionCode.TRAIL, obj=999, extra=[0])
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), trail_phase)

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None


def test_run_turn_defend_is_cancelled_by_the_declarers_own_patrol_declaration():
    # Phase 1041 bug fix: a self-targeting PURSUE phase (a Patrol
    # declaration, rulebook [3.16]) is still a PURSUE order for [3.15]'s
    # own Defend-cancellation purposes ("If he receives a Move, Pursue
    # or Trail order, the Defend order is cancelled"), but it used to be
    # stripped out of this phase's own `entries` before
    # `_apply_defend_cancellations()` ever ran, so declaring a Patrol
    # never cancelled the declarer's own active Defend order -- unlike
    # an ordinary (non-self-targeting) Pursue, already covered by
    # `test_run_turn_defend_is_cancelled_by_a_later_pursue_order` above.
    # The defender's own army (901, GARRISON) means `find_patrol_target()`
    # never finds an interception target either way (rule (a): an armied
    # patroller's own Patrol is ignored) -- isolating this test to the
    # Defend-cancellation side effect alone, with no interception noise.
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    patrol_phase = PlanPhase(label="P1", action=ActionCode.PURSUE, obj=100, extra=[0, -1])  # self-targeting: Patrol
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), patrol_phase)

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None  # cancelled -- walks in uncontested


def test_run_turn_defend_survives_an_unrelated_action():
    # WAIT (and, by the same logic, Practice/Explore/etc.) doesn't cancel
    # Defend -- only LMOVE/PURSUE/TRAIL do. Proves the cancellation check
    # isn't over-broad.
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    wait_phase = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), wait_phase)

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is not None


# -- Naval Long Defend (Phase 524) -------------------------------------------

TWO_HEXES_AWAY = HexCoord(6, 3)  # not adjacent to DEFEND_HOME, but within radius 2
TWO_AWAY_ATTACKER_ORIGIN = HexCoord(6, 2)  # adjacent to TWO_HEXES_AWAY


def test_run_turn_defend_reinforces_two_hexes_away_with_long_naval_defend():
    # AdvancedAbility.NAVAL_LONG_DEFEND doubles the coverage radius (Phase
    # 524) -- a Fleet-commanding leader holding it reacts to an invasion
    # two hexes out, something the default radius-1 coverage (proven by
    # test_run_turn_defend_does_not_reinforce_a_province_it_does_not_own
    # and friends) would never reach.
    state = _defend_state()
    # A Fleet can't hop land-to-land (find_transport_illegality()'s own
    # "naval_land_hop" check) -- DEFEND_HOME needs a Sea coast of its own
    # for this Fleet-commanding defender's reinforcement to be legal at
    # all, independent of the NAVAL_LONG_DEFEND radius this test is
    # actually about.
    state.provinces[DEFEND_HOME].terrain = Terrain.SEA
    state.leaders[100].advanced_abilities.add(AdvancedAbility.NAVAL_LONG_DEFEND)
    state.armies[901] = ArmyState(901, 2, ArmyType.FLEET, Quality.GREEN, DEFEND_HOME, commanded_by=100, movement_points=2)
    state.add_province(ProvinceState(TWO_HEXES_AWAY, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(TWO_AWAY_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=TWO_AWAY_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TWO_AWAY_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, TWO_AWAY_ATTACKER_ORIGIN, TWO_HEXES_AWAY, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    by_leader = {r.leader_id: r for r in results}
    move_result = by_leader[200].result
    assert isinstance(move_result, MoveExecutionResult)
    assert move_result.battle_report is not None  # reinforced from 2 hexes away


def test_run_turn_defend_does_not_reach_two_hexes_away_without_the_ability():
    # Same geometry as above, but no NAVAL_LONG_DEFEND and no Fleet --
    # ordinary radius-1 coverage never sees an invasion this far out.
    state = _defend_state()
    state.add_province(ProvinceState(TWO_HEXES_AWAY, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(TWO_AWAY_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=TWO_AWAY_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TWO_AWAY_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, TWO_AWAY_ATTACKER_ORIGIN, TWO_HEXES_AWAY, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    by_leader = {r.leader_id: r for r in results}
    move_result = by_leader[200].result
    assert isinstance(move_result, MoveExecutionResult)
    assert move_result.battle_report is None  # no reinforcement reached this far
    assert state.leaders[100].location == DEFEND_HOME  # defender never moved


# -- Persistent Pursue/Trail chase (Phase 70) -------------------------------


CHASE_START = HexCoord(5, 4)
CHASE_STEP = HexCoord(6, 4)  # one hex closer, same row (even -> even, E offset (1, 0))
CHASE_TARGET = HexCoord(7, 4)  # 2 hexes from CHASE_START
DECOY = HexCoord(5, 5)  # adjacent to CHASE_START (SE), an uninvolved LMOVE destination


def _chase_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Chasia", Race.HUMAN, Alignment.NEUTRAL, CHASE_START))
    state.add_kingdom(KingdomState(2, "Runnia", Race.HUMAN, Alignment.NEUTRAL, CHASE_TARGET))
    for coord in (CHASE_START, CHASE_STEP, CHASE_TARGET, DECOY):
        state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Pursuer", location=CHASE_START))
    state.add_leader(LeaderState(20, kingdom_id=2, name="Target", location=CHASE_TARGET))
    return state


def _pursue_phase(label: str, target_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.PURSUE, obj=target_id, extra=[0, -1])  # no tactics


def _trail_phase(label: str, target_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.TRAIL, obj=target_id, extra=[0])


def _three_phase_leader(leader_id: int, name: str, p0: PlanPhase, p1: PlanPhase, p2: PlanPhase) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(
            leader_id=leader_id,
            segments=[PlanSegment(0, 2, (), {p0.label: p0, p1.label: p1, p2.label: p2})],
        ),
    )


def test_run_turn_unresolved_pursue_preempts_p1_and_continues_the_chase():
    # Spy skill 0, armyless, different Kingdoms: distance 2 -> 25% catch-up
    # chance, distance 1 (after one chase step) -> 50%. First roll (0.9)
    # misses at P0; second roll (0.1), taken by the *continuation* dispatch
    # at P1, catches -- and since neither side leads an army and the
    # Pursue carries no combat tactics, catching up ends the chase
    # immediately with no further combat.
    state = _chase_state()
    p0 = _pursue_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)  # would relocate the pursuer to DECOY if NOT preempted
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    pursuer = _three_phase_leader(10, "Pursuer", p0, p1, p2)

    results = run_turn(
        [TurnLeader(pursuer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    p0_result = by_label[(10, "P0")].result
    assert p0_result.caught_up is False
    assert p0_result.reason == "did not catch up this phase"

    # P1's own LMOVE order never dispatched -- the chase continuation ran
    # instead, at segment_index=-1 (not tied to a real plan segment).
    assert (10, "P1") in by_label
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.PURSUE
    assert p1_entry.result.caught_up is True
    # Phase 856 bug fix: a successful catch-up relocates the pursuer to
    # the target's own province -- not just the CHASE_STEP left behind
    # by the earlier, unresolved hex-stepping continuation -- matching
    # pursue_execution.py's own module docstring ("the same abstraction
    # level already used for the armyless case's encounter") and the
    # army-vs-army branch's own already-established relocation-on-
    # catch-up precedent. This assertion used to read CHASE_STEP,
    # silently encoding the bug (the armyless case never relocated at
    # all) as if it were the intended behavior.
    assert state.leaders[10].location == CHASE_TARGET  # relocated to the target's own province, not DECOY

    # Resolved -- P2's own WAIT order dispatches normally again.
    p2_entry = by_label[(10, "P2")]
    assert p2_entry.segment_index == 0
    assert p2_entry.action is ActionCode.WAIT


def test_run_turn_unresolved_trail_preempts_p1_and_continues_the_chase():
    state = _chase_state()
    p0 = _trail_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    trailer = _three_phase_leader(10, "Trailer", p0, p1, p2)

    results = run_turn(
        [TurnLeader(trailer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    assert by_label[(10, "P0")].result.spied_on is False

    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.TRAIL
    assert p1_entry.result.spied_on is True
    assert state.leaders[10].location == CHASE_STEP

    p2_entry = by_label[(10, "P2")]
    assert p2_entry.segment_index == 0
    assert p2_entry.action is ActionCode.WAIT


def test_run_turn_trail_continuation_wires_spy_blackmail():
    # Same P0-miss/P1-continuation shape as the test above, proving
    # `caster_has_spy_blackmail` reaches through `_continue_active_
    # pursuits()`'s own Trail branch, not just the initial dispatch.
    state = _chase_state()
    state.leaders[20].is_king = True
    state.leaders[10].advanced_abilities.add(AdvancedAbility.SPY_BLACKMAIL)
    p0 = _trail_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    trailer = _three_phase_leader(10, "Trailer", p0, p1, p2)

    results = run_turn(
        [TurnLeader(trailer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0, 0.0])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.result.spied_on is True
    assert p1_entry.result.blackmail_claim is not None
    assert state.kingdoms[2].pending_blackmail is p1_entry.result.blackmail_claim


# -- Trail's own "Actions" field (Phase 252) ---------------------------------


def test_run_turn_trail_backfills_the_targets_own_action_this_phase():
    state = _chase_state()
    state.leaders[20].location = CHASE_START  # same province as trailer -> guaranteed catch
    trailer = _leader_with_phase(10, "Trailer", "P0", _trail_phase("P0", 20))
    target = Leader(
        leader_id=20,
        name="Target",
        plan=ActionPlan(
            leader_id=20,
            segments=[PlanSegment(0, 0, (), {"P0": PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])})],
        ),
    )

    results = run_turn(
        [TurnLeader(trailer, 1), TurnLeader(target, 2)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.1, 0.5, 0.5, 0.0, 0.0])
    )

    trail_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0").result
    assert trail_result.spied_on is True
    assert trail_result.actions is ActionCode.WAIT


def test_run_turn_trail_actions_is_none_when_target_has_no_order_this_phase():
    state = _chase_state()
    state.leaders[20].location = CHASE_START
    trailer = _leader_with_phase(10, "Trailer", "P0", _trail_phase("P0", 20))
    # Target has no P0 phase at all -- idle this phase.
    target = Leader(leader_id=20, name="Target", plan=ActionPlan(leader_id=20, segments=[PlanSegment(0, 0, (), {})]))

    results = run_turn(
        [TurnLeader(trailer, 1), TurnLeader(target, 2)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.1, 0.5, 0.5, 0.0, 0.0])
    )

    trail_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0").result
    assert trail_result.spied_on is True
    assert trail_result.actions is None


def test_run_turn_trail_continuation_backfills_the_targets_own_action():
    # Same P0-miss/P1-continuation shape as
    # test_run_turn_unresolved_trail_preempts_p1_and_continues_the_chase,
    # but the target is now a real TurnLeader with its own P1 order, so
    # the continuation's own backfill (via _continue_active_pursuits) has
    # something real to find.
    state = _chase_state()
    p0 = _trail_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    trailer = _three_phase_leader(10, "Trailer", p0, p1, p2)
    target = Leader(
        leader_id=20,
        name="Target",
        plan=ActionPlan(
            leader_id=20,
            segments=[PlanSegment(0, 0, (), {"P1": PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])})],
        ),
    )

    results = run_turn(
        [TurnLeader(trailer, 1), TurnLeader(target, 2)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1  # continuation, not a real plan segment
    assert p1_entry.result.spied_on is True
    assert p1_entry.result.actions is ActionCode.WAIT


def test_run_turn_trail_actions_is_none_when_the_target_is_itself_mid_chase():
    """Phase 817 regression: ``action_this_phase_by_leader`` used to be
    built from the *unfiltered* phase entries, before the mid-chase
    preemption filter ran -- so a Trail target who was itself mid-Pursue
    this same phase, but still had a real (never-actually-dispatched,
    preempted) order queued for it, leaked that discarded order into the
    Trail report instead of the documented ``None``. Here leader 20 is
    mid-Pursue (still chasing leader 999 from P0) *and* has a real P1
    WAIT order in its own plan -- that WAIT order must never dispatch
    (it's preempted by the still-active chase) and must not leak into
    the trailer's own report either.

    ``execute_pursue``/``advance_pursuit`` are both mocked to a fixed
    "still chasing" result -- this test is only about which map
    ``action_this_phase_by_leader`` gets built from, not about the
    already-reviewed mechanics of Pursue's own catch-up roll.
    """

    state = _chase_state()
    state.leaders[20].location = CHASE_START  # co-located with the trailer -> guaranteed Trail catch-up
    trailer = _leader_with_phase(10, "Trailer", "P1", _trail_phase("P1", 20))
    target = Leader(
        leader_id=20,
        name="Target",
        plan=ActionPlan(
            leader_id=20,
            segments=[
                PlanSegment(
                    0,
                    1,
                    (),
                    {
                        "P0": _pursue_phase("P0", 999),
                        "P1": PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0]),
                    },
                )
            ],
        ),
    )

    still_chasing = PursueExecutionResult(caught_up=False, reason="did not catch up this phase")
    with patch("ak_engine.turn.plan_dispatch.execute_pursue", return_value=still_chasing):
        with patch("ak_engine.turn.turn_processor.advance_pursuit", return_value=still_chasing):
            results = run_turn(
                [TurnLeader(trailer, 1), TurnLeader(target, 2)],
                state,
                board_width=BOARD_WIDTH,
                # Trailing 0.0, 0.0: apply_turn_revenue()'s own end-of-turn
                # Invention-Bonus draw, one per Kingdom (2 here), unrelated
                # to what this test is about.
                rng=ScriptedRandom([0.1, 0.5, 0.5, 0.0, 0.0]),
            )

    trail_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P1").result
    assert trail_result.spied_on is True
    # Leader 20's own P1 WAIT order never actually dispatched (preempted
    # by its still-active P0 Pursue chase) -- reported as no data, not
    # as the discarded order.
    assert trail_result.actions is None


def test_run_turn_trail_actions_is_none_when_the_target_is_patrol_preempted():
    """Phase 817 follow-up regression: ``action_this_phase_by_leader`` is
    snapshotted (see the comment above its own assignment in
    ``run_turn()``) before Patrol cancellation/preemption runs a few
    lines later -- only the mid-chase filter has happened by then -- so a
    Trail target whose own queued order this same phase was preempted by
    their own standing Patrol interception used to leak that
    never-dispatched order into the Trail report too, the same failure
    mode as ``test_run_turn_trail_actions_is_none_when_the_target_is_itself_mid_chase``
    above but via Patrol instead of a mid-chase filter. Leader 20
    declares a Patrol at P0 and has a real P1 WAIT order queued; the
    (mocked) Patrol interception at P1 preempts that WAIT order, and it
    must not leak into leader 10's own Trail report.

    ``execute_patrol`` is mocked to a fixed "intercepted" result -- this
    test is only about which map ``action_this_phase_by_leader`` gets
    pruned from, not about Patrol's own already-reviewed adjacency/
    wander-roll mechanics.
    """

    state = _chase_state()
    state.leaders[20].location = CHASE_START  # co-located with the trailer -> guaranteed Trail catch-up
    trailer = _leader_with_phase(10, "Trailer", "P1", _trail_phase("P1", 20))
    target = Leader(
        leader_id=20,
        name="Target",
        plan=ActionPlan(
            leader_id=20,
            segments=[
                PlanSegment(
                    0,
                    1,
                    (),
                    {
                        "P0": _patrol_declare_phase("P0", 20),
                        "P1": PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0]),
                    },
                )
            ],
        ),
    )

    intercepted = PatrolExecutionResult(intercepted=True, target_leader_id=999)
    with patch("ak_engine.turn.turn_processor.execute_patrol", return_value=intercepted):
        results = run_turn(
            [TurnLeader(trailer, 1), TurnLeader(target, 2)],
            state,
            board_width=BOARD_WIDTH,
            rng=ScriptedRandom([0.1, 0.5, 0.5, 0.0, 0.0]),
        )

    trail_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P1").result
    assert trail_result.spied_on is True
    # Leader 20's own P1 WAIT order never actually dispatched (preempted
    # by its own standing Patrol interception) -- reported as no data,
    # not as the discarded order.
    assert trail_result.actions is None


def test_run_turn_unresolved_move_chase_preempts_p1_and_continues_the_chase():
    # Phase 632: CHASE_TARGET is 2 hexes from CHASE_START (same geometry
    # the Pursue/Trail tests above reuse) -- P0's own LMOVE hop lands at
    # CHASE_STEP (not yet arrived), P1's own explicit LMOVE-to-DECOY
    # order is preempted by the ongoing chase's own continuation instead
    # (the user's own confirmed "mirror Pursue/Trail exactly" broad
    # reading), and once the chase resolves at P1, P2 dispatches
    # normally again.
    state = _chase_state()
    p0 = _lmove_phase("P0", CHASE_TARGET)
    p1 = _lmove_phase("P1", DECOY)  # would relocate the mover to DECOY if NOT preempted
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    mover = _three_phase_leader(10, "Mover", p0, p1, p2)

    results = run_turn([TurnLeader(mover, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.5] * 10))

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    p0_result = by_label[(10, "P0")].result
    assert p0_result.reached_target is False
    assert p0_result.stopped_chasing is False
    # new_location, not state.leaders[10].location -- by the time run_turn()
    # returns, the P1 continuation below has already advanced the mover
    # further; new_location is P0's own immutable snapshot of the hop it
    # actually took.
    assert p0_result.new_location == CHASE_STEP

    # P1's own LMOVE-to-DECOY order never dispatched -- the chase
    # continuation ran instead, at segment_index=-1 (not tied to a real
    # plan segment).
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.LMOVE
    assert p1_entry.result.reached_target is True
    assert state.leaders[10].location == CHASE_TARGET  # not DECOY

    # Resolved -- P2's own WAIT order dispatches normally again.
    p2_entry = by_label[(10, "P2")]
    assert p2_entry.segment_index == 0
    assert p2_entry.action is ActionCode.WAIT


def test_run_turn_move_chase_that_stops_does_not_preempt_the_next_phase():
    # Mirrors turn/move_execution.py's own "stop chasing" geometry (a
    # mover pinned at the board's own southern edge, y=14 of
    # NORMAL_MAP_BOUNDS' 0..14 range, with a target further south than
    # any real province can be -- no neighbor can possibly get closer)
    # via non-negative coordinates so it round-trips through the real
    # LMOVE hex-number encode/decode path, not synthesized directly.
    state = GameState()
    origin = HexCoord(5, 14)
    unreachable_target = HexCoord(5, 200)
    state.add_kingdom(KingdomState(1, "Stuckia", Race.HUMAN, Alignment.NEUTRAL, origin))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Mover", location=origin))
    p0 = _lmove_phase("P0", unreachable_target)
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    mover = _leader_with_phase(10, "Mover", "P0", p0)
    mover.plan.segments[0] = PlanSegment(0, 1, (), {"P0": p0, "P1": p1})

    results = run_turn([TurnLeader(mover, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(10, "P0")].result.stopped_chasing is True
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # ordinary dispatch, not a continuation
    assert p1_entry.action is ActionCode.WAIT


def test_continue_active_move_chases_appends_a_straggler_sentinel():
    # Phase 766: mirrors run_leader_plan()'s own identical addendum --
    # a chase-continuation LMOVE can trigger the Naval Hug Coastline
    # stragglers split too. dispatch_phase() itself is mocked here (the
    # split mechanism is already exhaustively tested at the
    # execute_move()/plan_dispatch.py level) to isolate this function's
    # own real job: turning `straggler_result` into a second sentinel.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Mover", location=HexCoord(3, 9)))
    straggler_result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1, new_location=HexCoord(9, 9)
    )
    scripted_result = MoveExecutionResult(
        moved=True,
        battle_report=None,
        exploration=None,
        movement_points_spent=1,
        new_location=HexCoord(4, 9),
        reached_target=True,
        straggler_result=straggler_result,
    )
    active_move_chases = {10: _ActiveMoveChase(kingdom_id=1, target=HexCoord(4, 9))}

    with patch("ak_engine.turn.turn_processor.dispatch_phase", return_value=scripted_result):
        results = _continue_active_move_chases(active_move_chases, "P1", state, BOARD_WIDTH, 0, random.Random(1))

    assert [r.phase_label for r in results] == ["P1", "P1"]
    sentinel = results[1]
    assert sentinel.segment_index == -1
    assert sentinel.action is None
    assert sentinel.result is straggler_result
    assert 10 not in active_move_chases  # reached_target=True -> chase resolved


def test_run_turn_pursue_with_no_target_is_not_registered_for_continuation():
    # "pursuer or target not found" is a terminal reason, not "did not
    # catch up this phase" -- P1's own order must dispatch normally, not
    # be preempted by a chase that can never resolve.
    state = _chase_state()
    p0 = _pursue_phase("P0", 999)  # no such leader
    p1 = _lmove_phase("P1", DECOY)
    pursuer = _leader_with_phase(10, "Pursuer", "P0", p0)
    pursuer.plan.segments[0] = PlanSegment(0, 1, (), {"P0": p0, "P1": p1})

    results = run_turn([TurnLeader(pursuer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(10, "P0")].result.reason == "pursuer or target not found"
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # ordinary _dispatch_single, not a continuation
    assert isinstance(p1_entry.result, MoveExecutionResult)
    assert state.leaders[10].location == DECOY


# -- Chase-continuation registration skips a trailing sentinel (Phase 1041) --


def test_main_dispatch_result_finds_the_real_entry_past_a_trailing_sentinel():
    # Phase 1041 bug fix -- a single dispatched phase can produce more
    # than one PhaseDispatchResult: run_leader_plan() appends a trailing
    # random-encounter sentinel after an LMOVE/PURSUE/TRAIL phase
    # whenever one fires, always with action=None, never the real
    # dispatched ActionCode. Blindly indexing [-1] can grab the sentinel
    # instead of the real result.
    real = PursueExecutionResult(caught_up=False, reason="did not catch up this phase")
    sentinel = RandomEncounterResult(10, ORIGIN, terrain_roll_succeeded=True)
    dispatch_results = [
        PhaseDispatchResult(10, 0, "P0", ActionCode.PURSUE, real, None),
        PhaseDispatchResult(10, -1, "P0", None, sentinel, None),
    ]

    assert _main_dispatch_result(dispatch_results, ActionCode.PURSUE) is real
    assert dispatch_results[-1].result is sentinel  # the pitfall this guards against


def test_register_pursuit_continuation_still_registers_past_a_trailing_sentinel():
    active_pursuits: dict[int, _ActivePursuit] = {}
    phase = _pursue_phase("P0", 20)
    real = PursueExecutionResult(caught_up=False, reason="did not catch up this phase")
    sentinel = RandomEncounterResult(10, ORIGIN, terrain_roll_succeeded=True)
    dispatch_results = [
        PhaseDispatchResult(10, 0, "P0", ActionCode.PURSUE, real, None),
        PhaseDispatchResult(10, -1, "P0", None, sentinel, None),
    ]

    _register_pursuit_continuation(active_pursuits, 10, phase, dispatch_results)

    # Without the fix, dispatch_results[-1].result is the sentinel, the
    # isinstance(result, PursueExecutionResult) check fails, and the
    # chase is never registered for continuation -- even though the
    # real result (still in dispatch_results[0]) said "still chasing."
    assert 10 in active_pursuits
    assert active_pursuits[10].kind == "pursue"
    assert active_pursuits[10].request.target_character_id == 20


def test_register_move_chase_continuation_still_registers_past_a_trailing_sentinel():
    # Same bug, for LMOVE's own continuation registration -- here BOTH
    # the real move and its own Naval Hug Coastline straggler sentinel
    # are MoveExecutionResult instances, so an isinstance check alone
    # (unlike Pursue/Trail's distinct result types) can't tell them
    # apart from a trailing sentinel; matching on `action` can.
    active_move_chases: dict[int, _ActiveMoveChase] = {}
    real = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1, new_location=ORIGIN,
        reached_target=False, stopped_chasing=False,
    )
    sentinel = RandomEncounterResult(10, ORIGIN, terrain_roll_succeeded=True)
    dispatch_results = [
        PhaseDispatchResult(10, 0, "P0", ActionCode.LMOVE, real, None),
        PhaseDispatchResult(10, -1, "P0", None, sentinel, None),
    ]

    _register_move_chase_continuation(active_move_chases, 10, 1, TARGET, dispatch_results)

    assert 10 in active_move_chases
    assert active_move_chases[10].target == TARGET


def test_continue_active_pursuits_stamps_request_onto_the_continuation_result():
    # Phase 1041 bug fix -- the first-phase dispatch (plan_dispatch.py's
    # own _dispatch_pursue()/_dispatch_trail()) always stamps
    # result.request right after dispatching; this continuation path
    # never did, so a real catch-up resolved here (a kill, loot, an
    # intelligence report -- fully applied to state) had .request left
    # None, and report/turn_report.py's own describe_turn_results()
    # unconditionally skips narration whenever .request is None --
    # silently dropping the whole event from the player's turn report.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    request = PursueRequest(target_character_id=20, unconfirmed_extra0=0, tactics=[])
    active_pursuits = {10: _ActivePursuit(kind="pursue", request=request)}

    still_chasing = PursueExecutionResult(caught_up=False, reason="did not catch up this phase")
    with patch("ak_engine.turn.turn_processor.advance_pursuit", return_value=still_chasing):
        results = _continue_active_pursuits(active_pursuits, "P1", state, random.Random(0))

    assert results[0].result.request is request


# -- Patrol / "Characters On Patrol" (Phase 71) -----------------------------


PATROL_HOME = HexCoord(5, 4)
INTRUDER_HEX = _neighbors(PATROL_HOME, _BOUNDS)[0]
MOVE_TARGET = _neighbors(PATROL_HOME, _BOUNDS)[1]


def _patrol_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Patrolia", Race.HUMAN, Alignment.GOOD, PATROL_HOME))
    state.add_kingdom(KingdomState(2, "Intrudia", Race.HUMAN, Alignment.EVIL, INTRUDER_HEX))
    state.add_province(ProvinceState(PATROL_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(INTRUDER_HEX, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(MOVE_TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Patroller", location=PATROL_HOME))
    return state


def _patrol_declare_phase(label: str, own_leader_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.PURSUE, obj=own_leader_id, extra=[0, -1])  # peaceful, no tactics


def test_run_turn_patrol_intercepts_an_adjacent_intruder_and_preempts_a_later_order():
    state = _patrol_state()
    state.add_leader(LeaderState(20, kingdom_id=2, name="Intruder", location=INTRUDER_HEX))
    p0 = _patrol_declare_phase("P0", 10)
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    patroller = _two_phase_leader(10, "Patroller", p0, p1)

    # Spy skill 0 -> a 50% wander roll every phase the intruder is still
    # adjacent -- run_turn always processes all 5 phases (P0-P4)
    # regardless of how many the plan itself uses, and nothing here ever
    # removes the intruder, so the standing Patrol keeps re-checking
    # through P2-P4 too; one scripted success per phase.
    results = run_turn([TurnLeader(patroller, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.0, 0.0] * 5))

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    p0_entry = by_label[(10, "P0")]
    assert p0_entry.segment_index == -1
    assert p0_entry.action is ActionCode.PURSUE
    assert p0_entry.result.intercepted is True
    assert p0_entry.result.target_leader_id == 20

    # P1's own WAIT never dispatched -- the still-adjacent intruder
    # preempted it too (rule (d): the Patrol re-checks every phase).
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.PURSUE
    assert p1_entry.result.target_leader_id == 20


def test_run_turn_patrol_lets_the_scheduled_order_through_when_no_threat():
    state = _patrol_state()  # no intruder anywhere
    p0 = _patrol_declare_phase("P0", 10)
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    patroller = _two_phase_leader(10, "Patroller", p0, p1)

    results = run_turn([TurnLeader(patroller, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    # No threat at P0 -- the Patrol declaration itself produces no
    # dispatch result at all (rule (d): "other orders ... are used").
    assert (10, "P0") not in by_label
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # ordinary dispatch, not preempted
    assert p1_entry.action is ActionCode.WAIT


def test_run_turn_active_patrol_persists_across_a_turn_boundary():
    # Phase 1041 bug fix -- ``active_patrols`` used to be a plain local
    # dict recreated empty at the top of every ``run_turn()`` call, even
    # though rule (d) says Patrol "stays active indefinitely until
    # cancelled by a later Move/Pursue/Trail order" -- unlike Defend/
    # Pursue/Trail, which the rulebook scopes only to "the rest of the
    # turn." A Patrol order used to silently vanish at the next turn
    # boundary even though nothing had ever cancelled it. Now backed by
    # ``GameState.active_patrols``, so it survives a second ``run_turn()``
    # call on the same state.
    state = _patrol_state()  # no intruder yet -- turn 1 just declares the Patrol
    p0 = _patrol_declare_phase("P0", 10)
    patroller_turn1 = _leader_with_phase(10, "Patroller", "P0", p0)

    run_turn([TurnLeader(patroller_turn1, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert 10 in state.active_patrols  # still registered once run_turn() returns

    # Turn 2 -- a fresh run_turn() call on the same state. The patroller
    # submits no new Patrol order at all (just an ordinary WAIT); an
    # intruder has now shown up adjacent to the patrol's home. The
    # standing Patrol from turn 1 should still intercept it.
    state.add_leader(LeaderState(20, kingdom_id=2, name="Intruder", location=INTRUDER_HEX))
    wait_phase = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    patroller_turn2 = _leader_with_phase(10, "Patroller", "P0", wait_phase)

    # The Patrol isn't removed from ``active_patrols`` just because it
    # intercepted once (rule (d): it stays active) -- the intruder is
    # never moved away in this fixture, so every later phase re-checks
    # it too, each consuming its own wander-check roll; a generous
    # buffer also covers unrelated end-of-turn rng draws (e.g. revenue).
    results = run_turn([TurnLeader(patroller_turn2, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9] * 30))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    p0_entry = by_label[(10, "P0")]
    assert p0_entry.segment_index == -1  # standing-order dispatch, preempted the WAIT
    assert p0_entry.action is ActionCode.PURSUE
    assert p0_entry.result.intercepted is True
    assert p0_entry.result.target_leader_id == 20


def test_run_turn_patrol_is_cancelled_by_a_later_move_order():
    # The intruder stays adjacent the whole time -- proves cancellation
    # itself, at P1, wins over interception, not just "there was nothing
    # to intercept."
    state = _patrol_state()
    state.add_leader(LeaderState(20, kingdom_id=2, name="Intruder", location=INTRUDER_HEX))
    p0 = _patrol_declare_phase("P0", 10)
    p1 = _lmove_phase("P1", MOVE_TARGET)
    patroller = _two_phase_leader(10, "Patroller", p0, p1)

    # One roll: P0's own adjacent-hex wander check (succeeds, intercepts).
    # P1's cancelling LMOVE removes the Patrol before any P1 wander check
    # would otherwise run, even though the intruder is still adjacent.
    results = run_turn([TurnLeader(patroller, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.0, 0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(10, "P0")].result.intercepted is True

    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # cancellation ran before dispatch -- not preempted
    assert p1_entry.action is ActionCode.LMOVE
    assert isinstance(p1_entry.result, MoveExecutionResult)
    assert state.leaders[10].location == MOVE_TARGET


# -- Defend battle-loss cancellation (Phase 72) ------------------------------


# Phase 314: DL_FIRST_ATTACKER_ORIGIN/DL_SECOND_COVERED/DL_SECOND_ATTACKER_ORIGIN
# moved -- neighbors()'s own real-data-sourced parity fix (see turn/movement.py's
# docstring) changed which hexes are actually adjacent to DL_FIRST_COVERED/
# DL_SECOND_COVERED; DL_HOME and DL_FIRST_COVERED are unaffected.
DL_HOME = HexCoord(5, 4)
DL_FIRST_COVERED = HexCoord(5, 3)  # adjacent to DL_HOME
DL_FIRST_ATTACKER_ORIGIN = HexCoord(6, 3)  # adjacent to DL_FIRST_COVERED
DL_SECOND_COVERED = HexCoord(4, 3)  # adjacent to DL_FIRST_COVERED (the leader's post-reinforcement location)
DL_SECOND_ATTACKER_ORIGIN = HexCoord(3, 3)  # adjacent to DL_SECOND_COVERED


def _defend_loss_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, DL_FIRST_ATTACKER_ORIGIN))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, DL_HOME))
    for coord in (DL_HOME, DL_FIRST_COVERED, DL_SECOND_COVERED):
        state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(DL_FIRST_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(DL_SECOND_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(100, kingdom_id=2, name="Defender", location=DL_HOME))
    state.add_army(ArmyState(901, 2, ArmyType.GARRISON, Quality.GREEN, DL_HOME, commanded_by=100, movement_points=2))
    return state


def _defend_loss_attacker(leader_id: int, army_id: int, origin: HexCoord, target: HexCoord, label: str) -> Leader:
    return _leader_with_phase(leader_id, "Attacker", label, _lmove_phase(label, target))


def test_run_turn_defend_battle_loss_blocks_a_later_redeclaration():
    # seed 1: the attacker wins this exact matchup (HVY_CAVALRY/ELITE vs
    # GARRISON/GREEN) -- verified deterministic for this fixture. (Phase
    # 296: reselected after fight_battle()'s own new terrain-line-length-
    # cap roll shifted the RNG stream -- seed 0 no longer lands here.)
    state = _defend_loss_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=DL_SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _defend_phase("P2"))
    attacker = _defend_loss_attacker(200, 902, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_attacker = _defend_loss_attacker(300, 903, DL_SECOND_ATTACKER_ORIGIN, DL_SECOND_COVERED, "P3")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1), TurnLeader(second_attacker, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(1),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(200, "P1")].result.battle_report.battle_result.winner == "attacker"  # defender lost

    # P2's Defend re-declaration never re-arms coverage -- reinforcement
    # never relocates the leader again for the P3 invasion, regardless of
    # whatever their own army independently did (e.g. retreated).
    assert state.leaders[100].location == DL_FIRST_COVERED


@patch("ak_engine.turn.battle_orchestrator._resolve_duel_death", new=lambda *args, **kwargs: None)  # incidental duel: keep the commander alive
def test_run_turn_defend_battle_win_registers_a_pursuit_of_the_defeated_attacker_instead_of_redeclaring():
    # seed 1: the defender wins this exact matchup -- verified
    # deterministic for this fixture. (Phase 370: the shared
    # _defend_loss_state()'s own GARRISON/GREEN defender is categorically
    # outmatched by an ELITE HVY_CAVALRY attacker under the real,
    # deterministic column_bres formula -- luck's own bounded R_s
    # multiplier, up to ~2.5x/4x, was never going to be enough to flip
    # that big a strength gap, unlike the pre-Phase-370 model's plain
    # probability-then-coin-flip win roll. Evened the defender's own army
    # up to the attacker's own type/quality so a genuine coin-flip battle
    # -- decided by the real luck draws, not an unwinnable mismatch -- is
    # possible again. Phase 744: both kingdoms here are Alignment.GOOD, so
    # turning on real per-army Fanaticism rolls (apply_fanaticism=True at
    # every real production battle call site) makes this a genuinely live
    # coin-flip, not just an RNG-position shift -- seed 0 no longer lands
    # a defender win, reselected to seed 1.
    #
    # 2026-11-01: this test used to be named "...does_not_block_a_later_
    # redeclaration" and asserted the P2 Defend order re-armed coverage
    # for the P3 invasion -- stale now that a win registers a real
    # pursuit of the defeated attacker (_apply_defend_battle_win()).
    # That pursuit preempts the P2 phase exactly like any other active
    # chase, so the P2 Defend order is never even dispatched. The
    # attacker's own army is captured (commanded_by=None) by the loss
    # itself, so the very next phase's pursuit continuation immediately
    # finds an army-leading mismatch and ends there, never re-arming
    # Defend -- the P3 invasion walks in uncontested as a result, the
    # opposite of this test's old name.
    state = _defend_loss_state()
    state.add_army(ArmyState(901, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_HOME, commanded_by=100, movement_points=2))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=DL_SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _defend_phase("P2"))
    attacker = _defend_loss_attacker(200, 902, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_attacker = _defend_loss_attacker(300, 903, DL_SECOND_ATTACKER_ORIGIN, DL_SECOND_COVERED, "P3")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1), TurnLeader(second_attacker, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(1),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(200, "P1")].result.battle_report.battle_result.winner == "defender"  # defender won

    # P2's own real Defend re-declaration is preempted -- the pursuit
    # registered by the win dispatches instead (segment_index=-1, same
    # sentinel every other active-chase continuation uses). The defeated
    # attacker's commander retreated *with* his army ([7.4], user ruling
    # 2026-11-24), so the pursuit finds the same leader leading the same
    # army and catches up for a real fight (it used to end in an
    # "army-leading mismatch" because the army retreated without him).
    p2_entry = by_label[(100, "P2")]
    assert p2_entry.segment_index == -1
    assert p2_entry.action is ActionCode.PURSUE
    assert p2_entry.result.caught_up and p2_entry.result.combat_occurred
    assert state.leaders[200].location == state.armies[902].location

    # Defend never re-armed -- the P3 invasion walks in uncontested.
    assert by_label[(300, "P3")].result.battle_report is None


DL_ILLEGAL_ORIGIN = HexCoord(4, 3)  # adjacent to DL_FIRST_COVERED, distinct from the other DL_* origins


@patch("ak_engine.turn.battle_orchestrator._resolve_duel_death", new=lambda *args, **kwargs: None)  # incidental duel: keep the commander alive
def test_run_turn_defend_battle_loss_blocks_a_later_redeclaration_with_a_leading_group_error():
    # Phase 299 regression: _dispatch_multi_attacker_lmove() appends a
    # validation-error entry for an illegal mover BEFORE the real
    # MultiAttackerMoveResult entries for the movers who actually joined
    # the battle (see
    # test_run_turn_excludes_an_illegal_contested_mover_but_still_groups_the_rest
    # for that ordering in isolation). _apply_defend_battle_loss used to
    # trust dispatch_results[0] to carry the real battle, so when a group
    # like that reinforced a Defend leader's own province, the loss went
    # undetected and the Defend order was never cancelled. Reproduced
    # here by declaring the illegal mover first in the TurnLeader list so
    # its error lands at index 0 of the group's own dispatch_results.
    state = _defend_loss_state()
    state.add_province(ProvinceState(DL_ILLEGAL_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.provinces[DL_ILLEGAL_ORIGIN].contested_by_kingdom_id = 1  # self-contested -- illegal to move out of

    state.add_leader(LeaderState(400, kingdom_id=1, name="IllegalMover", location=DL_ILLEGAL_ORIGIN))
    state.add_army(
        ArmyState(904, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_ILLEGAL_ORIGIN, commanded_by=400, movement_points=3)
    )
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    state.add_leader(LeaderState(250, kingdom_id=1, name="SecondWave", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(905, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=250, movement_points=3)
    )
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=DL_SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )

    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _defend_phase("P2"))
    illegal_mover = _leader_with_phase(400, "IllegalMover", "P1", _lmove_phase("P1", DL_FIRST_COVERED))
    attacker = _defend_loss_attacker(200, 902, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_wave = _defend_loss_attacker(250, 905, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_attacker = _defend_loss_attacker(300, 903, DL_SECOND_ATTACKER_ORIGIN, DL_SECOND_COVERED, "P3")

    results = run_turn(
        [
            TurnLeader(defender, 2),
            TurnLeader(illegal_mover, 1),  # declared first -- its error lands at group index 0
            TurnLeader(attacker, 1),
            TurnLeader(second_wave, 1),
            TurnLeader(second_attacker, 1),
        ],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(1),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[400].error is not None
    assert by_leader[400].result is None
    assert isinstance(by_leader[200].result, MultiAttackerMoveResult)
    assert isinstance(by_leader[250].result, MultiAttackerMoveResult)
    assert sorted(by_leader[200].result.battle.leader_ids) == [200, 250]
    assert by_leader[200].result.battle.report.battle_result.winner == "attacker"  # defender lost

    # Despite the illegal mover's error occupying index 0 of the group's
    # own dispatch_results, the fix still finds the real battle result and
    # correctly cancels the Defend order on loss -- P2's re-declaration
    # never re-arms coverage for the P3 invasion.
    assert state.leaders[100].location == DL_FIRST_COVERED


# -- build_missed_deadline_turn_leaders() (Phase 138) --


def test_build_missed_deadline_turn_leaders_defends_the_army_commanding_leader():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=HexCoord(3, 3)))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, HexCoord(3, 3), commanded_by=10))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)

    assert len(turn_leaders) == 1
    tl = turn_leaders[0]
    assert tl.kingdom_id == 1
    assert tl.leader.leader_id == 10
    phases = tl.leader.plan.segments[0].phases
    assert phases["P0"].action is ActionCode.DEFEND
    for label in ("P1", "P2", "P3", "P4"):
        assert phases[label].action is ActionCode.WAIT


def test_build_missed_deadline_turn_leaders_waits_the_armyless_leader():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Advisor", location=HexCoord(4, 4)))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)

    assert len(turn_leaders) == 1
    phases = turn_leaders[0].leader.plan.segments[0].phases
    for label in ("P0", "P1", "P2", "P3", "P4"):
        assert phases[label].action is ActionCode.WAIT


def test_build_missed_deadline_turn_leaders_only_includes_that_kingdoms_own_leaders():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otheria", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(3, 3)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=HexCoord(4, 4)))
    state.add_leader(LeaderState(30, kingdom_id=2, name="C", location=HexCoord(9, 9)))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)

    assert {tl.leader.leader_id for tl in turn_leaders} == {10, 20}
    assert all(tl.kingdom_id == 1 for tl in turn_leaders)


def test_build_missed_deadline_turn_leaders_dispatches_cleanly_through_run_turn():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=HexCoord(3, 3)))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, HexCoord(3, 3), commanded_by=10))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Advisor", location=HexCoord(4, 4)))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)
    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert len(results) == 10  # 2 leaders x 5 phases
    assert all(r.error is None for r in results)
    general_p0 = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0")
    advisor_p0 = next(r for r in results if r.leader_id == 20 and r.phase_label == "P0")
    assert general_p0.action is ActionCode.DEFEND
    assert advisor_p0.action is ActionCode.WAIT
    assert isinstance(advisor_p0.result, NoOpResult)


# ---------------------------------------------------------------------------
# Gate Angel / VALHALLA visit (Phase 199) -- finalize_gate_angel_visit()
# (Phase 196) wired in after the PHASE_LABELS loop. GATE_ANGEL_ELIGIBLE_
# ALIGNMENTS is (GOOD, DRUID, NEUTRAL, PAGAN, EVIL), so choice_indices=[0]
# picks GOOD as the due alignment for turn/cast_execution.py's own draw.
# ---------------------------------------------------------------------------


def _cast_gate_angel_phase(label: str) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.CAST, obj=Spell.GATE_ANGEL.value, extra=[0])


def test_run_turn_spawns_a_valhalla_visitor_after_a_successful_gate_angel_cast():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3), is_king=True))
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_gate_angel_phase("P0")), 1)]
    # [0] -> due alignment GOOD (matches kingdom 1). GameState.turn_number
    # defaults to 1, so visitor_selection is deterministic (Phase 386: the
    # roster's own final record, no rng.choice consumed at all).
    rng = ScriptedRandom([0.0], choice_indices=[0])

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=rng)

    visit_results = [r for r in results if r.phase_label == "gate-angel-visit"]
    assert len(visit_results) == 1
    visitor = visit_results[0].result
    assert visit_results[0].leader_id == VALHALLA_VISITOR_LEADER_ID
    assert visit_results[0].action is None
    assert visitor.leader_id == VALHALLA_VISITOR_LEADER_ID
    assert visitor.name == VALHALLA_ROSTER[Alignment.GOOD][-1].name
    assert state.leaders[VALHALLA_VISITOR_LEADER_ID] is visitor
    # Spawned beside kingdom 1's own King (leader 10), per the rulebook.
    assert visitor.location == HexCoord(3, 3)
    # The visitor's own fixed item is real ItemInstance state, not just the
    # LeaderState -- confirms finalize_gate_angel_visit()'s own item grant
    # flowed through run_turn() end to end.
    items = state.items_held_by(VALHALLA_VISITOR_LEADER_ID)
    assert len(items) == 1
    assert items[0].treasure == VALHALLA_ROSTER[Alignment.GOOD][-1].fixed_item


def test_run_turn_produces_no_gate_angel_result_when_the_cast_targets_the_wrong_alignment():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3)))
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_gate_angel_phase("P0")), 1)]
    # [0] -> due alignment GOOD -- doesn't match kingdom 1's own NEUTRAL
    rng = ScriptedRandom([0.0], choice_indices=[0])

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=rng)

    assert not [r for r in results if r.phase_label == "gate-angel-visit"]
    assert VALHALLA_VISITOR_LEADER_ID not in state.leaders


def test_run_turn_produces_no_gate_angel_result_when_no_leader_casts_it():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3)))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert not [r for r in results if r.phase_label == "gate-angel-visit"]
    assert VALHALLA_VISITOR_LEADER_ID not in state.leaders


def test_run_turn_ordinary_valhalla_visit_fires_with_no_gate_angel_caster_anywhere():
    # Phase 756: uses _run_turn_unfiltered directly (not this file's own
    # run_turn() wrapper, which neutralizes the ordinary visit for every
    # other test in this file) -- the one dedicated end-to-end proof that
    # a real turn, with nobody anywhere casting Gate Angel, still produces
    # a real "valhalla-visit" sentinel via turn_processor.py's own wiring.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="King", location=HexCoord(3, 3), is_king=True))

    results = _run_turn_unfiltered([], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    visit_results = [r for r in results if r.phase_label == "valhalla-visit"]
    assert len(visit_results) == 1
    assert visit_results[0].result.kingdom_id == 1
    assert not [r for r in results if r.phase_label == "gate-angel-visit"]


# ---------------------------------------------------------------------------
# Analytical Psychology end-of-turn Charm revert (Phase 302) --
# run_turn()'s own end-of-turn sweep, _revert_analytical_psychology_charms().
# ---------------------------------------------------------------------------


def _cast_charm_phase(label: str, target_leader_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.CAST, obj=Spell.CHARM.value, extra=[target_leader_id])


def test_run_turn_reverts_an_analytical_psychology_protected_charm_at_end_of_turn():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Casteria", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_kingdom(KingdomState(2, "Protectia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.kingdoms[2].discoveries.add(Discovery.ANALYTICAL_PSYCHOLOGY)
    caster = LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3))
    target = LeaderState(78, kingdom_id=2, name="Protected Hero", location=HexCoord(3, 3))
    state.add_leader(caster)
    state.add_leader(target)
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_charm_phase("P0", 78)), 1)]

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(0))

    cast_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0")
    assert cast_result.result.applied is True  # the spell really did fire, not silently blocked
    # By the time run_turn() returns, the end-of-turn sweep has already put
    # the target back under their own original kingdom (2), not the
    # caster's (1) -- proving the revert genuinely ran, not just that the
    # Charm itself was rejected.
    assert state.leaders[78].kingdom_id == 2
    assert state.leaders[78].analytical_psychology_revert_kingdom_id is None


def test_run_turn_does_not_revert_an_ordinary_unprotected_charm():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Casteria", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_kingdom(KingdomState(2, "Ordinaria", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    caster = LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3))
    target = LeaderState(78, kingdom_id=2, name="Ordinary Hero", location=HexCoord(3, 3))
    state.add_leader(caster)
    state.add_leader(target)
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_charm_phase("P0", 78)), 1)]

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(0))

    cast_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0")
    assert cast_result.result.applied is True
    assert state.leaders[78].kingdom_id == 1  # stays charmed -- no protection, no revert


def test_run_turn_decomposes_the_graveyard_once_at_turn_end_when_over_the_world_cap():
    # Phase 309: turn/skeletal_decay.py decompose_graveyard() runs once,
    # after every phase, alongside _revert_analytical_psychology_charms
    # -- see run_turn()'s own docstring. A trivial single-WAIT-phase plan
    # is enough to exercise the end-of-run_turn() housekeeping sweep.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0)))
    for _ in range(340):
        state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HexCoord(0, 0)))
    for _ in range(20):
        state.record_battle_death(HexCoord(1, 1), ArmyType.HVY_CAVALRY, Quality.AVERAGE, kingdom_id=1)
    # 340 + 20 = 360 > 350 -- the 10 oldest dead rot, bringing the world back to 350.

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert len(state.battle_graveyard[HexCoord(1, 1)]) == 10


# -- Per-turn treasury maintenance debit (Phase 404) -----------------------


def test_run_turn_debits_expected_expenses_from_treasury_once_at_turn_end():
    # Phase 404: turn/expenses.py apply_turn_maintenance() runs once,
    # alongside decompose_graveyard() -- see run_turn()'s own docstring.
    # The King himself contributes 0 leader pay (see expenses.py's own
    # leader_pay()), so the only expected debit here is the one Legion's
    # army maintenance (2 gold, ARMY_TABLE), a concrete, non-circular
    # expected value.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].treasury = 50
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0), is_king=True))
    state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0)))

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.kingdoms[1].treasury == 48


# -- Per-turn treasury revenue credit (Phase 412) --------------------------


def test_run_turn_credits_expected_revenues_to_treasury_before_debiting_expenses():
    # Phase 412: turn/tax_base.py apply_turn_revenue() now runs once per
    # turn, before apply_turn_maintenance() -- rulebook [9]'s own explicit
    # "si incassano le rendite, quindi si paga il mantenimento" ordering.
    # Same one-Legion-army expected debit (2 gold) as the Phase 404 test
    # above, plus a real 10-gold province tax base as the new credit.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].treasury = 50
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0), is_king=True))
    state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=10))

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.kingdoms[1].treasury == 58


# -- Werebeast bite-transform, end-of-turn half (Phase 392) ---------------


def test_apply_werebeast_transformations_converts_a_queued_army_to_werebeasts():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=HexCoord(9, 9))
    state.add_army(army)
    state.werebeast_bitten_army_ids.add(101)

    _apply_werebeast_transformations(state)

    assert state.armies[101].army_type is ArmyType.WEREBEASTS
    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_transformations_silently_skips_an_army_that_no_longer_exists():
    state = GameState()
    state.werebeast_bitten_army_ids.add(999)  # already destroyed before this point

    _apply_werebeast_transformations(state)  # must not raise

    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_transformations_no_op_when_nothing_was_bitten():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=HexCoord(9, 9))
    state.add_army(army)

    _apply_werebeast_transformations(state)

    assert state.armies[101].army_type is ArmyType.LEGION


# -- Phase 573: the turn-boundary reset (movement_points/march-naval
# bonus flags/recruited_this_turn/turn_number) this project never had.


def test_replenish_turn_scoped_state_refills_movement_points_to_the_real_rate():
    state = _base_state()
    depleted = ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=0)
    state.add_army(depleted)

    _replenish_turn_scoped_state(state)

    assert state.armies[101].movement_points == ARMY_TABLE[ArmyType.HVY_CAVALRY].speed


def test_replenish_turn_scoped_state_does_not_crash_for_an_army_type_with_no_army_table_entry():
    # Phase 820 bug fix: 8 real, catalog-named ArmyType members (Vampires,
    # Marauders, Shamans, Crossbow, Javelins, Artillery, Spiders, D-Turtle
    # -- models/army_type.py's own Phase 383 addendum) have no ARMY_TABLE
    # entry at all. Before the fix, the bare ARMY_TABLE[army.army_type]
    # lookup here raised KeyError for any of them -- the one unconditional,
    # unguarded step at the tail of every run_turn() call, so a single
    # such army anywhere on the map would crash the entire turn's
    # processing. No current world-generation path constructs one, but
    # GameState.add_army() is a fully public API. Fixed to leave
    # movement_points untouched (no invented value) instead of crashing.
    state = _base_state()
    state.add_army(ArmyState(101, 1, ArmyType.MARAUDERS, Quality.AVERAGE, ORIGIN, movement_points=3))

    _replenish_turn_scoped_state(state)  # must not raise

    assert state.armies[101].movement_points == 3
    assert state.armies[101].unhireable_this_turn is False  # every other field still resets normally


def test_replenish_turn_scoped_state_clears_march_and_naval_bonus_flags():
    state = _base_state()
    army = ArmyState(
        101,
        1,
        ArmyType.HVY_CAVALRY,
        Quality.ELITE,
        ORIGIN,
        march_bonus_applied_this_turn=True,
        naval_bonus_applied_this_turn=True,
    )
    state.add_army(army)

    _replenish_turn_scoped_state(state)

    assert state.armies[101].march_bonus_applied_this_turn is False
    assert state.armies[101].naval_bonus_applied_this_turn is False


def test_replenish_turn_scoped_state_clears_recruited_this_turn():
    state = _base_state()
    state.provinces[ORIGIN].recruited_this_turn = {ArmyType.LEGION: 1}

    _replenish_turn_scoped_state(state)

    assert state.provinces[ORIGIN].recruited_this_turn == {}


def test_replenish_turn_scoped_state_clears_treasury_raid_attempts_this_turn():
    state = _base_state()
    state.kingdoms[2].treasury_raid_attempts_this_turn = 3

    _replenish_turn_scoped_state(state)

    assert state.kingdoms[2].treasury_raid_attempts_this_turn == 0


def test_replenish_turn_scoped_state_clears_unhireable_this_turn():
    state = _base_state()
    army = ArmyState(101, None, ArmyType.LEGION, Quality.AVERAGE, ORIGIN, unhireable_this_turn=True)
    state.add_army(army)

    _replenish_turn_scoped_state(state)

    assert state.armies[101].unhireable_this_turn is False


def test_replenish_turn_scoped_state_clears_recruited_this_turn():
    # Bug fix, sourced directly from the user (2026-10-29): otherwise a
    # freshly levied army would stay permanently un-Pick-Up-able for
    # the rest of the game (turn/plan_dispatch.py _dispatch_pick_up()).
    state = _base_state()
    army = ArmyState(101, None, ArmyType.LEGION, Quality.AVERAGE, ORIGIN, recruited_this_turn=True)
    state.add_army(army)

    _replenish_turn_scoped_state(state)

    assert state.armies[101].recruited_this_turn is False


def test_replenish_turn_scoped_state_clears_oratory_boosted_this_turn():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, oratory_boosted_this_turn=True))

    _replenish_turn_scoped_state(state)

    assert state.leaders[10].oratory_boosted_this_turn is False


def test_replenish_turn_scoped_state_clears_terrain_override():
    # Phase 1046 bug fix: Part Sea/Flood's own "for the rest of the
    # turn" terrain change (turn/cast_execution.py) had no reset call
    # anywhere -- a Part Sea'd/Flooded province stayed permanently
    # transformed for the rest of the game.
    state = _base_state()
    state.provinces[ORIGIN].terrain_override = Terrain.PLAINS

    _replenish_turn_scoped_state(state)

    assert state.provinces[ORIGIN].terrain_override is None


def test_replenish_turn_scoped_state_clears_tax_modifier_percent_and_earthquake_flat_reduction():
    # Phase 1046 bug fix: Bless's "+60% for one turn" and Earthquake's
    # "-100%"/Reinforced-Concrete-defended flat reduction, both
    # documented one-turn effects, had no reset call anywhere either.
    state = _base_state()
    state.provinces[ORIGIN].tax_modifier_percent = 60
    state.provinces[ORIGIN].earthquake_flat_reduction = 3

    _replenish_turn_scoped_state(state)

    assert state.provinces[ORIGIN].tax_modifier_percent == 0
    assert state.provinces[ORIGIN].earthquake_flat_reduction == 0


def test_run_turn_replenishes_movement_points_at_the_end():
    # A real moderator running turn after turn via orchestrator.
    # process_turn() needs every army's movement pool back for the next
    # turn -- run_turn() itself, not just the private helper, must do
    # this (it's the one real per-turn boundary a caller ever sees).
    state = _base_state()
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=0))

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.armies[101].movement_points == ARMY_TABLE[ArmyType.HVY_CAVALRY].speed


def test_run_turn_increments_the_turn_number():
    state = _base_state()
    state.turn_number = 5

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.turn_number == 6


# -- Phase 575: action_casts_used, the fourth "never reset -- caller's
# job" field, missed by Phase 573's own audit and fixed here.


def test_replenish_turn_scoped_state_clears_action_casts_used():
    state = _base_state()
    state.action_casts_used[(10, Ability.WHITE)] = 3

    _replenish_turn_scoped_state(state)

    assert state.action_casts_used == {}


# -- Phase 874: treat_permissions, the fifth "never reset -- caller's
# job" field. Rulebook [3.4]: a Treat grant is scoped to "this
# gameturn" -- nothing in production currently populates the field (no
# Treat-order decoder exists yet), so this is a proactive, sourced fix
# against the exact bug class Phase 573/575/670/702 already found and
# fixed for every sibling field in this same family.


def test_replenish_turn_scoped_state_clears_treat_permissions():
    state = _base_state()
    state.treat_permissions.add((1, 2))

    _replenish_turn_scoped_state(state)

    assert state.treat_permissions == set()


def test_run_turn_clears_action_casts_used_at_the_end():
    state = _base_state()
    state.action_casts_used[(10, Ability.WHITE)] = 3

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.action_casts_used == {}


# -- 2026-11-04: RULES.AK [3.18]'s own "treasury at the start of the
# gameturn" snapshot for the Give Gold 10% cap -- taken once, at the
# very start of every run_turn() call. See turn/turn_processor.py's own
# call site and GameState.KingdomState.treasury_at_turn_start's own
# docstring.


def test_run_turn_snapshots_treasury_at_the_very_start_of_the_turn():
    state = _base_state()
    state.kingdoms[1].treasury = 1000

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    # apply_turn_revenue()/apply_turn_maintenance() (end-of-turn financial
    # steps) may have since changed the live treasury, but the snapshot
    # itself must still read this turn's own starting value, 1000.
    assert state.kingdoms[1].treasury_at_turn_start == 1000


def test_run_turn_resets_gold_given_this_turn_for_the_next_turn():
    state = _base_state()
    state.kingdoms[1].gold_given_this_turn = 60  # left over from a Give last turn

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.kingdoms[1].gold_given_this_turn == 0


# -- 2026-11-03: RULES.AK [8.3]'s own Evil/Undead Break Treat timing
# exception, end-to-end through two real run_turn() calls -- see
# turn/diplomacy.py's own module docstring for the full mechanics.


def test_run_turn_ordinary_kings_break_treat_relation_change_waits_for_next_turn():
    state = _base_state()  # kingdom 1 Good, kingdom 2 Neutral -- neither Evil nor Undead
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.add((1, 2))

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    # Not yet visible to this turn's own combat, and no report notice
    # for it yet either.
    assert state.is_allied(1, 2)
    assert state.diplomacy_relation_change_notices == []
    assert frozenset({1, 2}) in state.pending_break_treat_transitions

    # Next turn's own orders carry nothing further for this pair --
    # break_treat_orders was already cleared by the first run_turn()
    # call's own end-of-turn _replenish_turn_scoped_state().
    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(2))

    assert not state.is_allied(1, 2)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert frozenset({1, 2}) not in state.pending_break_treat_transitions
    assert state.diplomacy_relation_change_notices == [
        (1, 2, DiplomaticRelation.ALLIED, DiplomaticRelation.NEUTRAL)
    ]


def test_run_turn_evil_kings_break_treat_relation_change_is_immediate():
    state = _base_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.break_treat_orders.add((1, 2))

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    # Visible to this same turn's own combat, per [8.3]'s own exception.
    assert not state.is_allied(1, 2)
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL
    assert frozenset({1, 2}) not in state.pending_break_treat_transitions
    assert state.diplomacy_relation_change_notices == [
        (1, 2, DiplomaticRelation.ALLIED, DiplomaticRelation.NEUTRAL)
    ]


# -- 2026-11-05: RULES.AK [8.2]'s own Treat timing -- a mutual Treat
# with at least one Druidic party is immediate; an ordinary mutual
# Treat waits for next turn, same shape as Break Treat's own split.


def test_run_turn_ordinary_mutual_treat_relation_change_waits_for_next_turn():
    state = _base_state()  # neither kingdom 1 nor 2 is Druidic
    state.treat_permissions.update({(1, 2), (2, 1)})

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.NEUTRAL  # still, this turn
    assert state.diplomacy_relation_change_notices == []
    assert frozenset({1, 2}) in state.pending_treat_transitions

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(2))

    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.is_allied(1, 2)
    assert frozenset({1, 2}) not in state.pending_treat_transitions
    assert state.diplomacy_relation_change_notices == []  # never announced, confirmed with the user


def test_run_turn_druidic_mutual_treat_relation_change_is_immediate():
    state = _base_state()
    state.kingdoms[1].alignment = Alignment.DRUID
    state.treat_permissions.update({(1, 2), (2, 1)})

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    # Visible to this same turn's own combat, per [8.2]'s own exception.
    assert state.diplomatic_relation(1, 2) is DiplomaticRelation.ALLIED
    assert state.is_allied(1, 2)
    assert frozenset({1, 2}) not in state.pending_treat_transitions
    assert state.diplomacy_relation_change_notices == [
        (1, 2, DiplomaticRelation.NEUTRAL, DiplomaticRelation.ALLIED)
    ]


# -- Phase 576: illusory_fog_active, found the same way action_casts_used
# was (re-auditing every remaining "not auto-cleared" field comment) --
# the rulebook's own text says Illusory Fog "dissipates at the end of the
# gameturn," but the flag it sets had no clearing site anywhere despite
# already having a real battle-strength consumer.


def test_replenish_turn_scoped_state_clears_illusory_fog_active():
    state = _base_state()
    state.provinces[ORIGIN].illusory_fog_active = True

    _replenish_turn_scoped_state(state)

    assert state.provinces[ORIGIN].illusory_fog_active is False


def test_run_turn_clears_illusory_fog_active_at_the_end():
    state = _base_state()
    state.provinces[ORIGIN].illusory_fog_active = True

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.provinces[ORIGIN].illusory_fog_active is False


# -- Phase 674: _dispatch_mutual_encounter() picks up the non-initiator's
# own real Special Encounter Plan automatically, via execute_challenge()'s
# own eligibility check -- no code change was needed in turn_processor.py
# itself (Design point 6 of the Phase 674 plan); this proves that claim
# end to end rather than only by inspection.


def _leader_with_phase_and_sep(leader_id: int, name: str, label: str, phase: PlanPhase, sp: tuple) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(leader_id=leader_id, segments=[PlanSegment(0, 0, sp, {label: phase})]),
    )


def test_run_turn_mutual_encounter_lets_the_targets_own_special_encounter_plan_decide_the_winner():
    # Leader 10 (higher Melee skill) challenges leader 20; without any
    # Special Encounter Plan of its own, leader 20 has no leading Cast
    # to resolve and the ordinary Melee tactic proceeds -- the higher-
    # skilled challenger (10) wins, exactly like the pre-existing mutual-
    # Challenge test above. Giving leader 20 a real, decoded SP: CAST
    # tactic (SP: 0 <spell> -1) flips the outcome: its own leading cast
    # (mocked to a decisive "b", target-wins) resolves before the
    # challenger's Melee tactic is ever reached.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9)))
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN, skills=_skills_with(Ability.MELEE, 0, 9)))
    challenge_phase_10 = _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)
    challenge_phase_20 = _encounter_phase("P0", ActionCode.CHALLENGE, 10, melee=True)
    leaders_no_sep = [
        _leader_with_phase_and_sep(10, "A", "P0", challenge_phase_10, ()),
        _leader_with_phase_and_sep(20, "B", "P0", challenge_phase_20, ()),
    ]

    no_sep_results = run_turn(
        [TurnLeader(leaders_no_sep[0], 1), TurnLeader(leaders_no_sep[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
    )

    by_leader_no_sep = {r.leader_id: r for r in no_sep_results}
    assert by_leader_no_sep[10].result.winner_leader_id == 10  # higher-skilled challenger wins, no SEP involved

    state2 = _base_state()
    state2.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9)))
    state2.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN, skills=_skills_with(Ability.MELEE, 0, 9)))
    leaders_with_sep = [
        _leader_with_phase_and_sep(10, "A", "P0", challenge_phase_10, ()),
        _leader_with_phase_and_sep(20, "B", "P0", challenge_phase_20, (0, Spell.FIREBALL.value, -1)),
    ]

    # The inner cast call plays target-as-caster: its own "a" (the inner
    # caster, i.e. the real target) winning flips to this function's
    # outer "b" -- see resolve_challenge_combat()'s own _resolve_target_
    # cast() flip convention (module docstring / Phase 674 addendum).
    with patch("ak_engine.turn.challenge_execution._resolve_personal_combat_cast", return_value="a"):
        with_sep_results = run_turn(
            [TurnLeader(leaders_with_sep[0], 1), TurnLeader(leaders_with_sep[1], 2)],
            state2,
            board_width=BOARD_WIDTH,
            rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
        )

    by_leader_with_sep = {r.leader_id: r for r in with_sep_results}
    assert state2.leaders[20].special_encounter_plan == (SearchTactic(Maneuver.CAST, Spell.FIREBALL.value),)
    assert by_leader_with_sep[10].result.winner_leader_id == 20  # target's own leading Cast decided it instead

    assert state.provinces[ORIGIN].illusory_fog_active is False


# -- Phase 781: MERCHERO.md's own autonomous wandering ----------------------


from ak_engine.turn.turn_processor import _kingdom_submitted_real_orders
from ak_engine.turn.wandering_units import WanderRelocation


def test_kingdom_submitted_real_orders_true_when_any_leader_has_a_real_p0_action():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(11, kingdom_id=1, name="B", location=HexCoord(0, 0)))
    p0_real = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    p0_none = PlanPhase(label="P0", action=ActionCode.NO_ACTION, obj=0, extra=[0])
    leader_a = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0_none})]))
    leader_b = Leader(11, "B", ActionPlan(11, [PlanSegment(0, 0, (), {"P0": p0_real})]))

    result = _kingdom_submitted_real_orders([TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state)

    assert result == {1: True}


def test_kingdom_submitted_real_orders_false_when_every_leader_is_empty_or_absent():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(11, kingdom_id=1, name="B", location=HexCoord(0, 0)))
    p0_none = PlanPhase(label="P0", action=ActionCode.NO_ACTION, obj=0, extra=[0])
    leader_a = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0_none})]))
    # leader 11 not present in turn_leaders at all this turn.

    result = _kingdom_submitted_real_orders([TurnLeader(leader_a, 1)], state)

    assert result == {1: False}


def test_kingdom_submitted_real_orders_omits_a_kingdom_with_no_registered_leaders():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    result = _kingdom_submitted_real_orders([], state)
    assert result == {}


def test_run_turn_appends_wandering_relocations_as_sentinel_results():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    relocation = WanderRelocation("hero", 55, ORIGIN, TARGET)
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0})]))

    with patch("ak_engine.turn.turn_processor.resolve_wandering", return_value=[relocation]):
        results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    wander_entries = [r for r in results if r.phase_label == "hero-wander"]
    assert len(wander_entries) == 1
    assert wander_entries[0].leader_id == 55
    assert wander_entries[0].result is relocation
    assert wander_entries[0].action is None
    assert wander_entries[0].segment_index == -1


def test_run_turn_labels_an_army_relocation_distinctly_from_a_hero_one():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    relocation = WanderRelocation("army", 301, ORIGIN, TARGET)
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0})]))

    with patch("ak_engine.turn.turn_processor.resolve_wandering", return_value=[relocation]):
        results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    wander_entries = [r for r in results if r.phase_label == "army-wander"]
    assert len(wander_entries) == 1
    assert wander_entries[0].leader_id == 301
    assert wander_entries[0].result is relocation


def test_run_turn_end_to_end_hero_wander_and_king_orders_flag_gate():
    # A real, unmocked end-to-end case: an independent Hero standing in
    # Kingdom 1's own home province wanders under a favorable scripted
    # roll sequence, and the same setup is genuinely blocked once
    # Kingdom 1's own King submits no real order this turn.
    state = GameState()
    home = HexCoord(2, 2)
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, home))
    state.board_width = 5
    state.board_height = 5
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="King", location=home, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=None, name="Wanderer", location=home))

    p0_real = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    king_leader = Leader(1, "King", ActionPlan(1, [PlanSegment(0, 0, (), {"P0": p0_real})]))

    results = run_turn([TurnLeader(king_leader, 1)], state, board_width=5, rng=random.Random(3))

    wander_entries = [r for r in results if r.phase_label == "hero-wander"]
    assert len(wander_entries) == 1
    assert wander_entries[0].leader_id == 2

    # Same setup, but the King submits no real order this turn -- the
    # orders-flag gate now genuinely blocks the wander outright.
    state2 = GameState()
    state2.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, home))
    state2.board_width = 5
    state2.board_height = 5
    state2.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state2.add_leader(LeaderState(1, kingdom_id=1, name="King", location=home, is_king=True))
    state2.add_leader(LeaderState(2, kingdom_id=None, name="Wanderer", location=home))
    p0_none = PlanPhase(label="P0", action=ActionCode.NO_ACTION, obj=0, extra=[0])
    king_leader_idle = Leader(1, "King", ActionPlan(1, [PlanSegment(0, 0, (), {"P0": p0_none})]))

    results2 = run_turn([TurnLeader(king_leader_idle, 1)], state2, board_width=5, rng=random.Random(3))

    assert [r for r in results2 if r.phase_label == "hero-wander"] == []
    assert state2.leaders[2].location == home


# -- Phase 869: [8.4] Scientific Treaty exchange + Silver Tongue merit,
# previously fully built (Phase 445/474/511/643/714/738) but never
# actually called from anywhere -- now wired into run_turn() right after
# both real financial steps. See turn/scientific_treaty.py's own module
# docstring for the full sourcing this fixture mirrors.


def _treaty_state() -> GameState:
    state = GameState()
    home_a = HexCoord(2, 2)
    home_b = HexCoord(3, 2)  # adjacent to home_a on the odd-r grid
    state.board_width = 10
    state.board_height = 10
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, home_a))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.GOOD, home_b))
    state.add_province(ProvinceState(home_a, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(home_b, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.treat_permissions.add((1, 2))
    state.treat_permissions.add((2, 1))
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)
    state.kingdoms[2].discoveries.add(Discovery.TELESCOPE)
    return state


def test_run_turn_exchanges_discoveries_via_mutual_treat_order():
    state = _treaty_state()
    leader_a = _empty_plan_leader(10, "A")
    leader_b = _empty_plan_leader(20, "B")

    run_turn([TurnLeader(leader_a, 1), TurnLeader(leader_b, 2)], state, board_width=10, rng=random.Random(0))

    assert Discovery.TELESCOPE in state.kingdoms[1].discoveries
    assert Discovery.COMPASS in state.kingdoms[2].discoveries
    assert state.discovery_exchanged_from[(1, 2)] == Discovery.COMPASS
    assert state.discovery_exchanged_from[(2, 1)] == Discovery.TELESCOPE


def test_run_turn_credits_silver_tongue_merit_to_both_kings():
    state = _treaty_state()
    state.add_leader(
        LeaderState(10, kingdom_id=1, name="King A", location=state.kingdoms[1].home_province, is_king=True)
    )
    state.add_leader(
        LeaderState(20, kingdom_id=2, name="King B", location=state.kingdoms[2].home_province, is_king=True)
    )
    king_a = _empty_plan_leader(10, "King A")
    king_b = _empty_plan_leader(20, "King B")

    run_turn([TurnLeader(king_a, 1), TurnLeader(king_b, 2)], state, board_width=10, rng=random.Random(0))

    # +1 allied, +2 adjacent, +5 for the one real Discovery received each way.
    assert state.leaders[10].merit_tally.diplomatic_merit_points == 8
    assert state.leaders[20].merit_tally.diplomatic_merit_points == 8


def test_a_hired_heros_embedded_plan_starts_from_the_next_phase_not_at_once():
    # [3.5]/[10]: "non potete dare ordini nella stessa fase in cui sono assoldati, ma a partire da
    # quella successiva" -- the hired hero's P1 order must run in phase P1, after everyone's P0
    # orders, not right after the Hire inside P0.
    state = _ordering_state({10: 0, 11: 0})
    state.kingdoms[1].treasury = 50
    state.add_leader(LeaderState(50, None, "Wandering Hero", ORIGIN))
    hire = PlanPhase(
        label="P0", action=ActionCode.HIRE, obj=50, extra=[4],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.WAIT, 0, [0])})],
        ),
    )
    hirer = Leader(10, "Hirer", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": hire})]))
    other = _leader_with_phase(11, "Other", "P0", _wait_phase("P0"))
    turn_leaders = [TurnLeader(hirer, 1), TurnLeader(other, 1)]

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(0))

    order = [(r.leader_id, r.phase_label) for r in results if r.leader_id in (10, 11, 50) and r.segment_index >= 0]
    assert order == [(10, "P0"), (11, "P0"), (50, "P1")]
    assert state.leaders[50].kingdom_id == 1
    assert len(turn_leaders) == 2  # the caller's list is left alone


# -- Initiative audit ([3] "Un personaggio può attendere se un altro deve fare qualcosa per lui") --


@pytest.mark.parametrize(
    "beneficiary_action",
    [ActionCode.LMOVE, ActionCode.PURSUE, ActionCode.TRAIL, ActionCode.SEARCH, ActionCode.CHALLENGE, ActionCode.PRACTICE],
)
def test_a_higher_initiative_beneficiary_waits_before_any_kind_of_order(beneficiary_action: ActionCode):
    # Whatever the favoured leader means to do (move, pursue, trail, enter a Special Place, meet another
    # hero...), he waits until the lower-Initiative colleague has done his favour.
    state = _ordering_state({20: 0, 21: 3})
    beneficiary_phase = PlanPhase(
        label="P1",
        action=beneficiary_action,
        obj=encode_hex_number(ORIGIN2, BOARD_WIDTH) if beneficiary_action is ActionCode.LMOVE else 99,
        extra=[0],
    )
    turn_leaders = _turn_leaders(
        (20, 1, "P1", _recruit_phase("P1", target_leader_id=21)),
        (21, 1, "P1", beneficiary_phase),
    )

    entries = _collect_phase_entries(turn_leaders, "P1", state, BOARD_WIDTH)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [20, 21]


def test_a_spell_wand_used_on_a_colleague_makes_him_wait_like_a_favourable_cast():
    state = _ordering_state({22: 0, 23: 3})
    wand = state.add_item(Treasure.WAND_ORATORY, owner_leader_id=22, charges=1)
    use_mi = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=wand.item_id, extra=[23])
    turn_leaders = _turn_leaders((22, 1, "P0", use_mi), (23, 1, "P0", _wait_phase("P0")))

    entries = _collect_phase_entries(turn_leaders, "P0", state, BOARD_WIDTH)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [22, 23]


def test_the_benefactor_waits_for_a_newcomer_who_is_moving_into_his_province():
    # [3]: "quando il personaggio A sta entrando in una provincia in cui il personaggio B ha in programma di
    # fare qualcosa per A, anche se B ha un'iniziativa più alta, aspetterà A."
    state = _ordering_state({70: 0, 71: 3})  # B (71) has the higher Initiative
    state.leaders[71].location = ORIGIN2  # B stands where A is going
    turn_leaders = _turn_leaders(
        (70, 1, "P1", _lmove_phase("P1", ORIGIN2)),
        (71, 1, "P1", _recruit_phase("P1", target_leader_id=70)),
    )

    entries = _collect_phase_entries(turn_leaders, "P1", state, BOARD_WIDTH)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [70, 71]


def test_the_benefactor_still_goes_first_when_the_beneficiary_moves_elsewhere():
    state = _ordering_state({70: 3, 71: 0})
    state.leaders[71].location = ORIGIN2
    turn_leaders = _turn_leaders(
        (70, 1, "P1", _lmove_phase("P1", TARGET)),  # not the benefactor's province
        (71, 1, "P1", _recruit_phase("P1", target_leader_id=70)),
    )

    entries = _collect_phase_entries(turn_leaders, "P1", state, BOARD_WIDTH)

    assert [tl.leader.leader_id for tl, _segment_index, _phase in entries] == [71, 70]


def test_run_turn_a_joint_practice_group_still_waits_for_the_favour_it_depends_on():
    # Two heroes practising the same ability together are dispatched as one group, which used to run
    # ahead of every ordinary order -- even ahead of the Give one of them was waiting for.
    state = _base_state()
    state.add_leader(LeaderState(13, 1, "Benefactor", ORIGIN, skills=_skills_with(Ability.MARCH, 1, 1)))
    state.add_leader(LeaderState(14, 1, "Beneficiary", ORIGIN, skills=_skills_with(Ability.MARCH, 3, 3)))
    state.add_leader(LeaderState(15, 1, "Partner", ORIGIN, skills=_skills_with(Ability.MARCH, 2, 2)))
    turn_leaders = [
        TurnLeader(Leader(13, "Benefactor", ActionPlan(13, [PlanSegment(0, 0, (), {"P1": _trade_phase("P1", 14)})])), 1),
        TurnLeader(Leader(14, "Beneficiary", ActionPlan(14, [PlanSegment(0, 0, (), {"P1": _practice_phase("P1", Ability.MELEE)})])), 1),
        TurnLeader(Leader(15, "Partner", ActionPlan(15, [PlanSegment(0, 0, (), {"P1": _practice_phase("P1", Ability.MELEE)})])), 1),
    ]

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(1))

    p1 = [r.leader_id for r in results if r.phase_label == "P1" and r.leader_id in (13, 14, 15)]
    assert p1.index(13) < p1.index(14)
    assert p1.index(13) < p1.index(15)  # the whole group runs after the Give


def test_order_phase_units_keeps_rank_order_unless_a_dependency_forces_otherwise():
    from ak_engine.turn.turn_processor import _order_phase_units

    log: list[str] = []
    units = [
        ((0, 0), [0, 1], lambda: log.append("group")),
        ((1, 0), [2], lambda: log.append("single")),
    ]

    for run in _order_phase_units(units, {}):
        run()
    assert log == ["group", "single"]

    log.clear()
    for run in _order_phase_units(units, {2: {1}}):  # the single must go before the group's member 1
        run()
    assert log == ["single", "group"]


def test_a_same_kingdom_trail_also_acts_right_after_its_target():
    # [3.16]: "Se il personaggio ne insegue o pedina un altro che appartiene al proprio Reame ed entrambi
    # partono dalla stessa provincia, l'inseguitore eseguirà l'azione dopo l'inseguito."
    from ak_engine.turn.turn_processor import _order_same_kingdom_pursuits_after_their_target

    trail = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=20, extra=[0])
    leaders = _turn_leaders((10, 1, "P0", trail), (20, 1, "P0", _lmove_phase("P0", TARGET)))
    entries = [(leaders[0], 0, trail), (leaders[1], 0, _lmove_phase("P0", TARGET))]

    order = _order_same_kingdom_pursuits_after_their_target(entries, [0, 1], {10: ORIGIN, 20: ORIGIN})

    assert order == [1, 0]  # the trailed leader moves first, the trailer follows
