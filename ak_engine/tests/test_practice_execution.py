from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.practice_execution import (
    APT_RISE_CHANCE,
    MAX_SKILL_LEVEL,
    SOLO_PRACTICE_CHANCE,
    PracticeExecutionResult,
    attempt_skill_rise,
    execute_practice,
    resolve_practice_group,
    resolve_practice_pair,
    resolve_practice_solo,
)

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)


def test_apt_rise_chance_matches_ctme_pas_table_exactly():
    # CTME.PAS: apt_rise: array[0..10] OF byte = (0,10,25,50,100,80,60,40,20,0,0);
    assert APT_RISE_CHANCE == (0.0, 0.10, 0.25, 0.50, 1.0, 0.80, 0.60, 0.40, 0.20, 0.0, 0.0)


def test_attempt_skill_rise_succeeds_and_does_not_touch_aptitude():
    rng = ScriptedRandom([0.01])  # well under any base chance
    outcome = attempt_skill_rise(current_skill=2, aptitude=5, base_chance=SOLO_PRACTICE_CHANCE, rng=rng)

    assert outcome.skill_rose is True
    assert outcome.aptitude_rose is False
    assert outcome.new_skill == 3
    assert outcome.new_aptitude == 5


def test_attempt_skill_rise_failure_within_aptitude_never_rolls_for_aptitude():
    # aptitude(5) >= target level (3) -> levels_beyond_aptitude == 0, so a
    # failed skill roll is NOT "because of low aptitude" -- only 1 rng
    # call total; a 2nd .random() call would raise IndexError.
    rng = ScriptedRandom([0.99])
    outcome = attempt_skill_rise(current_skill=2, aptitude=5, base_chance=SOLO_PRACTICE_CHANCE, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.aptitude_rose is False
    assert outcome.new_skill == 2
    assert outcome.new_aptitude == 5


def test_attempt_skill_rise_failure_beyond_aptitude_rolls_for_aptitude_increase():
    # aptitude(0), target level 1 -> 1 level beyond aptitude -> the skill
    # roll's own failure is "because of low aptitude", triggering the
    # apt_rise roll. APT_RISE_CHANCE[0] == 0.0 (current skill 0), so a
    # near-1.0 roll still fails -- confirms the 2nd roll actually ran
    # (would raise IndexError on ScriptedRandom's queue underflow if not).
    rng = ScriptedRandom([0.99, 0.99])
    outcome = attempt_skill_rise(current_skill=0, aptitude=0, base_chance=SOLO_PRACTICE_CHANCE, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.aptitude_rose is False
    assert outcome.new_skill == 0
    assert outcome.new_aptitude == 0


def test_attempt_skill_rise_aptitude_increase_succeeds():
    # current_skill=4 -> APT_RISE_CHANCE[4] == 1.0 (guaranteed).
    rng = ScriptedRandom([0.99, 0.01])
    outcome = attempt_skill_rise(current_skill=4, aptitude=4, base_chance=SOLO_PRACTICE_CHANCE, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.aptitude_rose is True
    assert outcome.new_skill == 4
    assert outcome.new_aptitude == 5


def test_attempt_skill_rise_noop_when_skill_already_at_cap():
    # SkillTable's documented 0-9 range -- no roll at all, no rng consumed.
    rng = ScriptedRandom([])
    outcome = attempt_skill_rise(current_skill=MAX_SKILL_LEVEL, aptitude=9, base_chance=1.0, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.aptitude_rose is False
    assert outcome.new_skill == MAX_SKILL_LEVEL
    assert outcome.new_aptitude == 9


def test_maybe_raise_aptitude_guard_consumes_no_rng_when_aptitude_already_at_cap():
    # Defensive guard: _maybe_raise_aptitude itself never rolls once
    # aptitude is already at MAX_SKILL_LEVEL -- in practice unreachable
    # via attempt_skill_rise (aptitude=9 always makes levels_beyond_
    # aptitude 0 there, short-circuiting before this is even called), so
    # tested directly against the empty-list ScriptedRandom guard instead.
    from ak_engine.turn.practice_execution import _maybe_raise_aptitude

    assert _maybe_raise_aptitude(current_skill=4, aptitude=9, rng=ScriptedRandom([])) is False


def test_chance_after_aptitude_halving_matches_rulebooks_own_worked_example():
    from ak_engine.turn.practice_execution import _chance_after_aptitude_halving

    # "aptitude of 1: no trouble attaining level 1 (100%), 50% for level
    # 2, 25% for level 3, 12.5% for level 4."
    assert _chance_after_aptitude_halving(1.0, current_skill=0, aptitude=1) == pytest.approx(1.0)
    assert _chance_after_aptitude_halving(1.0, current_skill=1, aptitude=1) == pytest.approx(0.5)
    assert _chance_after_aptitude_halving(1.0, current_skill=2, aptitude=1) == pytest.approx(0.25)
    assert _chance_after_aptitude_halving(1.0, current_skill=3, aptitude=1) == pytest.approx(0.125)


def test_resolve_practice_solo_uses_the_5_percent_base_chance():
    rng = ScriptedRandom([0.04])  # just under 5%
    outcome = resolve_practice_solo(current_skill=0, aptitude=9, rng=rng)
    assert outcome.skill_rose is True

    rng = ScriptedRandom([0.06])  # just over 5%
    outcome = resolve_practice_solo(current_skill=0, aptitude=9, rng=rng)
    assert outcome.skill_rose is False


def test_resolve_practice_pair_guaranteed_rise_for_the_lower_skill_partner():
    # skill_a(1) < skill_b(3) -> a is guaranteed (subject to aptitude);
    # b gets nothing this action -- 0 rng calls for b confirmed via the
    # single-value scripted queue underflowing if b were rolled too.
    rng = ScriptedRandom([0.01])
    outcome_a, outcome_b = resolve_practice_pair(
        skill_a=1, aptitude_a=9, skill_b=3, aptitude_b=9, rng=rng
    )

    assert outcome_a.skill_rose is True
    assert outcome_a.new_skill == 2
    assert outcome_b.skill_rose is False
    assert outcome_b.new_skill == 3


def test_resolve_practice_pair_reverse_order_still_favors_the_lower_skill_partner():
    rng = ScriptedRandom([0.01])
    outcome_a, outcome_b = resolve_practice_pair(
        skill_a=5, aptitude_a=9, skill_b=2, aptitude_b=9, rng=rng
    )

    assert outcome_a.skill_rose is False
    assert outcome_b.skill_rose is True
    assert outcome_b.new_skill == 3


def test_resolve_practice_pair_tied_skill_rolls_10_percent_each_independently():
    rng = ScriptedRandom([0.05, 0.5])  # a succeeds (< 10%), b fails (>= 10%)
    outcome_a, outcome_b = resolve_practice_pair(
        skill_a=2, aptitude_a=9, skill_b=2, aptitude_b=9, rng=rng
    )

    assert outcome_a.skill_rose is True
    assert outcome_b.skill_rose is False


def test_resolve_practice_group_requires_at_least_two_practicers():
    with pytest.raises(ValueError):
        resolve_practice_group([(0, 9)], rng=random.Random(0))


def test_resolve_practice_group_all_equal_uses_tied_chance_for_everyone():
    rng = ScriptedRandom([0.05, 0.05, 0.5])
    outcomes = resolve_practice_group([(2, 9), (2, 9), (2, 9)], rng=rng)

    assert [o.skill_rose for o in outcomes] == [True, True, False]


def test_resolve_practice_group_only_the_minimum_skill_members_roll():
    # Two tied at the group minimum (1), one strictly higher (4) -- only
    # the two at the minimum get a (guaranteed, aptitude-permitting) roll;
    # the higher-skill member gets nothing, no rng consumed for them.
    rng = ScriptedRandom([0.01, 0.01])
    outcomes = resolve_practice_group([(1, 9), (4, 9), (1, 9)], rng=rng)

    assert outcomes[0].skill_rose is True
    assert outcomes[1].skill_rose is False
    assert outcomes[1].new_skill == 4
    assert outcomes[2].skill_rose is True


def _state_with_leader(skills: SkillTable | None) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Practicer", location=LOCATION, skills=skills))
    return state


def test_execute_practice_attaches_a_fresh_skill_table_when_none_recorded():
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01]))

    assert isinstance(result, PracticeExecutionResult)
    assert result.skill_rose is True
    assert result.new_skill == 1
    assert result.new_aptitude == 0
    assert state.leaders[1].skills is not None
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (1, 0)


def test_execute_practice_reuses_and_only_touches_the_practiced_abilitys_pair():
    raw = [0] * 30
    raw[Ability.NECROMANCY.value * 2] = 3
    raw[Ability.NECROMANCY.value * 2 + 1] = 5
    state = _state_with_leader(skills=SkillTable(raw))

    execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01]))

    # Sage rose from the fresh-zero baseline...
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (1, 0)
    # ...but Necromancy's own pair is untouched.
    assert state.leaders[1].skills.pair_for_ability(Ability.NECROMANCY) == (3, 5)


def test_execute_practice_tactical_is_not_implemented_and_does_not_mutate_state():
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.TACTICAL, rng=ScriptedRandom([]))

    assert result.not_implemented_for_ability is True
    assert result.skill_rose is False
    assert state.leaders[1].skills is None  # never even attached a placeholder table


def test_execute_practice_raw_out_of_range_ability_is_not_implemented():
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=99, rng=ScriptedRandom([]))

    assert result.not_implemented_for_ability is True
    assert result.ability == 99
    assert state.leaders[1].skills is None


def test_execute_practice_sages_own_skill_still_rises_normally():
    # Sage's extra device-discovery roll isn't modeled, but its ordinary
    # [3.13] skill rise still runs like any other ability.
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01]))

    assert result.not_implemented_for_ability is False
    assert result.skill_rose is True
