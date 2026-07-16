from __future__ import annotations

import pytest

from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_BASE_HIT_CHANCE,
    FIRE_ARROW_HIT_CHANCE_PER_LEVEL,
    HOLY_SYMBOL_HIT_CHANCE_REDUCTION_PER_LEVEL,
    HOLY_SYMBOL_UNDEAD_DAMAGE_RANGE_PER_LEVEL,
    HOLY_SYMBOL_UNDEAD_HIT_CHANCE_REDUCTION_PER_LEVEL,
    MELEE_HIT_CHANCE,
    NEUTRAL_DUELIST_BONUS,
    PERSONAL_COMBAT_SPELL_LEVEL_CAP,
    SPELL_DISRUPTION_CHANCE_CAP,
    SPELL_DISRUPTION_CHANCE_PER_HIT,
    CHARM_FLEE_ALWAYS_SUCCEEDS,
    PSYCHIC_BLAST_STUN_ROUNDS_RANGE,
    SPIRITWRACK_ANIMAL_INTELLIGENCE_DAMAGE_RATE_MULTIPLIER,
    SPIRITWRACK_MELEE_DAMAGE_REDUCTION_PER_LEVEL,
    TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE,
    TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE,
    Combatant,
    CombatRange,
    _acts_first,
    effective_archery_skill,
    effective_melee_skill,
    fire_arrow_free_attacks,
    fire_arrow_hit_chance,
    holy_symbol_hit_chance,
    resolve_fire_arrow_duel,
    resolve_melee_duel,
    resolve_spell_disruption,
    roll_fire_arrow_attack,
    roll_holy_symbol_undead_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spell_disruption_chance,
    spiritwrack_blocks_cast_and_archery,
    spiritwrack_melee_damage_reduction,
)

from _helpers import ScriptedRandom


def test_combatant_defaults_to_character_hit_points():
    assert Combatant("A").hit_points == CHARACTER_HIT_POINTS == 10


def test_effective_skills_add_neutral_duelist_bonus():
    plain = Combatant("A", melee_skill=2, archery_skill=1)
    neutral = Combatant("B", melee_skill=2, archery_skill=1, neutral_duelist_bonus=True)

    assert effective_melee_skill(plain) == 2
    assert effective_melee_skill(neutral) == 2 + NEUTRAL_DUELIST_BONUS
    assert effective_archery_skill(plain) == 1
    assert effective_archery_skill(neutral) == 1 + NEUTRAL_DUELIST_BONUS


def test_fire_arrow_hit_chance_matches_formula():
    assert fire_arrow_hit_chance(0) == pytest.approx(FIRE_ARROW_BASE_HIT_CHANCE)
    assert fire_arrow_hit_chance(3) == pytest.approx(FIRE_ARROW_BASE_HIT_CHANCE + 3 * FIRE_ARROW_HIT_CHANCE_PER_LEVEL)


def test_fire_arrow_free_attacks_equals_archery_skill():
    assert fire_arrow_free_attacks(0) == 0
    assert fire_arrow_free_attacks(4) == 4


def test_roll_melee_attack_hit_returns_damage_in_range():
    rng = ScriptedRandom([0.49, 0.5])  # under 50% -> hit, then the damage roll
    damage = roll_melee_attack(rng)
    assert 1 <= damage <= 6


def test_roll_melee_attack_miss_returns_zero():
    rng = ScriptedRandom([0.5])  # exactly at the 50% boundary -> miss (strict <)
    assert roll_melee_attack(rng) == 0


def test_roll_fire_arrow_attack_hit_returns_damage_in_range():
    rng = ScriptedRandom([0.29, 0.5])  # under the level-0 30% chance -> hit
    damage = roll_fire_arrow_attack(0, rng)
    assert 1 <= damage <= 6


def test_roll_fire_arrow_attack_miss_returns_zero():
    rng = ScriptedRandom([0.3])  # exactly at the level-0 30% boundary -> miss
    assert roll_fire_arrow_attack(0, rng) == 0


def test_acts_first_higher_skill_wins_without_consuming_rng():
    rng = ScriptedRandom([])  # any .random() call here raises IndexError
    assert _acts_first(3, 1, rng) is True
    assert _acts_first(1, 3, rng) is False


def test_acts_first_tied_skill_breaks_randomly():
    assert _acts_first(2, 2, ScriptedRandom([0.1])) is True
    assert _acts_first(2, 2, ScriptedRandom([0.9])) is False


def test_resolve_melee_duel_decisive_winner_leaves_the_other_undamaged():
    # A(melee_skill=1) always acts first (no initiative roll needed);
    # scripted so A always hits and B always misses, so B dies without
    # ever landing a blow on A.
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=10)
    block = [0.1, 0.5, 0.9]  # A hits (chance + damage roll), B misses
    rng = ScriptedRandom(block * 15)  # generously more than enough rounds

    result = resolve_melee_duel(a, b, rng)

    assert result.winner == "a"
    assert a.hit_points == 10
    assert b.hit_points <= 0


def test_resolve_melee_duel_respects_max_rounds_cap_when_nobody_lands_a_hit():
    a = Combatant("A", hit_points=10)
    b = Combatant("B", hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # both always miss

    result = resolve_melee_duel(a, b, rng, max_rounds=2)

    assert result.winner is None
    assert result.rounds == 2
    assert a.hit_points == 10
    assert b.hit_points == 10


def test_resolve_fire_arrow_duel_decisive_winner():
    # A has real Archery skill (some shots); B has none (0 free attacks,
    # never fires at all) and starts at 1 hit point, so A's very first
    # (scripted) hit is lethal regardless of its exact 1-6 magnitude.
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # A's shot: hit-chance roll, then damage roll

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner == "a"
    assert a.hit_points == 10
    assert b.hit_points <= 0


def test_resolve_fire_arrow_duel_no_kill_when_free_attacks_run_out():
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # every shot misses

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner is None
    assert result.rounds == 2  # max(free_attacks(2), free_attacks(1))
    assert a.hit_points == 10
    assert b.hit_points == 10


# -- Phase 175: per-shot Fire Arrow log --


def test_resolve_fire_arrow_duel_logs_every_shot_fired():
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # A's one and only shot: hit-chance roll, then damage roll

    result = resolve_fire_arrow_duel(a, b, rng)

    assert len(result.shots) == 1
    assert result.shots[0].shooter == "a"
    assert result.shots[0].hit is True
    assert 1 <= result.shots[0].damage <= 6


def test_resolve_fire_arrow_duel_logs_a_miss_as_zero_damage():
    a = Combatant("A", archery_skill=1, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # every shot misses

    result = resolve_fire_arrow_duel(a, b, rng)

    assert len(result.shots) == 2  # one shot each (fire_arrow_free_attacks(1) == 1)
    assert {shot.shooter for shot in result.shots} == {"a", "b"}
    assert all(shot.hit is False and shot.damage == 0 for shot in result.shots)


def test_resolve_fire_arrow_duel_shots_are_recorded_in_firing_order():
    # A(skill=2) always acts first (no initiative roll needed, higher skill
    # wins outright per _acts_first) and gets 2 free attacks vs B's 1, so
    # the log should read a, b, a.
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # every shot misses -- nobody dies mid-log

    result = resolve_fire_arrow_duel(a, b, rng)

    assert [shot.shooter for shot in result.shots] == ["a", "b", "a"]


def test_resolve_melee_duel_never_logs_shots():
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=10)
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = resolve_melee_duel(a, b, rng)

    assert result.shots == ()


# -- Phase 132: monster-specific melee damage range --


def test_combatant_defaults_melee_damage_range_to_the_character_rule():
    assert Combatant("A").melee_damage_range == (1, 6)


def test_roll_melee_attack_uses_the_supplied_damage_range():
    rng = ScriptedRandom([0.1, 0.5])  # under 50% -> hit, then the damage roll
    damage = roll_melee_attack(rng, damage_range=(1, 7))
    assert 1 <= damage <= 7


def test_resolve_melee_duel_uses_each_combatants_own_melee_damage_range():
    # A monster combatant (Giant-style 1-7 die) always acts first
    # (higher melee_skill) and always hits; the character combatant
    # starts at 1 hit point, so any positive damage from the monster's
    # own 1-7 die is lethal regardless of its exact magnitude.
    monster = Combatant("Giant", melee_skill=1, hit_points=25, melee_damage_range=(1, 7))
    character = Combatant("Hero", melee_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # monster: hit-chance roll, then damage roll

    result = resolve_melee_duel(monster, character, rng)

    assert result.winner == "a"
    assert character.hit_points <= 0


# -- Phase 170: monster-specific missile damage range --


def test_combatant_defaults_missile_damage_range_to_the_character_rule():
    assert Combatant("A").missile_damage_range == (1, 6)


def test_roll_fire_arrow_attack_uses_the_supplied_damage_range():
    rng = ScriptedRandom([0.1, 0.5])  # under the hit chance -> hit, then the damage roll
    damage = roll_fire_arrow_attack(0, rng, damage_range=(3, 9))
    assert 3 <= damage <= 9


def test_resolve_fire_arrow_duel_uses_each_combatants_own_missile_damage_range():
    # A monster combatant (Archer-style 3-9 die, skill 1 -> 1 free attack)
    # always acts first (higher archery_skill) and always hits; the
    # character combatant starts at 1 hit point, so any positive damage
    # from the monster's own 3-9 die is lethal regardless of magnitude.
    monster = Combatant("Archer", archery_skill=1, hit_points=12, missile_damage_range=(3, 9))
    character = Combatant("Hero", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # monster: hit-chance roll, then damage roll

    result = resolve_fire_arrow_duel(monster, character, rng)

    assert result.winner == "a"
    assert character.hit_points <= 0


def test_resolve_fire_arrow_duel_higher_skill_keeps_firing_solo_after_the_other_runs_out():
    # A(skill 2) gets 2 shots, B(skill 0) gets 0 -- B never fires at all,
    # so only A's shots can matter; confirmed via a miss-then-hit script
    # that still ends the fight (round 2's hit kills B at 1 hp).
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.99, 0.1, 0.5])  # round 1: A misses; round 2: A hits (+damage)

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner == "a"
    assert result.rounds == 2
    assert b.hit_points <= 0


# -- Phase 155: Troll-style end-of-round regeneration --


def test_combatant_defaults_regenerates_hp_to_zero():
    assert Combatant("A").regenerates_hp == 0


def test_resolve_melee_duel_regenerates_hp_after_a_surviving_round():
    a = Combatant("A", hit_points=10)
    b = Combatant("B", hit_points=10, regenerates_hp=1)
    rng = ScriptedRandom([0.99] * 10)  # both always miss

    result = resolve_melee_duel(a, b, rng, max_rounds=1)

    assert result.winner is None
    assert a.hit_points == 10
    assert b.hit_points == 11


def test_resolve_melee_duel_does_not_regenerate_a_combatant_killed_that_round():
    a = Combatant("A", hit_points=10, melee_skill=1)
    b = Combatant("B", hit_points=1, regenerates_hp=5)
    rng = ScriptedRandom([0.1, 0.5])  # A hits (chance + damage roll), kills B outright

    result = resolve_melee_duel(a, b, rng)

    assert result.winner == "a"
    assert b.hit_points <= 0


def test_resolve_fire_arrow_duel_regenerates_hp_after_a_surviving_round():
    a = Combatant("A", archery_skill=1, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10, regenerates_hp=1)
    rng = ScriptedRandom([0.5, 0.99, 0.99])  # tie-break, then both shots miss

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner is None
    assert a.hit_points == 10
    assert b.hit_points == 11


# -- Phase 179: the three combat ranges + spell disruption --


def test_combat_range_is_ordered_farthest_to_closest():
    assert CombatRange.SPELL_RANGE.value == 0
    assert CombatRange.BOW_RANGE.value == 1
    assert CombatRange.MELEE_RANGE.value == 2


def test_spell_disruption_chance_matches_the_formula():
    assert spell_disruption_chance(0) == 0.0
    assert spell_disruption_chance(1) == pytest.approx(SPELL_DISRUPTION_CHANCE_PER_HIT)
    assert spell_disruption_chance(2) == pytest.approx(2 * SPELL_DISRUPTION_CHANCE_PER_HIT)
    assert spell_disruption_chance(3) == pytest.approx(3 * SPELL_DISRUPTION_CHANCE_PER_HIT)


def test_spell_disruption_chance_caps_at_95_percent():
    # 4 hits = 80%, not yet capped; 5 hits would be 100% uncapped, so
    # that's the first value the 95% cap actually clips.
    assert spell_disruption_chance(4) == pytest.approx(4 * SPELL_DISRUPTION_CHANCE_PER_HIT)
    assert spell_disruption_chance(5) == pytest.approx(SPELL_DISRUPTION_CHANCE_CAP)
    assert spell_disruption_chance(100) == pytest.approx(SPELL_DISRUPTION_CHANCE_CAP)


def test_resolve_spell_disruption_zero_hits_never_consumes_a_roll():
    # Matches the worked example's own implicit case: a caster who took
    # no hits this round always gets to attempt the cast.
    rng = ScriptedRandom([])
    assert resolve_spell_disruption(0, rng) is False


def test_resolve_spell_disruption_one_hit_matches_the_worked_example():
    # Ablamor's own cast attempt was disrupted after exactly one landed
    # hit (Marzials's own 8-point Melee attack) earlier the same round --
    # a 20% chance, so 0.19 disrupts and 0.20 doesn't.
    assert resolve_spell_disruption(1, ScriptedRandom([0.19])) is True
    assert resolve_spell_disruption(1, ScriptedRandom([0.20])) is False


def test_resolve_spell_disruption_consumes_exactly_one_roll_when_hits_taken():
    rng = ScriptedRandom([0.99])  # a second .random() call would raise IndexError
    resolve_spell_disruption(2, rng)


# -- Phase 180: Holy Symbol [HO] --


def test_holy_symbol_hit_chance_matches_the_worked_example():
    # Level 1 against a 50% base chance -> reduced by 5% (10% of 50%).
    assert holy_symbol_hit_chance(0.50, 1) == pytest.approx(0.45)


def test_holy_symbol_hit_chance_scales_with_skill_level():
    assert holy_symbol_hit_chance(0.50, 2) == pytest.approx(0.50 * (1 - 2 * HOLY_SYMBOL_HIT_CHANCE_REDUCTION_PER_LEVEL))
    assert holy_symbol_hit_chance(0.50, 0) == pytest.approx(0.50)


def test_holy_symbol_hit_chance_undead_or_anti_holy_uses_the_20_percent_rate():
    # Same level-1-vs-50% worked example, but against an Undead/Anti-Holy
    # target the reduction rate doubles to 20% per level -> 40%, not 45%.
    assert holy_symbol_hit_chance(0.50, 1, target_is_undead_or_anti_holy=True) == pytest.approx(0.40)


def test_holy_symbol_hit_chance_caps_skill_level_at_4():
    # Phase 181: "come tutti quelli di combattimento ha il CAP al
    # livello 4" -- WH 5 (or higher) has exactly the same effect as
    # WH 4, the confirmed cap on every Personal-Combat spell.
    assert PERSONAL_COMBAT_SPELL_LEVEL_CAP == 4
    at_cap = holy_symbol_hit_chance(0.50, 4, target_is_undead_or_anti_holy=True)
    assert holy_symbol_hit_chance(0.50, 5, target_is_undead_or_anti_holy=True) == pytest.approx(at_cap)
    assert holy_symbol_hit_chance(0.50, 100, target_is_undead_or_anti_holy=True) == pytest.approx(at_cap)


def test_holy_symbol_hit_chance_stays_nonnegative_at_the_capped_maximum_reduction():
    # 4 levels * 20%/level = 80% reduction -- the largest possible
    # reduction now that levels beyond the cap no longer count -- still
    # leaves a positive floor rather than reaching (or crossing) zero.
    assert holy_symbol_hit_chance(0.50, 100, target_is_undead_or_anti_holy=True) == pytest.approx(0.10)


def test_roll_holy_symbol_undead_damage_level_zero_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert roll_holy_symbol_undead_damage(0, rng) == 0


def test_roll_holy_symbol_undead_damage_caps_skill_level_at_4():
    # WH 5 (or higher) rolls exactly 4 dice, not 5 -- verified by
    # counting the underlying random() draws.
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0])
    call_count = 0
    real_random = rng.random

    def counting_random():
        nonlocal call_count
        call_count += 1
        return real_random()

    rng.random = counting_random
    damage = roll_holy_symbol_undead_damage(5, rng)
    assert call_count == 4
    assert 4 <= damage <= 16


def test_roll_holy_symbol_undead_damage_range_at_level_1():
    # ScriptedRandom overrides random() but not getrandbits(), so
    # rng.randint() itself draws from the scripted queue via
    # _randbelow_without_getrandbits (one random() draw per randint()
    # call for a 4-wide range, since 4 evenly divides the float
    # resolution) -- same mechanism the file's pre-existing
    # roll_melee_attack tests already rely on.
    rng = ScriptedRandom([0.0])
    damage = roll_holy_symbol_undead_damage(1, rng)
    assert 1 <= damage <= 4


def test_roll_holy_symbol_undead_damage_sums_one_independent_roll_per_level():
    # Level 2 -> two separate 1-4 rolls, summed (confirmed range 2-8),
    # not a single roll scaled or multiplied by level -- verified by
    # counting how many times the underlying random() draw is consumed.
    rng = ScriptedRandom([0.0, 0.5])
    call_count = 0
    real_random = rng.random

    def counting_random():
        nonlocal call_count
        call_count += 1
        return real_random()

    rng.random = counting_random
    damage = roll_holy_symbol_undead_damage(2, rng)
    assert call_count == 2
    assert 2 <= damage <= 8


def test_roll_holy_symbol_undead_damage_range_is_1_to_4_per_level():
    assert HOLY_SYMBOL_UNDEAD_DAMAGE_RANGE_PER_LEVEL == (1, 4)


# -- Phase 182: Spiritwrack [SP] --


def test_spiritwrack_blocks_cast_and_archery_by_default():
    assert spiritwrack_blocks_cast_and_archery() is True


def test_spiritwrack_blocks_cast_and_archery_never_applies_to_an_immune_target():
    assert spiritwrack_blocks_cast_and_archery(target_is_immune=True) is False


def test_spiritwrack_melee_damage_reduction_immune_target_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(4, rng, target_is_immune=True) == 0
    # Immune wins even if the target is also flagged Animal-Intelligence.
    assert spiritwrack_melee_damage_reduction(4, rng, target_is_immune=True, target_is_animal_intelligence=True) == 0


def test_spiritwrack_melee_damage_reduction_level_zero_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(0, rng) == 0


def test_spiritwrack_melee_damage_reduction_level_2_is_a_whole_point_no_roll_needed():
    # 0.5 * 2 = 1.0 exactly -- no fractional part, no roll consumed.
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(2, rng) == 1


def test_spiritwrack_melee_damage_reduction_level_1_rounds_randomly():
    # 0.5 * 1 = 0.5 -- rounds up to 1 half the time, down to 0 the rest.
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.49])) == 1
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.5])) == 0


def test_spiritwrack_melee_damage_reduction_level_3_rounds_randomly_around_its_own_whole_part():
    # 0.5 * 3 = 1.5 -- rounds up to 2 half the time, down to 1 the rest.
    assert spiritwrack_melee_damage_reduction(3, ScriptedRandom([0.49])) == 2
    assert spiritwrack_melee_damage_reduction(3, ScriptedRandom([0.5])) == 1


def test_spiritwrack_melee_damage_reduction_caps_skill_level_at_4():
    # 0.5 * 4 = 2.0 exactly -- level 5 (or higher) must match level 4
    # exactly, and also needs no roll since the capped exact value has
    # no fractional part.
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(4, rng) == 2
    assert spiritwrack_melee_damage_reduction(5, rng) == 2
    assert spiritwrack_melee_damage_reduction(100, rng) == 2


def test_spiritwrack_melee_damage_reduction_animal_intelligence_halves_the_rate():
    # 0.25 * 1 = 0.25 -- rounds up to 1 a quarter of the time.
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.24]), target_is_animal_intelligence=True) == 1
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.25]), target_is_animal_intelligence=True) == 0


def test_spiritwrack_melee_damage_reduction_animal_intelligence_at_capped_level_is_a_whole_point_no_roll():
    # 0.25 * 4 (capped) = 1.0 exactly -- no fractional part, no roll.
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(4, rng, target_is_animal_intelligence=True) == 1


def test_spiritwrack_rate_constants():
    assert SPIRITWRACK_MELEE_DAMAGE_REDUCTION_PER_LEVEL == 0.5
    assert SPIRITWRACK_ANIMAL_INTELLIGENCE_DAMAGE_RATE_MULTIPLIER == 0.5


# -- Phase 183: Charm [CH]'s Personal-Combat effect --


def test_charm_flee_always_succeeds_constant():
    # "Praticamente se usato in combattimento equivale a un comando FL
    # che riesce sempre" -- no roll, no skill-level scaling at all.
    assert CHARM_FLEE_ALWAYS_SUCCEEDS is True


# -- Phase 184: Psychic Blast [PS] --


def test_psychic_blast_stun_rounds_range_constant():
    assert PSYCHIC_BLAST_STUN_ROUNDS_RANGE == (2, 5)


def test_roll_psychic_blast_stun_rounds_stays_within_range():
    for scripted in (0.0, 0.25, 0.5, 0.75, 0.999):
        rounds = roll_psychic_blast_stun_rounds(ScriptedRandom([scripted]))
        assert 2 <= rounds <= 5


def test_roll_psychic_blast_stun_rounds_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    roll_psychic_blast_stun_rounds(rng)


# -- Phase 185: Telekinetic Storm [TE] --


def test_telekinetic_storm_victim_damage_range_constant():
    assert TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE == (4, 16)


def test_telekinetic_storm_caster_damage_range_by_combat_range_constant():
    assert TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE == {
        CombatRange.MELEE_RANGE: (4, 16),
        CombatRange.BOW_RANGE: (2, 8),
        CombatRange.SPELL_RANGE: (1, 4),
    }


def test_roll_telekinetic_storm_victim_damage_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_victim_damage(ScriptedRandom([scripted]))
        assert 4 <= damage <= 16


def test_roll_telekinetic_storm_victim_damage_immune_target_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert roll_telekinetic_storm_victim_damage(rng, target_is_immune=True) == 0


def test_roll_telekinetic_storm_caster_damage_at_melee_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_caster_damage(CombatRange.MELEE_RANGE, ScriptedRandom([scripted]))
        assert 4 <= damage <= 16


def test_roll_telekinetic_storm_caster_damage_at_bow_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_caster_damage(CombatRange.BOW_RANGE, ScriptedRandom([scripted]))
        assert 2 <= damage <= 8


def test_roll_telekinetic_storm_caster_damage_at_spell_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_caster_damage(CombatRange.SPELL_RANGE, ScriptedRandom([scripted]))
        assert 1 <= damage <= 4


def test_roll_telekinetic_storm_caster_damage_immune_target_returns_zero_without_a_roll():
    # Immune (submarine) means the storm never manifests, so the
    # caster takes no self-damage either -- unlike Spiritwrack's own
    # immunity, which only ever affected the target's side.
    rng = ScriptedRandom([])
    assert roll_telekinetic_storm_caster_damage(CombatRange.MELEE_RANGE, rng, target_is_immune=True) == 0
