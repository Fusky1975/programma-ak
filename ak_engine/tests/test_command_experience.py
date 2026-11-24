"""Experience for commanding in battle and for taking/leaving units
(rulebook [3.13] table; see turn/command_experience.py)."""

from __future__ import annotations

import random
from unittest.mock import patch

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import PlanPhase
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.command_experience import (
    COMMANDER_BASE_POINTS,
    PICK_UP_LEAVE_BASE_POINTS,
    SUPREME_COMMANDER_BASE_POINTS,
    award_battle_command_experience,
    award_pick_up_leave_experience,
)
from ak_engine.turn.experience import ExperienceOutcome
from ak_engine.turn.plan_dispatch import dispatch_phase

PLACE = HexCoord(3, 9)


def _state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(PLACE, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    for leader_id in (1, 2, 3):
        state.add_leader(LeaderState(leader_id, 1, f"Leader{leader_id}", PLACE))
    return state


def _no_rise(*_args, **_kwargs) -> ExperienceOutcome:
    return ExperienceOutcome(skill_rose=False, aptitude_rose=False, new_skill=0, new_aptitude=0, new_credit=0)


def _battle_calls(terrain: Terrain, supreme, leaders) -> list[tuple[int, Ability, int]]:
    state = _state()
    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        award_battle_command_experience(
            state, terrain, province_key="3,9", supreme_commander_ids=supreme, commanding_leader_ids=leaders
        )
    return sorted((call.args[0].leader_id, call.args[1], call.args[2]) for call in mocked.call_args_list)


def test_a_land_battle_credits_tactical_supreme_commander_at_fifteen_and_the_others_at_ten():
    assert _battle_calls(Terrain.PLAINS, (1, None), ([1, 2], [])) == [
        (1, Ability.TACTICAL, SUPREME_COMMANDER_BASE_POINTS),
        (2, Ability.TACTICAL, COMMANDER_BASE_POINTS),
    ]


def test_a_sea_battle_credits_naval_instead():
    assert _battle_calls(Terrain.SEA, (1, 3), ([1], [3])) == [
        (1, Ability.NAVAL, SUPREME_COMMANDER_BASE_POINTS),
        (3, Ability.NAVAL, SUPREME_COMMANDER_BASE_POINTS),
    ]


def test_a_battle_with_no_commanding_leader_credits_nobody():
    assert _battle_calls(Terrain.PLAINS, (None, None), ([], [])) == []


def test_a_leader_commanding_on_both_sides_of_a_merged_battle_is_credited_once():
    assert len(_battle_calls(Terrain.PLAINS, (1, None), ([1, 2], [2]))) == 2


def test_a_dead_commander_is_skipped_without_error():
    state = _state()
    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        award_battle_command_experience(
            state, Terrain.PLAINS, province_key="3,9", supreme_commander_ids=(99, None), commanding_leader_ids=([99, 1], [])
        )
    assert [call.args[0].leader_id for call in mocked.call_args_list] == [1]


def test_battle_experience_really_accumulates_on_the_leader_and_is_repeatable():
    first = _state()
    second = _state()
    for state in (first, second):
        award_battle_command_experience(
            state, Terrain.SEA, province_key="3,9", supreme_commander_ids=(1, None), commanding_leader_ids=([1], [])
        )

    assert first.leaders[1].experience_credit > 0
    # The award has its own stream, seeded by game/turn/leader/place: the same
    # battle always credits the same amount.
    assert first.leaders[1].experience_credit == second.leaders[1].experience_credit


def _army(state: GameState, army_id: int, army_type: ArmyType) -> int:
    state.add_army(ArmyState(army_id, 1, army_type, Quality.AVERAGE, PLACE, commanded_by=1))
    return army_id


def _pick_up_leave_calls(army_types: list[ArmyType]) -> list[tuple[Ability, int]]:
    state = _state()
    ids = [_army(state, 100 + index, army_type) for index, army_type in enumerate(army_types)]
    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        award_pick_up_leave_experience(state, 1, ids)
    return sorted(((call.args[1], call.args[2]) for call in mocked.call_args_list), key=lambda c: c[0].value)


def test_taking_or_leaving_land_units_credits_march_at_five():
    assert _pick_up_leave_calls([ArmyType.LEGION, ArmyType.BOWMEN]) == [(Ability.MARCH, PICK_UP_LEAVE_BASE_POINTS)]


def test_taking_or_leaving_a_fleet_credits_naval_at_five():
    assert _pick_up_leave_calls([ArmyType.FLEET]) == [(Ability.NAVAL, PICK_UP_LEAVE_BASE_POINTS)]


def test_a_mixed_stack_credits_both_once():
    assert _pick_up_leave_calls([ArmyType.FLEET, ArmyType.LEGION, ArmyType.LEGION]) == [
        (Ability.MARCH, PICK_UP_LEAVE_BASE_POINTS),
        (Ability.NAVAL, PICK_UP_LEAVE_BASE_POINTS),
    ]


def test_flying_units_and_empty_lists_credit_nothing():
    assert _pick_up_leave_calls([ArmyType.DRAGON_WING]) == []
    assert _pick_up_leave_calls([]) == []


def test_a_leave_order_credits_the_acting_leader_for_the_armies_that_actually_left():
    state = _state()
    fleet = _army(state, 100, ArmyType.FLEET)
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, fleet, -1])

    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=1, board_width=10)

    assert [(call.args[0].leader_id, call.args[1]) for call in mocked.call_args_list] == [(1, Ability.NAVAL)]


def test_a_pick_up_order_that_finds_nothing_credits_nothing():
    state = _state()
    phase = PlanPhase(label="P3", action=ActionCode.PICK_UP, obj=0, extra=[255, 255, -1])

    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=1, board_width=10)

    assert mocked.call_count == 0


def test_a_rise_grants_the_naval_advanced_ability_of_the_new_level():
    from ak_engine.worldgen.naval_ability_level_schedule import build_naval_ability_level_schedule

    state = _state()
    schedule = build_naval_ability_level_schedule(state.game_number)
    level, expected = next(iter(schedule.items()))
    rise = ExperienceOutcome(skill_rose=True, aptitude_rose=False, new_skill=level, new_aptitude=level, new_credit=0)

    with patch("ak_engine.turn.command_experience.add_experience", return_value=rise):
        award_battle_command_experience(
            state, Terrain.SEA, province_key="3,9", supreme_commander_ids=(1, None), commanding_leader_ids=([1], [])
        )

    assert expected in state.leaders[1].advanced_abilities


def test_an_explore_order_that_explores_something_credits_explorer_at_ten():
    from ak_engine.turn.command_experience import EXPLORE_BASE_POINTS

    state = _state()
    state.provinces[PLACE].explored_percent = 20
    phase = PlanPhase(label="P1", action=ActionCode.EXPLORE, obj=0, extra=[0])

    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=1, board_width=10)

    assert [(call.args[0].leader_id, call.args[1], call.args[2]) for call in mocked.call_args_list] == [
        (1, Ability.EXPLORER, EXPLORE_BASE_POINTS)
    ]


def test_exploring_a_province_the_kingdom_has_fully_explored_credits_nothing():
    state = _state()
    state.provinces[PLACE].explored_percent = 100
    state.provinces[PLACE].explored_percent_by_kingdom[1] = 100  # this Kingdom's own exploration is complete
    phase = PlanPhase(label="P1", action=ActionCode.EXPLORE, obj=0, extra=[0])

    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=1, board_width=10)

    assert mocked.call_count == 0


def test_exploring_a_province_only_another_kingdom_has_explored_still_credits_experience():
    # What counts is the exploring Kingdom's own cumulative exploration, not the shared scalar.
    state = _state()
    state.provinces[PLACE].explored_percent = 100  # explored by someone else
    phase = PlanPhase(label="P1", action=ActionCode.EXPLORE, obj=0, extra=[0])

    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=1, board_width=10)

    assert mocked.call_count == 1


def test_an_explorer_rise_grants_the_explorer_advanced_ability_of_the_new_level():
    from ak_engine.turn.command_experience import award_explore_experience
    from ak_engine.worldgen.explorer_ability_level_schedule import build_explorer_ability_level_schedule

    state = _state()
    level, expected = next(iter(build_explorer_ability_level_schedule(state.game_number).items()))
    rise = ExperienceOutcome(skill_rose=True, aptitude_rose=False, new_skill=level, new_aptitude=level, new_credit=0)

    with patch("ak_engine.turn.command_experience.add_experience", return_value=rise):
        award_explore_experience(state, 1)

    assert expected in state.leaders[1].advanced_abilities


def test_practicing_sageness_also_credits_sage_experience_at_ten():
    from ak_engine.turn.command_experience import SAGE_PRACTICE_BASE_POINTS

    state = _state()
    phase = PlanPhase(label="P2", action=ActionCode.PRACTICE, obj=Ability.SAGE.value, extra=[0])

    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=1, board_width=10, rng=random.Random(1))

    assert [(call.args[0].leader_id, call.args[1], call.args[2]) for call in mocked.call_args_list] == [
        (1, Ability.SAGE, SAGE_PRACTICE_BASE_POINTS)
    ]


def test_practicing_another_ability_credits_no_sage_experience():
    state = _state()
    phase = PlanPhase(label="P2", action=ActionCode.PRACTICE, obj=Ability.MELEE.value, extra=[0])

    with patch("ak_engine.turn.command_experience.add_experience", side_effect=_no_rise) as mocked:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=1, board_width=10, rng=random.Random(1))

    assert mocked.call_count == 0


def test_the_same_award_twice_in_a_turn_does_not_repeat_the_same_draws():
    # The leader's running credit is part of the stream's seed.
    state = _state()
    gains = []
    for phase in ("P1", "P2", "P3", "P4"):
        before = state.leaders[1].experience_credit
        from ak_engine.turn.command_experience import award_sage_practice_experience

        award_sage_practice_experience(state, 1, phase)
        gains.append(state.leaders[1].experience_credit - before)

    assert len(set(gains)) > 1
