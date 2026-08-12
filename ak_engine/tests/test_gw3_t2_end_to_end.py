"""End-to-end validation of `bridge_new_game_state()` against `GW3__T2`
(Phase 479), continuing the real-turn coverage started at Phase 340/478.

`GW3__T2` reflects the state at the end of real turn 1, so it is
cross-checked against the real `SE3__T1.K1` letter (`Esempi turni/`).
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

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T2"


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
    # Kelderek is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Kelderek"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_uga_buga_makumb_conquers_virgo_sea_then_the_jellyfish_sea():
    # SE3__T1.K1's own action report: "Uga-Buga Makumb marched on the
    # Virgo Sea (#1005) with his formidable forces" -> "Uga-Buga Makumb's
    # host concluded the campaign successfully and conquered the province
    # of the Virgo Sea" -> "Uga-Buga Makumb marched on the Jellyfish Sea
    # (#1105) with his forces" -> "The Jellyfish Sea was overrun by
    # Uga-Buga Makumb's men in a hard-fought campaign" -> "Thus endeth the
    # adventures of Shaman Uga-Buga Makumb ... for this year" (his own
    # letter ends there, so the Jellyfish Sea is his final location).
    state, _ = _bridge_fixture()

    kingdom1 = state.kingdoms[1]
    assert kingdom1.name == "Uga-Buga Makumb"
    assert kingdom1.race is Race.ELVEN
    assert kingdom1.alignment is Alignment.UNDEAD

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(10, 4)

    virgo_sea = state.provinces[HexCoord(9, 4)]
    assert virgo_sea.name == "the Virgo Sea"
    assert virgo_sea.owner_kingdom_id == 1

    jellyfish_sea = state.provinces[HexCoord(10, 4)]
    assert jellyfish_sea.name == "the Jellyfish Sea"
    assert jellyfish_sea.owner_kingdom_id == 1


def test_guerin_and_teleko_both_stay_home_in_the_dolphin_sea():
    # SE3__T1.K1's own "From: Montgomery, Squire to Guerin" and "From:
    # Teleko" letters: neither narrates a move this turn -- Guerin
    # "dropped off" armies "in the Dolphin Sea", Teleko "levied" and
    # "hired" armies "in the Dolphin Sea" -- both stay at the Kingdom's
    # own home province (#1006, per SE3__T0.K1's own CHARACTERS table).
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.kingdom_id == 1
    assert guerin.location == HexCoord(9, 5)

    assert report.heroes_with_confirmed_id["Teleko"] == 72
    teleko = state.leaders[72]
    assert teleko.kingdom_id == 1
    assert teleko.race is Race.DWARVEN
    assert teleko.alignment is Alignment.EVIL
    assert teleko.location == HexCoord(9, 5)

    dolphin_sea = state.provinces[HexCoord(9, 5)]
    assert dolphin_sea.name == "the Dolphin Sea"
    assert dolphin_sea.owner_kingdom_id == 1
