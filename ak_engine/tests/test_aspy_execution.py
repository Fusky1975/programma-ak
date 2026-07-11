from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.aspy_execution import SpyReport, execute_aspy

LEADER_ID = 1
HOME = HexCoord(3, 9)


def _state(*, owner_kingdom_id: int | None = 1, home_province: HexCoord = HOME, leader_location: HexCoord = HOME) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, home_province))
    state.add_province(ProvinceState(leader_location, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=owner_kingdom_id))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", leader_location))
    return state


def _request() -> SpyProvinceRequest:
    # obj is deliberately never trusted by execute_aspy -- see module
    # docstring -- so any value here should have no effect on the result.
    return SpyProvinceRequest(target_province=9999, unconfirmed_extra0=0)


def test_execute_aspy_reports_the_casters_own_province_and_owner():
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert isinstance(report, SpyReport)
    assert report.province == HOME
    assert report.owner_kingdom_id == 1


def test_execute_aspy_ignores_the_raw_target_province_field():
    state = _state(leader_location=HexCoord(5, 5), home_province=HexCoord(5, 5))
    report = execute_aspy(state, LEADER_ID, SpyProvinceRequest(target_province=1, unconfirmed_extra0=0))

    assert report.province == HexCoord(5, 5)


def test_execute_aspy_reports_none_owner_for_an_unowned_province():
    state = _state(owner_kingdom_id=None)
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.owner_kingdom_id is None
    assert report.is_capital is False


def test_execute_aspy_reports_adjacent_province_owners():
    state = _state()
    neighbor = HexCoord(4, 9)  # adjacent to (3, 9) on the odd-r grid
    state.add_province(ProvinceState(neighbor, Terrain.FOREST, Race.ELVEN, owner_kingdom_id=2))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.adjacent_owners == {neighbor: 2}


def test_execute_aspy_omits_unknown_neighboring_hexes():
    # Only (3, 9)'s own province is registered -- every neighboring hex is
    # unknown to this GameState, so adjacent_owners stays empty rather than
    # guessing.
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.adjacent_owners == {}


def test_execute_aspy_reports_recruitable_army_types_for_the_provinces_race():
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert ArmyType.BOWMEN in report.recruitable_army_types
    assert ArmyType.TROLLS not in report.recruitable_army_types  # Race.HUMAN isn't a monstrous race


def test_execute_aspy_reports_is_capital_true_at_the_kingdoms_home_province():
    state = _state(home_province=HOME, leader_location=HOME)
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.is_capital is True


def test_execute_aspy_reports_is_capital_false_away_from_home():
    state = _state(home_province=HexCoord(0, 0), leader_location=HOME)
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.is_capital is False


def test_execute_aspy_returns_none_when_the_casters_province_is_unknown():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", HOME))
    # No ProvinceState registered at HOME.

    assert execute_aspy(state, LEADER_ID, _request()) is None
