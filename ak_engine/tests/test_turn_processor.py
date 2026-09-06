from __future__ import annotations

import random
from unittest.mock import patch

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, ActionCode, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.models.valhalla import VALHALLA_ROSTER, VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.battle_orchestrator import BattleReport, MultiAttackerBattle
from ak_engine.turn.battle_resolution import BattleResult
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.move_execution import MoveExecutionResult, TransportIllegalMoveError
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.contested_province import IllegalMoveFromContestedError
from ak_engine.turn.movement import neighbors as _neighbors
from ak_engine.turn.aspy_execution import SpyReport
from ak_engine.turn.plan_dispatch import NoOpResult
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.turn_processor import (
    MultiAttackerMoveResult,
    TurnLeader,
    _apply_werebeast_transformations,
    _replenish_turn_scoped_state,
    build_missed_deadline_turn_leaders,
    run_turn as _run_turn_unfiltered,
)

from _helpers import ScriptedRandom


def run_turn(*args, **kwargs):
    """Phase 756: the automatic per-turn Valhalla visit is now truly
    unconditional (fires whenever no Gate Angel cast claimed this turn's
    one visit, which is every pre-existing fixture in this file, since
    none of them cast it) -- an orthogonal, always-on mechanic that would
    otherwise force every one of this file's ~90 `run_turn()` call sites
    to individually account for an unrelated new "valhalla-visit"
    sentinel *and* its own real RNG consumption (which would shift the
    exact scripted-value sequence every `ScriptedRandom`-based test in
    this file relies on, for a mechanic none of them are about).
    Neutralized here by default via a scoped monkey-patch to a no-op;
    tests that specifically exercise the automatic visit itself call
    `_run_turn_unfiltered` directly instead (see the dedicated Phase 756
    section near the bottom of this file).
    """

    with patch("ak_engine.turn.turn_processor.finalize_ordinary_valhalla_visit", return_value=None):
        return _run_turn_unfiltered(*args, **kwargs)

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


# -- Phase 669: per-leader Special Encounter Plan, populated before phase 0 --


def test_run_turn_decodes_the_real_sp_block_before_phase_0():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    # Real SP: wire format (Phase 659): "10 -1" = [Flee], matching a
    # real hand-decoded sample from turn/sep_decode.py's own docstring.
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (10, -1), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.leaders[10].special_encounter_plan == (SearchTactic(Maneuver.FLEE),)


# -- Phase 670: monster-raid guardian maturation only from Fall (P3) onward,
# and apply_turn_revenue() now runs off the real per-turn rng --------------


def _empty_plan_leader(leader_id: int, name: str) -> Leader:
    return Leader(leader_id, name, ActionPlan(leader_id, [PlanSegment(0, 0, (), {})]))


def test_run_turn_ages_feature_guardians_only_from_fall_phase_index_3_onward():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_feature(
        Feature(
            feature_id=1,
            coord=coord,
            kind=FeatureType.DUNGEON,
            guardian_monster=Monster.CHIMERA,
            guardian_alignment=Alignment.NEUTRAL,
            guardian_state=MonsterEngagementState.CALM,
        )
    )
    leader = _empty_plan_leader(10, "A")

    # Exactly 3 draws expected: P3's 3%-hit (0.02) + Worldly-threshold
    # pick (0.1) transitions Calm -> Mercenary; P4's 3%-miss (0.5)
    # consumes only one more. If maturation ran during P0/P1/P2 too, this
    # exact-length script would either desync the CALM->MERCENARY
    # transition's own timing or raise IndexError on an unexpected extra
    # draw -- either way the assertion below would fail.
    rng = ScriptedRandom([0.02, 0.1, 0.5, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert state.features[1].guardian_state is MonsterEngagementState.MERCENARY


def test_run_turn_apply_turn_revenue_consumes_the_real_shared_rng():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=700))
    state.add_feature(
        Feature(
            feature_id=1,
            coord=coord,
            kind=FeatureType.DUNGEON,
            # Gr. Dragon: Temper.COWARDLY (25% raid-activity chance) --
            # avoids interaction with the maturation rolls below (its
            # own guardian_alignment doesn't matter once already BOLD).
            guardian_monster=Monster.GR_DRAGON,
            guardian_state=MonsterEngagementState.BOLD,
        )
    )
    leader = _empty_plan_leader(10, "A")

    # P3/P4 maturation rolls (3%-miss each, no threshold consumed) +
    # the raid activity check (>= 0.25 -> inactive). If `apply_turn_
    # revenue()` used its own fresh `random.Random()` instead of this
    # same shared `rng`, this script would be left with one unconsumed
    # element at the end.
    rng = ScriptedRandom([0.5, 0.5, 0.9, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert rng._randoms == []
    assert state.turn_raid_events == []
    assert state.kingdoms[1].treasury == 700


def test_run_turn_dissolves_illusory_terrain_once_per_real_turn_not_per_phase():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(
        ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, illusory_terrain=Terrain.SEA)
    )
    leader = _empty_plan_leader(10, "A")

    # Exactly one draw expected: the illusory-terrain dissolve roll for
    # this province's single entry. If the roll ran once per phase (5x)
    # instead of once per real turn, this exact-length script would
    # raise IndexError on the second draw.
    rng = ScriptedRandom([0.1, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert rng._randoms == []
    assert state.provinces[coord].illusory_terrain is None


def test_run_turn_leaves_illusory_terrain_untouched_on_a_scripted_miss():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(
        ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, illusory_terrain=Terrain.SEA)
    )
    leader = _empty_plan_leader(10, "A")

    rng = ScriptedRandom([0.9, 0.0])

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert rng._randoms == []
    assert state.provinces[coord].illusory_terrain is Terrain.SEA


# -- Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT's own end-of-turn intel grant


def test_run_turn_grants_a_double_agent_report_when_apparently_hired_and_in_the_hiring_kingdoms_own_territory():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    spy = LeaderState(20, 1, "Double Agent", coord, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    spy.double_agent_hired_by_kingdom_id = 2
    state.add_leader(spy)
    leader = _empty_plan_leader(10, "A")

    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    matching = [r for r in results if r.phase_label == "double-agent-report"]
    assert len(matching) == 1
    assert matching[0].leader_id == 20
    assert isinstance(matching[0].result, SpyReport)
    assert state.leaders[20].double_agent_hired_by_kingdom_id is None


def test_run_turn_grants_no_double_agent_report_when_the_province_is_not_the_hiring_kingdoms_own():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    # Owned by a third Kingdom, not the hiring Kingdom (2).
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=3))
    spy = LeaderState(20, 1, "Double Agent", coord, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    spy.double_agent_hired_by_kingdom_id = 2
    state.add_leader(spy)
    leader = _empty_plan_leader(10, "A")

    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert not [r for r in results if r.phase_label == "double-agent-report"]
    assert state.leaders[20].double_agent_hired_by_kingdom_id is None


def test_run_turn_no_hire_this_turn_grants_no_report_and_draws_no_extra_rng():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    coord = HexCoord(5, 5)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    spy = LeaderState(20, 1, "Double Agent", coord, race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    state.add_leader(spy)  # double_agent_hired_by_kingdom_id stays None -- not hired this turn
    leader = _empty_plan_leader(10, "A")

    rng = ScriptedRandom([0.0])
    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=rng)

    assert not [r for r in results if r.phase_label == "double-agent-report"]


def test_run_turn_empty_sp_block_leaves_special_encounter_plan_empty():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.leaders[10].special_encounter_plan == ()


def test_run_turn_leaves_an_absent_leaders_own_special_encounter_plan_untouched():
    # A leader not included in this call's own turn_leaders (e.g. never
    # dispatched this turn for whatever reason) keeps whatever real SEP
    # they already had recorded, rather than being reset to empty.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(5, 5)))
    absent_leader = LeaderState(20, kingdom_id=1, name="B", location=HexCoord(6, 6))
    absent_leader.special_encounter_plan = (SearchTactic(Maneuver.MELEE),)
    state.add_leader(absent_leader)
    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 0, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.leaders[20].special_encounter_plan == (SearchTactic(Maneuver.MELEE),)


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
    # Phase 307: same-origin (distance 0) union is only guaranteed (100%)
    # at March level 2+ -- level 0's own 80% left this test's real,
    # unscripted `random.Random(0)` sequence sensitive to a threshold
    # that shifted once the real MARCH TABLE replaced the old flat 85%.
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
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


def test_run_turn_multi_attacker_lmove_threads_apply_fanaticism_true():
    # Phase 744: the multi-attacker-LMOVE dispatch's own real
    # fight_multi_attacker_battle() call now opts real production
    # battles into Fanaticism -- mirrors the "mock the shared function,
    # assert the call kwarg" convention already used for execute_move()/
    # execute_pursue()'s own equivalent Phase 744 tests.
    state = _base_state()
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    stub_report = BattleReport(battle_result=BattleResult(), conquered=False)
    stub_battle = MultiAttackerBattle(leader_ids=[10, 20], report=stub_report)
    with patch("ak_engine.turn.turn_processor.fight_multi_attacker_battle") as mock_fight:
        mock_fight.return_value = [stub_battle]
        run_turn([TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    mock_fight.assert_called_once()
    assert mock_fight.call_args.kwargs["apply_fanaticism"] is True


def test_run_turn_multi_attacker_lmove_reports_illegal_move_from_contested():
    # Phase 718: _dispatch_multi_attacker_lmove()'s own real is_illegal_
    # move_from_contested() check, mirroring test_move_execution.py's
    # own single-mover equivalent.
    state = _base_state()
    state.provinces[ORIGIN].contested_by_kingdom_id = 1
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert len(results) == 2
    assert all(isinstance(r.error, IllegalMoveFromContestedError) for r in results)


def test_run_turn_multi_attacker_lmove_reports_transport_illegal_move():
    # Phase 737: _dispatch_multi_attacker_lmove() has its own separate
    # movement logic (never calls execute_move()) and needs its own
    # copy of find_transport_illegality() -- an unassisted land army
    # moving onto Sea terrain is refused here too, mirroring test_move_
    # execution.py's own single-mover equivalent.
    state = _base_state()
    state.provinces[TARGET].terrain = Terrain.SEA
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=march_4))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN, skills=march_4))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=10))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=5, commanded_by=20))

    leader_a = _leader_with_phase(10, "A", "P0", _lmove_phase("P0", TARGET))
    leader_b = _leader_with_phase(20, "B", "P0", _lmove_phase("P0", TARGET))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert len(results) == 2
    assert all(isinstance(r.error, TransportIllegalMoveError) for r in results)
    assert all(r.error.reason == "insufficient_water_transport" for r in results)


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
    # Phase 630: each mover's own Ranger of the Plains merit (TARGET is
    # Plains terrain, per _base_state()), not just one shared credit.
    assert state.leaders[10].merit_tally.plains_explorations == 1
    assert state.leaders[30].merit_tally.plains_explorations == 1


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
    # Phase 307: guarantees B/C's own same-origin union (see the sibling
    # test's own Phase 307 note above for why).
    march_4 = _skills_with(Ability.MARCH, 4, 9)
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=ORIGIN2, skills=march_4))
    state.add_leader(LeaderState(30, kingdom_id=1, name="C", location=ORIGIN2, skills=march_4))
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
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.01, 0.0])
    )

    by_leader = {r.leader_id: r for r in results}
    # Lower-skill leader 10 gets the guaranteed (subject to aptitude) roll;
    # leader 20 (already higher) gets nothing this phase -- only reachable
    # if they were actually grouped together, not resolved independently.
    assert by_leader[10].result.skill_rose is True
    assert by_leader[10].result.new_skill == 2
    assert by_leader[20].result.skill_rose is False
    assert by_leader[20].result.new_skill == 4


def test_run_turn_pools_armies_for_co_located_tactical_practicers():
    # Phase 304 end-to-end: two co-located leaders both ordering Practice
    # Tactical get grouped by run_turn()'s own same-ability/same-location
    # rule (Phase 46) exactly like any other ability, and now actually
    # resolve through the [6.1] army-pooling mechanic instead of
    # silently training nobody. Leader 10's own Green army has no
    # higher-tier army under 10's own command -- only leader 20's pooled
    # Veteran army makes it trainable.
    state = _practice_state(10, 20)
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.GREEN, ORIGIN, commanded_by=10))
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.VETERAN, ORIGIN, commanded_by=20))
    leader_a = _leader_with_phase(10, "A", "P0", _practice_phase("P0", Ability.TACTICAL))
    leader_b = _leader_with_phase(20, "B", "P0", _practice_phase("P0", Ability.TACTICAL))

    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0])
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[10].result.not_implemented_for_ability is False
    assert by_leader[10].result.trained_army_ids == (1,)
    assert by_leader[20].result.trained_army_ids == ()
    assert state.armies[1].quality is Quality.AVERAGE
    assert state.armies[2].quality is Quality.VETERAN  # untouched


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
    # A third value pads leader_b's own Sage device-discovery roll (Phase
    # 171) -- moot here since skill=0 gives it a 0% chance regardless.
    results = run_turn(
        [TurnLeader(leader_a, 1), TurnLeader(leader_b, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.07, 0.07, 0.9, 0.0]),
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
        rng=ScriptedRandom([0.07, 0.07, 0.0]),
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
        rng=ScriptedRandom([0.01, 0.01, 0.0]),
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
    # Phase 573: run_turn() now replenishes every army's own movement
    # points at the very end (real per-turn housekeeping this project
    # never had before), so a post-run_turn() movement_points reading no
    # longer reflects mid-turn deductions -- checking for the
    # "forced-rebattle" PhaseDispatchResult itself (the same signal
    # test_run_turn_does_not_force_a_rebattle_once_movement_points_run_out
    # already uses, just for presence instead of absence) is the direct,
    # still-valid way to confirm the rebattle/deduction logic engaged.
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] != []


def test_run_turn_forced_rebattle_wires_battle_carrier_destruction():
    # Phase 716: same real-battle fixture as the test above, proving the
    # forced-rebattle continuation's own real fight_battle() call
    # reaches turn/sea_transport.py apply_battle_carrier_destruction()
    # (Phase 686's own "mock the shared function, assert the call"
    # convention).
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))

    with patch("ak_engine.turn.turn_processor.apply_battle_carrier_destruction") as mock_cascade:
        run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    mock_cascade.assert_called_once()


def test_run_turn_does_not_force_a_rebattle_once_movement_points_run_out():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=0))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


# -- Plague spread (Phase 233) ----------------------------------------------


def test_run_turn_spreads_plague_to_adjacent_provinces_at_phase_boundaries():
    state = _base_state()
    state.provinces[TARGET].plague_active = True

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    # Deterministic under this fixed seed -- see turn/plague_spread.py's
    # own module docstring for the mechanic (rulebook [4.25.3]) this
    # exercises via run_turn()'s own per-phase-boundary dispatch.
    assert state.provinces[ORIGIN].plague_active is True

    # Phase 234: each newly-infected coordinate is also surfaced as its
    # own PhaseDispatchResult, the same sentinel convention
    # "forced-rebattle" already uses, so report/turn_report.py's own
    # record_plague_spread_world_events() can find it in run_turn()'s
    # return value.
    spread = [r for r in results if r.phase_label == "plague-spread"]
    assert [r.result for r in spread] == [ORIGIN]
    assert spread[0].leader_id == 0
    assert spread[0].segment_index == -1
    assert spread[0].action is None
    assert state.provinces[ORIGIN2].plague_active is False


def test_run_turn_does_not_force_a_rebattle_when_no_defender_remains():
    state = _base_state()
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TARGET, movement_points=3))
    del state.armies[201]  # the defender fixture army -- nothing left to fight

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(42))

    assert [r for r in results if r.phase_label == "forced-rebattle"] == []


def test_run_turn_forced_rebattle_retreat_uses_the_original_invasion_origin():
    # Phase 409: without ProvinceState.contested_from_coord, this rebattle
    # had no origin to pass to fight_battle(), so a clean-swept attacker
    # fell back to the wrong (defender-style, nearest-friendly-neighbor-
    # of-TARGET) rule instead of the real rulebook [7.4] one. FAR_ORIGIN
    # is deliberately not adjacent to TARGET at all, so the old fallback
    # could never have produced it -- only reading contested_from_coord
    # can. seed=1 is a decisive defender win (GREEN attacker vs. ELITE
    # defender) found by search.
    far_origin = HexCoord(8, 8)
    state = _base_state()
    state.add_province(ProvinceState(far_origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.provinces[TARGET].contested_by_kingdom_id = 1
    state.provinces[TARGET].contested_from_coord = far_origin
    state.add_army(ArmyState(101, 1, ArmyType.GARRISON, Quality.GREEN, TARGET, movement_points=3))
    state.armies[201].quality = Quality.ELITE
    state.armies[201].army_type = ArmyType.HVY_CAVALRY

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert 101 in state.armies
    assert state.armies[101].location == far_origin


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
    # Phase 259: a King's death installs a Royal Heir under the same
    # leader_id rather than leaving the Kingdom leaderless.
    assert 5 in state.dead_leaders
    assert state.leaders[5].is_royal_heir is True


def test_run_turn_one_sided_challenge_dispatches_normally_not_as_mutual():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    state.add_leader(LeaderState(20, kingdom_id=2, name="King", location=ORIGIN, is_king=True))
    leaders = [
        _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)),
        # B has no reciprocal order this phase at all -- not a mutual pair.
        _leader_with_phase(20, "King", "P1", _encounter_phase("P1", ActionCode.CHALLENGE, 10, melee=True)),
    ]

    # P1's own King-challenges-a-Hero roll ("evade encounters from Kings
    # 50% of the time") also fires this turn -- 0.9 misses it (refused,
    # no combat, matching pre-Phase-747 behavior, where this exact draw
    # ran out of an empty script and errored silently inside that one
    # phase's own dispatch, rather than proceeding). Phase 747 then adds
    # one more unconditional `rng.random()` draw per kingdom (2 here).
    results = run_turn(
        [TurnLeader(leaders[0], 1), TurnLeader(leaders[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.9, 0.0, 0.0]),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    a_result = by_label[(10, "P0")].result
    assert a_result.accepted is False
    assert a_result.reason == "encounter refused"  # mutual_encounter defaults False, King target refuses


def test_run_turn_self_targeting_pursue_is_not_misdetected_as_mutual():
    # Also the Phase 71 correct-path check: a self-targeting Pursue is a
    # Patrol declaration, not an ordinary Pursue dispatch -- with no
    # other leader around to intercept, it produces no dispatch result
    # at all (rule (d): "no current threat" -> nothing to report), not
    # the nonsensical self-battle the old (pre-Phase-71) dispatch path
    # would have produced.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN))
    leader = _leader_with_phase(10, "A", "P0", _encounter_phase("P0", ActionCode.PURSUE, 10, melee=False))

    results = run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0, 0.0]))

    assert results == []


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


# -- Naval Long Defend (Phase 524) -------------------------------------------

TWO_HEXES_AWAY = HexCoord(6, 3)  # not adjacent to DEFEND_HOME, but within radius 2
TWO_AWAY_ATTACKER_ORIGIN = HexCoord(6, 2)  # adjacent to TWO_HEXES_AWAY


def test_run_turn_defend_reinforces_two_hexes_away_with_long_naval_defend():
    # AdvancedAbility.NAVAL_LONG_DEFEND doubles the coverage radius (Phase
    # 524) -- a Fleet-commanding leader holding it reacts to an invasion
    # two hexes out, something the default radius-1 coverage (proven by
    # test_run_turn_defend_does_not_reinforce_a_province_it_does_not_own
    # and friends) would never reach.
    state = _defend_state()
    state.leaders[100].advanced_abilities.add(AdvancedAbility.NAVAL_LONG_DEFEND)
    state.armies[901] = ArmyState(901, 2, ArmyType.FLEET, Quality.GREEN, DEFEND_HOME, commanded_by=100)
    state.add_province(ProvinceState(TWO_HEXES_AWAY, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(TWO_AWAY_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=TWO_AWAY_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TWO_AWAY_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, TWO_AWAY_ATTACKER_ORIGIN, TWO_HEXES_AWAY, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    by_leader = {r.leader_id: r for r in results}
    move_result = by_leader[200].result
    assert isinstance(move_result, MoveExecutionResult)
    assert move_result.battle_report is not None  # reinforced from 2 hexes away


def test_run_turn_defend_does_not_reach_two_hexes_away_without_the_ability():
    # Same geometry as above, but no NAVAL_LONG_DEFEND and no Fleet --
    # ordinary radius-1 coverage never sees an invasion this far out.
    state = _defend_state()
    state.add_province(ProvinceState(TWO_HEXES_AWAY, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(TWO_AWAY_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=TWO_AWAY_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, TWO_AWAY_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    defender = _leader_with_phase(100, "Defender", "P0", _defend_phase("P0"))
    attacker = _attacker(200, 902, TWO_AWAY_ATTACKER_ORIGIN, TWO_HEXES_AWAY, "P1")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1)], state, board_width=BOARD_WIDTH, rng=random.Random(7)
    )

    by_leader = {r.leader_id: r for r in results}
    move_result = by_leader[200].result
    assert isinstance(move_result, MoveExecutionResult)
    assert move_result.battle_report is None  # no reinforcement reached this far
    assert state.leaders[100].location == DEFEND_HOME  # defender never moved


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
        [TurnLeader(pursuer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0])
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
        [TurnLeader(trailer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0])
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


def test_run_turn_trail_continuation_wires_spy_blackmail():
    # Same P0-miss/P1-continuation shape as the test above, proving
    # `caster_has_spy_blackmail` reaches through `_continue_active_
    # pursuits()`'s own Trail branch, not just the initial dispatch.
    state = _chase_state()
    state.leaders[20].is_king = True
    state.leaders[10].advanced_abilities.add(AdvancedAbility.SPY_BLACKMAIL)
    p0 = _trail_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    trailer = _three_phase_leader(10, "Trailer", p0, p1, p2)

    results = run_turn(
        [TurnLeader(trailer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0, 0.0])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.result.spied_on is True
    assert p1_entry.result.blackmail_claim is not None
    assert state.kingdoms[2].pending_blackmail is p1_entry.result.blackmail_claim


# -- Trail's own "Actions" field (Phase 252) ---------------------------------


def test_run_turn_trail_backfills_the_targets_own_action_this_phase():
    state = _chase_state()
    state.leaders[20].location = CHASE_START  # same province as trailer -> guaranteed catch
    trailer = _leader_with_phase(10, "Trailer", "P0", _trail_phase("P0", 20))
    target = Leader(
        leader_id=20,
        name="Target",
        plan=ActionPlan(
            leader_id=20,
            segments=[PlanSegment(0, 0, (), {"P0": PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])})],
        ),
    )

    results = run_turn(
        [TurnLeader(trailer, 1), TurnLeader(target, 2)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.1, 0.5, 0.5, 0.0, 0.0])
    )

    trail_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0").result
    assert trail_result.spied_on is True
    assert trail_result.actions is ActionCode.WAIT


def test_run_turn_trail_actions_is_none_when_target_has_no_order_this_phase():
    state = _chase_state()
    state.leaders[20].location = CHASE_START
    trailer = _leader_with_phase(10, "Trailer", "P0", _trail_phase("P0", 20))
    # Target has no P0 phase at all -- idle this phase.
    target = Leader(leader_id=20, name="Target", plan=ActionPlan(leader_id=20, segments=[PlanSegment(0, 0, (), {})]))

    results = run_turn(
        [TurnLeader(trailer, 1), TurnLeader(target, 2)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.1, 0.5, 0.5, 0.0, 0.0])
    )

    trail_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0").result
    assert trail_result.spied_on is True
    assert trail_result.actions is None


def test_run_turn_trail_continuation_backfills_the_targets_own_action():
    # Same P0-miss/P1-continuation shape as
    # test_run_turn_unresolved_trail_preempts_p1_and_continues_the_chase,
    # but the target is now a real TurnLeader with its own P1 order, so
    # the continuation's own backfill (via _continue_active_pursuits) has
    # something real to find.
    state = _chase_state()
    p0 = _trail_phase("P0", 20)
    p1 = _lmove_phase("P1", DECOY)
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    trailer = _three_phase_leader(10, "Trailer", p0, p1, p2)
    target = Leader(
        leader_id=20,
        name="Target",
        plan=ActionPlan(
            leader_id=20,
            segments=[PlanSegment(0, 0, (), {"P1": PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])})],
        ),
    )

    results = run_turn(
        [TurnLeader(trailer, 1), TurnLeader(target, 2)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.1, 0.5, 0.5, 0.0, 0.0])
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1  # continuation, not a real plan segment
    assert p1_entry.result.spied_on is True
    assert p1_entry.result.actions is ActionCode.WAIT


def test_run_turn_unresolved_move_chase_preempts_p1_and_continues_the_chase():
    # Phase 632: CHASE_TARGET is 2 hexes from CHASE_START (same geometry
    # the Pursue/Trail tests above reuse) -- P0's own LMOVE hop lands at
    # CHASE_STEP (not yet arrived), P1's own explicit LMOVE-to-DECOY
    # order is preempted by the ongoing chase's own continuation instead
    # (the user's own confirmed "mirror Pursue/Trail exactly" broad
    # reading), and once the chase resolves at P1, P2 dispatches
    # normally again.
    state = _chase_state()
    p0 = _lmove_phase("P0", CHASE_TARGET)
    p1 = _lmove_phase("P1", DECOY)  # would relocate the mover to DECOY if NOT preempted
    p2 = PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[0])
    mover = _three_phase_leader(10, "Mover", p0, p1, p2)

    results = run_turn([TurnLeader(mover, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.5] * 10))

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    p0_result = by_label[(10, "P0")].result
    assert p0_result.reached_target is False
    assert p0_result.stopped_chasing is False
    # new_location, not state.leaders[10].location -- by the time run_turn()
    # returns, the P1 continuation below has already advanced the mover
    # further; new_location is P0's own immutable snapshot of the hop it
    # actually took.
    assert p0_result.new_location == CHASE_STEP

    # P1's own LMOVE-to-DECOY order never dispatched -- the chase
    # continuation ran instead, at segment_index=-1 (not tied to a real
    # plan segment).
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.LMOVE
    assert p1_entry.result.reached_target is True
    assert state.leaders[10].location == CHASE_TARGET  # not DECOY

    # Resolved -- P2's own WAIT order dispatches normally again.
    p2_entry = by_label[(10, "P2")]
    assert p2_entry.segment_index == 0
    assert p2_entry.action is ActionCode.WAIT


def test_run_turn_move_chase_that_stops_does_not_preempt_the_next_phase():
    # Mirrors turn/move_execution.py's own "stop chasing" geometry (a
    # mover pinned at the board's own southern edge, y=14 of
    # NORMAL_MAP_BOUNDS' 0..14 range, with a target further south than
    # any real province can be -- no neighbor can possibly get closer)
    # via non-negative coordinates so it round-trips through the real
    # LMOVE hex-number encode/decode path, not synthesized directly.
    state = GameState()
    origin = HexCoord(5, 14)
    unreachable_target = HexCoord(5, 200)
    state.add_kingdom(KingdomState(1, "Stuckia", Race.HUMAN, Alignment.NEUTRAL, origin))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Mover", location=origin))
    p0 = _lmove_phase("P0", unreachable_target)
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    mover = _leader_with_phase(10, "Mover", "P0", p0)
    mover.plan.segments[0] = PlanSegment(0, 1, (), {"P0": p0, "P1": p1})

    results = run_turn([TurnLeader(mover, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(10, "P0")].result.stopped_chasing is True
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # ordinary dispatch, not a continuation
    assert p1_entry.action is ActionCode.WAIT


def test_run_turn_pursue_with_no_target_is_not_registered_for_continuation():
    # "pursuer or target not found" is a terminal reason, not "did not
    # catch up this phase" -- P1's own order must dispatch normally, not
    # be preempted by a chase that can never resolve.
    state = _chase_state()
    p0 = _pursue_phase("P0", 999)  # no such leader
    p1 = _lmove_phase("P1", DECOY)
    pursuer = _leader_with_phase(10, "Pursuer", "P0", p0)
    pursuer.plan.segments[0] = PlanSegment(0, 1, (), {"P0": p0, "P1": p1})

    results = run_turn([TurnLeader(pursuer, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(10, "P0")].result.reason == "pursuer or target not found"
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # ordinary _dispatch_single, not a continuation
    assert isinstance(p1_entry.result, MoveExecutionResult)
    assert state.leaders[10].location == DECOY


# -- Patrol / "Characters On Patrol" (Phase 71) -----------------------------


PATROL_HOME = HexCoord(5, 4)
INTRUDER_HEX = _neighbors(PATROL_HOME, _BOUNDS)[0]
MOVE_TARGET = _neighbors(PATROL_HOME, _BOUNDS)[1]


def _patrol_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Patrolia", Race.HUMAN, Alignment.GOOD, PATROL_HOME))
    state.add_kingdom(KingdomState(2, "Intrudia", Race.HUMAN, Alignment.EVIL, INTRUDER_HEX))
    state.add_province(ProvinceState(PATROL_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(INTRUDER_HEX, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(MOVE_TARGET, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Patroller", location=PATROL_HOME))
    return state


def _patrol_declare_phase(label: str, own_leader_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.PURSUE, obj=own_leader_id, extra=[0, -1])  # peaceful, no tactics


def test_run_turn_patrol_intercepts_an_adjacent_intruder_and_preempts_a_later_order():
    state = _patrol_state()
    state.add_leader(LeaderState(20, kingdom_id=2, name="Intruder", location=INTRUDER_HEX))
    p0 = _patrol_declare_phase("P0", 10)
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    patroller = _two_phase_leader(10, "Patroller", p0, p1)

    # Spy skill 0 -> a 50% wander roll every phase the intruder is still
    # adjacent -- run_turn always processes all 5 phases (P0-P4)
    # regardless of how many the plan itself uses, and nothing here ever
    # removes the intruder, so the standing Patrol keeps re-checking
    # through P2-P4 too; one scripted success per phase.
    results = run_turn([TurnLeader(patroller, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.0, 0.0] * 5))

    by_label = {(r.leader_id, r.phase_label): r for r in results}

    p0_entry = by_label[(10, "P0")]
    assert p0_entry.segment_index == -1
    assert p0_entry.action is ActionCode.PURSUE
    assert p0_entry.result.intercepted is True
    assert p0_entry.result.target_leader_id == 20

    # P1's own WAIT never dispatched -- the still-adjacent intruder
    # preempted it too (rule (d): the Patrol re-checks every phase).
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == -1
    assert p1_entry.action is ActionCode.PURSUE
    assert p1_entry.result.target_leader_id == 20


def test_run_turn_patrol_lets_the_scheduled_order_through_when_no_threat():
    state = _patrol_state()  # no intruder anywhere
    p0 = _patrol_declare_phase("P0", 10)
    p1 = PlanPhase(label="P1", action=ActionCode.WAIT, obj=0, extra=[0])
    patroller = _two_phase_leader(10, "Patroller", p0, p1)

    results = run_turn([TurnLeader(patroller, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0, 0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    # No threat at P0 -- the Patrol declaration itself produces no
    # dispatch result at all (rule (d): "other orders ... are used").
    assert (10, "P0") not in by_label
    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # ordinary dispatch, not preempted
    assert p1_entry.action is ActionCode.WAIT


def test_run_turn_patrol_is_cancelled_by_a_later_move_order():
    # The intruder stays adjacent the whole time -- proves cancellation
    # itself, at P1, wins over interception, not just "there was nothing
    # to intercept."
    state = _patrol_state()
    state.add_leader(LeaderState(20, kingdom_id=2, name="Intruder", location=INTRUDER_HEX))
    p0 = _patrol_declare_phase("P0", 10)
    p1 = _lmove_phase("P1", MOVE_TARGET)
    patroller = _two_phase_leader(10, "Patroller", p0, p1)

    # One roll: P0's own adjacent-hex wander check (succeeds, intercepts).
    # P1's cancelling LMOVE removes the Patrol before any P1 wander check
    # would otherwise run, even though the intruder is still adjacent.
    results = run_turn([TurnLeader(patroller, 1)], state, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.9, 0.0, 0.0]))

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(10, "P0")].result.intercepted is True

    p1_entry = by_label[(10, "P1")]
    assert p1_entry.segment_index == 0  # cancellation ran before dispatch -- not preempted
    assert p1_entry.action is ActionCode.LMOVE
    assert isinstance(p1_entry.result, MoveExecutionResult)
    assert state.leaders[10].location == MOVE_TARGET


# -- Defend battle-loss cancellation (Phase 72) ------------------------------


# Phase 314: DL_FIRST_ATTACKER_ORIGIN/DL_SECOND_COVERED/DL_SECOND_ATTACKER_ORIGIN
# moved -- neighbors()'s own real-data-sourced parity fix (see turn/movement.py's
# docstring) changed which hexes are actually adjacent to DL_FIRST_COVERED/
# DL_SECOND_COVERED; DL_HOME and DL_FIRST_COVERED are unaffected.
DL_HOME = HexCoord(5, 4)
DL_FIRST_COVERED = HexCoord(5, 3)  # adjacent to DL_HOME
DL_FIRST_ATTACKER_ORIGIN = HexCoord(6, 3)  # adjacent to DL_FIRST_COVERED
DL_SECOND_COVERED = HexCoord(4, 3)  # adjacent to DL_FIRST_COVERED (the leader's post-reinforcement location)
DL_SECOND_ATTACKER_ORIGIN = HexCoord(3, 3)  # adjacent to DL_SECOND_COVERED


def _defend_loss_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, DL_FIRST_ATTACKER_ORIGIN))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, DL_HOME))
    for coord in (DL_HOME, DL_FIRST_COVERED, DL_SECOND_COVERED):
        state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(DL_FIRST_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(DL_SECOND_ATTACKER_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(100, kingdom_id=2, name="Defender", location=DL_HOME))
    state.add_army(ArmyState(901, 2, ArmyType.GARRISON, Quality.GREEN, DL_HOME, commanded_by=100))
    return state


def _defend_loss_attacker(leader_id: int, army_id: int, origin: HexCoord, target: HexCoord, label: str) -> Leader:
    return _leader_with_phase(leader_id, "Attacker", label, _lmove_phase(label, target))


def test_run_turn_defend_battle_loss_blocks_a_later_redeclaration():
    # seed 1: the attacker wins this exact matchup (HVY_CAVALRY/ELITE vs
    # GARRISON/GREEN) -- verified deterministic for this fixture. (Phase
    # 296: reselected after fight_battle()'s own new terrain-line-length-
    # cap roll shifted the RNG stream -- seed 0 no longer lands here.)
    state = _defend_loss_state()
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=DL_SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _defend_phase("P2"))
    attacker = _defend_loss_attacker(200, 902, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_attacker = _defend_loss_attacker(300, 903, DL_SECOND_ATTACKER_ORIGIN, DL_SECOND_COVERED, "P3")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1), TurnLeader(second_attacker, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(1),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(200, "P1")].result.battle_report.battle_result.winner == "attacker"  # defender lost

    # P2's Defend re-declaration never re-arms coverage -- reinforcement
    # never relocates the leader again for the P3 invasion, regardless of
    # whatever their own army independently did (e.g. retreated).
    assert state.leaders[100].location == DL_FIRST_COVERED


def test_run_turn_defend_battle_win_does_not_block_a_later_redeclaration():
    # seed 1: the defender wins this exact matchup -- verified
    # deterministic for this fixture. (Phase 370: the shared
    # _defend_loss_state()'s own GARRISON/GREEN defender is categorically
    # outmatched by an ELITE HVY_CAVALRY attacker under the real,
    # deterministic column_bres formula -- luck's own bounded R_s
    # multiplier, up to ~2.5x/4x, was never going to be enough to flip
    # that big a strength gap, unlike the pre-Phase-370 model's plain
    # probability-then-coin-flip win roll. Evened the defender's own army
    # up to the attacker's own type/quality so a genuine coin-flip battle
    # -- decided by the real luck draws, not an unwinnable mismatch -- is
    # possible again. Phase 744: both kingdoms here are Alignment.GOOD, so
    # turning on real per-army Fanaticism rolls (apply_fanaticism=True at
    # every real production battle call site) makes this a genuinely live
    # coin-flip, not just an RNG-position shift -- seed 0 no longer lands
    # a defender win, reselected to seed 1.)
    state = _defend_loss_state()
    state.add_army(ArmyState(901, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_HOME, commanded_by=100))
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=DL_SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )
    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _defend_phase("P2"))
    attacker = _defend_loss_attacker(200, 902, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_attacker = _defend_loss_attacker(300, 903, DL_SECOND_ATTACKER_ORIGIN, DL_SECOND_COVERED, "P3")

    results = run_turn(
        [TurnLeader(defender, 2), TurnLeader(attacker, 1), TurnLeader(second_attacker, 1)],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(1),
    )

    by_label = {(r.leader_id, r.phase_label): r for r in results}
    assert by_label[(200, "P1")].result.battle_report.battle_result.winner == "defender"  # defender won

    # P2's Defend re-declaration re-arms coverage -- the P3 invasion
    # relocates the leader again.
    assert state.leaders[100].location == DL_SECOND_COVERED


DL_ILLEGAL_ORIGIN = HexCoord(4, 3)  # adjacent to DL_FIRST_COVERED, distinct from the other DL_* origins


def test_run_turn_defend_battle_loss_blocks_a_later_redeclaration_with_a_leading_group_error():
    # Phase 299 regression: _dispatch_multi_attacker_lmove() appends a
    # validation-error entry for an illegal mover BEFORE the real
    # MultiAttackerMoveResult entries for the movers who actually joined
    # the battle (see
    # test_run_turn_excludes_an_illegal_contested_mover_but_still_groups_the_rest
    # for that ordering in isolation). _apply_defend_battle_loss used to
    # trust dispatch_results[0] to carry the real battle, so when a group
    # like that reinforced a Defend leader's own province, the loss went
    # undetected and the Defend order was never cancelled. Reproduced
    # here by declaring the illegal mover first in the TurnLeader list so
    # its error lands at index 0 of the group's own dispatch_results.
    state = _defend_loss_state()
    state.add_province(ProvinceState(DL_ILLEGAL_ORIGIN, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.provinces[DL_ILLEGAL_ORIGIN].contested_by_kingdom_id = 1  # self-contested -- illegal to move out of

    state.add_leader(LeaderState(400, kingdom_id=1, name="IllegalMover", location=DL_ILLEGAL_ORIGIN))
    state.add_army(
        ArmyState(904, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_ILLEGAL_ORIGIN, commanded_by=400, movement_points=3)
    )
    state.add_leader(LeaderState(200, kingdom_id=1, name="Attacker", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(902, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=200, movement_points=3)
    )
    state.add_leader(LeaderState(250, kingdom_id=1, name="SecondWave", location=DL_FIRST_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(905, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_FIRST_ATTACKER_ORIGIN, commanded_by=250, movement_points=3)
    )
    state.add_leader(LeaderState(300, kingdom_id=1, name="SecondAttacker", location=DL_SECOND_ATTACKER_ORIGIN))
    state.add_army(
        ArmyState(903, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, DL_SECOND_ATTACKER_ORIGIN, commanded_by=300, movement_points=3)
    )

    defender = _two_phase_leader(100, "Defender", _defend_phase("P0"), _defend_phase("P2"))
    illegal_mover = _leader_with_phase(400, "IllegalMover", "P1", _lmove_phase("P1", DL_FIRST_COVERED))
    attacker = _defend_loss_attacker(200, 902, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_wave = _defend_loss_attacker(250, 905, DL_FIRST_ATTACKER_ORIGIN, DL_FIRST_COVERED, "P1")
    second_attacker = _defend_loss_attacker(300, 903, DL_SECOND_ATTACKER_ORIGIN, DL_SECOND_COVERED, "P3")

    results = run_turn(
        [
            TurnLeader(defender, 2),
            TurnLeader(illegal_mover, 1),  # declared first -- its error lands at group index 0
            TurnLeader(attacker, 1),
            TurnLeader(second_wave, 1),
            TurnLeader(second_attacker, 1),
        ],
        state,
        board_width=BOARD_WIDTH,
        rng=random.Random(1),
    )

    by_leader = {r.leader_id: r for r in results}
    assert by_leader[400].error is not None
    assert by_leader[400].result is None
    assert isinstance(by_leader[200].result, MultiAttackerMoveResult)
    assert isinstance(by_leader[250].result, MultiAttackerMoveResult)
    assert sorted(by_leader[200].result.battle.leader_ids) == [200, 250]
    assert by_leader[200].result.battle.report.battle_result.winner == "attacker"  # defender lost

    # Despite the illegal mover's error occupying index 0 of the group's
    # own dispatch_results, the fix still finds the real battle result and
    # correctly cancels the Defend order on loss -- P2's re-declaration
    # never re-arms coverage for the P3 invasion.
    assert state.leaders[100].location == DL_FIRST_COVERED


# -- build_missed_deadline_turn_leaders() (Phase 138) --


def test_build_missed_deadline_turn_leaders_defends_the_army_commanding_leader():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=HexCoord(3, 3)))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, HexCoord(3, 3), commanded_by=10))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)

    assert len(turn_leaders) == 1
    tl = turn_leaders[0]
    assert tl.kingdom_id == 1
    assert tl.leader.leader_id == 10
    phases = tl.leader.plan.segments[0].phases
    assert phases["P0"].action is ActionCode.DEFEND
    for label in ("P1", "P2", "P3", "P4"):
        assert phases[label].action is ActionCode.WAIT


def test_build_missed_deadline_turn_leaders_waits_the_armyless_leader():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Advisor", location=HexCoord(4, 4)))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)

    assert len(turn_leaders) == 1
    phases = turn_leaders[0].leader.plan.segments[0].phases
    for label in ("P0", "P1", "P2", "P3", "P4"):
        assert phases[label].action is ActionCode.WAIT


def test_build_missed_deadline_turn_leaders_only_includes_that_kingdoms_own_leaders():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otheria", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(3, 3)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="B", location=HexCoord(4, 4)))
    state.add_leader(LeaderState(30, kingdom_id=2, name="C", location=HexCoord(9, 9)))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)

    assert {tl.leader.leader_id for tl in turn_leaders} == {10, 20}
    assert all(tl.kingdom_id == 1 for tl in turn_leaders)


def test_build_missed_deadline_turn_leaders_dispatches_cleanly_through_run_turn():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="General", location=HexCoord(3, 3)))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, HexCoord(3, 3), commanded_by=10))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Advisor", location=HexCoord(4, 4)))

    turn_leaders = build_missed_deadline_turn_leaders(state, 1)
    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert len(results) == 10  # 2 leaders x 5 phases
    assert all(r.error is None for r in results)
    general_p0 = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0")
    advisor_p0 = next(r for r in results if r.leader_id == 20 and r.phase_label == "P0")
    assert general_p0.action is ActionCode.DEFEND
    assert advisor_p0.action is ActionCode.WAIT
    assert isinstance(advisor_p0.result, NoOpResult)


# ---------------------------------------------------------------------------
# Gate Angel / VALHALLA visit (Phase 199) -- finalize_gate_angel_visit()
# (Phase 196) wired in after the PHASE_LABELS loop. GATE_ANGEL_ELIGIBLE_
# ALIGNMENTS is (GOOD, DRUID, NEUTRAL, PAGAN, EVIL), so choice_indices=[0]
# picks GOOD as the due alignment for turn/cast_execution.py's own draw.
# ---------------------------------------------------------------------------


def _cast_gate_angel_phase(label: str) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.CAST, obj=Spell.GATE_ANGEL.value, extra=[0])


def test_run_turn_spawns_a_valhalla_visitor_after_a_successful_gate_angel_cast():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3), is_king=True))
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_gate_angel_phase("P0")), 1)]
    # [0] -> due alignment GOOD (matches kingdom 1). GameState.turn_number
    # defaults to 1, so visitor_selection is deterministic (Phase 386: the
    # roster's own final record, no rng.choice consumed at all).
    rng = ScriptedRandom([0.0], choice_indices=[0])

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=rng)

    visit_results = [r for r in results if r.phase_label == "gate-angel-visit"]
    assert len(visit_results) == 1
    visitor = visit_results[0].result
    assert visit_results[0].leader_id == VALHALLA_VISITOR_LEADER_ID
    assert visit_results[0].action is None
    assert visitor.leader_id == VALHALLA_VISITOR_LEADER_ID
    assert visitor.name == VALHALLA_ROSTER[Alignment.GOOD][-1].name
    assert state.leaders[VALHALLA_VISITOR_LEADER_ID] is visitor
    # Spawned beside kingdom 1's own King (leader 10), per the rulebook.
    assert visitor.location == HexCoord(3, 3)
    # The visitor's own fixed item is real ItemInstance state, not just the
    # LeaderState -- confirms finalize_gate_angel_visit()'s own item grant
    # flowed through run_turn() end to end.
    items = state.items_held_by(VALHALLA_VISITOR_LEADER_ID)
    assert len(items) == 1
    assert items[0].treasure == VALHALLA_ROSTER[Alignment.GOOD][-1].fixed_item


def test_run_turn_produces_no_gate_angel_result_when_the_cast_targets_the_wrong_alignment():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3)))
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_gate_angel_phase("P0")), 1)]
    # [0] -> due alignment GOOD -- doesn't match kingdom 1's own NEUTRAL
    rng = ScriptedRandom([0.0], choice_indices=[0])

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=rng)

    assert not [r for r in results if r.phase_label == "gate-angel-visit"]
    assert VALHALLA_VISITOR_LEADER_ID not in state.leaders


def test_run_turn_produces_no_gate_angel_result_when_no_leader_casts_it():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3)))

    results = run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    assert not [r for r in results if r.phase_label == "gate-angel-visit"]
    assert VALHALLA_VISITOR_LEADER_ID not in state.leaders


def test_run_turn_ordinary_valhalla_visit_fires_with_no_gate_angel_caster_anywhere():
    # Phase 756: uses _run_turn_unfiltered directly (not this file's own
    # run_turn() wrapper, which neutralizes the ordinary visit for every
    # other test in this file) -- the one dedicated end-to-end proof that
    # a real turn, with nobody anywhere casting Gate Angel, still produces
    # a real "valhalla-visit" sentinel via turn_processor.py's own wiring.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="King", location=HexCoord(3, 3), is_king=True))

    results = _run_turn_unfiltered([], state, board_width=BOARD_WIDTH, rng=random.Random(0))

    visit_results = [r for r in results if r.phase_label == "valhalla-visit"]
    assert len(visit_results) == 1
    assert visit_results[0].result.kingdom_id == 1
    assert not [r for r in results if r.phase_label == "gate-angel-visit"]


# ---------------------------------------------------------------------------
# Analytical Psychology end-of-turn Charm revert (Phase 302) --
# run_turn()'s own end-of-turn sweep, _revert_analytical_psychology_charms().
# ---------------------------------------------------------------------------


def _cast_charm_phase(label: str, target_leader_id: int) -> PlanPhase:
    return PlanPhase(label=label, action=ActionCode.CAST, obj=Spell.CHARM.value, extra=[target_leader_id])


def test_run_turn_reverts_an_analytical_psychology_protected_charm_at_end_of_turn():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Casteria", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_kingdom(KingdomState(2, "Protectia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.kingdoms[2].discoveries.add(Discovery.ANALYTICAL_PSYCHOLOGY)
    caster = LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3))
    target = LeaderState(78, kingdom_id=2, name="Protected Hero", location=HexCoord(3, 3))
    state.add_leader(caster)
    state.add_leader(target)
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_charm_phase("P0", 78)), 1)]

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(0))

    cast_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0")
    assert cast_result.result.applied is True  # the spell really did fire, not silently blocked
    # By the time run_turn() returns, the end-of-turn sweep has already put
    # the target back under their own original kingdom (2), not the
    # caster's (1) -- proving the revert genuinely ran, not just that the
    # Charm itself was rejected.
    assert state.leaders[78].kingdom_id == 2
    assert state.leaders[78].analytical_psychology_revert_kingdom_id is None


def test_run_turn_does_not_revert_an_ordinary_unprotected_charm():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Casteria", Race.HUMAN, Alignment.GOOD, HexCoord(3, 3)))
    state.add_kingdom(KingdomState(2, "Ordinaria", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    caster = LeaderState(10, kingdom_id=1, name="Caster", location=HexCoord(3, 3))
    target = LeaderState(78, kingdom_id=2, name="Ordinary Hero", location=HexCoord(3, 3))
    state.add_leader(caster)
    state.add_leader(target)
    turn_leaders = [TurnLeader(_leader_with_phase(10, "Caster", "P0", _cast_charm_phase("P0", 78)), 1)]

    results = run_turn(turn_leaders, state, board_width=BOARD_WIDTH, rng=random.Random(0))

    cast_result = next(r for r in results if r.leader_id == 10 and r.phase_label == "P0")
    assert cast_result.result.applied is True
    assert state.leaders[78].kingdom_id == 1  # stays charmed -- no protection, no revert


def test_run_turn_decomposes_the_graveyard_once_at_turn_end_when_over_the_world_cap():
    # Phase 309: turn/skeletal_decay.py decompose_graveyard() runs once,
    # after every phase, alongside _revert_analytical_psychology_charms
    # -- see run_turn()'s own docstring. A trivial single-WAIT-phase plan
    # is enough to exercise the end-of-run_turn() housekeeping sweep.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0)))
    for _ in range(340):
        state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HexCoord(0, 0)))
    for _ in range(20):
        state.record_battle_death(HexCoord(1, 1), ArmyType.HVY_CAVALRY, Quality.AVERAGE, kingdom_id=1)
    # 340 + 20 = 360 > 350 -- decay should remove round(20 * 0.10) == 2.

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert len(state.battle_graveyard[HexCoord(1, 1)]) == 18


# -- Per-turn treasury maintenance debit (Phase 404) -----------------------


def test_run_turn_debits_expected_expenses_from_treasury_once_at_turn_end():
    # Phase 404: turn/expenses.py apply_turn_maintenance() runs once,
    # alongside decompose_graveyard() -- see run_turn()'s own docstring.
    # The King himself contributes 0 leader pay (see expenses.py's own
    # leader_pay()), so the only expected debit here is the one Legion's
    # army maintenance (2 gold, ARMY_TABLE), a concrete, non-circular
    # expected value.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].treasury = 50
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0), is_king=True))
    state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0)))

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.kingdoms[1].treasury == 48


# -- Per-turn treasury revenue credit (Phase 412) --------------------------


def test_run_turn_credits_expected_revenues_to_treasury_before_debiting_expenses():
    # Phase 412: turn/tax_base.py apply_turn_revenue() now runs once per
    # turn, before apply_turn_maintenance() -- rulebook [9]'s own explicit
    # "si incassano le rendite, quindi si paga il mantenimento" ordering.
    # Same one-Legion-army expected debit (2 gold) as the Phase 404 test
    # above, plus a real 10-gold province tax base as the new credit.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].treasury = 50
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=HexCoord(0, 0), is_king=True))
    state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=10))

    p0 = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    leader = Leader(10, "A", ActionPlan(10, [PlanSegment(0, 1, (), {"P0": p0})]))

    run_turn([TurnLeader(leader, 1)], state, board_width=BOARD_WIDTH)

    assert state.kingdoms[1].treasury == 58


# -- Werebeast bite-transform, end-of-turn half (Phase 392) ---------------


def test_apply_werebeast_transformations_converts_a_queued_army_to_werebeasts():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=HexCoord(9, 9))
    state.add_army(army)
    state.werebeast_bitten_army_ids.add(101)

    _apply_werebeast_transformations(state)

    assert state.armies[101].army_type is ArmyType.WEREBEASTS
    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_transformations_silently_skips_an_army_that_no_longer_exists():
    state = GameState()
    state.werebeast_bitten_army_ids.add(999)  # already destroyed before this point

    _apply_werebeast_transformations(state)  # must not raise

    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_transformations_no_op_when_nothing_was_bitten():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=HexCoord(9, 9))
    state.add_army(army)

    _apply_werebeast_transformations(state)

    assert state.armies[101].army_type is ArmyType.LEGION


# -- Phase 573: the turn-boundary reset (movement_points/march-naval
# bonus flags/recruited_this_turn/turn_number) this project never had.


def test_replenish_turn_scoped_state_refills_movement_points_to_the_real_rate():
    state = _base_state()
    depleted = ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=0)
    state.add_army(depleted)

    _replenish_turn_scoped_state(state)

    assert state.armies[101].movement_points == ARMY_TABLE[ArmyType.HVY_CAVALRY].speed


def test_replenish_turn_scoped_state_clears_march_and_naval_bonus_flags():
    state = _base_state()
    army = ArmyState(
        101,
        1,
        ArmyType.HVY_CAVALRY,
        Quality.ELITE,
        ORIGIN,
        march_bonus_applied_this_turn=True,
        naval_bonus_applied_this_turn=True,
    )
    state.add_army(army)

    _replenish_turn_scoped_state(state)

    assert state.armies[101].march_bonus_applied_this_turn is False
    assert state.armies[101].naval_bonus_applied_this_turn is False


def test_replenish_turn_scoped_state_clears_recruited_this_turn():
    state = _base_state()
    state.provinces[ORIGIN].recruited_this_turn = {ArmyType.LEGION: 1}

    _replenish_turn_scoped_state(state)

    assert state.provinces[ORIGIN].recruited_this_turn == {}


def test_replenish_turn_scoped_state_clears_treasury_raid_attempts_this_turn():
    state = _base_state()
    state.kingdoms[2].treasury_raid_attempts_this_turn = 3

    _replenish_turn_scoped_state(state)

    assert state.kingdoms[2].treasury_raid_attempts_this_turn == 0


def test_replenish_turn_scoped_state_clears_unhireable_this_turn():
    state = _base_state()
    army = ArmyState(101, None, ArmyType.LEGION, Quality.AVERAGE, ORIGIN, unhireable_this_turn=True)
    state.add_army(army)

    _replenish_turn_scoped_state(state)

    assert state.armies[101].unhireable_this_turn is False


def test_replenish_turn_scoped_state_clears_oratory_boosted_this_turn():
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, oratory_boosted_this_turn=True))

    _replenish_turn_scoped_state(state)

    assert state.leaders[10].oratory_boosted_this_turn is False


def test_run_turn_replenishes_movement_points_at_the_end():
    # A real moderator running turn after turn via orchestrator.
    # process_turn() needs every army's movement pool back for the next
    # turn -- run_turn() itself, not just the private helper, must do
    # this (it's the one real per-turn boundary a caller ever sees).
    state = _base_state()
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, ORIGIN, movement_points=0))

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.armies[101].movement_points == ARMY_TABLE[ArmyType.HVY_CAVALRY].speed


def test_run_turn_increments_the_turn_number():
    state = _base_state()
    state.turn_number = 5

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.turn_number == 6


# -- Phase 575: action_casts_used, the fourth "never reset -- caller's
# job" field, missed by Phase 573's own audit and fixed here.


def test_replenish_turn_scoped_state_clears_action_casts_used():
    state = _base_state()
    state.action_casts_used[(10, Ability.WHITE)] = 3

    _replenish_turn_scoped_state(state)

    assert state.action_casts_used == {}


def test_run_turn_clears_action_casts_used_at_the_end():
    state = _base_state()
    state.action_casts_used[(10, Ability.WHITE)] = 3

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))

    assert state.action_casts_used == {}


# -- Phase 576: illusory_fog_active, found the same way action_casts_used
# was (re-auditing every remaining "not auto-cleared" field comment) --
# the rulebook's own text says Illusory Fog "dissipates at the end of the
# gameturn," but the flag it sets had no clearing site anywhere despite
# already having a real battle-strength consumer.


def test_replenish_turn_scoped_state_clears_illusory_fog_active():
    state = _base_state()
    state.provinces[ORIGIN].illusory_fog_active = True

    _replenish_turn_scoped_state(state)

    assert state.provinces[ORIGIN].illusory_fog_active is False


def test_run_turn_clears_illusory_fog_active_at_the_end():
    state = _base_state()
    state.provinces[ORIGIN].illusory_fog_active = True

    run_turn([], state, board_width=BOARD_WIDTH, rng=random.Random(1))


# -- Phase 674: _dispatch_mutual_encounter() picks up the non-initiator's
# own real Special Encounter Plan automatically, via execute_challenge()'s
# own eligibility check -- no code change was needed in turn_processor.py
# itself (Design point 6 of the Phase 674 plan); this proves that claim
# end to end rather than only by inspection.


def _leader_with_phase_and_sep(leader_id: int, name: str, label: str, phase: PlanPhase, sp: tuple) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(leader_id=leader_id, segments=[PlanSegment(0, 0, sp, {label: phase})]),
    )


def test_run_turn_mutual_encounter_lets_the_targets_own_special_encounter_plan_decide_the_winner():
    # Leader 10 (higher Melee skill) challenges leader 20; without any
    # Special Encounter Plan of its own, leader 20 has no leading Cast
    # to resolve and the ordinary Melee tactic proceeds -- the higher-
    # skilled challenger (10) wins, exactly like the pre-existing mutual-
    # Challenge test above. Giving leader 20 a real, decoded SP: CAST
    # tactic (SP: 0 <spell> -1) flips the outcome: its own leading cast
    # (mocked to a decisive "b", target-wins) resolves before the
    # challenger's Melee tactic is ever reached.
    state = _base_state()
    state.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9)))
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN, skills=_skills_with(Ability.MELEE, 0, 9)))
    challenge_phase_10 = _encounter_phase("P0", ActionCode.CHALLENGE, 20, melee=True)
    challenge_phase_20 = _encounter_phase("P0", ActionCode.CHALLENGE, 10, melee=True)
    leaders_no_sep = [
        _leader_with_phase_and_sep(10, "A", "P0", challenge_phase_10, ()),
        _leader_with_phase_and_sep(20, "B", "P0", challenge_phase_20, ()),
    ]

    no_sep_results = run_turn(
        [TurnLeader(leaders_no_sep[0], 1), TurnLeader(leaders_no_sep[1], 2)],
        state,
        board_width=BOARD_WIDTH,
        rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
    )

    by_leader_no_sep = {r.leader_id: r for r in no_sep_results}
    assert by_leader_no_sep[10].result.winner_leader_id == 10  # higher-skilled challenger wins, no SEP involved

    state2 = _base_state()
    state2.add_leader(LeaderState(10, kingdom_id=1, name="A", location=ORIGIN, skills=_skills_with(Ability.MELEE, 3, 9)))
    state2.add_leader(LeaderState(20, kingdom_id=2, name="B", location=ORIGIN, skills=_skills_with(Ability.MELEE, 0, 9)))
    leaders_with_sep = [
        _leader_with_phase_and_sep(10, "A", "P0", challenge_phase_10, ()),
        _leader_with_phase_and_sep(20, "B", "P0", challenge_phase_20, (0, Spell.FIREBALL.value, -1)),
    ]

    # The inner cast call plays target-as-caster: its own "a" (the inner
    # caster, i.e. the real target) winning flips to this function's
    # outer "b" -- see resolve_challenge_combat()'s own _resolve_target_
    # cast() flip convention (module docstring / Phase 674 addendum).
    with patch("ak_engine.turn.challenge_execution._resolve_personal_combat_cast", return_value="a"):
        with_sep_results = run_turn(
            [TurnLeader(leaders_with_sep[0], 1), TurnLeader(leaders_with_sep[1], 2)],
            state2,
            board_width=BOARD_WIDTH,
            rng=ScriptedRandom([0.1, 0.5, 0.9] * 15),
        )

    by_leader_with_sep = {r.leader_id: r for r in with_sep_results}
    assert state2.leaders[20].special_encounter_plan == (SearchTactic(Maneuver.CAST, Spell.FIREBALL.value),)
    assert by_leader_with_sep[10].result.winner_leader_id == 20  # target's own leading Cast decided it instead

    assert state.provinces[ORIGIN].illusory_fog_active is False
