from __future__ import annotations

from ak_engine.models.treasure import Treasure
from ak_engine.worldgen.magic_item_placement import (
    MAGIC_ITEM_COUNT,
    cursor_to_treasure,
    feature_gets_item_slot,
    initial_item_cursor,
    item_slot_count,
    next_item_cursor,
)
from ak_engine.worldgen.pascal_random import PascalRandom


def test_item_slot_count_matches_both_confirmed_totals():
    assert item_slot_count(128) == 64
    assert item_slot_count(230) == 114


def test_feature_gets_item_slot_gives_four_gold_then_four_item_per_block():
    slots = [feature_gets_item_slot(i) for i in range(8)]
    assert slots == [False, False, False, False, True, True, True, True]


def test_feature_gets_item_slot_cumulative_count_matches_item_slot_count():
    for feature_count in (128, 230):
        actual = sum(1 for i in range(feature_count) if feature_gets_item_slot(i))
        assert actual == item_slot_count(feature_count)


def test_initial_item_cursor_stays_within_0_to_66():
    rng = PascalRandom(seed=1)
    for _ in range(2000):
        cursor = initial_item_cursor(rng)
        assert 0 <= cursor < MAGIC_ITEM_COUNT


def test_next_item_cursor_wraps_around_at_67():
    assert next_item_cursor(66) == 0
    assert next_item_cursor(0) == 1
    assert next_item_cursor(33) == 34


def test_next_item_cursor_full_cycle_returns_to_start():
    cursor = 12
    for _ in range(MAGIC_ITEM_COUNT):
        cursor = next_item_cursor(cursor)
    assert cursor == 12


def test_cursor_to_treasure_covers_every_id_0_to_66():
    for cursor in range(MAGIC_ITEM_COUNT):
        treasure = cursor_to_treasure(cursor)
        assert isinstance(treasure, Treasure)
        assert treasure.value == cursor


def test_magic_item_count_matches_the_treasure_enums_own_contiguous_block():
    assert MAGIC_ITEM_COUNT == 67
    for value in range(67):
        Treasure(value)  # must not raise
