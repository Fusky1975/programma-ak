from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.item import ItemInstance
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.rumor import Rumor, RumorContent
from ak_engine.models.treasure import TREASURE_NAME, Treasure
from ak_engine.report.turn_report import describe_turn_results
from ak_engine.turn.assassin_guild import GrandfatherOfAssassinsAttemptResult, GuildAssassinationOutcome
from ak_engine.turn.aspy_execution import SpyReport
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult
from ak_engine.turn.challenge_execution import ChallengeExecutionResult
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest, PursueRequest
from ak_engine.turn.encounter import FireArrowShot, MeleeSwing
from ak_engine.turn.exploration import ExploreResult
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest
from ak_engine.turn.aspy_defend_decode import DefendRequest
from ak_engine.turn.defend_execution import DefendReinforcement
from ak_engine.turn.move_execution import MoveExecutionResult
from ak_engine.turn.plan_dispatch import ArmyListExecutionResult, FireExecutionResult, HireExecutionResult, PhaseDispatchResult
from ak_engine.turn.practice_execution import PracticeExecutionResult
from ak_engine.turn.combat import Quality
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.recruit_execution import RecruitedUnit, RecruitExecutionResult
from ak_engine.turn.search_decode import SearchRequest
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.trade_decode import TradeRequest
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


# -- Grandfather of Assassins (Phase 614) ------------------------------------


def test_describe_turn_results_renders_fire_queued_as_guild_assassination_order():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    result = FireExecutionResult(FireRequest(hero_id=32), fired=False, guild_assassination_queued=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.FIRE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines == ["Aldric ordered the assassination of Borin."]


def test_describe_turn_results_renders_guild_assassination_already_dead():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    outcome = GuildAssassinationOutcome(target_leader_id=32, already_dead=True, attempt=None)
    results = [
        PhaseDispatchResult(
            leader_id=32, segment_index=-1, phase_label="guild-assassination", action=None, result=outcome, error=None
        )
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == ["Borin could not be assassinated because Borin was dead and buried."]


def test_describe_turn_results_renders_guild_assassination_success():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    attempt = GrandfatherOfAssassinsAttemptResult(
        titleholder_leader_id=1, target_leader_id=32, success_chance=0.5, succeeded=True
    )
    outcome = GuildAssassinationOutcome(target_leader_id=32, already_dead=False, attempt=attempt)
    results = [
        PhaseDispatchResult(
            leader_id=32, segment_index=-1, phase_label="guild-assassination", action=None, result=outcome, error=None
        )
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0, 0]))

    assert lines == [
        "While Borin was out for a stroll, suddenly an assassin launched himself at Borin!",
        "Borin was wounded by a poisoned dagger!Cursed be the Assassin's Guild and whoever heads it!",
    ]


def test_describe_turn_results_renders_guild_assassination_failure():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    attempt = GrandfatherOfAssassinsAttemptResult(
        titleholder_leader_id=1, target_leader_id=32, success_chance=0.5, succeeded=False
    )
    outcome = GuildAssassinationOutcome(target_leader_id=32, already_dead=False, attempt=attempt)
    results = [
        PhaseDispatchResult(
            leader_id=32, segment_index=-1, phase_label="guild-assassination", action=None, result=outcome, error=None
        )
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0, 0]))

    assert lines == [
        "While Borin was out for a stroll, suddenly an assassin launched himself at Borin!",
        "Fortunately, Borin survived the attempt and the assassin (apparently, a member of the "
        "Assassin's Guild) was killed.Of course, the guard in Borin's kingdom was doubled.",
    ]


def test_describe_turn_results_renders_nothing_when_the_title_is_vacant_at_resolution():
    # attempt is None only when Office.ASSASSIN itself became vacant
    # between the FI interception and phase-5 resolution -- no sourced
    # text covers it, so nothing is narrated (not a dangling _ASeek).
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(32, "Borin"))
    outcome = GuildAssassinationOutcome(target_leader_id=32, already_dead=False, attempt=None)
    results = [
        PhaseDispatchResult(
            leader_id=32, segment_index=-1, phase_label="guild-assassination", action=None, result=outcome, error=None
        )
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


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


def test_describe_turn_results_narrates_kill_enemy_berserk_retaliation_even_when_the_caster_dies():
    # Phase 612: describe_cast() itself returns None for every branch of
    # this outcome (applied stays False), and -- before this same
    # phase's _leader_name() fix -- the caster's own death (state.
    # remove_leader() already ran by the time this composer runs) made
    # caster_name resolve to None too, silently dropping the WHOLE
    # entry. Both are exercised together here: state.remove_leader(1)
    # simulates exactly what execute_cast() already did to state by the
    # time a real turn report gets composed.
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    state.remove_leader(1)
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=2),
        applied=False,
        reason="spell failed",
        kill_enemy_berserk_winner="b",
        melee_swings=(MeleeSwing(attacker="b", hit=False, damage=0),),
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0]))

    assert lines == [
        "Borin went berserk over the Kill-Enemy attempt.Guided by eerily accurate psychotic visions, "
        "Borin assailed Aldric and missed.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
    ]


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


def test_describe_turn_results_renders_recruit():
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_province(
        ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor")
    )
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=None))
    result = RecruitExecutionResult(
        request=None, recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=2)]
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.RECRUIT, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert lines == [
        "Aldric recruited Bowmen from among the people of Numenor, to serve under "
        "the provincial garrison commander."
    ]


def test_describe_turn_results_skips_recruit_when_leader_has_no_province():
    # _state_with_leaders() never registers a province at the leader's
    # own location -- the RECRUIT branch should skip cleanly, not crash.
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = RecruitExecutionResult(
        request=None, recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=2)]
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.RECRUIT, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_leave():
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_province(
        ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor")
    )
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=None))
    result = ArmyListExecutionResult(request=None, succeeded=[100])
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.LEAVE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([], choice_indices=[0]))

    assert lines == ["Aldric left Bowmen with the provincial garrison commander in Numenor."]


def test_describe_turn_results_renders_pick_up():
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_province(
        ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor")
    )
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=1))
    result = ArmyListExecutionResult(request=None, succeeded=[100])
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.PICK_UP, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([], choice_indices=[0]))

    assert lines == ["Aldric picked up Bowmen in Numenor."]


def test_describe_turn_results_renders_disband():
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_army(ArmyState(100, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=None))
    result = ArmyListExecutionResult(request=None, succeeded=[100])
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.DISBAND, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == ["Aldric disbanded Bowmen."]


def test_describe_turn_results_renders_defend():
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_province(
        ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor")
    )
    result = DefendRequest(target_province=0, unconfirmed_extra0=0)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.DEFEND, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == ["Aldric prepared Aldric's armies to defend Numenor and the surrounding provinces."]


def test_describe_turn_results_renders_defend_reinforcement():
    # Phase 422: a sentinel PhaseDispatchResult (action=None, segment_index=-1),
    # same convention as the "gate-angel-visit"/"forced-rebattle" sentinels --
    # matched by isinstance(entry.result, DefendReinforcement), not by action.
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.add_province(ProvinceState(HexCoord(1, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Gondor"))
    result = DefendReinforcement(origin=HexCoord(0, 0), target=HexCoord(1, 0))
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=-1, phase_label="defend-reinforcement", action=None, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.0, 0.0]))

    # Phase 769: _LHearInv (learning of the attack) + _LCMarch (the
    # actual march-in to defend), both real sentences for this one
    # atomic reinforcement event.
    assert lines == [
        "Aldric, responsible for the defense of Numenor, learned of an enemy attack on Gondor.",
        "Aldric marched into Gondor from Numenor to defend Gondor against its would-be conquerors.",
    ]


def test_describe_turn_results_renders_move():
    state = _state_with_leaders(_leader(1, "Aldric"))
    state.add_province(
        ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor")
    )
    result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1, new_location=HexCoord(3, 9)
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.LMOVE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1, 0.1], choice_indices=[0]), board_width=20)

    assert lines == ["Aldric marched on Numenor 183 with Aldric's command."]


def test_describe_turn_results_skips_move_without_board_width():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1, new_location=HexCoord(0, 0)
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.LMOVE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_trade_without_a_request():
    # A direct execute_give() caller (every existing unit test
    # included) never gets .request stamped -- only plan_dispatch.py's
    # own _dispatch_trade() does (Phase 214).
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


def test_describe_turn_results_renders_trade_gold_give():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    result = TradeExecutionResult(
        applied=True, gold_transferred=10, request=TradeRequest(obj=10, target_leader_id=2, extra=[0, 2])
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.TRADE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10))

    assert lines == ["Aldric gave to Borin 10 gold from Aldric's treasury."]


def test_describe_turn_results_renders_trade_item_give():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    item = ItemInstance(item_id=7, treasure=Treasure.WAND_FIREBALL, owner_leader_id=2)
    result = TradeExecutionResult(
        applied=True, item_transferred=True, item=item, request=TradeRequest(obj=7, target_leader_id=2, extra=[0, 2])
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.TRADE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == [f"Aldric gave the {TREASURE_NAME[Treasure.WAND_FIREBALL]} to Borin."]


def test_describe_turn_results_skips_trade_when_recipient_unknown():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = TradeExecutionResult(
        applied=True, gold_transferred=10, request=TradeRequest(obj=10, target_leader_id=999, extra=[0, 999])
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P1", action=ActionCode.TRADE, result=result, error=None)
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


def test_describe_turn_results_renders_pursue_combat_after_the_catch_up_sentence():
    # Phase 417: the armyless personal-duel case's own combat now gets
    # narrated too, right after the pre-existing _LCatch sentence.
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    state.provinces[HexCoord(0, 0)] = ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, name="Eldoria")
    result = PursueExecutionResult(
        caught_up=True,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=4),),
        request=PursueRequest(target_character_id=2, unconfirmed_extra0=0),
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PURSUE, result=result, error=None)
    ]

    # Phase 611: HORDEATH.X's own generic closing beat now follows the
    # mortal-wound sentence.
    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 30, choice_indices=[8, 0, 0, 0]))

    assert lines == [
        "Aldric caught up with Borin in Eldoria.",
        "Aldric Attacked Borin and inflicted 4 damage points.",
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
    ]


def test_describe_turn_results_renders_challenge_combat():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=5),),
        request=ChallengeRequest(target_character_id=2, unconfirmed_extra0=0),
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CHALLENGE, result=result, error=None)
    ]

    # Phase 793: one more choice_indices entry for the new, unconditional
    # ENCATT.X opening line.
    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0]))

    assert lines == [
        "Aldric searched throughout (0, 0) for Borin.",
        "Aldric Fired an arrow at Borin and inflicted 5 damage points.",
    ]


def test_describe_turn_results_narrates_challenge_even_when_the_challenger_dies_in_it():
    # Phase 612: before the _leader_name()/_leader_location() dead-
    # leaders fallback, a challenger who lost and died in their own
    # Challenge got ZERO narration -- caster_name resolved to None at
    # the very top of the loop (entry.leader_id already popped from
    # state.leaders by state.remove_leader(), same timing as a real
    # end-to-end run: run_turn() fully mutates state before any
    # narration composer runs), so this whole entry was silently
    # skipped, even the real swings that happened before the death.
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    state.remove_leader(1)
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=2,
        loser_leader_id=1,
        loser_killed=True,
        melee_swings=(MeleeSwing(attacker="b", hit=True, damage=6),),
        request=ChallengeRequest(target_character_id=2, unconfirmed_extra0=0),
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CHALLENGE, result=result, error=None)
    ]

    # Phase 793: one more choice_indices entry for the new, unconditional
    # ENCATT.X opening line.
    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0, 0]))

    assert lines == [
        "Aldric searched throughout (0, 0) for Borin.",
        "Borin assailed Aldric and inflicted 6 damage points.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
    ]


def test_describe_turn_results_skips_challenge_without_a_request():
    # A direct execute_challenge() caller (every existing unit test
    # included) never gets .request stamped -- only plan_dispatch.py's
    # own _dispatch_challenge() does (Phase 417).
    state = _state_with_leaders(_leader(1, "Aldric"))
    results = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.CHALLENGE,
            result=ChallengeExecutionResult(accepted=True, combat_occurred=False),
            error=None,
        ),
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_challenge_when_target_unknown():
    state = _state_with_leaders(_leader(1, "Aldric"))
    result = ChallengeExecutionResult(
        accepted=True, combat_occurred=True, request=ChallengeRequest(target_character_id=999, unconfirmed_extra0=0)
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CHALLENGE, result=result, error=None)
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
    # Phase 400: describe_aspy() now resolves owner_kingdom_id into a real
    # display name (_diplomacy_entry()), so a report claiming ownership by
    # kingdom 1 needs that kingdom to actually be registered.
    state.kingdoms[1] = KingdomState(
        kingdom_id=1, name="Testia", race=Race.HUMAN, alignment=Alignment.GOOD, home_province=HexCoord(0, 0)
    )
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


# -- Phase 247: EXPLORE discovery + rumor narration --


def test_describe_turn_results_renders_explore_discovered_features():
    state = _state_with_leaders(_leader(1, "Aldric"))
    feature = Feature(feature_id=5, coord=HexCoord(3, 4), kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    result = ExploreResult(new_percent=100, delta_applied=50, fully_explored=True, discovered_features=[feature])
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    # Phase 613: MONSTERS.X2's own flavor text for the guardian now
    # follows FINDFEAT.X's own discovery sentence as its own line.
    assert len(lines) == 2
    assert "Aldric" in lines[0]
    assert "(3, 4)" in lines[0]
    assert "Gargoyle" in lines[1]


def test_describe_turn_results_omits_rumors_without_board_width():
    state = _state_with_leaders(_leader(1, "Aldric"))
    feature = Feature(feature_id=5, coord=HexCoord(3, 4), kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    rumor = Rumor(
        rumor_id=state.new_rumor_id(),
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=5,
        is_true=True,
        described_coord=HexCoord(3, 4),
        described_monster=Monster.GARGOYLE,
    )
    state.add_rumor(rumor)
    result = ExploreResult(new_percent=50, delta_applied=50, fully_explored=False)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_renders_rumors_when_board_width_given():
    state = _state_with_leaders(_leader(1, "Aldric"))
    feature = Feature(feature_id=5, coord=HexCoord(3, 4), kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    rumor = Rumor(
        rumor_id=state.new_rumor_id(),
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=5,
        is_true=True,
        described_coord=HexCoord(3, 4),
        described_monster=Monster.GARGOYLE,
    )
    state.add_rumor(rumor)
    result = ExploreResult(new_percent=50, delta_applied=50, fully_explored=False)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0]), board_width=10)

    assert len(lines) == 1
    assert "Aldric" in lines[0]


def test_describe_turn_results_only_narrates_rumors_heard_by_that_leader():
    state = _state_with_leaders(_leader(1, "Aldric"), _leader(2, "Borin"))
    feature = Feature(feature_id=5, coord=HexCoord(3, 4), kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    rumor = Rumor(
        rumor_id=state.new_rumor_id(),
        kingdom_id=1,
        leader_id=2,  # Borin heard it, not Aldric
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=5,
        is_true=True,
        described_coord=HexCoord(3, 4),
        described_monster=Monster.GARGOYLE,
    )
    state.add_rumor(rumor)
    result = ExploreResult(new_percent=50, delta_applied=50, fully_explored=False)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=result, error=None)
    ]

    lines = describe_turn_results(results, state, ScriptedRandom([0.1] * 10, choice_indices=[0]), board_width=10)

    assert lines == []
