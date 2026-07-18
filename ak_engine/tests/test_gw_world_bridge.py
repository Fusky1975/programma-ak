"""Tests for the GW-world-to-`GameState.provinces` coordinate bridge.

See `parser/gw_world_bridge.py`'s own module docstring for the empirical,
100%-match evidence behind the column-major coordinate mapping this
module implements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_gw_world_provinces

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T1"


def test_bridges_all_162_provinces():
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)
    assert len(provinces) == 162


def test_macondo_lands_at_its_real_confirmed_coordinate():
    # Real map legend: "Macondo(0205)" -- x=02, y=05 (1-indexed).
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)

    macondo = provinces[HexCoord(1, 4)]
    assert macondo.name == "Macondo"
    assert macondo.tax == 4
    assert macondo.terrain is Terrain.JUNGLE
    assert macondo.race is Race.ORCISH


def test_alderwood_lands_at_the_origin():
    # The file's own very first record -- x=01, y=01 (1-indexed) -> (0, 0).
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)

    assert provinces[HexCoord(0, 0)].name == "Alderwood"


def test_owner_kingdom_id_always_none_governor_resolution_deferred():
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)

    assert all(p.owner_kingdom_id is None for p in provinces.values())


def test_raises_on_a_records_count_not_a_multiple_of_height():
    with pytest.raises(ValueError):
        bridge_gw_world_provinces([], height=0)

    records = parse_gw_world(FIXTURE)
    with pytest.raises(ValueError):
        bridge_gw_world_provinces(records[:-1])
