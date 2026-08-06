from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.persistence import load_game_state, save_game_state
from ak_engine.turn.combat import Quality


def _sample_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(0, 0), is_king=True))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.VETERAN, HexCoord(0, 0), commanded_by=1))
    state.turn_number = 3
    return state


def test_save_then_load_round_trips_the_whole_state(tmp_path: Path):
    state = _sample_state()
    path = tmp_path / "save.pkl"

    save_game_state(state, path)
    loaded = load_game_state(path)

    assert loaded.turn_number == 3
    assert loaded.kingdoms[1].name == "Humania"
    assert loaded.provinces[HexCoord(0, 0)].name == "Numenor"
    assert loaded.leaders[1].name == "Arthur"
    assert loaded.leaders[1].is_king is True
    assert loaded.armies[101].army_type is ArmyType.HVY_CAVALRY
    assert loaded.armies[101].quality is Quality.VETERAN


def test_save_overwrites_an_existing_file(tmp_path: Path):
    path = tmp_path / "save.pkl"
    save_game_state(_sample_state(), path)

    other = GameState()
    other.turn_number = 99
    save_game_state(other, path)

    loaded = load_game_state(path)
    assert loaded.turn_number == 99
    assert loaded.kingdoms == {}


def test_loaded_state_is_a_deep_copy_not_shared_with_the_original(tmp_path: Path):
    state = _sample_state()
    path = tmp_path / "save.pkl"
    save_game_state(state, path)

    loaded = load_game_state(path)
    loaded.leaders[1].name = "Someone Else"

    assert state.leaders[1].name == "Arthur"
