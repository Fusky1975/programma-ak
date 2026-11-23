"""[4.1.5]: the Melee Talent changes the 50% base chance to hit by 10 points per level of
difference (level 3 vs 2: 60% to hit, the other side 40%) -- confirmed by the user 2026-11-23."""

from __future__ import annotations

import random

import pytest

from ak_engine.turn.encounter import (
    Combatant,
    melee_skill_hit_bonus,
    resolve_one_melee_round,
    resolve_reactive_melee_swing,
    roll_melee_attack,
)

from _helpers import ScriptedRandom


@pytest.mark.parametrize("attacker,defender,bonus", [(3, 2, 0.1), (2, 3, -0.1), (3, 3, 0.0), (5, 0, 0.5), (0, 5, -0.5)])
def test_the_bonus_is_ten_points_per_level_of_difference(attacker, defender, bonus):
    assert melee_skill_hit_bonus(attacker, defender) == pytest.approx(bonus)


def test_roll_melee_attack_uses_the_adjusted_chance():
    # 0.55 is a miss at the flat 50% but a hit at 60%.
    assert roll_melee_attack(ScriptedRandom([0.55, 0.0]), skill_hit_bonus=0.1) > 0
    assert roll_melee_attack(ScriptedRandom([0.55, 0.0])) == 0
    # ...and 0.45 is a hit at 50% but a miss at 40%.
    assert roll_melee_attack(ScriptedRandom([0.45, 0.0])) > 0
    assert roll_melee_attack(ScriptedRandom([0.45, 0.0]), skill_hit_bonus=-0.1) == 0


def test_the_base_chance_stays_within_zero_and_one_hundred_percent():
    assert roll_melee_attack(ScriptedRandom([0.999, 0.0]), skill_hit_bonus=0.9) > 0  # 100%: always hits
    assert roll_melee_attack(ScriptedRandom([0.0, 0.0]), skill_hit_bonus=-0.9) == 0  # 0%: never hits


def test_the_other_multipliers_still_apply_after_the_skill_adjustment():
    # 60% base x 0.5 (e.g. Invisibility) = 30%.
    assert roll_melee_attack(ScriptedRandom([0.35, 0.0]), skill_hit_bonus=0.1, hit_chance_multiplier=0.5) == 0
    assert roll_melee_attack(ScriptedRandom([0.25, 0.0]), skill_hit_bonus=0.1, hit_chance_multiplier=0.5) > 0


def _hit_rate(a_skill: int, b_skill: int, trials: int = 20000) -> float:
    rng = random.Random(7)
    hits = swings = 0
    for _ in range(trials):
        a = Combatant("a", hit_points=1000, melee_skill=a_skill)
        b = Combatant("b", hit_points=1000, melee_skill=b_skill)
        for swing in resolve_one_melee_round(a, b, rng).swings:
            if swing.attacker == "a":
                swings += 1
                hits += swing.hit
    return hits / swings


def test_a_round_hits_at_sixty_percent_for_the_better_fighter_and_forty_for_the_other():
    assert _hit_rate(3, 2) == pytest.approx(0.60, abs=0.02)
    assert _hit_rate(2, 3) == pytest.approx(0.40, abs=0.02)
    assert _hit_rate(2, 2) == pytest.approx(0.50, abs=0.02)


def test_a_level_five_gap_is_a_certain_hit_and_a_certain_miss():
    assert _hit_rate(5, 0) == 1.0
    assert _hit_rate(0, 5) == 0.0


def test_the_reactive_swing_uses_the_adjusted_chance_too():
    attacker = Combatant("att", hit_points=10, melee_skill=3)
    defender = Combatant("def", hit_points=10, melee_skill=2)
    assert resolve_reactive_melee_swing(attacker, defender, ScriptedRandom([0.55, 0.0])).hit is True
    attacker = Combatant("att", hit_points=10, melee_skill=2)
    defender = Combatant("def", hit_points=10, melee_skill=3)
    assert resolve_reactive_melee_swing(attacker, defender, ScriptedRandom([0.45, 0.0])).hit is False
