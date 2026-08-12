"""End-to-end validation of `bridge_new_game_state()` against `GW3__T11`
(Phase 486), continuing the real-turn coverage started at Phase 340/478-485.

`GW3__T11` reflects the state at the end of real turn 10, so it is
cross-checked against the real `SE3__T10.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, no unresolved
army records) -- pure coverage-widening confirmation. Unlike every
earlier fixture in this series, this game has lost one Hero by this
point (89, not 90), a real, letter-independent fact about the game's
own progression, not a parser defect.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T11"


def _bridge_fixture():
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)
    return bridge_new_game_state(leader_records, province_records, army_records)


def test_every_province_and_leader_bridges_with_nothing_left_unresolved():
    state, report = _bridge_fixture()

    assert report.provinces_created == 162
    assert report.kings_created == 10
    assert report.heroes_created == 89
    # Kurator is this turn's Valhalla arrival.
    assert set(report.heroes_with_synthetic_id) == {"Kurator"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_kingdom_1_holds_ngara_but_loses_chirfa_and_sherwood():
    # SE3__T10.K1's own action report narrates a mixed defensive turn: at
    # Ngara, "the provincial garrison commander's host were victorious"
    # against Samantha's first attack, and though "Samantha (#95)
    # regrouped her forces and prepared to fight for Ngara" again, the
    # real snapshot shows Kingdom 1 still holding it. By contrast, "In
    # Chirfa, Cosmic Herderer Mugai (#3) brought to bay the forces of
    # ... Samantha (#95)'s armies took control of Chirfa practically
    # uncontested" and "In Sherwood, II Kahn (#6) brought to bay ...
    # Sredna (#99)'s forces conquered Sherwood without any major
    # engagements" -- both real, uncontested losses (Sherwood itself was
    # only won at Phase 483, then lost again at Phase 484, regained by
    # neither Kingdom 1 fixture before being lost a second time here).
    state, _ = _bridge_fixture()

    ngara = state.provinces[HexCoord(5, 3)]
    assert ngara.name == "Ngara"
    assert ngara.owner_kingdom_id == 1
    assert ngara.tax == 10

    chirfa = state.provinces[HexCoord(5, 2)]
    assert chirfa.name == "Chirfa"
    assert chirfa.owner_kingdom_id == 3

    sherwood = state.provinces[HexCoord(12, 1)]
    assert sherwood.name == "Sherwood"
    assert sherwood.owner_kingdom_id == 6


def test_uga_buga_makumb_conquers_plumwood_and_stays_after_two_failed_moves():
    # SE3__T10.K1's own action report: "Uga-Buga Makumb moved into
    # Plumwood (#202) with his army" -> "Uga-Buga Makumb there
    # established our reign. Plumwood was found to have an income of 6
    # gold" (exact match) -> two separate illegal-move attempts out of
    # Plumwood both fail ("insufficient" water transport to Mare Imbrium,
    # then a non-adjacent move to the Aries Sea), leaving Plumwood as his
    # own letter's final location.
    state, _ = _bridge_fixture()

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(1, 1)

    plumwood = state.provinces[HexCoord(1, 1)]
    assert plumwood.name == "Plumwood"
    assert plumwood.owner_kingdom_id == 1
    assert plumwood.tax == 6
