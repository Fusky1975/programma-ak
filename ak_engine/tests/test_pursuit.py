from __future__ import annotations

import random

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.pursuit import (
    CAVALRY_PURSUIT_CHANCE,
    INFANTRY_PURSUIT_CHANCE,
    draw_pursuit_random_multiplier,
    pursuit_destruction_probability,
    resolve_pursuit,
    select_pursuers,
)

TRIALS = 3000
TOLERANCE = 0.03


def unit(army_type: ArmyType, strength: float = 10) -> BattleUnit:
    return BattleUnit(army_type=army_type, effective_strength=strength)


def test_infantry_pursuit_rate_matches_documented_25_percent():
    rng = random.Random(1)
    victors = [unit(ArmyType.BOWMEN) for _ in range(TRIALS)]
    pursuers = select_pursuers(victors, rng)
    assert abs(len(pursuers) / TRIALS - INFANTRY_PURSUIT_CHANCE) < TOLERANCE


def test_cavalry_pursuit_rate_matches_documented_75_percent():
    rng = random.Random(2)
    victors = [unit(ArmyType.HVY_CAVALRY) for _ in range(TRIALS)]
    pursuers = select_pursuers(victors, rng)
    assert abs(len(pursuers) / TRIALS - CAVALRY_PURSUIT_CHANCE) < TOLERANCE


def test_light_cavalry_and_air_wings_can_pursue_twice():
    rng = random.Random(0)
    rng.random = lambda: 0.0  # force every pursuit roll to succeed
    victors = [unit(ArmyType.LT_CAVALRY), unit(ArmyType.DRAGON_WING), unit(ArmyType.BOWMEN)]

    pursuers = select_pursuers(victors, rng)

    assert pursuers.count(victors[0]) == 2
    assert pursuers.count(victors[1]) == 2
    assert pursuers.count(victors[2]) == 1


def test_resolve_pursuit_catches_slowest_retreaters_first():
    fast = unit(ArmyType.LT_CAVALRY, strength=1)   # speed 4
    slow = unit(ArmyType.ENTS, strength=1)          # speed 1
    pursuers = [unit(ArmyType.HVY_CAVALRY, strength=1000)]  # overwhelming strength -> always "destroys"
    rng = random.Random(0)

    outcomes = resolve_pursuit(pursuers, [fast, slow], rng)

    assert len(outcomes) == 1
    assert outcomes[0].target is slow


def test_resolve_pursuit_leaves_excess_retreaters_unengaged():
    pursuers = [unit(ArmyType.HVY_CAVALRY, 10)]
    targets = [unit(ArmyType.ENTS, 1), unit(ArmyType.TROLLS, 1)]
    outcomes = resolve_pursuit(pursuers, targets, random.Random(0))
    assert len(outcomes) == 1


def test_resolve_pursuit_destroys_when_pursuer_overwhelms():
    pursuer = unit(ArmyType.HVY_CAVALRY, strength=1000)
    target = unit(ArmyType.ENTS, strength=1)
    rng = random.Random(0)
    rng.random = lambda: 0.0  # below any non-trivial win probability

    outcomes = resolve_pursuit([pursuer], [target], rng)

    assert outcomes[0].target_destroyed is True


def test_resolve_pursuit_survives_when_pursuer_is_weak():
    pursuer = unit(ArmyType.HVY_CAVALRY, strength=1)
    target = unit(ArmyType.ENTS, strength=1000)
    rng = random.Random(0)
    rng.random = lambda: 0.99  # above any low win probability

    outcomes = resolve_pursuit([pursuer], [target], rng)

    assert outcomes[0].target_destroyed is False


# -- Phase 349: the confirmed AK.EXE/AK.OVR pursuit standstill formula ----


def test_pursuit_destruction_probability_matches_the_source_examples():
    # Source: examples_percent for r_p = 0.8/1.0/1.25/1.5/2.0.
    assert pursuit_destruction_probability(0.8) == pytest.approx(0.225)
    assert pursuit_destruction_probability(1.0) == pytest.approx(0.5)
    assert pursuit_destruction_probability(1.25) == pytest.approx(0.775)
    assert pursuit_destruction_probability(1.5) == pytest.approx(0.916666667, rel=1e-6)
    assert pursuit_destruction_probability(2.0) == pytest.approx(1.0)


def test_pursuit_destruction_probability_clamps_outside_the_documented_range():
    assert pursuit_destruction_probability(0.1) == 0.0
    assert pursuit_destruction_probability(0.5) == 0.0
    assert pursuit_destruction_probability(10.0) == 1.0
    assert pursuit_destruction_probability(float("inf")) == 1.0


def test_draw_pursuit_random_multiplier_stays_within_u1_2():
    rng = random.Random(349)
    for _ in range(TRIALS):
        multiplier = draw_pursuit_random_multiplier(rng)
        assert 1.0 <= multiplier < 2.0


def test_resolve_pursuit_handles_a_strengthless_target_without_crashing():
    # A retreater already reduced to zero effective strength (e.g. a
    # fully depleted unit) must not raise ZeroDivisionError -- it's the
    # r_p -> infinity edge case, a guaranteed catch.
    pursuer = unit(ArmyType.HVY_CAVALRY, strength=10)
    target = unit(ArmyType.ENTS, strength=0)
    rng = random.Random(0)

    outcomes = resolve_pursuit([pursuer], [target], rng)

    assert outcomes[0].target_destroyed is True
