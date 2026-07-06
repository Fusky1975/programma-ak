from ak_engine.models.enums import Ability, ActionCode, action_from_int
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import Feature, HexCoord, Terrain


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


def test_feature_defaults_to_unexplored():
    feature = Feature(coord=HexCoord(1, 2), terrain=Terrain.FOREST)
    assert feature.explored_percent == 0
    assert feature.owner_kingdom is None
