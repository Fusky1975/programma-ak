from __future__ import annotations

import random
from unittest.mock import ANY, patch

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.challenge_execution import ChallengeCombatOutcome
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.encounter import EncounterCombatResult, MeleeRoundOutcome, MeleeSwing, ReactiveMeleeSwingResult
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


def test_leader_combatant_gives_the_imperial_defender_a_damage_reduction_of_one():
    # Phase 489: CARICHE E ABLITA.txt's own Office.DEFENDER perk ("reduce
    # any strike against you in personal combat ... by one damage point").
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD)
    leader.merit_tally.monster_hp_defeated = 1  # meets OFFICE_MIN_POINTS[Office.DEFENDER]
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.damage_reduction == 1


def test_leader_combatant_reads_the_melee_hit_points_advanced_ability():
    # Phase 516: AdvancedAbility.MELEE_HIT_POINTS.
    state = _base_state()
    leader = LeaderState(
        1, kingdom_id=1, name="Chaser", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_HIT_POINTS}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.has_melee_hit_points_ability is True


def test_leader_combatant_reads_melee_mastery():
    # Phase 517: AdvancedAbility.MELEE_MASTERY/MELEE_TRUE_MASTERY.
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_MASTERY})
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.10)
    assert combatant.melee_damage_dealt_bonus == 1


def test_leader_combatant_reads_melee_true_mastery():
    state = _base_state()
    leader = LeaderState(
        1, kingdom_id=1, name="Chaser", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_TRUE_MASTERY}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == 1.0
    assert combatant.melee_damage_dealt_bonus == 2


def test_leader_combatant_reads_duellists_medal_and_kingdom_race_humanoid():
    # Phase 518: AdvancedAbility.MELEE_DUELLISTS_MEDAL + is_humanoid.
    state = _base_state()
    leader = LeaderState(
        1, kingdom_id=1, name="Chaser", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_DUELLISTS_MEDAL}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.has_duellists_medal_ability is True
    assert combatant.is_humanoid is True


def test_leader_combatant_reads_control_temper_ability():
    # Phase 519: AdvancedAbility.MELEE_CONTROL_TEMPER.
    state = _base_state()
    leader = LeaderState(
        1, kingdom_id=1, name="Chaser", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_CONTROL_TEMPER}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.has_control_temper_ability is True


def test_leader_combatant_reads_archery_free_attack_bonus():
    # Phase 520: AdvancedAbility.ARCHERY_FREE_ATTACK/_MASTERY/_TRUE_MASTERY.
    state = _base_state()
    leader = LeaderState(
        1, kingdom_id=1, name="Chaser", location=FIELD, advanced_abilities={AdvancedAbility.ARCHERY_FREE_ATTACK}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.archery_free_attack_bonus == 1


def test_leader_combatant_reads_equipped_weapon_hit_and_damage_bonus():
    # Phase 684: this project's own Phase 535 weapon-bonus wiring never
    # reached this builder until now.
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_3, owner_leader_id=1)  # Flaming Scimitar: +20%/+3

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.20)
    assert combatant.melee_damage_dealt_bonus == 3
    assert combatant.equipped_weapon is Treasure.WEAPON_3


def test_leader_combatant_composes_weapon_bonus_with_melee_mastery():
    state = _base_state()
    leader = LeaderState(
        1, kingdom_id=1, name="Chaser", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_MASTERY}
    )
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_3, owner_leader_id=1)

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.10 * 1.20)
    assert combatant.melee_damage_dealt_bonus == 1 + 3


def test_leader_combatant_reads_bow_of_the_elven_kings_archery_bonus():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=1)

    combatant = _leader_combatant(leader, state)

    assert combatant.archery_hit_multiplier == pytest.approx(1.25)
    assert combatant.missile_damage_dealt_bonus == 2


def test_leader_combatant_reads_holy_sword_auto_protection():
    # Phase 536: AKGEN_reverse_engineering_report (4).md SS7.3.
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)

    combatant = _leader_combatant(leader, state)

    assert combatant.defensive_hit_multiplier == pytest.approx(0.6)
    assert combatant.is_invisible is False
    assert combatant.equipped_weapon is Treasure.WEAPON_1


def test_leader_combatant_reads_invisible_sword_auto_invisibility():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_5, owner_leader_id=1)

    combatant = _leader_combatant(leader, state)

    assert combatant.is_invisible is True
    assert combatant.defensive_hit_multiplier == pytest.approx(0.5)


def test_leader_combatant_equipped_weapon_field_is_none_with_no_weapon():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.equipped_weapon is None
    assert combatant.offensive_hit_multiplier == 1.0
    assert combatant.melee_damage_dealt_bonus == 0


def test_leader_combatant_reads_undead_alignment_as_undead_or_anti_holy():
    # Phase 682/684: SS7.1's Holy Sword vs-Undead bonus needs the
    # combatant's own nature, set independently of any weapon.
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD, alignment=Alignment.UNDEAD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.is_undead_or_anti_holy is True


def test_leader_combatant_reads_non_undead_alignment_as_not_undead_or_anti_holy():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Chaser", location=FIELD, alignment=Alignment.GOOD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.is_undead_or_anti_holy is False


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
    # (any value < 1.0 succeeds against it) -- [0] catch-up roll, [1:] the
    # peaceful request bypasses acceptance/combat entirely, so the only
    # further draws are Add_Experience's own gain rolls.
    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.99, 0.5, 0.5]))

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

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.caught_up is True


def test_execute_pursue_uses_pursuers_real_spy_skill():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD, skills=_skills_with(Ability.SPY, 4, 9))
    )
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=HexCoord(3, 1)))  # distance 2

    # Level-4 Spy skill gives a 250% base chance; /2 distance = 125% -> capped at
    # 100%, so even a near-1.0 roll still catches up.
    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.99, 0.5, 0.5]))

    assert result.caught_up is True


# -- armyless combat resolution (caught up + combat intent) ---------------


def test_execute_pursue_peaceful_plan_bypasses_acceptance_and_combat():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result == PursueExecutionResult(caught_up=True, combat_occurred=False)
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_pursue_king_target_refused_when_not_mutual():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    # catch-up roll (0.0, guaranteed at distance 0) then is_encounter_accepted's
    # King-target branch, which reads mutual_encounter directly with no roll.
    result = execute_pursue(state, 1, _melee_request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

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
    rng = ScriptedRandom([0.0, 0.5, 0.5] + [0.1, 0.5, 0.9] * 15)

    result = execute_pursue(state, 1, _melee_request(2), rng=rng)

    assert result.caught_up is True
    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True
    assert 2 not in state.leaders
    assert 1 in state.leaders


def test_execute_pursue_combat_loots_the_decisive_losers_items():
    # Phase 313, rulebook [5.9] -- same setup as the removal test above.
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=2)
    rng = ScriptedRandom([0.0, 0.5, 0.5] + [0.1, 0.5, 0.9] * 15)

    result = execute_pursue(state, 1, _melee_request(2), rng=rng)

    assert result.loser_killed is True
    assert result.looted_item_ids == [item.item_id]
    assert state.items[item.item_id].owner_leader_id == 1


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
    rng = ScriptedRandom([0.0, 0.5, 0.5] + [0.1, 0.5, 0.9] * 15)

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

    result = execute_pursue(state, 1, _melee_request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

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

    result = execute_pursue(state, 1, _melee_request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

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


# -- Add_Experience wiring (Phase 461) ----------------------------------------


def test_execute_pursue_catch_up_awards_real_add_experience_credit():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))  # distance 0 -> chance 1.0

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.caught_up is True
    assert state.leaders[1].experience_credit == 10  # round(10*(1+0.5-0.5))


def test_execute_pursue_failed_catch_up_awards_no_add_experience_credit():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))  # distant, different Kingdom

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.99]))

    assert result.caught_up is False
    assert state.leaders[1].experience_credit == 0


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
    # catch-up roll, Add_Experience's own gain draws, then the cast's own success roll.
    rng = ScriptedRandom([0.0, 0.5, 0.5, 0.1])

    result = execute_pursue(state, 1, request, rng=rng)

    assert result.caught_up is True
    assert result.combat_occurred is True
    assert result.fled is True
    assert result.winner_leader_id is None
    assert 1 in state.leaders and 2 in state.leaders


# -- Phase 295: round-per-round engine + Temper-setup fix reachable via execute_pursue --


def test_execute_pursue_non_last_melee_tactic_steps_one_round_via_the_shared_engine():
    # Proves the armyless case's delegation to resolve_challenge_combat()
    # really does reach the Phase 292 round-stepping branch through
    # execute_pursue's own public API (not just in theory, from reading
    # the source) -- a MELEE tactic followed by more tactics fights only
    # one round via resolve_one_melee_round(), not the atomic duel.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = PursueRequest(
        target_character_id=2,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)],
    )

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        result = execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert mock_round.called
    assert mock_duel.called  # the exhausted-list fallback still ran afterward
    assert result.caught_up is True


def test_execute_pursue_non_last_melee_applies_temper_setup_exactly_once():
    # Same inheritance proof as above, for the Phase 294 fix: Berserk's
    # Temper setup must fire exactly once before round-stepping starts,
    # reached here through execute_pursue -- not just resolve_challenge_
    # combat() called directly, as the Phase 294 tests already cover.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, temper=Temper.BERSERK))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = PursueRequest(
        target_character_id=2,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)],
    )

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.apply_temper_melee_setup"
    ) as mock_setup, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert mock_setup.call_count == 1


# -- Phase 674: the armyless case threads the target's own real Special
# Encounter Plan into resolve_challenge_combat()'s target_tactics --


def test_execute_pursue_threads_an_armyless_targets_special_encounter_plan():
    state = _base_state()
    pursuer = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target.special_encounter_plan = (SearchTactic(Maneuver.CAST, Spell.FIREBALL.value),)
    state.add_leader(pursuer)
    state.add_leader(target)
    request = _melee_request(2)

    with patch("ak_engine.turn.pursue_execution.resolve_challenge_combat") as mock_resolve:
        mock_resolve.return_value = ChallengeCombatOutcome(winner="a")
        execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert mock_resolve.called
    assert mock_resolve.call_args.kwargs["target_tactics"] == list(target.special_encounter_plan)


# -- Phase 686: Melee/Archery combat-experience wiring --


def test_execute_pursue_landed_melee_hit_credits_the_pursuer():
    state = _base_state()
    pursuer = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(pursuer)
    state.add_leader(target)
    request = _melee_request(2)

    with patch("ak_engine.turn.pursue_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.pursue_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = ChallengeCombatOutcome(
            winner="a", melee_swings=(MeleeSwing(attacker="a", hit=True, damage=3),)
        )
        execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    mock_add_experience.assert_any_call(pursuer, Ability.MELEE, 10, ANY)


def test_execute_pursue_landed_melee_hit_credits_the_target_independently():
    state = _base_state()
    pursuer = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(pursuer)
    state.add_leader(target)
    request = _melee_request(2)

    with patch("ak_engine.turn.pursue_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.pursue_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = ChallengeCombatOutcome(
            winner="b", melee_swings=(MeleeSwing(attacker="b", hit=True, damage=3),)
        )
        execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    mock_add_experience.assert_any_call(target, Ability.MELEE, 10, ANY)
    # Phase 461's own SPY credit (unconditional, unrelated to combat) still
    # fires for `pursuer` here -- only Melee/Archery credit is under test.
    combat_ability_calls = [c for c in mock_add_experience.call_args_list if c.args[1] in (Ability.MELEE, Ability.ARCHERY)]
    assert all(call.args[0] is not pursuer for call in combat_ability_calls)


def test_execute_pursue_all_miss_credits_nothing():
    state = _base_state()
    pursuer = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(pursuer)
    state.add_leader(target)
    request = _melee_request(2)

    with patch("ak_engine.turn.pursue_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.pursue_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = ChallengeCombatOutcome(winner=None)
        execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    # Phase 461's own SPY credit (unconditional, unrelated to combat) may
    # still fire here -- only Melee/Archery credit is under test.
    combat_ability_calls = [c for c in mock_add_experience.call_args_list if c.args[1] in (Ability.MELEE, Ability.ARCHERY)]
    assert combat_ability_calls == []


def test_execute_pursue_never_threads_an_army_commanding_targets_plan():
    # execute_pursue()'s armyless-case call site is only ever reached
    # after the "pursuer_leads_army != target_leads_army" mismatch
    # check already returned early -- so both sides need to command an
    # army here for the walk to even reach that far, which routes to
    # the real army-battle branch (_fight_army_pursuit_battle) instead,
    # never to resolve_challenge_combat() at all -- confirming the
    # armyless-only scoping is real, not just asserted, is exactly
    # what this test is for.
    state = _base_state()
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, name="Field"))
    pursuer = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target.special_encounter_plan = (SearchTactic(Maneuver.CAST, Spell.FIREBALL.value),)
    state.add_leader(pursuer)
    state.add_leader(target)
    state.add_army(ArmyState(101, 1, ArmyType.AXEMEN, Quality.AVERAGE, FIELD, commanded_by=1))
    state.add_army(ArmyState(201, 2, ArmyType.AXEMEN, Quality.AVERAGE, FIELD, commanded_by=2))
    request = _melee_request(2)

    with patch("ak_engine.turn.pursue_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.pursue_execution.fight_battle"
    ) as mock_fight_battle:
        mock_fight_battle.return_value = None
        result = execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert not mock_resolve.called
    assert result.caught_up is True
    assert result.combat_occurred is True


# -- Phase 695: AdvancedAbility.SPY_SUPER_SLEUTH --------------------------


def test_execute_pursue_spy_super_sleuth_bypasses_the_catch_up_roll():
    # Same setup as test_execute_pursue_fails_to_catch_up_when_roll_is_
    # too_high (distant, different Kingdom -- a near-certain-fail roll)
    # -- succeeds anyway with the ability, since the roll is never made.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))

    result = execute_pursue(
        state,
        1,
        _peaceful_request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[1]),  # (-1,0,1)[1] == 0 offset
        has_spy_super_sleuth=True,
    )

    assert result.caught_up is True
    assert result.guessed_distance == hex_distance(FIELD, FAR_AWAY)


def test_execute_pursue_spy_super_sleuth_guessed_distance_can_be_off_by_one():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=HexCoord(3, 1)))  # distance 2

    result = execute_pursue(
        state,
        1,
        _peaceful_request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[2]),  # (-1,0,1)[2] == +1 offset
        has_spy_super_sleuth=True,
    )

    assert result.guessed_distance == 3


def test_execute_pursue_spy_super_sleuth_guessed_distance_floored_at_zero():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))  # distance 0

    result = execute_pursue(
        state,
        1,
        _peaceful_request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[0]),  # (-1,0,1)[0] == -1 offset
        has_spy_super_sleuth=True,
    )

    assert result.guessed_distance == 0


def test_execute_pursue_guessed_distance_is_none_without_the_ability():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_pursue(state, 1, _peaceful_request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.caught_up is True
    assert result.guessed_distance is None


def test_advance_pursuit_forwards_has_spy_super_sleuth():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Pursuer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))

    result = advance_pursuit(
        state,
        1,
        _peaceful_request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[1]),
        has_spy_super_sleuth=True,
    )

    assert result.caught_up is True
    assert result.guessed_distance is not None


# -- Phase 698: AdvancedAbility.SPY_ASSASSINATE --------------------------


def test_execute_pursue_spy_assassinate_accepts_a_king_target():
    # A King target would normally require mutual_encounter=True here --
    # the ability bypasses that unconditionally.
    state = _base_state()
    pursuer = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD, advanced_abilities={AdvancedAbility.SPY_ASSASSINATE})
    target = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(pursuer)
    state.add_leader(target)
    request = _melee_request(2)

    with patch("ak_engine.turn.pursue_execution.resolve_challenge_combat") as mock_resolve:
        mock_resolve.return_value = ChallengeCombatOutcome(winner=None)
        result = execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.caught_up is True
    assert result.combat_occurred is True


# -- Phase 700: AdvancedAbility.LONG_RANGE_ARCHERY (via the shared function) --


def test_execute_pursue_long_range_archery_reaches_through_the_shared_function():
    # Proves execute_pursue()'s armyless case reuses turn/challenge_
    # execution.py resolve_challenge_combat() unchanged -- the new
    # Phase 700 branch reaches through with zero pursue-side wiring.
    state = _base_state()
    pursuer = LeaderState(
        1, kingdom_id=1, name="Archer", location=FIELD, advanced_abilities={AdvancedAbility.LONG_RANGE_ARCHERY}
    )
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(pursuer)
    state.add_leader(target)
    request = PursueRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.SHOOT)])

    with patch("ak_engine.turn.challenge_execution.resolve_fire_arrow_duel") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    mock_resolve.assert_called_once_with(ANY, ANY, ANY, long_range_archer="a")


# -- Phase 701: AdvancedAbility.SHORT_RANGE_ARCHERY (via the shared function) --


def test_execute_pursue_short_range_archery_reaches_through_the_shared_function():
    # Proves execute_pursue()'s armyless case reuses turn/challenge_
    # execution.py resolve_challenge_combat() unchanged -- the new
    # Phase 701 branch reaches through with zero pursue-side wiring.
    state = _base_state()
    pursuer = LeaderState(
        1, kingdom_id=1, name="Archer", location=FIELD, advanced_abilities={AdvancedAbility.SHORT_RANGE_ARCHERY}
    )
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(pursuer)
    state.add_leader(target)
    request = PursueRequest(
        target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.SHOOT)]
    )

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=False, damage=0),
    ), patch("ak_engine.turn.challenge_execution.resolve_fire_arrow_duel") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_pursue(state, 1, request, rng=ScriptedRandom([0.0, 0.5, 0.5]))

    mock_resolve.assert_called_once_with(ANY, ANY, ANY, short_range_archer="a")
