from __future__ import annotations

from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.retreat import (
    attacker_retreat_candidates,
    find_retreat_destination,
    select_attacker_retreat_destination,
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


def test_select_attacker_retreat_destination_prefers_the_origin_when_friendly():
    invaded_from = HexCoord(5, 5)
    battlefield = neighbors(invaded_from, BOUNDS)[0]
    friendly = {invaded_from, *neighbors(invaded_from, BOUNDS)}
    destination = select_attacker_retreat_destination(invaded_from, battlefield, BOUNDS, friendly)
    assert destination == invaded_from


def test_select_attacker_retreat_destination_falls_back_to_a_friendly_neighbor_if_the_origin_was_captured():
    # Phase 912: a third Kingdom could have captured the origin province
    # earlier the same turn -- "retreating" there would hand the army
    # straight to an enemy, so it must not be picked once it's no longer
    # friendly.
    invaded_from = HexCoord(5, 5)
    battlefield = neighbors(invaded_from, BOUNDS)[0]
    friendly_neighbor_of_origin = neighbors(invaded_from, BOUNDS)[1]
    friendly = {friendly_neighbor_of_origin}
    destination = select_attacker_retreat_destination(invaded_from, battlefield, BOUNDS, friendly)
    assert destination == friendly_neighbor_of_origin


def test_select_attacker_retreat_destination_never_picks_the_battlefield_itself():
    # invaded_from and the battlefield are adjacent by definition (the
    # army marched from one to the other), so the battlefield is always
    # structurally present in attacker_retreat_candidates(invaded_from,
    # ...)'s own neighbor list -- it must never be treated as a valid
    # "friendly" retreat destination even if the caller's own friendly
    # set still (wrongly) included it.
    invaded_from = HexCoord(5, 5)
    battlefield = neighbors(invaded_from, BOUNDS)[0]
    friendly = {battlefield}  # deliberately excludes invaded_from itself
    destination = select_attacker_retreat_destination(invaded_from, battlefield, BOUNDS, friendly)
    assert destination is None


def test_select_attacker_retreat_destination_falls_back_to_find_retreat_destination():
    # None of the origin-or-adjacent candidates are friendly, but a
    # friendly province exists adjacent to the battlefield itself --
    # the same general nearest-friendly-neighbor logic the
    # attacker_origin-is-None branch already uses.
    invaded_from = HexCoord(5, 5)
    battlefield = HexCoord(9, 9)
    friendly_neighbor_of_battlefield = neighbors(battlefield, BOUNDS)[0]
    friendly = {friendly_neighbor_of_battlefield}
    destination = select_attacker_retreat_destination(invaded_from, battlefield, BOUNDS, friendly)
    assert destination == friendly_neighbor_of_battlefield


def test_select_attacker_retreat_destination_none_when_nothing_is_friendly():
    invaded_from = HexCoord(5, 5)
    battlefield = neighbors(invaded_from, BOUNDS)[0]
    destination = select_attacker_retreat_destination(invaded_from, battlefield, BOUNDS, set())
    assert destination is None
