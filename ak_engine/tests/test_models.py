from ak_engine.models.enums import ABILITY_ABBREVIATION, ABILITY_NAME, Ability, ActionCode, action_from_int
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.kingdom import VOTE_TURN_SENTINEL, Kingdom, KingdomMoveHeader, SkillTable
from ak_engine.models.map import TERRAIN_NAME, HexCoord, Terrain, province_code


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


def test_kingdom_move_header_field_order_matches_def2_pas():
    # Phase 464: raw_fields, in DEF2.PAS Write_Moves/Read_Moves order
    # (sex is parsed separately -- see the parser test for that).
    header = KingdomMoveHeader(raw_fields=[27, 1, 0, 101, 1, 15, 1], sex="M")
    assert header.sex == "M"
    assert header.interp_vers == 27
    assert header.allreq == 1
    assert header.brreq == 0
    assert header.kacct == 101
    assert header.kpmode == 1
    assert header.kprevgold == 15
    assert header.ksendmeth == 1


def test_kingdom_number_is_the_same_slot_as_interp_vers():
    # Phase 464: kingdom_number is confirmed NOT a per-Kingdom id -- it's
    # literally the same raw_fields[0] slot as interp_vers.
    header = KingdomMoveHeader(raw_fields=[27, 1, 0, 101, 1, 15, 1])
    assert header.kingdom_number == header.interp_vers == 27


def test_kingdom_id_is_derived_from_the_source_filenames_own_k_suffix():
    # Phase 574: kingdom_id replaces the confirmed-broken header.kingdom_
    # number (test_kingdom_number_is_the_same_slot_as_interp_vers above)
    # with the real per-Kingdom identifier, parsed from the move file's
    # own name instead -- note header.kingdom_number here still reads 27
    # (unchanged, still the same interp_vers slot) while kingdom_id
    # correctly reads 4 from the filename's own trailing suffix.
    kingdom = Kingdom(
        source_filename="AK3__T7.K4",
        king_name="Someone",
        king_title=None,
        header=KingdomMoveHeader(raw_fields=[27, 1, 0, 101, 1, 15, 1]),
        skills=SkillTable(raw_values=[0] * 31),
    )
    assert kingdom.kingdom_id == 4
    assert kingdom.header.kingdom_number == 27


def test_is_vote_turn_true_only_at_the_sentinel():
    holding_vote = KingdomMoveHeader(raw_fields=[27, 1, 0, 101, 1, VOTE_TURN_SENTINEL, 1])
    assert holding_vote.is_vote_turn() is True

    not_holding_vote = KingdomMoveHeader(raw_fields=[27, 1, 0, 101, 1, 15, 1])
    assert not_holding_vote.is_vote_turn() is False


def test_province_code_matches_the_real_mongu_sample():
    # Phase 431: turn/movement.py's own docstring cites the real report
    # narrative naming Mongu as "#305" -- confirmed (number // 100, number
    # % 100) == (x, y).
    assert province_code(HexCoord(3, 5)) == 305


def test_province_code_matches_the_real_acacia_sample():
    # Same citation category: Acacia's own CHARACTERS/ADVENTURE "Loc"
    # field in the real SE0__T0.K0.txt sample reads "2103".
    assert province_code(HexCoord(21, 3)) == 2103


def test_province_code_has_no_leading_zero_padding():
    # Mongu's own real code is exactly "305", not "0305" -- province_code()
    # returns an int, not a zero-padded string; a caller formats it.
    assert str(province_code(HexCoord(3, 5))) == "305"


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


# -- Phase 268: ABILITY_NAME (CTBOTH.PAS `anoun`) --


def test_ability_name_covers_every_ability_member():
    assert set(ABILITY_NAME.keys()) == set(Ability)


def test_ability_name_verbatim_samples():
    assert ABILITY_NAME[Ability.TACTICAL] == "Tactics"
    assert ABILITY_NAME[Ability.MELEE] == "Meleeing"
    assert ABILITY_NAME[Ability.WHITE] == "White Magic"
    assert ABILITY_NAME[Ability.SAGE] == "Sageness"
    assert ABILITY_NAME[Ability.EXPLORER] == "Exploring"
