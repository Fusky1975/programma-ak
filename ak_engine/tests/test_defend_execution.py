from __future__ import annotations

from ak_engine.models.map import HexCoord
from ak_engine.turn.defend_execution import defend_coverage_area
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors

BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def test_defend_coverage_area_is_the_leaders_own_neighbors():
    location = HexCoord(5, 5)

    coverage = defend_coverage_area(location, BOUNDS)

    assert coverage == set(neighbors(location, BOUNDS))


def test_defend_coverage_area_does_not_include_the_leaders_own_province():
    location = HexCoord(5, 5)

    coverage = defend_coverage_area(location, BOUNDS)

    assert location not in coverage


def test_defend_coverage_area_is_bounds_filtered_at_the_map_edge():
    location = HexCoord(0, 0)

    coverage = defend_coverage_area(location, BOUNDS)

    assert all(BOUNDS.contains(c) for c in coverage)
    assert len(coverage) < 6
