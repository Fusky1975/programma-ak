"""Tests for turn/merit_points.py -- see its module docstring for the
full derivation of each Imperial Office's Merit Point formula, sourced
from the rulebook's own "TABELLA DELLE CARICHE IMPERIALI" (page 51).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.merit_points import (
    LEGENDARY_ITEM_BONUS_TREASURES,
    admiral_merit_points,
    chancellor_merit_points,
    defender_merit_points,
    emperor_merit_points,
    evilking_merit_points,
    legendary_item_victory_point_bonus_count,
    mage_merit_points,
    marshal_merit_points,
    merit_point_tiebreak_key,
    priest_merit_points,
    thiefprince_merit_points,
    treasurer_merit_points,
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
    # Phase 271: discoveries_found_first is worth 3 (world's first
    # discoverer), discoveries_found_not_first is worth 2 -- the
    # user-specified scoring that supersedes the rulebook's own flat
    # "+2 per Invention found first" figure.
    state = make_state()
    leader = state.leaders[1]
    leader.merit_tally.features_discovered_first = 2
    leader.merit_tally.discoveries_found_first = 1
    leader.merit_tally.discoveries_found_not_first = 4
    leader.merit_tally.discoveries_via_espionage = 3

    assert chancellor_merit_points(state, leader) == 2 * 2 + 3 * 1 + 2 * 4 + 3


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
    leader.merit_tally.land_battles_won_enemy_units = 5
    leader.merit_tally.land_battles_lost_own_units = 2

    assert marshal_merit_points(leader) == 3


def test_admiral_merit_points_combines_battles_skill_and_rich_sea_provinces():
    state = make_state()
    leader = state.leaders[1]
    leader.skills = skills_with(NAVAL=4)
    leader.merit_tally.naval_battles_won_enemy_units = 6
    leader.merit_tally.naval_battles_lost_own_units = 1
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

    assert merit_point_tiebreak_key(state, state.leaders[1]) == (42, 9)


def test_merit_point_tiebreak_key_independent_hero_is_zero_zero():
    state = make_state()
    hero = LeaderState(9, None, "Wanderer", HOME)
    state.add_leader(hero)

    assert merit_point_tiebreak_key(state, hero) == (0, 0)


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


def test_evilking_merit_points_combines_tax_base_skills_and_tally():
    state = make_evil_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=6))
    king = state.leaders[1]
    king.skills = skills_with(NECROMANCY=3, THIEF=2)
    king.merit_tally.monsters_killed_in_realm_province = 4
    king.merit_tally.successful_thief_tactics = 1

    assert evilking_merit_points(state, king) == 6 + 3 + 2 + 4 + 1


def test_thiefprince_merit_points_open_to_a_hero():
    # Unlike King of Pain, Prince of Thieves has no King-only/alignment gate.
    state = make_state()
    hero = LeaderState(9, 1, "Sneak", HOME)
    hero.skills = skills_with(THIEF=3)
    hero.merit_tally.gold_stolen = 10
    hero.merit_tally.magic_items_stolen = 2
    state.add_leader(hero)

    assert thiefprince_merit_points(state, hero) == 3 + 10 + 5 * 2


def test_thiefprince_merit_points_works_for_a_king_too():
    state = make_state()
    king = state.leaders[1]
    king.skills = skills_with(THIEF=1)

    assert thiefprince_merit_points(state, king) == 1
