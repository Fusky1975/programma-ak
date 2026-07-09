from __future__ import annotations

import random

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import BattleUnit, estimate_win_probability
from ak_engine.turn.battle_resolution import resolve_battle

from _helpers import ScriptedRandom


def unit(strength: float, army_type: ArmyType = ArmyType.BOWMEN) -> BattleUnit:
    return BattleUnit(army_type=army_type, effective_strength=strength)


def test_resolve_battle_with_no_luck_events_uses_plain_win_probability():
    # random() sequence: attacker-col-luck-skip, defender-col-luck-skip,
    # battle-luck-skip, win-roll.
    probability = estimate_win_probability(10, 10)
    win_roll = probability - 0.1  # below probability -> attacker wins
    rng = ScriptedRandom([0.9, 0.9, 0.9, win_roll])

    result = resolve_battle([unit(10)], [unit(10)], rng=rng)

    assert result.battle_luck is None
    assert result.columns[0].attacker_column_luck is None
    assert result.columns[0].defender_column_luck is None
    assert result.columns[0].attacker_strength == 10
    assert result.columns[0].defender_strength == 10
    assert result.columns[0].attacker_won is True
    assert result.winner == "attacker"
    assert result.attacker_columns_won == 1
    assert result.defender_columns_won == 0


def test_resolve_battle_defender_wins_when_roll_is_above_probability():
    probability = estimate_win_probability(10, 10)
    win_roll = probability + 0.1  # above probability -> defender wins
    rng = ScriptedRandom([0.9, 0.9, 0.9, win_roll])

    result = resolve_battle([unit(10)], [unit(10)], rng=rng)

    assert result.columns[0].attacker_won is False
    assert result.winner == "defender"


def test_resolve_battle_applies_battle_luck_to_chosen_side_totals():
    # random() sequence: attacker-col-luck-skip, defender-col-luck-skip,
    # battle-luck-triggers (< 0.55), then .uniform() consumes one more
    # random() call for the multiplier, then the win-roll.
    rng = ScriptedRandom([0.9, 0.9, 0.1, 0.5, 0.99], choice_indices=[1])  # index 1 -> "defender"

    result = resolve_battle([unit(10)], [unit(10)], rng=rng)

    expected_multiplier = 1.01 + (1.10 - 1.01) * 0.5
    assert result.battle_luck is not None
    assert result.battle_luck.side == "defender"
    assert result.battle_luck.multiplier == pytest.approx(expected_multiplier)
    assert result.columns[0].attacker_strength == 10
    assert result.columns[0].defender_strength == pytest.approx(10 * expected_multiplier)


def test_resolve_battle_applies_column_luck_to_front_line_unit():
    # attacker-col-luck triggers (< 0.75), bonus branch (< 0.5), uniform() consumes
    # one more random() call; defender-col-luck-skip; battle-luck-skip; win-roll.
    rng = ScriptedRandom([0.5, 0.2, 0.5, 0.9, 0.9, 0.99])

    result = resolve_battle([unit(10)], [unit(10)], rng=rng)

    expected_multiplier = 1.10 + (1.50 - 1.10) * 0.5
    assert result.columns[0].attacker_column_luck is not None
    assert result.columns[0].attacker_column_luck.is_bonus is True
    assert result.columns[0].attacker_strength == pytest.approx(10 * expected_multiplier)


def test_resolve_battle_rejects_empty_side():
    with pytest.raises(ValueError):
        resolve_battle([], [unit(10)], rng=random.Random(0))


def test_resolve_battle_structural_invariants_with_real_rng_multi_column():
    attacker = [unit(s) for s in [12, 10, 8, 6, 4]]
    defender = [unit(s) for s in [11, 9, 7, 5]]
    rng = random.Random(2026)

    result = resolve_battle(attacker, defender, rng=rng)

    line_length = min(len(attacker), len(defender))
    assert len(result.columns) == line_length
    assert result.attacker_columns_won + result.defender_columns_won == line_length
    if result.attacker_columns_won > result.defender_columns_won:
        assert result.winner == "attacker"
    elif result.defender_columns_won > result.attacker_columns_won:
        assert result.winner == "defender"
    else:
        assert result.winner == "tie"
    for column in result.columns:
        assert column.attacker_strength >= 0
        assert column.defender_strength >= 0


def test_resolve_battle_applies_nemesis_penalty_before_column_strength_is_reported():
    # Phalanx is Legion's nemesis-victim (see turn/battle_line.py's
    # apply_nemesis_penalties) -- the attacker's reported column strength
    # should already reflect the 2/3 penalty, before any luck is rolled.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.5])

    result = resolve_battle([unit(10, ArmyType.PHALANX)], [unit(10, ArmyType.LEGION)], rng=rng)

    assert result.columns[0].attacker_strength == pytest.approx(10 * 2 / 3)
    assert result.columns[0].defender_strength == 10


def test_resolve_battle_column_results_expose_the_actual_units_for_bookkeeping():
    attacker = [BattleUnit(ArmyType.BOWMEN, 10, source_id=101)]
    defender = [BattleUnit(ArmyType.AXEMEN, 5, source_id=202)]

    result = resolve_battle(attacker, defender, rng=random.Random(0))

    assert [u.source_id for u in result.columns[0].attacker_units] == [101]
    assert [u.source_id for u in result.columns[0].defender_units] == [202]
