from __future__ import annotations

import random
from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.army_list_decode import ArmyListRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.move_execution import MoveExecutionResult
from ak_engine.turn.plan_dispatch import (
    ArmyListExecutionResult,
    FireExecutionResult,
    HireExecutionResult,
    NoOpResult,
    UnsupportedActionError,
    dispatch_phase,
    run_leader_plan,
)
from ak_engine.turn.aspy_defend_decode import DefendRequest
from ak_engine.turn.aspy_execution import SpyReport
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult
from ak_engine.turn.challenge_execution import ChallengeExecutionResult
from ak_engine.turn.practice_execution import PracticeExecutionResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.recruit_execution import RecruitExecutionResult
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.trade_execution import TradeExecutionResult
from ak_engine.turn.trail_execution import TrailExecutionResult
from ak_engine.turn.use_mi_execution import UseMIExecutionResult

from _helpers import ScriptedRandom

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
BOARD_WIDTH = 10
LEADER_ID = 1


def _state_with_army(
    location: HexCoord, target_terrains: dict[HexCoord, Terrain], *, treasury: int = 100
) -> tuple[GameState, int]:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, location, treasury=treasury))
    state.add_province(ProvinceState(location, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    for coord, terrain in target_terrains.items():
        state.add_province(ProvinceState(coord, terrain, Race.HUMAN))
    # is_king=True: most tests using this helper predate Phase 40's
    # King-vs-Hero co-location enforcement and were never about testing
    # that restriction -- treating this shared leader as the King
    # preserves their original intent. Tests that specifically exercise
    # Hero co-location build their own LeaderState with is_king=False.
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", location, is_king=True))
    army_id = 1
    state.add_army(
        ArmyState(army_id, 1, ArmyType.BOWMEN, Quality.AVERAGE, location, movement_points=5, commanded_by=LEADER_ID)
    )
    return state, army_id


def test_dispatch_lmove_decodes_hex_number_and_moves():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)  # hex number 94, adjacent to origin on the odd-r grid
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert isinstance(result, MoveExecutionResult)
    assert result.moved is True
    assert state.armies[army_id].location == target
    assert state.leaders[LEADER_ID].location == target


def test_dispatch_lmove_derives_army_ids_from_leader_command():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.moved is True
    assert state.armies[army_id].location == target


def test_dispatch_lmove_leader_can_move_alone_without_triggering_battle():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {})
    state.add_province(ProvinceState(target, Terrain.PLAINS, Race.HUMAN))
    # An enemy army occupies the target, but the leader brings none of
    # their own -- rulebook [3.1]: combat only occurs if the mover has an army.
    state.add_army(ArmyState(99, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, target))
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert result.moved is True
    assert result.battle_report is None
    assert state.leaders[LEADER_ID].location == target
    assert state.armies[army_id].location == origin  # left behind, wasn't brought along


def test_dispatch_explore_uses_leader_location():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=1
    )

    assert result.new_percent == 100  # Plains(50) * (skill 1 + 1) = 100
    assert state.provinces[location].explored_percent == 100


def test_dispatch_explore_also_records_the_kingdoms_own_exploration():
    # Phase 69: alongside the pre-existing shared explored_percent scalar.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, explorer_skill=1
    )

    assert state.provinces[location].explored_percent_by_kingdom[1] == 100


def test_dispatch_explore_also_rolls_feature_discovery():
    # Phase 242: EXPLORE dispatch now also rolls discover_features() for
    # any feature already present in the province.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=1, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    # Plains(50) * (skill 1 + 1) = 100% -- guaranteed discovery.
    result = dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert feature.discovery_level(1) == 3
    # Phase 245: the dispatch result now surfaces which features were
    # just discovered, closing the "rolled but thrown away" gap so a
    # report layer can narrate them (describe_feature_discovery()).
    assert result.discovered_features == [feature]


def test_dispatch_explore_credits_chancellor_merit_when_first_to_discover():
    # Phase 256: nobody else has discovered this feature yet, so the
    # acting leader's own Chancellor Merit Point tally is credited.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=1, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert state.leaders[LEADER_ID].merit_tally.features_discovered_first == 1


def test_dispatch_explore_does_not_credit_merit_when_another_kingdom_already_found_it():
    # Phase 256: a rival kingdom's own entry already sits in
    # Feature.discovered_by_kingdom -- this kingdom wasn't first, so no
    # Merit Point credit, even though it does discover the feature too.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=1, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    feature.discovered_by_kingdom[2] = 3
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[])

    dispatch_phase(
        phase,
        state,
        kingdom_id=1,
        leader_id=LEADER_ID,
        army_ids=[army_id],
        board_width=BOARD_WIDTH,
        explorer_skill=1,
        rng=random.Random(0),
    )

    assert feature.discovery_level(1) == 3  # this kingdom did discover it...
    assert state.leaders[LEADER_ID].merit_tally.features_discovered_first == 0  # ...but wasn't first


def test_dispatch_lmove_also_rolls_rumor_generation_for_a_nearby_feature():
    # Phase 243: LMOVE is one of the 7 rumor-eligible order types (20%
    # chance). A feature 1 hex away from the mover's own pre-move
    # location is eligible (distance 0 -- the destination itself --
    # would just be found by Explore, not rumored about).
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)  # adjacent to origin
    nearby = HexCoord(2, 9)  # 1 hex from origin, distinct from target
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS, nearby: Terrain.PLAINS})
    feature = Feature(feature_id=1, coord=nearby, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    # trigger roll 0.0 < 0.20 -> succeeds; candidate choice index 0; content
    # roll (guardian-only feature) is skipped; is_true roll 0.0 -> True.
    rng = ScriptedRandom([0.0, 0.0], choice_indices=[0])
    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, rng=rng
    )

    assert len(state.rumors) == 1
    rumor = next(iter(state.rumors.values()))
    assert rumor.feature_id == feature.feature_id
    assert rumor.kingdom_id == 1


def test_dispatch_lmove_without_nearby_features_generates_no_rumor():
    origin = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, army_id = _state_with_army(origin, {target: Terrain.PLAINS})
    phase = PlanPhase(label="P0", action=ActionCode.LMOVE, obj=94, extra=[0])

    dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert state.rumors == {}


def test_dispatch_search_reports_feature_not_found():
    # Phase 132: SEARCH now actually executes -- with no feature 20
    # registered in GameState, execute_search() reports why rather than
    # merely decoding the request (see turn/search_execution.py).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 0, 11, 0, 22, 0, 7, 9, 13, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SearchExecutionResult)
    assert result.accepted is False
    assert result.reason == "feature not found"


def test_dispatch_search_stamps_the_request_onto_the_result():
    # Phase 213: same reasoning as test_dispatch_pursue_stamps_the_request_onto_the_result.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 0, 11, 0, 22, 0, 7, 9, 13, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.feature_id == 20


def test_dispatch_search_resolves_real_melee_combat_against_a_sourced_guardian():
    # A feature guarded by a Monster with real MONSTER_STATS + a Melee
    # tactic in the Encounter Plan resolves a real duel via turn/
    # encounter.py (Phase 132).
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_feature(Feature(feature_id=20, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 9, -1])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, SearchExecutionResult)
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner in ("leader", "monster")


def test_dispatch_search_leader_victory_marks_feature_looted():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    feature = Feature(feature_id=20, coord=location, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    # Give the leader a strong Melee skill so a low-variance rng favors them.
    state.leaders[LEADER_ID].skills = None
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 9, -1])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(1)
    )

    assert result.combat_resolved is True
    if result.winner == "leader":
        assert feature.looted is True
        assert LEADER_ID in state.leaders
    else:
        # Phase 259: this leader is a King (see _state_with_army's own
        # comment) -- a King's death installs a Royal Heir under the
        # same leader_id rather than leaving the Kingdom leaderless.
        assert LEADER_ID in state.dead_leaders
        assert state.leaders[LEADER_ID].is_royal_heir is True


def test_real_move_file_leader_search_phase_dispatches():
    # Leader 42 ("Garin") in AK3__T10.K1 has a real Search phase (P2):
    # "P2 : 2 20 0 0 11 0 22 0 7 9 13 -1" -> Search feature 20. No
    # feature 20 is registered in this bare test GameState (world
    # generation isn't modeled -- see models/feature.py), so execution
    # honestly reports it can't find the target.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T10.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 42)
    search_phase = leader.plan.segments[0].phases["P2"]
    assert search_phase.action == ActionCode.SEARCH

    state, army_id = _state_with_army(HexCoord(3, 9), {})

    result = dispatch_phase(search_phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SearchExecutionResult)
    assert result.accepted is False
    assert result.reason == "feature not found"


def test_dispatch_trade_reports_recipient_not_found():
    # Phase 133: TRADE now actually executes via execute_give() -- with
    # no leader 3 registered, it reports why rather than merely
    # decoding the request (see turn/trade_execution.py).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=42, extra=[0, 3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)
    assert result.applied is False
    assert result.reason == "recipient not found"


def test_dispatch_trade_gold_give_succeeds_between_two_co_located_kings():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {}, treasury=1000)
    recipient_id = 2
    state.add_kingdom(KingdomState(2, "Recipient", Race.HUMAN, Alignment.GOOD, location, treasury=0))
    state.add_leader(LeaderState(recipient_id, 2, "Recipient King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=100, extra=[0, recipient_id])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)
    assert result.applied is True
    assert result.gold_transferred == 100
    assert state.kingdoms[1].treasury == 900
    assert state.kingdoms[2].treasury == 100


def test_dispatch_trade_stamps_the_request_onto_the_result():
    # Phase 214: same reasoning as test_dispatch_pursue_stamps_the_request_onto_the_result.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {}, treasury=1000)
    recipient_id = 2
    state.add_kingdom(KingdomState(2, "Recipient", Race.HUMAN, Alignment.GOOD, location, treasury=0))
    state.add_leader(LeaderState(recipient_id, 2, "Recipient King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=100, extra=[0, recipient_id])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.target_leader_id == recipient_id


def test_dispatch_trade_self_targeted_secret_spell_ordinal_rewrites_to_cast():
    # Phase 397: DEF2.PAS's own Trade branch reclassifies a self-targeted
    # Give of a secret-spell ordinal (25-34) into a Cast -- see
    # turn/trade_decode.py's module docstring. Gate Angel is a
    # NO_TARGET_SPELLS member, so the rewrite's own forced target=0
    # doesn't get in its way here.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[LEADER_ID, 3])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, CastExecutionResult)
    assert result.request.spell == Spell.GATE_ANGEL
    assert result.request.target == 0


def test_dispatch_trade_self_targeted_secret_spell_zeroes_a_normally_targeted_spells_target():
    # Scar Terrain ordinarily needs a real province target -- the Trade->Cast
    # rewrite forces target=0 regardless (DEF2.PAS: lextra[m] := 0), so it
    # faithfully fails at execution rather than being "fixed" to keep working.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.SCAR_TERRAIN), extra=[LEADER_ID, 3])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, CastExecutionResult)
    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_dispatch_trade_ordinary_give_of_a_secret_spell_ordinal_is_not_rewritten():
    # Same obj range, but not self-targeted (extra[0] != leader_id) -- an
    # ordinary Give to leader 3 of "item/gold 25", not a Cast rewrite.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {}, treasury=1000)
    recipient_id = 3
    state.add_kingdom(KingdomState(2, "Recipient", Race.HUMAN, Alignment.GOOD, location, treasury=0))
    state.add_leader(LeaderState(recipient_id, 2, "Recipient King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[0, recipient_id])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)


def test_dispatch_trade_self_targeted_ordinary_gold_amount_is_not_rewritten():
    # Self-targeted, but obj (24) is below the secret-spell range -- an
    # ordinary (if unusual) self-Give, not a rewrite trigger.
    state, army_id = _state_with_army(HexCoord(3, 9), {}, treasury=1000)
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=24, extra=[LEADER_ID, LEADER_ID])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TradeExecutionResult)


def test_dispatch_practice_executes_and_mutates_leader_skills():
    # Phase 44: PRACTICE now actually executes (always resolved as solo
    # practice -- see turn/practice_execution.py's module docstring).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=14, extra=[0])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, PracticeExecutionResult)
    assert result.ability == Ability.SAGE
    assert result.not_implemented_for_ability is False
    # LEADER_ID had no skills recorded -- execute_practice attaches a
    # fresh all-zero SkillTable and rolls against it.
    assert state.leaders[LEADER_ID].skills is not None
    assert state.leaders[LEADER_ID].skills.pair_for_ability(Ability.SAGE) == (result.new_skill, result.new_aptitude)


def test_real_move_file_leader_practice_phase_dispatches():
    # Leader 1 (the King) in AK3__T1.K1 has real Practice phases (P0-P2):
    # "P0 : 12 6 0" -> Practice Necromancy.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)
    practice_phase = leader.plan.segments[0].phases["P0"]
    assert practice_phase.action == ActionCode.PRACTICE

    state, army_id = _state_with_army(HexCoord(3, 9), {})

    result = dispatch_phase(
        practice_phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=random.Random(0)
    )

    assert isinstance(result, PracticeExecutionResult)
    assert result.ability == Ability.NECROMANCY


def test_dispatch_wait_no_action_move_abort_are_bare_noops():
    state, army_id = _state_with_army(HexCoord(3, 9), {})

    for action in (ActionCode.WAIT, ActionCode.NO_ACTION, ActionCode.MOVE_ABORT):
        phase = PlanPhase(label="P0", action=action, obj=0, extra=[])

        result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

        assert result == NoOpResult(action=action)

    # Genuinely inert: nothing about the state changed.
    assert state.armies[army_id].location == HexCoord(3, 9)
    assert state.kingdoms[1].treasury == 100


def test_dispatch_cast_holy_symbol_is_not_executed():
    # Holy_Symbol is one of the ten Personal-Combat-only spells -- see
    # cast_execution.py's module docstring for why those have no
    # Action-Cast dispatch branch (unlike Hide_Feature/Clairvoyance,
    # which gained real execution in Phase 193).
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.CAST, obj=int(Spell.HOLY_SYMBOL), extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, CastExecutionResult)
    assert result.request.spell == Spell.HOLY_SYMBOL
    assert result.applied is False
    assert result.reason == "spell effect not modeled"


def test_dispatch_cast_charm_assigns_colocated_target_to_casters_kingdom():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(78, None, "Wandering Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.CAST, obj=12, extra=[78])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, CastExecutionResult)
    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_real_move_file_leader_cast_phase_dispatches():
    # Leader 1 (the King) in AK3__T10.K1 has a real Cast phase (P1):
    # "P1 : 9 12 78" -> Cast Charm targeting character 78.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T10.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)
    cast_phase = leader.plan.segments[0].phases["P1"]
    assert cast_phase.action == ActionCode.CAST

    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(78, None, "Wandering Hero", location))

    result = dispatch_phase(cast_phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, CastExecutionResult)
    assert result.request.spell == Spell.CHARM
    assert result.request.target == 78
    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_dispatch_use_mi_reports_an_unowned_item_id():
    # Phase 141: USE_MI now actually executes -- an item id nobody in
    # this GameState.items registry actually owns fails cleanly instead
    # of just handing back the raw decoded request.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=31, extra=[97])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, UseMIExecutionResult)
    assert result.applied is False
    assert result.reason == "item not found"


def test_dispatch_use_mi_reads_a_real_skill_book():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    item = state.add_item(Treasure.BOOK_MELEE, owner_leader_id=LEADER_ID)
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=item.item_id, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, UseMIExecutionResult)
    assert result.applied is True
    assert result.ability_boosted is Ability.MELEE
    assert item.item_id not in state.items


def test_dispatch_challenge_executes_and_reports_target_not_found():
    # Phase 54: CHALLENGE now dispatches to execute_challenge, not just
    # decode_challenge_phase -- target 88 doesn't exist in this fixture.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.CHALLENGE, obj=88, extra=[0, 9, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ChallengeExecutionResult)
    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_dispatch_challenge_executes_a_real_encounter_when_target_exists():
    # Challenger is an armyless Hero (not the shared King fixture leader),
    # so is_encounter_accepted's "Heroes... can always be Encountered by
    # other Heroes" branch applies deterministically (no rng consumed for
    # acceptance) -- only the resulting duel's winner is left to chance.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_kingdom(KingdomState(2, "Otheria", Race.HUMAN, Alignment.GOOD, HexCoord(3, 9)))
    state.add_leader(LeaderState(LEADER_ID, kingdom_id=1, name="Challenger", location=HexCoord(3, 9)))
    state.add_leader(LeaderState(88, kingdom_id=2, name="Target", location=HexCoord(3, 9)))
    phase = PlanPhase(label="P0", action=ActionCode.CHALLENGE, obj=88, extra=[0, 9, -1])  # tactic 9 = Melee

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ChallengeExecutionResult)
    assert result.accepted is True
    assert result.combat_occurred is True


def test_dispatch_pursue_executes_and_reports_target_not_found():
    # Phase 54: PURSUE now dispatches to execute_pursue, not just
    # decode_pursue_phase -- target 88 doesn't exist in this fixture.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=88, extra=[0, 9, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, PursueExecutionResult)
    assert result.caught_up is False
    assert result.reason == "pursuer or target not found"


def test_dispatch_pursue_stamps_the_request_onto_the_result():
    # Phase 213: report/turn_report.py describe_turn_results() needs the
    # target's own id to resolve a display name -- the dispatcher (not
    # execute_pursue() itself) stamps it.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=88, extra=[0, 9, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.target_character_id == 88


def test_dispatch_aspy_executes_and_reports_the_casters_own_province():
    # Phase 62: ASPY now dispatches to execute_aspy, not just
    # decode_aspy_phase -- the report is always for the caster's own
    # current province, per rulebook [3.14] ("a character may only Spy
    # on a province he is actually in"), regardless of the raw obj value.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, SpyReport)
    assert result.province == HexCoord(3, 9)
    assert result.owner_kingdom_id == 1
    assert result.is_capital is True


def test_dispatch_defend_is_decode_only():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DEFEND, obj=304, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, DefendRequest)
    assert result.target_province == 304


def test_dispatch_trail_executes_and_reports_target_not_found():
    # Phase 54: TRAIL now dispatches to execute_trail, not just
    # decode_trail_phase -- target 88 doesn't exist in this fixture.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, TrailExecutionResult)
    assert result.spied_on is False
    assert result.reason == "trailer or target not found"


def test_dispatch_trail_stamps_the_request_onto_the_result():
    # Phase 213: same reasoning as test_dispatch_pursue_stamps_the_request_onto_the_result.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request is not None
    assert result.request.target_character_id == 88


def test_dispatch_succ_trail_is_deliberately_unsupported():
    # ActionCode.SUCC_TRAIL is intentionally excluded from
    # SUPPORTED_ACTIONS -- see plan_dispatch.py's module docstring: no
    # writer, no assignment site anywhere in the available Pascal
    # source, no rulebook order, never observed in real data. This test
    # guards against a future edit silently "completing" it without
    # revisiting that reasoning.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.SUCC_TRAIL, obj=88, extra=[0])

    try:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)
        assert False, "expected UnsupportedActionError"
    except UnsupportedActionError:
        pass


def test_dispatch_recruit_executes_debits_treasury_and_creates_armies():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    # Real example from AK3__T1.K1 leader 72: recruit under leader 1,
    # two Bowmen (pay 2 each) and one Warg Riders (pay 3) = 7 gold.
    phase = PlanPhase(label="P3", action=ActionCode.RECRUIT, obj=1, extra=[0, 1, 1, 10, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert isinstance(result, RecruitExecutionResult)
    assert [u.army_type for u in result.recruited] == [ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.WARG_RIDERS]
    assert result.total_gold_spent == 7
    assert state.kingdoms[1].treasury == 93
    assert all(state.armies[u.army_id].commanded_by == 1 for u in result.recruited)
    assert all(state.armies[u.army_id].location == location for u in result.recruited)
    assert all(state.armies[u.army_id].quality == Quality.AVERAGE for u in result.recruited)


def test_dispatch_unsupported_action_raises():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.SUCC_TRAIL, obj=6, extra=[0])

    try:
        dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH)
        assert False, "expected UnsupportedActionError"
    except UnsupportedActionError:
        pass


def test_dispatch_leave_transfers_command_to_target_leader():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(2, 1, "Other Leader", HexCoord(3, 9)))
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[2, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ArmyListExecutionResult)
    assert result.succeeded == [army_id]
    assert state.armies[army_id].commanded_by == 2


def test_dispatch_leave_all_transfers_every_commanded_army_and_clears_to_garrison():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by is None


def test_dispatch_leave_in_allied_province_transfers_kingdom_ownership():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.provinces[HexCoord(3, 9)].owner_kingdom_id = 2  # an ally's province
    phase = PlanPhase(label="P3", action=ActionCode.LEAVE, obj=0, extra=[255, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id == 2


def test_dispatch_pick_up_attaches_colocated_army():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None  # unled, at the leader's location
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_pick_up_ignores_army_in_a_different_province():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.armies[army_id].location = HexCoord(9, 9)
    state.armies[army_id].commanded_by = None
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by is None


def test_dispatch_pick_up_all_only_attaches_unled_armies():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.armies[army_id].commanded_by = None
    state.add_leader(LeaderState(2, 1, "Other Leader", location))
    state.add_army(ArmyState(2, 1, ArmyType.AXEMEN, Quality.AVERAGE, location, commanded_by=2))
    phase = PlanPhase(label="P0", action=ActionCode.PICK_UP, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].commanded_by == LEADER_ID  # was unled -> picked up
    assert state.armies[2].commanded_by == 2  # already led by someone else -> untouched


def test_dispatch_disband_releases_army_into_mercenary_status():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, ArmyListExecutionResult)
    assert result.request.army_ids == [army_id]
    assert result.succeeded == [army_id]
    assert army_id in state.armies  # not removed -- still exists as an unowned mercenary
    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_disband_all_releases_every_commanded_army():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[255, 255, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_hire_assigns_independent_hero_and_debits_treasury():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, None, "Wandering Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, HireExecutionResult)
    assert result.hired is True
    assert state.leaders[32].kingdom_id == 1
    # Neither the Hero nor Testia's King has a recorded alignment/temper
    # (Phase 162's required_pay() default -- see turn/hire_pay.py), so
    # required pay is the cheapest bucket (1), not the raw 3-gold offer.
    assert state.kingdoms[1].treasury == 99
    assert result.minimum_gold == 1


def test_dispatch_hire_fails_when_hero_not_colocated():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, None, "Wandering Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "not co-located"
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_fails_when_hero_already_employed():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, 2, "Rival's Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "hero already in service"
    assert state.leaders[32].kingdom_id == 2  # untouched


def test_dispatch_hire_fails_on_insufficient_treasury():
    location = HexCoord(3, 9)
    # required_pay() defaults to 1 (no alignment/temper recorded on
    # either side, Phase 162) -- treasury must be below *that*, not
    # merely below the gold_offer, to genuinely exercise this path.
    state, army_id = _state_with_army(location, {}, treasury=0)
    state.add_leader(LeaderState(32, None, "Wandering Hero", location))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "insufficient treasury"
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 0  # untouched


# --- Hire's real required-pay formula (Phase 162) -------------------------


def test_dispatch_hire_refuses_a_hero_with_too_wide_an_alignment_gap():
    # Testia's King (_state_with_army) has no recorded alignment/temper,
    # so give him one explicitly here: GOOD vs the Hero's PAGAN is real
    # ordinal distance 3 -- "a Good King generally cannot hire a Pagan
    # Hero" (the user's own rulebook-quoted anchor case). Scripted rng
    # deliberately fails the Phase 264 "rare exception" roll (>= 0.15),
    # so this test still exercises the ordinary refusal path only.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.PAGAN))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[4])  # max legal offer

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.99])
    )

    assert result.hired is False
    assert result.reason == "alignment gap too wide"
    assert result.minimum_gold == 5
    assert result.rare_alignment_exception is False
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_rare_exception_succeeds_at_the_offer_ceiling():
    # Phase 264: same wide alignment gap, but the "rare exception" roll
    # (user-specified 15% chance) succeeds this time -- pay drops to the
    # Hire ceiling (4), and a max offer covers it.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.PAGAN))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[4])

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0])
    )

    assert result.hired is True
    assert result.minimum_gold == 4
    assert result.rare_alignment_exception is True
    assert state.leaders[32].kingdom_id == 1
    assert state.kingdoms[1].treasury == 96


def test_dispatch_hire_rare_exception_success_still_needs_the_offer_ceiling():
    # The bypass lowers the price to 4, not to nothing -- an offer below
    # that still isn't enough, even when the rare roll itself succeeds.
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.PAGAN))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])  # below the ceiling

    result = dispatch_phase(
        phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH, rng=ScriptedRandom([0.0])
    )

    assert result.hired is False
    assert result.reason == "offer below required pay"
    assert result.minimum_gold == 4
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_counter_offers_when_offer_is_below_required_pay():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    # DRUID is real ordinal distance 1 from GOOD -> required pay 2.
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.DRUID))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[1])  # below the required 2

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "offer below required pay"
    assert result.minimum_gold == 2
    assert state.leaders[32].kingdom_id is None
    assert state.kingdoms[1].treasury == 100  # untouched


def test_dispatch_hire_succeeds_and_charges_only_the_required_pay_not_the_offer():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.leaders[LEADER_ID].alignment = Alignment.GOOD
    state.add_leader(LeaderState(32, None, "Wandering Hero", location, alignment=Alignment.GOOD))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[4])  # offers more than required

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is True
    assert result.minimum_gold == 1
    assert state.leaders[32].kingdom_id == 1
    assert state.kingdoms[1].treasury == 99  # only the required 1, not the offered 4


def test_dispatch_fire_releases_hero_to_independent():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert isinstance(result, FireExecutionResult)
    assert result.request.hero_id == 32
    assert result.fired is True
    assert state.leaders[32].kingdom_id is None


def test_dispatch_fire_unknown_hero_id_reports_the_real_failure():
    # Phase 143: previously a silent no-op with no signal at all --
    # now an honest fired=False/reason.
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=999, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.request.hero_id == 999
    assert result.fired is False
    assert result.reason == "hero not found"


# --- King/Hero distinction (Phase 40) ------------------------------------


def test_dispatch_disband_by_a_hero_skips_a_noncolocated_army():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(50, 1, "A Hero", HexCoord(9, 9), is_king=False))  # not co-located with army_id
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=50, army_ids=[], board_width=BOARD_WIDTH)

    # Rulebook [3.6]: "A character can Disband an army only if he is in
    # the same province." -- left untouched, still owned and led.
    assert state.armies[army_id].kingdom_id == 1
    assert state.armies[army_id].commanded_by == LEADER_ID


def test_dispatch_disband_by_a_hero_succeeds_when_colocated():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(50, 1, "A Hero", location, is_king=False))
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=50, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_disband_by_a_king_bypasses_colocation():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(50, 1, "The King", HexCoord(9, 9), is_king=True))  # not co-located, but a King
    phase = PlanPhase(label="P0", action=ActionCode.DISBAND, obj=0, extra=[0, army_id, -1])

    dispatch_phase(phase, state, kingdom_id=1, leader_id=50, army_ids=[], board_width=BOARD_WIDTH)

    assert state.armies[army_id].kingdom_id is None
    assert state.armies[army_id].commanded_by is None


def test_dispatch_fire_by_a_hero_fails_when_not_colocated():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", HexCoord(9, 9)))
    state.add_leader(LeaderState(50, 1, "Acting Hero", HexCoord(1, 1), is_king=False))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=50, board_width=BOARD_WIDTH)

    # Rulebook [3.7]: "A character can Fire a Hero only if he is in the
    # same province." -- not co-located, so the Hero stays employed.
    assert result.fired is False
    assert result.reason == "not co-located"
    assert state.leaders[32].kingdom_id == 1


def test_dispatch_fire_by_a_hero_succeeds_when_colocated():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", location))
    state.add_leader(LeaderState(50, 1, "Acting Hero", location, is_king=False))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=50, board_width=BOARD_WIDTH)

    assert result.fired is True
    assert state.leaders[32].kingdom_id is None


def test_dispatch_fire_by_a_king_bypasses_colocation():
    state, army_id = _state_with_army(HexCoord(3, 9), {})
    state.add_leader(LeaderState(32, 1, "Employed Hero", HexCoord(9, 9)))
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=32, extra=[])

    # LEADER_ID (from _state_with_army) is a King, not co-located with 32.
    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)
    assert result.fired is True

    assert state.leaders[32].kingdom_id is None


def test_dispatch_hire_cannot_hire_a_king():
    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    # A King without a kingdom_id (e.g. deposed) -- proves this is a real,
    # explicit check, not just an accidental side effect of the
    # "already in service" check below it.
    state.add_leader(LeaderState(32, None, "A Rival King", location, is_king=True))
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    result = dispatch_phase(phase, state, kingdom_id=1, leader_id=LEADER_ID, board_width=BOARD_WIDTH)

    assert result.hired is False
    assert result.reason == "cannot hire a King"
    assert state.leaders[32].kingdom_id is None  # untouched
    assert state.kingdoms[1].treasury == 100  # untouched


def test_real_move_file_leader_hire_phase_dispatches():
    # Leader 18 ("Guerin") in AK3__T2.K1 has a real Hire phase (P1):
    # "P1 : 5 32 3" -> Hire hero 32, offer 3 gold.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T2.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    hire_phase = leader.plan.segments[0].phases["P1"]
    assert hire_phase.action == ActionCode.HIRE

    location = HexCoord(3, 9)
    state, army_id = _state_with_army(location, {})
    state.add_leader(LeaderState(18, 1, "Guerin", location))
    state.add_leader(LeaderState(32, None, "Wandering Hero", location))

    result = dispatch_phase(hire_phase, state, kingdom_id=1, leader_id=18, board_width=BOARD_WIDTH)

    assert isinstance(result, HireExecutionResult)
    assert result.hired is True
    assert state.leaders[32].kingdom_id == 1


def test_run_leader_plan_records_errors_and_continues():
    origin = HexCoord(3, 9)
    mid = HexCoord(4, 9)
    end = HexCoord(4, 10)
    state, army_id = _state_with_army(origin, {mid: Terrain.PLAINS, end: Terrain.PLAINS})

    leader = Leader(
        leader_id=LEADER_ID,
        name="Test Leader",
        plan=ActionPlan(
            leader_id=LEADER_ID,
            segments=[
                PlanSegment(
                    plan_start=0,
                    plan_end=4,
                    sp=(),
                    phases={
                        "P0": PlanPhase("P0", ActionCode.SUCC_TRAIL, 6, [0]),
                        "P1": PlanPhase("P1", ActionCode.SUCC_TRAIL, 6, [0]),
                        "P2": PlanPhase("P2", ActionCode.SUCC_TRAIL, 6, [0]),
                        "P3": PlanPhase("P3", ActionCode.LMOVE, 94, [0]),
                        "P4": PlanPhase("P4", ActionCode.LMOVE, 104, [0]),
                    },
                )
            ],
        ),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert [r.phase_label for r in results] == ["P0", "P1", "P2", "P3", "P4"]
    assert all(isinstance(r.error, UnsupportedActionError) for r in results[:3])
    assert results[3].error is None
    assert results[4].error is None
    assert state.armies[army_id].location == end


def test_real_move_file_leader_plan_dispatches_its_lmoves():
    # End-to-end: parse a real player move-submission file (Phase 1's
    # parser), take a leader with genuine LMOVE phases, and dispatch them
    # against a synthetic GameState built around the decoded coordinates.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)

    segment = leader.plan.segments[0]
    lmove_targets = [
        phase.obj for label in ("P0", "P1", "P2", "P3", "P4")
        if (phase := segment.phases.get(label)) is not None and phase.action == ActionCode.LMOVE
    ]
    assert lmove_targets, "expected leader 1 in AK3__T1.K1 to have at least one real LMOVE phase"

    from ak_engine.turn.hex_numbering import decode_hex_number

    coords = [decode_hex_number(obj, BOARD_WIDTH) for obj in lmove_targets]
    origin = HexCoord(coords[0].x - 1, coords[0].y)  # a starting point adjacent to the first target

    state, army_id = _state_with_army(origin, {c: Terrain.PLAINS for c in coords})

    results = run_leader_plan(leader, state, kingdom_id=1, army_ids=[army_id], board_width=BOARD_WIDTH)

    assert len(results) == 5  # P0-P4 all present in this fixture's first segment
    lmove_results = [r for r in results if r.action == ActionCode.LMOVE]
    assert lmove_results
    assert all(r.error is None for r in lmove_results)


def test_real_move_file_leader_recruit_phase_dispatches():
    # Leader 72 ("Teleko") in AK3__T1.K1 has a real Recruit phase (P3):
    # "P3 : 3 1 0 1 1 10 -1" -> recruit 2 Bowmen + 1 Warg Riders under leader 1.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 72)
    recruit_phase = leader.plan.segments[0].phases["P3"]
    assert recruit_phase.action == ActionCode.RECRUIT

    state, army_id = _state_with_army(HexCoord(3, 9), {})

    result = dispatch_phase(
        recruit_phase, state, kingdom_id=1, leader_id=LEADER_ID, army_ids=[army_id], board_width=BOARD_WIDTH
    )

    assert isinstance(result, RecruitExecutionResult)
    assert [u.army_type for u in result.recruited] == [ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.WARG_RIDERS]


def test_real_move_file_leader_leave_phase_dispatches():
    # Leader 18 ("Guerin") in AK3__T1.K1 has a real Leave phase (P3):
    # "P3 : 7 0 1 108 109 110 -1" -> leave armies 108/109/110 to leader 1.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    leave_phase = leader.plan.segments[0].phases["P3"]
    assert leave_phase.action == ActionCode.LEAVE

    state, army_id = _state_with_army(HexCoord(3, 9), {})
    for army_id_moved in (108, 109, 110):
        state.add_army(ArmyState(army_id_moved, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=18))
    state.add_leader(LeaderState(18, 1, "Guerin", HexCoord(3, 9)))

    result = dispatch_phase(leave_phase, state, kingdom_id=1, leader_id=18, army_ids=[], board_width=BOARD_WIDTH)

    assert isinstance(result, ArmyListExecutionResult)
    assert result.request.target_leader_id == 1
    assert result.request.army_ids == [108, 109, 110]
    assert result.succeeded == [108, 109, 110]
    assert all(state.armies[aid].commanded_by == 1 for aid in (108, 109, 110))


# --- Nested-plan dispatch (Phase 32) -------------------------------------


def test_successful_hire_dispatches_the_hired_characters_own_plan():
    location = HexCoord(3, 9)
    target = HexCoord(4, 9)
    state, _ = _state_with_army(location, {target: Terrain.PLAINS})
    state.add_leader(LeaderState(50, None, "Wandering Hero", location))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(plan_start=1, plan_end=1, sp=(), phases={"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Hirer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": hire_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    hirer_results = [r for r in results if r.leader_id == LEADER_ID]
    nested_results = [r for r in results if r.leader_id == 50]
    assert len(hirer_results) == 1
    assert hirer_results[0].result.hired is True
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P1"
    assert nested_results[0].error is None
    assert state.leaders[50].location == target


def test_failed_hire_does_not_dispatch_the_nested_plan():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    # Hero 50 already in another kingdom's service -> Hire fails.
    state.add_leader(LeaderState(50, 2, "Enemy's Hero", location))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Hirer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": hire_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1
    assert results[0].result.hired is False
    assert not any(r.leader_id == 50 for r in results)


def test_successful_charm_dispatches_the_charmed_characters_own_plan():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Wandering Hero", location))

    charm_phase = PlanPhase(
        label="P0",
        action=ActionCode.CAST,
        obj=int(Spell.CHARM),
        extra=[50],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.PRACTICE, 14, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Charmer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": charm_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    nested_results = [r for r in results if r.leader_id == 50]
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P1"
    assert nested_results[0].error is None
    assert isinstance(nested_results[0].result, PracticeExecutionResult)
    assert state.leaders[50].kingdom_id == 1


def test_resurrections_own_nested_plan_never_dispatches_without_a_dead_leader():
    # Resurrection has real embedded plans in sample data (see AK3__T6.K1)
    # and is executed as of Phase 59, but only for a target actually
    # archived in state.dead_leaders (see cast_execution.py). Here the
    # target is a plain, living LeaderState instead -- not what
    # Resurrection looks for -- so it still can't apply, and
    # _nested_plan_triggered still never fires.
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Would-be Revived", location))

    resurrection_phase = PlanPhase(
        label="P0",
        action=ActionCode.CAST,
        obj=int(Spell.RESURRECTION),
        extra=[50],
        nested_plan=ActionPlan(
            leader_id=50,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Necromancer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": resurrection_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1
    assert results[0].result.applied is False
    assert not any(r.leader_id == 50 for r in results)


def test_nested_plan_skipped_when_target_has_no_existing_leaderstate():
    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(50, None, "Wandering Hero", location))

    hire_phase = PlanPhase(
        label="P0",
        action=ActionCode.HIRE,
        obj=50,
        extra=[5],
        # A different character (999) is who the file says joined -- but
        # nothing in `state` ever created a LeaderState for them.
        nested_plan=ActionPlan(
            leader_id=999,
            segments=[PlanSegment(1, 1, (), {"P1": PlanPhase("P1", ActionCode.LMOVE, 94, [0])})],
        ),
    )
    leader = Leader(
        leader_id=LEADER_ID,
        name="Hirer",
        plan=ActionPlan(leader_id=LEADER_ID, segments=[PlanSegment(0, 0, (), {"P0": hire_phase})]),
    )

    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1  # no crash, no phantom nested results
    assert results[0].result.hired is True


def test_real_move_file_hire_dispatches_the_hired_heros_nested_lmove():
    # Leader 58 ("Elmer") in AK3__T5.K1 has a real Hire phase (P3):
    # "P3 : 5 38 4" -> Hire hero 38, offer 4 gold, with hero 38's own
    # nested plan embedded right after it: a single P4 LMOVE to hex 115.
    # Dispatched in isolation (not Elmer's whole real plan) so his own
    # earlier real LMOVE phases (which this synthetic state doesn't have
    # provinces for) can't move him away before the Hire phase runs.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T5.K1")
    real_leader = next(leader for leader in kingdom.leaders if leader.leader_id == 58)
    hire_phase = real_leader.plan.segments[0].phases["P3"]
    assert hire_phase.action == ActionCode.HIRE
    assert hire_phase.nested_plan.leader_id == 38

    from ak_engine.turn.hex_numbering import decode_hex_number

    target = decode_hex_number(hire_phase.nested_plan.segments[0].phases["P4"].obj, BOARD_WIDTH)
    origin = HexCoord(target.x - 1, target.y)  # adjacent starting point, same pattern as the LMOVE test above

    state, _ = _state_with_army(origin, {target: Terrain.PLAINS})
    state.add_leader(LeaderState(58, 1, "Elmer", origin))
    state.add_leader(LeaderState(38, None, "Wandering Hero", origin))

    leader = Leader(
        leader_id=58,
        name="Elmer",
        plan=ActionPlan(leader_id=58, segments=[PlanSegment(3, 3, (), {"P3": hire_phase})]),
    )
    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    nested_results = [r for r in results if r.leader_id == 38]
    assert len(nested_results) == 1
    assert nested_results[0].phase_label == "P4"
    assert nested_results[0].error is None
    assert state.leaders[38].location == target


def test_real_move_file_charm_dispatches_the_charmed_heros_nested_practice():
    # Leader 1 (the King) in AK3__T2.K1 has a real Cast phase (P2):
    # "P2 : 9 12 30" -> Cast Charm targeting character 30, whose own
    # nested plan (P3/P4 Practice) is embedded right after it. Dispatched
    # in isolation (not the King's whole real plan), same reason as the
    # Hire test above -- his own earlier real LMOVE phase would otherwise
    # move him off this synthetic state's single province.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T2.K1")
    real_leader = next(leader for leader in kingdom.leaders if leader.leader_id == 1)
    charm_phase = real_leader.plan.segments[0].phases["P2"]
    assert charm_phase.action == ActionCode.CAST
    assert charm_phase.nested_plan.leader_id == 30

    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(1, 1, "Uga-Buga Makumb", location))
    state.add_leader(LeaderState(30, None, "Wandering Hero", location))

    leader = Leader(
        leader_id=1,
        name="Uga-Buga Makumb",
        plan=ActionPlan(leader_id=1, segments=[PlanSegment(2, 2, (), {"P2": charm_phase})]),
    )
    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    nested_results = [r for r in results if r.leader_id == 30]
    assert [r.phase_label for r in nested_results] == ["P3", "P4"]
    assert all(r.error is None for r in nested_results)
    assert all(isinstance(r.result, PracticeExecutionResult) for r in nested_results)
    assert state.leaders[30].kingdom_id == 1


def test_real_move_file_resurrections_nested_plan_never_dispatches_without_a_dead_leader():
    # Leader 18 ("Guerin") in AK3__T6.K1 has a real Cast phase (P3):
    # "P3 : 9 0 22" -> Cast Resurrection targeting character 22, whose
    # own nested plan (a real P4 Recruit) is embedded right after it --
    # confirming Resurrection's nested plans are real data, not just a
    # theoretical case. As of Phase 59 Resurrection is executed, but only
    # for a target actually archived in state.dead_leaders -- see
    # cast_execution.py; a real successful revival's own nested-plan
    # dispatch is covered separately in test_cast_execution.py /
    # test_plan_dispatch.py's newer Resurrection tests.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T6.K1")
    real_leader = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    resurrection_phase = real_leader.plan.segments[0].phases["P3"]
    assert resurrection_phase.action == ActionCode.CAST
    assert resurrection_phase.nested_plan.leader_id == 22

    location = HexCoord(3, 9)
    state, _ = _state_with_army(location, {})
    state.add_leader(LeaderState(18, 1, "Guerin", location))
    # No LeaderState 22, and no state.dead_leaders[22] either -- nothing
    # for Resurrection to revive, so nested dispatch never gets that far.

    leader = Leader(
        leader_id=18,
        name="Guerin",
        plan=ActionPlan(leader_id=18, segments=[PlanSegment(3, 3, (), {"P3": resurrection_phase})]),
    )
    results = run_leader_plan(leader, state, kingdom_id=1, board_width=BOARD_WIDTH)

    assert len(results) == 1
    assert results[0].result.applied is False
    assert not any(r.leader_id == 22 for r in results)
