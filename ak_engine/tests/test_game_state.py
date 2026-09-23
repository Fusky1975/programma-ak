from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.rumor import Rumor, RumorContent
from ak_engine.models.temper import Temper
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


def test_kingdom_state_starts_with_no_discoveries():
    # Phase 266: KingdomState.discoveries mirrors CTBOTH.PAS's own `dknow`
    # per-kingdom boolean array -- a fresh kingdom knows nothing yet.
    state = make_state()
    assert state.kingdoms[1].discoveries == set()


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


def test_has_met_true_for_same_kingdom():
    # Phase 408 -- mirrors is_allied's own same-kingdom shortcut.
    state = make_state()
    assert state.has_met(1, 1) is True


def test_has_met_false_without_recorded_contact():
    state = make_state()
    assert state.has_met(1, 2) is False


def test_has_met_true_when_contact_recorded():
    state = make_state()
    state.kingdoms_met.add(frozenset({1, 2}))
    assert state.has_met(1, 2) is True
    assert state.has_met(2, 1) is True


def test_has_met_none_kingdom_id_has_met_nobody():
    state = make_state()
    assert state.has_met(None, 1) is False
    assert state.has_met(1, None) is False
    assert state.has_met(None, None) is False


def test_has_met_for_full_turn_true_for_same_kingdom():
    # Phase 491 -- mirrors has_met()'s own same-kingdom shortcut.
    state = make_state()
    assert state.has_met_for_full_turn(1, 1) is True


def test_has_met_for_full_turn_none_kingdom_id_has_met_nobody():
    state = make_state()
    assert state.has_met_for_full_turn(None, 1) is False
    assert state.has_met_for_full_turn(1, None) is False


def test_has_met_for_full_turn_false_without_any_recorded_contact():
    state = make_state()
    assert state.has_met_for_full_turn(1, 2) is False


def test_has_met_for_full_turn_false_the_same_turn_contact_was_first_made():
    state = make_state()
    state.turn_number = 5
    state.kingdoms_met.add(frozenset({1, 2}))
    state.kingdoms_met_since[frozenset({1, 2})] = 5

    assert state.has_met_for_full_turn(1, 2) is False


def test_has_met_for_full_turn_true_once_a_full_turn_has_passed():
    state = make_state()
    state.turn_number = 6
    state.kingdoms_met.add(frozenset({1, 2}))
    state.kingdoms_met_since[frozenset({1, 2})] = 5

    assert state.has_met_for_full_turn(1, 2) is True
    assert state.has_met_for_full_turn(2, 1) is True


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


# -- Rumor registry (Phase 243) --


def _dummy_rumor(rumor_id: int, kingdom_id: int = 1) -> Rumor:
    return Rumor(
        rumor_id=rumor_id,
        kingdom_id=kingdom_id,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=1,
        is_true=True,
        described_coord=FIELD,
        described_monster=Monster.ARCHER,
    )


def test_add_rumor_stores_it_by_id():
    state = make_state()
    rumor = _dummy_rumor(state.new_rumor_id())
    state.add_rumor(rumor)
    assert state.rumors[rumor.rumor_id] is rumor


def test_new_rumor_ids_do_not_collide():
    state = make_state()
    first = _dummy_rumor(state.new_rumor_id())
    state.add_rumor(first)
    second = _dummy_rumor(state.new_rumor_id())
    assert second.rumor_id == first.rumor_id + 1


def test_rumors_heard_by_filters_correctly():
    state = make_state()
    mine = _dummy_rumor(state.new_rumor_id(), kingdom_id=1)
    state.add_rumor(mine)
    other = _dummy_rumor(state.new_rumor_id(), kingdom_id=2)
    state.add_rumor(other)
    assert [r.rumor_id for r in state.rumors_heard_by(1)] == [mine.rumor_id]
    assert state.rumors_heard_by(3) == []


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


# -- Phase 623: ProvinceState.known_to_kingdom() -----------------------------


def test_known_to_kingdom_false_with_no_recorded_exploration():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN)

    assert province.known_to_kingdom(1) is False


def test_known_to_kingdom_true_at_exactly_the_floor():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN)
    province.explored_percent_by_kingdom[1] = 1

    assert province.known_to_kingdom(1) is True


def test_known_to_kingdom_true_above_the_floor():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN)
    province.explored_percent_by_kingdom[1] = 50

    assert province.known_to_kingdom(1) is True


def test_known_to_kingdom_is_per_kingdom():
    province = ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN)
    province.explored_percent_by_kingdom[1] = 50

    assert province.known_to_kingdom(2) is False


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
    assert tally.land_battles_won_points == 0
    assert tally.land_battles_lost_points == 0
    assert tally.naval_battles_won_points == 0
    assert tally.naval_battles_lost_points == 0
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


# -- Phase 231: GameState.world_events / record_world_event() ----------------


def test_game_state_world_events_starts_empty():
    state = GameState()

    assert state.world_events == []


# -- Phase 493: LeaderState.advanced_abilities / GameState.game_number ------


def test_leader_state_advanced_abilities_defaults_to_an_empty_set():
    leader = LeaderState(1, 1, "King", HOME)

    assert leader.advanced_abilities == set()


def test_leader_state_advanced_abilities_is_not_shared_between_instances():
    # A mutable default-factory bug (a shared literal set) would let one
    # leader's own grant leak into every other leader's own set.
    leader_a = LeaderState(1, 1, "King", HOME)
    leader_b = LeaderState(2, 1, "Hero", HOME)

    leader_a.advanced_abilities.add(AdvancedAbility.HOLY_PLACES)

    assert leader_b.advanced_abilities == set()


def test_game_state_game_number_defaults_to_1():
    state = GameState()

    assert state.game_number == 1


def test_leader_state_special_encounter_plan_defaults_to_empty():
    # Phase 669 -- an unset SEP reads as a real, sourced empty-plan
    # fallback, not a placeholder (see the field's own docstring).
    leader = LeaderState(1, 1, "King", HOME)

    assert leader.special_encounter_plan == ()


def test_record_world_event_appends_a_world_event():
    state = GameState()

    state.record_world_event(FIELD, ["Something happened."])

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == FIELD
    assert event.lines == ["Something happened."]


def test_record_world_event_is_independent_per_call():
    state = GameState()

    state.record_world_event(HOME, ["First."])
    state.record_world_event(FIELD, ["Second."])

    assert [event.coord for event in state.world_events] == [HOME, FIELD]
    assert [event.lines for event in state.world_events] == [["First."], ["Second."]]


# -- Phase 259: King succession (remove_leader's Royal Heir installation) --


def test_remove_leader_installs_a_royal_heir_when_a_king_dies():
    state = make_state()
    king = LeaderState(
        1, 1, "Aldric", FIELD, skills=SkillTable(raw_values=list(range(31))),
        is_king=True, temper=Temper.BRAVE, alignment=Alignment.GOOD, race=Race.HUMAN,
    )
    state.add_leader(king)

    state.remove_leader(1)

    assert 1 in state.dead_leaders
    dead_king = state.dead_leaders[1]
    assert dead_king.name == "Aldric"
    assert dead_king.skills.raw_values == list(range(31))  # the exact original, untouched

    heir = state.leaders[1]
    assert heir is not dead_king
    assert heir.leader_id == 1
    assert heir.kingdom_id == 1
    assert heir.name == "Aldric"  # SAY.PAS _LSucc: "will use > predecessor's name"
    assert heir.location == FIELD
    assert heir.is_king is True
    assert heir.is_royal_heir is True
    assert heir.temper is Temper.BRAVE
    assert heir.alignment is Alignment.GOOD
    assert heir.race is Race.HUMAN
    # Phase 552: the real reset keeps the automatic training bonus
    # (AKGEN_reverse_engineering_report (5).md SS6.2) -- Melee/Archery/
    # Sage at (1, 3), everything else at 0 -- not fully zeroed.
    expected_skills = SkillTable(raw_values=[0] * 31)
    for bonus_ability in (Ability.MELEE, Ability.ARCHERY, Ability.SAGE):
        expected_skills.set_pair_for_ability(bonus_ability, skill=1, aptitude=3)
    assert heir.skills.raw_values == expected_skills.raw_values


def test_remove_leader_royal_heir_total_usable_skill_is_the_real_baseline_of_3():
    # Phase 552: 3 (this reset) + 4 ((K)g Ab's later points) = the real
    # Total_USkill < 7 threshold -- not 0 + 7.
    from ak_engine.turn.cast_execution import _total_usable_skill

    state = make_state()
    king = LeaderState(
        1, 1, "Aldric", FIELD, skills=SkillTable(raw_values=list(range(31))),
        is_king=True, temper=Temper.BRAVE, alignment=Alignment.GOOD, race=Race.HUMAN,
    )
    state.add_leader(king)

    state.remove_leader(1)

    assert _total_usable_skill(state.leaders[1]) == 3


def test_remove_leader_hero_death_leaves_no_heir():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Hero", FIELD, is_king=False))

    state.remove_leader(1)

    assert 1 in state.dead_leaders
    assert 1 not in state.leaders


def test_remove_leader_kingless_king_leaves_no_heir():
    # Not a reachable state via kingdom_bridge.py, but remove_leader()
    # should still degrade gracefully rather than install a throne with
    # no Kingdom to belong to.
    state = make_state()
    state.add_leader(LeaderState(1, None, "Wanderer", FIELD, is_king=True))

    state.remove_leader(1)

    assert 1 in state.dead_leaders
    assert 1 not in state.leaders


def test_remove_leader_unknown_leader_id_is_a_no_op():
    state = make_state()

    state.remove_leader(999)  # never raises, never touches dead_leaders

    assert state.dead_leaders == {}
    assert 999 not in state.leaders


def test_remove_leader_applies_the_real_25_percent_office_merit_death_penalty():
    # Phase 377: AKGEN_embedded_catalogs.json.txt's own two real worked
    # examples, "old - old div 4": Teleko lgenp 23->18, lmhpp 21->16.
    state = make_state()
    leader = LeaderState(1, 1, "Hero", FIELD, is_king=False)
    leader.merit_tally.land_battles_won_points = 23
    leader.merit_tally.monster_hp_defeated = 21
    state.add_leader(leader)

    state.remove_leader(1)

    dead = state.dead_leaders[1]
    assert dead.merit_tally.land_battles_won_points == 18
    assert dead.merit_tally.monster_hp_defeated == 16


def test_merit_tally_apply_death_penalty_uses_pascal_truncating_division():
    # Phase 377: AKGEN_embedded_catalogs.json.txt's own third real
    # example, Adele lgenp -17 -> -13 -- only matches truncating-toward-
    # zero division (Pascal's own `div`), not Python's floor `//`
    # (-17 // 4 == -5, giving -12, not the real -13).
    from ak_engine.models.game_state import MeritTally

    tally = MeritTally(land_battles_won_points=-17)
    tally.apply_death_penalty()
    assert tally.land_battles_won_points == -13


def test_apply_death_penalty_does_not_touch_royal_title_fields():
    # Phase 377: successful_thefts/diplomatic_merit_points back Phase
    # 369's own royal_title_system formulas, a separate title system
    # this same JSON source doesn't state the same death-penalty rule
    # for -- deliberately left untouched.
    state = make_state()
    leader = LeaderState(1, 1, "Hero", FIELD, is_king=False)
    leader.merit_tally.successful_thefts = 8
    leader.merit_tally.diplomatic_merit_points = 8.0
    state.add_leader(leader)

    state.remove_leader(1)

    dead = state.dead_leaders[1]
    assert dead.merit_tally.successful_thefts == 8
    assert dead.merit_tally.diplomatic_merit_points == 8.0


def test_board_width_and_height_default_to_normal_map_bounds():
    # Phase 780: the real value the world was actually built at is now
    # tracked here, but every existing fixture that never sets it must
    # keep exactly today's already-established effective board size --
    # NORMAL_MAP_BOUNDS's own real value (30, 15), the Super-AK size,
    # not "normale" 18x9 (see turn/movement.py's own corrected comment).
    state = GameState()
    assert state.board_width == 30
    assert state.board_height == 15
