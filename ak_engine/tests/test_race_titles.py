"""Tests for turn/race_titles.py -- the 11 race-fanaticism Imperial
title Merit Point formulas (Phase 367). See that module's own docstring
for the full derivation.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import (
    ArmyState,
    GameState,
    KingdomState,
    LeaderState,
    ProvinceState,
    RaceTitleTally,
)
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.race_titles import (
    RACE_TITLE_LEGENDARY_ITEM,
    RACE_TITLE_NAMED_MONSTERS,
    RACE_TITLE_OFFICE,
    RACE_TITLE_REQUIRES_OWNED_PROVINCE,
    RACE_TITLE_RIVAL_RACES,
    RACE_TITLE_TURN_GATE,
    race_title_merit_points,
)

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Dwarfhold", Race.DWARVEN, Alignment.NEUTRAL, HOME, treasury=10))
    return state


def test_all_11_races_have_a_consistent_entry_in_every_table():
    assert len(RACE_TITLE_OFFICE) == 11
    for race in RACE_TITLE_OFFICE:
        assert race in RACE_TITLE_TURN_GATE
        assert race in RACE_TITLE_RIVAL_RACES
        assert race in RACE_TITLE_NAMED_MONSTERS
        assert race in RACE_TITLE_LEGENDARY_ITEM


def test_office_mapping_matches_the_confirmed_office_names():
    assert RACE_TITLE_OFFICE[Race.HUMAN] is Office.HUMAN_KING
    assert RACE_TITLE_OFFICE[Race.ELVEN] is Office.ELVEN_KING
    assert RACE_TITLE_OFFICE[Race.DWARVEN] is Office.DWARVEN_KING
    assert RACE_TITLE_OFFICE[Race.ORCISH] is Office.ORC_LORD
    assert RACE_TITLE_OFFICE[Race.DRAGONS] is Office.DRAGON_LORD
    assert RACE_TITLE_OFFICE[Race.EAGLES] is Office.EAGLE_KING
    assert RACE_TITLE_OFFICE[Race.WHALES] is Office.WHALE_KING
    assert RACE_TITLE_OFFICE[Race.MERMISH] is Office.MERMAN_KING
    assert RACE_TITLE_OFFICE[Race.ENTISH] is Office.ENT_KING
    assert RACE_TITLE_OFFICE[Race.TROLLISH] is Office.TROLL_KING
    assert RACE_TITLE_OFFICE[Race.WEREFOLK] is Office.WERE_KING


def test_only_the_4_core_humanoid_races_skip_the_owned_province_prerequisite():
    assert RACE_TITLE_REQUIRES_OWNED_PROVINCE == {
        Race.DRAGONS,
        Race.EAGLES,
        Race.WHALES,
        Race.MERMISH,
        Race.ENTISH,
        Race.TROLLISH,
        Race.WEREFOLK,
    }


def test_werefolk_named_monster_is_the_renegade_priest():
    # "Renegade priest" is Monster.WHITE_MAGE's own confirmed display
    # name (MONSTER_NAMES[Monster.WHITE_MAGE] == "Renegade Priest").
    from ak_engine.models.monster import Monster

    assert RACE_TITLE_NAMED_MONSTERS[Race.WEREFOLK] == frozenset({Monster.WHITE_MAGE})


def test_human_title_sums_every_tally_term_no_owned_province_needed():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)
    king.race_title_tally[Race.HUMAN] = RaceTitleTally(
        front_line_battles_won_points=3,
        front_line_battles_lost_points=1,
        rival_race_units_destroyed=4,  # Human's own rival is Orcish
        monsters_killed_in_race_province=2,
        named_monster_kills=0,
    )

    points = race_title_merit_points(state, king, Race.HUMAN)

    # (3-1) + 0 crack (humanoid, unresolvable) + 0 heroes-in-service +
    # 0 provinces-owned + 0.5*4 + 2 + 0 legendary-item = 6
    assert points == 6


def test_special_race_title_reads_0_without_an_owned_province():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)
    king.race_title_tally[Race.DRAGONS] = RaceTitleTally(front_line_battles_won_points=10)

    assert race_title_merit_points(state, king, Race.DRAGONS) == 0


def test_special_race_title_live_terms_once_a_province_is_owned():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.MTNS, Race.DRAGONS, owner_kingdom_id=1))
    king.race_title_tally[Race.DRAGONS] = RaceTitleTally(front_line_battles_won_points=10)

    # 10 (won) + 0 (crack, no armies yet) + 0 (heroes-in-service, king
    # is Dwarven not Dragon) + 1 (province owned)
    assert race_title_merit_points(state, king, Race.DRAGONS) == 11

    state.add_army(
        ArmyState(1, 1, ArmyType.DRAGON_WING, Quality.CRACK, HexCoord(5, 5), commanded_by=1)
    )
    # + 1 crack dragon unit commanded
    assert race_title_merit_points(state, king, Race.DRAGONS) == 12


def test_crack_plus_units_commanded_is_always_0_for_the_4_humanoid_races():
    # ArmyType carries no race marker for humanoid provinces (see module
    # docstring) -- even a Legion commanded by a Human King never counts.
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.HUMAN)
    state.add_leader(king)
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.CRACK, HOME, commanded_by=1))

    assert race_title_merit_points(state, king, Race.HUMAN) == 0


def test_heroes_in_service_and_provinces_owned_are_king_only():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    hero = LeaderState(2, 1, "Bram", HOME, is_king=False, race=Race.DWARVEN)
    state.add_leader(king)
    state.add_leader(hero)
    state.add_province(ProvinceState(HOME, Terrain.MTNS, Race.DWARVEN, owner_kingdom_id=1))

    # King: +1 hero-in-service (Bram) +1 province-owned (Home)
    assert race_title_merit_points(state, king, Race.DWARVEN) == 2
    # Hero: neither term applies
    assert race_title_merit_points(state, hero, Race.DWARVEN) == 0


def test_legendary_item_grants_2_points():
    state = make_state()
    king = LeaderState(1, 1, "Thane", HOME, is_king=True, race=Race.DWARVEN)
    state.add_leader(king)

    assert race_title_merit_points(state, king, Race.DWARVEN) == 0

    state.add_item(Treasure.LEADERSHIP_DWARVEN, owner_leader_id=1)

    assert race_title_merit_points(state, king, Race.DWARVEN) == 2


def test_whale_and_merman_titles_share_the_same_real_legendary_item():
    assert RACE_TITLE_LEGENDARY_ITEM[Race.WHALES] is Treasure.MONSTER_AID_WHALE
    assert RACE_TITLE_LEGENDARY_ITEM[Race.MERMISH] is Treasure.MONSTER_AID_WHALE
