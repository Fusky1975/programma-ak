"""End-to-end validation of `bridge_new_game_state()` against a real,
non-T1 world file (Phase 340).

Every earlier test of `parser/gw_world_bridge.py` exercised only the
committed `GW3__T1` fixture. This module instead runs the whole chain --
`parse_gw_leaders`/`parse_gw_world`/`parse_gw_armies` -> `bridge_new_game_state()`
-- against `tests/fixtures/world/G3/GW3__T5`, and cross-checks the
resulting `GameState` against ground truth quoted directly from the real
`SE3__T4.K1` letter for that same turn (the project's standing
turn-alignment convention: `GW3__Tn` reflects the state at the end of
real turn `n-1`, so `GW3__T5` <-> `SE3__T4.Kx`).

This validation pass is what caught a real, previously-undetected parser
bug (see `parser/gw_world.py parse_gw_world()`'s own Phase 340 docstring
addendum): the province-header regex hard-coded a field that isn't
actually constant, silently dropping 3 of `GW3__T5`'s 162 real
provinces. That bug is fixed as of this phase; every assertion below
passes against the fixed parser.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_new_game_state
from ak_engine.turn.combat import Quality

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T5"


def _bridge_fixture():
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)
    return bridge_new_game_state(leader_records, province_records, army_records)


def test_every_province_and_leader_bridges_with_nothing_left_unresolved():
    # Ground truth: this is the same 162-province, 10-kingdom, 90-Hero
    # game as GW3__T1 -- only the turn number changed. Phase 340's own
    # parser fix (see module docstring) is what makes 162 achievable
    # here; before it, this file only yielded 159 provinces.
    state, report = _bridge_fixture()

    assert report.provinces_created == 162
    assert report.kings_created == 10
    assert report.heroes_created == 90
    # Bagmore and Kitralus (VALHALLA arrivals, Phase 339) are the only
    # real un-rostered Heroes in this game -- unlike at T1, neither one
    # commands a Block B army row at this particular turn, so every
    # single army record bridges cleanly with nothing left unresolved.
    assert set(report.heroes_with_synthetic_id) == {"Bagmore", "Kitralus"}
    assert report.unresolved_army_records == []
    assert len(state.provinces) == 162


def test_kingdom_1_matches_uga_buga_makumbs_own_letter_salutation():
    # SE3__T4.K1's own header: "FOR SHAMAN UGA-BUGA MAKUMBU", and its
    # CHARACTERS table: "Uga-Buga Ma(1)0807 Undea Bersk M Elf ...".
    state, _ = _bridge_fixture()

    kingdom1 = state.kingdoms[1]
    assert kingdom1.name == "Uga-Buga Makumb"
    assert kingdom1.race is Race.ELVEN
    assert kingdom1.alignment is Alignment.UNDEAD

    king = state.leaders[1]
    assert king.is_king is True
    assert king.race is Race.ELVEN
    assert king.alignment is Alignment.UNDEAD


def test_guerin_matches_his_own_letter_exactly():
    # SE3__T4.K1's CHARACTERS table: "Guerin (18) 1305 Undea Caut M Elf".
    # Province 1305 (the Falkland Sea, 1-indexed) is HexCoord(12, 4).
    state, report = _bridge_fixture()

    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.kingdom_id == 1
    assert guerin.race is Race.ELVEN
    assert guerin.alignment is Alignment.UNDEAD
    assert guerin.sex is Sex.MALE
    assert guerin.location == HexCoord(12, 4)


def test_wandering_heroes_kokocala_and_dracona_are_independent_of_kingdom_1():
    # SE3__T4.K1 lists these two separately from Uga-Buga Makumb's own
    # CHARACTERS table, each tagged "a wandering Hero" -- i.e. present
    # in the kingdom's territory but NOT one of its own leaders:
    #   "Kokocala (10) 1104: a wandering Hero ... a Human famous for
    #    Element Magic"
    #   "Dracona (38) 1306: a wandering Hero ... a Orc famous for
    #    Necromancy"
    # Province 1104 -> HexCoord(10, 3); province 1306 -> HexCoord(12, 5).
    state, _ = _bridge_fixture()

    kokocala = state.leaders[10]
    assert kokocala.kingdom_id is None
    assert kokocala.race is Race.HUMAN
    assert kokocala.sex is Sex.MALE
    assert kokocala.location == HexCoord(10, 3)

    dracona = state.leaders[38]
    assert dracona.kingdom_id is None
    assert dracona.race is Race.ORCISH
    assert dracona.sex is Sex.FEMALE
    assert dracona.location == HexCoord(12, 5)


def test_guerins_nine_armies_match_the_letters_normal_quality_column():
    # SE3__T4.K1's own ARMIES table, "Falkland Sea / Guerin" row group,
    # "Normal Quality" column (the bridge stores base/unmodified
    # Quality, not the letter's separate "Modified Quality" column):
    #   108th Skel Bowmen   Crack     110th Bowmen       Veteran
    #   109th Heavy Cavalry Average   124th Skel Dragons Average
    #   209th Warg Riders   Average   240th Bowmen       Crack
    #   241st Bowmen        Crack     272nd Dragons      Average
    #   277th Eagles        Average
    state, _ = _bridge_fixture()

    guerins_armies = [a for a in state.armies.values() if a.commanded_by == 18]
    assert len(guerins_armies) == 9
    for army in guerins_armies:
        assert army.kingdom_id == 1
        assert army.location == HexCoord(12, 4)

    by_type_and_quality = sorted((a.army_type.name, a.quality.value) for a in guerins_armies)
    assert by_type_and_quality == sorted(
        (t.name, q.value)
        for t, q in [
            (ArmyType.BOWMEN, Quality.CRACK),  # 108th Skel Bowmen
            (ArmyType.BOWMEN, Quality.VETERAN),  # 110th Bowmen
            (ArmyType.BOWMEN, Quality.CRACK),  # 240th Bowmen
            (ArmyType.BOWMEN, Quality.CRACK),  # 241st Bowmen
            (ArmyType.HVY_CAVALRY, Quality.AVERAGE),  # 109th Heavy Cavalry
            (ArmyType.DRAGON_WING, Quality.AVERAGE),  # 124th Skel Dragons
            (ArmyType.DRAGON_WING, Quality.AVERAGE),  # 272nd Dragons
            (ArmyType.WARG_RIDERS, Quality.AVERAGE),  # 209th Warg Riders
            (ArmyType.EAGLE_WING, Quality.AVERAGE),  # 277th Eagles
        ]
    )


def test_falkland_and_ark_royal_seas_resolve_to_kingdom_1():
    # SE3__T4.K1's own PROVINCES table:
    #   "the Falkland Sea    6  Elf  Forest  8%  Bowmen  Fleet"
    #   "the Ark Royal Sea   2  Orc  Mountain 8%  Legion  Wargs"
    # -- both listed among Uga-Buga Makumb's own kingdom's provinces,
    # and the letter body narrates Guerin personally conquering both
    # this same turn on the King's behalf.
    state, _ = _bridge_fixture()

    falkland = state.provinces[HexCoord(12, 4)]
    assert falkland.name == "the Falkland Sea"
    assert falkland.owner_kingdom_id == 1
    assert falkland.tax == 6
    assert falkland.race is Race.ELVEN

    ark_royal = state.provinces[HexCoord(12, 5)]
    assert ark_royal.name == "the Ark Royal Sea"
    assert ark_royal.owner_kingdom_id == 1


def test_balearic_sea_remains_unowned():
    # Guerin's own letter, in-narrative: "West of here lies the province
    # of the Balearic Sea (#0707), ruled by no one." Province 0707 (1-
    # indexed) -> HexCoord(6, 6).
    state, _ = _bridge_fixture()

    balearic = state.provinces[HexCoord(6, 6)]
    assert balearic.name == "the Balearic Sea"
    assert balearic.owner_kingdom_id is None
