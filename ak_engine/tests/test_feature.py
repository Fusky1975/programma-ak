from __future__ import annotations

from ak_engine.models.feature import FEATURE_TYPE_NAMES, Feature, FeatureType
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster

COORD = HexCoord(3, 4)


def test_feature_type_enum_has_32_declared_values():
    assert len(FeatureType) == 32
    assert FeatureType.PYRAMID.value == 0
    assert FeatureType.NOFTYPE.value == 31


def test_feature_type_names_cover_every_enum_value():
    assert set(FEATURE_TYPE_NAMES.keys()) == set(FeatureType)
    assert FEATURE_TYPE_NAMES[FeatureType.PYRAMID] == "Pyramid"
    assert FEATURE_TYPE_NAMES[FeatureType.NOFTYPE] == "encounter area"


def test_feature_defaults_to_undiscovered_and_not_looted():
    feature = Feature(feature_id=1, coord=COORD, kind=FeatureType.DUNGEON)
    assert feature.guardian_monster is None
    assert feature.looted is False
    assert feature.discovered_by_kingdom == {}
    assert feature.discovery_level(kingdom_id=1) == 0


def test_feature_discovery_level_is_per_kingdom():
    feature = Feature(feature_id=1, coord=COORD, kind=FeatureType.TOMB)
    feature.discovered_by_kingdom[1] = 3
    feature.discovered_by_kingdom[2] = 1
    assert feature.discovery_level(kingdom_id=1) == 3
    assert feature.discovery_level(kingdom_id=2) == 1
    assert feature.discovery_level(kingdom_id=3) == 0


def test_feature_carries_its_own_coordinate_independent_of_province():
    feature = Feature(feature_id=1, coord=COORD, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL)
    assert feature.coord == COORD
    assert feature.guardian_monster is Monster.TROLL


def test_feature_looted_flag():
    feature = Feature(feature_id=1, coord=COORD, kind=FeatureType.CRYPT, looted=True)
    assert feature.looted is True
