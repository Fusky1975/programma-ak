"""Spy/Thief cover: a character using Spy, Trail or a Steal tactic is less likely to be noticed
for the whole turn (rulebook [4.3.3], Spy Table column 1) -- by a Patrol and in the other
Kings' CHARACTERS report."""

from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, ActionCode, Maneuver
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.turn.leader_visibility import leader_location_known_to_kingdom
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.patrol_execution import find_patrol_target
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.spy_cover import compute_cover_ability, notice_chance, notice_chance_of
from ak_engine.turn.turn_processor import TurnLeader, run_turn

from _helpers import ScriptedRandom

HOME = HexCoord(5, 4)
BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def _skills(ability: Ability, level: int) -> SkillTable:
    raw = [0] * 31
    raw[ability.value * 2] = level
    raw[ability.value * 2 + 1] = 9
    return SkillTable(raw)


def _plan(*phases: PlanPhase) -> ActionPlan:
    return ActionPlan(1, [PlanSegment(0, 0, (), {p.label: p for p in phases})])


def _phase(label: str, action: ActionCode, obj: int = 0, extra=()) -> PlanPhase:
    return PlanPhase(label=label, action=action, obj=obj, extra=list(extra))


# -- the Spy Table's chance of being noticed --


@pytest.mark.parametrize("level,chance", [(0, 1.0), (1, 0.5), (2, 0.25), (3, 0.12), (4, 0.05), (9, 0.05)])
def test_notice_chance_follows_the_spy_table(level, chance):
    assert notice_chance(level) == chance


# -- which Talent covers the turn --


def test_a_spy_order_gives_spy_cover():
    plan = _plan(_phase("P0", ActionCode.PRACTICE), _phase("P2", ActionCode.ASPY))
    assert compute_cover_ability(plan) is Ability.SPY


def test_a_trail_order_gives_spy_cover():
    assert compute_cover_ability(_plan(_phase("P1", ActionCode.TRAIL, obj=7))) is Ability.SPY


def test_plain_orders_give_no_cover():
    assert compute_cover_ability(_plan(_phase("P0", ActionCode.PRACTICE), _phase("P1", ActionCode.DEFEND))) is None
    assert compute_cover_ability(None) is None


def test_a_steal_tactic_gives_thief_cover():
    steal = SearchTactic(Maneuver.STEAL)
    assert compute_cover_ability(_plan(_phase("P0", ActionCode.PRACTICE)), (steal,)) is Ability.THIEF


def test_the_last_covering_order_in_plan_order_wins():
    plan = _plan(_phase("P0", ActionCode.ASPY), _phase("P3", ActionCode.TRAIL, obj=7))
    assert compute_cover_ability(plan) is Ability.SPY


def test_notice_chance_of_uses_the_covering_talents_level():
    state = GameState()
    leader = LeaderState(2, 2, "Spy", HOME, skills=_skills(Ability.SPY, 2))
    state.add_leader(leader)
    assert notice_chance_of(state, leader) == 1.0  # no cover this turn
    leader.cover_ability = Ability.SPY
    assert notice_chance_of(state, leader) == 0.25
    leader.cover_ability = Ability.THIEF  # level 0 in Thief: no help
    assert notice_chance_of(state, leader) == 1.0


# -- Patrol rule (e) --


def _patrol_state(cover: Ability | None, level: int) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Patrolia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Intrudia", Race.HUMAN, Alignment.GOOD, HexCoord(20, 10)))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, 1, "Patroller", HOME))
    intruder = LeaderState(2, 2, "Intruder", HOME, skills=_skills(Ability.SPY, level))
    intruder.cover_ability = cover
    state.add_leader(intruder)
    return state


def test_an_uncovered_intruder_is_always_found_and_costs_no_roll():
    state = _patrol_state(None, 0)
    rng = ScriptedRandom([])  # a roll would exhaust it
    assert find_patrol_target(state, 1, BOUNDS, rng).leader_id == 2


def test_a_covered_intruder_slips_past_when_the_notice_roll_fails():
    state = _patrol_state(Ability.SPY, 1)  # 50% noticed
    assert find_patrol_target(state, 1, BOUNDS, ScriptedRandom([0.6])) is None


def test_a_covered_intruder_is_found_when_the_notice_roll_succeeds():
    state = _patrol_state(Ability.SPY, 1)
    assert find_patrol_target(state, 1, BOUNDS, ScriptedRandom([0.4])).leader_id == 2


def test_without_an_rng_there_is_no_cover_effect():
    state = _patrol_state(Ability.SPY, 4)
    assert find_patrol_target(state, 1, BOUNDS).leader_id == 2


# -- CHARACTERS report (Known_Loc) --


def _known_loc_state(cover: Ability | None, level: int) -> GameState:
    state = GameState()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # the viewer's own
    leader = LeaderState(2, 2, "Spy", HOME, skills=_skills(Ability.SPY, level))
    leader.cover_ability = cover
    state.add_leader(leader)
    return state


def test_an_uncovered_stranger_in_the_viewers_province_is_known():
    assert leader_location_known_to_kingdom(_known_loc_state(None, 0), 2, 1, orig_turn=3) is True


def test_a_max_level_spy_is_never_known():
    state = _known_loc_state(Ability.SPY, 4)  # 5% -> Trunc(16 * .05) = 0 > hash is never true
    assert all(leader_location_known_to_kingdom(state, 2, 1, orig_turn=t) is False for t in range(16))


def test_a_level_one_spy_is_known_for_half_the_turn_hashes():
    state = _known_loc_state(Ability.SPY, 1)  # 50% -> 8 > ((1 + 2 + turn) & 15)
    known = [leader_location_known_to_kingdom(state, 2, 1, orig_turn=t) for t in range(16)]
    assert known.count(True) == 8


# -- the turn --


def test_run_turn_records_the_cover_and_clears_it_for_idle_leaders():
    state = GameState()
    state.board_width = 30
    state.board_height = 15
    state.add_kingdom(KingdomState(1, "K", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, 1, "Spy", HOME, skills=_skills(Ability.SPY, 2)))
    state.add_leader(LeaderState(2, 1, "Idle", HOME))
    state.leaders[2].cover_ability = Ability.SPY  # stale from a previous turn

    plan = _plan(_phase("P0", ActionCode.ASPY))
    run_turn([TurnLeader(Leader(1, "Spy", plan), 1)], state, rng=random.Random(1))

    assert state.leaders[1].cover_ability is Ability.SPY
    assert state.leaders[2].cover_ability is None


def test_a_thief_with_banditry_or_piracy_gets_spy_cover_from_a_practice_thief_order():
    # "This action also counts as a normal 'Spy' action in all respects" (Banditry/Piracy text).
    thievery = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=Ability.THIEF.value, extra=[0])
    plan = ActionPlan(1, [PlanSegment(0, 0, (), {"P0": thievery})])

    assert compute_cover_ability(plan) is None
    assert compute_cover_ability(plan, raids_as_bandit_or_pirate=True) is Ability.SPY


def test_banditry_cover_does_not_apply_to_practising_another_talent():
    melee = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=Ability.MELEE.value, extra=[0])
    plan = ActionPlan(1, [PlanSegment(0, 0, (), {"P0": melee})])

    assert compute_cover_ability(plan, raids_as_bandit_or_pirate=True) is None
