from __future__ import annotations

import random

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.turn.cast_execution import is_unfinalized_royal_heir
from ak_engine.turn.combat import Quality
from ak_engine.turn.practice_execution import (
    APT_RISE_CHANCE,
    MAX_SKILL_LEVEL,
    PRACTICE_CREDIT_RISE_THRESHOLD,
    PRACTICE_CREDIT_SOLO_GAIN,
    PRACTICE_CREDIT_TIED_GAIN,
    SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL,
    TACTICAL_TRAINING_CHANCE,
    PracticeExecutionResult,
    _improved_training_multiplier,
    _maybe_grant_advanced_ability,
    _maybe_receive_society_maps,
    _select_discovery_to_grant,
    _teacher_aptitude_bonus,
    execute_practice,
    execute_practice_group,
    execute_practice_tactical,
    execute_practice_tactical_group,
    resolve_practice_group,
    resolve_practice_pair,
    resolve_practice_solo,
    roll_practice_aptitude_gate,
)
from ak_engine.worldgen.explorer_ability_level_schedule import build_explorer_ability_level_schedule
from ak_engine.worldgen.special_ability_level_schedule import MAGIC_COLLEGES, build_magic_ability_level_schedule

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)


def test_apt_rise_chance_matches_ctme_pas_table_exactly():
    # CTME.PAS: apt_rise: array[0..10] OF byte = (0,10,25,50,100,80,60,40,20,0,0);
    assert APT_RISE_CHANCE == (0.0, 0.10, 0.25, 0.50, 1.0, 0.80, 0.60, 0.40, 0.20, 0.0, 0.0)


def test_practice_credit_constants_match_the_real_formula():
    # AKGEN_reverse_engineering_report (2).md SS2/SS6 (Phase 449).
    assert PRACTICE_CREDIT_SOLO_GAIN == 5
    assert PRACTICE_CREDIT_TIED_GAIN == 10
    assert PRACTICE_CREDIT_RISE_THRESHOLD == 100


def test_roll_practice_aptitude_gate_matches_rulebooks_own_worked_example():
    # "aptitude of 1: no trouble attaining level 1 (100%), 50% for level
    # 2, 25% for level 3, 12.5% for level 4."
    assert roll_practice_aptitude_gate(current_skill=0, aptitude=1, rng=ScriptedRandom([0.999])) is True
    assert roll_practice_aptitude_gate(current_skill=1, aptitude=1, rng=ScriptedRandom([0.49])) is True
    assert roll_practice_aptitude_gate(current_skill=1, aptitude=1, rng=ScriptedRandom([0.51])) is False
    assert roll_practice_aptitude_gate(current_skill=2, aptitude=1, rng=ScriptedRandom([0.24])) is True
    assert roll_practice_aptitude_gate(current_skill=2, aptitude=1, rng=ScriptedRandom([0.26])) is False
    assert roll_practice_aptitude_gate(current_skill=3, aptitude=1, rng=ScriptedRandom([0.124])) is True
    assert roll_practice_aptitude_gate(current_skill=3, aptitude=1, rng=ScriptedRandom([0.126])) is False


def test_roll_practice_aptitude_gate_always_succeeds_once_aptitude_covers_the_target():
    # deficit == 0 -> P == 1.0 -- rng.random() always returns < 1.0, so
    # the gate can never fail once aptitude already covers target_skill.
    assert roll_practice_aptitude_gate(current_skill=4, aptitude=9, rng=ScriptedRandom([0.999999])) is True


def test_roll_practice_aptitude_gate_aptitude_bonus_shrinks_the_effective_deficit():
    # Phase 473: current_skill=1, aptitude=1 -> deficit=1, P=0.5 unboosted
    # (0.6 fails); aptitude_bonus=1 -> deficit=0, P=1.0 (0.6 succeeds).
    assert roll_practice_aptitude_gate(current_skill=1, aptitude=1, rng=ScriptedRandom([0.6])) is False
    assert (
        roll_practice_aptitude_gate(current_skill=1, aptitude=1, rng=ScriptedRandom([0.6]), aptitude_bonus=1) is True
    )


def test_maybe_raise_aptitude_guard_consumes_no_rng_when_aptitude_already_at_cap():
    # Defensive guard: _maybe_raise_aptitude itself never rolls once
    # aptitude is already at MAX_SKILL_LEVEL -- in practice unreachable
    # via the real resolvers (aptitude=9 always makes levels_beyond_
    # aptitude 0 there, short-circuiting before this is even called), so
    # tested directly against the empty-list ScriptedRandom guard instead.
    from ak_engine.turn.practice_execution import _maybe_raise_aptitude

    assert _maybe_raise_aptitude(current_skill=4, aptitude=9, rng=ScriptedRandom([])) is False


# -- resolve_practice_solo (Phase 449: gate + persistent credit) -----------


def test_resolve_practice_solo_gate_success_earns_credit_not_an_immediate_rise():
    rng = ScriptedRandom([0.01])  # unconstrained (aptitude 9 >= target 1) -- gate always succeeds
    outcome = resolve_practice_solo(current_skill=0, aptitude=9, credit=0, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.new_skill == 0
    assert outcome.new_credit == PRACTICE_CREDIT_SOLO_GAIN


def test_resolve_practice_solo_credit_crossing_the_threshold_rises_the_skill():
    rng = ScriptedRandom([0.01])
    outcome = resolve_practice_solo(current_skill=3, aptitude=9, credit=96, rng=rng)

    assert outcome.skill_rose is True
    assert outcome.new_skill == 4
    assert outcome.new_aptitude == 9
    assert outcome.new_credit == 1  # 96 + 5 - 100


def test_resolve_practice_solo_gate_failure_within_aptitude_never_rolls_for_aptitude():
    # aptitude(5) >= target level (3) -> deficit == 0 -> gate can never
    # fail (see test_roll_practice_aptitude_gate_always_succeeds...), so
    # this exercises the credit path instead -- only 1 rng call total; a
    # 2nd .random() call would raise IndexError.
    rng = ScriptedRandom([0.99])
    outcome = resolve_practice_solo(current_skill=2, aptitude=5, credit=0, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.new_skill == 2
    assert outcome.new_credit == PRACTICE_CREDIT_SOLO_GAIN


def test_resolve_practice_solo_gate_failure_beyond_aptitude_rolls_for_aptitude_increase():
    # current_skill=2, aptitude=1 -> target 3, deficit 2, gate P=0.25.
    # First roll (0.99) fails the gate; deficit>0 triggers the aptitude-
    # rise roll (APT_RISE_CHANCE[2]==0.25); 0.99 also fails that.
    rng = ScriptedRandom([0.99, 0.99])
    outcome = resolve_practice_solo(current_skill=2, aptitude=1, credit=0, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.aptitude_rose is False
    assert outcome.new_skill == 2
    assert outcome.new_aptitude == 1
    assert outcome.new_credit is None  # gate failed -- credit path never reached


def test_resolve_practice_solo_aptitude_increase_succeeds():
    # current_skill=4, aptitude=0 -> target 5, deficit 5, gate P=2^-5.
    # APT_RISE_CHANCE[4] == 1.0 (guaranteed) once the gate fails.
    rng = ScriptedRandom([0.99, 0.01])
    outcome = resolve_practice_solo(current_skill=4, aptitude=0, credit=0, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.aptitude_rose is True
    assert outcome.new_skill == 4
    assert outcome.new_aptitude == 1
    assert outcome.new_credit is None


def test_resolve_practice_solo_noop_when_skill_already_at_cap():
    # SkillTable's documented 0-9 range -- no roll at all, no rng consumed.
    rng = ScriptedRandom([])
    outcome = resolve_practice_solo(current_skill=MAX_SKILL_LEVEL, aptitude=9, credit=50, rng=rng)

    assert outcome.skill_rose is False
    assert outcome.aptitude_rose is False
    assert outcome.new_skill == MAX_SKILL_LEVEL
    assert outcome.new_aptitude == 9
    assert outcome.new_credit is None  # credit dict untouched


# -- resolve_practice_pair --------------------------------------------------


def test_resolve_practice_pair_immediate_rise_for_the_lower_skill_partner():
    # skill_a(1) < skill_b(3) -> a rises immediately (subject to
    # aptitude), no credit involved; b gets nothing this action -- 0 rng
    # calls for b confirmed via the single-value scripted queue
    # underflowing if b were rolled too.
    rng = ScriptedRandom([0.01])
    outcome_a, outcome_b = resolve_practice_pair(
        skill_a=1, aptitude_a=9, credit_a=0, skill_b=3, aptitude_b=9, credit_b=0, rng=rng
    )

    assert outcome_a.skill_rose is True
    assert outcome_a.new_skill == 2
    assert outcome_a.new_credit is None  # immediate rise, not credit
    assert outcome_b.skill_rose is False
    assert outcome_b.new_skill == 3


def test_resolve_practice_pair_reverse_order_still_favors_the_lower_skill_partner():
    rng = ScriptedRandom([0.01])
    outcome_a, outcome_b = resolve_practice_pair(
        skill_a=5, aptitude_a=9, credit_a=0, skill_b=2, aptitude_b=9, credit_b=0, rng=rng
    )

    assert outcome_a.skill_rose is False
    assert outcome_b.skill_rose is True
    assert outcome_b.new_skill == 3


def test_resolve_practice_pair_tied_skill_earns_credit_independently():
    rng = ScriptedRandom([0.01, 0.01])
    outcome_a, outcome_b = resolve_practice_pair(
        skill_a=2, aptitude_a=9, credit_a=0, skill_b=2, aptitude_b=9, credit_b=95, rng=rng
    )

    assert outcome_a.skill_rose is False
    assert outcome_a.new_credit == PRACTICE_CREDIT_TIED_GAIN
    assert outcome_b.skill_rose is True  # 95 + 10 crosses the threshold
    assert outcome_b.new_skill == 3
    assert outcome_b.new_credit == 5


# -- resolve_practice_group --------------------------------------------------


def test_resolve_practice_group_requires_at_least_two_practicers():
    with pytest.raises(ValueError):
        resolve_practice_group([(0, 9, 0)], rng=random.Random(0))


def test_resolve_practice_group_all_equal_earns_tied_credit_for_everyone():
    rng = ScriptedRandom([0.01, 0.01, 0.01])
    outcomes = resolve_practice_group([(2, 9, 0), (2, 9, 90), (2, 9, 0)], rng=rng)

    assert outcomes[0].skill_rose is False
    assert outcomes[0].new_credit == PRACTICE_CREDIT_TIED_GAIN
    assert outcomes[1].skill_rose is True  # 90 + 10 crosses the threshold
    assert outcomes[1].new_skill == 3
    assert outcomes[1].new_credit == 0
    assert outcomes[2].new_credit == PRACTICE_CREDIT_TIED_GAIN


def test_resolve_practice_group_only_the_minimum_skill_members_roll():
    # Two tied at the group minimum (1), one strictly higher (4) -- only
    # the two at the minimum get an immediate-rise (aptitude-permitting)
    # attempt; the higher-skill member gets nothing, no rng consumed.
    rng = ScriptedRandom([0.01, 0.01])
    outcomes = resolve_practice_group([(1, 9, 0), (4, 9, 0), (1, 9, 0)], rng=rng)

    assert outcomes[0].skill_rose is True
    assert outcomes[1].skill_rose is False
    assert outcomes[1].new_skill == 4
    assert outcomes[2].skill_rose is True


def test_resolve_practice_group_rejects_a_mismatched_aptitude_bonuses_length():
    with pytest.raises(ValueError):
        resolve_practice_group([(1, 1, 0), (4, 9, 0)], rng=random.Random(0), aptitude_bonuses=[1])


def test_resolve_practice_group_aptitude_bonuses_thread_into_the_gate_roll():
    # Phase 473: same 0.6 gate roll as the direct roll_practice_aptitude_
    # gate test above -- unboosted (bonus 0) it fails the minimum-skill
    # member's own gate; boosted (bonus 1) it succeeds.
    rng = ScriptedRandom([0.6, 0.99])  # second value: the failing member's own aptitude-rise fallback
    outcomes = resolve_practice_group([(1, 1, 0), (4, 9, 0)], rng=rng, aptitude_bonuses=[0, 0])
    assert outcomes[0].skill_rose is False

    outcomes = resolve_practice_group([(1, 1, 0), (4, 9, 0)], rng=ScriptedRandom([0.6]), aptitude_bonuses=[1, 0])
    assert outcomes[0].skill_rose is True


def _state_with_leader(skills: SkillTable | None) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Practicer", location=LOCATION, skills=skills))
    return state


def test_execute_practice_attaches_a_fresh_skill_table_when_none_recorded():
    state = _state_with_leader(skills=None)

    # skill=0, aptitude=0 -> target 1, deficit 1, gate P=0.5; 0.01
    # succeeds, earning solo credit (not an immediate rise). Second value
    # pads Sage's own device-discovery roll (Phase 171) -- moot here
    # since current_skill=0 (pre-attempt) gives it a 0% chance.
    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.9]))

    assert isinstance(result, PracticeExecutionResult)
    assert result.skill_rose is False
    assert result.new_skill == 0
    assert result.new_aptitude == 0
    assert state.leaders[1].skills is not None
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (0, 0)
    assert state.leaders[1].experience_credit == PRACTICE_CREDIT_SOLO_GAIN


def test_execute_practice_reuses_and_only_touches_the_practiced_abilitys_pair():
    raw = [0] * 30
    raw[Ability.NECROMANCY.value * 2] = 3
    raw[Ability.NECROMANCY.value * 2 + 1] = 5
    state = _state_with_leader(skills=SkillTable(raw))

    execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.9]))

    # Sage earned credit off the fresh-zero baseline, into the leader's
    # own single shared counter (Phase 456: not a per-ability dict)...
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (0, 0)
    assert state.leaders[1].experience_credit == PRACTICE_CREDIT_SOLO_GAIN
    # ...and Necromancy's own skill/aptitude pair (untouched by this call) is unaffected.
    assert state.leaders[1].skills.pair_for_ability(Ability.NECROMANCY) == (3, 5)


def test_execute_practice_credit_carries_over_and_raises_a_different_ability():
    # Phase 456's own real "occult rule" (AKGEN_reverse_engineering_
    # report (2).md SS3.3): the shared credit counter doesn't belong to
    # any one ability -- whichever ability's own attempt happens to push
    # it past 100 is the one that rises, even if most of that credit was
    # earned practicing something else entirely.
    state = _state_with_leader(skills=SkillTable([0] * 30))

    # Earns +5 solo credit on Sage (skill=0, aptitude=0 -> deficit=1,
    # gate P=0.5; second scripted value pads Sage's own moot device-
    # discovery roll, skill 0 gives it 0% chance regardless).
    execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.9]))
    assert state.leaders[1].experience_credit == PRACTICE_CREDIT_SOLO_GAIN
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (0, 0)

    # Fast-forward the shared counter to just below threshold, then
    # practice a *different* ability (Necromancy, skill=2/aptitude=9 so
    # the gate is guaranteed) -- its own +5 solo gain is what crosses
    # 100, so Necromancy rises, not Sage.
    state.leaders[1].experience_credit = 96
    raw = [0] * 30
    raw[Ability.NECROMANCY.value * 2] = 2
    raw[Ability.NECROMANCY.value * 2 + 1] = 9
    state.leaders[1].skills = SkillTable(raw)

    result = execute_practice(state, leader_id=1, ability=Ability.NECROMANCY, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert result.new_skill == 3
    assert state.leaders[1].skills.pair_for_ability(Ability.NECROMANCY) == (3, 9)
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (0, 0)  # never touched by the credit it earned
    assert state.leaders[1].experience_credit == 1  # 96 + 5 - 100


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
    # The real stored pair (and shared experience credit) are untouched.
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (3, 0)
    assert state.leaders[1].experience_credit == 0


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
# Unaffected by Phase 449 -- Tactical never routes through the skill-rise
# mechanic at all, see module docstring.


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


# -- Phase 641: Improved Training (AIR_FORCE/PRAETOR/FLAGSHIP) --------------


def _titled_army(army_id: int, army_type, *, commanded_by: int | None = None) -> ArmyState:
    # ELITE clears every real army-office's own quality/strength minimum
    # (mirrors tests/test_office_holder.py's own AIR_FORCE/PRAETOR/
    # FLAGSHIP fixtures exactly). commanded_by defaults to None -- a
    # Dragon/Eagle Wing is a monstrous type (turn/battle_orchestrator.py
    # MONSTROUS_ARMY_RACE); commanding it with an ordinary Human, no-
    # Druidic-skill leader would trigger a real [4.32] Druidic-shortfall
    # quality penalty and defeat these fixtures' own point (the same
    # class of test contamination Phase 633 already hit and fixed) --
    # left uncommanded here since office *eligibility* itself never
    # requires a commander (test_office_holder.py's own fixtures don't
    # set one either).
    return ArmyState(army_id, 1, army_type, Quality.ELITE, LOCATION, commanded_by=commanded_by)


def _state_with_air_force_title() -> GameState:
    state = _state_with_leader(skills=None)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(_titled_army(900, ArmyType.DRAGON_WING))
    return state


def _max_druid_skills() -> SkillTable:
    # Clears any real [4.32] Druidic-shortfall requirement outright, so
    # the end-to-end tests below can safely have their own practicing
    # leader directly command a monstrous Dragon/Eagle Wing army without
    # that unrelated mechanic interfering with the Improved Training
    # roll being tested.
    raw = [0] * 31
    raw[Ability.DRUID.value * 2] = 9
    raw[Ability.DRUID.value * 2 + 1] = 9
    return SkillTable(raw_values=raw)


def test_improved_training_multiplier_no_title_held():
    state = _state_with_leader(skills=None)
    army = _army(1, Quality.GREEN)
    state.add_army(army)

    assert _improved_training_multiplier(state, army, [army]) == 1.0


def test_improved_training_multiplier_matching_type_doubles():
    state = _state_with_air_force_title()
    army = ArmyState(1, 1, ArmyType.EAGLE_WING, Quality.GREEN, LOCATION)
    holder = state.armies[900]

    assert _improved_training_multiplier(state, army, [army, holder]) == 2.0


def test_improved_training_multiplier_non_matching_type_gets_one_and_a_half():
    state = _state_with_air_force_title()
    army = _army(1, Quality.GREEN)  # BOWMEN -- land, not flying
    holder = state.armies[900]

    assert _improved_training_multiplier(state, army, [army, holder]) == 1.5


def test_improved_training_multiplier_the_title_holder_does_not_boost_itself():
    state = _state_with_air_force_title()
    holder = state.armies[900]

    assert _improved_training_multiplier(state, holder, [holder]) == 1.0


def test_improved_training_multiplier_holder_outside_the_pool_grants_nothing():
    state = _state_with_air_force_title()
    army = ArmyState(1, 1, ArmyType.EAGLE_WING, Quality.GREEN, LOCATION)

    assert _improved_training_multiplier(state, army, [army]) == 1.0  # holder never passed in `pool`


def test_improved_training_multiplier_takes_the_best_of_multiple_titles():
    state = _state_with_leader(skills=None)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    air_force = _titled_army(900, ArmyType.DRAGON_WING)  # non-matching for a land army
    praetor = _titled_army(901, ArmyType.LEGION)  # matching for a land army
    state.add_army(air_force)
    state.add_army(praetor)
    army = _army(1, Quality.GREEN)  # BOWMEN -- land, matches PRAETOR not AIR_FORCE

    assert _improved_training_multiplier(state, army, [army, air_force, praetor]) == 2.0


def test_execute_practice_tactical_the_improved_training_boost_reaches_the_real_roll():
    # GREEN's own base chance is 0.25 -- 0.3 fails it, but succeeds the
    # AIR_FORCE-doubled 0.5. Proves the multiplier actually reaches
    # rng.random(), not just computed and discarded.
    state = _state_with_leader(skills=_max_druid_skills())
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    holder = ArmyState(900, 1, ArmyType.DRAGON_WING, Quality.ELITE, LOCATION, commanded_by=1)
    trainee = ArmyState(1, 1, ArmyType.EAGLE_WING, Quality.GREEN, LOCATION, commanded_by=1)
    state.add_army(holder)  # the ELITE title-holder itself is the "inspiring" higher-tier army
    state.add_army(trainee)

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.3]))

    assert trained == (1,)
    assert state.armies[1].quality is Quality.AVERAGE


def test_execute_practice_tactical_the_title_holder_gets_no_self_boost():
    # Both the holder and the sibling are CRACK (rolling for Elite, base
    # chance 0.002, AIR_FORCE-doubled 0.004); 0.003 sits strictly
    # between the two. A third, ELITE land army supplies the "inspiring
    # higher-tier army" both CRACK armies need to be roll-eligible at
    # all ([6.1]: "need not be of the same type") without itself
    # contesting the AIR_FORCE title (ineligible type). The title-
    # holder's own roll must use the UNBOOSTED chance (fail at 0.003),
    # while the sibling flying army's own roll gets the doubled chance
    # (succeed at the same 0.003) -- same rng value, opposite outcomes,
    # isolating the self-exclusion rule from everything else.
    state = _state_with_leader(skills=_max_druid_skills())
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    holder = ArmyState(900, 1, ArmyType.DRAGON_WING, Quality.CRACK, LOCATION, commanded_by=1)
    sibling = ArmyState(1, 1, ArmyType.EAGLE_WING, Quality.CRACK, LOCATION, commanded_by=1)
    inspiration = ArmyState(2, 1, ArmyType.BOWMEN, Quality.ELITE, LOCATION, commanded_by=1)
    state.add_army(holder)
    state.add_army(sibling)
    state.add_army(inspiration)

    trained = execute_practice_tactical(state, leader_id=1, rng=ScriptedRandom([0.003, 0.003]))

    assert trained == (1,)  # only the sibling trained up
    assert state.armies[900].quality is Quality.CRACK  # the title-holder itself, unboosted, stayed put
    assert state.armies[1].quality is Quality.ELITE


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


def test_execute_practice_sages_own_credit_still_accrues_normally():
    # Sage's own ordinary [3.13] skill-credit accrual runs like any
    # other ability, independent of its own extra device-discovery roll
    # (Phase 171).
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.01, 0.9]))

    assert result.not_implemented_for_ability is False
    assert result.skill_rose is False
    assert state.leaders[1].experience_credit == PRACTICE_CREDIT_SOLO_GAIN


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


def test_execute_practice_group_lower_skill_member_gets_immediate_rise():
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
    assert state.leaders[1].experience_credit == 0  # immediate rise, no credit


def test_execute_practice_group_tied_skill_earns_credit_independently_for_each():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
        },
    )

    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.01, 0.01]))

    assert results[0].skill_rose is False
    assert results[1].skill_rose is False
    assert state.leaders[1].experience_credit == PRACTICE_CREDIT_TIED_GAIN
    assert state.leaders[2].experience_credit == PRACTICE_CREDIT_TIED_GAIN


def test_execute_practice_group_tied_skill_credit_threshold_crossing_still_gives_no_teacher():
    # No co-practicer has strictly higher skill when tied, so no
    # candidate ever qualifies -- matches the source's "no teacher when
    # tied" rule, even when the credit accumulator itself does cross the
    # threshold and genuinely raises a skill level this call.
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
        },
    )
    state.leaders[1].experience_credit = 95

    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.01, 0.01]))

    assert results[0].skill_rose is True  # 95 + 10 crosses the threshold
    assert results[0].new_skill == 3
    assert state.leaders[1].merit_tally.teaching_interactions == 0
    assert state.leaders[2].merit_tally.teaching_interactions == 0


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


def test_execute_practice_group_comatose_co_practicer_credit_stays_untouched():
    # Direct proof of the Phase 449/456 comatose/credit interaction: a
    # tied scenario would normally earn +10 credit for both co-
    # practicers, but a comatose participant's own experience_credit
    # must stay completely untouched, exactly like their skill/aptitude.
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=2, aptitude=9),
        },
    )
    state.leaders[1].is_comatose = True

    execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.01, 0.01]))

    assert state.leaders[1].experience_credit == 0
    assert state.leaders[2].experience_credit == PRACTICE_CREDIT_TIED_GAIN


# -- Phase 446: Teacher merit (Office.TEACHER) -----------------------------


def test_execute_practice_group_credits_teacher_merit_when_the_student_actually_levels_up():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=3, aptitude=9),
        },
    )

    execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.01]))

    assert state.leaders[2].merit_tally.teaching_interactions == 1
    assert state.leaders[1].merit_tally.teaching_interactions == 0


def test_execute_practice_group_credits_only_the_current_officeholder_among_qualified_candidates():
    state = _state_with_leaders(
        1,
        2,
        3,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=5, aptitude=9),
            3: _skills_with(Ability.NECROMANCY, skill=3, aptitude=9),
        },
    )
    # Leader 3 already qualifies as the current Teacher officeholder
    # (Office.TEACHER minpts=5) despite having lower skill than leader 2.
    state.leaders[3].merit_tally.teaching_interactions = 10

    execute_practice_group(state, [1, 2, 3], Ability.NECROMANCY, rng=ScriptedRandom([0.01]))

    assert state.leaders[3].merit_tally.teaching_interactions == 11
    assert state.leaders[2].merit_tally.teaching_interactions == 0


def test_execute_practice_group_falls_back_to_the_highest_skill_candidate_without_an_officeholder():
    state = _state_with_leaders(
        1,
        2,
        3,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            2: _skills_with(Ability.NECROMANCY, skill=5, aptitude=9),
            3: _skills_with(Ability.NECROMANCY, skill=3, aptitude=9),
        },
    )

    execute_practice_group(state, [1, 2, 3], Ability.NECROMANCY, rng=ScriptedRandom([0.01]))

    assert state.leaders[2].merit_tally.teaching_interactions == 1
    assert state.leaders[3].merit_tally.teaching_interactions == 0


def test_execute_practice_group_credits_no_teacher_for_an_aptitude_only_rise():
    # Aptitude rise != skill rise -- Teacher merit only ever credits a
    # real natural skill level actually gained.
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=0),
            2: _skills_with(Ability.NECROMANCY, skill=3, aptitude=9),
        },
    )

    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.99, 0.01]))

    assert results[0].skill_rose is False
    assert results[0].aptitude_rose is True
    assert state.leaders[2].merit_tally.teaching_interactions == 0


# -- Phase 473: Professor Whizdumb's own aptitude-gate bonus (SS2.5) -------


def test_teacher_aptitude_bonus_grants_one_to_a_strictly_lower_skilled_co_practicer():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=1),
            2: _skills_with(Ability.NECROMANCY, skill=5, aptitude=9),
        },
    )
    state.leaders[2].merit_tally.teaching_interactions = 10  # qualifies as Office.TEACHER holder

    assert _teacher_aptitude_bonus(state, [1, 2], [(1, 1), (5, 9)]) == [1, 0]


def test_teacher_aptitude_bonus_is_zero_without_an_officeholder():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=1),
            2: _skills_with(Ability.NECROMANCY, skill=5, aptitude=9),
        },
    )

    assert _teacher_aptitude_bonus(state, [1, 2], [(1, 1), (5, 9)]) == [0, 0]


def test_teacher_aptitude_bonus_is_zero_when_officeholder_is_tied_not_strictly_higher():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=3, aptitude=1),
            2: _skills_with(Ability.NECROMANCY, skill=3, aptitude=9),
        },
    )
    state.leaders[2].merit_tally.teaching_interactions = 10

    assert _teacher_aptitude_bonus(state, [1, 2], [(3, 1), (3, 9)]) == [0, 0]


def test_teacher_aptitude_bonus_is_zero_when_officeholder_is_not_in_this_group():
    state = _state_with_leaders(
        1,
        2,
        3,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=1),
            2: _skills_with(Ability.NECROMANCY, skill=5, aptitude=9),
            3: _skills_with(Ability.NECROMANCY, skill=9, aptitude=9),
        },
    )
    state.leaders[3].merit_tally.teaching_interactions = 10  # officeholder, but absent from this group

    assert _teacher_aptitude_bonus(state, [1, 2], [(1, 1), (5, 9)]) == [0, 0]


def test_execute_practice_group_whizdumb_bonus_turns_a_failing_gate_into_a_success():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=1),
            2: _skills_with(Ability.NECROMANCY, skill=5, aptitude=9),
        },
    )
    state.leaders[2].merit_tally.teaching_interactions = 10  # Office.TEACHER holder

    # Leader 1's own gate: target=2, aptitude=1, deficit=1, P=0.5 unboosted;
    # with the Whizdumb +1, deficit=0, P=1.0 -- 0.6 fails unboosted, succeeds boosted.
    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.6]))

    assert results[0].skill_rose is True
    assert results[0].new_skill == 2


def test_execute_practice_group_no_whizdumb_bonus_without_an_officeholder():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=1),
            2: _skills_with(Ability.NECROMANCY, skill=5, aptitude=9),
        },
    )

    # Same 0.6 gate roll as the boosted test above, but no officeholder --
    # unboosted P=0.5 fails, falling through to the APT_RISE_CHANCE[1]=0.10
    # aptitude-rise roll, which also fails at 0.99.
    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.6, 0.99]))

    assert results[0].skill_rose is False


def test_execute_practice_group_no_whizdumb_bonus_when_titleholder_tied_with_student():
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.NECROMANCY, skill=1, aptitude=1),
            2: _skills_with(Ability.NECROMANCY, skill=1, aptitude=1),
        },
    )
    state.leaders[2].merit_tally.teaching_interactions = 10  # Office.TEACHER holder, but tied skill

    # Tied branch: both roll independently, neither boosted (holder isn't
    # strictly higher-skilled than the other). Each gate (0.6) fails at
    # unboosted P=0.5, then each aptitude-rise roll (0.99) fails too.
    results = execute_practice_group(state, [1, 2], Ability.NECROMANCY, rng=ScriptedRandom([0.6, 0.99, 0.6, 0.99]))

    assert results[0].skill_rose is False
    assert results[1].skill_rose is False


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
    # turn"). Chance = 4 * 5% = 20%. First roll (0.99) is the aptitude
    # gate, which always succeeds when unconstrained (Phase 449 -- earns
    # solo credit, not an immediate rise); second roll (0.15) succeeds
    # the independent device-discovery roll. A successful roll now also
    # grants a real Discovery (Phase 266) -- choice_indices=[0] picks the
    # first eligible not-yet-owned Discovery deterministically. Phase
    # 448: a fresh state's ``discoveries_first_found_by`` is empty, so
    # the picked candidate isn't yet owned by any Kingdom in the world --
    # a third scripted roll (0.01) is needed for the 5% world-diffusion
    # keep check.
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))

    result = execute_practice(
        state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15, 0.01], choice_indices=[0])
    )

    assert result.skill_rose is False
    assert state.leaders[1].experience_credit == PRACTICE_CREDIT_SOLO_GAIN
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
    # values: the aptitude gate (fails, deficit=1 -> P=0.5), the
    # aptitude-rise roll it also triggers (APT_RISE_CHANCE[0]==0.0, so
    # any roll fails), then the device-discovery roll itself.
    state = _state_with_leader(skills=None)

    result = execute_practice(state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.99, 0.001]))

    assert result.device_discovered is False


def test_execute_practice_sage_device_discovery_uses_pre_attempt_skill():
    # Skill 1, aptitude 9 (unconstrained), with credit already at 96 so
    # this call's own +5 gate success crosses the PRACTICE_CREDIT_RISE_
    # THRESHOLD and genuinely rises the skill this same call (1 -> 2).
    # The discovery roll must still use the *pre*-rise skill (1 * 5% =
    # 5%), not the post-rise one (2 * 5% = 10%) -- 0.07 is above the
    # correct 5% (fails) but below the wrong 10% (would incorrectly
    # succeed).
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=1, aptitude=9))
    state.leaders[1].experience_credit = 96

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


def test_select_discovery_to_grant_excludes_already_owned():
    state = GameState()
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)
    kingdom.discoveries = {Discovery.LAND_SHIP, Discovery.SCYTHED_CHARIOTS}
    state.discoveries_first_found_by[Discovery.PONY_EXPRESS] = 1  # keep deterministic: no diffusion roll needed

    # choice_indices=[0] picks the first entry of the *filtered* list --
    # confirms the two already-owned discoveries were excluded from it
    # (PONY_EXPRESS, ordinal 2, is the first eligible one left).
    granted = _select_discovery_to_grant(state, kingdom, ScriptedRandom([], choice_indices=[0]))

    assert granted is Discovery.PONY_EXPRESS


def test_select_discovery_to_grant_returns_none_when_kingdom_owns_everything():
    state = GameState()
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)
    kingdom.discoveries = set(Discovery)

    granted = _select_discovery_to_grant(state, kingdom, ScriptedRandom([], choice_indices=[]))

    assert granted is None


def test_select_discovery_to_grant_permanently_excludes_hieroglyphic_and_scientific_method():
    # AKGEN_reverse_engineering_report (2).md SS4.2.1: these two ordinals
    # are never selected by ordinary research, even when they're the only
    # discoveries the kingdom doesn't already own.
    state = GameState()
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)
    kingdom.discoveries = set(Discovery) - {
        Discovery.LAND_SHIP,
        Discovery.HIEROGLYPHIC_TRANSLATION,
        Discovery.SCIENTIFIC_METHOD,
    }
    state.discoveries_first_found_by[Discovery.LAND_SHIP] = 1  # skip the diffusion roll

    granted = _select_discovery_to_grant(state, kingdom, ScriptedRandom([], choice_indices=[0]))

    assert granted is Discovery.LAND_SHIP


def test_select_discovery_to_grant_returns_none_when_only_excluded_ordinals_remain():
    state = GameState()
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)
    kingdom.discoveries = set(Discovery) - {Discovery.HIEROGLYPHIC_TRANSLATION, Discovery.SCIENTIFIC_METHOD}

    granted = _select_discovery_to_grant(state, kingdom, ScriptedRandom([], choice_indices=[]))

    assert granted is None


def test_select_discovery_to_grant_always_keeps_a_candidate_the_world_already_owns():
    # No scripted .random() values at all -- an IndexError would surface
    # if the diffusion-bias roll were consumed, proving it's skipped
    # entirely whenever some Kingdom in the world already has it.
    state = GameState()
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)
    state.discoveries_first_found_by[Discovery.LAND_SHIP] = 7

    granted = _select_discovery_to_grant(state, kingdom, ScriptedRandom([], choice_indices=[0]))

    assert granted is Discovery.LAND_SHIP


def test_select_discovery_to_grant_rerolls_95_percent_of_the_time_when_world_lacks_it():
    # Neither candidate is in discoveries_first_found_by. The first pick
    # (LAND_SHIP, index 0) rolls 0.5 -- above the 5% keep chance, so it's
    # rerolled; the second pick (SCYTHED_CHARIOTS, index 1) rolls 0.01 --
    # below 5%, so it's kept.
    state = GameState()
    kingdom = KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION)

    granted = _select_discovery_to_grant(
        state, kingdom, ScriptedRandom([0.5, 0.01], choice_indices=[0, 1])
    )

    assert granted is Discovery.SCYTHED_CHARIOTS


def test_execute_practice_sage_discovery_grants_a_real_discovery_to_the_kingdom():
    state = _state_with_leader(skills=_skills_with(Ability.SAGE, skill=4, aptitude=9))

    result = execute_practice(
        state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15, 0.01], choice_indices=[0])
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
        state, leader_id=1, ability=Ability.SAGE, rng=ScriptedRandom([0.99, 0.15, 0.01], choice_indices=[0])
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


# -- Phase 259/553: Royal Heir resurrection eligibility --
#
# Phase 553 correction: execute_practice()/execute_practice_group() no
# longer clear is_royal_heir on a skill/aptitude rise -- the real engine
# (AKGEN_reverse_engineering_report (5).md SS6.2/SS11.1) gates
# eligibility on a numeric Total_USkill(leader) < 7 threshold instead,
# checked dynamically via turn/cast_execution.py
# is_unfinalized_royal_heir(), not by mutating this flag here.


def test_execute_practice_does_not_clear_is_royal_heir_when_skill_rises():
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))
    state.leaders[1].experience_credit = 96  # +5 this call crosses the threshold
    state.leaders[1].is_royal_heir = True

    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert state.leaders[1].is_royal_heir is True  # Phase 553: no longer cleared here


def test_execute_practice_leaves_is_royal_heir_when_nothing_rises():
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))
    state.leaders[1].is_royal_heir = True

    # skill=0, aptitude=0 -- both the aptitude gate and the aptitude-rise
    # roll it triggers fail (APT_RISE_CHANCE[0] == 0.0 too).
    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.99, 0.99]))

    assert result.skill_rose is False
    assert result.aptitude_rose is False
    assert state.leaders[1].is_royal_heir is True  # untouched -- nothing actually improved


def test_execute_practice_non_heir_is_royal_heir_stays_false():
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))
    state.leaders[1].experience_credit = 96

    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert state.leaders[1].is_royal_heir is False  # was already False -- stays False


def test_execute_practice_group_does_not_clear_is_royal_heir_for_either_leader():
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
    assert state.leaders[1].is_royal_heir is True  # Phase 553: no longer cleared here
    assert state.leaders[2].is_royal_heir is True  # didn't rise -- untouched anyway


def test_execute_practice_one_skill_rise_below_threshold_stays_resurrection_eligible():
    # Phase 553: the real gate is numeric (Total_USkill < 7), not
    # edge-triggered on any Practice rise -- a Heir with a low starting
    # total who trains one ability stays eligible.
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))
    state.leaders[1].skills.set_pair_for_ability(Ability.MELEE, skill=1, aptitude=3)
    state.leaders[1].experience_credit = 96
    state.leaders[1].is_royal_heir = True

    result = execute_practice(state, leader_id=1, ability=Ability.ARCHERY, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert is_unfinalized_royal_heir(state.leaders[1]) is True


def test_execute_practice_skill_rise_crossing_threshold_ends_resurrection_eligibility():
    # Total_USkill reaches 7 with this rise -- the numeric check alone
    # (not a flag mutation) now correctly reports ineligible.
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 31))
    state.leaders[1].skills.set_pair_for_ability(Ability.MELEE, skill=6, aptitude=9)
    state.leaders[1].experience_credit = 96
    state.leaders[1].is_royal_heir = True

    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert state.leaders[1].is_royal_heir is True  # flag itself untouched
    assert is_unfinalized_royal_heir(state.leaders[1]) is False  # but no longer eligible


# -- Phase 396: Sage's device-discovery roll extended to group practice ---


def test_execute_practice_group_sage_rolls_device_discovery_independently_per_leader():
    # Skill 2 (leader 1, the group's minimum -- immediate-rise roll,
    # always succeeds regardless of the scripted value since deficit is
    # 0 at aptitude 9) and skill 5 (leader 2, static/no roll). Device
    # chances are pre-attempt-skill-based: leader 1 = 2*5% = 10%, leader
    # 2 = 5*5% = 25%. 0.05 < 10% succeeds for leader 1; 0.30 >= 25% fails
    # for leader 2 -- proving each co-practicer's own roll is genuinely
    # independent, not shared or skipped. The third scripted roll (0.01)
    # is leader 1's own world-diffusion keep check (Phase 448) -- a fresh
    # state's discoveries_first_found_by is empty.
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.SAGE, skill=2, aptitude=9),
            2: _skills_with(Ability.SAGE, skill=5, aptitude=9),
        },
    )

    results = execute_practice_group(
        state, [1, 2], Ability.SAGE, rng=ScriptedRandom([0.5, 0.05, 0.01, 0.30], choice_indices=[0])
    )

    assert results[0].skill_rose is True  # the immediate-rise (lower-skill) roll
    assert results[0].device_discovered is True
    assert results[0].discovery_granted is not None
    assert results[0].discovery_granted in state.kingdoms[1].discoveries

    assert results[1].skill_rose is False  # static -- not the group minimum
    assert results[1].device_discovered is False
    assert results[1].discovery_granted is None


def test_execute_practice_group_sage_uses_each_leaders_own_pre_attempt_skill():
    # Tied skill (3 each), both already at credit 95 so this call's own
    # +10 tied gain crosses the threshold for both -- a real skill rise
    # (3 -> 4) via the credit accumulator, not an immediate rise. The
    # device roll must still use the *pre*-rise skill (3*5% = 15%), not
    # the post-rise one (4*5% = 20%): 0.17 is above the correct 15%
    # (fails) but below the wrong 20% (would incorrectly succeed).
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.SAGE, skill=3, aptitude=9),
            2: _skills_with(Ability.SAGE, skill=3, aptitude=9),
        },
    )
    state.leaders[1].experience_credit = 95
    state.leaders[2].experience_credit = 95

    results = execute_practice_group(state, [1, 2], Ability.SAGE, rng=ScriptedRandom([0.01, 0.01, 0.17, 0.17]))

    assert results[0].skill_rose is True
    assert results[0].new_skill == 4
    assert results[0].device_discovered is False
    assert results[1].skill_rose is True
    assert results[1].new_skill == 4
    assert results[1].device_discovered is False


def test_execute_practice_group_sage_comatose_co_practicer_gets_no_device_roll():
    # Leader 1 (skill 2, the group's minimum) is comatose -- Phase 310's
    # own gate applies before ever reaching the device roll (matching
    # execute_practice()'s own comatose short-circuit), so only leader
    # 2's own draw is on the scripted list; a stray draw for leader 1
    # would surface as an IndexError.
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.SAGE, skill=2, aptitude=9),
            2: _skills_with(Ability.SAGE, skill=5, aptitude=9),
        },
    )
    state.leaders[1].is_comatose = True

    results = execute_practice_group(state, [1, 2], Ability.SAGE, rng=ScriptedRandom([0.5, 0.30]))

    assert results[0].skill_rose is False
    assert results[0].device_discovered is False
    assert state.leaders[1].skills.pair_for_ability(Ability.SAGE) == (2, 9)  # untouched
    assert results[1].device_discovered is False  # 0.30 >= 25%


def test_execute_practice_group_non_sage_ability_never_rolls_device_discovery():
    # Only one scripted value, for the group's own immediate-rise roll --
    # proves no extra draw is consumed for a non-Sage ability (an
    # IndexError would surface otherwise, same proof shape as the solo
    # case's own equivalent test).
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.MELEE, skill=2, aptitude=9),
            2: _skills_with(Ability.MELEE, skill=5, aptitude=9),
        },
    )

    results = execute_practice_group(state, [1, 2], Ability.MELEE, rng=ScriptedRandom([0.5]))

    assert all(not r.device_discovered for r in results)


# -- Phase 493: Advanced Ability grant (5 magic colleges + Explorer) -----


def test_maybe_grant_advanced_ability_returns_none_without_a_skill_rise():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    leader = LeaderState(1, kingdom_id=1, name="L1", location=LOCATION)
    state.add_leader(leader)

    granted = _maybe_grant_advanced_ability(state, leader, Ability.WHITE, skill_rose=False, new_skill=5)

    assert granted is None
    assert leader.advanced_abilities == set()


def test_maybe_grant_advanced_ability_returns_none_for_an_unscheduled_ability():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    leader = LeaderState(1, kingdom_id=1, name="L1", location=LOCATION)
    state.add_leader(leader)

    assert Ability.MELEE not in MAGIC_COLLEGES
    assert Ability.MELEE is not Ability.EXPLORER
    granted = _maybe_grant_advanced_ability(state, leader, Ability.MELEE, skill_rose=True, new_skill=5)

    assert granted is None
    assert leader.advanced_abilities == set()


def test_maybe_grant_advanced_ability_returns_none_when_new_skill_is_none():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    leader = LeaderState(1, kingdom_id=1, name="L1", location=LOCATION)
    state.add_leader(leader)

    granted = _maybe_grant_advanced_ability(state, leader, Ability.WHITE, skill_rose=True, new_skill=None)

    assert granted is None


def test_maybe_grant_advanced_ability_grants_the_real_scheduled_ability():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    leader = LeaderState(1, kingdom_id=1, name="L1", location=LOCATION)
    state.add_leader(leader)

    expected = build_magic_ability_level_schedule(state.game_number)[Ability.WHITE].get(5)

    granted = _maybe_grant_advanced_ability(state, leader, Ability.WHITE, skill_rose=True, new_skill=5)

    assert granted is expected
    if expected is not None:
        assert expected in leader.advanced_abilities


def test_maybe_grant_advanced_ability_grants_the_real_scheduled_explorer_ability():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    leader = LeaderState(1, kingdom_id=1, name="L1", location=LOCATION)
    state.add_leader(leader)

    expected = build_explorer_ability_level_schedule(state.game_number).get(5)

    granted = _maybe_grant_advanced_ability(state, leader, Ability.EXPLORER, skill_rose=True, new_skill=5)

    assert granted is expected
    assert expected is not None
    assert expected in leader.advanced_abilities


# -- Phase 510: Society Maps ------------------------------------------


def _state_with_leader_and_provinces(*, has_society_maps: bool, kingdom_id: int | None = 1) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    leader = LeaderState(1, kingdom_id=kingdom_id, name="L1", location=LOCATION)
    if has_society_maps:
        leader.advanced_abilities.add(AdvancedAbility.EXPLORERS_SOCIETY_MAPS)
    state.add_leader(leader)
    for i in range(5):
        state.add_province(ProvinceState(HexCoord(i, 0), Terrain.PLAINS, Race.HUMAN))
    return state


def test_maybe_receive_society_maps_returns_nothing_for_a_non_explorer_ability():
    state = _state_with_leader_and_provinces(has_society_maps=True)
    revealed = _maybe_receive_society_maps(state, state.leaders[1], Ability.WHITE, random.Random(0))
    assert revealed == ()


def test_maybe_receive_society_maps_returns_nothing_without_the_advanced_ability():
    state = _state_with_leader_and_provinces(has_society_maps=False)
    revealed = _maybe_receive_society_maps(state, state.leaders[1], Ability.EXPLORER, random.Random(0))
    assert revealed == ()


def test_maybe_receive_society_maps_returns_nothing_for_a_kingdom_less_hero():
    state = _state_with_leader_and_provinces(has_society_maps=True, kingdom_id=None)
    revealed = _maybe_receive_society_maps(state, state.leaders[1], Ability.EXPLORER, random.Random(0))
    assert revealed == ()


def test_maybe_receive_society_maps_reveals_one_to_three_provinces():
    state = _state_with_leader_and_provinces(has_society_maps=True)
    revealed = _maybe_receive_society_maps(state, state.leaders[1], Ability.EXPLORER, random.Random(0))
    assert 1 <= len(revealed) <= 3
    for coord in revealed:
        assert state.provinces[coord].explored_percent_by_kingdom[1] > 0


def test_execute_practice_reveals_society_maps_provinces_when_the_skill_rises():
    # skill=4, aptitude=9 -> deficit 0, gate guaranteed; credit=95 means
    # the +5 solo gain crosses the 100 threshold, an immediate rise --
    # same guaranteed-rise setup test_execute_practice_grants_advanced_
    # ability_on_a_magic_college_skill_rise uses. Real (unscripted)
    # seeded RNG since _maybe_receive_society_maps's own shuffle()/
    # randint() draws extra randomness beyond the gate roll itself.
    state = _state_with_leader_and_provinces(has_society_maps=True)
    state.leaders[1].skills = _skills_with(Ability.EXPLORER, skill=4, aptitude=9)
    state.leaders[1].experience_credit = 95

    result = execute_practice(state, leader_id=1, ability=Ability.EXPLORER, rng=random.Random(0))

    assert result.skill_rose is True
    assert 1 <= len(result.society_maps_revealed) <= 3


def test_execute_practice_reveals_society_maps_provinces_when_the_skill_does_not_rise():
    # skill=0, aptitude=0, credit=0 -> even a successful gate roll only
    # earns +5 solo credit, nowhere near the 100 threshold -- skill_rose
    # is deterministically False in a single call from a fresh baseline,
    # regardless of the gate roll's own outcome. Society Maps still
    # fires, proving it's independent of skill_rose either way.
    state = _state_with_leader_and_provinces(has_society_maps=True)
    state.leaders[1].skills = None

    result = execute_practice(state, leader_id=1, ability=Ability.EXPLORER, rng=random.Random(0))

    assert result.skill_rose is False
    assert 1 <= len(result.society_maps_revealed) <= 3


def test_execute_practice_group_reveals_society_maps_for_each_qualifying_participant():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    leader1 = LeaderState(1, kingdom_id=1, name="L1", location=LOCATION)
    leader1.advanced_abilities.add(AdvancedAbility.EXPLORERS_SOCIETY_MAPS)
    leader2 = LeaderState(2, kingdom_id=1, name="L2", location=LOCATION)
    state.add_leader(leader1)
    state.add_leader(leader2)
    for i in range(6):
        state.add_province(ProvinceState(HexCoord(i, 0), Terrain.PLAINS, Race.HUMAN))

    results = execute_practice_group(state, [1, 2], Ability.EXPLORER, rng=random.Random(0))

    assert 1 <= len(results[0].society_maps_revealed) <= 3
    assert results[1].society_maps_revealed == ()


def test_execute_practice_grants_advanced_ability_on_a_magic_college_skill_rise():
    # skill=4, aptitude=9 -> target 5, deficit 0, gate guaranteed. credit
    # starts at 95 so the +5 solo gain crosses the 100 threshold and
    # rises White Magic straight from 4 to 5 this same call.
    state = _state_with_leader(skills=_skills_with(Ability.WHITE, skill=4, aptitude=9))
    state.leaders[1].experience_credit = 95

    expected = build_magic_ability_level_schedule(state.game_number)[Ability.WHITE].get(5)

    result = execute_practice(state, leader_id=1, ability=Ability.WHITE, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert result.new_skill == 5
    assert result.advanced_ability_granted is expected
    if expected is not None:
        assert expected in state.leaders[1].advanced_abilities


def test_execute_practice_grants_nothing_for_a_non_magic_college_skill_rise():
    # Same guaranteed-rise shape as the test above, but Ability.MELEE
    # isn't one of the 5 wired categories -- see _maybe_grant_advanced_
    # ability()'s own docstring for why (real template content for the
    # other 10 categories was never recovered from source material).
    state = _state_with_leader(skills=_skills_with(Ability.MELEE, skill=4, aptitude=9))
    state.leaders[1].experience_credit = 95

    result = execute_practice(state, leader_id=1, ability=Ability.MELEE, rng=ScriptedRandom([0.01]))

    assert result.skill_rose is True
    assert result.new_skill == 5
    assert result.advanced_ability_granted is None
    assert state.leaders[1].advanced_abilities == set()


def test_execute_practice_grants_nothing_for_an_aptitude_only_rise():
    # current_skill=5 (already a valid schedule level, proving the guard
    # is skill_rose itself, not "new_skill isn't a valid level"), aptitude
    # =0 -> deficit 6, gate fails (0.99); APT_RISE_CHANCE[5]==0.80 succeeds
    # (0.5). new_skill stays 5 -- an aptitude-only rise never touches spabord.
    state = _state_with_leader(skills=_skills_with(Ability.WHITE, skill=5, aptitude=0))

    result = execute_practice(state, leader_id=1, ability=Ability.WHITE, rng=ScriptedRandom([0.99, 0.5]))

    assert result.skill_rose is False
    assert result.aptitude_rose is True
    assert result.new_skill == 5
    assert result.advanced_ability_granted is None
    assert state.leaders[1].advanced_abilities == set()


def test_execute_practice_group_grants_advanced_ability_on_an_immediate_rise():
    # Leader 1 (skill 4, the group's minimum, tied-loser role) gets an
    # immediate rise to 5 because leader 2 has strictly higher skill --
    # the immediate-rise branch also has to reach the new grant helper,
    # not just the credit-accumulation branch covered by the solo test above.
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.WHITE, skill=4, aptitude=9),
            2: _skills_with(Ability.WHITE, skill=6, aptitude=9),
        },
    )

    expected = build_magic_ability_level_schedule(state.game_number)[Ability.WHITE].get(5)

    results = execute_practice_group(state, [1, 2], Ability.WHITE, rng=ScriptedRandom([0.01]))

    assert results[0].skill_rose is True
    assert results[0].new_skill == 5
    assert results[0].advanced_ability_granted is expected
    if expected is not None:
        assert expected in state.leaders[1].advanced_abilities
    assert results[1].skill_rose is False
    assert results[1].advanced_ability_granted is None


def test_execute_practice_group_comatose_leader_never_reaches_the_grant_helper():
    # Leader 1 is both the group's minimum skill (so resolve_practice_
    # group() still computes -- and consumes one gate roll for -- its own
    # would-be immediate rise) and comatose: execute_practice_group()'s
    # own Phase 310 short-circuit discards that computed outcome before
    # ever writing it back or reaching _maybe_grant_advanced_ability, so
    # leader 1 ends up with no Advanced Ability despite the group-level
    # computation having produced a skill-rise outcome for it.
    state = _state_with_leaders(
        1,
        2,
        skills_by_id={
            1: _skills_with(Ability.WHITE, skill=4, aptitude=9),
            2: _skills_with(Ability.WHITE, skill=6, aptitude=9),
        },
    )
    state.leaders[1].is_comatose = True

    results = execute_practice_group(state, [1, 2], Ability.WHITE, rng=ScriptedRandom([0.01]))

    assert results[0].advanced_ability_granted is None
    assert state.leaders[1].advanced_abilities == set()
