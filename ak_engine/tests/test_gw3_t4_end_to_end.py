"""End-to-end validation of `bridge_new_game_state()` against `GW3__T4`
(Phase 481), continuing the real-turn coverage started at Phase 340/478-480.

`GW3__T4` reflects the state at the end of real turn 3, so it is
cross-checked against the real `SE3__T3.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, 90 heroes, no
unresolved army records) -- pure coverage-widening confirmation.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T4"


def _bridge_fixture():
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)
    return bridge_new_game_state(leader_records, province_records, army_records)


def test_every_province_and_leader_bridges_with_nothing_left_unresolved():
    state, report = _bridge_fixture()

    assert report.provinces_created == 162
    assert report.kings_created == 10
    assert report.heroes_created == 90
    # Bo is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Bo"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_uga_buga_makumb_charms_three_more_heroes_and_ends_at_mare_tarkium():
    # SE3__T3.K1's own action report: "Lallipugh was magically charmed
    # ... Lallipugh changed to Undead alignment!"; "Odysseus was
    # magically charmed ... Odysseus changed to Undead alignment!";
    # "Amalric was magically charmed ... Amalric changed to Evil
    # alignment!" -- three real Charm conversions in one turn, two to
    # Undead and (notably) one to Evil, not the same target alignment
    # every time. "Uga-Buga Makumb travelled to Mare Tarkium" is his own
    # letter's final narrated move.
    state, _ = _bridge_fixture()

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(10, 6)

    lallipugh = state.leaders[11]
    assert lallipugh.name == "Lallipugh"
    assert lallipugh.kingdom_id == 1
    assert lallipugh.alignment is Alignment.UNDEAD
    assert lallipugh.race is Race.ELVEN

    odysseus = state.leaders[97]
    assert odysseus.name == "Odysseus"
    assert odysseus.kingdom_id == 1
    assert odysseus.alignment is Alignment.UNDEAD

    amalric = state.leaders[29]
    assert amalric.name == "Amalric"
    assert amalric.kingdom_id == 1
    assert amalric.alignment is Alignment.EVIL


def test_guerin_conquers_hollabrand_and_ends_the_turn_there():
    # SE3__T3.K1's own "From: Montgomery, Squire to Guerin" letter:
    # "Guerin marched on Hollabrand (#1206)" -> "Guerin's host ended the
    # campaign successfully and conquered the province of Hollabrand"
    # (his own letter's final narrated event).
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.kingdom_id == 1
    assert guerin.location == HexCoord(11, 5)

    hollabrand = state.provinces[HexCoord(11, 5)]
    assert hollabrand.name == "Hollabrand"
    assert hollabrand.owner_kingdom_id == 1


def test_teleko_conquers_the_icaria_sea_then_the_near_beer_sea_and_ends_there():
    # SE3__T3.K1's own "From: Gunga Din, Squire to Teleko" letter: "Teleko
    # moved into the Icaria Sea (#1007)" -> "The Icaria Sea was overrun by
    # the forces of Teleko" -> "Teleko moved into the Near-Beer Sea
    # (#907)" -> "The Near-Beer Sea was overrun by Teleko's men in a
    # bloody campaign" (his own letter's final narrated event).
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Teleko"] == 72
    teleko = state.leaders[72]
    assert teleko.kingdom_id == 1
    assert teleko.location == HexCoord(8, 6)

    icaria_sea = state.provinces[HexCoord(9, 6)]
    assert icaria_sea.name == "the Icaria Sea"
    assert icaria_sea.owner_kingdom_id == 1

    near_beer_sea = state.provinces[HexCoord(8, 6)]
    assert near_beer_sea.name == "the Near-Beer Sea"
    assert near_beer_sea.owner_kingdom_id == 1
