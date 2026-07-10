from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.pursue_execution import PursueExecutionResult, execute_pursue
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
FAR_AWAY = HexCoord(20, 10)


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _peaceful_request(target_id: int) -> PursueRequest:
    return PursueRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK)])


def _melee_request(target_id: int) -> PursueRequest:
    return PursueRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Chasia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Fleeland", Race.HUMAN, Alignment.GOOD, FIELD))
    return state


# -- not found / army-leading mismatch -----------------------------------


def test_execute_pursue_reports_not_found_when_pursuer_missing():
    state = _base_state()
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_pursue(state, 1, _peaceful_request(2))

    assert result.caught_up is False
    assert result.reason == "pursuer or target not found"


def test_execute_pursue_reports_not_found_when_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))

    result = execute_pursue(state, 1, _peaceful_request(2))

    assert result.caught_up is False
    assert result.reason == "pursuer or target not found"


def test_execute_pursue_ignored_when_only_pursuer_leads_an_army():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([]))

    assert result.caught_up is False
    assert result.reason == "army-leading mismatch, order ignored"


def test_execute_pursue_ignored_when_only_target_leads_an_army():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([]))

    assert result.caught_up is False
    assert result.reason == "army-leading mismatch, order ignored"


# -- catch-up roll ---------------------------------------------------------


def test_execute_pursue_same_kingdom_target_is_guaranteed_to_catch_up():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Target", location=FAR_AWAY))

    # Same-Kingdom gives a 100% chance, but the catch-up roll is still made
    # (any value < 1.0 succeeds against it) -- only one value is consumed
    # since the peaceful request bypasses acceptance/combat entirely.
    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.99]))

    assert result.caught_up is True


def test_execute_pursue_fails_to_catch_up_when_roll_is_too_high():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))  # distant, different Kingdom

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.99]))

    assert result.caught_up is False
    assert result.reason == "did not catch up this phase"


def test_execute_pursue_catches_up_when_roll_is_low_enough():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))  # distance 0 -> chance 1.0

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.0]))

    assert result.caught_up is True


def test_execute_pursue_uses_pursuers_real_spy_skill():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD, skills=_skills_with(Ability.SPY, 4, 9))
    )
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=HexCoord(3, 1)))  # distance 2

    # Level-4 Spy skill gives a 250% base chance; /2 distance = 125% -> capped at
    # 100%, so even a near-1.0 roll still catches up.
    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.99]))

    assert result.caught_up is True


# -- armyless combat resolution (caught up + combat intent) ---------------


def test_execute_pursue_peaceful_plan_bypasses_acceptance_and_combat():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.0]))

    assert result == PursueExecutionResult(caught_up=True, combat_occurred=False)
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_pursue_king_target_refused_when_not_mutual():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    # catch-up roll (0.0, guaranteed at distance 0) then is_encounter_accepted's
    # King-target branch, which reads mutual_encounter directly with no roll.
    result = execute_pursue(state, 1, _melee_request(2), rng=ScriptedRandom([0.0]))

    assert result.caught_up is True
    assert result.reason == "encounter refused"
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_pursue_combat_removes_the_decisive_loser():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    # catch-up roll, then A always acts first (higher melee skill) and always
    # hits while B always misses.
    rng = ScriptedRandom([0.0] + [0.1, 0.5, 0.9] * 15)

    result = execute_pursue(state, 1, _melee_request(2), rng=rng)

    assert result.caught_up is True
    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True
    assert 2 not in state.leaders
    assert 1 in state.leaders


def test_execute_pursue_mutual_king_encounter_can_result_in_combat():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    rng = ScriptedRandom([0.0] + [0.1, 0.5, 0.9] * 15)

    result = execute_pursue(state, 1, _melee_request(2), rng=rng, mutual_encounter=True)

    assert result.caught_up is True
    assert result.winner_leader_id == 1
    assert 2 not in state.leaders


# -- army-vs-army pursuit: caught up but not fought here -------------------


def test_execute_pursue_army_vs_army_catch_up_reports_unmodeled_battle():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_pursue(state, 1, _melee_request(2), rng=ScriptedRandom([0.0]))

    assert result.caught_up is True
    assert result.combat_occurred is False
    assert result.reason == "army-vs-army pursuit battle not modeled"
    assert 1 in state.leaders and 2 in state.leaders
