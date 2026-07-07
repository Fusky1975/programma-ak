from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import (
    BattleUnit,
    assign_battle_lines,
    column_strength,
    contest_columns,
    line_length_for_battle,
    switch_chance,
)


def unit(army_type: ArmyType, strength: float) -> BattleUnit:
    return BattleUnit(army_type=army_type, effective_strength=strength)


def test_line_length_is_capped_by_smaller_force():
    assert line_length_for_battle(5, 3) == 3
    assert line_length_for_battle(2, 7) == 2


def test_line_length_respects_terrain_cap_when_given():
    assert line_length_for_battle(10, 10, terrain_line_length_cap=4) == 4


def test_line_length_ignores_terrain_cap_when_not_given():
    assert line_length_for_battle(10, 10) == 10


def test_assign_battle_lines_fills_front_line_across_columns_first():
    units = [unit(ArmyType.BOWMEN, s) for s in [7, 6, 5, 4, 3, 2, 1]]
    columns = assign_battle_lines(units, line_length=3)

    assert len(columns) == 3
    # Front line: units[0..2] go one per column.
    assert [c[0].effective_strength for c in columns] == [7, 6, 5]
    # Second line: units[3..5] go one per column.
    assert [c[1].effective_strength for c in columns] == [4, 3, 2]
    # Third line: only column 0 gets the leftover unit.
    assert columns[0][2].effective_strength == 1
    assert len(columns[1]) == 2
    assert len(columns[2]) == 2


def test_assign_battle_lines_rejects_non_positive_line_length():
    with pytest.raises(ValueError):
        assign_battle_lines([unit(ArmyType.BOWMEN, 1)], line_length=0)


def test_column_strength_halves_per_depth_for_ordinary_units():
    column = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.AXEMEN, 10), unit(ArmyType.PHALANX, 10)]
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 0.5 + 10 * 0.25)


def test_column_strength_gives_overflight_units_full_strength_regardless_of_depth():
    column = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.DRAGON_WING, 10)]
    # Dragon Wing is at depth 1 but is an overflight unit -> 100%, not 50%.
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_column_strength_halves_stacked_overflight_units_within_the_same_group():
    column = [unit(ArmyType.DRAGON_WING, 10), unit(ArmyType.EAGLE_WING, 10)]
    # Both are 'air' group -> first at 100%, second (same group) at 50%.
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 0.5)


def test_column_strength_keeps_air_and_sea_overflight_groups_independent():
    column = [unit(ArmyType.DRAGON_WING, 10), unit(ArmyType.WHALES, 10)]
    # Different groups (air vs sea) -> both count as the "first" in their group.
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_column_strength_outflank_boosts_second_line_to_full_strength():
    column = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.AXEMEN, 10)]
    normal = column_strength(column)
    outflanked = column_strength(column, outflank_second_line=True)
    assert normal == pytest.approx(10 * 1.0 + 10 * 0.5)
    assert outflanked == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_switch_chance_matches_formula():
    assert switch_chance(tactical_ability=2, line_length=4) == pytest.approx(0.5)


def test_switch_chance_clamped_to_one():
    assert switch_chance(tactical_ability=10, line_length=2) == 1.0


def test_switch_chance_rejects_bad_inputs():
    with pytest.raises(ValueError):
        switch_chance(tactical_ability=1, line_length=0)
    with pytest.raises(ValueError):
        switch_chance(tactical_ability=-1, line_length=1)


def test_contest_columns_pairs_up_and_estimates_probability():
    attacker_columns = [[unit(ArmyType.BOWMEN, 10)]]
    defender_columns = [[unit(ArmyType.AXEMEN, 10)]]

    contests = contest_columns(attacker_columns, defender_columns)

    assert len(contests) == 1
    assert contests[0].attacker_strength == 10
    assert contests[0].defender_strength == 10
    assert contests[0].attacker_win_probability == pytest.approx(0.5)


def test_contest_columns_handles_undefended_column():
    attacker_columns = [[unit(ArmyType.BOWMEN, 10)]]
    defender_columns = [[]]

    contests = contest_columns(attacker_columns, defender_columns)

    assert contests[0].attacker_win_probability == 1.0


def test_contest_columns_requires_equal_column_counts():
    with pytest.raises(ValueError):
        contest_columns([[unit(ArmyType.BOWMEN, 10)]], [])
