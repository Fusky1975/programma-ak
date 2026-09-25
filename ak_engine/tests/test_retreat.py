from __future__ import annotations

from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.retreat import (
    attacker_retreat_candidates,
    find_retreat_destination,
)

BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def test_find_retreat_destination_returns_a_friendly_neighbor():
    origin = HexCoord(5, 5)
    friendly_neighbor = neighbors(origin, BOUNDS)[0]
    destination = find_retreat_destination(origin, BOUNDS, {friendly_neighbor})
    assert destination == friendly_neighbor


def test_find_retreat_destination_none_when_no_friendly_neighbor():
    origin = HexCoord(5, 5)
    assert find_retreat_destination(origin, BOUNDS, set()) is None


def test_attacker_retreat_candidates_includes_origin_and_neighbors():
    invaded_from = HexCoord(5, 5)
    candidates = attacker_retreat_candidates(invaded_from, BOUNDS)
    assert invaded_from in candidates
    assert set(neighbors(invaded_from, BOUNDS)).issubset(set(candidates))
