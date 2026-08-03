from __future__ import annotations

from pathlib import Path

from ak_engine.models.map import Terrain
from ak_engine.models.province_names import PROVINCE_NAME_POOLS
from ak_engine.parser.gw_world import parse_gw_world

FIXTURES = [
    Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T1",
    Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T5",
]


def test_pools_cover_every_real_terrain_but_no_terrain():
    assert set(PROVINCE_NAME_POOLS) == {
        Terrain.DESERT,
        Terrain.FOREST,
        Terrain.JUNGLE,
        Terrain.SEA,
        Terrain.MTNS,
        Terrain.PLAINS,
    }


def test_pool_sizes_match_the_confirmed_prnames_pas_layout():
    # Plains 0-49, Desert 50-99, Jungle 100-149, Forest 150-199,
    # Mountains 200-249 (50 each), Sea 250-511 (262) -- the source's own
    # confirmed contiguous id ranges.
    assert len(PROVINCE_NAME_POOLS[Terrain.PLAINS]) == 50
    assert len(PROVINCE_NAME_POOLS[Terrain.DESERT]) == 50
    assert len(PROVINCE_NAME_POOLS[Terrain.JUNGLE]) == 50
    assert len(PROVINCE_NAME_POOLS[Terrain.FOREST]) == 50
    assert len(PROVINCE_NAME_POOLS[Terrain.MTNS]) == 50
    assert len(PROVINCE_NAME_POOLS[Terrain.SEA]) == 262
    assert sum(len(pool) for pool in PROVINCE_NAME_POOLS.values()) == 512


def test_first_and_last_name_of_each_pool_matches_prnames_pas_order():
    assert PROVINCE_NAME_POOLS[Terrain.PLAINS][0] == "Candelaria"
    assert PROVINCE_NAME_POOLS[Terrain.PLAINS][-1] == "Jutland"
    assert PROVINCE_NAME_POOLS[Terrain.DESERT][0] == "Jerbilia"
    assert PROVINCE_NAME_POOLS[Terrain.DESERT][-1] == "Kassala"
    assert PROVINCE_NAME_POOLS[Terrain.JUNGLE][0] == "Oaxaca"
    assert PROVINCE_NAME_POOLS[Terrain.JUNGLE][-1] == "Kulungu"
    assert PROVINCE_NAME_POOLS[Terrain.FOREST][0] == "Sherwood"
    assert PROVINCE_NAME_POOLS[Terrain.FOREST][-1] == "Tigerhome"
    assert PROVINCE_NAME_POOLS[Terrain.MTNS][0] == "Denali"
    assert PROVINCE_NAME_POOLS[Terrain.MTNS][-1] == "Coralgate"
    assert PROVINCE_NAME_POOLS[Terrain.SEA][0] == "Mare Imbrium"
    assert PROVINCE_NAME_POOLS[Terrain.SEA][-1] == "the Lepanto Sea"


def test_sea_pool_preserves_the_two_real_duplicate_spelling_pairs_verbatim():
    # PRNAMES.PAS itself contains these two duplicate-spelling pairs
    # (ids 287/318 "the Hammerhead Sea", 475/477 "the Otter Sea") --
    # transcribed as-is, not deduplicated (see module docstring).
    sea = PROVINCE_NAME_POOLS[Terrain.SEA]
    assert sea.count("the Hammerhead Sea") == 2
    assert sea.count("the Otter Sea") == 2


def test_all_names_are_unique_within_their_own_pool_except_the_two_confirmed_pairs():
    for terrain, pool in PROVINCE_NAME_POOLS.items():
        if terrain is Terrain.SEA:
            continue
        assert len(pool) == len(set(pool)), f"unexpected duplicate in {terrain}"


def test_every_real_gw3_province_name_matches_the_catalog():
    all_names = {name for pool in PROVINCE_NAME_POOLS.values() for name in pool}
    for fixture in FIXTURES:
        records = parse_gw_world(fixture)
        assert len(records) == 162
        unmatched = [r.name for r in records if r.name not in all_names]
        assert unmatched == [], f"{fixture.name}: {unmatched}"
