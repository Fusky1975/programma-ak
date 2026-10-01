"""Tests for webapp/hex_map.py -- the Provinces page's visual hex-grid map
(GM interface, Phase 981)."""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.webapp.hex_map import build_hex_map, kingdom_color


def test_kingdom_color_is_deterministic_and_cycles_past_the_palette_size():
    assert kingdom_color(1) == kingdom_color(1)
    assert kingdom_color(1) != kingdom_color(2)
    assert kingdom_color(1) == kingdom_color(1 + 12)  # cycles rather than erroring


def test_build_hex_map_has_one_cell_per_province():
    state = GameState()
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))
    state.add_province(ProvinceState(HexCoord(1, 0), Terrain.SEA, Race.NO_RACE, owner_kingdom_id=None))

    hex_map = build_hex_map(state)

    assert len(hex_map.cells) == 2
    assert {cell.x for cell in hex_map.cells} == {0, 1}


def test_build_hex_map_colors_unowned_provinces_neutral():
    state = GameState()
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))

    cell = build_hex_map(state).cells[0]

    assert cell.stroke_width == 1.0
    assert "Unowned" in cell.title


def test_build_hex_map_colors_owned_provinces_by_kingdom():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))

    cell = build_hex_map(state).cells[0]

    assert cell.stroke == kingdom_color(1)
    assert cell.stroke_width > 1.0
    assert "Testland" in cell.title


def test_build_hex_map_marks_a_kingdoms_home_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HexCoord(1, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))

    cells_by_x = {cell.x: cell for cell in build_hex_map(state).cells}

    assert cells_by_x[0].is_home is True
    assert cells_by_x[0].home_marker is not None
    assert cells_by_x[1].is_home is False
    assert cells_by_x[1].home_marker is None
    assert "Home of Testland" in cells_by_x[0].title


def test_build_hex_map_points_are_a_real_six_vertex_polygon():
    state = GameState()
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))

    cell = build_hex_map(state).cells[0]

    assert len(cell.points.split(" ")) == 6


def test_build_hex_map_size_grows_with_the_boards_own_extent():
    small = GameState()
    small.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))

    large = GameState()
    for x in range(10):
        large.add_province(ProvinceState(HexCoord(x, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))

    assert build_hex_map(large).width > build_hex_map(small).width
