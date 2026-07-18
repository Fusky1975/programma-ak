from ak_engine.models.enums import ABILITY_ABBREVIATION, Ability, ActionCode, action_from_int
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import TERRAIN_NAME, HexCoord, Terrain


def test_action_from_int_maps_known_codes():
    assert action_from_int(9) == ActionCode.CAST
    assert action_from_int(0) == ActionCode.LMOVE


def test_action_from_int_keeps_unknown_codes_raw():
    assert action_from_int(999) == 999


def test_skill_table_pair_for_ability():
    raw = list(range(31))
    table = SkillTable(raw_values=raw)
    assert table.pair_for_ability(Ability.TACTICAL) == (0, 1)
    assert table.pair_for_ability(Ability.SAGE) == (28, 29)


def test_feature_defaults_to_undiscovered():
    feature = Feature(feature_id=1, coord=HexCoord(1, 2), kind=FeatureType.DUNGEON)
    assert feature.guardian_monster is None
    assert feature.looted is False
    assert feature.discovery_level(kingdom_id=7) == 0


def test_terrain_name_covers_every_terrain_member():
    assert set(TERRAIN_NAME.keys()) == set(Terrain)


def test_terrain_name_matches_sourced_display_names():
    assert TERRAIN_NAME[Terrain.PLAINS] == "Plain"
    assert TERRAIN_NAME[Terrain.DESERT] == "Desert"
    assert TERRAIN_NAME[Terrain.JUNGLE] == "Jungle"
    assert TERRAIN_NAME[Terrain.FOREST] == "Forest"
    assert TERRAIN_NAME[Terrain.MTNS] == "Mountain"
    assert TERRAIN_NAME[Terrain.SEA] == "Sea"
    assert TERRAIN_NAME[Terrain.NO_TERRAIN] == "No Terrain"


def test_ability_abbreviation_covers_every_ability_member():
    assert set(ABILITY_ABBREVIATION.keys()) == set(Ability)


def test_ability_abbreviation_matches_sourced_column_header():
    assert ABILITY_ABBREVIATION[Ability.TACTICAL] == "Ta"
    assert ABILITY_ABBREVIATION[Ability.MARCH] == "Ma"
    assert ABILITY_ABBREVIATION[Ability.NAVAL] == "Na"
    assert ABILITY_ABBREVIATION[Ability.ARCHERY] == "Ar"
    assert ABILITY_ABBREVIATION[Ability.MELEE] == "Me"
    assert ABILITY_ABBREVIATION[Ability.WHITE] == "Wh"
    assert ABILITY_ABBREVIATION[Ability.NECROMANCY] == "Ne"
    assert ABILITY_ABBREVIATION[Ability.ELEMENTAL] == "El"
    assert ABILITY_ABBREVIATION[Ability.PSYCHIC] == "Ps"
    assert ABILITY_ABBREVIATION[Ability.ILLUSION] == "Il"
    assert ABILITY_ABBREVIATION[Ability.DRUID] == "Dr"
    assert ABILITY_ABBREVIATION[Ability.THIEF] == "Th"
    assert ABILITY_ABBREVIATION[Ability.EXPLORER] == "Ex"
    assert ABILITY_ABBREVIATION[Ability.SPY] == "Sp"
    assert ABILITY_ABBREVIATION[Ability.SAGE] == "Sa"
