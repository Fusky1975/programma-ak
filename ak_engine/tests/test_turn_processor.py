from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.move_execution import MoveExecutionResult
from ak_engine.turn.turn_processor import MultiAttackerMoveResult, TurnLeader, run_turn

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
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN))
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


def test_run_turn_excludes_an_illegal_contested_mover_but_still_groups_the_rest():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN2))
    state.add_leader(LeaderState(30, kingdom_id=1, name="C", location=ORIGIN2))
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
