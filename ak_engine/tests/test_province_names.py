from __future__ import annotations

from ak_engine.models.map import Terrain
from ak_engine.models.province_names import PROVINCE_NAME_POOLS


def test_pools_cover_every_real_terrain_but_no_terrain():
    assert set(PROVINCE_NAME_POOLS) == {
        Terrain.DESERT,
        Terrain.FOREST,
        Terrain.JUNGLE,
        Terrain.SEA,
        Terrain.MTNS,
        Terrain.PLAINS,
    }


def test_pool_sizes_match_the_supplied_list():
    assert len(PROVINCE_NAME_POOLS[Terrain.DESERT]) == 30
    assert len(PROVINCE_NAME_POOLS[Terrain.FOREST]) == 50
    assert len(PROVINCE_NAME_POOLS[Terrain.JUNGLE]) == 40
    assert len(PROVINCE_NAME_POOLS[Terrain.SEA]) == 80
    assert len(PROVINCE_NAME_POOLS[Terrain.MTNS]) == 50
    assert len(PROVINCE_NAME_POOLS[Terrain.PLAINS]) == 50


def test_first_and_last_name_of_each_pool_matches_the_supplied_order():
    assert PROVINCE_NAME_POOLS[Terrain.DESERT][0] == "Al Jair"
    assert PROVINCE_NAME_POOLS[Terrain.DESERT][-1] == "Quaib"
    assert PROVINCE_NAME_POOLS[Terrain.FOREST][0] == "Amazonia"
    assert PROVINCE_NAME_POOLS[Terrain.FOREST][-1] == "Castewellan"
    assert PROVINCE_NAME_POOLS[Terrain.JUNGLE][0] == "Mitumba"
    assert PROVINCE_NAME_POOLS[Terrain.JUNGLE][-1] == "Rotswana"
    assert PROVINCE_NAME_POOLS[Terrain.SEA][0] == "Yellow Sea"
    assert PROVINCE_NAME_POOLS[Terrain.SEA][-1] == "Square Sea"
    assert PROVINCE_NAME_POOLS[Terrain.MTNS][0] == "Blue Ridge"
    assert PROVINCE_NAME_POOLS[Terrain.MTNS][-1] == "Schwatka"
    assert PROVINCE_NAME_POOLS[Terrain.PLAINS][0] == "Smeraldine"
    assert PROVINCE_NAME_POOLS[Terrain.PLAINS][-1] == "Hoorn"


def test_sea_pool_preserves_the_two_incidental_repeats_verbatim():
    # The user's own supplied list repeats "Frog Sea" and "Pocket Sea"
    # once each -- transcribed as-is, not deduplicated.
    sea = PROVINCE_NAME_POOLS[Terrain.SEA]
    assert sea.count("Frog Sea") == 2
    assert sea.count("Pocket Sea") == 2
