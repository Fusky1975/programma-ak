from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.army_list_decode import ArmyListRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.move_execution import MoveExecutionResult
from ak_engine.turn.plan_dispatch import UnsupportedActionError, dispatch_phase, run_leader_plan
from ak_engine.turn.recruit_execution import RecruitExecutionResult

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
BOARD_WIDTH = 10
LEADER_ID = 1


def _state_with_army(
    location: HexCoord, target_terrains: dict[HexCoord, Terrain], *, treasury: int = 100
) -> tuple[GameState, int]:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, location, treasury=treasury))
    state.add_province(ProvinceState(location, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    for coord, terrain in target_terrains.items():
        state.add_province(ProvinceState(coord, terrain, Race.HUMAN))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", location))
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


def test_dispatch_explore_uses_leader_location():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=1
    )

    assert result.new_percent == 100  # Plains(50) * (skill 1 + 1) = 100
    assert state.provinces[location].explored_percent == 100


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
    phase = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=6, extra=[0])

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

    assert isinstance(result, ArmyListRequest)
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


def test_dispatch_disband_releases_army_into_mercenary_status():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ArmyListRequest)
    assert result.army_ids == [army_id]
    assert army_id in state.armies  # not removed -- still exists as an unowned mercenary
    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_disband_all_releases_every_commanded_army():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


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

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

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

    assert isinstance(result, ArmyListRequest)
    assert result.target_leader_id == 1
    assert result.army_ids == [108, 109, 110]
    assert all(state.armies[aid].commanded_by == 1 for aid in (108, 109, 110))
