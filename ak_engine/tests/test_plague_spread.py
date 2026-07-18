"""Tests for turn/plague_spread.py -- see its module docstring for the
rulebook [4.25.3] spread rule this implements (Phase 233).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.plague_spread import resolve_plague_spread

from _helpers import ScriptedRandom

BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)
HOME = HexCoord(5, 5)
N1 = neighbors(HOME, BOUNDS)[0]
C = next(coord for coord in neighbors(N1, BOUNDS) if coord != HOME)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, plague_active=True))
    state.add_province(ProvinceState(N1, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    return state


def test_resolve_plague_spread_infects_an_adjacent_province_on_a_hit():
    state = make_state()
    rng = ScriptedRandom([0.01])  # hits the 15% spread chance; N1 has no armies to expose

    newly_infected = resolve_plague_spread(state, rng, BOUNDS)

    assert newly_infected == [N1]
    assert state.provinces[N1].plague_active is True


def test_resolve_plague_spread_skips_on_a_miss():
    state = make_state()
    rng = ScriptedRandom([0.99])  # misses the 15% spread chance

    newly_infected = resolve_plague_spread(state, rng, BOUNDS)

    assert newly_infected == []
    assert state.provinces[N1].plague_active is False


def test_resolve_plague_spread_does_not_reinfect_an_already_active_province():
    state = make_state()
    state.provinces[N1].plague_active = True
    rng = ScriptedRandom([])  # already-active neighbor is skipped before any roll

    newly_infected = resolve_plague_spread(state, rng, BOUNDS)

    assert newly_infected == []


def test_resolve_plague_spread_does_not_cascade_within_the_same_call():
    state = make_state()
    state.add_province(ProvinceState(C, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    rng = ScriptedRandom([0.01, 0.01])  # HOME->N1 hits; N1's own neighbors (incl. C) would hit too, if visited

    newly_infected = resolve_plague_spread(state, rng, BOUNDS)

    assert newly_infected == [N1]
    assert state.provinces[C].plague_active is False


def test_resolve_plague_spread_applies_exposure_to_newly_infected_armies():
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, N1))
    rng = ScriptedRandom([0.01, 0.01])  # [0] spread hits, [1] destroy-chance roll (base 10%) hits

    resolve_plague_spread(state, rng, BOUNDS)

    assert 1 not in state.armies


def test_resolve_plague_spread_returns_empty_list_with_no_active_provinces():
    state = make_state()
    state.provinces[HOME].plague_active = False
    rng = ScriptedRandom([])

    newly_infected = resolve_plague_spread(state, rng, BOUNDS)

    assert newly_infected == []
