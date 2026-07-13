from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.missed_deadline import build_missed_deadline_plan
from ak_engine.turn.plan_dispatch import NoOpResult, run_leader_plan

HOME = HexCoord(3, 9)
LEADER_ID = 1
BOARD_WIDTH = 10


def _build_state(*, with_army: bool) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME, treasury=100))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", HOME, is_king=True))
    if with_army:
        state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=LEADER_ID))
    return state


def test_build_missed_deadline_plan_defends_when_leader_commands_an_army():
    state = _build_state(with_army=True)

    plan = build_missed_deadline_plan(state, LEADER_ID)

    assert plan.leader_id == LEADER_ID
    segment = plan.segments[0]
    assert segment.plan_start == 0
    assert segment.plan_end == 4
    assert segment.phases["P0"].action is ActionCode.DEFEND
    for label in ("P1", "P2", "P3", "P4"):
        assert segment.phases[label].action is ActionCode.WAIT


def test_build_missed_deadline_plan_waits_every_phase_when_armyless():
    state = _build_state(with_army=False)

    plan = build_missed_deadline_plan(state, LEADER_ID)

    segment = plan.segments[0]
    for label in ("P0", "P1", "P2", "P3", "P4"):
        assert segment.phases[label].action is ActionCode.WAIT


def test_missed_deadline_plan_dispatches_cleanly_via_run_leader_plan():
    state = _build_state(with_army=True)
    plan = build_missed_deadline_plan(state, LEADER_ID)
    leader = Leader(leader_id=LEADER_ID, name="Test Leader", plan=plan)

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert len(results) == 5
    assert all(r.error is None for r in results)
    assert results[0].action is ActionCode.DEFEND
    assert all(r.action is ActionCode.WAIT for r in results[1:])
    assert all(isinstance(r.result, NoOpResult) for r in results[1:])
