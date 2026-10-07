"""Tests for webapp/app.py -- the Flask routes (Phase 1: game registry
screen only; later phases add their own route tests)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.webapp.app import create_app, display_name
from ak_engine.webapp.games import create_game, list_games, open_game


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
            "terrain": "JUNGLE",
            "race": "TROLLISH",
            "tax": "7",
            "recruit_type_1": "PHALANX",
            "recruit_type_2": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    province = state.provinces[HexCoord(0, 0)]
    assert province.terrain.name == "JUNGLE"
    assert province.race.name == "TROLLISH"
    assert province.tax == 7
    assert province.recruit_type_1.name == "PHALANX"
    assert province.recruit_type_2 is None


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
        data={"name": "Aldric the Wise", "race": "HUMAN", "alignment": "EVIL", "temper": "BERSERK", "sex": "MALE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    leader = state.leaders[1]
    assert leader.name == "Aldric the Wise"
    assert leader.alignment.name == "EVIL"
    assert leader.temper.name == "BERSERK"
    assert leader.sex.name == "MALE"


def test_save_leader_can_clear_optional_fields_back_to_unset(tmp_path):
    client = _client(tmp_path)
    meta = _game_with_world(tmp_path, client)
    client.post(
        f"/games/{meta.slug}/leaders/1",
        data={"name": "Aldric", "race": "HUMAN", "alignment": "EVIL", "temper": "BERSERK", "sex": "MALE"},
    )

    client.post(f"/games/{meta.slug}/leaders/1", data={"name": "Aldric", "race": "HUMAN"})

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
        data={"army_type": "HVY_CAVALRY", "quality": "ELITE", "kingdom_id": "", "location_x": "5", "location_y": "3"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    _, state = open_game(tmp_path, meta.slug)
    saved = state.armies[army.army_id]
    assert saved.army_type == ArmyType.HVY_CAVALRY
    assert saved.quality == Quality.ELITE
    assert saved.kingdom_id is None
    assert saved.location == HexCoord(5, 3)


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

    assert b">Elf<" in response.data
    assert b"Elven" not in response.data
