"""Tests for turn/discovery_effects.py -- see its module docstring for the
stacking and MAX_SKILL_LEVEL-cap rationale.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.discovery_effects import ability_bonus_from_discoveries, effective_skill_level, holder_is_immune_to_spell
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
