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


def test_a_game_saved_before_a_field_existed_loads_with_that_field_at_its_default(tmp_path):
    # Dataclasses here use slots: a field added after a game was saved is *unset* on the loaded object, which would
    # break a running game on the next update. Simulated by removing the fields of the objects before saving.
    from ak_engine.models.feature import Feature, FeatureType
    from ak_engine.models.map import HexCoord
    from ak_engine.models.rumor import Rumor, RumorContent
    from ak_engine.models.enums import ActionCode
    from ak_engine.models.game_state import GameState

    state = GameState()
    feature = Feature(feature_id=1, coord=HexCoord(1, 1), kind=FeatureType.DUNGEON)
    state.add_feature(feature)
    rumor = Rumor(1, 1, 1, ActionCode.EXPLORE, RumorContent.ITEM, 1, True, HexCoord(1, 1))
    state.add_rumor(rumor)
    del feature.pending_deal_ready_turn
    del rumor.phase_label
    del state.emperor_best_hope_leader_id
    path = tmp_path / "old.pkl"
    save_game_state(state, path)

    loaded = load_game_state(path)

    assert loaded.features[1].pending_deal_ready_turn is None
    assert loaded.rumors[1].phase_label is None
    assert loaded.emperor_best_hope_leader_id is None
