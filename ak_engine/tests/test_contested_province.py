from __future__ import annotations

from ak_engine.turn.contested_province import (
    attacker_can_force_rebattle,
    contested_battle_movement_cost,
    is_illegal_move_from_contested,
)


def test_attacker_can_force_rebattle_when_all_armies_have_a_point():
    assert attacker_can_force_rebattle({1: 1, 2: 2}) is True


def test_attacker_cannot_force_rebattle_if_any_army_is_out_of_points():
    assert attacker_can_force_rebattle({1: 1, 2: 0}) is False


def test_attacker_cannot_force_rebattle_with_no_armies():
    assert attacker_can_force_rebattle({}) is False


def test_illegal_move_only_when_origin_contested_and_target_enemy():
    assert is_illegal_move_from_contested(origin_is_contested=True, target_owner_is_enemy=True) is True
    assert is_illegal_move_from_contested(origin_is_contested=True, target_owner_is_enemy=False) is False
    assert is_illegal_move_from_contested(origin_is_contested=False, target_owner_is_enemy=True) is False


def test_contested_battle_movement_cost():
    assert contested_battle_movement_cost(conquered=False) == 1
    assert contested_battle_movement_cost(conquered=True) == 2
