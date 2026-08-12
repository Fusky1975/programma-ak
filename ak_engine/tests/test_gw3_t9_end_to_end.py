"""End-to-end validation of `bridge_new_game_state()` against `GW3__T9`
(Phase 484), continuing the real-turn coverage started at Phase 340/478-483.

`GW3__T9` reflects the state at the end of real turn 8, so it is
cross-checked against the real `SE3__T8.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, 90 heroes, no
unresolved army records) -- pure coverage-widening confirmation.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T9"


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
    # Lancelot is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Lancelot"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_the_buccaneer_sea_is_defended_but_bronzeleaf_and_peachwood_are_lost():
    # SE3__T8.K1's own action report narrates a mixed defensive turn for
    # Kingdom 1: "The defenders defeated Samantha's forces and drove them
    # out of the Buccaneer Sea" (held), but "Kahn's host concluded the
    # campaign successfully and conquered the province of Bronzeleaf"
    # (lost, after an initial defensive win forced a rebattle Kahn then
    # won) and "Hawkins (#56)'s forces experienced little resistance in
    # Peachwood and Hawkins there established our reign" (lost outright,
    # uncontested) -- both provinces this project's own earlier fixtures
    # (Phase 480/483) had shown Kingdom 1 winning in previous turns.
    state, _ = _bridge_fixture()

    buccaneer_sea = state.provinces[HexCoord(7, 5)]
    assert buccaneer_sea.name == "the Buccaneer Sea"
    assert buccaneer_sea.owner_kingdom_id == 1

    bronzeleaf = state.provinces[HexCoord(12, 2)]
    assert bronzeleaf.name == "Bronzeleaf"
    assert bronzeleaf.owner_kingdom_id == 6

    peachwood = state.provinces[HexCoord(11, 1)]
    assert peachwood.name == "Peachwood"
    assert peachwood.owner_kingdom_id == 6


def test_uga_buga_makumb_conquers_balmwood_then_silvermist_and_ends_there():
    # SE3__T8.K1's own action report: "Uga-Buga Makumb's armies took
    # possession of Balmwood practically uncontested. Balmwood was found
    # to have a tax base of 4 gold" (exact match) -> "Uga-Buga Makumb
    # rode his flying armies into Silvermist" -> "Uga-Buga Makumb there
    # established our rule. Silvermist was discovered to have an income
    # of 6 gold" (exact match, his own letter's final narrated event).
    state, _ = _bridge_fixture()

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(4, 1)

    balmwood = state.provinces[HexCoord(4, 2)]
    assert balmwood.name == "Balmwood"
    assert balmwood.owner_kingdom_id == 1
    assert balmwood.tax == 4

    silvermist = state.provinces[HexCoord(4, 1)]
    assert silvermist.name == "Silvermist"
    assert silvermist.owner_kingdom_id == 1
    assert silvermist.tax == 6
