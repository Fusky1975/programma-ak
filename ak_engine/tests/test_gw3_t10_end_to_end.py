"""End-to-end validation of `bridge_new_game_state()` against `GW3__T10`
(Phase 485), continuing the real-turn coverage started at Phase 340/478-484.

`GW3__T10` reflects the state at the end of real turn 9, so it is
cross-checked against the real `SE3__T9.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, 90 heroes, no
unresolved army records) -- pure coverage-widening confirmation.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T10"


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
    # Sredna is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Sredna"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_kingdom_6_takes_bir_nzaran_and_ravenwood_from_kingdom_1():
    # SE3__T9.K1's own action report: "II Kahn (#6)'s forces initiated a
    # campaign of conquest directed at Bir Nzaran ... Bir Nzaran was
    # overrun by Kahn's forces in a bloody campaign" and, separately,
    # "II Kahn (#6)'s forces initiated a campaign of conquest in
    # Ravenwood ... Kahn's forces conquered Ravenwood without any major
    # engagements" -- two real, uncontested-and-contested losses in the
    # same turn, both to Kingdom 6 (matching Kahn's earlier Bronzeleaf/
    # Peachwood conquests at Phase 483/484).
    state, _ = _bridge_fixture()

    bir_nzaran = state.provinces[HexCoord(11, 2)]
    assert bir_nzaran.name == "Bir Nzaran"
    assert bir_nzaran.owner_kingdom_id == 6
    assert bir_nzaran.tax == 5

    ravenwood = state.provinces[HexCoord(10, 1)]
    assert ravenwood.name == "Ravenwood"
    assert ravenwood.owner_kingdom_id == 6


def test_uga_buga_makumb_conquers_st_helens_then_belladonna_and_ends_there():
    # SE3__T9.K1's own action report: "Uga-Buga Makumb boldly marched his
    # forces into St Helens (#402)" -> "St Helens was overrun by
    # Uga-Buga Makumb's host. St Helens was found to have an income of 4
    # gold" (exact match) -> "Uga-Buga Makumb moved into Belladonna
    # (#302)" -> "Belladonna was overrun by the forces of Uga-Buga
    # Makumb" -> his own later illegal move (Belladonna to Plumwood,
    # "further than his army could move") fails, so Belladonna remains
    # his own letter's final location.
    state, _ = _bridge_fixture()

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(2, 1)

    st_helens = state.provinces[HexCoord(3, 1)]
    assert st_helens.name == "St Helens"
    assert st_helens.owner_kingdom_id == 1
    assert st_helens.tax == 4

    belladonna = state.provinces[HexCoord(2, 1)]
    assert belladonna.name == "Belladonna"
    assert belladonna.owner_kingdom_id == 1
