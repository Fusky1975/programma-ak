"""The Order of Duelists' +1 Melee/Archery (Neutral Kingdoms) counts only against Heroes or
humanoid monsters ([5.0]); the Duellist's Medal likewise needs a humanoid opponent."""

from __future__ import annotations

import random
from unittest.mock import patch

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.turn.encounter import EncounterCombatResult, effective_melee_skill
from ak_engine.turn.random_encounter_execution import monster_combatant
from ak_engine.turn.search_decode import SearchRequest, SearchTactic
from ak_engine.turn.search_execution import execute_search

FIELD = HexCoord(1, 1)


def _state(kingdom_alignment: Alignment, guardian: Monster) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Duelia", Race.HUMAN, kingdom_alignment, FIELD))
    raw = [0] * 31
    raw[Ability.MELEE.value * 2] = 2
    raw[Ability.MELEE.value * 2 + 1] = 9
    state.add_leader(LeaderState(1, 1, "Hero", FIELD, skills=SkillTable(raw), alignment=Alignment.GOOD))
    state.add_feature(Feature(feature_id=1, coord=FIELD, kind=FeatureType.DUNGEON, guardian_monster=guardian))
    return state


def _search_melee_skills(state: GameState) -> tuple[int, bool]:
    """Runs a Melee-only Search and returns the leader's effective Melee skill and whether the
    guardian counted as humanoid, as seen by the duel."""

    seen: list = []

    def _capture(a, b, rng, **kwargs):
        seen.extend([a, b])
        return EncounterCombatResult(winner="a", rounds=1)

    request = SearchRequest(feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])
    with patch("ak_engine.turn.search_execution.resolve_melee_duel", side_effect=_capture), patch(
        "ak_engine.turn.search_execution.roll_monster_alignment", return_value=Alignment.GOOD
    ):
        execute_search(state, 1, request, random.Random(0))
    leader_side, monster_side = seen[0], seen[1]
    return effective_melee_skill(leader_side), monster_side.is_humanoid


def test_a_neutral_hero_gets_the_duelist_bonus_against_a_humanoid_guardian():
    skill, humanoid = _search_melee_skills(_state(Alignment.NEUTRAL, Monster.SWORDSMAN))
    assert humanoid is True
    assert skill == 3  # 2 + the Order of Duelists' +1


def test_a_neutral_hero_gets_no_duelist_bonus_against_a_dragon():
    skill, humanoid = _search_melee_skills(_state(Alignment.NEUTRAL, Monster.R_DRAGON))
    assert humanoid is False
    assert skill == 2


def test_a_non_neutral_hero_never_gets_it():
    skill, _ = _search_melee_skills(_state(Alignment.GOOD, Monster.SWORDSMAN))
    assert skill == 2


@pytest.mark.parametrize(
    "monster,humanoid",
    [(Monster.SWORDSMAN, True), (Monster.GIANT, True), (Monster.WITCH, True), (Monster.R_DRAGON, False), (Monster.DRYAD, False)],
)
def test_wandering_monsters_know_whether_they_are_humanoid(monster, humanoid):
    assert monster_combatant(monster, random.Random(1)).is_humanoid is humanoid
