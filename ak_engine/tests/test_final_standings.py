"""Tests for turn/final_standings.py -- see its module docstring for the
full AKGEN_reverse_engineering_report (2).md SS14.6 derivation.
"""

from __future__ import annotations

from unittest.mock import patch

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.final_standings import (
    compose_final_standings_report,
    final_standings,
    individual_king_points,
    kingdom_points,
    kingdom_sort_key,
    qualifies_for_all_star,
    qualifies_for_valhalla_induction,
)

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


def test_individual_king_points_matches_kingdom_points_when_king_holds_everything():
    # Same worked example as test_kingdom_points_combines_office_and_
    # treasure_terms (20 Emperor + 10 Treasurer + 1 item == 31) -- when
    # the King himself is the one holding every title and item,
    # individual_king_points has nothing to narrow away.
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=10))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.kingdoms[1].treasury = 7
    state.add_item(Treasure.WEAPON_1, owner_leader_id=1)
    state.emperor_kingdom_id = 1

    assert individual_king_points(state, 1) == 31.0
    assert individual_king_points(state, 1) == kingdom_points(state, 1)


def test_individual_king_points_excludes_a_treasure_item_held_by_a_hero_not_the_king():
    # Treasurer is still won by the King (Treasurer's own Merit Points are
    # Kingdom-scoped treasury, tied between every leader of the Kingdom,
    # broken by lower leader_id) -- but the trvic item itself is owned by
    # a Hero, not the King, so only that term drops out: kingdom_points
    # stays 31.0 (Emperor 20 + Treasurer 10 + item 1), individual_king_
    # points drops to 30.0 (Emperor 20 + Treasurer 10, no item credit).
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=10))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.add_leader(LeaderState(2, 1, "HeroRich", HOME))
    state.kingdoms[1].treasury = 7
    state.add_item(Treasure.WEAPON_1, owner_leader_id=2)
    state.emperor_kingdom_id = 1

    assert kingdom_points(state, 1) == 31.0
    assert individual_king_points(state, 1) == 30.0


def test_individual_king_points_excludes_an_office_won_by_a_hero_not_the_king():
    # A Hero with a real Chancellor-qualifying Merit tally (discoveries_
    # found_first, 3 points each) outranks the King's own zero and wins
    # Office.CHANCELLOR outright -- kingdom_points still banks it (30.0 =
    # Emperor 20 + Chancellor 10), but individual_king_points only credits
    # the King's own personal win, Emperor alone (20.0).
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    hero = LeaderState(2, 1, "HeroSage", HOME)
    hero.merit_tally.discoveries_found_first = 1
    state.add_leader(hero)
    state.emperor_kingdom_id = 1

    assert kingdom_points(state, 1) == 30.0
    assert individual_king_points(state, 1) == 20.0


def test_individual_king_points_is_zero_with_no_king_registered():
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_leader(LeaderState(2, 1, "HeroOnly", HOME))
    state.emperor_kingdom_id = 1

    assert individual_king_points(state, 1) == 0.0


def test_individual_king_points_is_zero_before_any_emperor_is_elected():
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    assert individual_king_points(state, 1) == 0.0


def test_qualifies_for_all_star_true_at_and_above_the_new_rules_threshold():
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)

    with patch("ak_engine.turn.final_standings.kingdom_points", return_value=7.5):
        assert qualifies_for_all_star(state, 1) is True

    with patch("ak_engine.turn.final_standings.kingdom_points", return_value=100.0):
        assert qualifies_for_all_star(state, 1) is True


def test_qualifies_for_all_star_false_just_below_the_new_rules_threshold():
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)

    with patch("ak_engine.turn.final_standings.kingdom_points", return_value=7.499):
        assert qualifies_for_all_star(state, 1) is False


def test_qualifies_for_valhalla_induction_true_when_individual_points_meet_the_threshold():
    # Kingdom 1's own individual_king_points clears 20 even though
    # Kingdom 2 is the real #1 in final_standings (fewer individual
    # points doesn't block the "or first place" branch from mattering
    # here -- the >= 20 branch alone is enough).
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_kingdom(KingdomState(2, "B", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=10_000))
    state.emperor_kingdom_id = 1

    with patch("ak_engine.turn.final_standings.individual_king_points", return_value=20.0):
        assert final_standings(state)[0] != 1
        assert qualifies_for_valhalla_induction(state, 1) is True


def test_qualifies_for_valhalla_induction_false_below_threshold_and_not_first():
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_kingdom(KingdomState(2, "B", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=10_000))
    state.emperor_kingdom_id = 1

    with patch("ak_engine.turn.final_standings.individual_king_points", return_value=19.999):
        assert final_standings(state)[0] != 1
        assert qualifies_for_valhalla_induction(state, 1) is False


def test_qualifies_for_valhalla_induction_true_when_kingdom_is_first_despite_low_individual_points():
    # Kingdom 1 is the real #1 (Tax_Base 1000 dwarfs Kingdom 2's own 0) --
    # the "or first place" branch alone qualifies it even with 0
    # individual King points.
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=1000))
    state.add_kingdom(KingdomState(2, "B", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.emperor_kingdom_id = 1

    with patch("ak_engine.turn.final_standings.individual_king_points", return_value=0.0):
        assert final_standings(state)[0] == 1
        assert qualifies_for_valhalla_induction(state, 1) is True


# -- Phase 476: compose_final_standings_report() ---------------------------


def test_compose_final_standings_report_is_none_before_any_emperor_is_elected():
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    assert compose_final_standings_report(state) is None


def test_compose_final_standings_report_matches_the_individual_functions():
    # Kingdom 1's own King holds Emperor (20, self, no discount) and
    # Treasurer (10, treasury 7 > 0) -- kingdom_points/individual_king_
    # points both 30.0, clearing both the all-star (>=7.5) and Valhalla
    # (>=20) thresholds. Kingdom 2 has nothing at all (0.0, neither).
    state = _state_with_kingdom(1, Alignment.GOOD, HOME)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=10))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.kingdoms[1].treasury = 7
    state.emperor_kingdom_id = 1
    state.add_kingdom(KingdomState(2, "B", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))

    report = compose_final_standings_report(state)

    assert report is not None
    assert report.standings == tuple(final_standings(state))
    assert report.standings == (1, 2)
    assert report.kingdom_points == {1: kingdom_points(state, 1), 2: kingdom_points(state, 2)}
    assert report.kingdom_points == {1: 30.0, 2: 0.0}
    assert report.all_star_qualifiers == (1,)
    assert report.valhalla_qualifiers == (1,)
