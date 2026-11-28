"""Tests for turn/experience.py -- see its module docstring for the full
AKGEN_reverse_engineering_report (2).md SS3 derivation.
"""

from __future__ import annotations

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.turn.experience import EXPERIENCE_CREDIT_RISE_THRESHOLD, add_experience, record_experience

from _helpers import ScriptedRandom

LOCATION = None


def _leader(skill: int = 0, aptitude: int = 0, credit: int = 0) -> LeaderState:
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = skill
    raw[Ability.MELEE.value * 2 + 1] = aptitude
    leader = LeaderState(1, kingdom_id=1, name="L", location=LOCATION, skills=SkillTable(raw))
    leader.experience_credit = credit
    return leader


def test_experience_credit_rise_threshold_matches_the_real_formula():
    assert EXPERIENCE_CREDIT_RISE_THRESHOLD == 100


def test_add_experience_sentinel_100_raises_skill_directly_no_credit_touched():
    leader = _leader(skill=0, aptitude=0, credit=42)

    result = add_experience(leader, Ability.MELEE, 100, ScriptedRandom([]))

    assert result.skill_rose is True
    assert result.aptitude_rose is False
    assert result.new_skill == 1
    assert result.new_aptitude == 0
    assert result.new_credit == 42  # sentinel bypasses the credit counter entirely
    assert leader.experience_credit == 42


def test_add_experience_sentinel_100_no_rise_at_max_skill():
    leader = _leader(skill=9, aptitude=9, credit=0)

    result = add_experience(leader, Ability.MELEE, 100, ScriptedRandom([]))

    assert result.skill_rose is False
    assert result.new_skill == 9


def test_add_experience_triangular_gain_below_threshold_accumulates_only():
    # round(10 * (1 + 0.3 - 0.1)) == 12 -- worked example cross-checked
    # via a scratch script before writing this assertion.
    leader = _leader(skill=0, aptitude=0, credit=0)

    result = add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.3, 0.1]))

    assert result.skill_rose is False
    assert result.aptitude_rose is False
    assert result.new_skill == 0
    assert result.new_credit == 12
    assert leader.experience_credit == 12


def test_add_experience_threshold_crossing_gate_success_raises_skill():
    # skill=2, aptitude=9 (unconstrained -> gate P=1.0, always succeeds).
    # credit 90 + gain 12 == 102 >= 100 -> skill rises, credit -= 100.
    leader = _leader(skill=2, aptitude=9, credit=90)

    result = add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.3, 0.1, 0.01]))

    assert result.skill_rose is True
    assert result.aptitude_rose is False
    assert result.new_skill == 3
    assert result.new_aptitude == 9
    assert result.new_credit == 2
    assert leader.experience_credit == 2


def test_add_experience_threshold_crossing_gate_failure_zero_percent_aptitude_rise_fails():
    # skill=0, aptitude=0 -> gate deficit=1 (P=0.5, 0.99 fails); the
    # failure-triggered aptitude-rise attempt uses APT_RISE_CHANCE[0] ==
    # 0.0, so it can never succeed regardless of the roll.
    leader = _leader(skill=0, aptitude=0, credit=90)

    result = add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.3, 0.1, 0.99, 0.05]))

    assert result.skill_rose is False
    assert result.aptitude_rose is False
    assert result.new_skill == 0
    assert result.new_aptitude == 0
    assert result.new_credit == 2  # 100 still subtracted even on total failure


def test_add_experience_threshold_crossing_gate_failure_aptitude_rise_succeeds():
    # skill=1, aptitude=0 -> gate deficit=2 (P=0.25, 0.99 fails); the
    # aptitude-rise attempt uses APT_RISE_CHANCE[1] == 0.10, and 0.05 < 0.10 succeeds.
    leader = _leader(skill=1, aptitude=0, credit=90)

    result = add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.3, 0.1, 0.99, 0.05]))

    assert result.skill_rose is False
    assert result.aptitude_rose is True
    assert result.new_skill == 1
    assert result.new_aptitude == 1
    assert result.new_credit == 2


def test_add_experience_threshold_crossing_at_max_skill_no_rise_credit_still_subtracted():
    leader = _leader(skill=9, aptitude=9, credit=90)

    result = add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.3, 0.1]))

    assert result.skill_rose is False
    assert result.new_skill == 9
    assert result.new_credit == 2


def test_add_experience_attaches_a_fresh_skill_table_when_none_recorded():
    leader = LeaderState(1, kingdom_id=1, name="L", location=LOCATION)

    result = add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.3, 0.1]))

    assert leader.skills is not None
    assert result.new_skill == 0
    assert result.new_credit == 12


def test_add_experience_shares_the_credit_counter_across_abilities():
    # Direct proof of the real "occult rule" (SS3.3) for the non-Practice
    # side too: credit earned via one ability's own Add_Experience call
    # carries over and can raise a completely different ability.
    leader = _leader(skill=0, aptitude=0, credit=0)
    raw = leader.skills.raw_values
    raw[Ability.NECROMANCY.value * 2] = 2
    raw[Ability.NECROMANCY.value * 2 + 1] = 9
    leader.skills = SkillTable(raw)

    add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.3, 0.1]))
    assert leader.experience_credit == 12

    # Fast-forward the remaining accumulation (as if from further real
    # Melee/other Add_Experience calls not scripted here) up to just
    # below threshold, keeping the 12 already earned genuinely folded in.
    leader.experience_credit += 84  # 12 + 84 == 96
    result = add_experience(leader, Ability.NECROMANCY, 10, ScriptedRandom([0.3, 0.1, 0.01]))

    assert result.skill_rose is True
    assert result.new_skill == 3
    assert leader.skills.pair_for_ability(Ability.MELEE) == (0, 0)  # never touched
    assert leader.experience_credit == 8  # 96 + 12 (this call's own gain) - 100


def test_record_experience_collects_the_skill_rises_granted_inside_the_block_only():
    leader = _leader(skill=1, aptitude=3)
    outside = _leader(skill=1, aptitude=3)

    add_experience(outside, Ability.MELEE, 100, ScriptedRandom([]))  # before the block: not recorded
    with record_experience() as log:
        add_experience(leader, Ability.MELEE, 100, ScriptedRandom([]))  # the sentinel raises the skill outright
        add_experience(leader, Ability.ARCHERY, 10, ScriptedRandom([0.3, 0.1]))  # 12 credit: no rise
    add_experience(outside, Ability.MELEE, 100, ScriptedRandom([]))  # after the block: not recorded

    assert log == [(1, Ability.MELEE, "skill")]


def test_award_combat_cast_experience_credits_the_school_only_to_a_caster_with_skill():
    from ak_engine.models.game_state import GameState
    from ak_engine.turn.challenge_execution import award_combat_cast_experience

    state = GameState()
    skilled = _leader(skill=2, aptitude=3, credit=0)
    unskilled = _leader(skill=0, aptitude=3, credit=0)
    unskilled.leader_id = 2
    state.add_leader(skilled)
    state.add_leader(unskilled)

    award_combat_cast_experience(state, ((1, Ability.MELEE), (2, Ability.MELEE)), ScriptedRandom([0.3, 0.1]))

    assert skilled.experience_credit == 12  # round(10 * (1 + 0.3 - 0.1))
    assert unskilled.experience_credit == 0  # "skill 0 stays excluded"


def test_add_experience_builds_on_a_rise_already_waiting_for_the_next_phase():
    # A skill rise is pending; a second Add_Experience in the same phase raises the aptitude: both must survive.
    leader = _leader(skill=2, aptitude=2, credit=99)
    leader.pending_skill_advancement[Ability.MELEE] = (3, 2)

    result = add_experience(leader, Ability.MELEE, 10, ScriptedRandom([0.5, 0.5, 0.99, 0.0]))

    assert result.aptitude_rose is True
    assert leader.pending_skill_advancement[Ability.MELEE] == (3, 3)
