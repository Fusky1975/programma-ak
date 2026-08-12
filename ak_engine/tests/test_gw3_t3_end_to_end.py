"""End-to-end validation of `bridge_new_game_state()` against `GW3__T3`
(Phase 480), continuing the real-turn coverage started at Phase 340/478/479.

`GW3__T3` reflects the state at the end of real turn 2, so it is
cross-checked against the real `SE3__T2.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, 90 heroes, no
unresolved army records) -- pure coverage-widening confirmation.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T3"


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
    # Quintilian is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Quintilian"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_uga_buga_makumb_charms_melantheus_and_ends_the_turn_at_the_mermaid_sea():
    # SE3__T2.K1's own action report: "Uga-Buga Makumb travelled to the
    # Virgo Sea" -> "Melantheus was magically charmed by Uga-Buga Makumb
    # ... Melantheus changed to Undead alignment!" -> "Uga-Buga Makumb
    # rode into the Mermaid Sea" -> "failed in his attempt to cast a
    # Charm spell" (his own letter's final narrated event, no further
    # move) -- and Teleko's own letter confirms "The Mermaid Sea was
    # overrun by the forces of Teleko."
    state, _ = _bridge_fixture()

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(8, 5)

    mermaid_sea = state.provinces[HexCoord(8, 5)]
    assert mermaid_sea.name == "the Mermaid Sea"
    assert mermaid_sea.owner_kingdom_id == 1

    virgo_sea = state.provinces[HexCoord(9, 4)]
    assert virgo_sea.owner_kingdom_id == 1

    # Charmed onto Uga-Buga Makumb's own side, alignment flipped to
    # Undead exactly as narrated.
    melantheus = state.leaders[30]
    assert melantheus.name == "Melantheus"
    assert melantheus.kingdom_id == 1
    assert melantheus.alignment is Alignment.UNDEAD
    assert melantheus.race is Race.ELVEN


def test_guerin_conquers_falkenheim_then_mare_tarkium_and_ends_the_turn_there():
    # SE3__T2.K1's own "From: Guerin" letter: "I marched on Falkenheim
    # (#1106)" -> "Guerin's campaign effected the conquest of Falkenheim"
    # -> "I moved into Mare Tarkium (#1107)" -> "Guerin's host concluded
    # the campaign successfully and conquered Mare Tarkium" (his own
    # letter's final narrated event, so Mare Tarkium is his location).
    # The same letter also has Guerin personally judge Tao-Li (a Dwarf
    # who pledged allegiance this turn) as "Evil, Brave".
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.kingdom_id == 1
    assert guerin.location == HexCoord(10, 6)

    falkenheim = state.provinces[HexCoord(10, 5)]
    assert falkenheim.name == "Falkenheim"
    assert falkenheim.owner_kingdom_id == 1

    mare_tarkium = state.provinces[HexCoord(10, 6)]
    assert mare_tarkium.name == "Mare Tarkium"
    assert mare_tarkium.owner_kingdom_id == 1

    tao_li = state.leaders[32]
    assert tao_li.name == "Tao-Li"
    assert tao_li.kingdom_id == 1
    assert tao_li.race is Race.DWARVEN
    assert tao_li.alignment is Alignment.EVIL
    assert tao_li.temper is Temper.BRAVE
