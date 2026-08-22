from __future__ import annotations

import random

import pytest

from ak_engine.turn.encounter import (
    ARCHERY_FREE_ATTACK_BONUS,
    CHARACTER_HIT_POINTS,
    DAMP_MAGIC_CAST_CHANCE_MULTIPLIER,
    FIRE_ARROW_BASE_HIT_CHANCE,
    FIRE_ARROW_HIT_CHANCE_PER_LEVEL,
    HOLY_SYMBOL_HIT_CHANCE_REDUCTION_PER_LEVEL,
    HOLY_SYMBOL_UNDEAD_DAMAGE_RANGE_PER_LEVEL,
    HOLY_SYMBOL_UNDEAD_HIT_CHANCE_REDUCTION_PER_LEVEL,
    MELEE_HIT_CHANCE,
    NEUTRAL_DUELIST_BONUS,
    PERSONAL_COMBAT_SPELL_LEVEL_CAP,
    SPELL_DISRUPTION_CHANCE_CAP,
    SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT,
    SPELL_DISRUPTION_MISSED_ATTACK_CHANCE,
    CHARM_FLEE_ALWAYS_SUCCEEDS,
    CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE,
    CONTROL_UNDEAD_SUCCESS_NEUTRALIZES_TARGET,
    FIREBALL_DAMAGE_PER_LEVEL,
    FIREBALL_DAMAGE_RANGE,
    HAND_OF_DEATH_BASE_DAMAGE,
    HAND_OF_DEATH_BLOCKS_CASTER_MELEE_ATTACK,
    HAND_OF_DEATH_BLOCKS_CASTER_OTHER_CASTS,
    HAND_OF_DEATH_DAMAGE_PER_LEVEL,
    HAND_OF_DEATH_ENDS_WHEN_CASTER_IS_HIT,
    HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER,
    ICE_SUSPENSION_FLYING_BONUS_ROUNDS_RANGE,
    ICE_SUSPENSION_FLYING_CRASH_DAMAGE_RANGE,
    ICE_SUSPENSION_FREEZE_POINTS_PER_LEVEL,
    ICE_SUSPENSION_FREEZE_THRESHOLD_CAP,
    ICE_SUSPENSION_FROZEN_BONUS_ROUNDS,
    ICE_SUSPENSION_FROZEN_FLEE_ALWAYS_SUCCEEDS,
    ICE_SUSPENSION_SEIZES_UNCARRIED_MAGIC_ITEMS,
    INVISIBILITY_HIT_CHANCE_MULTIPLIER,
    MIRROR_IMAGE_DISBELIEF_BASE_CHANCE,
    MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP,
    MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL,
    MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE,
    MIRROR_IMAGE_MASTER_DISBELIEF_BONUS,
    PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS,
    PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE,
    PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP,
    PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL,
    PSYCHIC_BLAST_STUN_ROUNDS_RANGE,
    SPIRITWRACK_ANIMAL_INTELLIGENCE_DAMAGE_RATE_MULTIPLIER,
    SPIRITWRACK_MELEE_DAMAGE_REDUCTION_PER_LEVEL,
    TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE,
    TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE,
    Combatant,
    CombatRange,
    MeleeRoundOutcome,
    MirrorImageIntelligenceTier,
    ReactiveMeleeSwingResult,
    _acts_first,
    effective_archery_skill,
    effective_melee_skill,
    control_undead_failure_new_hit_points,
    fire_arrow_free_attacks,
    fire_arrow_hit_chance,
    hand_of_death_caster_melee_defense_skill,
    hand_of_death_victim_hit_chance,
    holy_symbol_hit_chance,
    ice_suspension_freeze_threshold,
    ice_suspension_is_frozen,
    ice_suspension_slowed_bonus_rounds,
    invisibility_reduced_hit_chance,
    mirror_image_disbelief_chance,
    personal_combat_spell_cast_chance,
    resolve_encounter_combat,
    resolve_fire_arrow_duel,
    resolve_melee_duel,
    resolve_one_melee_round,
    resolve_personal_combat_spell_cast,
    resolve_reactive_melee_swing,
    resolve_spell_disruption,
    resolve_spell_disruption_from_missed_attack,
    roll_fire_arrow_attack,
    roll_holy_symbol_undead_damage,
    resolve_mirror_image_disbelief,
    roll_control_undead_failure_hp_increase,
    roll_fireball_damage,
    roll_hand_of_death_damage,
    roll_ice_suspension_flying_bonus_rounds,
    roll_ice_suspension_flying_crash_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spell_disruption_chance,
    spell_disruption_chance_from_missed_attack,
    spiritwrack_melee_damage_reduction,
    blocks_cast_and_archery,
    WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER,
    WORDS_OF_HEALING_HEALS_TO_FULL,
    resolve_words_of_healing_disruption,
    resolve_words_of_healing_disruption_from_missed_attack,
    words_of_healing_disruption_chance,
    words_of_healing_disruption_chance_from_missed_attack,
    words_of_healing_heal,
    GATE_DEMON_REFUSAL_CHANCE,
    GATE_DEMON_WINNER_RETURNS_TO_ABYSS,
    GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE,
    GATE_DEMON_NULLIFIED_BY_SIMULTANEOUS_MIRROR_IMAGE_OR_GATE_DEMON,
    resolve_gate_demon_refusal,
    FLAMING_SCIMITAR_INSTAKILL_CHANCE,
    HOLY_SWORD_AUTO_PROTECTION_LEVEL,
    PSYCHIC_FLAIL_STUN_CHANCE,
    SHADOW_SWORD_LIFE_DRAIN_FRACTION,
    apply_weapon_on_hit_effects,
    weapon_defensive_hit_multiplier,
    weapon_grants_auto_invisibility,
    LAVA_POOL_ESCAPE_CHANCE,
    LAVA_POOL_KILLS_INSTANTLY,
    lava_pool_escape_chance,
    resolve_lava_pool_escape,
    MonsterSpeed,
    AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER,
    AUGUR_COMBAT_FREE_WHEN_CAST_FIRST,
    AUGUR_COMBAT_SHIRK_CHANCE,
    Temper,
    augur_combat_shirk_chance,
    resolve_augur_combat,
    resolve_augur_combat_shirk,
    ILLUSORY_HERO_DISBELIEF_REDUCTION,
    ILLUSORY_HERO_TURNS_ON_MASTER_BY_DEFAULT,
    illusory_hero_disbelief_chance,
    resolve_illusory_hero_disbelief,
    PERSONAL_COMBAT_SPELL_ABILITY,
    MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT,
    MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER,
    mirror_image_leader_disbelief_bonus,
    resolve_hand_of_death_channel,
    resolve_mirror_image_duel,
    ILLUSORY_HERO_HOSTILE_ALIGNMENT_PAIRS,
    illusory_hero_alignments_are_implacably_hostile,
    resolve_illusory_hero_duel,
    STEAL_SUCCESS_MAX_CHANCE,
    STEAL_THIEF_MASTERY_ABILITIES,
    MONSTER_STEAL_GOLD_IF_NO_ITEM,
    resolve_steal_attempt,
    resolve_steal_character_item_transfer,
    resolve_steal_evasion,
    resolve_steal_monster_item_transfer,
    steal_character_item_transfer_chance,
    steal_evasion_chance,
    steal_monster_item_transfer_chance,
    steal_ransom_amount,
    steal_success_chance,
    TALK_ATTACK_CHANCE,
    TALK_DRUIDIC_ATTACK_CHANCE,
    TALK_IGNORE_CHANCE,
    TALK_MONSTER_DRUID_LEVEL_REQUIRED,
    MONSTER_TALK_ACCEPT_TEXT,
    MONSTER_TALK_FULFILL_TEXT,
    MONSTER_TALK_OFFER_TEXT,
    MONSTER_TALK_REPLY_FREQUENCY,
    MONSTER_TALK_REPLY_INTELLIGENCE,
    MONSTER_TALK_REPLY_INTELLIGENCE_VARIANCE,
    MONSTER_TALK_REPLY_INVOLVES_CHARACTER,
    MONSTER_TALK_REPLY_NAME,
    MONSTER_TALK_REPLY_OUTCOME,
    MONSTER_TALK_REPLY_VIEW,
    MONSTER_TALK_REPLY_VIEW_VARIANCE,
    MonsterTalkReply,
    TalkReaction,
    TalkReplyOutcome,
    can_talk_to_monster,
    monster_talk_reply_eligible,
    resolve_talk_reaction,
    select_monster_talk_reply,
    BEG_MERCY_CHANCE,
    resolve_beg_for_mercy,
    FULFILL_COMMON_BONUS,
    FULFILL_UNRECORDED_ALIGNMENT_FALLBACK,
    fulfill_honor_threshold,
    fulfill_monster_honors,
    resolve_fulfill_honored,
    BERSERK_FURY_BONUS_HIT_POINTS_RANGE,
    BERSERK_INTIMIDATION_HIT_CHANCE_REDUCTION,
    BRAVE_MOMENTUM_HIT_CHANCE_BONUS,
    CAUTIOUS_DODGE_HIT_CHANCE_REDUCTION,
    MELEE_HIT_POINTS_ABILITY_BONUS_RANGE,
    MELEE_MASTERY_DAMAGE_BONUS,
    MELEE_MASTERY_HIT_CHANCE_BONUS,
    MELEE_TRUE_MASTERY_DAMAGE_BONUS,
    MELEE_DUELLISTS_MEDAL_DAMAGE_BONUS,
    MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS,
    WARP_SPACE_ARCHERY_HIT_CHANCE_MULTIPLIER,
    WARP_SPACE_MELEE_HIT_CHANCE_MULTIPLIER,
    apply_temper_melee_setup,
    archery_free_attack_bonus,
    berserk_fury_bonus_hit_points,
    roll_melee_hit_points_ability_bonus,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    _melee_landed_damage,
    loot_defeated_leader,
)
from ak_engine.models.alignment import Alignment
from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster, MonsterIntelligence, SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure

from _helpers import ScriptedRandom


def test_combatant_defaults_to_character_hit_points():
    assert Combatant("A").hit_points == CHARACTER_HIT_POINTS == 10


def test_effective_skills_add_neutral_duelist_bonus():
    plain = Combatant("A", melee_skill=2, archery_skill=1)
    neutral = Combatant("B", melee_skill=2, archery_skill=1, neutral_duelist_bonus=True)

    assert effective_melee_skill(plain) == 2
    assert effective_melee_skill(neutral) == 2 + NEUTRAL_DUELIST_BONUS
    assert effective_archery_skill(plain) == 1
    assert effective_archery_skill(neutral) == 1 + NEUTRAL_DUELIST_BONUS


def test_fire_arrow_hit_chance_matches_formula():
    assert fire_arrow_hit_chance(0) == pytest.approx(FIRE_ARROW_BASE_HIT_CHANCE)
    assert fire_arrow_hit_chance(3) == pytest.approx(FIRE_ARROW_BASE_HIT_CHANCE + 3 * FIRE_ARROW_HIT_CHANCE_PER_LEVEL)


def test_fire_arrow_free_attacks_equals_archery_skill():
    assert fire_arrow_free_attacks(0) == 0
    assert fire_arrow_free_attacks(4) == 4


def test_roll_melee_attack_hit_returns_damage_in_range():
    rng = ScriptedRandom([0.49, 0.5])  # under 50% -> hit, then the damage roll
    damage = roll_melee_attack(rng)
    assert 1 <= damage <= 6


def test_roll_melee_attack_miss_returns_zero():
    rng = ScriptedRandom([0.5])  # exactly at the 50% boundary -> miss (strict <)
    assert roll_melee_attack(rng) == 0


def test_roll_fire_arrow_attack_hit_returns_damage_in_range():
    rng = ScriptedRandom([0.29, 0.5])  # under the level-0 30% chance -> hit
    damage = roll_fire_arrow_attack(0, rng)
    assert 1 <= damage <= 6


def test_roll_fire_arrow_attack_miss_returns_zero():
    rng = ScriptedRandom([0.3])  # exactly at the level-0 30% boundary -> miss
    assert roll_fire_arrow_attack(0, rng) == 0


def test_acts_first_higher_skill_wins_without_consuming_rng():
    rng = ScriptedRandom([])  # any .random() call here raises IndexError
    assert _acts_first(3, 1, rng) is True
    assert _acts_first(1, 3, rng) is False


def test_acts_first_tied_skill_breaks_randomly():
    assert _acts_first(2, 2, ScriptedRandom([0.1])) is True
    assert _acts_first(2, 2, ScriptedRandom([0.9])) is False


def test_resolve_melee_duel_decisive_winner_leaves_the_other_undamaged():
    # A(melee_skill=1) always acts first (no initiative roll needed);
    # scripted so A always hits and B always misses, so B dies without
    # ever landing a blow on A.
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=10)
    block = [0.1, 0.5, 0.9]  # A hits (chance + damage roll), B misses
    rng = ScriptedRandom(block * 15)  # generously more than enough rounds

    result = resolve_melee_duel(a, b, rng)

    assert result.winner == "a"
    assert a.hit_points == 10
    assert b.hit_points <= 0


def test_resolve_melee_duel_respects_max_rounds_cap_when_nobody_lands_a_hit():
    a = Combatant("A", hit_points=10)
    b = Combatant("B", hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # both always miss

    result = resolve_melee_duel(a, b, rng, max_rounds=2)

    assert result.winner is None
    assert result.rounds == 2
    assert a.hit_points == 10
    assert b.hit_points == 10


# -- Phase 292: resolve_one_melee_round (single-round Melee primitive) --


def test_resolve_one_melee_round_returns_a_melee_round_outcome():
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=10)
    rng = ScriptedRandom([0.99, 0.99])

    outcome = resolve_one_melee_round(a, b, rng, round_number=1)

    assert isinstance(outcome, MeleeRoundOutcome)


def test_resolve_one_melee_round_no_death_reports_both_sides_damage():
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=10)
    block = [0.1, 0.5, 0.1, 0.4]  # A hits (chance, damage), B hits (chance, damage)
    rng = ScriptedRandom(block)

    outcome = resolve_one_melee_round(a, b, rng, round_number=1)

    assert outcome.result is None
    assert outcome.a_attacked is True
    assert outcome.b_attacked is True
    assert outcome.damage_dealt_to_b > 0  # A's landed damage against B
    assert outcome.damage_dealt_to_a > 0  # B's landed damage against A
    assert a.hit_points == 10 - outcome.damage_dealt_to_a
    assert b.hit_points == 10 - outcome.damage_dealt_to_b


def test_resolve_one_melee_round_records_a_miss_as_zero_damage_but_attacked_true():
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=10)
    rng = ScriptedRandom([0.99, 0.99])  # both swing, both miss

    outcome = resolve_one_melee_round(a, b, rng, round_number=1)

    assert outcome.result is None
    assert outcome.a_attacked is True
    assert outcome.b_attacked is True
    assert outcome.damage_dealt_to_a == 0
    assert outcome.damage_dealt_to_b == 0


def test_resolve_one_melee_round_dead_defender_never_swings_back():
    # A(melee_skill=1) acts first and lands a lethal hit on a 1-hp B;
    # B must never get a turn -- attacked flag stays False and no roll
    # is consumed for it (ScriptedRandom raises IndexError otherwise).
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # A's hit-chance roll, then damage roll

    outcome = resolve_one_melee_round(a, b, rng, round_number=3)

    assert outcome.result is not None
    assert outcome.result.winner == "a"
    assert outcome.result.rounds == 3
    assert outcome.a_attacked is True
    assert outcome.b_attacked is False
    assert outcome.damage_dealt_to_a == 0


def test_resolve_one_melee_round_regenerates_hp_only_when_nobody_died():
    a = Combatant("A", melee_skill=1, hit_points=5, regenerates_hp=2)
    b = Combatant("B", melee_skill=0, hit_points=10)
    rng = ScriptedRandom([0.99, 0.99])  # both miss -- nobody dies

    resolve_one_melee_round(a, b, rng, round_number=1)

    assert a.hit_points == 7  # 5 + regenerates_hp, since it survived undamaged


def test_resolve_melee_duel_matches_looping_resolve_one_melee_round():
    # Same scripted rolls, same seed-free deterministic sequence -- the
    # atomic resolve_melee_duel must be exactly a loop over
    # resolve_one_melee_round with identical RNG consumption.
    block = [0.1, 0.5, 0.9]  # A hits, B misses
    a1 = Combatant("A", melee_skill=1, hit_points=10)
    b1 = Combatant("B", melee_skill=0, hit_points=10)
    result = resolve_melee_duel(a1, b1, ScriptedRandom(block * 15))

    a2 = Combatant("A", melee_skill=1, hit_points=10)
    b2 = Combatant("B", melee_skill=0, hit_points=10)
    rng2 = ScriptedRandom(block * 15)
    round_number = 1
    all_swings = []
    outcome = resolve_one_melee_round(a2, b2, rng2, round_number=round_number)
    all_swings.extend(outcome.swings)
    while outcome.result is None:
        round_number += 1
        outcome = resolve_one_melee_round(a2, b2, rng2, round_number=round_number)
        all_swings.extend(outcome.swings)

    # Phase 415: resolve_melee_duel() aggregates melee_swings across every
    # round onto its own returned result; a manual per-round loop has to
    # do the same aggregation itself for a fair comparison here.
    outcome.result.melee_swings = tuple(all_swings)
    assert outcome.result == result
    assert a2.hit_points == a1.hit_points
    assert b2.hit_points == b1.hit_points


def test_resolve_fire_arrow_duel_decisive_winner():
    # A has real Archery skill (some shots); B has none (0 free attacks,
    # never fires at all) and starts at 1 hit point, so A's very first
    # (scripted) hit is lethal regardless of its exact 1-6 magnitude.
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # A's shot: hit-chance roll, then damage roll

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner == "a"
    assert a.hit_points == 10
    assert b.hit_points <= 0


def test_resolve_fire_arrow_duel_no_kill_when_free_attacks_run_out():
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # every shot misses

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner is None
    assert result.rounds == 2  # max(free_attacks(2), free_attacks(1))
    assert a.hit_points == 10
    assert b.hit_points == 10


def test_resolve_fire_arrow_duel_archery_free_attack_bonus_grants_an_extra_shot():
    # B has 0 base Archery skill (0 free attacks) but holds the Advanced
    # Ability, so gets exactly one shot instead of none.
    a = Combatant("A", archery_skill=0, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=10, archery_free_attack_bonus=1)
    # Tied 0 skill needs an _acts_first tie-break roll, then B's one shot's
    # own hit-chance roll (both miss the 0.30 base hit chance).
    rng = ScriptedRandom([0.99, 0.99])

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner is None
    assert result.rounds == 1
    assert len(result.shots) == 1
    assert result.shots[0].shooter == "b"


# -- Phase 175: per-shot Fire Arrow log --


def test_resolve_fire_arrow_duel_logs_every_shot_fired():
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # A's one and only shot: hit-chance roll, then damage roll

    result = resolve_fire_arrow_duel(a, b, rng)

    assert len(result.shots) == 1
    assert result.shots[0].shooter == "a"
    assert result.shots[0].hit is True
    assert 1 <= result.shots[0].damage <= 6


def test_resolve_fire_arrow_duel_logs_a_miss_as_zero_damage():
    a = Combatant("A", archery_skill=1, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # every shot misses

    result = resolve_fire_arrow_duel(a, b, rng)

    assert len(result.shots) == 2  # one shot each (fire_arrow_free_attacks(1) == 1)
    assert {shot.shooter for shot in result.shots} == {"a", "b"}
    assert all(shot.hit is False and shot.damage == 0 for shot in result.shots)


def test_resolve_fire_arrow_duel_shots_are_recorded_in_firing_order():
    # A(skill=2) always acts first (no initiative roll needed, higher skill
    # wins outright per _acts_first) and gets 2 free attacks vs B's 1, so
    # the log should read a, b, a.
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10)
    rng = ScriptedRandom([0.99] * 10)  # every shot misses -- nobody dies mid-log

    result = resolve_fire_arrow_duel(a, b, rng)

    assert [shot.shooter for shot in result.shots] == ["a", "b", "a"]


def test_resolve_melee_duel_never_logs_shots():
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=10)
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = resolve_melee_duel(a, b, rng)

    assert result.shots == ()


# -- Phase 273: resolve_encounter_combat, the Challenge/Pursue/Duel plan walk --


def test_resolve_encounter_combat_shoot_tactic_resolves_via_fire_arrow():
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=1)  # dies to A's first hit
    rng = ScriptedRandom([0.1, 0.5])  # A's shot: hit-chance roll, then damage roll

    result = resolve_encounter_combat([Maneuver.SHOOT], a, b, rng)

    assert result.winner == "a"
    assert len(result.shots) == 1  # only resolve_fire_arrow_duel ever logs shots


def test_resolve_encounter_combat_falls_through_to_melee_once_shots_exhaust():
    a = Combatant("A", archery_skill=1, melee_skill=1, hit_points=10)
    b = Combatant("B", archery_skill=0, melee_skill=0, hit_points=1)
    # A's one Fire Arrow shot misses (shots then exhausted, nobody dead), so
    # the walk falls through to a Melee duel -- B's own 1 hit point means
    # A's first Melee swing kills instantly if it lands.
    rng = ScriptedRandom([0.99, 0.1, 0.5])  # shot misses; Melee hit-chance, then damage roll

    result = resolve_encounter_combat([Maneuver.SHOOT], a, b, rng)

    assert result.winner == "a"
    assert result.shots == ()  # the winning duel was Melee, not Fire Arrow


def test_resolve_encounter_combat_empty_tactic_list_defaults_to_melee():
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])

    result = resolve_encounter_combat([], a, b, rng)

    assert result.winner == "a"


def test_resolve_encounter_combat_melee_never_reaches_a_later_shoot_entry():
    a = Combatant("A", melee_skill=1, archery_skill=0, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # only enough for the one Melee swing

    result = resolve_encounter_combat([Maneuver.MELEE, Maneuver.SHOOT], a, b, rng)

    assert result.winner == "a"
    assert result.shots == ()


def test_resolve_encounter_combat_skips_unrelated_maneuvers():
    a = Combatant("A", melee_skill=1, hit_points=10)
    b = Combatant("B", melee_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])

    result = resolve_encounter_combat([Maneuver.TALK, Maneuver.MELEE], a, b, rng)

    assert result.winner == "a"


# -- Phase 132: monster-specific melee damage range --


def test_combatant_defaults_melee_damage_range_to_the_character_rule():
    assert Combatant("A").melee_damage_range == (1, 6)


def test_roll_melee_attack_uses_the_supplied_damage_range():
    rng = ScriptedRandom([0.1, 0.5])  # under 50% -> hit, then the damage roll
    damage = roll_melee_attack(rng, damage_range=(1, 7))
    assert 1 <= damage <= 7


def test_resolve_melee_duel_uses_each_combatants_own_melee_damage_range():
    # A monster combatant (Giant-style 1-7 die) always acts first
    # (higher melee_skill) and always hits; the character combatant
    # starts at 1 hit point, so any positive damage from the monster's
    # own 1-7 die is lethal regardless of its exact magnitude.
    monster = Combatant("Giant", melee_skill=1, hit_points=25, melee_damage_range=(1, 7))
    character = Combatant("Hero", melee_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # monster: hit-chance roll, then damage roll

    result = resolve_melee_duel(monster, character, rng)

    assert result.winner == "a"
    assert character.hit_points <= 0


# -- Phase 170: monster-specific missile damage range --


def test_combatant_defaults_missile_damage_range_to_the_character_rule():
    assert Combatant("A").missile_damage_range == (1, 6)


def test_roll_fire_arrow_attack_uses_the_supplied_damage_range():
    rng = ScriptedRandom([0.1, 0.5])  # under the hit chance -> hit, then the damage roll
    damage = roll_fire_arrow_attack(0, rng, damage_range=(3, 9))
    assert 3 <= damage <= 9


def test_resolve_fire_arrow_duel_uses_each_combatants_own_missile_damage_range():
    # A monster combatant (Archer-style 3-9 die, skill 1 -> 1 free attack)
    # always acts first (higher archery_skill) and always hits; the
    # character combatant starts at 1 hit point, so any positive damage
    # from the monster's own 3-9 die is lethal regardless of magnitude.
    monster = Combatant("Archer", archery_skill=1, hit_points=12, missile_damage_range=(3, 9))
    character = Combatant("Hero", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.1, 0.5])  # monster: hit-chance roll, then damage roll

    result = resolve_fire_arrow_duel(monster, character, rng)

    assert result.winner == "a"
    assert character.hit_points <= 0


def test_resolve_fire_arrow_duel_higher_skill_keeps_firing_solo_after_the_other_runs_out():
    # A(skill 2) gets 2 shots, B(skill 0) gets 0 -- B never fires at all,
    # so only A's shots can matter; confirmed via a miss-then-hit script
    # that still ends the fight (round 2's hit kills B at 1 hp).
    a = Combatant("A", archery_skill=2, hit_points=10)
    b = Combatant("B", archery_skill=0, hit_points=1)
    rng = ScriptedRandom([0.99, 0.1, 0.5])  # round 1: A misses; round 2: A hits (+damage)

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner == "a"
    assert result.rounds == 2
    assert b.hit_points <= 0


# -- Phase 155: Troll-style end-of-round regeneration --


def test_combatant_defaults_regenerates_hp_to_zero():
    assert Combatant("A").regenerates_hp == 0


def test_resolve_melee_duel_regenerates_hp_after_a_surviving_round():
    a = Combatant("A", hit_points=10)
    b = Combatant("B", hit_points=10, regenerates_hp=1)
    rng = ScriptedRandom([0.99] * 10)  # both always miss

    result = resolve_melee_duel(a, b, rng, max_rounds=1)

    assert result.winner is None
    assert a.hit_points == 10
    assert b.hit_points == 11


def test_resolve_melee_duel_does_not_regenerate_a_combatant_killed_that_round():
    a = Combatant("A", hit_points=10, melee_skill=1)
    b = Combatant("B", hit_points=1, regenerates_hp=5)
    rng = ScriptedRandom([0.1, 0.5])  # A hits (chance + damage roll), kills B outright

    result = resolve_melee_duel(a, b, rng)

    assert result.winner == "a"


def test_resolve_melee_duel_skip_temper_setup_default_still_applies_setup():
    # Phase 297: skip_temper_setup defaults to False -- every pre-Phase-
    # 297 caller (which never passes this new keyword at all) is
    # unaffected, still getting the same single, real Temper setup call
    # resolve_melee_duel() has always made internally.
    a = Combatant("Wary Hero", hit_points=CHARACTER_HIT_POINTS, temper=Temper.CAUTIOUS)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)
    rng = ScriptedRandom([0.99] * 10)  # both always miss -- max_rounds cuts it short, unaffected either way

    resolve_melee_duel(a, b, rng, max_rounds=1)

    assert a.defensive_hit_multiplier == pytest.approx(0.90)


def test_resolve_melee_duel_skip_temper_setup_true_skips_the_internal_call():
    # Phase 297 fix for the real, confirmed double-apply bug found in a
    # dedicated bug-hunt audit: a caller that already applied a real,
    # direct apply_temper_melee_setup() call itself (turn/challenge_
    # execution.py's/turn/search_execution.py's own round-stepping
    # engines) can now tell resolve_melee_duel() not to apply it again.
    a = Combatant("Wary Hero", hit_points=CHARACTER_HIT_POINTS, temper=Temper.CAUTIOUS)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)
    rng = ScriptedRandom([0.99] * 10)

    resolve_melee_duel(a, b, rng, max_rounds=1, skip_temper_setup=True)

    # Still 1.0 -- neither this call nor any prior one in this isolated
    # unit test ever applied Cautious' own dodge multiplier.
    assert a.defensive_hit_multiplier == 1.0


def test_resolve_fire_arrow_duel_regenerates_hp_after_a_surviving_round():
    a = Combatant("A", archery_skill=1, hit_points=10)
    b = Combatant("B", archery_skill=1, hit_points=10, regenerates_hp=1)
    rng = ScriptedRandom([0.5, 0.99, 0.99])  # tie-break, then both shots miss

    result = resolve_fire_arrow_duel(a, b, rng)

    assert result.winner is None
    assert a.hit_points == 10
    assert b.hit_points == 11


# -- Phase 179: the three combat ranges + spell disruption --


def test_combat_range_is_ordered_farthest_to_closest():
    assert CombatRange.SPELL_RANGE.value == 0
    assert CombatRange.BOW_RANGE.value == 1
    assert CombatRange.MELEE_RANGE.value == 2


def test_spell_disruption_chance_matches_the_rules_ak_formula():
    # RULES.AK [5.1]: "3 hit points will disrupt your spell 50% of the
    # time" -- confirmed by the user as a straight linear rate.
    assert spell_disruption_chance(0) == 0.0
    assert spell_disruption_chance(1) == pytest.approx(SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT)
    assert spell_disruption_chance(3) == pytest.approx(0.50)


def test_spell_disruption_chance_caps_at_95_percent():
    # 5 damage points = 83.3%, not yet capped; 6 points would be 100%
    # uncapped, so that's the first value the 95% cap actually clips.
    assert spell_disruption_chance(5) == pytest.approx(5 * SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT)
    assert spell_disruption_chance(6) == pytest.approx(SPELL_DISRUPTION_CHANCE_CAP)
    assert spell_disruption_chance(100) == pytest.approx(SPELL_DISRUPTION_CHANCE_CAP)


def test_resolve_spell_disruption_zero_damage_never_consumes_a_roll():
    # Matches the worked example's own implicit case: a caster who took
    # no damage this round always gets to attempt the cast.
    rng = ScriptedRandom([])
    assert resolve_spell_disruption(0, rng) is False


def test_resolve_spell_disruption_matches_the_worked_example():
    # Ablamor's own cast attempt was disrupted right after Marzials's own
    # 8-point Melee hit -- 8 damage points caps the formula at 95%,
    # matching the narrated outcome (the spell was in fact disrupted).
    assert spell_disruption_chance(8) == pytest.approx(SPELL_DISRUPTION_CHANCE_CAP)
    assert resolve_spell_disruption(8, ScriptedRandom([0.94])) is True
    assert resolve_spell_disruption(8, ScriptedRandom([0.95])) is False


def test_resolve_spell_disruption_consumes_exactly_one_roll_when_damaged():
    rng = ScriptedRandom([0.99])  # a second .random() call would raise IndexError
    resolve_spell_disruption(2, rng)


def test_spell_disruption_chance_from_missed_attack_matches_rules_ak():
    # RULES.AK [5.1]: "a missed swing will disrupt you 30% of the time".
    assert spell_disruption_chance_from_missed_attack() == pytest.approx(0.30)


def test_resolve_spell_disruption_from_missed_attack_uses_the_flat_30_percent():
    assert resolve_spell_disruption_from_missed_attack(ScriptedRandom([0.29])) is True
    assert resolve_spell_disruption_from_missed_attack(ScriptedRandom([0.30])) is False


def test_resolve_spell_disruption_from_missed_attack_always_consumes_a_roll():
    # Unlike the damage-taken case, a missed attack still happened --
    # there's no "zero" shortcut here.
    rng = ScriptedRandom([0.99])
    resolve_spell_disruption_from_missed_attack(rng)


# -- Phase 416: resolve_reactive_melee_swing()'s own hit-vs-damage split --


def test_resolve_reactive_melee_swing_hit_returns_hit_true_and_positive_damage():
    attacker = Combatant("A", melee_skill=1)
    defender = Combatant("B", hit_points=10)
    rng = ScriptedRandom([0.49, 0.5])  # under 50% -> hit, then the damage roll

    result = resolve_reactive_melee_swing(attacker, defender, rng)

    assert result == ReactiveMeleeSwingResult(hit=True, damage=result.damage)
    assert result.hit is True
    assert 1 <= result.damage <= 6
    assert defender.hit_points == 10 - result.damage


def test_resolve_reactive_melee_swing_miss_returns_hit_false_and_zero_damage():
    attacker = Combatant("A")
    defender = Combatant("B", hit_points=10)
    rng = ScriptedRandom([0.5])  # exactly at the 50% boundary -> miss (strict <)

    result = resolve_reactive_melee_swing(attacker, defender, rng)

    assert result == ReactiveMeleeSwingResult(hit=False, damage=0)
    assert defender.hit_points == 10


def test_resolve_reactive_melee_swing_spiritwrack_reduction_can_floor_a_real_hit_to_zero_damage():
    # A landed hit (raw roll > 0) whose net damage is fully absorbed by
    # the attacker's own Spiritwrack reduction must still report hit=True
    # -- damage > 0 alone can't stand in for hit, the same reasoning
    # MeleeSwing's own Phase 415 addendum already documents.
    attacker = Combatant("A", melee_skill=1, melee_damage_dealt_reduction=999)
    defender = Combatant("B", hit_points=10)
    rng = ScriptedRandom([0.49, 0.5])  # under 50% -> hit, then the damage roll

    result = resolve_reactive_melee_swing(attacker, defender, rng)

    assert result == ReactiveMeleeSwingResult(hit=True, damage=0)
    assert defender.hit_points == 10  # fully absorbed -- no net damage taken


# -- Phase 180: Holy Symbol [HO] --


def test_holy_symbol_hit_chance_matches_the_worked_example():
    # Level 1 against a 50% base chance -> reduced by 5% (10% of 50%).
    assert holy_symbol_hit_chance(0.50, 1) == pytest.approx(0.45)


def test_holy_symbol_hit_chance_scales_with_skill_level():
    assert holy_symbol_hit_chance(0.50, 2) == pytest.approx(0.50 * (1 - 2 * HOLY_SYMBOL_HIT_CHANCE_REDUCTION_PER_LEVEL))
    assert holy_symbol_hit_chance(0.50, 0) == pytest.approx(0.50)


def test_holy_symbol_hit_chance_undead_or_anti_holy_uses_the_20_percent_rate():
    # Same level-1-vs-50% worked example, but against an Undead/Anti-Holy
    # target the reduction rate doubles to 20% per level -> 40%, not 45%.
    assert holy_symbol_hit_chance(0.50, 1, target_is_undead_or_anti_holy=True) == pytest.approx(0.40)


def test_holy_symbol_hit_chance_caps_skill_level_at_4():
    # Phase 181: "come tutti quelli di combattimento ha il CAP al
    # livello 4" -- WH 5 (or higher) has exactly the same effect as
    # WH 4, the confirmed cap on every Personal-Combat spell.
    assert PERSONAL_COMBAT_SPELL_LEVEL_CAP == 4
    at_cap = holy_symbol_hit_chance(0.50, 4, target_is_undead_or_anti_holy=True)
    assert holy_symbol_hit_chance(0.50, 5, target_is_undead_or_anti_holy=True) == pytest.approx(at_cap)
    assert holy_symbol_hit_chance(0.50, 100, target_is_undead_or_anti_holy=True) == pytest.approx(at_cap)


def test_holy_symbol_hit_chance_stays_nonnegative_at_the_capped_maximum_reduction():
    # 4 levels * 20%/level = 80% reduction -- the largest possible
    # reduction now that levels beyond the cap no longer count -- still
    # leaves a positive floor rather than reaching (or crossing) zero.
    assert holy_symbol_hit_chance(0.50, 100, target_is_undead_or_anti_holy=True) == pytest.approx(0.10)


def test_roll_holy_symbol_undead_damage_level_zero_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert roll_holy_symbol_undead_damage(0, rng) == 0


def test_roll_holy_symbol_undead_damage_caps_skill_level_at_4():
    # WH 5 (or higher) rolls exactly 4 dice, not 5 -- verified by
    # counting the underlying random() draws.
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0])
    call_count = 0
    real_random = rng.random

    def counting_random():
        nonlocal call_count
        call_count += 1
        return real_random()

    rng.random = counting_random
    damage = roll_holy_symbol_undead_damage(5, rng)
    assert call_count == 4
    assert 4 <= damage <= 16


def test_roll_holy_symbol_undead_damage_range_at_level_1():
    # ScriptedRandom overrides random() but not getrandbits(), so
    # rng.randint() itself draws from the scripted queue via
    # _randbelow_without_getrandbits (one random() draw per randint()
    # call for a 4-wide range, since 4 evenly divides the float
    # resolution) -- same mechanism the file's pre-existing
    # roll_melee_attack tests already rely on.
    rng = ScriptedRandom([0.0])
    damage = roll_holy_symbol_undead_damage(1, rng)
    assert 1 <= damage <= 4


def test_roll_holy_symbol_undead_damage_sums_one_independent_roll_per_level():
    # Level 2 -> two separate 1-4 rolls, summed (confirmed range 2-8),
    # not a single roll scaled or multiplied by level -- verified by
    # counting how many times the underlying random() draw is consumed.
    rng = ScriptedRandom([0.0, 0.5])
    call_count = 0
    real_random = rng.random

    def counting_random():
        nonlocal call_count
        call_count += 1
        return real_random()

    rng.random = counting_random
    damage = roll_holy_symbol_undead_damage(2, rng)
    assert call_count == 2
    assert 2 <= damage <= 8


def test_roll_holy_symbol_undead_damage_range_is_1_to_4_per_level():
    assert HOLY_SYMBOL_UNDEAD_DAMAGE_RANGE_PER_LEVEL == (1, 4)


# -- Phase 182: Spiritwrack [SP] --


def test_blocks_cast_and_archery_by_default():
    assert blocks_cast_and_archery() is True


def test_blocks_cast_and_archery_never_applies_to_an_immune_target():
    assert blocks_cast_and_archery(target_is_immune=True) is False


def test_spiritwrack_melee_damage_reduction_immune_target_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(4, rng, target_is_immune=True) == 0
    # Immune wins even if the target is also flagged Animal-Intelligence.
    assert spiritwrack_melee_damage_reduction(4, rng, target_is_immune=True, target_is_animal_intelligence=True) == 0


def test_spiritwrack_melee_damage_reduction_level_zero_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(0, rng) == 0


def test_spiritwrack_melee_damage_reduction_level_2_is_a_whole_point_no_roll_needed():
    # 0.5 * 2 = 1.0 exactly -- no fractional part, no roll consumed.
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(2, rng) == 1


def test_spiritwrack_melee_damage_reduction_level_1_rounds_randomly():
    # 0.5 * 1 = 0.5 -- rounds up to 1 half the time, down to 0 the rest.
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.49])) == 1
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.5])) == 0


def test_spiritwrack_melee_damage_reduction_level_3_rounds_randomly_around_its_own_whole_part():
    # 0.5 * 3 = 1.5 -- rounds up to 2 half the time, down to 1 the rest.
    assert spiritwrack_melee_damage_reduction(3, ScriptedRandom([0.49])) == 2
    assert spiritwrack_melee_damage_reduction(3, ScriptedRandom([0.5])) == 1


def test_spiritwrack_melee_damage_reduction_caps_skill_level_at_4():
    # 0.5 * 4 = 2.0 exactly -- level 5 (or higher) must match level 4
    # exactly, and also needs no roll since the capped exact value has
    # no fractional part.
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(4, rng) == 2
    assert spiritwrack_melee_damage_reduction(5, rng) == 2
    assert spiritwrack_melee_damage_reduction(100, rng) == 2


def test_spiritwrack_melee_damage_reduction_animal_intelligence_halves_the_rate():
    # 0.25 * 1 = 0.25 -- rounds up to 1 a quarter of the time.
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.24]), target_is_animal_intelligence=True) == 1
    assert spiritwrack_melee_damage_reduction(1, ScriptedRandom([0.25]), target_is_animal_intelligence=True) == 0


def test_spiritwrack_melee_damage_reduction_animal_intelligence_at_capped_level_is_a_whole_point_no_roll():
    # 0.25 * 4 (capped) = 1.0 exactly -- no fractional part, no roll.
    rng = ScriptedRandom([])
    assert spiritwrack_melee_damage_reduction(4, rng, target_is_animal_intelligence=True) == 1


def test_spiritwrack_rate_constants():
    assert SPIRITWRACK_MELEE_DAMAGE_REDUCTION_PER_LEVEL == 0.5
    assert SPIRITWRACK_ANIMAL_INTELLIGENCE_DAMAGE_RATE_MULTIPLIER == 0.5


# -- Phase 183: Charm [CH]'s Personal-Combat effect --


def test_charm_flee_always_succeeds_constant():
    # "Praticamente se usato in combattimento equivale a un comando FL
    # che riesce sempre" -- no roll, no skill-level scaling at all.
    assert CHARM_FLEE_ALWAYS_SUCCEEDS is True


# -- Phase 184: Psychic Blast [PS] --


def test_psychic_blast_stun_rounds_range_constant():
    assert PSYCHIC_BLAST_STUN_ROUNDS_RANGE == (2, 5)


def test_roll_psychic_blast_stun_rounds_stays_within_range():
    for scripted in (0.0, 0.25, 0.5, 0.75, 0.999):
        rounds = roll_psychic_blast_stun_rounds(ScriptedRandom([scripted]))
        assert 2 <= rounds <= 5


def test_roll_psychic_blast_stun_rounds_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    roll_psychic_blast_stun_rounds(rng)


# -- Phase 185: Telekinetic Storm [TE] --


def test_telekinetic_storm_victim_damage_range_constant():
    assert TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE == (4, 16)


def test_telekinetic_storm_caster_damage_range_by_combat_range_constant():
    assert TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE == {
        CombatRange.MELEE_RANGE: (4, 16),
        CombatRange.BOW_RANGE: (2, 8),
        CombatRange.SPELL_RANGE: (1, 4),
    }


def test_roll_telekinetic_storm_victim_damage_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_victim_damage(ScriptedRandom([scripted]))
        assert 4 <= damage <= 16


def test_roll_telekinetic_storm_victim_damage_immune_target_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert roll_telekinetic_storm_victim_damage(rng, target_is_immune=True) == 0


def test_roll_telekinetic_storm_caster_damage_at_melee_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_caster_damage(CombatRange.MELEE_RANGE, ScriptedRandom([scripted]))
        assert 4 <= damage <= 16


def test_roll_telekinetic_storm_caster_damage_at_bow_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_caster_damage(CombatRange.BOW_RANGE, ScriptedRandom([scripted]))
        assert 2 <= damage <= 8


def test_roll_telekinetic_storm_caster_damage_at_spell_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_telekinetic_storm_caster_damage(CombatRange.SPELL_RANGE, ScriptedRandom([scripted]))
        assert 1 <= damage <= 4


def test_roll_telekinetic_storm_caster_damage_immune_target_returns_zero_without_a_roll():
    # Immune (submarine) means the storm never manifests, so the
    # caster takes no self-damage either -- unlike Spiritwrack's own
    # immunity, which only ever affected the target's side.
    rng = ScriptedRandom([])
    assert roll_telekinetic_storm_caster_damage(CombatRange.MELEE_RANGE, rng, target_is_immune=True) == 0


# -- Phase 186: Invisibility [IN] --


def test_invisibility_hit_chance_multiplier_constant():
    assert INVISIBILITY_HIT_CHANCE_MULTIPLIER == 0.5


def test_invisibility_reduced_hit_chance_halves_the_base_chance():
    # "la probabilita' di essere colpiti con l'arco o nel corpo a
    # mischia viene dimezzata" -- applies equally to Fire Arrow's own
    # hit-chance formula and the flat Melee hit chance.
    assert invisibility_reduced_hit_chance(0.50) == pytest.approx(0.25)
    assert invisibility_reduced_hit_chance(fire_arrow_hit_chance(2)) == pytest.approx(fire_arrow_hit_chance(2) * 0.5)
    assert invisibility_reduced_hit_chance(MELEE_HIT_CHANCE) == pytest.approx(0.25)


# -- Phase 187: Mirror-Image Phantasm (MI) --


def test_mirror_image_disbelief_base_chance_table():
    assert MIRROR_IMAGE_DISBELIEF_BASE_CHANCE == {
        MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN: 1.20,
        MirrorImageIntelligenceTier.HIGH_HUMAN: 1.00,
        MirrorImageIntelligenceTier.MEDIUM_HUMAN: 0.80,
        MirrorImageIntelligenceTier.LOW_HUMAN: 0.60,
        MirrorImageIntelligenceTier.ANIMAL: 0.40,
        MirrorImageIntelligenceTier.MECHANICAL: 0.20,
    }


def test_mirror_image_master_disbelief_base_chance_is_medium_plus_25_percent():
    # "a bonus of 25% above Medium intelligence" -- 80% + 25% = 105%.
    assert MIRROR_IMAGE_MASTER_DISBELIEF_BONUS == 0.25
    assert MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE == pytest.approx(1.05)


def test_mirror_image_disbelief_chance_subtracts_15_percent_per_level():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.HIGH_HUMAN]  # 100%
    assert mirror_image_disbelief_chance(base, 0) == pytest.approx(1.00)
    assert mirror_image_disbelief_chance(base, 1) == pytest.approx(0.85)
    assert mirror_image_disbelief_chance(base, 2) == pytest.approx(0.70)


def test_mirror_image_disbelief_chance_reduction_caps_at_60_percent():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]  # 120%
    # 15%*4 = 60% (the cap itself); 15%*5 = 75% would exceed it uncapped.
    assert mirror_image_disbelief_chance(base, 4) == pytest.approx(base - MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP)
    assert mirror_image_disbelief_chance(base, 5) == pytest.approx(base - MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP)
    assert MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL == 0.15
    assert MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP == 0.60


def test_mirror_image_disbelief_chance_clamps_to_0_and_100_percent():
    # Mechanical's own 20% base, fully reduced, floors at 0% rather
    # than going negative.
    low_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MECHANICAL]
    assert mirror_image_disbelief_chance(low_base, 10) == 0.0
    # Divine/Superhuman's own 120% base, unreduced, clamps to 100%.
    high_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]
    assert mirror_image_disbelief_chance(high_base, 0) == 1.0


def test_resolve_mirror_image_disbelief_zero_percent_never_consumes_a_roll():
    rng = ScriptedRandom([])
    low_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MECHANICAL]
    assert resolve_mirror_image_disbelief(low_base, 10, rng) is False


def test_resolve_mirror_image_disbelief_hundred_percent_never_consumes_a_roll():
    rng = ScriptedRandom([])
    high_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]
    assert resolve_mirror_image_disbelief(high_base, 0, rng) is True


def test_resolve_mirror_image_disbelief_consumes_exactly_one_roll_in_between():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MEDIUM_HUMAN]  # 80%
    rng = ScriptedRandom([0.79])  # a second .random() call would raise IndexError
    assert resolve_mirror_image_disbelief(base, 0, rng) is True
    rng = ScriptedRandom([0.80])
    assert resolve_mirror_image_disbelief(base, 0, rng) is False


# -- Phase 188: Fireball [FI] --


def test_fireball_damage_range_constant():
    assert FIREBALL_DAMAGE_RANGE == (1, 8)


def test_fireball_damage_per_level_constant():
    assert FIREBALL_DAMAGE_PER_LEVEL == 1


def test_roll_fireball_damage_stays_within_range_at_level_zero():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_fireball_damage(0, ScriptedRandom([scripted]))
        assert 1 <= damage <= 8


def test_roll_fireball_damage_adds_one_point_per_level():
    rng = ScriptedRandom([0.0])  # base roll pinned to the range floor: 1
    assert roll_fireball_damage(3, rng) == 1 + FIREBALL_DAMAGE_PER_LEVEL * 3


def test_roll_fireball_damage_caps_bonus_at_level_four():
    # "max 4" -- level 5 behaves exactly like level 4 (PERSONAL_COMBAT_SPELL_LEVEL_CAP).
    rng_level_4 = ScriptedRandom([0.0])
    rng_level_5 = ScriptedRandom([0.0])
    assert roll_fireball_damage(4, rng_level_4) == roll_fireball_damage(5, rng_level_5)
    assert PERSONAL_COMBAT_SPELL_LEVEL_CAP == 4


def test_roll_fireball_damage_immune_target_returns_zero_without_a_roll():
    # Immune (submarine monster) -- no roll consumed at all.
    rng = ScriptedRandom([])
    assert roll_fireball_damage(4, rng, target_is_immune=True) == 0


# -- Phase 189: Ice Suspension [IC] --


def test_ice_suspension_freeze_points_per_level_constant():
    assert ICE_SUSPENSION_FREEZE_POINTS_PER_LEVEL == 4


def test_ice_suspension_freeze_threshold_scales_with_level_up_to_the_cap():
    assert ice_suspension_freeze_threshold(1) == 4
    assert ice_suspension_freeze_threshold(2) == 8
    assert ice_suspension_freeze_threshold(3) == 12
    assert ice_suspension_freeze_threshold(4) == 16
    assert ice_suspension_freeze_threshold(5) == 16  # capped
    assert ICE_SUSPENSION_FREEZE_THRESHOLD_CAP == 16


def test_ice_suspension_is_frozen_true_at_or_below_threshold():
    assert ice_suspension_is_frozen(4, 1) is True  # exactly at threshold
    assert ice_suspension_is_frozen(3, 1) is True  # below threshold
    assert ice_suspension_is_frozen(5, 1) is False  # above threshold


def test_ice_suspension_frozen_flee_always_succeeds_constant():
    assert ICE_SUSPENSION_FROZEN_FLEE_ALWAYS_SUCCEEDS is True


def test_ice_suspension_frozen_bonus_rounds_constant():
    assert ICE_SUSPENSION_FROZEN_BONUS_ROUNDS == 3


def test_ice_suspension_seizes_uncarried_magic_items_constant():
    assert ICE_SUSPENSION_SEIZES_UNCARRIED_MAGIC_ITEMS is True


def test_ice_suspension_slowed_bonus_rounds_matches_the_user_supplied_example():
    # 16 HP remaining, caster skill level 1 -> 1 bonus round. Reverse-
    # engineered and confirmed via AskUserQuestion (see module docstring).
    assert ice_suspension_slowed_bonus_rounds(16, 1) == 1


def test_ice_suspension_slowed_bonus_rounds_stays_within_zero_to_three():
    # Just above the freeze threshold (16), the fraction approaches but
    # never reaches 1, so floor(4*16/17) = 3 is the practical ceiling.
    assert ice_suspension_slowed_bonus_rounds(17, 4) == 3
    # A victim with far more HP than the threshold yields 0 (no bonus).
    assert ice_suspension_slowed_bonus_rounds(1000, 1) == 0


def test_ice_suspension_flying_crash_damage_range_constant():
    assert ICE_SUSPENSION_FLYING_CRASH_DAMAGE_RANGE == (5, 10)


def test_ice_suspension_flying_bonus_rounds_range_constant():
    assert ICE_SUSPENSION_FLYING_BONUS_ROUNDS_RANGE == (1, 3)


def test_roll_ice_suspension_flying_crash_damage_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        damage = roll_ice_suspension_flying_crash_damage(ScriptedRandom([scripted]))
        assert 5 <= damage <= 10


def test_roll_ice_suspension_flying_bonus_rounds_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        rounds = roll_ice_suspension_flying_bonus_rounds(ScriptedRandom([scripted]))
        assert 1 <= rounds <= 3


# -- Phase 190: Hand of Death [HA] --


def test_hand_of_death_caster_constraint_constants():
    assert HAND_OF_DEATH_BLOCKS_CASTER_OTHER_CASTS is True
    assert HAND_OF_DEATH_BLOCKS_CASTER_MELEE_ATTACK is True
    assert HAND_OF_DEATH_ENDS_WHEN_CASTER_IS_HIT is True


def test_hand_of_death_caster_melee_defense_skill_substitutes_necromancy_for_melee():
    assert hand_of_death_caster_melee_defense_skill(3) == 3
    assert hand_of_death_caster_melee_defense_skill(0) == 0


def test_hand_of_death_damage_constants():
    assert HAND_OF_DEATH_BASE_DAMAGE == 1
    assert HAND_OF_DEATH_DAMAGE_PER_LEVEL == 0.5


def test_roll_hand_of_death_damage_whole_exact_value_never_consumes_a_roll():
    # Level 2: 1 + 0.5*2 = 2, a whole number -- no coin-flip roll needed.
    rng = ScriptedRandom([])
    assert roll_hand_of_death_damage(2, rng) == 2


def test_roll_hand_of_death_damage_fractional_value_is_a_coin_flip():
    # Level 1: 1 + 0.5*1 = 1.5 -- rounds down to 1 or up to 2.
    rng_low = ScriptedRandom([0.49])
    assert roll_hand_of_death_damage(1, rng_low) == 2
    rng_high = ScriptedRandom([0.50])
    assert roll_hand_of_death_damage(1, rng_high) == 1


def test_roll_hand_of_death_damage_immune_target_returns_zero_without_a_roll():
    rng = ScriptedRandom([])
    assert roll_hand_of_death_damage(4, rng, target_is_immune=True) == 0


def test_hand_of_death_victim_hit_chance_multiplier_constant():
    assert HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER == 0.5


def test_hand_of_death_victim_hit_chance_halves_the_base_chance():
    assert hand_of_death_victim_hit_chance(0.6) == pytest.approx(0.3)


def test_hand_of_death_victim_hit_chance_immune_target_is_unaffected():
    assert hand_of_death_victim_hit_chance(0.6, target_is_immune=True) == 0.6


def test_blocks_cast_and_archery_shared_with_spiritwrack():
    # Renamed from spiritwrack_blocks_cast_and_archery in Phase 190,
    # confirmed to be Hand of Death's own victim effect too.
    assert blocks_cast_and_archery() is True
    assert blocks_cast_and_archery(target_is_immune=True) is False


# -- Phase 191: Control Undead [CO] --


def test_control_undead_success_neutralizes_target_constant():
    assert CONTROL_UNDEAD_SUCCESS_NEUTRALIZES_TARGET is True


def test_control_undead_failure_hp_increase_range_constant():
    assert CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE == (0.50, 1.00)


def test_roll_control_undead_failure_hp_increase_stays_within_range():
    for scripted in (0.0, 0.5, 0.999):
        increase = roll_control_undead_failure_hp_increase(ScriptedRandom([scripted]))
        assert 0.50 <= increase <= 1.00


def test_roll_control_undead_failure_hp_increase_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    roll_control_undead_failure_hp_increase(rng)


def test_control_undead_failure_new_hit_points_at_the_low_end_of_the_range():
    # 10 HP, +50% -> 15.
    rng = ScriptedRandom([0.0])
    assert control_undead_failure_new_hit_points(10, rng) == 15


def test_control_undead_failure_new_hit_points_at_the_high_end_of_the_range():
    # 10 HP, +100% -> 20. uniform() never returns exactly b, so pin very
    # close to it instead.
    rng = ScriptedRandom([0.999999999])
    assert control_undead_failure_new_hit_points(10, rng) == 20


# -- Phase 192: general Personal-Combat spell cast success formula --


def test_personal_combat_spell_cast_chance_constants():
    assert PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE == 0.30
    assert PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL == 0.15
    assert PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP == 1.00
    assert PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS == 0.10


def test_personal_combat_spell_cast_chance_scales_with_level():
    assert personal_combat_spell_cast_chance(0) == pytest.approx(0.30)
    assert personal_combat_spell_cast_chance(1) == pytest.approx(0.45)
    assert personal_combat_spell_cast_chance(2) == pytest.approx(0.60)


def test_personal_combat_spell_cast_chance_matches_the_reports_own_pagan_table():
    # AKGEN_reverse_engineering_report (2).md SS21.1's own worked table:
    # "Ai livelli 1-4... per un Pagan diventano 55%, 70%, 85%, 100%."
    assert personal_combat_spell_cast_chance(1, caster_is_pagan=True) == pytest.approx(0.55)
    assert personal_combat_spell_cast_chance(2, caster_is_pagan=True) == pytest.approx(0.70)
    assert personal_combat_spell_cast_chance(3, caster_is_pagan=True) == pytest.approx(0.85)
    assert personal_combat_spell_cast_chance(4, caster_is_pagan=True) == pytest.approx(1.00)


def test_personal_combat_spell_cast_chance_caps_at_100_percent():
    # Level 5, Pagan: 30% + 15%*5 + 10% = 115%, clamped to 100% (Phase
    # 467 -- corrected from the rulebook's own claimed 95% cap).
    assert personal_combat_spell_cast_chance(5, caster_is_pagan=True) == pytest.approx(1.00)


def test_personal_combat_spell_cast_chance_pagan_bonus():
    assert personal_combat_spell_cast_chance(1, caster_is_pagan=True) == pytest.approx(0.55)


def test_resolve_personal_combat_spell_cast_succeeds_under_the_chance():
    rng = ScriptedRandom([0.44])  # level 1 -> 45% chance
    assert resolve_personal_combat_spell_cast(1, rng) is True


def test_resolve_personal_combat_spell_cast_fails_over_the_chance():
    rng = ScriptedRandom([0.99])
    assert resolve_personal_combat_spell_cast(1, rng) is False


# -- Phase 617: Power.DAMP_MAGIC halves every spell's own cast chance --


def test_personal_combat_spell_cast_chance_damp_magic_halves_the_result():
    assert personal_combat_spell_cast_chance(1, damp_magic=True) == pytest.approx(0.225)  # 0.45 * 0.5


def test_personal_combat_spell_cast_chance_damp_magic_applies_after_the_cap():
    # Level 5, Pagan: capped at 100%, then halved by Damp Magic -> 50%.
    assert personal_combat_spell_cast_chance(5, caster_is_pagan=True, damp_magic=True) == pytest.approx(0.50)


def test_resolve_personal_combat_spell_cast_damp_magic_fails_a_roll_the_undamped_chance_would_pass():
    # Level 1 -> 45% undamped, 22.5% damped -- 0.3 clears the damped
    # threshold's failure but would have succeeded undamped.
    rng = ScriptedRandom([0.3])
    assert resolve_personal_combat_spell_cast(1, rng, damp_magic=True) is False


def test_damp_magic_and_warp_space_constants():
    assert DAMP_MAGIC_CAST_CHANCE_MULTIPLIER == 0.5
    assert WARP_SPACE_ARCHERY_HIT_CHANCE_MULTIPLIER == 0.25
    assert WARP_SPACE_MELEE_HIT_CHANCE_MULTIPLIER == 0.5


# -- Phase 200: Words of Healing [WH] --


def test_words_of_healing_constants():
    assert WORDS_OF_HEALING_HEALS_TO_FULL is True
    assert WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER == 0.5


def test_words_of_healing_disruption_chance_is_half_the_normal_rate():
    assert words_of_healing_disruption_chance(1) == pytest.approx(
        SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT * 0.5
    )
    assert words_of_healing_disruption_chance(2) == pytest.approx(
        2 * SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT * 0.5
    )
    assert words_of_healing_disruption_chance(0) == 0.0


def test_words_of_healing_disruption_chance_still_caps_at_95_percent():
    # 12 damage points * (16.67%/2) = 100%, uncapped -- clamped to the same 95% cap.
    assert words_of_healing_disruption_chance(12) == pytest.approx(SPELL_DISRUPTION_CHANCE_CAP)


def test_resolve_words_of_healing_disruption_zero_hits_never_consumes_a_roll():
    rng = ScriptedRandom([])
    assert resolve_words_of_healing_disruption(0, rng) is False


def test_resolve_words_of_healing_disruption_uses_the_halved_chance():
    # 1 damage point -> ~8.33% (half of the normal ~16.67%): 0.08 disrupts, 0.09 doesn't --
    # a roll that would disrupt a normal spell (0.15) does not disrupt WH.
    assert resolve_words_of_healing_disruption(1, ScriptedRandom([0.08])) is True
    assert resolve_words_of_healing_disruption(1, ScriptedRandom([0.09])) is False
    assert resolve_words_of_healing_disruption(1, ScriptedRandom([0.15])) is False


def test_resolve_words_of_healing_disruption_consumes_exactly_one_roll_when_hits_taken():
    rng = ScriptedRandom([0.99])  # a second .random() call would raise IndexError
    resolve_words_of_healing_disruption(2, rng)


def test_words_of_healing_disruption_chance_from_missed_attack_is_half_the_normal_rate():
    assert words_of_healing_disruption_chance_from_missed_attack() == pytest.approx(
        SPELL_DISRUPTION_MISSED_ATTACK_CHANCE * 0.5
    )


def test_resolve_words_of_healing_disruption_from_missed_attack_uses_the_halved_chance():
    assert resolve_words_of_healing_disruption_from_missed_attack(ScriptedRandom([0.14])) is True
    assert resolve_words_of_healing_disruption_from_missed_attack(ScriptedRandom([0.15])) is False


def test_resolve_words_of_healing_disruption_from_missed_attack_always_consumes_a_roll():
    rng = ScriptedRandom([0.99])
    resolve_words_of_healing_disruption_from_missed_attack(rng)


def test_words_of_healing_heal_restores_to_full():
    combatant = Combatant("Ablamor", hit_points=3)

    words_of_healing_heal(combatant, CHARACTER_HIT_POINTS)

    assert combatant.hit_points == CHARACTER_HIT_POINTS == 10


def test_words_of_healing_heal_defaults_to_character_hit_points():
    combatant = Combatant("Ablamor", hit_points=1)

    words_of_healing_heal(combatant)

    assert combatant.hit_points == CHARACTER_HIT_POINTS


def test_words_of_healing_heal_uses_a_monster_supplied_max():
    combatant = Combatant("Troll", hit_points=5)

    words_of_healing_heal(combatant, max_hit_points=30)

    assert combatant.hit_points == 30


# -- Phase 202: Gate Demon [GD] --


def test_gate_demon_constants():
    assert GATE_DEMON_REFUSAL_CHANCE == 0.5
    assert GATE_DEMON_WINNER_RETURNS_TO_ABYSS is True
    assert GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE is True
    assert GATE_DEMON_NULLIFIED_BY_SIMULTANEOUS_MIRROR_IMAGE_OR_GATE_DEMON is True


def test_resolve_gate_demon_refusal_below_the_50_percent_threshold_refuses():
    assert resolve_gate_demon_refusal(ScriptedRandom([0.0])) is True
    assert resolve_gate_demon_refusal(ScriptedRandom([0.49])) is True


def test_resolve_gate_demon_refusal_at_or_above_the_50_percent_threshold_fights():
    assert resolve_gate_demon_refusal(ScriptedRandom([0.5])) is False
    assert resolve_gate_demon_refusal(ScriptedRandom([0.99])) is False


def test_resolve_gate_demon_refusal_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    resolve_gate_demon_refusal(rng)


# -- Phase 203: Lava Pool [LP] --


def test_lava_pool_constants():
    assert LAVA_POOL_KILLS_INSTANTLY is True
    assert LAVA_POOL_ESCAPE_CHANCE[MonsterSpeed.FAST] == 0.60
    assert LAVA_POOL_ESCAPE_CHANCE[MonsterSpeed.MEDIUM] == 0.30
    assert LAVA_POOL_ESCAPE_CHANCE[MonsterSpeed.SLOW] == 0.0


def test_lava_pool_escape_chance_looks_up_by_speed():
    assert lava_pool_escape_chance(MonsterSpeed.FAST) == 0.60
    assert lava_pool_escape_chance(MonsterSpeed.MEDIUM) == 0.30
    assert lava_pool_escape_chance(MonsterSpeed.SLOW) == 0.0


def test_resolve_lava_pool_escape_fast_speed_threshold():
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.0])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.59])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.60])) is False
    assert resolve_lava_pool_escape(MonsterSpeed.FAST, ScriptedRandom([0.99])) is False


def test_resolve_lava_pool_escape_medium_speed_threshold():
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.0])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.29])) is True
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.30])) is False
    assert resolve_lava_pool_escape(MonsterSpeed.MEDIUM, ScriptedRandom([0.99])) is False


def test_resolve_lava_pool_escape_slow_speed_never_escapes():
    assert resolve_lava_pool_escape(MonsterSpeed.SLOW, ScriptedRandom([0.0])) is False
    assert resolve_lava_pool_escape(MonsterSpeed.SLOW, ScriptedRandom([0.99])) is False


def test_resolve_lava_pool_escape_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    resolve_lava_pool_escape(MonsterSpeed.MEDIUM, rng)


# -- Phase 205: Augur Combat [AC] --


def test_augur_combat_constants():
    assert AUGUR_COMBAT_FREE_WHEN_CAST_FIRST is True
    assert AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER is True
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.COWARDLY] == 0.80
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.CAUTIOUS] == 0.60
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.BRAVE] == 0.40
    assert AUGUR_COMBAT_SHIRK_CHANCE[Temper.BERSERK] == 0.20


def test_augur_combat_shirk_chance_looks_up_by_temper():
    assert augur_combat_shirk_chance(Temper.COWARDLY) == 0.80
    assert augur_combat_shirk_chance(Temper.CAUTIOUS) == 0.60
    assert augur_combat_shirk_chance(Temper.BRAVE) == 0.40
    assert augur_combat_shirk_chance(Temper.BERSERK) == 0.20


def test_resolve_augur_combat_shirk_cowardly_threshold():
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.0])) is True
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.79])) is True
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.80])) is False
    assert resolve_augur_combat_shirk(Temper.COWARDLY, ScriptedRandom([0.99])) is False


def test_resolve_augur_combat_shirk_berserk_threshold():
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.0])) is True
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.19])) is True
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.20])) is False
    assert resolve_augur_combat_shirk(Temper.BERSERK, ScriptedRandom([0.99])) is False


def test_resolve_augur_combat_shirk_consumes_exactly_one_roll():
    rng = ScriptedRandom([0.5])  # a second .random() call would raise IndexError
    resolve_augur_combat_shirk(Temper.BRAVE, rng)


def test_resolve_augur_combat_never_shirks_on_a_simulated_win():
    rng = ScriptedRandom([])  # a simulated win must not consume a roll at all
    assert resolve_augur_combat(would_lose_simulated_combat=False, temper=Temper.COWARDLY, rng=rng) is False


def test_resolve_augur_combat_rolls_the_shirk_chance_on_a_simulated_loss():
    assert (
        resolve_augur_combat(would_lose_simulated_combat=True, temper=Temper.COWARDLY, rng=ScriptedRandom([0.79]))
        is True
    )
    assert (
        resolve_augur_combat(would_lose_simulated_combat=True, temper=Temper.COWARDLY, rng=ScriptedRandom([0.80]))
        is False
    )


def test_spell_disruption_chance_still_defaults_to_the_normal_rate():
    # The keyword-only chance_per_point override doesn't change any
    # existing caller's behavior.
    assert spell_disruption_chance(1) == pytest.approx(SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT)


def test_resolve_spell_disruption_still_defaults_to_the_normal_rate():
    assert resolve_spell_disruption(1, ScriptedRandom([0.16])) is True
    assert resolve_spell_disruption(1, ScriptedRandom([0.17])) is False


# -- Phase 208: Illusory Hero [IH] --


def test_illusory_hero_constants():
    assert ILLUSORY_HERO_DISBELIEF_REDUCTION == 0.15
    assert ILLUSORY_HERO_TURNS_ON_MASTER_BY_DEFAULT is False


def test_illusory_hero_disbelief_chance_subtracts_a_further_15_percent():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.HIGH_HUMAN]  # 100%
    # Mirror-Image's own formula at level 0 leaves 100%; Illusory Hero
    # subtracts one further flat 15 percentage points on top of that.
    assert illusory_hero_disbelief_chance(base, 0) == pytest.approx(0.85)
    assert illusory_hero_disbelief_chance(base, 1) == pytest.approx(0.70)


def test_illusory_hero_disbelief_chance_clamps_to_0_percent():
    low_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MECHANICAL]  # 20%
    assert illusory_hero_disbelief_chance(low_base, 10) == 0.0


def test_illusory_hero_disbelief_chance_never_reaches_100_percent():
    # Mirror-Image's own per-round chance is already clamped to 100%
    # *before* Illusory Hero's flat -15% is applied, so the highest
    # achievable chance here is 85%, never 100% -- unlike Mirror-Image
    # itself, whose own Divine/Superhuman tier can hit 100% outright.
    high_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]  # 120%
    assert illusory_hero_disbelief_chance(high_base, 0) == pytest.approx(0.85)


def test_resolve_illusory_hero_disbelief_zero_percent_never_consumes_a_roll():
    rng = ScriptedRandom([])
    low_base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MECHANICAL]
    assert resolve_illusory_hero_disbelief(low_base, 10, rng) is False


def test_resolve_illusory_hero_disbelief_consumes_exactly_one_roll_in_between():
    base = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MEDIUM_HUMAN]  # 80%, minus 15% = 65%
    rng = ScriptedRandom([0.64])  # a second .random() call would raise IndexError
    assert resolve_illusory_hero_disbelief(base, 0, rng) is True
    rng = ScriptedRandom([0.65])
    assert resolve_illusory_hero_disbelief(base, 0, rng) is False


# -- Phase 209: CAST orchestration engine (Combatant extensions + PERSONAL_COMBAT_SPELL_ABILITY) --


def test_combatant_phase_209_fields_default_to_no_op():
    c = Combatant("A")
    assert c.defensive_hit_multiplier == 1.0
    assert c.melee_damage_dealt_reduction == 0
    assert c.blocked_from_cast_and_archery is False
    assert c.bonus_unanswered_attacks == 0


def test_personal_combat_spell_ability_covers_all_ten_base_spells():
    # Sourced from turn/cast_execution.py's own [4.2X.4]-[4.2X.5] citation
    # grouping (module docstring's Phase 209 addendum) -- five Ability
    # blocks, two spells each.
    assert PERSONAL_COMBAT_SPELL_ABILITY == {
        Spell.HOLY_SYMBOL: Ability.WHITE,
        Spell.SPIRITWRACK: Ability.WHITE,
        Spell.PSYCHIC_BLAST: Ability.PSYCHIC,
        Spell.TELEK_STORM: Ability.PSYCHIC,
        Spell.INVISIBILITY: Ability.ILLUSION,
        Spell.MIRROR_IMAGE: Ability.ILLUSION,
        Spell.FIREBALL: Ability.ELEMENTAL,
        Spell.ICE_SUSPEND: Ability.ELEMENTAL,
        Spell.HAND_OF_DEATH: Ability.NECROMANCY,
        Spell.CONTROL_UNDEAD: Ability.NECROMANCY,
    }


def test_roll_melee_attack_zero_hit_chance_multiplier_never_hits():
    rng = ScriptedRandom([0.0, 0.0, 0.0])  # even the lowest possible roll still misses
    assert roll_melee_attack(rng, hit_chance_multiplier=0.0) == 0
    assert roll_melee_attack(rng, hit_chance_multiplier=0.0) == 0
    assert roll_melee_attack(rng, hit_chance_multiplier=0.0) == 0


def test_roll_melee_attack_high_hit_chance_multiplier_always_hits():
    rng = ScriptedRandom([0.99, 0.5])  # even the highest possible roll still hits, then the damage roll
    damage = roll_melee_attack(rng, hit_chance_multiplier=10.0)
    assert 1 <= damage <= 6


def test_roll_fire_arrow_attack_zero_hit_chance_multiplier_never_hits():
    rng = ScriptedRandom([0.0])
    assert roll_fire_arrow_attack(3, rng, hit_chance_multiplier=0.0) == 0


def test_roll_fire_arrow_attack_high_hit_chance_multiplier_always_hits():
    rng = ScriptedRandom([0.99, 0.5])
    damage = roll_fire_arrow_attack(0, rng, hit_chance_multiplier=10.0)
    assert 1 <= damage <= 6


def test_resolve_melee_duel_defensive_hit_multiplier_prevents_defender_from_ever_being_hit():
    # A can never be hit (multiplier 0.0); regardless of who acts first or
    # how the dice fall, only A can ever land a blow, so A must eventually win.
    a = Combatant("A", defensive_hit_multiplier=0.0)
    b = Combatant("B")

    result = resolve_melee_duel(a, b, random.Random(1))

    assert result.winner == "a"
    assert a.hit_points == CHARACTER_HIT_POINTS
    assert b.hit_points <= 0


def test_resolve_melee_duel_melee_damage_dealt_reduction_floors_at_zero():
    # A's own outgoing damage is reduced far below zero -- every landed
    # hit still deals 0. A is also unhittable (defensive_hit_multiplier=0)
    # so B's own unaffected counter-attacks don't confound the assertion --
    # nobody can die, no matter how many rounds are played.
    a = Combatant("A", melee_skill=1, melee_damage_dealt_reduction=999, defensive_hit_multiplier=0.0)
    b = Combatant("B", melee_skill=0)

    result = resolve_melee_duel(a, b, random.Random(1), max_rounds=5)

    assert result.winner is None
    assert b.hit_points == CHARACTER_HIT_POINTS
    assert a.hit_points == CHARACTER_HIT_POINTS


def test_resolve_fire_arrow_duel_defensive_hit_multiplier_prevents_hits():
    # Only A has any free attacks (archery_skill=3 vs 0); B's own
    # defensive_hit_multiplier=0.0 means none of A's shots can ever land.
    a = Combatant("A", archery_skill=3)
    b = Combatant("B", archery_skill=0, defensive_hit_multiplier=0.0)

    result = resolve_fire_arrow_duel(a, b, random.Random(1))

    assert result.winner is None
    assert b.hit_points == CHARACTER_HIT_POINTS
    assert all(shot.hit is False and shot.damage == 0 for shot in result.shots)


# -- Phase 210: Hand of Death channel + Mirror-Image duel --


def test_resolve_hand_of_death_channel_immune_target_returns_immediately_no_roll():
    caster = Combatant("Caster")
    victim = Combatant("Victim")
    rng = ScriptedRandom([])  # any .random() call here raises IndexError

    result = resolve_hand_of_death_channel(caster, victim, 3, rng, target_is_immune=True)

    assert result.winner is None
    assert result.rounds == 0
    assert victim.hit_points == CHARACTER_HIT_POINTS
    assert caster.hit_points == CHARACTER_HIT_POINTS
    assert result.squeeze_hits == ()


def test_resolve_hand_of_death_channel_caster_kills_victim_without_ever_being_hit():
    # Necromancy skill 2 -> caster's own attack always lands for an exact
    # 2 damage (no coin-flip roll needed); caster's own initiative skill
    # (2) beats the victim's real Melee skill (0), so the caster always
    # acts first with no tie-break roll either. The victim's own halved
    # counter-attacks are scripted to miss for the two rounds it survives.
    caster = Combatant("Caster", hit_points=10)
    victim = Combatant("Victim", hit_points=5, melee_skill=0)
    rng = ScriptedRandom([0.9, 0.9])

    result = resolve_hand_of_death_channel(caster, victim, 2, rng)

    assert result.winner == "a"
    assert victim.hit_points <= 0
    assert caster.hit_points == 10
    # Phase 413: the caster's own 2-damage attack, once per round it acted
    # (round 3's killing blow included) -- see report/turn_report.py
    # render_squeeze_attack()'s own Phase 413 addendum.
    assert result.squeeze_hits == (2, 2, 2)


def test_resolve_hand_of_death_channel_ends_the_instant_the_caster_is_hit():
    caster = Combatant("Caster", hit_points=10)
    victim = Combatant("Victim", hit_points=10, melee_skill=0)
    rng = ScriptedRandom([0.1, 0.5])  # victim's halved-chance attack hits, then a damage roll

    result = resolve_hand_of_death_channel(caster, victim, 2, rng)

    assert result.winner is None
    assert result.rounds == 1
    assert caster.hit_points < 10
    assert victim.hit_points == 10 - 2  # the caster's own round-1 attack still landed first
    # Phase 413: the one round the caster did get to squeeze, even though
    # the channel itself ended without a winner.
    assert result.squeeze_hits == (2,)


def test_resolve_hand_of_death_channel_respects_max_rounds_cap():
    caster = Combatant("Caster", hit_points=10)
    victim = Combatant("Victim", hit_points=999999, melee_skill=0)
    rng = ScriptedRandom([0.9, 0.9, 0.9])  # victim's own attack misses every round

    result = resolve_hand_of_death_channel(caster, victim, 2, rng, max_rounds=3)

    assert result.winner is None
    assert result.rounds == 3
    assert caster.hit_points == 10


def test_mirror_image_monster_intelligence_tier_covers_every_real_species():
    real_species = {m for m in Monster if m is not Monster.NOMONSTER}
    assert set(MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER) == real_species


def test_mirror_image_monster_intelligence_tier_diverges_from_spiritwrack_for_three_species():
    # Confirmed by the user (Desktop "Intelligenza mostri.txt"): Giant
    # Worm/Amoeba/Clam are Spiritwrack-Animal-Intelligence but Mirror-
    # Image-Mechanical -- a genuine, sourced divergence between the two
    # classifications, not an oversight or a reuse of the Spiritwrack set.
    for species in (Monster.GI_WORM, Monster.GI_AMOEBA, Monster.GI_CLAM):
        assert MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER[species] is MirrorImageIntelligenceTier.MECHANICAL
        assert species in SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS


def test_mirror_image_leader_intelligence_tier_default_is_medium_human():
    # Phase 470: AKGEN_reverse_engineering_report (2).md SS21.4, certain
    # from the disassembly (`AK.OVR 0x1DCAC-0x1DCB7`) -- every playing
    # character (combatant id < 256) is hardcoded I=3 (Medium Human),
    # superseding the earlier project-author verbal note that had said
    # High Human.
    assert MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT is MirrorImageIntelligenceTier.MEDIUM_HUMAN


def test_mirror_image_leader_disbelief_bonus_matches_the_confirmed_rates():
    assert mirror_image_leader_disbelief_bonus(0, 0) == 0.0
    assert mirror_image_leader_disbelief_bonus(3, 0) == pytest.approx(0.06)
    assert mirror_image_leader_disbelief_bonus(0, 4) == pytest.approx(0.04)
    assert mirror_image_leader_disbelief_bonus(2, 5) == pytest.approx(0.04 + 0.05)


def test_resolve_mirror_image_duel_leader_bonus_applies_on_top_of_the_table_value():
    # High Human (100%) + a leader's own +6% (Sage 3) bonus = 106%, still
    # clamped to 100% by mirror_image_disbelief_chance -- guaranteed
    # disbelief, no roll consumed.
    caster = Combatant("Caster")
    opponent = Combatant("Opponent")
    rng = ScriptedRandom([])
    bonus = mirror_image_leader_disbelief_bonus(3, 0)

    result = resolve_mirror_image_duel(
        caster, opponent, MirrorImageIntelligenceTier.HIGH_HUMAN, 0, rng, opponent_disbelief_bonus=bonus
    )

    assert result.winner is None
    assert result.rounds == 1


def test_resolve_mirror_image_duel_opponent_detect_illusions_adds_flat_25_percent():
    # Phase 463 -- SS21.4's own `D` term. Low Human base is 60% at level
    # 0 -- 0.70 would NOT disbelieve on its own. Detect Illusions' flat
    # +25 points raises it to 85%, so the same 0.70 roll DOES disbelieve.
    caster = Combatant("Caster")
    opponent = Combatant("Opponent")
    rng = ScriptedRandom([0.70])

    result = resolve_mirror_image_duel(
        caster, opponent, MirrorImageIntelligenceTier.LOW_HUMAN, 0, rng, opponent_has_detect_illusions=True
    )

    assert result.winner is None
    assert result.rounds == 1


def test_resolve_mirror_image_duel_caster_detect_illusions_pushes_stage2_to_guaranteed_disbelief():
    # Same Stage 1 setup as test_resolve_mirror_image_duel_stage2_caster_
    # disbelieves_and_wins (tie-break -> illusion acts first, lands a hit
    # + damage roll, mentally slaying the 1 hp opponent). Stage 2:
    # without Detect Illusions the 105% master base minus 30% (level 2)
    # is a real 75% chance that needs a roll; with caster_has_detect_
    # illusions=True it's 130% minus 30% = 100%, clamped -- a guaranteed
    # disbelief that consumes no further roll at all (only the 3 Stage-1
    # values are scripted here, not the extra one a real 75%-chance roll
    # would need).
    caster = Combatant("Caster", hit_points=10, melee_skill=1)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=1)
    rng = ScriptedRandom([0.1, 0.1, 0.5])

    result = resolve_mirror_image_duel(
        caster, opponent, MirrorImageIntelligenceTier.MECHANICAL, 2, rng, caster_has_detect_illusions=True
    )

    assert result.winner == "a"
    assert result.rounds == 2
    assert caster.hit_points == 10


def test_resolve_mirror_image_duel_disbelieved_immediately_returns_no_winner_no_roll():
    caster = Combatant("Caster")
    opponent = Combatant("Opponent")
    rng = ScriptedRandom([])  # 120% base at level 0 clamps to a guaranteed disbelief -- no roll

    result = resolve_mirror_image_duel(caster, opponent, MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN, 0, rng)

    assert result.winner is None
    assert result.rounds == 1
    assert caster.hit_points == CHARACTER_HIT_POINTS
    assert opponent.hit_points == CHARACTER_HIT_POINTS


def test_resolve_mirror_image_duel_stage1_illusion_dies_falls_through_to_real_combat():
    # Mechanical tier (20% base) at level 2 clamps the per-round disbelief
    # chance to 0% -- guaranteed *not* disbelieved, no roll consumed for
    # that check. The opponent (1 hp) then kills the illusion outright on
    # the very first exchange; the real caster is never touched, per the
    # rule ("the caster must concentrate... performing no other actions").
    caster = Combatant("Caster", hit_points=10, melee_skill=1)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=1)
    rng = ScriptedRandom([0.9, 0.1, 0.5])  # tie-break -> opponent first, then a landed hit + damage

    result = resolve_mirror_image_duel(caster, opponent, MirrorImageIntelligenceTier.MECHANICAL, 2, rng)

    assert result.winner is None
    assert result.rounds == 1
    assert caster.hit_points == 10
    assert opponent.hit_points == 1


def test_resolve_mirror_image_duel_stage2_caster_disbelieves_and_wins():
    caster = Combatant("Caster", hit_points=10, melee_skill=1)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=1)
    rng = ScriptedRandom([0.1, 0.1, 0.5, 0.1])
    # Stage 1: tie-break -> illusion acts first, lands a hit + damage roll,
    # mentally slaying the (1 hp) opponent. Stage 2: at level 2, the 105%
    # master base reduces to a real 75% chance -- 0.1 < 0.75 disbelieves.

    result = resolve_mirror_image_duel(caster, opponent, MirrorImageIntelligenceTier.MECHANICAL, 2, rng)

    assert result.winner == "a"
    assert result.rounds == 2
    assert caster.hit_points == 10


def test_resolve_mirror_image_duel_stage2_illusion_kills_the_caster():
    caster = Combatant("Caster", hit_points=1, melee_skill=1)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=1)
    rng = ScriptedRandom([0.1, 0.1, 0.5, 0.9, 0.9, 0.1, 0.5])
    # Stage 1: illusion mentally slays the opponent (same shape as above).
    # Stage 2: the 0.9 roll fails to disbelieve (< 0.75 needed), so a real
    # round happens; the second 0.9 is the tie-break -- in Stage 2 the
    # roll's own True/False sense is flipped from Stage 1 (skill_a is now
    # the caster's own skill, not the illusion's), so >= 0.5 puts the
    # illusion first here -- and its landed hit finishes off the
    # caster's own 1 hp.

    result = resolve_mirror_image_duel(caster, opponent, MirrorImageIntelligenceTier.MECHANICAL, 2, rng)

    assert result.winner == "b"
    assert result.rounds == 2


def test_illusory_hero_hostile_alignment_pairs_table():
    assert ILLUSORY_HERO_HOSTILE_ALIGNMENT_PAIRS == {
        frozenset({Alignment.DIVINE, Alignment.PAGAN}),
        frozenset({Alignment.DIVINE, Alignment.EVIL}),
        frozenset({Alignment.DIVINE, Alignment.UNDEAD}),
        frozenset({Alignment.GOOD, Alignment.EVIL}),
        frozenset({Alignment.GOOD, Alignment.UNDEAD}),
        frozenset({Alignment.UNDEAD, Alignment.DRUID}),
    }


def test_illusory_hero_alignments_are_implacably_hostile_confirmed_pairs():
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.GOOD, Alignment.EVIL) is True
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.EVIL, Alignment.GOOD) is True  # symmetric
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.DIVINE, Alignment.PAGAN) is True
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.UNDEAD, Alignment.DRUID) is True


def test_illusory_hero_alignments_are_implacably_hostile_false_for_unconfirmed_pairs():
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.GOOD, Alignment.DIVINE) is False
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.NEUTRAL, Alignment.EVIL) is False
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.DRUID, Alignment.GOOD) is False
    assert illusory_hero_alignments_are_implacably_hostile(Alignment.MECHANICAL, Alignment.SPECIAL) is False


def test_resolve_illusory_hero_duel_stage1_disbelieved_returns_no_winner_and_no_combat():
    caster = Combatant("Caster", hit_points=10)
    opponent = Combatant("Opponent", hit_points=10)
    hero = Combatant("Hero", hit_points=10, melee_skill=5)
    rng = ScriptedRandom([0.1])
    # High Human base (100%) at level 0, minus the flat 15% Illusory Hero
    # reduction, is 85% -- unlike Mirror-Image this never reaches a fixed
    # 100%, so a real roll is consumed; 0.1 < 0.85 disbelieves on the very
    # first round, before any melee exchange happens.

    result = resolve_illusory_hero_duel(caster, opponent, hero, MirrorImageIntelligenceTier.HIGH_HUMAN, 0, rng)

    assert result.winner is None
    assert result.rounds == 1
    assert caster.hit_points == 10
    assert opponent.hit_points == 10


def test_resolve_illusory_hero_duel_leader_bonus_applies_on_top_of_the_table_value():
    caster = Combatant("Caster", hit_points=10)
    opponent = Combatant("Opponent", hit_points=10)
    hero = Combatant("Hero", hit_points=10)
    bonus = mirror_image_leader_disbelief_bonus(5, 0)  # +10% (Sage level 5)
    rng = ScriptedRandom([0.55])
    # Medium Human base (80%) at level 1: without the bonus the real
    # chance is 50% (0.55 would NOT disbelieve); with the +10% bonus it
    # rises to 60%, so the same 0.55 roll DOES disbelieve.

    result = resolve_illusory_hero_duel(
        caster, opponent, hero, MirrorImageIntelligenceTier.MEDIUM_HUMAN, 1, rng, opponent_disbelief_bonus=bonus
    )

    assert result.winner is None
    assert result.rounds == 1


def test_resolve_illusory_hero_duel_opponent_detect_illusions_adds_flat_25_percent():
    # Phase 463 -- SS21.4's own `D` term. Low Human base (60%) minus
    # Illusory Hero's own flat 15% is 45% at level 0 -- 0.50 would NOT
    # disbelieve on its own. Detect Illusions' +25 points raises the
    # pre-Illusory-Hero chance to 85%, so after the same -15% it's 70% --
    # the same 0.50 roll now disbelieves.
    caster = Combatant("Caster", hit_points=10)
    opponent = Combatant("Opponent", hit_points=10)
    hero = Combatant("Hero", hit_points=10)
    rng = ScriptedRandom([0.50])

    result = resolve_illusory_hero_duel(
        caster, opponent, hero, MirrorImageIntelligenceTier.LOW_HUMAN, 0, rng, opponent_has_detect_illusions=True
    )

    assert result.winner is None
    assert result.rounds == 1


def test_resolve_illusory_hero_duel_caster_detect_illusions_adds_flat_25_percent_to_stage2():
    # Same Stage 1 setup as test_resolve_illusory_hero_duel_stage2_caster_
    # disbelieves_and_wins (the hero-illusion's guaranteed hit-chance +
    # damage roll kills the 1 hp opponent outright -- no tie-break needed
    # since the hero's own skill 5 beats the opponent's 0). Stage 2:
    # without Detect Illusions the master base (105%) minus 30% (level 2)
    # minus the flat 15% Illusory Hero reduction is 60% -- 0.70 would NOT
    # disbelieve on its own. With caster_has_detect_illusions=True the
    # pre-Illusory-Hero chance is instead clamped to 100%, so after the
    # same -15% it's 85% -- the same 0.70 roll now disbelieves.
    caster = Combatant("Caster", hit_points=10, melee_skill=0)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=0)
    hero = Combatant("Hero", hit_points=10, melee_skill=5, melee_damage_range=(10, 10))
    rng = ScriptedRandom([0.1, 0.5, 0.70])

    result = resolve_illusory_hero_duel(
        caster,
        opponent,
        hero,
        MirrorImageIntelligenceTier.MECHANICAL,
        2,
        rng,
        turns_on_master=True,
        caster_has_detect_illusions=True,
    )

    assert result.winner == "a"
    assert result.rounds == 2
    assert caster.hit_points == 10


def test_resolve_illusory_hero_duel_stage1_win_without_turning_on_master_is_instant():
    caster = Combatant("Caster", hit_points=10, melee_skill=0)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=0)
    hero = Combatant("Hero", hit_points=10, melee_skill=5, melee_damage_range=(10, 10))
    rng = ScriptedRandom([0.1, 0.5])
    # Mechanical tier at level 2 clamps disbelief to 0% (no roll). The
    # hero-illusion's higher skill (5 > 0) means no tie-break roll either
    # -- it acts first and a guaranteed hit (10-10 damage range) kills
    # the 1 hp opponent outright. With turns_on_master=False, Stage 1's
    # win is an immediate caster victory -- no Stage 2 duel at all.

    result = resolve_illusory_hero_duel(
        caster, opponent, hero, MirrorImageIntelligenceTier.MECHANICAL, 2, rng, turns_on_master=False
    )

    assert result.winner == "a"
    assert result.rounds == 1
    assert caster.hit_points == 10


def test_resolve_illusory_hero_duel_stage2_caster_disbelieves_and_wins():
    caster = Combatant("Caster", hit_points=10, melee_skill=0)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=0)
    hero = Combatant("Hero", hit_points=10, melee_skill=5, melee_damage_range=(10, 10))
    rng = ScriptedRandom([0.1, 0.5, 0.1])
    # Stage 1 as above kills the opponent outright. Stage 2 (only reached
    # because turns_on_master=True): the master base (105%) minus 30%
    # (level 2) minus a further flat 15% is 60% -- 0.1 < 0.6 disbelieves
    # immediately, no Stage 2 combat round.

    result = resolve_illusory_hero_duel(
        caster, opponent, hero, MirrorImageIntelligenceTier.MECHANICAL, 2, rng, turns_on_master=True
    )

    assert result.winner == "a"
    assert result.rounds == 2
    assert caster.hit_points == 10


def test_resolve_illusory_hero_duel_stage2_illusion_kills_the_caster():
    caster = Combatant("Caster", hit_points=1, melee_skill=0)
    opponent = Combatant("Opponent", hit_points=1, melee_skill=0)
    hero = Combatant("Hero", hit_points=10, melee_skill=5, melee_damage_range=(10, 10))
    rng = ScriptedRandom([0.1, 0.5, 0.9, 0.1, 0.5])
    # Stage 1 kills the opponent outright (same shape as above). Stage 2:
    # the 0.9 roll fails to disbelieve (needs < 0.6); the hero-illusion's
    # higher skill (5 > 0) means it acts first with no tie-break roll,
    # and its guaranteed hit (10-10 damage range) finishes off the
    # caster's own 1 hp.

    result = resolve_illusory_hero_duel(
        caster, opponent, hero, MirrorImageIntelligenceTier.MECHANICAL, 2, rng, turns_on_master=True
    )

    assert result.winner == "b"
    assert result.rounds == 2


# -- Phase 506: Steal, real disassembly-sourced formula --


def test_steal_success_chance_base_and_per_level():
    # raw = 15*(1 + min(4,S)), divisor = 1, no M/I/E/H terms.
    assert steal_success_chance(0) == pytest.approx(0.15)
    assert steal_success_chance(1) == pytest.approx(0.30)
    assert steal_success_chance(2) == pytest.approx(0.45)
    assert steal_success_chance(4) == pytest.approx(0.75)


def test_steal_success_chance_level_term_caps_at_4():
    # min(4, S) -- level 9 gives the same raw chance as level 4.
    assert steal_success_chance(9) == pytest.approx(steal_success_chance(4)) == pytest.approx(0.75)


def test_steal_success_chance_thief_mastery_adds_one_to_raw():
    # level 0, M=1: raw = 15*(1+0+1) = 30 -> 0.30.
    assert steal_success_chance(0, has_thief_mastery=True) == pytest.approx(0.30)


def test_steal_success_chance_invisibility_and_enhanced_invisibility():
    # level 0, I=1, E=0: raw = 15*(1+0+0+1*1) = 30 -> 0.30.
    assert steal_success_chance(0, is_invisible=True) == pytest.approx(0.30)
    # level 0, I=1, E=1: raw = 15*(1+0+0+1*2) = 45 -> 0.45.
    assert steal_success_chance(0, is_invisible=True, has_enhanced_invisibility=True) == pytest.approx(0.45)
    # Enhanced Invisibility alone (I=0) contributes nothing.
    assert steal_success_chance(0, has_enhanced_invisibility=True) == pytest.approx(0.15)


def test_steal_success_chance_caps_at_95_percent():
    # level 4, M=1, I=1, E=1: raw = 15*(1+4+1+1*2) = 120 -> capped to 95%.
    assert (
        steal_success_chance(4, has_thief_mastery=True, is_invisible=True, has_enhanced_invisibility=True)
        == pytest.approx(STEAL_SUCCESS_MAX_CHANCE)
        == pytest.approx(0.95)
    )


def test_steal_success_chance_halved_against_a_king_or_army_commander():
    # level 4, H=1: raw = 75, divisor = 2 -> 75 // 2 = 37 -> 0.37 (integer
    # division happens before the percentage cap, not after).
    assert steal_success_chance(4, target_leads_army_or_is_king=True) == pytest.approx(0.37)


def test_resolve_steal_attempt_uses_the_success_chance():
    rng = ScriptedRandom([0.29, 0.31])
    # level 1 -> 30% chance: 0.29 succeeds, 0.31 fails.
    assert resolve_steal_attempt(1, rng) is True
    assert resolve_steal_attempt(1, rng) is False


def test_steal_evasion_chance_base_and_per_level():
    assert steal_evasion_chance(0) == pytest.approx(0.10)
    assert steal_evasion_chance(1) == pytest.approx(0.175)
    # The dossier's own worked example: level 9 -> 77.5%.
    assert steal_evasion_chance(9) == pytest.approx(0.775)


def test_steal_evasion_chance_caps_at_100_percent():
    assert steal_evasion_chance(12) == pytest.approx(1.0)
    assert steal_evasion_chance(20) == pytest.approx(1.0)


def test_resolve_steal_evasion_uses_the_evasion_chance():
    rng = ScriptedRandom([0.17, 0.18])
    # level 1 -> 17.5% chance: 0.17 evades, 0.18 doesn't.
    assert resolve_steal_evasion(1, rng) is True
    assert resolve_steal_evasion(1, rng) is False


def test_steal_thief_mastery_abilities_span_all_five_tiers():
    assert STEAL_THIEF_MASTERY_ABILITIES == {
        AdvancedAbility.THIEF_MASTERY_I,
        AdvancedAbility.THIEF_MASTERY_II,
        AdvancedAbility.THIEF_MASTERY_III,
        AdvancedAbility.THIEF_MASTERY_IV,
        AdvancedAbility.THIEF_MASTERY_V,
    }


def test_steal_character_item_transfer_chance_halves_after_each_transfer():
    # 75, 37, 18, 9, 4, 2, 1, 0 -- integer right-shift, not float halving.
    assert [steal_character_item_transfer_chance(n) for n in range(8)] == pytest.approx(
        [0.75, 0.37, 0.18, 0.09, 0.04, 0.02, 0.01, 0.0]
    )


def test_resolve_steal_character_item_transfer_uses_the_chance():
    rng = ScriptedRandom([0.74, 0.76])
    assert resolve_steal_character_item_transfer(0, rng) is True
    assert resolve_steal_character_item_transfer(0, rng) is False


def test_steal_ransom_amount_rounds_up_half():
    assert steal_ransom_amount(10) == 5
    assert steal_ransom_amount(11) == 6
    assert steal_ransom_amount(0) == 0
    assert steal_ransom_amount(1) == 1


def test_steal_monster_item_transfer_chance_matches_the_dossiers_intelligence_table():
    # Mech=0 99%, Semi=1 97%, Low=2 94%, Medium=3 88%, High=4 75%,
    # Godlike=5 50% -- confirmed to match only with Mech at ordinal 0
    # (independently cross-checking Phase 504's own MECH ordinal fix).
    assert steal_monster_item_transfer_chance(0, 0) == pytest.approx(0.99)
    assert steal_monster_item_transfer_chance(1, 0) == pytest.approx(0.97)
    assert steal_monster_item_transfer_chance(2, 0) == pytest.approx(0.94)
    assert steal_monster_item_transfer_chance(3, 0) == pytest.approx(0.88)
    assert steal_monster_item_transfer_chance(4, 0) == pytest.approx(0.75)
    assert steal_monster_item_transfer_chance(5, 0) == pytest.approx(0.50)


def test_steal_monster_item_transfer_chance_halves_after_each_transfer():
    # Mech (99%) after one prior transfer: 99 >> 1 = 49 -> 0.49.
    assert steal_monster_item_transfer_chance(0, 1) == pytest.approx(0.49)


def test_resolve_steal_monster_item_transfer_uses_the_chance():
    rng = ScriptedRandom([0.98, 0.99])
    assert resolve_steal_monster_item_transfer(0, 0, rng) is True
    assert resolve_steal_monster_item_transfer(0, 0, rng) is False


def test_monster_steal_gold_if_no_item_covers_every_real_species():
    all_real_species = set(Monster) - {Monster.NOMONSTER}
    assert MONSTER_STEAL_GOLD_IF_NO_ITEM.keys() == all_real_species
    # Spot-check a few of the dossier's own named magnitudes.
    assert MONSTER_STEAL_GOLD_IF_NO_ITEM[Monster.GO_DRAGON] == 6
    assert MONSTER_STEAL_GOLD_IF_NO_ITEM[Monster.TITAN] == 6
    assert MONSTER_STEAL_GOLD_IF_NO_ITEM[Monster.ROC] == 1
    assert MONSTER_STEAL_GOLD_IF_NO_ITEM[Monster.MERMAID] == 1


# -- Phase 240: Talk / Say / Fulfill --


def test_talk_monster_druid_level_required_covers_all_60_species():
    all_real_species = set(Monster) - {Monster.NOMONSTER}
    assert TALK_MONSTER_DRUID_LEVEL_REQUIRED.keys() == all_real_species


def test_talk_monster_druid_level_required_spot_values():
    # Sourced from HostAK/TP/CTME.PAS's own talkdiff table, per the user's
    # own confirmation to prefer it over their supplied text where the two
    # disagreed (see module docstring's own Phase 240 addendum).
    assert TALK_MONSTER_DRUID_LEVEL_REQUIRED[Monster.ROC] == 1
    assert TALK_MONSTER_DRUID_LEVEL_REQUIRED[Monster.COUATL] == 0
    assert TALK_MONSTER_DRUID_LEVEL_REQUIRED[Monster.GOLEM] == 4
    assert TALK_MONSTER_DRUID_LEVEL_REQUIRED[Monster.CHIMERA] == 4
    assert TALK_MONSTER_DRUID_LEVEL_REQUIRED[Monster.ARCHER] == 0


def test_talk_monster_druid_level_required_documented_disagreements_with_user_compiled_list():
    # Phase 549: Desktop/TALK SAY FULFILL.txt's own "DR che serve per
    # parlarci" table disagrees with this Pascal-sourced (CTME.PAS
    # talkdiff) table for exactly these 17 of 60 species -- pinned here
    # as the deliberate resolution (the Pascal table wins, per the
    # user's own direct confirmation, same precedent as Phase 545's own
    # monster-intelligence resolution), not an oversight. If any of
    # these ever changes, TALK_MONSTER_DRUID_LEVEL_REQUIRED's own module
    # comment needs updating too.
    disagreements = {
        Monster.BEHOLDER: 2,  # TALK SAY FULFILL.txt: 1
        Monster.B_DRAGON: 0,  # TALK SAY FULFILL.txt: 2
        Monster.CHIMERA: 4,  # TALK SAY FULFILL.txt: 2
        Monster.ELE_MAGE: 0,  # TALK SAY FULFILL.txt: 1
        Monster.GARGOYLE: 2,  # TALK SAY FULFILL.txt: 1
        Monster.GHOST: 0,  # TALK SAY FULFILL.txt: 1
        Monster.GIANT: 0,  # TALK SAY FULFILL.txt: 1
        Monster.GI_CLAM: 2,  # TALK SAY FULFILL.txt: 4
        Monster.GI_WORM: 3,  # TALK SAY FULFILL.txt: 4
        Monster.GR_DRAGON: 0,  # TALK SAY FULFILL.txt: 1
        Monster.HYDRA: 4,  # TALK SAY FULFILL.txt: 2
        Monster.IMP: 0,  # TALK SAY FULFILL.txt: 1
        Monster.MERMAID: 0,  # TALK SAY FULFILL.txt: 2
        Monster.MUMMY: 0,  # TALK SAY FULFILL.txt: 1
        Monster.SPECTRE: 0,  # TALK SAY FULFILL.txt: 1
        Monster.TROLL: 0,  # TALK SAY FULFILL.txt: 1
        Monster.WEREWOLF: 0,  # TALK SAY FULFILL.txt: 1
    }
    assert len(disagreements) == 17
    for monster, expected in disagreements.items():
        assert TALK_MONSTER_DRUID_LEVEL_REQUIRED[monster] == expected


def test_can_talk_to_monster_gate():
    assert can_talk_to_monster(Monster.GARGOYLE, 1) is False
    assert can_talk_to_monster(Monster.GARGOYLE, 2) is True
    assert can_talk_to_monster(Monster.ARCHER, 0) is True


def test_resolve_talk_reaction_boundaries():
    # Attack 0-0.40, Ignore 0.40-0.75, Deal 0.75-1.0.
    assert resolve_talk_reaction(ScriptedRandom([0.0])) is TalkReaction.ATTACK
    assert resolve_talk_reaction(ScriptedRandom([TALK_ATTACK_CHANCE - 0.01])) is TalkReaction.ATTACK
    assert resolve_talk_reaction(ScriptedRandom([TALK_ATTACK_CHANCE])) is TalkReaction.IGNORE
    assert (
        resolve_talk_reaction(ScriptedRandom([TALK_ATTACK_CHANCE + TALK_IGNORE_CHANCE - 0.01]))
        is TalkReaction.IGNORE
    )
    assert resolve_talk_reaction(ScriptedRandom([TALK_ATTACK_CHANCE + TALK_IGNORE_CHANCE])) is TalkReaction.DEAL
    assert resolve_talk_reaction(ScriptedRandom([0.999])) is TalkReaction.DEAL


def test_resolve_talk_reaction_druidic_shifts_attack_to_deal():
    # A roll that reads Ignore/Deal for a non-Druidic caster (0.30 is above
    # the Druidic 20% attack threshold) reads Attack for a Druidic one.
    assert resolve_talk_reaction(ScriptedRandom([0.30]), caster_is_druidic=False) is TalkReaction.ATTACK
    assert resolve_talk_reaction(ScriptedRandom([0.30]), caster_is_druidic=True) is TalkReaction.IGNORE
    # Ignore's own boundary is unaffected by the Druidic bonus.
    assert (
        resolve_talk_reaction(ScriptedRandom([TALK_DRUIDIC_ATTACK_CHANCE]), caster_is_druidic=True)
        is TalkReaction.IGNORE
    )


# -- Phase 468: Silver Tongue never lets a Talk reaction turn violent ---


def test_resolve_talk_reaction_silver_tongue_downgrades_attack_to_ignore():
    # A roll that would be ATTACK for anyone else reads IGNORE for the
    # Silver Tongue titleholder -- report SS18.4's own "un mostro non
    # reagisce violentemente a TALK".
    assert resolve_talk_reaction(ScriptedRandom([0.0]), caster_is_silver_tongue=False) is TalkReaction.ATTACK
    assert resolve_talk_reaction(ScriptedRandom([0.0]), caster_is_silver_tongue=True) is TalkReaction.IGNORE


def test_resolve_talk_reaction_silver_tongue_does_not_touch_ignore_or_deal():
    # The guarantee is only "never violent" -- Ignore and Deal keep their
    # own ordinary boundaries exactly as they already were.
    assert (
        resolve_talk_reaction(ScriptedRandom([TALK_ATTACK_CHANCE]), caster_is_silver_tongue=True)
        is TalkReaction.IGNORE
    )
    assert (
        resolve_talk_reaction(ScriptedRandom([0.999]), caster_is_silver_tongue=True) is TalkReaction.DEAL
    )


# -- Phase 382: the real 24-reply Talk selector -----------------------------


def test_monster_talk_reply_covers_all_24_real_ids():
    assert len(MonsterTalkReply) == 24
    assert len(MONSTER_TALK_REPLY_NAME) == 24
    assert len(MONSTER_TALK_REPLY_FREQUENCY) == 24
    assert len(MONSTER_TALK_REPLY_INTELLIGENCE) == 24
    assert len(MONSTER_TALK_REPLY_INTELLIGENCE_VARIANCE) == 24
    assert len(MONSTER_TALK_REPLY_VIEW) == 24
    assert len(MONSTER_TALK_REPLY_VIEW_VARIANCE) == 24
    assert len(MONSTER_TALK_REPLY_INVOLVES_CHARACTER) == 24
    assert len(MONSTER_TALK_REPLY_OUTCOME) == 24


def test_monster_talk_reply_outcome_categories_match_the_real_source():
    # ids {0, 2} ignore, {1, 23} attack, the remaining 20 are each a
    # distinct quest/agreement.
    assert MONSTER_TALK_REPLY_OUTCOME[MonsterTalkReply.R_PUZZLED] is TalkReplyOutcome.IGNORE
    assert MONSTER_TALK_REPLY_OUTCOME[MonsterTalkReply.R_WARN] is TalkReplyOutcome.IGNORE
    assert MONSTER_TALK_REPLY_OUTCOME[MonsterTalkReply.R_CHARGE] is TalkReplyOutcome.ATTACK
    assert MONSTER_TALK_REPLY_OUTCOME[MonsterTalkReply.R_MADVANCE] is TalkReplyOutcome.ATTACK
    quest_count = sum(1 for outcome in MONSTER_TALK_REPLY_OUTCOME.values() if outcome is TalkReplyOutcome.QUEST_OR_AGREEMENT)
    assert quest_count == 20


def test_monster_talk_reply_only_frevenge_and_prevenge_involve_a_character():
    involved = {reply for reply, flag in MONSTER_TALK_REPLY_INVOLVES_CHARACTER.items() if flag}
    assert involved == {MonsterTalkReply.R_FREVENGE, MonsterTalkReply.R_PREVENGE}


# -- Phase 581: MTALK.X2/FULFILL.X2/MACCEPT.X2 -------------------------------


def test_monster_talk_offer_text_covers_all_24_ids():
    assert len(MONSTER_TALK_OFFER_TEXT) == 24


def test_monster_talk_offer_text_has_real_content_even_for_ignore_and_attack():
    # Unlike FULFILL/MACCEPT, MTALK is shown for every one of the 24
    # replies -- even the Ignore/Attack ones have real source text here.
    assert MONSTER_TALK_OFFER_TEXT[MonsterTalkReply.R_PUZZLED] != ""
    assert MONSTER_TALK_OFFER_TEXT[MonsterTalkReply.R_CHARGE] != ""
    assert MONSTER_TALK_OFFER_TEXT[MonsterTalkReply.R_WARN] != ""
    assert MONSTER_TALK_OFFER_TEXT[MonsterTalkReply.R_MADVANCE] != ""


def test_monster_talk_fulfill_and_accept_text_cover_all_24_ids():
    assert len(MONSTER_TALK_FULFILL_TEXT) == 24
    assert len(MONSTER_TALK_ACCEPT_TEXT) == 24


def test_monster_talk_fulfill_and_accept_text_are_blank_for_non_quest_replies():
    # The source's own literal "na" for these four -- they never reach a
    # real quest to fulfill.
    for reply in (MonsterTalkReply.R_PUZZLED, MonsterTalkReply.R_CHARGE, MonsterTalkReply.R_WARN, MonsterTalkReply.R_MADVANCE):
        assert MONSTER_TALK_FULFILL_TEXT[reply] == ""
        assert MONSTER_TALK_ACCEPT_TEXT[reply] == ""


def test_monster_talk_fulfill_text_rwish_is_blank_not_na():
    # Genuinely blank in the source (not "na") -- the hero's wish is
    # spoken via a separate SAY order instead, per report/turn_report.py's
    # own already-documented Phase 129 finding.
    assert MONSTER_TALK_FULFILL_TEXT[MonsterTalkReply.R_WISH] == ""


def test_monster_talk_text_verbatim_samples():
    assert MONSTER_TALK_OFFER_TEXT[MonsterTalkReply.R_CHARGE] == "[1 attacked without warning."
    assert MONSTER_TALK_FULFILL_TEXT[MonsterTalkReply.R_SLAVE] == (
        "< visited [, bringing/Roffering food/Rprovisions, and {for ⟦CTRL-A:a/an⟧ time }cared "
        "after [{, a fierce/Rstrong but waning/Raged creature/Rbeing}."
    )
    assert MONSTER_TALK_ACCEPT_TEXT[MonsterTalkReply.R_SELL].startswith('[1 held forth ] \\ and nodded.')


def test_monster_talk_text_preserves_control_byte_and_pronoun_markers_literally():
    # Not resolved -- this project's own pronoun-substitution system is
    # explicitly out of scope, same posture OFFICE_TITLE_DESCRIPTION
    # already took for its own </>/[/]  markers.
    assert "⟦CTRL-T:treasure-2⟧" in MONSTER_TALK_OFFER_TEXT[MonsterTalkReply.R_REGAIN]
    assert "[1" in MONSTER_TALK_ACCEPT_TEXT[MonsterTalkReply.R_REGAIN]


def test_monster_talk_reply_eligible_roc_matches_the_real_view_and_intelligence_bands():
    # Roc: base_view=Pagan (ordinal 4), intelligence=Semi (ordinal 0;
    # Phase 381's own MONSTER_RUNTIME_PROFILE). RPuzzled (view=Special
    # ordinal 9, rvvar=0) is never eligible for Roc -- |9-4|=5 > 0.
    # RPain (view=Neutral ordinal 3, rvvar=2; intel=Semi, rivar=0) IS
    # eligible: |3-4|=1 <= 2 and |0-0|=0 <= 0.
    assert monster_talk_reply_eligible(MonsterTalkReply.R_PUZZLED, Monster.ROC) is False
    assert monster_talk_reply_eligible(MonsterTalkReply.R_PAIN, Monster.ROC) is True
    # RWish (view=Divine ordinal 0, rvvar=1) is far outside Roc's own
    # Pagan view: |0-4|=4 > 1.
    assert monster_talk_reply_eligible(MonsterTalkReply.R_WISH, Monster.ROC) is False


def test_monster_talk_reply_eligible_rmate_requires_can_offer_mate_quest():
    # Archer's own MONSTER_RUNTIME_PROFILE.can_offer_mate_quest is False
    # (Phase 381); Centaur's is True. Both otherwise pass RMate's own
    # view/intelligence bands (view=Neutral rvvar=2, intel=Low rivar=2).
    assert monster_talk_reply_eligible(MonsterTalkReply.R_MATE, Monster.ARCHER) is False
    assert monster_talk_reply_eligible(MonsterTalkReply.R_MATE, Monster.CENTAUR) is True


def test_monster_talk_reply_eligible_rsell_requires_the_caller_supplied_flag():
    assert monster_talk_reply_eligible(MonsterTalkReply.R_SELL, Monster.ARCHER, has_purchasable_treasure=False) is False
    assert monster_talk_reply_eligible(MonsterTalkReply.R_SELL, Monster.ARCHER, has_purchasable_treasure=True) is True


def test_monster_talk_reply_eligible_rtrade_reflects_the_fixed_mech_ordinal_for_gi_amoeba():
    # Phase 504: Giant Amoeba's own MonsterIntelligence is Mech (base_view
    # Pagan, ordinal 4). RTrade (view=Neutral ordinal 3, rvvar=4; passes:
    # |3-4|=1<=4) is keyed to intel=High with rivar=2. Under the earlier,
    # unsourced MECH=5 placeholder, |5-3|=2<=2 made this reply eligible;
    # the CTBOTH.PAS-confirmed MECH=0 gives |0-4|=4>2, correctly making it
    # ineligible -- this is the one real behavior change from the ordinal
    # fix (see MONSTER_INTELLIGENCE_ORDINAL's own Phase 504 docstring).
    assert monster_talk_reply_eligible(MonsterTalkReply.R_TRADE, Monster.GI_AMOEBA) is False


def test_select_monster_talk_reply_sphinx_forces_rriddle_below_50_percent():
    assert select_monster_talk_reply(Monster.SPHINX, ScriptedRandom([0.0])) is MonsterTalkReply.R_RIDDLE
    assert select_monster_talk_reply(Monster.SPHINX, ScriptedRandom([0.49])) is MonsterTalkReply.R_RIDDLE


def test_select_monster_talk_reply_sphinx_falls_through_to_general_selector_at_50_percent():
    # >= 0.5 skips the forced RRiddle branch and falls through to the
    # general selector instead (a real random.Random since the general
    # selector's own .choice() calls aren't scripted here).
    rng = random.Random(7)
    for _ in range(20):
        result = select_monster_talk_reply(Monster.SPHINX, rng)
        assert result is not None


def test_select_monster_talk_reply_only_returns_eligible_replies_for_the_monster():
    rng = random.Random(1234)
    eligible = {reply for reply in MonsterTalkReply if monster_talk_reply_eligible(reply, Monster.ROC)}
    for _ in range(200):
        result = select_monster_talk_reply(Monster.ROC, rng)
        assert result in eligible


def test_select_monster_talk_reply_returns_none_when_nothing_is_eligible(monkeypatch):
    # A defensive check, not a real game state: force every reply to be
    # ineligible and confirm the selector doesn't infinite-loop.
    monkeypatch.setattr("ak_engine.turn.encounter.monster_talk_reply_eligible", lambda *args, **kwargs: False)
    assert select_monster_talk_reply(Monster.ROC, random.Random(1)) is None


# -- Phase 241: Beg --


def test_beg_mercy_chance_covers_all_six_tiers():
    assert BEG_MERCY_CHANCE.keys() == set(MirrorImageIntelligenceTier)


def test_beg_mercy_chance_animal_and_mechanical_are_zero():
    # Confirmed by the user: only monsters with sufficient intelligence can
    # even understand a plea -- Animal/Mechanical can't grant mercy at all.
    assert BEG_MERCY_CHANCE[MirrorImageIntelligenceTier.ANIMAL] == 0.0
    assert BEG_MERCY_CHANCE[MirrorImageIntelligenceTier.MECHANICAL] == 0.0


def test_beg_mercy_chance_increases_with_intelligence():
    assert (
        BEG_MERCY_CHANCE[MirrorImageIntelligenceTier.LOW_HUMAN]
        < BEG_MERCY_CHANCE[MirrorImageIntelligenceTier.MEDIUM_HUMAN]
        < BEG_MERCY_CHANCE[MirrorImageIntelligenceTier.HIGH_HUMAN]
        < BEG_MERCY_CHANCE[MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN]
    )


def test_resolve_beg_for_mercy_boundary():
    tier = MirrorImageIntelligenceTier.HIGH_HUMAN
    chance = BEG_MERCY_CHANCE[tier]
    assert resolve_beg_for_mercy(tier, ScriptedRandom([chance - 0.01])) is True
    assert resolve_beg_for_mercy(tier, ScriptedRandom([chance])) is False


def test_resolve_beg_for_mercy_animal_never_succeeds():
    assert resolve_beg_for_mercy(MirrorImageIntelligenceTier.ANIMAL, ScriptedRandom([0.0])) is False


# -- Phase 258/525: Fulfill --
#
# Phase 525 replaced the old unsourced base-chance/distance-penalty/
# evil-penalty formula with the dossier's exact `WillHonor` formula --
# see `turn/encounter.py`'s own module comment above
# `FULFILL_HELLISH_REFERENCE_ORDINAL` for full sourcing. Worked examples
# below are the dossier's own (SS80, bonus=100).


def test_fulfill_honor_threshold_worldly_vs_worldly():
    # threshold = (60 + 100 - 0) div 2 = 80 -> 20% betrayal.
    assert fulfill_honor_threshold(Alignment.NEUTRAL, Alignment.NEUTRAL, FULFILL_COMMON_BONUS) == 80


def test_fulfill_honor_threshold_hellish_vs_heavenly():
    # threshold = (0 + 100 - 90) div 2 = 5 -> 95% betrayal.
    assert fulfill_honor_threshold(Alignment.ANTI_HOLY, Alignment.DIVINE, FULFILL_COMMON_BONUS) == 5


def test_fulfill_honor_threshold_evil_vs_evil():
    # threshold = (20 + 100 - 0) div 2 = 60 -> 40% betrayal.
    assert fulfill_honor_threshold(Alignment.EVIL, Alignment.EVIL, FULFILL_COMMON_BONUS) == 60


def test_fulfill_honor_threshold_trunc_div_toward_zero_for_a_negative_numerator():
    # Divine(0) monster vs Anti-Holy(6) hero: natural=20*6=120,
    # mismatch=15*6=90 -> numerator negative only for a hypothetical
    # bonus<90-120; use bonus=0 (RDrain's own bonus) with divisor=1 so the
    # negative numerator survives undivided: (120 + 0 - 90) div 1 = 30,
    # still non-negative -- flip monster/hero to get a genuinely negative
    # numerator: Anti-Holy(6) monster vs Divine(0) hero, bonus=0:
    # natural=20*0=0, mismatch=15*6=90 -> (0+0-90) div 1 = -90, truncated
    # toward zero (not floored to a more-negative value by Python's `//`).
    assert fulfill_honor_threshold(Alignment.ANTI_HOLY, Alignment.DIVINE, 0) == -90


def test_fulfill_monster_honors_uses_the_threshold_as_a_0_99_boundary():
    threshold = fulfill_honor_threshold(Alignment.NEUTRAL, Alignment.NEUTRAL, FULFILL_COMMON_BONUS)
    assert (
        fulfill_monster_honors(
            Alignment.NEUTRAL, Alignment.NEUTRAL, FULFILL_COMMON_BONUS, ScriptedRandom([(threshold - 1) / 100])
        )
        is True
    )
    assert (
        fulfill_monster_honors(
            Alignment.NEUTRAL, Alignment.NEUTRAL, FULFILL_COMMON_BONUS, ScriptedRandom([threshold / 100])
        )
        is False
    )


def test_fulfill_monster_honors_rdrain_intelligence_veto_auto_betrays():
    # Dossier SS82: bonus<=0 and monster intelligence above Semi vetoes
    # honor outright, no roll consumed regardless of how favorable the
    # threshold would otherwise be (Divine vs Divine, bonus=0 -> a very
    # high threshold that would normally almost always honor).
    assert (
        fulfill_monster_honors(
            Alignment.DIVINE,
            Alignment.DIVINE,
            0,
            ScriptedRandom([]),
            monster_intelligence=MonsterIntelligence.HIGH,
        )
        is False
    )


def test_fulfill_monster_honors_rdrain_semi_intelligence_is_not_vetoed():
    threshold = fulfill_honor_threshold(Alignment.DIVINE, Alignment.DIVINE, 0)
    assert (
        fulfill_monster_honors(
            Alignment.DIVINE,
            Alignment.DIVINE,
            0,
            ScriptedRandom([(threshold - 1) / 100]),
            monster_intelligence=MonsterIntelligence.SEMI,
        )
        is True
    )


def test_fulfill_monster_honors_positive_bonus_is_never_vetoed_regardless_of_intelligence():
    threshold = fulfill_honor_threshold(Alignment.NEUTRAL, Alignment.NEUTRAL, FULFILL_COMMON_BONUS)
    assert (
        fulfill_monster_honors(
            Alignment.NEUTRAL,
            Alignment.NEUTRAL,
            FULFILL_COMMON_BONUS,
            ScriptedRandom([(threshold - 1) / 100]),
            monster_intelligence=MonsterIntelligence.GODLIKE,
        )
        is True
    )


def test_resolve_fulfill_honored_matches_fulfill_monster_honors_at_the_common_bonus():
    threshold = fulfill_honor_threshold(Alignment.EVIL, Alignment.GOOD, FULFILL_COMMON_BONUS)
    assert (
        resolve_fulfill_honored(Alignment.EVIL, Alignment.GOOD, ScriptedRandom([(threshold - 1) / 100])) is True
    )
    assert resolve_fulfill_honored(Alignment.EVIL, Alignment.GOOD, ScriptedRandom([threshold / 100])) is False


def test_resolve_fulfill_honored_missing_alignment_falls_back_to_neutral():
    # Neither side recorded -- both fall back to
    # FULFILL_UNRECORDED_ALIGNMENT_FALLBACK (Neutral), so this is exactly
    # the Neutral-vs-Neutral threshold.
    threshold = fulfill_honor_threshold(
        FULFILL_UNRECORDED_ALIGNMENT_FALLBACK, FULFILL_UNRECORDED_ALIGNMENT_FALLBACK, FULFILL_COMMON_BONUS
    )
    assert resolve_fulfill_honored(None, None, ScriptedRandom([(threshold - 1) / 100])) is True
    assert resolve_fulfill_honored(None, None, ScriptedRandom([threshold / 100])) is False


def test_resolve_fulfill_honored_missing_character_alignment_falls_back_to_neutral():
    threshold = fulfill_honor_threshold(Alignment.EVIL, FULFILL_UNRECORDED_ALIGNMENT_FALLBACK, FULFILL_COMMON_BONUS)
    assert resolve_fulfill_honored(Alignment.EVIL, None, ScriptedRandom([(threshold - 1) / 100])) is True
    assert resolve_fulfill_honored(Alignment.EVIL, None, ScriptedRandom([threshold / 100])) is False


def test_resolve_fulfill_honored_silver_tongue_always_honors_no_roll_consumed():
    # Report SS18.4's own "onora sempre un accordo completato" -- an
    # unconditional guarantee, even for a maximally-hostile-distance,
    # maximally-unlucky roll that would otherwise fail. ScriptedRandom([])
    # (no values queued) proves no rng roll happens at all.
    assert (
        resolve_fulfill_honored(Alignment.UNDEAD, Alignment.DIVINE, ScriptedRandom([]), caster_is_silver_tongue=True)
        is True
    )


def test_resolve_fulfill_honored_silver_tongue_bypasses_the_rdrain_veto():
    # Silver Tongue short-circuits before WillHonor is even called (SS83-
    # 84), so it bypasses the intelligence veto too -- even at bonus=0
    # with a high-intelligence guardian, still always honors.
    assert (
        resolve_fulfill_honored(
            Alignment.DIVINE,
            Alignment.DIVINE,
            ScriptedRandom([]),
            caster_is_silver_tongue=True,
            bonus=0,
            guardian_intelligence=MonsterIntelligence.GODLIKE,
        )
        is True
    )


# -- Phase 284: the Temper Table's own melee mechanics --------------------


def test_temper_table_melee_constants():
    assert BERSERK_FURY_BONUS_HIT_POINTS_RANGE == (1, 4)
    assert BERSERK_INTIMIDATION_HIT_CHANCE_REDUCTION == {
        Temper.BRAVE: 0.05,
        Temper.CAUTIOUS: 0.10,
        Temper.COWARDLY: 0.15,
    }
    assert BRAVE_MOMENTUM_HIT_CHANCE_BONUS == 0.10
    assert CAUTIOUS_DODGE_HIT_CHANCE_REDUCTION == 0.10


def test_berserk_fury_bonus_hit_points_stays_within_range():
    rng = random.Random(0)
    for _ in range(200):
        bonus = berserk_fury_bonus_hit_points(rng)
        assert 1 <= bonus <= 4


def test_roll_melee_hit_points_ability_bonus_stays_within_range():
    rng = random.Random(0)
    for _ in range(200):
        bonus = roll_melee_hit_points_ability_bonus(rng)
        assert MELEE_HIT_POINTS_ABILITY_BONUS_RANGE[0] <= bonus <= MELEE_HIT_POINTS_ABILITY_BONUS_RANGE[1]


def test_apply_temper_melee_setup_furia_adds_bonus_hit_points_only_to_the_berserk_side():
    a = Combatant("Berserker", hit_points=CHARACTER_HIT_POINTS, temper=Temper.BERSERK)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, random.Random(0))

    assert CHARACTER_HIT_POINTS < a.hit_points <= CHARACTER_HIT_POINTS + 4
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_apply_temper_melee_setup_intimidazione_reduces_defense_by_opponent_own_temper():
    for opponent_temper, expected_reduction in (
        (Temper.BRAVE, 0.05),
        (Temper.CAUTIOUS, 0.10),
        (Temper.COWARDLY, 0.15),
    ):
        a = Combatant("Berserker", hit_points=CHARACTER_HIT_POINTS, temper=Temper.BERSERK)
        b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS, temper=opponent_temper)

        apply_temper_melee_setup(a, b, random.Random(0))

        # Only the Berserk side's own defense is under test here -- b's
        # own temper may separately trigger its own unrelated mechanic
        # (e.g. Cautious's own Schivare), which isn't what this asserts.
        assert a.defensive_hit_multiplier == pytest.approx(1.0 - expected_reduction)


def test_apply_temper_melee_setup_berserk_vs_berserk_has_no_intimidation():
    a = Combatant("Berserker A", hit_points=CHARACTER_HIT_POINTS, temper=Temper.BERSERK)
    b = Combatant("Berserker B", hit_points=CHARACTER_HIT_POINTS, temper=Temper.BERSERK)

    apply_temper_melee_setup(a, b, random.Random(0))

    assert a.defensive_hit_multiplier == 1.0
    assert b.defensive_hit_multiplier == 1.0
    # Furia still applies to both -- it's a Berserk's own psychological
    # toughness, not contingent on the opponent.
    assert a.hit_points > CHARACTER_HIT_POINTS
    assert b.hit_points > CHARACTER_HIT_POINTS


def test_apply_temper_melee_setup_slancio_boosts_own_offense_only():
    a = Combatant("Bold Hero", hit_points=CHARACTER_HIT_POINTS, temper=Temper.BRAVE)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))  # no roll needed -- Slancio/Schivare are deterministic

    assert a.offensive_hit_multiplier == pytest.approx(1.10)
    assert a.defensive_hit_multiplier == 1.0
    assert b.offensive_hit_multiplier == 1.0


def test_apply_temper_melee_setup_schivare_reduces_the_opponents_own_chance_to_hit():
    a = Combatant("Wary Hero", hit_points=CHARACTER_HIT_POINTS, temper=Temper.CAUTIOUS)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.defensive_hit_multiplier == pytest.approx(0.90)
    assert a.offensive_hit_multiplier == 1.0
    assert b.defensive_hit_multiplier == 1.0


def test_apply_temper_melee_setup_no_temper_on_either_side_is_a_no_op():
    a = Combatant("A", hit_points=CHARACTER_HIT_POINTS)
    b = Combatant("B", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.hit_points == CHARACTER_HIT_POINTS
    assert b.hit_points == CHARACTER_HIT_POINTS
    assert a.offensive_hit_multiplier == a.defensive_hit_multiplier == 1.0
    assert b.offensive_hit_multiplier == b.defensive_hit_multiplier == 1.0


def test_apply_temper_melee_setup_multipliers_compose_independently_for_both_sides():
    a = Combatant("Bold Hero", hit_points=CHARACTER_HIT_POINTS, temper=Temper.BRAVE)
    b = Combatant("Wary Foe", hit_points=CHARACTER_HIT_POINTS, temper=Temper.CAUTIOUS)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.offensive_hit_multiplier == pytest.approx(1.10)
    assert a.defensive_hit_multiplier == 1.0
    assert b.offensive_hit_multiplier == 1.0
    assert b.defensive_hit_multiplier == pytest.approx(0.90)


def test_apply_temper_melee_setup_melee_hit_points_ability_adds_bonus_only_to_the_holder():
    a = Combatant("Lucky Hero", hit_points=CHARACTER_HIT_POINTS, has_melee_hit_points_ability=True)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, random.Random(0))

    assert CHARACTER_HIT_POINTS < a.hit_points <= CHARACTER_HIT_POINTS + 5
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_apply_temper_melee_setup_melee_hit_points_ability_stacks_with_furia():
    a = Combatant(
        "Blessed Berserker",
        hit_points=CHARACTER_HIT_POINTS,
        temper=Temper.BERSERK,
        has_melee_hit_points_ability=True,
    )
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, random.Random(0))

    # Furia alone tops out at +4; both bonuses together can reach +9.
    assert CHARACTER_HIT_POINTS + 4 < a.hit_points <= CHARACTER_HIT_POINTS + 9
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_apply_temper_melee_setup_no_melee_hit_points_ability_is_a_no_op_for_hit_points():
    a = Combatant("A", hit_points=CHARACTER_HIT_POINTS)
    b = Combatant("B", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.hit_points == CHARACTER_HIT_POINTS
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_melee_mastery_offensive_hit_multiplier_returns_110_for_mastery():
    assert melee_mastery_offensive_hit_multiplier({AdvancedAbility.MELEE_MASTERY}) == pytest.approx(
        1.0 + MELEE_MASTERY_HIT_CHANCE_BONUS
    )


def test_melee_mastery_offensive_hit_multiplier_returns_100_for_true_mastery_alone():
    assert melee_mastery_offensive_hit_multiplier({AdvancedAbility.MELEE_TRUE_MASTERY}) == 1.0


def test_melee_mastery_offensive_hit_multiplier_returns_100_without_either_ability():
    assert melee_mastery_offensive_hit_multiplier(set()) == 1.0


def test_melee_mastery_damage_bonus_returns_1_for_mastery():
    assert melee_mastery_damage_bonus({AdvancedAbility.MELEE_MASTERY}) == MELEE_MASTERY_DAMAGE_BONUS


def test_melee_mastery_damage_bonus_returns_2_for_true_mastery():
    assert melee_mastery_damage_bonus({AdvancedAbility.MELEE_TRUE_MASTERY}) == MELEE_TRUE_MASTERY_DAMAGE_BONUS


def test_melee_mastery_damage_bonus_prefers_true_mastery_when_both_are_somehow_held():
    both = {AdvancedAbility.MELEE_MASTERY, AdvancedAbility.MELEE_TRUE_MASTERY}
    assert melee_mastery_damage_bonus(both) == MELEE_TRUE_MASTERY_DAMAGE_BONUS


def test_melee_mastery_damage_bonus_returns_0_without_either_ability():
    assert melee_mastery_damage_bonus(set()) == 0


def test_melee_mastery_offensive_hit_multiplier_widens_the_hit_window():
    # Base 50% + Mastery's own +10% = 55% -- a roll of 0.52 misses without
    # the ability but hits with it. A second scripted value feeds the
    # subsequent damage roll (roll_melee_attack's own rng.randint call).
    rng = ScriptedRandom([0.52, 0.1])
    multiplier = melee_mastery_offensive_hit_multiplier({AdvancedAbility.MELEE_MASTERY})

    damage = roll_melee_attack(rng, hit_chance_multiplier=multiplier)

    assert damage > 0


def test_melee_mastery_offensive_hit_multiplier_without_the_ability_still_misses_the_same_roll():
    rng = ScriptedRandom([0.52])
    multiplier = melee_mastery_offensive_hit_multiplier(set())

    damage = roll_melee_attack(rng, hit_chance_multiplier=multiplier)

    assert damage == 0


def test_archery_free_attack_bonus_returns_1_for_base_ability():
    assert archery_free_attack_bonus({AdvancedAbility.ARCHERY_FREE_ATTACK}) == ARCHERY_FREE_ATTACK_BONUS


def test_archery_free_attack_bonus_returns_1_for_mastery():
    assert archery_free_attack_bonus({AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY}) == ARCHERY_FREE_ATTACK_BONUS


def test_archery_free_attack_bonus_returns_1_for_true_mastery():
    assert (
        archery_free_attack_bonus({AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY}) == ARCHERY_FREE_ATTACK_BONUS
    )


def test_archery_free_attack_bonus_returns_0_without_any_of_the_three_tiers():
    assert archery_free_attack_bonus(set()) == 0
    assert archery_free_attack_bonus({AdvancedAbility.MELEE_MASTERY}) == 0


def test_melee_landed_damage_returns_zero_on_a_miss_even_with_a_bonus():
    attacker = Combatant("A", melee_damage_dealt_bonus=5)
    defender = Combatant("B")

    assert _melee_landed_damage(0, attacker, defender) == 0


def test_melee_landed_damage_adds_the_bonus_on_a_landed_hit():
    attacker = Combatant("A", melee_damage_dealt_bonus=2)
    defender = Combatant("B")

    assert _melee_landed_damage(3, attacker, defender) == 5


def test_melee_landed_damage_floors_at_zero_when_reduction_exceeds_raw_plus_bonus():
    attacker = Combatant("A", melee_damage_dealt_bonus=1, melee_damage_dealt_reduction=10)
    defender = Combatant("B")

    assert _melee_landed_damage(3, attacker, defender) == 0


def test_melee_landed_damage_matches_the_pre_phase_517_formula_when_bonus_is_zero():
    attacker = Combatant("A", melee_damage_dealt_reduction=1)
    defender = Combatant("B", damage_reduction=1)

    assert _melee_landed_damage(4, attacker, defender) == 2


def test_resolve_one_melee_round_melee_damage_dealt_bonus_adds_only_to_a_landed_hit():
    a_baseline = Combatant("A", melee_skill=1, hit_points=20)
    b_baseline = Combatant("B", melee_skill=0, hit_points=20)
    baseline = resolve_one_melee_round(a_baseline, b_baseline, random.Random(1), round_number=1)

    a_bonused = Combatant("A", melee_skill=1, hit_points=20, melee_damage_dealt_bonus=2)
    b_bonused = Combatant("B", melee_skill=0, hit_points=20)
    bonused = resolve_one_melee_round(a_bonused, b_bonused, random.Random(1), round_number=1)

    expected_bonus = 2 if baseline.damage_dealt_to_b > 0 else 0
    assert bonused.damage_dealt_to_b == baseline.damage_dealt_to_b + expected_bonus


def test_resolve_reactive_melee_swing_melee_damage_dealt_bonus_adds_only_to_a_landed_hit():
    attacker_baseline = Combatant("A", melee_skill=1, hit_points=20)
    defender_baseline = Combatant("B", melee_skill=0, hit_points=20)
    baseline = resolve_reactive_melee_swing(attacker_baseline, defender_baseline, random.Random(1))

    attacker_bonused = Combatant("A", melee_skill=1, hit_points=20, melee_damage_dealt_bonus=2)
    defender_bonused = Combatant("B", melee_skill=0, hit_points=20)
    bonused = resolve_reactive_melee_swing(attacker_bonused, defender_bonused, random.Random(1))

    expected_bonus = 2 if baseline.damage > 0 else 0
    assert bonused.damage == baseline.damage + expected_bonus


def test_apply_temper_melee_setup_duellists_medal_boosts_holder_against_a_humanoid_opponent():
    a = Combatant("Duellist", hit_points=CHARACTER_HIT_POINTS, has_duellists_medal_ability=True)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS, is_humanoid=True)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.offensive_hit_multiplier == pytest.approx(1.0 + MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS)
    assert a.melee_damage_dealt_bonus == MELEE_DUELLISTS_MEDAL_DAMAGE_BONUS


def test_apply_temper_melee_setup_duellists_medal_weakens_the_humanoid_opponent():
    a = Combatant("Duellist", hit_points=CHARACTER_HIT_POINTS, has_duellists_medal_ability=True)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS, is_humanoid=True)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert b.offensive_hit_multiplier == pytest.approx(1.0 - MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS)
    assert b.melee_damage_dealt_bonus == -MELEE_DUELLISTS_MEDAL_DAMAGE_BONUS


def test_apply_temper_melee_setup_duellists_medal_has_no_effect_against_a_non_humanoid_opponent():
    a = Combatant("Duellist", hit_points=CHARACTER_HIT_POINTS, has_duellists_medal_ability=True)
    b = Combatant("Monster", hit_points=CHARACTER_HIT_POINTS, is_humanoid=False)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.offensive_hit_multiplier == 1.0
    assert a.melee_damage_dealt_bonus == 0
    assert b.offensive_hit_multiplier == 1.0
    assert b.melee_damage_dealt_bonus == 0


def test_apply_temper_melee_setup_duellists_medal_does_nothing_without_the_ability():
    a = Combatant("A", hit_points=CHARACTER_HIT_POINTS)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS, is_humanoid=True)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.offensive_hit_multiplier == 1.0
    assert a.melee_damage_dealt_bonus == 0
    assert b.offensive_hit_multiplier == 1.0
    assert b.melee_damage_dealt_bonus == 0


def test_apply_temper_melee_setup_duellists_medal_applies_symmetrically_when_both_hold_it():
    a = Combatant(
        "A", hit_points=CHARACTER_HIT_POINTS, is_humanoid=True, has_duellists_medal_ability=True
    )
    b = Combatant(
        "B", hit_points=CHARACTER_HIT_POINTS, is_humanoid=True, has_duellists_medal_ability=True
    )

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    # Each side's own medal boosts itself and weakens the other -- net
    # multiplier composes both effects on each combatant.
    expected = (1.0 + MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS) * (1.0 - MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS)
    assert a.offensive_hit_multiplier == pytest.approx(expected)
    assert b.offensive_hit_multiplier == pytest.approx(expected)
    assert a.melee_damage_dealt_bonus == 0
    assert b.melee_damage_dealt_bonus == 0


def test_apply_temper_melee_setup_control_temper_adds_bonus_only_to_the_holder():
    a = Combatant("Tempered Duellist", hit_points=CHARACTER_HIT_POINTS, has_control_temper_ability=True)
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, random.Random(0))

    assert CHARACTER_HIT_POINTS < a.hit_points <= CHARACTER_HIT_POINTS + 4
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_apply_temper_melee_setup_control_temper_does_nothing_without_the_ability():
    a = Combatant("A", hit_points=CHARACTER_HIT_POINTS)
    b = Combatant("B", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, ScriptedRandom([]))

    assert a.hit_points == CHARACTER_HIT_POINTS
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_apply_temper_melee_setup_control_temper_applies_regardless_of_real_temper():
    # The ability grants its own bonus "as if Berserk" even when the
    # combatant's own recorded .temper is something else entirely (or
    # None) -- "used initially" is not gated on genuinely being Berserk.
    a = Combatant(
        "Composed Duellist",
        hit_points=CHARACTER_HIT_POINTS,
        temper=Temper.CAUTIOUS,
        has_control_temper_ability=True,
    )
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, random.Random(0))

    assert CHARACTER_HIT_POINTS < a.hit_points <= CHARACTER_HIT_POINTS + 4


def test_apply_temper_melee_setup_control_temper_stacks_with_genuine_berserk():
    # A documented, deliberate quirk: holding the ability *and* being
    # genuinely Berserk rolls Furia's own bonus twice.
    a = Combatant(
        "Doubly Tempered",
        hit_points=CHARACTER_HIT_POINTS,
        temper=Temper.BERSERK,
        has_control_temper_ability=True,
    )
    b = Combatant("Foe", hit_points=CHARACTER_HIT_POINTS)

    apply_temper_melee_setup(a, b, random.Random(0))

    assert CHARACTER_HIT_POINTS + 1 < a.hit_points <= CHARACTER_HIT_POINTS + 8
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_resolve_melee_duel_applies_temper_setup_before_any_combat():
    # max_rounds=0 skips the round loop entirely, isolating
    # apply_temper_melee_setup()'s own effect (called first, inside
    # resolve_melee_duel() itself) from any combat damage.
    a = Combatant("Berserker", melee_skill=0, hit_points=CHARACTER_HIT_POINTS, temper=Temper.BERSERK)
    b = Combatant("Foe", melee_skill=0, hit_points=CHARACTER_HIT_POINTS)

    resolve_melee_duel(a, b, random.Random(0), max_rounds=0)

    assert CHARACTER_HIT_POINTS < a.hit_points <= CHARACTER_HIT_POINTS + 4
    assert b.hit_points == CHARACTER_HIT_POINTS


def test_resolve_melee_duel_reads_the_attackers_own_offensive_multiplier_from_temper():
    # Slancio: +10% to a Brave attacker's own hit chance (50% -> 55%).
    # 0.52 is a miss at the plain 50% threshold but a hit once Slancio
    # applies -- proves resolve_melee_duel() actually reads *attacker*.
    # offensive_hit_multiplier (set by apply_temper_melee_setup() from
    # a.temper), not just the defender's own defensive_hit_multiplier.
    a = Combatant("Bold Hero", melee_skill=0, hit_points=CHARACTER_HIT_POINTS, temper=Temper.BRAVE)
    b = Combatant("Victim", melee_skill=0, hit_points=1)
    # acts_first, a's hit-chance roll, a's damage roll (any 1-6 kills b's 1 HP)
    rng = ScriptedRandom([0.1, 0.52, 0.5])

    result = resolve_melee_duel(a, b, rng)

    assert result.winner == "a"
    assert result.rounds == 1


# -- loot_defeated_leader (Phase 313, rulebook [5.9]) -----------------------


def _loot_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Winland", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(10, kingdom_id=1, name="Winner", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Loser", location=HexCoord(0, 0)))
    return state


def test_loot_defeated_leader_transfers_every_item_the_loser_owned():
    state = _loot_state()
    item_a = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=20)
    item_b = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=20)
    other_leaders_item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=10)

    looted = loot_defeated_leader(state, winner_id=10, loser_id=20)

    assert {item.item_id for item in looted} == {item_a.item_id, item_b.item_id}
    assert state.items[item_a.item_id].owner_leader_id == 10
    assert state.items[item_b.item_id].owner_leader_id == 10
    assert state.items[other_leaders_item.item_id].owner_leader_id == 10  # untouched, already the winner's


def test_loot_defeated_leader_returns_empty_list_when_loser_owned_nothing():
    state = _loot_state()

    looted = loot_defeated_leader(state, winner_id=10, loser_id=20)

    assert looted == []


def test_loot_defeated_leader_works_after_remove_leader_since_item_ownership_is_independent():
    # Item ownership (ItemInstance.owner_leader_id) isn't tied to
    # GameState.leaders -- every real call site calls remove_leader()
    # first, so this confirms that order doesn't break the transfer.
    state = _loot_state()
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=20)
    state.remove_leader(20)

    looted = loot_defeated_leader(state, winner_id=10, loser_id=20)

    assert looted == [item]
    assert state.items[item.item_id].owner_leader_id == 10


# -- Phase 489: Imperial Defender's own "reduce any strike against you in
# personal combat (including magical damage) by one damage point" perk
# (CARICHE E ABLITA.txt, ofcname index confirmed at Office.DEFENDER, Phase
# 103's own OFFICE_PERK_DESCRIPTION). Combatant.damage_reduction is set by
# each real consumer's own leader-combatant builder (see e.g.
# battle_orchestrator.py _commander_combatant's own Phase 489 addendum),
# never by encounter.py itself -- these tests only exercise the generic
# defender-side subtraction encounter.py applies at every hit-point site.


def test_combatant_damage_reduction_defaults_to_zero():
    assert Combatant("A").damage_reduction == 0


def test_resolve_one_melee_round_damage_reduction_floors_a_real_hit_to_zero():
    # A's higher skill means no order-tiebreak roll is needed (_acts_first
    # is deterministic here): A swings first and hits (floored to 0 damage
    # by B's own damage_reduction) -- a hit consumes two .random() calls,
    # the hit-chance check plus the damage-magnitude roll (`ScriptedRandom`
    # overrides only `.random()`, so `rng.randint()` also draws from the
    # scripted list -- the same convention every other Phase 209+ test in
    # this file already relies on, e.g. the Hand of Death tests' own
    # "then a damage roll" comments). B then swings back and misses,
    # consuming one more .random() call for its own hit-chance check only.
    attacker = Combatant("A", melee_skill=1)
    defender = Combatant("B", melee_skill=0, damage_reduction=999)
    rng = ScriptedRandom([0.1, 0.3, 0.9])  # A's hit-chance + damage rolls, then B's miss

    outcome = resolve_one_melee_round(attacker, defender, rng, round_number=1)

    assert outcome.result is None
    assert defender.hit_points == CHARACTER_HIT_POINTS
    assert any(swing.hit and swing.damage == 0 for swing in outcome.swings)


def test_resolve_reactive_melee_swing_damage_reduction_floors_a_real_hit_to_zero():
    attacker = Combatant("A", melee_skill=1)
    defender = Combatant("B", damage_reduction=999)
    rng = ScriptedRandom([0.1, 0.5])  # hit roll, then damage roll

    result = resolve_reactive_melee_swing(attacker, defender, rng)

    assert result.hit is True
    assert result.damage == 0
    assert defender.hit_points == CHARACTER_HIT_POINTS


def test_resolve_fire_arrow_duel_damage_reduction_floors_a_real_hit_to_zero_but_still_logs_the_hit():
    a = Combatant("A", archery_skill=3)
    b = Combatant("B", archery_skill=0, damage_reduction=999)

    result = resolve_fire_arrow_duel(a, b, random.Random(1))

    assert result.winner is None
    assert b.hit_points == CHARACTER_HIT_POINTS
    assert any(shot.shooter == "a" and shot.hit and shot.damage == 0 for shot in result.shots)


def test_resolve_hand_of_death_channel_damage_reduction_applies_to_both_the_squeeze_and_the_counter_melee():
    caster = Combatant("Caster", hit_points=10, damage_reduction=999)
    victim = Combatant("Victim", hit_points=10, melee_skill=0, damage_reduction=999)
    rng = ScriptedRandom([0.1, 0.5])  # victim's halved-chance counter-attack hits, then a damage roll

    result = resolve_hand_of_death_channel(caster, victim, 2, rng)

    # The caster's own squeeze this round is floored to 0 -- the victim
    # never takes damage, so the channel keeps going instead of ending in
    # an instant kill.
    assert victim.hit_points == 10
    assert result.squeeze_hits == (0,)
    # The victim's own counter-hit lands (raw_damage > 0 still ends the
    # channel per [5.1]'s "the caster loses concentration" rule) but is
    # also floored to 0 by the caster's own damage_reduction.
    assert result.winner is None
    assert caster.hit_points == 10


# -- Phase 536: magic weapon auto-equip effects + on-hit procs -----------
# AKGEN_reverse_engineering_report (4).md SS7.3 (Holy Sword protection /
# Invisible Sword auto-invisibility) and SS7.4 (Shadow Sword drain /
# Flaming Scimitar instakill / Psychic Flail stun).


def test_weapon_defensive_hit_multiplier_is_a_no_op_with_no_weapon():
    assert weapon_defensive_hit_multiplier(None) == 1.0


def test_weapon_defensive_hit_multiplier_is_a_no_op_for_other_weapons():
    assert weapon_defensive_hit_multiplier(Treasure.WEAPON_2) == 1.0


def test_weapon_defensive_hit_multiplier_applies_level_4_holy_symbol_protection():
    # 10%/level * 4 (HOLY_SWORD_AUTO_PROTECTION_LEVEL) = 40% reduction,
    # "senza danno" -- the non-Undead rate only (see the function's own
    # docstring for why the Undead/Anti-Holy variant can't apply here).
    assert HOLY_SWORD_AUTO_PROTECTION_LEVEL == PERSONAL_COMBAT_SPELL_LEVEL_CAP
    assert weapon_defensive_hit_multiplier(Treasure.WEAPON_1) == pytest.approx(0.6)


def test_weapon_defensive_hit_multiplier_applies_invisible_sword_halving():
    assert weapon_defensive_hit_multiplier(Treasure.WEAPON_5) == pytest.approx(INVISIBILITY_HIT_CHANCE_MULTIPLIER)


def test_weapon_grants_auto_invisibility_only_for_the_invisible_sword():
    assert weapon_grants_auto_invisibility(Treasure.WEAPON_5) is True
    assert weapon_grants_auto_invisibility(Treasure.WEAPON_1) is False
    assert weapon_grants_auto_invisibility(None) is False


def test_apply_weapon_on_hit_effects_no_op_on_a_miss_regardless_of_weapon():
    attacker = Combatant("A", equipped_weapon=Treasure.WEAPON_3)
    defender = Combatant("B")
    rng = ScriptedRandom([])  # any .random() call here raises IndexError

    apply_weapon_on_hit_effects(attacker, defender, 0, rng)

    assert defender.hit_points == CHARACTER_HIT_POINTS


def test_apply_weapon_on_hit_effects_no_op_with_no_weapon_equipped():
    attacker = Combatant("A")
    defender = Combatant("B")
    rng = ScriptedRandom([])

    apply_weapon_on_hit_effects(attacker, defender, 5, rng)

    assert defender.hit_points == CHARACTER_HIT_POINTS


def test_apply_weapon_on_hit_effects_shadow_sword_drains_half_the_landed_damage():
    attacker = Combatant("A", hit_points=5, equipped_weapon=Treasure.WEAPON_2)
    defender = Combatant("B")
    rng = ScriptedRandom([])

    apply_weapon_on_hit_effects(attacker, defender, 4, rng)

    assert SHADOW_SWORD_LIFE_DRAIN_FRACTION == 0.5
    assert attacker.hit_points == 7  # 5 + (4 // 2)


def test_apply_weapon_on_hit_effects_shadow_sword_drain_is_capped_at_character_hit_points():
    attacker = Combatant("A", hit_points=9, equipped_weapon=Treasure.WEAPON_2)
    defender = Combatant("B")
    rng = ScriptedRandom([])

    apply_weapon_on_hit_effects(attacker, defender, 6, rng)

    assert attacker.hit_points == CHARACTER_HIT_POINTS


def test_apply_weapon_on_hit_effects_flaming_scimitar_instakills_below_the_chance_threshold():
    attacker = Combatant("A", equipped_weapon=Treasure.WEAPON_3)
    defender = Combatant("B")
    rng = ScriptedRandom([0.01])

    assert FLAMING_SCIMITAR_INSTAKILL_CHANCE == 0.05
    apply_weapon_on_hit_effects(attacker, defender, 3, rng)

    assert defender.hit_points == 0


def test_apply_weapon_on_hit_effects_flaming_scimitar_does_not_instakill_above_the_chance_threshold():
    attacker = Combatant("A", equipped_weapon=Treasure.WEAPON_3)
    defender = Combatant("B")
    rng = ScriptedRandom([0.5])

    apply_weapon_on_hit_effects(attacker, defender, 3, rng)

    assert defender.hit_points == CHARACTER_HIT_POINTS


def test_apply_weapon_on_hit_effects_psychic_flail_stuns_below_the_chance_threshold():
    attacker = Combatant("A", equipped_weapon=Treasure.WEAPON_4)
    defender = Combatant("B")
    rng = ScriptedRandom([0.49])

    assert PSYCHIC_FLAIL_STUN_CHANCE == 0.50
    apply_weapon_on_hit_effects(attacker, defender, 3, rng)

    # "si somma a Psychic Blast invece di sostituirlo" -- same
    # bonus_unanswered_attacks counter Psychic Blast's own stun feeds.
    assert attacker.bonus_unanswered_attacks == 1


def test_apply_weapon_on_hit_effects_psychic_flail_does_not_stun_above_the_chance_threshold():
    attacker = Combatant("A", equipped_weapon=Treasure.WEAPON_4)
    defender = Combatant("B")
    rng = ScriptedRandom([0.5])

    apply_weapon_on_hit_effects(attacker, defender, 3, rng)

    assert attacker.bonus_unanswered_attacks == 0


def test_resolve_one_melee_round_flaming_scimitar_proc_wins_the_round_via_instakill():
    attacker = Combatant("A", melee_skill=1, equipped_weapon=Treasure.WEAPON_3)
    defender = Combatant("B", melee_skill=0)
    # A's hit-chance roll, A's damage roll, then the Flaming Scimitar
    # instakill roll (below the 5% threshold).
    rng = ScriptedRandom([0.1, 0.5, 0.01])

    outcome = resolve_one_melee_round(attacker, defender, rng, round_number=1)

    assert outcome.result is not None
    assert outcome.result.winner == "a"
    assert defender.hit_points == 0


def test_resolve_reactive_melee_swing_shadow_sword_proc_heals_the_attacker():
    attacker = Combatant("A", hit_points=5, melee_skill=1, equipped_weapon=Treasure.WEAPON_2)
    defender = Combatant("B")
    rng = ScriptedRandom([0.1, 0.5])  # hit roll, then damage roll

    result = resolve_reactive_melee_swing(attacker, defender, rng)

    assert result.hit is True
    assert attacker.hit_points == 5 + (result.damage // 2)
