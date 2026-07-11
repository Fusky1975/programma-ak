from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.move_execution import MoveExecutionResult
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.movement import neighbors as _neighbors
from ak_engine.turn.turn_processor import MultiAttackerMoveResult, TurnLeader, run_turn

from _helpers import ScriptedRandom

BOARD_WIDTH = 10
ORIGIN = HexCoord(1, 1)
ORIGIN2 = HexCoord(3, 1)  # also adjacent to TARGET, distinct from ORIGIN
TARGET = HexCoord(2, 1)  # adjacent to both ORIGIN and ORIGIN2 on the odd-r grid


def _lmove_phase(label: str, target: HexCoord) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.LMOVE, obj=encode_hex_number(target, BOARD_WIDTH), extra=[0])


def _leader_with_phase(leader_id: int, name: str, label: str, phase: PlanPhase) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(leader_id=leader_id, segments=[PlanSegment(0, 0, (), {label: phase})]),
    )


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, TARGET))
    state.add_province(ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(ORIGIN2, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, TARGET))
    return state


def test_run_turn_dispatches_phase_by_phase_not_leader_by_leader():
    # If this were leader-by-leader (run_leader_plan called once per
    # leader in sequence), leader 10's P1 would appear before leader
    # 20's P0 in the results. Phase-by-phase means both P0s come first.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=HexCoord(6, 6)))

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    leader_a = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0, "P1": p1})]))
    leader_b = Leader(20, "B", ActionPlan(20, [PlanSegment(0, 1, (), {"P0": p0, "P1": p1})]))

    results = run_turn([TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH)

    assert [(r.phase_label, r.leader_id) for r in results] == [
        ("P0", 10),
        ("P0", 20),
        ("P1", 10),
        ("P1", 20),
    ]


def test_run_turn_single_attacker_lmove_resolves_as_ordinary_solo_battle():
    # Non-breaking check: exactly one leader targeting the enemy
    # province still resolves through the ordinary single-attacker path
    # (execute_move -> MoveExecutionResult), same as run_leader_plan
    # alone would produce -- no Multiple Contingents grouping possible
    # with only one attacker.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))

    results = run_turn([TurnLeader(leader_a, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert len(results) == 1
    assert results[0].error is None
    assert isinstance(results[0].result, MoveExecutionResult)


def test_run_turn_groups_same_phase_same_target_lmoves_into_one_multi_attacker_battle():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert len(results) == 2
    assert all(r.error is None for r in results)
    assert all(isinstance(r.result, MultiAttackerMoveResult) for r in results)
    # Same battle object for both -- they really did unite into one fight,
    # not two coincidentally-identical ones.
    battle_ids = {id(r.result.battle) for r in results}
    assert len(battle_ids) == 1
    assert sorted(results[0].result.battle.leader_ids) == [10, 20]


def test_run_turn_multi_attacker_lmove_records_each_movers_own_kingdom_exploration():
    # Phase 69: two *different* (allied) kingdoms uniting into one Multiple
    # Contingents battle each still get their own independent
    # explored_percent_by_kingdom entry -- unlike the pre-existing shared
    # explored_percent scalar, where only the last mover in the loop wins.
    state = _base_state()
    state.add_kingdom(KingdomState(3, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.allied_kingdoms.add(frozenset({1, 3}))
    # Same origin as each other (unlike the "peaceful mover" fixture's
    # ORIGIN/ORIGIN2 split) so Multiple Contingents' own grouping unites
    # them into one battle instead of two sequential ones -- the latter
    # would exhaust the lone defender on the first pass (a separate,
    # already-documented fight_multi_attacker_battle() edge case, not
    # something this test is about).
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(30, kingdom_id=3, name="C", location=ORIGIN))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(103, 3, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN, movement_points=5, commanded_by=30))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_c = _leader_with_phase(30, "C", "P0", _lmove_phase("P0", TARGET))

    run_turn([TurnLeader(leader_a, 1), TurnLeader(leader_c, 3)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    explored = state.provinces[TARGET].explored_percent_by_kingdom
    assert explored.get(1, 0) > 0
    assert explored.get(3, 0) > 0


def test_run_turn_peaceful_mover_unaffected_by_a_lone_attacker_targeting_the_same_hex():
    # Kingdom 3 is allied with both the attacker's kingdom (1) and the
    # defender's kingdom (2), so its own mover always sees only allied
    # forces at TARGET regardless of who ends up holding it after the
    # attacker's own battle resolves -- an unambiguous "peaceful" case.
    state = _base_state()
    state.add_kingdom(KingdomState(3, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.allied_kingdoms.add(frozenset({1, 3}))
    state.allied_kingdoms.add(frozenset({2, 3}))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(30, kingdom_id=3, name="C", location=ORIGIN2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(103, 3, ArmyType.BOWMEN, Quality.AVERAGE, ORIGIN2, movement_points=5, commanded_by=30))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_c = _leader_with_phase(30, "C", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_c, 3)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    by_leader = {r.leader_id: r for r in results}
    # Only one genuine attacker (A) -- not enough to unite, so both
    # dispatch through the ordinary single-mover path.
    assert isinstance(by_leader[10].result, MoveExecutionResult)
    assert isinstance(by_leader[30].result, MoveExecutionResult)
    assert by_leader[30].result.battle_report is None  # peaceful entry, no fight at all
    assert by_leader[30].result.moved is True


def test_run_turn_excludes_an_illegal_contested_mover_but_still_groups_the_rest():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN2))
    state.add_leader(LeaderState(30, kingdom_id=1, name="C", location=ORIGIN2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN2, movement_points=5, commanded_by=20))
    state.add_army(ArmyState(103, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN2, movement_points=5, commanded_by=30))
    # ORIGIN is contested by kingdom 1 itself -- illegal to move from
    # there to the (enemy-owned) TARGET province. B and C move from the
    # uncontested ORIGIN2 instead.
    state.provinces[ORIGIN].contested_by_kingdom_id = 1

    leaders = [
        _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET)),
        _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET)),
        _leader_with_phase(30, "C", "P0", _lmove_phase("P0", TARGET)),
    ]
    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 1), TurnLeader(leaders[2], 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(0),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].error is not None
    assert by_leader[10].result is None
    assert isinstance(by_leader[20].result, MultiAttackerMoveResult)
    assert isinstance(by_leader[30].result, MultiAttackerMoveResult)
    assert sorted(by_leader[20].result.battle.leader_ids) == [20, 30]


def test_run_turn_nested_plan_dispatch_still_works_through_the_wrapper():
    # _dispatch_single wraps a single phase in a throwaway ActionPlan and
    # calls the existing run_leader_plan -- confirms that wrapping
    # doesn't break Hire's own nested-plan dispatch (Phase 32).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=100))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hirer", location=HexCoord(3, 9)))
    state.add_leader(LeaderState(50, kingdom_id=None, name="Wandering Hero", location=HexCoord(3, 9)))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.WAIT, 0, [0])})],
        ),
    )
    hirer = _leader_with_phase(1, "Hirer", "P0", hire_phase)

    results = run_turn([TurnLeader(hirer, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    hirer_results = [r for r in results if r.leader_id == 1]
    nested_results = [r for r in results if r.leader_id == 50]
    assert len(hirer_results) == 1
    assert hirer_results[0].result.hired is True
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P1"
    assert nested_results[0].error is None
    assert state.leaders[50].kingdom_id == 1


# --- Practice multi-character coordination (Phase 46) ---------------------


def _practice_phase(label: str, ability: Ability) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.PRACTICE, obj=ability.value, extra=[0])


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _practice_state(*leader_ids: int, skills_by_id: dict[int, SkillTable] | None = None) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    skills_by_id = skills_by_id or {}
    for leader_id in leader_ids:
        state.add_leader(
            LeaderState(leader_id, kingdom_id=1, name=f"L{leader_id}", location=ORIGIN, skills=skills_by_id.get(leader_id))
        )
    return state


def test_run_turn_groups_co_located_same_ability_practicers():
    state = _practice_state(
        10,
        20,
        skills_by_id={
            10: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            20: _skills_with(Ability.NECROMANCY, skill=4, aptitude=9),
        },
    )
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.NECROMANCY))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.01])
    )

    by_leader = {r.leader_id: r for r in results}
    # Lower-skill leader 10 gets the guaranteed (subject to aptitude) roll;
    # leader 20 (already higher) gets nothing this phase -- only reachable
    # if they were actually grouped together, not resolved independently.
    assert by_leader[10].result.skill_rose is True
    assert by_leader[10].result.new_skill == 2
    assert by_leader[20].result.skill_rose is False
    assert by_leader[20].result.new_skill == 4


def test_run_turn_does_not_group_different_abilities_even_when_co_located():
    state = _practice_state(
        10,
        20,
        skills_by_id={
            10: _skills_with(Ability.NECROMANCY, skill=0, aptitude=9),
            20: _skills_with(Ability.SAGE, skill=0, aptitude=9),
        },
    )
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.SAGE))

    # 0.07 is above the 5% solo chance (correct, independent behavior) but
    # below the 10% tied-group chance -- if these were incorrectly grouped
    # by location alone (ignoring ability), both would succeed instead.
    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.07, 0.07]),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].result.skill_rose is False
    assert by_leader[20].result.skill_rose is False


def test_run_turn_does_not_group_same_ability_at_different_locations():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.NECROMANCY, 0, 9))
    )
    state.add_leader(
        LeaderState(20, kingdom_id=1, name="B", location=ORIGIN2, skills=_skills_with(Ability.NECROMANCY, 0, 9))
    )
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.NECROMANCY))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.07, 0.07]),
    )

    by_leader = {r.leader_id: r for r in results}
    # Solo (5%) chance for both, not the tied-group (10%) chance.
    assert by_leader[10].result.skill_rose is False
    assert by_leader[20].result.skill_rose is False


def test_run_turn_groups_three_co_located_same_ability_practicers():
    state = _practice_state(
        10,
        20,
        30,
        skills_by_id={
            10: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
            20: _skills_with(Ability.NECROMANCY, skill=4, aptitude=9),
            30: _skills_with(Ability.NECROMANCY, skill=1, aptitude=9),
        },
    )
    leaders = [
        _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.NECROMANCY)),
        _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.NECROMANCY)),
        _leader_with_phase(30, "C", "P0", _practice_phase("P0", Ability.NECROMANCY)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 1), TurnLeader(leaders[2], 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.01, 0.01]),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].result.skill_rose is True
    assert by_leader[20].result.skill_rose is False
    assert by_leader[30].result.skill_rose is True


# -- Contested-province forced rebattle (Phase 55) -------------------------


def test_run_turn_forces_a_rebattle_before_the_next_phase_when_contested():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    forced = [r for r in results if r.phase_label == "forced-rebattle"]
    assert len(forced) == 1
    assert forced[0].segment_index == -1
    assert forced[0].action is None
    assert forced[0].result is not None  # a real BattleReport


def test_run_turn_deducts_movement_points_for_the_forced_rebattle():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    army = state.armies.get(101)
    if army is not None:  # survives an ELITE-vs-GREEN battle either way, but guard for safety
        assert army.movement_points < 3


def test_run_turn_does_not_force_a_rebattle_once_movement_points_run_out():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=0))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


def test_run_turn_does_not_force_a_rebattle_when_no_defender_remains():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))
    del state.armies[201]  # the defender fixture army -- nothing left to fight

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


def test_run_turn_ignores_a_province_with_no_contested_flag():
    state = _base_state()  # TARGET's contested_by_kingdom_id defaults to None
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


# -- Mutual Challenge/Pursue detection (Phase 56) ---------------------------


def _encounter_phase(label: str, action: ActionCode, target_id: int, *, melee: bool) -> PlanPhase:
    tactic = 9 if melee else 3  # Maneuver.MELEE / Maneuver.TALK ordinals
    return PlanPhase(label=label, action=action, obj=target_id, extra=[0, tactic, -1])


def test_run_turn_resolves_a_mutual_challenge_as_a_single_shared_encounter():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9)))
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN, skills=_skills_with(Ability.MELEE, 0, 9)))
    leaders = [
        _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)),
        _leader_with_phase(20, "B", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 10, melee=True)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
    )

    by_leader = {r.leader_id: r for r in results}
    assert set(by_leader) == {10, 20}
    # Single shared resolution: both dispatch entries point at the exact
    # same result object, not two independently-fought duels.
    assert by_leader[10].result is by_leader[20].result
    assert by_leader[10].result.accepted is True
    assert by_leader[10].result.combat_occurred is True
    assert by_leader[10].result.winner_leader_id == 10  # lower id -> challenger, higher skill -> wins
    assert 20 not in state.leaders
    assert 10 in state.leaders


def test_run_turn_mutual_encounter_keeps_the_king_as_target_regardless_of_leader_id():
    # King has the *lower* leader_id -- a naive "lower id is always
    # challenger" tiebreak would wrongly make the King the challenger here,
    # routing through the King-challenger 50% evade roll instead of the
    # King-target's guaranteed mutual acceptance ([3.12]).
    state = _base_state()
    state.add_leader(
        LeaderState(5, kingdom_id=1, name="King", location=ORIGIN, is_king=True, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    state.add_leader(
        LeaderState(20, kingdom_id=2, name="Hero", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    leaders = [
        _leader_with_phase(5, "King", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)),
        _leader_with_phase(20, "Hero", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 5, melee=True)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[5].result is by_leader[20].result
    assert by_leader[5].result.accepted is True  # guaranteed, no 50% roll -- King stayed the target
    assert by_leader[5].result.winner_leader_id == 20  # the Hero (challenger), higher melee skill
    assert 5 not in state.leaders


def test_run_turn_one_sided_challenge_dispatches_normally_not_as_mutual():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=2, name="King", location=ORIGIN, is_king=True))
    leaders = [
        _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)),
        # B has no reciprocal order this phase at all -- not a mutual pair.
        _leader_with_phase(20, "King", "P1", _encounter_phase("P1", ActionCode.CHALLENGE, 10, melee=True)),
    ]

    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([]),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    a_result = by_label[(10, "P0")].result
    assert a_result.accepted is False
    assert a_result.reason == "encounter refused"  # mutual_encounter defaults False, King target refuses


def test_run_turn_self_targeting_pursue_is_not_misdetected_as_mutual():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    leader = _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.PURSUE, 10, melee=False))

    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0]))

    assert len(results) == 1
    assert results[0].leader_id == 10


# -- Defend reactive reinforcement (Phase 57) -------------------------------


_BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)
DEFEND_HOME = HexCoord(5, 5)
COVERED = _neighbors(DEFEND_HOME, _BOUNDS)[0]
ANOTHER_COVERED = _neighbors(DEFEND_HOME, _BOUNDS)[1]
ATTACKER_ORIGIN = next(n for n in _neighbors(COVERED, _BOUNDS) if n != DEFEND_HOME)
SECOND_ATTACKER_ORIGIN = next(n for n in _neighbors(ANOTHER_COVERED, _BOUNDS) if n != DEFEND_HOME)


def _defend_phase(label: str) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.DEFEND, obj=0, extra=[0])


def _defend_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, ATTACKER_ORIGIN))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, DEFEND_HOME))
    state.add_province(ProvinceState(DEFEND_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(COVERED, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(ANOTHER_COVERED, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(SECOND_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(100, kingdom_id=2, name="Defender", location=DEFEND_HOME))
    state.add_army(ArmyState(901, 2, ArmyType.GARRISON, Quality.GREEN, DEFEND_HOME, commanded_by=100))
    return state


def _attacker(leader_id: int, army_id: int, origin: HexCoord, target: HexCoord, label: str) -> Leader:
    return _leader_with_phase(leader_id, "Attacker", label, _lmove_phase(label, target))


def test_run_turn_defend_reinforces_an_invaded_covered_province_next_phase():
    state = _defend_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    # The defender's leader (and, before the battle, the garrison itself)
    # physically converges on the invaded province -- otherwise a
    # province with zero standing defenders wouldn't trigger a battle at
    # all (move_execution.py's own occupied_by_enemy check). The garrison
    # may not have survived the battle itself, so only the leader's own
    # post-battle position (leaders aren't removed by an ordinary army
    # battle) is asserted directly.
    assert state.leaders[100].location == COVERED

    by_leader = {r.leader_id: r for r in results}
    move_result = by_leader[200].result
    assert isinstance(move_result, MoveExecutionResult)
    assert move_result.battle_report is not None  # a battle happened -- reinforcement worked


def test_run_turn_defend_does_not_relocate_without_an_invasion():
    state = _defend_state()
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))

    run_turn([TurnLeader(defender, 2)], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.armies[901].location == DEFEND_HOME
    assert state.leaders[100].location == DEFEND_HOME


def test_run_turn_defend_does_not_reinforce_a_province_it_does_not_own():
    state = _defend_state()
    state.provinces[COVERED].owner_kingdom_id = 3  # a third, unrelated Kingdom's ground
    state.add_kingdom(KingdomState(3, "Neutralia", Race.HUMAN, Alignment.NEUTRAL, COVERED))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")

    run_turn([TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(3))

    assert state.armies[901].location == DEFEND_HOME  # never relocated


def test_run_turn_defend_is_consumed_after_its_first_reinforcement():
    state = _defend_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN))
    state.add_army(ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3))
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P1")
    second_attacker = _attacker(300, 903, SECOND_ATTACKER_ORIGIN, ANOTHER_COVERED, "P2")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1), TurnLeader(second_attacker, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(11),
    )

    # Committed to the first (P1) invasion -- never covers the second (P2)
    # one, which walks in uncontested (battle_report is None).
    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is not None
    assert by_leader[300].result.battle_report is None


# -- Defend cancellation (Phase 67) -----------------------------------------


def _two_phase_leader(leader_id: int, name: str, phase0: PlanPhase, phase1: PlanPhase) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(
            leader_id=leader_id, segments=[PlanSegment(0, 1, (), {phase0.label: phase0, phase1.label: phase1})]
        ),
    )


def _invading_attacker() -> tuple[LeaderState, ArmyState, Leader]:
    leader_state = LeaderState(200, kingdom_id=1, name="Attacker", location=ATTACKER_ORIGIN)
    army_state = ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    leader = _attacker(200, 902, ATTACKER_ORIGIN, COVERED, "P2")
    return leader_state, army_state, leader


def test_run_turn_defend_is_cancelled_by_a_later_move_order():
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _lmove_phase("P1", ANOTHER_COVERED))

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None  # cancelled -- walks in uncontested


def test_run_turn_defend_is_cancelled_by_a_later_pursue_order():
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    pursue_phase = PlanPhase(label="P1", action=ActionCode.PURSUE, obj=999, extra=[-1])
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), pursue_phase)

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None


def test_run_turn_defend_is_cancelled_by_a_later_trail_order():
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    trail_phase = PlanPhase(label="P1", action=ActionCode.TRAIL, obj=999, extra=[0])
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), trail_phase)

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is None


def test_run_turn_defend_survives_an_unrelated_action():
    # WAIT (and, by the same logic, Practice/Explore/etc.) doesn't cancel
    # Defend -- only LMOVE/PURSUE/TRAIL do. Proves the cancellation check
    # isn't over-broad.
    state = _defend_state()
    attacker_state, attacker_army, attacker = _invading_attacker()
    state.add_leader(attacker_state)
    state.add_army(attacker_army)
    wait_phase = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), wait_phase)

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(5)
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[200].result.battle_report is not None


# -- Persistent Pursue/Trail chase (Phase 70) -------------------------------


CHASE_START = HexCoord(5, 4)
CHASE_STEP = HexCoord(6, 4)  # one hex closer, same row (even -> even, E offset (1, 0))
CHASE_TARGET = HexCoord(7, 4)  # 2 hexes from CHASE_START
DECOY = HexCoord(5, 5)  # adjacent to CHASE_START (SE), an uninvolved LMOVE destination


def _chase_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Chasia", Race.HUMAN, Alignment.NEUTRAL, CHASE_START))
    state.add_kingdom(KingdomState(2, "Runnia", Race.HUMAN, Alignment.NEUTRAL, CHASE_TARGET))
    for coord in (CHASE_START, CHASE_STEP, CHASE_TARGET, DECOY):
        state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Pursuer", location=CHASE_START))
    state.add_leader(LeaderState(20, kingdom_id=2, name="Target", location=CHASE_TARGET))
    return state


def _pursue_phase(label: str, target_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.PURSUE, obj=target_id, extra=[0, -1])  # no tactics


def _trail_phase(label: str, target_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.TRAIL, obj=target_id, extra=[0])


def _three_phase_leader(leader_id: int, name: str, p0: PlanPhase, p1: PlanPhase, p2: PlanPhase) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(
            leader_id=leader_id,
            segments=[PlanSegment(0, 2, (), {p0.label: p0, p1.label: p1, p2.label: p2})],
        ),
    )


def test_run_turn_unresolved_pursue_preempts_p1_and_continues_the_chase():
    # Spy skill 0, armyless, different Kingdoms: distance 2 -> 25% catch-up
    # chance, distance 1 (after one chase step) -> 50%. First roll (0.9)
    # misses at P0; second roll (0.1), taken by the *continuation* dispatch
    # at P1, catches -- and since neither side leads an army and the
    # Pursue carries no combat tactics, catching up ends the chase
    # immediately with no further combat.
    state = _chase_state()
    p0 = _pursue_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)  # would relocate the pursuer to DECOY if NOT preempted
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    pursuer = _three_phase_leader(10, "Pursuer", p0, p1, p2)

    results = run_turn(
        [TurnLeader(pursuer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    p0_result = by_label[(10, "P0")].result
    assert p0_result.caught_up is False
    assert p0_result.reason == "did not catch up this phase"

    # P1's own LMOVE order never dispatched -- the chase continuation ran
    # instead, at segment_index=-1 (not tied to a real plan segment).
    assert (10, "P1") in by_label
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.PURSUE
    assert p1_entry.result.caught_up is True
    assert state.leaders[10].location == CHASE_STEP  # one chase step, not DECOY

    # Resolved -- P2's own WAIT order dispatches normally again.
    p2_entry = by_label[(10, "P2")]
    assert p2_entry.segment_index == 0
    assert p2_entry.action is ActionCode.WAIT


def test_run_turn_unresolved_trail_preempts_p1_and_continues_the_chase():
    state = _chase_state()
    p0 = _trail_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    trailer = _three_phase_leader(10, "Trailer", p0, p1, p2)

    results = run_turn(
        [TurnLeader(trailer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    assert by_label[(10, "P0")].result.spied_on is False

    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.TRAIL
    assert p1_entry.result.spied_on is True
    assert state.leaders[10].location == CHASE_STEP

    p2_entry = by_label[(10, "P2")]
    assert p2_entry.segment_index == 0
    assert p2_entry.action is ActionCode.WAIT


def test_run_turn_pursue_with_no_target_is_not_registered_for_continuation():
    # "pursuer or target not found" is a terminal reason, not "did not
    # catch up this phase" -- P1's own order must dispatch normally, not
    # be preempted by a chase that can never resolve.
    state = _chase_state()
    p0 = _pursue_phase("P0", 999)  # no such leader
    p1 = _lmove_phase("P1", DECOY)
    pursuer = _leader_with_phase(10, "Pursuer", "P0", p0)
    pursuer.plan.segments[0] = PlanSegment(0, 1, (), {"P0": p0, "P1": p1})

    results = run_turn([TurnLeader(pursuer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(10, "P0")].result.reason == "pursuer or target not found"
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # ordinary _dispatch_single, not a continuation
    assert isinstance(p1_entry.result, MoveExecutionResult)
    assert state.leaders[10].location == DECOY
