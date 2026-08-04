"""Tests for turn/merit_points.py's Phase 368 additions -- the 6
alignment-King titles plus Chief of Staff/Silver Tongue. See that
module's own Phase 368 docstring addendum for the full derivation.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.merit_points import (
    chiefofstaff_merit_points,
    divinearchangel_merit_points,
    druidking_merit_points,
    goodking_merit_points,
    neutralking_merit_points,
    paganking_merit_points,
    silvertongue_merit_points,
    undeadking_merit_points,
)

HOME = HexCoord(0, 0)


def make_state(alignment: Alignment) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, alignment, HOME, treasury=10))
    return state


def test_divinearchangel_zero_for_wrong_alignment():
    state = make_state(Alignment.NEUTRAL)
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    state.add_leader(king)

    assert divinearchangel_merit_points(state, king) == 0


def test_divinearchangel_zero_for_a_hero_of_the_right_alignment():
    state = make_state(Alignment.DIVINE)
    hero = LeaderState(2, 1, "Wanderer", HOME, is_king=False)
    state.add_leader(hero)

    assert divinearchangel_merit_points(state, hero) == 0


def test_divinearchangel_sums_tax_skill_and_anti_holy_kills():
    state = make_state(Alignment.DIVINE)
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    king.merit_tally.monsters_killed_anti_holy_in_realm_province = 3
    state.add_leader(king)

    # tax base (0, no provinces) + White skill (0, no SkillTable) + 3 anti-holy kills
    assert divinearchangel_merit_points(state, king) == 3


def test_goodking_and_druidking_share_the_same_monster_kill_field():
    good_state = make_state(Alignment.GOOD)
    good_king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    good_king.merit_tally.monsters_killed_anti_holy_or_evil_in_realm_province = 4
    good_state.add_leader(good_king)
    assert goodking_merit_points(good_state, good_king) == 4

    druid_state = make_state(Alignment.DRUID)
    druid_king = LeaderState(1, 1, "Bram", HOME, is_king=True)
    druid_king.merit_tally.monsters_killed_anti_holy_or_evil_in_realm_province = 4
    druid_state.add_leader(druid_king)
    assert druidking_merit_points(druid_state, druid_king) == 4


def test_neutralking_and_paganking_reuse_the_unfiltered_monster_kill_field():
    neutral_state = make_state(Alignment.NEUTRAL)
    neutral_king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    neutral_king.merit_tally.monsters_killed_in_realm_province = 5
    neutral_state.add_leader(neutral_king)
    assert neutralking_merit_points(neutral_state, neutral_king) == 5

    pagan_state = make_state(Alignment.PAGAN)
    pagan_king = LeaderState(1, 1, "Bram", HOME, is_king=True)
    pagan_king.merit_tally.monsters_killed_in_realm_province = 5
    pagan_state.add_leader(pagan_king)
    assert paganking_merit_points(pagan_state, pagan_king) == 5


def test_undeadking_sums_necromancy_kills_and_charm_transformations():
    state = make_state(Alignment.UNDEAD)
    king = LeaderState(1, 1, "Vaelgor", HOME, is_king=True)
    king.merit_tally.monsters_killed_good_druid_neutral_in_realm_province = 2
    king.merit_tally.ch_undead_transformations = 1
    state.add_leader(king)

    assert undeadking_merit_points(state, king) == 3


def test_chiefofstaff_open_to_a_hero_no_alignment_gate():
    state = make_state(Alignment.NEUTRAL)
    hero = LeaderState(2, 1, "Sneak", HOME, is_king=False)
    hero.merit_tally.military_units_recruited = 4
    state.add_leader(hero)

    assert chiefofstaff_merit_points(state, hero) == 4


def test_chiefofstaff_live_commanded_units_flat_plus_quality_bonus():
    state = make_state(Alignment.NEUTRAL)
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    state.add_leader(king)
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, HOME, commanded_by=1))
    state.add_army(ArmyState(2, 1, ArmyType.LEGION, Quality.CRACK, HOME, commanded_by=1))

    # 0 recruited + 0.25*2 commanded + (0 Green bonus + 0.20 Crack bonus)
    assert chiefofstaff_merit_points(state, king) == 0.70


def test_silvertongue_king_only():
    state = make_state(Alignment.NEUTRAL)
    hero = LeaderState(2, 1, "Sneak", HOME, is_king=False)
    hero.merit_tally.alliances_formed = 5
    state.add_leader(hero)

    assert silvertongue_merit_points(state, hero) == 0


def test_silvertongue_sums_alliance_druid_skill_and_discovery_terms():
    state = make_state(Alignment.NEUTRAL)
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    king.merit_tally.alliances_formed = 2
    king.merit_tally.alliance_upkeep_points = 1.5
    king.merit_tally.discoveries_traded = 3
    state.add_leader(king)

    # 2 formed + 1.5 upkeep + 0 Druidic skill (no SkillTable) + 3 traded
    assert silvertongue_merit_points(state, king) == 6.5
