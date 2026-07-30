from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, hex_distance
from ak_engine.turn.pursue_execution import (
    PursueExecutionResult,
    _leader_combatant,
    advance_pursuit,
    execute_pursue,
    step_toward_target,
)
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
DEFENDER_HOME = HexCoord(2, 1)  # a neighbor of FIELD on the odd-r grid
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


def test_leader_combatant_reads_real_temper():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD, temper=Temper.COWARDLY)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.temper is Temper.COWARDLY


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


# -- Fire Arrow (Phase 273): SHOOT now actually resolves via Fire Arrow --


def test_execute_pursue_shoot_tactic_resolves_via_fire_arrow_before_melee():
    state = _base_state()
    # Same reasoning as challenge_execution.py's own Phase 273 test: A's 10
    # guaranteed Archery hits (minimum 1 damage each) always total at least
    # 10, guaranteeing B's death via Fire Arrow alone -- if this still fell
    # straight to Melee (the pre-Phase-273 bug), B's own higher Melee skill
    # would act first instead.
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ARCHERY, 10, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9))
    )
    rng = ScriptedRandom([0.0] + [0.01] * 25)  # catch-up roll, then A's guaranteed archery hits
    shoot_request = PursueRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.SHOOT)])

    result = execute_pursue(state, 1, shoot_request, rng=rng)

    assert result.caught_up is True
    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


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
    # Phase 259: a King's death installs a Royal Heir under the same
    # leader_id rather than leaving the Kingdom leaderless.
    assert 2 in state.dead_leaders
    assert state.leaders[2].is_royal_heir is True


# -- army-vs-army pursuit: caught up but not fought here -------------------


def test_execute_pursue_army_vs_army_catch_up_fights_a_real_battle():
    state = _base_state()
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(DEFENDER_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD, skills=_skills_with(Ability.SPY, 4, 9))
    )
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=DEFENDER_HOME))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, DEFENDER_HOME, commanded_by=2))

    # Spy 4 (250%) x2 (target leads an army) / distance 1 = 500%, clamped to
    # 100% -- catch-up always succeeds regardless of the rng's actual
    # values (random() is always < 1.0), so a real, unseeded rng is fine
    # here; only the battle's occurrence and the relocation are asserted,
    # not its win/loss outcome.
    result = execute_pursue(state, 1, _melee_request(2), rng=random.Random(1234))

    assert result.caught_up is True
    assert result.combat_occurred is True
    assert result.battle_report is not None
    assert state.leaders[1].location == DEFENDER_HOME
    assert state.armies[101].location == DEFENDER_HOME


def test_execute_pursue_army_vs_army_catch_up_with_no_province_data_is_not_fought():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))
    # No ProvinceState registered at FIELD.

    result = execute_pursue(state, 1, _melee_request(2), rng=ScriptedRandom([0.0]))

    assert result.caught_up is True
    assert result.combat_occurred is False
    assert result.reason == "no province data recorded at the target's location"
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_pursue_army_vs_army_catch_up_with_no_pursuer_kingdom_is_not_fought():
    state = _base_state()
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_leader(LeaderState(1, kingdom_id=None, name="Independent Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(101, None, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_pursue(state, 1, _melee_request(2), rng=ScriptedRandom([0.0]))

    assert result.caught_up is True
    assert result.combat_occurred is False
    assert result.reason == "pursuer has no Kingdom to fight the battle under"


# -- step_toward_target / advance_pursuit (Phase 66) -----------------------


_BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def test_step_toward_target_reduces_distance_by_exactly_one():
    before = hex_distance(FIELD, FAR_AWAY)
    stepped = step_toward_target(FIELD, FAR_AWAY, _BOUNDS)

    assert hex_distance(stepped, FAR_AWAY) == before - 1


def test_step_toward_target_is_a_no_op_when_already_there():
    assert step_toward_target(FIELD, FIELD, _BOUNDS) == FIELD


def test_advance_pursuit_moves_the_pursuer_and_commanded_armies_one_step():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))  # different Kingdom
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))

    # Rigged to fail the catch-up roll at the new (still nonzero) distance --
    # proves execute_pursue ran on the *post-step* location without erroring.
    result = advance_pursuit(state, 1, _melee_request(2), rng=ScriptedRandom([1.0]))

    assert result.caught_up is False
    assert state.leaders[1].location != FIELD
    assert hex_distance(state.leaders[1].location, FAR_AWAY) == hex_distance(FIELD, FAR_AWAY) - 1
    assert state.armies[101].location == state.leaders[1].location


def test_advance_pursuit_reports_not_found_when_pursuer_or_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))

    result = advance_pursuit(state, 1, _melee_request(2))

    assert result.caught_up is False
    assert result.reason == "pursuer or target not found"


# -- Phase 290: armyless case reuses challenge_execution's Personal-Combat wiring --


def test_execute_pursue_cast_charm_success_makes_the_pursuer_flee():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = PursueRequest(
        target_character_id=2,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(Maneuver.CAST, Spell.CHARM.value), SearchTactic(Maneuver.MELEE)],
    )
    # catch-up roll, then the cast's own success roll.
    rng = ScriptedRandom([0.0, 0.1])

    result = execute_pursue(state, 1, request, rng=rng)

    assert result.caught_up is True
    assert result.combat_occurred is True
    assert result.fled is True
    assert result.winner_leader_id is None
    assert 1 in state.leaders and 2 in state.leaders
