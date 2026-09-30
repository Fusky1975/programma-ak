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
    assert "Nessuna partita ancora creata".encode() in response.data


def test_games_list_shows_created_games(tmp_path):
    create_game(tmp_path, "Terza Campagna")
    client = _client(tmp_path)

    response = client.get("/")

    assert "Terza Campagna".encode() in response.data


def test_create_game_via_form_persists_it(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games", data={"name": "Nuova Partita"}, follow_redirects=True)

    assert response.status_code == 200
    assert [g.name for g in list_games(tmp_path)] == ["Nuova Partita"]
    assert "Nuova Partita".encode() in response.data


def test_create_game_with_blank_name_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games", data={"name": "   "}, follow_redirects=True)

    assert response.status_code == 200
    assert list_games(tmp_path) == []
    assert "Inserisci un nome".encode() in response.data


def test_create_game_duplicate_name_shows_an_error(tmp_path):
    create_game(tmp_path, "Terza Campagna")
    client = _client(tmp_path)

    response = client.post("/games", data={"name": "Terza Campagna"}, follow_redirects=True)

    assert response.status_code == 200
    assert len(list_games(tmp_path)) == 1
    assert "Esiste già una partita".encode("utf-8") in response.data


def test_delete_game_via_form_removes_it(tmp_path):
    meta = create_game(tmp_path, "Terza Campagna")
    client = _client(tmp_path)

    response = client.post(f"/games/{meta.slug}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert list_games(tmp_path) == []


def test_delete_unknown_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/non-esiste/delete", follow_redirects=True)

    assert response.status_code == 200
    assert "Partita non trovata".encode() in response.data


def test_font_size_base_is_at_least_18px_in_the_stylesheet(tmp_path):
    # The interface's own stated requirement -- guard it with a real test
    # rather than trusting the CSS was never edited down.
    client = _client(tmp_path)

    response = client.get("/static/style.css")

    assert response.status_code == 200
    css = response.data.decode("utf-8")
    assert "--font-size-base: 18px" in css
