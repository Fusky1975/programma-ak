"""Tests for turn/army_quality.py -- the ARMIES report's "Modified Quality"
column (Phase 279). See that module's own docstring for the full
derivation of each of its five modifiers.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import RACE_LEADERSHIP_TREASURE, Treasure
from ak_engine.turn.army_quality import army_peacetime_strength, compute_army_modified_quality
from ak_engine.turn.combat import Quality

HOME = HexCoord(0, 0)
FIELD = HexCoord(5, 5)


def _skills_with_druid(level: int) -> SkillTable:
    raw = [0] * 30
    raw[Ability.DRUID.value * 2] = level
    return SkillTable(raw)


def _state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home_province=HOME))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    return state


def test_home_province_gives_plus_one():
    state = _state()
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.VETERAN


def test_away_from_home_province_no_bonus():
    state = _state()
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_desert_without_camels_gives_minus_one():
    state = _state()
    state.provinces[FIELD].terrain = Terrain.DESERT
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.GREEN


def test_desert_with_a_camel_corps_present_has_no_penalty():
    state = _state()
    state.provinces[FIELD].terrain = Terrain.DESERT
    bowmen = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD)
    camels = ArmyState(2, 1, ArmyType.CAMEL_CORPS, Quality.AVERAGE, FIELD)
    state.add_army(bowmen)
    state.add_army(camels)

    assert compute_army_modified_quality(state, bowmen) == Quality.AVERAGE


def test_desert_without_camels_waived_by_a_present_explorer_with_find_water():
    # Bug fix: this ARMIES-report column was missing the same Find
    # Water (Advanced Ability) carve-out both real-combat copies in
    # battle_orchestrator.py already honor -- "If the Explorer is
    # present..., no units fighting with his side will suffer from
    # thirst and penalties in a Desert province," read as "present,"
    # not necessarily commanding this specific army.
    state = _state()
    state.provinces[FIELD].terrain = Terrain.DESERT
    state.add_leader(LeaderState(1, 1, "Explorer", FIELD, advanced_abilities={AdvancedAbility.EXPLORER_FIND_WATER}))
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_desert_without_camels_still_penalized_without_find_water():
    state = _state()
    state.provinces[FIELD].terrain = Terrain.DESERT
    state.add_leader(LeaderState(1, 1, "Hero", FIELD, advanced_abilities=set()))
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.GREEN


def test_druidic_shortfall_for_a_led_army_of_a_foreign_race():
    state = _state()
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=FIELD))
    state.add_leader(LeaderState(1, 1, "Hero", FIELD, skills=_skills_with_druid(0)))
    army = ArmyState(1, 2, ArmyType.DRAGON_WING, Quality.ELITE, FIELD, commanded_by=1)
    state.add_army(army)

    # DRUID_TABLE requires level 4 for Dragons; the Human leader has 0 --
    # shortfall 4, ELITE(5) - 4 = GREEN(1). FIELD is kingdom 2's own home
    # province (+1), but that's kingdom 2's bonus, not this army's owning
    # kingdom (2) either way -- home_province is compared against the
    # army's own kingdom, which also happens to be kingdom 2 here, so the
    # +1 applies too: GREEN(1) + 1 = AVERAGE(2).
    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_druidic_shortfall_king_substitution_for_an_unled_army():
    state = _state()
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_leader(LeaderState(1, 1, "The King", FIELD, is_king=True, skills=_skills_with_druid(0)))
    army = ArmyState(1, 2, ArmyType.DRAGON_WING, Quality.ELITE, FIELD)  # unled
    state.add_army(army)
    # FIELD is owned by kingdom 1 (see _state()); kingdom 1's own King
    # substitutes his Druidic ability for the garrison commander.
    state.provinces[FIELD].owner_kingdom_id = 1

    assert compute_army_modified_quality(state, army) == Quality.GREEN  # ELITE(5) - 4 shortfall


def test_race_item_bonus_for_a_matching_leadership_item():
    state = _state()
    state.add_leader(LeaderState(1, 1, "Hero", FIELD, skills=_skills_with_druid(0)))
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.VETERAN


def test_race_item_bonus_requires_the_item_to_match_the_armys_own_race():
    state = _state()
    state.add_leader(LeaderState(1, 1, "Hero", FIELD, skills=_skills_with_druid(0)))
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=1)  # wrong race's item
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_race_item_bonus_not_applied_to_an_unled_army():
    # No King-substitution carve-out for this rule, unlike Druidic ability
    # -- the user's own rules only ever name the army's own commanding
    # Hero or King.
    state = _state()
    state.add_leader(LeaderState(1, 1, "The King", FIELD, is_king=True))
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD)  # unled
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_clamped_at_elite_ceiling():
    state = _state()
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.ELITE, HOME)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.ELITE


def test_unregistered_province_has_no_desert_penalty():
    state = _state()
    away = HexCoord(20, 20)  # never added to state.provinces
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, away)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_army_peacetime_strength_reaches_through_illusory_terrain():
    # Phase 724: ProvinceState.illusory_terrain reaches army_peacetime_
    # strength() the same way is_island already does -- see turn/
    # strength.py compute_effective_strength()'s own docstring.
    state = _state()
    state.provinces[FIELD].illusory_terrain = Terrain.SEA
    army = ArmyState(1, 1, ArmyType.PHALANX, Quality.AVERAGE, FIELD)
    state.add_army(army)

    illusory = army_peacetime_strength(state, army, Ability.TACTICAL)

    state_without = _state()
    army_without = ArmyState(1, 1, ArmyType.PHALANX, Quality.AVERAGE, FIELD)
    state_without.add_army(army_without)
    ordinary = army_peacetime_strength(state_without, army_without, Ability.TACTICAL)

    assert illusory != ordinary


def test_army_peacetime_strength_reaches_through_illusory_terrain_enhanced():
    # Phase 757: ProvinceState.illusory_terrain_enhanced widens the same
    # blend from 50/50 to 33/67 -- reaches army_peacetime_strength() the
    # same way illusory_terrain itself already does, above.
    state = _state()
    state.provinces[FIELD].illusory_terrain = Terrain.SEA
    state.provinces[FIELD].illusory_terrain_enhanced = True
    army = ArmyState(1, 1, ArmyType.PHALANX, Quality.AVERAGE, FIELD)
    state.add_army(army)

    enhanced = army_peacetime_strength(state, army, Ability.TACTICAL)

    state_base = _state()
    state_base.provinces[FIELD].illusory_terrain = Terrain.SEA
    army_base = ArmyState(1, 1, ArmyType.PHALANX, Quality.AVERAGE, FIELD)
    state_base.add_army(army_base)
    base_blend = army_peacetime_strength(state_base, army_base, Ability.TACTICAL)

    assert enhanced != base_blend


def test_race_leadership_treasure_covers_the_four_humanoid_races():
    # Phase 285: this table moved to models/treasure.py so turn/
    # battle_orchestrator.py could share it too, without a circular
    # import -- see that module's own docstring.
    assert RACE_LEADERSHIP_TREASURE == {
        Race.HUMAN: Treasure.LEADERSHIP_HUMAN,
        Race.ELVEN: Treasure.LEADERSHIP_ELVEN,
        Race.DWARVEN: Treasure.LEADERSHIP_DWARVEN,
        Race.ORCISH: Treasure.LEADERSHIP_ORCISH,
    }


def test_druidic_shortfall_uses_the_commanders_own_race_not_the_kingdoms():
    # A King's companion can be of another race than the kingdom they serve
    # (a Dwarf under a Human King): leading the Human army is leading a race
    # other than their own, so the Druid Table applies to them.
    state = _state()
    state.add_leader(LeaderState(1, 1, "Companion", FIELD, skills=_skills_with_druid(0), race=Race.DWARVEN))
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.GREEN  # AVERAGE(2) - 1


def test_druidic_shortfall_a_companion_leading_his_own_race_has_none():
    state = _state()
    state.add_leader(LeaderState(1, 1, "Companion", FIELD, skills=_skills_with_druid(0), race=Race.HUMAN))
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_druidic_shortfall_with_one_druid_level_covers_a_human_army():
    state = _state()
    state.add_leader(LeaderState(1, 1, "Companion", FIELD, skills=_skills_with_druid(1), race=Race.DWARVEN))
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE


def test_druidic_shortfall_uses_the_race_an_army_is_composed_of():
    # A mercenary band of Dwarves (ArmyState.race) picked up by a Human
    # commander with no Druidism: the Human leads a race other than his own.
    state = _state()
    state.add_leader(LeaderState(1, 1, "Hero", FIELD, skills=_skills_with_druid(0)))
    army = ArmyState(1, 1, ArmyType.AXEMEN, Quality.AVERAGE, FIELD, commanded_by=1, race=Race.DWARVEN)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.GREEN  # AVERAGE(2) - 1


def test_druidic_shortfall_a_dwarf_leading_a_dwarven_band_has_none():
    state = _state()
    state.add_leader(LeaderState(1, 1, "Dwarf", FIELD, skills=_skills_with_druid(0), race=Race.DWARVEN))
    army = ArmyState(1, 1, ArmyType.AXEMEN, Quality.AVERAGE, FIELD, commanded_by=1, race=Race.DWARVEN)
    state.add_army(army)

    assert compute_army_modified_quality(state, army) == Quality.AVERAGE
