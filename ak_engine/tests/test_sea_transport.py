"""Tests for turn/sea_transport.py -- see its module docstring for the
full, Regolamento-AK.txt-sourced Fleet/Whale cargo-capacity mechanic
these exercise.
"""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.combat import Quality
from ak_engine.turn.sea_transport import (
    apply_battle_carrier_destruction,
    apply_carrier_destruction,
    board_army,
    can_board,
    cargo_aboard,
    disembark_army,
)

HOME = HexCoord(0, 0)
ELSEWHERE = HexCoord(9, 9)


def _army(army_id: int, army_type: ArmyType, *, location: HexCoord = HOME, transported_by: int | None = None) -> ArmyState:
    return ArmyState(army_id, kingdom_id=1, army_type=army_type, quality=Quality.AVERAGE, location=location, transported_by=transported_by)


def _state(*armies: ArmyState) -> GameState:
    state = GameState()
    for army in armies:
        state.add_army(army)
    return state


# -- can_board(): Fleet, ordinary infantry/mounted rule --------------------


def test_can_board_fleet_accepts_a_mounted_unit_when_empty():
    fleet = _army(1, ArmyType.FLEET)
    state = _state(fleet)

    assert can_board(state, fleet, ArmyType.ELEPHANTS) is True


def test_can_board_fleet_refuses_a_second_mounted_unit():
    fleet = _army(1, ArmyType.FLEET)
    cargo = _army(2, ArmyType.ELEPHANTS, transported_by=1)
    state = _state(fleet, cargo)

    assert can_board(state, fleet, ArmyType.CAMEL_CORPS) is False


def test_can_board_fleet_accepts_two_infantry_units():
    fleet = _army(1, ArmyType.FLEET)
    first = _army(2, ArmyType.BOWMEN, transported_by=1)
    state = _state(fleet, first)

    assert can_board(state, fleet, ArmyType.AXEMEN) is True


def test_can_board_fleet_refuses_a_third_infantry_unit():
    fleet = _army(1, ArmyType.FLEET)
    first = _army(2, ArmyType.BOWMEN, transported_by=1)
    second = _army(3, ArmyType.AXEMEN, transported_by=1)
    state = _state(fleet, first, second)

    assert can_board(state, fleet, ArmyType.PHALANX) is False


def test_can_board_fleet_refuses_infantry_once_a_mounted_unit_is_aboard():
    fleet = _army(1, ArmyType.FLEET)
    mounted = _army(2, ArmyType.CHARIOTS, transported_by=1)
    state = _state(fleet, mounted)

    assert can_board(state, fleet, ArmyType.BOWMEN) is False


def test_can_board_fleet_refuses_a_mounted_unit_once_infantry_is_aboard():
    fleet = _army(1, ArmyType.FLEET)
    infantry = _army(2, ArmyType.LEGION, transported_by=1)
    state = _state(fleet, infantry)

    assert can_board(state, fleet, ArmyType.LT_CAVALRY) is False


def test_can_board_fleet_troll_and_werebeast_count_as_infantry():
    # Regolamento AK.txt's own explicit parenthetical: "(inclusi Troll
    # e Bestie Mannare)".
    fleet = _army(1, ArmyType.FLEET)
    state = _state(fleet)

    assert can_board(state, fleet, ArmyType.TROLLS) is True
    assert can_board(state, fleet, ArmyType.WEREBEASTS) is True


# -- can_board(): Fleet, DRUIDIC_TRANSPORT's own otherwise-ineligible bucket --


def test_can_board_fleet_refuses_ents_without_the_ability():
    fleet = _army(1, ArmyType.FLEET)
    state = _state(fleet)

    assert can_board(state, fleet, ArmyType.ENTS) is False


def test_can_board_fleet_accepts_exactly_one_ent_with_the_ability():
    fleet = _army(1, ArmyType.FLEET)
    state = _state(fleet)

    assert can_board(state, fleet, ArmyType.ENTS, caster_has_druidic_transport=True) is True


def test_can_board_fleet_refuses_a_second_special_unit_even_with_the_ability():
    fleet = _army(1, ArmyType.FLEET)
    ent = _army(2, ArmyType.ENTS, transported_by=1)
    state = _state(fleet, ent)

    assert can_board(state, fleet, ArmyType.DINOSAURS, caster_has_druidic_transport=True) is False


def test_can_board_fleet_accepts_dinosaurs_with_the_ability():
    fleet = _army(1, ArmyType.FLEET)
    state = _state(fleet)

    assert can_board(state, fleet, ArmyType.DINOSAURS, caster_has_druidic_transport=True) is True


def test_can_board_fleet_special_capacity_is_independent_of_infantry_slots():
    # A special (Ent) unit aboard doesn't block ordinary infantry, and
    # vice versa -- two genuinely separate capacity pools on the Fleet.
    fleet = _army(1, ArmyType.FLEET)
    ent = _army(2, ArmyType.ENTS, transported_by=1)
    state = _state(fleet, ent)

    assert can_board(state, fleet, ArmyType.BOWMEN) is True


# -- can_board(): Whales, DRUIDIC_WHALE_TRANSPORT ---------------------------


def test_can_board_whale_refuses_without_the_ability():
    whale = _army(1, ArmyType.WHALES)
    state = _state(whale)

    assert can_board(state, whale, ArmyType.BOWMEN) is False


def test_can_board_whale_accepts_one_infantry_with_the_ability():
    whale = _army(1, ArmyType.WHALES)
    state = _state(whale)

    assert can_board(state, whale, ArmyType.BOWMEN, caster_has_druidic_whale_transport=True) is True


def test_can_board_whale_refuses_a_second_infantry_unit():
    whale = _army(1, ArmyType.WHALES)
    cargo = _army(2, ArmyType.BOWMEN, transported_by=1)
    state = _state(whale, cargo)

    assert can_board(state, whale, ArmyType.AXEMEN, caster_has_druidic_whale_transport=True) is False


def test_can_board_whale_refuses_a_mounted_unit_even_with_the_ability():
    # The ability's own text says "infantry armies" only.
    whale = _army(1, ArmyType.WHALES)
    state = _state(whale)

    assert can_board(state, whale, ArmyType.ELEPHANTS, caster_has_druidic_whale_transport=True) is False


# -- can_board(): Mermen and other non-carriers never carry anything -------


def test_can_board_mermen_never_carries_cargo():
    mermen = _army(1, ArmyType.MERMEN)
    state = _state(mermen)

    assert can_board(state, mermen, ArmyType.BOWMEN, caster_has_druidic_whale_transport=True) is False


def test_can_board_ordinary_land_army_never_carries_cargo():
    legion = _army(1, ArmyType.LEGION)
    state = _state(legion)

    assert can_board(state, legion, ArmyType.BOWMEN, caster_has_druidic_transport=True) is False


# -- board_army() / disembark_army() ----------------------------------------


def test_board_army_success_sets_transported_by():
    fleet = _army(1, ArmyType.FLEET)
    cargo = _army(2, ArmyType.BOWMEN)
    state = _state(fleet, cargo)

    assert board_army(state, 2, 1) is True
    assert state.armies[2].transported_by == 1


def test_board_army_refuses_when_not_co_located():
    fleet = _army(1, ArmyType.FLEET)
    cargo = _army(2, ArmyType.BOWMEN, location=ELSEWHERE)
    state = _state(fleet, cargo)

    assert board_army(state, 2, 1) is False
    assert state.armies[2].transported_by is None


def test_board_army_refuses_when_already_boarded_elsewhere():
    fleet_a = _army(1, ArmyType.FLEET)
    fleet_b = _army(2, ArmyType.FLEET)
    cargo = _army(3, ArmyType.BOWMEN, transported_by=1)
    state = _state(fleet_a, fleet_b, cargo)

    assert board_army(state, 3, 2) is False
    assert state.armies[3].transported_by == 1


def test_board_army_refuses_when_can_board_refuses():
    fleet = _army(1, ArmyType.FLEET)
    cargo = _army(2, ArmyType.ENTS)
    state = _state(fleet, cargo)

    assert board_army(state, 2, 1) is False  # no DRUIDIC_TRANSPORT


def test_board_army_refuses_for_a_missing_army():
    fleet = _army(1, ArmyType.FLEET)
    state = _state(fleet)

    assert board_army(state, 999, 1) is False
    assert board_army(state, 1, 999) is False


def test_disembark_army_clears_transported_by():
    cargo = _army(2, ArmyType.BOWMEN, transported_by=1)
    state = _state(cargo)

    assert disembark_army(state, 2) is True
    assert state.armies[2].transported_by is None


def test_disembark_army_returns_false_when_not_boarded():
    cargo = _army(2, ArmyType.BOWMEN)
    state = _state(cargo)

    assert disembark_army(state, 2) is False


def test_disembark_army_returns_false_for_a_missing_army():
    state = _state()

    assert disembark_army(state, 999) is False


# -- apply_carrier_destruction(): cargo sinks with the carrier --------------


def test_apply_carrier_destruction_removes_all_boarded_cargo():
    fleet = _army(1, ArmyType.FLEET)
    first = _army(2, ArmyType.BOWMEN, transported_by=1)
    second = _army(3, ArmyType.AXEMEN, transported_by=1)
    unrelated = _army(4, ArmyType.LEGION)
    state = _state(fleet, first, second, unrelated)

    destroyed = apply_carrier_destruction(state, 1)

    assert sorted(destroyed) == [2, 3]
    assert 2 not in state.armies
    assert 3 not in state.armies
    assert 4 in state.armies  # untouched


def test_apply_carrier_destruction_returns_empty_list_with_no_cargo():
    fleet = _army(1, ArmyType.FLEET)
    state = _state(fleet)

    assert apply_carrier_destruction(state, 1) == []


def test_cargo_aboard_returns_only_matching_carrier():
    fleet_a = _army(1, ArmyType.FLEET)
    fleet_b = _army(2, ArmyType.FLEET)
    on_a = _army(3, ArmyType.BOWMEN, transported_by=1)
    on_b = _army(4, ArmyType.AXEMEN, transported_by=2)
    state = _state(fleet_a, fleet_b, on_a, on_b)

    assert [army.army_id for army in cargo_aboard(state, 1)] == [3]


# -- Phase 716: apply_battle_carrier_destruction() -- battle integration ---


def test_apply_battle_carrier_destruction_sinks_cargo_on_a_destroyed_fleet():
    fleet = _army(1, ArmyType.FLEET)
    cargo = _army(2, ArmyType.BOWMEN, transported_by=1)
    state = _state(fleet, cargo)

    sunk = apply_battle_carrier_destruction(state, destroyed_army_ids=[1])

    assert sunk == [2]
    assert 2 not in state.armies


def test_apply_battle_carrier_destruction_checks_all_three_lists():
    fleet_a = _army(1, ArmyType.FLEET)
    fleet_b = _army(2, ArmyType.FLEET)
    fleet_c = _army(3, ArmyType.FLEET)
    on_a = _army(4, ArmyType.BOWMEN, transported_by=1)
    on_b = _army(5, ArmyType.AXEMEN, transported_by=2)
    on_c = _army(6, ArmyType.PHALANX, transported_by=3)
    state = _state(fleet_a, fleet_b, fleet_c, on_a, on_b, on_c)

    sunk = apply_battle_carrier_destruction(
        state, destroyed_army_ids=[1], disbanded_army_ids=[2], pursuit_destroyed_army_ids=[3]
    )

    assert sorted(sunk) == [4, 5, 6]


def test_apply_battle_carrier_destruction_ignores_non_carrier_destroyed_armies():
    legion = _army(1, ArmyType.LEGION)
    state = _state(legion)

    sunk = apply_battle_carrier_destruction(state, destroyed_army_ids=[1])

    assert sunk == []


def test_apply_battle_carrier_destruction_returns_empty_with_no_arguments():
    state = _state()

    assert apply_battle_carrier_destruction(state) == []
