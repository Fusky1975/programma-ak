"""A spy watching a province learns what happens there in that phase ([3.14], [4.3.3])."""

from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.report.turn_report import describe_aspy, describe_general_intelligence_report
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.aspy_execution import execute_aspy
from ak_engine.turn.combat import Quality
from ak_engine.turn.spy_watch import note_spy_watch
from ak_engine.turn.turn_processor import TurnLeader, run_turn
from ak_engine.models.army_type import ArmyType

from _helpers import ScriptedRandom

TARGET = HexCoord(5, 4)  # owned by kingdom 1
FAR = HexCoord(25, 12)  # kingdom 4's own province, nowhere near TARGET
OTHER = HexCoord(6, 4)


def _skills(spy: int) -> SkillTable:
    raw = [0] * 31
    raw[Ability.SPY.value * 2] = spy
    raw[Ability.SPY.value * 2 + 1] = 9
    return SkillTable(raw)


def _state(spy_level: int = 2) -> GameState:
    state = GameState()
    state.board_width = 30
    state.board_height = 15
    state.add_kingdom(KingdomState(1, "Owneria", Race.HUMAN, Alignment.GOOD, TARGET))
    state.add_kingdom(KingdomState(4, "Spyland", Race.HUMAN, Alignment.GOOD, FAR))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Hotspot"))
    state.add_province(ProvinceState(OTHER, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Quiet"))
    state.add_province(ProvinceState(FAR, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=4))
    state.add_leader(LeaderState(40, 4, "Agent", TARGET, skills=_skills(spy_level)))
    return state


def _phase(label: str, action: ActionCode, obj: int = 0) -> PlanPhase:
    return PlanPhase(label=label, action=action, obj=obj, extra=[])


def _gir(state: GameState, kingdom_id: int) -> list[str]:
    return describe_general_intelligence_report(state, kingdom_id)


# -- the watch is recorded --


def test_a_spy_order_watches_the_province_in_that_phase():
    state = _state(spy_level=0)
    report = execute_aspy(state, 40, SpyProvinceRequest(0, 0), rng=random.Random(1))

    note_spy_watch(state, 40, _phase("P2", ActionCode.ASPY), report)

    assert state.spy_watches == [(4, TARGET, "P2")]


def test_an_explore_with_spy_skill_watches_but_without_it_does_not():
    state = _state(spy_level=1)
    note_spy_watch(state, 40, _phase("P1", ActionCode.EXPLORE), object())
    assert state.spy_watches == [(4, TARGET, "P1")]

    state = _state(spy_level=0)
    note_spy_watch(state, 40, _phase("P1", ActionCode.EXPLORE), object())
    assert state.spy_watches == []


def test_a_move_with_spy_skill_watches_the_province_it_arrives_in():
    class _Moved:
        moved = True
        new_location = OTHER

    state = _state(spy_level=1)
    note_spy_watch(state, 40, _phase("P3", ActionCode.LMOVE), _Moved())

    assert state.spy_watches == [(4, OTHER, "P3")]


def test_a_move_that_goes_nowhere_watches_nothing():
    class _Stayed:
        moved = False
        new_location = None

    state = _state(spy_level=3)
    note_spy_watch(state, 40, _phase("P3", ActionCode.LMOVE), _Stayed())

    assert state.spy_watches == []


def test_a_trail_that_caught_its_target_watches_where_the_target_is():
    class _Caught:
        spied_on = True

    state = _state(spy_level=0)
    state.add_leader(LeaderState(7, 1, "Quarry", OTHER))
    note_spy_watch(state, 40, _phase("P0", ActionCode.TRAIL, obj=7), _Caught())
    assert state.spy_watches == [(4, OTHER, "P0")]

    class _Missed:
        spied_on = False

    state = _state(spy_level=0)
    state.add_leader(LeaderState(7, 1, "Quarry", OTHER))
    note_spy_watch(state, 40, _phase("P0", ActionCode.TRAIL, obj=7), _Missed())
    assert state.spy_watches == []


def test_running_a_turn_records_the_watch():
    state = _state()
    plan = ActionPlan(40, [PlanSegment(0, 0, (), {"P1": _phase("P1", ActionCode.ASPY)})])

    run_turn([TurnLeader(Leader(40, "Agent", plan), 4)], state, rng=random.Random(1))

    assert (4, TARGET, "P1") in state.spy_watches


# -- the GENERAL INTELLIGENCE REPORT --


def test_a_far_kingdom_sees_nothing_without_a_watch():
    state = _state()
    state.record_world_event(TARGET, ["Hotspot was overrun."], phase="P1")

    assert _gir(state, 4) == ["GENERAL INTELLIGENCE REPORT", "None at present"]


def test_the_watching_kingdom_sees_what_happened_there_in_the_watched_phase():
    state = _state()
    state.record_world_event(TARGET, ["Hotspot was overrun."], phase="P1")
    state.spy_watches.append((4, TARGET, "P1"))

    assert _gir(state, 4) == ["GENERAL INTELLIGENCE REPORT", "Kingdom of Owneria (#1):", "Hotspot was overrun."]


def test_events_in_other_phases_or_provinces_stay_hidden():
    state = _state()
    state.record_world_event(TARGET, ["Early skirmish."], phase="P0")
    state.record_world_event(OTHER, ["Elsewhere."], phase="P1")
    state.spy_watches.append((4, TARGET, "P1"))

    assert _gir(state, 4) == ["GENERAL INTELLIGENCE REPORT", "None at present"]


def test_an_event_with_no_phase_is_never_seen_through_a_watch():
    state = _state()
    state.record_world_event(TARGET, ["Plague spread."])  # end-of-turn event: no phase
    state.spy_watches.append((4, TARGET, "P1"))

    assert _gir(state, 4) == ["GENERAL INTELLIGENCE REPORT", "None at present"]


def test_another_kingdoms_watch_does_not_help():
    state = _state()
    state.add_kingdom(KingdomState(5, "Elsewhere", Race.HUMAN, Alignment.GOOD, HexCoord(28, 1)))
    state.record_world_event(TARGET, ["Hotspot was overrun."], phase="P1")
    state.spy_watches.append((4, TARGET, "P1"))

    assert _gir(state, 5) == ["GENERAL INTELLIGENCE REPORT", "None at present"]


def test_watches_are_cleared_with_the_turns_other_report_scratch():
    state = _state()
    state.spy_watches.append((4, TARGET, "P1"))
    state.spy_force_reports.add((40, TARGET))

    state.reset_turn_report_scratch()

    assert state.spy_watches == [] and state.spy_force_reports == set()


# -- the military/characters report is made once per turn --


def _state_with_company() -> GameState:
    state = _state()
    state.add_leader(LeaderState(7, 1, "Resident", TARGET))
    state.add_army(ArmyState(1, 1, ArmyType.GARRISON, Quality.AVERAGE, TARGET))
    return state


def test_the_first_spy_order_in_a_province_reports_forces_and_characters():
    state = _state_with_company()

    report = execute_aspy(state, 40, SpyProvinceRequest(0, 0), rng=random.Random(1))

    assert report.forces_reported is True
    assert [c.name for c in report.spotted_characters] == ["Resident"]
    assert report.garrison_estimate


def test_a_second_spy_order_by_the_same_spy_in_the_same_province_leaves_that_part_out():
    state = _state_with_company()
    execute_aspy(state, 40, SpyProvinceRequest(0, 0), rng=random.Random(1))

    again = execute_aspy(state, 40, SpyProvinceRequest(0, 0), rng=random.Random(2))

    assert again.forces_reported is False
    assert again.spotted_characters == [] and again.garrison_estimate == ()
    assert again.owner_kingdom_id == 1  # the rest of the report is still made
    lines = describe_aspy(
        again, spy_name="Agent", province_name="Hotspot", owner_name="Owneria", adjacent_owner_names=[],
        rng=ScriptedRandom([0.1] * 30, choice_indices=[0]),
    )
    assert not any("conspicuous" in line or "elements are present" in line or "is here" in line for line in lines)
    assert any("any further news is in the General Intelligence Report" in line for line in lines)


def test_another_spy_or_another_province_gets_its_own_forces_report():
    state = _state_with_company()
    state.add_leader(LeaderState(41, 4, "Second Agent", TARGET))
    execute_aspy(state, 40, SpyProvinceRequest(0, 0), rng=random.Random(1))

    other_spy = execute_aspy(state, 41, SpyProvinceRequest(0, 0), rng=random.Random(1))
    assert other_spy.forces_reported is True

    state.leaders[40].location = OTHER
    elsewhere = execute_aspy(state, 40, SpyProvinceRequest(0, 0), rng=random.Random(1))
    assert elsewhere.forces_reported is True


def test_the_double_agents_end_of_turn_report_is_not_a_repeat():
    state = _state_with_company()
    execute_aspy(state, 40, SpyProvinceRequest(0, 0), rng=random.Random(1))

    end_of_turn = execute_aspy(state, 40, SpyProvinceRequest(0, 0), once_per_turn=False, rng=random.Random(1))

    assert end_of_turn.forces_reported is True
