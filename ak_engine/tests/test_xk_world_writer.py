"""Tests for ``parser/xk_world_writer.py`` -- the ``XK`` binary writer.

The main acceptance criterion (Phase 1026, see that module's own
docstring): ``write_xk_world(parse_xk_world(path))`` is byte-identical to
``path.read_bytes()`` for every one of the 17 real fixtures. Everything
else here isolates *where* a round trip would break, using real parsed
data rather than hand-built synthetic records.
"""

from __future__ import annotations

import dataclasses

import pytest

from ak_engine.models.treasure import Treasure
from ak_engine.parser.xk_world import (
    _TR_LLS_END,
    _Reader,
    _read_army,
    _read_feature,
    _read_leader_card,
    _read_province,
    _read_treasure,
    parse_xk_world,
)
from ak_engine.parser.xk_world_writer import (
    _write_army,
    _write_feature,
    _write_leader_card,
    _write_partial_leader_card,
    _write_province,
    _write_treasure,
    _Writer,
    write_xk_world,
)
from tests.test_xk_world_parser import ALL_17_SAMPLES


@pytest.mark.parametrize("fixture", ALL_17_SAMPLES)
def test_roundtrip_is_byte_identical_to_the_real_file(fixture):
    original_bytes = fixture.read_bytes()
    world = parse_xk_world(fixture)
    rewritten_bytes = write_xk_world(world)
    assert rewritten_bytes == original_bytes


@pytest.mark.parametrize("fixture", ALL_17_SAMPLES)
def test_leader_cards_roundtrip_field_by_field(fixture):
    world = parse_xk_world(fixture)
    for card in world.leader_cards:
        w = _Writer()
        _write_leader_card(w, card)
        r = _Reader(w.getvalue())
        reread = _read_leader_card(r)
        assert reread == card


@pytest.mark.parametrize("fixture", ALL_17_SAMPLES)
def test_partial_leader_cards_roundtrip(fixture):
    world = parse_xk_world(fixture)
    for partial in world.partial_leader_cards:
        w = _Writer()
        _write_partial_leader_card(w, partial)
        r = _Reader(w.getvalue())
        leader_id = r.u8("id")
        x = r.u8("x")
        y = r.u8("y")
        assert (leader_id, x, y) == (partial.leader_id, partial.coord.x, partial.coord.y)


@pytest.mark.parametrize("fixture", ALL_17_SAMPLES)
def test_provinces_roundtrip_field_by_field(fixture):
    world = parse_xk_world(fixture)
    for province in world.provinces:
        w = _Writer()
        _write_province(w, province)
        r = _Reader(w.getvalue())
        reread = _read_province(r)
        assert reread == province


def test_provinces_cover_all_three_ownership_branches_in_the_corpus():
    owned = no_visible_owner = no_ownership_info = 0
    for fixture in ALL_17_SAMPLES:
        for province in parse_xk_world(fixture).provinces:
            if province.owner_kingdom_id is not None:
                owned += 1
            elif province.no_ownership_info:
                no_ownership_info += 1
            else:
                no_visible_owner += 1
    assert owned > 0
    assert no_visible_owner > 0
    assert no_ownership_info > 0


@pytest.mark.parametrize("fixture", ALL_17_SAMPLES)
def test_features_roundtrip_field_by_field(fixture):
    world = parse_xk_world(fixture)
    for feature in world.features:
        w = _Writer()
        _write_feature(w, feature)
        r = _Reader(w.getvalue())
        reread = _read_feature(r)
        assert reread == feature


@pytest.mark.parametrize("fixture", ALL_17_SAMPLES)
def test_treasures_roundtrip_field_by_field(fixture):
    world = parse_xk_world(fixture)
    for treasure in world.treasures:
        w = _Writer()
        _write_treasure(w, treasure)
        r = _Reader(w.getvalue())
        reread = _read_treasure(r)
        assert reread == treasure


def test_treasures_without_charges_are_present_in_the_corpus():
    assert any(
        treasure.trcharges is None for fixture in ALL_17_SAMPLES for treasure in parse_xk_world(fixture).treasures
    )


def test_treasure_with_charges_roundtrips_even_though_no_real_sample_has_one():
    # No fixture in the 17-file corpus has a treasure ordinal in [70, 92)
    # (confirmed: the real ordinals present are a fixed, disjoint set) --
    # this branch is exercised with a constructed record instead, per the
    # Fase 1 plan's own "build the case if no real example exists" note.
    original = next(
        treasure for fixture in ALL_17_SAMPLES for treasure in parse_xk_world(fixture).treasures if treasure.trcharges is None
    )
    with_charges = dataclasses.replace(original, treasure=Treasure(70), trcharges=3)
    w = _Writer()
    _write_treasure(w, with_charges)
    r = _Reader(w.getvalue())
    reread = _read_treasure(r)
    assert reread == with_charges


@pytest.mark.parametrize("fixture", ALL_17_SAMPLES)
def test_armies_roundtrip_field_by_field(fixture):
    world = parse_xk_world(fixture)
    for army in world.armies:
        w = _Writer()
        _write_army(w, army)
        r = _Reader(w.getvalue())
        reread = _read_army(r, army.army_index)
        assert reread == army


def test_armies_cover_both_short_and_long_forms_in_the_corpus():
    short_form = long_form = 0
    for fixture in ALL_17_SAMPLES:
        for army in parse_xk_world(fixture).armies:
            if army.coord is None:
                short_form += 1
            else:
                long_form += 1
    assert short_form > 0
    assert long_form > 0


def test_at_least_one_real_fixture_exercises_the_army_index_255_skip():
    assert any(parse_xk_world(fixture).globals.army_count > 255 for fixture in ALL_17_SAMPLES)
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        if world.globals.army_count > 255:
            indices = [army.army_index for army in world.armies]
            assert 255 not in indices
            assert indices == sorted(indices)


def test_tr_lls_uses_0xff_as_its_own_sentinel_not_0xfe():
    for fixture in ALL_17_SAMPLES:
        world = parse_xk_world(fixture)
        if world.liege_extension is not None and world.liege_extension.liege_by_leader_id:
            assert _TR_LLS_END == 0xFF
            return
    pytest.fail("no fixture exercised a non-empty TR_LLs extension")


def test_write_leader_card_rejects_leader_id_colliding_with_sentinel():
    world = parse_xk_world(ALL_17_SAMPLES[0])
    bad_card = dataclasses.replace(world.leader_cards[0], leader_id=0xFE)
    w = _Writer()
    with pytest.raises(ValueError, match="sentinel"):
        _write_leader_card(w, bad_card)


def test_write_province_rejects_owner_kingdom_id_colliding_with_sentinel():
    world = parse_xk_world(ALL_17_SAMPLES[0])
    owned = next(p for p in world.provinces if p.owner_kingdom_id is not None)
    bad_province = dataclasses.replace(owned, owner_kingdom_id=0xFE)
    w = _Writer()
    with pytest.raises(ValueError, match="sentinel"):
        _write_province(w, bad_province)


def test_write_army_requires_detail_status_when_coord_is_present():
    long_form = next(a for a in parse_xk_world(ALL_17_SAMPLES[0]).armies if a.coord is not None)
    bad_army = dataclasses.replace(long_form, detail_status=None)
    w = _Writer()
    with pytest.raises(ValueError, match="detail_status"):
        _write_army(w, bad_army)
