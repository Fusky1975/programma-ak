"""Tests for webapp/world_creation.py -- "Create World" (Phase 4 of the
GM interface): turning a Phase 2 King roster into a real, generated
GameState."""

from __future__ import annotations

import json

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.webapp.games import create_game, game_dir, open_game
from ak_engine.webapp.players import add_player
from ak_engine.webapp.world_creation import (
    RosterOutOfBoundsError,
    WorldAlreadyCreatedError,
    create_world,
)


def _game_with_players(tmp_path, count: int):
    meta = create_game(tmp_path, "Third Campaign")
    directory = game_dir(tmp_path, meta.slug)
    races = [Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH]
    for i in range(count):
        add_player(directory, f"King {i}", races[i % 4], Alignment.NEUTRAL)
    return meta


def test_create_world_with_two_players_populates_the_game(tmp_path):
    meta = _game_with_players(tmp_path, 2)

    updated_meta, state = create_world(tmp_path, meta.slug, seed=1)

    assert updated_meta.kingdom_count == 2
    assert len(state.kingdoms) == 2
    assert len(state.leaders) >= 2
    assert len(state.provinces) > 0


def test_create_world_persists_so_open_game_sees_it(tmp_path):
    meta = _game_with_players(tmp_path, 2)

    create_world(tmp_path, meta.slug, seed=1)

    _, reloaded = open_game(tmp_path, meta.slug)
    assert len(reloaded.kingdoms) == 2


def test_create_world_auto_places_every_kings_home(tmp_path):
    meta = _game_with_players(tmp_path, 3)

    _, state = create_world(tmp_path, meta.slug, seed=7)

    for kingdom_id, kingdom in state.kingdoms.items():
        king_leader = next(leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king)
        assert kingdom.home_province == king_leader.location
        assert kingdom.home_province != HexCoord(0, 0)


def test_create_world_below_min_players_raises(tmp_path):
    meta = _game_with_players(tmp_path, 1)

    with pytest.raises(RosterOutOfBoundsError):
        create_world(tmp_path, meta.slug, seed=1)


def test_create_world_above_max_players_raises(tmp_path):
    # add_player() itself already refuses a 13th King (RosterFullError),
    # so the only way this bound gets exercised is a roster file edited
    # by hand past that guard -- write players.json directly to simulate
    # that, rather than skip testing this bound at all.
    meta = _game_with_players(tmp_path, 12)
    directory = game_dir(tmp_path, meta.slug)
    players = json.loads((directory / "players.json").read_text(encoding="utf-8"))
    players.append({"player_id": 12, "name": "King 12", "race": "HUMAN", "alignment": "NEUTRAL"})
    (directory / "players.json").write_text(json.dumps(players), encoding="utf-8")

    with pytest.raises(RosterOutOfBoundsError):
        create_world(tmp_path, meta.slug, seed=1)


def test_create_world_twice_raises_without_touching_the_first_world(tmp_path):
    meta = _game_with_players(tmp_path, 2)
    create_world(tmp_path, meta.slug, seed=1)
    _, first_state = open_game(tmp_path, meta.slug)
    first_provinces = dict(first_state.provinces)

    with pytest.raises(WorldAlreadyCreatedError):
        create_world(tmp_path, meta.slug, seed=99)

    _, reloaded = open_game(tmp_path, meta.slug)
    assert reloaded.provinces == first_provinces
