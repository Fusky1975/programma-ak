from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, ProvinceState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.combat import Quality
from ak_engine.turn.move_execution import MoveExecutionResult
from ak_engine.turn.plan_dispatch import UnsupportedActionError, dispatch_phase, run_leader_plan

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
BOARD_WIDTH = 10


def _state_with_army(location: HexCoord, target_terrains: dict[HexCoord, Terrain]) -> tuple[GameState, int]:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, location))
    state.add_province(ProvinceState(location, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    for coord, terrain in target_terrains.items():
        state.add_province(ProvinceState(coord, terrain, Race.HUMAN))
    army_id = 1
    state.add_army(ArmyState(army_id, 1, ArmyType.BOWMEN, Quality.AVERAGE, location, movement_points=5))
    return state, army_id


def test_dispatch_lmove_decodes_hex_number_and_moves():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)  # hex number 94, adjacent to origin on the odd-r grid
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert isinstance(result, MoveExecutionResult)
    assert result.moved is True
    assert state.armies[army_id].location == target


def test_dispatch_explore_uses_current_province():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=1)

    assert result.new_percent == 100  # Plains(50) * (skill 1 + 1) = 100
    assert state.provinces[location].explored_percent == 100


def test_dispatch_unsupported_action_raises():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=6, extra=[0])

    try:
        dispatch_phase(phase, state, kingdom_id=1, army_ids=[army_id], board_width=BOARD_WIDTH)
        assert False, "expected UnsupportedActionError"
    except UnsupportedActionError:
        pass


def test_run_leader_plan_records_errors_and_continues():
    origin = HexCoord(3, 9)
    mid = HexCoord(4, 9)
    end = HexCoord(4, 10)
    state, army_id = _state_with_army(origin, {mid: Terrain.PLAINS, end: Terrain.PLAINS})

    leader = Leader(
        leader_id=1,
        name="Test Leader",
        plan=ActionPlan(
            leader_id=1,
            segments=[
                PlanSegment(
                    plan_start=0,
                    plan_end=4,
                    sp=(),
                    phases={
                        "P0": PlanPhase("P0", ActionCode.PRACTICE, 6, [0]),
                        "P1": PlanPhase("P1", ActionCode.PRACTICE, 6, [0]),
                        "P2": PlanPhase("P2", ActionCode.PRACTICE, 6, [0]),
                        "P3": PlanPhase("P3", ActionCode.LMOVE, 94, [0]),
                        "P4": PlanPhase("P4", ActionCode.LMOVE, 104, [0]),
                    },
                )
            ],
        ),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert [r.phase_label for r in results] == ["P0", "P1", "P2", "P3", "P4"]
    assert all(isinstance(r.error, UnsupportedActionError) for r in results[:3])
    assert results[3].error is None
    assert results[4].error is None
    assert state.armies[army_id].location == end


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
