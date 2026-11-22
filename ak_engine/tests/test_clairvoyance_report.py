"""The CLAIRVOYANCE REPORT section: after a successful Clairvoyance the caster's
Kingdom reads the target's turn from the cast onward; a target whose Kingdom owns
Dry Ice Fog only lets the large-scale facts through (project-original design,
user-specified 2026-11-22)."""

from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.plan import PlanPhase
from ak_engine.models.race import Race
from ak_engine.report.turn_report import compose_letter_report
from ak_engine.turn.battle_orchestrator import BattleReport
from ak_engine.turn.battle_resolution import BattleResult
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult
from ak_engine.turn.plan_dispatch import PhaseDispatchResult, dispatch_phase

BW = 10
HOME = HexCoord(3, 3)
NEIGHBOR = HexCoord(4, 3)
SECTION = "CLAIRVOYANCE REPORT"
ABILITY_NAMES = {ability: ability.name.title() for ability in Ability}


def _skills() -> SkillTable:
    raw = [0] * 31
    for ability in Ability:
        raw[ability.value * 2] = 2
        raw[ability.value * 2 + 1] = 9
    return SkillTable(raw)


def _world(*, fog: bool = False, target_kingdom: int = 2) -> GameState:
    state = GameState()
    state.board_width = BW
    state.board_height = 10
    state.add_kingdom(KingdomState(1, "Aland", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Bland", Race.HUMAN, Alignment.EVIL, HexCoord(8, 8)))
    if fog:
        state.kingdoms[2].discoveries.add(Discovery.DRY_ICE_FOG)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Home"))
    state.add_province(ProvinceState(NEIGHBOR, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, name="Border"))
    state.add_leader(LeaderState(1, 1, "Caster", HOME, is_king=True, skills=_skills()))
    state.add_leader(LeaderState(3, 2, "Bland King", HexCoord(8, 8), is_king=True, skills=_skills()))
    state.add_leader(LeaderState(2, target_kingdom, "Target", HOME, skills=_skills()))
    state.add_feature(Feature(feature_id=1, coord=HOME, kind=FeatureType.CAVE, guardian_monster=Monster.ARCHER))
    return state


def _cast(phase: str = "P0", *, caster: int = 1, target: int = 2) -> PhaseDispatchResult:
    result = CastExecutionResult(CastRequest(Spell.CLAIRVOYANCE, target=target), applied=True)
    return PhaseDispatchResult(caster, 0, phase, ActionCode.CAST, result, None)


def _act(state: GameState, results: list, label: str, action: ActionCode, obj: int = 0, extra=()) -> None:
    phase = PlanPhase(label=label, action=action, obj=obj, extra=list(extra))
    result = dispatch_phase(phase, state, 2, 2, board_width=BW, rng=random.Random(3))
    results.append(PhaseDispatchResult(2, 0, label, action, result, None))


def _section(state: GameState, results: list, *, kingdom_id: int = 1, pascal: bool = True) -> str:
    lines = compose_letter_report(
        results, state, kingdom_id, random.Random(1), ability_names=ABILITY_NAMES, board_width=BW, pascal_layout=pascal
    )
    text = "\n".join(lines)
    start = text.find(SECTION)
    if start < 0:
        return ""
    end = text.find("STATE OF THE NATION", start)
    return " ".join(text[start:end if end >= 0 else None].split())  # the layout wraps lines


def test_the_caster_reads_what_the_target_does_after_the_cast():
    state = _world()
    results = [_cast()]
    _act(state, results, "P1", ActionCode.EXPLORE)
    _act(state, results, "P2", ActionCode.PRACTICE, Ability.SAGE.value)

    section = _section(state, results)

    assert "through the Clairvoyance of Caster" in section
    assert "Target travelled about Home" in section  # the ordinary Explore narration
    assert "Cave" in section  # the discovery is told in full
    assert "Sage" in section  # and what was practiced


def test_what_the_target_did_before_the_cast_is_not_shown():
    state = _world()
    results: list = []
    _act(state, results, "P0", ActionCode.EXPLORE)
    results.append(_cast("P1"))
    _act(state, results, "P2", ActionCode.PRACTICE, Ability.SAGE.value)

    section = _section(state, results)

    assert "travelled" not in section
    assert "Sage" in section


def test_no_section_when_nobody_cast_clairvoyance():
    state = _world()
    results: list = []
    _act(state, results, "P1", ActionCode.EXPLORE)

    assert _section(state, results) == ""


def test_no_section_for_a_target_of_the_casters_own_kingdom():
    state = _world(target_kingdom=1)
    results = [_cast()]
    _act(state, results, "P1", ActionCode.EXPLORE)

    assert _section(state, results) == ""


def test_the_target_kingdom_does_not_get_the_section():
    state = _world()
    results = [_cast()]
    _act(state, results, "P1", ActionCode.EXPLORE)

    assert _section(state, results, kingdom_id=2) == ""


def test_a_second_cast_by_the_same_caster_ends_the_first_watch():
    state = _world()
    state.add_leader(LeaderState(4, 2, "Other", HOME, skills=_skills()))
    results = [_cast("P0", target=2)]
    _act(state, results, "P1", ActionCode.EXPLORE)
    results.append(_cast("P2", target=4))
    _act(state, results, "P3", ActionCode.PRACTICE, Ability.SAGE.value)  # Target, after the watch moved on

    section = _section(state, results)

    assert "Target travelled" in section
    assert "Nothing befell Target" not in section
    assert "Sage" not in section  # Target's later Practice is no longer watched
    assert "Nothing befell Other after the spell was cast." in section


def test_a_cast_with_nothing_after_it_says_so():
    state = _world()
    results = [_cast("P4")]

    assert "Nothing befell Target after the spell was cast." in _section(state, results)


def test_the_plain_layout_carries_the_section_too():
    state = _world()
    results = [_cast()]
    _act(state, results, "P1", ActionCode.EXPLORE)

    assert "Target travelled" in _section(state, results, pascal=False)


# -- Dry Ice Fog --


def test_fog_tells_that_the_target_explored_but_not_what_was_found():
    state = _world(fog=True)
    results = [_cast()]
    _act(state, results, "P1", ActionCode.EXPLORE)

    section = _section(state, results)

    assert "Target explored Home." in section
    assert "Cave" not in section and "Archer" not in section
    assert "fog of dry ice" in section


def test_fog_tells_that_the_target_practiced_but_not_what():
    state = _world(fog=True)
    results = [_cast()]
    _act(state, results, "P1", ActionCode.PRACTICE, Ability.SAGE.value)

    section = _section(state, results)

    assert "Target practiced." in section
    assert "Sage" not in section


def test_fog_tells_that_the_target_entered_a_feature_and_came_out_alive():
    state = _world(fog=True)
    results = [_cast()]
    _act(state, results, "P1", ActionCode.SEARCH, 1, [0, 9, -1])

    section = _section(state, results)

    assert "Target entered a feature in Home and came out alive." in section or (
        "Target entered a feature in Home and did not come out alive." in section
    )
    assert "Archer" not in section


def test_fog_tells_that_the_target_cast_a_spell_but_not_which_or_how_it_went():
    state = _world(fog=True)
    results = [_cast()]
    spell_cast = CastExecutionResult(CastRequest(Spell.BLESS, target=0), applied=True)
    results.append(PhaseDispatchResult(2, 0, "P1", ActionCode.CAST, spell_cast, None))

    section = _section(state, results)

    assert "Target cast a spell." in section
    assert "Bless" not in section


def test_fog_tells_that_the_target_pursued_or_trailed_someone_without_who_or_how_it_went():
    state = _world(fog=True)
    results = [_cast()]
    results.append(PhaseDispatchResult(2, 0, "P1", ActionCode.PURSUE, object(), None))
    results.append(PhaseDispatchResult(2, 0, "P2", ActionCode.TRAIL, object(), None))

    section = _section(state, results)

    assert "Target pursued someone." in section
    assert "Target trailed someone." in section


def test_fog_hides_spying_object_use_and_every_unlisted_order():
    state = _world(fog=True)
    results = [_cast()]
    for label, action in (
        ("P1", ActionCode.ASPY),
        ("P2", ActionCode.USE_MI),
        ("P3", ActionCode.RECRUIT),
        ("P4", ActionCode.HIRE),
    ):
        results.append(PhaseDispatchResult(2, 0, label, action, object(), None))

    section = _section(state, results)

    assert "Nothing befell Target after the spell was cast." in section


def test_fog_without_the_discovery_on_the_target_side_shows_everything():
    state = _world(fog=False)
    results = [_cast()]
    _act(state, results, "P1", ActionCode.EXPLORE)

    assert "fog of dry ice" not in _section(state, results)


def test_an_independent_target_is_never_fogged():
    state = _world(fog=True)
    state.leaders[2].kingdom_id = None
    state.leaders[2].race = Race.HUMAN
    results = [_cast()]
    _act(state, results, "P1", ActionCode.EXPLORE)

    section = _section(state, results)

    assert "fog of dry ice" not in section
    assert "Cave" in section


# -- Battles --


def _battle_entry(label: str = "P2") -> PhaseDispatchResult:
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"),
        conquered=False,
        province_coord=NEIGHBOR,
        attacker_kingdom_id=2,
        defender_kingdom_id=1,
        attacker_commander_leader_id=2,
        attacker_commanding_leader_ids=[2],
    )
    return PhaseDispatchResult(2, 0, label, None, report, None)


def test_fog_gives_only_the_result_of_a_battle_the_target_fought():
    state = _world(fog=True)
    results = [_cast(), _battle_entry()]

    section = _section(state, results)

    assert "A battle was fought at Border" in section
    assert "prevailed" in section
    assert "ATTACKING ARMY" not in section


def test_a_battle_the_target_did_not_fight_is_not_shown():
    state = _world(fog=True)
    entry = _battle_entry()
    entry.result.attacker_commander_leader_id = 3
    entry.result.attacker_commanding_leader_ids = [3]

    assert "battle" not in _section(state, [_cast(), entry])


# -- A whole turn through run_turn() --


def test_through_a_real_turn_only_what_follows_the_cast_is_shown():
    from ak_engine.models.leader import Leader
    from ak_engine.models.plan import ActionPlan, PlanSegment
    from ak_engine.turn.turn_processor import TurnLeader, run_turn

    state = _world()
    for ability in Ability:
        state.leaders[1].skills.set_pair_for_ability(ability, 9, 9)  # a sure cast
    caster_plan = {"P1": PlanPhase(label="P1", action=ActionCode.CAST, obj=Spell.CLAIRVOYANCE.value, extra=[2])}
    target_plan = {
        "P0": PlanPhase(label="P0", action=ActionCode.EXPLORE, obj=0, extra=[]),
        "P3": PlanPhase(label="P3", action=ActionCode.PRACTICE, obj=Ability.SAGE.value, extra=[]),
    }
    leaders = [
        TurnLeader(Leader(1, "Caster", ActionPlan(1, [PlanSegment(0, 0, (), caster_plan)])), 1),
        TurnLeader(Leader(2, "Target", ActionPlan(2, [PlanSegment(0, 0, (), target_plan)])), 2),
    ]

    results = run_turn(leaders, state, board_width=BW, rng=random.Random(5))
    cast = next(entry for entry in results if entry.leader_id == 1 and entry.phase_label == "P1")
    assert cast.result.applied is True  # the real spell fired

    section = _section(state, results)

    assert "Sage" in section  # P3, after the cast
    assert "travelled" not in section  # P0, before it


# -- A hero who leaves a Kingdom keeps his race (the CHARACTERS report needs it) --


def test_a_fired_hero_keeps_the_race_of_the_kingdom_he_served():
    from ak_engine.turn.plan_dispatch import _dispatch_fire

    state = _world()
    state.leaders[2].kingdom_id = 1
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=2, extra=[])

    result = _dispatch_fire(phase, state, 1)

    assert result.fired is True
    assert state.leaders[2].kingdom_id is None
    assert state.leaders[2].race is Race.HUMAN


def test_a_deserting_hero_keeps_his_race_and_the_characters_report_still_composes():
    from ak_engine.turn.expenses import apply_turn_maintenance

    state = _world()
    state.kingdoms[2].treasury = 0
    state.add_province(ProvinceState(HexCoord(8, 8), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, name="Far"))
    # No pay in the treasury and no liking for the King: the hero walks out.
    with __import__("unittest.mock").mock.patch("ak_engine.turn.expenses.hero_liking", return_value=-99):
        apply_turn_maintenance(state, random.Random(0))
    hero = state.leaders[2]
    assert hero.kingdom_id is None
    assert hero.race is Race.HUMAN

    lines = compose_letter_report([], state, 1, random.Random(1), board_width=BW, pascal_layout=True)

    assert any("CHARACTERS" in line for line in lines)


def test_without_fog_a_battle_the_target_fought_is_told_in_full():
    state = _world(fog=False)
    results = [_cast(), _battle_entry()]

    section = _section(state, results)

    assert "Nothing befell Target" not in section  # the battle fills the report
    assert "fog of dry ice" not in section
