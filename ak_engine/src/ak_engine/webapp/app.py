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

from ak_engine.models.advanced_ability import ADVANCED_ABILITY_NAME, AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ARMY_TYPE_NAME, ArmyType
from ak_engine.models.discovery import DISCOVERY_NAME, Discovery, sorted_kingdom_discoveries
from ak_engine.models.enums import ABILITY_NAME, Ability
from ak_engine.models.feature import FEATURE_TYPE_NAMES, Feature, FeatureType
from ak_engine.models.game_state import ArmyState, BlackmailClaim, LeaderState, ProvinceState
from ak_engine.models.game_type import GameType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.magic_feature import MAGIC_FEATURE_NAME, MagicFeature
from ak_engine.models.map import TERRAIN_NAME, HexCoord, Terrain
from ak_engine.models.monster import MONSTER_NAMES, Monster, MonsterEngagementState
from ak_engine.models.office import OFFICE_NAME, Office
from ak_engine.models.power import POWER_NAME, Power
from ak_engine.models.race import RACE_NAME, Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import TEMPER_NAME, Temper
from ak_engine.models.treasure import GOLD_HOARD_DISPLAY_NAME, TREASURE_NAME, Treasure
from ak_engine.turn.combat import QUALITY_NAME, Quality
from ak_engine.turn.office_holder import ALL_OFFICES, ARMY_RANKED_OFFICES
from ak_engine.turn.race_titles import RACE_TITLE_OFFICE
from ak_engine.turn.sea_transport import board_army, disembark_army
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
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.diplomacy import set_relation
from ak_engine.turn.encounter import MonsterTalkReply
from ak_engine.webapp.diplomacy_orders import InvalidDiplomacyOrderError, set_turn_diplomacy_orders
from ak_engine.webapp.kingdom_create import (
    NoProvinceAtCoordError,
    ProvinceAlreadyAHomeError,
    ProvinceAlreadyOwnedError,
    create_kingdom,
)
from ak_engine.webapp.kingdom_delete import KingdomHasEmperorError, delete_kingdom
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


def _parse_king_form_fields(form) -> tuple[str, Race, Alignment, Temper, dict[Ability, int]]:
    """The "name/race/alignment/temper/4-point talent allocation" fields
    every post-world King-creation form submits (rulebook [2.1]) --
    shared by ``kingdom_create()`` and ``province_kingdom_create()``
    (Phase 1027/1029), the two entry points for creating a brand-new
    Kingdom in an already-created world. Raises ``ValueError`` with a
    user-facing message on the first invalid field, so each caller can
    just redirect with ``error=str(exc)`` to whichever screen it owns.
    """

    name = form.get("name", "").strip()
    if not name:
        raise ValueError("Please enter a King's name.")
    try:
        race = Race[form.get("race", "")]
    except KeyError:
        raise ValueError("Please choose a valid race.")
    if race not in PLAYABLE_RACES:
        raise ValueError("Kings may only be Human, Elven, Dwarven, or Orcish.")
    try:
        alignment = Alignment[form.get("alignment", "")]
    except KeyError:
        raise ValueError("Please choose a valid alignment.")
    if alignment not in PLAYABLE_ALIGNMENTS:
        raise ValueError("Kings may only be Divine, Good, Druidic, Neutral, Pagan, Evil, or Undead.")
    try:
        temper = Temper[form.get("temper", "")]
    except KeyError:
        raise ValueError("Please choose a valid Temper.")

    talent_allocation: dict[Ability, int] = {}
    for ability in Ability:
        raw_points = form.get(f"talent_{ability.name}", "0").strip()
        try:
            points = int(raw_points) if raw_points else 0
        except ValueError:
            raise ValueError("Talent points must be whole numbers.") from None
        if points < 0 or points > MAX_POINTS_PER_ABILITY:
            raise ValueError(f"Each Ability can have at most {MAX_POINTS_PER_ABILITY} starting talent points.")
        if points:
            talent_allocation[ability] = points
    if sum(talent_allocation.values()) != MAX_TALENT_POINTS:
        raise ValueError(f"Please distribute exactly {MAX_TALENT_POINTS} starting talent points.")

    return name, race, alignment, temper, talent_allocation


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
    Discovery: DISCOVERY_NAME,
    AdvancedAbility: ADVANCED_ABILITY_NAME,
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

    @app.post("/games/<slug>/rename")
    def games_rename(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        name = request.form.get("name", "").strip()
        if not name:
            return redirect(url_for("games_list", error="Please enter a game name."))
        # Renames the display name only -- the slug (and its on-disk
        # directory) stays fixed, so every existing bookmark/link into
        # this game keeps working. save_game()'s own meta_overrides is
        # the one real primitive for this (create_game() already uses it
        # for the initial name); no new games.py code needed.
        save_game(root, slug, state, meta_overrides={"name": name})
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
            races=PLAYABLE_RACES,
            alignments=PLAYABLE_ALIGNMENTS,
            tempers=list(Temper),
            abilities=list(Ability),
            max_talent_points=MAX_TALENT_POINTS,
            max_points_per_ability=MAX_POINTS_PER_ABILITY,
            game_types=list(GameType),
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/kingdoms/new")
    def kingdom_create(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        try:
            name, race, alignment, temper, talent_allocation = _parse_king_form_fields(request.form)
        except ValueError as exc:
            return redirect(url_for("world_setup", slug=slug, error=str(exc)))

        try:
            x = int(request.form.get("home_x", ""))
            y = int(request.form.get("home_y", ""))
        except ValueError:
            return redirect(url_for("world_setup", slug=slug, error="Home coordinates must be whole numbers."))

        try:
            create_kingdom(
                state,
                name=name,
                race=race,
                alignment=alignment,
                temper=temper,
                talent_allocation=talent_allocation,
                coord=HexCoord(x, y),
            )
        except NoProvinceAtCoordError:
            return redirect(
                url_for(
                    "world_setup",
                    slug=slug,
                    error=f"({x}, {y}) has no province -- create it first, or pick an existing one.",
                )
            )
        except ProvinceAlreadyOwnedError as exc:
            return redirect(
                url_for("world_setup", slug=slug, error=f"({x}, {y}) is already owned by {exc.owner_name}.")
            )
        except ProvinceAlreadyAHomeError:
            return redirect(
                url_for("world_setup", slug=slug, error=f"({x}, {y}) is already another Kingdom's Home province.")
            )
        save_game(root, slug, state)
        return redirect(url_for("world_setup", slug=slug))

    @app.get("/games/<slug>/provinces/<int:x>/<int:y>/kingdoms/new")
    def province_kingdom_new(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        coord = HexCoord(x, y)
        province = state.provinces.get(coord)
        if province is None:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))
        if province.owner_kingdom_id is not None:
            return redirect(
                url_for(
                    "province_edit",
                    slug=slug,
                    x=x,
                    y=y,
                    error=f"({x}, {y}) is already owned by {state.kingdoms[province.owner_kingdom_id].name}.",
                )
            )
        if any(kingdom.home_province == coord for kingdom in state.kingdoms.values()):
            return redirect(
                url_for(
                    "province_edit", slug=slug, x=x, y=y, error=f"({x}, {y}) is already another Kingdom's Home province."
                )
            )
        return render_template(
            "kingdom_new.html",
            meta=meta,
            coord=coord,
            races=PLAYABLE_RACES,
            alignments=PLAYABLE_ALIGNMENTS,
            tempers=list(Temper),
            abilities=list(Ability),
            max_talent_points=MAX_TALENT_POINTS,
            max_points_per_ability=MAX_POINTS_PER_ABILITY,
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>/kingdoms/new")
    def province_kingdom_create(slug: str, x: int, y: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _create_error(message: str):
            return redirect(url_for("province_kingdom_new", slug=slug, x=x, y=y, error=message))

        try:
            name, race, alignment, temper, talent_allocation = _parse_king_form_fields(request.form)
        except ValueError as exc:
            return _create_error(str(exc))

        try:
            create_kingdom(
                state,
                name=name,
                race=race,
                alignment=alignment,
                temper=temper,
                talent_allocation=talent_allocation,
                coord=HexCoord(x, y),
            )
        except NoProvinceAtCoordError:
            return redirect(url_for("provinces_list", slug=slug, error="Province not found."))
        except ProvinceAlreadyOwnedError as exc:
            return redirect(
                url_for(
                    "province_edit", slug=slug, x=x, y=y, error=f"({x}, {y}) is already owned by {exc.owner_name}."
                )
            )
        except ProvinceAlreadyAHomeError:
            return redirect(
                url_for(
                    "province_edit",
                    slug=slug,
                    x=x,
                    y=y,
                    error=f"({x}, {y}) is already another Kingdom's Home province.",
                )
            )
        save_game(root, slug, state)
        return redirect(url_for("province_edit", slug=slug, x=x, y=y))

    @app.get("/games/<slug>/kingdoms/<int:kingdom_id>")
    def kingdom_edit(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        kingdom = state.kingdoms.get(kingdom_id)
        if kingdom is None:
            return redirect(url_for("world_setup", slug=slug, error="Kingdom not found."))
        owned_discoveries = sorted_kingdom_discoveries(kingdom.discoveries)
        return render_template(
            "kingdom_edit.html",
            meta=meta,
            state=state,
            kingdom=kingdom,
            races=PLAYABLE_RACES,
            alignments=PLAYABLE_ALIGNMENTS,
            discoveries=owned_discoveries,
            available_discoveries=[d for d in Discovery if d not in kingdom.discoveries],
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/kingdoms/<int:kingdom_id>")
    def kingdom_save(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        kingdom = state.kingdoms.get(kingdom_id)
        if kingdom is None:
            return redirect(url_for("world_setup", slug=slug, error="Kingdom not found."))

        def _edit_error(message: str):
            return redirect(url_for("kingdom_edit", slug=slug, kingdom_id=kingdom_id, error=message))

        name = request.form.get("name", "").strip()
        if not name:
            return _edit_error("Please enter a Kingdom name.")
        try:
            race = Race[request.form.get("race", "")]
        except KeyError:
            return _edit_error("Please choose a valid race.")
        if race not in PLAYABLE_RACES:
            return _edit_error("Kingdoms may only be Human, Elven, Dwarven, or Orcish.")
        try:
            alignment = Alignment[request.form.get("alignment", "")]
        except KeyError:
            return _edit_error("Please choose a valid alignment.")
        if alignment not in PLAYABLE_ALIGNMENTS:
            return _edit_error("Kingdoms may only be Divine, Good, Druidic, Neutral, Pagan, Evil, or Undead.")
        try:
            treasury = int(request.form.get("treasury", ""))
        except ValueError:
            return _edit_error("Treasury must be a whole number.")
        try:
            account_number = int(request.form.get("account_number", ""))
        except ValueError:
            return _edit_error("Account number must be a whole number.")

        kingdom.name = name
        kingdom.race = race
        kingdom.alignment = alignment
        kingdom.treasury = treasury
        kingdom.account_number = account_number
        kingdom.king_title_prefix = request.form.get("king_title_prefix", "").strip()
        kingdom.king_title_suffix = request.form.get("king_title_suffix", "").strip()
        save_game(root, slug, state)
        return redirect(url_for("kingdom_edit", slug=slug, kingdom_id=kingdom_id))

    @app.post("/games/<slug>/kingdoms/<int:kingdom_id>/status")
    def kingdom_status_save(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        kingdom = state.kingdoms.get(kingdom_id)
        if kingdom is None:
            return redirect(url_for("world_setup", slug=slug, error="Kingdom not found."))

        def _edit_error(message: str):
            return redirect(url_for("kingdom_edit", slug=slug, kingdom_id=kingdom_id, error=message))

        def _int_field(field: str) -> int:
            raw = request.form.get(field, "").strip()
            return int(raw) if raw else 0

        try:
            treasury_raid_attempts_this_turn = _int_field("treasury_raid_attempts_this_turn")
            valhalla_visit_count = _int_field("valhalla_visit_count")
        except ValueError:
            return _edit_error("Status values must be whole numbers.")

        def _blackmail_claim(prefix: str) -> BlackmailClaim | None:
            leader_raw = request.form.get(f"{prefix}_spy_leader_id", "").strip()
            kingdom_raw = request.form.get(f"{prefix}_spy_kingdom_id", "").strip()
            amount_raw = request.form.get(f"{prefix}_amount", "").strip()
            if not leader_raw and not kingdom_raw and not amount_raw:
                return None
            if not leader_raw or not kingdom_raw or not amount_raw:
                raise ValueError("every field of a Blackmail claim is required once any one is set")
            spy_leader_id = int(leader_raw)
            spy_kingdom_id = int(kingdom_raw)
            amount = int(amount_raw)
            if spy_leader_id not in state.leaders:
                raise KeyError("spy leader")
            if spy_kingdom_id not in state.kingdoms:
                raise KeyError("spy kingdom")
            return BlackmailClaim(spy_leader_id=spy_leader_id, spy_kingdom_id=spy_kingdom_id, amount=amount)

        try:
            pending_blackmail = _blackmail_claim("pending")
            active_blackmail = _blackmail_claim("active")
        except ValueError:
            return _edit_error("A Blackmail claim needs its Spy, Spy's Kingdom, and Amount all set.")
        except KeyError:
            return _edit_error("Please choose a valid Spy and Spy's Kingdom for the Blackmail claim.")

        kingdom.treasury_raid_attempts_this_turn = treasury_raid_attempts_this_turn
        kingdom.valhalla_visit_count = valhalla_visit_count
        kingdom.pending_blackmail = pending_blackmail
        kingdom.active_blackmail = active_blackmail
        save_game(root, slug, state)
        return redirect(url_for("kingdom_edit", slug=slug, kingdom_id=kingdom_id))

    @app.post("/games/<slug>/kingdoms/<int:kingdom_id>/delete")
    def kingdom_delete(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if kingdom_id not in state.kingdoms:
            return redirect(url_for("world_setup", slug=slug, error="Kingdom not found."))
        try:
            delete_kingdom(state, kingdom_id)
        except KingdomHasEmperorError:
            return redirect(
                url_for("world_setup", slug=slug, error="This Kingdom is the crowned Emperor and can't be deleted.")
            )
        save_game(root, slug, state)
        return redirect(url_for("world_setup", slug=slug))

    @app.post("/games/<slug>/kingdoms/<int:kingdom_id>/discoveries/new")
    def kingdom_discovery_create(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        kingdom = state.kingdoms.get(kingdom_id)
        if kingdom is None:
            return redirect(url_for("world_setup", slug=slug, error="Kingdom not found."))
        try:
            discovery = Discovery[request.form.get("discovery", "")]
        except KeyError:
            return redirect(
                url_for("kingdom_edit", slug=slug, kingdom_id=kingdom_id, error="Please choose a valid Discovery.")
            )
        kingdom.discoveries.add(discovery)
        save_game(root, slug, state)
        return redirect(url_for("kingdom_edit", slug=slug, kingdom_id=kingdom_id))

    @app.post("/games/<slug>/kingdoms/<int:kingdom_id>/discoveries/<discovery_name>/delete")
    def kingdom_discovery_delete(slug: str, kingdom_id: int, discovery_name: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        kingdom = state.kingdoms.get(kingdom_id)
        if kingdom is not None:
            try:
                kingdom.discoveries.discard(Discovery[discovery_name])
            except KeyError:
                pass
        save_game(root, slug, state)
        return redirect(url_for("kingdom_edit", slug=slug, kingdom_id=kingdom_id))

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

    @app.post("/games/<slug>/world/emperor")
    def world_emperor_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _setup_error(message: str):
            return redirect(url_for("world_setup", slug=slug, error=message))

        emperor_raw = request.form.get("emperor_kingdom_id", "").strip()
        emperor_kingdom_id: int | None
        if emperor_raw:
            try:
                emperor_kingdom_id = int(emperor_raw)
            except ValueError:
                return _setup_error("Please choose a valid World Emperor.")
            if emperor_kingdom_id not in state.kingdoms:
                return _setup_error("Please choose a valid World Emperor.")
        else:
            emperor_kingdom_id = None

        vote_turn_raw = request.form.get("last_emperor_vote_turn", "").strip()
        last_emperor_vote_turn: int | None
        if vote_turn_raw:
            try:
                last_emperor_vote_turn = int(vote_turn_raw)
            except ValueError:
                return _setup_error("Last Emperor Vote Turn must be a whole number.")
        else:
            last_emperor_vote_turn = None

        state.emperor_kingdom_id = emperor_kingdom_id
        state.last_emperor_vote_turn = last_emperor_vote_turn
        save_game(root, slug, state)
        return redirect(url_for("world_setup", slug=slug))

    @app.post("/games/<slug>/world/header")
    def world_header_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _setup_error(message: str):
            return redirect(url_for("world_setup", slug=slug, error=message))

        game_number_raw = request.form.get("game_number", "").strip()
        try:
            game_number = int(game_number_raw) if game_number_raw else 1
        except ValueError:
            return _setup_error("Game Number must be a whole number.")

        try:
            game_type = _optional_enum(GameType, request.form.get("game_type", ""))
        except KeyError:
            return _setup_error("Please choose a valid Game Type.")

        miscwrit_raw = request.form.get("miscwrit", "").strip()
        try:
            miscwrit = int(miscwrit_raw) if miscwrit_raw else 2
        except ValueError:
            return _setup_error("Miscwrit must be a whole number.")

        gdday_raw = request.form.get("gdday", "").strip()
        try:
            gdday = int(gdday_raw) if gdday_raw else 1
        except ValueError:
            return _setup_error("Due Day must be a whole number.")

        state.game_number = game_number
        state.game_type = game_type
        state.miscwrit = miscwrit
        state.gdday = gdday
        save_game(root, slug, state)
        return redirect(url_for("world_setup", slug=slug))

    @app.get("/games/<slug>/provinces")
    def provinces_list(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        provinces = sorted(state.provinces.values(), key=lambda p: (p.coord.y, p.coord.x))
        leaders_by_coord: dict[HexCoord, list] = {}
        for leader in state.leaders.values():
            leaders_by_coord.setdefault(leader.location, []).append(leader)
        armies_by_coord: dict[HexCoord, list] = {}
        for army in state.armies.values():
            armies_by_coord.setdefault(army.location, []).append(army)
        features_by_coord: dict[HexCoord, list] = {}
        for feature in state.features.values():
            features_by_coord.setdefault(feature.coord, []).append(feature)
        return render_template(
            "world_provinces.html",
            meta=meta,
            state=state,
            provinces=provinces,
            hex_map=build_hex_map(state) if provinces else None,
            leaders_by_coord=leaders_by_coord,
            armies_by_coord=armies_by_coord,
            features_by_coord=features_by_coord,
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

    @app.post("/games/<slug>/world/resize")
    def world_resize(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _resize_error(message: str):
            return redirect(url_for("provinces_list", slug=slug, error=message))

        try:
            new_width = int(request.form.get("new_width", ""))
            new_height = int(request.form.get("new_height", ""))
        except ValueError:
            return _resize_error("New width and height must be whole numbers.")

        old_width, old_height = state.board_width, state.board_height
        # Growing only -- shrinking would need to decide what happens to
        # any Kingdom's Home, Army, Leader, or Feature sitting in the
        # removed area (the same crash-risk question province_delete()
        # already answers one province at a time); refused outright here
        # rather than guessed at. Delete provinces individually first if
        # a smaller map is really wanted.
        if new_width < old_width or new_height < old_height:
            return _resize_error(
                f"Can't shrink the map (currently {old_width}x{old_height}) -- delete provinces "
                "individually first if you want a smaller map."
            )

        try:
            terrain = Terrain[request.form.get("terrain", "")]
        except KeyError:
            return _resize_error("Please choose a valid terrain.")
        try:
            race = Race[request.form.get("race", "")]
        except KeyError:
            return _resize_error("Please choose a valid race.")

        for y in range(new_height):
            for x in range(new_width):
                if x < old_width and y < old_height:
                    continue  # already within the old bounds -- any hole there is the GM's own earlier choice, not ours to fill
                coord = HexCoord(x, y)
                if coord not in state.provinces:
                    state.add_province(ProvinceState(coord=coord, terrain=terrain, race=race))
        state.board_width = new_width
        state.board_height = new_height
        save_game(root, slug, state)
        return redirect(url_for("provinces_list", slug=slug))

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
            leaders=state.leaders_at(HexCoord(x, y)),
            armies=state.armies_at(HexCoord(x, y)),
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

        owner_raw = request.form.get("owner_kingdom_id", "").strip()
        owner_kingdom_id: int | None
        if owner_raw:
            try:
                owner_kingdom_id = int(owner_raw)
            except ValueError:
                return _edit_error("Please choose a valid Owner.")
            if owner_kingdom_id not in state.kingdoms:
                return _edit_error("Please choose a valid Owner.")
        else:
            owner_kingdom_id = None

        name_raw = request.form.get("name", "").strip()

        province.terrain = terrain
        province.race = race
        province.tax = tax
        province.recruit_type_1 = recruit_type_1
        province.recruit_type_2 = recruit_type_2
        province.owner_kingdom_id = owner_kingdom_id
        province.name = name_raw or None
        save_game(root, slug, state)
        return redirect(url_for("province_edit", slug=slug, x=x, y=y))

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>/effects")
    def province_effects_save(slug: str, x: int, y: int):
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

        def _optional_terrain(field: str) -> Terrain | None:
            raw = request.form.get(field, "")
            return Terrain[raw] if raw else None

        try:
            terrain_override = _optional_terrain("terrain_override")
            illusory_terrain = _optional_terrain("illusory_terrain")
        except KeyError:
            return _edit_error("Please choose a valid terrain.")

        def _int_field(field: str) -> int:
            raw = request.form.get(field, "").strip()
            return int(raw) if raw else 0

        try:
            tax_modifier_percent = _int_field("tax_modifier_percent")
            scar_terrain_gold_reduction = _int_field("scar_terrain_gold_reduction")
            earthquake_flat_reduction = _int_field("earthquake_flat_reduction")
            mine_gold_bonus = _int_field("mine_gold_bonus")
            mine_find_attempts = _int_field("mine_find_attempts")
        except ValueError:
            return _edit_error("Effect values must be whole numbers.")

        contested_by_raw = request.form.get("contested_by_kingdom_id", "").strip()
        contested_by_kingdom_id: int | None
        if contested_by_raw:
            try:
                contested_by_kingdom_id = int(contested_by_raw)
            except ValueError:
                return _edit_error("Please choose a valid Contested-By Kingdom.")
            if contested_by_kingdom_id not in state.kingdoms:
                return _edit_error("Please choose a valid Contested-By Kingdom.")
        else:
            contested_by_kingdom_id = None

        contested_from_x_raw = request.form.get("contested_from_x", "").strip()
        contested_from_y_raw = request.form.get("contested_from_y", "").strip()
        contested_from_coord: HexCoord | None
        if contested_from_x_raw or contested_from_y_raw:
            try:
                contested_from_coord = HexCoord(int(contested_from_x_raw), int(contested_from_y_raw))
            except ValueError:
                return _edit_error("Contested-From Coordinate needs both x and y as whole numbers.")
        else:
            contested_from_coord = None

        province.terrain_override = terrain_override
        province.tax_modifier_percent = tax_modifier_percent
        province.illusory_terrain = illusory_terrain
        province.illusory_terrain_enhanced = "illusory_terrain_enhanced" in request.form
        province.scar_terrain_gold_reduction = scar_terrain_gold_reduction
        province.earthquake_flat_reduction = earthquake_flat_reduction
        province.illusory_fog_active = "illusory_fog_active" in request.form
        province.plague_active = "plague_active" in request.form
        province.is_island = "is_island" in request.form
        province.mine_gold_bonus = mine_gold_bonus
        province.mine_find_attempts = mine_find_attempts
        province.contested_by_kingdom_id = contested_by_kingdom_id
        province.contested_from_coord = contested_from_coord
        save_game(root, slug, state)
        return redirect(url_for("province_edit", slug=slug, x=x, y=y))

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>/exploration")
    def province_exploration_save(slug: str, x: int, y: int):
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

        explored_percent_by_kingdom: dict[int, int] = {}
        for kingdom_id in state.kingdoms:
            raw = request.form.get(f"explored_{kingdom_id}", "").strip()
            try:
                percent = int(raw) if raw else 0
            except ValueError:
                return _edit_error("Exploration percentages must be whole numbers.")
            if not 0 <= percent <= 100:
                return _edit_error("Exploration percentages must be 0-100.")
            if percent:
                explored_percent_by_kingdom[kingdom_id] = percent

        province.explored_percent_by_kingdom = explored_percent_by_kingdom
        save_game(root, slug, state)
        return redirect(url_for("province_edit", slug=slug, x=x, y=y))

    @app.post("/games/<slug>/provinces/<int:x>/<int:y>/recruitment")
    def province_recruitment_save(slug: str, x: int, y: int):
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

        recruited_this_turn: dict[ArmyType, int] = {}
        for army_type in ArmyType:
            raw = request.form.get(f"recruited_{army_type.name}", "").strip()
            try:
                count = int(raw) if raw else 0
            except ValueError:
                return _edit_error("Recruited counts must be whole numbers.")
            if count < 0:
                return _edit_error("Recruited counts can't be negative.")
            if count:
                recruited_this_turn[army_type] = count

        province.recruited_this_turn = recruited_this_turn
        province.recruit_locked_this_turn = "recruit_locked_this_turn" in request.form
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
            items=state.items_held_by(leader_id),
            treasures=list(Treasure),
            advanced_abilities=sorted(leader.advanced_abilities, key=lambda a: a.name),
            available_advanced_abilities=[a for a in AdvancedAbility if a not in leader.advanced_abilities],
            skill_abilities=list(Ability),
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

        # A King's own kingdom_id is locked to his own leader_id (the
        # project-wide "King resolves directly" convention, e.g.
        # parser/gw_world.py's own docstring) -- leader_edit.html never
        # offers the Kingdom field for a King, but guard it here too in
        # case of a direct POST, rather than trusting the template alone.
        if leader.is_king:
            kingdom_id = leader.kingdom_id
        else:
            kingdom_id_raw = request.form.get("kingdom_id", "").strip()
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

        leader.name = name
        leader.race = race
        leader.alignment = alignment
        leader.temper = temper
        leader.sex = sex
        leader.kingdom_id = kingdom_id
        leader.location = HexCoord(x, y)
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/effects")
    def leader_effects_save(slug: str, leader_id: int):
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

        raw = request.form.get("phantasmal_armies_level", "").strip()
        try:
            phantasmal_armies_level = int(raw) if raw else 0
        except ValueError:
            return _edit_error("Phantasmal Armies Level must be a whole number.")

        target_raw = request.form.get("clairvoyance_cast_target", "").strip()
        clairvoyance_cast_target: int | None
        if target_raw:
            try:
                clairvoyance_cast_target = int(target_raw)
            except ValueError:
                return _edit_error("Please choose a valid Clairvoyance Target.")
            if clairvoyance_cast_target not in state.leaders:
                return _edit_error("Please choose a valid Clairvoyance Target.")
        else:
            clairvoyance_cast_target = None

        leader.phantasmal_armies_level = phantasmal_armies_level
        leader.oratory_boosted_this_turn = "oratory_boosted_this_turn" in request.form
        leader.mystic_winds_active = "mystic_winds_active" in request.form
        leader.clairvoyance_cast_target = clairvoyance_cast_target
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/history")
    def leader_history_save(slug: str, leader_id: int):
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

        birth_x_raw = request.form.get("birth_x", "").strip()
        birth_y_raw = request.form.get("birth_y", "").strip()
        birth_x: int | None
        birth_y: int | None
        if birth_x_raw or birth_y_raw:
            try:
                birth_x = int(birth_x_raw)
                birth_y = int(birth_y_raw)
            except ValueError:
                return _edit_error("Birth Coordinate needs both x and y as whole numbers.")
        else:
            birth_x = None
            birth_y = None

        hire_turn_raw = request.form.get("hire_turn", "").strip()
        try:
            hire_turn = int(hire_turn_raw) if hire_turn_raw else 0
        except ValueError:
            return _edit_error("Hire Turn must be a whole number.")

        leader.birth_x = birth_x
        leader.birth_y = birth_y
        leader.is_starting_companion = "is_starting_companion" in request.form
        leader.hire_turn = hire_turn
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/status")
    def leader_status_save(slug: str, leader_id: int):
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

        attempts_raw = request.form.get("assassination_guild_attempts", "").strip()
        try:
            assassination_guild_attempts = int(attempts_raw) if attempts_raw else 0
        except ValueError:
            return _edit_error("Assassins Guild Attempts must be a whole number.")

        exponent_raw = request.form.get("unpaid_blackmail_penalty_exponent", "").strip()
        try:
            unpaid_blackmail_penalty_exponent = int(exponent_raw) if exponent_raw else 0
        except ValueError:
            return _edit_error("Unpaid Blackmail Penalty Exponent must be a whole number.")

        double_agent_raw = request.form.get("double_agent_hired_by_kingdom_id", "").strip()
        double_agent_hired_by_kingdom_id: int | None
        if double_agent_raw:
            try:
                double_agent_hired_by_kingdom_id = int(double_agent_raw)
            except ValueError:
                return _edit_error("Please choose a valid Double Agent Hirer.")
            if double_agent_hired_by_kingdom_id not in state.kingdoms:
                return _edit_error("Please choose a valid Double Agent Hirer.")
        else:
            double_agent_hired_by_kingdom_id = None

        clairvoyance_watchers: set[int] = set()
        for raw_id in request.form.getlist("clairvoyance_watchers"):
            try:
                watcher_id = int(raw_id)
            except ValueError:
                return _edit_error("Please choose valid Clairvoyance Watchers.")
            if watcher_id not in state.kingdoms:
                return _edit_error("Please choose valid Clairvoyance Watchers.")
            clairvoyance_watchers.add(watcher_id)

        valhalla_active_turn_raw = request.form.get("valhalla_active_turn", "").strip()
        try:
            valhalla_active_turn = int(valhalla_active_turn_raw) if valhalla_active_turn_raw else None
        except ValueError:
            return _edit_error("Valhalla Active Turn must be a whole number.")

        valhalla_allowed_phase_count_raw = request.form.get("valhalla_allowed_phase_count", "").strip()
        try:
            valhalla_allowed_phase_count = int(valhalla_allowed_phase_count_raw) if valhalla_allowed_phase_count_raw else None
        except ValueError:
            return _edit_error("Valhalla Allowed Phase Count must be a whole number.")

        valhalla_fixed_item_id_raw = request.form.get("valhalla_fixed_item_id", "").strip()
        try:
            valhalla_fixed_item_id = int(valhalla_fixed_item_id_raw) if valhalla_fixed_item_id_raw else None
        except ValueError:
            return _edit_error("Valhalla Fixed Item ID must be a whole number.")

        leader.is_comatose = "is_comatose" in request.form
        leader.is_royal_heir = "is_royal_heir" in request.form
        leader.assassination_guild_attempts = assassination_guild_attempts
        leader.unpaid_blackmail_penalty_exponent = unpaid_blackmail_penalty_exponent
        leader.double_agent_hired_by_kingdom_id = double_agent_hired_by_kingdom_id
        leader.clairvoyance_watchers = clairvoyance_watchers
        leader.valhalla_active_turn = valhalla_active_turn
        leader.valhalla_allowed_phase_count = valhalla_allowed_phase_count
        leader.valhalla_fixed_item_id = valhalla_fixed_item_id
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
        # Phase 1030: a delete triggered from a specific province's own
        # "Leaders Here" panel (world_provinces.html's own per-coordinate
        # link) returns to that same province instead of the Kings &
        # Heroes list -- query params, not route params, so the existing
        # leader_edit.html delete form (no params) keeps its own
        # unchanged redirect target.
        return_x = request.args.get("return_x")
        return_y = request.args.get("return_y")
        if return_x is not None and return_y is not None:
            try:
                return redirect(url_for("province_edit", slug=slug, x=int(return_x), y=int(return_y)))
            except ValueError:
                pass
        if request.args.get("return_to") == "provinces":
            return redirect(url_for("provinces_list", slug=slug))
        return redirect(url_for("leaders_list", slug=slug))

    @app.post("/games/<slug>/leaders/<int:leader_id>/items/new")
    def leader_item_create(slug: str, leader_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if leader_id not in state.leaders:
            return redirect(url_for("leaders_list", slug=slug, error="Hero not found."))

        def _create_error(message: str):
            return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id, error=message))

        try:
            treasure = Treasure[request.form.get("treasure", "")]
        except KeyError:
            return _create_error("Please choose a valid Treasure.")

        charges_raw = request.form.get("charges", "").strip()
        try:
            charges = int(charges_raw) if charges_raw else 0
        except ValueError:
            return _create_error("Charges must be a whole number.")

        # GameState.add_item() (models/item.py, Phase 140): a faithful,
        # already-built primitive this project's own module docstring
        # explicitly anticipated "a scenario-scripted grant" caller for --
        # this is that caller.
        state.add_item(treasure, leader_id, charges)
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/items/<int:item_id>/delete")
    def leader_item_delete(slug: str, leader_id: int, item_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        state.remove_item(item_id)
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/advanced-abilities/new")
    def leader_advanced_ability_create(slug: str, leader_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        leader = state.leaders.get(leader_id)
        if leader is None:
            return redirect(url_for("leaders_list", slug=slug, error="Hero not found."))
        try:
            ability = AdvancedAbility[request.form.get("advanced_ability", "")]
        except KeyError:
            return redirect(
                url_for("leader_edit", slug=slug, leader_id=leader_id, error="Please choose a valid Advanced Ability.")
            )
        leader.advanced_abilities.add(ability)
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/advanced-abilities/<ability_name>/delete")
    def leader_advanced_ability_delete(slug: str, leader_id: int, ability_name: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        leader = state.leaders.get(leader_id)
        if leader is not None:
            try:
                leader.advanced_abilities.discard(AdvancedAbility[ability_name])
            except KeyError:
                pass
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/skills")
    def leader_skills_save(slug: str, leader_id: int):
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

        # 15 (skill, aptitude) pairs, each 0-9 -- the real CTBOTH.PAS
        # `skillrange = 0..9` bound (models/kingdom.py SkillTable's own
        # Phase 21 docstring), not an invented limit.
        raw_values = [0] * 31
        for ability in Ability:
            try:
                skill = int(request.form.get(f"skill_{ability.name}", ""))
                aptitude = int(request.form.get(f"aptitude_{ability.name}", ""))
            except ValueError:
                return _edit_error(f"{display_name(ability)}: skill/aptitude must be whole numbers.")
            if not (0 <= skill <= 9) or not (0 <= aptitude <= 9):
                return _edit_error(f"{display_name(ability)}: skill/aptitude must be 0-9.")
            raw_values[ability.value * 2] = skill
            raw_values[ability.value * 2 + 1] = aptitude

        try:
            trailing_value = int(request.form.get("trailing_value", ""))
        except ValueError:
            return _edit_error("The trailing value must be a whole number.")
        raw_values[30] = trailing_value

        leader.skills = SkillTable(raw_values=raw_values)
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

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
        # Phase 1033: the Commander dropdown only lists Heroes currently
        # co-located with this Army (mirroring the real Pick_Up rule,
        # turn/plan_dispatch.py) -- but if the Army's own current
        # commander has since moved away, he's still included (flagged
        # "not here" in the template) so an unrelated save of this form
        # doesn't silently clear a pre-existing, still-valid assignment.
        commanders = list(state.leaders_at(army.location))
        current_commander = state.leaders.get(army.commanded_by) if army.commanded_by is not None else None
        if current_commander is not None and current_commander not in commanders:
            commanders.append(current_commander)
        # Candidate carriers for the Transport panel: every other Army
        # co-located with this one -- turn/sea_transport.py board_army()
        # itself rejects anything illegal (wrong cargo type, full
        # capacity, not actually a carrier), so the dropdown doesn't need
        # to pre-filter by ArmyType; a rejected attempt just surfaces
        # board_army()'s own False return as a plain error message.
        carrier_candidates = [a for a in state.armies_at(army.location) if a.army_id != army.army_id]
        current_carrier = state.armies.get(army.transported_by) if army.transported_by is not None else None
        return render_template(
            "army_edit.html",
            meta=meta,
            state=state,
            army=army,
            army_types=list(ArmyType),
            qualities=list(Quality),
            commanders=commanders,
            carrier_candidates=carrier_candidates,
            current_carrier=current_carrier,
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

        commanded_by_raw = request.form.get("commanded_by", "").strip()
        commanded_by: int | None
        if commanded_by_raw:
            try:
                commanded_by = int(commanded_by_raw)
            except ValueError:
                return _edit_error("Please choose a valid Commander.")
            if commanded_by not in state.leaders:
                return _edit_error("Please choose a valid Commander.")
            # Only enforce "must already be at this Army's own location"
            # (the real Pick_Up rule, turn/plan_dispatch.py) when this
            # save actually assigns a *new* commander -- an unrelated
            # field edit must not fail just because an already-set
            # commander has since moved away (see army_edit() above).
            if commanded_by != army.commanded_by and state.leaders[commanded_by].location != HexCoord(x, y):
                return _edit_error("A Commander must already be at this Army's own location.")
        else:
            commanded_by = None

        army.army_type = army_type
        army.quality = quality
        army.kingdom_id = kingdom_id
        army.location = HexCoord(x, y)
        army.commanded_by = commanded_by
        army.is_skeletal = request.form.get("is_skeletal") == "on"
        army.plague_immune = request.form.get("plague_immune") == "on"
        save_game(root, slug, state)
        return redirect(url_for("army_edit", slug=slug, army_id=army_id))

    @app.post("/games/<slug>/armies/<int:army_id>/effects")
    def army_effects_save(slug: str, army_id: int):
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

        raw = request.form.get("movement_points", "").strip()
        try:
            movement_points = int(raw) if raw else 0
        except ValueError:
            return _edit_error("Movement Points must be a whole number.")

        flood_x_raw = request.form.get("flood_dams_exempt_at_x", "").strip()
        flood_y_raw = request.form.get("flood_dams_exempt_at_y", "").strip()
        flood_dams_exempt_at: HexCoord | None
        if flood_x_raw or flood_y_raw:
            try:
                flood_dams_exempt_at = HexCoord(int(flood_x_raw), int(flood_y_raw))
            except ValueError:
                return _edit_error("Flood Dams Exempt At needs both coordinates as whole numbers.")
        else:
            flood_dams_exempt_at = None

        army.movement_points = movement_points
        army.unhireable_this_turn = "unhireable_this_turn" in request.form
        army.march_bonus_applied_this_turn = "march_bonus_applied_this_turn" in request.form
        army.naval_bonus_applied_this_turn = "naval_bonus_applied_this_turn" in request.form
        army.march_table_bonus_applied_this_turn = "march_table_bonus_applied_this_turn" in request.form
        army.flood_dams_exempt_at = flood_dams_exempt_at
        save_game(root, slug, state)
        return redirect(url_for("army_edit", slug=slug, army_id=army_id))

    @app.post("/games/<slug>/armies/<int:army_id>/board")
    def army_board(slug: str, army_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if army_id not in state.armies:
            return redirect(url_for("armies_list", slug=slug, error="Army not found."))

        def _edit_error(message: str):
            return redirect(url_for("army_edit", slug=slug, army_id=army_id, error=message))

        try:
            carrier_id = int(request.form.get("carrier_id", ""))
        except ValueError:
            return _edit_error("Please choose a valid Carrier.")
        if carrier_id not in state.armies:
            return _edit_error("Please choose a valid Carrier.")

        # board_army() (turn/sea_transport.py) is the one real primitive
        # for this -- it already enforces every real legality rule
        # (co-located, not already boarded, carrier has room, cargo type
        # is actually eligible for this carrier). A GM editor doesn't get
        # the Druidic caster capacity bonuses (those are a spell-cast
        # context this action has none of), so both default to False.
        if not board_army(state, army_id, carrier_id):
            return _edit_error(
                "Can't board there -- not co-located with that Army, already boarded elsewhere, "
                "or illegal/full for that Carrier."
            )
        save_game(root, slug, state)
        return redirect(url_for("army_edit", slug=slug, army_id=army_id))

    @app.post("/games/<slug>/armies/<int:army_id>/disembark")
    def army_disembark(slug: str, army_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        disembark_army(state, army_id)
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
        # Phase 1031: same optional "return to this province" redirect
        # leader_delete() already supports (query params, not route
        # params, so army_edit.html's own existing delete form -- no
        # params -- keeps its own unchanged redirect target).
        return_x = request.args.get("return_x")
        return_y = request.args.get("return_y")
        if return_x is not None and return_y is not None:
            try:
                return redirect(url_for("province_edit", slug=slug, x=int(return_x), y=int(return_y)))
            except ValueError:
                pass
        if request.args.get("return_to") == "provinces":
            return redirect(url_for("provinces_list", slug=slug))
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
            talk_replies=list(MonsterTalkReply),
            guardian_states=list(MonsterEngagementState),
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
        feature.looted = request.form.get("looted") == "on"
        feature.magically_hidden = request.form.get("magically_hidden") == "on"
        save_game(root, slug, state)
        return redirect(url_for("feature_edit", slug=slug, feature_id=feature_id))

    @app.post("/games/<slug>/features/<int:feature_id>/status")
    def feature_status_save(slug: str, feature_id: int):
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

        deal_raw = request.form.get("pending_deal_leader_id", "").strip()
        pending_deal_leader_id: int | None
        if deal_raw:
            try:
                pending_deal_leader_id = int(deal_raw)
            except ValueError:
                return _edit_error("Please choose a valid Pending Deal Leader.")
            if pending_deal_leader_id not in state.leaders:
                return _edit_error("Please choose a valid Pending Deal Leader.")
        else:
            pending_deal_leader_id = None

        discovered_by_kingdom: dict[int, int] = {}
        for kingdom_id in state.kingdoms:
            raw = request.form.get(f"discovered_{kingdom_id}", "").strip()
            try:
                level = int(raw) if raw else 0
            except ValueError:
                return _edit_error("Discovery levels must be whole numbers.")
            if not 0 <= level <= 3:
                return _edit_error("Discovery levels must be 0-3.")
            if level:
                discovered_by_kingdom[kingdom_id] = level

        reply_raw = request.form.get("guardian_talk_reply_id", "").strip()
        guardian_talk_reply_id: int | None
        if reply_raw:
            try:
                guardian_talk_reply_id = MonsterTalkReply[reply_raw].value
            except KeyError:
                return _edit_error("Please choose a valid Guardian Talk Reply.")
        else:
            guardian_talk_reply_id = None

        guardian_state_raw = request.form.get("guardian_state", "").strip()
        if guardian_state_raw:
            try:
                guardian_state = MonsterEngagementState[guardian_state_raw]
            except KeyError:
                return _edit_error("Please choose a valid Guardian State.")
        else:
            guardian_state = MonsterEngagementState.MERCENARY

        power_used_raw = request.form.get("power_used_turn", "").strip()
        power_used_turn: int | None
        if power_used_raw:
            try:
                power_used_turn = int(power_used_raw)
            except ValueError:
                return _edit_error("Power Used Turn must be a whole number.")
        else:
            power_used_turn = None

        feature.pending_deal_leader_id = pending_deal_leader_id
        feature.discovered_by_kingdom = discovered_by_kingdom
        feature.guardian_talk_reply_id = guardian_talk_reply_id
        feature.guardian_state = guardian_state
        feature.power_used_turn = power_used_turn
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
        # Phase 1032: same optional "return to this province" redirect
        # leader_delete()/army_delete() already support.
        return_x = request.args.get("return_x")
        return_y = request.args.get("return_y")
        if return_x is not None and return_y is not None:
            try:
                return redirect(url_for("province_edit", slug=slug, x=int(return_x), y=int(return_y)))
            except ValueError:
                pass
        if request.args.get("return_to") == "provinces":
            return redirect(url_for("provinces_list", slug=slug))
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
            relations=[DiplomaticRelation.ENEMY, DiplomaticRelation.NEUTRAL, DiplomaticRelation.ALLIED],
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

    @app.post("/games/<slug>/turns/diplomacy/set-relation")
    def turns_diplomacy_set_relation(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _edit_error(message: str):
            return redirect(url_for("turns_diplomacy", slug=slug, error=message))

        try:
            kingdom_a = int(request.form.get("kingdom_a", ""))
            kingdom_b = int(request.form.get("kingdom_b", ""))
        except ValueError:
            return _edit_error("Please choose two valid Kingdoms.")
        if kingdom_a not in state.kingdoms or kingdom_b not in state.kingdoms:
            return _edit_error("Please choose two valid Kingdoms.")
        if kingdom_a == kingdom_b:
            return _edit_error("A Kingdom can't have a relation with itself.")

        # Only the 3 relations rulebook [8] itself describes -- TEAMED is
        # deliberately not offered here (turn/diplomacy.py's own module
        # docstring: never produced by apply_treat_orders(), and this
        # project has deferred whether a GM editor should be able to
        # write it at all pending the user's own confirmation).
        try:
            relation = DiplomaticRelation[request.form.get("relation", "")]
        except KeyError:
            return _edit_error("Please choose a valid relation.")
        if relation not in (DiplomaticRelation.ENEMY, DiplomaticRelation.NEUTRAL, DiplomaticRelation.ALLIED):
            return _edit_error("Please choose a valid relation.")

        # turn/diplomacy.py set_relation(): the same primitive
        # apply_treat_orders() itself uses, so a direct GM override looks
        # identical to one reached through real Treat/Break Treat orders
        # (allied_kingdoms/diplomatic_relations_since stay in sync either way).
        set_relation(state, kingdom_a, kingdom_b, relation)
        save_game(root, slug, state)
        return redirect(url_for("turns_diplomacy", slug=slug))

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
