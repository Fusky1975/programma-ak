"""Tests for the ``XK`` per-Kingdom file parser, against 4 real fixtures.

The fixtures (`tests/fixtures/world/G3/XK3__T{1,2}.K{0,1}`) are real,
user-provided per-Kingdom snapshots from the same real campaign "3" this
project's own `GW3__T1`-`T12`/`SE3__T*.K1` fixtures already come from --
see `parser/xk_world.py`'s own module docstring for the full derivation,
sourced to a real disassembly of `AK.EXE`'s own XK-writing routine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import FeatureType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.parser.xk_world import (
    SUPPORTED_FORMAT_REVISION,
    SUPPORTED_GAME_VERSION,
    XK_NAME_TABLE_OFFSET,
    XKParseError,
    parse_xk_world,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "world" / "G3"
T1_K0 = FIXTURE_DIR / "XK3__T1.K0"
T1_K1 = FIXTURE_DIR / "XK3__T1.K1"
T1_K2 = FIXTURE_DIR / "XK3__T1.K2"
T2_K0 = FIXTURE_DIR / "XK3__T2.K0"
T2_K1 = FIXTURE_DIR / "XK3__T2.K1"
T2_K2 = FIXTURE_DIR / "XK3__T2.K2"
T3_K0 = FIXTURE_DIR / "XK3__T3.K0"
T3_K1 = FIXTURE_DIR / "XK3__T3.K1"
T3_K2 = FIXTURE_DIR / "XK3__T3.K2"
T4_K0 = FIXTURE_DIR / "XK3__T4.K0"
T4_K1 = FIXTURE_DIR / "XK3__T4.K1"
T4_K2 = FIXTURE_DIR / "XK3__T4.K2"
ALL_FIXTURES = (T1_K0, T1_K1, T2_K0, T2_K1)
# The full real 12-sample corpus this module's own Phase 992 rewrite was
# verified against (same real campaign "3", Turns 1-4, Kingdoms 0-2) --
# legitimately reconstructed, byte-for-byte, from the delivered
# decode's own per-field raw_hex trail and independently confirmed
# against its own declared SHA-256 for each file (the originals
# themselves weren't included in that delivery).
ALL_12_SAMPLES = (T1_K0, T1_K1, T1_K2, T2_K0, T2_K1, T2_K2, T3_K0, T3_K1, T3_K2, T4_K0, T4_K1, T4_K2)

REAL_KING_NAMES = [
    "Babba Sissoko",
    "Uga-Buga Makumb",
    None,  # "Bradibo I" at Turn 1, "Bradipo I" at Turn 2 -- see its own test.
    "Kwoth",
    "Hokuto",
    "Prometeo",
    "Kahn",
    "Giovanna d'Arco",
    "Circe",
    "Agesilao",
]


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_parses_every_real_fixture_without_error(fixture):
    world = parse_xk_world(fixture)
    assert world.header.format_revision == SUPPORTED_FORMAT_REVISION
    assert world.globals.game_version == SUPPORTED_GAME_VERSION


# field_counts: (leader_cards, partial_leader_cards, provinces, features,
# treasures, armies, discoveries) -- matches the delivered material's own
# verification table exactly, for all 12 real samples in the corpus.
_EXPECTED_FIELD_COUNTS: dict[Path, tuple[int, int, int, int, int, int, int]] = {
    T1_K0: (3, 4, 7, 2, 1, 218, 0),
    T1_K1: (3, 4, 7, 2, 1, 218, 0),
    T1_K2: (3, 4, 7, 2, 1, 218, 0),
    T2_K0: (4, 5, 13, 2, 1, 247, 0),
    T2_K1: (3, 5, 12, 2, 1, 247, 0),
    T2_K2: (3, 6, 12, 3, 1, 247, 1),
    T3_K0: (6, 8, 20, 3, 2, 259, 0),
    T3_K1: (5, 9, 19, 2, 1, 259, 0),
    T3_K2: (4, 5, 14, 3, 2, 259, 1),
    T4_K0: (12, 5, 26, 8, 4, 281, 0),
    T4_K1: (8, 7, 24, 3, 1, 281, 0),
    T4_K2: (4, 6, 16, 4, 1, 281, 3),
}


@pytest.mark.parametrize("fixture", ALL_12_SAMPLES)
def test_parses_every_sample_of_the_full_12_file_corpus_with_the_right_field_counts(fixture):
    world = parse_xk_world(fixture)
    actual = (
        len(world.leader_cards),
        len(world.partial_leader_cards),
        len(world.provinces),
        len(world.features),
        len(world.treasures),
        len(world.armies),
        len(world.discoveries),
    )
    assert actual == _EXPECTED_FIELD_COUNTS[fixture]


@pytest.mark.parametrize("fixture", ALL_12_SAMPLES)
def test_no_treasure_in_the_real_corpus_exercises_the_trcharges_branch(fixture):
    # Confirmed by the delivered disassembly evidence (raw 0x40558) to be
    # a real, gated field (ordinal in [70, 92)) -- just never hit by any
    # of these 12 real samples.
    for treasure in parse_xk_world(fixture).treasures:
        assert treasure.trcharges is None


def test_discoveries_use_the_real_0xfe01_legacy_word_not_a_plain_boolean():
    discoveries = parse_xk_world(T2_K2).discoveries
    assert len(discoveries) == 1
    assert discoveries[0].feature_id == 2
    assert (discoveries[0].legacy_word & 0xFFFF) == 0xFE01


def test_discoveries_accumulate_turn_over_turn_for_kingdom_2():
    t2 = {d.feature_id for d in parse_xk_world(T2_K2).discoveries}
    t3 = {d.feature_id for d in parse_xk_world(T3_K2).discoveries}
    t4 = {d.feature_id for d in parse_xk_world(T4_K2).discoveries}
    assert t2 == {2}
    assert t3 == {2}
    assert t4 == {2, 9, 34}


def test_header_kingdom_id_matches_the_filenames_own_k_suffix():
    assert parse_xk_world(T1_K0).header.kingdom_id == 0
    assert parse_xk_world(T1_K1).header.kingdom_id == 1
    assert parse_xk_world(T2_K0).header.kingdom_id == 0
    assert parse_xk_world(T2_K1).header.kingdom_id == 1


def test_globals_game_turn_matches_the_filenames_own_t_prefix():
    assert parse_xk_world(T1_K0).globals.game_turn == 1
    assert parse_xk_world(T1_K1).globals.game_turn == 1
    assert parse_xk_world(T2_K0).globals.game_turn == 2
    assert parse_xk_world(T2_K1).globals.game_turn == 2


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_globals_king_count_matches_the_real_10_kingdom_campaign(fixture):
    assert parse_xk_world(fixture).globals.king_count == 10


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_globals_leader_capacity_is_100(fixture):
    assert parse_xk_world(fixture).globals.leader_capacity == 100


def test_globals_board_bounds_match_the_real_18x9_default_board():
    globals_ = parse_xk_world(T1_K0).globals
    assert (globals_.board_left, globals_.board_right) == (0, 17)
    assert (globals_.board_top, globals_.board_bottom) == (0, 8)


def test_rejects_a_file_too_short_for_the_header(tmp_path):
    truncated = tmp_path / "XK3__T1.K0"
    truncated.write_bytes(b"\x00" * 3)

    with pytest.raises(XKParseError):
        parse_xk_world(truncated)


def test_rejects_an_unsupported_format_revision(tmp_path):
    bad = tmp_path / "XK3__T1.K0"
    bad.write_bytes((99).to_bytes(2, "little") + b"\x00" + (0).to_bytes(2, "little"))

    with pytest.raises(XKParseError, match="format_revision"):
        parse_xk_world(bad)


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_name_table_starts_at_the_confirmed_offset(fixture):
    data = fixture.read_bytes()
    assert data[XK_NAME_TABLE_OFFSET : XK_NAME_TABLE_OFFSET + 14] == b"\rBabba Sissoko"


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_every_king_is_always_known_by_their_real_name(fixture):
    names = parse_xk_world(fixture).leader_names
    for king_id, real_name in enumerate(REAL_KING_NAMES):
        if real_name is not None:
            assert names[king_id] == real_name


def test_king_2s_name_is_spelled_differently_between_turn_1_and_turn_2():
    # A genuine, reproducible spelling correction inside this one real
    # campaign's own data between turns 1 and 2 -- not a parser quirk.
    assert parse_xk_world(T1_K0).leader_names[2] == "Bradibo I"
    assert parse_xk_world(T1_K1).leader_names[2] == "Bradibo I"
    assert parse_xk_world(T2_K0).leader_names[2] == "Bradipo I"
    assert parse_xk_world(T2_K1).leader_names[2] == "Bradipo I"


def test_an_unknown_ordinary_hero_reads_as_none_not_the_raw_placeholder():
    assert parse_xk_world(T1_K0).leader_names[10] is None


def test_kingdom_1_knows_its_own_two_starting_companions_by_name():
    names = parse_xk_world(T1_K1).leader_names
    assert names[18] == "Guerin"
    assert names[72] == "Teleko"


def test_full_leader_card_decodes_kingdom_0s_own_king_correctly():
    # King Babba Sissoko: real GW3__T1 facts are Orcish, Undead, Berserk,
    # at his own Home (11,7), with no out-of-range birth coordinate.
    cards = {c.leader_id: c for c in parse_xk_world(T1_K0).leader_cards}
    king = cards[0]

    assert king.temper is Temper.BERSERK
    assert king.alignment is Alignment.UNDEAD
    assert king.coord == HexCoord(11, 7)
    assert king.birth_coord == HexCoord(11, 7)
    assert king.planstart == -1
    assert king.planend == -1


def test_full_leader_card_shows_a_companions_own_reserved_birth_slot():
    # Rainulf (id 25), one of Kingdom 0's own 2 starting Companions: real
    # GW3__T1 facts are Elven, Evil, Berserk, at the Home (11,7), but with
    # an out-of-range birth coordinate (the real "unlanded companion"
    # reserved-slot quirk this project's own GW parser already documents).
    cards = {c.leader_id: c for c in parse_xk_world(T1_K0).leader_cards}
    companion = cards[25]

    assert companion.temper is Temper.BERSERK
    assert companion.alignment is Alignment.EVIL
    assert companion.coord == HexCoord(11, 7)
    assert companion.birth_coord != companion.coord


def test_partial_leader_cards_show_only_coordinates():
    partials = {p.leader_id: p for p in parse_xk_world(T1_K0).partial_leader_cards}
    assert partials[52].coord == HexCoord(11, 6)  # governs Florence
    assert partials[65].coord == HexCoord(10, 7)  # governs the Maldive Sea


def test_leader_races_and_states_vectors_are_leader_capacity_plus_one():
    world = parse_xk_world(T1_K0)
    assert len(world.leader_races) == world.globals.leader_capacity + 1
    assert len(world.leader_states) == world.globals.leader_capacity + 1
    assert world.leader_races[0] is Race.ORCISH  # King Babba Sissoko


def test_province_record_decodes_an_ordinary_known_neighbor():
    provinces = {p.coord: p for p in parse_xk_world(T1_K0).provinces}
    florence = provinces[HexCoord(11, 6)]

    assert florence.name == "Florence"
    assert florence.terrain is Terrain.MTNS
    assert florence.race is Race.DWARVEN
    assert florence.owner_kingdom_id is None
    assert florence.visible_owner_leader_id == 52
    assert florence.tax is None


def test_province_record_decodes_an_ungoverned_neighbor_distinctly_from_unowned():
    # Redwood: no ownership information at all (ownership_marker == 0xFE),
    # distinct from Florence's "visibly ungoverned" (visible_owner == 0xFF).
    provinces = {p.coord: p for p in parse_xk_world(T1_K0).provinces}
    redwood = provinces[HexCoord(11, 8)]

    assert redwood.owner_kingdom_id is None
    assert redwood.visible_owner_leader_id is None


def test_province_record_decodes_kingdom_0s_own_home_with_full_economics():
    provinces = {p.coord: p for p in parse_xk_world(T1_K0).provinces}
    piratum = provinces[HexCoord(11, 7)]

    assert piratum.owner_kingdom_id == 0
    assert piratum.visible_owner_leader_id is None
    assert piratum.exploration_percent == 100
    assert piratum.tax == 10
    assert piratum.recruit_type_1 is ArmyType.PHALANX
    assert piratum.recruit_type_2 is ArmyType.WARG_RIDERS


def test_province_record_gives_a_newly_conquered_province_the_owned_shape_too():
    # By Turn 2, Kingdom 0 has taken Redwood (real GW3__T2 data) --
    # exploration_percent is a real, independently varying value (8%),
    # not a Home-only fixed 100.
    provinces = {p.coord: p for p in parse_xk_world(T2_K0).provinces}
    redwood = provinces[HexCoord(11, 8)]

    assert redwood.owner_kingdom_id == 0
    assert redwood.exploration_percent == 8
    assert redwood.tax == 2
    assert redwood.recruit_type_1 is ArmyType.TROLLS
    assert redwood.recruit_type_2 is None


def test_province_record_decodes_a_sea_province_with_no_race():
    provinces = {p.coord: p for p in parse_xk_world(T2_K0).provinces}
    orca_sea = provinces[HexCoord(13, 7)]

    assert orca_sea.terrain is Terrain.SEA
    assert orca_sea.race is Race.NO_RACE


def test_feature_records_decode_both_of_kingdom_0s_own_home_features():
    features = {f.feature_id: f for f in parse_xk_world(T1_K0).features}

    first = features[0]
    assert first.coord == HexCoord(11, 7)
    assert first.monster is Monster.MUMMY
    assert first.engagement_state is MonsterEngagementState.MERCENARY
    assert first.feature_type is FeatureType.TOMB

    second = features[15]
    assert second.monster is Monster.SPECTRE
    assert second.feature_type is FeatureType.CATACOMBS


def test_feature_records_decode_both_of_kingdom_1s_own_home_features():
    features = {f.feature_id: f for f in parse_xk_world(T1_K1).features}

    assert features[1].monster is Monster.NEC_MAGE
    assert features[1].feature_type is FeatureType.ALTAR
    assert features[16].monster is Monster.SWORDSMAN
    assert features[16].feature_type is FeatureType.HOLLOW_TREE


def test_treasure_record_decodes_a_real_magic_item_name():
    treasures = parse_xk_world(T1_K0).treasures
    assert len(treasures) == 1
    record = treasures[0]

    assert record.feature_id == 15
    assert record.treasure is Treasure.WEAPON_2
    assert record.name == "Shadow Sword"
    assert record.trcharges is None  # WEAPON_2's ordinal (36) is outside [70, 92)
    assert record.trowner == 256 + 15  # the real "owned by this feature" convention


def test_treasure_record_does_not_truncate_a_long_name():
    record = parse_xk_world(T1_K1).treasures[0]

    assert record.treasure is Treasure.GOLD_HOARD_LARGE
    assert record.name == "Large Hoard of Gold"


def test_army_record_decodes_kingdom_0s_own_skeletal_home_army():
    # King Babba Sissoko is Undead-aligned, so his Home's own first army
    # is raised Skeletal/Zomboid (status 3).
    armies = [a for a in parse_xk_world(T1_K0).armies if a.coord == HexCoord(11, 7)]
    assert len(armies) == 4

    zomboid = next(a for a in armies if a.status == 3)
    assert zomboid.race is Race.ORCISH
    assert zomboid.army_type is ArmyType.PHALANX
    assert zomboid.commanded_by_leader_id is None


def test_army_record_decodes_the_real_mercenary_army_a_phase_988_991_guess_missed():
    # Phase 988-991's own hand-derived 8-byte army shape never found this
    # real Mercenary (status 2) army at all -- its own field order guess
    # (quality/state swapped and partly duplicated) didn't generalize.
    armies = [a for a in parse_xk_world(T1_K0).armies if a.coord == HexCoord(11, 7)]
    mercenary = next(a for a in armies if a.status == 2)

    assert mercenary.race is Race.HUMAN
    assert mercenary.army_type is ArmyType.CHARIOTS
    assert mercenary.commanded_by_leader_id is None


def test_army_without_location_details_has_no_coordinate():
    armies = parse_xk_world(T1_K0).armies
    hidden = [a for a in armies if a.coord is None]
    assert hidden  # most of the real 218 armies carry no location details
    for army in hidden:
        assert army.commanded_by_leader_id is None
        assert army.detail_status is None


def test_recruitment_map_covers_every_cell_of_the_real_18x9_board():
    world = parse_xk_world(T1_K0)
    assert len(world.recruitment_map) == 18 * 9


def test_secondary_ability_table_and_liege_extension_are_present():
    world = parse_xk_world(T1_K0)
    assert world.secondary_abilities is not None
    assert len(world.secondary_abilities.levels_by_ability) == 15
    assert all(len(levels) == 6 for levels in world.secondary_abilities.levels_by_ability)
    assert world.liege_extension is not None


def test_secondary_terrain_table_has_its_own_fixed_capacity():
    world = parse_xk_world(T1_K0)
    assert world.secondary_terrain is not None
    assert len(world.secondary_terrain.raw) == 450
