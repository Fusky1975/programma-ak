"""End-to-end validation of `bridge_new_game_state()` against `GW3__T12`
(Phase 487), completing the real-turn coverage started at Phase 340/478-486
across every GW3 snapshot in the user's own archive (`GW3__T1`-`T12`).

`GW3__T12` reflects the state at the end of real turn 11, so it is
cross-checked against the real `SE3__T11.K1` letter (`Esempi turni/`).
Parses and bridges cleanly (162 provinces, 10 kingdoms, no unresolved
army records) -- pure coverage-widening confirmation.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T12"


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
    # Two-Headed_Eagl is this turn's Valhalla arrival (the real GW record
    # truncates his own name -- "Two-Headed Eagle" -- to fit its field
    # width, exactly like every other name field this project's own
    # parser reads verbatim rather than reformatting).
    assert set(report.heroes_with_synthetic_id) == {"Two-Headed_Eagl"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_kingdom_1_defends_ngara_and_the_jellyfish_sea_but_loses_maplehaven_and_sageleaf():
    # SE3__T11.K1's own action report: a third Samantha attack on Ngara
    # is beaten back ("Samantha (#95)'s armies were defeated and pushed
    # out of Ngara"), and Kahn's own attack on the Jellyfish Sea also
    # fails ("Kahn's armies were defeated and pushed out of the
    # Jellyfish Sea") -- both provinces held. But "Giovanna (#7) ordered
    # an invasion force into ... Maplehaven ... Rolando (#55)'s forces
    # took Maplehaven without any major battles" and, separately,
    # "Giovanna (#7)'s forces initiated a campaign of conquest in
    # Sageleaf ... Hakim (#79)'s forces experienced little resistance in
    # Sageleaf" -- two real, uncontested losses to Kingdom 7 this same
    # turn.
    state, _ = _bridge_fixture()

    ngara = state.provinces[HexCoord(5, 3)]
    assert ngara.owner_kingdom_id == 1

    jellyfish_sea = state.provinces[HexCoord(10, 4)]
    assert jellyfish_sea.owner_kingdom_id == 1

    maplehaven = state.provinces[HexCoord(14, 1)]
    assert maplehaven.name == "Maplehaven"
    assert maplehaven.owner_kingdom_id == 7

    sageleaf = state.provinces[HexCoord(15, 1)]
    assert sageleaf.name == "Sageleaf"
    assert sageleaf.owner_kingdom_id == 7


def test_uga_buga_makumb_conquers_mare_imbrium_then_the_aries_sea_and_ends_at_tigerhome():
    # SE3__T11.K1's own action report: "Uga-Buga Makumb rode his flying
    # armies into Mare Imbrium ... Mare Imbrium was conquered and
    # occupied ... found to have an income of 1 gold" (exact match) ->
    # "Uga-Buga Makumb rode his flying armies over to the Aries Sea ...
    # The Aries Sea was overrun and occupied ... found to have a tax
    # base of 3 gold" (exact match) -> "Uga-Buga Makumb flew over to
    # Tigerhome" (his own letter's final narrated move, with no further
    # conquest -- the Cavern he finds there was "already... killed;
    # ... sacked and looted" by someone else earlier).
    state, _ = _bridge_fixture()

    king = state.leaders[1]
    assert king.is_king is True
    assert king.location == HexCoord(16, 1)

    mare_imbrium = state.provinces[HexCoord(0, 1)]
    assert mare_imbrium.name == "Mare Imbrium"
    assert mare_imbrium.owner_kingdom_id == 1
    assert mare_imbrium.tax == 1

    aries_sea = state.provinces[HexCoord(17, 1)]
    assert aries_sea.name == "the Aries Sea"
    assert aries_sea.owner_kingdom_id == 1
    assert aries_sea.tax == 3

    tigerhome = state.provinces[HexCoord(16, 1)]
    assert tigerhome.name == "Tigerhome"
    assert tigerhome.owner_kingdom_id == 1
