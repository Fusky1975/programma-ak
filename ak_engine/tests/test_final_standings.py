"""Tests for turn/final_standings.py -- see its module docstring for the
full AKGEN_reverse_engineering_report (2).md SS14.6 derivation.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.final_standings import final_standings, kingdom_points, kingdom_sort_key

HOME = HexCoord(0, 0)


def _state_with_kingdom(kingdom_id: int, alignment: Alignment, coord: HexCoord) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(kingdom_id, f"K{kingdom_id}", Race.HUMAN, alignment, coord))
    return state


def test_kingdom_points_is_zero_before_any_emperor_is_elected():
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.kingdoms[1].treasury = 10
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)

    assert kingdom_points(state, 1) == 0.0


def test_kingdom_points_combines_office_and_treasure_terms():
    # Kingdom 1 is both the elected Emperor (Office.EMPEROR value 20,
    # zero Alignment-distance discount against itself) and holds
    # Office.TREASURER (value 10, treasury > 0) via the same King, plus
    # one real trvic=1 legendary item: 20 + 10 + 1 == 31.
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=10))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.kingdoms[1].treasury = 7
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)
    state.emperor_kingdom_id = 1

    assert kingdom_points(state, 1) == 31.0


def test_kingdom_points_undiscounted_treasure_term_even_far_from_the_emperor():
    # Kingdom 2 holds no offices at all, just a legendary item -- its own
    # Alignment distance from the Emperor (Kingdom 1, Good) doesn't
    # touch the treasure term, only office_victory_points() would.
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_kingdom(KingdomState(2, "Farland", Race.HUMAN, Alignment.UNDEAD, HexCoord(5, 5)))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.emperor_kingdom_id = 1
    state.add_leader(LeaderState(20, 2, "Hero", HexCoord(5, 5)))
    state.add_item(Treasure.WEAPON_2, owner_leader_id=20)

    assert kingdom_points(state, 2) == 1.0


def test_kingdom_sort_key_composite_arithmetic_can_flip_a_naive_tuple_ordering():
    # Kingdom A has FEWER kingdom_points than Kingdom B (1.0 vs 2.0) --
    # a naive lexicographic (points, tax_base, treasury) tuple comparison
    # would always rank B above A regardless of tax_base. The real
    # composite key sums instead of comparing field-by-field, so A's own
    # much higher Tax_Base (1000*256 == 256000) outweighs its point
    # deficit: keyA (321536) > keyB (131072).
    state = _state_with_kingdom(3, Alignment.NEUTRAL, HexCoord(9, 9))
    state.emperor_kingdom_id = 3  # opens the "Emperor elected" gate; no King to hold any office

    state.add_kingdom(KingdomState(1, "A", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=1000))
    state.add_leader(LeaderState(10, 1, "HeroA", HOME))
    state.add_item(Treasure.WEAPON_1, owner_leader_id=10)

    state.add_kingdom(KingdomState(2, "B", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_leader(LeaderState(20, 2, "HeroB", HexCoord(1, 1)))
    state.add_item(Treasure.WEAPON_2, owner_leader_id=20)
    state.add_item(Treasure.WEAPON_5, owner_leader_id=20)

    assert kingdom_points(state, 1) == 1.0
    assert kingdom_points(state, 2) == 2.0
    key_a = kingdom_sort_key(state, 1)
    key_b = kingdom_sort_key(state, 2)
    assert key_a == 321536
    assert key_b == 131072
    assert key_a > key_b  # the real composite key flips the naive points-first ordering


def test_final_standings_orders_kingdoms_descending_by_sort_key():
    state = _state_with_kingdom(3, Alignment.NEUTRAL, HexCoord(9, 9))
    state.emperor_kingdom_id = 3

    state.add_kingdom(KingdomState(1, "A", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=1000))
    state.add_leader(LeaderState(10, 1, "HeroA", HOME))
    state.add_item(Treasure.WEAPON_1, owner_leader_id=10)

    state.add_kingdom(KingdomState(2, "B", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_leader(LeaderState(20, 2, "HeroB", HexCoord(1, 1)))
    state.add_item(Treasure.WEAPON_2, owner_leader_id=20)
    state.add_item(Treasure.WEAPON_5, owner_leader_id=20)

    # A (key 321536) > B (key 131072) > Empire (0 points, 0 tax, 0 treasury)
    assert final_standings(state) == [1, 2, 3]


def test_final_standings_ties_keep_original_iteration_order():
    state = GameState()
    state.add_kingdom(KingdomState(1, "First", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Second", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    # No emperor elected -- both Kingdoms' own kingdom_points, Tax_Base,
    # and treasury are all 0, a genuine tie.

    assert final_standings(state) == [1, 2]
