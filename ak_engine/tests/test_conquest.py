from __future__ import annotations

from ak_engine.turn.conquest import movement_cost_for_move


def test_plain_move_costs_one_point():
    assert movement_cost_for_move() == 1


def test_conquest_adds_one_point():
    assert movement_cost_for_move(conquered=True) == 2


def test_sea_battle_without_conquest_adds_one_point():
    assert movement_cost_for_move(is_sea_province=True, battle_occurred=True) == 2


def test_sea_move_without_battle_costs_only_base():
    assert movement_cost_for_move(is_sea_province=True, battle_occurred=False) == 1


def test_land_battle_without_conquest_costs_only_base():
    assert movement_cost_for_move(is_sea_province=False, battle_occurred=True) == 1


def test_conquest_and_sea_battle_stack():
    assert movement_cost_for_move(is_sea_province=True, battle_occurred=True, conquered=True) == 3
