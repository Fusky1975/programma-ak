from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.retreat import (
    attacker_retreat_candidates,
    find_retreat_destination,
    resolve_retreat,
)

BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def unit(army_type: ArmyType = ArmyType.BOWMEN, strength: float = 10) -> BattleUnit:
    return BattleUnit(army_type=army_type, effective_strength=strength)


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


def test_resolve_retreat_moves_units_when_destination_exists():
    origin = HexCoord(5, 5)
    friendly_neighbor = neighbors(origin, BOUNDS)[0]
    units = [(unit(), Quality.AVERAGE)]

    result = resolve_retreat(units, origin, BOUNDS, {friendly_neighbor})

    assert result.destination == friendly_neighbor
    assert len(result.retreating_units) == 1
    assert result.disbanded_units == []
    assert result.mercenary_units == []


def test_resolve_retreat_disbands_green_and_depleted_when_impossible():
    origin = HexCoord(5, 5)
    green_unit = unit(strength=1)
    depleted_unit = unit(strength=2)
    average_unit = unit(strength=3)
    units = [(green_unit, Quality.GREEN), (depleted_unit, Quality.DEPLETED), (average_unit, Quality.AVERAGE)]

    result = resolve_retreat(units, origin, BOUNDS, set())

    assert result.destination is None
    assert result.disbanded_units == [green_unit, depleted_unit]
    assert result.mercenary_units == [average_unit]
