from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.aspy_execution import SpottedCharacter, SpyReport, execute_aspy

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


# --- Phase 139: spotted_characters (Align_Est/Temper_Est consumer) ---


def test_execute_aspy_omits_the_caster_itself_from_spotted_characters():
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.spotted_characters == []


def test_execute_aspy_spots_a_co_located_leader():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Rival", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request())

    assert len(report.spotted_characters) == 1
    spotted = report.spotted_characters[0]
    assert isinstance(spotted, SpottedCharacter)
    assert spotted.leader_id == 2
    assert spotted.name == "Rival"


def test_execute_aspy_does_not_spot_leaders_in_other_provinces():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Elsewhere", HexCoord(0, 0), temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.spotted_characters == []


def test_execute_aspy_reports_true_alignment_and_temper_for_a_psychic_mage_caster():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Rival", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request(), caster_holds_psychic_mage_office=True)

    spotted = report.spotted_characters[0]
    assert spotted.estimated_alignment == Alignment.GOOD  # Testia's own KingdomState.alignment
    assert spotted.estimated_temper == Temper.BRAVE


def test_execute_aspy_detect_align_talent_perfects_alignment_only():
    state = _state()
    # Caster's own birth_x=3 (odd parity) vs spotted leader_id=2 (even
    # parity) forces a real nudge in estimate_temper() -- proving
    # caster_has_detect_align alone grants the perfect *alignment* path
    # without also perfecting temper (the real Pascal source gives temper
    # detection no advanced-ability bypass at all; see
    # turn/intelligence_estimate.py's _nudge()).
    state.leaders[LEADER_ID].birth_x = 3
    state.add_leader(LeaderState(2, 1, "Rival", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_detect_align=True)

    spotted = report.spotted_characters[0]
    assert spotted.estimated_alignment == Alignment.GOOD
    assert spotted.estimated_temper == Temper.CAUTIOUS  # BRAVE nudged down one step


def test_execute_aspy_estimates_alignment_imperfectly_by_default():
    state = _state()
    # Testia's alignment is GOOD (ordinal 1). spotted.leader_id=2 (even
    # parity) vs caster LEADER_ID=1 (odd parity) nudges the ordinal down
    # by one to DIVINE (ordinal 0) per turn/intelligence_estimate.py's
    # _nudge() formula.
    state.add_leader(LeaderState(2, 1, "Rival", HOME))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.spotted_characters[0].estimated_alignment == Alignment.DIVINE


def test_execute_aspy_reports_none_alignment_for_an_independent_hero():
    state = _state()
    state.add_leader(LeaderState(2, None, "Wandering Hero", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request(), caster_holds_psychic_mage_office=True)

    spotted = report.spotted_characters[0]
    assert spotted.estimated_alignment is None
    assert spotted.estimated_temper == Temper.BRAVE


def test_execute_aspy_reports_none_temper_when_not_recorded():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Rival", HOME))  # temper defaults to None

    report = execute_aspy(state, LEADER_ID, _request(), caster_holds_psychic_mage_office=True)

    assert report.spotted_characters[0].estimated_temper is None
