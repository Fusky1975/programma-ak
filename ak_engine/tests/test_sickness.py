"""Hidden Tattoos sickness: a Kill Enemy that succeeds against a protected character
makes them sick; until the end of the turn their orders become Practice."""

from __future__ import annotations

import random
from unittest.mock import patch

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.report.turn_report import describe_cast
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import execute_cast
from ak_engine.turn.combat import Quality
from ak_engine.turn.sickness import apply_sickness, make_sick
from ak_engine.turn.turn_processor import TurnLeader, run_turn

HOME = HexCoord(3, 3)
SEA = HexCoord(4, 3)
BW = 10


def _skills(**levels: int) -> SkillTable:
    raw = [0] * 31
    for name, level in levels.items():
        raw[Ability[name.upper()].value * 2] = level
        raw[Ability[name.upper()].value * 2 + 1] = 9
    return SkillTable(raw)


def _state(*, protected: bool = True) -> GameState:
    state = GameState()
    state.board_width = BW
    state.board_height = 10
    state.add_kingdom(KingdomState(1, "Dark", Race.HUMAN, Alignment.EVIL, HOME))
    state.add_kingdom(KingdomState(2, "Tattooed", Race.HUMAN, Alignment.GOOD, HexCoord(8, 8)))
    if protected:
        state.kingdoms[2].discoveries.add(Discovery.HIDDEN_TATTOOS)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Home"))
    state.add_province(ProvinceState(SEA, Terrain.SEA, Race.HUMAN, owner_kingdom_id=2, name="Sea"))
    state.add_leader(LeaderState(1, 1, "Necromancer", HOME, is_king=True, skills=_skills(necromancy=5)))
    state.add_leader(LeaderState(44, 2, "Victim", HOME, skills=_skills(melee=3, sage=3, druid=1)))
    return state


def _phase(label: str, action: ActionCode, obj: int = 0, extra=()) -> PlanPhase:
    return PlanPhase(label=label, action=action, obj=obj, extra=list(extra))


# -- the substitution --


def test_a_healthy_character_keeps_every_order():
    state = _state()
    phase = _phase("P1", ActionCode.EXPLORE)

    assert apply_sickness(state, 44, phase) is phase


def test_a_sick_character_keeps_a_practice_order():
    state = _state()
    make_sick(state, 44)
    phase = _phase("P1", ActionCode.PRACTICE, Ability.MELEE.value)

    assert apply_sickness(state, 44, phase) is phase


def test_a_sick_character_without_armies_practices_the_highest_talent():
    state = _state()
    state.leaders[44].skills = _skills(melee=3, sage=5, druid=1)
    make_sick(state, 44)

    replaced = apply_sickness(state, 44, _phase("P2", ActionCode.EXPLORE))

    assert replaced.action is ActionCode.PRACTICE
    assert replaced.obj == Ability.SAGE.value
    assert replaced.label == "P2"


def test_a_tie_for_the_highest_talent_is_settled_at_random_but_always_the_same_way():
    state = _state()
    state.leaders[44].skills = _skills(melee=4, sage=4, druid=1)
    make_sick(state, 44)

    picked = {apply_sickness(state, 44, _phase(f"P{i}", ActionCode.EXPLORE)).obj for i in range(5)}

    assert picked <= {Ability.MELEE.value, Ability.SAGE.value}
    assert apply_sickness(state, 44, _phase("P0", ActionCode.EXPLORE)) == apply_sickness(
        state, 44, _phase("P0", ActionCode.EXPLORE)
    )


def test_a_sick_character_leading_armies_on_land_practices_tactics():
    state = _state()
    state.add_army(ArmyState(101, 2, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=44))
    make_sick(state, 44)

    replaced = apply_sickness(state, 44, _phase("P1", ActionCode.LMOVE, 0, [0]))

    assert replaced.action is ActionCode.PRACTICE
    assert replaced.obj == Ability.TACTICAL.value


def test_a_sick_character_leading_armies_at_sea_practices_navigation():
    state = _state()
    state.leaders[44].location = SEA
    state.add_army(ArmyState(101, 2, ArmyType.FLEET, Quality.AVERAGE, SEA, commanded_by=44))
    make_sick(state, 44)

    replaced = apply_sickness(state, 44, _phase("P1", ActionCode.EXPLORE))

    assert replaced.obj == Ability.NAVAL.value


# -- what makes a character sick --


def test_kill_enemy_against_hidden_tattoos_makes_the_target_sick_not_dead_nor_comatose():
    state = _state()
    request = CastRequest(Spell.KILL_ENEMY, target=44)
    with patch("ak_engine.turn.cast_execution._roll_cast_success", return_value=(True, None)):
        result = execute_cast(state, 1, 1, request, random.Random(1), board_width=BW)

    assert result.applied is True
    assert result.discovery_defended is Discovery.HIDDEN_TATTOOS
    assert state.leaders[44].sick_this_turn is True
    assert state.leaders[44].is_comatose is False


def test_kill_enemy_without_the_discovery_does_not_make_anyone_sick():
    state = _state(protected=False)
    with patch("ak_engine.turn.cast_execution._roll_cast_success", return_value=(True, None)):
        execute_cast(state, 1, 1, CastRequest(Spell.KILL_ENEMY, target=44), random.Random(1), board_width=BW)

    assert state.leaders[44].sick_this_turn is False


def test_a_failed_kill_enemy_does_not_make_the_target_sick():
    state = _state()
    with patch("ak_engine.turn.cast_execution._roll_cast_success", return_value=(False, "spell failed")), patch(
        "ak_engine.turn.cast_execution.resolve_melee_duel"
    ) as duel:
        duel.return_value.winner = None
        duel.return_value.melee_swings = []
        execute_cast(state, 1, 1, CastRequest(Spell.KILL_ENEMY, target=44), random.Random(1), board_width=BW)

    assert state.leaders[44].sick_this_turn is False


def test_the_cast_is_told_in_the_casters_report():
    state = _state()
    request = CastRequest(Spell.KILL_ENEMY, target=44)
    with patch("ak_engine.turn.cast_execution._roll_cast_success", return_value=(True, None)):
        result = execute_cast(state, 1, 1, request, random.Random(1), board_width=BW)

    line = describe_cast(result, caster_name="Necromancer", rng=random.Random(1), target_name="Victim")

    assert "Hidden Tattoos" in line
    assert "killed" not in line


# -- a whole turn --


def _turn(*, caster_first: bool) -> tuple[GameState, list]:
    state = _state()
    # The one who acts first in a phase is the one with the higher initiative (total skill).
    state.leaders[1 if caster_first else 44].skills = _skills(necromancy=5, melee=9, sage=9, druid=9)
    caster_plan = {"P1": _phase("P1", ActionCode.CAST, Spell.KILL_ENEMY.value, [44])}
    target_plan = {
        "P0": _phase("P0", ActionCode.EXPLORE),
        "P1": _phase("P1", ActionCode.EXPLORE),
        "P2": _phase("P2", ActionCode.EXPLORE),
        "P3": _phase("P3", ActionCode.PRACTICE, Ability.DRUID.value),
        "P4": _phase("P4", ActionCode.EXPLORE),
    }
    leaders = [
        TurnLeader(Leader(1, "Necromancer", ActionPlan(1, [PlanSegment(0, 0, (), caster_plan)])), 1),
        TurnLeader(Leader(44, "Victim", ActionPlan(44, [PlanSegment(0, 0, (), target_plan)])), 2),
    ]
    with patch("ak_engine.turn.cast_execution._roll_cast_success", return_value=(True, None)):
        results = run_turn(leaders, state, board_width=BW, rng=random.Random(2))
    return state, results


def _actions_of(results: list, leader_id: int) -> dict[str, ActionCode]:
    return {
        entry.phase_label: entry.action
        for entry in results
        if entry.leader_id == leader_id and entry.segment_index >= 0 and entry.action is not None
    }


def test_a_character_who_has_not_yet_acted_that_phase_is_changed_from_that_phase():
    state, results = _turn(caster_first=True)

    actions = _actions_of(results, 44)

    assert actions["P0"] is ActionCode.EXPLORE  # before the spell
    assert actions["P1"] is ActionCode.PRACTICE  # the caster acted first in phase 1
    assert actions["P2"] is ActionCode.PRACTICE
    assert actions["P3"] is ActionCode.PRACTICE
    assert actions["P4"] is ActionCode.PRACTICE


def test_a_character_who_already_acted_that_phase_is_changed_from_the_next_one():
    state, results = _turn(caster_first=False)

    actions = _actions_of(results, 44)

    assert actions["P0"] is ActionCode.EXPLORE
    assert actions["P1"] is ActionCode.EXPLORE  # he had already acted in phase 1
    assert actions["P2"] is ActionCode.PRACTICE
    assert actions["P4"] is ActionCode.PRACTICE


def test_the_sickness_is_gone_when_the_turn_ends():
    state, _results = _turn(caster_first=True)

    assert state.leaders[44].sick_this_turn is False
