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
import tempfile
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from ak_engine.models.advanced_ability import ADVANCED_ABILITY_NAME, AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ARMY_TYPE_NAME, ArmyType
from ak_engine.models.discovery import DISCOVERY_NAME, Discovery, sorted_kingdom_discoveries
from ak_engine.models.enums import ABILITY_NAME, Ability, ActionCode, Maneuver, Spell
from ak_engine.models.feature import FEATURE_TYPE_NAMES, Feature, FeatureType
from ak_engine.models.game_state import ArmyState, BlackmailClaim, LeaderState, ProvinceState, RaceTitleTally
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
from ak_engine.turn.office_holder import (
    ALL_OFFICES,
    ARMY_RANKED_OFFICES,
    RANKED_OFFICES,
    leader_office_merit_points,
    resolve_army_office_holder,
    resolve_office_holder,
)
from ak_engine.turn.merit_points import emperor_merit_points
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
from ak_engine.webapp.game_export import build_game_bundle
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
from ak_engine.parser.gw_world import DiplomaticRelation, parse_gw_leaders
from ak_engine.turn.diplomacy import set_relation
from ak_engine.turn.kingdom_bridge import sync_leaders_from_gw_world
from ak_engine.turn.succession import create_king
from ak_engine.turn.encounter import MonsterTalkReply
from ak_engine.turn.exploration import FIND_MINES_TAX_CAP
from ak_engine.turn.plan_dispatch import SUPPORTED_ACTIONS
from ak_engine.parser.k1_moves_writer import K1WriteError, write_k1_moves_file
from ak_engine.webapp.diplomacy_orders import InvalidDiplomacyOrderError, set_turn_diplomacy_orders
from ak_engine.webapp.moves_compose import (
    CAST_CHARACTER_TARGET_SPELLS,
    CAST_FEATURE_TARGET_SPELLS,
    CAST_ITEM_TARGET_SPELLS,
    CAST_NESTED_PLAN_SPELLS,
    CAST_PROVINCE_TARGET_UI_SPELLS,
    CAST_TERRAIN_CHOICES,
    DISBAND_ALL_VALUE,
    DISBAND_SLOT_COUNT,
    EXPANDABLE_TACTIC_SLOT_COUNT,
    HIRE_GOLD_OFFER_RANGE,
    LEAVE_ALL_VALUE,
    LEAVE_SLOT_COUNT,
    PHASE_COUNT,
    PHASE_DISPLAY_NAME,
    PICK_UP_ALL_VALUE,
    PICK_UP_SLOT_COUNT,
    RECRUIT_TYPE_SLOT_COUNT,
    SAY_TEXT_MAX_LENGTH,
    TACTIC_SLOT_COUNT,
    TRADE_GOLD_VALUE,
    TRADE_ITEM_NUMBER_VALUE,
    InvalidComposedMovesError,
    build_composed_kingdom,
    cast_character_target_options,
    cast_spell_options,
    challenge_target_options,
    charm_target_options,
    disband_target_options,
    feature_options,
    fire_target_options,
    give_item_options,
    hire_target_options,
    item_options,
    kill_enemy_target_options,
    kingdom_leaders_for_compose,
    leave_army_target_options,
    leave_target_options,
    nested_hero_option_bundle,
    pick_up_army_target_options,
    practice_ability_options,
    province_options,
    pursue_target_options,
    recruit_target_options,
    recruit_type_options,
    resurrection_target_options,
    spell_options,
    tactic_options,
    trade_gift_options,
    trade_recipient_options,
    trail_target_options,
    use_mi_item_options,
    use_mi_item_spell_by_id,
)
from ak_engine.webapp.kingdom_create import (
    NoProvinceAtCoordError,
    ProvinceAlreadyAHomeError,
    ProvinceAlreadyOwnedError,
    coord_is_a_kingdom_home_province,
    create_kingdom,
)
from ak_engine.webapp.kingdom_delete import KingdomHasEmperorError, delete_kingdom
from ak_engine.webapp.reports import turn_zero_report
from ak_engine.webapp.turn_processing import (
    InvalidMoveFileError,
    load_turn_processing_log,
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
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS
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

# Every `models/game_state.py MeritTally` field, in that class's own
# declared order, with a GM-readable label -- the raw, cumulative inputs
# `turn/merit_points.py`'s own per-office formulas read. `is_float` picks
# which ones accept a fractional value (currently only Silver Tongue's
# own `diplomatic_merit_points`, the one real `Tit_Pts`-style counter
# this project models as a float -- see that field's own docstring).
MERIT_TALLY_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("land_battles_won_points", "Land Battles Won (points)", False),
    ("land_battles_lost_points", "Land Battles Lost (points)", False),
    ("naval_battles_won_points", "Naval Battles Won (points)", False),
    ("naval_battles_lost_points", "Naval Battles Lost (points)", False),
    ("monster_hp_defeated", "Monster HP Defeated", False),
    ("monster_hp_neutralized", "Monster HP Neutralized", False),
    ("resurrection_bless_casts", "Resurrection/Bless Casts", False),
    ("features_discovered_first", "Features Discovered First", False),
    ("discoveries_found_first", "Discoveries Found First", False),
    ("discoveries_found_not_first", "Discoveries Found (Not First)", False),
    ("discoveries_via_espionage", "Discoveries Via Espionage", False),
    ("successful_thefts", "Successful Thefts", False),
    ("diplomatic_merit_points", "Diplomatic Merit Points", True),
    ("elemental_spell_casts", "Elemental Spell Casts", False),
    ("illusionist_spell_casts", "Illusionist Spell Casts", False),
    ("necromancy_spell_casts", "Necromancy Spell Casts", False),
    ("psychic_spell_casts", "Psychic Spell Casts", False),
    ("plains_explorations", "Plains Explorations", False),
    ("desert_explorations", "Desert Explorations", False),
    ("jungle_explorations", "Jungle Explorations", False),
    ("forest_explorations", "Forest Explorations", False),
    ("mountain_explorations", "Mountain Explorations", False),
    ("sea_explorations", "Sea Explorations", False),
    ("teaching_interactions", "Teaching Interactions", False),
    ("successful_assassinations", "Successful Assassinations", False),
    ("duel_merit_net", "Duel Merit (net)", False),
    ("air_combat_merit", "Air Combat Merit", False),
    ("courage_encounter_merit", "Courage Encounter Merit", False),
    ("bravery_merit", "Bravery Merit", False),
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


# User-sourced renames (2026-11-15/16, three rounds) for the Action
# dropdown -- this project's own internal `ActionCode` member names
# ("Lmove"/"Aspy"/"Challenge"/bare "Recruit"/"Use Mi"/...) were never
# meant as player-facing text, just the closest bare identifier
# `display_name()`'s own fallback could title-case. Every one of these
# appends its own two-letter order-sheet code for the GM's own
# convenience. `ActionCode.CHALLENGE`'s own real tactic, "Kill Enemy",
# is renamed "Kill an Enemy" too (second round) -- see ``SPELL_NAME``'s
# own override in ``models/enums.py`` for that one, a `Spell` member
# rather than an `ActionCode`. `ActionCode.TRADE` (third round) folds
# in what the template used to special-case on its own ("Give" instead
# of the bare "Trade" this Action is still internally named) -- one
# dict entry now, not a per-template-occurrence conditional. Every
# other ActionCode member is unaffected, still falling back to the
# same bare-identifier title-casing as before.
ACTION_NAME: dict[ActionCode, str] = {
    ActionCode.LMOVE: "Move (MO)",
    ActionCode.EXPLORE: "Explore (EX)",
    ActionCode.SEARCH: "Search (SE)",
    ActionCode.RECRUIT: "Recruit (RE)",
    ActionCode.DISBAND: "Disband (DI)",
    ActionCode.HIRE: "Hire (HI)",
    ActionCode.FIRE: "Fire (FI)",
    ActionCode.LEAVE: "Leave (LE)",
    ActionCode.PICK_UP: "Pick Up (PI)",
    ActionCode.CAST: "Cast (CA)",
    ActionCode.USE_MI: "Use Item (UI)",
    ActionCode.CHALLENGE: "Encounter (EN)",
    ActionCode.ASPY: "Spy (SP)",
    ActionCode.PRACTICE: "Practice (PR)",
    ActionCode.TRADE: "Give (GI)",
    ActionCode.DEFEND: "Defend (DE)",
    ActionCode.PURSUE: "Pursue (PU)",
    ActionCode.TRAIL: "Trail (TR)",
}

# User-sourced (2026-11-15): WAIT and MOVE_ABORT are real, harmless
# no-ops (`turn/plan_dispatch.py`'s own dispatch, `ActionCode.WAIT`/
# `ActionCode.MOVE_ABORT` both resolve to the same `NoOpResult` as
# `NO_ACTION`), but the user found no practical use for offering either
# one on this screen -- NO_ACTION alone covers "nothing ordered this
# phase." Still real, valid ``SUPPORTED_ACTIONS`` members server-side
# (a tampered POST naming either one is still accepted, unchanged), so
# this only narrows the Action dropdown's own displayed option list.
ACTION_UI_HIDDEN_VALUES: frozenset[ActionCode] = frozenset({ActionCode.WAIT, ActionCode.MOVE_ABORT})

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
    ActionCode: ACTION_NAME,
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

    @app.get("/games/<slug>/export")
    def games_export(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            data = build_game_bundle(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        return Response(
            data,
            mimetype="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{slug}_debug_bundle.zip"'},
        )

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

        # The 37 leader-scoped ranked offices' own live-computed current
        # holder -- read-only context for the "Office Holders" panel,
        # alongside the raw sticky tie-break record the GM can edit
        # directly. Wrapped per-office so one formula's own edge case
        # can't blank the whole page (same caution as the leader Merit
        # Points table and the army-scoped Royal Titles panel).
        office_current_holders: dict[Office, int | None] = {}
        for office in RANKED_OFFICES:
            try:
                holder = resolve_office_holder(state, office)
            except Exception:
                holder = None
            office_current_holders[office] = holder.leader_id if holder is not None else None

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
            all_alignments=list(Alignment),
            discoveries=list(Discovery),
            ranked_offices=RANKED_OFFICES,
            office_name=OFFICE_NAME,
            office_current_holders=office_current_holders,
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
        if coord_is_a_kingdom_home_province(state, coord):
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
        # Bug fix: both are divisor/subtraction terms downstream
        # (turn/encounter.py steal_success_chance()'s own treasury-raid
        # guard divisor; turn/valhalla_execution.py select_ordinary_
        # valhalla_recipient()'s own score formula) that assume a
        # non-negative count -- a negative treasury_raid_attempts_this_
        # turn can drive that divisor to zero (ZeroDivisionError) or
        # negative, and a negative valhalla_visit_count breaks the
        # documented "fewer visits always outscores more" invariant.
        if treasury_raid_attempts_this_turn < 0 or valhalla_visit_count < 0:
            return _edit_error("Status values must not be negative.")

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
            if amount < 0:
                raise ValueError("Blackmail amount must not be negative")
            if spy_leader_id not in state.leaders:
                raise KeyError("spy leader")
            if spy_kingdom_id not in state.kingdoms:
                raise KeyError("spy kingdom")
            return BlackmailClaim(spy_leader_id=spy_leader_id, spy_kingdom_id=spy_kingdom_id, amount=amount)

        try:
            pending_blackmail = _blackmail_claim("pending")
            active_blackmail = _blackmail_claim("active")
        except ValueError:
            return _edit_error("A Blackmail claim needs its Spy, Spy's Kingdom, and a non-negative Amount all set.")
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
        # Bug fix (security: unbounded resource-exhaustion DoS): this had
        # no upper bound at all -- a crafted width/height (e.g. 10**9)
        # reaches generate_new_game() directly, which allocates and
        # iterates a province/feature/army grid sized off them. Capped
        # at the real game's own documented maximum map size, Regolamento
        # AK.txt [12.1]'s "Super-AK" variant (turn/movement.py's own
        # confirmed NORMAL_MAP_BOUNDS) -- nothing in this project's own
        # worldgen ever legitimately needs a larger board than that.
        max_width, max_height = NORMAL_MAP_BOUNDS
        if width > max_width or height > max_height:
            return redirect(
                url_for(
                    "world_setup", slug=slug,
                    error=f"Width and height can't exceed the game's own maximum map size ({max_width}x{max_height}).",
                )
            )

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

    @app.post("/games/<slug>/world/events")
    def world_events_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _setup_error(message: str):
            return redirect(url_for("world_setup", slug=slug, error=message))

        def _optional_int(field: str) -> int | None:
            raw = request.form.get(field, "").strip()
            return int(raw) if raw else None

        try:
            last_gate_angel_turn = _optional_int("last_gate_angel_turn")
            gate_angel_due_alignment_turn = _optional_int("gate_angel_due_alignment_turn")
            election_pending_turn = _optional_int("election_pending_turn")
        except ValueError:
            return _setup_error("Turn numbers must be whole numbers.")

        gate_angel_candidates_raw = request.form.get("gate_angel_candidates_this_turn", "").strip()
        try:
            gate_angel_candidates_this_turn = int(gate_angel_candidates_raw) if gate_angel_candidates_raw else 0
        except ValueError:
            return _setup_error("Gate Angel Candidates This Turn must be a whole number.")

        last_gate_angel_kingdom_raw = request.form.get("last_gate_angel_kingdom", "").strip()
        last_gate_angel_kingdom: int | None
        if last_gate_angel_kingdom_raw:
            try:
                last_gate_angel_kingdom = int(last_gate_angel_kingdom_raw)
            except ValueError:
                return _setup_error("Please choose a valid Last Gate Angel Kingdom.")
            if last_gate_angel_kingdom not in state.kingdoms:
                return _setup_error("Please choose a valid Last Gate Angel Kingdom.")
        else:
            last_gate_angel_kingdom = None

        last_valhalla_visited_raw = request.form.get("last_valhalla_visited_kingdom_id", "").strip()
        last_valhalla_visited_kingdom_id: int | None
        if last_valhalla_visited_raw:
            try:
                last_valhalla_visited_kingdom_id = int(last_valhalla_visited_raw)
            except ValueError:
                return _setup_error("Please choose a valid Last Valhalla Visited Kingdom.")
            if last_valhalla_visited_kingdom_id not in state.kingdoms:
                return _setup_error("Please choose a valid Last Valhalla Visited Kingdom.")
        else:
            last_valhalla_visited_kingdom_id = None

        try:
            gate_angel_due_alignment = _optional_enum(Alignment, request.form.get("gate_angel_due_alignment", ""))
            election_pending_alignment_trigger = _optional_enum(
                Alignment, request.form.get("election_pending_alignment_trigger", "")
            )
        except KeyError:
            return _setup_error("Please choose valid alignments.")

        gate_angel_cycle_visited: set[Alignment] = set()
        for raw_name in request.form.getlist("gate_angel_cycle_visited"):
            try:
                gate_angel_cycle_visited.add(Alignment[raw_name])
            except KeyError:
                return _setup_error("Please choose valid Gate Angel Cycle Visited alignments.")

        guild_target_raw = request.form.get("pending_guild_target", "").strip()
        pending_guild_target: int | None
        if guild_target_raw:
            try:
                pending_guild_target = int(guild_target_raw)
            except ValueError:
                return _setup_error("Please choose a valid Pending Guild Target.")
            if pending_guild_target not in state.leaders:
                return _setup_error("Please choose a valid Pending Guild Target.")
        else:
            pending_guild_target = None

        state.last_gate_angel_turn = last_gate_angel_turn
        state.last_gate_angel_kingdom = last_gate_angel_kingdom
        state.last_valhalla_visited_kingdom_id = last_valhalla_visited_kingdom_id
        state.gate_angel_cycle_visited = gate_angel_cycle_visited
        state.gate_angel_due_alignment = gate_angel_due_alignment
        state.gate_angel_due_alignment_turn = gate_angel_due_alignment_turn
        state.gate_angel_candidates_this_turn = gate_angel_candidates_this_turn
        state.election_pending_turn = election_pending_turn
        state.election_pending_alignment_trigger = election_pending_alignment_trigger
        state.pending_guild_target = pending_guild_target
        save_game(root, slug, state)
        return redirect(url_for("world_setup", slug=slug))

    @app.post("/games/<slug>/world/discoveries")
    def world_discoveries_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _setup_error(message: str):
            return redirect(url_for("world_setup", slug=slug, error=message))

        first_found_by: dict[Discovery, int] = {}
        for discovery in Discovery:
            raw = request.form.get(f"first_found_by_{discovery.name}", "").strip()
            if not raw:
                continue
            try:
                kingdom_id = int(raw)
            except ValueError:
                return _setup_error(f"{display_name(discovery)}: please choose a valid Kingdom.")
            if kingdom_id not in state.kingdoms:
                return _setup_error(f"{display_name(discovery)}: please choose a valid Kingdom.")
            first_found_by[discovery] = kingdom_id

        state.discoveries_first_found_by = first_found_by
        save_game(root, slug, state)
        return redirect(url_for("world_setup", slug=slug))

    @app.post("/games/<slug>/world/office-holders")
    def world_office_holders_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _setup_error(message: str):
            return redirect(url_for("world_setup", slug=slug, error=message))

        holders: dict[Office, int] = {}
        for office in RANKED_OFFICES:
            raw = request.form.get(f"office_holder_{office.name}", "").strip()
            if not raw:
                continue
            try:
                leader_id = int(raw)
            except ValueError:
                return _setup_error(f"{OFFICE_NAME[office]}: please choose a valid Hero/King.")
            if leader_id not in state.leaders:
                return _setup_error(f"{OFFICE_NAME[office]}: please choose a valid Hero/King.")
            holders[office] = leader_id

        state.office_holders = holders
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
            army_types=list(ArmyType),
            qualities=list(Quality),
            feature_types=list(FeatureType),
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
        # Bug fix (security: unbounded resource-exhaustion DoS): this had
        # no upper bound at all -- a crafted new_width/new_height (e.g.
        # 10**9) reaches the real `for y in range(new_height): for x in
        # range(new_width):` double loop below directly. Same cap as
        # world_create()'s own identical fix: the real game's own
        # documented maximum map size (NORMAL_MAP_BOUNDS, Regolamento
        # AK.txt [12.1]'s "Super-AK" variant).
        max_width, max_height = NORMAL_MAP_BOUNDS
        if new_width > max_width or new_height > max_height:
            return _resize_error(f"Can't grow the map past its own maximum size ({max_width}x{max_height}).")

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
        # Bug fix: an owned province's tax is written as a single
        # unsigned byte (parser/xk_world_writer.py w.u8(province.tax)),
        # valid only 0-255 -- out of that range used to save fine here
        # and only fail later, as an unhandled struct.error, when a GM
        # tried to export/download this Kingdom's own XK file.
        if tax is not None and not (0 <= tax <= 255):
            return _edit_error("Tax must be between 0 and 255.")

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
        # Bug fix: both feed turn/tax_base.py's own tax computation and
        # turn/exploration.py resolve_find_mines()'s own halving formula
        # with no re-clamp downstream -- models/game_state.py's own
        # ProvinceState.mine_gold_bonus docstring documents a real,
        # permanent cap ("capped at 10"), and a negative mine_find_
        # attempts inflates 2**attempts_so_far into a fraction, making a
        # mine-find roll near-certain instead of halved.
        if not (0 <= mine_gold_bonus <= FIND_MINES_TAX_CAP):
            return _edit_error(f"Mine Gold Bonus must be between 0 and {FIND_MINES_TAX_CAP}.")
        if mine_find_attempts < 0:
            return _edit_error("Mine Find Attempts must not be negative.")

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
        if coord_is_a_kingdom_home_province(state, coord):
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
        # Bug fix: an out-of-map/unprovinced location used to save fine
        # here and only surface later, as a bare KeyError crashing turn
        # processing, the first time this leader was given an EXPLORE
        # order (turn/plan_dispatch.py indexes state.provinces[leader.
        # location] directly, with no .get()/default).
        if HexCoord(x, y) not in state.provinces:
            return _create_error("Location must be a real province.")

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

        # Current Merit Point score for every real office this leader
        # could stand for -- not just whichever office they actually hold
        # right now (resolve_office_holder() only ever returns the single
        # current top scorer, discarding everyone else's own number).
        # Wrapped per-office so one formula's own edge case can't blank
        # the whole page.
        def _format_points(value: int | float) -> str:
            return f"{value:.2f}" if isinstance(value, float) else str(value)

        office_merit_points: list[tuple[Office, str]] = []
        if leader.is_king and leader.kingdom_id is not None:
            try:
                office_merit_points.append((Office.EMPEROR, _format_points(emperor_merit_points(state, leader.kingdom_id))))
            except Exception:
                pass
        for office in RANKED_OFFICES:
            try:
                office_merit_points.append((office, _format_points(leader_office_merit_points(office, state, leader))))
            except Exception:
                continue

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
            office_name=OFFICE_NAME,
            office_merit_points=office_merit_points,
            merit_tally_fields=MERIT_TALLY_FIELDS,
            race_title_races=list(RACE_TITLE_OFFICE),
            race_name=RACE_NAME,
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
        # Bug fix: see leaders_create()'s own identical comment -- an
        # out-of-map/unprovinced location used to save fine here and
        # only crash later, the first time this leader was given an
        # EXPLORE order.
        if HexCoord(x, y) not in state.provinces:
            return _edit_error("Location must be a real province.")

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
        # Bug fix: this is a right-shift count downstream (turn/
        # assassin_guild.py resolve_grandfather_of_assassins_attempt()'s
        # own `base_percent >> target.assassination_guild_attempts`) --
        # a negative value raises ValueError ("negative shift count")
        # the next time that leader is targeted, crashing the whole
        # run_turn() pipeline (same shape as kingdom_status_save's own
        # treasury_raid_attempts_this_turn/valhalla_visit_count guard
        # above).
        if assassination_guild_attempts < 0:
            return _edit_error("Assassins Guild Attempts must not be negative.")

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

    @app.post("/games/<slug>/leaders/<int:leader_id>/finalize-heir")
    def leader_finalize_royal_heir(slug: str, leader_id: int):
        # Phase 1193: the real call site turn/succession.py create_king()
        # previously had none of -- see that module's own Phase 1193
        # addendum.
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

        if not leader.is_royal_heir:
            return _edit_error("This Hero/King isn't an unfinalized Royal Heir.")

        name = request.form.get("name", "").strip()
        if not name:
            return _edit_error("Please enter the new King's name.")
        try:
            temper = Temper[request.form.get("temper", "")]
        except KeyError:
            return _edit_error("Please choose a valid Temper.")
        try:
            sex = Sex[request.form.get("sex", "")]
        except KeyError:
            return _edit_error("Please choose a valid Sex.")

        skill_points: dict[Ability, int] = {}
        for ability in Ability:
            raw_points = request.form.get(f"heir_talent_{ability.name}", "0").strip()
            try:
                points = int(raw_points) if raw_points else 0
            except ValueError:
                return _edit_error("Talent points must be whole numbers.")
            if points:
                skill_points[ability] = points

        result = create_king(state, leader_id, name=name, temper=temper, sex=sex, skill_points=skill_points)
        if not result.applied:
            return _edit_error(result.reason or "Couldn't finalize this Royal Heir.")

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
        # Bug fix: remove_item() is a bare-id pop with no ownership check
        # of its own -- a stale or hand-crafted item_id (this leader's
        # own item list may have changed since the page was rendered, or
        # the form could simply be edited) must not silently delete a
        # different Hero's item.
        item = state.items.get(item_id)
        if item is None or item.owner_leader_id != leader_id:
            return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id, error="Item not found."))
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

        try:
            experience_credit = int(request.form.get("experience_credit", ""))
        except ValueError:
            return _edit_error("Experience Credit must be a whole number.")
        if experience_credit < 0:
            return _edit_error("Experience Credit must be 0 or more.")

        leader.skills = SkillTable(raw_values=raw_values)
        leader.experience_credit = experience_credit
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/merit-tally")
    def leader_merit_tally_save(slug: str, leader_id: int):
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

        values: dict[str, int | float] = {}
        for field_name, label, is_float in MERIT_TALLY_FIELDS:
            raw = request.form.get(field_name, "")
            try:
                values[field_name] = float(raw) if is_float else int(raw)
            except ValueError:
                return _edit_error(f"{label} must be a number.")

        for field_name, value in values.items():
            setattr(leader.merit_tally, field_name, value)
        save_game(root, slug, state)
        return redirect(url_for("leader_edit", slug=slug, leader_id=leader_id))

    @app.post("/games/<slug>/leaders/<int:leader_id>/race-title-tally")
    def leader_race_title_tally_save(slug: str, leader_id: int):
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

        tallies: dict[Race, RaceTitleTally] = {}
        for race in RACE_TITLE_OFFICE:
            label = RACE_NAME[race]
            try:
                won = int(request.form.get(f"race_title_won_{race.name}", ""))
                lost = int(request.form.get(f"race_title_lost_{race.name}", ""))
            except ValueError:
                return _edit_error(f"{label}: Front-Line Battles Won/Lost must be whole numbers.")
            tallies[race] = RaceTitleTally(front_line_battles_won_points=won, front_line_battles_lost_points=lost)

        leader.race_title_tally = tallies
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

        # The 3 army-scoped Royal Titles' own live-computed current
        # holder -- read-only context for the "Army-Scoped Royal Titles"
        # panel, alongside the raw sticky tie-break record the GM can
        # edit directly. Wrapped per-office so one formula's own edge
        # case can't blank the whole page (same caution as the leader
        # Merit Points table).
        army_office_current_holders: dict[Office, int | None] = {}
        for office in ARMY_RANKED_OFFICES:
            try:
                holder = resolve_army_office_holder(state, office)
            except Exception:
                holder = None
            army_office_current_holders[office] = holder.army_id if holder is not None else None

        return render_template(
            "world_armies.html",
            meta=meta,
            state=state,
            armies=armies,
            army_types=list(ArmyType),
            qualities=list(Quality),
            army_ranked_offices=ARMY_RANKED_OFFICES,
            army_office_name=OFFICE_NAME,
            army_office_current_holders=army_office_current_holders,
            error=request.args.get("error"),
        )

    @app.post("/games/<slug>/armies/new")
    def armies_create(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        # The Provinces table's own inline "add army" forms post here with ``?return_to=provinces`` and go back to
        # that table (to the same province's row) instead of to the new army's editor.
        back_to_provinces = request.args.get("return_to") == "provinces"

        def _create_error(message: str):
            if back_to_provinces:
                return redirect(url_for("provinces_list", slug=slug, error=message))
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
        # Bug fix: an out-of-map location used to save fine here and
        # only surface later, as an unhandled struct.error, when a GM
        # tried to export/download this army's own Kingdom's XK file
        # (parser/xk_world_writer.py writes an army's own coordinate as
        # a single unsigned byte each, valid only 0-255).
        if HexCoord(x, y) not in state.provinces:
            return _create_error("Location must be a real province.")

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
        if back_to_provinces:
            return redirect(url_for("provinces_list", slug=slug, _anchor=f"province-{x}-{y}"))
        return redirect(url_for("army_edit", slug=slug, army_id=army_id))

    @app.post("/games/<slug>/armies/office-holders")
    def army_office_holders_save(slug: str):
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))

        def _setup_error(message: str):
            return redirect(url_for("armies_list", slug=slug, error=message))

        holders: dict[Office, int] = {}
        for office in ARMY_RANKED_OFFICES:
            raw = request.form.get(f"army_office_holder_{office.name}", "").strip()
            if not raw:
                continue
            try:
                army_id = int(raw)
            except ValueError:
                return _setup_error(f"{OFFICE_NAME[office]}: please choose a valid Army.")
            if army_id not in state.armies:
                return _setup_error(f"{OFFICE_NAME[office]}: please choose a valid Army.")
            holders[office] = army_id

        state.army_office_holders = holders
        save_game(root, slug, state)
        return redirect(url_for("armies_list", slug=slug))

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
        # Bug fix: see armies_create()'s own identical comment.
        if HexCoord(x, y) not in state.provinces:
            return _edit_error("Location must be a real province.")

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
        army.is_mercenary = request.form.get("is_mercenary") == "on"
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

        # Same ``?return_to=provinces`` convention as ``armies_create``: the Provinces table's own inline "add feature".
        back_to_provinces = request.args.get("return_to") == "provinces"

        def _create_error(message: str):
            if back_to_provinces:
                return redirect(url_for("provinces_list", slug=slug, error=message))
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
        if back_to_provinces:
            return redirect(url_for("provinces_list", slug=slug, _anchor=f"province-{x}-{y}"))
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
        game_label = meta.name.replace(" ", "_")
        # Same Game/Turn/Kingdom naming convention as the XK download
        # right below -- "T0" literally here (this *is* the turn-0
        # report itself, unlike the XK file, which is materials for the
        # turn *about to be processed*).
        return Response(
            "\n".join(lines),
            mimetype="text/plain",
            headers={"Content-Disposition": f'attachment; filename="SE{game_label}T0.K{kingdom_id}"'},
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
        game_label = meta.name.replace(" ", "_")
        # Turn-zero's own file is what this King needs to plan their
        # very first real move -- state.turn_number already reads 1 at
        # this point (never yet incremented), matching the "turn about
        # to be processed" convention this filename's own T<n> component
        # uses everywhere else, so no separate turn-zero special case.
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="XK{game_label}T{state.turn_number}.K{kingdom_id}"'
            },
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
            gw_sync_result=request.args.get("gw_sync_result"),
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

        # 2026-11-14 bug fix (user-requested): a King may try a Treat or a
        # Break Treat toward several other Kingdoms the same turn -- the
        # real move-file shape this mirrors (`KingdomMoveHeader.allreq`/
        # `.brreq`, see turn/diplomacy.py's own module docstring) is a
        # per-Kingdom-id request *bitmask*, not a single target. The old
        # one-dropdown-per-ordered-pair table could only ever express one
        # choice (none/treat/break) per pair anyway, so it never actually
        # blocked multiple simultaneous targets -- but it forced the GM to
        # scroll every possible pair to find them. Two independent
        # checkbox groups per issuing King (`treat_<issuer>_<target>`/
        # `break_<issuer>_<target>`) let the GM pick several targets for
        # each order type directly, while still writing the exact same
        # `treat_permissions`/`break_treat_orders` pairs as before.
        treat_pairs: set[tuple[int, int]] = set()
        break_pairs: set[tuple[int, int]] = set()
        for issuer_id in state.kingdoms:
            for target_id in state.kingdoms:
                if issuer_id == target_id:
                    continue
                if request.form.get(f"treat_{issuer_id}_{target_id}"):
                    treat_pairs.add((issuer_id, target_id))
                if request.form.get(f"break_{issuer_id}_{target_id}"):
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

    @app.post("/games/<slug>/turns/sync-world-leaders")
    def turns_sync_world_leaders(slug: str):
        # Phase 1193: the real call site turn/kingdom_bridge.py
        # sync_leaders_from_gw_world() previously had none of -- see
        # that module's own Phase 1193 addendum. Unlike a move file
        # (turns_upload() above), a world file isn't tied to any one
        # turn's own upload slot -- it's a point-in-time snapshot the GM
        # applies whenever they have a fresher one, so nothing is kept
        # on disk after parsing (unlike move files, which stay uploaded
        # for turns_process() to consume later).
        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        upload = request.files.get("world_file")
        if upload is None or not upload.filename:
            return redirect(url_for("turns_hub", slug=slug, error="Please choose a world file to upload."))

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(upload.read())
                tmp_path = Path(tmp.name)
            records = parse_gw_leaders(tmp_path)
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        if not records:
            return redirect(
                url_for(
                    "turns_hub", slug=slug, error=f"{upload.filename}: no recognizable King/Hero records found in this file."
                )
            )

        report = sync_leaders_from_gw_world(records, state)
        save_game(root, slug, state)
        summary = (
            f"Synced {len(report.synced_names)} leader(s) from the world file "
            f"({len(report.kingdom_id_set_for_names)} Kingdom assignment(s) updated); "
            f"{len(report.not_found_names)} name(s) had no matching Hero/King in this game."
        )
        return redirect(url_for("turns_hub", slug=slug, gw_sync_result=summary))

    @app.post("/games/<slug>/turns/<int:kingdom_id>/remove")
    def turns_remove_upload(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        remove_uploaded_move_file(game_dir(root, slug), state.turn_number, kingdom_id, state.kingdoms.keys())
        return redirect(url_for("turns_hub", slug=slug))

    @app.get("/games/<slug>/turns/<int:kingdom_id>/view")
    def turns_view_upload(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if kingdom_id not in state.kingdoms:
            return redirect(url_for("turns_hub", slug=slug, error="Kingdom not found."))
        uploads = uploaded_move_files(game_dir(root, slug), state.turn_number, state.kingdoms.keys())
        path = uploads.get(kingdom_id)
        if path is None:
            return redirect(url_for("turns_hub", slug=slug, error="No saved move file for this Kingdom yet."))
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return render_template(
            "turns_view_upload.html",
            meta=meta,
            kingdom=state.kingdoms[kingdom_id],
            filename=path.name,
            lines=lines,
        )

    @app.get("/games/<slug>/turns/<int:kingdom_id>/compose")
    def turns_compose(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if kingdom_id not in state.kingdoms:
            return redirect(url_for("turns_hub", slug=slug, error="Kingdom not found."))
        roster = kingdom_leaders_for_compose(state, kingdom_id)
        if not any(leader.is_king for leader in roster):
            return redirect(url_for("turns_hub", slug=slug, error="This Kingdom has no King on record."))
        return render_template(
            "turns_compose.html",
            meta=meta,
            state=state,
            kingdom_id=kingdom_id,
            kingdom=state.kingdoms[kingdom_id],
            roster=roster,
            phase_numbers=range(PHASE_COUNT),
            phase_display_name=PHASE_DISPLAY_NAME,
            # 2026-11-07 bug fix: this used to offer every ActionCode
            # member, including SUCC_TRAIL (ordinal 20) -- the one
            # ActionCode plan_dispatch.py's own SUPPORTED_ACTIONS
            # frozenset deliberately excludes "by design" (see that
            # module's own docstring). A GM selecting it could compose
            # and save a phase that then fails, opaquely, at real
            # turn-processing time (caught only by run_leader_plan()'s
            # own broad per-phase exception handler) instead of simply
            # never being offered in the first place.
            #
            # 2026-11-15 (user-requested): WAIT and MOVE_ABORT are
            # likewise still accepted server-side (still real, harmless
            # no-ops in plan_dispatch.py's own dispatch -- see this
            # module's own ACTION_UI_HIDDEN_VALUES) but no longer
            # *offered* here -- the user found no real use for either
            # one on this screen. NO_ACTION alone stays, and becomes the
            # default below, since it's this engine's own real "this
            # leader submitted no real order" sentinel (``turn/turn_
            # processor.py``'s own ``_kingdom_submitted_real_orders()``)
            # -- exactly the state an untouched row is actually in.
            actions=[
                action for action in ActionCode if action in SUPPORTED_ACTIONS and action not in ACTION_UI_HIDDEN_VALUES
            ],
            move_action_value=int(ActionCode.LMOVE),
            explore_action_value=int(ActionCode.EXPLORE),
            search_action_value=int(ActionCode.SEARCH),
            recruit_action_value=int(ActionCode.RECRUIT),
            recruit_slot_numbers=range(RECRUIT_TYPE_SLOT_COUNT),
            recruit_target_choices_by_leader={
                leader.leader_id: recruit_target_options(state, leader.leader_id) for leader in roster
            },
            recruit_type_choices_by_leader={
                leader.leader_id: recruit_type_options(state, leader.leader_id) for leader in roster
            },
            disband_action_value=int(ActionCode.DISBAND),
            disband_slot_numbers=range(DISBAND_SLOT_COUNT),
            disband_all_value=DISBAND_ALL_VALUE,
            disband_choices_by_leader={
                leader.leader_id: [
                    disband_target_options(state, leader.leader_id, slot=slot) for slot in range(DISBAND_SLOT_COUNT)
                ]
                for leader in roster
            },
            leave_action_value=int(ActionCode.LEAVE),
            leave_slot_numbers=range(LEAVE_SLOT_COUNT),
            leave_all_value=LEAVE_ALL_VALUE,
            leave_target_choices_by_leader={
                leader.leader_id: leave_target_options(state, leader.leader_id) for leader in roster
            },
            leave_army_choices_by_leader={
                leader.leader_id: [
                    leave_army_target_options(state, leader.leader_id, slot=slot) for slot in range(LEAVE_SLOT_COUNT)
                ]
                for leader in roster
            },
            pick_up_action_value=int(ActionCode.PICK_UP),
            pick_up_slot_numbers=range(PICK_UP_SLOT_COUNT),
            pick_up_all_value=PICK_UP_ALL_VALUE,
            pick_up_choices_by_leader={
                leader.leader_id: [
                    pick_up_army_target_options(state, leader.leader_id, slot=slot)
                    for slot in range(PICK_UP_SLOT_COUNT)
                ]
                for leader in roster
            },
            trade_action_value=int(ActionCode.TRADE),
            trade_gold_value=TRADE_GOLD_VALUE,
            trade_item_number_value=TRADE_ITEM_NUMBER_VALUE,
            trade_recipient_choices_by_leader={
                leader.leader_id: trade_recipient_options(state, leader.leader_id) for leader in roster
            },
            trade_gift_choices_by_leader={
                leader.leader_id: trade_gift_options(state, leader.leader_id) for leader in roster
            },
            practice_action_value=int(ActionCode.PRACTICE),
            practice_ability_choices=practice_ability_options(),
            trail_action_value=int(ActionCode.TRAIL),
            trail_target_choices_by_leader={
                leader.leader_id: trail_target_options(state, leader.leader_id) for leader in roster
            },
            challenge_action_value=int(ActionCode.CHALLENGE),
            challenge_target_choices_by_leader={
                leader.leader_id: challenge_target_options(state, leader.leader_id) for leader in roster
            },
            challenge_tactic_choices_by_slot=[
                tactic_options(slot, allow_give=True) for slot in range(EXPANDABLE_TACTIC_SLOT_COUNT)
            ],
            pursue_action_value=int(ActionCode.PURSUE),
            pursue_target_choices_by_leader={
                leader.leader_id: pursue_target_options(state, leader.leader_id) for leader in roster
            },
            pursue_tactic_choices_by_slot=[
                tactic_options(slot, allow_give=True) for slot in range(EXPANDABLE_TACTIC_SLOT_COUNT)
            ],
            # 2026-11-16 (user-requested, Special Encounter Plan), then
            # 2026-11-18 (user-requested, the ordinary per-phase tables
            # too): a much larger slot ceiling than every real phase's
            # own TACTIC_SLOT_COUNT, pre-rendered but mostly hidden --
            # tactic_default_visible_slot_count/sep_default_visible_
            # slot_count below, not tactic_slot_numbers/sep_tactic_slot_
            # numbers, drives each table's own visible row count; see
            # EXPANDABLE_TACTIC_SLOT_COUNT's own docstring.
            sep_tactic_choices_by_slot=[
                tactic_options(slot, passive=True) for slot in range(EXPANDABLE_TACTIC_SLOT_COUNT)
            ],
            sep_tactic_slot_numbers=range(EXPANDABLE_TACTIC_SLOT_COUNT),
            sep_default_visible_slot_count=TACTIC_SLOT_COUNT,
            defend_action_value=int(ActionCode.DEFEND),
            hire_action_value=int(ActionCode.HIRE),
            hire_target_choices_by_leader={
                leader.leader_id: hire_target_options(state, leader.leader_id) for leader in roster
            },
            hire_gold_offer_choices=HIRE_GOLD_OFFER_RANGE,
            fire_action_value=int(ActionCode.FIRE),
            fire_target_choices_by_leader={
                leader.leader_id: fire_target_options(state, leader.leader_id) for leader in roster
            },
            cast_action_value=int(ActionCode.CAST),
            cast_spell_choices=cast_spell_options(),
            cast_character_target_choices=cast_character_target_options(state),
            cast_terrain_choices=[(t.value, TERRAIN_NAME.get(t, t.name.title())) for t in CAST_TERRAIN_CHOICES],
            resurrection_target_choices_by_leader={
                leader.leader_id: resurrection_target_options(state, leader.leader_id) for leader in roster
            },
            cast_resurrection_value=int(Spell.RESURRECTION),
            charm_target_choices_by_leader={
                leader.leader_id: charm_target_options(state, leader.leader_id) for leader in roster
            },
            cast_charm_value=int(Spell.CHARM),
            kill_enemy_target_choices_by_leader={
                leader.leader_id: kill_enemy_target_options(state, leader.leader_id) for leader in roster
            },
            cast_kill_enemy_value=int(Spell.KILL_ENEMY),
            is_undead_king_by_leader={
                leader.leader_id: leader.is_king and leader.alignment is Alignment.UNDEAD for leader in roster
            },
            cast_character_target_spell_values=[int(s) for s in CAST_CHARACTER_TARGET_SPELLS],
            # 2026-11-16: Hide Feature is carved out of this UI-facing
            # list into its own cast_feature_target_spell_values below
            # -- the real backend shape classification (CAST_PROVINCE_
            # TARGET_SPELLS, still including Hide Feature) is untouched.
            cast_province_target_spell_values=[int(s) for s in CAST_PROVINCE_TARGET_UI_SPELLS],
            cast_feature_target_spell_values=[int(s) for s in CAST_FEATURE_TARGET_SPELLS],
            cast_feature_target_choices_by_leader={
                leader.leader_id: feature_options(state, leader_id=leader.leader_id) for leader in roster
            },
            cast_item_target_spell_values=[int(s) for s in CAST_ITEM_TARGET_SPELLS],
            cast_illus_terrain_value=int(Spell.ILLUS_TERRAIN),
            cast_nested_plan_spell_values=[int(s) for s in CAST_NESTED_PLAN_SPELLS],
            aspy_action_value=int(ActionCode.ASPY),
            use_mi_action_value=int(ActionCode.USE_MI),
            use_mi_item_choices_by_leader={
                leader.leader_id: use_mi_item_options(state, leader.leader_id) for leader in roster
            },
            use_mi_item_spell_by_id=use_mi_item_spell_by_id(state),
            # 2026-11-15: unfiltered here -- Defend's and Cast's/Use
            # Item's own province-target dropdowns, out of this round's
            # narrower scope, still show the whole map. Move's own
            # destination dropdown uses the per-leader-filtered dict
            # below instead (a real information leak the user flagged:
            # a GM composing one Kingdom's moves shouldn't see every
            # province's real identity, only what that Kingdom knows).
            province_choices=province_options(state),
            move_target_choices_by_leader={
                leader.leader_id: province_options(state, leader.leader_id) for leader in roster
            },
            feature_choices_by_leader={
                leader.leader_id: feature_options(state, leader_id=leader.leader_id) for leader in roster
            },
            tactic_slot_numbers=range(EXPANDABLE_TACTIC_SLOT_COUNT),
            tactic_default_visible_slot_count=TACTIC_SLOT_COUNT,
            tactic_choices_by_slot=[
                tactic_options(slot, allow_give=True, allow_fulfill_scout=True)
                for slot in range(EXPANDABLE_TACTIC_SLOT_COUNT)
            ],
            talk_value=int(Maneuver.TALK),
            fulfill_value=int(Maneuver.FULFILL),
            steal_value=int(Maneuver.STEAL),
            flee_value=int(Maneuver.FLEE),
            shoot_value=int(Maneuver.SHOOT),
            say_value=int(Maneuver.SAY),
            say_text_max_length=SAY_TEXT_MAX_LENGTH,
            cast_value=int(Maneuver.CAST),
            # 2026-11-14: unfiltered here -- the nested-hero-not-yet-
            # resolved rows still use this bare list, since the real
            # casting leader isn't known at render time. Top-level rows
            # use the per-leader-filtered dict below instead.
            spell_choices=spell_options(),
            spell_choices_by_leader={leader.leader_id: spell_options(state, leader.leader_id) for leader in roster},
            # Both Cast and Use Item now get their own dedicated named
            # dropdown (spell / this leader's own owned items) instead
            # of a generic numeric sub-object field -- nothing in
            # Search's own composer still needs that generic field.
            use_mi_value=int(Maneuver.USE_MI),
            item_choices_by_leader={
                leader.leader_id: item_options(state, leader.leader_id) for leader in roster
            },
            give_value=int(Maneuver.GIVE),
            give_item_choices_by_leader={
                leader.leader_id: give_item_options(state, leader.leader_id) for leader in roster
            },
            error=request.args.get("error"),
        )

    @app.get("/games/<slug>/turns/<int:kingdom_id>/compose/hero_options")
    def turns_compose_hero_options(slug: str, kingdom_id: int):
        """JSON bundle of every leader-scoped dropdown's own choices for
        one hero (``?hero_id=<id>``) -- see ``moves_compose.py``'s own
        ``nested_hero_option_bundle()`` docstring for why this exists:
        a nested-plan editor's own target character isn't known until
        the GM picks one in the *same* form, so those cells are
        populated client-side from this endpoint (``updateNestedPlan()``
        in ``turns_compose.html``) instead of at page-render time.
        ``kingdom_id`` is only part of this URL for consistency with
        the compose page's own -- a Hire/Charm/Resurrection target can
        be any hero in the whole game, never restricted to one Kingdom.
        """

        root: Path = app.config["GAMES_ROOT"]
        try:
            _, state = open_game(root, slug)
        except GameNotFoundError:
            return jsonify({"error": "Game not found."}), 404
        hero_id = request.args.get("hero_id", type=int)
        if hero_id is None:
            return jsonify({"error": "hero_id is required."}), 400
        return jsonify(nested_hero_option_bundle(state, hero_id))

    @app.post("/games/<slug>/turns/<int:kingdom_id>/compose")
    def turns_compose_save(slug: str, kingdom_id: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        if kingdom_id not in state.kingdoms:
            return redirect(url_for("turns_hub", slug=slug, error="Kingdom not found."))

        def _compose_error(message: str):
            return redirect(url_for("turns_compose", slug=slug, kingdom_id=kingdom_id, error=message))

        game_label = meta.name.replace(" ", "_")
        try:
            kingdom = build_composed_kingdom(
                state, game_label=game_label, turn_number=state.turn_number, kingdom_id=kingdom_id, form=request.form
            )
            content = write_k1_moves_file(kingdom)
        except (InvalidComposedMovesError, K1WriteError) as exc:
            return _compose_error(str(exc))

        try:
            save_uploaded_move_file(
                game_dir(root, slug), state.turn_number, kingdom.source_filename, content.encode("utf-8"), state.kingdoms.keys()
            )
        except InvalidMoveFileError as exc:
            # Would only mean a bug in build_composed_kingdom()/the
            # writer itself producing an unparseable file -- every
            # genuinely invalid *input* is already caught above.
            return _compose_error(f"Couldn't save the composed moves: {exc}")
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
        game_label = meta.name.replace(" ", "_")
        # Same Game/Turn/Kingdom naming convention as the XK download
        # right below -- "T<turn_number>" literally here (this *is* the
        # report for that turn, unlike the XK file, labelled one turn
        # ahead).
        return Response(
            "\n".join(lines),
            mimetype="text/plain",
            headers={"Content-Disposition": f'attachment; filename="SE{game_label}T{turn_number}.K{kingdom_id}"'},
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
        game_label = meta.name.replace(" ", "_")
        # `turn_number` here is the turn that was already processed (the
        # URL/storage convention `save_turn_xk_files()` uses) -- this
        # file is what the Kingdom needs to plan its *next* turn, so the
        # filename's own T<n> component is one past it, matching the
        # same "turn about to be processed" convention turn_zero_
        # download_xk() above uses.
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="XK{game_label}T{turn_number + 1}.K{kingdom_id}"'
            },
        )

    @app.get("/games/<slug>/turns/<int:turn_number>/processing-log")
    def turn_processing_log_view(slug: str, turn_number: int):
        root: Path = app.config["GAMES_ROOT"]
        try:
            meta, state = open_game(root, slug)
        except GameNotFoundError:
            return redirect(url_for("games_list", error="Game not found."))
        lines = load_turn_processing_log(game_dir(root, slug), turn_number)
        if lines is None:
            return redirect(
                url_for("turn_report_list", slug=slug, turn_number=turn_number, error="No processing log found for this turn.")
            )
        return render_template(
            "turn_processing_log_view.html", meta=meta, turn_number=turn_number, lines=lines
        )

    return app
