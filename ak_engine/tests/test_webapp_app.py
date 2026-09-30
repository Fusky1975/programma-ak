"""Tests for webapp/app.py -- the Flask routes (Phase 1: game registry
screen only; later phases add their own route tests)."""

from __future__ import annotations

from ak_engine.webapp.app import create_app
from ak_engine.webapp.games import create_game, list_games


def _client(tmp_path):
    app = create_app(games_root=tmp_path)
    app.testing = True
    return app.test_client()


def test_games_list_empty_state(tmp_path):
    client = _client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert b"No games created yet" in response.data


def test_games_list_shows_created_games(tmp_path):
    create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get("/")

    assert b"Third Campaign" in response.data


def test_create_game_via_form_persists_it(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games", data={"name": "New Game"}, follow_redirects=True)

    assert response.status_code == 200
    assert [g.name for g in list_games(tmp_path)] == ["New Game"]
    assert b"New Game" in response.data


def test_create_game_with_blank_name_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games", data={"name": "   "}, follow_redirects=True)

    assert response.status_code == 200
    assert list_games(tmp_path) == []
    assert b"Please enter a game name" in response.data


def test_create_game_duplicate_name_shows_an_error(tmp_path):
    create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post("/games", data={"name": "Third Campaign"}, follow_redirects=True)

    assert response.status_code == 200
    assert len(list_games(tmp_path)) == 1
    assert b"already exists" in response.data


def test_delete_game_via_form_removes_it(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(f"/games/{meta.slug}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert list_games(tmp_path) == []


def test_delete_unknown_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_font_size_base_is_at_least_18px_in_the_stylesheet(tmp_path):
    # The interface's own stated requirement -- guard it with a real test
    # rather than trusting the CSS was never edited down.
    client = _client(tmp_path)

    response = client.get("/static/style.css")

    assert response.status_code == 200
    css = response.data.decode("utf-8")
    assert "--font-size-base: 18px" in css


def test_interface_is_declared_english(tmp_path):
    # The game and its reports are English throughout (SAY.PAS/.X2-sourced
    # prose) -- the GM interface must not be the one Italian screen in
    # front of it.
    client = _client(tmp_path)

    response = client.get("/")

    assert b'lang="en"' in response.data


def test_games_list_open_link_leads_to_player_setup(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get("/")

    assert f"/games/{meta.slug}/players".encode() in response.data


def test_player_setup_shows_below_minimum_warning_on_a_fresh_game(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/players")

    assert response.status_code == 200
    assert b"0 of 2-12 Kings added" in response.data


def test_player_setup_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/players", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_add_king_via_form_persists_it(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(
        f"/games/{meta.slug}/players",
        data={"name": "Bram Ironhand", "race": "HUMAN", "alignment": "GOOD"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Bram Ironhand" in response.data
    assert b"1 of 2-12 Kings added" in response.data


def test_add_king_with_blank_name_shows_an_error_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(
        f"/games/{meta.slug}/players",
        data={"name": "   ", "race": "HUMAN", "alignment": "GOOD"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please enter a King" in response.data


def test_add_king_with_a_non_playable_race_shows_an_error(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(
        f"/games/{meta.slug}/players",
        data={"name": "Smaug", "race": "DRAGONS", "alignment": "EVIL"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Human, Elven, Dwarven, or Orcish" in response.data
    assert b"Smaug" not in response.data


def test_remove_king_via_form_removes_it(tmp_path):
    # A name that doesn't overlap the Add-King form's own placeholder text
    # ("e.g. Aldric the Bold"), so this only matches the roster listing.
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    client.post(f"/games/{meta.slug}/players", data={"name": "Bram Ironhand", "race": "HUMAN", "alignment": "GOOD"})

    response = client.post(f"/games/{meta.slug}/players/0/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Bram Ironhand" not in response.data
    assert b"0 of 2-12 Kings added" in response.data


def test_remove_unknown_king_shows_an_error_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(f"/games/{meta.slug}/players/99/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"King not found" in response.data


def test_player_setup_shows_ok_status_within_bounds(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    client.post(f"/games/{meta.slug}/players", data={"name": "Aldric", "race": "HUMAN", "alignment": "GOOD"})
    client.post(f"/games/{meta.slug}/players", data={"name": "Elara", "race": "ELVEN", "alignment": "NEUTRAL"})

    response = client.get(f"/games/{meta.slug}/players")

    assert b"2 of 2-12 Kings added" in response.data
    assert b"Ready to continue" in response.data
