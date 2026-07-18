from __future__ import annotations

from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.report.turn_report import describe_turn_results
from ak_engine.turn.aspy_execution import SpyReport
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest
from ak_engine.turn.plan_dispatch import FireExecutionResult, HireExecutionResult, PhaseDispatchResult
from ak_engine.turn.practice_execution import PracticeExecutionResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.search_decode import SearchRequest
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.trade_execution import TradeExecutionResult
from ak_engine.turn.trail_decode import TrailRequest
from ak_engine.turn.trail_execution import TrailExecutionResult
from ak_engine.turn.use_mi_execution import UseMIExecutionResult

from tests._helpers import ScriptedRandom


def _state_with_leaders(*leaders: LeaderState) -> GameState:
    state = GameState()
    for leader in leaders:
        state.leaders[leader.leader_id] = leader
    return state


def _leader(leader_id: int, name: str) -> LeaderState:
    return LeaderState(leader_id=leader_id, kingdom_id=1, name=name, location=HexCoord(0, 0))


def test_describe_turn_results_renders_hire():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines == ["Aldric spoke to Borin and convinced Borin to pledge Borin's allegiance to Aldric."]


def test_describe_turn_results_renders_fire():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    result = FireExecutionResult(FireRequest(hero_id=32), fired=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.FIRE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert len(lines) == 1
    assert "Borin" in lines[0] and "Aldric" in lines[0]


def test_describe_turn_results_skips_hire_when_hireling_unknown():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = HireExecutionResult(HireRequest(hero_id=999, gold_offer=2), hired=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_cast_target_spell():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    result = CastExecutionResult(request=CastRequest(spell=Spell.KILL_ENEMY, target=2), applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == ["Aldric cast a Kill Enemy spell and Borin was magically killed by a dark Necromantic spell!"]


def test_describe_turn_results_skips_cast_for_province_targeted_spell():
    # EARTHQUAKE needs a province_name this function has no way to
    # auto-resolve (Phase 150's own confirmed province-naming gap).
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = CastExecutionResult(request=CastRequest(spell=Spell.EARTHQUAKE, target=1234), applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_use_mi_wand_target_spell():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    cast_result = CastExecutionResult(request=CastRequest(spell=Spell.KILL_ENEMY, target=2), applied=True)
    result = UseMIExecutionResult(applied=True, cast_result=cast_result)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.USE_MI, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == ["Aldric cast a Kill Enemy spell and Borin was magically killed by a dark Necromantic spell!"]


def test_describe_turn_results_skips_use_mi_skill_book():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = UseMIExecutionResult(applied=True, ability_boosted=Ability.MELEE)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.USE_MI, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_practice_with_supplied_ability_name():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = PracticeExecutionResult(ability=Ability.MELEE, skill_rose=False, new_skill=9)
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PRACTICE, result=result, error=None
        )
    ]

    lines = describe_turn_results(
        results, state, ScriptedRandom([]), ability_names={Ability.MELEE: "Melee"}
    )

    assert lines == ["Aldric practiced Melee even though Aldric had already reached the maximum skill level."]


def test_describe_turn_results_skips_practice_without_ability_names_map():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = PracticeExecutionResult(ability=Ability.MELEE, skill_rose=False, new_skill=9)
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PRACTICE, result=result, error=None
        )
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_trade_entirely():
    # Confirmed (not guessed): TradeExecutionResult still carries no
    # item-instance identity -- see describe_turn_results()'s own
    # Phase 213 note (PURSUE/TRAIL/SEARCH/ASPY are now wired below).
    state = _state_with_leaders(_leader(1, "Aldric"))
    results = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P1",
            action=ActionCode.TRADE,
            result=TradeExecutionResult(applied=True, gold_transferred=10),
            error=None,
        ),
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_pursue_without_a_request():
    # A direct execute_pursue() caller (every existing unit test
    # included) never gets .request stamped -- only plan_dispatch.py's
    # own _dispatch_pursue() does (Phase 213).
    state = _state_with_leaders(_leader(1, "Aldric"))
    results = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.PURSUE,
            result=PursueExecutionResult(caught_up=True),
            error=None,
        ),
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_pursue():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    state.provinces[HexCoord(0, 0)] = ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, name="Eldoria")
    result = PursueExecutionResult(
        caught_up=True, request=PursueRequest(target_character_id=2, unconfirmed_extra0=0)
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PURSUE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == ["Aldric caught up with Borin in Eldoria."]


def test_describe_turn_results_skips_pursue_when_target_unknown():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = PursueExecutionResult(
        caught_up=True, request=PursueRequest(target_character_id=999, unconfirmed_extra0=0)
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PURSUE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_trail_without_a_request():
    state = _state_with_leaders(_leader(1, "Aldric"))
    results = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.TRAIL,
            result=TrailExecutionResult(spied_on=True),
            error=None,
        ),
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_trail_catch_up_and_intelligence():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    state.provinces[HexCoord(0, 0)] = ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, name="Eldoria")
    result = TrailExecutionResult(
        spied_on=True, request=TrailRequest(target_character_id=2, unconfirmed_extra0=0)
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.TRAIL, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 20))

    assert lines[0] == "Aldric caught up with Borin in Eldoria."
    assert "Aldric learned that Borin owns no treasures." in lines
    assert "Aldric learned that Borin leads no armies." in lines


def test_describe_turn_results_skips_search_without_a_request():
    state = _state_with_leaders(_leader(1, "Aldric"))
    results = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.SEARCH,
            result=SearchExecutionResult(accepted=True),
            error=None,
        ),
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_search():
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_feature(Feature(feature_id=5, coord=HexCoord(3, 4), kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    result = SearchExecutionResult(accepted=True, request=SearchRequest(feature_id=5, unconfirmed_extra0=0))
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.SEARCH, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert len(lines) == 1
    assert "Aldric" in lines[0]
    assert "(3, 4)" in lines[0]


def test_describe_turn_results_renders_aspy():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.ASPY, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 20, choice_indices=[0]))

    assert len(lines) >= 2  # at least the opening + closing sentences
    assert "Aldric" in lines[0]


def test_describe_turn_results_skips_entries_with_an_error():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    results = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.HIRE,
            result=HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=True),
            error=ValueError("boom"),
        )
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_entries_for_unknown_leader():
    state = GameState()
    results = [
        PhaseDispatchResult(
            leader_id=999,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.HIRE,
            result=HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=True),
            error=None,
        )
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []
