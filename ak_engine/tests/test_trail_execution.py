from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, hex_distance
from ak_engine.turn.trail_decode import TrailRequest
from ak_engine.turn.trail_execution import TrailExecutionResult, advance_trail, execute_trail

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
FAR_AWAY = HexCoord(20, 10)


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _request(target_id: int) -> TrailRequest:
    return TrailRequest(target_character_id=target_id, unconfirmed_extra0=0)


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Chasia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Fleeland", Race.HUMAN, Alignment.GOOD, FIELD))
    return state


def test_execute_trail_reports_not_found_when_trailer_missing():
    state = _base_state()
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2))

    assert result.spied_on is False
    assert result.reason == "trailer or target not found"


def test_execute_trail_reports_not_found_when_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))

    result = execute_trail(state, 1, _request(2))

    assert result.spied_on is False
    assert result.reason == "trailer or target not found"


def test_execute_trail_rejected_when_trailer_leads_an_army():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([]))

    assert result.spied_on is False
    assert result.reason == "a character leading an army may not be ordered to Trail"


def test_execute_trail_allowed_when_only_target_leads_an_army():
    # Unlike Pursue, Trail has no "both must match" rule -- only the
    # trailer is restricted from leading an army ([3.17]).
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0]))

    assert result.spied_on is True


def test_execute_trail_same_kingdom_target_is_guaranteed_to_be_found():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Target", location=FAR_AWAY))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99]))

    assert result.spied_on is True


def test_execute_trail_same_province_target_is_guaranteed_to_be_found():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0]))

    assert result.spied_on is True


def test_execute_trail_fails_when_roll_is_too_high():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99]))

    assert result.spied_on is False
    assert result.reason == "did not find the target this phase"


def test_execute_trail_uses_trailers_real_spy_skill():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD, skills=_skills_with(Ability.SPY, 4, 9))
    )
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=HexCoord(3, 1)))  # distance 2

    # Level-4 Spy gives 250% base, /2 distance = 125% -> capped at 100%.
    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99]))

    assert result.spied_on is True


# -- advance_trail (Phase 68) -------------------------------------------------


_BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def test_advance_trail_moves_the_trailer_one_step_closer_then_rerolls():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))  # different Kingdom

    # Rigged to fail the catch-up roll at the new (still nonzero) distance --
    # proves execute_trail ran on the *post-step* location without erroring.
    result = advance_trail(state, 1, _request(2), rng=ScriptedRandom([1.0]))

    assert result.spied_on is False
    assert state.leaders[1].location != FIELD
    assert hex_distance(state.leaders[1].location, FAR_AWAY) == hex_distance(FIELD, FAR_AWAY) - 1


def test_advance_trail_reports_not_found_when_trailer_or_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))

    result = advance_trail(state, 1, _request(2))

    assert result.spied_on is False
    assert result.reason == "trailer or target not found"
