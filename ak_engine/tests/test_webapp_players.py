"""Tests for webapp/players.py -- the pre-world-creation King roster
(Phase 2 of the GM interface)."""

from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.race import Race
from ak_engine.webapp.players import (
    MAX_PLAYERS,
    PLAYABLE_RACES,
    PlayerNotFoundError,
    RosterFullError,
    add_player,
    list_players,
    remove_player,
)


def test_list_players_on_a_fresh_game_dir_is_empty(tmp_path):
    assert list_players(tmp_path) == []


def test_add_player_makes_it_listable(tmp_path):
    entry = add_player(tmp_path, "Andrea", Race.HUMAN, Alignment.GOOD)

    assert entry.player_id == 0
    assert entry.name == "Andrea"
    assert entry.race_enum is Race.HUMAN
    assert entry.alignment_enum is Alignment.GOOD

    listed = list_players(tmp_path)
    assert len(listed) == 1
    assert listed[0].name == "Andrea"


def test_add_player_assigns_increasing_ids(tmp_path):
    first = add_player(tmp_path, "First", Race.HUMAN, Alignment.GOOD)
    second = add_player(tmp_path, "Second", Race.ELVEN, Alignment.NEUTRAL)

    assert (first.player_id, second.player_id) == (0, 1)


def test_add_player_beyond_max_players_raises(tmp_path):
    for i in range(MAX_PLAYERS):
        add_player(tmp_path, f"King {i}", Race.HUMAN, Alignment.GOOD)

    with pytest.raises(RosterFullError):
        add_player(tmp_path, "One Too Many", Race.HUMAN, Alignment.GOOD)


def test_remove_player_removes_it_from_the_list(tmp_path):
    entry = add_player(tmp_path, "Andrea", Race.HUMAN, Alignment.GOOD)
    add_player(tmp_path, "Someone Else", Race.DWARVEN, Alignment.EVIL)

    remove_player(tmp_path, entry.player_id)

    assert [p.name for p in list_players(tmp_path)] == ["Someone Else"]


def test_remove_player_missing_id_raises(tmp_path):
    with pytest.raises(PlayerNotFoundError):
        remove_player(tmp_path, 99)


def test_playable_races_are_exactly_the_four_engine_supported_ones():
    # worldgen/initial_armies.py BEST_ATYPE only has entries for these --
    # any other race would KeyError in generate_new_game()'s own
    # home_first_slot(king.race) call, so the interface must not offer it.
    assert set(PLAYABLE_RACES) == {Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH}
