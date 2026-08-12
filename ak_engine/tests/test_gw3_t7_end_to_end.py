"""End-to-end validation of `bridge_new_game_state()` against `GW3__T7`
(Phase 482), continuing the real-turn coverage started at Phase 340/478-481.

`GW3__T7` reflects the state at the end of real turn 6, so it is
cross-checked against the real `SE3__T6.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, 90 heroes, no
unresolved army records) -- pure coverage-widening confirmation.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T7"


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
    # Nixie is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Nixie"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_uga_buga_makumb_charms_two_more_heroes_and_conquers_chaco():
    # SE3__T6.K1's own action report: "Pascal was magically charmed ...
    # Pascal changed to Pagan alignment!"; "Constantine was magically
    # charmed ... Constantine changed to Undead alignment!"; "Uga-Buga
    # Makumb flew into Chaco" -> won a King's-champion Duel against
    # Hokuto (King #4) via a Gate Demon summon, then "Uga-Buga Makumb's
    # campaign effected the conquest of Chaco" (his own letter's final
    # narrated event, so Chaco is his location). Jerbilia was conquered
    # earlier the same turn: "Jerbilia was discovered to have an income
    # of 3 gold" -- matches exactly.
    state, _ = _bridge_fixture()

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(4, 3)

    chaco = state.provinces[HexCoord(4, 3)]
    assert chaco.name == "Chaco"
    assert chaco.owner_kingdom_id == 1

    jerbilia = state.provinces[HexCoord(5, 4)]
    assert jerbilia.name == "Jerbilia"
    assert jerbilia.owner_kingdom_id == 1
    assert jerbilia.tax == 3

    pascal = state.leaders[78]
    assert pascal.name == "Pascal"
    assert pascal.kingdom_id == 1
    assert pascal.alignment is Alignment.PAGAN

    constantine = state.leaders[49]
    assert constantine.name == "Constantine"
    assert constantine.kingdom_id == 1
    assert constantine.alignment is Alignment.UNDEAD


def test_guerin_conquers_bir_nzaran_and_stays_after_a_failed_further_move():
    # SE3__T6.K1's own "From: Guerin" letter: "I moved into Bir Nzaran
    # (#1203)" -> "Guerin's well-planned campaign accomplished the
    # conquest of Bir Nzaran" -> "I tried to move from Bir Nzaran to
    # Peachwood, but provincial flooding and insufficient transport
    # thwarted the move" -- the illegal/failed move leaves him at Bir
    # Nzaran, his own letter's final location.
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.kingdom_id == 1
    assert guerin.location == HexCoord(11, 2)

    bir_nzaran = state.provinces[HexCoord(11, 2)]
    assert bir_nzaran.name == "Bir Nzaran"
    assert bir_nzaran.owner_kingdom_id == 1


def test_teleko_conquers_gafsa_then_loses_at_limerick_but_stays_to_contest_it():
    # SE3__T6.K1's own "From: Gunga Din, Squire to Teleko" letter:
    # "Gafsa was overrun by Teleko's host. Gafsa was discovered to have
    # a tax base of 2 gold" (exact match) -> "Teleko rode his flying
    # armies into Limerick" -> Teleko personally duels and kills Kwoth
    # (King #3) in single combat, but the battle itself goes the other
    # way: "Circe's great horde overwhelmed the army of Uga-Buga Makumb
    # and took the field" -> "Though Circe's forces were triumphant,
    # Teleko rallied his men and decided to contest Limerick" -- a real,
    # letter-documented case of the *attacker* losing a battle yet
    # staying to force a rebattle, rather than retreating. Limerick
    # itself is therefore still Kingdom 3's own, not Kingdom 1's, and
    # Teleko's own location stays Limerick (he didn't retreat).
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Teleko"] == 72
    teleko = state.leaders[72]
    assert teleko.kingdom_id == 1
    assert teleko.location == HexCoord(6, 2)

    gafsa = state.provinces[HexCoord(7, 2)]
    assert gafsa.name == "Gafsa"
    assert gafsa.owner_kingdom_id == 1
    assert gafsa.tax == 2

    limerick = state.provinces[HexCoord(6, 2)]
    assert limerick.name == "Limerick"
    assert limerick.owner_kingdom_id == 3
