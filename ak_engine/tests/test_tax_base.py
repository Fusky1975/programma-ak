"""Tests for turn/tax_base.py -- see its module docstring for the full,
project-original scar-then-percent-modifier formula this exercises.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.tax_base import (
    apply_turn_revenue,
    compute_invention_bonus_percent,
    compute_office_gold_bonus,
    compute_tax_base,
    province_tax_yield,
)

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HOME))
    return state


def test_province_tax_yield_none_when_tax_unrecorded():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN)
    assert province_tax_yield(province) is None


def test_province_tax_yield_plain_base_tax():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=4)
    assert province_tax_yield(province) == 4


def test_province_tax_yield_applies_scar_terrain_reduction():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=4, scar_terrain_gold_reduction=2)
    assert province_tax_yield(province) == 2


def test_province_tax_yield_scar_terrain_floors_at_zero():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=3, scar_terrain_gold_reduction=10)
    assert province_tax_yield(province) == 0


def test_province_tax_yield_applies_bless_bonus():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=10, tax_modifier_percent=60)
    assert province_tax_yield(province) == 16


def test_province_tax_yield_earthquake_zeroes_revenue():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=10, tax_modifier_percent=-100)
    assert province_tax_yield(province) == 0


def test_province_tax_yield_applies_earthquake_flat_reduction():
    # Phase 270: Reinforced Concrete's own flat 3-gold Earthquake
    # replacement -- ProvinceState.earthquake_flat_reduction.
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=10, earthquake_flat_reduction=3)
    assert province_tax_yield(province) == 7


def test_province_tax_yield_earthquake_flat_reduction_floors_at_zero():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=2, earthquake_flat_reduction=3)
    assert province_tax_yield(province) == 0


def test_province_tax_yield_combines_scar_then_bless():
    # base 10 -> scar -2 -> 8 -> Bless +60% -> 12
    province = ProvinceState(
        HOME, Terrain.PLAINS, Race.HUMAN, tax=10, scar_terrain_gold_reduction=2, tax_modifier_percent=60
    )
    assert province_tax_yield(province) == 12


# -- Phase 509: Find Mines' own mine_gold_bonus -----------------------------


def test_province_tax_yield_applies_find_mines_bonus():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=4, mine_gold_bonus=3)
    assert province_tax_yield(province) == 7


def test_province_tax_yield_combines_mines_with_scar_then_bless():
    # base 10 -> scar -2, mines +5 -> 13 -> Bless +60% -> 20 (20.8 floored)
    province = ProvinceState(
        HOME,
        Terrain.PLAINS,
        Race.HUMAN,
        tax=10,
        scar_terrain_gold_reduction=2,
        mine_gold_bonus=5,
        tax_modifier_percent=60,
    )
    assert province_tax_yield(province) == 20


def test_province_tax_yield_mines_cannot_push_below_zero_floor():
    # scar reduction still dominates -- mines only ever add, never rescue
    # a heavily scarred province past its own floor-at-zero rule doesn't
    # apply here since mines are additive, but the combined value must
    # never go negative even in a degenerate scar > tax + mines case.
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=2, scar_terrain_gold_reduction=10, mine_gold_bonus=3)
    assert province_tax_yield(province) == 0


def test_compute_tax_base_sums_only_owned_provinces_with_known_tax():
    state = make_state()
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=4))
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=6))
    state.add_province(ProvinceState(HexCoord(0, 2), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=10))
    state.add_province(ProvinceState(HexCoord(0, 3), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # tax unknown

    assert compute_tax_base(state, 1) == 10
    assert compute_tax_base(state, 2) == 10


def test_compute_tax_base_ignores_unowned_provinces():
    state = make_state()
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, tax=4))

    assert compute_tax_base(state, 1) == 0


def test_compute_tax_base_zero_for_a_kingdom_with_no_provinces():
    state = make_state()
    assert compute_tax_base(state, 1) == 0


def test_compute_tax_base_does_not_count_allied_kingdoms_provinces():
    # Tax_Base is a single kingdom's own revenue figure, distinct from
    # GameState.friendly_provinces_for's broader owned-or-allied scope.
    state = make_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=10))

    assert compute_tax_base(state, 1) == 0


# -- Phase 268: compute_invention_bonus_percent() (Inv_Bonus) --------------


def test_compute_invention_bonus_percent_zero_with_no_discoveries():
    kingdom = KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME)
    assert compute_invention_bonus_percent(kingdom) == 0


def test_compute_invention_bonus_percent_sums_only_revenue_discoveries():
    kingdom = KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME)
    kingdom.discoveries = {
        Discovery.PEANUT_BUTTER_SANDWICH,  # 1%
        Discovery.ASPIRIN_PILL,  # 2%
        Discovery.COMPASS,  # ability bonus, no revenue contribution
    }

    assert compute_invention_bonus_percent(kingdom) == 3


# -- Phase 412: compute_office_gold_bonus() + apply_turn_revenue() --------


def test_compute_office_gold_bonus_credits_this_kingdoms_king_of_pain():
    # King of Pain's own merit-point formula is plain Tax_Base(King)
    # (Phase 369), gated at OFFICE_MIN_POINTS[EVIL_KING] == 25 -- a real
    # province tax base is needed to actually clear the Rank contest.
    state = make_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    state.add_leader(LeaderState(1, 1, "Vaelgor", HOME, is_king=True))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    assert compute_office_gold_bonus(state, 1) == 5


def test_compute_office_gold_bonus_credits_this_kingdoms_prince_of_thieves():
    state = make_state()
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    king.merit_tally.successful_thefts = 5
    state.add_leader(king)

    assert compute_office_gold_bonus(state, 1) == 10


def test_compute_office_gold_bonus_sums_both_offices_when_both_are_earned():
    state = make_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    king = LeaderState(1, 1, "Vaelgor", HOME, is_king=True)
    king.merit_tally.successful_thefts = 5
    state.add_leader(king)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    assert compute_office_gold_bonus(state, 1) == 15


def test_compute_office_gold_bonus_ignores_another_kingdoms_holder():
    state = make_state()
    state.kingdoms[2].alignment = Alignment.EVIL
    state.add_leader(LeaderState(2, 2, "Borin", HOME, is_king=True))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=30))

    assert compute_office_gold_bonus(state, 1) == 0


def test_compute_office_gold_bonus_zero_when_nobody_holds_either_office():
    state = make_state()

    assert compute_office_gold_bonus(state, 1) == 0


def test_apply_turn_revenue_credits_tax_base_plus_office_bonus_to_treasury():
    state = make_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    state.kingdoms[1].treasury = 50
    state.add_leader(LeaderState(1, 1, "Vaelgor", HOME, is_king=True))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    credited = apply_turn_revenue(state)

    assert credited == {1: 35, 2: 0}
    assert state.kingdoms[1].treasury == 85


def test_apply_turn_revenue_credits_each_kingdom_independently():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=4))
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=6))

    credited = apply_turn_revenue(state)

    assert credited == {1: 4, 2: 6}
    assert state.kingdoms[1].treasury == 4
    assert state.kingdoms[2].treasury == 6
