"""Tests for turn/merit_points.py -- see its module docstring for the
full derivation of each Imperial Office's Merit Point formula, sourced
from the rulebook's own "TABELLA DELLE CARICHE IMPERIALI" (page 51).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.merit_points import (
    LEGENDARY_ITEM_BONUS_TREASURES,
    MARSHAL_QUALITY_POINTS,
    admiral_merit_points,
    assassin_merit_points,
    battle_quality_points,
    battlefool_merit_points,
    bravest_merit_points,
    chancellor_merit_points,
    cravenest_merit_points,
    curator_merit_points,
    defender_merit_points,
    desertking_merit_points,
    duellist_merit_points,
    elementalmage_merit_points,
    emperor_merit_points,
    evilking_merit_points,
    forestking_merit_points,
    illusionistmage_merit_points,
    jungleking_merit_points,
    legendary_item_victory_point_bonus_count,
    mage_merit_points,
    marshal_merit_points,
    merit_point_tiebreak_key,
    mountainking_merit_points,
    necromancermage_merit_points,
    plainsking_merit_points,
    priest_merit_points,
    psychicmage_merit_points,
    seaking_merit_points,
    teacher_merit_points,
    thiefprince_merit_points,
    treasurer_merit_points,
    wingman_merit_points,
)

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HOME, treasury=42))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    return state


def skills_with(**levels: int) -> SkillTable:
    raw_values = [0] * (len(Ability) * 2 + 1)
    for name, level in levels.items():
        i = Ability[name].value * 2
        raw_values[i] = level
        raw_values[i + 1] = level
    return SkillTable(raw_values)


def test_emperor_merit_points_is_tax_base():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=7))

    assert emperor_merit_points(state, 1) == 7


def test_treasurer_merit_points_is_kingdom_treasury():
    state = make_state()

    assert treasurer_merit_points(state, 1) == 42


def test_chancellor_merit_points_sums_explorer_spy_sage_skills():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(EXPLORER=2, SPY=1, SAGE=3, TACTICAL=9)

    assert chancellor_merit_points(state, leader) == 6


def test_chancellor_merit_points_adds_discovery_tally_terms():
    # Phase 1189 correction: discoveries_found_first is worth 2 (the real
    # compiled ldiscp accumulator, turn/practice_execution.py's own Phase
    # 795 addendum) and discoveries_found_not_first earns nothing --
    # superseding the former Phase 271 user-specified 3/2 scoring.
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.features_discovered_first = 2
    leader.merit_tally.discoveries_found_first = 1
    leader.merit_tally.discoveries_found_not_first = 4
    leader.merit_tally.discoveries_via_espionage = 3

    assert chancellor_merit_points(state, leader) == 2 * 2 + 2 * 1 + 3


def test_chancellor_merit_points_zero_with_no_skills_and_no_tally():
    state = make_state()
    leader = state.leaders[1]

    assert chancellor_merit_points(state, leader) == 0


def test_chancellor_merit_points_includes_ability_bonus_discoveries():
    # Phase 269: the Explorer/Spy/Sage skill term now reads
    # turn/discovery_effects.py's effective_skill_level(), so an owned
    # ability-bonus Discovery (COMPASS -> Explorer) is included.
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(EXPLORER=2, SPY=1, SAGE=3)
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    assert chancellor_merit_points(state, leader) == (2 + 1) + 1 + 3


def test_marshal_merit_points_nets_won_and_lost_units():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.land_battles_won_points = 5
    leader.merit_tally.land_battles_lost_points = 2

    assert marshal_merit_points(leader) == 3


def test_admiral_merit_points_combines_battles_skill_and_rich_sea_provinces():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(NAVAL=4)
    leader.merit_tally.naval_battles_won_points = 6
    leader.merit_tally.naval_battles_lost_points = 1
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.SEA, Race.NO_RACE, owner_kingdom_id=1, tax=2))
    state.add_province(ProvinceState(HexCoord(0, 2), Terrain.SEA, Race.NO_RACE, owner_kingdom_id=1, tax=1))

    assert admiral_merit_points(state, leader) == (6 - 1) + 4 + 1


def test_admiral_merit_points_rich_sea_bonus_applies_to_every_kingdom_member():
    # Footnote 1: the rich-sea-province bonus is per-kingdom, not tied to
    # whichever leader owns/found the province -- every leader of the
    # same kingdom gets the identical figure.
    state = make_state()
    state.add_leader(LeaderState(2, 1, "Borin", HOME))
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.SEA, Race.NO_RACE, owner_kingdom_id=1, tax=5))

    assert admiral_merit_points(state, state.leaders[1]) == admiral_merit_points(state, state.leaders[2]) == 1


def test_admiral_merit_points_independent_hero_has_no_rich_sea_bonus():
    state = make_state()
    hero = LeaderState(9, None, "Wanderer", HOME)
    state.add_leader(hero)

    assert admiral_merit_points(state, hero) == 0


# -- Phase 308: quality-weighted Marshal/Admiral battle scoring -------------


def test_marshal_quality_points_table_matches_the_rulebook():
    assert MARSHAL_QUALITY_POINTS == {
        Quality.DEPLETED: 0,
        Quality.GREEN: 0,
        Quality.AVERAGE: 1,
        Quality.VETERAN: 2,
        Quality.CRACK: 3,
        Quality.ELITE: 4,
    }


def test_battle_quality_points_reads_the_table_for_a_non_garrison_unit():
    assert battle_quality_points(ArmyType.HVY_CAVALRY, Quality.ELITE, is_attacker=False) == 4
    assert battle_quality_points(ArmyType.HVY_CAVALRY, Quality.GREEN, is_attacker=True) == 0


def test_battle_quality_points_applies_the_attacking_garrison_modifier():
    # The rulebook's own worked example: a Crack Garrison that attacks and
    # is destroyed gives only 2 points (3 - 1), not 3.
    assert battle_quality_points(ArmyType.GARRISON, Quality.CRACK, is_attacker=True) == 2


def test_battle_quality_points_garrison_modifier_only_applies_when_attacking():
    # The same Crack Garrison, as the defender, scores the unmodified 3.
    assert battle_quality_points(ArmyType.GARRISON, Quality.CRACK, is_attacker=False) == 3


def test_battle_quality_points_attacking_garrison_can_go_negative():
    # No floor is invented -- a defeated Green attacking Garrison scores -1.
    assert battle_quality_points(ArmyType.GARRISON, Quality.GREEN, is_attacker=True) == -1


def test_defender_merit_points_full_for_kills_half_for_negotiated():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.monster_hp_defeated = 10
    leader.merit_tally.monster_hp_neutralized = 7

    assert defender_merit_points(leader) == 10 + 7 // 2


def test_priest_merit_points_combines_casts_and_druid_white_skills():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(DRUID=2, WHITE=3)
    leader.merit_tally.resurrection_bless_casts = 4

    assert priest_merit_points(state, leader) == 4 + 2 * (2 + 3)


def test_mage_merit_points_sums_the_five_magic_talents_and_owned_wands():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(WHITE=1, NECROMANCY=1, ELEMENTAL=1, PSYCHIC=1, ILLUSION=1, DRUID=9)
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)
    state.add_item(Treasure.WAND_CHARM, owner_leader_id=1)

    assert mage_merit_points(state, leader) == 5 + 2


def test_mage_merit_points_ignores_skill_books_and_other_categories():
    # A Skill Book is consumed on read, not an ongoing "possessed" item --
    # only SPELL_WAND-category items count.
    state = make_state()
    leader = state.leaders[1]
    state.add_item(Treasure.BOOK_WHITE, owner_leader_id=1)
    state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=1)

    assert mage_merit_points(state, leader) == 0


def test_legendary_item_bonus_count_matches_the_ten_named_artifacts():
    state = make_state()
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)  # Excalibur
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)  # Holy Sword
    state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=1)  # not one of the 10

    assert legendary_item_victory_point_bonus_count(state, 1) == 2
    assert len(LEGENDARY_ITEM_BONUS_TREASURES) == 10


def test_merit_point_tiebreak_key_reads_treasury_then_tax_base():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=9))

    # Phase 377: a real third tier, lower leader_id wins -- encoded as
    # -leader_id so the whole tuple stays a plain "higher wins" key.
    assert merit_point_tiebreak_key(state, state.leaders[1]) == (42, 9, -1)


def test_merit_point_tiebreak_key_independent_hero_breaks_ties_by_leader_id():
    state = make_state()
    hero = LeaderState(9, None, "Wanderer", HOME)
    state.add_leader(hero)

    # Phase 377: previously (0, 0) for every kingdom-less Hero alike (an
    # unresolved tie); now the real third tier still applies.
    assert merit_point_tiebreak_key(state, hero) == (0, 0, -9)


def make_evil_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Mordoth", Race.HUMAN, Alignment.EVIL, HOME, treasury=42))
    state.add_leader(LeaderState(1, 1, "Vaelgor", HOME, is_king=True))
    return state


def test_evilking_merit_points_zero_for_non_king():
    state = make_evil_state()
    hero = LeaderState(9, 1, "Thug", HOME)
    hero.skills = skills_with(NECROMANCY=5)
    state.add_leader(hero)

    assert evilking_merit_points(state, hero) == 0


def test_evilking_merit_points_zero_when_kingdom_not_evil():
    state = make_state()  # Alignment.NEUTRAL, see make_state()
    king = state.leaders[1]
    king.skills = skills_with(NECROMANCY=5)

    assert evilking_merit_points(state, king) == 0


def test_evilking_merit_points_is_plain_tax_base():
    # Phase 369: the real disassembled formula is exactly Emperor's own
    # Tax_Base(King), restricted to the Evil-aligned King -- no skill or
    # tally terms at all (see turn/merit_points.py's own Phase 369 note).
    state = make_evil_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=6))
    king = state.leaders[1]
    king.skills = skills_with(NECROMANCY=3, THIEF=2)

    assert evilking_merit_points(state, king) == 6


def test_thiefprince_merit_points_reads_the_single_successful_thefts_tally():
    # Phase 369: the real formula is +1 per successful theft result, no
    # TH-skill term and no gold-vs-item distinction.
    state = make_state()
    hero = LeaderState(9, 1, "Sneak", HOME)
    hero.skills = skills_with(THIEF=3)
    hero.merit_tally.successful_thefts = 4
    state.add_leader(hero)

    assert thiefprince_merit_points(state, hero) == 4


def test_thiefprince_merit_points_works_for_a_king_too():
    state = make_state()
    king = state.leaders[1]
    king.merit_tally.successful_thefts = 1

    assert thiefprince_merit_points(state, king) == 1


# -- Phase 379: 18 leader-scoped royal titles -------------------------------
# See turn/merit_points.py's own Phase 379 addendum for the full sourcing
# (AKGEN_embedded_catalogs.json.txt gw_format.royal_title_system.entries).
# Most of these are single-field readers with no writer yet ("field
# exists, no populating consumer yet"); BATTLE_FOOL and CURATOR are the
# two computed exceptions and get more thorough coverage below.


def test_elementalmage_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.elemental_spell_casts = 3

    assert elementalmage_merit_points(leader) == 3


def test_illusionistmage_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.illusionist_spell_casts = 2

    assert illusionistmage_merit_points(leader) == 2


def test_necromancermage_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.necromancy_spell_casts = 4

    assert necromancermage_merit_points(leader) == 4


def test_psychicmage_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.psychic_spell_casts = 1

    assert psychicmage_merit_points(leader) == 1


def test_plainsking_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.plains_explorations = 5

    assert plainsking_merit_points(leader) == 5


def test_desertking_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.desert_explorations = 6

    assert desertking_merit_points(leader) == 6


def test_jungleking_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.jungle_explorations = 7

    assert jungleking_merit_points(leader) == 7


def test_forestking_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.forest_explorations = 8

    assert forestking_merit_points(leader) == 8


def test_mountainking_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.mountain_explorations = 9

    assert mountainking_merit_points(leader) == 9


def test_seaking_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.sea_explorations = 10

    assert seaking_merit_points(leader) == 10


def test_battlefool_merit_points_is_the_negative_of_combined_land_and_naval_merit():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.land_battles_won_points = 5
    leader.merit_tally.land_battles_lost_points = 8
    leader.merit_tally.naval_battles_won_points = 1
    leader.merit_tally.naval_battles_lost_points = 3

    # land = 5 - 8 = -3, naval = 1 - 3 = -2 -> -(-3 + -2) = 5
    assert battlefool_merit_points(leader) == 5


def test_battlefool_merit_points_negative_when_the_combined_record_is_positive():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.land_battles_won_points = 10
    leader.merit_tally.land_battles_lost_points = 1

    assert battlefool_merit_points(leader) == -9


def test_curator_merit_points_counts_items_outside_the_excluded_categories():
    state = make_state()
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)  # SPELL_WAND, counted
    state.add_item(Treasure.BOOK_WHITE, owner_leader_id=1)  # SKILL_BOOK, counted
    state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=1)  # excluded
    state.add_item(Treasure.QUEST_SNOW_QUEST, owner_leader_id=1)  # excluded
    state.add_item(Treasure.NO_TREASURE, owner_leader_id=1)  # SENTINEL, excluded

    assert curator_merit_points(state, state.leaders[1]) == 2


def test_curator_merit_points_zero_with_no_items():
    state = make_state()

    assert curator_merit_points(state, state.leaders[1]) == 0


def test_curator_merit_points_excludes_named_unique_artifacts():
    # Phase 503: the real Pascal `hla..rali` range (CTBOTH.PAS's own
    # `treasure` enum) tops out at ordinal 66 (SKILL_BOOK's own last
    # member), just before GOLD_HOARD (67-69) -- NAMED_UNIQUE (93-98)
    # is well past `rali` and was never eligible, unlike the earlier
    # 4-category approximation this phase corrected.
    state = make_state()
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)  # SPELL_WAND, counted
    state.add_item(Treasure.NAMED_UNIQUE_CROWN_ROHAN, owner_leader_id=1)  # excluded

    assert curator_merit_points(state, state.leaders[1]) == 1


def test_teacher_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.teaching_interactions = 3

    assert teacher_merit_points(leader) == 3


def test_assassin_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.successful_assassinations = 2

    assert assassin_merit_points(leader) == 2


def test_duellist_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.duel_merit_net = -4

    assert duellist_merit_points(leader) == -4


def test_wingman_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.air_combat_merit = 6

    assert wingman_merit_points(leader) == 6


def test_cravenest_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.courage_encounter_merit = 5

    assert cravenest_merit_points(leader) == 5


def test_bravest_merit_points_reads_the_tally():
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.bravery_merit = 15

    assert bravest_merit_points(leader) == 15


def test_all_18_phase_379_fields_default_to_zero():
    # No writer populates any of these 16 MeritTally fields yet -- a
    # fresh leader reads 0 for all 18 formulas (2 of the 18, BATTLE_FOOL
    # and CURATOR, are computed rather than raw-field reads and are
    # covered on their own above).
    state = make_state()
    leader = state.leaders[1]

    assert elementalmage_merit_points(leader) == 0
    assert illusionistmage_merit_points(leader) == 0
    assert necromancermage_merit_points(leader) == 0
    assert psychicmage_merit_points(leader) == 0
    assert plainsking_merit_points(leader) == 0
    assert desertking_merit_points(leader) == 0
    assert jungleking_merit_points(leader) == 0
    assert forestking_merit_points(leader) == 0
    assert mountainking_merit_points(leader) == 0
    assert seaking_merit_points(leader) == 0
    assert teacher_merit_points(leader) == 0
    assert assassin_merit_points(leader) == 0
    assert duellist_merit_points(leader) == 0
    assert wingman_merit_points(leader) == 0
    assert cravenest_merit_points(leader) == 0
    assert bravest_merit_points(leader) == 0
