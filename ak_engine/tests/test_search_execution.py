from __future__ import annotations

import random
from unittest.mock import patch

from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import MONSTER_COMBAT_STATS, Monster, MonsterSpeed
from ak_engine.turn.encounter import EncounterCombatResult
from ak_engine.turn.search_decode import SearchRequest, SearchTactic
from ak_engine.turn.search_execution import (
    FLEE_CHANCE,
    TROLL_REGENERATION_PER_COMBAT_ROUND,
    SearchExecutionResult,
    execute_search,
)

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
LEADER_ID = 1


def _state_with_leader(*, skills: SkillTable | None = None) -> GameState:
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION, skills=skills))
    return state


def _melee_request(feature_id: int) -> SearchRequest:
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.MELEE)])


def test_execute_search_leader_not_found():
    state = GameState()
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result == SearchExecutionResult(accepted=False, reason="leader not found")


def test_execute_search_feature_not_found():
    state = _state_with_leader()
    result = execute_search(state, LEADER_ID, _melee_request(99))
    assert result.accepted is False
    assert result.reason == "feature not found"


def test_execute_search_already_looted_feature_rejected():
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE, looted=True)
    )
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "feature already looted"


def test_execute_search_no_guardian_recorded_rejected():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=None))
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "feature has no guardian recorded"


def test_execute_search_not_co_located_rejected():
    state = _state_with_leader()
    elsewhere = HexCoord(9, 9)
    state.add_feature(Feature(feature_id=1, coord=elsewhere, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "not co-located with feature"


def test_execute_search_unsourced_guardian_stats_reports_unresolved():
    # Monster.NOMONSTER is the "no monster" sentinel, not a real species --
    # it has no MONSTER_COMBAT_STATS entry by design (Phase 154 gave all
    # 60 real species combat stats, so NOMONSTER is the one remaining
    # guaranteed-unsourced case).
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PET_FOREST, guardian_monster=Monster.NOMONSTER)
    )
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is True
    assert result.combat_resolved is False
    assert "no combat stats" in result.reason


def test_execute_search_previously_unsourced_species_now_resolves():
    # Monster.ROC had no MONSTER_STATS entry before Phase 154; it now has
    # a MONSTER_COMBAT_STATS entry (project-original data) and resolves
    # real combat like any other species.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PET_FOREST, guardian_monster=Monster.ROC))

    result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(1))

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.reason is None


def test_execute_search_no_melee_tactic_reports_unresolved():
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    )
    scout_only = SearchRequest(feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.SCOUT)])

    result = execute_search(state, LEADER_ID, scout_only)

    assert result.accepted is True
    assert result.combat_resolved is False
    assert "no Melee tactic" in result.reason


def test_execute_search_leader_wins_marks_feature_looted():
    # A leader with high Melee skill (level 9) always acts first against
    # a Gargoyle (melee_skill=1); scripted so the leader always hits and
    # the Gargoyle (15 hp) always misses.
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = 9
    raw[Ability.MELEE.value * 2 + 1] = 9
    state = _state_with_leader(skills=SkillTable(raw_values=raw))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]  # leader hits (chance+damage), Gargoyle misses
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert feature.looted is True
    assert LEADER_ID in state.leaders


def test_execute_search_leader_loses_is_removed_from_state():
    # A leaderless-skill searcher (melee_skill=0) faces a Troll
    # (melee_skill=1): the Troll always acts first and always hits;
    # the leader (10 hp) always misses.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]  # Troll hits (chance+damage), leader misses
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "monster"
    assert result.leader_killed is True
    assert LEADER_ID not in state.leaders
    assert LEADER_ID in state.dead_leaders
    assert feature.looted is False


# -- Phase 155: Troll regeneration wiring --


def test_execute_search_sets_troll_regeneration_on_the_monster_combatant():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.regenerates_hp == TROLL_REGENERATION_PER_COMBAT_ROUND


def test_execute_search_non_troll_guardian_has_no_regeneration():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.regenerates_hp == 0


# -- Phase 169: Flee (rulebook [5.6]) --


def test_flee_chance_matches_the_rulebooks_three_speed_tiers():
    assert FLEE_CHANCE == {
        MonsterSpeed.FAST: 0.20,
        MonsterSpeed.MEDIUM: 0.50,
        MonsterSpeed.SLOW: 0.80,
    }
    # Confirms the tiers line up with real species, not just the enum.
    assert MONSTER_COMBAT_STATS[Monster.GRYPHON].speed is MonsterSpeed.FAST
    assert MONSTER_COMBAT_STATS[Monster.GARGOYLE].speed is MonsterSpeed.MEDIUM
    assert MONSTER_COMBAT_STATS[Monster.GOLEM].speed is MonsterSpeed.SLOW


def test_execute_search_flee_tactic_success_ends_search_without_combat():
    # Gryphon is Fast (20% flee chance) -- 0.1 < 0.20 succeeds.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON)
    state.add_feature(feature)
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1]))

    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.fled is True
    assert result.winner is None
    assert feature.looted is False
    assert LEADER_ID in state.leaders


def test_execute_search_flee_tactic_failure_falls_through_to_melee():
    # Gryphon is Fast (20% flee chance) -- 0.99 >= 0.20 fails, so the plan's
    # Melee tactic still runs afterward exactly as if Flee weren't there.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        # Padding beyond the flee roll: rng.randint() for the monster's hit
        # points draws further from the same scripted queue.
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.99] + [0.5] * 10))

    assert mock_resolve.called
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.fled is False


def test_execute_search_no_flee_tactic_never_rolls_for_it():
    # A Melee-only plan against a Fast monster must not flee even though
    # the very first scripted roll (0.1) would satisfy the 20% chance --
    # confirms the roll is only consumed when Flee is actually in the plan.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), ScriptedRandom([0.1] + [0.5] * 10))

    assert mock_resolve.called
    assert result.fled is False
