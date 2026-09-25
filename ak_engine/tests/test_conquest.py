from __future__ import annotations

from ak_engine.turn.conquest import movement_cost_for_move


def test_plain_move_costs_one_point():
    assert movement_cost_for_move() == 1


def test_conquest_adds_one_point():
    assert movement_cost_for_move(conquered=True) == 2


def test_battle_without_conquest_adds_one_point():
    # Phase 915, user-confirmed: a battle merely taking place owes the
    # extra point, on any terrain -- winning isn't required.
    assert movement_cost_for_move(battle_occurred=True) == 2


def test_no_battle_and_no_conquest_costs_only_base():
    assert movement_cost_for_move(battle_occurred=False, conquered=False) == 1


def test_conquest_and_battle_never_stack():
    # Phase 915: the previous implementation double-charged a won sea
    # battle (conquest + sea-battle surcharge, 3 total) -- Regolamento
    # AK.txt [7.7]'s own full text ("Come avviene nelle province di
    # terra, entrare in una di mare costa 1 Punto Movimento supplementare
    # solo se si dà luogo a una battaglia") ties the sea condition back
    # to the same single land surcharge, not a second, stackable one.
    assert movement_cost_for_move(battle_occurred=True, conquered=True) == 2
