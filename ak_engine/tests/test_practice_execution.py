from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.practice_execution import (
    APT_RISE_CHANCE,
    MAX_SKILL_LEVEL,
    SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL,
    SOLO_PRACTICE_CHANCE,
    TACTICAL_TRAINING_CHANCE,
    PracticeExecutionResult,
    _select_discovery_to_grant,
    attempt_skill_rise,
    execute_practice,
    execute_practice_group,
    execute_practice_tactical,
    execute_practice_tactical_group,
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

    # Second value pads Sage's own device-discovery roll (Phase 171) --
    # moot here since current_skill=0 (pre-rise) gives it a 0% chance.
    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.9]))

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

    execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.9]))

    # Sage rose from the fresh-zero baseline...
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (1, 0)
    # ...but Necromancy's own pair is untouched.
    assert state.leaders[1].skills.pair_for_ability(Ability.NECROMANCY) == (3, 5)


def test_execute_practice_blocked_while_comatose():
    # Phase 310: Kill_Enemy's own coma variant ([4.25.2]) -- "non potrà
    # aumentare i talenti con l'esperienza."
    raw = [0] * 30
    raw[Ability.SAGE.value * 2] = 3
    state = _state_with_leader(skills=SkillTable(raw))
    state.leaders[1].is_comatose = True

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([]))

    assert result.skill_rose is False
    assert result.aptitude_rose is False
    # The real stored pair is untouched.
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (3, 0)


def test_execute_practice_tactical_still_works_while_comatose():
    # Training the leader's own *armies* doesn't depend on the leader's
    # own ability -- only raising the leader's own Talents is blocked.
    state = _state_with_leader(skills=None)
    state.leaders[1].is_comatose = True
    state.add_army(ArmyState(101, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=1))
    state.add_army(ArmyState(102, 1, ArmyType.LEGION, Quality.CRACK, LOCATION, commanded_by=1))

    result = execute_practice(state, leader_id=1, ability=Ability.TACTICAL, rng=ScriptedRandom([0.01]))

    assert result.trained_army_ids == (101,)


def test_execute_practice_tactical_does_not_touch_personal_skill():
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.TACTICAL, rng=ScriptedRandom([]))

    assert result.not_implemented_for_ability is False
    assert result.skill_rose is False
    assert result.trained_army_ids == ()
    assert state.leaders[1].skills is None  # [6.1] never touches personal skill at all


# -- Phase 167: Ability.TACTICAL's own army-training mechanic ([6.1]) -------


def _army(army_id: int, quality: Quality, *, commanded_by: int | None = 1) -> ArmyState:
    return ArmyState(army_id, 1, ArmyType.BOWMEN, quality, LOCATION, commanded_by=commanded_by)


def test_execute_practice_tactical_trains_a_green_army_when_a_higher_tier_army_is_present():
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.GREEN))
    state.add_army(_army(2, Quality.VETERAN))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.0]))

    assert trained == (1,)
    assert state.armies[1].quality is Quality.AVERAGE
    assert state.armies[2].quality is Quality.VETERAN  # untouched, not itself trainable


def test_execute_practice_tactical_trains_a_crack_army_at_its_own_sourced_chance():
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.CRACK))
    state.add_army(_army(2, Quality.ELITE))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.001]))

    assert trained == (1,)
    assert state.armies[1].quality is Quality.ELITE


def test_execute_practice_tactical_requires_a_higher_quality_army_present():
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.GREEN))
    state.add_army(_army(2, Quality.GREEN))  # same tier, doesn't count as "higher"

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.0]))

    assert trained == ()
    assert state.armies[1].quality is Quality.GREEN


def test_execute_practice_tactical_leaves_elite_alone():
    # Elite has no next tier to rise to -- the one quality genuinely
    # absent from TACTICAL_TRAINING_CHANCE (see module docstring).
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.ELITE))
    state.add_army(_army(2, Quality.ELITE))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.0]))

    assert trained == ()
    assert state.armies[1].quality is Quality.ELITE


def test_execute_practice_tactical_trains_a_depleted_army_at_full_source_from_rules_ak():
    # Phase 263: RULES.AK [6.1]'s own complete table -- "Depleted =>
    # Green: 100%", still gated on an inspiring higher-quality army.
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.DEPLETED))
    state.add_army(_army(2, Quality.GREEN))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.0]))

    assert trained == (1,)
    assert state.armies[1].quality is Quality.GREEN


def test_execute_practice_tactical_trains_an_average_army_at_its_sourced_chance():
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.AVERAGE))
    state.add_army(_army(2, Quality.VETERAN))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.049]))

    assert trained == (1,)
    assert state.armies[1].quality is Quality.VETERAN


def test_execute_practice_tactical_trains_a_veteran_army_at_its_sourced_chance():
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.VETERAN))
    state.add_army(_army(2, Quality.CRACK))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.009]))

    assert trained == (1,)
    assert state.armies[1].quality is Quality.CRACK


def test_execute_practice_tactical_depleted_still_needs_an_inspiring_army():
    # Even the "100%" tier is gated on the same "train and inspire"
    # precondition -- no army present above Depleted means no roll.
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.DEPLETED))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.0]))

    assert trained == ()
    assert state.armies[1].quality is Quality.DEPLETED


def test_execute_practice_tactical_ignores_armies_commanded_by_someone_else():
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.GREEN, commanded_by=2))
    state.add_army(_army(2, Quality.VETERAN, commanded_by=2))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.0]))

    assert trained == ()


def test_execute_practice_tactical_fails_the_roll():
    state = _state_with_leader(skills=None)
    state.add_army(_army(1, Quality.GREEN))
    state.add_army(_army(2, Quality.VETERAN))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.99]))

    assert trained == ()
    assert state.armies[1].quality is Quality.GREEN


def test_execute_practice_tactical_group_pools_armies_across_co_practicing_leaders():
    # Phase 304: RULES.AK [6.1] -- "If two leaders Practice Tactics
    # together, their armies are pooled into the same training
    # maneuvers." Leader 1's own Green army has no higher-tier army of
    # its OWN command to inspire it, but leader 2 (co-practicing)
    # commands a Veteran army -- pooled, that's enough to train it,
    # which the single-leader execute_practice_tactical() alone could
    # never do for leader 1's own command.
    state = _state_with_leaders(1, 2)
    state.add_army(_army(1, Quality.GREEN, commanded_by=1))
    state.add_army(_army(2, Quality.VETERAN, commanded_by=2))

    trained_by_leader = execute_practice_tactical_group(state, [1, 2], rng=ScriptedRandom([0.0]))

    assert trained_by_leader == {1: (1,), 2: ()}
    assert state.armies[1].quality is Quality.AVERAGE
    assert state.armies[2].quality is Quality.VETERAN  # untouched, not itself trainable


def test_execute_practice_tactical_group_without_pooling_would_never_have_trained():
    # Same setup as above, but proves the *solo* mechanic genuinely
    # can't do this -- leader 1's own command alone has no inspiring
    # army, so execute_practice_tactical() finds nothing to train.
    state = _state_with_leaders(1, 2)
    state.add_army(_army(1, Quality.GREEN, commanded_by=1))
    state.add_army(_army(2, Quality.VETERAN, commanded_by=2))

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([]))

    assert trained == ()
    assert state.armies[1].quality is Quality.GREEN


def test_execute_practice_tactical_group_reports_each_leaders_own_armies_only():
    state = _state_with_leaders(1, 2)
    state.add_army(_army(10, Quality.GREEN, commanded_by=1))
    state.add_army(_army(20, Quality.GREEN, commanded_by=2))
    state.add_army(_army(30, Quality.VETERAN, commanded_by=2))  # inspires both Green armies

    trained_by_leader = execute_practice_tactical_group(state, [1, 2], rng=ScriptedRandom([0.0, 0.0]))

    assert trained_by_leader[1] == (10,)  # leader 1's own result never lists leader 2's army id 20
    assert trained_by_leader[2] == (20,)
    assert state.armies[10].quality is Quality.AVERAGE
    assert state.armies[20].quality is Quality.AVERAGE
    assert state.armies[30].quality is Quality.VETERAN


def test_execute_practice_tactical_group_requires_at_least_two_leaders_via_execute_practice_group():
    state = _state_with_leaders(1)

    with pytest.raises(ValueError):
        execute_practice_group(state, [1], Ability.TACTICAL, rng=ScriptedRandom([]))


def test_tactical_training_chance_covers_all_five_transitions_per_rules_ak_6_1():
    # Phase 263: the complete RULES.AK [6.1] training-maneuvers table --
    # Elite has no next tier, so it's the only Quality absent here.
    assert set(TACTICAL_TRAINING_CHANCE) == {
        Quality.DEPLETED, Quality.GREEN, Quality.AVERAGE, Quality.VETERAN, Quality.CRACK,
    }
    assert TACTICAL_TRAINING_CHANCE[Quality.DEPLETED] == 1.0
    assert TACTICAL_TRAINING_CHANCE[Quality.GREEN] == 0.25
    assert TACTICAL_TRAINING_CHANCE[Quality.AVERAGE] == 0.05
    assert TACTICAL_TRAINING_CHANCE[Quality.VETERAN] == 0.01
    assert TACTICAL_TRAINING_CHANCE[Quality.CRACK] == 0.002


def test_execute_practice_raw_out_of_range_ability_is_not_implemented():
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=99, rng=ScriptedRandom([]))

    assert result.not_implemented_for_ability is True
    assert result.ability == 99
    assert state.leaders[1].skills is None


def test_execute_practice_sages_own_skill_still_rises_normally():
    # Sage's own ordinary [3.13] skill rise runs like any other ability,
    # independent of its own extra device-discovery roll (Phase 171).
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.9]))

    assert result.not_implemented_for_ability is False
    assert result.skill_rose is True


# --- execute_practice_group (Phase 46) ------------------------------------


def _state_with_leaders(*leader_ids: int, skills_by_id: dict[int, SkillTable | None] | None = None) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    skills_by_id = skills_by_id or {}
    for leader_id in leader_ids:
        state.add_leader(
            LeaderState(leader_id, kingdom_id=1, name=f"L{leader_id}", location=LOCATION, skills=skills_by_id.get(leader_id))
        )
    return state


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def test_execute_practice_group_lower_skill_member_gets_guaranteed_roll():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=3, aptitude=9),
        },
    )

    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.01]))

    assert len(results) == 2
    assert results[0].skill_rose is True
    assert results[0].new_skill == 2
    assert results[1].skill_rose is False
    assert results[1].new_skill == 3
    assert state.leaders[1].skills.pair_for_ability(Ability.NECROMANCY) == (2, 9)
    assert state.leaders[2].skills.pair_for_ability(Ability.NECROMANCY) == (3, 9)


def test_execute_practice_group_tied_skill_rolls_independently_for_each():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
        },
    )

    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.05, 0.5]))

    assert results[0].skill_rose is True  # 0.05 < 10%
    assert results[1].skill_rose is False  # 0.5 >= 10%


def test_execute_practice_group_three_leaders_only_minimum_skill_ones_roll():
    state = _state_with_leaders(
        1,
        2,
        3,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=4, aptitude=9),
            3: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
        },
    )

    results = execute_practice_group(state, [1, 2, 3], Ability.NECROMANCY, rng=ScriptedRandom([0.01, 0.01]))

    assert results[0].skill_rose is True
    assert results[1].skill_rose is False
    assert results[1].new_skill == 4
    assert results[2].skill_rose is True


def test_execute_practice_group_attaches_fresh_skill_tables_when_none_recorded():
    state = _state_with_leaders(1, 2)  # neither has skills recorded

    results = execute_practice_group(state, [1, 2], Ability.SAGE, rng=random.Random(0))

    assert state.leaders[1].skills is not None
    assert state.leaders[2].skills is not None
    assert len(results) == 2


def test_execute_practice_group_tactical_resolves_via_army_pooling_not_skill_rise():
    # Phase 304 fix: TACTICAL used to be a blanket not_implemented for
    # the whole group (worse than the solo case, which does train) --
    # it now resolves through execute_practice_tactical_group() instead
    # of the ordinary skill-rise mechanic, and never touches
    # LeaderState.skills at all (TACTICAL trains armies, not skill).
    state = _state_with_leaders(1, 2)

    results = execute_practice_group(state, [1, 2], Ability.TACTICAL, rng=ScriptedRandom([]))

    assert all(not r.not_implemented_for_ability for r in results)
    assert all(r.trained_army_ids == () for r in results)  # no armies commanded -- nothing to pool or train
    assert state.leaders[1].skills is None
    assert state.leaders[2].skills is None


def test_execute_practice_group_raw_out_of_range_ability_is_not_implemented():
    state = _state_with_leaders(1, 2)

    results = execute_practice_group(state, [1, 2], 99, rng=ScriptedRandom([]))

    assert all(r.not_implemented_for_ability for r in results)
    assert all(r.ability == 99 for r in results)


def test_execute_practice_group_requires_at_least_two_leaders():
    state = _state_with_leaders(1)

    with pytest.raises(ValueError):
        execute_practice_group(state, [1], Ability.SAGE, rng=random.Random(0))


# -- Phase 171: Sage's own device-discovery roll ([4.3.1]) --


def test_sage_device_discovery_chance_per_level_is_5_percent():
    assert SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL == 0.05


def test_execute_practice_sage_device_discovery_succeeds():
    # Skill 4, aptitude 9 (unconstrained) -- the rulebook's own worked
    # example ("a level-4 character... will average one discovery per
    # turn"). Chance = 4 * 5% = 20%. First roll (0.99) fails the ordinary
    # skill-rise attempt; second roll (0.15) succeeds the independent
    # device-discovery roll. A successful roll now also grants a real
    # Discovery (Phase 266) -- choice_indices=[0] picks the first
    # not-yet-owned Discovery deterministically.
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))

    result = execute_practice(
        state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15], choice_indices=[0])
    )

    assert result.skill_rose is False
    assert result.device_discovered is True
    assert result.discovery_granted is not None
    assert result.discovery_granted in state.kingdoms[1].discoveries


def test_execute_practice_sage_device_discovery_fails_above_chance():
    # Same 20% chance as above; 0.25 >= 0.20 fails.
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.25]))

    assert result.device_discovered is False


def test_execute_practice_sage_device_discovery_is_zero_chance_at_skill_zero():
    # A fresh (skill=0, aptitude=0) Sageness practicer has a 0 * 5% = 0%
    # discovery chance -- even an almost-zero roll must still fail. Three
    # values: skill-rise roll (fails), the aptitude-rise roll it also
    # triggers (aptitude 0 constrains skill-rise, see attempt_skill_rise),
    # then the device-discovery roll itself.
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.99, 0.001]))

    assert result.device_discovered is False


def test_execute_practice_sage_device_discovery_uses_pre_attempt_skill():
    # Skill 1 rises to 2 this same call (roll 0.01 < the unconstrained 5%
    # solo chance), but the discovery roll must still use the *pre*-rise
    # skill (1 * 5% = 5%), not the post-rise one (2 * 5% = 10%) -- 0.07 is
    # below the wrong 10% chance but above the correct 5% one.
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=1, aptitude=9))

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.07]))

    assert result.skill_rose is True
    assert result.new_skill == 2
    assert result.device_discovered is False


def test_execute_practice_non_sage_ability_never_sets_device_discovered():
    # Only one scripted value is supplied -- proves no extra roll is
    # consumed for a non-Sage ability (an IndexError would surface
    # otherwise, same as Sage's own extra-roll tests above).
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.01]))

    assert result.device_discovered is False


# -- Phase 266: Sage device-discovery acquisition (granting a real Discovery) --


def test_select_discovery_to_grant_picks_uniformly_among_not_yet_owned():
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)
    kingdom.discoveries = {Discovery.LAND_SHIP, Discovery.SCYTHED_CHARIOTS}

    # choice_indices=[0] picks the first entry of the *filtered* list --
    # confirms the two already-owned discoveries were excluded from it.
    granted = _select_discovery_to_grant(kingdom, ScriptedRandom([], choice_indices=[0]))

    assert granted is not None
    assert granted not in {Discovery.LAND_SHIP, Discovery.SCYTHED_CHARIOTS}


def test_select_discovery_to_grant_returns_none_when_kingdom_owns_everything():
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)
    kingdom.discoveries = set(Discovery)

    granted = _select_discovery_to_grant(kingdom, ScriptedRandom([], choice_indices=[]))

    assert granted is None


def test_execute_practice_sage_discovery_grants_a_real_discovery_to_the_kingdom():
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))

    result = execute_practice(
        state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15], choice_indices=[0])
    )

    assert result.device_discovered is True
    assert result.discovery_granted is not None
    assert state.kingdoms[1].discoveries == {result.discovery_granted}


def test_execute_practice_sage_discovery_grants_nothing_for_a_kingdomless_hero():
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=None, name="Wanderer", location=LOCATION,
                                  skills=_skills_with(Ability.SAGE, skill=4, aptitude=9)))

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15]))

    assert result.device_discovered is True
    assert result.discovery_granted is None


def test_execute_practice_sage_discovery_grants_nothing_when_kingdom_already_complete():
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))
    state.kingdoms[1].discoveries = set(Discovery)

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15]))

    assert result.device_discovered is True
    assert result.discovery_granted is None
    assert state.kingdoms[1].discoveries == set(Discovery)


# -- Phase 271: Chancellor Merit Points -- world-first vs. not-first --


def test_execute_practice_sage_discovery_credits_the_worlds_first_discoverer():
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))

    result = execute_practice(
        state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15], choice_indices=[0])
    )

    assert result.discovery_granted is Discovery.LAND_SHIP
    leader = state.leaders[1]
    assert leader.merit_tally.discoveries_found_first == 1
    assert leader.merit_tally.discoveries_found_not_first == 0
    assert state.discoveries_first_found_by[Discovery.LAND_SHIP] == 1


def test_execute_practice_sage_discovery_credits_a_later_independent_discoverer():
    # Another Kingdom (2) already discovered LAND_SHIP first; Kingdom 1's
    # own leader now discovers it independently via Practice.
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.discoveries_first_found_by[Discovery.LAND_SHIP] = 2

    result = execute_practice(
        state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15], choice_indices=[0])
    )

    assert result.discovery_granted is Discovery.LAND_SHIP
    leader = state.leaders[1]
    assert leader.merit_tally.discoveries_found_first == 0
    assert leader.merit_tally.discoveries_found_not_first == 1
    assert state.discoveries_first_found_by[Discovery.LAND_SHIP] == 2  # unchanged -- kingdom 2 stays first


# -- Phase 259: Practice clears a Royal Heir's resurrection eligibility --


def test_execute_practice_clears_is_royal_heir_when_skill_rises():
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))
    state.leaders[1].is_royal_heir = True

    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert state.leaders[1].is_royal_heir is False


def test_execute_practice_leaves_is_royal_heir_when_nothing_rises():
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))
    state.leaders[1].is_royal_heir = True

    # skill=0, aptitude=0 -- both the skill roll and the aptitude-rise
    # roll it triggers fail (APT_RISE_CHANCE[0] == 0.0 too).
    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.99, 0.99]))

    assert result.skill_rose is False
    assert result.aptitude_rose is False
    assert state.leaders[1].is_royal_heir is True  # untouched -- nothing actually improved


def test_execute_practice_non_heir_is_royal_heir_stays_false():
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))

    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert state.leaders[1].is_royal_heir is False  # was already False -- stays False


def test_execute_practice_group_clears_is_royal_heir_only_for_the_leader_who_actually_rose():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=3, aptitude=9),
        },
    )
    state.leaders[1].is_royal_heir = True
    state.leaders[2].is_royal_heir = True

    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.01]))

    assert results[0].skill_rose is True
    assert results[1].skill_rose is False
    assert state.leaders[1].is_royal_heir is False  # rose -- cleared
    assert state.leaders[2].is_royal_heir is True  # didn't rise -- untouched
