from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality

HOME = HexCoord(0, 0)
FIELD = HexCoord(1, 1)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.AXEMEN, Quality.AVERAGE, FIELD))
    return state


def test_add_leader_and_leaders_at():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", FIELD))
    state.add_leader(LeaderState(2, 2, "Rival", HOME))
    assert {leader.leader_id for leader in state.leaders_at(FIELD)} == {1}
    assert state.leaders_at(HexCoord(9, 9)) == []


def test_armies_commanded_by_filters_correctly():
    state = make_state()
    state.armies[101].commanded_by = 1
    assert [army.army_id for army in state.armies_commanded_by(1)] == [101]
    assert state.armies_commanded_by(2) == []


def test_army_defaults_to_unled():
    state = make_state()
    assert state.armies[101].commanded_by is None


def test_armies_at_returns_only_armies_in_that_province():
    state = make_state()
    assert {a.army_id for a in state.armies_at(FIELD)} == {101, 201}
    assert state.armies_at(HOME) == []


def test_remove_army_drops_it():
    state = make_state()
    state.remove_army(101)
    assert 101 not in state.armies
    assert {a.army_id for a in state.armies_at(FIELD)} == {201}


def test_is_allied_true_for_same_kingdom():
    state = make_state()
    assert state.is_allied(1, 1) is True


def test_is_allied_false_without_alliance():
    state = make_state()
    assert state.is_allied(1, 2) is False


def test_is_allied_true_when_alliance_recorded():
    state = make_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    assert state.is_allied(1, 2) is True
    assert state.is_allied(2, 1) is True


def test_friendly_provinces_for_includes_owned_and_allied():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    assert state.friendly_provinces_for(1) == {HOME}
    state.allied_kingdoms.add(frozenset({1, 2}))
    assert state.friendly_provinces_for(1) == {HOME, FIELD}


def test_mercenaries_at_returns_only_ownerless_armies_at_that_location():
    state = make_state()
    state.add_army(ArmyState(301, None, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    assert {a.army_id for a in state.mercenaries_at(FIELD)} == {301}
    assert state.mercenaries_at(HOME) == []


def test_is_allied_none_kingdom_id_is_allied_with_nobody():
    state = make_state()
    assert state.is_allied(None, 1) is False
    assert state.is_allied(1, None) is False
    assert state.is_allied(None, None) is False


def test_independent_heroes_at_returns_only_ownerless_leaders_at_that_location():
    state = make_state()
    state.add_leader(LeaderState(50, None, "Wandering Hero", FIELD))
    state.add_leader(LeaderState(51, 1, "Employed Leader", FIELD))
    assert {leader.leader_id for leader in state.independent_heroes_at(FIELD)} == {50}
    assert state.independent_heroes_at(HOME) == []


def test_add_feature_and_features_at():
    state = make_state()
    state.add_feature(Feature(feature_id=1, coord=FIELD, kind=FeatureType.DUNGEON, guardian_monster=Monster.TROLL))
    state.add_feature(Feature(feature_id=2, coord=HOME, kind=FeatureType.TOMB))
    assert {f.feature_id for f in state.features_at(FIELD)} == {1}
    assert state.features_at(HexCoord(9, 9)) == []


def test_features_at_returns_multiple_features_sharing_a_coordinate():
    state = make_state()
    state.add_feature(Feature(feature_id=1, coord=FIELD, kind=FeatureType.DUNGEON))
    state.add_feature(Feature(feature_id=2, coord=FIELD, kind=FeatureType.TOMB))
    assert {f.feature_id for f in state.features_at(FIELD)} == {1, 2}


# -- Item-ownership registry (Phase 140) --


def test_add_item_assigns_a_new_id_and_stores_the_instance():
    state = make_state()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1, charges=10)
    assert item.item_id == 1
    assert state.items[item.item_id] is item
    assert item.treasure == Treasure.WAND_FIREBALL
    assert item.owner_leader_id == 1
    assert item.charges == 10


def test_new_item_ids_do_not_collide():
    state = make_state()
    first = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)
    second = state.add_item(Treasure.BOOK_MELEE, owner_leader_id=1)
    assert second.item_id == first.item_id + 1


def test_add_item_masks_charges_to_a_byte_like_the_pascal_source():
    # RUMORS.PAS Add_Tr: "trcharges[trav]:= tch and 255"
    state = make_state()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1, charges=300)
    assert item.charges == 300 & 255


def test_add_item_allows_an_unowned_instance():
    state = make_state()
    item = state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=None)
    assert item.owner_leader_id is None


def test_items_held_by_filters_correctly():
    state = make_state()
    mine = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)
    state.add_item(Treasure.BOOK_MELEE, owner_leader_id=2)
    assert [item.item_id for item in state.items_held_by(1)] == [mine.item_id]
    assert state.items_held_by(3) == []


def test_transfer_item_reassigns_the_owner():
    state = make_state()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)
    state.transfer_item(item.item_id, 2)
    assert state.items[item.item_id].owner_leader_id == 2
    assert state.items_held_by(1) == []
    assert [i.item_id for i in state.items_held_by(2)] == [item.item_id]


def test_transfer_item_to_none_makes_it_unowned():
    # Mirrors REPORTS.PAS's own quest-fulfillment cleanup: "trowner[tn]:= noleader".
    state = make_state()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)
    state.transfer_item(item.item_id, None)
    assert state.items[item.item_id].owner_leader_id is None


def test_transfer_item_on_unknown_id_is_a_no_op():
    state = make_state()
    state.transfer_item(999, 1)  # must not raise
    assert 999 not in state.items


# -- Phase 168: ProvinceState.effective_terrain() ---------------------------


def test_effective_terrain_returns_base_terrain_when_no_override():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN)

    assert province.effective_terrain() is Terrain.PLAINS


def test_effective_terrain_returns_override_when_set():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA)

    assert province.effective_terrain() is Terrain.SEA


def test_effective_terrain_ignores_illusory_terrain():
    # illusory_terrain (Illusory Terrain) only deceives what an outside
    # observer is told -- it must never leak into a real mechanics read.
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, illusory_terrain=Terrain.SEA)

    assert province.effective_terrain() is Terrain.PLAINS


# -- Phase 223: ProvinceState.tax -------------------------------------------


def test_province_tax_defaults_to_none():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN)

    assert province.tax is None


def test_province_tax_can_be_set():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, tax=4)

    assert province.tax == 4


# -- Phase 227: LeaderState.merit_tally -------------------------------------


def test_leader_merit_tally_defaults_to_all_zero():
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))

    tally = leader.merit_tally
    assert tally.land_battles_won_enemy_units == 0
    assert tally.land_battles_lost_own_units == 0
    assert tally.naval_battles_won_enemy_units == 0
    assert tally.naval_battles_lost_own_units == 0
    assert tally.monster_hp_defeated == 0
    assert tally.monster_hp_neutralized == 0
    assert tally.resurrection_bless_casts == 0
    assert tally.features_discovered_first == 0
    assert tally.discoveries_found_first == 0
    assert tally.discoveries_via_espionage == 0


def test_leader_merit_tally_is_independent_per_leader():
    a = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
    b = LeaderState(2, 1, "Borin", HexCoord(0, 0))

    a.merit_tally.monster_hp_defeated = 10

    assert b.merit_tally.monster_hp_defeated == 0


# -- Phase 228: GameState Emperor-election fields ----------------------------


def test_game_state_emperor_fields_default_to_none():
    state = GameState()

    assert state.emperor_kingdom_id is None
    assert state.last_emperor_vote_turn is None
