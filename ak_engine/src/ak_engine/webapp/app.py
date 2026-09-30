"""Flask app factory and routes.

Phase 1 wires the "My Games" screen -- list, create, delete -- as the
entry point every later flow hangs off of. Phase 2 adds the player/King
roster screen every game's "Open" link now leads to. Phase 3 adds the
optional-titles screen. Phase 4 adds "Create World". Later phases add the
world editor and the turn-cycle routes on top of this same app.

**The interface is English throughout**, matching the game itself: every
composer in ``report/turn_report.py`` already renders English prose
(``SAY.PAS``/``.X2``-sourced), so an Italian GM screen sitting in front
of English reports would be its own, needless inconsistency.
"""

from __future__ import annotations

import random
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import OFFICE_NAME, Office
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.turn.office_holder import ALL_OFFICES, ARMY_RANKED_OFFICES
from ak_engine.webapp.games import (
    DuplicateGameNameError,
    GameNotFoundError,
    create_game,
    delete_game,
    game_dir,
    list_games,
    open_game,
    save_game,
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
from ak_engine.webapp.world_creation import (
    RosterOutOfBoundsError,
    WorldAlreadyCreatedError,
    create_world,
)
from ak_engine.worldgen.place_map import DEFAULT_HEIGHT, DEFAULT_WIDTH

# The 8 mandatory Imperial Offices (rulebook [10.1]) vs. every other real,
# modeled title the GM may opt in or out of for this game -- see
# GameState.enabled_optional_offices's own docstring for why these are
# the two groups (`report/turn_report.py describe_imperial_office_report()`
# is the consumer this screen's choice feeds).
MANDATORY_OFFICES: tuple[Office, ...] = tuple(o for o in ALL_OFFICES if o.value <= Office.MAGE.value)
OPTIONAL_OFFICES: tuple[Office, ...] = tuple(o for o in ALL_OFFICES if o.value > Office.MAGE.value) + ARMY_RANKED_OFFICES

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

    @app.get("/games/<slug>/titles")
    def titles_setup(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        enabled = state.enabled_optional_offices
        return render_template(
            "titles_setup.html",
            meta=meta,
            mandatory_offices=MANDATORY_OFFICES,
            optional_offices=OPTIONAL_OFFICES,
            office_name=OFFICE_NAME,
            is_enabled=(lambda office: enabled is None or office in enabled),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/titles")
    def titles_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        try:
            selected = {Office[name] for name in request.form.getlist("office")}
        except KeyError:
            return redirect(url_for("titles_setup", slug=slug, error="Please choose valid titles."))

        state.enabled_optional_offices = selected
        save_game(root, slug, state)
        return redirect(url_for("titles_setup", slug=slug))

    @app.get("/games/<slug>/world")
    def world_setup(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        return render_template(
            "world_setup.html",
            meta=meta,
            state=state,
            player_count=len(list_players(game_dir(root, slug))),
            min_players=MIN_PLAYERS,
            max_players=MAX_PLAYERS,
            default_width=DEFAULT_WIDTH,
            default_height=DEFAULT_HEIGHT,
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/world")
    def world_create(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _parse_int(field: str, default: int) -> int:
            raw = request.form.get(field, "").strip()
            return default if not raw else int(raw)

        try:
            width = _parse_int("width", DEFAULT_WIDTH)
            height = _parse_int("height", DEFAULT_HEIGHT)
            seed = _parse_int("seed", random.randint(1, 2**31 - 1))
        except ValueError:
            return redirect(url_for("world_setup", slug=slug, error="Width, height, and seed must be whole numbers."))
        if width < 1 or height < 1:
            return redirect(url_for("world_setup", slug=slug, error="Width and height must be positive."))

        try:
            create_world(root, slug, width=width, height=height, seed=seed)
        except RosterOutOfBoundsError as exc:
            return redirect(
                url_for(
                    "world_setup",
                    slug=slug,
                    error=f"Need {MIN_PLAYERS}-{MAX_PLAYERS} Kings to create the world "
                    f"(currently {exc.player_count}).",
                )
            )
        except WorldAlreadyCreatedError:
            return redirect(url_for("world_setup", slug=slug, error="This game's world has already been created."))
        return redirect(url_for("world_setup", slug=slug))

    @app.get("/games/<slug>/provinces")
    def provinces_list(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        provinces = sorted(state.provinces.values(), key=lambda p: (p.coord.y, p.coord.x))
        return render_template(
            "world_provinces.html",
            meta=meta,
            state=state,
            provinces=provinces,
            error=request.args.get("error"),
        )

    @app.get("/games/<slug>/provinces/<int:x>/<int:y>")
    def province_edit(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        province = state.provinces.get(HexCoord(x, y))
        if province is None:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))
        return render_template(
            "province_edit.html",
            meta=meta,
            state=state,
            province=province,
            terrains=list(Terrain),
            races=list(Race),
            army_types=list(ArmyType),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>")
    def province_save(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        coord = HexCoord(x, y)
        province = state.provinces.get(coord)
        if province is None:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))

        def _edit_error(message: str):
            return redirect(url_for("province_edit", slug=slug, x=x, y=y, error=message))

        try:
            terrain = Terrain[request.form.get("terrain", "")]
        except KeyError:
            return _edit_error("Please choose a valid terrain.")
        try:
            race = Race[request.form.get("race", "")]
        except KeyError:
            return _edit_error("Please choose a valid race.")

        tax_raw = request.form.get("tax", "").strip()
        try:
            tax = int(tax_raw) if tax_raw else None
        except ValueError:
            return _edit_error("Tax must be a whole number.")

        def _army_type(field: str) -> ArmyType | None:
            raw = request.form.get(field, "")
            return ArmyType[raw] if raw else None

        try:
            recruit_type_1 = _army_type("recruit_type_1")
            recruit_type_2 = _army_type("recruit_type_2")
        except KeyError:
            return _edit_error("Please choose valid recruitable unit types.")

        province.terrain = terrain
        province.race = race
        province.tax = tax
        province.recruit_type_1 = recruit_type_1
        province.recruit_type_2 = recruit_type_2
        save_game(root, slug, state)
        return redirect(url_for("province_edit", slug=slug, x=x, y=y))

    @app.get("/games/<slug>/leaders")
    def leaders_list(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        leaders = sorted(state.leaders.values(), key=lambda leader: (leader.kingdom_id is None, leader.kingdom_id or 0, leader.name))
        return render_template(
            "world_leaders.html",
            meta=meta,
            state=state,
            leaders=leaders,
            error=request.args.get("error"),
        )

    @app.get("/games/<slug>/leaders/<int:leader_id>")
    def leader_edit(slug: str, leader_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        leader = state.leaders.get(leader_id)
        if leader is None:
            return redirect(url_for("leaders_list", slug=slug, error="Hero not found."))
        return render_template(
            "leader_edit.html",
            meta=meta,
            state=state,
            leader=leader,
            races=list(Race),
            alignments=list(Alignment),
            tempers=list(Temper),
            sexes=list(Sex),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/leaders/<int:leader_id>")
    def leader_save(slug: str, leader_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        leader = state.leaders.get(leader_id)
        if leader is None:
            return redirect(url_for("leaders_list", slug=slug, error="Hero not found."))

        def _edit_error(message: str):
            return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id, error=message))

        name = request.form.get("name", "").strip()
        if not name:
            return _edit_error("Please enter a name.")
        try:
            race = Race[request.form.get("race", "")]
        except KeyError:
            return _edit_error("Please choose a valid race.")

        def _optional_enum(cls, field: str):
            raw = request.form.get(field, "")
            return cls[raw] if raw else None

        try:
            alignment = _optional_enum(Alignment, "alignment")
            temper = _optional_enum(Temper, "temper")
            sex = _optional_enum(Sex, "sex")
        except KeyError:
            return _edit_error("Please choose valid values.")

        leader.name = name
        leader.race = race
        leader.alignment = alignment
        leader.temper = temper
        leader.sex = sex
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    return app
