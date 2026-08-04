"""Tests for turn/race_titles.py -- the 11 race-fanaticism Imperial
title Merit Point formulas (Phase 367, reformulated Phase 369). See
that module's own docstring for the full derivation.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState, RaceTitleTally
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.turn.race_titles import (
    RACE_TITLE_OFFICE,
    RACE_TITLE_REQUIRES_OWNED_PROVINCE,
    RACE_TITLE_TURN_GATE,
    race_title_merit_points,
)

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Dwarfhold", Race.DWARVEN, Alignment.NEUTRAL, HOME, treasury=10))
    return state


def test_all_11_races_have_a_consistent_entry_in_every_table():
    assert len(RACE_TITLE_OFFICE) == 11
    for race in RACE_TITLE_OFFICE:
        assert race in RACE_TITLE_TURN_GATE


def test_office_mapping_matches_the_confirmed_office_names():
    assert RACE_TITLE_OFFICE[Race.HUMAN] is Office.HUMAN_KING
    assert RACE_TITLE_OFFICE[Race.ELVEN] is Office.ELVEN_KING
    assert RACE_TITLE_OFFICE[Race.DWARVEN] is Office.DWARVEN_KING
    assert RACE_TITLE_OFFICE[Race.ORCISH] is Office.ORC_LORD
    assert RACE_TITLE_OFFICE[Race.DRAGONS] is Office.DRAGON_LORD
    assert RACE_TITLE_OFFICE[Race.EAGLES] is Office.EAGLE_KING
    assert RACE_TITLE_OFFICE[Race.WHALES] is Office.WHALE_KING
    assert RACE_TITLE_OFFICE[Race.MERMISH] is Office.MERMAN_KING
    assert RACE_TITLE_OFFICE[Race.ENTISH] is Office.ENT_KING
    assert RACE_TITLE_OFFICE[Race.TROLLISH] is Office.TROLL_KING
    assert RACE_TITLE_OFFICE[Race.WEREFOLK] is Office.WERE_KING


def test_only_the_4_core_humanoid_races_skip_the_owned_province_prerequisite():
    assert RACE_TITLE_REQUIRES_OWNED_PROVINCE == {
        Race.DRAGONS,
        Race.EAGLES,
        Race.WHALES,
        Race.MERMISH,
        Race.ENTISH,
        Race.TROLLISH,
        Race.WEREFOLK,
    }


def test_win_and_loss_points_use_the_real_plus1_minus2_weighting():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.HUMAN)
    state.add_leader(king)
    king.race_title_tally[Race.HUMAN] = RaceTitleTally(
        front_line_battles_won_points=3,
        front_line_battles_lost_points=1,
    )

    # (3 - 2*1) = 1, then doubled because the King is Human
    assert race_title_merit_points(state, king, Race.HUMAN) == 2


def test_doubled_only_when_the_leaders_own_race_matches_the_title():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)
    king.race_title_tally[Race.HUMAN] = RaceTitleTally(front_line_battles_won_points=3)

    # Dwarven King scoring the Human title: not doubled
    assert race_title_merit_points(state, king, Race.HUMAN) == 3


def test_special_race_title_reads_0_without_an_owned_province():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)
    king.race_title_tally[Race.DRAGONS] = RaceTitleTally(front_line_battles_won_points=10)

    assert race_title_merit_points(state, king, Race.DRAGONS) == 0


def test_special_race_title_live_once_a_province_is_owned():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.MTNS, Race.DRAGONS, owner_kingdom_id=1))
    king.race_title_tally[Race.DRAGONS] = RaceTitleTally(front_line_battles_won_points=10)

    assert race_title_merit_points(state, king, Race.DRAGONS) == 10


def test_a_hero_with_no_kingdom_always_reads_0_for_a_special_race():
    state = make_state()
    hero = LeaderState(2, None, "Wanderer", HOME, race=Race.DRAGONS)
    state.add_leader(hero)
    hero.race_title_tally[Race.DRAGONS] = RaceTitleTally(front_line_battles_won_points=10)

    assert race_title_merit_points(state, hero, Race.DRAGONS) == 0


def test_no_tally_defaults_to_0():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)

    assert race_title_merit_points(state, king, Race.DWARVEN) == 0
