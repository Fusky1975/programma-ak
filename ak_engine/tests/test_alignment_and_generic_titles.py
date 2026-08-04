"""Tests for turn/merit_points.py's Phase 368 additions, reformulated
Phase 369 -- the 7 alignment-King titles (King of Pain included) plus
Chief of Staff/Silver Tongue/Prince of Thieves. See that module's own
Phase 369 docstring addendum for the full derivation.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.merit_points import (
    chiefofstaff_merit_points,
    divinearchangel_merit_points,
    druidking_merit_points,
    evilking_merit_points,
    goodking_merit_points,
    neutralking_merit_points,
    paganking_merit_points,
    silvertongue_merit_points,
    thiefprince_merit_points,
    undeadking_merit_points,
)

HOME = HexCoord(0, 0)


def make_state(alignment: Alignment) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, alignment, HOME, treasury=10))
    return state


def test_alignment_king_zero_for_wrong_alignment():
    state = make_state(Alignment.NEUTRAL)
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    state.add_leader(king)

    assert divinearchangel_merit_points(state, king) == 0
    assert evilking_merit_points(state, king) == 0


def test_alignment_king_zero_for_a_hero_of_the_right_alignment():
    state = make_state(Alignment.DIVINE)
    hero = LeaderState(2, 1, "Wanderer", HOME, is_king=False)
    state.add_leader(hero)

    assert divinearchangel_merit_points(state, hero) == 0


def test_alignment_king_score_is_plain_tax_base():
    state = make_state(Alignment.DIVINE)
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    state.add_leader(king)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=6))

    assert divinearchangel_merit_points(state, king) == 6


def test_all_7_alignment_king_titles_share_the_same_formula():
    for alignment, formula in (
        (Alignment.DIVINE, divinearchangel_merit_points),
        (Alignment.GOOD, goodking_merit_points),
        (Alignment.DRUID, druidking_merit_points),
        (Alignment.NEUTRAL, neutralking_merit_points),
        (Alignment.PAGAN, paganking_merit_points),
        (Alignment.EVIL, evilking_merit_points),
        (Alignment.UNDEAD, undeadking_merit_points),
    ):
        state = make_state(alignment)
        king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
        state.add_leader(king)
        state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=7))

        assert formula(state, king) == 7


def test_chiefofstaff_open_to_a_hero_sums_the_4_real_skills():
    state = make_state(Alignment.NEUTRAL)
    hero = LeaderState(2, 1, "Sneak", HOME, is_king=False)
    state.add_leader(hero)

    # No SkillTable recorded -- all 4 skills read 0.
    assert chiefofstaff_merit_points(state, hero) == 0


def test_silvertongue_open_to_a_hero_reads_the_single_tally():
    state = make_state(Alignment.NEUTRAL)
    hero = LeaderState(2, 1, "Sneak", HOME, is_king=False)
    hero.merit_tally.diplomatic_merit_points = 12
    state.add_leader(hero)

    assert silvertongue_merit_points(state, hero) == 12


def test_thiefprince_reads_the_single_successful_thefts_tally():
    state = make_state(Alignment.NEUTRAL)
    hero = LeaderState(2, 1, "Sneak", HOME, is_king=False)
    hero.merit_tally.successful_thefts = 4
    state.add_leader(hero)
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    king.merit_tally.successful_thefts = 1
    state.add_leader(king)

    assert thiefprince_merit_points(state, hero) == 4
    assert thiefprince_merit_points(state, king) == 1
