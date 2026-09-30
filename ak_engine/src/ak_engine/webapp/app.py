"""Flask app factory and routes.

Phase 1 wires the "My Games" screen -- list, create, delete -- as the
entry point every later flow hangs off of. Phase 2 adds the player/King
roster screen every game's "Open" link now leads to. Later phases add
optional-titles/world-creation/editor/turn-cycle routes on top of this
same app.

**The interface is English throughout**, matching the game itself: every
composer in ``report/turn_report.py`` already renders English prose
(``SAY.PAS``/``.X2``-sourced), so an Italian GM screen sitting in front
of English reports would be its own, needless inconsistency.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from ak_engine.models.alignment import Alignment
from ak_engine.models.race import Race
from ak_engine.webapp.games import (
    DuplicateGameNameError,
    GameNotFoundError,
    create_game,
    delete_game,
    game_dir,
    list_games,
    open_game,
)
from ak_engine.webapp.players import (
    MAX_PLAYERS,
    MIN_PLAYERS,
    PLAYABLE_RACES,
    PlayerNotFoundError,
    RosterFullError,
    add_player,
    list_players,
    remove_player,
)

DEFAULT_GAMES_ROOT = Path.home() / "ak_games"


def create_app(games_root: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["GAMES_ROOT"] = games_root if games_root is not None else DEFAULT_GAMES_ROOT

    @app.get("/")
    def games_list():
        root: Path = app.config["GAMES_ROOT"]
        return render_template("games_list.html", games=list_games(root), error=request.args.get("error"))

    @app.post("/games")
    def games_create():
        root: Path = app.config["GAMES_ROOT"]
        name = request.form.get("name", "").strip()
        if not name:
            return redirect(url_for("games_list", error="Please enter a game name."))
        try:
            create_game(root, name)
        except DuplicateGameNameError:
            return redirect(url_for("games_list", error=f'A game named "{name}" already exists.'))
        return redirect(url_for("games_list"))

    @app.post("/games/<slug>/delete")
    def games_delete(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            delete_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        return redirect(url_for("games_list"))

    @app.get("/games/<slug>/players")
    def players_setup(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, _ = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        players = list_players(game_dir(root, slug))
        return render_template(
            "player_setup.html",
            meta=meta,
            players=players,
            playable_races=PLAYABLE_RACES,
            alignments=list(Alignment),
            min_players=MIN_PLAYERS,
            max_players=MAX_PLAYERS,
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/players")
    def players_add(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        name = request.form.get("name", "").strip()
        race_name = request.form.get("race", "")
        alignment_name = request.form.get("alignment", "")

        if not name:
            return redirect(url_for("players_setup", slug=slug, error="Please enter a King's name."))
        try:
            race = Race[race_name]
        except KeyError:
            return redirect(url_for("players_setup", slug=slug, error="Please choose a valid race."))
        if race not in PLAYABLE_RACES:
            return redirect(
                url_for("players_setup", slug=slug, error="Kings may only be Human, Elven, Dwarven, or Orcish.")
            )
        try:
            alignment = Alignment[alignment_name]
        except KeyError:
            return redirect(url_for("players_setup", slug=slug, error="Please choose a valid alignment."))

        try:
            add_player(game_dir(root, slug), name, race, alignment)
        except RosterFullError:
            return redirect(
                url_for("players_setup", slug=slug, error=f"A game can have at most {MAX_PLAYERS} Kings.")
            )
        return redirect(url_for("players_setup", slug=slug))

    @app.post("/games/<slug>/players/<int:player_id>/delete")
    def players_remove(slug: str, player_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        try:
            remove_player(game_dir(root, slug), player_id)
        except PlayerNotFoundError:
            return redirect(url_for("players_setup", slug=slug, error="King not found."))
        return redirect(url_for("players_setup", slug=slug))

    return app
