"""Tests for the GW-world-to-`GameState.provinces` coordinate bridge.

See `parser/gw_world_bridge.py`'s own module docstring for the empirical,
100%-match evidence behind the column-major coordinate mapping this
module implements.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.parser.gw_world import (
    DiplomaticRelation,
    GWKingExtension,
    KingSendMethod,
    KingStandbyState,
    parse_gw_armies,
    parse_gw_king_extensions,
    parse_gw_leaders,
    parse_gw_world,
)
from ak_engine.parser.gw_world_bridge import (
    apply_confirmed_hero_ids,
    bridge_gw_world_provinces,
    bridge_new_game_state,
    resolve_province_owners,
)

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


# -- Phase 723: pt2/alternate_terrain -> is_island bridging ------------
#
# No real GW3__T1-T12 sample ever has a non-NO_TERRAIN alternate_terrain
# (see gw_world.py's own GWProvinceRecord.alternate_terrain docstring),
# so every case below is a synthetic record built via `replace()` on a
# real fixture record, explicitly labeled as such -- not a real-sample
# regression case.


def test_bridge_marks_a_sea_primary_record_with_a_real_alternate_terrain_as_an_island():
    records = parse_gw_world(FIXTURE)
    synthetic = replace(records[0], terrain=Terrain.SEA, alternate_terrain=Terrain.JUNGLE)

    provinces = bridge_gw_world_provinces([synthetic], height=1)

    province = provinces[HexCoord(0, 0)]
    assert province.terrain is Terrain.JUNGLE
    assert province.is_island is True


def test_bridge_leaves_a_sea_primary_record_with_no_alternate_terrain_unmarked():
    records = parse_gw_world(FIXTURE)
    synthetic = replace(records[0], terrain=Terrain.SEA, alternate_terrain=Terrain.NO_TERRAIN)

    provinces = bridge_gw_world_provinces([synthetic], height=1)

    province = provinces[HexCoord(0, 0)]
    assert province.terrain is Terrain.SEA
    assert province.is_island is False


def test_bridge_never_treats_a_land_primary_record_with_an_alternate_terrain_as_an_island():
    # Never observed in any real sample, and neither available source
    # describes this shape -- conservatively excluded, not guessed.
    records = parse_gw_world(FIXTURE)
    synthetic = replace(records[0], terrain=Terrain.PLAINS, alternate_terrain=Terrain.JUNGLE)

    provinces = bridge_gw_world_provinces([synthetic], height=1)

    province = provinces[HexCoord(0, 0)]
    assert province.terrain is Terrain.PLAINS
    assert province.is_island is False


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


# -- Phase 338: bridge_new_game_state() / apply_confirmed_hero_ids() ---


def _bridge_fixture():
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)
    return bridge_new_game_state(leader_records, province_records, army_records)


def test_every_king_gets_a_real_confirmed_id_and_kingdom():
    state, report = _bridge_fixture()

    assert report.kings_created == 10
    babba = state.kingdoms[0]
    assert babba.name == "Babba Sissoko"
    assert babba.race is Race.ORCISH
    assert babba.alignment is Alignment.UNDEAD
    assert babba.home_province == HexCoord(11, 7)
    king_leader = state.leaders[0]
    assert king_leader.is_king is True
    assert king_leader.kingdom_id == 0
    assert king_leader.skills is not None


def test_bridge_new_game_state_records_the_real_board_size():
    # Phase 780: 162 real province records / CONFIRMED_BOARD_HEIGHT (9)
    # = 18 -- independently reconfirming the rulebook's own "normale"
    # 18x9 default (Regolamento AK.txt 12.1) against real GW3 data, not
    # the wrong Super-AK (30x15) constant every downstream turn-engine
    # consumer used to fall back to.
    state, _ = _bridge_fixture()

    assert state.board_height == 9
    assert state.board_width == 18


def test_a_roster_matched_hero_gets_his_own_real_id_and_sex():
    # Phase 339: Guerin's own name is in models/hero_roster.py's fixed
    # 98-entry table (#18, confirmed independently many times over in
    # earlier phases), so he no longer needs a synthetic placeholder id.
    state, report = _bridge_fixture()

    assert report.heroes_created == 90
    assert report.heroes_with_confirmed_id["Guerin"] == 18
    guerin = state.leaders[18]
    assert guerin.is_king is False
    assert guerin.race is Race.ELVEN
    assert guerin.alignment is Alignment.UNDEAD
    assert guerin.sex is Sex.MALE
    # Liege field (Phase 325/327, confirmed real) -- Guerin serves
    # kingdom 1 (Uga-Buga Makumb), matching every earlier cross-check.
    assert guerin.kingdom_id == 1


def test_a_non_rostered_hero_falls_back_to_a_synthetic_negative_id():
    # Kitralus is a real VALHALLA NEUTRAL.txt entry -- the roster's own
    # documented "#99, arrived via VALHALLA" case, not a data error
    # (Phase 366's own re-verification: the real LNAMES.PAS-sourced
    # roster now also resolves Bagmore, previously a second unmatched
    # name under Phase 339's own hand-typed table).
    state, report = _bridge_fixture()

    assert set(report.heroes_with_synthetic_id) == {"Kitralus"}
    for name, synthetic_id in report.heroes_with_synthetic_id.items():
        assert synthetic_id < 0
        leader = state.leaders[synthetic_id]
        assert leader.name == name
        assert leader.sex is None


def test_provinces_and_king_owned_provinces_bridge_same_as_existing_functions():
    state, report = _bridge_fixture()

    assert report.provinces_created == 162
    # Phase 339: roster-matched Heroes now have real ids in state.leaders
    # too, so resolve_province_owners() resolves every Hero-governed
    # province as well, not just the 10 King-owned ones -- a real
    # improvement over Phase 338's narrower scope, not a regression.
    assert report.provinces_with_resolved_owner > report.kings_created
    pearlgate = state.provinces[HexCoord(16, 2)]
    assert pearlgate.name == "Pearlgate"
    assert pearlgate.owner_kingdom_id == 7
    # Transylvania is personally governed by Philo, an independent Hero
    # (kingdom_id=None) -- now resolvable directly, unlike Phase 338.
    transylvania = state.provinces[HexCoord(1, 5)]
    assert transylvania.name == "Transylvania"
    assert transylvania.owner_kingdom_id is None


def test_army_bridging_splits_mercenary_king_led_and_hero_led_correctly():
    state, report = _bridge_fixture()

    army_records = parse_gw_armies(FIXTURE)
    assert (
        report.armies_created + len(report.unresolved_army_records) + report.dead_army_records_excluded
        == len(army_records)
    )
    # GW3__T1 (pre-turn-1) is confirmed to have zero DEAD rows -- the
    # exclusion counter above should therefore be 0 for this fixture.
    assert report.dead_army_records_excluded == 0

    # Phase 337's own confirmed mercenary count for this fixture -- every
    # one bridges to kingdom_id=None/commanded_by=None (not skipped, not
    # confused with a province whose owner just couldn't be resolved).
    mercenary_count = sum(1 for r in army_records if r.is_mercenary)
    assert mercenary_count == 10
    for record in army_records:
        if record.is_mercenary:
            matches = [
                a
                for a in state.armies.values()
                if a.location == record.coord and a.army_type == record.army_type and a.quality == record.quality
            ]
            assert any(a.commanded_by is None and a.kingdom_id is None for a in matches)
            # Bug fix (2026-10-25): the real `is_mercenary` marker used
            # to be silently dropped on import -- see `ArmyState.
            # is_mercenary`'s own docstring.
            assert any(a.is_mercenary for a in matches)

    # And an *unled* row at a province with no real owning Kingdom (a
    # native garrison, not a real mercenary) must bridge to
    # `is_mercenary=False`, even though it also lands at
    # `kingdom_id=None` -- same bug fix, the other direction.
    unled_unowned_non_mercenary_records = [
        r
        for r in army_records
        if not r.is_mercenary and r.commanded_by_leader_id is None and r.state is not MonsterEngagementState.DEAD
    ]
    found_any_unled_unowned = False
    for record in unled_unowned_non_mercenary_records:
        province = state.provinces.get(record.coord)
        if province is None or province.owner_kingdom_id is not None:
            continue
        found_any_unled_unowned = True
        matches = [
            a
            for a in state.armies.values()
            if a.location == record.coord and a.army_type == record.army_type and a.quality == record.quality
        ]
        assert any(a.kingdom_id is None and a.is_mercenary is False for a in matches)
    assert found_any_unled_unowned

    # No King happens to command a Block B row at T1 in this fixture, but
    # the invariant must hold for any that do: a King's own leader_id
    # equals his kingdom_id (Phase 330), so a King-led army's commanded_by
    # and kingdom_id must always agree.
    for army in state.armies.values():
        if army.commanded_by is not None and state.leaders[army.commanded_by].is_king:
            assert army.commanded_by == army.kingdom_id

    # Phase 339: a roster-matched Hero's own led rows now bridge directly
    # too, owned by his own real kingdom_id (the Liege field) -- NOT his
    # own leader_id, which only coincides with kingdom_id for a King.
    # Philo's own 2 real Axemen rows (Phase 336's Dwarven-Axemen
    # cross-check) are the concrete case: he's an independent Hero
    # (kingdom_id=None), so this specifically catches the "used the
    # wrong id for ownership" bug class a synthetic-id-only test can't.
    philos_armies = [a for a in state.armies.values() if a.commanded_by == 70]
    assert len(philos_armies) == 2
    for army in philos_armies:
        assert army.army_type is ArmyType.AXEMEN
        assert army.kingdom_id is None

    # Only a row led by a genuinely un-rostered (synthetic-id) Hero ends
    # up unresolved -- its own commanded_by_leader_id is a real id no
    # `LeaderState` this bridge built actually carries as a key,
    # because a synthetic id is always negative.
    for record in report.unresolved_army_records:
        assert record.commanded_by_leader_id is not None
        assert record.commanded_by_leader_id not in state.leaders


def test_bridge_new_game_state_excludes_dead_block_b_rows():
    # Phase 789: a Block B row whose own `state` is `MonsterEngagementState.
    # DEAD` is a real historical dead army, not a live/garrison unit --
    # confirmed by cross-referencing GW6 against the full GW3__T1-T12
    # corpus. `bridge_new_game_state()` must exclude it entirely: not
    # bridged into `state.armies`, not added to `unresolved_army_records`
    # either (the `continue` fires before that fallback branch), and
    # counted in the report's own new `dead_army_records_excluded` field.
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)

    baseline_state, baseline_report = bridge_new_game_state(leader_records, province_records, army_records)
    assert baseline_report.dead_army_records_excluded == 0

    # GW3__T1 has zero real DEAD rows (confirmed) -- synthesize one from
    # a real HIRED, uncommanded row (bridges as a live army today) so
    # the fixture stays otherwise realistic and the exclusion has a real
    # effect to prove.
    hired_index = next(
        i
        for i, r in enumerate(army_records)
        if r.state is MonsterEngagementState.HIRED and r.commanded_by_leader_id is None
    )
    dead_record = replace(army_records[hired_index], state=MonsterEngagementState.DEAD)
    synthetic_records = list(army_records)
    synthetic_records[hired_index] = dead_record

    state, report = bridge_new_game_state(leader_records, province_records, synthetic_records)

    assert report.dead_army_records_excluded == 1
    assert (
        report.armies_created + len(report.unresolved_army_records) + report.dead_army_records_excluded
        == len(synthetic_records)
    )
    # Exactly one fewer live army was bridged than the unmodified baseline.
    assert report.armies_created == baseline_report.armies_created - 1
    assert len(state.armies) == len(baseline_state.armies) - 1
    # The synthesized DEAD row was not shunted into unresolved_army_records.
    assert dead_record not in report.unresolved_army_records


def test_apply_confirmed_hero_ids_rekeys_and_recovers_his_own_armies():
    # Phase 366's re-verification leaves only Kitralus (a genuine
    # VALHALLA arrival) as a candidate for this fallback path; a
    # hypothetical real id is supplied here purely to exercise the
    # re-keying/army-recovery mechanism itself.
    state, report = _bridge_fixture()
    synthetic_kitralus_id = report.heroes_with_synthetic_id["Kitralus"]

    applied = apply_confirmed_hero_ids(state, {"Kitralus": 991}, report.unresolved_army_records)

    assert applied.leaders_rekeyed == 1
    assert applied.not_found_names == []
    assert synthetic_kitralus_id not in state.leaders
    assert state.leaders[991].name == "Kitralus"
    assert applied.armies_recovered >= 0
    for army in state.armies.values():
        if army.commanded_by == 991:
            assert army.kingdom_id == state.leaders[991].kingdom_id

    # Philo's own 2 real Axemen rows (Phase 336/338's own Dwarven-Axemen
    # cross-check) get recovered, owned by his own real kingdom_id --
    # NOT his own leader_id (70) -- Philo is an independent Hero
    # (kingdom_id=None), so this specifically catches the "used the
    # wrong id for ownership" bug class.
    philos_armies = [a for a in state.armies.values() if a.commanded_by == 70]
    assert len(philos_armies) == 2
    for army in philos_armies:
        assert army.army_type is ArmyType.AXEMEN
        assert army.kingdom_id is None  # Philo's own real kingdom_id, not his leader_id


def test_apply_confirmed_hero_ids_reports_a_name_with_no_synthetic_match():
    state, report = _bridge_fixture()

    applied = apply_confirmed_hero_ids(state, {"Nobody Real": 999}, report.unresolved_army_records)

    assert applied.leaders_rekeyed == 0
    assert applied.not_found_names == ["Nobody Real"]


# -- Phase 788: bridge_new_game_state(king_extensions=...) --------------


def test_bridge_new_game_state_without_king_extensions_leaves_kingdom_defaults():
    # Default (None, every pre-Phase-788 caller/test) -- no data isn't a
    # guess, so every King stays at GameState's own real defaults.
    state, _ = _bridge_fixture()

    babba = state.kingdoms[0]
    assert babba.treasury == 0
    assert babba.discoveries == set()
    assert babba.valhalla_visit_count == 0
    assert state.kingdoms_met == set()
    assert state.allied_kingdoms == set()


def test_bridge_new_game_state_threads_real_king_extension_fields():
    leader_records = parse_gw_leaders(FIXTURE.parent / "GW3__T5")
    province_records = parse_gw_world(FIXTURE.parent / "GW3__T5")
    army_records = parse_gw_armies(FIXTURE.parent / "GW3__T5")
    king_extensions = parse_gw_king_extensions(FIXTURE.parent / "GW3__T5")

    state, _ = bridge_new_game_state(
        leader_records, province_records, army_records, king_extensions=king_extensions
    )

    babba = state.kingdoms[0]
    assert babba.treasury == 15
    assert babba.discoveries == set()  # real fixture: no Discovery owned yet by any King
    assert babba.valhalla_visit_count == 0

    # king0's own real met_kings_bitmask has bits 1, 8, 9 set -- every
    # other King's own met_kings_bitmask also contributes real pairs,
    # so this checks a subset, not exact equality.
    assert {frozenset({0, 1}), frozenset({0, 8}), frozenset({0, 9})} <= state.kingdoms_met
    # king0<->king1 and king0<->king9 both mutually record ALLIED for
    # each other in this real fixture -- a genuine, symmetric alliance.
    assert frozenset({0, 1}) in state.allied_kingdoms
    assert frozenset({0, 9}) in state.allied_kingdoms
    # king0 says NEUTRAL toward king2 (and king2 says NEUTRAL back) --
    # never bridged as an alliance.
    assert frozenset({0, 2}) not in state.allied_kingdoms


def test_bridge_new_game_state_bridges_a_real_mutual_enemy_pair_as_war():
    # Bug fix (2026-11-02): king0<->king5 mutually record ENEMY for each
    # other in this real fixture (a genuine war), but the bridge used to
    # only ever look at ALLIED, so this pair silently loaded as Neutral
    # instead -- letting their armies get blocked from attacking each
    # other by the Neutral-relations movement rule, despite the save
    # file recording them as already at war.
    leader_records = parse_gw_leaders(FIXTURE.parent / "GW3__T5")
    province_records = parse_gw_world(FIXTURE.parent / "GW3__T5")
    army_records = parse_gw_armies(FIXTURE.parent / "GW3__T5")
    king_extensions = parse_gw_king_extensions(FIXTURE.parent / "GW3__T5")

    state, _ = bridge_new_game_state(
        leader_records, province_records, army_records, king_extensions=king_extensions
    )

    assert state.diplomatic_relation(0, 5) is DiplomaticRelation.ENEMY
    assert state.diplomatic_relation(0, 7) is DiplomaticRelation.ENEMY
    assert state.diplomatic_relation(0, 8) is DiplomaticRelation.ENEMY
    assert not state.is_allied(0, 5)


def _synthetic_king_extension(*, diplomatic_relations: tuple[DiplomaticRelation, ...]) -> GWKingExtension:
    return GWKingExtension(
        is_male=True,
        treasury=0,
        alliance_requests_bitmask=0,
        break_treaty_requests_bitmask=0,
        account_number=0,
        player_mode=0,
        met_kings_bitmask=0,
        send_method=KingSendMethod.COMPUSERVE,
        election_request_or_previous_choice=0,
        payment_percent=0,
        miscellaneous_fee=0,
        turn_funds_received=0,
        consecutive_missed_turns=0,
        standby_state=KingStandbyState.NO,
        standby_max_percent=0,
        prize_credit=0,
        raw_administrative_flag=0,
        moves_read_success=False,
        order_interpreter_version=0,
        diplomatic_relations=diplomatic_relations,
        discovered=frozenset(),
        valhalla_visit_count=0,
        king_information_flags=0,
        disk_delivery_flags=0,
        king_power_or_votes_cast=0,
        moves_insurance=False,
        team_state=0,
        active_blackmailer_king_id=None,
        pending_blackmailer_king_id=None,
        power_percent=0,
        trailing_compatibility_zeros=(0, 0, 0, 0, 0),
        title_prefix="",
        title_suffix="",
        player_name="",
    )


def test_bridge_new_game_state_never_bridges_a_one_sided_alliance_claim():
    # A synthetic case, since the real GW3 corpus happens to have no
    # one-sided ALLIED claim to test against directly (Phase 788's own
    # research found every real ALLIED claim in the available fixtures
    # is mutually reciprocated) -- king 0 claims ALLIED toward king 1,
    # but king 1's own recorded view of king 0 is only NEUTRAL. `kallst`
    # is a directed, per-King array (this King's own view of every
    # other King), so a one-sided value could be a still-pending
    # request rather than a real, accepted alliance.
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)
    king_extensions = [
        _synthetic_king_extension(diplomatic_relations=(DiplomaticRelation.ALLIED, DiplomaticRelation.ALLIED)),
        _synthetic_king_extension(diplomatic_relations=(DiplomaticRelation.NEUTRAL, DiplomaticRelation.ALLIED)),
    ]

    state, _ = bridge_new_game_state(
        leader_records, province_records, army_records, king_extensions=king_extensions
    )

    assert frozenset({0, 1}) not in state.allied_kingdoms


def test_bridge_new_game_state_never_bridges_a_one_sided_enemy_claim_as_war():
    # Mirrors the one-sided-alliance test above: king 0 claims ENEMY
    # toward king 1, but king 1's own recorded view of king 0 is only
    # NEUTRAL -- a still-pending declaration, not a settled war, so it
    # stays Neutral (the missing-pair default) rather than bridging a
    # one-sided claim as a real war.
    leader_records = parse_gw_leaders(FIXTURE)
    province_records = parse_gw_world(FIXTURE)
    army_records = parse_gw_armies(FIXTURE)
    king_extensions = [
        _synthetic_king_extension(diplomatic_relations=(DiplomaticRelation.NEUTRAL, DiplomaticRelation.ENEMY)),
        _synthetic_king_extension(diplomatic_relations=(DiplomaticRelation.NEUTRAL, DiplomaticRelation.NEUTRAL)),
    ]

    state, _ = bridge_new_game_state(
        leader_records, province_records, army_records, king_extensions=king_extensions
    )

    assert state.diplomatic_relation(0, 1) is DiplomaticRelation.NEUTRAL
