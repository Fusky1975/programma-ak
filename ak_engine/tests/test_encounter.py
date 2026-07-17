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
    CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE,
    CONTROL_UNDEAD_SUCCESS_NEUTRALIZES_TARGET,
    FIREBALL_DAMAGE_PER_LEVEL,
    FIREBALL_DAMAGE_RANGE,
    HAND_OF_DEATH_BASE_DAMAGE,
    HAND_OF_DEATH_BLOCKS_CASTER_MELEE_ATTACK,
    HAND_OF_DEATH_BLOCKS_CASTER_OTHER_CASTS,
    HAND_OF_DEATH_DAMAGE_PER_LEVEL,
    HAND_OF_DEATH_ENDS_WHEN_CASTER_IS_HIT,
    HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER,
    ICE_SUSPENSION_FLYING_BONUS_ROUNDS_RANGE,
    ICE_SUSPENSION_FLYING_CRASH_DAMAGE_RANGE,
    ICE_SUSPENSION_FREEZE_POINTS_PER_LEVEL,
    ICE_SUSPENSION_FREEZE_THRESHOLD_CAP,
    ICE_SUSPENSION_FROZEN_BONUS_ROUNDS,
    ICE_SUSPENSION_FROZEN_FLEE_ALWAYS_SUCCEEDS,
    ICE_SUSPENSION_SEIZES_UNCARRIED_MAGIC_ITEMS,
    INVISIBILITY_HIT_CHANCE_MULTIPLIER,
    INVISIBILITY_STEAL_ATTEMPT_BONUS,
    MIRROR_IMAGE_DISBELIEF_BASE_CHANCE,
    MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP,
    MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL,
    MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE,
    MIRROR_IMAGE_MASTER_DISBELIEF_BONUS,
    PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS,
    PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE,
    PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP,
    PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL,
    PSYCHIC_BLAST_STUN_ROUNDS_RANGE,
    SPIRITWRACK_ANIMAL_INTELLIGENCE_DAMAGE_RATE_MULTIPLIER,
    SPIRITWRACK_MELEE_DAMAGE_REDUCTION_PER_LEVEL,
    TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE,
    TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE,
    Combatant,
    CombatRange,
    MirrorImageIntelligenceTier,
    _acts_first,
    effective_archery_skill,
    effective_melee_skill,
    control_undead_failure_new_hit_points,
    fire_arrow_free_attacks,
    fire_arrow_hit_chance,
    hand_of_death_caster_melee_defense_skill,
    hand_of_death_victim_hit_chance,
    holy_symbol_hit_chance,
    ice_suspension_freeze_threshold,
    ice_suspension_is_frozen,
    ice_suspension_slowed_bonus_rounds,
    invisibility_reduced_hit_chance,
    mirror_image_disbelief_chance,
    personal_combat_spell_cast_chance,
    resolve_fire_arrow_duel,
    resolve_melee_duel,
    resolve_personal_combat_spell_cast,
    resolve_spell_disruption,
    roll_fire_arrow_attack,
    roll_holy_symbol_undead_damage,
    resolve_mirror_image_disbelief,
    roll_control_undead_failure_hp_increase,
    roll_fireball_damage,
    roll_hand_of_death_damage,
    roll_ice_suspension_flying_bonus_rounds,
    roll_ice_suspension_flying_crash_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spell_disruption_chance,
    spiritwrack_melee_damage_reduction,
    blocks_cast_and_archery,
    WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER,
    WORDS_OF_HEALING_HEALS_TO_FULL,
    resolve_words_of_healing_disruption,
    words_of_healing_disruption_chance,
    words_of_healing_heal,
    GATE_DEMON_REFUSAL_CHANCE,
    GATE_DEMON_WINNER_RETURNS_TO_ABYSS,
    GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE,
    GATE_DEMON_NULLIFIED_BY_SIMULTANEOUS_MIRROR_IMAGE_OR_GATE_DEMON,
    resolve_gate_demon_refusal,
    LAVA_POOL_ESCAPE_CHANCE,
    LAVA_POOL_KILLS_INSTANTLY,
    lava_pool_escape_chance,
    resolve_lava_pool_escape,
    MonsterSpeed,
    AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER,
    AUGUR_COMBAT_FREE_WHEN_CAST_FIRST,
    AUGUR_COMBAT_SHIRK_CHANCE,
    Temper,
    augur_combat_shirk_chance,
    resolve_augur_combat,
    resolve_augur_combat_shirk,
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


def test_blocks_cast_and_archery_by_default():
    assert blocks_cast_and_archery() is True


def test_blocks_cast_and_archery_never_applies_to_an_immune_target():
    assert blocks_cast_and_archery(target_is_immune=True) is False


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


# -- Phase 186: Invisibility [IN] --


def test_invisibility_hit_chance_multiplier_constant():
    assert INVISIBILITY_HIT_CHANCE_MULTIPLIER == 0.5


def test_invisibility_reduced_hit_chance_halves_the_base_chance():
    # "la probabilita' di essere colpiti con l'arco o nel corpo a
    # mischia viene dimezzata" -- applies equally to Fire Arrow's own
    # hit-chance formula and the flat Melee hit chance.
    assert invisibility_reduced_hit_chance(0.50) == pytest.approx(0.25)
    assert invisibility_reduced_hit_chance(fire_arrow_hit_chance(2)) == pytest.approx(fire_arrow_hit_chance(2) * 0.5)
    assert invisibility_reduced_hit_chance(MELEE_HIT_CHANCE) == pytest.approx(0.25)


def test_invisibility_steal_attempt_bonus_constant():
    # "vale come un modificatore di +15% al tentativo di furto" --
    # confirmed but not yet backed by any real Steal-success formula
    # anywhere in this project (module docstring's Phase 186 addendum).
    assert INVISIBILITY_STEAL_ATTEMPT_BONUS == 0.15


# -- Phase 187: Mirror-Image Phantasm (MI) --


def test_mirror_image_disbelief_base_chance_table():
    assert MIRROR_IMAGE_DISBELIEF_BASE_CHANCE == {
        MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN: 1.20,
        MirrorImageIntelligenceTier.HIGH_HUMAN: 1.00,
        MirrorImageIntelligenceTier.MEDIUM_HUMAN: 0.80,
        MirrorImageIntelligenceTier.LOW_HUMAN: 0.60,
        MirrorImageIntelligenceTier.ANIMAL: 0.40,
        MirrorImageIntelligenceTier.MECHANICAL: 0.20,
    }


def test_mirror_image_master_disbelief_base_chance_is_medium_plus_25_percent():
    # "a bonus of 25% above Medium intelligence" -- 80% + 25% = 105%.
    assert MIRROR_IMAGE_MASTER_DISBELIEF_BONUS == 0.25
    assert MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE == pytest.approx(1.05)


def test_mirror_image_disbelief_chance_subtracts_15_percent_per_level():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.HIGH_HUMAN]  # 100%
    assert mirror_image_disbelief_chance(base, 0) == pytest.approx(1.00)
    assert mirror_image_disbelief_chance(base, 1) == pytest.approx(0.85)
    assert mirror_image_disbelief_chance(base, 2) == pytest.approx(0.70)


def test_mirror_image_disbelief_chance_reduction_caps_at_60_percent():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]  # 120%
    # 15%*4 = 60% (the cap itself); 15%*5 = 75% would exceed it uncapped.
    assert mirror_image_disbelief_chance(base, 4) == pytest.approx(base - MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP)
    assert mirror_image_disbelief_chance(base, 5) == pytest.approx(base - MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP)
    assert MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL == 0.15
    assert MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP == 0.60


def test_mirror_image_disbelief_chance_clamps_to_0_and_100_percent():
    # Mechanical's own 20% base, fully reduced, floors at 0% rather
    # than going negative.
    low_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MECHANICAL]
    assert mirror_image_disbelief_chance(low_base, 10) == 0.0
    # Divine/Superhuman's own 120% base, unreduced, clamps to 100%.
    high_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]
    assert mirror_image_disbelief_chance(high_base, 0) == 1.0


def test_resolve_mirror_image_disbelief_zero_percent_never_consumes_a_roll():
    rng = ScriptedRandom([])
    low_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MECHANICAL]
    assert resolve_mirror_image_disbelief(low_base, 10, rng) is False


def test_resolve_mirror_image_disbelief_hundred_percent_never_consumes_a_roll():
    rng = ScriptedRandom([])
    high_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]
    assert resolve_mirror_image_disbelief(high_base, 0, rng) is True


def test_resolve_mirror_image_disbelief_consumes_exactly_one_roll_in_between():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MEDIUM_HUMAN]  # 80%
    rng = ScriptedRandom([0.79])  # a second .random() call would raise IndexError
    assert resolve_mirror_image_disbelief(base, 0, rng) is True
    rng = ScriptedRandom([0.80])
    assert resolve_mirror_image_disbelief(base, 0, rng) is False


# -- Phase 188: Fireball [FI] --


def test_fireball_damage_range_constant():
    assert FIREBALL_DAMAGE_RANGE == (1, 8)


def test_fireball_damage_per_level_constant():
    assert FIREBALL_DAMAGE_PER_LEVEL == 1


def test_roll_fireball_damage_stays_within_range_at_level_zero():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_fireball_damage(0, ScriptedRandom([scripted]))
        assert 1 <= damage <= 8


def test_roll_fireball_damage_adds_one_point_per_level():
    rng = ScriptedRandom([0.0])  # base roll pinned to the range floor: 1
    assert roll_fireball_damage(3, rng) == 1 + FIREBALL_DAMAGE_PER_LEVEL * 3


def test_roll_fireball_damage_caps_bonus_at_level_four():
    # "max 4" -- level 5 behaves exactly like level 4 (PERSONAL_COMBAT_SPELL_LEVEL_CAP).
    rng_level_4 = ScriptedRandom([0.0])
    rng_level_5 = ScriptedRandom([0.0])
    assert roll_fireball_damage(4, rng_level_4) == roll_fireball_damage(5, rng_level_5)
    assert PERSONAL_COMBAT_SPELL_LEVEL_CAP == 4


def test_roll_fireball_damage_immune_target_returns_zero_without_a_roll():
    # Immune (submarine monster) -- no roll consumed at all.
    rng = ScriptedRandom([])
    assert roll_fireball_damage(4, rng, target_is_immune=True) == 0


# -- Phase 189: Ice Suspension [IC] --


def test_ice_suspension_freeze_points_per_level_constant():
    assert ICE_SUSPENSION_FREEZE_POINTS_PER_LEVEL == 4


def test_ice_suspension_freeze_threshold_scales_with_level_up_to_the_cap():
    assert ice_suspension_freeze_threshold(1) == 4
    assert ice_suspension_freeze_threshold(2) == 8
    assert ice_suspension_freeze_threshold(3) == 12
    assert ice_suspension_freeze_threshold(4) == 16
    assert ice_suspension_freeze_threshold(5) == 16  # capped
    assert ICE_SUSPENSION_FREEZE_THRESHOLD_CAP == 16


def test_ice_suspension_is_frozen_true_at_or_below_threshold():
    assert ice_suspension_is_frozen(4, 1) is True  # exactly at threshold
    assert ice_suspension_is_frozen(3, 1) is True  # below threshold
    assert ice_suspension_is_frozen(5, 1) is False  # above threshold


def test_ice_suspension_frozen_flee_always_succeeds_constant():
    assert ICE_SUSPENSION_FROZEN_FLEE_ALWAYS_SUCCEEDS is True


def test_ice_suspension_frozen_bonus_rounds_constant():
    assert ICE_SUSPENSION_FROZEN_BONUS_ROUNDS == 3


def test_ice_suspension_seizes_uncarried_magic_items_constant():
    assert ICE_SUSPENSION_SEIZES_UNCARRIED_MAGIC_ITEMS is True


def test_ice_suspension_slowed_bonus_rounds_matches_the_user_supplied_example():
    # 16 HP remaining, caster skill level 1 -> 1 bonus round. Reverse-
    # engineered and confirmed via AskUserQuestion (see module docstring).
    assert ice_suspension_slowed_bonus_rounds(16, 1) == 1


def test_ice_suspension_slowed_bonus_rounds_stays_within_zero_to_three():
    # Just above the freeze threshold (16), the fraction approaches but
    # never reaches 1, so floor(4*16/17) = 3 is the practical ceiling.
    assert ice_suspension_slowed_bonus_rounds(17, 4) == 3
    # A victim with far more HP than the threshold yields 0 (no bonus).
    assert ice_suspension_slowed_bonus_rounds(1000, 1) == 0


def test_ice_suspension_flying_crash_damage_range_constant():
    assert ICE_SUSPENSION_FLYING_CRASH_DAMAGE_RANGE == (5, 10)


def test_ice_suspension_flying_bonus_rounds_range_constant():
    assert ICE_SUSPENSION_FLYING_BONUS_ROUNDS_RANGE == (1, 3)


def test_roll_ice_suspension_flying_crash_damage_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_ice_suspension_flying_crash_damage(ScriptedRandom([scripted]))
        assert 5 <= damage <= 10


def test_roll_ice_suspension_flying_bonus_rounds_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        rounds = roll_ice_suspension_flying_bonus_rounds(ScriptedRandom([scripted]))
        assert 1 <= rounds <= 3


# -- Phase 190: Hand of Death [HA] --


def test_hand_of_death_caster_constraint_constants():
    assert HAND_OF_DEATH_BLOCKS_CASTER_OTHER_CASTS is True
    assert HAND_OF_DEATH_BLOCKS_CASTER_MELEE_ATTACK is True
    assert HAND_OF_DEATH_ENDS_WHEN_CASTER_IS_HIT is True


def test_hand_of_death_caster_melee_defense_skill_substitutes_necromancy_for_melee():
    assert hand_of_death_caster_melee_defense_skill(3) == 3
    assert hand_of_death_caster_melee_defense_skill(0) == 0


def test_hand_of_death_damage_constants():
    assert HAND_OF_DEATH_BASE_DAMAGE == 1
    assert HAND_OF_DEATH_DAMAGE_PER_LEVEL == 0.5


def test_roll_hand_of_death_damage_whole_exact_value_never_consumes_a_roll():
    # Level 2: 1 + 0.5*2 = 2, a whole number -- no coin-flip roll needed.
    rng = ScriptedRandom([])
    assert roll_hand_of_death_damage(2, rng) == 2


def test_roll_hand_of_death_damage_fractional_value_is_a_coin_flip():
    # Level 1: 1 + 0.5*1 = 1.5 -- rounds down to 1 or up to 2.
    rng_low = ScriptedRandom([0.49])
    assert roll_hand_of_death_damage(1, rng_low) == 2
    rng_high = ScriptedRandom([0.50])
    assert roll_hand_of_death_damage(1, rng_high) == 1


def test_roll_hand_of_death_damage_immune_target_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert roll_hand_of_death_damage(4, rng, target_is_immune=True) == 0


def test_hand_of_death_victim_hit_chance_multiplier_constant():
    assert HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER == 0.5


def test_hand_of_death_victim_hit_chance_halves_the_base_chance():
    assert hand_of_death_victim_hit_chance(0.6) == pytest.approx(0.3)


def test_hand_of_death_victim_hit_chance_immune_target_is_unaffected():
    assert hand_of_death_victim_hit_chance(0.6, target_is_immune=True) == 0.6


def test_blocks_cast_and_archery_shared_with_spiritwrack():
    # Renamed from spiritwrack_blocks_cast_and_archery in Phase 190,
    # confirmed to be Hand of Death's own victim effect too.
    assert blocks_cast_and_archery() is True
    assert blocks_cast_and_archery(target_is_immune=True) is False


# -- Phase 191: Control Undead [CO] --


def test_control_undead_success_neutralizes_target_constant():
    assert CONTROL_UNDEAD_SUCCESS_NEUTRALIZES_TARGET is True


def test_control_undead_failure_hp_increase_range_constant():
    assert CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE == (0.50, 1.00)


def test_roll_control_undead_failure_hp_increase_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        increase = roll_control_undead_failure_hp_increase(ScriptedRandom([scripted]))
        assert 0.50 <= increase <= 1.00


def test_roll_control_undead_failure_hp_increase_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    roll_control_undead_failure_hp_increase(rng)


def test_control_undead_failure_new_hit_points_at_the_low_end_of_the_range():
    # 10 HP, +50% -> 15.
    rng = ScriptedRandom([0.0])
    assert control_undead_failure_new_hit_points(10, rng) == 15


def test_control_undead_failure_new_hit_points_at_the_high_end_of_the_range():
    # 10 HP, +100% -> 20. uniform() never returns exactly b, so pin very
    # close to it instead.
    rng = ScriptedRandom([0.999999999])
    assert control_undead_failure_new_hit_points(10, rng) == 20


# -- Phase 192: general Personal-Combat spell cast success formula --


def test_personal_combat_spell_cast_chance_constants():
    assert PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE == 0.30
    assert PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL == 0.15
    assert PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP == 0.95
    assert PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS == 0.10


def test_personal_combat_spell_cast_chance_scales_with_level():
    assert personal_combat_spell_cast_chance(0) == pytest.approx(0.30)
    assert personal_combat_spell_cast_chance(1) == pytest.approx(0.45)
    assert personal_combat_spell_cast_chance(2) == pytest.approx(0.60)


def test_personal_combat_spell_cast_chance_caps_at_95_percent():
    # Level 5: 30% + 15%*5 = 105%, uncapped -- clamped to 95%.
    assert personal_combat_spell_cast_chance(5) == pytest.approx(0.95)


def test_personal_combat_spell_cast_chance_pagan_bonus():
    assert personal_combat_spell_cast_chance(1, caster_is_pagan=True) == pytest.approx(0.55)


def test_personal_combat_spell_cast_chance_pagan_bonus_still_capped():
    # 30% + 15%*4 = 90%, +10% Pagan = 100%, clamped to 95%.
    assert personal_combat_spell_cast_chance(4, caster_is_pagan=True) == pytest.approx(0.95)


def test_resolve_personal_combat_spell_cast_succeeds_under_the_chance():
    rng = ScriptedRandom([0.44])  # level 1 -> 45% chance
    assert resolve_personal_combat_spell_cast(1, rng) is True


def test_resolve_personal_combat_spell_cast_fails_over_the_chance():
    rng = ScriptedRandom([0.99])
    assert resolve_personal_combat_spell_cast(1, rng) is False


# -- Phase 200: Words of Healing [WH] --


def test_words_of_healing_constants():
    assert WORDS_OF_HEALING_HEALS_TO_FULL is True
    assert WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER == 0.5


def test_words_of_healing_disruption_chance_is_half_the_normal_rate():
    assert words_of_healing_disruption_chance(1) == pytest.approx(SPELL_DISRUPTION_CHANCE_PER_HIT * 0.5)
    assert words_of_healing_disruption_chance(2) == pytest.approx(2 * SPELL_DISRUPTION_CHANCE_PER_HIT * 0.5)
    assert words_of_healing_disruption_chance(0) == 0.0


def test_words_of_healing_disruption_chance_still_caps_at_95_percent():
    # 10 hits * (20%/2) = 100%, uncapped -- clamped to the same 95% cap.
    assert words_of_healing_disruption_chance(10) == pytest.approx(SPELL_DISRUPTION_CHANCE_CAP)


def test_resolve_words_of_healing_disruption_zero_hits_never_consumes_a_roll():
    rng = ScriptedRandom([])
    assert resolve_words_of_healing_disruption(0, rng) is False


def test_resolve_words_of_healing_disruption_uses_the_halved_chance():
    # 1 hit -> 10% (half of the normal 20%): 0.09 disrupts, 0.10 doesn't --
    # a roll that would disrupt a normal spell (0.19) does not disrupt WH.
    assert resolve_words_of_healing_disruption(1, ScriptedRandom([0.09])) is True
    assert resolve_words_of_healing_disruption(1, ScriptedRandom([0.10])) is False
    assert resolve_words_of_healing_disruption(1, ScriptedRandom([0.19])) is False


def test_resolve_words_of_healing_disruption_consumes_exactly_one_roll_when_hits_taken():
    rng = ScriptedRandom([0.99])  # a second .random() call would raise IndexError
    resolve_words_of_healing_disruption(2, rng)


def test_words_of_healing_heal_restores_to_full():
    combatant = Combatant("Ablamor", hit_points=3)

    words_of_healing_heal(combatant, CHARACTER_HIT_POINTS)

    assert combatant.hit_points == CHARACTER_HIT_POINTS == 10


def test_words_of_healing_heal_defaults_to_character_hit_points():
    combatant = Combatant("Ablamor", hit_points=1)

    words_of_healing_heal(combatant)

    assert combatant.hit_points == CHARACTER_HIT_POINTS


def test_words_of_healing_heal_uses_a_monster_supplied_max():
    combatant = Combatant("Troll", hit_points=5)

    words_of_healing_heal(combatant, max_hit_points=30)

    assert combatant.hit_points == 30


# -- Phase 202: Gate Demon [GD] --


def test_gate_demon_constants():
    assert GATE_DEMON_REFUSAL_CHANCE == 0.5
    assert GATE_DEMON_WINNER_RETURNS_TO_ABYSS is True
    assert GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE is True
    assert GATE_DEMON_NULLIFIED_BY_SIMULTANEOUS_MIRROR_IMAGE_OR_GATE_DEMON is True


def test_resolve_gate_demon_refusal_below_the_50_percent_threshold_refuses():
    assert resolve_gate_demon_refusal(ScriptedRandom([0.0])) is True
    assert resolve_gate_demon_refusal(ScriptedRandom([0.49])) is True


def test_resolve_gate_demon_refusal_at_or_above_the_50_percent_threshold_fights():
    assert resolve_gate_demon_refusal(ScriptedRandom([0.5])) is False
    assert resolve_gate_demon_refusal(ScriptedRandom([0.99])) is False


def test_resolve_gate_demon_refusal_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    resolve_gate_demon_refusal(rng)


# -- Phase 203: Lava Pool [LP] --


def test_lava_pool_constants():
    assert LAVA_POOL_KILLS_INSTANTLY is True
    assert LAVA_POOL_ESCAPE_CHANCE[MonsterSpeed.FAST] == 0.60
    assert LAVA_POOL_ESCAPE_CHANCE[MonsterSpeed.MEDIUM] == 0.30
    assert LAVA_POOL_ESCAPE_CHANCE[MonsterSpeed.SLOW] == 0.0


def test_lava_pool_escape_chance_looks_up_by_speed():
    assert lava_pool_escape_chance(MonsterSpeed.FAST) == 0.60
    assert lava_pool_escape_chance(MonsterSpeed.MEDIUM) == 0.30
    assert lava_pool_escape_chance(MonsterSpeed.SLOW) == 0.0


def test_resolve_lava_pool_escape_fast_speed_threshold():
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.0])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.59])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.60])) is False
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.99])) is False


def test_resolve_lava_pool_escape_medium_speed_threshold():
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.0])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.29])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.30])) is False
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.99])) is False


def test_resolve_lava_pool_escape_slow_speed_never_escapes():
    assert resolve_lava_pool_escape(MonsterSpeed.SLOW, ScriptedRandom([0.0])) is False
    assert resolve_lava_pool_escape(MonsterSpeed.SLOW, ScriptedRandom([0.99])) is False


def test_resolve_lava_pool_escape_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    resolve_lava_pool_escape(MonsterSpeed.MEDIUM, rng)


# -- Phase 205: Augur Combat [AC] --


def test_augur_combat_constants():
    assert AUGUR_COMBAT_FREE_WHEN_CAST_FIRST is True
    assert AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER is True
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.COWARDLY] == 0.80
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.CAUTIOUS] == 0.60
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.BRAVE] == 0.40
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.BERSERK] == 0.20


def test_augur_combat_shirk_chance_looks_up_by_temper():
    assert augur_combat_shirk_chance(Temper.COWARDLY) == 0.80
    assert augur_combat_shirk_chance(Temper.CAUTIOUS) == 0.60
    assert augur_combat_shirk_chance(Temper.BRAVE) == 0.40
    assert augur_combat_shirk_chance(Temper.BERSERK) == 0.20


def test_resolve_augur_combat_shirk_cowardly_threshold():
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.0])) is True
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.79])) is True
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.80])) is False
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.99])) is False


def test_resolve_augur_combat_shirk_berserk_threshold():
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.0])) is True
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.19])) is True
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.20])) is False
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.99])) is False


def test_resolve_augur_combat_shirk_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    resolve_augur_combat_shirk(Temper.BRAVE, rng)


def test_resolve_augur_combat_never_shirks_on_a_simulated_win():
    rng = ScriptedRandom([])  # a simulated win must not consume a roll at all
    assert resolve_augur_combat(would_lose_simulated_combat=False, temper=Temper.COWARDLY, rng=rng) is False


def test_resolve_augur_combat_rolls_the_shirk_chance_on_a_simulated_loss():
    assert (
        resolve_augur_combat(would_lose_simulated_combat=True, temper=Temper.COWARDLY, rng=ScriptedRandom([0.79]))
        is True
    )
    assert (
        resolve_augur_combat(would_lose_simulated_combat=True, temper=Temper.COWARDLY, rng=ScriptedRandom([0.80]))
        is False
    )


def test_spell_disruption_chance_still_defaults_to_the_normal_rate():
    # The new keyword-only chance_per_hit override doesn't change any
    # existing caller's behavior.
    assert spell_disruption_chance(1) == pytest.approx(SPELL_DISRUPTION_CHANCE_PER_HIT)


def test_resolve_spell_disruption_still_defaults_to_the_normal_rate():
    assert resolve_spell_disruption(1, ScriptedRandom([0.19])) is True
    assert resolve_spell_disruption(1, ScriptedRandom([0.20])) is False
