from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.monster import Monster
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.sense_magic_items import sense_magic_items_in_province

HOME = HexCoord(3, 9)
ELSEWHERE = HexCoord(9, 9)
MAGE_ID = 1
OTHER_ID = 2


def _state_with_mage(*, mage_qualifies: bool = True) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Magia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Otheria", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(MAGE_ID, 1, "Mage", HOME))
    state.add_leader(LeaderState(OTHER_ID, 2, "Other", HOME))
    if mage_qualifies:
        state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=MAGE_ID)  # meets OFFICE_MIN_POINTS[Office.MAGE]
    return state


def test_returns_none_when_leader_does_not_hold_the_office():
    state = _state_with_mage(mage_qualifies=False)
    state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=OTHER_ID)

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) is None


def test_returns_empty_list_when_arch_mage_but_nothing_present():
    state = _state_with_mage()

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == []


def test_senses_another_leaders_item_in_the_same_province():
    state = _state_with_mage()
    item = state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=OTHER_ID)

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == [item.treasure]


def test_excludes_the_sensing_leaders_own_items():
    state = _state_with_mage()
    state.add_item(Treasure.AMULET_ANTI_NECROMANCY, owner_leader_id=MAGE_ID)

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == []


def test_excludes_items_owned_by_leaders_in_a_different_province():
    state = _state_with_mage()
    state.leaders[OTHER_ID].location = ELSEWHERE
    state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=OTHER_ID)

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == []


def test_excludes_unowned_items():
    state = _state_with_mage()
    state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=None)

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == []


def test_excludes_gold_hoards_quest_items_and_the_no_treasure_sentinel():
    state = _state_with_mage()
    state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=OTHER_ID)
    state.add_item(Treasure.QUEST_SNOWBALL, owner_leader_id=OTHER_ID)
    state.add_item(Treasure.NO_TREASURE, owner_leader_id=OTHER_ID)

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == []


def test_senses_multiple_genuine_magic_items_at_once():
    state = _state_with_mage()
    wand = state.add_item(Treasure.WAND_CHARM, owner_leader_id=OTHER_ID)
    book = state.add_item(Treasure.BOOK_MELEE, owner_leader_id=OTHER_ID)

    sensed = sense_magic_items_in_province(state, MAGE_ID, HOME)

    assert sensed is not None
    assert set(sensed) == {wand.treasure, book.treasure}


def _feature(feature_id: int, coord: HexCoord, treasure: Treasure | None, *, looted: bool = False) -> Feature:
    return Feature(
        feature_id=feature_id, coord=coord, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE, treasure=treasure,
        looted=looted,
    )


def test_senses_the_magic_treasure_lying_in_a_feature_of_the_province_found_or_not():
    # Real SE3 reports: "Legend says the Cloak of Stealth is hidden here. ... The Platinum Wand senses the Cloak of
    # Stealth in Cretacia."
    state = _state_with_mage()
    state.add_feature(_feature(1, HOME, Treasure.AMULET_ANTI_WHITE))  # nobody has discovered it

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == [Treasure.AMULET_ANTI_WHITE]


def test_ignores_a_looted_feature_a_gold_hoard_and_a_feature_elsewhere():
    state = _state_with_mage()
    state.add_feature(_feature(1, HOME, Treasure.AMULET_ANTI_WHITE, looted=True))
    state.add_feature(_feature(2, HOME, Treasure.GOLD_HOARD_LARGE))
    state.add_feature(_feature(3, ELSEWHERE, Treasure.AMULET_ANTI_NECROMANCY))

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == []


def test_senses_feature_treasure_before_the_items_other_leaders_carry():
    state = _state_with_mage()
    state.add_item(Treasure.AMULET_ANTI_NECROMANCY, owner_leader_id=OTHER_ID)
    state.add_feature(_feature(1, HOME, Treasure.AMULET_ANTI_WHITE))

    assert sense_magic_items_in_province(state, MAGE_ID, HOME) == [Treasure.AMULET_ANTI_WHITE, Treasure.AMULET_ANTI_NECROMANCY]
