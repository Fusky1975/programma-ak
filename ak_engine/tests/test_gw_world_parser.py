"""Tests for the world-file (GW3-format) parser, against a real fixture.

The fixture (`tests/fixtures/world/G3/GW3__T1`) is a real, user-provided
world-file snapshot from a completed game -- see `parser/gw_world.py`'s own
module docstring for the full, evidence-based schema recovery this parser
implements (there is no surviving Pascal source for this file format).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.gw_world import GWProvinceRecord, parse_gw_armies, parse_gw_leaders, parse_gw_world
from ak_engine.turn.combat import Quality

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T1"


def test_parses_all_162_provinces():
    records = parse_gw_world(FIXTURE)
    assert len(records) == 162


def test_records_match_real_tax_race_terrain_from_the_letter_reports():
    # Ground truth quoted verbatim from SE3__T1.K2's own "PROVINCES" section
    # and its ASCII map legend (see parser/gw_world.py's own docstring).
    by_name = {r.name: r for r in parse_gw_world(FIXTURE)}

    macondo = by_name["Macondo"]
    assert macondo == GWProvinceRecord(
        name="Macondo",
        tax=4,
        terrain=Terrain.JUNGLE,
        race=Race.ORCISH,
        governor_leader_id=None,
        recruit_type_1=ArmyType.PHALANX,
        recruit_type_2=None,
    )

    transylvania = by_name["Transylvania"]
    assert transylvania.tax == 5
    assert transylvania.terrain is Terrain.MTNS
    assert transylvania.race is Race.DWARVEN
    # Philo(70), a Hero governing on his King's behalf -- not a kingdom id.
    assert transylvania.governor_leader_id == 70

    mongu = by_name["Mongu"]
    assert mongu.tax == 10
    assert mongu.terrain is Terrain.JUNGLE
    assert mongu.race is Race.HUMAN


def test_governor_leader_id_none_for_the_255_unowned_sentinel():
    by_name = {r.name: r for r in parse_gw_world(FIXTURE)}
    assert by_name["Macondo"].governor_leader_id is None


def test_governor_leader_id_set_for_a_kings_own_capital():
    by_name = {r.name: r for r in parse_gw_world(FIXTURE)}
    # Pearlgate is King 7's own capital in this game.
    assert by_name["Pearlgate"].governor_leader_id == 7


def test_race_ordinals_match_this_projects_own_race_enum_directly():
    by_name = {r.name: r for r in parse_gw_world(FIXTURE)}
    assert by_name["Kaluga"].race is Race.ELVEN
    assert by_name["Kerry"].race is Race.DWARVEN
    assert by_name["Kiska"].race is Race.EAGLES


def test_recruit_types_decoded_for_a_province_with_both_types():
    # Orielle: real line 3 "4 0  7 0" -- Legion (4) and Chariots (7), the
    # same "Le,Ch" pair the letter's own ASCII map legend shows for it
    # (parser/gw_world.py's own "Recruiting Types (Mod_PAT)" docstring
    # section has the full cross-reference).
    by_name = {r.name: r for r in parse_gw_world(FIXTURE)}
    orielle = by_name["Orielle"]
    assert orielle.recruit_type_1 is ArmyType.LEGION
    assert orielle.recruit_type_2 is ArmyType.CHARIOTS


def test_recruit_type_2_none_sentinel_for_a_single_recruit_type_province():
    # Macondo: real line 3 "3 0  15 0" -- ordinal 15 is the real "no
    # second recruit type" sentinel, matching SE3__T1.K2's own real
    # "Phalanx  None" PROVINCES table row for Macondo exactly.
    by_name = {r.name: r for r in parse_gw_world(FIXTURE)}
    assert by_name["Macondo"].recruit_type_2 is None


def test_recruit_types_monstrous_ordinals_are_one_higher_than_this_projects_own_enum():
    # Belladonna: real line 3 "19 0  15 0" -- ordinal 19 decodes to
    # WEREBEASTS even though this project's own ArmyType enum places
    # WEREBEASTS at ordinal 18 -- the real Pascal enum has one extra
    # member (a "no type" sentinel at 15) this project's own enum never
    # modeled. See the module docstring's ordinal table.
    by_name = {r.name: r for r in parse_gw_world(FIXTURE)}
    assert by_name["Belladonna"].recruit_type_1 is ArmyType.WEREBEASTS


def test_parses_all_100_leader_records():
    records = parse_gw_leaders(FIXTURE)
    assert len(records) == 100
    assert sum(1 for r in records if r.is_king) == 10
    assert sum(1 for r in records if not r.is_king) == 90


def test_kings_own_kingdom_id_derived_from_file_order_matches_real_letter_ids():
    # Ground truth from SE3__T1.Kx's own letters (parser/gw_world.py's own
    # Phase 330 addendum): Bradipo I is King #2, Kwoth #3, Hokuto #4,
    # Prometeo #5, Kahn #6, Giovanna d'Arco #7, Circe #8, Agesilao #9.
    by_name = {r.name: r for r in parse_gw_leaders(FIXTURE) if r.is_king}
    assert by_name["Bradipo I"].kingdom_id == 2
    assert by_name["Kwoth"].kingdom_id == 3
    assert by_name["Hokuto"].kingdom_id == 4
    assert by_name["Prometeo"].kingdom_id == 5
    assert by_name["Kahn"].kingdom_id == 6
    assert by_name["Giovanna d'Arco"].kingdom_id == 7
    assert by_name["Circe"].kingdom_id == 8
    assert by_name["Agesilao"].kingdom_id == 9
    # The first two Kings in file order -- consistent with, though not
    # independently confirmed against, real letter data the way the
    # other 8 are (see GWLeaderRecord's own docstring).
    assert by_name["Babba Sissoko"].kingdom_id == 0
    assert by_name["Uga-Buga Makumb"].kingdom_id == 1


def test_a_kings_own_race_alignment_temper_and_coordinate():
    by_name = {r.name: r for r in parse_gw_leaders(FIXTURE) if r.is_king}
    bradipo = by_name["Bradipo I"]
    assert bradipo.race is Race.HUMAN
    assert bradipo.alignment is Alignment.GOOD
    assert bradipo.temper is Temper.CAUTIOUS
    assert bradipo.coord == HexCoord(2, 4)
    # 15 (skill, aptitude) pairs -- Phase 325.
    assert len(bradipo.skills.raw_values) == 30


def test_a_heros_own_kingdom_id_decoded_from_the_liege_field():
    # Ningarl (#13) serves King Hokuto (#4) -- confirmed via SE3__T1.K4's
    # own real CHARACTERS roster (Phase 327).
    by_name = {r.name: r for r in parse_gw_leaders(FIXTURE)}
    assert by_name["Ningarl"].kingdom_id == 4
    assert by_name["Ningarl"].is_king is False


def test_an_independent_heros_own_kingdom_id_is_none():
    # Kokocala -- narrated in SE3__T2.K1's own letter as an independent
    # local ruler ("populated by Humans and Kokocala rules there"),
    # matching his own real Liege 255/255 header value.
    by_name = {r.name: r for r in parse_gw_leaders(FIXTURE)}
    assert by_name["Kokocala"].kingdom_id is None


def test_raises_gw_parse_error_on_truncated_record(tmp_path: Path):
    from ak_engine.parser.gw_world import parse_gw_world as parse

    truncated = tmp_path / "truncated_gw"
    truncated.write_text("SomeProvince\n1 0 0 0 0 6\n", encoding="utf-8")

    with pytest.raises(K1ParseError):
        parse(truncated)


def test_parses_all_218_block_b_army_records():
    # 218 rows at T1, 104 unled (`leader_id == 255`) -- Phase 316's own
    # confirmed counts for this exact fixture.
    records = parse_gw_armies(FIXTURE)
    assert len(records) == 218
    assert sum(1 for r in records if r.commanded_by_leader_id is None) == 104


def test_philos_own_block_b_rows_match_his_real_dwarven_axemen_garrison():
    # Philo(70) governs Transylvania (Dwarven) -- two duplicate real rows
    # (Phase 316), both Race=Dwarven/ArmyType=Axemen/Quality=Average.
    records = parse_gw_armies(FIXTURE)
    philos_rows = [r for r in records if r.commanded_by_leader_id == 70]
    assert len(philos_rows) == 2
    for row in philos_rows:
        assert row.coord == HexCoord(1, 5)
        assert row.race is Race.DWARVEN
        assert row.army_type is ArmyType.AXEMEN
        assert row.quality is Quality.AVERAGE
        assert row.is_skeletal is False


def test_is_skeletal_true_only_for_the_confirmed_field7_equals_3_rows():
    # Both of this fixture's own Skeletal rows are themselves unled --
    # a real correction to Phase 332's "field7 in {1, 3} only on led
    # rows" claim, which was only ever checked against a different turn.
    records = parse_gw_armies(FIXTURE)
    skeletal = [r for r in records if r.is_skeletal]
    assert len(skeletal) == 2
    for row in skeletal:
        assert row.raw_field7 == 3
        assert row.commanded_by_leader_id is None
    assert all(r.raw_field7 != 3 for r in records if not r.is_skeletal)


def test_block_b_raw_fields_are_preserved_undecoded():
    records = parse_gw_armies(FIXTURE)
    philo_row = next(r for r in records if r.commanded_by_leader_id == 70)
    assert philo_row.raw_field7 == 1
    assert philo_row.raw_field8 == 2
    assert philo_row.raw_field9 == 0
    assert philo_row.raw_field10 == 0


def test_raises_gw_parse_error_on_unrecognized_race_ordinal(tmp_path: Path):
    bad_race = tmp_path / "bad_race_gw_block_b"
    bad_race.write_text("70 1 5 99 2 2 1 2 0 0\n", encoding="utf-8")

    with pytest.raises(K1ParseError):
        parse_gw_armies(bad_race)
