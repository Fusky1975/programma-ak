"""Advanced Abilities are counted per occurrence (the original engine's ``SA_Num``): the same ability reached in
several slots of a Talent adds its effect once for each (user ruling 2026-11-26)."""

from __future__ import annotations

import pytest

from ak_engine.models.advanced_ability import (
    AdvancedAbilities,
    AdvancedAbility,
    advanced_ability_count,
    grant_advanced_ability,
)
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.turn.battle_orchestrator import _mastery_bonus_for
from ak_engine.turn.encounter import (
    archery_free_attack_bonus,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
)


def _leader() -> LeaderState:
    return LeaderState(1, 1, "Hero", HexCoord(0, 0))


def test_a_new_leader_starts_with_an_empty_counting_registry():
    leader = _leader()
    assert isinstance(leader.advanced_abilities, AdvancedAbilities) and not leader.advanced_abilities


def test_each_slot_counts_once_however_often_its_level_is_reached():
    leader = _leader()
    grant_advanced_ability(leader, AdvancedAbility.NAVAL_MASTERY_GREAT_15, Ability.NAVAL, 6)
    grant_advanced_ability(leader, AdvancedAbility.NAVAL_MASTERY_GREAT_15, Ability.NAVAL, 6)  # same slot again
    grant_advanced_ability(leader, AdvancedAbility.NAVAL_MASTERY_GREAT_15, Ability.NAVAL, 8)

    assert advanced_ability_count(leader.advanced_abilities, AdvancedAbility.NAVAL_MASTERY_GREAT_15) == 2
    assert advanced_ability_count(leader.advanced_abilities, AdvancedAbility.MELEE_MASTERY) == 0


def test_a_member_set_by_hand_counts_once_and_a_plain_set_is_supported():
    leader = _leader()
    leader.advanced_abilities.add(AdvancedAbility.MELEE_MASTERY)
    assert advanced_ability_count(leader.advanced_abilities, AdvancedAbility.MELEE_MASTERY) == 1
    assert advanced_ability_count({AdvancedAbility.MELEE_MASTERY}, AdvancedAbility.MELEE_MASTERY) == 1
    assert advanced_ability_count(set(), AdvancedAbility.MELEE_MASTERY) == 0


def test_a_leader_saved_with_a_plain_set_is_upgraded_on_the_next_grant():
    leader = _leader()
    leader.advanced_abilities = {AdvancedAbility.MELEE_EVASION}  # an old save
    grant_advanced_ability(leader, AdvancedAbility.MELEE_MASTERY, Ability.MELEE, 6)

    assert isinstance(leader.advanced_abilities, AdvancedAbilities)
    assert AdvancedAbility.MELEE_EVASION in leader.advanced_abilities


def test_tactical_and_naval_mastery_add_up_per_slot():
    leader = _leader()
    for level in (6, 8):
        grant_advanced_ability(leader, AdvancedAbility.TACTICAL_MASTERY_15, Ability.TACTICAL, level)
    for level in (6, 8, 9):
        grant_advanced_ability(leader, AdvancedAbility.NAVAL_MASTERY_GREAT_15, Ability.NAVAL, level)

    assert _mastery_bonus_for(leader, Ability.TACTICAL) == pytest.approx(0.30)
    assert _mastery_bonus_for(leader, Ability.NAVAL) == pytest.approx(0.45)  # the dossier's own +45%


def test_a_higher_mastery_tier_cancels_the_lower_one():
    leader = _leader()
    leader.advanced_abilities.add(AdvancedAbility.TACTICAL_MASTERY_10)
    grant_advanced_ability(leader, AdvancedAbility.TACTICAL_MASTERY_20, Ability.TACTICAL, 7)
    assert _mastery_bonus_for(leader, Ability.TACTICAL) == pytest.approx(0.20)


def test_melee_mastery_adds_hit_chance_and_damage_per_slot():
    leader = _leader()
    for level in (6, 8):
        grant_advanced_ability(leader, AdvancedAbility.MELEE_MASTERY, Ability.MELEE, level)

    assert melee_mastery_offensive_hit_multiplier(leader.advanced_abilities) == pytest.approx(1.20)
    assert melee_mastery_damage_bonus(leader.advanced_abilities) == 2
    assert melee_mastery_offensive_hit_multiplier(set()) == 1.0


def test_each_archery_free_attack_slot_is_one_more_arrow():
    leader = _leader()
    grant_advanced_ability(leader, AdvancedAbility.ARCHERY_FREE_ATTACK, Ability.ARCHERY, 5)
    grant_advanced_ability(leader, AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY, Ability.ARCHERY, 7)
    grant_advanced_ability(leader, AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY, Ability.ARCHERY, 9)

    assert archery_free_attack_bonus(leader.advanced_abilities) == 3
    assert archery_free_attack_bonus(set()) == 0
