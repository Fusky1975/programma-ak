"""Tests for the world-file (GW3-format) parser, against a real fixture.

The fixture (`tests/fixtures/world/G3/GW3__T1`) is a real, user-provided
world-file snapshot from a completed game -- see `parser/gw_world.py`'s own
module docstring for the full, evidence-based schema recovery this parser
implements (there is no surviving Pascal source for this file format).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.gw_world import GWProvinceRecord, parse_gw_world

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
        name="Macondo", tax=4, terrain=Terrain.JUNGLE, race=Race.ORCISH, governor_leader_id=None
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


def test_raises_gw_parse_error_on_truncated_record(tmp_path: Path):
    from ak_engine.parser.gw_world import parse_gw_world as parse

    truncated = tmp_path / "truncated_gw"
    truncated.write_text("SomeProvince\n1 0 0 0 0 6\n", encoding="utf-8")

    with pytest.raises(K1ParseError):
        parse(truncated)
