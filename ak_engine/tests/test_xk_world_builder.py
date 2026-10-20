"""Tests for parser/xk_world_builder.py -- Fase 3 of the XK-encoder plan
(Phase 1026): generating a brand-new per-Kingdom XKWorld directly from
GameState. See that module's own docstring for the documented defaults
used for byte ranges this engine has no real source for.

Acceptance criterion (per the approved plan): a file built here, written
by xk_world_writer.write_xk_world(), re-parses cleanly through parser/
xk_world.py parse_xk_world() -- not a guarantee the real SAGA client
would accept it, just this project's own strict decoder.
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.parser.xk_world import XKParseError, parse_xk_world
from ak_engine.parser.xk_world_builder import build_xk_world_for_kingdom
from ak_engine.parser.xk_world_writer import write_xk_world
from ak_engine.turn.combat import Quality

BOARD_WIDTH = 6
BOARD_HEIGHT = 6


def _realistic_state() -> GameState:
    state = GameState()
    state.turn_number = 3
    state.board_width = BOARD_WIDTH
    state.board_height = BOARD_HEIGHT
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(5, 5)))

    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            owner = 1 if (x, y) == (0, 0) else (2 if (x, y) == (5, 5) else None)
            province = ProvinceState(
                HexCoord(x, y),
                Terrain.PLAINS,
                Race.HUMAN,
                owner_kingdom_id=owner,
                tax=5 if owner is not None else None,
                name=f"P{x}{y}",
            )
            if owner == 1:
                province.explored_percent_by_kingdom[1] = 100
            state.add_province(province)

    king_a = LeaderState(1, 1, "King Aldric", HexCoord(0, 0), is_king=True, alignment=Alignment.GOOD)
    king_b = LeaderState(2, 2, "King Morgath", HexCoord(5, 5), is_king=True, alignment=Alignment.EVIL)
    state.add_leader(king_a)
    state.add_leader(king_b)
    state.add_leader(LeaderState(10, 1, "Hero Galen", HexCoord(0, 0), hire_turn=2))

    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=1))
    state.add_army(ArmyState(102, 2, ArmyType.GARRISON, Quality.ELITE, HexCoord(5, 5)))
    state.add_army(ArmyState(103, None, ArmyType.PHALANX, Quality.GREEN, HexCoord(0, 0)))  # mercenary, near kingdom 1

    feature = Feature(
        feature_id=1,
        coord=HexCoord(1, 1),
        kind=FeatureType.CAVE,
        guardian_monster=Monster.TROLL,
        treasure=Treasure.ABILITY_TACTICAL,
    )
    feature.discovered_by_kingdom[1] = 3
    state.add_feature(feature)
    return state


def test_builds_and_roundtrips_for_both_kingdoms():
    state = _realistic_state()
    for kingdom_id in (1, 2):
        world = build_xk_world_for_kingdom(state, kingdom_id)
        data = write_xk_world(world)
        path = pathlib.Path(tempfile.mktemp())
        try:
            path.write_bytes(data)
            reparsed = parse_xk_world(path)
        finally:
            path.unlink(missing_ok=True)
        assert reparsed.header.kingdom_id == kingdom_id


def test_own_kingdoms_leader_gets_a_full_card_not_a_partial_one():
    state = _realistic_state()
    world = build_xk_world_for_kingdom(state, 1)
    full_card_ids = {card.leader_id for card in world.leader_cards}
    partial_ids = {card.leader_id for card in world.partial_leader_cards}
    assert 1 in full_card_ids
    assert 10 in full_card_ids
    assert 1 not in partial_ids
    assert 10 not in partial_ids


def test_foreign_king_known_by_location_gets_a_partial_card_not_a_full_one():
    state = _realistic_state()
    world = build_xk_world_for_kingdom(state, 1)
    # King Morgath (leader_id 2) sits on his own throne province (5,5) --
    # leader_location_known_to_kingdom()'s own "sitting on own throne"
    # guard means he is never revealed this way; this just asserts he
    # never gets a full card in a foreign Kingdom's own file either way.
    full_card_ids = {card.leader_id for card in world.leader_cards}
    assert 2 not in full_card_ids


def test_own_provinces_known_a_foreign_unexplored_province_is_not():
    state = _realistic_state()
    world = build_xk_world_for_kingdom(state, 1)
    coords = {p.coord for p in world.provinces}
    assert HexCoord(0, 0) in coords
    assert HexCoord(5, 5) not in coords


def test_own_army_is_revealed_with_real_quality():
    state = _realistic_state()
    world = build_xk_world_for_kingdom(state, 1)
    own_army = next(a for a in world.armies if a.coord == HexCoord(0, 0) and a.commanded_by_leader_id == 1)
    assert own_army.quality_or_mask == Quality.AVERAGE.value


def test_nearby_mercenary_army_is_known_via_known_mercenary_rule():
    state = _realistic_state()
    world = build_xk_world_for_kingdom(state, 1)
    mercenary_records = [a for a in world.armies if a.race is not None and a.coord == HexCoord(0, 0) and a.commanded_by_leader_id is None]
    assert len(mercenary_records) == 1


def test_account_number_and_treasury_are_read_from_kingdom_state():
    state = _realistic_state()
    state.kingdoms[1].account_number = 42
    state.kingdoms[1].treasury = 777
    world = build_xk_world_for_kingdom(state, 1)
    assert world.account_number == 42
    assert world.treasury == 777


def test_sibling_supplies_the_shared_turn_level_blocks():
    state = _realistic_state()
    world_a = build_xk_world_for_kingdom(state, 1)
    world_a.globals.flags_c3fc = bytes([7]) + bytes(255)
    world_b = build_xk_world_for_kingdom(state, 2, sibling=world_a)
    assert world_b.globals.flags_c3fc == world_a.globals.flags_c3fc


def test_no_sibling_zero_fills_the_shared_turn_level_blocks():
    state = _realistic_state()
    world = build_xk_world_for_kingdom(state, 1)
    assert world.globals.flags_c3fc == bytes(256)
    assert world.globals.flags_c4fc == bytes(256)
    assert world.secondary_terrain.raw == bytes(450)


def test_diplomatic_relations_reflect_gamestate():
    state = _realistic_state()
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY
    world = build_xk_world_for_kingdom(state, 1)
    assert world.diplomatic_relations[2] is DiplomaticRelation.ENEMY
    assert world.diplomatic_relations[1] is DiplomaticRelation.ALLIED  # self-relation


def test_king_title_defaults_empty_unless_set():
    state = _realistic_state()
    world = build_xk_world_for_kingdom(state, 1)
    assert world.king_titles.prefix_by_king_id[1] == ""
    state.kingdoms[1].king_title_prefix = "Lord"
    world = build_xk_world_for_kingdom(state, 1)
    assert world.king_titles.prefix_by_king_id[1] == "Lord"


def test_army_count_over_255_skips_index_255():
    state = _realistic_state()
    for i in range(300):
        state.add_army(ArmyState(1000 + i, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=1))
    world = build_xk_world_for_kingdom(state, 1)
    data = write_xk_world(world)
    path = pathlib.Path(tempfile.mktemp())
    try:
        path.write_bytes(data)
        reparsed = parse_xk_world(path)
    finally:
        path.unlink(missing_ok=True)
    assert 255 not in {army.army_index for army in reparsed.armies}


def test_negative_synthetic_leader_id_is_excluded_from_full_and_partial_cards():
    # Found verifying against a real bridged GameState
    # (parser/gw_world_bridge.py bridge_new_game_state()): a Hero outside
    # the fixed roster match gets a synthetic *negative* leader_id there
    # -- the real XK leader_id space is 0..leader_capacity-1 only, so
    # this builder must skip such a leader rather than crash the writer.
    state = _realistic_state()
    state.add_leader(LeaderState(-1, 1, "Unidentified Valhalla Arrival", HexCoord(0, 0)))

    world = build_xk_world_for_kingdom(state, 1)
    data = write_xk_world(world)  # must not raise

    full_card_ids = {card.leader_id for card in world.leader_cards}
    partial_ids = {card.leader_id for card in world.partial_leader_cards}
    assert -1 not in full_card_ids
    assert -1 not in partial_ids
    assert all(0 <= name_id < 100 for name_id in range(len(world.leader_names)))


def test_army_commanded_by_a_negative_synthetic_leader_id_is_reported_unled():
    state = _realistic_state()
    state.add_leader(LeaderState(-1, 1, "Unidentified Valhalla Arrival", HexCoord(0, 0)))
    state.add_army(ArmyState(999, 1, ArmyType.GARRISON, Quality.AVERAGE, HexCoord(0, 0), commanded_by=-1))

    world = build_xk_world_for_kingdom(state, 1)
    write_xk_world(world)  # must not raise

    record = next(a for a in world.armies if a.army_index == sorted(state.armies).index(999))
    assert record.commanded_by_leader_id is None


def test_synthetic_item_feature_id_never_collides_with_a_real_features_own_id():
    # Bug fix: the synthetic feature_id _build_treasures_from_items()
    # assigns a Hero-held item used to start from len(state.features),
    # not the next truly-unused id -- a real collision as soon as any
    # feature id isn't contiguous from 0 (e.g. _realistic_state()'s own
    # single feature already sits at feature_id=1, matching len(features)
    # exactly, so the item below used to be assigned that same id 1,
    # duplicating the real feature's own treasure record).
    state = _realistic_state()
    state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=1)

    world = build_xk_world_for_kingdom(state, 1)
    write_xk_world(world)  # must not raise

    feature_ids = [t.feature_id for t in world.treasures]
    assert len(feature_ids) == len(set(feature_ids)), f"duplicate feature_id in treasures: {feature_ids}"


def test_item_owned_by_a_negative_synthetic_leader_id_is_omitted():
    state = _realistic_state()
    state.add_leader(LeaderState(-1, 1, "Unidentified Valhalla Arrival", HexCoord(0, 0)))
    state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=-1)

    world = build_xk_world_for_kingdom(state, 1)
    write_xk_world(world)  # must not raise

    assert all(t.trowner != -1 for t in world.treasures)


# -- Real-data verification (plan's own Fase 3 "Verifica" step) --

GW_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "world" / "G3"


def _bridged_real_state(gw_path: pathlib.Path) -> GameState:
    from ak_engine.parser.gw_world import parse_gw_armies, parse_gw_king_extensions, parse_gw_leaders, parse_gw_world
    from ak_engine.parser.gw_world_bridge import bridge_new_game_state

    provinces = parse_gw_world(gw_path)
    leaders = parse_gw_leaders(gw_path)
    armies = parse_gw_armies(gw_path)
    king_extensions = parse_gw_king_extensions(gw_path)
    state, _report = bridge_new_game_state(leaders, provinces, armies, turn_number=1, king_extensions=king_extensions)
    # gw_world_bridge.py doesn't populate per-kingdom exploration at all
    # (a separate, pre-existing gap outside this plan's own scope) -- a
    # Kingdom trivially knows its own territory, so seed that much for a
    # real exercise of the known-province path.
    for province in state.provinces.values():
        if province.owner_kingdom_id is not None:
            province.explored_percent_by_kingdom[province.owner_kingdom_id] = 100
    return state


@pytest.mark.parametrize("fixture_name", ["GW3__T1", "GW3__T12"])
def test_builds_for_every_real_kingdom_in_a_bridged_real_world(fixture_name):
    # Phase 1026: this exact test, run by hand against GW3__T1, is what
    # first found the negative-synthetic-leader_id crash fixed above --
    # kept as a permanent regression test against real data, not just the
    # synthetic fixtures above.
    state = _bridged_real_state(GW_FIXTURE_DIR / fixture_name)
    for kingdom_id in sorted(state.kingdoms):
        world = build_xk_world_for_kingdom(state, kingdom_id)
        data = write_xk_world(world)
        path = pathlib.Path(tempfile.mktemp())
        try:
            path.write_bytes(data)
            reparsed = parse_xk_world(path)
        finally:
            path.unlink(missing_ok=True)
        assert reparsed.header.kingdom_id == kingdom_id
        assert len(reparsed.armies) == len(state.armies)
        kingdom_still_owns_territory = any(p.owner_kingdom_id == kingdom_id for p in state.provinces.values())
        if kingdom_still_owns_territory:
            # A real Kingdom defeated by this turn (owns nothing in the
            # source state -- a real, correct GW3__T12 outcome, not a
            # bug) has nothing of its own to assert here.
            assert any(p.owner_kingdom_id == kingdom_id for p in reparsed.provinces)
