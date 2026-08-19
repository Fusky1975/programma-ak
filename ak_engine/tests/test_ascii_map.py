"""Tests for report/ascii_map.py -- see its module docstring for the full,
sourced derivation. The two full-band tests below are the primary
verification: byte-for-byte diffs against real `Desktop/SE3__T1.K2`
fragments transcribed directly during this session's own research
(lines 308-313 and 314-319).
"""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.report.ascii_map import (
    TERRAIN_SYMBOL,
    _pad_center,
    _pad_framed,
    _recruit_abbreviation,
    _race_name_plural,
    cell_pixel_column,
    render_ascii_map,
    render_cell,
)

HOME = HexCoord(0, 0)


def _state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(2, "Kingdom2", Race.HUMAN, None, HOME))
    return state


def _province(x: int, y: int, name: str, terrain: Terrain, race: Race, *, owner: int | None, tax: int, t1: ArmyType | None, t2: ArmyType | None, expl: int) -> ProvinceState:
    province = ProvinceState(HexCoord(x, y), terrain, race, owner_kingdom_id=owner, explored_percent=expl, name=name)
    province.tax = tax
    province.recruit_type_1 = t1
    province.recruit_type_2 = t2
    return province


# -- cell_pixel_column() -- the real horizontal stagger formula --


def test_cell_pixel_column_odd_row_no_stagger():
    assert cell_pixel_column(HexCoord(1, 5)) == 0
    assert cell_pixel_column(HexCoord(2, 3)) == 17


def test_cell_pixel_column_even_row_staggers_by_half_a_cell():
    assert cell_pixel_column(HexCoord(1, 4)) == 8
    assert cell_pixel_column(HexCoord(1, 6)) == 8


def test_cell_pixel_column_clamps_x_zero_instead_of_going_negative():
    assert cell_pixel_column(HexCoord(0, 5)) == cell_pixel_column(HexCoord(1, 5))


# -- _pad_center() -- rows 1 and 6's own full-fill, tie-left rule --


def test_pad_center_ties_left_on_odd_padding():
    assert _pad_center("Bam.Yanga(0105)", 16, ".") == ".Bam.Yanga(0105)"


def test_pad_center_even_padding_splits_evenly():
    assert _pad_center("Macondo(0205)", 16, "&") == "&&Macondo(0205)&"


def test_pad_center_truncates_overlong_content_rather_than_crashing():
    assert len(_pad_center("x" * 20, 16, "_")) == 16


# -- _pad_framed() -- rows 2-5's own tick/zone template + overflow --


def test_pad_framed_row2_short_content_ties_left():
    # "Unowned" (7 chars) in the row-2 template (zone 10) -- 3 extra,
    # 2 left/1 right (tie-left, confirmed against SE3__T1.K2's own
    # Shasta cell, line 309).
    result = _pad_framed("Unowned", left_template="T T", zone_width=10, right_template=" TT", symbol="^", tie_left=True)
    assert result == "^ ^  Unowned  ^^"


def test_pad_framed_row35_short_content_ties_right():
    # "Le" (2 chars) in the row-3/5 template (zone 7) -- 5 extra,
    # 2 left/3 right (tie-right, confirmed against SE3__T1.K2's own
    # Tesawa cell, line 304).
    result = _pad_framed("Le", left_template="T   T", zone_width=7, right_template="T  T", symbol="^", tie_left=False)
    assert result == "^   ^  Le   ^  ^"


def test_pad_framed_overflow_grows_at_most_one_left_then_the_rest_right():
    # "Loviatar(92)" (12 chars) over a 10-wide zone -- 2 overflow, 1
    # grows left, 1 grows right (confirmed against SE3__T1.K2's own
    # Bam Yanga cell, line 315).
    result = _pad_framed("Loviatar(92)", left_template="T T", zone_width=10, right_template=" TT", symbol=".", tie_left=True)
    assert result == ". Loviatar(92).."


def test_pad_framed_overflow_of_one_grows_only_left():
    # "Poor" (4 chars) over a 3-wide zone -- 1 overflow, all left
    # (confirmed against SE3__T1.K2's own Tesawa cell, line 305).
    result = _pad_framed("Poor", left_template="T T   T", zone_width=3, right_template="T   TT", symbol="^", tie_left=False)
    assert result == "^ ^   Poor^   ^^"


# -- Recruit abbreviations and race pluralization --


def test_recruit_abbreviation_confirmed_types():
    assert _recruit_abbreviation(ArmyType.LEGION) == "Le"
    assert _recruit_abbreviation(ArmyType.LT_CAVALRY) == "LC"
    assert _recruit_abbreviation(ArmyType.CAMEL_CORPS) == "CC"


def test_recruit_abbreviation_unconfirmed_type_falls_back_to_its_own_value():
    assert _recruit_abbreviation(ArmyType.SPIDERS) == ArmyType.SPIDERS.value


def test_race_name_plural_regular_and_irregular():
    assert _race_name_plural(Race.HUMAN) == "Humans"
    assert _race_name_plural(Race.ORCISH) == "Orcs"
    assert _race_name_plural(Race.EAGLES) == "Eagles"
    assert _race_name_plural(Race.ELVEN) == "Elves"
    assert _race_name_plural(Race.DWARVEN) == "Dwarves"


# -- render_cell() / render_ascii_map() -- full byte-for-byte band checks --


def test_render_ascii_map_matches_real_sample_own_kingdom_and_other_kingdom_band():
    # SE3__T1.K2 lines 314-319: this Kingdom's own provinces (Macondo,
    # Mongu) side by side with another Kingdom's (Bam Yanga, ruled by
    # Loviatar(92); Moongard, ruled by Brunhilda(86)) -- byte-for-byte.
    state = _state()
    state.add_leader(LeaderState(2, 2, "Bradipo I", HOME, is_king=True))
    state.add_leader(LeaderState(92, 99, "Loviatar", HOME, is_king=True))
    state.add_leader(LeaderState(86, 98, "Brunhilda", HOME, is_king=True))
    state.add_kingdom(KingdomState(99, "K99", Race.HUMAN, None, HOME))
    state.add_kingdom(KingdomState(98, "K98", Race.HUMAN, None, HOME))

    state.add_province(_province(1, 5, "Bam Yanga", Terrain.DESERT, Race.HUMAN, owner=99, tax=2, t1=ArmyType.CAMEL_CORPS, t2=None, expl=1))
    state.add_province(_province(2, 5, "Macondo", Terrain.JUNGLE, Race.ORCISH, owner=2, tax=4, t1=ArmyType.PHALANX, t2=None, expl=16))
    state.add_province(_province(3, 5, "Mongu", Terrain.JUNGLE, Race.HUMAN, owner=2, tax=10, t1=ArmyType.LEGION, t2=ArmyType.LT_CAVALRY, expl=100))
    state.add_province(_province(4, 5, "Moongard", Terrain.MTNS, Race.ORCISH, owner=98, tax=1, t1=ArmyType.AXEMEN, t2=ArmyType.HVY_CAVALRY, expl=1))

    lines = render_ascii_map(state, 2)

    assert lines == [
        ".Bam.Yanga(0105) &&Macondo(0205)& &&&Mongu(0305)&& ^Moongard(0405)^",
        ". Loviatar(92).. & Bradipo I(2)&& & Bradipo I(2)&& ^ Brunhilda(86)^",
        ".   .Humans .  . &   & Orcs  &  & &   &Humans &  & ^   ^ Orcs  ^  ^",
        ". .   .CC .   .. & &   &Ph &   && & &   Le,LC   && ^ ^   Ax,HC   ^^",
        ".   . Poor  .  . &   &Tax: 4 &  & &   &Tax: 10&  & ^   ^ Poor  ^  ^",
        "....1%.Expl..... &&&&16%&Expl.&&& &&&100%&Expl.&&& ^^^^1%^Expl.^^^^",
    ]


def test_render_ascii_map_matches_real_sample_other_kingdom_and_unowned_band():
    # SE3__T1.K2 lines 308-313, columns 8 onward: Orielle (another
    # Kingdom's own, ruled by Snorri(23)) and Shasta (unowned, race
    # Eagles) -- byte-for-byte for every row this phase models
    # (Waterford Sea's own overlong-name wrap is deliberately not
    # exercised here -- see module docstring's own deferred-gaps list).
    state = _state()
    state.add_leader(LeaderState(23, 97, "Snorri", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.HUMAN, None, HOME))

    state.add_province(_province(2, 4, "Orielle", Terrain.PLAINS, Race.HUMAN, owner=97, tax=10, t1=ArmyType.LEGION, t2=ArmyType.CHARIOTS, expl=26))
    state.add_province(_province(3, 4, "Shasta", Terrain.MTNS, Race.EAGLES, owner=None, tax=1, t1=ArmyType.EAGLE_WING, t2=None, expl=1))

    lines = render_ascii_map(state, 2)

    # 25 leading spaces: Orielle sits at x=2 -- cell_pixel_column()'s own
    # confirmed formula places it at column 25 when nothing occupies x=1
    # in this same row (Waterford Sea, deliberately not added here).
    pad = " " * 25
    assert lines == [
        pad + "__Orielle(0204)_ ^^Shasta(0304)^^",
        pad + "_ _Snorri(23) __ ^ ^  Unowned  ^^",
        pad + "_   _Humans _  _ ^   ^Eagles ^  ^",
        pad + "_ _   Le,Ch   __ ^ ^   ^EA ^   ^^",
        pad + "_   Prosperous _ ^   ^ Poor  ^  ^",
        pad + "____26%_Expl.___ ^^^^1%^Expl.^^^^",
    ]


def test_render_ascii_map_own_kingdom_shows_the_real_tax_number():
    state = _state()
    state.add_leader(LeaderState(2, 2, "Bradipo I", HOME, is_king=True))
    state.add_province(_province(1, 1, "Mongu", Terrain.JUNGLE, Race.HUMAN, owner=2, tax=10, t1=ArmyType.LEGION, t2=None, expl=100))

    lines = render_ascii_map(state, 2)

    assert any("Tax: 10" in line for line in lines)
    assert not any("Poor" in line or "Prosperous" in line for line in lines)


def test_render_ascii_map_other_kingdoms_low_tax_shows_poor():
    state = _state()
    state.add_leader(LeaderState(3, 3, "Someone", HOME, is_king=True))
    state.add_kingdom(KingdomState(3, "K3", Race.HUMAN, None, HOME))
    state.add_province(_province(1, 1, "X", Terrain.PLAINS, Race.HUMAN, owner=3, tax=2, t1=ArmyType.LEGION, t2=None, expl=1))

    lines = render_ascii_map(state, 2)

    assert any("Poor" in line for line in lines)


def test_render_ascii_map_other_kingdoms_high_tax_shows_prosperous():
    state = _state()
    state.add_leader(LeaderState(3, 3, "Someone", HOME, is_king=True))
    state.add_kingdom(KingdomState(3, "K3", Race.HUMAN, None, HOME))
    state.add_province(_province(1, 1, "X", Terrain.PLAINS, Race.HUMAN, owner=3, tax=6, t1=ArmyType.LEGION, t2=None, expl=1))

    lines = render_ascii_map(state, 2)

    assert any("Prosperous" in line for line in lines)


def test_render_ascii_map_empty_when_no_provinces_known():
    assert render_ascii_map(_state(), 2) == []


def test_render_cell_uses_the_provinces_own_terrain_symbol():
    state = _state()
    province = _province(1, 1, "X", Terrain.SEA, Race.HUMAN, owner=None, tax=0, t1=None, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert all(TERRAIN_SYMBOL[Terrain.SEA] in line or line.strip(TERRAIN_SYMBOL[Terrain.SEA]) for line in cell)
    assert len(cell) == 6
    assert all(len(line) == 16 for line in cell)
