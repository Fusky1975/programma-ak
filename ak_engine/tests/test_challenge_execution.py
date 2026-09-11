from __future__ import annotations

import random
from unittest.mock import ANY, patch

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.game_type import GameType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterSpeed
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.challenge_execution import (
    FLEE_CHANCE,
    INVISIBILITY_FLEE_CHANCE_BONUS,
    MELEE_EVASION_FLEE_CHANCE_BONUS,
    WEAK_TEMPER_FLEE_CHANCE_BONUS,
    ChallengeCombatOutcome,
    ChallengeExecutionResult,
    _apply_bravest_talk_inspiration,
    _apply_duel_encounter_merit,
    _apply_spy_brainwash_alignment_shift,
    _apply_successful_theft,
    _apply_treasury_raid,
    _close_to,
    _leader_combatant,
    _resolve_cast_disruption,
    _resolve_personal_combat_cast,
    _resolve_steal_tactic,
    effective_flee_chance,
    execute_challenge,
    has_combat_intent,
    is_encounter_accepted,
    resolve_challenge_combat,
    target_evades_via_sense_danger,
)
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    Combatant,
    CombatRange,
    EncounterCombatResult,
    FireArrowShot,
    MeleeRoundOutcome,
    MeleeSwing,
    ReactiveMeleeSwingResult,
)
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
ELSEWHERE = HexCoord(9, 9)


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _peaceful_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK)])


def _melee_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])


def _steal_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.STEAL)])


def _cast_request(target_id: int, spell: Spell, *following: Maneuver) -> ChallengeRequest:
    tactics = [SearchTactic(Maneuver.CAST, spell.value)]
    tactics += [SearchTactic(m) for m in following]
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=tactics)


# -- has_combat_intent --------------------------------------------------


def test_has_combat_intent_true_for_melee():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])
    assert has_combat_intent(request) is True


def test_has_combat_intent_true_for_fire_arrow():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.SHOOT)])
    assert has_combat_intent(request) is True


def test_has_combat_intent_false_for_peaceful_tactics():
    request = ChallengeRequest(
        target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK), SearchTactic(Maneuver.STEAL)]
    )
    assert has_combat_intent(request) is False


def test_has_combat_intent_false_for_no_tactics_at_all():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[])
    assert has_combat_intent(request) is False


def test_has_combat_intent_true_for_a_decodable_cast_tactic():
    # Phase 290: [3.12]'s own text names "personal combat spells
    # (including Charm)" alongside combat tactics -- a CAST entry is
    # combat intent too, not just Melee/Fire Arrow.
    request = ChallengeRequest(
        target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.CAST, Spell.CHARM.value)]
    )
    assert has_combat_intent(request) is True


def test_has_combat_intent_false_for_cast_with_an_undecodable_spell_id():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.CAST, 9999)])
    assert has_combat_intent(request) is False


# -- is_encounter_accepted: rulebook [3.12]'s King/Hero decision tree ---


def test_king_target_accepts_only_when_mutual():
    accepted = is_encounter_accepted(
        target_is_king=True, target_leads_army=False, challenger_is_king=False, mutual_encounter=True, rng=ScriptedRandom([])
    )
    assert accepted is True


def test_king_target_refuses_when_not_mutual():
    accepted = is_encounter_accepted(
        target_is_king=True, target_leads_army=False, challenger_is_king=False, mutual_encounter=False, rng=ScriptedRandom([])
    )
    assert accepted is False


def test_hero_leading_an_army_always_refuses():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=True, challenger_is_king=True, mutual_encounter=True, rng=ScriptedRandom([])
    )
    assert accepted is False


def test_armyless_hero_vs_king_challenger_is_a_50_50_roll():
    accepted_low = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=True, mutual_encounter=False,
        rng=ScriptedRandom([0.49]),
    )
    accepted_high = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=True, mutual_encounter=False,
        rng=ScriptedRandom([0.5]),
    )
    assert accepted_low is True
    assert accepted_high is False


def test_armyless_hero_vs_hero_challenger_always_accepts_without_consuming_rng():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=False, mutual_encounter=False,
        rng=ScriptedRandom([]),  # any .random() call here would raise IndexError
    )
    assert accepted is True


# -- Phase 698: AdvancedAbility.SPY_ASSASSINATE's own unconditional bypass --


def test_spy_assassinate_accepts_a_king_target_even_when_not_mutual():
    accepted = is_encounter_accepted(
        target_is_king=True, target_leads_army=False, challenger_is_king=False, mutual_encounter=False,
        rng=ScriptedRandom([]), has_spy_assassinate=True,
    )
    assert accepted is True


def test_spy_assassinate_accepts_an_army_leading_target():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=True, challenger_is_king=False, mutual_encounter=False,
        rng=ScriptedRandom([]), has_spy_assassinate=True,
    )
    assert accepted is True


def test_spy_assassinate_king_challenger_is_never_evaded_and_consumes_no_rng():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=True, mutual_encounter=False,
        rng=ScriptedRandom([]), has_spy_assassinate=True,  # any .random() call here would raise IndexError
    )
    assert accepted is True


def test_leader_combatant_reads_real_temper():
    # Phase 284: the Temper Table's own melee mechanics need each
    # combatant's real Temper threaded through.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD, temper=Temper.CAUTIOUS)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.temper is Temper.CAUTIOUS


def test_leader_combatant_gives_the_imperial_defender_a_damage_reduction_of_one():
    # Phase 489: CARICHE E ABLITA.txt's own Office.DEFENDER perk ("reduce
    # any strike against you in personal combat ... by one damage point").
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    leader.merit_tally.monster_hp_defeated = 1  # meets OFFICE_MIN_POINTS[Office.DEFENDER]
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.damage_reduction == 1


def test_leader_combatant_gives_no_damage_reduction_without_the_office():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.damage_reduction == 0


def test_leader_combatant_reads_the_illus_mage_titles_always_acts_first():
    # Phase 665: Office.ILLUS_MAGE's own Chameleon Familiar perk ("always
    # make the first move in combat, even if opponent has greater skill").
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    leader.merit_tally.illusionist_spell_casts = 20  # meets OFFICE_MIN_POINTS[Office.ILLUS_MAGE]
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.always_acts_first is True


def test_leader_combatant_defaults_always_acts_first_to_false_without_the_office():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.always_acts_first is False


def test_leader_combatant_reads_the_necro_mage_titles_regeneration():
    # Phase 666: Office.NECRO_MAGE's own Imp familiar -- "help <2
    # regenerate 1 hit point per 2 rounds of combat."
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    leader.merit_tally.necromancy_spell_casts = 20  # meets OFFICE_MIN_POINTS[Office.NECRO_MAGE]
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.regenerates_hp == 1
    assert combatant.regenerates_hp_interval == 2


def test_leader_combatant_no_necro_mage_regeneration_without_the_office():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.regenerates_hp == 0
    assert combatant.regenerates_hp_interval == 1


def test_leader_combatant_reads_the_melee_hit_points_advanced_ability():
    # Phase 516: AdvancedAbility.MELEE_HIT_POINTS.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(
        501, kingdom_id=1, name="Hero", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_HIT_POINTS}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.has_melee_hit_points_ability is True


def test_leader_combatant_reads_melee_mastery():
    # Phase 517: AdvancedAbility.MELEE_MASTERY/MELEE_TRUE_MASTERY.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_MASTERY})
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.10)
    assert combatant.melee_damage_dealt_bonus == 1


def test_leader_combatant_reads_melee_true_mastery():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(
        501, kingdom_id=1, name="Hero", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_TRUE_MASTERY}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == 1.0
    assert combatant.melee_damage_dealt_bonus == 2


def test_leader_combatant_reads_equipped_weapon_hit_and_damage_bonus():
    # Phase 535: AKGEN_reverse_engineering_report (4).md SS7.2 -- Flaming
    # Scimitar (WEAPON_3) is +20% hit, +3 damage, composed multiplicatively/
    # additively with any AdvancedAbility bonus (none held here).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_3, owner_leader_id=501)

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.20)
    assert combatant.melee_damage_dealt_bonus == 3


def test_leader_combatant_composes_weapon_bonus_with_melee_mastery():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_MASTERY})
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_2, owner_leader_id=501)  # Shadow Sword: +15%/+1

    combatant = _leader_combatant(leader, state)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.10 * 1.15)
    assert combatant.melee_damage_dealt_bonus == 1 + 1


def test_leader_combatant_reads_bow_of_the_elven_kings_archery_bonus():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=501)
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=501)  # doesn't stack

    combatant = _leader_combatant(leader, state)

    assert combatant.archery_hit_multiplier == pytest.approx(1.25)
    assert combatant.missile_damage_dealt_bonus == 2
    # The Bow never occupies the sword slot -- no Melee bonus leaks from it.
    assert combatant.offensive_hit_multiplier == 1.0
    assert combatant.melee_damage_dealt_bonus == 0


def test_leader_combatant_reads_undead_alignment_as_undead_or_anti_holy():
    # Phase 682: SS7.1's Holy Sword vs-Undead bonus needs the combatant's
    # own nature, set independently of any weapon.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD, alignment=Alignment.ANTI_HOLY)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.is_undead_or_anti_holy is True


def test_leader_combatant_reads_non_undead_alignment_as_not_undead_or_anti_holy():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD, alignment=Alignment.GOOD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.is_undead_or_anti_holy is False


def test_leader_combatant_reads_holy_sword_auto_protection():
    # Phase 536: AKGEN_reverse_engineering_report (4).md SS7.3 -- Holy
    # Sword grants an automatic, damage-free level-4 Holy Symbol
    # protection while equipped.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_1, owner_leader_id=501)

    combatant = _leader_combatant(leader, state)

    assert combatant.defensive_hit_multiplier == pytest.approx(0.6)
    assert combatant.is_invisible is False
    assert combatant.equipped_weapon is Treasure.WEAPON_1


def test_leader_combatant_reads_invisible_sword_auto_invisibility():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_5, owner_leader_id=501)

    combatant = _leader_combatant(leader, state)

    assert combatant.is_invisible is True
    assert combatant.defensive_hit_multiplier == pytest.approx(0.5)
    assert combatant.equipped_weapon is Treasure.WEAPON_5


def test_leader_combatant_equipped_weapon_field_is_none_with_no_weapon():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.equipped_weapon is None
    assert combatant.defensive_hit_multiplier == 1.0
    assert combatant.is_invisible is False


def test_leader_combatant_reads_arcane_valor_scepter_hit_points_bonus():
    # Phase 538: AKGEN_reverse_engineering_report (4).md SS11.2 -- +5
    # combat hit points for personally holding the Scepter of Life,
    # active only under GameType.ARCANES.
    state = GameState(game_type=GameType.ARCANES)
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.NAMED_UNIQUE_SCEPTER_LIFE, owner_leader_id=501)

    combatant = _leader_combatant(leader, state)

    assert combatant.hit_points == CHARACTER_HIT_POINTS + 5


def test_leader_combatant_arcane_valor_bonus_is_zero_outside_arcanes():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)
    state.add_item(Treasure.NAMED_UNIQUE_SCEPTER_LIFE, owner_leader_id=501)

    combatant = _leader_combatant(leader, state)

    assert combatant.hit_points == CHARACTER_HIT_POINTS


def test_leader_combatant_reads_duellists_medal_and_kingdom_race_humanoid():
    # Phase 518: AdvancedAbility.MELEE_DUELLISTS_MEDAL + is_humanoid.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(
        501, kingdom_id=1, name="Hero", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_DUELLISTS_MEDAL}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.has_duellists_medal_ability is True
    assert combatant.is_humanoid is True


def test_leader_combatant_reads_control_temper_ability():
    # Phase 519: AdvancedAbility.MELEE_CONTROL_TEMPER.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(
        501, kingdom_id=1, name="Hero", location=FIELD, advanced_abilities={AdvancedAbility.MELEE_CONTROL_TEMPER}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.has_control_temper_ability is True


def test_leader_combatant_reads_archery_free_attack_bonus():
    # Phase 520: AdvancedAbility.ARCHERY_FREE_ATTACK/_MASTERY/_TRUE_MASTERY.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(
        501, kingdom_id=1, name="Hero", location=FIELD, advanced_abilities={AdvancedAbility.ARCHERY_FREE_ATTACK}
    )
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.archery_free_attack_bonus == 1


def test_leader_combatant_non_humanoid_kingdom_race_is_not_humanoid():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Trollholm", Race.TROLLISH, Alignment.EVIL, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.is_humanoid is False


# -- execute_challenge: co-location, not-found, peaceful bypass ---------


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    return state


def test_execute_challenge_reports_not_found_when_challenger_missing():
    state = _base_state()
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_execute_challenge_reports_not_found_when_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_execute_challenge_refuses_when_not_co_located():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=ELSEWHERE))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "not co-located"


def test_execute_challenge_peaceful_plan_bypasses_acceptance_and_combat():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_challenge(state, 1, _peaceful_request(2), rng=ScriptedRandom([]))

    assert result == ChallengeExecutionResult(accepted=True, combat_occurred=False)
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_king_target_refused_when_not_mutual_and_no_combat_happens():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "encounter refused"
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_hero_with_army_target_refused():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "encounter refused"


# -- execute_challenge: combat resolution + loser removal ---------------


def test_execute_challenge_combat_removes_the_decisive_loser():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    # A always acts first (higher melee skill, no initiative roll needed);
    # scripted so A always hits and B always misses.
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True
    assert 2 not in state.leaders
    assert 1 in state.leaders


def test_execute_challenge_combat_loots_the_decisive_losers_items():
    # Phase 313, rulebook [5.9]: "looting a vanquished foe's treasure,
    # magic items changing hands" -- same setup as the removal test above.
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=2)
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.loser_killed is True
    assert result.looted_item_ids == [item.item_id]
    assert state.items[item.item_id].owner_leader_id == 1


def test_execute_challenge_combat_with_no_decisive_winner_kills_nobody():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    # execute_challenge doesn't expose resolve_melee_duel's max_rounds, so
    # this exercises the real default (1000) all the way to its cap: both
    # combatants have equal (zero) melee skill, so every round's initiative
    # tie-break plus both always-miss attack rolls consumes 3 scripted
    # values -- 1000 rounds * 3.
    rng = ScriptedRandom([0.99] * 3000)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.winner_leader_id is None
    assert result.loser_killed is False
    assert 1 in state.leaders and 2 in state.leaders


# -- Fire Arrow (Phase 273): SHOOT now actually resolves via Fire Arrow --


def test_execute_challenge_shoot_tactic_resolves_via_fire_arrow_before_melee():
    state = _base_state()
    # A has real Archery skill (10 free attacks, guaranteed hit chance since
    # 0.30 + 0.10*10 > 1.0) and no Melee skill at all. B has real Melee
    # skill (9) but no Archery -- if this still fell straight to Melee (the
    # pre-Phase-273 bug), B's own higher skill would act first and A
    # wouldn't reliably win. A's 10 guaranteed archery hits (minimum 1
    # damage each) always total at least 10, guaranteeing B's death within
    # Fire Arrow alone, regardless of the exact (unscripted) damage rolled
    # per hit.
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ARCHERY, 10, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9))
    )
    rng = ScriptedRandom([0.01] * 25)
    shoot_request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.SHOOT)])

    result = execute_challenge(state, 1, shoot_request, rng=rng)

    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_mutual_king_encounter_can_result_in_combat():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng, mutual_encounter=True)

    assert result.accepted is True
    assert result.winner_leader_id == 1
    # Phase 259: a King's death installs a Royal Heir under the same
    # leader_id rather than leaving the Kingdom leaderless.
    assert 2 in state.dead_leaders
    assert state.leaders[2].is_royal_heir is True


# -- Phase 290: Personal-Combat spells wired via resolve_challenge_combat --


def test_execute_challenge_cast_charm_success_makes_the_caster_flee():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.CHARM, Maneuver.MELEE)

    result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.1]))

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.fled is True
    assert result.winner_leader_id is None
    assert 1 in state.leaders and 2 in state.leaders


def test_resolve_personal_combat_cast_charm_blocked_by_analytical_psychology():
    # Phase 529: AKGEN_reverse_engineering_report (3).md SS8.3 -- Counter_
    # Science(target, Charm) is checked before the flee itself; when the
    # target's own Kingdom holds Discovery.ANALYTICAL_PSYCHOLOGY, the
    # spell is simply ineffective (combat continues), unlike the
    # Action-Cast form which still succeeds and only reverts later.
    state = _base_state()
    state.kingdoms[2].discoveries.add(Discovery.ANALYTICAL_PSYCHOLOGY)
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.CHARM.value)
    rng = ScriptedRandom([0.1])  # cast roll succeeds

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None  # ineffective -- no flee, combat continues


def test_resolve_personal_combat_cast_charm_unprotected_target_still_flees():
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.CHARM.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome == "fled"


def test_resolve_personal_combat_cast_charm_with_enhanced_ability_transfers_item():
    # Phase 529: AKGEN_reverse_engineering_report (3).md SS9.2 -- Enhanced
    # Charm's item transfer applies to Personal-Combat Charm too.
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9))
    caster_leader.advanced_abilities.add(AdvancedAbility.ENHANCED_CHARM)
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    first_item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=2)
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=2)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.CHARM.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome == "fled"
    assert state.items[first_item.item_id].owner_leader_id == 1
    assert state.items_held_by(2) == [state.items[first_item.item_id + 1]]


def test_resolve_personal_combat_cast_charm_blocked_target_never_transfers_item_even_with_enhanced_ability():
    state = _base_state()
    state.kingdoms[2].discoveries.add(Discovery.ANALYTICAL_PSYCHOLOGY)
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9))
    caster_leader.advanced_abilities.add(AdvancedAbility.ENHANCED_CHARM)
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=2)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.CHARM.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None
    assert state.items[item.item_id].owner_leader_id == 2  # untouched


def test_resolve_personal_combat_cast_fireball_blocked_by_anti_elemental_amulet():
    # Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- the Orb
    # of Elemental Stability personally blocks Fireball.
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=2)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    starting_hit_points = target.hit_points
    tactic = SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None
    assert target.hit_points == starting_hit_points  # negated -- no damage at all


def test_resolve_personal_combat_cast_psychic_blast_blocked_by_anti_psychic_amulet():
    # Both AKGEN_reverse_engineering_report (3).md SS3.4 and (4).md SS8
    # name Psychic Blast specifically as negated by the Helm of Psychic
    # Dampening -- the one amulet case that survived the Phase 531
    # rework unchanged.
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    state.add_item(Treasure.AMULET_ANTI_PSYCHIC, owner_leader_id=2)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    starting_bonus = caster.bonus_unanswered_attacks
    tactic = SearchTactic(Maneuver.CAST, Spell.PSYCHIC_BLAST.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None
    assert caster.bonus_unanswered_attacks == starting_bonus


def test_resolve_personal_combat_cast_hand_of_death_blocked_by_anti_necromancy_amulet():
    # Proves the single Phase 531 checkpoint also covers Hand of Death,
    # the True Cross's own second blocked spell (alongside Kill_Enemy).
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    state.add_item(Treasure.AMULET_ANTI_NECROMANCY, owner_leader_id=2)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    starting_hit_points = target.hit_points
    tactic = SearchTactic(Maneuver.CAST, Spell.HAND_OF_DEATH.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None
    assert target.hit_points == starting_hit_points


def test_resolve_personal_combat_cast_necro_mage_target_resists_the_successful_spell():
    # Phase 666: Office.NECRO_MAGE's own Imp familiar -- "25% magic
    # resistance, meaning that 25% of the spells cast against <2 will
    # fail." No amulet involved -- the resistance roll alone negates it.
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target_leader.merit_tally.necromancy_spell_casts = 20  # meets OFFICE_MIN_POINTS[Office.NECRO_MAGE]
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    starting_hit_points = target.hit_points
    tactic = SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)
    rng = ScriptedRandom([0.1, 0.1])  # [0] cast succeeds, [1] under the 25% resistance chance

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None
    assert target.hit_points == starting_hit_points  # resisted -- no damage at all


def test_resolve_personal_combat_cast_necro_mage_target_does_not_always_resist():
    # Same setup, but the resistance roll misses -- the spell lands normally.
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target_leader.merit_tally.necromancy_spell_casts = 20
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    starting_hit_points = target.hit_points
    tactic = SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)
    rng = ScriptedRandom([0.1, 0.99, 0.5])  # [0] cast succeeds, [1] over the 25% resistance chance, [2] damage roll

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None  # Fireball's own effect doesn't end the encounter outright
    assert target.hit_points < starting_hit_points  # not resisted -- damage landed


def test_resolve_personal_combat_cast_no_necro_mage_title_never_consumes_a_resistance_roll():
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)
    # [0] cast-success roll, [1] Fireball's own damage roll -- no 3rd
    # value: a non-titleholder never reaches the resistance roll at all,
    # confirmed by ScriptedRandom raising IndexError if it tried to.
    rng = ScriptedRandom([0.1, 0.5])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None


def test_resolve_personal_combat_cast_control_undead_not_blocked_by_anti_necromancy_amulet():
    # Phase 531's own correction, made concrete: the True Cross blocks
    # only Kill_Enemy/Hand_of_Death, not every Necromancy spell -- Control
    # Undead (also Necromancy) still succeeds against the same amulet that
    # would have blocked it under Phase 530's blanket-school approach.
    # Proves the checkpoint's placement (right after the succeeded roll,
    # before Control Undead's own early-return branch) doesn't accidentally
    # over-block spells the real amulet leaves alone.
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.UNDEAD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    state.add_item(Treasure.AMULET_ANTI_NECROMANCY, owner_leader_id=2)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.CONTROL_UNDEAD.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome == "a"  # succeeds -- not in the True Cross's blocked set


def test_resolve_personal_combat_cast_invisibility_not_blocked_by_target_anti_magic_amulet():
    # Phase 531: Invisibility is self-only (never reads/writes target) --
    # excluded from the immunity check regardless. (The Anti-Illusion
    # Amulet -- Crystal of True Seeing -- isn't even in AMULET_BLOCKED_
    # SPELLS yet; its own, structurally different mechanic is deferred to
    # Phase 532.)
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ILLUSION, 5, 9))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    state.add_item(Treasure.AMULET_ANTI_ILLUSION, owner_leader_id=2)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.INVISIBILITY.value)
    rng = ScriptedRandom([0.1])

    outcome = _resolve_personal_combat_cast(
        caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
    )

    assert outcome is None
    assert caster.is_invisible is True  # self-buff still applies


def test_execute_challenge_cast_augur_combat_not_blocked_by_target_anti_magic_amulet():
    # Phase 531: Augur_Combat is self-only -- excluded from the immunity
    # check even when the target holds the matching Anti-Psychic Amulet.
    state = _base_state()
    caster = LeaderState(
        1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9), temper=Temper.CAUTIOUS
    )
    state.add_leader(caster)
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    state.add_item(Treasure.AMULET_ANTI_PSYCHIC, owner_leader_id=2)
    request = _cast_request(2, Spell.AUGUR_COMBAT)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="b", rounds=1)
    ), patch("ak_engine.turn.challenge_execution.resolve_augur_combat", return_value=True):
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.fled is True


def test_execute_challenge_cast_control_undead_success_kills_undead_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.UNDEAD))
    request = _cast_request(2, Spell.CONTROL_UNDEAD)

    result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.1]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_cast_control_undead_ineligible_target_consumes_no_roll():
    # Target isn't Undead -- the same leader-only "else" branch `turn/
    # search_execution.py` already uses, re-derived here.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.GOOD))
    request = _cast_request(2, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert mock_melee.called
    assert result.winner_leader_id == 1


def test_execute_challenge_cast_control_undead_without_ability_anti_holy_target_stays_ineligible():
    # Phase 502: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS -- without the
    # ability, an Anti-Holy (not Undead) target is still ineligible.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.ANTI_HOLY))
    request = _cast_request(2, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert mock_melee.called


def test_execute_challenge_cast_control_undead_enhanced_ability_makes_anti_holy_target_eligible():
    # Phase 502: with the ability, an Anti-Holy target becomes eligible;
    # forcing the resist chance to zero lets a successful cast neutralize
    # it exactly like an ordinary Undead target.
    state = _base_state()
    caster = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 5, 9))
    caster.advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS)
    state.add_leader(caster)
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.ANTI_HOLY))
    request = _cast_request(2, Spell.CONTROL_UNDEAD)

    with patch("ak_engine.turn.challenge_execution.control_undead_anti_holy_resist_chance", return_value=0.0):
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.1, 0.9]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_cast_control_undead_anti_holy_resist_roll_blocks_neutralization():
    # Phase 502: forcing the resist chance to certainty makes an
    # otherwise successful cast fall through to ordinary Melee instead.
    state = _base_state()
    caster = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 5, 9))
    caster.advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS)
    state.add_leader(caster)
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.ANTI_HOLY))
    request = _cast_request(2, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.control_undead_anti_holy_resist_chance", return_value=1.0), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([0.1, 0.5]))

    assert mock_melee.called


def test_execute_challenge_cast_holy_symbol_enhanced_grants_bonus_damage_against_evil_target():
    # Phase 497: AdvancedAbility.ENHANCED_HOLY_SYMBOL -- "the Holy Symbol
    # spell now has the same effect against opponents who have an Evil
    # alignment as it does against Undead creatures."
    state = _base_state()
    caster = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.WHITE, 2, 9))
    caster.advanced_abilities.add(AdvancedAbility.ENHANCED_HOLY_SYMBOL)
    state.add_leader(caster)
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.EVIL))
    request = _cast_request(2, Spell.HOLY_SYMBOL)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_holy_symbol_undead_damage", return_value=999
    ):
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_cast_holy_symbol_without_enhancement_no_bonus_against_evil_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.WHITE, 2, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.EVIL))
    request = _cast_request(2, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_holy_symbol_undead_damage", return_value=999
    ) as mock_damage, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_damage.called
    assert mock_melee.called


def test_execute_challenge_cast_fireball_kills_via_damage():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.FIREBALL)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_fireball_damage", return_value=99
    ):
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_cast_words_of_healing_heals_the_caster():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.WHITE, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9)))
    request = _cast_request(2, Spell.HEAL, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    caster_combatant = mock_melee.call_args[0][0]
    assert caster_combatant.hit_points == CHARACTER_HIT_POINTS


def test_execute_challenge_cast_words_of_healing_level_gate_blocks_low_white_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.WHITE, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9)))
    request = _cast_request(2, Spell.HEAL, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert mock_melee.called


# -- Phase 761: the same skill-5+ gate for Gate Demon/Lava Pool/Augur Combat ---


def test_execute_challenge_cast_gate_demon_level_gate_blocks_low_necromancy_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9)))
    request = _cast_request(2, Spell.GATE_DEMON, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.roll_gate_demon_type"
    ) as mock_demon_type, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert not mock_demon_type.called
    assert mock_melee.called


def test_execute_challenge_cast_lava_pool_level_gate_blocks_low_elemental_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9)))
    request = _cast_request(2, Spell.LAVA_POOL, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.resolve_lava_pool_escape"
    ) as mock_escape, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert not mock_escape.called
    assert mock_melee.called


def test_execute_challenge_cast_augur_combat_level_gate_blocks_low_psychic_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9)))
    request = _cast_request(2, Spell.AUGUR_COMBAT, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert mock_melee.called


def test_execute_challenge_cast_hand_of_death_channel_win_kills_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.HAND_OF_DEATH)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_hand_of_death_channel"
    ) as mock_channel:
        mock_channel.return_value = EncounterCombatResult(winner="a", rounds=3)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2


def test_execute_challenge_cast_hand_of_death_enhanced_ability_overrides_the_immune_flag():
    # Phase 500: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS -- "'Hand of
    # Death' now works against all creatures." Without the ability, an
    # Undead target is immune; with it, the channel proceeds anyway.
    state = _base_state()
    caster = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 4, 9))
    caster.advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS)
    state.add_leader(caster)
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.UNDEAD))
    request = _cast_request(2, Spell.HAND_OF_DEATH)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_hand_of_death_channel"
    ) as mock_channel:
        mock_channel.return_value = EncounterCombatResult(winner="a", rounds=3)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert mock_channel.call_args.kwargs["target_is_immune"] is False


def test_execute_challenge_cast_mirror_image_caster_wins():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ILLUSION, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=2)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1


def test_execute_challenge_cast_mirror_image_caster_passes_own_detect_illusions_as_caster_bonus():
    # Phase 494: unlike turn/search_execution.py's own Search encounter
    # (always leader-vs-monster), a Challenge is leader-vs-leader -- both
    # sides can independently hold Detect Illusions, checked against
    # their own real LeaderState directly.
    state = _base_state()
    caster = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ILLUSION, 4, 9))
    caster.advanced_abilities.add(AdvancedAbility.DETECT_ILLUSIONS_TALENT)
    state.add_leader(caster)
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is True
    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is False


def test_execute_challenge_cast_mirror_image_target_passes_own_detect_illusions_as_opponent_bonus():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ILLUSION, 4, 9)))
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target.advanced_abilities.add(AdvancedAbility.DETECT_ILLUSIONS_TALENT)
    state.add_leader(target)
    request = _cast_request(2, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is True
    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is False


def test_execute_challenge_cast_illusory_hero_caster_passes_own_detect_illusions_as_caster_bonus():
    state = _base_state()
    caster = LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ILLUSION, 5, 9))
    caster.advanced_abilities.add(AdvancedAbility.DETECT_ILLUSIONS_TALENT)
    state.add_leader(caster)
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", FIELD))
    request = _cast_request(2, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is True
    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is False


def test_execute_challenge_cast_illusory_hero_target_passes_own_detect_illusions_as_opponent_bonus():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ILLUSION, 5, 9)))
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target.advanced_abilities.add(AdvancedAbility.DETECT_ILLUSIONS_TALENT)
    state.add_leader(target)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", FIELD))
    request = _cast_request(2, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is True
    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is False


def test_execute_challenge_cast_invisibility_target_with_witchsight_is_unaffected():
    # Phase 496: AdvancedAbility.WITCHSIGHT_TALENT -- "the Necromancer can
    # still see his opponent and is unaffected by the spell" -- the
    # caster becomes invisible, but the *target* (whoever has to keep
    # fighting them) needs Witchsight to be unaffected.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target.advanced_abilities.add(AdvancedAbility.WITCHSIGHT_TALENT)
    state.add_leader(target)
    request = _cast_request(2, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    caster_combatant = mock_melee.call_args[0][0]
    assert caster_combatant.defensive_hit_multiplier == 1.0
    assert caster_combatant.is_invisible is True


def test_execute_challenge_cast_invisibility_target_without_witchsight_is_halved():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    caster_combatant = mock_melee.call_args[0][0]
    assert caster_combatant.defensive_hit_multiplier == 0.5


def test_execute_challenge_cast_invisibility_target_holding_crystal_of_true_seeing_is_unaffected():
    # Phase 532: AKGEN_reverse_engineering_report (4).md SS8 point 3 --
    # the Crystal of True Seeing (AMULET_ANTI_ILLUSION) lets its holder
    # see through Invisibility, same shape as Witchsight above but via
    # item possession rather than an Advanced Ability.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    state.add_item(Treasure.AMULET_ANTI_ILLUSION, owner_leader_id=2)
    request = _cast_request(2, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    caster_combatant = mock_melee.call_args[0][0]
    assert caster_combatant.defensive_hit_multiplier == 1.0
    assert caster_combatant.is_invisible is True


def test_execute_challenge_cast_gate_demon_summons_and_the_demon_wins():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.GOOD))
    request = _cast_request(2, Spell.GATE_DEMON)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_gate_demon_type", return_value=Monster.SUCCUBUS
    ), patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.5]))

    assert result.winner_leader_id == 1
    demon_combatant = mock_melee.call_args[0][0]
    assert demon_combatant.name  # a real, named monster Combatant was summoned
    # Phase 682: Succubus is in HAND_OF_DEATH_ANTI_HOLY_MONSTERS -- the
    # summoned demon should carry the flag Holy Sword's vs-Undead bonus needs.
    assert demon_combatant.is_undead_or_anti_holy is True


def test_execute_challenge_cast_psychic_blast_bonus_attacks_can_finish_the_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.PSYCHIC_BLAST)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_psychic_blast_stun_rounds", return_value=2
    ), patch("ak_engine.turn.challenge_execution.roll_melee_attack", return_value=99):
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2


def test_augur_combat_cast_first_shirks_and_flees_on_a_simulated_loss():
    state = _base_state()
    caster_leader = LeaderState(
        1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9), temper=Temper.COWARDLY
    )
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.AUGUR_COMBAT.value)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.challenge_execution.resolve_augur_combat", return_value=True):
        mock_melee.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = _resolve_personal_combat_cast(
            caster, caster_leader, target, target_leader, tactic, state, ScriptedRandom([]), is_first_tactic=True, cast_slots_used={}, cast_spells_attempted=set()
        )

    assert outcome == "fled"


def test_augur_combat_cast_later_flee_succeeds():
    # Phase 743: AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER, now wired via
    # this module's own real [5.6] Flee formula. Cowardly gives +30% on
    # top of the MonsterSpeed.MEDIUM 50% base ("... or other characters"),
    # so 0.79 (< 0.80) succeeds. resolve_personal_combat_spell_cast() is
    # never reached -- the "cast later" branch returns before any roll.
    state = _base_state()
    caster_leader = LeaderState(
        1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9), temper=Temper.COWARDLY
    )
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.AUGUR_COMBAT.value)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll:
        outcome = _resolve_personal_combat_cast(
            caster,
            caster_leader,
            target,
            target_leader,
            tactic,
            state,
            ScriptedRandom([0.79]),
            is_first_tactic=False,
            cast_slots_used={},
            cast_spells_attempted=set(),
        )

    assert outcome == "fled"
    assert not mock_roll.called


def test_augur_combat_cast_later_flee_fails_falls_through():
    state = _base_state()
    caster_leader = LeaderState(
        1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9), temper=Temper.COWARDLY
    )
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.AUGUR_COMBAT.value)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll:
        outcome = _resolve_personal_combat_cast(
            caster,
            caster_leader,
            target,
            target_leader,
            tactic,
            state,
            ScriptedRandom([0.80]),
            is_first_tactic=False,
            cast_slots_used={},
            cast_spells_attempted=set(),
        )

    assert outcome is None
    assert not mock_roll.called


# -- Phase 292: the round-based range engine + real spell disruption ----


def _combatants(**overrides):
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, **overrides.pop("caster_kwargs", {}))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD, **overrides.pop("target_kwargs", {}))
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    return state, caster_leader, caster, target_leader, target


def test_close_to_advances_one_tier_at_a_time_and_never_widens():
    assert _close_to(CombatRange.BOW_RANGE, CombatRange.SPELL_RANGE) is CombatRange.BOW_RANGE
    assert _close_to(CombatRange.MELEE_RANGE, CombatRange.SPELL_RANGE) is CombatRange.MELEE_RANGE
    assert _close_to(CombatRange.MELEE_RANGE, CombatRange.BOW_RANGE) is CombatRange.MELEE_RANGE
    assert _close_to(CombatRange.MELEE_RANGE, CombatRange.MELEE_RANGE) is CombatRange.MELEE_RANGE
    assert _close_to(CombatRange.SPELL_RANGE, CombatRange.MELEE_RANGE) is CombatRange.MELEE_RANGE  # never widens


def test_resolve_challenge_combat_last_melee_tactic_fights_atomically():
    # Every real caller and pre-Phase-292 test orders MELEE last -- that
    # exact shape must still resolve via the full atomic resolve_melee_
    # duel(), not the new one-round primitive.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel, patch(
        "ak_engine.turn.challenge_execution.resolve_one_melee_round"
    ) as mock_round:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert mock_duel.called
    assert not mock_round.called
    assert outcome.winner == "a"


def test_resolve_challenge_combat_non_last_melee_tactic_steps_one_round_then_falls_through():
    # A MELEE tactic followed by more tactics is the new plan shape --
    # only one round is fought, and (undecided) the walk continues,
    # eventually reaching the same exhausted-list atomic fallback.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert mock_round.called
    assert mock_duel.called  # the exhausted-list fallback still ran afterward
    assert outcome.winner == "b"


def test_resolve_challenge_combat_non_last_melee_tactic_ends_combat_on_a_decisive_round():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=EncounterCombatResult(winner="a", rounds=1))
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert outcome.winner == "a"
    assert not mock_duel.called  # a decisive round ends the encounter outright


def test_resolve_challenge_combat_shoot_ignored_once_at_melee_range():
    # [5.0]: "In the melee zone, only spells or hand-to-hand attacks" --
    # a SHOOT tactic ordered after range has already closed to MELEE_
    # RANGE is a pure no-op, never reaching resolve_fire_arrow_duel.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.SHOOT)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_fire_arrow_duel"
    ) as mock_shoot, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert not mock_shoot.called
    assert mock_duel.called  # falls through to the atomic fallback afterward


def test_resolve_challenge_combat_cast_at_melee_range_disrupted_by_a_landed_hit_never_attempts_the_cast():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=5),
    ) as mock_swing, patch(
        "ak_engine.turn.challenge_execution.resolve_words_of_healing_disruption", return_value=True
    ) as mock_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_words_of_healing_disruption_from_missed_attack"
    ) as mock_miss_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast"
    ) as mock_cast, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_swing.called
    assert mock_disrupt.called  # Phase 730: Spell.HEAL routes through its own halved-rate roll, not the generic one
    assert not mock_miss_disrupt.called  # a landed hit uses the damage-scaled formula, not the flat-miss one
    assert not mock_cast.called  # disrupted -- "the caster loses a turn," no cast-chance roll at all


def test_resolve_challenge_combat_cast_at_melee_range_disrupted_by_a_missed_swing():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=False, damage=0),
    ), patch("ak_engine.turn.challenge_execution.resolve_words_of_healing_disruption") as mock_damage_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_words_of_healing_disruption_from_missed_attack", return_value=True
    ) as mock_miss_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast"
    ) as mock_cast, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_miss_disrupt.called
    assert not mock_damage_disrupt.called  # a miss uses the flat 30%, not the damage-scaled formula
    assert not mock_cast.called


def test_resolve_challenge_combat_cast_at_melee_range_not_disrupted_still_attempts_the_cast():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=2),
    ), patch("ak_engine.turn.challenge_execution.resolve_words_of_healing_disruption", return_value=False), patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.words_of_healing_heal") as mock_heal, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_cast.called  # not disrupted -- the cast-chance roll still happens
    assert mock_heal.called  # ... and, having succeeded, the spell's own effect still lands


# -- Phase 743: Maneuver.FLEE -----------------------------------------------


def test_effective_flee_chance_medium_speed_base_is_fifty_percent():
    # [5.6]: "... 50%..., from medium-speed monsters or other characters".
    assert effective_flee_chance(FLEE_CHANCE[MonsterSpeed.MEDIUM], temper=None, is_invisible=False) == 0.50


def test_effective_flee_chance_weak_temper_adds_its_own_bonus():
    assert effective_flee_chance(0.50, temper=Temper.CAUTIOUS, is_invisible=False) == pytest.approx(
        0.50 + WEAK_TEMPER_FLEE_CHANCE_BONUS
    )
    assert effective_flee_chance(0.50, temper=Temper.COWARDLY, is_invisible=False) == pytest.approx(
        0.50 + WEAK_TEMPER_FLEE_CHANCE_BONUS
    )
    assert effective_flee_chance(0.50, temper=Temper.BRAVE, is_invisible=False) == 0.50


def test_effective_flee_chance_invisibility_adds_its_own_bonus_independently_of_temper():
    assert effective_flee_chance(0.20, temper=None, is_invisible=True) == pytest.approx(
        0.20 + INVISIBILITY_FLEE_CHANCE_BONUS
    )


def test_effective_flee_chance_melee_evasion_adds_its_own_bonus_independently():
    assert effective_flee_chance(0.20, temper=None, is_invisible=False, has_melee_evasion=True) == pytest.approx(
        0.20 + MELEE_EVASION_FLEE_CHANCE_BONUS
    )


def test_effective_flee_chance_bonuses_stack_and_clamp_at_certainty():
    assert effective_flee_chance(0.80, temper=Temper.CAUTIOUS, is_invisible=True) == 1.0


def test_effective_flee_chance_air_elemental_familiar_guarantees_success():
    # Office.ELE_MAGE -- "all flee attempts are automatically successful,"
    # an unconditional override, not another additive bonus.
    assert effective_flee_chance(
        0.20, temper=Temper.BRAVE, is_invisible=False, has_air_elemental_familiar=True
    ) == 1.0


def test_resolve_challenge_combat_flee_tactic_success_ends_the_encounter():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.FLEE)]

    outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([0.49]))

    assert outcome.fled is True
    assert outcome.winner is None


def test_resolve_challenge_combat_flee_tactic_failure_falls_through_to_the_next_tactic():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.FLEE), SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([0.50])
        )

    assert outcome.fled is False
    assert outcome.winner == "a"
    mock_duel.assert_called_once()


def test_resolve_challenge_combat_flee_only_plan_still_falls_through_to_the_exhausted_list_melee_default():
    # A failed, standalone Flee tactic is the plan's own last (only)
    # tactic -- the pre-existing "exhausted tactic list defaults to
    # Melee" rule still applies, now reached via a real Flee branch
    # instead of the old unwired-tactic fallthrough.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.FLEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([0.99])
        )

    assert outcome.fled is False
    assert outcome.winner == "b"
    mock_duel.assert_called_once()


def test_resolve_challenge_combat_flee_tactic_temper_bonus_reaches_through():
    state, caster_leader, caster, target_leader, target = _combatants(caster_kwargs={"temper": Temper.COWARDLY})
    tactics = [SearchTactic(Maneuver.FLEE)]

    # 0.79 fails the bare 50% base but succeeds once Cowardly's own +30%
    # is applied (0.50 + 0.30 = 0.80) -- proves the real LeaderState.temper
    # reaches the roll, not just the formula in isolation.
    outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([0.79]))

    assert outcome.fled is True


def test_resolve_challenge_combat_flee_tactic_melee_evasion_bonus_reaches_through():
    state, caster_leader, caster, target_leader, target = _combatants()
    caster_leader.advanced_abilities.add(AdvancedAbility.MELEE_EVASION)
    tactics = [SearchTactic(Maneuver.FLEE)]

    outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([0.79]))

    assert outcome.fled is True


def test_resolve_challenge_combat_flee_tactic_with_no_real_caster_leader_uses_degraded_defaults():
    # caster_leader=None only for turn/battle_orchestrator.py's own Duel/
    # garrison-commander reuse (Phase 291) -- no real LeaderState to read
    # Temper/abilities/Office from, so the flee roll uses the bare 50%
    # base with no crash.
    state, _caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.FLEE)]

    outcome = resolve_challenge_combat(tactics, None, caster, target_leader, target, state, ScriptedRandom([0.49]))

    assert outcome.fled is True


def test_resolve_cast_disruption_words_of_healing_uses_its_own_halved_damage_formula():
    # Phase 730: SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT = 0.5/3, so 3
    # damage points is exactly 50% for an ordinary spell, 25% halved.
    tactic = SearchTactic(Maneuver.CAST, Spell.HEAL.value)
    assert _resolve_cast_disruption(tactic, 3, ScriptedRandom([0.3])) is False
    assert _resolve_cast_disruption(tactic, 3, ScriptedRandom([0.2])) is True


def test_resolve_cast_disruption_words_of_healing_uses_its_own_halved_missed_attack_chance():
    # Flat 30% ordinarily, 15% halved.
    tactic = SearchTactic(Maneuver.CAST, Spell.HEAL.value)
    assert _resolve_cast_disruption(tactic, 0, ScriptedRandom([0.2])) is False
    assert _resolve_cast_disruption(tactic, 0, ScriptedRandom([0.1])) is True


def test_resolve_cast_disruption_a_different_spell_uses_the_generic_formula():
    tactic = SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)
    assert _resolve_cast_disruption(tactic, 3, ScriptedRandom([0.4])) is True  # 0.4 < 0.5, the un-halved rate
    assert _resolve_cast_disruption(tactic, 0, ScriptedRandom([0.25])) is True  # 0.25 < the un-halved 30%


def test_resolve_cast_disruption_with_no_pending_cast_uses_the_generic_formula():
    assert _resolve_cast_disruption(None, 3, ScriptedRandom([0.4])) is True


def test_resolve_cast_disruption_with_an_out_of_range_sub_object_uses_the_generic_formula():
    # A non-CAST tactic (or any tactic whose own sub_object isn't a real
    # Spell ordinal) never crashes -- falls through to the generic roll.
    tactic = SearchTactic(Maneuver.MELEE)
    assert _resolve_cast_disruption(tactic, 3, ScriptedRandom([0.4])) is True


def test_resolve_challenge_combat_reactive_swing_killing_the_caster_ends_combat_immediately():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    caster.hit_points = 1
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    def _lethal_swing(attacker, defender, rng):
        defender.hit_points -= 5
        return ReactiveMeleeSwingResult(hit=True, damage=5)

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing", side_effect=_lethal_swing
    ), patch("ak_engine.turn.challenge_execution.resolve_spell_disruption") as mock_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast"
    ) as mock_cast:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert outcome.winner == "b"
    assert not mock_disrupt.called  # dead before a disruption check would even matter
    assert not mock_cast.called


def test_resolve_challenge_combat_cast_at_spell_range_never_checks_disruption():
    # Unchanged, established scope: disruption is only checked at
    # MELEE_RANGE -- a CAST as the very first tactic (still SPELL_RANGE)
    # never rolls it, matching every pre-Phase-292 CAST test unaffected.
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_reactive_melee_swing") as mock_swing, patch(
        "ak_engine.turn.challenge_execution.resolve_spell_disruption"
    ) as mock_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.challenge_execution.words_of_healing_heal"), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert not mock_swing.called
    assert not mock_disrupt.called


# -- Phase 732: combat_slots_per_school / same_combat_spell_may_repeat_in_encounter --


def test_resolve_challenge_combat_casters_own_cast_slot_level_1_blocks_a_second_different_spell():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.ELEMENTAL, 1, 9)}
    )
    tactics = [SearchTactic(Maneuver.CAST, Spell.FIREBALL.value), SearchTactic(Maneuver.CAST, Spell.ICE_SUSPEND.value)]

    with patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_cast.call_count == 1  # the 2nd attempt never reached the roll -- slot exhausted


def test_resolve_challenge_combat_casters_own_cast_slot_level_2_allows_two_different_spells():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.ELEMENTAL, 2, 9)}
    )
    tactics = [SearchTactic(Maneuver.CAST, Spell.FIREBALL.value), SearchTactic(Maneuver.CAST, Spell.ICE_SUSPEND.value)]

    with patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_cast.call_count == 2


def test_resolve_challenge_combat_casters_own_same_spell_never_repeats_even_with_slots_free():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.ELEMENTAL, 2, 9)}
    )
    tactics = [SearchTactic(Maneuver.CAST, Spell.FIREBALL.value), SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    with patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_cast.call_count == 1


def test_resolve_challenge_combat_caster_and_target_cast_slots_track_independently():
    # The target's own leading Cast(s) (`target_tactics`, resolved via
    # `_resolve_target_casts()` before the caster's own tactics even
    # start) must never share a slot pool with the caster's own side,
    # even for the identical Ability.
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.ELEMENTAL, 2, 9)},
        target_kwargs={"skills": _skills_with(Ability.ELEMENTAL, 2, 9)},
    )
    tactics = [SearchTactic(Maneuver.CAST, Spell.FIREBALL.value), SearchTactic(Maneuver.CAST, Spell.ICE_SUSPEND.value)]
    target_tactics = [
        SearchTactic(Maneuver.CAST, Spell.FIREBALL.value),
        SearchTactic(Maneuver.CAST, Spell.ICE_SUSPEND.value),
    ]

    with patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]), target_tactics=target_tactics
        )

    assert mock_cast.call_count == 4  # 2 real rolls per side


# -- Phase 294: apply_temper_melee_setup fix for the non-last MELEE branch --


def test_resolve_challenge_combat_non_last_melee_applies_temper_setup_before_the_first_round():
    # A real bug found while building the analogous engine in turn/
    # search_execution.py (Phase 293): the non-last-MELEE round-stepping
    # branch never called apply_temper_melee_setup() at all, so a
    # Berserk caster's own bonus hit points (turn/encounter.py's own
    # Phase 284 addendum) silently never applied for this specific plan
    # shape. resolve_one_melee_round() is mocked (undecided) so only the
    # setup step's own effect is observed.
    state, caster_leader, caster, target_leader, target = _combatants(caster_kwargs={"temper": Temper.BERSERK})
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        # mock_duel guards the exhausted-tactic-list fallback (reached
        # once TALK, unwired, falls through) -- unmocked, it would run a
        # second, real apply_temper_melee_setup() internally and muddy
        # this test's own isolated observation of the fix's own single
        # explicit call.
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, random.Random(0))

    assert CHARACTER_HIT_POINTS < caster.hit_points <= CHARACTER_HIT_POINTS + 4


def test_resolve_challenge_combat_non_last_melee_only_applies_temper_setup_once():
    # Two separate non-last MELEE tactics (a genuinely new plan shape,
    # but a real one this project must not silently mishandle) must not
    # double-apply Berserk's own bonus hit points or consume an extra
    # roll the second time around.
    state, caster_leader, caster, target_leader, target = _combatants(caster_kwargs={"temper": Temper.BERSERK})
    tactics = [
        SearchTactic(Maneuver.MELEE),
        SearchTactic(Maneuver.TALK),
        SearchTactic(Maneuver.MELEE),
        SearchTactic(Maneuver.TALK),
    ]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.apply_temper_melee_setup"
    ) as mock_setup, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_setup.call_count == 1


# -- Phase 297: the exhausted-fallback's own resolve_melee_duel() call must
# not re-apply Temper setup a second time --


def test_resolve_challenge_combat_non_last_melee_trailing_fallback_does_not_double_apply_temper_setup():
    # A real bug found in a dedicated bug-hunt audit: Phase 294's own fix
    # only guarded the *explicit* apply_temper_melee_setup() call before
    # round-stepping -- but resolve_melee_duel() itself always applies
    # setup again, internally, and the exhausted-tactic-list fallback
    # calls it unconditionally. So a non-last MELEE (round-stepping,
    # setup applied once) followed by an unwired tactic (TALK, falling
    # through to the fallback's own atomic resolve_melee_duel()) really
    # did apply Cautious' own dodge multiplier twice: 1.0 -> 0.9 -> 0.81
    # instead of the intended single 0.9. Unlike the two tests above,
    # resolve_melee_duel() is genuinely NOT mocked here -- the whole
    # point is observing its own real internal behavior.
    state, caster_leader, caster, target_leader, target = _combatants(caster_kwargs={"temper": Temper.CAUTIOUS})
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, random.Random(0))

    assert caster.defensive_hit_multiplier == pytest.approx(0.9)


# -- Phase 674: the target's own Special Encounter Plan (rulebook [5.10], --
# -- "used in every Encounter solicited by another character") ------------


def test_resolve_challenge_combat_target_tactics_none_never_consults_the_target_plan():
    # The default -- every pre-Phase-674 caller/test above already
    # proves this byte-for-byte via the full unmodified suite, but this
    # pins it directly: an explicit target_tactics=None with a lone
    # last MELEE still takes the atomic fast path.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel, patch(
        "ak_engine.turn.challenge_execution.resolve_one_melee_round"
    ) as mock_round:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]), target_tactics=None
        )

    assert mock_duel.called
    assert not mock_round.called
    assert outcome.winner == "a"


def test_resolve_challenge_combat_targets_leading_cast_resolves_before_any_caster_tactic():
    # Mirrors search_execution.py's own _resolve_monster_casts() burst --
    # the target's own leading Cast fires before the caster's own first
    # tactic even runs, regardless of what that tactic is.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]
    target_tactics = [SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    with patch(
        "ak_engine.turn.challenge_execution._resolve_personal_combat_cast", return_value="a"
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        outcome = resolve_challenge_combat(
            tactics,
            caster_leader,
            caster,
            target_leader,
            target,
            state,
            ScriptedRandom([]),
            target_tactics=target_tactics,
        )

    assert mock_cast.called
    # the target played the "caster" role in that inner call, so its own
    # "a" (that call's caster wins) flips to this function's own "b".
    assert outcome.winner == "b"
    assert not mock_duel.called  # the burst already ended the encounter


def test_resolve_challenge_combat_target_leading_cast_that_resolves_nothing_lets_the_caster_proceed():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]
    target_tactics = [SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    with patch(
        "ak_engine.turn.challenge_execution._resolve_personal_combat_cast", return_value=None
    ), patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics,
            caster_leader,
            caster,
            target_leader,
            target,
            state,
            ScriptedRandom([]),
            target_tactics=target_tactics,
        )

    assert mock_duel.called  # the target's own cast fizzled -- the caster's own Melee still runs
    assert outcome.winner == "a"


def test_resolve_challenge_combat_targets_pending_later_cast_disables_the_atomic_fast_path():
    # target_tactics' own immediate action is Melee (no leading cast to
    # burst), but a Cast further down its own plan must still disable
    # the atomic fast path -- mirrors search_execution.py's own
    # _monster_has_more_casts_pending() lookahead exactly.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]
    target_tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=False, damage=0),
    ), patch(
        "ak_engine.turn.challenge_execution.resolve_spell_disruption_from_missed_attack", return_value=False
    ), patch(
        "ak_engine.turn.challenge_execution._resolve_personal_combat_cast", return_value="b"
    ) as mock_cast:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        outcome = resolve_challenge_combat(
            tactics,
            caster_leader,
            caster,
            target_leader,
            target,
            state,
            ScriptedRandom([]),
            target_tactics=target_tactics,
        )

    assert mock_round.called  # round-stepped, not the atomic duel
    assert not mock_duel.called
    assert mock_cast.called  # the target's own later Cast eventually got its turn
    assert outcome.winner == "a"  # inner "b" (that call's target wins) flips to outer "a"


def test_resolve_challenge_combat_melee_vs_target_cast_caster_swing_lands_first():
    # [5.1]'s own melee-precedence rule: the caster's own swing at the
    # casting target happens before the target's own cast resolves.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]
    target_tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=3),
    ) as mock_swing, patch(
        "ak_engine.turn.challenge_execution.resolve_spell_disruption", return_value=False
    ) as mock_disrupt, patch(
        "ak_engine.turn.challenge_execution._resolve_personal_combat_cast", return_value=None
    ) as mock_cast, patch(
        # the target's own plan is now exhausted after this round, so the
        # exhausted-tactic-list tail's own atomic fast path re-engages --
        # a separate, already-tested concern, just given a decisive
        # winner here so this test can focus on the round just above it.
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        resolve_challenge_combat(
            tactics,
            caster_leader,
            caster,
            target_leader,
            target,
            state,
            ScriptedRandom([]),
            target_tactics=target_tactics,
        )

    assert mock_swing.called  # attacker="a" (the caster) -- not a reactive swing against the caster
    assert mock_disrupt.called
    assert mock_cast.called  # not disrupted -- the target's own cast still gets attempted


def test_resolve_challenge_combat_melee_vs_target_cast_disrupted_never_attempts_the_cast():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]
    target_tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=3),
    ), patch("ak_engine.turn.challenge_execution.resolve_spell_disruption", return_value=True), patch(
        "ak_engine.turn.challenge_execution._resolve_personal_combat_cast"
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        resolve_challenge_combat(
            tactics,
            caster_leader,
            caster,
            target_leader,
            target,
            state,
            ScriptedRandom([]),
            target_tactics=target_tactics,
        )

    assert not mock_cast.called  # disrupted -- the target's own cast never gets attempted


def test_resolve_challenge_combat_targets_leading_cast_can_end_with_the_caster_losing():
    # The leading-cast burst has no reactive swing of its own (only the
    # round-stepped Melee-vs-Cast branch does) -- the target's own
    # leading Cast just resolves directly and can decide the encounter
    # either way.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]
    target_tactics = [SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    with patch("ak_engine.turn.challenge_execution._resolve_personal_combat_cast", return_value="b") as mock_cast:
        outcome = resolve_challenge_combat(
            tactics,
            caster_leader,
            caster,
            target_leader,
            target,
            state,
            ScriptedRandom([]),
            target_tactics=target_tactics,
        )

    assert mock_cast.called
    # that inner call's "b" (its own target=caster wins) flips to this
    # function's own "a".
    assert outcome.winner == "a"


def test_resolve_challenge_combat_cast_vs_cast_both_sides_attempt_their_own_spell():
    # Caster orders CAST while the target's own peeked plan also wants
    # to Cast this round -- both attempt, no swings, no disruption.
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [
        SearchTactic(Maneuver.MELEE),  # closes range to MELEE_RANGE first
        SearchTactic(Maneuver.CAST, Spell.HEAL.value),
    ]
    target_tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)]

    caster_cast_calls = []
    target_cast_calls = []

    def _fake_cast(caster_arg, caster_leader_arg, target_arg, target_leader_arg, tactic, state_arg, rng_arg, *, is_first_tactic, **_kwargs):
        if caster_arg is caster:
            caster_cast_calls.append(tactic)
        else:
            target_cast_calls.append(tactic)
        return None

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=False, damage=0),
    ), patch(
        "ak_engine.turn.challenge_execution.resolve_spell_disruption_from_missed_attack", return_value=False
    ), patch(
        "ak_engine.turn.challenge_execution._resolve_personal_combat_cast", side_effect=_fake_cast
    ) as mock_cast, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        resolve_challenge_combat(
            tactics,
            caster_leader,
            caster,
            target_leader,
            target,
            state,
            ScriptedRandom([]),
            target_tactics=target_tactics,
        )

    assert mock_cast.called
    assert len(caster_cast_calls) == 1
    assert len(target_cast_calls) == 1  # the target's own later Cast also got attempted, same round


def test_resolve_challenge_combat_target_tactics_with_no_cast_at_all_behaves_like_none():
    # A real armyless target with an empty/Melee-only SEP is
    # indistinguishable from target_tactics=None throughout.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel, patch(
        "ak_engine.turn.challenge_execution.resolve_one_melee_round"
    ) as mock_round:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]), target_tactics=[]
        )

    assert mock_duel.called
    assert not mock_round.called
    assert outcome.winner == "a"


# -- Phase 305: character-vs-character Steal [ST], rulebook [5.5] ------


def test_apply_successful_theft_transfers_items_independently_with_a_halving_threshold():
    # Phase 506: the real formula scans every eligible item, not just the
    # first -- each rolls independently against a 75%-then-halved
    # threshold. Here: the Fisher-Yates shuffle over 2 items is a no-op
    # (0.5 * 2 == 1, swaps item[1] with itself); the first-scanned item's
    # own 75% roll (0.5) succeeds; the second-scanned item's own halved
    # 37% roll (0.9) fails.
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)
    first = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)
    second = state.add_item(Treasure.ABILITY_MARCH, owner_leader_id=2)

    # Trailing pair feeds Add_Experience's own `1 + random() - random()` spread.
    _apply_successful_theft(state, thief, victim, ScriptedRandom([0.5, 0.5, 0.9, 0.5, 0.5]))

    assert state.items[first.item_id].owner_leader_id == 1
    assert state.items[second.item_id].owner_leader_id == 2  # halved threshold roll failed


def test_apply_successful_theft_is_a_no_op_when_the_victim_holds_nothing():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)

    _apply_successful_theft(state, thief, victim, ScriptedRandom([0.5, 0.5]))  # must not raise

    assert state.items_held_by(1) == []


def test_apply_successful_theft_credits_the_thief_prince_merit_tally():
    # Phase 442: MeritTally.successful_thefts -- one of the real compiled
    # formula's own "two separate success paths" (thiefprince_merit_
    # points()'s own Phase 369 addendum). Credited regardless of whether
    # the victim actually held an item to take.
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)

    _apply_successful_theft(state, thief, victim, ScriptedRandom([0.5, 0.5]))
    _apply_successful_theft(state, thief, victim, ScriptedRandom([0.5, 0.5]))

    assert thief.merit_tally.successful_thefts == 2
    assert victim.merit_tally.successful_thefts == 0


def test_apply_successful_theft_also_awards_real_add_experience_credit():
    # Phase 457: AKGEN_reverse_engineering_report (2).md SS3.3's own
    # Thief row -- base 15, the shared LeaderState.experience_credit
    # counter (Phase 456) gains round(15*(1+0.5-0.5)) == 15.
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)

    _apply_successful_theft(state, thief, victim, ScriptedRandom([0.5, 0.5]))

    assert thief.experience_credit == 15


# -- Phase 443: Duellist/Cravenest/Bravest merit -------------------------


def test_apply_duel_encounter_merit_refusal_credits_stake_one_and_cravenest_penalty():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_duel_encounter_merit(
        challenger, target, accepted=False, winner_leader=None, loser_leader=None, challenger_combatant=None
    )

    assert challenger.merit_tally.duel_merit_net == 1
    assert target.merit_tally.duel_merit_net == -1
    assert target.merit_tally.courage_encounter_merit == -1
    assert challenger.merit_tally.courage_encounter_merit == 0
    assert challenger.merit_tally.bravery_merit == 0
    assert target.merit_tally.bravery_merit == 0


def test_apply_duel_encounter_merit_decisive_win_credits_stake_two_cravenest_and_bravery():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)
    # Challenger won but took 3 hit points of damage along the way.
    challenger_combatant = Combatant(name="Challenger", hit_points=CHARACTER_HIT_POINTS - 3)

    _apply_duel_encounter_merit(
        challenger,
        target,
        accepted=True,
        winner_leader=challenger,
        loser_leader=target,
        challenger_combatant=challenger_combatant,
    )

    assert challenger.merit_tally.duel_merit_net == 2
    assert target.merit_tally.duel_merit_net == -2
    assert target.merit_tally.courage_encounter_merit == -1
    assert challenger.merit_tally.courage_encounter_merit == 0
    assert challenger.merit_tally.bravery_merit == 3
    assert target.merit_tally.bravery_merit == 0


def test_apply_duel_encounter_merit_decisive_win_unscathed_credits_zero_bravery():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)
    challenger_combatant = Combatant(name="Challenger", hit_points=CHARACTER_HIT_POINTS)

    _apply_duel_encounter_merit(
        challenger,
        target,
        accepted=True,
        winner_leader=challenger,
        loser_leader=target,
        challenger_combatant=challenger_combatant,
    )

    assert challenger.merit_tally.bravery_merit == 0


def test_apply_duel_encounter_merit_target_wins_credits_no_bravery_to_anyone():
    # Bravest of the Brave only ever credits the protagonist (the
    # challenger) -- a target who successfully defends gets Duellist/
    # Cravenest credit but never Bravest, matching the source's own
    # protagonist-only semantics.
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)
    challenger_combatant = Combatant(name="Challenger", hit_points=CHARACTER_HIT_POINTS - 5)

    _apply_duel_encounter_merit(
        challenger,
        target,
        accepted=True,
        winner_leader=target,
        loser_leader=challenger,
        challenger_combatant=challenger_combatant,
    )

    assert target.merit_tally.duel_merit_net == 2
    assert challenger.merit_tally.duel_merit_net == -2
    assert challenger.merit_tally.courage_encounter_merit == -1
    assert target.merit_tally.bravery_merit == 0
    assert challenger.merit_tally.bravery_merit == 0


def test_apply_duel_encounter_merit_no_op_when_no_winner_or_loser():
    # Draw or magical escape (fled) -- excluded from all three titles.
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_duel_encounter_merit(
        challenger, target, accepted=True, winner_leader=None, loser_leader=None, challenger_combatant=None
    )

    assert challenger.merit_tally.duel_merit_net == 0
    assert target.merit_tally.duel_merit_net == 0
    assert challenger.merit_tally.courage_encounter_merit == 0
    assert target.merit_tally.courage_encounter_merit == 0
    assert challenger.merit_tally.bravery_merit == 0
    assert target.merit_tally.bravery_merit == 0


def test_execute_challenge_refusal_credits_duellist_and_cravenest_merit():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert state.leaders[1].merit_tally.duel_merit_net == 1
    assert state.leaders[2].merit_tally.duel_merit_net == -1
    assert state.leaders[2].merit_tally.courage_encounter_merit == -1
    assert state.leaders[1].merit_tally.bravery_merit == 0


def test_execute_challenge_decisive_combat_credits_duellist_cravenest_and_bravery_merit():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.winner_leader_id == 1
    winner = state.leaders[1]
    assert winner.merit_tally.duel_merit_net == 2
    assert winner.merit_tally.courage_encounter_merit == 0
    # B always missed in this scripted combat, so the winner took no damage.
    assert winner.merit_tally.bravery_merit == 0


def test_execute_challenge_fled_credits_no_duel_encounter_merit():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.CHARM, Maneuver.MELEE)

    result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.1]))

    assert result.fled is True
    assert state.leaders[1].merit_tally.duel_merit_net == 0
    assert state.leaders[2].merit_tally.duel_merit_net == 0
    assert state.leaders[1].merit_tally.courage_encounter_merit == 0
    assert state.leaders[2].merit_tally.courage_encounter_merit == 0


def test_execute_challenge_draw_credits_no_duel_encounter_merit():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    rng = ScriptedRandom([0.99] * 3000)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.winner_leader_id is None
    assert state.leaders[1].merit_tally.duel_merit_net == 0
    assert state.leaders[2].merit_tally.duel_merit_net == 0
    assert state.leaders[1].merit_tally.courage_encounter_merit == 0
    assert state.leaders[2].merit_tally.courage_encounter_merit == 0


# -- Phase 469: Bravest of the Brave's own Talk-triggered temper rise ---


def test_apply_bravest_talk_inspiration_raises_a_talking_heros_temper():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15  # meets OFFICE_MIN_POINTS[Office.BRAVEST]
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, temper=Temper.CAUTIOUS)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_bravest_talk_inspiration(state, challenger, target)

    assert target.temper is Temper.BRAVE


def test_apply_bravest_talk_inspiration_caps_at_berserk():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, temper=Temper.BERSERK)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_bravest_talk_inspiration(state, challenger, target)

    assert target.temper is Temper.BERSERK


def test_apply_bravest_talk_inspiration_does_not_inspire_a_king():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15
    target = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True, temper=Temper.CAUTIOUS)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_bravest_talk_inspiration(state, challenger, target)

    assert target.temper is Temper.CAUTIOUS


def test_apply_bravest_talk_inspiration_no_op_for_a_non_titleholder():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)  # bravery_merit defaults to 0
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, temper=Temper.CAUTIOUS)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_bravest_talk_inspiration(state, challenger, target)

    assert target.temper is Temper.CAUTIOUS


def test_apply_bravest_talk_inspiration_no_op_when_target_has_no_recorded_temper():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD)  # temper=None
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_bravest_talk_inspiration(state, challenger, target)

    assert target.temper is None


# -- Phase 697: Spy Brainwash's own Talk-triggered alignment shift ------


def test_apply_spy_brainwash_moves_target_one_step_toward_the_spys_alignment():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD, alignment=Alignment.EVIL)
    challenger.advanced_abilities.add(AdvancedAbility.SPY_BRAINWASH)
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, alignment=Alignment.NEUTRAL)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_spy_brainwash_alignment_shift(challenger, target)

    assert target.alignment is Alignment.PAGAN  # one ordinal step from Neutral toward Evil


def test_apply_spy_brainwash_moves_the_other_direction_too():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD, alignment=Alignment.DIVINE)
    challenger.advanced_abilities.add(AdvancedAbility.SPY_BRAINWASH)
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, alignment=Alignment.NEUTRAL)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_spy_brainwash_alignment_shift(challenger, target)

    assert target.alignment is Alignment.DRUID  # one ordinal step from Neutral toward Divine


def test_apply_spy_brainwash_no_op_once_already_aligned():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD, alignment=Alignment.NEUTRAL)
    challenger.advanced_abilities.add(AdvancedAbility.SPY_BRAINWASH)
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, alignment=Alignment.NEUTRAL)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_spy_brainwash_alignment_shift(challenger, target)

    assert target.alignment is Alignment.NEUTRAL


def test_apply_spy_brainwash_does_not_shift_a_king():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD, alignment=Alignment.EVIL)
    challenger.advanced_abilities.add(AdvancedAbility.SPY_BRAINWASH)
    target = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True, alignment=Alignment.NEUTRAL)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_spy_brainwash_alignment_shift(challenger, target)

    assert target.alignment is Alignment.NEUTRAL


def test_apply_spy_brainwash_no_op_without_the_advanced_ability():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD, alignment=Alignment.EVIL)
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, alignment=Alignment.NEUTRAL)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_spy_brainwash_alignment_shift(challenger, target)

    assert target.alignment is Alignment.NEUTRAL


def test_apply_spy_brainwash_no_op_when_either_alignment_is_unrecorded():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD)  # alignment=None
    challenger.advanced_abilities.add(AdvancedAbility.SPY_BRAINWASH)
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, alignment=Alignment.NEUTRAL)
    state.add_leader(challenger)
    state.add_leader(target)

    _apply_spy_brainwash_alignment_shift(challenger, target)

    assert target.alignment is Alignment.NEUTRAL


def test_execute_challenge_peaceful_talk_plan_shifts_the_targets_alignment():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Spy", location=FIELD, alignment=Alignment.EVIL)
    challenger.advanced_abilities.add(AdvancedAbility.SPY_BRAINWASH)
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, alignment=Alignment.NEUTRAL)
    state.add_leader(challenger)
    state.add_leader(target)

    result = execute_challenge(state, 1, _peaceful_request(2), rng=ScriptedRandom([]))

    assert result == ChallengeExecutionResult(accepted=True, combat_occurred=False)
    assert state.leaders[2].alignment is Alignment.PAGAN


def _talk_then_melee_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(
        target_character_id=target_id,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(Maneuver.TALK), SearchTactic(Maneuver.MELEE)],
    )


def test_execute_challenge_peaceful_talk_plan_inspires_the_titleholders_hero_target():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, temper=Temper.CAUTIOUS)
    state.add_leader(challenger)
    state.add_leader(target)

    result = execute_challenge(state, 1, _peaceful_request(2), rng=ScriptedRandom([]))

    assert result == ChallengeExecutionResult(accepted=True, combat_occurred=False)
    assert state.leaders[2].temper is Temper.BRAVE


def test_execute_challenge_repeated_talk_tactics_inspire_only_one_temper_level():
    # SS18.8: "la prosa del titolo... limita... a una sola tattica Talk
    # utile nello stesso incontro" -- two TALK entries in the same plan
    # still only raise the target's temper by one level.
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, temper=Temper.CAUTIOUS)
    state.add_leader(challenger)
    state.add_leader(target)
    request = ChallengeRequest(
        target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK), SearchTactic(Maneuver.TALK)]
    )

    execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert state.leaders[2].temper is Temper.BRAVE


def test_execute_challenge_bravest_inspiration_also_fires_alongside_accepted_combat():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15
    target = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, temper=Temper.CAUTIOUS)
    state.add_leader(challenger)
    state.add_leader(target)
    # Armyless Hero-vs-Hero always accepts without consuming a roll; the
    # combat itself is scripted to a draw (same all-misses sequence as
    # test_execute_challenge_draw_credits_no_duel_encounter_merit above).
    rng = ScriptedRandom([0.99] * 3000)

    result = execute_challenge(state, 1, _talk_then_melee_request(2), rng=rng)

    assert result.accepted is True
    assert result.winner_leader_id is None
    assert state.leaders[2].temper is Temper.BRAVE


def test_execute_challenge_bravest_inspiration_does_not_fire_when_encounter_is_refused():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Bard", location=FIELD)
    challenger.merit_tally.bravery_merit = 15
    target = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True, temper=Temper.CAUTIOUS)
    state.add_leader(challenger)
    state.add_leader(target)

    result = execute_challenge(state, 1, _talk_then_melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert state.leaders[2].temper is Temper.CAUTIOUS


def _thief_combatant() -> Combatant:
    return Combatant(name="Thief", hit_points=CHARACTER_HIT_POINTS)


def test_resolve_steal_tactic_success_applies_theft():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)

    # 0.1 < 15% base success chance; then a single-item scan, whose own
    # 75% transfer roll (0.5) succeeds; the trailing pair feeds Add_
    # Experience's own `1 + random() - random()` spread.
    outcome, _, stolen_item_ids = _resolve_steal_tactic(
        thief, _thief_combatant(), victim, state, ScriptedRandom([0.1, 0.5, 0.5, 0.5])
    )

    assert outcome == "success"
    assert stolen_item_ids == [item.item_id]
    assert state.items[item.item_id].owner_leader_id == 1


def test_resolve_steal_tactic_failure_then_evaded_leaves_no_trace():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)

    # 0.2 fails the 15% base success chance; 0.09 < 10% base evasion chance.
    outcome, _, _ = _resolve_steal_tactic(thief, _thief_combatant(), victim, state, ScriptedRandom([0.2, 0.09]))

    assert outcome == "evaded"


def test_resolve_steal_tactic_hero_thief_caught_robbing_a_king_is_executed():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)

    outcome, _, _ = _resolve_steal_tactic(thief, _thief_combatant(), king, state, ScriptedRandom([0.5, 0.5]))  # fail attempt, fail evasion

    assert outcome == "executed"


def test_resolve_steal_tactic_hero_thief_caught_robbing_an_army_commanding_hero_is_executed():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    general = LeaderState(2, kingdom_id=2, name="General", location=FIELD)
    state.add_leader(thief)
    state.add_leader(general)
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    outcome, _, _ = _resolve_steal_tactic(thief, _thief_combatant(), general, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "executed"


def test_resolve_steal_tactic_king_vs_king_caught_pays_half_treasury_as_ransom():
    state = _base_state()
    state.kingdoms[1].treasury = 100
    thief_king = LeaderState(1, kingdom_id=1, name="Thief King", location=FIELD, is_king=True)
    victim_king = LeaderState(2, kingdom_id=2, name="Victim King", location=FIELD, is_king=True)
    state.add_leader(thief_king)
    state.add_leader(victim_king)

    outcome, _, _ = _resolve_steal_tactic(thief_king, _thief_combatant(), victim_king, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "ransom"
    # Phase 506: ceil(treasury/2), transferred to the victim's own
    # kingdom -- not merely subtracted from the thief's, per the real
    # ransom formula's own bug fix (module docstring's own addendum).
    assert state.kingdoms[1].treasury == 50
    assert state.kingdoms[2].treasury == 50


def test_resolve_steal_tactic_king_vs_king_caught_with_no_gold_is_executed():
    state = _base_state()
    state.kingdoms[1].treasury = 0
    thief_king = LeaderState(1, kingdom_id=1, name="Thief King", location=FIELD, is_king=True)
    victim_king = LeaderState(2, kingdom_id=2, name="Victim King", location=FIELD, is_king=True)
    state.add_leader(thief_king)
    state.add_leader(victim_king)

    outcome, _, _ = _resolve_steal_tactic(thief_king, _thief_combatant(), victim_king, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "executed"
    assert state.kingdoms[1].treasury == 0


def test_resolve_steal_tactic_caught_targeting_a_non_army_hero_is_combat():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    hero = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD)
    state.add_leader(thief)
    state.add_leader(hero)

    outcome, _, _ = _resolve_steal_tactic(thief, _thief_combatant(), hero, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "combat"


def test_resolve_steal_tactic_king_caught_targeting_a_non_army_hero_is_also_combat():
    state = _base_state()
    king = LeaderState(1, kingdom_id=1, name="King", location=FIELD, is_king=True)
    hero = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD)
    state.add_leader(king)
    state.add_leader(hero)

    outcome, _, _ = _resolve_steal_tactic(king, _thief_combatant(), hero, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "combat"


def test_resolve_steal_tactic_king_thief_caught_robbing_a_non_king_army_hero_pays_ransom():
    # Phase 526: AKGEN_reverse_engineering_report (3).md SS42's own
    # capture table pays the same ransom whether the victim is
    # personally the King or merely an army-commanding Hero -- see
    # module docstring's own Phase 526 addendum. This combination used
    # to be "unresolved" (Phase 305) before that source was found.
    state = _base_state()
    state.kingdoms[1].treasury = 100
    king = LeaderState(1, kingdom_id=1, name="King", location=FIELD, is_king=True)
    general = LeaderState(2, kingdom_id=2, name="General", location=FIELD)
    state.add_leader(king)
    state.add_leader(general)
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    outcome, _, _ = _resolve_steal_tactic(king, _thief_combatant(), general, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "ransom"
    assert state.kingdoms[1].treasury == 50
    assert state.kingdoms[2].treasury == 50


def test_resolve_steal_tactic_king_thief_caught_robbing_a_non_king_army_hero_with_no_gold_is_executed():
    # Same Phase 526 sourcing -- an empty thief treasury executes
    # regardless of whether the victim is a King or an army-commanding
    # Hero, matching the King-vs-King no-gold branch exactly.
    state = _base_state()
    state.kingdoms[1].treasury = 0
    king = LeaderState(1, kingdom_id=1, name="King", location=FIELD, is_king=True)
    general = LeaderState(2, kingdom_id=2, name="General", location=FIELD)
    state.add_leader(king)
    state.add_leader(general)
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    outcome, _, _ = _resolve_steal_tactic(king, _thief_combatant(), general, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "executed"
    assert state.kingdoms[1].treasury == 0


def test_resolve_steal_tactic_is_unresolved_with_no_rng_consumed_for_a_missing_leaderstate():
    # A garrison commander (Phase 291's own Duel reuse) has no LeaderState.
    state = _base_state()
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(target)

    # any .random() call would raise
    outcome, _, _ = _resolve_steal_tactic(None, _thief_combatant(), target, state, ScriptedRandom([]))

    assert outcome == "unresolved"


def test_resolve_challenge_combat_steal_executed_ends_the_encounter():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value=("executed", 0, [])):
        outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert outcome.winner == "b"
    assert outcome.steal_outcome == "executed"


def test_resolve_challenge_combat_steal_success_lets_the_plan_continue():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL), SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value=("success", 0, [])), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert outcome.winner == "a"
    assert outcome.steal_outcome == "success"


def test_resolve_challenge_combat_steal_capture_combat_at_spell_range_lets_a_following_melee_tactic_decide():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL), SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value=("combat", 0, [])), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([], choice_indices=[0])
        )

    assert outcome.winner == "a"  # decided by the following MELEE tactic, not an atomic Steal-side duel
    assert outcome.steal_outcome == "combat"
    assert outcome.steal_capture_range is CombatRange.SPELL_RANGE


def test_resolve_challenge_combat_steal_capture_sets_the_rolled_range_and_falls_through_to_the_exhausted_default():
    # Phase 306 correction: no follow-up tactic after STEAL -- being
    # caught no longer atomically resolves its own duel, so this falls
    # through to the pre-existing "exhausted tactic list defaults to
    # Melee" tail, the same way an unwired trailing tactic already would.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value=("combat", 0, [])), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([], choice_indices=[1])
        )

    assert outcome.winner == "b"
    assert outcome.steal_outcome == "combat"
    assert outcome.steal_capture_range is CombatRange.BOW_RANGE
    mock_duel.assert_called_once()  # the exhausted-list tail, not an atomic Steal-side resolution


def test_resolve_challenge_combat_steal_capture_at_melee_range_then_a_following_melee_tactic_resolves_once():
    # [11.3]'s own worked example ("CA-IN, ST, FL, ME"): getting caught
    # hands control to the plan's own next tactic. Phase 743: FLEE is now
    # wired (base 50%, no bonuses on this fixture's default leaders) --
    # scripted to fail (0.50, not < 0.50) so the following MELEE still
    # picks up from the rolled range without re-closing it.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL), SearchTactic(Maneuver.FLEE), SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value=("combat", 0, [])), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([0.50], choice_indices=[2])
        )

    assert outcome.winner == "b"
    assert outcome.steal_outcome == "combat"
    assert outcome.steal_capture_range is CombatRange.MELEE_RANGE
    mock_duel.assert_called_once()


# -- Phase 674: execute_challenge() threads a real armyless target's own --
# -- special_encounter_plan into resolve_challenge_combat() ---------------


def test_execute_challenge_threads_an_armyless_targets_special_encounter_plan():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    target.special_encounter_plan = (SearchTactic(Maneuver.CAST, Spell.FIREBALL.value),)
    state.add_leader(challenger)
    state.add_leader(target)
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_challenge_combat") as mock_resolve:
        mock_resolve.return_value = ChallengeCombatOutcome(winner="a")
        execute_challenge(state, 1, ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=tactics))

    assert mock_resolve.called
    assert mock_resolve.call_args.kwargs["target_tactics"] == list(target.special_encounter_plan)


# -- Phase 686: Melee/Archery combat-experience wiring --


def test_execute_challenge_landed_melee_hit_credits_the_challenger():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = ChallengeCombatOutcome(
            winner="a", melee_swings=(MeleeSwing(attacker="a", hit=True, damage=3),)
        )
        execute_challenge(state, 1, ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=tactics))

    mock_add_experience.assert_any_call(challenger, Ability.MELEE, 10, ANY)


def test_execute_challenge_landed_melee_hit_credits_the_target_independently():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = ChallengeCombatOutcome(
            winner="b", melee_swings=(MeleeSwing(attacker="b", hit=True, damage=3),)
        )
        execute_challenge(state, 1, ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=tactics))

    mock_add_experience.assert_any_call(target, Ability.MELEE, 10, ANY)
    for call in mock_add_experience.call_args_list:
        assert call.args[0] is not challenger


def test_execute_challenge_landed_fire_arrow_shot_credits_the_challenger():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)
    tactics = [SearchTactic(Maneuver.SHOOT)]

    with patch("ak_engine.turn.challenge_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = ChallengeCombatOutcome(
            winner="a", fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=4),)
        )
        execute_challenge(state, 1, ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=tactics))

    mock_add_experience.assert_any_call(challenger, Ability.ARCHERY, 10, ANY)


def test_execute_challenge_all_miss_credits_nothing():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(challenger)
    state.add_leader(target)
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_challenge_combat") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = ChallengeCombatOutcome(
            winner=None,
            melee_swings=(MeleeSwing(attacker="a", hit=False, damage=0), MeleeSwing(attacker="b", hit=False, damage=0)),
        )
        execute_challenge(state, 1, ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=tactics))

    mock_add_experience.assert_not_called()


def test_execute_challenge_never_threads_an_army_commanding_targets_plan():
    # An ordinary (non-King) army-commanding target always refuses the
    # encounter outright (is_encounter_accepted's own real rule) --
    # resolve_challenge_combat() is never even reached for that case, so
    # this uses a King target with mutual_encounter=True (acceptance
    # independent of army command) to actually exercise the gate.
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="A", location=FIELD)
    target = LeaderState(2, kingdom_id=2, name="B", location=FIELD, is_king=True)
    target.special_encounter_plan = (SearchTactic(Maneuver.CAST, Spell.FIREBALL.value),)
    state.add_leader(challenger)
    state.add_leader(target)
    state.add_army(ArmyState(201, 2, ArmyType.AXEMEN, Quality.AVERAGE, FIELD, commanded_by=2))
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_challenge_combat") as mock_resolve:
        mock_resolve.return_value = ChallengeCombatOutcome(winner="a")
        execute_challenge(
            state,
            1,
            ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=tactics),
            mutual_encounter=True,
        )

    assert mock_resolve.called
    assert mock_resolve.call_args.kwargs["target_tactics"] is None


def test_execute_challenge_spy_assassinate_accepts_a_king_target_non_mutually():
    # Phase 698: a King target would normally require mutual_encounter=
    # True to be accepted at all -- the ability bypasses that
    # unconditionally, even for a non-mutual encounter.
    state = _base_state()
    challenger = LeaderState(
        1, kingdom_id=1, name="Spy", location=FIELD, advanced_abilities={AdvancedAbility.SPY_ASSASSINATE}
    )
    target = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(challenger)
    state.add_leader(target)

    with patch("ak_engine.turn.challenge_execution.resolve_challenge_combat") as mock_resolve:
        mock_resolve.return_value = ChallengeCombatOutcome(winner=None)
        result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is True
    assert result.combat_occurred is True


# -- Phase 700: AdvancedAbility.LONG_RANGE_ARCHERY -----------------------


def test_resolve_challenge_combat_long_range_archery_fires_from_spell_range():
    state = _base_state()
    caster_leader = LeaderState(
        1, kingdom_id=1, name="Archer", location=FIELD, advanced_abilities={AdvancedAbility.LONG_RANGE_ARCHERY}
    )
    target_leader = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)

    with patch("ak_engine.turn.challenge_execution.resolve_fire_arrow_duel") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(
            [SearchTactic(Maneuver.SHOOT)], caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    mock_resolve.assert_called_once_with(caster, target, ANY, long_range_archer="a")


def test_resolve_challenge_combat_without_the_ability_closes_to_bow_range():
    # Non-regression: the ordinary close-to-Bow-Range behavior is
    # unchanged for a caster who doesn't hold the ability.
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="Archer", location=FIELD)
    target_leader = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)

    with patch("ak_engine.turn.challenge_execution.resolve_fire_arrow_duel") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(
            [SearchTactic(Maneuver.SHOOT)], caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    mock_resolve.assert_called_once_with(caster, target, ANY)


def test_resolve_challenge_combat_no_caster_leader_closes_to_bow_range():
    # Phase 291's own garrison/Duel-reuse case: no real LeaderState, so
    # no Advanced Ability to check -- falls back to ordinary behavior.
    state = _base_state()
    target_leader = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(target_leader)
    caster = Combatant(name="Garrison", hit_points=CHARACTER_HIT_POINTS)
    target = _leader_combatant(target_leader, state)

    with patch("ak_engine.turn.challenge_execution.resolve_fire_arrow_duel") as mock_resolve, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(
            [SearchTactic(Maneuver.SHOOT)], None, caster, target_leader, target, state, ScriptedRandom([])
        )

    mock_resolve.assert_called_once_with(caster, target, ANY)


# -- Phase 701: AdvancedAbility.SHORT_RANGE_ARCHERY ----------------------


def test_resolve_challenge_combat_short_range_archery_fires_with_a_reactive_swing_first():
    # Range closes to MELEE_RANGE via the leading Melee tactic (mocked to
    # a no-decision round); the ability then lets the second, SHOOT
    # tactic fire anyway -- the target gets a free reactive Melee swing
    # against the archer first (mirroring the Cast-at-Melee-Range
    # pattern), then a one-sided shot with no return fire.
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"advanced_abilities": {AdvancedAbility.SHORT_RANGE_ARCHERY}}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.SHOOT)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=2),
    ) as mock_swing, patch(
        "ak_engine.turn.challenge_execution.resolve_fire_arrow_duel"
    ) as mock_shoot, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    mock_swing.assert_called_once_with(target, caster, ANY)
    mock_shoot.assert_called_once_with(caster, target, ANY, short_range_archer="a")


def test_resolve_challenge_combat_short_range_archery_ends_early_if_the_swing_kills_the_archer():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"advanced_abilities": {AdvancedAbility.SHORT_RANGE_ARCHERY}}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.SHOOT)]

    def _lethal_swing(attacker, defender, rng):
        defender.hit_points = 0
        return ReactiveMeleeSwingResult(hit=True, damage=defender.hit_points)

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing", side_effect=_lethal_swing
    ), patch("ak_engine.turn.challenge_execution.resolve_fire_arrow_duel") as mock_shoot:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert outcome.winner == "b"
    assert not mock_shoot.called  # the archer died to the counter-swing before ever firing


def test_resolve_challenge_combat_without_short_range_archery_still_blocks_shoot_at_melee_range():
    # Non-regression: [5.0]'s own existing block stays in force for a
    # caster who doesn't hold the ability.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.SHOOT)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_fire_arrow_duel"
    ) as mock_shoot, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert not mock_shoot.called
    assert mock_duel.called  # falls through to the atomic fallback afterward


# -- Phase 702: AdvancedAbility.THIEF_TREASURY_RAIDS ---------------------


def test_apply_treasury_raid_moves_gold_not_items():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)
    state.kingdoms[2].treasury = 1000
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)

    # Phase 785: 0.5 -> treasury_raid_amount(1000, ...) = round(500*0.625)
    # = 312; trailing pair feeds Add_Experience's own spread.
    amount = _apply_treasury_raid(state, thief, king, ScriptedRandom([0.5, 0.5, 0.5]))

    assert amount == 312
    assert state.kingdoms[2].treasury == 688
    assert state.kingdoms[1].treasury == 312
    assert state.items[item.item_id].owner_leader_id == 2  # untouched -- gold, not items
    assert thief.merit_tally.successful_thefts == 1


def test_apply_treasury_raid_kingdomless_thief_keeps_the_gold_off_the_books():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=None, name="Wandering Thief", location=FIELD)
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)
    state.kingdoms[2].treasury = 1000

    # Phase 785: 0.5 -> treasury_raid_amount(1000, ...) = round(500*0.625) = 312.
    amount = _apply_treasury_raid(state, thief, king, ScriptedRandom([0.5, 0.5, 0.5]))

    assert amount == 312
    assert state.kingdoms[2].treasury == 688  # still deducted from the victim
    assert state.kingdoms[1].treasury == 0  # nowhere for a kingdomless thief to bank it


def test_resolve_steal_tactic_treasury_raid_success_raids_gold_not_items():
    state = _base_state()
    thief = LeaderState(
        1, kingdom_id=1, name="Thief", location=FIELD, advanced_abilities={AdvancedAbility.THIEF_TREASURY_RAIDS}
    )
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)
    state.kingdoms[2].treasury = 1000
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)

    # level 0 vs a King: raw=15, divisor=1+1+0=2 -> threshold 0.07;
    # 0.06 succeeds. Then treasury_raid_amount (0.5 -> round(500*0.625)=
    # 312, Phase 785) and Add_Experience's own trailing pair (0.5, 0.5).
    outcome, gold_raided, stolen_item_ids = _resolve_steal_tactic(
        thief, _thief_combatant(), king, state, ScriptedRandom([0.06, 0.5, 0.5, 0.5])
    )

    assert outcome == "success"
    assert gold_raided == 312
    assert stolen_item_ids == []
    assert state.kingdoms[2].treasury == 688
    assert state.items[item.item_id].owner_leader_id == 2  # not stolen -- gold replaces items here
    assert state.kingdoms[2].treasury_raid_attempts_this_turn == 1


def test_resolve_steal_tactic_treasury_raid_guard_counter_only_increments_on_success():
    state = _base_state()
    thief = LeaderState(
        1, kingdom_id=1, name="Thief", location=FIELD, advanced_abilities={AdvancedAbility.THIEF_TREASURY_RAIDS}
    )
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)
    state.kingdoms[2].treasury = 1000

    # First attempt: guard counter 0, divisor 1+1+0=2 -> threshold 0.07
    # -- 0.06 succeeds, incrementing the counter.
    outcome1, gold1, _ = _resolve_steal_tactic(thief, _thief_combatant(), king, state, ScriptedRandom([0.06, 0.5, 0.5, 0.5]))
    assert outcome1 == "success"
    assert gold1 > 0
    assert state.kingdoms[2].treasury_raid_attempts_this_turn == 1

    # Second attempt, same turn: guard counter now 1, divisor 1+1+1=3 ->
    # threshold 15//3/100 = 0.05. The same 0.06 roll that succeeded
    # before now fails -- but a FAILED attempt no longer increments the
    # counter (Phase 786's own real, binary-confirmed fix: only a
    # successful raid does), so it stays at 1, not 2.
    outcome2, gold2, _ = _resolve_steal_tactic(thief, _thief_combatant(), king, state, ScriptedRandom([0.06, 0.5]))
    assert outcome2 == "executed"  # failed attempt, failed evasion, Hero thief vs. King
    assert gold2 == 0
    assert state.kingdoms[2].treasury_raid_attempts_this_turn == 1


def test_resolve_steal_tactic_treasury_raid_not_triggered_for_a_same_kingdom_king():
    state = _base_state()
    thief = LeaderState(
        1, kingdom_id=1, name="Thief", location=FIELD, advanced_abilities={AdvancedAbility.THIEF_TREASURY_RAIDS}
    )
    king = LeaderState(2, kingdom_id=1, name="King", location=FIELD, is_king=True)  # same kingdom as the thief
    state.add_leader(thief)
    state.add_leader(king)
    state.kingdoms[1].treasury = 1000
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)

    outcome, gold_raided, _ = _resolve_steal_tactic(thief, _thief_combatant(), king, state, ScriptedRandom([0.06, 0.5, 0.5, 0.5]))

    assert outcome == "success"
    assert gold_raided == 0  # not a "foreign" king -- ordinary item theft instead
    assert state.items[item.item_id].owner_leader_id == 1
    assert state.kingdoms[1].treasury_raid_attempts_this_turn == 0


def test_resolve_steal_tactic_treasury_raid_not_triggered_against_a_hero():
    state = _base_state()
    thief = LeaderState(
        1, kingdom_id=1, name="Thief", location=FIELD, advanced_abilities={AdvancedAbility.THIEF_TREASURY_RAIDS}
    )
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)

    outcome, gold_raided, _ = _resolve_steal_tactic(thief, _thief_combatant(), victim, state, ScriptedRandom([0.1, 0.5, 0.5, 0.5]))

    assert outcome == "success"
    assert gold_raided == 0  # never a King -- the ability makes no difference here
    assert state.items[item.item_id].owner_leader_id == 1


def test_target_evades_via_sense_danger_requires_the_ability():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2, kingdom_id=2, name="Target", location=FIELD, special_encounter_plan=(SearchTactic(Maneuver.FLEE),)
    )
    state.add_leader(challenger)
    state.add_leader(target)

    assert target_evades_via_sense_danger(state, target, challenger) is False


def test_target_evades_via_sense_danger_requires_flee_first_in_the_sep():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2,
        kingdom_id=2,
        name="Target",
        location=FIELD,
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.MELEE),),
    )
    state.add_leader(challenger)
    state.add_leader(target)

    assert target_evades_via_sense_danger(state, target, challenger) is False


def test_target_evades_via_sense_danger_requires_an_unfriendly_challenger():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2,
        kingdom_id=1,  # same kingdom as the challenger -- allied by construction
        name="Target",
        location=FIELD,
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.FLEE),),
    )
    state.add_leader(challenger)
    state.add_leader(target)

    assert target_evades_via_sense_danger(state, target, challenger) is False


def test_target_evades_via_sense_danger_true_when_all_conditions_met():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2,
        kingdom_id=2,
        name="Target",
        location=FIELD,
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.FLEE),),
    )
    state.add_leader(challenger)
    state.add_leader(target)

    assert target_evades_via_sense_danger(state, target, challenger) is True


def test_target_evades_via_sense_danger_ignores_an_army_commanding_targets_own_sep():
    # [5.10]'s own scoping: the SEP is only "used" for a leader who
    # commands no armies -- an army-commanding target's own Flee-first
    # plan is never consulted here either.
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2,
        kingdom_id=2,
        name="Target",
        location=FIELD,
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.FLEE),),
    )
    state.add_leader(challenger)
    state.add_leader(target)
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    assert target_evades_via_sense_danger(state, target, challenger) is False


def test_is_encounter_accepted_sense_danger_evasion_accepts_under_50_percent():
    assert (
        is_encounter_accepted(
            target_is_king=False,
            target_leads_army=False,
            challenger_is_king=False,
            mutual_encounter=False,
            rng=ScriptedRandom([0.3]),
            has_sense_danger_evasion=True,
        )
        is True
    )


def test_is_encounter_accepted_sense_danger_evasion_refuses_at_or_over_50_percent():
    assert (
        is_encounter_accepted(
            target_is_king=False,
            target_leads_army=False,
            challenger_is_king=False,
            mutual_encounter=False,
            rng=ScriptedRandom([0.7]),
            has_sense_danger_evasion=True,
        )
        is False
    )


def test_is_encounter_accepted_without_sense_danger_evasion_reproduces_the_default_case():
    # Non-regression: default False reproduces the pre-Phase-706 result
    # (unconditional accept) with no roll consumed.
    assert (
        is_encounter_accepted(
            target_is_king=False,
            target_leads_army=False,
            challenger_is_king=False,
            mutual_encounter=False,
            rng=ScriptedRandom([]),
        )
        is True
    )


def test_execute_challenge_sense_danger_talent_can_refuse_an_ordinary_encounter():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2,
        kingdom_id=2,
        name="Target",
        location=FIELD,
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.FLEE),),
    )
    state.add_leader(challenger)
    state.add_leader(target)

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([0.7]))

    assert result.accepted is False
    assert result.reason == "encounter refused"


def test_execute_challenge_sense_danger_talent_still_allows_the_encounter_sometimes():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2,
        kingdom_id=2,
        name="Target",
        location=FIELD,
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.FLEE),),
    )
    state.add_leader(challenger)
    state.add_leader(target)

    with patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([0.3]))

    assert result.accepted is True


def test_execute_challenge_sense_danger_talent_does_not_apply_to_allied_challengers():
    state = _base_state()
    challenger = LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD)
    target = LeaderState(
        2,
        kingdom_id=1,  # same kingdom -- allied, so the Talent never applies regardless of the roll
        name="Target",
        location=FIELD,
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.FLEE),),
    )
    state.add_leader(challenger)
    state.add_leader(target)

    with patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([0.99]))

    assert result.accepted is True


def test_is_encounter_accepted_treasury_raid_attempt_bypasses_king_refusal():
    assert (
        is_encounter_accepted(
            target_is_king=True,
            target_leads_army=False,
            challenger_is_king=False,
            mutual_encounter=False,
            rng=ScriptedRandom([]),
            is_treasury_raid_attempt=True,
        )
        is True
    )


def test_execute_challenge_treasury_raid_remote_co_location_via_still_owned_home_province():
    state = _base_state()
    state.kingdoms[2].treasury = 1000
    thief = LeaderState(
        1, kingdom_id=1, name="Thief", location=FIELD, advanced_abilities={AdvancedAbility.THIEF_TREASURY_RAIDS}
    )
    king = LeaderState(2, kingdom_id=2, name="King", location=ELSEWHERE, is_king=True)  # king is elsewhere
    state.add_leader(thief)
    state.add_leader(king)
    # Kingdom 2's own home province (FIELD, per _base_state()) still belongs to it.
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)):
        result = execute_challenge(state, 1, _steal_request(2), rng=ScriptedRandom([0.06, 0.5, 0.5, 0.5]))

    assert result.accepted is True
    assert result.gold_raided == 312


def test_execute_challenge_treasury_raid_remote_co_location_requires_the_ability():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)  # no ability
    king = LeaderState(2, kingdom_id=2, name="King", location=ELSEWHERE, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))

    result = execute_challenge(state, 1, _steal_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "not co-located"


def test_execute_challenge_treasury_raid_remote_co_location_requires_the_kingdom_still_own_it():
    state = _base_state()
    thief = LeaderState(
        1, kingdom_id=1, name="Thief", location=FIELD, advanced_abilities={AdvancedAbility.THIEF_TREASURY_RAIDS}
    )
    king = LeaderState(2, kingdom_id=2, name="King", location=ELSEWHERE, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)
    # Kingdom 2's own home province has since been captured by kingdom 1.
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))

    result = execute_challenge(state, 1, _steal_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "not co-located"


def test_execute_challenge_treasury_raid_bypasses_the_king_refusal_even_when_co_located():
    state = _base_state()
    state.kingdoms[2].treasury = 1000
    thief = LeaderState(
        1, kingdom_id=1, name="Thief", location=FIELD, advanced_abilities={AdvancedAbility.THIEF_TREASURY_RAIDS}
    )
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)  # co-located
    state.add_leader(thief)
    state.add_leader(king)

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)):
        result = execute_challenge(state, 1, _steal_request(2), rng=ScriptedRandom([0.06, 0.5, 0.5, 0.5]))

    assert result.accepted is True
    assert result.gold_raided == 312


def test_execute_challenge_steal_only_plan_now_actually_attempts_the_steal():
    # Phase 305/306's own "consciously-not-fixed gap" corrected: a
    # Steal-only plan used to bypass resolve_challenge_combat() entirely
    # (accepted=True, combat_occurred=False, Steal never fires).
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)

    with patch(
        "ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value=("evaded", 0, [])
    ) as mock_steal, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner=None, rounds=1)
    ):
        result = execute_challenge(state, 1, _steal_request(2), rng=ScriptedRandom([]))

    assert mock_steal.called
    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.steal_outcome == "evaded"


def test_execute_challenge_steal_only_plan_against_a_king_still_refused_without_the_ability():
    # Non-regression: the Steal-only-plan fix doesn't also bypass the
    # ordinary King-refusal gate for a thief without the ability.
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)

    result = execute_challenge(state, 1, _steal_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "encounter refused"
