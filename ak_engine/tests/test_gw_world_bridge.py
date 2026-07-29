"""Tests for the GW-world-to-`GameState.provinces` coordinate bridge.

See `parser/gw_world_bridge.py`'s own module docstring for the empirical,
100%-match evidence behind the column-major coordinate mapping this
module implements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import parse_gw_world
from ak_engine.parser.gw_world_bridge import bridge_gw_world_provinces, resolve_province_owners

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
    assert macondo.recruit_type_1 is ArmyType.PHALANX
    assert macondo.recruit_type_2 is None


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


# -- Phase 224: resolve_province_owners() ------------------------------


def test_resolve_province_owners_resolves_a_kings_own_capital():
    # Pearlgate(1703) is King 7's own capital in this game -- his own
    # leader_id equals his kingdom_id, the project-wide King convention.
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)
    state = GameState()
    state.leaders[7] = LeaderState(leader_id=7, kingdom_id=7, name="SomeKing", location=HexCoord(0, 0), is_king=True)

    resolved = resolve_province_owners(provinces, records, state)

    assert resolved == 1
    assert provinces[HexCoord(16, 2)].name == "Pearlgate"
    assert provinces[HexCoord(16, 2)].owner_kingdom_id == 7


def test_resolve_province_owners_resolves_a_hero_governed_province_to_his_kingdom():
    # Transylvania(0206) is governed by Philo(70), a Hero -- confirmed
    # by parser/gw_world.py's own docstring cross-check.
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)
    state = GameState()
    state.leaders[70] = LeaderState(leader_id=70, kingdom_id=6, name="Philo", location=HexCoord(0, 0))

    resolve_province_owners(provinces, records, state)

    assert provinces[HexCoord(1, 5)].name == "Transylvania"
    assert provinces[HexCoord(1, 5)].owner_kingdom_id == 6


def test_resolve_province_owners_leaves_unknown_governors_unresolved():
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)
    state = GameState()  # no leaders bridged at all

    resolved = resolve_province_owners(provinces, records, state)

    assert resolved == 0
    assert all(p.owner_kingdom_id is None for p in provinces.values())


def test_resolve_province_owners_resolves_independent_hero_to_none():
    records = parse_gw_world(FIXTURE)
    provinces = bridge_gw_world_provinces(records)
    state = GameState()
    state.leaders[70] = LeaderState(leader_id=70, kingdom_id=None, name="Philo", location=HexCoord(0, 0))

    resolved = resolve_province_owners(provinces, records, state)

    assert resolved == 1
    assert provinces[HexCoord(1, 5)].owner_kingdom_id is None
