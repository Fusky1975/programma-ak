"""Tests for webapp/app.py -- the Flask routes (Phase 1: game registry
screen only; later phases add their own route tests)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TYPE_NAME, ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import BlackmailClaim
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.encounter import MonsterTalkReply
from ak_engine.webapp.app import create_app, display_name
from ak_engine.webapp.games import create_game, list_games, open_game, save_game


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


def test_rename_game_via_form_persists_it(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(
        f"/games/{meta.slug}/rename", data={"name": "The Four Kingdoms War"}, follow_redirects=True
    )

    assert response.status_code == 200
    (saved,) = list_games(tmp_path)
    assert saved.name == "The Four Kingdoms War"
    assert saved.slug == meta.slug  # the slug/directory stays fixed
    assert b"The Four Kingdoms War" in response.data


def test_rename_game_with_blank_name_shows_an_error_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(f"/games/{meta.slug}/rename", data={"name": "   "}, follow_redirects=True)

    assert response.status_code == 200
    assert b"enter a game name" in response.data
    (saved,) = list_games(tmp_path)
    assert saved.name == "Third Campaign"


def test_rename_unknown_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/rename", data={"name": "New Name"}, follow_redirects=True)

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


def _king_form_data(name: str, race: str = "HUMAN", alignment: str = "GOOD", temper: str = "BRAVE") -> dict[str, str]:
    """A complete, valid "Add a King" POST payload -- rulebook [2.1]'s own
    exactly-4-points/max-2-per-Ability talent allocation, split across two
    Abilities here (MELEE, SAGE) so neither test fixture nor assertion
    needs to care which ones specifically."""

    return {
        "name": name,
        "race": race,
        "alignment": alignment,
        "temper": temper,
        "talent_MELEE": "2",
        "talent_SAGE": "2",
    }


def test_add_king_via_form_persists_it(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(
        f"/games/{meta.slug}/players",
        data=_king_form_data("Bram Ironhand"),
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


def test_add_king_with_a_non_playable_alignment_shows_an_error(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(
        f"/games/{meta.slug}/players",
        data={"name": "Smaug", "race": "HUMAN", "alignment": "ANTI_HOLY"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Divine, Good, Druidic, Neutral, Pagan, Evil, or Undead" in response.data
    assert b"Smaug" not in response.data


def test_player_setup_does_not_offer_monster_only_alignments(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/players")

    assert response.status_code == 200
    assert b'value="ANTI_HOLY"' not in response.data
    assert b'value="MECHANICAL"' not in response.data
    assert b'value="SPECIAL"' not in response.data
    assert b'value="UNDEAD"' in response.data


def test_add_king_with_wrong_total_talent_points_shows_an_error(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    data = _king_form_data("Smaug")
    data["talent_SAGE"] = "1"  # now totals 3, not the required 4

    response = client.post(f"/games/{meta.slug}/players", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"exactly 4 starting talent points" in response.data
    assert b"Smaug" not in response.data


def test_add_king_with_too_many_points_on_one_ability_shows_an_error(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    data = _king_form_data("Smaug")
    data["talent_MELEE"] = "3"
    data["talent_SAGE"] = "1"

    response = client.post(f"/games/{meta.slug}/players", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"at most 2 starting talent points" in response.data
    assert b"Smaug" not in response.data


def test_add_king_with_invalid_temper_shows_an_error(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    data = _king_form_data("Smaug")
    data["temper"] = "NOT_A_TEMPER"

    response = client.post(f"/games/{meta.slug}/players", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"valid Temper" in response.data
    assert b"Smaug" not in response.data


def test_player_setup_shows_the_talent_allocation_grid(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/players")

    assert response.status_code == 200
    assert b'name="talent_MELEE"' in response.data
    assert b'name="talent_SAGE"' in response.data
    assert b'name="temper"' in response.data


def test_remove_king_via_form_removes_it(tmp_path):
    # A name that doesn't overlap the Add-King form's own placeholder text
    # ("e.g. Aldric the Bold"), so this only matches the roster listing.
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    client.post(f"/games/{meta.slug}/players", data=_king_form_data("Bram Ironhand"))

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
    client.post(f"/games/{meta.slug}/players", data=_king_form_data("Aldric"))
    client.post(f"/games/{meta.slug}/players", data=_king_form_data("Elara", "ELVEN", "NEUTRAL"))

    response = client.get(f"/games/{meta.slug}/players")

    assert b"2 of 2-12 Kings added" in response.data
    assert f'/games/{meta.slug}/titles'.encode() in response.data


def test_titles_setup_shows_mandatory_offices_and_all_optional_checked_by_default(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/titles")

    assert response.status_code == 200
    assert b"World Emperor" in response.data
    assert b"Arch-Mage Palatine" in response.data
    assert b"King of Pain" in response.data
    # Nothing has been saved yet (enabled_optional_offices is still None),
    # so every optional title's checkbox starts checked.
    assert b'name="office" value="EVIL_KING" checked' in response.data


def test_titles_setup_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/titles", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_save_titles_persists_the_chosen_subset(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(
        f"/games/{meta.slug}/titles",
        data={"office": ["EVIL_KING", "THIEF_PRINCE"]},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.enabled_optional_offices == {Office.EVIL_KING, Office.THIEF_PRINCE}


def test_save_titles_with_none_checked_disables_every_optional_title(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    client.post(f"/games/{meta.slug}/titles", data={})

    _, state = open_game(tmp_path, meta.slug)
    assert state.enabled_optional_offices == set()


def test_titles_setup_reflects_a_previously_saved_selection(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    client.post(f"/games/{meta.slug}/titles", data={"office": ["EVIL_KING"]})

    response = client.get(f"/games/{meta.slug}/titles")

    assert b'name="office" value="EVIL_KING" checked' in response.data
    assert b'name="office" value="THIEF_PRINCE" >' in response.data


def test_save_titles_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/titles", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def _add_king(client, slug, name, race="HUMAN", alignment="GOOD"):
    client.post(f"/games/{slug}/players", data=_king_form_data(name, race, alignment))


def test_world_setup_below_min_players_shows_a_warning_not_a_form(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    _add_king(client, meta.slug, "Aldric")

    response = client.get(f"/games/{meta.slug}/world")

    assert response.status_code == 200
    assert b"need 2-12" in response.data
    assert b'name="seed"' not in response.data


def test_world_setup_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/world", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_create_world_via_form_populates_and_shows_a_summary(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    _add_king(client, meta.slug, "Aldric", "HUMAN", "GOOD")
    _add_king(client, meta.slug, "Elara", "ELVEN", "NEUTRAL")

    response = client.post(f"/games/{meta.slug}/world", data={"seed": "1"}, follow_redirects=True)

    assert response.status_code == 200
    assert b"World Created" in response.data
    assert b"Aldric" in response.data
    assert b"Elara" in response.data
    assert b"2 Kingdoms" in response.data


def test_create_world_twice_shows_an_error_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    _add_king(client, meta.slug, "Aldric", "HUMAN", "GOOD")
    _add_king(client, meta.slug, "Elara", "ELVEN", "NEUTRAL")
    client.post(f"/games/{meta.slug}/world", data={"seed": "1"})

    response = client.post(f"/games/{meta.slug}/world", data={"seed": "2"}, follow_redirects=True)

    assert response.status_code == 200
    assert b"already been created" in response.data
    # Still shows the original (seed=1) world, not a fresh regeneration.
    assert b"World Created" in response.data


def test_create_world_with_non_numeric_seed_shows_an_error_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)
    _add_king(client, meta.slug, "Aldric", "HUMAN", "GOOD")
    _add_king(client, meta.slug, "Elara", "ELVEN", "NEUTRAL")

    response = client.post(f"/games/{meta.slug}/world", data={"seed": "not-a-number"}, follow_redirects=True)

    assert response.status_code == 200
    assert b"whole numbers" in response.data


def _game_with_world(tmp_path, client):
    meta = create_game(tmp_path, "Third Campaign")
    _add_king(client, meta.slug, "Aldric", "HUMAN", "GOOD")
    _add_king(client, meta.slug, "Elara", "ELVEN", "NEUTRAL")
    client.post(f"/games/{meta.slug}/world", data={"seed": "1"})
    return meta


def test_kingdom_create_adds_a_new_kingdom_and_king(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)
    before_kingdom_ids = set(state.kingdoms)

    data = _king_form_data("Sir Newling", race="DWARVEN", alignment="EVIL", temper="CAUTIOUS")
    data["home_x"] = str(coord.x)
    data["home_y"] = str(coord.y)
    response = client.post(f"/games/{meta.slug}/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    new_ids = set(state.kingdoms) - before_kingdom_ids
    assert len(new_ids) == 1
    kingdom_id = next(iter(new_ids))
    kingdom = state.kingdoms[kingdom_id]
    assert kingdom.name == "Sir Newling"
    assert kingdom.race == Race.DWARVEN
    assert kingdom.alignment == Alignment.EVIL
    assert kingdom.home_province == coord
    assert kingdom.treasury == 10

    # A King's own leader_id always equals his kingdom_id.
    king = state.leaders[kingdom_id]
    assert king.is_king is True
    assert king.kingdom_id == kingdom_id
    assert king.name == "Sir Newling"
    assert king.temper == Temper.CAUTIOUS
    assert king.location == coord
    # Automatic +1 Melee/Archery/Sage on top of the 4 distributed points.
    assert king.skills.pair_for_ability(Ability.MELEE)[0] == 3

    # Home-seating effects, matching worldgen's own King Home convention.
    province = state.provinces[coord]
    assert province.owner_kingdom_id == kingdom_id
    assert province.tax == 10
    assert province.race == Race.DWARVEN
    assert province.explored_percent == 100
    assert province.explored_percent_by_kingdom[kingdom_id] == 100


def test_kingdom_create_rejects_a_coordinate_with_no_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.kingdoms)

    data = _king_form_data("Nobody")
    data["home_x"] = "999"
    data["home_y"] = "999"
    response = client.post(f"/games/{meta.slug}/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"has no province" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.kingdoms) == before_ids


def test_kingdom_create_rejects_an_already_owned_home(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    taken = state.kingdoms[1].home_province
    before_ids = set(state.kingdoms)

    data = _king_form_data("Usurper")
    data["home_x"] = str(taken.x)
    data["home_y"] = str(taken.y)
    response = client.post(f"/games/{meta.slug}/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"already" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.kingdoms) == before_ids


def test_kingdom_create_with_invalid_race_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)

    data = _king_form_data("Someone", race="NOT_A_RACE")
    data["home_x"] = str(coord.x)
    data["home_y"] = str(coord.y)
    response = client.post(f"/games/{meta.slug}/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"valid race" in response.data


def test_kingdom_create_with_a_monster_only_alignment_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)

    data = _king_form_data("Someone", alignment="MECHANICAL")
    data["home_x"] = str(coord.x)
    data["home_y"] = str(coord.y)
    response = client.post(f"/games/{meta.slug}/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"Divine, Good, Druidic" in response.data


def test_kingdom_create_with_wrong_talent_total_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)

    data = _king_form_data("Someone")
    data["talent_MELEE"] = "1"
    data["talent_SAGE"] = "1"
    data["home_x"] = str(coord.x)
    data["home_y"] = str(coord.y)
    response = client.post(f"/games/{meta.slug}/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"distribute exactly" in response.data


def test_kingdom_create_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    data = _king_form_data("Someone")
    data["home_x"] = "0"
    data["home_y"] = "0"
    response = client.post("/games/does-not-exist/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_kingdom_delete_removes_it_and_everything_in_its_service(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[2].home_province

    response = client.post(f"/games/{meta.slug}/kingdoms/2/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert 2 not in state.kingdoms
    assert 2 not in state.leaders  # its King
    assert all(leader.kingdom_id != 2 for leader in state.leaders.values())
    assert all(army.kingdom_id != 2 for army in state.armies.values())
    assert state.provinces[home].owner_kingdom_id is None
    # The other Kingdom is completely untouched.
    assert 1 in state.kingdoms
    assert 1 in state.leaders


def test_kingdom_delete_refuses_the_crowned_emperor(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    state.emperor_kingdom_id = 1
    save_game(tmp_path, meta.slug, state)

    response = client.post(f"/games/{meta.slug}/kingdoms/1/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"crowned Emperor" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert 1 in state.kingdoms


def test_kingdom_delete_missing_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/kingdoms/999/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_kingdom_delete_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/kingdoms/1/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_kingdom_edit_shows_the_current_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/kingdoms/1")

    assert response.status_code == 200
    assert b'<select id="race" name="race">' in response.data
    assert b"Aldric" in response.data


def test_kingdom_edit_missing_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/kingdoms/999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_kingdom_edit_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/kingdoms/1", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_kingdom_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1",
        data={
            "name": "New Aldria",
            "race": "DWARVEN",
            "alignment": "EVIL",
            "treasury": "42",
            "account_number": "7",
            "king_title_prefix": "Lord",
            "king_title_suffix": "of the Eastern Reach",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    kingdom = state.kingdoms[1]
    assert kingdom.name == "New Aldria"
    assert kingdom.race.name == "DWARVEN"
    assert kingdom.alignment.name == "EVIL"
    assert kingdom.treasury == 42
    assert kingdom.account_number == 7
    assert kingdom.king_title_prefix == "Lord"
    assert kingdom.king_title_suffix == "of the Eastern Reach"


def test_kingdom_save_with_empty_name_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1",
        data={"name": "", "race": "HUMAN", "alignment": "GOOD", "treasury": "0", "account_number": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"enter a Kingdom name" in response.data


def test_kingdom_save_with_invalid_race_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1",
        data={"name": "Aldric", "race": "NOT_A_RACE", "alignment": "GOOD", "treasury": "0", "account_number": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid race" in response.data


def test_kingdom_save_with_a_monster_only_race_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1",
        data={"name": "Aldric", "race": "TROLLISH", "alignment": "GOOD", "treasury": "0", "account_number": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Human, Elven, Dwarven, or Orcish" in response.data


def test_kingdom_save_with_invalid_alignment_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1",
        data={"name": "Aldric", "race": "HUMAN", "alignment": "NOT_AN_ALIGNMENT", "treasury": "0", "account_number": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid alignment" in response.data


def test_kingdom_save_with_non_numeric_treasury_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1",
        data={"name": "Aldric", "race": "HUMAN", "alignment": "GOOD", "treasury": "lots", "account_number": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Treasury must be a whole number" in response.data


def test_kingdom_save_with_non_numeric_account_number_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1",
        data={"name": "Aldric", "race": "HUMAN", "alignment": "GOOD", "treasury": "0", "account_number": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Account number must be a whole number" in response.data


def test_kingdom_save_missing_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/999",
        data={"name": "Aldric", "race": "HUMAN", "alignment": "GOOD", "treasury": "0", "account_number": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_kingdom_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/kingdoms/1",
        data={"name": "Aldric", "race": "HUMAN", "alignment": "GOOD", "treasury": "0", "account_number": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_kingdom_status_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    other_kingdom_id = next(kid for kid in state.kingdoms if kid != 1)
    spy_leader_id = next(iter(state.leaders))

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/status",
        data={
            "treasury_raid_attempts_this_turn": "2",
            "valhalla_visit_count": "5",
            "pending_spy_leader_id": str(spy_leader_id),
            "pending_spy_kingdom_id": str(other_kingdom_id),
            "pending_amount": "15",
            "active_spy_leader_id": str(spy_leader_id),
            "active_spy_kingdom_id": str(other_kingdom_id),
            "active_amount": "30",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    kingdom = state.kingdoms[1]
    assert kingdom.treasury_raid_attempts_this_turn == 2
    assert kingdom.valhalla_visit_count == 5
    assert kingdom.pending_blackmail == BlackmailClaim(
        spy_leader_id=spy_leader_id, spy_kingdom_id=other_kingdom_id, amount=15
    )
    assert kingdom.active_blackmail == BlackmailClaim(
        spy_leader_id=spy_leader_id, spy_kingdom_id=other_kingdom_id, amount=30
    )


def test_kingdom_status_save_can_clear_back_to_defaults(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    other_kingdom_id = next(kid for kid in state.kingdoms if kid != 1)
    spy_leader_id = next(iter(state.leaders))
    client.post(
        f"/games/{meta.slug}/kingdoms/1/status",
        data={
            "treasury_raid_attempts_this_turn": "2",
            "valhalla_visit_count": "5",
            "pending_spy_leader_id": str(spy_leader_id),
            "pending_spy_kingdom_id": str(other_kingdom_id),
            "pending_amount": "15",
        },
    )

    client.post(f"/games/{meta.slug}/kingdoms/1/status", data={})

    _, state = open_game(tmp_path, meta.slug)
    kingdom = state.kingdoms[1]
    assert kingdom.treasury_raid_attempts_this_turn == 0
    assert kingdom.valhalla_visit_count == 0
    assert kingdom.pending_blackmail is None
    assert kingdom.active_blackmail is None


def test_kingdom_status_save_rejects_a_partially_filled_blackmail_claim(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/status",
        data={"pending_amount": "15"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"all set" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.kingdoms[1].pending_blackmail is None


def test_kingdom_status_save_rejects_an_invalid_blackmail_spy(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    other_kingdom_id = next(kid for kid in state.kingdoms if kid != 1)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/status",
        data={
            "pending_spy_leader_id": "999999",
            "pending_spy_kingdom_id": str(other_kingdom_id),
            "pending_amount": "15",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Spy" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.kingdoms[1].pending_blackmail is None


def test_kingdom_status_save_rejects_a_non_numeric_value(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/status",
        data={"treasury_raid_attempts_this_turn": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be whole numbers" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.kingdoms[1].treasury_raid_attempts_this_turn == 0


def test_kingdom_status_save_missing_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/kingdoms/999/status", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_kingdom_status_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/kingdoms/1/status", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_kingdom_edit_shows_the_status_effects_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/kingdoms/1")

    assert response.status_code == 200
    assert b"Status Effects" in response.data


def test_world_setup_shows_an_edit_link_for_each_kingdom(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/world")

    assert response.status_code == 200
    assert f'/kingdoms/1"'.encode() in response.data


def test_world_emperor_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/world/emperor",
        data={"emperor_kingdom_id": "1", "last_emperor_vote_turn": "3"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.emperor_kingdom_id == 1
    assert state.last_emperor_vote_turn == 3


def test_world_emperor_save_can_clear_back_to_no_emperor(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/world/emperor",
        data={"emperor_kingdom_id": "1", "last_emperor_vote_turn": "3"},
    )

    client.post(f"/games/{meta.slug}/world/emperor", data={})

    _, state = open_game(tmp_path, meta.slug)
    assert state.emperor_kingdom_id is None
    assert state.last_emperor_vote_turn is None


def test_world_emperor_save_rejects_an_invalid_emperor(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/world/emperor",
        data={"emperor_kingdom_id": "999999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid World Emperor" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.emperor_kingdom_id is None


def test_world_emperor_save_rejects_a_non_numeric_vote_turn(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/world/emperor",
        data={"last_emperor_vote_turn": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Last Emperor Vote Turn must be a whole number" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.last_emperor_vote_turn is None


def test_world_emperor_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/world/emperor", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_world_setup_shows_the_world_emperor_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/world")

    assert response.status_code == 200
    assert b"World Emperor" in response.data


def test_kingdom_edit_shows_no_discoveries_for_a_new_kingdom(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/kingdoms/1")

    assert response.status_code == 200
    assert b"No Discoveries known yet" in response.data


def test_kingdom_discovery_create_adds_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/discoveries/new",
        data={"discovery": "GREEK_FIRE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert Discovery.GREEK_FIRE in state.kingdoms[1].discoveries
    assert b"Greek Fire" in response.data


def test_kingdom_discovery_create_with_invalid_discovery_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/discoveries/new",
        data={"discovery": "NOT_A_DISCOVERY"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Discovery" in response.data


def test_kingdom_discovery_create_missing_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/999999/discoveries/new",
        data={"discovery": "GREEK_FIRE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_kingdom_discovery_delete_removes_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(f"/games/{meta.slug}/kingdoms/1/discoveries/new", data={"discovery": "GREEK_FIRE"})

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/discoveries/GREEK_FIRE/delete", follow_redirects=True
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert Discovery.GREEK_FIRE not in state.kingdoms[1].discoveries


def test_kingdom_discovery_delete_missing_discovery_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/1/discoveries/NOT_A_DISCOVERY/delete", follow_redirects=True
    )

    assert response.status_code == 200


def test_kingdom_discovery_delete_missing_kingdom_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/kingdoms/999999/discoveries/GREEK_FIRE/delete", follow_redirects=True
    )

    assert response.status_code == 200


def test_kingdom_edit_does_not_offer_an_already_known_discovery_again(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(f"/games/{meta.slug}/kingdoms/1/discoveries/new", data={"discovery": "GREEK_FIRE"})

    response = client.get(f"/games/{meta.slug}/kingdoms/1")

    assert response.status_code == 200
    assert b'value="GREEK_FIRE"' not in response.data


def test_province_kingdom_new_shows_the_form_for_an_eligible_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)

    response = client.get(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/kingdoms/new")

    assert response.status_code == 200
    assert b"New Kingdom at" in response.data


def test_province_kingdom_new_redirects_when_already_owned(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province

    response = client.get(f"/games/{meta.slug}/provinces/{home.x}/{home.y}/kingdoms/new", follow_redirects=True)

    assert response.status_code == 200
    assert b"already owned by" in response.data


def test_province_kingdom_new_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/999/999/kingdoms/new", follow_redirects=True)

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_province_kingdom_create_adds_a_kingdom_at_that_coordinate(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)
    before_ids = set(state.kingdoms)

    data = _king_form_data("Sir Newling", race="DWARVEN", alignment="EVIL", temper="CAUTIOUS")
    response = client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/kingdoms/new", data=data, follow_redirects=True
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    new_ids = set(state.kingdoms) - before_ids
    assert len(new_ids) == 1
    kingdom = state.kingdoms[next(iter(new_ids))]
    assert kingdom.name == "Sir Newling"
    assert kingdom.home_province == coord
    assert state.provinces[coord].owner_kingdom_id == kingdom.kingdom_id


def test_province_kingdom_create_rejects_an_already_owned_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    before_ids = set(state.kingdoms)

    data = _king_form_data("Usurper")
    response = client.post(
        f"/games/{meta.slug}/provinces/{home.x}/{home.y}/kingdoms/new", data=data, follow_redirects=True
    )

    assert response.status_code == 200
    assert b"already owned by" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.kingdoms) == before_ids


def test_province_kingdom_create_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    data = _king_form_data("Someone")
    response = client.post("/games/does-not-exist/provinces/0/0/kingdoms/new", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_provinces_list_shows_create_kingdom_link_only_for_eligible_provinces(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert f'/provinces/{coord.x}/{coord.y}/kingdoms/new'.encode() in response.data
    home = state.kingdoms[1].home_province
    assert f'/provinces/{home.x}/{home.y}/kingdoms/new'.encode() not in response.data


def test_provinces_list_before_world_creation_shows_a_message_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert b"no world yet" in response.data


def test_provinces_list_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/provinces", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_provinces_list_shows_every_generated_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert b"(0, 0)" in response.data


def test_provinces_list_shows_a_hex_map_svg(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert b"<svg" in response.data
    assert b"<polygon" in response.data
    assert b"Home of" in response.data  # tooltip text for at least one King's Home


def test_provinces_list_before_world_creation_has_no_hex_map(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert b"<svg" not in response.data


def test_province_edit_shows_the_current_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/0/0")

    assert response.status_code == 200
    assert b'<select id="terrain" name="terrain">' in response.data


def test_province_edit_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/999/999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_save_province_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0",
        data={
            "name": "Anglia",
            "terrain": "JUNGLE",
            "race": "TROLLISH",
            "owner_kingdom_id": "1",
            "tax": "7",
            "recruit_type_1": "PHALANX",
            "recruit_type_2": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[HexCoord(0, 0)]
    assert province.name == "Anglia"
    assert province.terrain.name == "JUNGLE"
    assert province.race.name == "TROLLISH"
    assert province.owner_kingdom_id == 1
    assert province.tax == 7
    assert province.recruit_type_1.name == "PHALANX"
    assert province.recruit_type_2 is None


def test_save_province_can_clear_the_name(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/provinces/0/0",
        data={"terrain": "PLAINS", "race": "HUMAN", "name": "Anglia"},
    )

    client.post(f"/games/{meta.slug}/provinces/0/0", data={"terrain": "PLAINS", "race": "HUMAN"})

    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[HexCoord(0, 0)].name is None


def test_province_edit_shows_the_current_name(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/provinces/0/0",
        data={"terrain": "PLAINS", "race": "HUMAN", "name": "Anglia"},
    )

    response = client.get(f"/games/{meta.slug}/provinces/0/0")

    assert response.status_code == 200
    assert b'value="Anglia"' in response.data


def test_save_province_can_clear_the_owner_back_to_unowned(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/provinces/0/0",
        data={"terrain": "PLAINS", "race": "HUMAN", "owner_kingdom_id": "1"},
    )

    client.post(f"/games/{meta.slug}/provinces/0/0", data={"terrain": "PLAINS", "race": "HUMAN"})

    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[HexCoord(0, 0)].owner_kingdom_id is None


def test_save_province_with_invalid_owner_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0",
        data={"terrain": "PLAINS", "race": "HUMAN", "owner_kingdom_id": "999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Owner" in response.data


def test_save_province_with_invalid_terrain_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0",
        data={"terrain": "NOT_A_TERRAIN", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid terrain" in response.data


def test_save_province_with_non_numeric_tax_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0",
        data={"terrain": "PLAINS", "race": "HUMAN", "tax": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"whole number" in response.data


def test_save_province_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/999/999",
        data={"terrain": "PLAINS", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_set_home_province_moves_a_kings_home(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    some_other_coord = next(coord for coord in state.provinces if coord != state.kingdoms[1].home_province)

    response = client.post(
        f"/games/{meta.slug}/provinces/{some_other_coord.x}/{some_other_coord.y}/set-home",
        data={"kingdom_id": "1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, reloaded = open_game(tmp_path, meta.slug)
    assert reloaded.kingdoms[1].home_province == some_other_coord


def test_set_home_province_does_not_touch_the_provinces_own_owner_or_tax(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    some_other_coord = next(coord for coord in state.provinces if coord != state.kingdoms[1].home_province)
    original_owner = state.provinces[some_other_coord].owner_kingdom_id
    original_tax = state.provinces[some_other_coord].tax

    client.post(f"/games/{meta.slug}/provinces/{some_other_coord.x}/{some_other_coord.y}/set-home", data={"kingdom_id": "1"})

    _, reloaded = open_game(tmp_path, meta.slug)
    assert reloaded.provinces[some_other_coord].owner_kingdom_id == original_owner
    assert reloaded.provinces[some_other_coord].tax == original_tax


def test_set_home_province_with_invalid_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0/set-home",
        data={"kingdom_id": "999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Kingdom" in response.data


def test_set_home_province_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/999/999/set-home",
        data={"kingdom_id": "1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_province_edit_shows_which_kingdom_it_is_home_to(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province

    response = client.get(f"/games/{meta.slug}/provinces/{home.x}/{home.y}")

    assert response.status_code == 200
    assert b"Home of" in response.data
    assert state.kingdoms[1].name.encode() in response.data


def test_province_edit_shows_leaders_here_with_a_delete_button(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    king = state.leaders[1]

    response = client.get(f"/games/{meta.slug}/provinces/{home.x}/{home.y}")

    assert response.status_code == 200
    assert king.name.encode() in response.data
    assert b"Delete" in response.data
    assert b"No Leaders here" not in response.data


def test_province_edit_shows_no_leaders_here_for_an_empty_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    empty_coords = [c for c in state.provinces if not state.leaders_at(c)]
    coord = empty_coords[0]

    response = client.get(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}")

    assert response.status_code == 200
    assert b"No Leaders here" in response.data


def test_deleting_a_leader_from_a_province_returns_to_that_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province

    response = client.post(
        f"/games/{meta.slug}/leaders/1/delete?return_x={home.x}&return_y={home.y}", follow_redirects=True
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert 1 not in state.leaders
    # Back on the province page (Province's own heading), not the Kings &
    # Heroes list -- confirmed by the still-present "Leaders Here" panel
    # heading and the now-absent deleted King.
    assert b"Leaders Here" in response.data


def test_deleting_a_leader_without_return_params_still_goes_to_leaders_list(tmp_path):
    # Backward compatibility: leader_edit.html's own delete form (Phase
    # 1026) passes no return_x/return_y and must keep its own original
    # redirect target.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/leaders/1/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Kings &amp; Heroes" in response.data


def test_provinces_list_shows_leaders_here_and_links_to_the_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    king = state.leaders[1]

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert king.name.encode() in response.data
    assert f'/provinces/{home.x}/{home.y}'.encode() in response.data


def test_provinces_list_shows_a_delete_button_for_each_leader_here(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert b"/leaders/1/delete" in response.data


def test_deleting_a_leader_from_the_provinces_list_returns_to_the_provinces_list(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    hero = next(leader for leader in state.leaders.values() if not leader.is_king)

    response = client.post(
        f"/games/{meta.slug}/leaders/{hero.leader_id}/delete?return_to=provinces",
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert hero.leader_id not in state.leaders
    assert f"{meta.name} &mdash; Provinces".encode() in response.data


def test_province_edit_shows_armies_here_with_a_delete_button(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    armies_here = state.armies_at(home)
    assert armies_here, "expected worldgen to seed at least one Army at a King's own Home"

    response = client.get(f"/games/{meta.slug}/provinces/{home.x}/{home.y}")

    assert response.status_code == 200
    assert b"No Armies here" not in response.data
    assert b"Armies Here" in response.data


def test_province_edit_shows_no_armies_here_for_an_empty_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    empty_coords = [c for c in state.provinces if not state.armies_at(c)]
    coord = empty_coords[0]

    response = client.get(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}")

    assert response.status_code == 200
    assert b"No Armies here" in response.data


def test_deleting_an_army_from_a_province_returns_to_that_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}/delete?return_x={home.x}&return_y={home.y}", follow_redirects=True
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert army.army_id not in state.armies
    # Back on the province page, not the Armies list.
    assert b"Armies Here" in response.data


def test_deleting_an_army_without_return_params_still_goes_to_armies_list(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army_id = next(iter(state.armies))

    response = client.post(f"/games/{meta.slug}/armies/{army_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Add Army" in response.data  # only on world_armies.html, not province_edit.html


def test_provinces_list_shows_armies_here_and_links_to_the_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert ARMY_TYPE_NAME[army.army_type].encode() in response.data
    assert f'/provinces/{home.x}/{home.y}'.encode() in response.data


def test_provinces_list_shows_a_delete_button_for_each_army_here(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert f"/armies/{army.army_id}/delete".encode() in response.data


def test_deleting_an_army_from_the_provinces_list_returns_to_the_provinces_list(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}/delete?return_to=provinces",
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert army.army_id not in state.armies
    assert f"{meta.name} &mdash; Provinces".encode() in response.data


def test_province_edit_shows_features_here_with_a_delete_button(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    feature_id = next(iter(state.features))
    coord = state.features[feature_id].coord

    response = client.get(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}")

    assert response.status_code == 200
    assert b"No special features here yet" not in response.data
    assert b"Special Features" in response.data


def test_province_edit_shows_no_special_features_for_an_empty_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    empty_coords = [c for c in state.provinces if not state.features_at(c)]
    coord = empty_coords[0]

    response = client.get(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}")

    assert response.status_code == 200
    assert b"No special features here yet" in response.data


def test_deleting_a_feature_from_a_province_returns_to_that_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    feature_id = next(iter(state.features))
    coord = state.features[feature_id].coord

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}/delete?return_x={coord.x}&return_y={coord.y}",
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert feature_id not in state.features
    # Back on the province page, not the global Features list.
    assert b"Special Features" in response.data


def test_deleting_a_feature_without_return_params_still_goes_to_features_list(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    feature_id = next(iter(state.features))

    response = client.post(f"/games/{meta.slug}/features/{feature_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert f"{meta.name} &mdash; Special Features".encode() in response.data


def test_provinces_list_shows_features_here_and_links_to_the_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    feature_id = next(iter(state.features))
    feature = state.features[feature_id]

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert f'/provinces/{feature.coord.x}/{feature.coord.y}'.encode() in response.data


def test_provinces_list_shows_a_delete_button_for_each_feature_here(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    feature_id = next(iter(state.features))

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert f"/features/{feature_id}/delete".encode() in response.data


def test_deleting_a_feature_from_the_provinces_list_returns_to_the_provinces_list(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    feature_id = next(iter(state.features))

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}/delete?return_to=provinces",
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert feature_id not in state.features
    # Back on the Provinces list, not the global Features list.
    assert f"{meta.name} &mdash; Provinces".encode() in response.data


def _safe_province_coords(state, count):
    """``count`` distinct province coordinates with no Kingdom Home, no
    Army, no Leader, and no Feature on them -- safe to delete without
    tripping any of province_delete()'s own real preconditions."""

    homes = {kingdom.home_province for kingdom in state.kingdoms.values()}
    found = []
    for coord in state.provinces:
        if coord in homes:
            continue
        if state.armies_at(coord) or state.leaders_at(coord) or state.features_at(coord):
            continue
        found.append(coord)
        if len(found) == count:
            return found
    raise AssertionError(f"could not find {count} safe province coordinates to delete")


def test_province_delete_removes_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)

    response = client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert coord not in state.provinces


def test_province_delete_also_removes_its_own_features(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)
    client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/features/new",
        data={"kind": "TEMPLE"},
    )
    _, state = open_game(tmp_path, meta.slug)
    assert state.features_at(coord)

    response = client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert coord not in state.provinces
    assert state.features_at(coord) == []


def test_province_delete_blocked_for_a_kingdoms_home_province(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province

    response = client.post(f"/games/{meta.slug}/provinces/{home.x}/{home.y}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Home province" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert home in state.provinces


def test_province_delete_blocked_when_an_army_is_present(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)
    army = next(iter(state.armies.values()))
    army.location = coord
    save_game(tmp_path, meta.slug, state)

    response = client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Armies present" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert coord in state.provinces


def test_province_delete_blocked_when_a_leader_is_present(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)
    leader = next(leader for leader in state.leaders.values() if not leader.is_king)
    leader.location = coord
    save_game(tmp_path, meta.slug, state)

    response = client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Leaders present" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert coord in state.provinces


def test_province_delete_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/provinces/999/999/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_province_delete_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/provinces/0/0/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_province_create_fills_a_deleted_coordinate(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)
    client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/delete")
    _, state = open_game(tmp_path, meta.slug)
    assert coord not in state.provinces

    response = client.post(
        f"/games/{meta.slug}/provinces/new",
        data={"x": str(coord.x), "y": str(coord.y), "terrain": "MTNS", "race": "DWARVEN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[coord]
    assert province.terrain == Terrain.MTNS
    assert province.race == Race.DWARVEN
    assert province.owner_kingdom_id is None
    assert province.tax is None


def test_province_create_rejects_an_already_occupied_coordinate(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    existing = next(iter(state.provinces.values()))

    response = client.post(
        f"/games/{meta.slug}/provinces/new",
        data={"x": str(existing.coord.x), "y": str(existing.coord.y), "terrain": "PLAINS", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"already has a province" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[existing.coord].terrain == existing.terrain


def test_province_create_rejects_an_out_of_bounds_coordinate(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/new",
        data={"x": "99999", "y": "0", "terrain": "PLAINS", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"outside this map" in response.data


def test_province_create_with_invalid_terrain_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    (coord,) = _safe_province_coords(state, 1)
    client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/delete")

    response = client.post(
        f"/games/{meta.slug}/provinces/new",
        data={"x": str(coord.x), "y": str(coord.y), "terrain": "NOT_A_TERRAIN", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid terrain" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert coord not in state.provinces


def test_province_create_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/provinces/new",
        data={"x": "0", "y": "0", "terrain": "PLAINS", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_world_resize_grows_the_board_and_fills_new_provinces(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    old_width, old_height = state.board_width, state.board_height
    old_coord = HexCoord(0, 0)
    before = state.provinces[old_coord]
    before_terrain, before_race = before.terrain, before.race

    response = client.post(
        f"/games/{meta.slug}/world/resize",
        data={
            "new_width": str(old_width + 2),
            "new_height": str(old_height + 3),
            "terrain": "MTNS",
            "race": "DWARVEN",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.board_width == old_width + 2
    assert state.board_height == old_height + 3
    # Every cell in the newly exposed strip is filled...
    new_coord = HexCoord(old_width, 0)
    assert state.provinces[new_coord].terrain == Terrain.MTNS
    assert state.provinces[new_coord].race == Race.DWARVEN
    new_corner = HexCoord(old_width + 1, old_height + 2)
    assert new_corner in state.provinces
    # ...but nothing within the old bounds was touched.
    assert state.provinces[old_coord].terrain == before_terrain
    assert state.provinces[old_coord].race == before_race


def test_world_resize_does_not_refill_a_hole_inside_the_old_bounds(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    old_width, old_height = state.board_width, state.board_height
    (coord,) = _safe_province_coords(state, 1)
    client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/delete")
    _, state = open_game(tmp_path, meta.slug)
    assert coord not in state.provinces

    client.post(
        f"/games/{meta.slug}/world/resize",
        data={
            "new_width": str(old_width + 1),
            "new_height": str(old_height),
            "terrain": "MTNS",
            "race": "DWARVEN",
        },
    )

    _, state = open_game(tmp_path, meta.slug)
    assert coord not in state.provinces


def test_world_resize_rejects_shrinking(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    old_width, old_height = state.board_width, state.board_height

    response = client.post(
        f"/games/{meta.slug}/world/resize",
        data={
            "new_width": str(old_width - 1),
            "new_height": str(old_height),
            "terrain": "PLAINS",
            "race": "HUMAN",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Can&#39;t shrink the map" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.board_width == old_width
    assert state.board_height == old_height


def test_world_resize_with_non_numeric_dimensions_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/world/resize",
        data={"new_width": "lots", "new_height": "10", "terrain": "PLAINS", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be whole numbers" in response.data


def test_world_resize_with_invalid_terrain_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    old_width = state.board_width

    response = client.post(
        f"/games/{meta.slug}/world/resize",
        data={
            "new_width": str(old_width + 1),
            "new_height": str(state.board_height),
            "terrain": "NOT_A_TERRAIN",
            "race": "HUMAN",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid terrain" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.board_width == old_width


def test_world_resize_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/world/resize",
        data={"new_width": "10", "new_height": "10", "terrain": "PLAINS", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_provinces_list_shows_the_resize_form(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces")

    assert response.status_code == 200
    assert b"Resize Map" in response.data


def test_province_effects_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0/effects",
        data={
            "terrain_override": "SEA",
            "tax_modifier_percent": "-100",
            "illusory_terrain": "MTNS",
            "illusory_terrain_enhanced": "on",
            "scar_terrain_gold_reduction": "4",
            "earthquake_flat_reduction": "3",
            "illusory_fog_active": "on",
            "plague_active": "on",
            "is_island": "on",
            "mine_gold_bonus": "6",
            "mine_find_attempts": "2",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[HexCoord(0, 0)]
    assert province.terrain_override.name == "SEA"
    assert province.tax_modifier_percent == -100
    assert province.illusory_terrain.name == "MTNS"
    assert province.illusory_terrain_enhanced is True
    assert province.scar_terrain_gold_reduction == 4
    assert province.earthquake_flat_reduction == 3
    assert province.illusory_fog_active is True
    assert province.plague_active is True
    assert province.is_island is True
    assert province.mine_gold_bonus == 6
    assert province.mine_find_attempts == 2


def test_province_effects_save_can_clear_optional_terrains_and_checkboxes(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/provinces/0/0/effects",
        data={
            "terrain_override": "SEA",
            "illusory_terrain": "MTNS",
            "illusory_terrain_enhanced": "on",
            "illusory_fog_active": "on",
            "plague_active": "on",
            "is_island": "on",
        },
    )

    client.post(f"/games/{meta.slug}/provinces/0/0/effects", data={})

    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[HexCoord(0, 0)]
    assert province.terrain_override is None
    assert province.illusory_terrain is None
    assert province.illusory_terrain_enhanced is False
    assert province.illusory_fog_active is False
    assert province.plague_active is False
    assert province.is_island is False
    assert province.tax_modifier_percent == 0
    assert province.scar_terrain_gold_reduction == 0
    assert province.earthquake_flat_reduction == 0
    assert province.mine_gold_bonus == 0
    assert province.mine_find_attempts == 0


def test_province_effects_save_with_invalid_terrain_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0/effects",
        data={"terrain_override": "NOT_A_TERRAIN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid terrain" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[HexCoord(0, 0)].terrain_override is None


def test_province_effects_save_with_non_numeric_value_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0/effects",
        data={"tax_modifier_percent": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be whole numbers" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[HexCoord(0, 0)].tax_modifier_percent == 0


def test_province_effects_save_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/provinces/999/999/effects", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_province_effects_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/provinces/0/0/effects",
        data={},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_province_edit_shows_the_magic_and_terrain_effects_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/0/0")

    assert response.status_code == 200
    assert b"Magic &amp; Terrain Effects" in response.data


def test_province_exploration_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)

    response = client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/exploration",
        data={"explored_1": "40", "explored_2": "100"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[coord]
    assert province.explored_percent_by_kingdom.get(1) == 40
    assert province.explored_percent_by_kingdom.get(2) == 100


def test_province_exploration_save_can_clear_back_to_unexplored(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)
    client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/exploration",
        data={"explored_1": "40"},
    )

    client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/exploration", data={})

    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[coord].explored_percent_by_kingdom == {}


def test_province_exploration_save_rejects_an_out_of_range_percent(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)
    _, state = open_game(tmp_path, meta.slug)
    before = dict(state.provinces[coord].explored_percent_by_kingdom)

    response = client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/exploration",
        data={"explored_1": "150"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be 0-100" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[coord].explored_percent_by_kingdom == before


def test_province_exploration_save_rejects_a_non_numeric_percent(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)
    _, state = open_game(tmp_path, meta.slug)
    before = dict(state.provinces[coord].explored_percent_by_kingdom)

    response = client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/exploration",
        data={"explored_1": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be whole numbers" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[coord].explored_percent_by_kingdom == before


def test_province_exploration_save_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/999/999/exploration", data={}, follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_province_exploration_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/provinces/0/0/exploration", data={}, follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_province_edit_shows_the_exploration_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/0/0")

    assert response.status_code == 200
    assert b"Exploration" in response.data


def test_province_recruitment_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)

    response = client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/recruitment",
        data={"recruited_BOWMEN": "1", "recruited_LEGION": "2", "recruit_locked_this_turn": "on"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[coord]
    assert province.recruited_this_turn.get(ArmyType.BOWMEN) == 1
    assert province.recruited_this_turn.get(ArmyType.LEGION) == 2
    assert province.recruit_locked_this_turn is True


def test_province_recruitment_save_can_clear_back_to_defaults(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)
    client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/recruitment",
        data={"recruited_BOWMEN": "1", "recruit_locked_this_turn": "on"},
    )

    client.post(f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/recruitment", data={})

    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[coord]
    assert province.recruited_this_turn == {}
    assert province.recruit_locked_this_turn is False


def test_province_recruitment_save_rejects_a_negative_count(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)

    response = client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/recruitment",
        data={"recruited_BOWMEN": "-1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"can&#39;t be negative" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[coord].recruited_this_turn == {}


def test_province_recruitment_save_rejects_a_non_numeric_count(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    (coord,) = _safe_province_coords(open_game(tmp_path, meta.slug)[1], 1)

    response = client.post(
        f"/games/{meta.slug}/provinces/{coord.x}/{coord.y}/recruitment",
        data={"recruited_BOWMEN": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be whole numbers" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.provinces[coord].recruited_this_turn == {}


def test_province_recruitment_save_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/999/999/recruitment", data={}, follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_province_recruitment_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/provinces/0/0/recruitment", data={}, follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_province_edit_shows_the_recruitment_this_turn_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/0/0")

    assert response.status_code == 200
    assert b"Recruitment This Turn" in response.data


def test_leaders_list_before_world_creation_shows_a_message_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/leaders")

    assert response.status_code == 200
    assert b"no world yet" in response.data


def test_leaders_list_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/leaders", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_leaders_list_shows_every_kings_own_name(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders")

    assert response.status_code == 200
    assert b"Aldric" in response.data
    assert b"Elara" in response.data
    assert b"(King)" in response.data


def test_leader_edit_shows_the_current_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b'value="Aldric"' in response.data


def test_leader_edit_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_save_leader_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1",
        data={
            "name": "Aldric the Wise",
            "race": "HUMAN",
            "alignment": "EVIL",
            "temper": "BERSERK",
            "sex": "MALE",
            "location_x": "3",
            "location_y": "4",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.name == "Aldric the Wise"
    assert leader.alignment.name == "EVIL"
    assert leader.temper.name == "BERSERK"
    assert leader.sex.name == "MALE"
    assert leader.location == HexCoord(3, 4)


def test_save_leader_can_clear_optional_fields_back_to_unset(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/leaders/1",
        data={
            "name": "Aldric",
            "race": "HUMAN",
            "alignment": "EVIL",
            "temper": "BERSERK",
            "sex": "MALE",
            "location_x": "0",
            "location_y": "0",
        },
    )

    client.post(
        f"/games/{meta.slug}/leaders/1",
        data={"name": "Aldric", "race": "HUMAN", "location_x": "0", "location_y": "0"},
    )

    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.alignment is None
    assert leader.temper is None
    assert leader.sex is None


def test_save_leader_with_blank_name_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1",
        data={"name": "   ", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please enter a name" in response.data


def test_save_leader_with_invalid_race_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1",
        data={"name": "Aldric", "race": "NOT_A_RACE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid race" in response.data


def test_save_leader_with_a_monster_only_alignment_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1",
        data={"name": "Aldric", "race": "HUMAN", "alignment": "MECHANICAL"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please choose valid values" in response.data


def test_leader_edit_does_not_offer_monster_only_alignments(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b'value="ANTI_HOLY"' not in response.data
    assert b'value="MECHANICAL"' not in response.data
    assert b'value="SPECIAL"' not in response.data
    assert b'value="UNDEAD"' in response.data


def test_save_leader_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/999",
        data={"name": "Nobody", "race": "HUMAN"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_save_leader_can_relocate_and_reassign_a_hero_to_a_different_kingdom(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    hero = next(leader for leader in state.leaders.values() if not leader.is_king)

    response = client.post(
        f"/games/{meta.slug}/leaders/{hero.leader_id}",
        data={"name": hero.name, "race": hero.race.name, "kingdom_id": "2", "location_x": "5", "location_y": "3"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    saved = state.leaders[hero.leader_id]
    assert saved.kingdom_id == 2
    assert saved.location == HexCoord(5, 3)


def test_save_leader_can_make_a_hero_independent(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    hero = next(leader for leader in state.leaders.values() if not leader.is_king)

    response = client.post(
        f"/games/{meta.slug}/leaders/{hero.leader_id}",
        data={"name": hero.name, "race": hero.race.name, "kingdom_id": "", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[hero.leader_id].kingdom_id is None


def test_save_leader_with_invalid_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    hero = next(leader for leader in state.leaders.values() if not leader.is_king)

    response = client.post(
        f"/games/{meta.slug}/leaders/{hero.leader_id}",
        data={"name": hero.name, "race": hero.race.name, "kingdom_id": "999", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Kingdom" in response.data


def test_save_leader_with_non_numeric_location_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1",
        data={"name": "Aldric", "race": "HUMAN", "location_x": "nope", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Location must be whole numbers" in response.data


def test_save_leader_cannot_move_a_king_out_of_his_own_kingdoms_service(tmp_path):
    # A King's own kingdom_id is locked to his own leader_id project-wide
    # -- leader_edit.html never offers the Kingdom field for a King, but
    # a direct POST (bypassing the form) must still be guarded server-side.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1",
        data={"name": "Aldric", "race": "HUMAN", "kingdom_id": "2", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].kingdom_id == 1


def test_king_leader_edit_does_not_offer_a_kingdom_dropdown(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b'name="kingdom_id"' not in response.data
    assert b"locked to his own Kingdom" in response.data


def test_non_king_leader_edit_offers_a_kingdom_dropdown(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    hero = next(leader for leader in state.leaders.values() if not leader.is_king)

    response = client.get(f"/games/{meta.slug}/leaders/{hero.leader_id}")

    assert response.status_code == 200
    assert b'name="kingdom_id"' in response.data


def test_leader_edit_shows_no_items_for_a_hero_with_none(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b"No items held" in response.data


def test_leader_item_create_adds_a_new_item(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/items/new",
        data={"treasure": "GOLD_HOARD_HUGE", "charges": "3"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    items = state.items_held_by(1)
    assert len(items) == 1
    assert items[0].treasure.name == "GOLD_HOARD_HUGE"
    assert items[0].charges == 3
    assert b"Huge Hoard of Gold" in response.data


def test_leader_item_create_defaults_charges_to_zero(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    client.post(f"/games/{meta.slug}/leaders/1/items/new", data={"treasure": "GOLD_HOARD_HUGE"})

    _, state = open_game(tmp_path, meta.slug)
    assert state.items_held_by(1)[0].charges == 0


def test_leader_item_create_with_invalid_treasure_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/items/new",
        data={"treasure": "NOT_A_TREASURE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Treasure" in response.data


def test_leader_item_create_with_non_numeric_charges_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/items/new",
        data={"treasure": "GOLD_HOARD_HUGE", "charges": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Charges must be a whole number" in response.data


def test_leader_item_create_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/999999/items/new",
        data={"treasure": "GOLD_HOARD_HUGE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_leader_item_delete_removes_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(f"/games/{meta.slug}/leaders/1/items/new", data={"treasure": "GOLD_HOARD_HUGE"})
    _, state = open_game(tmp_path, meta.slug)
    item_id = state.items_held_by(1)[0].item_id

    response = client.post(
        f"/games/{meta.slug}/leaders/1/items/{item_id}/delete", follow_redirects=True
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert item_id not in state.items


def test_leader_item_delete_missing_item_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/leaders/1/items/999999/delete", follow_redirects=True)

    assert response.status_code == 200


def test_leader_edit_shows_no_advanced_abilities_for_a_new_hero(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b"No Advanced Abilities held" in response.data


def test_leader_advanced_ability_create_adds_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/advanced-abilities/new",
        data={"advanced_ability": "TACTICAL_WARGAMES_MASTERY"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert AdvancedAbility.TACTICAL_WARGAMES_MASTERY in state.leaders[1].advanced_abilities
    assert b"Tactical Wargames Mastery" in response.data


def test_leader_advanced_ability_create_with_invalid_ability_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/advanced-abilities/new",
        data={"advanced_ability": "NOT_AN_ABILITY"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Advanced Ability" in response.data


def test_leader_advanced_ability_create_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/999999/advanced-abilities/new",
        data={"advanced_ability": "TACTICAL_WARGAMES_MASTERY"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_leader_advanced_ability_delete_removes_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/leaders/1/advanced-abilities/new",
        data={"advanced_ability": "TACTICAL_WARGAMES_MASTERY"},
    )

    response = client.post(
        f"/games/{meta.slug}/leaders/1/advanced-abilities/TACTICAL_WARGAMES_MASTERY/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert AdvancedAbility.TACTICAL_WARGAMES_MASTERY not in state.leaders[1].advanced_abilities


def test_leader_advanced_ability_delete_missing_ability_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/advanced-abilities/NOT_AN_ABILITY/delete", follow_redirects=True
    )

    assert response.status_code == 200


def test_leader_advanced_ability_delete_missing_leader_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/999999/advanced-abilities/TACTICAL_WARGAMES_MASTERY/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200


def test_leader_edit_does_not_offer_an_already_held_advanced_ability_again(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/leaders/1/advanced-abilities/new",
        data={"advanced_ability": "TACTICAL_WARGAMES_MASTERY"},
    )

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b'value="TACTICAL_WARGAMES_MASTERY"' not in response.data


def _skills_form_data(overrides=None, trailing_value=0):
    from ak_engine.models.enums import Ability

    data = {"trailing_value": str(trailing_value)}
    overrides = overrides or {}
    for ability in Ability:
        skill, aptitude = overrides.get(ability, (0, 0))
        data[f"skill_{ability.name}"] = str(skill)
        data[f"aptitude_{ability.name}"] = str(aptitude)
    return data


def test_leader_edit_shows_the_current_skill_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b"No skill data recorded" not in response.data
    assert b"Tactics" in response.data


def test_leader_edit_shows_no_skill_data_message_for_a_fresh_hero(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "New Hero", "race": "HUMAN", "location_x": "0", "location_y": "0"},
    )
    _, state = open_game(tmp_path, meta.slug)
    fresh = max(state.leaders)
    assert state.leaders[fresh].skills is None

    response = client.get(f"/games/{meta.slug}/leaders/{fresh}")

    assert response.status_code == 200
    assert b"No skill data recorded" in response.data


def test_leader_skills_save_persists_the_new_values(tmp_path):
    from ak_engine.models.enums import Ability

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/skills",
        data=_skills_form_data({Ability.TACTICAL: (5, 7)}, trailing_value=9),
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    skills = state.leaders[1].skills
    assert skills.pair_for_ability(Ability.TACTICAL) == (5, 7)
    assert skills.raw_values[30] == 9


def test_leader_skills_save_initializes_skills_when_none(tmp_path):
    from ak_engine.models.enums import Ability

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "New Hero", "race": "HUMAN", "location_x": "0", "location_y": "0"},
    )
    _, state = open_game(tmp_path, meta.slug)
    fresh = max(state.leaders)
    assert state.leaders[fresh].skills is None

    response = client.post(
        f"/games/{meta.slug}/leaders/{fresh}/skills",
        data=_skills_form_data({Ability.SAGE: (3, 4)}),
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[fresh].skills is not None
    assert state.leaders[fresh].skills.pair_for_ability(Ability.SAGE) == (3, 4)


def test_leader_skills_save_rejects_an_out_of_range_value(tmp_path):
    from ak_engine.models.enums import Ability

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/skills",
        data=_skills_form_data({Ability.TACTICAL: (10, 0)}),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be 0-9" in response.data


def test_leader_skills_save_rejects_a_non_numeric_value(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    data = _skills_form_data()
    data["skill_TACTICAL"] = "lots"

    response = client.post(f"/games/{meta.slug}/leaders/1/skills", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"must be whole numbers" in response.data


def test_leader_skills_save_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/999999/skills", data=_skills_form_data(), follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_leader_effects_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    other_leader_id = next(leader_id for leader_id in state.leaders if leader_id != 1)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/effects",
        data={
            "phantasmal_armies_level": "3",
            "oratory_boosted_this_turn": "on",
            "mystic_winds_active": "on",
            "clairvoyance_cast_target": str(other_leader_id),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.phantasmal_armies_level == 3
    assert leader.oratory_boosted_this_turn is True
    assert leader.mystic_winds_active is True
    assert leader.clairvoyance_cast_target == other_leader_id


def test_leader_effects_save_can_clear_back_to_defaults(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    other_leader_id = next(leader_id for leader_id in state.leaders if leader_id != 1)
    client.post(
        f"/games/{meta.slug}/leaders/1/effects",
        data={
            "phantasmal_armies_level": "3",
            "oratory_boosted_this_turn": "on",
            "mystic_winds_active": "on",
            "clairvoyance_cast_target": str(other_leader_id),
        },
    )

    client.post(f"/games/{meta.slug}/leaders/1/effects", data={})

    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.phantasmal_armies_level == 0
    assert leader.oratory_boosted_this_turn is False
    assert leader.mystic_winds_active is False
    assert leader.clairvoyance_cast_target is None


def test_leader_effects_save_with_invalid_clairvoyance_target_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/effects",
        data={"clairvoyance_cast_target": "999999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Clairvoyance Target" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].clairvoyance_cast_target is None


def test_leader_effects_save_rejects_a_non_numeric_value(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/effects",
        data={"phantasmal_armies_level": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be a whole number" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].phantasmal_armies_level == 0


def test_leader_effects_save_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/leaders/999999/effects", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_leader_effects_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/leaders/1/effects", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_leader_edit_shows_the_spell_effects_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b"Spell Effects" in response.data


def test_leader_history_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/history",
        data={"birth_x": "3", "birth_y": "4", "is_starting_companion": "on", "hire_turn": "2"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.birth_x == 3
    assert leader.birth_y == 4
    assert leader.is_starting_companion is True
    assert leader.hire_turn == 2


def test_leader_history_save_can_clear_back_to_defaults(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/leaders/1/history",
        data={"birth_x": "3", "birth_y": "4", "is_starting_companion": "on", "hire_turn": "2"},
    )

    client.post(f"/games/{meta.slug}/leaders/1/history", data={})

    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.birth_x is None
    assert leader.birth_y is None
    assert leader.is_starting_companion is False
    assert leader.hire_turn == 0


def test_leader_history_save_rejects_a_half_filled_birth_coordinate(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_birth_x = state.leaders[1].birth_x

    response = client.post(
        f"/games/{meta.slug}/leaders/1/history",
        data={"birth_x": "3"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"both x and y" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].birth_x == before_birth_x


def test_leader_history_save_rejects_a_non_numeric_hire_turn(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/history",
        data={"hire_turn": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Hire Turn must be a whole number" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].hire_turn == 0


def test_leader_history_save_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/leaders/999999/history", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_leader_history_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/leaders/1/history", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_leader_edit_shows_the_origin_and_hire_history_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b"Hire History" in response.data


def test_leader_status_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    other_kingdom_id = next(kid for kid in state.kingdoms if kid != 1)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/status",
        data={
            "is_comatose": "on",
            "is_royal_heir": "on",
            "assassination_guild_attempts": "3",
            "unpaid_blackmail_penalty_exponent": "2",
            "double_agent_hired_by_kingdom_id": str(other_kingdom_id),
            "clairvoyance_watchers": [str(other_kingdom_id)],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.is_comatose is True
    assert leader.is_royal_heir is True
    assert leader.assassination_guild_attempts == 3
    assert leader.unpaid_blackmail_penalty_exponent == 2
    assert leader.double_agent_hired_by_kingdom_id == other_kingdom_id
    assert leader.clairvoyance_watchers == {other_kingdom_id}


def test_leader_status_save_can_clear_back_to_defaults(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    other_kingdom_id = next(kid for kid in state.kingdoms if kid != 1)
    client.post(
        f"/games/{meta.slug}/leaders/1/status",
        data={
            "is_comatose": "on",
            "is_royal_heir": "on",
            "assassination_guild_attempts": "3",
            "unpaid_blackmail_penalty_exponent": "2",
            "double_agent_hired_by_kingdom_id": str(other_kingdom_id),
            "clairvoyance_watchers": [str(other_kingdom_id)],
        },
    )

    client.post(f"/games/{meta.slug}/leaders/1/status", data={})

    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.is_comatose is False
    assert leader.is_royal_heir is False
    assert leader.assassination_guild_attempts == 0
    assert leader.unpaid_blackmail_penalty_exponent == 0
    assert leader.double_agent_hired_by_kingdom_id is None
    assert leader.clairvoyance_watchers == set()


def test_leader_status_save_with_invalid_double_agent_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/status",
        data={"double_agent_hired_by_kingdom_id": "999999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Double Agent Hirer" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].double_agent_hired_by_kingdom_id is None


def test_leader_status_save_with_invalid_clairvoyance_watcher_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/status",
        data={"clairvoyance_watchers": ["999999"]},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Clairvoyance Watchers" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].clairvoyance_watchers == set()


def test_leader_status_save_rejects_a_non_numeric_value(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/1/status",
        data={"assassination_guild_attempts": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be a whole number" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.leaders[1].assassination_guild_attempts == 0


def test_leader_status_save_missing_leader_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/leaders/999999/status", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Hero not found" in response.data


def test_leader_status_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/leaders/1/status", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_leader_edit_shows_the_status_and_guild_effects_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/leaders/1")

    assert response.status_code == 200
    assert b"Status &amp; Guild Effects" in response.data


def test_leader_delete_removes_a_hero(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    hero = next(leader for leader in state.leaders.values() if not leader.is_king)

    response = client.post(f"/games/{meta.slug}/leaders/{hero.leader_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert hero.leader_id not in state.leaders


def test_leader_delete_of_a_king_leaves_the_kingdom_without_a_king(tmp_path):
    # Unlike GameState.remove_leader() (the real in-game death mechanic),
    # the editor's own delete must NOT archive into dead_leaders, apply
    # the merit death penalty, or install a Royal Heir -- it's a mistake-
    # correction tool, not a simulated death.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    king = next(leader for leader in state.leaders.values() if leader.is_king)

    response = client.post(f"/games/{meta.slug}/leaders/{king.leader_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert king.leader_id not in state.leaders
    assert king.leader_id not in state.dead_leaders


def test_leader_delete_missing_leader_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.leaders)

    response = client.post(f"/games/{meta.slug}/leaders/999999/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.leaders) == before_ids


def test_leader_delete_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/leaders/1/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_leaders_create_adds_a_new_hero(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    kingdom_id = next(iter(state.kingdoms))
    before_ids = set(state.leaders)

    response = client.post(
        f"/games/{meta.slug}/leaders/new",
        data={
            "name": "Brand New Hero",
            "race": "DWARVEN",
            "alignment": "GOOD",
            "temper": "BRAVE",
            "sex": "FEMALE",
            "kingdom_id": str(kingdom_id),
            "location_x": "3",
            "location_y": "2",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    new_ids = set(state.leaders) - before_ids
    assert len(new_ids) == 1
    hero = state.leaders[next(iter(new_ids))]
    assert hero.name == "Brand New Hero"
    assert hero.race == Race.DWARVEN
    assert hero.alignment == Alignment.GOOD
    assert hero.temper == Temper.BRAVE
    assert hero.sex == Sex.FEMALE
    assert hero.kingdom_id == kingdom_id
    assert hero.location == HexCoord(3, 2)
    assert hero.is_king is False


def test_leaders_create_as_independent_hero_with_minimal_fields(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.leaders)

    response = client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "Loner", "race": "HUMAN", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    new_ids = set(state.leaders) - before_ids
    assert len(new_ids) == 1
    hero = state.leaders[next(iter(new_ids))]
    assert hero.kingdom_id is None
    assert hero.alignment is None
    assert hero.temper is None
    assert hero.sex is None


def test_leaders_create_does_not_reuse_an_archived_dead_leader_id(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    hero_to_kill = next(leader for leader in state.leaders.values() if not leader.is_king)
    state.remove_leader(hero_to_kill.leader_id)
    save_game(tmp_path, meta.slug, state)
    before_ids = set(state.leaders) | set(state.dead_leaders)

    response = client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "Newcomer", "race": "HUMAN", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    new_leader = next(leader for leader in state.leaders.values() if leader.name == "Newcomer")
    assert new_leader.leader_id not in before_ids


def test_leaders_create_with_blank_name_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.leaders)

    response = client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "   ", "race": "HUMAN", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"enter a name" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.leaders) == before_ids


def test_leaders_create_with_invalid_race_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "Someone", "race": "NOT_A_RACE", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid race" in response.data


def test_leaders_create_with_a_monster_only_alignment_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "Someone", "race": "HUMAN", "alignment": "MECHANICAL", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid values" in response.data


def test_leaders_create_with_invalid_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/leaders/new",
        data={"name": "Someone", "race": "HUMAN", "kingdom_id": "999", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Kingdom" in response.data


def test_leaders_create_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/leaders/new",
        data={"name": "Someone", "race": "HUMAN", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_armies_list_before_world_creation_shows_a_message_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/armies")

    assert response.status_code == 200
    assert b"no world yet" in response.data


def test_armies_list_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/armies", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_armies_list_shows_every_generated_army(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/armies")

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert len(state.armies) > 0
    assert b"Edit" in response.data


def test_army_edit_shows_the_current_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.get(f"/games/{meta.slug}/armies/{army.army_id}")

    assert response.status_code == 200
    assert f'value="{army.location.x}"'.encode() in response.data
    assert f'value="{army.location.y}"'.encode() in response.data


def test_army_edit_missing_army_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/armies/999999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Army not found" in response.data


def test_save_army_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": "HVY_CAVALRY",
            "quality": "ELITE",
            "kingdom_id": "",
            "location_x": "5",
            "location_y": "3",
            "commanded_by": "",
            "is_skeletal": "on",
            "plague_immune": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    saved = state.armies[army.army_id]
    assert saved.army_type == ArmyType.HVY_CAVALRY
    assert saved.quality == Quality.ELITE
    assert saved.kingdom_id is None
    assert saved.location == HexCoord(5, 3)
    assert saved.commanded_by is None
    assert saved.is_skeletal is True
    assert saved.plague_immune is True


def test_save_army_can_clear_is_skeletal_and_plague_immune(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))
    base_data = {
        "army_type": army.army_type.name,
        "quality": army.quality.name,
        "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
        "location_x": str(army.location.x),
        "location_y": str(army.location.y),
        "commanded_by": "",
    }
    client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={**base_data, "is_skeletal": "on", "plague_immune": "on"},
    )

    client.post(f"/games/{meta.slug}/armies/{army.army_id}", data=base_data)

    _, state = open_game(tmp_path, meta.slug)
    saved = state.armies[army.army_id]
    assert saved.is_skeletal is False
    assert saved.plague_immune is False


def test_army_edit_shows_is_skeletal_and_plague_immune_as_checked(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))
    client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": army.quality.name,
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(army.location.x),
            "location_y": str(army.location.y),
            "commanded_by": "",
            "is_skeletal": "on",
        },
    )

    response = client.get(f"/games/{meta.slug}/armies/{army.army_id}")

    assert response.status_code == 200
    assert b'name="is_skeletal" checked' in response.data
    assert b'name="plague_immune" checked' not in response.data


def _add_army(state, army_type, location, kingdom_id=None):
    from ak_engine.models.game_state import ArmyState

    army = ArmyState(
        army_id=state.new_army_id(),
        kingdom_id=kingdom_id,
        army_type=army_type,
        quality=Quality.AVERAGE,
        location=location,
    )
    state.add_army(army)
    return army


def test_army_edit_shows_not_boarded_for_a_fresh_army(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.get(f"/games/{meta.slug}/armies/{army.army_id}")

    assert response.status_code == 200
    assert b"Not boarded on anything" in response.data


def test_army_board_boards_onto_a_legal_carrier(tmp_path):
    from ak_engine.models.army_type import ArmyType

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    coord = next(iter(state.provinces))
    carrier = _add_army(state, ArmyType.FLEET, coord)
    cargo = _add_army(state, ArmyType.LEGION, coord)
    save_game(tmp_path, meta.slug, state)

    response = client.post(
        f"/games/{meta.slug}/armies/{cargo.army_id}/board",
        data={"carrier_id": str(carrier.army_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.armies[cargo.army_id].transported_by == carrier.army_id
    assert b"Boarded on" in response.data


def test_army_board_rejects_an_illegal_carrier(tmp_path):
    from ak_engine.models.army_type import ArmyType

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    coord = next(iter(state.provinces))
    not_a_carrier = _add_army(state, ArmyType.LEGION, coord)
    cargo = _add_army(state, ArmyType.LEGION, coord)
    save_game(tmp_path, meta.slug, state)

    response = client.post(
        f"/games/{meta.slug}/armies/{cargo.army_id}/board",
        data={"carrier_id": str(not_a_carrier.army_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Can&#39;t board there" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.armies[cargo.army_id].transported_by is None


def test_army_board_rejects_a_non_co_located_carrier(tmp_path):
    from ak_engine.models.army_type import ArmyType

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    coords = iter(state.provinces)
    coord_a, coord_b = next(coords), next(coords)
    carrier = _add_army(state, ArmyType.FLEET, coord_a)
    cargo = _add_army(state, ArmyType.LEGION, coord_b)
    save_game(tmp_path, meta.slug, state)

    response = client.post(
        f"/games/{meta.slug}/armies/{cargo.army_id}/board",
        data={"carrier_id": str(carrier.army_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Can&#39;t board there" in response.data


def test_army_board_with_invalid_carrier_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army_id = next(iter(state.armies))

    response = client.post(
        f"/games/{meta.slug}/armies/{army_id}/board",
        data={"carrier_id": "999999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Carrier" in response.data


def test_army_board_missing_army_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army_id = next(iter(state.armies))

    response = client.post(
        f"/games/{meta.slug}/armies/999999/board",
        data={"carrier_id": str(army_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Army not found" in response.data


def test_army_disembark_removes_the_boarding(tmp_path):
    from ak_engine.models.army_type import ArmyType

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    coord = next(iter(state.provinces))
    carrier = _add_army(state, ArmyType.FLEET, coord)
    cargo = _add_army(state, ArmyType.LEGION, coord)
    cargo.transported_by = carrier.army_id
    save_game(tmp_path, meta.slug, state)

    response = client.post(f"/games/{meta.slug}/armies/{cargo.army_id}/disembark", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.armies[cargo.army_id].transported_by is None
    assert b"Not boarded on anything" in response.data


def test_army_disembark_an_unboarded_army_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army_id = next(iter(state.armies))

    response = client.post(f"/games/{meta.slug}/armies/{army_id}/disembark", follow_redirects=True)

    assert response.status_code == 200


def test_army_edit_offers_only_leaders_at_the_armys_own_location(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]
    # Excludes Kings specifically: a King's own name can coincidentally
    # match his Kingdom's own name (e.g. this fixture's "Elara"), which
    # would also appear in this same page's unrelated Kingdom dropdown.
    elsewhere_leader = next(
        leader for leader in state.leaders.values() if leader.location != home and not leader.is_king
    )

    response = client.get(f"/games/{meta.slug}/armies/{army.army_id}")

    assert response.status_code == 200
    assert "Aldric".encode() in response.data
    assert elsewhere_leader.name.encode() not in response.data


def test_save_army_can_assign_a_co_located_leader_as_commander(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]
    leader = state.leaders_at(home)[0]

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": army.quality.name,
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(home.x),
            "location_y": str(home.y),
            "commanded_by": str(leader.leader_id),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.armies[army.army_id].commanded_by == leader.leader_id


def test_save_army_rejects_a_commander_not_at_the_armys_own_location(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]
    elsewhere_leader = next(leader for leader in state.leaders.values() if leader.location != home)

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": army.quality.name,
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(home.x),
            "location_y": str(home.y),
            "commanded_by": str(elsewhere_leader.leader_id),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must already be at this Army" in response.data


def test_save_army_can_clear_the_commander(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]
    leader = state.leaders_at(home)[0]
    client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": army.quality.name,
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(home.x),
            "location_y": str(home.y),
            "commanded_by": str(leader.leader_id),
        },
    )

    client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": army.quality.name,
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(home.x),
            "location_y": str(home.y),
            "commanded_by": "",
        },
    )

    _, state = open_game(tmp_path, meta.slug)
    assert state.armies[army.army_id].commanded_by is None


def test_save_army_with_invalid_commander_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": army.quality.name,
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(home.x),
            "location_y": str(home.y),
            "commanded_by": "999999",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Commander" in response.data


def test_save_army_leaves_a_stale_commander_untouched_by_an_unrelated_edit(tmp_path):
    # If the Army's own current commander has since moved away, saving
    # this form for an unrelated change (e.g. Quality) must not silently
    # clear that still-recorded assignment -- only *assigning a new*
    # Commander enforces co-location (army_save()'s own docstring note).
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    home = state.kingdoms[1].home_province
    army = state.armies_at(home)[0]
    leader = state.leaders_at(home)[0]
    client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": army.quality.name,
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(home.x),
            "location_y": str(home.y),
            "commanded_by": str(leader.leader_id),
        },
    )
    _, state = open_game(tmp_path, meta.slug)
    # Move the commander away without touching the Army at all.
    state.leaders[leader.leader_id].location = HexCoord(home.x + 1, home.y)
    save_game(tmp_path, meta.slug, state)

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": army.army_type.name,
            "quality": "ELITE",
            "kingdom_id": str(army.kingdom_id) if army.kingdom_id is not None else "",
            "location_x": str(home.x),
            "location_y": str(home.y),
            "commanded_by": str(leader.leader_id),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    saved = state.armies[army.army_id]
    assert saved.quality == Quality.ELITE
    assert saved.commanded_by == leader.leader_id


def test_save_army_with_invalid_army_type_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={"army_type": "NOT_A_TYPE", "quality": "ELITE", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid army type" in response.data


def test_save_army_with_invalid_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}",
        data={
            "army_type": "LEGION",
            "quality": "AVERAGE",
            "kingdom_id": "999",
            "location_x": "0",
            "location_y": "0",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Kingdom" in response.data


def test_save_army_missing_army_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/armies/999999",
        data={"army_type": "LEGION", "quality": "AVERAGE", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Army not found" in response.data


def test_army_effects_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}/effects",
        data={
            "movement_points": "3",
            "unhireable_this_turn": "on",
            "march_bonus_applied_this_turn": "on",
            "naval_bonus_applied_this_turn": "on",
            "march_table_bonus_applied_this_turn": "on",
            "flood_dams_exempt_at_x": "4",
            "flood_dams_exempt_at_y": "5",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    saved = state.armies[army.army_id]
    assert saved.movement_points == 3
    assert saved.unhireable_this_turn is True
    assert saved.march_bonus_applied_this_turn is True
    assert saved.naval_bonus_applied_this_turn is True
    assert saved.march_table_bonus_applied_this_turn is True
    assert saved.flood_dams_exempt_at == HexCoord(4, 5)


def test_army_effects_save_can_clear_back_to_defaults(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))
    client.post(
        f"/games/{meta.slug}/armies/{army.army_id}/effects",
        data={
            "movement_points": "3",
            "unhireable_this_turn": "on",
            "march_bonus_applied_this_turn": "on",
            "naval_bonus_applied_this_turn": "on",
            "march_table_bonus_applied_this_turn": "on",
            "flood_dams_exempt_at_x": "4",
            "flood_dams_exempt_at_y": "5",
        },
    )

    client.post(f"/games/{meta.slug}/armies/{army.army_id}/effects", data={})

    _, state = open_game(tmp_path, meta.slug)
    saved = state.armies[army.army_id]
    assert saved.movement_points == 0
    assert saved.unhireable_this_turn is False
    assert saved.march_bonus_applied_this_turn is False
    assert saved.naval_bonus_applied_this_turn is False
    assert saved.march_table_bonus_applied_this_turn is False
    assert saved.flood_dams_exempt_at is None


def test_army_effects_save_rejects_a_non_numeric_movement_points(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))
    before_movement_points = army.movement_points

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}/effects",
        data={"movement_points": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Movement Points must be a whole number" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.armies[army.army_id].movement_points == before_movement_points


def test_army_effects_save_rejects_a_half_filled_flood_coordinate(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.post(
        f"/games/{meta.slug}/armies/{army.army_id}/effects",
        data={"flood_dams_exempt_at_x": "4"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"both coordinates" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.armies[army.army_id].flood_dams_exempt_at is None


def test_army_effects_save_missing_army_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/armies/999999/effects", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Army not found" in response.data


def test_army_effects_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/armies/1/effects", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_army_edit_shows_the_turn_effects_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army = next(iter(state.armies.values()))

    response = client.get(f"/games/{meta.slug}/armies/{army.army_id}")

    assert response.status_code == 200
    assert b"Turn Effects" in response.data


def test_armies_create_adds_a_new_army_with_real_movement_points(tmp_path):
    # Before this route existed, the GM world editors could edit an
    # existing Army but had no way to add a brand-new one at all.
    from ak_engine.models.army_type import ARMY_TABLE

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    kingdom_id = next(iter(state.kingdoms))
    before_ids = set(state.armies)

    response = client.post(
        f"/games/{meta.slug}/armies/new",
        data={
            "army_type": "LEGION",
            "quality": "ELITE",
            "kingdom_id": str(kingdom_id),
            "location_x": "3",
            "location_y": "2",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    new_ids = set(state.armies) - before_ids
    assert len(new_ids) == 1
    army = state.armies[next(iter(new_ids))]
    assert army.army_type == ArmyType.LEGION
    assert army.quality == Quality.ELITE
    assert army.kingdom_id == kingdom_id
    assert army.location == HexCoord(3, 2)
    # Matches how a freshly-generated army is seeded (worldgen/generate_
    # new_game.py) -- not the dataclass's own 0 default, which would
    # leave the army unable to move until the next turn's replenishment.
    assert army.movement_points == ARMY_TABLE[ArmyType.LEGION].speed


def test_armies_create_as_unowned_mercenary(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.armies)

    response = client.post(
        f"/games/{meta.slug}/armies/new",
        data={"army_type": "LEGION", "quality": "AVERAGE", "kingdom_id": "", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    new_ids = set(state.armies) - before_ids
    assert len(new_ids) == 1
    assert state.armies[next(iter(new_ids))].kingdom_id is None


def test_armies_create_with_invalid_army_type_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.armies)

    response = client.post(
        f"/games/{meta.slug}/armies/new",
        data={"army_type": "NOT_A_TYPE", "quality": "ELITE", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid army type" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.armies) == before_ids


def test_armies_create_with_invalid_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.armies)

    response = client.post(
        f"/games/{meta.slug}/armies/new",
        data={
            "army_type": "LEGION",
            "quality": "AVERAGE",
            "kingdom_id": "999",
            "location_x": "0",
            "location_y": "0",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Kingdom" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.armies) == before_ids


def test_armies_create_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/armies/new",
        data={"army_type": "LEGION", "quality": "AVERAGE", "location_x": "0", "location_y": "0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_army_delete_removes_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    army_id = next(iter(state.armies))

    response = client.post(f"/games/{meta.slug}/armies/{army_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert army_id not in state.armies


def test_army_delete_missing_army_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.armies)

    response = client.post(f"/games/{meta.slug}/armies/999999/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.armies) == before_ids


def test_army_delete_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/armies/1/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_features_list_before_world_creation_shows_a_message_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/features")

    assert response.status_code == 200
    assert b"no world yet" in response.data


def test_features_list_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/features", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_features_list_shows_generated_features(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/features")

    assert response.status_code == 200
    assert b"<table" in response.data


def test_features_list_shows_a_hex_map_svg(tmp_path):
    # Phase 985: the Features page gets the same colored world map the
    # Provinces page already has, with its own gold marker on every
    # province that carries a Special Feature.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/features")

    assert response.status_code == 200
    assert b"svg" in response.data
    assert b"class=\"hex-map\"" in response.data
    assert b"Special Feature" in response.data


def test_features_list_before_world_creation_has_no_hex_map(tmp_path):
    meta = create_game(tmp_path, "No World Yet")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/features")

    assert response.status_code == 200
    assert b"class=\"hex-map\"" not in response.data


def _first_feature_id(tmp_path, slug):
    _, state = open_game(tmp_path, slug)
    return next(iter(state.features))


def test_feature_edit_shows_the_current_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)

    response = client.get(f"/games/{meta.slug}/features/{feature_id}")

    assert response.status_code == 200
    assert b'<select id="kind" name="kind">' in response.data


def test_feature_edit_missing_feature_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/features/999999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Feature not found" in response.data


def test_feature_delete_removes_it(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)

    response = client.post(f"/games/{meta.slug}/features/{feature_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert feature_id not in state.features


def test_feature_delete_missing_feature_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    before_ids = set(state.features)

    response = client.post(f"/games/{meta.slug}/features/999999/delete", follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert set(state.features) == before_ids


def test_feature_delete_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/features/1/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_save_feature_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}",
        data={
            "kind": "DUNGEON",
            "guardian_monster": "GR_DRAGON",
            "guardian_alignment": "EVIL",
            "treasure": "GOLD_HOARD_HUGE",
            "magic_location": "",
            "magic_power": "",
            "looted": "on",
            "magically_hidden": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    feature = state.features[feature_id]
    assert feature.kind.name == "DUNGEON"
    assert feature.guardian_monster.name == "GR_DRAGON"
    assert feature.guardian_alignment.name == "EVIL"
    assert feature.treasure.name == "GOLD_HOARD_HUGE"
    assert feature.magic_location is None
    assert feature.magic_power is None
    assert feature.looted is True
    assert feature.magically_hidden is True


def test_save_feature_can_clear_looted_and_magically_hidden(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)
    client.post(
        f"/games/{meta.slug}/features/{feature_id}",
        data={"kind": "DUNGEON", "looted": "on", "magically_hidden": "on"},
    )

    client.post(f"/games/{meta.slug}/features/{feature_id}", data={"kind": "DUNGEON"})

    _, state = open_game(tmp_path, meta.slug)
    feature = state.features[feature_id]
    assert feature.looted is False
    assert feature.magically_hidden is False


def test_feature_edit_shows_looted_and_magically_hidden_as_checked(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)
    client.post(
        f"/games/{meta.slug}/features/{feature_id}",
        data={"kind": "DUNGEON", "looted": "on"},
    )

    response = client.get(f"/games/{meta.slug}/features/{feature_id}")

    assert response.status_code == 200
    assert b'name="looted" checked' in response.data
    assert b'name="magically_hidden" checked' not in response.data


def test_save_feature_with_invalid_kind_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}",
        data={"kind": "NOT_A_KIND"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid feature type" in response.data


def test_save_feature_missing_feature_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/features/999999",
        data={"kind": "DUNGEON"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Feature not found" in response.data


def test_feature_status_save_persists_the_new_values(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)
    _, state = open_game(tmp_path, meta.slug)
    leader_id = next(iter(state.leaders))

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}/status",
        data={
            "pending_deal_leader_id": str(leader_id),
            "discovered_1": "2",
            "discovered_2": "3",
            "guardian_talk_reply_id": "R_RIDDLE",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    feature = state.features[feature_id]
    assert feature.pending_deal_leader_id == leader_id
    assert feature.discovered_by_kingdom.get(1) == 2
    assert feature.discovered_by_kingdom.get(2) == 3
    assert feature.guardian_talk_reply_id == MonsterTalkReply.R_RIDDLE.value


def test_feature_status_save_can_clear_back_to_defaults(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)
    _, state = open_game(tmp_path, meta.slug)
    leader_id = next(iter(state.leaders))
    client.post(
        f"/games/{meta.slug}/features/{feature_id}/status",
        data={
            "pending_deal_leader_id": str(leader_id),
            "discovered_1": "2",
            "guardian_talk_reply_id": "R_RIDDLE",
        },
    )

    client.post(f"/games/{meta.slug}/features/{feature_id}/status", data={})

    _, state = open_game(tmp_path, meta.slug)
    feature = state.features[feature_id]
    assert feature.pending_deal_leader_id is None
    assert feature.discovered_by_kingdom == {}
    assert feature.guardian_talk_reply_id is None


def test_feature_status_save_rejects_an_invalid_guardian_talk_reply(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}/status",
        data={"guardian_talk_reply_id": "NOT_A_REPLY"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Guardian Talk Reply" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.features[feature_id].guardian_talk_reply_id is None


def test_feature_status_save_rejects_an_invalid_pending_deal_leader(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}/status",
        data={"pending_deal_leader_id": "999999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Pending Deal Leader" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.features[feature_id].pending_deal_leader_id is None


def test_feature_status_save_rejects_an_out_of_range_discovery_level(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)
    _, state = open_game(tmp_path, meta.slug)
    before = dict(state.features[feature_id].discovered_by_kingdom)

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}/status",
        data={"discovered_1": "9"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be 0-3" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.features[feature_id].discovered_by_kingdom == before


def test_feature_status_save_rejects_a_non_numeric_discovery_level(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)
    _, state = open_game(tmp_path, meta.slug)
    before = dict(state.features[feature_id].discovered_by_kingdom)

    response = client.post(
        f"/games/{meta.slug}/features/{feature_id}/status",
        data={"discovered_1": "lots"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"must be whole numbers" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.features[feature_id].discovered_by_kingdom == before


def test_feature_status_save_missing_feature_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/features/999999/status", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Feature not found" in response.data


def test_feature_status_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/features/1/status", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_feature_edit_shows_the_discovery_and_deal_status_panel(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    feature_id = _first_feature_id(tmp_path, meta.slug)

    response = client.get(f"/games/{meta.slug}/features/{feature_id}")

    assert response.status_code == 200
    assert b"Discovery" in response.data and b"Deal Status" in response.data
    assert b"Guardian Talk Reply" in response.data


def test_turn_zero_list_before_world_creation_shows_a_message_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/turn0")

    assert response.status_code == 200
    assert b"no world yet" in response.data


def test_turn_zero_list_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/turn0", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turn_zero_list_shows_every_kingdom(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turn0")

    assert response.status_code == 200
    assert b"Aldric" in response.data
    assert b"Elara" in response.data


def test_turn_zero_view_shows_the_report_and_no_action_report_section(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turn0/1")

    assert response.status_code == 200
    assert b"PROVINCES" in response.data
    assert b"ACTION REPORT" not in response.data


def test_turn_zero_view_unknown_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turn0/999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_turn_zero_view_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/turn0/1", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turn_zero_download_serves_a_text_attachment(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turn0/1/download")

    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert "attachment" in response.headers["Content-Disposition"]
    assert b"PROVINCES" in response.data


def test_turn_zero_download_unknown_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turn0/999/download", follow_redirects=True)

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_turn_zero_download_xk_serves_a_real_xk_file(tmp_path):
    from ak_engine.parser.xk_world import parse_xk_world
    import pathlib
    import tempfile

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turn0/1/download/xk")

    assert response.status_code == 200
    assert response.mimetype == "application/octet-stream"
    assert "attachment" in response.headers["Content-Disposition"]
    path = pathlib.Path(tempfile.mktemp())
    try:
        path.write_bytes(response.data)
        world = parse_xk_world(path)
    finally:
        path.unlink(missing_ok=True)
    assert world.header.kingdom_id == 1


def test_turn_zero_download_xk_unknown_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turn0/999/download/xk", follow_redirects=True)

    assert response.status_code == 200
    assert b"Kingdom not found" in response.data


def test_turn_zero_reports_do_not_advance_the_turn_number(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    client.get(f"/games/{meta.slug}/turn0/1")
    client.get(f"/games/{meta.slug}/turn0/1/download")

    _, state = open_game(tmp_path, meta.slug)
    assert state.turn_number == 1


_REAL_MOVE_FILE = (Path(__file__).resolve().parents[2] / "AK3__T1.K1").read_bytes()


def _upload_move_file(client, slug, filename, content=_REAL_MOVE_FILE):
    return client.post(
        f"/games/{slug}/turns/upload",
        data={"move_file": (BytesIO(content), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_turns_hub_before_world_creation_shows_a_message_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.get(f"/games/{meta.slug}/turns")

    assert response.status_code == 200
    assert b"no world yet" in response.data


def test_turns_hub_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/turns", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turns_hub_shows_not_uploaded_for_every_kingdom(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turns")

    assert response.status_code == 200
    assert b"Turn 1" in response.data
    assert b"Not uploaded" in response.data


def test_turns_hub_shows_no_emperor_banner_before_any_election(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turns")

    assert response.status_code == 200
    assert b"has been crowned" not in response.data


def test_turns_hub_shows_the_emperor_banner_once_one_is_crowned(tmp_path):
    # The game's own real sample move file (AK3__T1.K1) is enough on its
    # own to crown an Emperor by the end of Turn 1 -- confirmed via a real
    # end-to-end run, not assumed.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")
    client.post(f"/games/{meta.slug}/turns/process")

    response = client.get(f"/games/{meta.slug}/turns")

    assert response.status_code == 200
    assert b"has been crowned" in response.data
    assert b"Aldric" in response.data


def test_upload_move_file_shows_it_as_uploaded(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = _upload_move_file(client, meta.slug, "AK3__T1.K1")

    assert response.status_code == 200
    assert b"AK3__T1.K1" in response.data
    assert b"Not uploaded" in response.data  # still true for the other Kingdom (K2)


def test_upload_move_file_with_no_file_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/turns/upload", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Please choose a move file" in response.data


def test_upload_invalid_move_file_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = _upload_move_file(client, meta.slug, "garbage.K1", content=b"not a real move file")

    assert response.status_code == 200
    assert b"not a valid move file" in response.data


def test_upload_move_file_for_an_unknown_kingdom_shows_an_error_and_does_not_affect_real_kingdoms(tmp_path):
    # A copy of a real sample renamed to an unrelated .K99 parses cleanly
    # on its own (confirmed) -- without a Kingdom-membership check, it
    # would be accepted and, on processing, sync_leaders_from_kingdom()
    # would reassign a real leader's kingdom_id to the nonexistent #99.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)  # Kingdoms 1 (Aldric) and 2 (Elara) only

    response = _upload_move_file(client, meta.slug, "AK3__T1.K99")

    assert response.status_code == 200
    assert b"not a valid move file" in response.data
    # Neither real Kingdom shows an upload -- the bad file was rejected
    # outright, not silently attributed to one of them.
    assert response.data.count(b"Not uploaded") == 2


def test_remove_uploaded_move_file_removes_it(tmp_path):
    # The upload form's own instructional text also mentions "AK3__T1.K1"
    # as an example filename, so check the upload-status count instead of
    # the filename's bare absence.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")

    response = client.post(f"/games/{meta.slug}/turns/1/remove", follow_redirects=True)

    assert response.status_code == 200
    assert response.data.count(b"Not uploaded") == 2


def test_turns_upload_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = _upload_move_file(client, "does-not-exist", "AK3__T1.K1")

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_process_turn_advances_state_and_redirects_to_the_report(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")

    response = client.post(f"/games/{meta.slug}/turns/process", follow_redirects=True)

    assert response.status_code == 200
    assert b"Turn 1 Reports" in response.data
    _, state = open_game(tmp_path, meta.slug)
    assert state.turn_number == 2


def test_turns_diplomacy_shows_the_default_neutral_relation(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)  # Kingdoms 1 (Aldric) and 2 (Elara)

    response = client.get(f"/games/{meta.slug}/turns/diplomacy")

    assert response.status_code == 200
    assert b"Aldric" in response.data
    assert b"Elara" in response.data
    assert b"Neutral" in response.data


def test_turns_diplomacy_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/turns/diplomacy", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turns_diplomacy_save_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/turns/diplomacy", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turns_diplomacy_save_with_no_orders_is_a_no_op(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(f"/games/{meta.slug}/turns/diplomacy", data={}, follow_redirects=True)

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.treat_permissions == set()
    assert state.break_treat_orders == set()


def test_turns_diplomacy_mutual_treat_upgrades_relation_once_the_turn_is_processed(tmp_path):
    # Before Phase 1027, nothing in the GM web interface could ever
    # populate treat_permissions/break_treat_orders -- apply_treat_
    # orders() was real but entirely unreachable from a real game. This
    # is the end-to-end proof the gap is actually closed: both Kings
    # (1=Aldric, 2=Elara, Neutral to each other by default) issue a
    # mutual Treat here, then processing the turn should upgrade them
    # straight to Allied (Neutral -> Allied, rulebook [8.2]).
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    client.post(
        f"/games/{meta.slug}/turns/diplomacy",
        data={"order_1_2": "treat", "order_2_1": "treat"},
    )
    _, state = open_game(tmp_path, meta.slug)
    assert state.treat_permissions == {(1, 2), (2, 1)}

    client.post(f"/games/{meta.slug}/turns/process")

    _, state = open_game(tmp_path, meta.slug)
    assert state.is_allied(1, 2)
    # Turn-scoped fields are cleared again once the turn that consumed
    # them has been processed.
    assert state.treat_permissions == set()


def test_turns_diplomacy_set_relation_overrides_it_directly(tmp_path):
    # Scenario setup: start two Kingdoms already at War, without playing
    # out any Treat/Break Treat orders at all.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/turns/diplomacy/set-relation",
        data={"kingdom_a": "1", "kingdom_b": "2", "relation": "ENEMY"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    assert state.diplomatic_relation(1, 2).name == "ENEMY"


def test_turns_diplomacy_set_relation_to_allied_stamps_the_since_timestamp(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    client.post(
        f"/games/{meta.slug}/turns/diplomacy/set-relation",
        data={"kingdom_a": "1", "kingdom_b": "2", "relation": "ALLIED"},
    )

    _, state = open_game(tmp_path, meta.slug)
    assert state.is_allied(1, 2)
    assert state.diplomatic_relations_since[frozenset({1, 2})] == state.turn_number


def test_turns_diplomacy_set_relation_rejects_the_same_kingdom_twice(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/turns/diplomacy/set-relation",
        data={"kingdom_a": "1", "kingdom_b": "1", "relation": "ALLIED"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"can&#39;t have a relation with itself" in response.data


def test_turns_diplomacy_set_relation_with_invalid_kingdom_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/turns/diplomacy/set-relation",
        data={"kingdom_a": "1", "kingdom_b": "999", "relation": "ALLIED"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid Kingdoms" in response.data


def test_turns_diplomacy_set_relation_with_invalid_relation_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/turns/diplomacy/set-relation",
        data={"kingdom_a": "1", "kingdom_b": "2", "relation": "NOT_A_RELATION"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid relation" in response.data


def test_turns_diplomacy_set_relation_rejects_teamed(tmp_path):
    # TEAMED is deliberately never offered here (see the route's own
    # comment) -- a direct POST attempting it must still be rejected,
    # not silently accepted.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/turns/diplomacy/set-relation",
        data={"kingdom_a": "1", "kingdom_b": "2", "relation": "TEAMED"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid relation" in response.data


def test_turns_diplomacy_set_relation_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/turns/diplomacy/set-relation",
        data={"kingdom_a": "1", "kingdom_b": "2", "relation": "ALLIED"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turns_diplomacy_shows_a_set_to_dropdown_for_each_pair(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turns/diplomacy")

    assert response.status_code == 200
    assert b"Set To" in response.data
    assert b'name="kingdom_a" value="1"' in response.data
    assert b'name="kingdom_b" value="2"' in response.data


def test_process_turn_without_a_world_shows_an_error_not_a_crash(tmp_path):
    meta = create_game(tmp_path, "Third Campaign")
    client = _client(tmp_path)

    response = client.post(f"/games/{meta.slug}/turns/process", follow_redirects=True)

    assert response.status_code == 200
    assert b"no world yet" in response.data


def test_process_turn_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post("/games/does-not-exist/turns/process", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turn_report_list_for_unprocessed_turn_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/turns/1/report", follow_redirects=True)

    assert response.status_code == 200
    assert b"hasn&#39;t been processed yet" in response.data or b"hasn't been processed yet" in response.data


def test_turn_report_list_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/turns/1/report", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_turn_report_view_and_download_after_processing(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")
    client.post(f"/games/{meta.slug}/turns/process")

    view = client.get(f"/games/{meta.slug}/turns/1/report/1")
    download = client.get(f"/games/{meta.slug}/turns/1/report/1/download")

    assert view.status_code == 200
    assert b"PROVINCES" in view.data
    assert download.status_code == 200
    assert download.mimetype == "text/plain"
    assert "attachment" in download.headers["Content-Disposition"]


def test_turn_report_download_xk_after_processing_serves_a_real_xk_file(tmp_path):
    from ak_engine.parser.xk_world import parse_xk_world
    import pathlib
    import tempfile

    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")
    client.post(f"/games/{meta.slug}/turns/process")

    response = client.get(f"/games/{meta.slug}/turns/1/report/1/download/xk")

    assert response.status_code == 200
    assert response.mimetype == "application/octet-stream"
    assert "attachment" in response.headers["Content-Disposition"]
    path = pathlib.Path(tempfile.mktemp())
    try:
        path.write_bytes(response.data)
        world = parse_xk_world(path)
    finally:
        path.unlink(missing_ok=True)
    assert world.header.kingdom_id == 1


def test_turn_report_download_xk_missing_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")
    client.post(f"/games/{meta.slug}/turns/process")

    response = client.get(f"/games/{meta.slug}/turns/1/report/999/download/xk", follow_redirects=True)

    assert response.status_code == 200
    assert b"XK file not found" in response.data


def test_turn_report_view_missing_report_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")
    client.post(f"/games/{meta.slug}/turns/process")

    response = client.get(f"/games/{meta.slug}/turns/1/report/999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Report not found" in response.data


def test_turn_report_view_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/turns/1/report/1", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_processing_a_turn_with_a_missing_kingdom_still_succeeds(tmp_path):
    # Only Kingdom 1 uploads -- Kingdom 2 gets the real missed-deadline
    # Defend/Wait auto-fill (process_turn()'s own existing behavior), not
    # an error.
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _upload_move_file(client, meta.slug, "AK3__T1.K1")

    response = client.post(f"/games/{meta.slug}/turns/process", follow_redirects=True)

    assert response.status_code == 200
    view = client.get(f"/games/{meta.slug}/turns/1/report/2")
    assert view.status_code == 200


def test_feature_new_shows_the_next_feature_id(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    expected_next_id = max(state.features.keys(), default=0) + 1

    response = client.get(f"/games/{meta.slug}/provinces/0/0/features/new")

    assert response.status_code == 200
    assert f"Feature <strong>#{expected_next_id}</strong>".encode() in response.data


def test_feature_new_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/999/999/features/new", follow_redirects=True)

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_feature_new_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.get("/games/does-not-exist/provinces/0/0/features/new", follow_redirects=True)

    assert response.status_code == 200
    assert b"Game not found" in response.data


def test_create_feature_persists_it_with_the_right_id_and_coord(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    _, state = open_game(tmp_path, meta.slug)
    expected_id = max(state.features.keys(), default=0) + 1

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0/features/new",
        data={
            "kind": "CAVE",
            "guardian_monster": "GO_DRAGON",
            "treasure": "GOLD_HOARD_LARGE",
            "guardian_alignment": "",
            "magic_location": "",
            "magic_power": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    feature = state.features[expected_id]
    assert feature.coord == HexCoord(0, 0)
    assert feature.kind.name == "CAVE"
    assert feature.guardian_monster.name == "GO_DRAGON"
    assert feature.treasure.name == "GOLD_HOARD_LARGE"
    assert feature.guardian_alignment is None
    # The new feature's own edit page is shown right after creation.
    assert b"Gold Dragon" in response.data


def test_create_feature_with_invalid_kind_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/0/0/features/new",
        data={"kind": "NOT_A_KIND"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"valid feature type" in response.data


def test_create_feature_missing_province_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.post(
        f"/games/{meta.slug}/provinces/999/999/features/new",
        data={"kind": "CAVE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Province not found" in response.data


def test_create_feature_missing_game_shows_an_error_not_a_crash(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/games/does-not-exist/provinces/0/0/features/new",
        data={"kind": "CAVE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Game not found" in response.data


# -- display_name() -- the Jinja filter every editor screen renders enum
# members through -- real curated names, not a naive "underscore -> title
# case" guess at the enum identifier.


def test_display_name_uses_the_curated_name_when_one_exists():
    # Race.ELVEN's own curated RACE_NAME is "Elf" -- "Elven".title() would
    # have been a plausible-looking but wrong guess.
    assert display_name(Race.ELVEN) == "Elf"
    # ArmyType.LT_CAVALRY's own curated name spells out the abbreviation.
    assert display_name(ArmyType.LT_CAVALRY) == "Light Cavalry"
    # Monster.GO_DRAGON's own curated name is "Gold Dragon" -- the bare
    # identifier prettifies to the wrong "Go Dragon" ("Go" is the real
    # game's own abbreviation for "Gold", not a separate word).
    assert display_name(Monster.GO_DRAGON) == "Gold Dragon"


def test_display_name_prefers_the_real_adventure_report_gold_hoard_names():
    # models/treasure.py TREASURE_NAME alone gives the 3 gold-hoard tiers
    # only their bare "Hoard" (TREASURE.X2's own flavor-name extraction,
    # that module's own docstring says, "not what the report actually
    # prints") -- GOLD_HOARD_DISPLAY_NAME's own real ADVENTURE-report text
    # must win for exactly these 3 members.
    assert display_name(Treasure.GOLD_HOARD_LARGE) == "Large Hoard of Gold"
    assert display_name(Treasure.GOLD_HOARD_HUGE) == "Huge Hoard of Gold"
    assert display_name(Treasure.GOLD_HOARD_FABULOUS) == "Fabulous Hoard of Gold"


def test_display_name_uses_alignments_own_real_value_not_the_identifier():
    # Alignment.ANTI_HOLY.value is already "Anti-Holy" -- the bare
    # identifier's own naive prettification would give "Anti Holy" (no
    # hyphen) instead.
    assert display_name(Alignment.ANTI_HOLY) == "Anti-Holy"
    assert display_name(Alignment.DRUID) == "Druidic"


def test_display_name_falls_back_to_the_bare_identifier_when_uncurated():
    # Race.DROW has no entry in RACE_NAME (a documented gap in that dict
    # itself) -- falls back to a plain title-cased identifier rather than
    # raising.
    assert display_name(Race.DROW) == "Drow"


def test_display_name_handles_an_enum_with_no_curated_dict_at_all():
    # Sex has no curated *_NAME dict anywhere in this project -- the bare
    # identifier is already exactly right.
    assert display_name(Sex.MALE) == "Male"


def test_display_name_of_none_is_empty_string():
    assert display_name(None) == ""


def test_province_edit_shows_the_real_curated_recruit_type_names(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)

    response = client.get(f"/games/{meta.slug}/provinces/0/0")

    assert b"Light Cavalry" in response.data
    assert b"Lt Cavalry" not in response.data


def test_leader_edit_shows_the_real_curated_race_name(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)  # leader 2 is Elara, Elven

    response = client.get(f"/games/{meta.slug}/leaders/2")

    # Scoped to the Race <select> specifically: a curated Treasure name
    # elsewhere on this same page ("Bow of the Elven Kings," the Items
    # Held panel's own Treasure dropdown) legitimately contains "Elven"
    # as part of its own real, curated name -- not the bug this test
    # guards against.
    race_select = response.data.split(b'<select id="race" name="race">')[1].split(b"</select>")[0]
    assert b">Elf<" in race_select
    assert b"Elven" not in race_select
