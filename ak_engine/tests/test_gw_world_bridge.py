"""Tests for the GW-world-to-`GameState.provinces` coordinate bridge.

See `parser/gw_world_bridge.py`'s own module docstring for the empirical,
100%-match evidence behind the column-major coordinate mapping this
module implements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_leaders, parse_gw_world
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


def test_every_hero_gets_a_synthetic_negative_id_but_real_data():
    state, report = _bridge_fixture()

    assert report.heroes_created == 90
    guerin_id = report.hero_synthetic_ids["Guerin"]
    assert guerin_id < 0
    guerin = state.leaders[guerin_id]
    assert guerin.is_king is False
    assert guerin.race is Race.ELVEN
    assert guerin.alignment is Alignment.UNDEAD
    # Liege field (Phase 325/327, confirmed real) -- Guerin serves
    # kingdom 1 (Uga-Buga Makumb), matching every earlier cross-check.
    assert guerin.kingdom_id == 1


def test_provinces_and_king_owned_provinces_bridge_same_as_existing_functions():
    state, report = _bridge_fixture()

    assert report.provinces_created == 162
    assert report.provinces_with_resolved_owner == report.kings_created
    pearlgate = state.provinces[HexCoord(16, 2)]
    assert pearlgate.name == "Pearlgate"
    assert pearlgate.owner_kingdom_id == 7


def test_army_bridging_splits_mercenary_king_led_and_hero_led_correctly():
    state, report = _bridge_fixture()

    army_records = parse_gw_armies(FIXTURE)
    assert report.armies_created + len(report.unresolved_army_records) == len(army_records)

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

    # No King happens to command a Block B row at T1 in this fixture, but
    # the invariant must hold for any that do: a King's own leader_id
    # equals his kingdom_id (Phase 330), so a King-led army's commanded_by
    # and kingdom_id must always agree.
    for army in state.armies.values():
        if army.commanded_by is not None:
            assert army.commanded_by == army.kingdom_id

    # Every unresolved record is genuinely Hero-led (not unled, not a King).
    king_ids = {leader.leader_id for leader in state.leaders.values() if leader.is_king}
    for record in report.unresolved_army_records:
        assert record.commanded_by_leader_id is not None
        assert record.commanded_by_leader_id not in king_ids


def test_apply_confirmed_hero_ids_rekeys_and_recovers_his_own_armies():
    state, report = _bridge_fixture()
    synthetic_guerin_id = report.hero_synthetic_ids["Guerin"]
    synthetic_philo_id = report.hero_synthetic_ids["Philo"]

    applied = apply_confirmed_hero_ids(state, {"Guerin": 18, "Philo": 70}, report.unresolved_army_records)

    assert applied.leaders_rekeyed == 2
    assert applied.not_found_names == []
    assert synthetic_guerin_id not in state.leaders
    assert synthetic_philo_id not in state.leaders
    assert state.leaders[18].name == "Guerin"
    assert state.leaders[70].name == "Philo"

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
