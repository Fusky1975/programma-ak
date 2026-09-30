"""Tests for webapp/games.py -- the local, folder-per-game registry
(Phase 1 of the GM interface)."""

from __future__ import annotations

import pytest

from ak_engine.models.game_state import GameState, KingdomState
from ak_engine.models.alignment import Alignment
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.webapp.games import (
    DuplicateGameNameError,
    GameNotFoundError,
    create_game,
    delete_game,
    list_games,
    open_game,
    save_game,
)


def test_list_games_on_a_fresh_root_is_empty(tmp_path):
    assert list_games(tmp_path) == []


def test_create_game_makes_it_listable(tmp_path):
    meta = create_game(tmp_path, "Terza Campagna")

    assert meta.slug == "terza-campagna"
    assert meta.turn_number == 1  # GameState.turn_number's own real default
    assert meta.kingdom_count == 0

    listed = list_games(tmp_path)
    assert len(listed) == 1
    assert listed[0].name == "Terza Campagna"


def test_create_game_with_duplicate_name_raises(tmp_path):
    create_game(tmp_path, "Terza Campagna")
    with pytest.raises(DuplicateGameNameError):
        create_game(tmp_path, "Terza Campagna")


def test_create_game_slugifies_distinct_names_differently(tmp_path):
    create_game(tmp_path, "Partita Uno")
    create_game(tmp_path, "Partita Due")
    assert {g.slug for g in list_games(tmp_path)} == {"partita-uno", "partita-due"}


def test_open_game_round_trips_the_real_state(tmp_path):
    meta = create_game(tmp_path, "Terza Campagna")
    _, state = open_game(tmp_path, meta.slug)
    assert isinstance(state, GameState)
    assert state.kingdoms == {}


def test_open_game_missing_slug_raises(tmp_path):
    with pytest.raises(GameNotFoundError):
        open_game(tmp_path, "non-esiste")


def test_save_game_refreshes_meta_from_the_real_state(tmp_path):
    meta = create_game(tmp_path, "Terza Campagna")
    _, state = open_game(tmp_path, meta.slug)
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.turn_number = 3

    updated = save_game(tmp_path, meta.slug, state)

    assert updated.kingdom_count == 1
    assert updated.turn_number == 3
    assert updated.name == "Terza Campagna"  # name/created_at survive, not overwritten

    _, reloaded = open_game(tmp_path, meta.slug)
    assert reloaded.turn_number == 3
    assert 1 in reloaded.kingdoms


def test_delete_game_removes_it_from_the_list(tmp_path):
    meta = create_game(tmp_path, "Terza Campagna")
    delete_game(tmp_path, meta.slug)
    assert list_games(tmp_path) == []


def test_delete_game_missing_slug_raises(tmp_path):
    with pytest.raises(GameNotFoundError):
        delete_game(tmp_path, "non-esiste")


def test_list_games_skips_a_directory_with_no_real_meta_json(tmp_path):
    # A stray/corrupt directory shouldn't take down the whole list screen.
    (tmp_path / "not-a-game").mkdir()
    create_game(tmp_path, "Vera Partita")

    listed = list_games(tmp_path)

    assert len(listed) == 1
    assert listed[0].name == "Vera Partita"


def test_list_games_orders_newest_first(tmp_path):
    create_game(tmp_path, "Prima")
    create_game(tmp_path, "Seconda")

    listed = list_games(tmp_path)

    assert [g.name for g in listed] == ["Seconda", "Prima"]
