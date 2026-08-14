from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.defend_execution import (
    DEFAULT_DEFEND_RADIUS,
    LONG_NAVAL_DEFEND_RADIUS,
    defend_coverage_area,
    defend_radius_for_leader,
)
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, hex_distance, neighbors

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


# -- Phase 524: AdvancedAbility.NAVAL_LONG_DEFEND widens the radius --


def _state_with_leader(*, has_ability: bool, army_type: ArmyType | None) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(5, 5)))
    leader = LeaderState(1, 1, "Admiral", HexCoord(5, 5))
    if has_ability:
        leader.advanced_abilities.add(AdvancedAbility.NAVAL_LONG_DEFEND)
    state.add_leader(leader)
    if army_type is not None:
        state.add_army(ArmyState(1, 1, army_type, Quality.AVERAGE, HexCoord(5, 5), commanded_by=1))
    return state


def test_defend_radius_for_leader_is_default_without_the_ability():
    state = _state_with_leader(has_ability=False, army_type=ArmyType.FLEET)

    assert defend_radius_for_leader(state, 1) == DEFAULT_DEFEND_RADIUS


def test_defend_radius_for_leader_is_default_with_the_ability_but_no_sea_army():
    state = _state_with_leader(has_ability=True, army_type=ArmyType.BOWMEN)

    assert defend_radius_for_leader(state, 1) == DEFAULT_DEFEND_RADIUS


def test_defend_radius_for_leader_is_long_naval_with_ability_and_a_sea_army():
    state = _state_with_leader(has_ability=True, army_type=ArmyType.FLEET)

    assert defend_radius_for_leader(state, 1) == LONG_NAVAL_DEFEND_RADIUS


def test_defend_radius_for_leader_recognizes_whales_and_mermen_too():
    for army_type in (ArmyType.WHALES, ArmyType.MERMEN):
        state = _state_with_leader(has_ability=True, army_type=army_type)
        assert defend_radius_for_leader(state, 1) == LONG_NAVAL_DEFEND_RADIUS


def test_defend_coverage_area_radius_1_matches_neighbors():
    location = HexCoord(5, 5)

    assert defend_coverage_area(location, BOUNDS, radius=1) == set(neighbors(location, BOUNDS))


def test_defend_coverage_area_radius_2_is_a_strict_superset_reaching_two_hexes_out():
    location = HexCoord(5, 5)

    radius_1 = defend_coverage_area(location, BOUNDS, radius=1)
    radius_2 = defend_coverage_area(location, BOUNDS, radius=LONG_NAVAL_DEFEND_RADIUS)

    assert radius_1 < radius_2
    assert all(hex_distance(location, c) <= 2 for c in radius_2)
    assert any(hex_distance(location, c) == 2 for c in radius_2)
    assert location not in radius_2
