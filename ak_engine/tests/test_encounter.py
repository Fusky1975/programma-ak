from __future__ import annotations

import pytest

from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_BASE_HIT_CHANCE,
    FIRE_ARROW_HIT_CHANCE_PER_LEVEL,
    MELEE_HIT_CHANCE,
    NEUTRAL_DUELIST_BONUS,
    Combatant,
    _acts_first,
    effective_archery_skill,
    effective_melee_skill,
    fire_arrow_free_attacks,
    fire_arrow_hit_chance,
    resolve_fire_arrow_duel,
    resolve_melee_duel,
    roll_fire_arrow_attack,
    roll_melee_attack,
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
