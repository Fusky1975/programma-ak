"""Varied Special Encounter Plans for the intelligent monsters (models/monster_encounter_plan.py)."""

from __future__ import annotations

import random

import pytest

from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.monster import MONSTER_MAGIC_ABILITIES, MONSTER_RUNTIME_PROFILE, Monster, MonsterIntelligence
from ak_engine.models.monster_encounter_plan import (
    GENERATED_PLAN_CHANCE,
    MONSTER_ENCOUNTER_PLANS,
    _SPELL_SCHOOL,
    generate_monster_encounter_plan,
    monster_gets_generated_plans,
    roll_monster_encounter_plan,
)
from ak_engine.models.temper import Temper

ELIGIBLE = [m for m in MONSTER_RUNTIME_PROFILE if monster_gets_generated_plans(m)]


def _casts(plan):
    return [Spell(t.sub_object) for t in plan if t.maneuver is Maneuver.CAST]


def test_only_intelligent_monsters_get_varied_plans():
    assert ELIGIBLE  # something to vary
    for monster in ELIGIBLE:
        assert MONSTER_RUNTIME_PROFILE[monster].intelligence in (
            MonsterIntelligence.MEDIUM, MonsterIntelligence.HIGH, MonsterIntelligence.GODLIKE
        )
    for animal_or_machine in (Monster.GI_SPIDER, Monster.GI_AMOEBA, Monster.GOLEM, Monster.GRYPHON, Monster.TROLL):
        assert not monster_gets_generated_plans(animal_or_machine)


@pytest.mark.parametrize("attacker_is_undead", [False, True])
def test_every_generated_plan_uses_only_what_the_monster_can_really_do(attacker_is_undead):
    for monster in ELIGIBLE:
        abilities = MONSTER_MAGIC_ABILITIES.get(monster, {})
        for seed in range(60):
            plan = generate_monster_encounter_plan(monster, random.Random(seed), attacker_is_undead=attacker_is_undead)
            casts = _casts(plan)
            assert len(casts) == len(set(casts))  # a spell at most once per encounter
            per_school: dict[Ability, int] = {}
            for spell in casts:
                if spell is Spell.CHARM:
                    school = Ability.PSYCHIC
                else:
                    school = _SPELL_SCHOOL[spell]
                per_school[school] = per_school.get(school, 0) + 1
                assert abilities.get(school, 0) >= 1, (monster, spell)
            for school, used in per_school.items():
                assert used <= (1 if abilities[school] <= 1 else 2), (monster, per_school)
            assert plan[-1].maneuver in (Maneuver.MELEE, Maneuver.FLEE)
            assert sum(1 for t in plan if t.maneuver is Maneuver.SHOOT) <= 1
            if attacker_is_undead:
                assert Spell.HAND_OF_DEATH not in casts  # useless against the undead
            else:
                assert Spell.CONTROL_UNDEAD not in casts
            if any(t.maneuver is Maneuver.FLEE for t in plan):
                assert MONSTER_RUNTIME_PROFILE[monster].temper in (Temper.CAUTIOUS, Temper.COWARDLY)
                assert [t.maneuver for t in plan[-3:]] == [Maneuver.MELEE, Maneuver.MELEE, Maneuver.FLEE]


def test_monsters_that_always_shoot_in_their_table_always_shoot_in_a_generated_plan():
    for seed in range(40):
        assert any(t.maneuver is Maneuver.SHOOT for t in generate_monster_encounter_plan(Monster.ARCHER, random.Random(seed)))


def test_an_undead_attacker_draws_control_undead_from_a_necromancer():
    plan = generate_monster_encounter_plan(Monster.LICH, random.Random(1), attacker_is_undead=True)
    assert _casts(plan)[0] is Spell.CONTROL_UNDEAD


def test_the_plans_of_a_great_caster_are_really_varied():
    plans = {
        tuple((t.maneuver, t.sub_object) for t in generate_monster_encounter_plan(Monster.TITAN, random.Random(seed)))
        for seed in range(300)
    }
    assert len(plans) >= 40


def test_without_a_variety_stream_the_tables_are_used_as_before():
    for seed in range(20):
        plan = roll_monster_encounter_plan(Monster.GR_DRAGON, random.Random(seed))
        assert plan in [v.tactics for v in MONSTER_ENCOUNTER_PLANS[Monster.GR_DRAGON].variants]


def test_with_a_variety_stream_an_intelligent_monster_often_gets_a_generated_plan():
    table_plans = [v.tactics for v in MONSTER_ENCOUNTER_PLANS[Monster.GR_DRAGON].variants]
    generated = 0
    for seed in range(200):
        plan = roll_monster_encounter_plan(Monster.GR_DRAGON, random.Random(seed), variety_rng=random.Random(seed))
        if plan not in table_plans:
            generated += 1
    assert 0.35 * 200 < generated  # roughly GENERATED_PLAN_CHANCE of the encounters, minus coincidences


def test_animals_and_machines_keep_their_plain_melee_plan_even_with_a_variety_stream():
    for monster in (Monster.GI_SPIDER, Monster.GOLEM):
        assert roll_monster_encounter_plan(monster, random.Random(1), variety_rng=random.Random(1)) == (
            MONSTER_ENCOUNTER_PLANS[monster].variants[0].tactics
        )


def test_the_variety_stream_leaves_the_encounters_own_dice_untouched():
    rng = random.Random(5)
    before = rng.getstate()
    roll_monster_encounter_plan(Monster.ARCHER, rng, variety_rng=random.Random(9))
    assert rng.getstate() == before


def test_the_generated_chance_is_the_documented_one():
    assert GENERATED_PLAN_CHANCE == 0.6
