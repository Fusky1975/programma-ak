"""Tests for turn/assassin_guild.py -- see its module docstring for the
full AKGEN_reverse_engineering_report (2).md SS20.9 derivation.
"""

from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.assassin_guild import (
    grandfather_of_assassins_base_success_chance,
    resolve_grandfather_of_assassins_attempt,
)
from ak_engine.turn.combat import Quality

from _helpers import ScriptedRandom

HOME = HexCoord(0, 0)
TARGET_LOCATION = HexCoord(5, 5)


def _skills_with(ability: Ability, skill: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    return SkillTable(raw)


def build_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Assassinia", Race.HUMAN, Alignment.EVIL, HOME))
    state.add_kingdom(KingdomState(2, "Targetia", Race.HUMAN, Alignment.GOOD, TARGET_LOCATION))
    titleholder = LeaderState(1, 1, "Grandfather", HOME)
    titleholder.merit_tally.successful_assassinations = 2  # meets OFFICE_MIN_POINTS[Office.ASSASSIN]
    state.add_leader(titleholder)
    state.add_leader(LeaderState(2, 2, "Victim", TARGET_LOCATION))
    return state


def test_grandfather_of_assassins_base_success_chance_matches_the_formula():
    assert grandfather_of_assassins_base_success_chance(0, 0) == 0.50
    assert grandfather_of_assassins_base_success_chance(2, 1) == pytest.approx(0.30)  # 0.50 - 0.10 - 0.10


def test_grandfather_of_assassins_base_success_chance_floors_at_zero():
    assert grandfather_of_assassins_base_success_chance(10, 10) == 0.0


def test_resolve_attempt_none_without_a_titleholder():
    state = build_state()
    state.leaders[1].merit_tally.successful_assassinations = 0  # no longer qualifies

    assert resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([])) is None


def test_resolve_attempt_none_for_a_missing_target():
    state = build_state()

    assert resolve_grandfather_of_assassins_attempt(state, target_leader_id=999, rng=ScriptedRandom([])) is None


def test_resolve_attempt_none_for_a_king_target():
    state = build_state()
    state.leaders[2].is_king = True

    assert resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([])) is None


def test_resolve_attempt_success_removes_the_target():
    state = build_state()
    # A=0, M=0 -> chance 0.50; 0.49 succeeds.
    result = resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([0.49]))

    assert result is not None
    assert result.succeeded is True
    assert result.success_chance == 0.50
    assert 2 not in state.leaders
    assert 2 in state.dead_leaders


def test_resolve_attempt_failure_increments_the_guard():
    state = build_state()
    # 0.50 fails (not < 0.50).
    result = resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([0.50]))

    assert result is not None
    assert result.succeeded is False
    assert 2 in state.leaders
    assert state.leaders[2].assassination_guild_failed_attempts == 1


def test_resolve_attempt_guard_escalation_halves_the_chance():
    state = build_state()
    state.leaders[2].assassination_guild_failed_attempts = 1  # one prior failure

    result = resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([0.0]))

    assert result is not None
    assert result.success_chance == 0.25  # 0.50 * 0.5**1


def test_resolve_attempt_accounts_for_armies_and_melee_skill():
    state = build_state()
    state.leaders[2].skills = _skills_with(Ability.MELEE, 3)
    state.add_army(ArmyState(100, None, ArmyType.BOWMEN, Quality.AVERAGE, TARGET_LOCATION))

    result = resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([0.0]))

    # A=1 army present, M=3 Melee -> 0.50 - 0.05 - 0.30 = 0.15
    assert result is not None
    assert result.success_chance == pytest.approx(0.15)


def test_resolve_attempt_never_touches_merit_tally_on_success():
    state = build_state()
    titleholder_tally_before = state.leaders[1].merit_tally.successful_assassinations

    resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([0.0]))

    assert state.leaders[1].merit_tally.successful_assassinations == titleholder_tally_before


def test_resolve_attempt_never_touches_merit_tally_on_failure():
    state = build_state()
    titleholder_tally_before = state.leaders[1].merit_tally.successful_assassinations

    resolve_grandfather_of_assassins_attempt(state, target_leader_id=2, rng=ScriptedRandom([0.99]))

    assert state.leaders[1].merit_tally.successful_assassinations == titleholder_tally_before
    assert state.leaders[2].merit_tally.successful_assassinations == 0
