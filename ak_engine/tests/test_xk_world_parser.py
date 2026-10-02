"""Tests for the ``XK`` per-Kingdom file parser, against 4 real fixtures.

The fixtures (`tests/fixtures/world/G3/XK3__T{1,2}.K{0,1}`) are real,
user-provided per-Kingdom snapshots from the same real campaign "3" this
project's own `GW3__T1`-`T12`/`SE3__T*.K1` fixtures already come from --
see `parser/xk_world.py`'s own module docstring for the full, evidence-
based (known-plaintext) derivation of every field tested here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.xk_world import (
    XK_HEADER_SIZE,
    XK_LEADER_ROSTER_COUNT,
    XKParseError,
    parse_xk_header,
    parse_xk_known_leader_names,
    parse_xk_province_record,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "world" / "G3"
T1_K0 = FIXTURE_DIR / "XK3__T1.K0"
T1_K1 = FIXTURE_DIR / "XK3__T1.K1"
T2_K0 = FIXTURE_DIR / "XK3__T2.K0"
T2_K1 = FIXTURE_DIR / "XK3__T2.K1"


@pytest.mark.parametrize("fixture", [T1_K0, T1_K1, T2_K0, T2_K1])
def test_header_revision_matches_the_real_gw_header_revision(fixture):
    # Every real GW3__T1-T12 file in this project's corpus also reads
    # header_revision == 30 -- the same save-format revision marker.
    assert parse_xk_header(fixture).header_revision == 30


@pytest.mark.parametrize("fixture", [T1_K0, T1_K1, T2_K0, T2_K1])
def test_king_count_matches_the_real_10_kingdom_campaign(fixture):
    assert parse_xk_header(fixture).king_count == 10


def test_kingdom_id_matches_the_filenames_own_k_suffix():
    assert parse_xk_header(T1_K0).kingdom_id == 0
    assert parse_xk_header(T1_K1).kingdom_id == 1
    assert parse_xk_header(T2_K0).kingdom_id == 0
    assert parse_xk_header(T2_K1).kingdom_id == 1


def test_game_turn_matches_the_filenames_own_t_prefix():
    assert parse_xk_header(T1_K0).game_turn == 1
    assert parse_xk_header(T1_K1).game_turn == 1
    assert parse_xk_header(T2_K0).game_turn == 2
    assert parse_xk_header(T2_K1).game_turn == 2


def test_parse_xk_header_rejects_a_too_short_file(tmp_path):
    truncated = tmp_path / "XK3__T1.K0"
    truncated.write_bytes(b"\x00" * (XK_HEADER_SIZE - 1))

    with pytest.raises(XKParseError):
        parse_xk_header(truncated)


@pytest.mark.parametrize("fixture", [T1_K0, T1_K1, T2_K0, T2_K1])
def test_known_leader_names_table_has_exactly_100_entries(fixture):
    names = parse_xk_known_leader_names(fixture)
    assert len(names) == XK_LEADER_ROSTER_COUNT
    assert set(names) == set(range(XK_LEADER_ROSTER_COUNT))


@pytest.mark.parametrize("fixture", [T1_K0, T1_K1, T2_K0, T2_K1])
def test_every_king_is_always_known_by_their_real_name(fixture):
    # Confirmed against the real GW3__T1 leader roster -- every King is
    # always known, in every Kingdom's own file, at every turn. King id 2
    # is spelled "Bradibo I" in both real Turn 1 files and "Bradipo I" in
    # both real Turn 2 files -- a genuine, reproducible spelling change
    # between turns in the real data itself (matching GW3__T1's own
    # "Bradipo I" only from Turn 2 onward), not a parser quirk.
    names = parse_xk_known_leader_names(fixture)
    king_2_name = "Bradibo I" if fixture in (T1_K0, T1_K1) else "Bradipo I"
    real_king_names = [
        "Babba Sissoko",
        "Uga-Buga Makumb",
        king_2_name,
        "Kwoth",
        "Hokuto",
        "Prometeo",
        "Kahn",
        "Giovanna d'Arco",
        "Circe",
        "Agesilao",
    ]
    for king_id, real_name in enumerate(real_king_names):
        assert names[king_id] == real_name


def test_an_unknown_ordinary_hero_reads_as_none_not_the_raw_placeholder():
    names = parse_xk_known_leader_names(T1_K0)
    assert names[10] is None


def test_kingdom_1_knows_its_own_two_starting_companions_by_name():
    # Guerin (id 18) and Teleko (id 72) -- Kingdom 1's own real starting
    # Companions in the real GW3__T1 data, both at its own Home coordinate.
    names = parse_xk_known_leader_names(T1_K1)
    assert names[18] == "Guerin"
    assert names[72] == "Teleko"


def test_kingdom_0_does_not_know_kingdom_1s_own_companions_at_turn_1():
    names = parse_xk_known_leader_names(T1_K0)
    assert names[18] is None
    assert names[72] is None


def test_known_leader_count_only_grows_from_turn_1_to_turn_2():
    # More exploration happens over time -- never less.
    t1_known = {i for i, n in parse_xk_known_leader_names(T1_K1).items() if n is not None}
    t2_known = {i for i, n in parse_xk_known_leader_names(T2_K1).items() if n is not None}
    assert t1_known <= t2_known
    assert len(t2_known) > len(t1_known)


def _record_start(data: bytes, name: str) -> int:
    """Test-only helper: finds a known province record's own starting
    byte offset (its ``coord_x`` byte) by searching for its real,
    already-confirmed name -- not a general province-table scanner
    (see `parse_xk_world.py`'s own module docstring for why locating
    the table's start in an arbitrary file remains genuinely open).
    """

    needle = bytes([len(name)]) + name.encode("latin-1")
    idx = data.find(needle)
    assert idx != -1, f"{name!r} not found"
    return idx - 2


def test_parse_xk_province_record_decodes_an_ordinary_known_neighbor():
    data = T1_K0.read_bytes()
    record, next_offset = parse_xk_province_record(data, _record_start(data, "Florence"))

    assert record.coord == HexCoord(11, 6)
    assert record.name == "Florence"
    assert record.terrain is Terrain.MTNS
    assert record.race is Race.DWARVEN
    assert record.governor_leader_id == 52
    assert record.explored_percent is None
    assert record.owner_kingdom_id is None
    assert record.tax is None
    assert record.recruit_type_1 is None
    assert record.recruit_type_2 is None
    # The next record (Piratum) starts right where this one says it does.
    assert data[next_offset : next_offset + 2] == bytes([11, 7])


def test_parse_xk_province_record_decodes_an_ungoverned_neighbor():
    data = T1_K1.read_bytes()
    record, _ = parse_xk_province_record(data, _record_start(data, "Falkenheim"))

    assert record.coord == HexCoord(10, 5)
    assert record.terrain is Terrain.FOREST
    assert record.race is Race.EAGLES
    assert record.governor_leader_id is None


def test_parse_xk_province_record_decodes_kingdom_0s_own_home():
    data = T1_K0.read_bytes()
    record, _ = parse_xk_province_record(data, _record_start(data, "Piratum"))

    assert record.coord == HexCoord(11, 7)
    assert record.terrain is Terrain.MTNS
    assert record.race is Race.ORCISH
    assert record.governor_leader_id is None
    assert record.explored_percent == 100
    assert record.owner_kingdom_id == 0
    assert record.tax == 10
    assert record.recruit_type_1 is ArmyType.PHALANX
    assert record.recruit_type_2 is ArmyType.WARG_RIDERS


def test_parse_xk_province_record_decodes_kingdom_1s_own_home():
    data = T1_K1.read_bytes()
    record, _ = parse_xk_province_record(data, _record_start(data, "the Dolphin Sea"))

    assert record.coord == HexCoord(9, 5)
    assert record.terrain is Terrain.FOREST
    assert record.race is Race.ELVEN
    assert record.explored_percent == 100
    assert record.owner_kingdom_id == 1
    assert record.tax == 10
    assert record.recruit_type_1 is ArmyType.BOWMEN
    assert record.recruit_type_2 is ArmyType.HVY_CAVALRY


def test_parse_xk_province_record_chains_through_every_known_province():
    # Kingdom 0's entire known-province table at Turn 1, decoded in
    # sequence via each record's own returned next-offset, matching
    # every real GW3__T1 fact for all 7 (Home + 6 real neighbors, minus
    # the 2 real Dragon-race ones this Kingdom doesn't know -- see
    # module docstring).
    data = T1_K0.read_bytes()
    offset = _record_start(data, "the Maldive Sea")
    expected = [
        ("the Maldive Sea", HexCoord(10, 7), Terrain.PLAINS, Race.HUMAN),
        ("Florence", HexCoord(11, 6), Terrain.MTNS, Race.DWARVEN),
        ("Piratum", HexCoord(11, 7), Terrain.MTNS, Race.ORCISH),
        ("Redwood", HexCoord(11, 8), Terrain.FOREST, Race.TROLLISH),
        ("Jutland", HexCoord(12, 6), Terrain.MTNS, Race.ORCISH),
        ("Silvania", HexCoord(12, 7), Terrain.MTNS, Race.ELVEN),
        ("Tanglewood", HexCoord(12, 8), Terrain.PLAINS, Race.DWARVEN),
    ]
    for name, coord, terrain, race in expected:
        record, offset = parse_xk_province_record(data, offset)
        assert (record.name, record.coord, record.terrain, record.race) == (name, coord, terrain, race)


def test_parse_xk_province_record_gives_a_newly_conquered_province_the_owned_shape_too():
    # By Turn 2, Kingdom 0 has taken Redwood (real GW3__T2 data) -- the
    # expanded, owned-province shape isn't exclusive to the literal
    # Home, and explored_percent is a real varying value (8%), not a
    # Home-only fixed 100.
    data = T2_K0.read_bytes()
    record, _ = parse_xk_province_record(data, _record_start(data, "Redwood"))

    assert record.owner_kingdom_id == 0
    assert record.explored_percent == 8
    assert record.tax == 2
    assert record.recruit_type_1 is ArmyType.TROLLS
    assert record.recruit_type_2 is None
    assert record.governor_leader_id is None


def test_parse_xk_province_record_decodes_a_sea_province_with_no_race():
    data = T2_K0.read_bytes()
    record, _ = parse_xk_province_record(data, _record_start(data, "the Orca Sea"))

    assert record.terrain is Terrain.SEA
    assert record.race is Race.NO_RACE
    assert record.governor_leader_id is None
