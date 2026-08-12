"""End-to-end validation of `bridge_new_game_state()` against `GW3__T8`
(Phase 483), continuing the real-turn coverage started at Phase 340/478-482.

`GW3__T8` reflects the state at the end of real turn 7, so it is
cross-checked against the real `SE3__T7.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, 90 heroes, no
unresolved army records) -- pure coverage-widening confirmation.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T8"


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
    # Ambrosius is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Ambrosius"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_uga_buga_makumb_loses_kabompo_and_the_amazonian_sea_to_kingdom_3():
    # SE3__T7.K1's own action report: "A fleet coming from the empire of
    # Lady of Beer Mbaba (#3) entered Kabompo, hoping to subjugate that
    # province ruled by Shaman Uga-Buga Makumb ... Samantha (#95)'s naval
    # forces took control of Kabompo practically uncontested"; "Ships
    # bearing the battle-standards of the Mbaba (#3)ian empire cruised
    # into ... the Amazonian Sea, a land defended by the forces of Shaman
    # Uga-Buga Makumb ... Samantha (#95)'s naval forces took control of
    # the Amazonian Sea practically uncontested." Both are genuine
    # territorial LOSSES for Kingdom 1 this turn (not the usual
    # conquest-report direction this project's own fixtures have
    # exercised so far), letter-confirmed against the real snapshot: both
    # provinces now belong to Kingdom 3.
    state, _ = _bridge_fixture()

    kabompo = state.provinces[HexCoord(7, 3)]
    assert kabompo.name == "Kabompo"
    assert kabompo.owner_kingdom_id == 3

    amazonian_sea = state.provinces[HexCoord(8, 4)]
    assert amazonian_sea.name == "the Amazonian Sea"
    assert amazonian_sea.owner_kingdom_id == 3


def test_guerin_conquers_peachwood_then_sherwood_and_ends_the_turn_there():
    # SE3__T7.K1's own "From: Guerin" letter: "I marched on Peachwood
    # (#1202)" -> "Guerin's campaign accomplished the conquest of
    # Peachwood" -> "I marched on Sherwood (#1302)" -> a real King-vs-
    # King's-champion battle against Kahn himself, resolving in Guerin's
    # favor per the real snapshot (Sherwood now Kingdom 1's own, Guerin's
    # own final location).
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.kingdom_id == 1
    assert guerin.location == HexCoord(12, 1)

    peachwood = state.provinces[HexCoord(11, 1)]
    assert peachwood.name == "Peachwood"
    assert peachwood.owner_kingdom_id == 1

    sherwood = state.provinces[HexCoord(12, 1)]
    assert sherwood.name == "Sherwood"
    assert sherwood.owner_kingdom_id == 1
