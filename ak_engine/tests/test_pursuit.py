from __future__ import annotations

import random

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.pursuit import (
    CAVALRY_PURSUIT_CHANCE,
    INFANTRY_PURSUIT_CHANCE,
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
