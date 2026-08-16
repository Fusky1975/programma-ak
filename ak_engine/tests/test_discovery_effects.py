"""Tests for turn/discovery_effects.py -- see its module docstring for the
stacking and MAX_SKILL_LEVEL-cap rationale.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.discovery_effects import (
    ability_bonus_from_discoveries,
    ability_bonus_from_items,
    effective_skill_level,
    equipped_combat_weapon,
    holder_is_immune_to_spell,
    holds_bow_of_elven_kings,
    holds_monster_command_item_for,
    province_halves_spell_chance,
)
from ak_engine.turn.practice_execution import MAX_SKILL_LEVEL

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HOME))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME))
    return state


def skills_with(**levels: int) -> SkillTable:
    raw_values = [0] * (len(Ability) * 2 + 1)
    for name, level in levels.items():
        i = Ability[name].value * 2
        raw_values[i] = level
        raw_values[i + 1] = level
    return SkillTable(raw_values)


def test_ability_bonus_from_discoveries_zero_when_none_owned():
    state = make_state()
    leader = state.leaders[1]

    assert ability_bonus_from_discoveries(state, leader, Ability.TACTICAL) == 0


def test_ability_bonus_from_discoveries_one_matching_discovery():
    state = make_state()
    leader = state.leaders[1]
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    assert ability_bonus_from_discoveries(state, leader, Ability.EXPLORER) == 1
    assert ability_bonus_from_discoveries(state, leader, Ability.TACTICAL) == 0


def test_ability_bonus_from_discoveries_stacks_two_matching_discoveries():
    # LAND_SHIP and SCYTHED_CHARIOTS both bonus Tactical -- see module
    # docstring's stacking rationale.
    state = make_state()
    leader = state.leaders[1]
    state.kingdoms[1].discoveries.update({Discovery.LAND_SHIP, Discovery.SCYTHED_CHARIOTS})

    assert ability_bonus_from_discoveries(state, leader, Ability.TACTICAL) == 2


def test_ability_bonus_from_discoveries_independent_hero_is_zero():
    state = make_state()
    hero = LeaderState(9, None, "Wanderer", HOME)
    state.add_leader(hero)

    assert ability_bonus_from_discoveries(state, hero, Ability.TACTICAL) == 0


def test_ability_bonus_from_discoveries_kingdomless_id_not_in_state_is_zero():
    state = GameState()
    leader = LeaderState(1, 1, "Ghost", HOME)
    state.add_leader(leader)

    assert ability_bonus_from_discoveries(state, leader, Ability.TACTICAL) == 0


def test_effective_skill_level_no_skills_recorded():
    state = make_state()
    leader = state.leaders[1]

    assert effective_skill_level(state, leader, Ability.MELEE) == 0


def test_effective_skill_level_adds_discovery_bonus_to_stored_skill():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(EXPLORER=3)
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    assert effective_skill_level(state, leader, Ability.EXPLORER) == 4


def test_effective_skill_level_caps_at_max_skill_level():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(TACTICAL=MAX_SKILL_LEVEL)
    state.kingdoms[1].discoveries.update({Discovery.LAND_SHIP, Discovery.SCYTHED_CHARIOTS})

    assert effective_skill_level(state, leader, Ability.TACTICAL) == MAX_SKILL_LEVEL


def test_ability_bonus_from_items_zero_when_none_held():
    state = make_state()
    leader = state.leaders[1]

    assert ability_bonus_from_items(state, leader, Ability.NAVAL) == 0


def test_ability_bonus_from_items_one_copy():
    state = make_state()
    leader = state.leaders[1]
    state.add_item(Treasure.ABILITY_NAVAL, owner_leader_id=1)

    assert ability_bonus_from_items(state, leader, Ability.NAVAL) == 1
    assert ability_bonus_from_items(state, leader, Ability.MELEE) == 0


def test_ability_bonus_from_items_stacks_per_copy_held():
    # Phase 534: AKGEN_reverse_engineering_report (4).md SS5 -- unlike
    # Discoveries (capped at 2 matching entries by the Pascal enum
    # itself), every held copy of an ability item counts.
    state = make_state()
    leader = state.leaders[1]
    state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=1)
    state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=1)
    state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=1)

    assert ability_bonus_from_items(state, leader, Ability.MELEE) == 3


def test_effective_skill_level_adds_item_bonus_to_stored_skill():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(NAVAL=3)
    state.add_item(Treasure.ABILITY_NAVAL, owner_leader_id=1)

    assert effective_skill_level(state, leader, Ability.NAVAL) == 4


def test_effective_skill_level_combines_discovery_and_item_bonuses_under_one_shared_cap():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(TACTICAL=MAX_SKILL_LEVEL - 1)
    state.kingdoms[1].discoveries.add(Discovery.LAND_SHIP)  # +1 Tactical
    state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=1)  # +1 Tactical

    # MAX_SKILL_LEVEL - 1 + 1 (Discovery) + 1 (item) would be MAX_SKILL_LEVEL + 1
    # -- capped once, combined, not per-source.
    assert effective_skill_level(state, leader, Ability.TACTICAL) == MAX_SKILL_LEVEL


def test_effective_skill_level_reads_zero_for_a_comatose_leader():
    # Phase 310: Kill_Enemy's own [4.25.2] coma variant -- "tutti i suoi
    # Talenti sono ridotti a livello zero" -- a flat floor, not "0 plus
    # whatever Discovery bonus would otherwise apply."
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(TACTICAL=MAX_SKILL_LEVEL)
    state.kingdoms[1].discoveries.update({Discovery.LAND_SHIP, Discovery.SCYTHED_CHARIOTS})
    leader.is_comatose = True

    assert effective_skill_level(state, leader, Ability.TACTICAL) == 0
    # The real, stored value is never mutated -- only hidden.
    assert leader.skills.pair_for_ability(Ability.TACTICAL)[0] == MAX_SKILL_LEVEL


# -- Phase 531: holder_is_immune_to_spell --------------------------------
# AKGEN_reverse_engineering_report (4).md SS8 -- each amulet blocks only
# specific named spells, not every spell of the matching magic college
# (replaces Phase 530's blanket-school approximation).


def test_holder_is_immune_to_spell_true_for_a_blocked_spell():
    state = make_state()
    state.add_item(Treasure.AMULET_ANTI_PSYCHIC, owner_leader_id=1)

    assert holder_is_immune_to_spell(state, 1, Spell.CHARM) is True
    assert holder_is_immune_to_spell(state, 1, Spell.PSYCHIC_BLAST) is True


def test_holder_is_immune_to_spell_false_for_a_same_college_but_unlisted_spell():
    # Anti-Psychic blocks Charm/Psychic Blast, but not every Psychic
    # spell -- Telekinetic Storm and Augur Combat are unaffected.
    state = make_state()
    state.add_item(Treasure.AMULET_ANTI_PSYCHIC, owner_leader_id=1)

    assert holder_is_immune_to_spell(state, 1, Spell.TELEK_STORM) is False
    assert holder_is_immune_to_spell(state, 1, Spell.AUGUR_COMBAT) is False


def test_holder_is_immune_to_spell_false_when_a_different_amulet_is_held():
    state = make_state()
    state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=1)

    assert holder_is_immune_to_spell(state, 1, Spell.CHARM) is False


def test_holder_is_immune_to_spell_false_when_holder_owns_no_items():
    state = make_state()

    assert holder_is_immune_to_spell(state, 1, Spell.KILL_ENEMY) is False


def test_holder_is_immune_to_spell_covers_every_amulets_own_blocked_set():
    cases = (
        (Treasure.AMULET_ANTI_WHITE, Spell.HOLY_SYMBOL),
        (Treasure.AMULET_ANTI_NECROMANCY, Spell.KILL_ENEMY),
        (Treasure.AMULET_ANTI_NECROMANCY, Spell.HAND_OF_DEATH),
        (Treasure.AMULET_ANTI_ELEMENTAL, Spell.FIREBALL),
        (Treasure.AMULET_ANTI_PSYCHIC, Spell.CHARM),
        (Treasure.AMULET_ANTI_PSYCHIC, Spell.PSYCHIC_BLAST),
    )
    for amulet, spell in cases:
        solo_state = make_state()
        solo_state.add_item(amulet, owner_leader_id=1)
        assert holder_is_immune_to_spell(solo_state, 1, spell) is True


def test_holder_is_immune_to_spell_true_when_either_of_necromancys_two_amulet_spells_is_held():
    # The True Cross uniquely blocks *two* spells -- confirm both
    # independently reach the same amulet instance.
    state = make_state()
    state.add_item(Treasure.AMULET_ANTI_NECROMANCY, owner_leader_id=1)

    assert holder_is_immune_to_spell(state, 1, Spell.KILL_ENEMY) is True
    assert holder_is_immune_to_spell(state, 1, Spell.HAND_OF_DEATH) is True
    assert holder_is_immune_to_spell(state, 1, Spell.CONTROL_UNDEAD) is False


# -- Phase 533: province_halves_spell_chance -----------------------------
# AKGEN_reverse_engineering_report (4).md SS8 -- a genuinely whole-college
# effect, separate from holder_is_immune_to_spell()'s per-spell personal
# immunity: any spell of the matching college targeted at a province the
# amulet holder's own Kingdom owns has its cast-success chance halved.


def _province_owned_by(kingdom_id: int) -> ProvinceState:
    return ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=kingdom_id)


def test_province_halves_spell_chance_true_when_owning_kingdoms_leader_holds_matching_amulet():
    state = make_state()
    state.add_province(_province_owned_by(1))
    state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=1)

    assert province_halves_spell_chance(state, HOME, Ability.ELEMENTAL) is True


def test_province_halves_spell_chance_false_for_unowned_province():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN))  # owner_kingdom_id=None
    state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=1)

    assert province_halves_spell_chance(state, HOME, Ability.ELEMENTAL) is False


def test_province_halves_spell_chance_false_for_unknown_province():
    state = make_state()
    state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=1)

    assert province_halves_spell_chance(state, HOME, Ability.ELEMENTAL) is False


def test_province_halves_spell_chance_false_when_owning_kingdom_holds_a_different_amulet():
    state = make_state()
    state.add_province(_province_owned_by(1))
    state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=1)

    assert province_halves_spell_chance(state, HOME, Ability.ELEMENTAL) is False


def test_province_halves_spell_chance_false_when_owning_kingdom_holds_no_items():
    state = make_state()
    state.add_province(_province_owned_by(1))

    assert province_halves_spell_chance(state, HOME, Ability.ELEMENTAL) is False


def test_province_halves_spell_chance_false_when_a_different_kingdom_holds_the_matching_amulet():
    # The amulet must belong to the *owning* Kingdom's own leader -- a
    # rival Kingdom holding the same amulet type has no effect on a
    # province it doesn't own.
    state = make_state()
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.NEUTRAL, HOME))
    state.add_leader(LeaderState(2, 2, "Rival", HOME))
    state.add_province(_province_owned_by(1))
    state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=2)

    assert province_halves_spell_chance(state, HOME, Ability.ELEMENTAL) is False


def test_province_halves_spell_chance_covers_every_amulet_ability():
    cases = (
        (Ability.WHITE, Treasure.AMULET_ANTI_WHITE),
        (Ability.NECROMANCY, Treasure.AMULET_ANTI_NECROMANCY),
        (Ability.ELEMENTAL, Treasure.AMULET_ANTI_ELEMENTAL),
        (Ability.PSYCHIC, Treasure.AMULET_ANTI_PSYCHIC),
        (Ability.ILLUSION, Treasure.AMULET_ANTI_ILLUSION),
    )
    for ability, amulet in cases:
        solo_state = make_state()
        solo_state.add_province(_province_owned_by(1))
        solo_state.add_item(amulet, owner_leader_id=1)
        assert province_halves_spell_chance(solo_state, HOME, ability) is True


# -- Phase 532: Crystal of True Seeing (AMULET_ANTI_ILLUSION) joins the
# same holder_is_immune_to_spell() table -- see turn/discovery_effects.py
# module docstring's own Phase 532 addendum for why Phantasmal Armies is
# deliberately excluded (a separate battle-wide mechanic, not a personal
# spell immunity).


def test_holder_is_immune_to_spell_true_for_all_three_of_crystal_of_true_seeings_illusion_spells():
    state = make_state()
    state.add_item(Treasure.AMULET_ANTI_ILLUSION, owner_leader_id=1)

    assert holder_is_immune_to_spell(state, 1, Spell.INVISIBILITY) is True
    assert holder_is_immune_to_spell(state, 1, Spell.ILLUS_TERRAIN) is True
    assert holder_is_immune_to_spell(state, 1, Spell.HIDE_FEATURE) is True


def test_holder_is_immune_to_spell_false_for_phantasmal_armies_even_with_crystal_of_true_seeing():
    # Phantasmal Armies is a separate battle-wide strength-bonus halving
    # (turn/battle_orchestrator.py), not a personal spell immunity -- it's
    # deliberately absent from AMULET_ANTI_ILLUSION's own blocked set.
    state = make_state()
    state.add_item(Treasure.AMULET_ANTI_ILLUSION, owner_leader_id=1)

    assert holder_is_immune_to_spell(state, 1, Spell.ILLUS_ARMIES) is False


# -- Phase 535: equipped_combat_weapon / holds_bow_of_elven_kings --------
# AKGEN_reverse_engineering_report (4).md SS7.1/SS7.2 -- 8 of the 9 magic
# weapons share one mutually-exclusive "equipped" slot; the Bow of the
# Elven Kings is a separate, possession-gated, Archery-only bonus.


def test_equipped_combat_weapon_none_when_holder_owns_no_weapon():
    state = make_state()

    assert equipped_combat_weapon(state, 1) is None


def test_equipped_combat_weapon_returns_the_single_held_weapon():
    state = make_state()
    state.add_item(Treasure.WEAPON_3, owner_leader_id=1)

    assert equipped_combat_weapon(state, 1) is Treasure.WEAPON_3


def test_equipped_combat_weapon_ignores_the_bow_of_the_elven_kings():
    # The Bow (LEADERSHIP_ELVEN) never occupies the equip slot.
    state = make_state()
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=1)

    assert equipped_combat_weapon(state, 1) is None


def test_equipped_combat_weapon_picks_the_lowest_item_id_when_multiple_are_held():
    # Documented tie-break, not a sourced priority rule -- see the
    # function's own docstring.
    state = make_state()
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)  # item_id 0
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)  # item_id 1, held second

    assert equipped_combat_weapon(state, 1) is Treasure.LEADERSHIP_HUMAN


def test_holds_bow_of_elven_kings_false_when_not_held():
    state = make_state()

    assert holds_bow_of_elven_kings(state, 1) is False


def test_holds_bow_of_elven_kings_true_regardless_of_copy_count():
    # A plain boolean, not a count -- SS7.1 point 5: "il bonus non si
    # moltiplica con le copie."
    state = make_state()
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=1)
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=1)

    assert holds_bow_of_elven_kings(state, 1) is True


# -- Phase 537: holds_monster_command_item_for ----------------------------
# AKGEN_reverse_engineering_report (4).md SS9's own "TA-lk skips the
# normal social roll" mechanic for the 3 racial-command items (49-51).


def test_holds_monster_command_item_for_false_when_not_held():
    state = make_state()

    assert holds_monster_command_item_for(state, 1, Monster.R_DRAGON) is False


def test_holds_monster_command_item_for_true_for_any_dragon_species():
    state = make_state()
    state.add_item(Treasure.MONSTER_AID_DRAGON, owner_leader_id=1)

    for species in (Monster.R_DRAGON, Monster.B_DRAGON, Monster.GR_DRAGON, Monster.S_DRAGON, Monster.GO_DRAGON):
        assert holds_monster_command_item_for(state, 1, species) is True


def test_holds_monster_command_item_for_eagle():
    state = make_state()
    state.add_item(Treasure.MONSTER_AID_EAGLE, owner_leader_id=1)

    assert holds_monster_command_item_for(state, 1, Monster.GI_EAGLE) is True


def test_holds_monster_command_item_for_whale():
    state = make_state()
    state.add_item(Treasure.MONSTER_AID_WHALE, owner_leader_id=1)

    assert holds_monster_command_item_for(state, 1, Monster.GW_WHALE) is True


def test_holds_monster_command_item_for_false_for_a_non_matching_species():
    # A Dragon-command item held, but the guardian is neither Dragon,
    # Eagle, nor Whale -- no item exists for this species at all.
    state = make_state()
    state.add_item(Treasure.MONSTER_AID_DRAGON, owner_leader_id=1)

    assert holds_monster_command_item_for(state, 1, Monster.TROLL) is False


def test_holds_monster_command_item_for_false_when_holding_the_wrong_species_item():
    state = make_state()
    state.add_item(Treasure.MONSTER_AID_EAGLE, owner_leader_id=1)

    assert holds_monster_command_item_for(state, 1, Monster.R_DRAGON) is False
