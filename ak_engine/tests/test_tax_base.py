"""Tests for turn/tax_base.py -- see its module docstring for the full,
project-original scar-then-percent-modifier formula this exercises.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.tax_base import compute_tax_base, province_tax_yield

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


def test_province_tax_yield_combines_scar_then_bless():
    # base 10 -> scar -2 -> 8 -> Bless +60% -> 12
    province = ProvinceState(
        HOME, Terrain.PLAINS, Race.HUMAN, tax=10, scar_terrain_gold_reduction=2, tax_modifier_percent=60
    )
    assert province_tax_yield(province) == 12


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
