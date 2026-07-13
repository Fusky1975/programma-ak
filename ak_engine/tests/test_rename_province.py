from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.rename_province import rename_home_province


def _state_with_kingdom(home_province: HexCoord) -> GameState:
    state = GameState()
    state.kingdoms[1] = KingdomState(
        kingdom_id=1, name="Testland", race=Race.HUMAN, alignment=Alignment.GOOD, home_province=home_province
    )
    state.provinces[home_province] = ProvinceState(coord=home_province, terrain=Terrain.PLAINS, race=Race.HUMAN)
    return state


def test_province_name_defaults_to_none():
    coord = HexCoord(1, 1)
    state = _state_with_kingdom(coord)
    assert state.provinces[coord].name is None


def test_rename_home_province_sets_the_name():
    coord = HexCoord(2, 2)
    state = _state_with_kingdom(coord)

    rename_home_province(state, 1, "Candelaria")

    assert state.provinces[coord].name == "Candelaria"


def test_rename_home_province_only_affects_the_named_kingdoms_province():
    home = HexCoord(3, 3)
    other = HexCoord(4, 4)
    state = _state_with_kingdom(home)
    state.provinces[other] = ProvinceState(coord=other, terrain=Terrain.PLAINS, race=Race.HUMAN)

    rename_home_province(state, 1, "Candelaria")

    assert state.provinces[home].name == "Candelaria"
    assert state.provinces[other].name is None


def test_rename_home_province_raises_for_unknown_kingdom():
    state = _state_with_kingdom(HexCoord(5, 5))
    with pytest.raises(KeyError):
        rename_home_province(state, 999, "Candelaria")


def test_rename_home_province_raises_when_home_province_missing_from_state():
    state = GameState()
    state.kingdoms[1] = KingdomState(
        kingdom_id=1,
        name="Testland",
        race=Race.HUMAN,
        alignment=Alignment.GOOD,
        home_province=HexCoord(6, 6),
    )
    with pytest.raises(KeyError):
        rename_home_province(state, 1, "Candelaria")
