from __future__ import annotations

import random

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import BattleUnit, estimate_win_probability
from ak_engine.turn.battle_resolution import resolve_battle


class ScriptedRandom(random.Random):
    """A Random whose .random()/.choice() replay a fixed script, for deterministic tests.

    random.Random.uniform() calls self.random() internally, so scripting
    .random() also controls .uniform(); .choice() is overridden directly
    since CPython's implementation uses _randbelow (bit generation), not
    .random().
    """

    def __init__(self, randoms, choice_indices=()):
        super().__init__()
        self._randoms = list(randoms)
        self._choice_indices = list(choice_indices)

    def random(self):
        return self._randoms.pop(0)

    def choice(self, seq):
        return seq[self._choice_indices.pop(0)]


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
