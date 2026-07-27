from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.challenge_execution import (
    ChallengeExecutionResult,
    execute_challenge,
    has_combat_intent,
    is_encounter_accepted,
)
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
ELSEWHERE = HexCoord(9, 9)


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _peaceful_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK)])


def _melee_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])


# -- has_combat_intent --------------------------------------------------


def test_has_combat_intent_true_for_melee():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])
    assert has_combat_intent(request) is True


def test_has_combat_intent_true_for_fire_arrow():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.SHOOT)])
    assert has_combat_intent(request) is True


def test_has_combat_intent_false_for_peaceful_tactics():
    request = ChallengeRequest(
        target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK), SearchTactic(Maneuver.STEAL)]
    )
    assert has_combat_intent(request) is False


def test_has_combat_intent_false_for_no_tactics_at_all():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[])
    assert has_combat_intent(request) is False


# -- is_encounter_accepted: rulebook [3.12]'s King/Hero decision tree ---


def test_king_target_accepts_only_when_mutual():
    accepted = is_encounter_accepted(
        target_is_king=True, target_leads_army=False, challenger_is_king=False, mutual_encounter=True, rng=ScriptedRandom([])
    )
    assert accepted is True


def test_king_target_refuses_when_not_mutual():
    accepted = is_encounter_accepted(
        target_is_king=True, target_leads_army=False, challenger_is_king=False, mutual_encounter=False, rng=ScriptedRandom([])
    )
    assert accepted is False


def test_hero_leading_an_army_always_refuses():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=True, challenger_is_king=True, mutual_encounter=True, rng=ScriptedRandom([])
    )
    assert accepted is False


def test_armyless_hero_vs_king_challenger_is_a_50_50_roll():
    accepted_low = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=True, mutual_encounter=False,
        rng=ScriptedRandom([0.49]),
    )
    accepted_high = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=True, mutual_encounter=False,
        rng=ScriptedRandom([0.5]),
    )
    assert accepted_low is True
    assert accepted_high is False


def test_armyless_hero_vs_hero_challenger_always_accepts_without_consuming_rng():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=False, mutual_encounter=False,
        rng=ScriptedRandom([]),  # any .random() call here would raise IndexError
    )
    assert accepted is True


# -- execute_challenge: co-location, not-found, peaceful bypass ---------


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    return state


def test_execute_challenge_reports_not_found_when_challenger_missing():
    state = _base_state()
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_execute_challenge_reports_not_found_when_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_execute_challenge_refuses_when_not_co_located():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=ELSEWHERE))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "not co-located"


def test_execute_challenge_peaceful_plan_bypasses_acceptance_and_combat():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_challenge(state, 1, _peaceful_request(2), rng=ScriptedRandom([]))

    assert result == ChallengeExecutionResult(accepted=True, combat_occurred=False)
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_king_target_refused_when_not_mutual_and_no_combat_happens():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "encounter refused"
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_hero_with_army_target_refused():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "encounter refused"


# -- execute_challenge: combat resolution + loser removal ---------------


def test_execute_challenge_combat_removes_the_decisive_loser():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    # A always acts first (higher melee skill, no initiative roll needed);
    # scripted so A always hits and B always misses.
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True
    assert 2 not in state.leaders
    assert 1 in state.leaders


def test_execute_challenge_combat_with_no_decisive_winner_kills_nobody():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    # execute_challenge doesn't expose resolve_melee_duel's max_rounds, so
    # this exercises the real default (1000) all the way to its cap: both
    # combatants have equal (zero) melee skill, so every round's initiative
    # tie-break plus both always-miss attack rolls consumes 3 scripted
    # values -- 1000 rounds * 3.
    rng = ScriptedRandom([0.99] * 3000)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.winner_leader_id is None
    assert result.loser_killed is False
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_mutual_king_encounter_can_result_in_combat():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng, mutual_encounter=True)

    assert result.accepted is True
    assert result.winner_leader_id == 1
    # Phase 259: a King's death installs a Royal Heir under the same
    # leader_id rather than leaving the Kingdom leaderless.
    assert 2 in state.dead_leaders
    assert state.leaders[2].is_royal_heir is True
