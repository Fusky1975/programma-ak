"""Tests for turn/initiative.py -- see its module docstring for the sourced
"con Marcia contato 3 volte" formula.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.initiative import character_initiative

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HOME))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME))
    return state


def skills_with(**levels: int) -> SkillTable:
    raw_values = [0] * (len(Ability) * 2 + 1)
    for name, level in levels.items():
        i = Ability[name].value * 2
        raw_values[i] = level
        raw_values[i + 1] = level
    return SkillTable(raw_values)


def test_character_initiative_is_zero_for_a_leader_with_no_skill_data():
    state = make_state()
    leader = state.leaders[1]  # skills is None -- Phase 30's own "no data" placeholder

    assert character_initiative(state, leader) == 0


def test_character_initiative_sums_every_ability_plus_two_extra_march_copies():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(MARCH=4, MELEE=2, WHITE=1)

    # ordinary sum (4 + 2 + 1 = 7) plus 2 extra copies of March's own
    # level (2 * 4 = 8) -- equivalent to counting March three times.
    assert character_initiative(state, leader) == 7 + 8


def test_character_initiative_folds_in_discovery_bonuses_for_free():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(TACTICAL=1)
    state.kingdoms[1].discoveries.add(Discovery.LAND_SHIP)  # bonuses Tactical by 1

    # effective_skill_level() already applies the Discovery bonus before
    # character_initiative() ever sums it -- no separate wiring needed.
    without_bonus = 1  # what it would be if the bonus weren't applied
    assert character_initiative(state, leader) > without_bonus


def test_character_initiative_reads_zero_for_a_comatose_leader():
    # Phase 310's own is_comatose short-circuit in effective_skill_level()
    # zeroes out every ability read, including here.
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(MARCH=4, MELEE=2)
    leader.is_comatose = True

    assert character_initiative(state, leader) == 0
