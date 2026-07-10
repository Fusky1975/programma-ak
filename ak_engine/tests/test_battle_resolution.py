from __future__ import annotations

import random

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import BattleUnit, estimate_win_probability
from ak_engine.turn.battle_resolution import resolve_battle

from _helpers import ScriptedRandom


def unit(strength: float, army_type: ArmyType = ArmyType.BOWMEN, *, druidic_rear_targeting_blocked: bool = False) -> BattleUnit:
    return BattleUnit(
        army_type=army_type,
        effective_strength=strength,
        druidic_rear_targeting_blocked=druidic_rear_targeting_blocked,
    )


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


def test_resolve_battle_runs_tactical_switches_before_nemesis_penalties_and_luck():
    # Same nemesis chain as test_battle_line.py's
    # test_apply_tactical_switches_defenders_decision_uses_the_attackers_post_switch_front:
    # both sides are nemesis-eligible to switch once ability lets them, and
    # the defender's switch only makes sense reading the attacker's
    # already-switched front. terrain_line_length_cap=1 forces both units
    # per side into one stacked column instead of two separate ones.
    attacker_units = [unit(10, ArmyType.PHALANX), unit(9, ArmyType.HVY_CAVALRY)]
    defender_units = [unit(10, ArmyType.LEGION), unit(9, ArmyType.BOWMEN)]
    # atk-switch-roll, def-switch-roll, atk-col-luck-skip, def-col-luck-skip,
    # battle-luck-skip, win-roll.
    rng = ScriptedRandom([0.0, 0.0, 0.9, 0.9, 0.9, 0.5])

    result = resolve_battle(
        attacker_units,
        defender_units,
        terrain_line_length_cap=1,
        attacker_tactical_ability=1,
        defender_tactical_ability=1,
        rng=rng,
    )

    column = result.columns[0]
    assert column.attacker_switched is True
    assert column.defender_switched is True
    assert [u.army_type for u in column.attacker_units] == [ArmyType.HVY_CAVALRY, ArmyType.PHALANX]
    assert [u.army_type for u in column.defender_units] == [ArmyType.BOWMEN, ArmyType.LEGION]
    # Post-switch, the defender's rearward Legion is nemesis-weak against
    # the attacker's new front (Heavy Cavalry) -- apply_nemesis_penalties
    # ran against the final lineup, not the original one.
    assert column.attacker_strength == pytest.approx(9 * 1.0 + 10 * 0.5)
    assert column.defender_strength == pytest.approx(9 * 1.0 + (10 * 2 / 3) * 0.5)


def test_resolve_battle_defaults_to_no_switching():
    # attacker_tactical_ability/defender_tactical_ability default to 0 --
    # switch_chance is 0, so even a nemesis-eligible column never swaps.
    attacker_units = [unit(10, ArmyType.PHALANX), unit(9, ArmyType.HVY_CAVALRY)]
    defender_units = [unit(10, ArmyType.LEGION)]
    rng = ScriptedRandom([0.0, 0.9, 0.9, 0.9, 0.5])  # atk-switch-roll (consumed, fails), rest as usual

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=1, rng=rng)

    assert result.columns[0].attacker_switched is False
    assert [u.army_type for u in result.columns[0].attacker_units] == [ArmyType.PHALANX, ArmyType.HVY_CAVALRY]


def test_resolve_battle_opposing_overflight_unit_boosts_second_line_to_full_strength():
    # Rulebook [7.2]: an overflight attacker "will attack the rear unit
    # instead (the non-human unit and the rearward unit will both be at
    # 100% strength in this case.)" -- the defender's own second-line
    # Axemen goes from 50% to 100% because the attacker's Whales unit is
    # present, regardless of column depth on either side. (Whales, not
    # Dragon/Eagle Wing or Mermen, to avoid an incidental nemesis
    # matchup against Bowmen muddying the numbers -- NEMESIS[Whales] is
    # Mermen, not Bowmen.)
    attacker_units = [unit(10, ArmyType.WHALES)]
    defender_units = [unit(10, ArmyType.BOWMEN), unit(9, ArmyType.AXEMEN)]
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.5])

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=1, rng=rng)

    assert result.columns[0].attacker_strength == pytest.approx(10)
    assert result.columns[0].defender_strength == pytest.approx(10 * 1.0 + 9 * 1.0)


def test_resolve_battle_druidic_blocked_overflight_unit_does_not_trigger_rear_targeting():
    # Phase 43: same setup as the boost test above, but the attacker's
    # Whales unit is held back (insufficient Druidic ability) -- the
    # defender's second-line Axemen stays at ordinary 50%, not boosted.
    attacker_units = [unit(10, ArmyType.WHALES, druidic_rear_targeting_blocked=True)]
    defender_units = [unit(10, ArmyType.BOWMEN), unit(9, ArmyType.AXEMEN)]
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.5])

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=1, rng=rng)

    # The blocked Whales unit also loses its own 100%-regardless-of-depth
    # treatment, but it's alone at depth 0 so that part reads the same
    # either way (100%) -- the defender side is where the difference shows.
    assert result.columns[0].attacker_strength == pytest.approx(10)
    assert result.columns[0].defender_strength == pytest.approx(10 * 1.0 + 9 * 0.5)


def test_resolve_battle_druidic_blocked_flag_survives_front_line_luck():
    # Regression (Phase 43): _apply_front_line_luck replaces the front-line
    # unit with a new BattleUnit when a luck event lands -- the held-back
    # flag must survive that replacement too, or a later opposing-side
    # column_has_overflight_unit check downstream would misread it.
    attacker_units = [unit(10, ArmyType.WHALES, druidic_rear_targeting_blocked=True)]
    defender_units = [unit(10, ArmyType.BOWMEN), unit(9, ArmyType.AXEMEN)]
    # No tactical switching happens either side (ability=0 default, and
    # the check bails before consuming rng -- see the sibling boost test
    # above for the same structural setup). Sequence: attacker column-luck
    # chance (0.05, under COLUMN_LUCK_CHANCE=0.75 -> event triggers),
    # is_bonus roll, uniform's internal random() call; defender column-luck
    # chance (0.9, no event); battle-luck chance (0.9, no event); the
    # single column's win roll (0.5).
    rng = ScriptedRandom([0.05, 0.5, 0.5, 0.9, 0.9, 0.5])

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=1, rng=rng)

    # Still no rear-targeting boost for the defender's second-line unit,
    # proving the flag wasn't reset to False by the luck-driven replacement.
    assert result.columns[0].defender_strength == pytest.approx(10 * 1.0 + 9 * 0.5)


def test_resolve_battle_column_results_expose_the_actual_units_for_bookkeeping():
    attacker = [BattleUnit(ArmyType.BOWMEN, 10, source_id=101)]
    defender = [BattleUnit(ArmyType.AXEMEN, 5, source_id=202)]

    result = resolve_battle(attacker, defender, rng=random.Random(0))

    assert [u.source_id for u in result.columns[0].attacker_units] == [101]
    assert [u.source_id for u in result.columns[0].defender_units] == [202]
