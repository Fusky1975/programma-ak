from __future__ import annotations

from ak_engine.models.enums import Maneuver, Spell
from ak_engine.models.monster import Monster
from ak_engine.models.monster_encounter_plan import (
    MONSTER_ENCOUNTER_PLANS,
    MonsterEncounterPlan,
    MonsterEncounterPlanVariant,
    roll_monster_encounter_plan,
)
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom


def test_monster_encounter_plans_covers_every_real_species():
    all_real = {m for m in Monster if m is not Monster.NOMONSTER}
    assert set(MONSTER_ENCOUNTER_PLANS.keys()) == all_real


def test_monster_encounter_plans_nomonster_sentinel_has_no_entry():
    assert Monster.NOMONSTER not in MONSTER_ENCOUNTER_PLANS


def test_monster_encounter_plans_every_species_variants_sum_to_100_percent():
    for monster, plan in MONSTER_ENCOUNTER_PLANS.items():
        assert sum(v.percent for v in plan.variants) == 100, monster


def test_monster_encounter_plans_every_variant_ends_in_a_bare_melee_tactic():
    # "ME fino alla fine" is modeled as one trailing MELEE tactic -- see
    # the module's own docstring for why no special "repeat" marker
    # is needed (resolve_melee_duel already fights to the death).
    for monster, plan in MONSTER_ENCOUNTER_PLANS.items():
        for variant in plan.variants:
            assert variant.tactics[-1] == SearchTactic(maneuver=Maneuver.MELEE), monster
        if plan.undead_variant is not None:
            assert plan.undead_variant.tactics[-1] == SearchTactic(maneuver=Maneuver.MELEE), monster


def test_monster_encounter_plans_undead_override_species_are_exactly_the_four_confirmed():
    undead_species = {m for m, plan in MONSTER_ENCOUNTER_PLANS.items() if plan.undead_variant is not None}
    assert undead_species == {Monster.GO_DRAGON, Monster.TITAN, Monster.NEC_MAGE, Monster.WITCH}


def test_monster_encounter_plans_single_variant_sample():
    # Gryphon: "ME fino alla fine" -- no percentage in the source at all.
    plan = MONSTER_ENCOUNTER_PLANS[Monster.GRYPHON]
    assert plan == MonsterEncounterPlan(
        variants=(MonsterEncounterPlanVariant(tactics=(SearchTactic(maneuver=Maneuver.MELEE),), percent=100),)
    )


def test_monster_encounter_plans_shoot_then_melee_sample():
    # Giant: "FI, ME fino alla fine".
    plan = MONSTER_ENCOUNTER_PLANS[Monster.GIANT]
    assert plan.variants[0].tactics == (
        SearchTactic(maneuver=Maneuver.SHOOT),
        SearchTactic(maneuver=Maneuver.MELEE),
    )


def test_monster_encounter_plans_cast_then_melee_decodes_the_spell():
    # Renegade Necromancer: "CA-HA, ME fino alla fine" -- CA-HA = Hand of Death.
    plan = MONSTER_ENCOUNTER_PLANS[Monster.NEC_MAGE]
    assert plan.variants[0].tactics == (
        SearchTactic(maneuver=Maneuver.CAST, sub_object=int(Spell.HAND_OF_DEATH)),
        SearchTactic(maneuver=Maneuver.MELEE),
    )
    assert plan.undead_variant.tactics == (
        SearchTactic(maneuver=Maneuver.CAST, sub_object=int(Spell.CONTROL_UNDEAD)),
        SearchTactic(maneuver=Maneuver.MELEE),
    )


def test_monster_encounter_plans_dryad_preserves_five_discrete_melee_rounds():
    # Dryad's own 30%/30% variants read "CA-PS/CA-TE, ME, ME, ME, ME, ME,
    # CA-CH, ME fino alla fine" -- 5 explicit ME entries plus the final
    # trailing one, not collapsed into a single MELEE tactic.
    plan = MONSTER_ENCOUNTER_PLANS[Monster.DRYAD]
    second_variant = plan.variants[1]
    melee_count = sum(1 for t in second_variant.tactics if t.maneuver is Maneuver.MELEE)
    assert melee_count == 6  # 5 explicit rounds + 1 trailing "fino alla fine"
    assert second_variant.tactics[-2] == SearchTactic(maneuver=Maneuver.CAST, sub_object=int(Spell.CHARM))


def test_monster_encounter_plans_titan_ten_variants_all_ten_percent():
    plan = MONSTER_ENCOUNTER_PLANS[Monster.TITAN]
    assert len(plan.variants) == 10
    assert all(v.percent == 10 for v in plan.variants)
    assert plan.undead_variant is not None


# -- roll_monster_encounter_plan() --


def test_roll_monster_encounter_plan_returns_none_for_the_nomonster_sentinel():
    assert roll_monster_encounter_plan(Monster.NOMONSTER, ScriptedRandom([])) is None


def test_roll_monster_encounter_plan_single_variant_species_never_consumes_a_roll():
    rng = ScriptedRandom([])
    result = roll_monster_encounter_plan(Monster.GRYPHON, rng)
    assert result == (SearchTactic(maneuver=Maneuver.MELEE),)


def test_roll_monster_encounter_plan_undead_override_bypasses_the_normal_roll():
    # Renegade Necromancer's Undead override must win even with a roll
    # value that would otherwise land squarely in the normal 100% pool,
    # and it must not consume any roll either (checked before rolling).
    rng = ScriptedRandom([])
    result = roll_monster_encounter_plan(Monster.NEC_MAGE, rng, attacker_is_undead=True)
    assert result == (
        SearchTactic(maneuver=Maneuver.CAST, sub_object=int(Spell.CONTROL_UNDEAD)),
        SearchTactic(maneuver=Maneuver.MELEE),
    )


def test_roll_monster_encounter_plan_non_undead_species_ignores_the_undead_flag():
    # Gryphon has no undead_variant at all -- the flag must be a no-op.
    rng = ScriptedRandom([])
    result = roll_monster_encounter_plan(Monster.GRYPHON, rng, attacker_is_undead=True)
    assert result == (SearchTactic(maneuver=Maneuver.MELEE),)


def test_roll_monster_encounter_plan_two_variant_species_below_and_above_threshold():
    # Vampire: (60%) CA-TE, CA-PS, ME / (40%) CA-PS, ME.
    below = roll_monster_encounter_plan(Monster.VAMPIRE, ScriptedRandom([0.59]))
    assert below[0] == SearchTactic(maneuver=Maneuver.CAST, sub_object=int(Spell.TELEK_STORM))

    above = roll_monster_encounter_plan(Monster.VAMPIRE, ScriptedRandom([0.60]))
    assert above[0] == SearchTactic(maneuver=Maneuver.CAST, sub_object=int(Spell.PSYCHIC_BLAST))
    assert len(above) == 2


def test_roll_monster_encounter_plan_multi_variant_species_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.1])  # a second .random() call would raise IndexError
    roll_monster_encounter_plan(Monster.VAMPIRE, rng)
    assert rng._randoms == []  # and confirms it wasn't skipped either -- exactly one
