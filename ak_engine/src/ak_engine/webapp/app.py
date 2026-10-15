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

from flask import Flask, Response, redirect, render_template, request, url_for

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ARMY_TYPE_NAME, ArmyType
from ak_engine.models.enums import ABILITY_NAME, Ability
from ak_engine.models.feature import FEATURE_TYPE_NAMES, Feature, FeatureType
from ak_engine.models.game_state import ArmyState, LeaderState, ProvinceState
from ak_engine.models.magic_feature import MAGIC_FEATURE_NAME, MagicFeature
from ak_engine.models.map import TERRAIN_NAME, HexCoord, Terrain
from ak_engine.models.monster import MONSTER_NAMES, Monster
from ak_engine.models.office import OFFICE_NAME, Office
from ak_engine.models.power import POWER_NAME, Power
from ak_engine.models.race import RACE_NAME, Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import TEMPER_NAME, Temper
from ak_engine.models.treasure import GOLD_HOARD_DISPLAY_NAME, TREASURE_NAME, Treasure
from ak_engine.turn.combat import QUALITY_NAME, Quality
from ak_engine.turn.office_holder import ALL_OFFICES, ARMY_RANKED_OFFICES
from ak_engine.turn.race_titles import RACE_TITLE_OFFICE
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
from ak_engine.webapp.hex_map import build_hex_map, kingdom_color
from ak_engine.webapp.players import (
    MAX_PLAYERS,
    MIN_PLAYERS,
    PLAYABLE_ALIGNMENTS,
    PLAYABLE_RACES,
    PlayerNotFoundError,
    RosterFullError,
    add_player,
    list_players,
    remove_player,
)
from ak_engine.webapp.diplomacy_orders import InvalidDiplomacyOrderError, set_turn_diplomacy_orders
from ak_engine.webapp.reports import turn_zero_report
from ak_engine.webapp.turn_processing import (
    InvalidMoveFileError,
    load_turn_report,
    load_turn_xk_file,
    process_and_save_current_turn,
    processed_turn_numbers,
    remove_uploaded_move_file,
    save_uploaded_move_file,
    uploaded_move_files,
)
from ak_engine.webapp.xk_reports import XKExportError, build_xk_file_for_kingdom
from ak_engine.webapp.world_creation import (
    RosterOutOfBoundsError,
    WorldAlreadyCreatedError,
    create_world,
)
from ak_engine.worldgen.king_talent import MAX_POINTS_PER_ABILITY, MAX_TALENT_POINTS
from ak_engine.worldgen.place_map import DEFAULT_HEIGHT, DEFAULT_WIDTH

# The 8 mandatory Imperial Offices (rulebook [10.1]) vs. every other real,
# modeled title the GM may opt in or out of for this game -- see
# GameState.enabled_optional_offices's own docstring for why these are
# the two groups (`report/turn_report.py describe_imperial_office_report()`
# is the consumer this screen's choice feeds).
MANDATORY_OFFICES: tuple[Office, ...] = tuple(o for o in ALL_OFFICES if o.value <= Office.MAGE.value)

# The optional titles, grouped for the GM's own screen: the 7 alignment-
# King titles first (same order as PLAYABLE_ALIGNMENTS), then the 11 race
# titles (RACE_TITLE_OFFICE's own order), then the 4 magic-school titles,
# then every remaining optional title (the terrain-explorer Kings, the
# other merit-based offices, and the 3 army-scoped Royal Titles) last, in
# their existing relative order.
_ALIGNMENT_OPTIONAL_OFFICES: tuple[Office, ...] = (
    Office.DIVINE_KING,
    Office.GOOD_KING,
    Office.DRUID_KING,
    Office.NEUTRAL_KING,
    Office.PAGAN_KING,
    Office.EVIL_KING,
    Office.UNDEAD_KING,
)
_RACE_OPTIONAL_OFFICES: tuple[Office, ...] = tuple(RACE_TITLE_OFFICE.values())
_MAGIC_OPTIONAL_OFFICES: tuple[Office, ...] = (
    Office.ELE_MAGE,
    Office.ILLUS_MAGE,
    Office.NECRO_MAGE,
    Office.PSYCHIC_MAGE,
)
_GROUPED_OPTIONAL_OFFICES = set(_ALIGNMENT_OPTIONAL_OFFICES + _RACE_OPTIONAL_OFFICES + _MAGIC_OPTIONAL_OFFICES)
OPTIONAL_OFFICES: tuple[Office, ...] = (
    _ALIGNMENT_OPTIONAL_OFFICES
    + _RACE_OPTIONAL_OFFICES
    + _MAGIC_OPTIONAL_OFFICES
    + tuple(o for o in ALL_OFFICES if o.value > Office.MAGE.value and o not in _GROUPED_OPTIONAL_OFFICES)
    + ARMY_RANKED_OFFICES
)


def _optional_enum(cls, raw: str):
    """A submitted <select>'s value, as an enum member, or ``None`` for the
    "unset"/"none" blank option every optional field's own template offers.
    """

    return cls[raw] if raw else None


# Every enum this interface renders in a dropdown or table, mapped to this
# project's own curated "real display name" dict (e.g. `models/race.py
# RACE_NAME`: "Elf" not "Elven", "Light Cavalry" not "Lt Cavalry" --
# sourced from the same real game text these models' own reports already
# render). `Alignment` has no such dict of its own, but its member values
# already *are* the real display string (`Alignment.ANTI_HOLY.value ==
# "Anti-Holy"`), so a one-off dict built from that is just as real.
_ENUM_DISPLAY_NAMES: dict[type, dict] = {
    Terrain: TERRAIN_NAME,
    # RACE_NAME's own Race.NO_RACE entry is lowercase ("no race") -- real,
    # sourced prose-fragment text (TREASURE.X2 et al.), correct mid-
    # sentence but not as a standalone dropdown label, so this interface
    # overrides just that one entry rather than title-casing the whole
    # dict (which would also wrongly capitalize "of"/"the" inside a
    # multi-word real name, e.g. Treasure's own gold-hoard names below).
    Race: {**RACE_NAME, Race.NO_RACE: "No Race"},
    ArmyType: ARMY_TYPE_NAME,
    FeatureType: FEATURE_TYPE_NAMES,
    Monster: MONSTER_NAMES,
    # GOLD_HOARD_DISPLAY_NAME overrides TREASURE_NAME's own bare "Hoard"
    # for the 3 gold-hoard tiers -- that module's own docstring confirms
    # TREASURE_NAME's "Hoard" is TREASURE.X2's flavor-name extraction, not
    # what a real ADVENTURE report actually prints ("Large Hoard of Gold").
    Treasure: {**TREASURE_NAME, **GOLD_HOARD_DISPLAY_NAME},
    MagicFeature: MAGIC_FEATURE_NAME,
    Power: POWER_NAME,
    Temper: TEMPER_NAME,
    Alignment: {member: member.value for member in Alignment},
    Ability: ABILITY_NAME,
    Quality: QUALITY_NAME,
}


def display_name(value) -> str:
    """The Jinja filter (``{{ value|display_name }}``) every template uses
    to show an enum member -- this project's own curated name verbatim
    when one covers this exact member (already correctly cased real text,
    e.g. "Large Hoard of Gold"/"Anti-Holy" -- blanket title-casing that
    would wrongly capitalize "of"/produce "Anti Holy"). Falls back to a
    title-cased version of the enum's own identifier for the handful of
    members no curated dict covers (documented gaps in those dicts
    themselves, e.g. `Race.DROW`/`ArmyType.ARTILLERY`) and for enums with
    no curated dict at all (`Sex` -- "Male"/"Female" is already exactly
    right from the bare identifier, so it needs none).
    """

    if value is None:
        return ""
    lookup = _ENUM_DISPLAY_NAMES.get(type(value), {})
    if value in lookup:
        return lookup[value]
    return value.name.replace("_", " ").title()


DEFAULT_GAMES_ROOT = Path.home() / "ak_games"


def create_app(games_root: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["GAMES_ROOT"] = games_root if games_root is not None else DEFAULT_GAMES_ROOT
    app.jinja_env.filters["display_name"] = display_name
    app.jinja_env.globals["kingdom_color"] = kingdom_color

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
            alignments=PLAYABLE_ALIGNMENTS,
            tempers=list(Temper),
            abilities=list(Ability),
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
        if alignment not in PLAYABLE_ALIGNMENTS:
            return redirect(
                url_for(
                    "players_setup",
                    slug=slug,
                    error="Kings may only be Divine, Good, Druidic, Neutral, Pagan, Evil, or Undead.",
                )
            )

        try:
            temper = Temper[request.form.get("temper", "")]
        except KeyError:
            return redirect(url_for("players_setup", slug=slug, error="Please choose a valid Temper."))

        talent_allocation: dict[Ability, int] = {}
        for ability in Ability:
            raw_points = request.form.get(f"talent_{ability.name}", "0").strip()
            try:
                points = int(raw_points) if raw_points else 0
            except ValueError:
                return redirect(url_for("players_setup", slug=slug, error="Talent points must be whole numbers."))
            if points < 0 or points > MAX_POINTS_PER_ABILITY:
                return redirect(
                    url_for(
                        "players_setup",
                        slug=slug,
                        error=f"Each Ability can have at most {MAX_POINTS_PER_ABILITY} starting talent points.",
                    )
                )
            if points:
                talent_allocation[ability] = points
        if sum(talent_allocation.values()) != MAX_TALENT_POINTS:
            return redirect(
                url_for(
                    "players_setup",
                    slug=slug,
                    error=f"Please distribute exactly {MAX_TALENT_POINTS} starting talent points.",
                )
            )

        try:
            add_player(game_dir(root, slug), name, race, alignment, temper, talent_allocation)
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
            hex_map=build_hex_map(state) if provinces else None,
            terrains=list(Terrain),
            races=list(Race),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/provinces/new")
    def province_create(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _create_error(message: str):
            return redirect(url_for("provinces_list", slug=slug, error=message))

        try:
            x = int(request.form.get("x", ""))
            y = int(request.form.get("y", ""))
        except ValueError:
            return _create_error("Coordinates must be whole numbers.")
        coord = HexCoord(x, y)
        if not (0 <= x < state.board_width and 0 <= y < state.board_height):
            return _create_error(f"({x}, {y}) is outside this map's {state.board_width}x{state.board_height} bounds.")
        if coord in state.provinces:
            return _create_error(f"({x}, {y}) already has a province -- edit it instead of recreating it.")

        try:
            terrain = Terrain[request.form.get("terrain", "")]
        except KeyError:
            return _create_error("Please choose a valid terrain.")
        try:
            race = Race[request.form.get("race", "")]
        except KeyError:
            return _create_error("Please choose a valid race.")

        state.add_province(ProvinceState(coord=coord, terrain=terrain, race=race))
        save_game(root, slug, state)
        return redirect(url_for("province_edit", slug=slug, x=x, y=y))

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
            features=state.features_at(HexCoord(x, y)),
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

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>/set-home")
    def province_set_home(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        coord = HexCoord(x, y)
        if coord not in state.provinces:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))

        def _edit_error(message: str):
            return redirect(url_for("province_edit", slug=slug, x=x, y=y, error=message))

        kingdom_id_raw = request.form.get("kingdom_id", "")
        try:
            kingdom_id = int(kingdom_id_raw)
            kingdom = state.kingdoms[kingdom_id]
        except (ValueError, KeyError):
            return _edit_error("Please choose a valid Kingdom.")

        kingdom.home_province = coord
        save_game(root, slug, state)
        return redirect(url_for("province_edit", slug=slug, x=x, y=y))

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>/delete")
    def province_delete(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        coord = HexCoord(x, y)
        if coord not in state.provinces:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))

        def _edit_error(message: str):
            return redirect(url_for("province_edit", slug=slug, x=x, y=y, error=message))

        # Unlike Army/Leader/Feature, a Province has no "Add" counterpart
        # in this editor and several live turn-processing call sites index
        # `state.provinces[coord]` directly for a Kingdom's own Home
        # province or a Leader/Army's own current location (confirmed real
        # invariants, e.g. `turn/rename_province.py`/`turn/recruit_
        # execution.py`'s own docstrings) -- deleting one of those out
        # from under a live game would crash the very next turn processed.
        # Refuse rather than silently corrupt the save.
        if any(kingdom.home_province == coord for kingdom in state.kingdoms.values()):
            return _edit_error("This is a Kingdom's Home province and can't be deleted -- set a different Home first.")
        if state.armies_at(coord):
            return _edit_error("This province has Armies present and can't be deleted -- move or remove them first.")
        if state.leaders_at(coord):
            return _edit_error("This province has Leaders present and can't be deleted -- move or remove them first.")

        for feature in state.features_at(coord):
            state.features.pop(feature.feature_id, None)
        del state.provinces[coord]
        save_game(root, slug, state)
        return redirect(url_for("provinces_list", slug=slug))

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
            races=list(Race),
            alignments=PLAYABLE_ALIGNMENTS,
            tempers=list(Temper),
            sexes=list(Sex),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/leaders/new")
    def leaders_create(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _create_error(message: str):
            return redirect(url_for("leaders_list", slug=slug, error=message))

        name = request.form.get("name", "").strip()
        if not name:
            return _create_error("Please enter a name.")
        try:
            race = Race[request.form.get("race", "")]
        except KeyError:
            return _create_error("Please choose a valid race.")

        try:
            alignment = _optional_enum(Alignment, request.form.get("alignment", ""))
            temper = _optional_enum(Temper, request.form.get("temper", ""))
            sex = _optional_enum(Sex, request.form.get("sex", ""))
        except KeyError:
            return _create_error("Please choose valid values.")
        if alignment is not None and alignment not in PLAYABLE_ALIGNMENTS:
            return _create_error("Please choose valid values.")

        kingdom_id_raw = request.form.get("kingdom_id", "").strip()
        kingdom_id: int | None
        if kingdom_id_raw:
            try:
                kingdom_id = int(kingdom_id_raw)
            except ValueError:
                return _create_error("Please choose a valid Kingdom.")
            if kingdom_id not in state.kingdoms:
                return _create_error("Please choose a valid Kingdom.")
        else:
            kingdom_id = None

        try:
            x = int(request.form.get("location_x", ""))
            y = int(request.form.get("location_y", ""))
        except ValueError:
            return _create_error("Location must be whole numbers.")

        leader_id = state.new_leader_id()
        state.add_leader(
            LeaderState(
                leader_id=leader_id,
                kingdom_id=kingdom_id,
                name=name,
                location=HexCoord(x, y),
                race=race,
                alignment=alignment,
                temper=temper,
                sex=sex,
            )
        )
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

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
            alignments=PLAYABLE_ALIGNMENTS,
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

        try:
            alignment = _optional_enum(Alignment, request.form.get("alignment", ""))
            temper = _optional_enum(Temper, request.form.get("temper", ""))
            sex = _optional_enum(Sex, request.form.get("sex", ""))
        except KeyError:
            return _edit_error("Please choose valid values.")
        if alignment is not None and alignment not in PLAYABLE_ALIGNMENTS:
            return _edit_error("Please choose valid values.")

        leader.name = name
        leader.race = race
        leader.alignment = alignment
        leader.temper = temper
        leader.sex = sex
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/delete")
    def leader_delete(slug: str, leader_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        # A plain dict removal, not GameState.remove_leader(): that method
        # is the real in-game death mechanic (archives into dead_leaders
        # for a future Resurrection, applies the 25% merit death penalty,
        # installs a Royal Heir for a King) -- none of which an editor
        # correcting a mistake should trigger. A stale ArmyState.
        # commanded_by/office_holders pointer left behind here is already
        # the exact same, already-handled condition as a leader who died
        # in battle (report/turn_report.py's own "alive-only" checks).
        state.leaders.pop(leader_id, None)
        save_game(root, slug, state)
        return redirect(url_for("leaders_list", slug=slug))

    @app.get("/games/<slug>/armies")
    def armies_list(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        armies = sorted(
            state.armies.values(),
            key=lambda army: (army.kingdom_id is None, army.kingdom_id or 0, army.location.y, army.location.x),
        )
        return render_template(
            "world_armies.html",
            meta=meta,
            state=state,
            armies=armies,
            army_types=list(ArmyType),
            qualities=list(Quality),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/armies/new")
    def armies_create(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _create_error(message: str):
            return redirect(url_for("armies_list", slug=slug, error=message))

        try:
            army_type = ArmyType[request.form.get("army_type", "")]
        except KeyError:
            return _create_error("Please choose a valid army type.")
        try:
            quality = Quality[request.form.get("quality", "")]
        except KeyError:
            return _create_error("Please choose a valid quality.")

        kingdom_id_raw = request.form.get("kingdom_id", "").strip()
        kingdom_id: int | None
        if kingdom_id_raw:
            try:
                kingdom_id = int(kingdom_id_raw)
            except ValueError:
                return _create_error("Please choose a valid Kingdom.")
            if kingdom_id not in state.kingdoms:
                return _create_error("Please choose a valid Kingdom.")
        else:
            kingdom_id = None

        try:
            x = int(request.form.get("location_x", ""))
            y = int(request.form.get("location_y", ""))
        except ValueError:
            return _create_error("Location must be whole numbers.")

        army_id = state.new_army_id()
        state.add_army(
            ArmyState(
                army_id=army_id,
                kingdom_id=kingdom_id,
                army_type=army_type,
                quality=quality,
                location=HexCoord(x, y),
                movement_points=ARMY_TABLE[army_type].speed,
            )
        )
        save_game(root, slug, state)
        return redirect(url_for("army_edit", slug=slug, army_id=army_id))

    @app.get("/games/<slug>/armies/<int:army_id>")
    def army_edit(slug: str, army_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        army = state.armies.get(army_id)
        if army is None:
            return redirect(url_for("armies_list", slug=slug, error="Army not found."))
        return render_template(
            "army_edit.html",
            meta=meta,
            state=state,
            army=army,
            army_types=list(ArmyType),
            qualities=list(Quality),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/armies/<int:army_id>")
    def army_save(slug: str, army_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        army = state.armies.get(army_id)
        if army is None:
            return redirect(url_for("armies_list", slug=slug, error="Army not found."))

        def _edit_error(message: str):
            return redirect(url_for("army_edit", slug=slug, army_id=army_id, error=message))

        try:
            army_type = ArmyType[request.form.get("army_type", "")]
        except KeyError:
            return _edit_error("Please choose a valid army type.")
        try:
            quality = Quality[request.form.get("quality", "")]
        except KeyError:
            return _edit_error("Please choose a valid quality.")

        kingdom_id_raw = request.form.get("kingdom_id", "").strip()
        kingdom_id: int | None
        if kingdom_id_raw:
            try:
                kingdom_id = int(kingdom_id_raw)
            except ValueError:
                return _edit_error("Please choose a valid Kingdom.")
            if kingdom_id not in state.kingdoms:
                return _edit_error("Please choose a valid Kingdom.")
        else:
            kingdom_id = None

        try:
            x = int(request.form.get("location_x", ""))
            y = int(request.form.get("location_y", ""))
        except ValueError:
            return _edit_error("Location must be whole numbers.")

        army.army_type = army_type
        army.quality = quality
        army.kingdom_id = kingdom_id
        army.location = HexCoord(x, y)
        save_game(root, slug, state)
        return redirect(url_for("army_edit", slug=slug, army_id=army_id))

    @app.post("/games/<slug>/armies/<int:army_id>/delete")
    def army_delete(slug: str, army_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        state.remove_army(army_id)
        save_game(root, slug, state)
        return redirect(url_for("armies_list", slug=slug))

    @app.get("/games/<slug>/features")
    def features_list(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        features = sorted(state.features.values(), key=lambda feature: (feature.coord.y, feature.coord.x))
        return render_template(
            "world_features.html",
            meta=meta,
            state=state,
            features=features,
            hex_map=build_hex_map(state) if state.provinces else None,
            error=request.args.get("error"),
        )

    @app.get("/games/<slug>/features/<int:feature_id>")
    def feature_edit(slug: str, feature_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        feature = state.features.get(feature_id)
        if feature is None:
            return redirect(url_for("features_list", slug=slug, error="Feature not found."))
        return render_template(
            "feature_edit.html",
            meta=meta,
            state=state,
            feature=feature,
            feature_types=list(FeatureType),
            monsters=list(Monster),
            alignments=list(Alignment),
            treasures=list(Treasure),
            magic_locations=list(MagicFeature),
            powers=list(Power),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/features/<int:feature_id>")
    def feature_save(slug: str, feature_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        feature = state.features.get(feature_id)
        if feature is None:
            return redirect(url_for("features_list", slug=slug, error="Feature not found."))

        def _edit_error(message: str):
            return redirect(url_for("feature_edit", slug=slug, feature_id=feature_id, error=message))

        try:
            kind = FeatureType[request.form.get("kind", "")]
        except KeyError:
            return _edit_error("Please choose a valid feature type.")

        try:
            guardian_monster = _optional_enum(Monster, request.form.get("guardian_monster", ""))
            guardian_alignment = _optional_enum(Alignment, request.form.get("guardian_alignment", ""))
            treasure = _optional_enum(Treasure, request.form.get("treasure", ""))
            magic_location = _optional_enum(MagicFeature, request.form.get("magic_location", ""))
            magic_power = _optional_enum(Power, request.form.get("magic_power", ""))
        except KeyError:
            return _edit_error("Please choose valid values.")

        feature.kind = kind
        feature.guardian_monster = guardian_monster
        feature.guardian_alignment = guardian_alignment
        feature.treasure = treasure
        feature.magic_location = magic_location
        feature.magic_power = magic_power
        save_game(root, slug, state)
        return redirect(url_for("feature_edit", slug=slug, feature_id=feature_id))

    @app.post("/games/<slug>/features/<int:feature_id>/delete")
    def feature_delete(slug: str, feature_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        state.features.pop(feature_id, None)
        save_game(root, slug, state)
        return redirect(url_for("features_list", slug=slug))

    @app.get("/games/<slug>/provinces/<int:x>/<int:y>/features/new")
    def feature_new(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        coord = HexCoord(x, y)
        if coord not in state.provinces:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))
        return render_template(
            "feature_new.html",
            meta=meta,
            coord=coord,
            next_feature_id=state.new_feature_id(),
            feature_types=list(FeatureType),
            monsters=list(Monster),
            alignments=list(Alignment),
            treasures=list(Treasure),
            magic_locations=list(MagicFeature),
            powers=list(Power),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>/features/new")
    def feature_create(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        coord = HexCoord(x, y)
        if coord not in state.provinces:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))

        def _create_error(message: str):
            return redirect(url_for("feature_new", slug=slug, x=x, y=y, error=message))

        try:
            kind = FeatureType[request.form.get("kind", "")]
        except KeyError:
            return _create_error("Please choose a valid feature type.")

        try:
            guardian_monster = _optional_enum(Monster, request.form.get("guardian_monster", ""))
            guardian_alignment = _optional_enum(Alignment, request.form.get("guardian_alignment", ""))
            treasure = _optional_enum(Treasure, request.form.get("treasure", ""))
            magic_location = _optional_enum(MagicFeature, request.form.get("magic_location", ""))
            magic_power = _optional_enum(Power, request.form.get("magic_power", ""))
        except KeyError:
            return _create_error("Please choose valid values.")

        feature_id = state.new_feature_id()
        state.add_feature(
            Feature(
                feature_id=feature_id,
                coord=coord,
                kind=kind,
                guardian_monster=guardian_monster,
                guardian_alignment=guardian_alignment,
                treasure=treasure,
                magic_location=magic_location,
                magic_power=magic_power,
            )
        )
        save_game(root, slug, state)
        return redirect(url_for("feature_edit", slug=slug, feature_id=feature_id))

    @app.get("/games/<slug>/turn0")
    def turn_zero_list(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        return render_template("turn_zero_list.html", meta=meta, state=state, error=request.args.get("error"))

    @app.get("/games/<slug>/turn0/<int:kingdom_id>")
    def turn_zero_view(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if kingdom_id not in state.kingdoms:
            return redirect(url_for("turn_zero_list", slug=slug, error="Kingdom not found."))
        return render_template(
            "turn_zero_view.html",
            meta=meta,
            kingdom=state.kingdoms[kingdom_id],
            lines=turn_zero_report(state, kingdom_id),
            error=request.args.get("error"),
        )

    @app.get("/games/<slug>/turn0/<int:kingdom_id>/download")
    def turn_zero_download(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if kingdom_id not in state.kingdoms:
            return redirect(url_for("turn_zero_list", slug=slug, error="Kingdom not found."))
        lines = turn_zero_report(state, kingdom_id)
        kingdom_name = state.kingdoms[kingdom_id].name.replace(" ", "_")
        return Response(
            "\n".join(lines),
            mimetype="text/plain",
            headers={"Content-Disposition": f'attachment; filename="SE_T0_{kingdom_name}.txt"'},
        )

    @app.get("/games/<slug>/turn0/<int:kingdom_id>/download/xk")
    def turn_zero_download_xk(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if kingdom_id not in state.kingdoms:
            return redirect(url_for("turn_zero_list", slug=slug, error="Kingdom not found."))
        try:
            data = build_xk_file_for_kingdom(state, kingdom_id)
        except XKExportError as exc:
            return redirect(url_for("turn_zero_view", slug=slug, kingdom_id=kingdom_id, error=f"Couldn't build the XK file: {exc}"))
        kingdom_name = state.kingdoms[kingdom_id].name.replace(" ", "_")
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="XK_T0_{kingdom_name}.xk"'},
        )

    @app.get("/games/<slug>/turns")
    def turns_hub(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        directory = game_dir(root, slug)
        uploads = uploaded_move_files(directory, state.turn_number, state.kingdoms.keys())
        return render_template(
            "turns_hub.html",
            meta=meta,
            state=state,
            uploads=uploads,
            processed_turns=processed_turn_numbers(directory),
            error=request.args.get("error"),
        )

    @app.get("/games/<slug>/turns/diplomacy")
    def turns_diplomacy(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        return render_template(
            "turns_diplomacy.html",
            meta=meta,
            state=state,
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/turns/diplomacy")
    def turns_diplomacy_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        treat_pairs: set[tuple[int, int]] = set()
        break_pairs: set[tuple[int, int]] = set()
        for issuer_id in state.kingdoms:
            for target_id in state.kingdoms:
                if issuer_id == target_id:
                    continue
                choice = request.form.get(f"order_{issuer_id}_{target_id}", "none")
                if choice == "treat":
                    treat_pairs.add((issuer_id, target_id))
                elif choice == "break":
                    break_pairs.add((issuer_id, target_id))

        try:
            set_turn_diplomacy_orders(state, treat_pairs, break_pairs)
        except InvalidDiplomacyOrderError as exc:
            return redirect(url_for("turns_diplomacy", slug=slug, error=str(exc)))

        save_game(root, slug, state)
        return redirect(url_for("turns_hub", slug=slug))

    @app.post("/games/<slug>/turns/upload")
    def turns_upload(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        upload = request.files.get("move_file")
        if upload is None or not upload.filename:
            return redirect(url_for("turns_hub", slug=slug, error="Please choose a move file to upload."))
        try:
            save_uploaded_move_file(
                game_dir(root, slug), state.turn_number, upload.filename, upload.read(), state.kingdoms.keys()
            )
        except InvalidMoveFileError as exc:
            return redirect(url_for("turns_hub", slug=slug, error=f"{upload.filename}: not a valid move file ({exc})."))
        return redirect(url_for("turns_hub", slug=slug))

    @app.post("/games/<slug>/turns/<int:kingdom_id>/remove")
    def turns_remove_upload(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        remove_uploaded_move_file(game_dir(root, slug), state.turn_number, kingdom_id, state.kingdoms.keys())
        return redirect(url_for("turns_hub", slug=slug))

    @app.post("/games/<slug>/turns/process")
    def turns_process(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if not state.kingdoms:
            return redirect(url_for("turns_hub", slug=slug, error="This game has no world yet."))
        processed_turn_number = state.turn_number
        process_and_save_current_turn(root, slug, state, game_dir(root, slug))
        return redirect(url_for("turn_report_list", slug=slug, turn_number=processed_turn_number))

    @app.get("/games/<slug>/turns/<int:turn_number>/report")
    def turn_report_list(slug: str, turn_number: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if turn_number not in processed_turn_numbers(game_dir(root, slug)):
            return redirect(url_for("turns_hub", slug=slug, error=f"Turn {turn_number} hasn't been processed yet."))
        return render_template(
            "turn_report_list.html", meta=meta, state=state, turn_number=turn_number, error=request.args.get("error")
        )

    @app.get("/games/<slug>/turns/<int:turn_number>/report/<int:kingdom_id>")
    def turn_report_view(slug: str, turn_number: int, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        lines = load_turn_report(game_dir(root, slug), turn_number, kingdom_id)
        if lines is None:
            return redirect(url_for("turn_report_list", slug=slug, turn_number=turn_number, error="Report not found."))
        kingdom_name = state.kingdoms[kingdom_id].name if kingdom_id in state.kingdoms else f"Kingdom #{kingdom_id}"
        return render_template(
            "turn_report_view.html",
            meta=meta,
            turn_number=turn_number,
            kingdom_id=kingdom_id,
            kingdom_name=kingdom_name,
            lines=lines,
            error=request.args.get("error"),
        )

    @app.get("/games/<slug>/turns/<int:turn_number>/report/<int:kingdom_id>/download")
    def turn_report_download(slug: str, turn_number: int, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        lines = load_turn_report(game_dir(root, slug), turn_number, kingdom_id)
        if lines is None:
            return redirect(url_for("turn_report_list", slug=slug, turn_number=turn_number, error="Report not found."))
        kingdom_name = (state.kingdoms[kingdom_id].name if kingdom_id in state.kingdoms else f"Kingdom_{kingdom_id}").replace(" ", "_")
        return Response(
            "\n".join(lines),
            mimetype="text/plain",
            headers={"Content-Disposition": f'attachment; filename="SE_T{turn_number}_{kingdom_name}.txt"'},
        )

    @app.get("/games/<slug>/turns/<int:turn_number>/report/<int:kingdom_id>/download/xk")
    def turn_report_download_xk(slug: str, turn_number: int, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        data = load_turn_xk_file(game_dir(root, slug), turn_number, kingdom_id)
        if data is None:
            return redirect(
                url_for("turn_report_list", slug=slug, turn_number=turn_number, error="XK file not found for this Kingdom.")
            )
        kingdom_name = (state.kingdoms[kingdom_id].name if kingdom_id in state.kingdoms else f"Kingdom_{kingdom_id}").replace(" ", "_")
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="XK_T{turn_number}_{kingdom_name}.xk"'},
        )

    return app
