from __future__ import annotations

import random

from ak_engine.turn.battle_luck import (
    BATTLE_LUCK_BONUS_RANGE,
    BATTLE_LUCK_CHANCE,
    COLUMN_LUCK_BONUS_RANGE,
    COLUMN_LUCK_CHANCE,
    COLUMN_LUCK_MALUS_RANGE,
    roll_battle_luck,
    roll_column_luck,
)

TRIALS = 5000
TOLERANCE = 0.03  # +/- 3 percentage points on a 5000-trial sample


def test_column_luck_triggers_at_roughly_75_percent():
    rng = random.Random(1234)
    triggered = sum(1 for _ in range(TRIALS) if roll_column_luck(rng) is not None)
    assert abs(triggered / TRIALS - COLUMN_LUCK_CHANCE) < TOLERANCE


def test_column_luck_multiplier_within_documented_ranges():
    rng = random.Random(5678)
    for _ in range(TRIALS):
        event = roll_column_luck(rng)
        if event is None:
            continue
        if event.is_bonus:
            assert COLUMN_LUCK_BONUS_RANGE[0] <= event.multiplier <= COLUMN_LUCK_BONUS_RANGE[1]
        else:
            assert COLUMN_LUCK_MALUS_RANGE[0] <= event.multiplier <= COLUMN_LUCK_MALUS_RANGE[1]


def test_column_luck_bonus_and_malus_are_roughly_50_50():
    rng = random.Random(42)
    events = [e for _ in range(TRIALS) if (e := roll_column_luck(rng)) is not None]
    bonuses = sum(1 for e in events if e.is_bonus)
    assert abs(bonuses / len(events) - 0.5) < TOLERANCE


def test_battle_luck_triggers_at_roughly_55_percent():
    rng = random.Random(99)
    triggered = sum(1 for _ in range(TRIALS) if roll_battle_luck(rng) is not None)
    assert abs(triggered / TRIALS - BATTLE_LUCK_CHANCE) < TOLERANCE


def test_battle_luck_multiplier_within_documented_range():
    rng = random.Random(7)
    for _ in range(TRIALS):
        event = roll_battle_luck(rng)
        if event is None:
            continue
        assert BATTLE_LUCK_BONUS_RANGE[0] <= event.multiplier <= BATTLE_LUCK_BONUS_RANGE[1]


def test_battle_luck_picks_each_side_roughly_half_the_time():
    rng = random.Random(2024)
    events = [e for _ in range(TRIALS) if (e := roll_battle_luck(rng)) is not None]
    attacker_side = sum(1 for e in events if e.side == "attacker")
    assert abs(attacker_side / len(events) - 0.5) < TOLERANCE
