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
    meta = create_game(tmp_path, "Third Campaign")

    assert meta.slug == "third-campaign"
    assert meta.turn_number == 1  # GameState.turn_number's own real default
    assert meta.kingdom_count == 0

    listed = list_games(tmp_path)
    assert len(listed) == 1
    assert listed[0].name == "Third Campaign"


def test_create_game_with_duplicate_name_raises(tmp_path):
    create_game(tmp_path, "Third Campaign")
    with pytest.raises(DuplicateGameNameError):
        create_game(tmp_path, "Third Campaign")


def test_create_game_slugifies_distinct_names_differently(tmp_path):
    create_game(tmp_path, "Game One")
    create_game(tmp_path, "Game Two")
    assert {g.slug for g in list_games(tmp_path)} == {"game-one", "game-two"}


def test_open_game_round_trips_the_real_state(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    _, state = open_game(tmp_path, meta.slug)
    assert isinstance(state, GameState)
    assert state.kingdoms == {}


def test_open_game_missing_slug_raises(tmp_path):
    with pytest.raises(GameNotFoundError):
        open_game(tmp_path, "does-not-exist")


def test_save_game_refreshes_meta_from_the_real_state(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    _, state = open_game(tmp_path, meta.slug)
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.turn_number = 3

    updated = save_game(tmp_path, meta.slug, state)

    assert updated.kingdom_count == 1
    assert updated.turn_number == 3
    assert updated.name == "Third Campaign"  # name/created_at survive, not overwritten

    _, reloaded = open_game(tmp_path, meta.slug)
    assert reloaded.turn_number == 3
    assert 1 in reloaded.kingdoms


def test_delete_game_removes_it_from_the_list(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    delete_game(tmp_path, meta.slug)
    assert list_games(tmp_path) == []


def test_delete_game_missing_slug_raises(tmp_path):
    with pytest.raises(GameNotFoundError):
        delete_game(tmp_path, "does-not-exist")


def test_delete_game_rejects_a_path_traversal_slug(tmp_path):
    # Bug fix: game_dir(root, slug) used to be a bare `root / slug` with
    # no validation -- Flask's own <slug> URL converter does not reject
    # ".." as a path segment, so POST /games/../delete used to reach
    # delete_game(root, "..") and shutil.rmtree() the *parent* of the
    # configured games root in full. Confirmed directly against a real
    # sibling directory before this fix existed.
    root = tmp_path / "games"
    root.mkdir()
    create_game(root, "Real Game")
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    (sibling / "important.txt").write_text("do not delete me")

    with pytest.raises(GameNotFoundError):
        delete_game(root, "..")

    assert sibling.is_dir()
    assert (sibling / "important.txt").read_text() == "do not delete me"
    assert len(list_games(root)) == 1


@pytest.mark.parametrize(
    "malicious_slug",
    ["..", "../escaped", "/etc", "a/b", "a\\b", "", "UPPER", "has space", "semi;colon"],
)
def test_game_dir_rejects_anything_not_shaped_like_a_real_slug(tmp_path, malicious_slug):
    from ak_engine.webapp.games import game_dir

    with pytest.raises(GameNotFoundError):
        game_dir(tmp_path, malicious_slug)


def test_game_dir_accepts_every_real_slugify_output(tmp_path):
    from ak_engine.webapp.games import game_dir

    for name in ("Third Campaign", "Game One", "G", "A--B", "Café del Rey"):
        meta = create_game(tmp_path, name)
        assert game_dir(tmp_path, meta.slug) == tmp_path / meta.slug


def test_list_games_skips_a_directory_with_no_real_meta_json(tmp_path):
    # A stray/corrupt directory shouldn't take down the whole list screen.
    (tmp_path / "not-a-game").mkdir()
    create_game(tmp_path, "Real Game")

    listed = list_games(tmp_path)

    assert len(listed) == 1
    assert listed[0].name == "Real Game"


def test_list_games_orders_newest_first(tmp_path):
    create_game(tmp_path, "First")
    create_game(tmp_path, "Second")

    listed = list_games(tmp_path)

    assert [g.name for g in listed] == ["Second", "First"]
