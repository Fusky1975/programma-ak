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
from ak_engine.models.enums import ActionCode
from ak_engine.models.feature import FeatureType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import GOLD_HOARD_DISPLAY_NAME, TREASURE_NAME, Treasure
from ak_engine.parser.gw_world import (
    TERMOD_PLAGUE_EFF_MASK,
    DiplomaticRelation,
    parse_gw_armies,
    parse_gw_features,
    parse_gw_king_extensions,
    parse_gw_leaders,
    parse_gw_world,
)
from ak_engine.parser.k1_moves import parse_k1_moves_file
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
T11_K0 = FIXTURE_DIR / "XK3__T11.K0"
T11_K1 = FIXTURE_DIR / "XK3__T11.K1"
T11_K2 = FIXTURE_DIR / "XK3__T11.K2"
T12_K0 = FIXTURE_DIR / "XK3__T12.K0"
T12_K1 = FIXTURE_DIR / "XK3__T12.K1"
ALL_FIXTURES = (T1_K0, T1_K1, T2_K0, T2_K1)
# The full real 12-sample corpus this module's own Phase 992 rewrite was
# verified against (same real campaign "3", Turns 1-4, Kingdoms 0-2) --
# legitimately reconstructed, byte-for-byte, from the delivered
# decode's own per-field raw_hex trail and independently confirmed
# against its own declared SHA-256 for each file (the originals
# themselves weren't included in that delivery).
ALL_12_SAMPLES = (T1_K0, T1_K1, T1_K2, T2_K0, T2_K1, T2_K2, T3_K0, T3_K1, T3_K2, T4_K0, T4_K1, T4_K2)
# Phase 1015: 5 more real, user-provided samples from the same campaign,
# much later (Turns 11-12, Kingdom 2 missing from Turn 12 -- only 5 files
# were provided). These snapshots are substantially larger (22-25 full
# leader cards and 30-121 known provinces, vs. 2-12 and 2-9 in the
# original corpus) and were the first real data able to falsify several
# of this module's own "zero exceptions" claims that the small original
# corpus had never been able to exercise -- see the Phase 1015 module
# docstring addendum.
ALL_17_SAMPLES = ALL_12_SAMPLES + (T11_K0, T11_K1, T11_K2, T12_K0, T12_K1)

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


def test_discoveries_hold_up_at_17_file_scale_including_resolved_features():
    # Phase 1021: the Turn 11-12 corpus extends the real discoveries
    # sample 27x (81 records, up from 3). legacy_word remains exactly
    # 0xFE01 throughout -- reinforcing, not contradicting, the original
    # small sample. The larger sample also shows discoveries can
    # reference a feature_id no longer in this same file's own current
    # features list (60 of 81) -- consistent with the already-confirmed
    # accumulation behavior: discoveries is a permanent historical
    # ledger, features only lists what's still currently live, so a
    # since-resolved feature (treasure claimed, guardian defeated) can
    # drop out of the latter while staying in the former. Every
    # discovered id that *is* still live matches its own known
    # feature's own feature_id exactly (21 of 21), consistent with
    # feature_id using the same real GW-list-index convention
    # XKFeatureRecord.feature_id itself already confirms (Phase 994).
    total = 0
    stale = 0
    live_matches = 0
    for fixture in (T11_K0, T11_K1, T11_K2, T12_K0, T12_K1):
        world = parse_xk_world(fixture)
        known_feature_ids = {feat.feature_id for feat in world.features}
        for d in world.discoveries:
            total += 1
            assert (d.legacy_word & 0xFFFF) == 0xFE01
            if d.feature_id in known_feature_ids:
                live_matches += 1
            else:
                stale += 1
    assert total == 81
    assert stale == 60
    assert live_matches == 21


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


def test_king_titles_match_the_real_gw_king_extension_fields_at_turn_1():
    # Cross-checked directly against parser/gw_world.py's own already-
    # confirmed GWKingExtension.title_prefix/title_suffix for the same
    # real GW3__T1 campaign.
    titles = parse_xk_world(T1_K0).king_titles
    assert titles.prefix_by_king_id[0] == "Lord"
    assert titles.suffix_by_king_id[0] == "Master of the s"  # real 15-char truncation
    assert titles.prefix_by_king_id[1] == "Shaman"
    assert titles.suffix_by_king_id[1] == "Lord of the stu"  # real 15-char truncation


def test_king_titles_change_by_turn_4_matching_the_real_gw_data():
    # Short enough this time to show untruncated -- same real values in
    # both XK and GW3__T4.
    titles = parse_xk_world(T4_K0).king_titles
    assert titles.suffix_by_king_id[0] == "Master orango"
    assert titles.suffix_by_king_id[1] == "Stuffy doll"


def test_king_titles_are_public_identical_across_different_kingdoms_own_files():
    assert parse_xk_world(T1_K0).king_titles == parse_xk_world(T1_K1).king_titles


def test_king_titles_table_has_12_slots_with_unused_ones_blank():
    titles = parse_xk_world(T1_K0).king_titles
    assert len(titles.prefix_by_king_id) == 12
    assert len(titles.suffix_by_king_id) == 12
    assert titles.prefix_by_king_id[9] == ""  # King 9 has no real title
    assert titles.prefix_by_king_id[11] == ""  # reserve slot, never a real King


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
    # is raised Skeletal/Zomboid.
    armies = [a for a in parse_xk_world(T1_K0).armies if a.coord == HexCoord(11, 7)]
    assert len(armies) == 4

    zomboid = next(a for a in armies if a.status is MonsterEngagementState.ZOMBOID)
    assert zomboid.race is Race.ORCISH
    assert zomboid.army_type is ArmyType.PHALANX
    assert zomboid.commanded_by_leader_id is None
    assert zomboid.detail_status is MonsterEngagementState.ZOMBOID


def test_army_record_decodes_the_real_mercenary_army_a_phase_988_991_guess_missed():
    # Phase 988-991's own hand-derived 8-byte army shape never found this
    # real Mercenary army at all -- its own field order guess (quality/
    # state swapped and partly duplicated) didn't generalize.
    armies = [a for a in parse_xk_world(T1_K0).armies if a.coord == HexCoord(11, 7)]
    mercenary = next(a for a in armies if a.status is MonsterEngagementState.MERCENARY)

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


def test_army_status_matches_the_real_gw_engagement_state_at_scale():
    # Index-exact pairing against every one of the real 218 GW3__T1
    # armies (not just the 4 at one Home) -- zero exceptions.
    world = parse_xk_world(T1_K0)
    gw_armies = parse_gw_armies(Path("/home/user/programma-ak/GW3__T1"))
    checked = 0
    for army in world.armies:
        gw_index = army.army_index if army.army_index < 255 else army.army_index - 1
        gw_army = gw_armies[gw_index]
        assert army.race == gw_army.race
        assert army.army_type == gw_army.army_type
        assert army.status is gw_army.state
        if army.detail_status is not None:
            assert army.detail_status is gw_army.state
        checked += 1
    assert checked == 218


_TURN_TO_REAL_GW_FILE = {
    1: Path("/home/user/programma-ak/GW3__T1"),
    2: Path("/home/user/programma-ak/GW3__T2"),
    3: Path("/home/user/programma-ak/GW3__T3"),
    4: Path("/home/user/programma-ak/GW3__T4"),
}


def test_quality_or_mask_is_a_real_masking_sentinel_not_a_clean_ordinal():
    # A nonzero quality_or_mask always matches the real Quality.value
    # exactly; zero is a real masking sentinel covering every possible
    # real quality, not literally Quality.DEPLETED -- confirmed across
    # the full 12-file corpus (one Home's own armies alone isn't varied
    # enough to show the ambiguity) -- see module docstring's own
    # Phase 994 addendum.
    masked_real_qualities = set()
    gw_cache = {}
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_armies(_TURN_TO_REAL_GW_FILE[turn])
        gw_armies = gw_cache[turn]
        for army in world.armies:
            gw_index = army.army_index if army.army_index < 255 else army.army_index - 1
            gw_army = gw_armies[gw_index]
            if army.quality_or_mask == 0:
                masked_real_qualities.add(gw_army.quality.value)
            else:
                assert army.quality_or_mask == gw_army.quality.value
    assert len(masked_real_qualities) > 1  # genuinely ambiguous, not a hidden constant


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


_TURN_TO_REAL_GW_FEATURES = {
    1: Path("/home/user/programma-ak/GW3__T1"),
    2: Path("/home/user/programma-ak/GW3__T2"),
    3: Path("/home/user/programma-ak/GW3__T3"),
    4: Path("/home/user/programma-ak/GW3__T4"),
}


def test_feature_type_matches_the_real_gw_feature_at_scale():
    # feature_id lines up exactly with parse_gw_features()'s own 0-based
    # list position for the same real world file -- the same proven
    # technique Phase 994 used for armies, applied here to every one of
    # the 36 real Feature records across the full 12-file corpus.
    gw_cache = {}
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_features(_TURN_TO_REAL_GW_FEATURES[turn])
        gw_features = gw_cache[turn]
        for feature in world.features:
            gw_feature = gw_features[feature.feature_id]
            assert feature.feature_type == gw_feature.feature_type
            assert feature.unknown_962a == 0
            checked += 1
    assert checked == 36


def test_defeated_feature_guardian_reports_nomonster_mercenary_not_dead():
    # Feature 15 (Piratum's Catacombs, Kingdom 0's Home): its Spectre
    # guardian was defeated between Turn 1 and Turn 2 -- the only dead
    # Feature anywhere in this campaign's Turns 1-4. Real GW keeps the
    # monster's identity and reports engagement_state=DEAD; XK instead
    # reports a real, reproducible "cleared" convention. Confirmed
    # across 3 independent XK snapshots of this same single real event.
    gw_features_t1 = parse_gw_features(Path("/home/user/programma-ak/GW3__T1"))
    assert gw_features_t1[15].monster is Monster.SPECTRE

    for fixture, gw_path in (
        (T2_K0, Path("/home/user/programma-ak/GW3__T2")),
        (T3_K0, Path("/home/user/programma-ak/GW3__T3")),
        (T4_K0, Path("/home/user/programma-ak/GW3__T4")),
    ):
        world = parse_xk_world(fixture)
        feature = next(f for f in world.features if f.feature_id == 15)
        assert feature.monster is Monster.NOMONSTER
        assert feature.engagement_state is MonsterEngagementState.MERCENARY
        assert feature.feature_type is FeatureType.CATACOMBS

        gw_features = parse_gw_features(gw_path)
        assert gw_features[15].engagement_state is MonsterEngagementState.DEAD


def test_shadow_sword_trowner_leaves_feature_held_once_guardian_falls():
    # Companion to the guardian-cleared finding: the same Feature 15's
    # own Treasure record (the Shadow Sword) moves from the documented
    # 256+feature_id feature-held convention (271) at Turn 1 to 0 once
    # the guardian is defeated.
    world_t1 = parse_xk_world(T1_K0)
    treasure_t1 = next(t for t in world_t1.treasures if t.feature_id == 15)
    assert treasure_t1.trowner == 256 + 15

    for fixture in (T2_K0, T3_K0, T4_K0):
        world = parse_xk_world(fixture)
        treasure = next(t for t in world.treasures if t.feature_id == 15)
        assert treasure.trowner == 0


def test_treasure_trowner_leader_held_convention_confirmed_by_quintilian():
    # Independent confirmation (not the King-id-0-coincident Shadow Sword
    # case) of the disassembly documentation's own asserted rule: a
    # leader-held item's trowner is that leader's own raw leader_id, not
    # a derived value. XK3__T3.K2 carries a Treasure record whose own
    # feature_id (130) is past this world's real 128-Feature range --
    # not bound to any currently-extant Feature -- with trowner=99.
    # Leader 99 is a real, ordinary (non-King) hero in that same file.
    world = parse_xk_world(T3_K2)
    treasure = next(t for t in world.treasures if t.feature_id == 130)
    assert treasure.treasure == Treasure.LEADERSHIP_HUMAN
    assert treasure.trowner == 99

    assert world.globals.king_count == 10  # King ids are 0-9; 99 can't be one
    assert world.leader_names[99] == "Quintilian"
    assert world.leader_races[99] == Race.HUMAN
    leader_card = next(lc for lc in world.leader_cards if lc.leader_id == 99)
    assert leader_card.client_owner == 2  # Kingdom 2 -- this file's own Kingdom

    gw_leaders = parse_gw_leaders(Path("/home/user/programma-ak/GW3__T3"))
    gw_quintilian = next(leader for leader in gw_leaders if leader.name == "Quintilian")
    assert gw_quintilian.is_king is False
    assert gw_quintilian.kingdom_id == 2


_TURN_TO_REAL_GW_LEADERS = {
    1: Path("/home/user/programma-ak/GW3__T1"),
    2: Path("/home/user/programma-ak/GW3__T2"),
    3: Path("/home/user/programma-ak/GW3__T3"),
    4: Path("/home/user/programma-ak/GW3__T4"),
    11: Path("/home/user/programma-ak/GW3__T11"),
    12: Path("/home/user/programma-ak/GW3__T12"),
}


def test_general_merit_matches_gw_general_merit_not_gw_admiral_merit():
    # The delivered disassembly material names this slot "admiral_merit"
    # on a corpus-correspondence guess, by its own admission (only the
    # far pointer address, 82E2, is disassembly-certain). Cross-checked
    # at scale against the real GW ground truth, it in fact equals GW's
    # own general_merit field exactly, every time -- not GW's own,
    # separate admiral_merit field, which only coincidentally agrees
    # when the two happen to hold the same value. Renamed accordingly.
    gw_cache = {}
    checked = 0
    agrees_with_general = 0
    agrees_with_admiral = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_leaders = gw_cache[turn]
        for card in world.leader_cards:
            if card.leader_id >= len(gw_leaders):
                continue
            gw = gw_leaders[card.leader_id]
            assert card.general_merit == gw.general_merit
            assert card.defender_merit == gw.defender_merit
            checked += 1
            if card.general_merit == gw.general_merit:
                agrees_with_general += 1
            if card.general_merit == gw.admiral_merit:
                agrees_with_admiral += 1
    assert checked == 58
    assert agrees_with_general == 58
    assert agrees_with_admiral < checked  # not merely a renamed duplicate check


def test_leader_feature_discoveries_points_and_white_magic_match_at_scale():
    gw_cache = {}
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_leaders = gw_cache[turn]
        for card in world.leader_cards:
            if card.leader_id >= len(gw_leaders):
                continue
            gw = gw_leaders[card.leader_id]
            assert card.lfdisc == gw.feature_discoveries
            assert card.ldiscp == gw.discovery_points
            assert card.lwmsp == gw.white_magic_service_points
            checked += 1
    assert checked == 58


def test_skills_and_aptitudes_pair_with_the_real_gw_skill_table_at_scale():
    # skills[i]/aptitudes[i] (LEADER_ABILITY_ORDER's first 15 real
    # abilities) equal GWLeaderRecord.skills.raw_values[2*i]/[2*i+1] for
    # the same real leader in the vast majority of real pairs; the
    # residual drift is explained (not just tolerated) below.
    gw_cache = {}
    total_pairs = 0
    mismatched_pairs = 0
    gw_at_least_as_high = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_leaders = gw_cache[turn]
        for card in world.leader_cards:
            if card.leader_id >= len(gw_leaders):
                continue
            gw = gw_leaders[card.leader_id]
            raw = gw.skills.raw_values
            # Slot 15 (noabil) is always (0, 0) padding, not real data.
            assert card.skills[15] == 0
            assert card.aptitudes[15] == 0
            for i in range(15):
                gskill, gapt = raw[2 * i], raw[2 * i + 1]
                xskill, xapt = card.skills[i], card.aptitudes[i]
                total_pairs += 1
                if (gskill, gapt) != (xskill, xapt):
                    mismatched_pairs += 1
                    if gskill >= xskill and gapt >= xapt:
                        gw_at_least_as_high += 1
    assert total_pairs == 870
    # The vast majority of real pairs match exactly.
    assert mismatched_pairs / total_pairs < 0.1
    # Of the mismatches, GW's own same-turn value is (almost) always
    # >= XK's in both dimensions -- consistent with GW reflecting a
    # later point in that turn's own processing than the XK snapshot,
    # not a pairing-order bug.
    assert gw_at_least_as_high / mismatched_pairs > 0.9


def test_sex_flags_and_leader_races_real_value_ranges():
    sex_flags_values = set()
    race_values = set()
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        for card in world.leader_cards:
            sex_flags_values.add(card.sex_flags)
        race_values.update(world.leader_races)
    # No real female leader exists in this campaign -- the bitfield's
    # own nonzero semantics remain genuinely untested, not confirmed 0.
    assert sex_flags_values == {0}
    assert race_values == {Race.DWARVEN, Race.ELVEN, Race.HUMAN, Race.ORCISH}


def test_leader_states_every_full_card_slot_reads_one():
    # leader_states' own per-value meaning is still genuinely open (see
    # module docstring's Phase 996 addendum), but this one sub-rule is
    # confirmed with zero exceptions across the full corpus: a leader_id
    # backing a full card always reads exactly 1 in leader_states.
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        for card in world.leader_cards:
            assert world.leader_states[card.leader_id] == 1
            checked += 1
    assert checked == 58


def test_leader_states_untracked_real_ids_are_always_exactly_seven():
    # Phase 1012: sharpens Phase 996's own ">95%" approximation into a
    # complete, zero-exception rule. Every untracked slot within the
    # real 0..leader_capacity-1 id range reads exactly 7; the single
    # exception in the whole corpus is always the structural padding
    # slot at index leader_capacity itself (never a real leader id).
    real_untracked = 0
    real_untracked_seven = 0
    padding_slot_values = set()
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        leader_capacity = world.globals.leader_capacity
        tracked_ids = {c.leader_id for c in world.leader_cards} | {
            c.leader_id for c in world.partial_leader_cards
        }
        for i, state in enumerate(world.leader_states):
            if i in tracked_ids:
                continue
            if i == leader_capacity:
                padding_slot_values.add(state)
                continue
            real_untracked += 1
            if state == 7:
                real_untracked_seven += 1
    assert real_untracked == real_untracked_seven == 1074
    assert padding_slot_values == {0}


_TURN_TO_REAL_GW_PROVINCES = {
    1: Path("/home/user/programma-ak/GW3__T1"),
    2: Path("/home/user/programma-ak/GW3__T2"),
    3: Path("/home/user/programma-ak/GW3__T3"),
    4: Path("/home/user/programma-ak/GW3__T4"),
    11: Path("/home/user/programma-ak/GW3__T11"),
    12: Path("/home/user/programma-ak/GW3__T12"),
}


def test_effects_bitmask_matches_real_gw_termod_at_scale():
    # Matched by each province's own real, unique name (both formats
    # carry one) -- unlike armies/features/leaders, there's no shared
    # index to zip by here. unknown_9197_word is fully decoded by this
    # cross-check: it's exactly GW's own effects_bitmask (termod).
    # Phase 1015's own Turn 11-12 corpus extends this to 651 real checks
    # (from the original 177), still zero exceptions.
    gw_cache = {}
    checked = 0
    nonzero_checked = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = {p.name: p for p in parse_gw_world(_TURN_TO_REAL_GW_PROVINCES[turn])}
        gw_by_name = gw_cache[turn]
        for province in world.provinces:
            gw = gw_by_name.get(province.name)
            if gw is None:
                continue
            assert province.effects_bitmask == gw.effects_bitmask
            checked += 1
            if province.effects_bitmask != 0:
                nonzero_checked += 1
    assert checked == 651
    assert nonzero_checked == 14


def test_mermaid_and_icaria_sea_effects_bitmask_is_a_real_plague_level():
    world = parse_xk_world(T2_K1)
    provinces = {p.name: p for p in world.provinces}
    for name in ("the Mermaid Sea", "the Icaria Sea"):
        province = provinces[name]
        assert province.effects_bitmask == 0x40
        assert province.effects_bitmask & TERMOD_PLAGUE_EFF_MASK == 0x40
        assert (province.effects_bitmask & TERMOD_PLAGUE_EFF_MASK) >> 4 == 4


def test_province_terrain_and_race_match_real_gw_at_scale():
    gw_cache = {}
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = {p.name: p for p in parse_gw_world(_TURN_TO_REAL_GW_PROVINCES[turn])}
        gw_by_name = gw_cache[turn]
        for province in world.provinces:
            gw = gw_by_name.get(province.name)
            if gw is None:
                continue
            assert province.terrain == gw.terrain
            assert province.race == gw.race
            checked += 1
    assert checked == 177


def test_owned_province_economics_match_real_gw_at_scale():
    gw_cache = {}
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = {p.name: p for p in parse_gw_world(_TURN_TO_REAL_GW_PROVINCES[turn])}
        gw_by_name = gw_cache[turn]
        for province in world.provinces:
            if province.tax is None:
                continue
            gw = gw_by_name.get(province.name)
            if gw is None:
                continue
            assert province.tax == gw.tax
            assert province.recruit_type_1 == gw.recruit_type_1
            assert province.recruit_type_2 == gw.recruit_type_2
            checked += 1
    assert checked == 59


def test_province_ownership_matches_real_gw_governor_at_scale():
    # owner_kingdom_id (the full-economics shape) must match the real
    # Kingdom of GW's own governor_leader_id; visible_owner_leader_id
    # (the visible-owner-only shape) must match that leader_id directly.
    gw_cache = {}
    leaders_cache = {}
    owner_checked = 0
    visible_checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = {p.name: p for p in parse_gw_world(_TURN_TO_REAL_GW_PROVINCES[turn])}
            leaders_cache[turn] = parse_gw_leaders(_TURN_TO_REAL_GW_PROVINCES[turn])
        gw_by_name = gw_cache[turn]
        leaders = leaders_cache[turn]
        for province in world.provinces:
            gw = gw_by_name.get(province.name)
            if gw is None:
                continue
            if province.owner_kingdom_id is not None:
                assert gw.governor_leader_id is not None
                assert leaders[gw.governor_leader_id].kingdom_id == province.owner_kingdom_id
                owner_checked += 1
            elif province.visible_owner_leader_id is not None:
                assert province.visible_owner_leader_id == gw.governor_leader_id
                visible_checked += 1
    assert owner_checked == 59
    assert visible_checked == 75


def test_quality_or_mask_revealed_exactly_for_this_kingdoms_own_leader_commanded_armies():
    # On the original 12-sample corpus (Turns 1-4), quality_or_mask was
    # nonzero (revealed) iff the army's real commander
    # (GWArmyRecord.commanded_by_leader_id) belonged to this file's own
    # Kingdom -- zero exceptions either direction. The counts below are
    # restricted to that original corpus to keep this exact historical
    # regression check; see
    # test_quality_or_mask_revealed_exactly_for_full_card_commanded_armies
    # below for the corrected, full-card-based rule that also holds over
    # the larger Phase 1015 corpus (Turns 11-12), where this "own
    # Kingdom" framing is no longer exception-free -- see the Phase 1015
    # module docstring addendum.
    gw_cache = {}
    leaders_cache = {}
    own_revealed = 0
    own_masked = 0
    other_revealed = 0
    other_masked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        kid = world.header.kingdom_id
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_armies(_TURN_TO_REAL_GW_LEADERS[turn])
            leaders_cache[turn] = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_armies = gw_cache[turn]
        leaders = leaders_cache[turn]
        for army in world.armies:
            gw_index = army.army_index if army.army_index < 255 else army.army_index - 1
            gw_army = gw_armies[gw_index]
            if gw_army.commanded_by_leader_id is None:
                continue
            owner_kid = leaders[gw_army.commanded_by_leader_id].kingdom_id
            revealed = army.quality_or_mask != 0
            if owner_kid == kid:
                own_revealed += int(revealed)
                own_masked += int(not revealed)
            else:
                other_revealed += int(revealed)
                other_masked += int(not revealed)
    assert (own_revealed, own_masked) == (77, 0)
    assert (other_revealed, other_masked) == (0, 1480)


def test_quality_or_mask_revealed_exactly_for_full_card_commanded_armies():
    # Phase 1015 correction: re-run across the larger 17-sample corpus
    # (adding Turns 11-12), the previous rule -- revealed iff the
    # commander's real GW kingdom_id matches this file's own Kingdom --
    # is no longer exception-free (2 "own but masked", 25 "other but
    # revealed" real cases). The real discriminator, confirmed with zero
    # exceptions across all 2274 real leader-commanded armies in the
    # full 17-file corpus, is not GW's raw kingdom_id at all: it is
    # whether the commanding leader has a FULL card in the *viewing*
    # Kingdom's own XK file.
    #
    # This also explains every one of the 27 apparent counterexamples:
    # - The 25 "other but revealed" cases are all armies of monster-type
    #   "pet" troops (Dragon Wings, Eagle Wings, Trolls, Warg Riders,
    #   hired Orcish Phalanxes) commanded by an enemy Hero who, by Turn
    #   11-12, has become familiar enough (presumably through repeated
    #   contact/combat) to have earned a full card in the viewing
    #   Kingdom's own file -- despite still genuinely serving a
    #   different, real Kingdom in GW's own ground truth.
    # - The 2 "own but masked" cases are the mirror image: a real member
    #   of the viewing Kingdom itself (GW kingdom_id matches) who
    #   nonetheless has no card at all (leader_states == 7, "untracked")
    #   in that Kingdom's own snapshot -- consistent with this project's
    #   own Phase 1014 finding that leader tracking/coverage is a
    #   genuinely dynamic, snapshot-specific property, not a fixed
    #   leader<->Kingdom relationship.
    #
    # In the original, smaller 12-sample corpus "own Kingdom" and "has a
    # full card here" always coincided (no Hero had yet been tracked
    # long enough to become fully known to a foreign Kingdom), which is
    # why the original, narrower rule looked exception-free there.
    gw_cache = {}
    revealed_count = 0
    masked_count = 0
    exceptions = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_armies(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_armies = gw_cache[turn]
        full_card_ids = {card.leader_id for card in world.leader_cards}
        for army in world.armies:
            gw_index = army.army_index if army.army_index < 255 else army.army_index - 1
            gw_army = gw_armies[gw_index]
            if gw_army.commanded_by_leader_id is None:
                continue
            revealed = army.quality_or_mask != 0
            has_full_card = gw_army.commanded_by_leader_id in full_card_ids
            if has_full_card != revealed:
                exceptions += 1
            if revealed:
                revealed_count += 1
            else:
                masked_count += 1
    assert exceptions == 0
    assert (revealed_count, masked_count) == (274, 1888)


def test_quality_or_mask_revealed_exactly_for_garrisons_in_this_kingdoms_own_provinces():
    # A leaderless HIRED or ZOMBOID army (a garrison) is revealed iff it
    # sits at a coordinate this file's own province list shows as
    # owned by this Kingdom -- zero exceptions either direction.
    gw_cache = {}
    own_revealed = 0
    own_masked = 0
    other_revealed = 0
    other_masked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        kid = world.header.kingdom_id
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_armies(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_armies = gw_cache[turn]
        prov_by_coord = {p.coord: p for p in world.provinces}
        for army in world.armies:
            gw_index = army.army_index if army.army_index < 255 else army.army_index - 1
            gw_army = gw_armies[gw_index]
            if gw_army.commanded_by_leader_id is not None:
                continue
            if gw_army.state.name not in ("HIRED", "ZOMBOID"):
                continue
            revealed = army.quality_or_mask != 0
            province = prov_by_coord.get(gw_army.coord)
            is_own_province = province is not None and province.owner_kingdom_id == kid
            if is_own_province:
                own_revealed += int(revealed)
                own_masked += int(not revealed)
            else:
                other_revealed += int(revealed)
                other_masked += int(not revealed)
    assert (own_revealed, own_masked) == (11, 0)
    assert (other_revealed, other_masked) == (0, 754)


def test_quality_or_mask_is_always_masked_for_dead_leaderless_armies():
    gw_cache = {}
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_armies(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_armies = gw_cache[turn]
        for army in world.armies:
            gw_index = army.army_index if army.army_index < 255 else army.army_index - 1
            gw_army = gw_armies[gw_index]
            if gw_army.commanded_by_leader_id is not None or gw_army.state.name != "DEAD":
                continue
            assert army.quality_or_mask == 0
            checked += 1
    assert checked == 582


def test_quality_or_mask_mercenary_armies_are_the_one_real_exception():
    # Mercenary-state leaderless armies do NOT follow the ownership
    # rule: checked directly, both directions are contradicted (some
    # own-province ones are masked; some other-Kingdom ones are
    # revealed). Documented as a genuine, unresolved exception rather
    # than forced into the otherwise-universal rule.
    gw_cache = {}
    revealed = 0
    masked = 0
    own_province_masked_examples = 0
    other_province_revealed_examples = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        kid = world.header.kingdom_id
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_armies(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_armies = gw_cache[turn]
        prov_by_coord = {p.coord: p for p in world.provinces}
        for army in world.armies:
            gw_index = army.army_index if army.army_index < 255 else army.army_index - 1
            gw_army = gw_armies[gw_index]
            if gw_army.commanded_by_leader_id is not None or gw_army.state.name != "MERCENARY":
                continue
            is_revealed = army.quality_or_mask != 0
            revealed += int(is_revealed)
            masked += int(not is_revealed)
            province = prov_by_coord.get(gw_army.coord)
            is_own_province = province is not None and province.owner_kingdom_id == kid
            if is_own_province and not is_revealed:
                own_province_masked_examples += 1
            if not is_own_province and is_revealed:
                other_province_revealed_examples += 1
    assert (revealed, masked) == (102, 9)
    assert own_province_masked_examples > 0
    assert other_province_revealed_examples > 0


_VARYING_UNNAMED_GLOBAL_KEYS = (
    "DS_C2F6", "DS_C2F8", "DS_C2FC", "DS_C2FE", "DS_C308", "DS_C316",
    "DS_C330", "DS_C332", "DS_C334", "DS_C336",
    "DS_C388", "DS_C38A", "DS_C38C", "DS_C38E", "DS_C390", "DS_C392",
    "DS_C394", "DS_C396", "DS_C398", "DS_C39A", "DS_C39C", "DS_C39E",
    "DS_C3A0", "DS_C3A2", "DS_C3A4", "DS_C3A6", "DS_C3A8", "DS_C3B4",
    "DS_C3B6", "DS_C3B8", "DS_C3BA", "DS_C3BC", "DS_C3BE", "DS_C3C0",
    "DS_C3C2", "DS_C3C4", "DS_C3C6", "DS_C3C8", "DS_C3CA", "DS_C3CC",
    "DS_C3D2", "DS_C3D4", "DS_C3D6", "DS_C3D8", "DS_C3DA", "DS_C3DC",
    "DS_C3DE", "DS_C3E0", "DS_C3E2", "DS_C3E4", "DS_C3E6", "DS_C3E8",
    "DS_C3EC", "DS_C3EE", "DS_C3F0", "DS_C3F2", "DS_C3F4", "DS_C3F6",
    "DS_C3F8", "DS_C3FA",
)  # noqa: E501


def test_unnamed_varying_globals_are_identical_across_this_turns_three_kingdoms():
    # Every unnamed global word that varies at all is the same across
    # all 3 of this campaign's own Kingdom files for a given turn --
    # turn-level/shared state, not a per-Kingdom secret (Phase 999).
    for turn, fixtures in ((1, (T1_K0, T1_K1, T1_K2)), (2, (T2_K0, T2_K1, T2_K2)),
                            (3, (T3_K0, T3_K1, T3_K2)), (4, (T4_K0, T4_K1, T4_K2))):
        worlds = [parse_xk_world(f) for f in fixtures]
        for key in _VARYING_UNNAMED_GLOBAL_KEYS:
            values = {w.globals.values[key] for w in worlds}
            assert len(values) == 1, f"turn {turn} key {key} differs across kingdoms: {values}"


def test_flags_c4fc_is_leader_id_indexed_not_a_flat_bitmask():
    # flags_c4fc[i] is confirmed 0 for every i that backs neither a full
    # nor a partial character card -- zero exceptions across the corpus
    # -- and the highest nonzero index ever seen is exactly
    # leader_capacity (100), the same N+1 boundary this format's other
    # leader vectors already use.
    max_nonzero_index = -1
    untracked_nonzero = 0
    untracked_checked = 0
    king_nonzero = 0
    king_checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        full_ids = {c.leader_id for c in world.leader_cards}
        partial_ids = {c.leader_id for c in world.partial_leader_cards}
        king_ids = set(range(world.globals.king_count))
        for i in range(world.globals.leader_capacity):
            val = world.globals.flags_c4fc[i]
            if val != 0:
                max_nonzero_index = max(max_nonzero_index, i)
            if i not in full_ids and i not in partial_ids:
                untracked_checked += 1
                if val != 0:
                    untracked_nonzero += 1
            if i in king_ids:
                king_checked += 1
                if val != 0:
                    king_nonzero += 1
    assert untracked_checked > 0
    assert untracked_nonzero == 0
    assert king_checked > 0
    assert king_nonzero == 0
    assert max_nonzero_index <= 100


def test_flags_c4fc_per_hero_value_distribution_at_17_file_scale():
    # Phase 1018: re-run across the larger 17-sample corpus, the real
    # own-Hero sample grows from 25 to 136, still showing only the
    # same 0-5 range with no new hypothesis (several further GW/card
    # fields tried, none correlating -- see the module docstring's own
    # Phase 1018 addendum). Captured here as a regression check on the
    # distribution itself, not a decode -- this field's real role
    # remains genuinely open.
    from collections import Counter

    leaders_cache = {}
    value_counts = Counter()
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in leaders_cache:
            leaders_cache[turn] = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        leaders = leaders_cache[turn]
        for card in world.leader_cards:
            if leaders[card.leader_id].is_king:
                continue
            value_counts[world.globals.flags_c4fc[card.leader_id]] += 1
    assert sum(value_counts.values()) == 136
    assert value_counts == Counter({3: 45, 2: 40, 1: 25, 5: 18, 4: 5, 0: 3})


def test_flags_c3fc_is_mostly_shared_across_kingdoms_with_a_few_real_exceptions():
    # Unlike flags_c4fc, flags_c3fc is not cleanly leader-indexed, but
    # for an ordinary turn (2-4) it's mostly identical across this
    # campaign's 3 Kingdoms, with only a handful of real per-Kingdom
    # byte differences -- Turn 1 (a pre-turn-1 snapshot, like GW3__T1)
    # has an entirely different nonzero-index shape.
    for turn, fixtures in ((2, (T2_K0, T2_K1, T2_K2)), (3, (T3_K0, T3_K1, T3_K2)),
                            (4, (T4_K0, T4_K1, T4_K2))):
        worlds = [parse_xk_world(f) for f in fixtures]
        c3fc = [w.globals.flags_c3fc for w in worlds]
        differing_bytes = sum(1 for i in range(256) if len({c[i] for c in c3fc}) > 1)
        identical_bytes = 256 - differing_bytes
        assert differing_bytes > 0  # real per-Kingdom differences exist
        assert identical_bytes / 256 > 0.9  # but it's mostly shared

    t1_worlds = [parse_xk_world(f) for f in (T1_K0, T1_K1, T1_K2)]
    t1_nonzero_indices = {i for w in t1_worlds for i, b in enumerate(w.globals.flags_c3fc) if b != 0}
    t2_worlds = [parse_xk_world(f) for f in (T2_K0, T2_K1, T2_K2)]
    t2_nonzero_indices = {i for w in t2_worlds for i, b in enumerate(w.globals.flags_c3fc) if b != 0}
    assert t1_nonzero_indices != t2_nonzero_indices


_TURN_TO_REAL_GW_FEATURES_1000 = {
    1: Path("/home/user/programma-ak/GW3__T1"),
    2: Path("/home/user/programma-ak/GW3__T2"),
    3: Path("/home/user/programma-ak/GW3__T3"),
    4: Path("/home/user/programma-ak/GW3__T4"),
}


def test_feature_count_global_is_the_real_world_total_not_a_per_kingdom_count():
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        gw_features = parse_gw_features(_TURN_TO_REAL_GW_FEATURES_1000[world.globals.game_turn])
        assert world.globals.feature_count == len(gw_features) == 128
        # this Kingdom's own known-feature count is always far smaller
        assert len(world.features) < world.globals.feature_count


def test_feature_held_trowner_matches_gws_own_raw_trowner_field_directly():
    # Stronger than the name/arithmetic-based confirmation: trowner is
    # cross-checked against GWFeatureRecord's own raw trowner_raw field
    # for the same real feature, not just re-derived from 256+feature_id.
    gw_cache = {}
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_features(_TURN_TO_REAL_GW_FEATURES_1000[turn])
        gw_features = gw_cache[turn]
        for treasure in world.treasures:
            if treasure.feature_id >= len(gw_features):
                continue
            if treasure.trowner != 256 + treasure.feature_id:
                continue
            gw_feature = gw_features[treasure.feature_id]
            assert treasure.trowner == gw_feature.trowner_raw
            checked += 1
    assert checked == 13


def test_generic_treasure_name_matches_the_pre_existing_gold_hoard_display_name():
    # Treasure.GOLD_HOARD_LARGE recurs at 3 distinct real features
    # (1, 17, 99) across the corpus -- name is always this project's
    # own pre-existing, TREASURE.X2-sourced generic display name, not a
    # per-instance string.
    seen_feature_ids = set()
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        for treasure in world.treasures:
            if treasure.treasure is not Treasure.GOLD_HOARD_LARGE:
                continue
            assert treasure.name == GOLD_HOARD_DISPLAY_NAME[Treasure.GOLD_HOARD_LARGE]
            assert treasure.name == "Large Hoard of Gold"
            seen_feature_ids.add(treasure.feature_id)
    assert seen_feature_ids == {1, 17, 99}


def test_unique_artifact_treasure_names_mostly_match_treasure_name_table():
    # 3 of 4 real unique-artifact instances match this project's own
    # pre-existing, directly TREASURE.X2-transcribed TREASURE_NAME table
    # exactly. LEADERSHIP_HUMAN is a confirmed real exception (Phase
    # 1001): XK's own real field is "Sword Excalibur", not the table's
    # own verbatim "Excalibur" -- a genuine discrepancy, not a decode
    # bug (the raw length-prefix byte matches a literal 15-char string).
    names_by_type: dict[Treasure, str] = {}
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        for treasure in world.treasures:
            names_by_type.setdefault(treasure.treasure, treasure.name)

    assert names_by_type[Treasure.WEAPON_2] == TREASURE_NAME[Treasure.WEAPON_2] == "Shadow Sword"
    assert names_by_type[Treasure.WAND_FLOOD] == TREASURE_NAME[Treasure.WAND_FLOOD] == "Feathers of Rain-Dancing"
    assert names_by_type[Treasure.BOOK_PSYCHIC] == TREASURE_NAME[Treasure.BOOK_PSYCHIC] == "Codex of Mental Prowess"

    assert TREASURE_NAME[Treasure.LEADERSHIP_HUMAN] == "Excalibur"
    assert names_by_type[Treasure.LEADERSHIP_HUMAN] == "Sword Excalibur"
    assert names_by_type[Treasure.LEADERSHIP_HUMAN] != TREASURE_NAME[Treasure.LEADERSHIP_HUMAN]


def test_treasure_name_is_not_truncated_at_the_king_title_tables_own_fifteen_chars():
    world = parse_xk_world(T4_K0)
    treasure = next(t for t in world.treasures if t.feature_id == 125)
    assert treasure.name == "Feathers of Rain-Dancing"
    assert len(treasure.name) == 24


def test_trcharges_still_has_no_real_example_in_its_own_ordinal_range():
    # No real Treasure ordinal in [70, 92) exists anywhere in the
    # corpus, so trcharges is None in every real record -- the presence
    # predicate is structurally confirmed (Phase 992) but its actual
    # value is still untested against GW's own trcharges field.
    seen_ordinals = set()
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        for treasure in world.treasures:
            seen_ordinals.add(treasure.treasure.value)
            assert treasure.trcharges is None
    assert not any(70 <= ordinal < 92 for ordinal in seen_ordinals)


_K1_MOVES_DIR = Path("/home/user/programma-ak")
_K1_TURN_PAIRS = ((1, T2_K1), (2, T3_K1), (3, T4_K1), (10, T11_K1))
# The real GW snapshot immediately *before* each paired turn's own real
# AK3__Tn.K1 moves were applied -- i.e. this Kingdom's own leaders'
# real starting coordinates for that turn's plan. Used by the Phase
# 1019 LMOVE-start-position tests below.
_K1_TURN_START_GW = {
    1: Path("/home/user/programma-ak/GW3__T1"),
    2: Path("/home/user/programma-ak/GW3__T2"),
    3: Path("/home/user/programma-ak/GW3__T3"),
    10: Path("/home/user/programma-ak/GW3__T10"),
}


def test_actions_match_the_real_submitted_k1_move_file_exactly():
    # Kingdom 1's own full cards, checked against that same Kingdom's
    # own real AK3__Tn.K1 move file (not just GW's post-processing
    # snapshot): actions[i] is the real P<i> action code submitted the
    # preceding turn, exact, zero exceptions.
    checked = 0
    for turn, xk_fixture in _K1_TURN_PAIRS:
        kingdom = parse_k1_moves_file(_K1_MOVES_DIR / f"AK3__T{turn}.K1")
        world = parse_xk_world(xk_fixture)
        cards_by_id = {c.leader_id: c for c in world.leader_cards}
        for leader in kingdom.leaders:
            card = cards_by_id.get(leader.leader_id)
            if card is None or not leader.plan.segments:
                continue
            segment = leader.plan.segments[0]
            for i in range(5):
                phase = segment.phases.get(f"P{i}")
                if phase is None:
                    continue
                assert int(phase.action) == card.actions[i]
                checked += 1
    assert checked == 170


def test_objects_match_k1_obj_for_every_action_except_lmove():
    # objects[i] is that phase's own real obj value, exact, for every
    # action type except LMOVE -- an LMOVE phase's own obj is itself a
    # packed hex-coordinate (turn/plan_dispatch.py's own
    # decode_hex_number), not a simple target id. Phase 1019 explains
    # what an LMOVE phase's own objects[i] *does* hold instead -- see
    # test_lmove_objects_is_the_phases_own_starting_position below.
    non_lmove_checked = 0
    lmove_mismatches = 0
    lmove_matches = 0
    lmove_checked = 0
    for turn, xk_fixture in _K1_TURN_PAIRS:
        kingdom = parse_k1_moves_file(_K1_MOVES_DIR / f"AK3__T{turn}.K1")
        world = parse_xk_world(xk_fixture)
        cards_by_id = {c.leader_id: c for c in world.leader_cards}
        for leader in kingdom.leaders:
            card = cards_by_id.get(leader.leader_id)
            if card is None or not leader.plan.segments:
                continue
            segment = leader.plan.segments[0]
            for i in range(5):
                phase = segment.phases.get(f"P{i}")
                if phase is None:
                    continue
                if phase.action is ActionCode.LMOVE:
                    lmove_checked += 1
                    if phase.obj != card.objects[i]:
                        lmove_mismatches += 1
                    else:
                        lmove_matches += 1
                else:
                    assert phase.obj == card.objects[i]
                    non_lmove_checked += 1
    assert non_lmove_checked == 108
    assert lmove_checked == 62
    # Phase 1019 correction: not "zero accidental matches" after all --
    # 2 of the larger corpus's own 62 real LMOVE phases do show
    # objects[i] == this same phase's own obj, both from the same one
    # real leader (32, Turn 10) whose own position-chain breaks in
    # exactly this way -- see the Phase 1019 chain test below.
    assert lmove_matches == 2
    assert lmove_mismatches == 60


def test_lmove_objects_is_the_phases_own_starting_position():
    # Phase 1019: the Phase 1002/1003 mystery of what an LMOVE phase's
    # own objects[i] holds (confirmed NOT that phase's own destination)
    # is resolved for the first LMOVE in a leader's own plan segment --
    # it is that leader's own real starting coordinate for the whole
    # turn (the position already on file before any of this turn's
    # moves execute), packed with the same board width
    # (EMPIRICAL_AK3_BOARD_WIDTH) turn/hex_numbering.py's own
    # decode_hex_number already uses for the plain K1 obj field, but
    # with x and y's roles swapped (``HexCoord(val // width, val %
    # width)`` instead of ``decode_hex_number``'s own ``(val % width,
    # val // width)``). Confirmed with zero exceptions across all 4
    # real turn-pairs on hand (including the Phase 1015/1016 Turn 10-11
    # pair), the first time any of this project's own real data points
    # have let "the first LMOVE phase in a plan" be distinguished from
    # "any LMOVE phase" -- the earlier, smaller corpus's own 8 real
    # first-LMOVE cases were too few on their own to separate this
    # rule from pure noise.
    from ak_engine.turn.hex_numbering import EMPIRICAL_AK3_BOARD_WIDTH

    checked = 0
    for turn, xk_fixture in _K1_TURN_PAIRS:
        start_gw_path = _K1_TURN_START_GW.get(turn)
        if start_gw_path is None:
            continue
        kingdom = parse_k1_moves_file(_K1_MOVES_DIR / f"AK3__T{turn}.K1")
        world = parse_xk_world(xk_fixture)
        cards_by_id = {c.leader_id: c for c in world.leader_cards}
        gw_leaders_start = parse_gw_leaders(start_gw_path)
        for leader in kingdom.leaders:
            card = cards_by_id.get(leader.leader_id)
            if card is None or not leader.plan.segments:
                continue
            segment = leader.plan.segments[0]
            first_lmove_idx = next(
                (i for i in range(5) if (segment.phases.get(f"P{i}") or None) and segment.phases[f"P{i}"].action is ActionCode.LMOVE),
                None,
            )
            if first_lmove_idx is None:
                continue
            val = card.objects[first_lmove_idx]
            decoded = HexCoord(x=val // EMPIRICAL_AK3_BOARD_WIDTH, y=val % EMPIRICAL_AK3_BOARD_WIDTH)
            assert decoded == gw_leaders_start[leader.leader_id].coord
            checked += 1
    assert checked == 26


def test_lmove_objects_chains_to_the_most_recent_executed_lmove():
    # Phase 1019, continued: for an LMOVE phase that is NOT the first
    # one in its own plan segment, objects[i] usually equals the real
    # destination (obj) of the most recently EXECUTED earlier LMOVE
    # phase in the same plan -- i.e. the position chains forward move
    # by move, consistent with objects[i] meaning "position before this
    # move" throughout, not just for the first move. 33 of 36 real
    # chained cases match exactly; the 3 real exceptions are all the
    # same one leader (32, Turn 10), whose own objects[i] instead
    # equals that exact phase's own destination (the same anomaly
    # test_objects_match_k1_obj_for_every_action_except_lmove's own
    # lmove_matches == 2 already flags, since 2 of these 3 exceptions'
    # chain target happens to coincide with the phase's own obj) --
    # consistent with (not proof of) that specific move not actually
    # having completed, but not independently confirmed.
    chain_matches = 0
    chain_total = 0
    for turn, xk_fixture in _K1_TURN_PAIRS:
        kingdom = parse_k1_moves_file(_K1_MOVES_DIR / f"AK3__T{turn}.K1")
        world = parse_xk_world(xk_fixture)
        cards_by_id = {c.leader_id: c for c in world.leader_cards}
        for leader in kingdom.leaders:
            card = cards_by_id.get(leader.leader_id)
            if card is None or not leader.plan.segments:
                continue
            segment = leader.plan.segments[0]
            last_lmove_obj = None
            for i in range(5):
                phase = segment.phases.get(f"P{i}")
                if phase is None or phase.action is not ActionCode.LMOVE:
                    continue
                if last_lmove_obj is not None:
                    chain_total += 1
                    if card.objects[i] == last_lmove_obj:
                        chain_matches += 1
                last_lmove_obj = phase.obj
    assert chain_total == 36
    assert chain_matches == 33


def test_planstart_planend_minus_one_does_not_mean_no_plan_was_submitted():
    # Corrects the field's own prior "a confirmed no-plan value"
    # reading: every full card in the whole corpus reads -1/-1, even
    # for leaders directly confirmed (via the K1 cross-check above) to
    # have had a full 5-phase plan submitted and already executed.
    kingdom = parse_k1_moves_file(_K1_MOVES_DIR / "AK3__T1.K1")
    world = parse_xk_world(T2_K1)
    cards_by_id = {c.leader_id: c for c in world.leader_cards}
    had_a_real_full_plan = False
    for leader in kingdom.leaders:
        card = cards_by_id.get(leader.leader_id)
        if card is None or not leader.plan.segments:
            continue
        segment = leader.plan.segments[0]
        if len(segment.phases) == 5:
            had_a_real_full_plan = True
            assert (card.planstart, card.planend) == (-1, -1)
    assert had_a_real_full_plan

    for fixture in ALL_17_SAMPLES:
        for card in parse_xk_world(fixture).leader_cards:
            assert (card.planstart, card.planend) == (-1, -1)


def test_extra_low_bytes_partially_matches_k1_obj_only_for_lmove():
    # A real, non-coincidental but incomplete pattern (Phase 1003,
    # re-run at larger scale in Phase 1019): extra_low_bytes[i] equals
    # that same phase's own real K1 obj value mostly for LMOVE phases
    # (45 of 62 at this larger scale, up from Phase 1003's original 10
    # of 18) -- consistent with usually carrying this exact phase's own
    # destination, the complement of what Phase 1019 found for
    # objects[i] (usually this phase's own *starting* position
    # instead). A handful of real non-LMOVE matches now also exist (7
    # of 108, up from Phase 1003's original 0 of 37) -- all EXPLORE or
    # CAST phases with small real obj values, not independently
    # explained, but too few and too specific to call pure
    # coincidence either.
    lmove_matches = 0
    lmove_total = 0
    nonlmove_matches = 0
    nonlmove_total = 0
    for turn, xk_fixture in _K1_TURN_PAIRS:
        kingdom = parse_k1_moves_file(_K1_MOVES_DIR / f"AK3__T{turn}.K1")
        world = parse_xk_world(xk_fixture)
        cards_by_id = {c.leader_id: c for c in world.leader_cards}
        for leader in kingdom.leaders:
            card = cards_by_id.get(leader.leader_id)
            if card is None or not leader.plan.segments:
                continue
            segment = leader.plan.segments[0]
            for i in range(5):
                phase = segment.phases.get(f"P{i}")
                if phase is None:
                    continue
                matches = card.extra_low_bytes[i] == phase.obj
                if phase.action is ActionCode.LMOVE:
                    lmove_total += 1
                    lmove_matches += int(matches)
                else:
                    nonlmove_total += 1
                    nonlmove_matches += int(matches)
    assert (lmove_matches, lmove_total) == (45, 62)
    assert (nonlmove_matches, nonlmove_total) == (7, 108)


def test_full_card_iff_own_leader_and_partial_card_never_own_leader():
    # A complete biconditional, zero exceptions in either direction:
    # a leader gets a full card here iff they belong to the viewing
    # Kingdom (GW's own kingdom_id); a partial card never belongs to it.
    gw_cache = {}
    own_full = 0
    own_partial = 0
    own_neither = 0
    partial_belongs_to_viewer = 0
    partial_checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        kingdom_id = world.header.kingdom_id
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        gw_leaders = gw_cache[turn]
        full_ids = {c.leader_id for c in world.leader_cards}
        partial_ids = {c.leader_id for c in world.partial_leader_cards}

        for i, gw_leader in enumerate(gw_leaders):
            if gw_leader.kingdom_id != kingdom_id:
                continue
            if i in full_ids:
                own_full += 1
            elif i in partial_ids:
                own_partial += 1
            else:
                own_neither += 1

        for leader_id in partial_ids:
            if leader_id >= len(gw_leaders):
                continue
            partial_checked += 1
            if gw_leaders[leader_id].kingdom_id == kingdom_id:
                partial_belongs_to_viewer += 1

    assert own_full == 57
    assert (own_partial, own_neither) == (0, 0)
    assert partial_checked == 68
    assert partial_belongs_to_viewer == 0


def test_full_card_does_not_imply_own_leader_at_scale():
    # Phase 1016 correction: re-run the same checks as
    # test_full_card_iff_own_leader_and_partial_card_never_own_leader
    # above across the larger 17-sample corpus (adding Turns 11-12),
    # the "full card iff belongs to the viewing Kingdom" biconditional
    # is no longer exception-free in either direction -- a well-tracked
    # foreign leader can earn a full card here (14 real cases, e.g.
    # Isis, genuinely Kingdom 7's own Hero, with a full card in Kingdom
    # 0's own file), and a genuine member of the viewing Kingdom can go
    # fully untracked in its own file (10 real cases, e.g. Indra,
    # genuinely Kingdom 2's own Hero, with no card at all in Kingdom
    # 2's own file). One direction does remain exception-free at this
    # larger scale and is the one still safe to rely on: a partial card
    # never belongs to the viewing Kingdom (0 of 166).
    own_full = 0
    own_neither = 0
    other_full = 0
    partial_belongs_to_viewer = 0
    partial_checked = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        kingdom_id = world.header.kingdom_id
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        full_ids = {c.leader_id for c in world.leader_cards}
        partial_ids = {c.leader_id for c in world.partial_leader_cards}

        for i, gw_leader in enumerate(gw_leaders):
            if gw_leader.name is None or gw_leader.name == "":
                continue
            is_own = gw_leader.kingdom_id == kingdom_id
            if is_own and i in full_ids:
                own_full += 1
            elif is_own:
                own_neither += 1
            elif i in full_ids:
                other_full += 1

        for leader_id in partial_ids:
            if leader_id >= len(gw_leaders):
                continue
            partial_checked += 1
            if gw_leaders[leader_id].kingdom_id == kingdom_id:
                partial_belongs_to_viewer += 1

    assert (own_full, own_neither) == (139, 10)
    assert other_full == 14
    assert partial_checked == 166
    assert partial_belongs_to_viewer == 0


_TURN_TO_REAL_GW_KING_EXTENSIONS = {
    1: Path("/home/user/programma-ak/GW3__T1"),
    2: Path("/home/user/programma-ak/GW3__T2"),
    3: Path("/home/user/programma-ak/GW3__T3"),
    4: Path("/home/user/programma-ak/GW3__T4"),
    11: Path("/home/user/programma-ak/GW3__T11"),
    12: Path("/home/user/programma-ak/GW3__T12"),
}


def test_diplomatic_relations_matches_real_gw_king_extension_at_scale():
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        kingdom_id = world.header.kingdom_id
        turn = world.globals.game_turn
        extensions = parse_gw_king_extensions(_TURN_TO_REAL_GW_KING_EXTENSIONS[turn])
        own_extension = extensions[kingdom_id]
        king_count = world.globals.king_count
        for i in range(king_count):
            assert world.diplomatic_relations[i] == own_extension.diplomatic_relations[i]
            checked += 1
    assert checked == 120


def test_diplomatic_relations_account_number_and_met_kings_mask_hold_at_17_file_scale():
    # Phase 1017: re-run across the 17-file corpus (adding the Phase
    # 1015/1016 Turn 11-12 samples), diplomatic_relations,
    # account_number and met_kings_bitmask_low all remain exact matches
    # against GWKingExtension with zero exceptions -- unlike the Army
    # quality_or_mask and full/partial-card rules (Phases 1015/1016),
    # these per-King fields are keyed to this file's own King
    # specifically (not to any leader's tracking status), so they are
    # not exposed to the same "tracking is dynamic, not ownership"
    # mechanism. See
    # test_king_sex_and_treasury_have_one_real_gw3_t12_discrepancy below
    # for the one real exception found elsewhere in this same King
    # extension data.
    dr_checked = 0
    acct_checked = 0
    met_kings_seen = set()
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        kingdom_id = world.header.kingdom_id
        turn = world.globals.game_turn
        extensions = parse_gw_king_extensions(_TURN_TO_REAL_GW_KING_EXTENSIONS[turn])
        own_extension = extensions[kingdom_id]
        king_count = world.globals.king_count
        for i in range(king_count):
            assert world.diplomatic_relations[i] == own_extension.diplomatic_relations[i]
            dr_checked += 1
        assert world.account_number == own_extension.account_number == 100 + kingdom_id
        acct_checked += 1
        assert world.met_kings_bitmask_low == own_extension.met_kings_bitmask
        met_kings_seen.add(world.met_kings_bitmask_low)
    assert dr_checked == 170
    assert acct_checked == 17
    assert met_kings_seen == {0, 1, 2, 256, 931, 998, 1021}


def test_diplomatic_relations_self_slot_is_always_allied():
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        assert world.diplomatic_relations[world.header.kingdom_id] is DiplomaticRelation.ALLIED


def test_diplomatic_relations_padding_slots_past_king_count_are_unused():
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        king_count = world.globals.king_count
        for relation in world.diplomatic_relations[king_count:]:
            assert relation is DiplomaticRelation.ENEMY  # unused padding, not a real relation


def test_relations_d1d4_is_no_longer_in_the_raw_player_tail_dict():
    world = parse_xk_world(T1_K0)
    assert "relations_D1D4" not in world.player_tail


def test_account_number_matches_real_gw_king_extension_at_scale():
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        kingdom_id = world.header.kingdom_id
        turn = world.globals.game_turn
        extensions = parse_gw_king_extensions(_TURN_TO_REAL_GW_KING_EXTENSIONS[turn])
        assert world.account_number == extensions[kingdom_id].account_number
        assert world.account_number == 100 + kingdom_id
        checked += 1
    assert checked == 12
    assert "DS_8D83" not in parse_xk_world(T1_K0).player_tail


def test_met_kings_bitmask_low_matches_real_gw_value_including_real_variance():
    seen_values = set()
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        kingdom_id = world.header.kingdom_id
        turn = world.globals.game_turn
        extensions = parse_gw_king_extensions(_TURN_TO_REAL_GW_KING_EXTENSIONS[turn])
        assert world.met_kings_bitmask_low == extensions[kingdom_id].met_kings_bitmask
        seen_values.add(world.met_kings_bitmask_low)
        checked += 1
    assert checked == 12
    assert seen_values == {0, 1, 2, 256}  # genuine variance, not a shared constant
    assert "DS_8E49_low" not in parse_xk_world(T1_K0).player_tail


def test_king_sex_matches_real_gw_king_extension_is_male():
    # Giovanna d'Arco (King 7) and Circe (King 8) are this campaign's
    # only two real female Kings -- exactly where the real F bytes land.
    world = parse_xk_world(T1_K0)
    king_count = world.globals.king_count
    extensions = parse_gw_king_extensions(Path("/home/user/programma-ak/GW3__T1"))
    assert king_count == 10
    for i in range(king_count):
        expected = Sex.MALE if extensions[i].is_male else Sex.FEMALE
        assert world.king_sex[i] == expected
    assert world.king_sex[7] == Sex.FEMALE
    assert world.king_sex[8] == Sex.FEMALE
    assert all(world.king_sex[i] == Sex.MALE for i in range(king_count) if i not in (7, 8))


def test_king_sex_identical_across_the_whole_corpus_and_padding_handled():
    reference = parse_xk_world(T1_K0).king_sex
    for fixture in ALL_12_SAMPLES:
        assert parse_xk_world(fixture).king_sex == reference
    assert len(reference) == 12
    assert reference[10] is None  # unused padding byte (0), not a real Sex


def test_treasury_matches_real_gw_king_extension_including_real_variance():
    seen_values = set()
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        kingdom_id = world.header.kingdom_id
        turn = world.globals.game_turn
        extensions = parse_gw_king_extensions(_TURN_TO_REAL_GW_KING_EXTENSIONS[turn])
        assert world.treasury == extensions[kingdom_id].treasury
        seen_values.add(world.treasury)
        checked += 1
    assert checked == 12
    assert len(seen_values) > 1  # genuine per-Kingdom/per-turn variance


def test_king_sex_and_treasury_have_one_real_gw3_t12_discrepancy():
    # Phase 1017: unlike diplomatic_relations/account_number/
    # met_kings_bitmask_low above, king_sex and treasury do NOT survive
    # the Turn 11-12 corpus unchanged -- but the real cause traces to
    # GW3__T12's own raw text, not to any XK decode gap. XK's own
    # king_sex[0] (King 0, Babba Sissoko) is stable FEMALE across every
    # one of this corpus's 17 real files, including both Turn 12
    # samples (K0 and K1) -- but GW3__T12's own King-0 extension line
    # literally reads "M" (``is_male=True``), disagreeing with both. The
    # same King-0 extension line's own treasury (``245``) also disagrees
    # with XK3__T12.K0's own ``treasury`` (``265``) -- a second, King-0-
    # specific GW3__T12 mismatch alongside the sex one, while every
    # other King's own treasury (including King 0's own at Turn 11, and
    # King 1's at Turn 12) matches exactly.
    #
    # Both disagreements coincide with a real, independently visible
    # fact in GW3__T12's own raw text: King 0's own real human player
    # name changes from "Andrea Ferrigno" (Turn 11) to "Brian Gruber"
    # (Turn 12) -- a mid-campaign handover of this Kingdom to a new real
    # player. Whatever produced the "M"/stale-treasury discrepancy in
    # GW3__T12's own King-0 extension line is tied to that handover, not
    # to an XK decode bug: both of XK's own independent Turn-12 files
    # (Kingdom 0's and Kingdom 1's) agree with each other and with every
    # earlier turn, while only this one real GW extension line disagrees
    # with all of them.
    world_t11_k0 = parse_xk_world(T11_K0)
    world_t12_k0 = parse_xk_world(T12_K0)
    world_t12_k1 = parse_xk_world(T12_K1)
    assert world_t11_k0.king_sex[0] == Sex.FEMALE
    assert world_t12_k0.king_sex[0] == Sex.FEMALE
    assert world_t12_k1.king_sex[0] == Sex.FEMALE

    ext_t11 = parse_gw_king_extensions(_TURN_TO_REAL_GW_KING_EXTENSIONS[11])
    ext_t12 = parse_gw_king_extensions(_TURN_TO_REAL_GW_KING_EXTENSIONS[12])
    assert ext_t11[0].is_male is False  # agrees with XK at Turn 11
    assert ext_t12[0].is_male is True  # disagrees with XK at Turn 12

    assert world_t12_k0.treasury == 265
    assert ext_t12[0].treasury == 245  # disagrees; King 1's own treasury matches fine
    assert world_t12_k1.treasury == ext_t12[1].treasury == 484


def test_recruitment_map_matches_real_gw_recruit_types_for_known_provinces():
    # Checked against real GW ground truth, not just this file's own
    # province list: the recruitment map reveals a known province's
    # real recruit types regardless of ownership, richer than
    # XKProvinceRecord's own recruit_type_1/2 (owned-only). Phase 1015's
    # own Turn 11-12 corpus extends this to 651 real checks (from the
    # original 177), still zero exceptions.
    gw_cache = {}
    known_checked = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        if turn not in gw_cache:
            gw_cache[turn] = {p.name: p for p in parse_gw_world(_TURN_TO_REAL_GW_PROVINCES[turn])}
        gw_by_name = gw_cache[turn]
        cell_by_coord = {c.coord: c for c in world.recruitment_map}
        for province in world.provinces:
            gw_province = gw_by_name.get(province.name)
            if gw_province is None:
                continue
            cell = cell_by_coord[province.coord]
            assert cell.recruit_type_1 == gw_province.recruit_type_1
            assert cell.recruit_type_2 == gw_province.recruit_type_2
            known_checked += 1
    assert known_checked == 651


def test_recruitment_map_is_richer_than_the_province_record_for_unowned_known_provinces():
    world = parse_xk_world(T1_K0)
    cell_by_coord = {c.coord: c for c in world.recruitment_map}
    unowned_known = [p for p in world.provinces if p.owner_kingdom_id is None]
    assert unowned_known  # real unowned-but-known provinces exist in this file
    for province in unowned_known:
        assert province.recruit_type_1 is None and province.recruit_type_2 is None
        cell = cell_by_coord[province.coord]
        assert cell.recruit_type_1 is not None  # the recruitment map still reveals it


def test_recruitment_map_cells_for_unknown_provinces_are_always_blank():
    checked = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        known_coords = {p.coord for p in world.provinces}
        for cell in world.recruitment_map:
            if cell.coord in known_coords:
                continue
            assert cell.recruit_type_1 is None
            assert cell.recruit_type_2 is None
            checked += 1
    assert checked == 2103


def test_liege_extension_matches_full_card_lliege_except_one_known_identity_reuse():
    # The one real exception (XK3__T4.K2, leader 99) is a genuine
    # leader-id-reuse artifact confirmed against GW, not a decode bug:
    # the real person behind leader_id 99 changes between GW3__T3
    # (Quintilian, Kingdom 2) and GW3__T4 (Bo, Kingdom 9). Re-run across
    # the larger 17-file corpus (Phase 1015/1016's own Turn 11-12
    # samples), this remains the only real exception -- 152 of 153 real
    # checks now, up from the original 57 of 58, with zero new ones
    # among the 95 additional real checks the new files add.
    matches = 0
    mismatches = []
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        if world.liege_extension is None:
            continue
        liege_map = world.liege_extension.liege_by_leader_id
        for card in world.leader_cards:
            if card.leader_id not in liege_map:
                continue
            if liege_map[card.leader_id] == card.lliege:
                matches += 1
            else:
                mismatches.append((fixture.name, card.leader_id, card.lliege, liege_map[card.leader_id]))
    assert matches == 152
    assert mismatches == [("XK3__T4.K2", 99, 255, 9)]

    leaders_t3 = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[3])
    leaders_t4 = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[4])
    assert (leaders_t3[99].name, leaders_t3[99].kingdom_id) == ("Quintilian", 2)
    assert (leaders_t4[99].name, leaders_t4[99].kingdom_id) == ("Bo", 9)


def test_liege_extension_coverage_is_not_about_employment():
    # Correction (Phase 1013): every real partial-card leader in this
    # corpus is independent (kingdom_id=None) -- employment status
    # cannot be what distinguishes the 62 covered from the 6 uncovered.
    # What actually predicts coverage is tested below.
    covered = 0
    uncovered = 0
    all_kingdom_ids = set()
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        if world.liege_extension is None:
            continue
        liege_map = world.liege_extension.liege_by_leader_id
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        for card in world.partial_leader_cards:
            all_kingdom_ids.add(gw_leaders[card.leader_id].kingdom_id)
            if card.leader_id in liege_map:
                covered += 1
            else:
                uncovered += 1
    assert covered == 62
    assert uncovered == 6
    assert all_kingdom_ids == {None}  # every partial card is independent, covered or not


def test_liege_extension_coverage_partial_cards_can_be_employed_at_scale():
    # Phase 1020 correction: re-run across the larger 17-file corpus,
    # "every partial-card leader is independent" no longer holds -- 51
    # of 211 real partial cards genuinely belong to some Kingdom. This
    # doesn't revive "employment predicts coverage" (both employed and
    # independent partial cards can be covered or uncovered), it just
    # means the above test's own all_kingdom_ids == {None} no longer
    # describes the full corpus.
    covered = 0
    uncovered = 0
    employed = 0
    independent = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        if world.liege_extension is None:
            continue
        liege_map = world.liege_extension.liege_by_leader_id
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        for card in world.partial_leader_cards:
            if gw_leaders[card.leader_id].kingdom_id is None:
                independent += 1
            else:
                employed += 1
            if card.leader_id in liege_map:
                covered += 1
            else:
                uncovered += 1
    assert covered == 160
    assert uncovered == 6
    assert (employed, independent) == (51, 115)


def test_leader_states_equals_gw_condition_for_a_nonone_independent_leader():
    # The first real decode of GW's own condition field for a value
    # other than 1 anywhere in this project.
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        for card in world.partial_leader_cards:
            gw_leader = gw_leaders[card.leader_id]
            if gw_leader.condition == 1:
                continue
            assert world.leader_states[card.leader_id] == gw_leader.condition
            checked += 1
    assert checked == 12


def test_leader_states_condition_rule_corrected_by_liege_sentinel_at_scale():
    # Phase 1020 correction: the original "leader_states always equals
    # condition for condition != 1" claim (12 of 12) was real but
    # incomplete -- every one of those 12 real cases happened, by
    # coincidence of the smaller corpus, to carry the TR_LLs liege
    # extension's own 255 "no real liege" sentinel wherever it applied
    # at all. The larger 17-file corpus's own 28 real condition == 2
    # cases (independent leaders only, as Phase 1010/1013 already
    # established for condition != 1) reveal the real, complete rule:
    # leader_states equals condition when the liege extension gives
    # nothing or the 255 sentinel (23 of 23), but equals 1 instead when
    # it gives a genuine, real liege id (5 of 5) -- zero exceptions once
    # the sentinel is accounted for. condition == 0's own 19 real cases
    # never carry a real, non-sentinel liege value in this corpus, so
    # this generalization isn't independently confirmed for 0, only
    # consistent with it (all 19 do carry the 255 sentinel, all read 0).
    SENTINEL = 255
    cond2_sentinel_matches = 0
    cond2_real_liege_matches = 0
    cond0_checked = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        liege_map = world.liege_extension.liege_by_leader_id if world.liege_extension else {}
        for card in world.partial_leader_cards:
            gw_leader = gw_leaders[card.leader_id]
            if gw_leader.condition not in (0, 2):
                continue
            liege_val = liege_map.get(card.leader_id)
            is_sentinel = liege_val is None or liege_val == SENTINEL
            if gw_leader.condition == 0:
                assert is_sentinel
                assert world.leader_states[card.leader_id] == 0
                cond0_checked += 1
                continue
            if is_sentinel:
                assert world.leader_states[card.leader_id] == gw_leader.condition
                cond2_sentinel_matches += 1
            else:
                assert world.leader_states[card.leader_id] == 1
                cond2_real_liege_matches += 1
    assert cond0_checked == 19
    assert cond2_sentinel_matches == 23
    assert cond2_real_liege_matches == 5


def test_leader_states_partial_card_condition_one_split_by_liege_coverage():
    # Completes the partial-card case of leader_states: when condition
    # is 1, leader_states is 1 iff the same leader_id is also covered
    # by the TR_LLs liege extension, 7 otherwise -- zero exceptions.
    checked = 0
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        liege_map = world.liege_extension.liege_by_leader_id if world.liege_extension else {}
        for card in world.partial_leader_cards:
            gw_leader = gw_leaders[card.leader_id]
            if gw_leader.condition != 1:
                continue
            expected = 1 if card.leader_id in liege_map else 7
            assert world.leader_states[card.leader_id] == expected
            checked += 1
    assert checked == 56


def test_leader_states_employed_condition_one_mostly_follows_coverage_rule():
    # Phase 1020: the newly-possible "employed partial card" category
    # (absent from the original corpus) mostly follows the established
    # "covered -> 1" rule (44 of 51), but has 7 real exceptions reading
    # 2 or 0 instead. See
    # test_leader_states_employed_exception_is_closed_by_hiring_turn
    # below for the Phase 1022 finding that fully closes *whether* a
    # case is an exception (hiring_turn != 0, not just sentinel liege
    # coverage) -- only which non-1 value it resolves to remains open.
    SENTINEL = 255
    normal = 0
    exceptions = []
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        liege_map = world.liege_extension.liege_by_leader_id if world.liege_extension else {}
        for card in world.partial_leader_cards:
            gw_leader = gw_leaders[card.leader_id]
            if gw_leader.condition != 1 or gw_leader.kingdom_id is None:
                continue
            assert card.leader_id in liege_map  # every real employed case is covered
            ls = world.leader_states[card.leader_id]
            if ls == 1:
                normal += 1
            else:
                exceptions.append((fixture.name, card.leader_id, gw_leader.name, liege_map[card.leader_id], ls))
    assert normal == 44
    assert len(exceptions) == 7
    assert all(liege_val == SENTINEL for *_, liege_val, _ls in exceptions)
    assert {name for _, _, name, _, _ in exceptions} == {"Odysseus", "Brunhilda", "Kishijoten", "Hecate"}


def test_leader_states_employed_exception_is_closed_by_hiring_turn():
    # Phase 1022: closes the Phase 1020 "sentinel + employed is
    # necessary but not sufficient" gap completely. The missing
    # ingredient is GWLeaderRecord.hiring_turn: among employed,
    # condition == 1 partial cards, leader_states == 1 unless the liege
    # extension gives the 255 sentinel AND this Hero's own hiring_turn
    # is nonzero (recruited after the game began, not a founding
    # member) -- 51 of 51 real cases, zero exceptions.
    SENTINEL = 255
    checked = 0
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        gw_leaders = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[turn])
        liege_map = world.liege_extension.liege_by_leader_id if world.liege_extension else {}
        for card in world.partial_leader_cards:
            gw_leader = gw_leaders[card.leader_id]
            if gw_leader.condition != 1 or gw_leader.kingdom_id is None:
                continue
            liege_val = liege_map[card.leader_id]
            is_exception = liege_val == SENTINEL and gw_leader.hiring_turn != 0
            ls = world.leader_states[card.leader_id]
            if is_exception:
                assert ls != 1
            else:
                assert ls == 1
            checked += 1
    assert checked == 51


def test_liege_coverage_is_not_a_fixed_leader_kingdom_relationship():
    # Phase 1014: rules out a static explanation for coverage. The same
    # real leader (Dracona, 38), viewed by the same real Kingdom (0)'s
    # own file, is covered at Turn 2 but uncovered at Turn 3 -- with an
    # unchanged real coord and known_by_kings_mask in between, so
    # neither can be what flips it.
    def covered(fixture):
        world = parse_xk_world(fixture)
        liege_map = world.liege_extension.liege_by_leader_id if world.liege_extension else {}
        return 38 in liege_map

    assert covered(T2_K0) is True
    assert covered(T3_K0) is False

    leaders_t2 = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[2])
    leaders_t3 = parse_gw_leaders(_TURN_TO_REAL_GW_LEADERS[3])
    assert leaders_t2[38].coord == leaders_t3[38].coord
    assert leaders_t2[38].known_by_kings_mask == leaders_t3[38].known_by_kings_mask


def test_secondary_ability_table_is_identical_across_the_whole_corpus():
    reference = None
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        table = tuple(tuple(row) for row in world.secondary_abilities.levels_by_ability)
        if reference is None:
            reference = table
        else:
            assert table == reference  # genuine static compiled data, not per-game state


def test_secondary_terrain_table_shared_per_turn_but_varies_across_turns():
    by_turn = {}
    for fixture in ALL_12_SAMPLES:
        world = parse_xk_world(fixture)
        turn = world.globals.game_turn
        by_turn.setdefault(turn, set()).add(world.secondary_terrain.raw)
    for turn, tables in by_turn.items():
        assert len(tables) == 1, f"turn {turn} differs across kingdoms"
    assert len({next(iter(tables)) for tables in by_turn.values()}) > 1  # varies turn to turn


def test_secondary_terrain_table_is_not_simply_per_province_alternate_terrain():
    # The straightforward reading (byte at real province list index i ==
    # that province's own real alternate_terrain ordinal) is falsified.
    world = parse_xk_world(T1_K0)
    gw_provinces = parse_gw_world(Path("/home/user/programma-ak/GW3__T1"))
    raw = world.secondary_terrain.raw
    mismatches = 0
    invalid_terrain_bytes = 0
    for i, province in enumerate(gw_provinces):
        byte = raw[i]
        try:
            terrain = Terrain(byte)
        except ValueError:
            terrain = None
            invalid_terrain_bytes += 1
        if terrain != province.alternate_terrain:
            mismatches += 1
    assert len(gw_provinces) == 162
    assert mismatches == 60
    assert invalid_terrain_bytes > 0
