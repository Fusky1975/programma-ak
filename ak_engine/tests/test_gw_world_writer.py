"""Tests for the world-file (GW3-format) writer -- the inverse of
`parser/gw_world.py`'s reader functions. Every test here is a genuine
round trip: build or parse a record, write it with the matching
`write_gw_*` function, feed the written text back through the real
`parse_gw_*` reader, and assert the re-parsed record(s) compare equal to
the original -- not just a shape/format assertion on the writer's own
output.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.feature import FeatureType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import (
    DiplomaticRelation,
    GameType,
    GWArmyRecord,
    GWHeader,
    GWKingExtension,
    GWLeaderRecord,
    GWOfficeMeritRecord,
    GWOfficeStateEntry,
    KingSendMethod,
    KingStandbyState,
    parse_gw_armies,
    parse_gw_features,
    parse_gw_header,
    parse_gw_king_extensions,
    parse_gw_leaders,
    parse_gw_offices,
    parse_gw_treasures_only,
    parse_gw_world,
)
from ak_engine.parser.gw_world_writer import (
    ARMY_TYPE_TO_MOD_PAT_ORDINAL,
    write_gw_army_record,
    write_gw_feature_record,
    write_gw_header,
    write_gw_king_extension,
    write_gw_leader_record,
    write_gw_office_records,
    write_gw_province_record,
    write_gw_treasure_only_record,
)
from ak_engine.turn.combat import Quality

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T1"


def test_army_type_to_mod_pat_ordinal_is_a_true_inverse():
    from ak_engine.parser.gw_world import MOD_PAT_ORDINAL_TO_ARMY_TYPE

    for ordinal, army_type in MOD_PAT_ORDINAL_TO_ARMY_TYPE.items():
        if army_type is None:
            continue
        assert ARMY_TYPE_TO_MOD_PAT_ORDINAL[army_type] == ordinal


def test_write_gw_header_round_trips(tmp_path: Path):
    header = parse_gw_header(FIXTURE)
    path = tmp_path / "header_only"
    path.write_text(write_gw_header(header), encoding="utf-8")
    assert parse_gw_header(path) == header


def test_write_gw_header_rejects_a_partial_extended_block():
    header = parse_gw_header(FIXTURE)
    header.last_leader_index = None
    try:
        write_gw_header(header)
    except ValueError:
        pass
    else:
        raise AssertionError("expected a ValueError for a partially-populated extended header block")


def test_write_gw_province_record_round_trips(tmp_path: Path):
    records = parse_gw_world(FIXTURE)
    record = records[0]
    path = tmp_path / "province_only"
    path.write_text(write_gw_province_record(record), encoding="utf-8")
    round_tripped = parse_gw_world(path)
    assert round_tripped == [record]


def test_write_gw_province_record_round_trips_every_real_province(tmp_path: Path):
    records = parse_gw_world(FIXTURE)
    text = "\n".join(write_gw_province_record(record) for record in records)
    path = tmp_path / "all_provinces"
    path.write_text(text, encoding="utf-8")
    assert parse_gw_world(path) == records


def _hero(name: str, kingdom_id: int | None) -> GWLeaderRecord:
    return GWLeaderRecord(
        name=name,
        is_king=False,
        race=Race.ELVEN,
        alignment=Alignment.GOOD,
        temper=Temper.BRAVE,
        condition=1,
        coord=HexCoord(3, 4),
        skills=SkillTable(raw_values=list(range(30))),
        kingdom_id=kingdom_id,
        birth_coord=HexCoord(3, 4),
        original_liege_raw=255 if kingdom_id is None else kingdom_id,
        hiring_turn=0,
        general_merit=0,
        admiral_merit=0,
        defender_merit=0,
        feature_discoveries=0,
        discovery_points=0,
        white_magic_service_points=0,
        experience_progress=42,
        sex_raw=0,
        sex_override_flag=False,
        unpaid_blackmail_penalty_exponent=0,
        known_by_kings_mask=0,
    )


def _king(name: str, kingdom_id: int) -> GWLeaderRecord:
    return GWLeaderRecord(
        name=name,
        is_king=True,
        race=Race.ORCISH,
        alignment=Alignment.EVIL,
        temper=Temper.BERSERK,
        condition=1,
        coord=HexCoord(11, 7),
        skills=SkillTable(raw_values=list(range(30))),
        kingdom_id=kingdom_id,
        birth_coord=HexCoord(11, 7),
        original_liege_raw=255,
        hiring_turn=0,
        general_merit=5,
        admiral_merit=6,
        defender_merit=7,
        feature_discoveries=8,
        discovery_points=9,
        white_magic_service_points=10,
        experience_progress=99,
        sex_raw=0,
        sex_override_flag=True,
        unpaid_blackmail_penalty_exponent=2,
        known_by_kings_mask=1023,
    )


def test_write_gw_leader_record_round_trips_a_hero(tmp_path: Path):
    hero = _hero("Guerin", kingdom_id=None)
    path = tmp_path / "hero_only"
    path.write_text(write_gw_leader_record(hero), encoding="utf-8")
    assert parse_gw_leaders(path) == [hero]


def test_write_gw_leader_record_round_trips_a_king(tmp_path: Path):
    king = _king("Babba Sissoko", kingdom_id=0)
    path = tmp_path / "king_only"
    path.write_text(write_gw_leader_record(king), encoding="utf-8")
    assert parse_gw_leaders(path) == [king]


def test_write_gw_leader_record_round_trips_a_mixed_kingdom_roster(tmp_path: Path):
    # A King's own `kingdom_id` is derived positionally by
    # `parse_gw_leaders` (the Nth King-shaped record encountered), so
    # this test writes Kings in ascending kingdom_id order to match.
    king0 = _king("Babba Sissoko", kingdom_id=0)
    king1 = _king("Bradipo I", kingdom_id=1)
    hero_of_king1 = _hero("Guerin", kingdom_id=1)
    independent_hero = _hero("Odysseus", kingdom_id=None)

    records = [king0, king1, hero_of_king1, independent_hero]
    text = "\n".join(write_gw_leader_record(record) for record in records)
    path = tmp_path / "mixed_roster"
    path.write_text(text, encoding="utf-8")
    assert parse_gw_leaders(path) == records


def test_write_gw_feature_record_round_trips_every_real_feature(tmp_path: Path):
    records = parse_gw_features(FIXTURE)
    text = "\n".join(write_gw_feature_record(record) for record in records)
    path = tmp_path / "all_features"
    path.write_text(text, encoding="utf-8")
    assert parse_gw_features(path) == records


def test_write_gw_treasure_only_record_round_trips_the_real_t1_and_t5_blocks(tmp_path: Path):
    for fixture in (FIXTURE, FIXTURE.parent / "GW3__T5"):
        header = parse_gw_header(fixture)
        features = parse_gw_features(fixture)
        records = parse_gw_treasures_only(fixture)

        text = "\n".join(
            (
                write_gw_header(header),
                *(write_gw_feature_record(feature) for feature in features),
                *(write_gw_treasure_only_record(record) for record in records),
            )
        )
        path = tmp_path / f"header_features_treasures_only_{fixture.name}"
        path.write_text(text, encoding="utf-8")

        assert parse_gw_treasures_only(path) == records


def test_write_gw_king_extension_round_trips_a_synthetic_record_with_real_discoveries(tmp_path: Path):
    # Real fixtures happen to have `discovered == frozenset()` for every
    # King (Discovery: none acquired yet by turn 5) -- this synthetic
    # record exercises the 64-boolean discovered range with real
    # nonzero flags, plus other fields real fixtures don't cover
    # (election sentinel 31000, an active blackmailer id, a non-NO
    # standby state).
    header = GWHeader(
        king_count=2,
        army_count=0,
        game_turn=1,
        raw_04=-1,
        setup_fee_cents=0,
        treasure_count=0,
        feature_count=0,
        map_left_x=0,
        map_right_x=17,
        map_top_y=0,
        map_bottom_y=8,
        game_version=1,
        game_number=1,
        due_day=1,
        due_month=1,
        due_year=2007,
        turn_length_days=14,
        diplomacy_type=0,
        header_revision=30,
        original_turn=1,
        turn_cost_cents=0,
        game_type=GameType.NORMAL,
        total_fees=0,
        last_leader_index=0,
        valhalla_alignment_rotation_mask=0,
        visiting_king=255,
        max_feature_index=0,
        setup_extra_1=0,
        office_merit_record_count=0,
        office_state_table_present=0,
        compatibility_revision_31=1,
        mine_write_flags=0,
        misc_write_flags=0,
    )
    king = _king("Test King", kingdom_id=0)
    record = GWKingExtension(
        is_male=False,
        treasury=500,
        alliance_requests_bitmask=3,
        break_treaty_requests_bitmask=1,
        account_number=42,
        player_mode=1,
        met_kings_bitmask=1,
        send_method=KingSendMethod.DISK,
        election_request_or_previous_choice=31000,
        payment_percent=50,
        miscellaneous_fee=5,
        turn_funds_received=10,
        consecutive_missed_turns=0,
        standby_state=KingStandbyState.WAITING,
        standby_max_percent=80,
        prize_credit=0,
        raw_administrative_flag=1,
        moves_read_success=True,
        order_interpreter_version=27,
        diplomatic_relations=(DiplomaticRelation.ALLIED, DiplomaticRelation.TEAMED),
        discovered=frozenset({Discovery(0), Discovery(63), Discovery(30)}),
        valhalla_visit_count=2,
        king_information_flags=1,
        disk_delivery_flags=0,
        king_power_or_votes_cast=7,
        moves_insurance=True,
        team_state=1,
        active_blackmailer_king_id=1,
        pending_blackmailer_king_id=None,
        power_percent=75,
        trailing_compatibility_zeros=(0, 0, 0, 0, 0),
    )

    text = "\n".join((write_gw_header(header), write_gw_leader_record(king), write_gw_king_extension(record)))
    path = tmp_path / "synthetic_king_extension"
    path.write_text(text, encoding="utf-8")

    assert parse_gw_king_extensions(path) == [record]


def test_write_gw_king_extension_round_trips_every_real_king_across_both_fixtures(tmp_path: Path):
    for fixture in (FIXTURE, FIXTURE.parent / "GW3__T5"):
        header = parse_gw_header(fixture)
        king_extensions = parse_gw_king_extensions(fixture)
        kings = [leader for leader in parse_gw_leaders(fixture) if leader.is_king]
        assert len(kings) == len(king_extensions)

        lines = [write_gw_header(header)]
        for king, extension in zip(kings, king_extensions):
            lines.append(write_gw_leader_record(king))
            lines.append(write_gw_king_extension(extension))
        path = tmp_path / f"king_extensions_{fixture.name}"
        path.write_text("\n".join(lines), encoding="utf-8")

        assert parse_gw_king_extensions(path) == king_extensions


def test_write_gw_army_record_round_trips_every_real_army(tmp_path: Path):
    records = parse_gw_armies(FIXTURE)
    text = "\n".join(write_gw_army_record(record) for record in records)
    path = tmp_path / "all_armies"
    path.write_text(text, encoding="utf-8")
    assert parse_gw_armies(path) == records


def test_write_gw_army_record_round_trips_a_state_not_seen_in_the_real_fixture(tmp_path: Path):
    # Phase 376: GW3__T1's own 218 Block B rows only ever show state in
    # {HIRED, MERCENARY, ZOMBOID} -- CALM (7) is real per the AKGEN
    # disassembly's own state_enum but untested by the fixture round
    # trip above, so this exercises it with a synthetic record.
    record = GWArmyRecord(
        commanded_by_leader_id=None,
        coord=HexCoord(3, 4),
        race=Race.HUMAN,
        army_type=ArmyType.BOWMEN,
        quality=Quality.VETERAN,
        state=MonsterEngagementState.CALM,
        is_skeletal=False,
        is_mercenary=False,
        movement_points=5,
        death_or_transformation_marker=251,
        plague_survival_count=1,
    )
    path = tmp_path / "calm_army_only"
    path.write_text(write_gw_army_record(record), encoding="utf-8")
    assert parse_gw_armies(path) == [record]


def test_write_gw_office_records_round_trips_through_a_synthetic_full_file(tmp_path: Path):
    header = GWHeader(
        king_count=1,
        army_count=1,
        game_turn=1,
        raw_04=-1,
        setup_fee_cents=0,
        treasure_count=0,
        feature_count=0,
        map_left_x=0,
        map_right_x=17,
        map_top_y=0,
        map_bottom_y=8,
        game_version=1,
        game_number=1,
        due_day=1,
        due_month=1,
        due_year=2007,
        turn_length_days=14,
        diplomacy_type=0,
        header_revision=30,
        original_turn=1,
        turn_cost_cents=0,
        game_type=GameType.NORMAL,
        total_fees=0,
        last_leader_index=0,
        valhalla_alignment_rotation_mask=0,
        visiting_king=255,
        max_feature_index=0,
        setup_extra_1=0,
        office_merit_record_count=2,
        office_state_table_present=1,
        compatibility_revision_31=1,
        mine_write_flags=0,
        misc_write_flags=0,
    )
    merit_records = [
        GWOfficeMeritRecord(office_code=Office.MARSHAL, leader_or_army_id=0, merit_points=100),
        GWOfficeMeritRecord(office_code=Office.ADMIRAL, leader_or_army_id=1, merit_points=50),
    ]
    state_entries = [
        GWOfficeStateEntry(office=Office(ordinal), previous_holder_raw=255, known_by_kings_mask=0)
        for ordinal in range(52)
    ]
    army_record_line = write_gw_army_record(parse_gw_armies(FIXTURE)[0])

    text = "\n".join(
        (
            write_gw_header(header),
            army_record_line,
            write_gw_office_records(merit_records, state_entries),
        )
    )
    path = tmp_path / "synthetic_full_file"
    path.write_text(text, encoding="utf-8")

    round_tripped_merit, round_tripped_state = parse_gw_offices(path)
    assert round_tripped_merit == merit_records
    assert round_tripped_state == state_entries
