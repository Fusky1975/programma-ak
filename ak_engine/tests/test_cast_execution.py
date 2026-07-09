from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import execute_cast

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
ELSEWHERE = HexCoord(9, 9)
CASTER_ID = 1


def _skills_with(ability: Ability, level: int) -> SkillTable:
    raw_values = [0] * 30
    raw_values[ability.value * 2] = level
    return SkillTable(raw_values=raw_values)


def build_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, LOCATION))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, ELSEWHERE))
    state.add_leader(LeaderState(CASTER_ID, 1, "Caster", LOCATION))
    return state


def test_charm_assigns_a_colocated_independent_hero_to_the_casters_kingdom():
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.reason is None
    assert state.leaders[78].kingdom_id == 1


def test_charm_steals_a_colocated_enemy_characters_allegiance():
    # Charm doesn't require the target to already be independent -- see
    # cast_execution.py's docstring for why this differs from Hire.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_fails_when_target_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.CHARM, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_kill_enemy_removes_a_colocated_target():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert 78 not in state.leaders


def test_kill_enemy_fails_when_target_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert 78 in state.leaders  # untouched


def test_kill_enemy_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.KILL_ENEMY, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_charm_succeeds_on_a_real_roll_under_the_casters_chance():
    # Rulebook [3.10]: 15% + 15%/level. Psychic level 2 -> 45% chance.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_fails_on_a_real_roll_over_the_casters_chance():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.99])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_fails_outright_when_caster_has_no_skill_in_the_ability():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 0)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # no roll consumed -- precondition fails first

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "insufficient skill"


def test_kill_enemy_success_roll_uses_necromancy_skill():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.29])  # 15% + 15%*1 = 30% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 78 not in state.leaders


def test_cast_always_succeeds_when_caster_has_no_skills_recorded():
    # LeaderState.skills is None by default -- see cast_execution.py's
    # module docstring for why this preserves pre-Phase-30 behavior.
    state = build_state()
    assert state.leaders[CASTER_ID].skills is None
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # no roll consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_unmodeled_spells_report_a_reason_without_touching_state():
    # Resurrection can't be executed even conceptually -- see the module
    # docstring (no "dead leader" registry to revive from). Representative
    # of every other real spell this project doesn't execute.
    state = build_state()
    request = CastRequest(spell=Spell.RESURRECTION, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "spell effect not modeled"
