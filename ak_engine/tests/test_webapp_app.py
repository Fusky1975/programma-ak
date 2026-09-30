"""Tests for webapp/app.py -- the Flask routes (Phase 1: game registry
screen only; later phases add their own route tests)."""

from __future__ import annotations

from ak_engine.models.map import HexCoord
from ak_engine.models.office import Office
from ak_engine.webapp.app import create_app
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
    client.post(f"/games/{slug}/players", data={"name": name, "race": race, "alignment": alignment})


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
