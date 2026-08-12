"""End-to-end validation of `bridge_new_game_state()` against a second real,
non-T1 world file (Phase 478).

`test_gw3_t5_end_to_end.py` (Phase 340) validated `GW3__T5` against the real
`SE3__T4.K1` letter, and caught a real parser bug in the process. This module
extends the same real-data cross-check to `GW3__T5` -> `GW3__T6` -- ground
truth quoted directly from the real `SE3__T5.K1` letter for that turn (the
project's standing turn-alignment convention: `GW3__Tn` reflects the state at
the end of real turn `n-1`, so `GW3__T6` <-> `SE3__T5.Kx`). Unlike Phase 340,
this file already parses and bridges cleanly (162 provinces, 10 kingdoms, 90
heroes, no unresolved army records) -- this module is pure coverage-widening
verification, not a bugfix, and every assertion below was cross-checked
directly against `SE3__T5.K1`'s own narrated text before being written, not
merely reproduced from parser output.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T6"


def _bridge_fixture():
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)
    return bridge_new_game_state(leader_records, province_records, army_records)


def test_every_province_and_leader_bridges_with_nothing_left_unresolved():
    # Same 162-province, 10-kingdom, 90-Hero game as GW3__T1/T5 -- only the
    # turn number changed, and this file needed no parser fix to reach it.
    state, report = _bridge_fixture()

    assert report.provinces_created == 162
    assert report.kings_created == 10
    assert report.heroes_created == 90
    # Roderoch is this turn's Valhalla arrival (SE3__T5.K1's own letter:
    # "Roderoch can be given orders only for the first 3 phase(s) of the
    # turn" -- the standard Valhalla-visitor disclaimer) -- the only
    # un-rostered Hero this turn, same role Kitralus played at T5.
    assert set(report.heroes_with_synthetic_id) == {"Roderoch"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_kingdom_1_matches_uga_buga_makumbs_own_letter_salutation():
    # SE3__T5.K1's own header: "FOR SHAMAN UGA-BUGA MAKUMBU".
    state, _ = _bridge_fixture()

    kingdom1 = state.kingdoms[1]
    assert kingdom1.name == "Uga-Buga Makumb"
    assert kingdom1.race is Race.ELVEN
    assert kingdom1.alignment is Alignment.UNDEAD

    king = state.leaders[1]
    assert king.is_king is True
    assert king.race is Race.ELVEN
    assert king.alignment is Alignment.UNDEAD


def test_uga_buga_makumbs_own_three_conquests_this_turn_all_bridge_correctly():
    # SE3__T5.K1's own action report, in turn order:
    #   "Tabora was found to have an income of 10 gold."
    #   "Ngara was found to have a tax base of 10 gold."
    #   "The Moonshine Sea was conquered by Uga-Buga Makumb's forces..."
    # (the Moonshine Sea's own tax figure is never stated in the letter --
    # "inhabited by no races" is, and matches the bridged Race exactly.)
    state, _ = _bridge_fixture()

    tabora = state.provinces[HexCoord(6, 4)]
    assert tabora.name == "Tabora"
    assert tabora.owner_kingdom_id == 1
    assert tabora.tax == 10
    assert tabora.race is Race.HUMAN

    ngara = state.provinces[HexCoord(5, 3)]
    assert ngara.name == "Ngara"
    assert ngara.owner_kingdom_id == 1
    assert ngara.tax == 10
    assert ngara.race is Race.HUMAN

    moonshine_sea = state.provinces[HexCoord(6, 5)]
    assert moonshine_sea.name == "the Moonshine Sea"
    assert moonshine_sea.owner_kingdom_id == 1
    assert moonshine_sea.race is Race.NO_RACE


def test_guerin_conquers_mercia_then_bronzeleaf_and_ends_the_turn_there():
    # SE3__T5.K1's own "From: Guerin" letter: "I marched my forces into
    # Mercia (#1304)" -> "Guerin's campaign effected the conquest of
    # Mercia" -> "I marched on Bronzeleaf (#1303) with my forces" -> "An
    # army sent by the empire of ... invaded Bronzeleaf ... Bronzeleaf was
    # overrun by Guerin's forces" -- Bronzeleaf is where his own letter
    # ends ("Thy humble servant, Guerin"), so it's his final location.
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.kingdom_id == 1
    assert guerin.race is Race.ELVEN
    assert guerin.alignment is Alignment.UNDEAD
    assert guerin.location == HexCoord(12, 2)

    mercia = state.provinces[HexCoord(12, 3)]
    assert mercia.name == "Mercia"
    assert mercia.owner_kingdom_id == 1

    bronzeleaf = state.provinces[HexCoord(12, 2)]
    assert bronzeleaf.name == "Bronzeleaf"
    assert bronzeleaf.owner_kingdom_id == 1


def test_teleko_conquers_kabompo_and_ends_the_turn_in_tebessa():
    # SE3__T5.K1's own "From: Teleko" letter: "A fleet ... invaded the
    # province of Kabompo ... Kabompo was found to have a tax base of 3
    # gold" -> "With the advent of the early winter season, I flew into
    # Tebessa" (his own letter's final narrated move).
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Teleko"] == 72
    teleko = state.leaders[72]
    assert teleko.kingdom_id == 1
    assert teleko.race is Race.DWARVEN
    assert teleko.alignment is Alignment.EVIL
    assert teleko.location == HexCoord(6, 3)

    kabompo = state.provinces[HexCoord(7, 3)]
    assert kabompo.name == "Kabompo"
    assert kabompo.owner_kingdom_id == 1
    assert kabompo.tax == 3
