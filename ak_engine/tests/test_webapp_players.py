"""Tests for webapp/players.py -- the pre-world-creation King roster
(Phase 2 of the GM interface)."""

from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.webapp.players import (
    MAX_PLAYERS,
    PLAYABLE_ALIGNMENTS,
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


def test_playable_alignments_are_exactly_the_seven_rulebook_ones():
    # RULES.AK [1.0]'s own "(Divine, Good, Druidic, Neutral, Pagan, Evil,
    # Undead)" -- Anti-Holy/Mechanical/Special are monster-only.
    assert set(PLAYABLE_ALIGNMENTS) == {
        Alignment.DIVINE,
        Alignment.GOOD,
        Alignment.DRUID,
        Alignment.NEUTRAL,
        Alignment.PAGAN,
        Alignment.EVIL,
        Alignment.UNDEAD,
    }


def test_add_player_without_temper_or_talents_leaves_them_unset(tmp_path):
    entry = add_player(tmp_path, "Andrea", Race.HUMAN, Alignment.GOOD)

    assert entry.temper_enum is None
    assert entry.talent_allocation_by_ability == {}


def test_add_player_persists_temper_and_talent_allocation(tmp_path):
    entry = add_player(
        tmp_path,
        "Fusky",
        Race.HUMAN,
        Alignment.UNDEAD,
        Temper.BRAVE,
        {Ability.MELEE: 2, Ability.NECROMANCY: 2},
    )

    assert entry.temper_enum is Temper.BRAVE
    assert entry.talent_allocation_by_ability == {Ability.MELEE: 2, Ability.NECROMANCY: 2}

    listed = list_players(tmp_path)
    assert listed[0].temper_enum is Temper.BRAVE
    assert listed[0].talent_allocation_by_ability == {Ability.MELEE: 2, Ability.NECROMANCY: 2}
