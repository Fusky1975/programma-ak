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
    CELL_STRIDE,
    DENSE_CELL_STRIDE,
    STRIDE8_CELL_STRIDE,
    STRIDE9_CELL_STRIDE,
    STRIDE10_CELL_STRIDE,
    STRIDE12_CELL_STRIDE,
    TERRAIN_SYMBOL,
    _contiguous_run_through,
    _cylindrical_distance,
    _pad_center,
    _pad_framed,
    _pad_overlay,
    _recruit_abbreviation,
    _race_name_plural,
    cell_pixel_column,
    dense_cell_pixel_column,
    map_region_label,
    max_columns_per_page,
    paginate_known_columns,
    render_ascii_map,
    render_ascii_map_dense,
    render_ascii_map_stride8,
    render_ascii_map_stride9,
    render_ascii_map_stride10,
    render_ascii_map_stride12,
    render_cell,
    render_cell_dense,
    render_cell_stride8,
    render_cell_stride9,
    render_cell_stride10,
    render_cell_stride12,
    select_layout_tier,
    stride8_cell_pixel_column,
    stride9_cell_pixel_column,
    stride10_cell_pixel_column,
    stride12_cell_pixel_column,
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
    assert cell_pixel_column(HexCoord(1, 5), x_min=1) == 0
    assert cell_pixel_column(HexCoord(2, 3), x_min=1) == 17


def test_cell_pixel_column_even_row_staggers_by_half_a_cell():
    assert cell_pixel_column(HexCoord(1, 4), x_min=1) == 8
    assert cell_pixel_column(HexCoord(1, 6), x_min=1) == 8


def test_cell_pixel_column_clamps_below_x_min_instead_of_going_negative():
    assert cell_pixel_column(HexCoord(0, 5), x_min=1) == cell_pixel_column(HexCoord(1, 5), x_min=1)


def test_cell_pixel_column_is_relative_to_x_min_not_hardcoded_to_one():
    # Phase 568: SE3__T1.K1's own real Sixth Sea/Kildare/M Ionium band
    # (x=9,10,11 at y=4) -- the same real provinces byte-verified in
    # SE3__T1.K2 at x=1-4, this time confirmed against a report whose
    # own map starts much further right. Column 8 for x=9 with x_min=9
    # matches cell_pixel_column(HexCoord(1, 4), x_min=1)'s own 8 exactly
    # -- the formula genuinely only cares about x relative to x_min.
    assert cell_pixel_column(HexCoord(9, 4), x_min=9) == 8
    assert cell_pixel_column(HexCoord(10, 4), x_min=9) == 25
    assert cell_pixel_column(HexCoord(11, 4), x_min=9) == 42


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
    # Kingdom's own, ruled by Snorri(23), real tax somewhere in 7-10 per
    # the user's own Phase 563 confirmation of the "Rich" threshold) and
    # Shasta (unowned, race Eagles) -- byte-for-byte for every row this
    # phase models (Waterford Sea's own overlong-name wrap is
    # deliberately not exercised here -- see module docstring's own
    # deferred-gaps list). Shasta's own real cell has no recruit row at
    # all (Phase 565: Eagles is not a `HUMANOID_RACES` member) -- its
    # own real `t1` is set here anyway to prove it's genuinely ignored,
    # not merely `None`.
    state = _state()
    state.add_leader(LeaderState(23, 97, "Snorri", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.HUMAN, None, HOME))

    state.add_province(_province(2, 4, "Orielle", Terrain.PLAINS, Race.HUMAN, owner=97, tax=10, t1=ArmyType.LEGION, t2=ArmyType.CHARIOTS, expl=26))
    state.add_province(_province(3, 4, "Shasta", Terrain.MTNS, Race.EAGLES, owner=None, tax=1, t1=ArmyType.EAGLE_WING, t2=None, expl=1))

    lines = render_ascii_map(state, 2)

    # 8 leading spaces (Phase 568): render_ascii_map() computes x_min as
    # the true minimum x among the provinces it's actually rendering --
    # here that's Orielle's own x=2 (Waterford Sea, the real sample's
    # own x=1 cell, is deliberately not added), so Orielle itself sits
    # at cell_pixel_column()'s own x_min-relative column 0, plus row 4's
    # own 8-column even-row stagger.
    pad = " " * 8
    assert lines == [
        pad + "__Orielle(0204)_ ^^Shasta(0304)^^",
        pad + "_ _Snorri(23) __ ^ ^  Unowned  ^^",
        pad + "_   _Humans _  _ ^   ^Eagles ^  ^",
        pad + "_ _   Le,Ch   __ ^ ^   Poor^   ^^",
        pad + "_   _ Rich  _  _ ^   1% Expl.^  ^",
        pad + "____26%_Expl.___ ^^^^^^^^^^^^^^^^",
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


def test_render_ascii_map_other_kingdoms_very_high_tax_shows_rich():
    state = _state()
    state.add_leader(LeaderState(3, 3, "Someone", HOME, is_king=True))
    state.add_kingdom(KingdomState(3, "K3", Race.HUMAN, None, HOME))
    state.add_province(_province(1, 1, "X", Terrain.PLAINS, Race.HUMAN, owner=3, tax=7, t1=ArmyType.LEGION, t2=None, expl=1))

    lines = render_ascii_map(state, 2)

    assert any("Rich" in line for line in lines)


def test_status_word_thresholds_confirmed_by_the_user():
    # Poor 0-2, Prosperous 3-6, Rich 7-10 -- both boundaries confirmed
    # directly by the user (project author), see module docstring.
    from ak_engine.report.ascii_map import _status_word

    assert _status_word(0) == "Poor"
    assert _status_word(2) == "Poor"
    assert _status_word(3) == "Prosperous"
    assert _status_word(6) == "Prosperous"
    assert _status_word(7) == "Rich"
    assert _status_word(10) == "Rich"


def test_render_ascii_map_empty_when_no_provinces_known():
    assert render_ascii_map(_state(), 2) == []


def test_render_cell_uses_the_provinces_own_terrain_symbol():
    state = _state()
    province = _province(1, 1, "X", Terrain.SEA, Race.HUMAN, owner=None, tax=0, t1=None, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert all(TERRAIN_SYMBOL[Terrain.SEA] in line or line.strip(TERRAIN_SYMBOL[Terrain.SEA]) for line in cell)
    assert len(cell) == 6
    assert all(len(line) == 16 for line in cell)


# -- Phase 564: long province names get cut to 8 chars, not wrapped --


def test_render_cell_truncates_a_ten_character_name_to_its_first_eight():
    # The user's own worked example.
    state = _state()
    province = _province(1, 4, "Marnus Sea", Terrain.SEA, Race.HUMAN, owner=None, tax=0, t1=None, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert cell[0] == "~Marnus~S(0104)~"


def test_render_cell_leaves_a_nine_character_name_whole():
    # "Bam Yanga" (9 chars) is confirmed to render in full in the real,
    # byte-for-byte-verified band (SE3__T1.K2 line 314) -- the trigger
    # is 10 characters, not 9, precisely so this stays untruncated.
    state = _state()
    province = _province(1, 5, "Bam Yanga", Terrain.DESERT, Race.HUMAN, owner=None, tax=0, t1=None, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert cell[0] == ".Bam.Yanga(0105)"


def test_render_cell_truncates_a_twelve_character_name_too():
    state = _state()
    province = _province(2, 6, "Transylvania", Terrain.MTNS, Race.DWARVEN, owner=None, tax=0, t1=None, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert "Transylv" in cell[0]
    assert "Transylvania" not in cell[0]


# -- Phase 565: recruit row omitted for a non-HUMANOID_RACES province --


def test_render_cell_matches_shastas_own_real_cell_with_no_recruit_row():
    # SE3__T1.K2's own Shasta: race Eagles (not a HUMANOID_RACES member).
    # `t1` is set anyway to prove it's genuinely ignored, not merely None.
    state = _state()
    province = _province(3, 4, "Shasta", Terrain.MTNS, Race.EAGLES, owner=None, tax=1, t1=ArmyType.EAGLE_WING, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert cell == [
        "^^Shasta(0304)^^",
        "^ ^  Unowned  ^^",
        "^   ^Eagles ^  ^",
        "^ ^   Poor^   ^^",
        "^   1% Expl.^  ^",
        "^^^^^^^^^^^^^^^^",
    ]


def test_render_cell_shows_the_real_tax_number_when_recruit_row_is_skipped():
    # Same as above, but owned by the viewing Kingdom -- the shifted
    # status row shows "Tax: N" instead of the qualitative word, using
    # the same row-4 template.
    state = _state()
    province = _province(3, 4, "Shasta", Terrain.MTNS, Race.EAGLES, owner=2, tax=7, t1=None, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert len(cell) == 6
    assert "Tax: 7" in cell[3]
    assert cell[5] == TERRAIN_SYMBOL[Terrain.MTNS] * 16


def test_render_cell_humanoid_race_keeps_its_recruit_row():
    # A HUMANOID_RACES province is unaffected -- all 6 rows keep their
    # Phase 562 shape, recruit row included, Expl% still merged into
    # the border row.
    state = _state()
    province = _province(1, 1, "Mongu", Terrain.JUNGLE, Race.HUMAN, owner=None, tax=0, t1=ArmyType.LEGION, t2=None, expl=1)
    cell = render_cell(state, province, viewing_kingdom_id=2)
    assert len(cell) == 6
    assert "Le" in cell[3]
    assert "Expl." in cell[5]


# -- Phase 566: the dense layout (SE3__T5.K2) -- own formula, own tick
# columns, own overlay algorithm; see module docstring's own section.


def test_dense_cell_pixel_column_odd_row_no_stagger():
    # SE3__T5.K2's own Jadegate/Kiska/Kaluga band (y=7, odd): x=1 -> 14,
    # x=2 -> 28, x=3 -> 42, confirmed against the real file's own column
    # positions.
    assert dense_cell_pixel_column(HexCoord(1, 7)) == 14
    assert dense_cell_pixel_column(HexCoord(3, 7)) == 42


def test_dense_cell_pixel_column_even_row_staggers_by_half_a_cell():
    # SE3__T5.K2's own Waterford Sea/Orielle/Shasta/Katanga band (y=4,
    # even): x=1 -> 21, x=3 -> 49.
    assert dense_cell_pixel_column(HexCoord(1, 4)) == 21
    assert dense_cell_pixel_column(HexCoord(3, 4)) == 49


def test_dense_cell_pixel_column_has_no_minus_one_unlike_the_wide_layout():
    # The wide layout's own formula is (x - 1) * stride + stagger, so
    # x=1 on an odd row lands at column 0. The dense layout's own real
    # data rules that out: x=1 lands at column 14 (= 1 * stride), not 0.
    assert dense_cell_pixel_column(HexCoord(1, 3)) == 14


def test_pad_overlay_non_space_content_overwrites_a_tick():
    # Macondo's own real "Tax: 4" (SE3__T5.K2): the 'x' of "Tax:" lands
    # squarely on tick column 4 and overwrites it.
    result = _pad_overlay("Tax: 4", tick_columns=frozenset({0, 4, 8, 12}), symbol="&")
    assert result == "&   Tax:&4  &"


def test_pad_overlay_space_content_is_transparent_over_a_tick():
    # Same tick set, one character longer ("Tax: 10"): the content's own
    # internal space now lands on a plain column, not a tick, and stays
    # literal -- both confirmed directly against SE3__T5.K2's own Macondo
    # (6-char content, tick shows through) and Mongu (7-char, literal
    # space) cells in the very same band.
    result = _pad_overlay("Tax: 10", tick_columns=frozenset({0, 4, 8, 12}), symbol="&")
    assert result == "&  Tax: 10  &"


def test_pad_overlay_short_content_reveals_the_tick_columns():
    # "Le" (row 4, ROW24 ticks): confirmed against Tesawa's own real
    # cell -- ticks at 0, 2, 10, 12 all show through since the 2-char
    # content only reaches columns 6-7.
    result = _pad_overlay("Le", tick_columns=frozenset({0, 2, 10, 12}), symbol="^")
    assert result == "^ ^   Le  ^ ^"


def test_render_cell_dense_matches_tesawa_and_marzuq_real_cells():
    # SE3__T5.K2 lines 343-348, x=2 and x=3 at y=3: Tesawa (unowned) and
    # Marzuq (owned by another Kingdom, ruled by Prometeo(5)) -- both
    # clean, non-shifted cells, byte-for-byte.
    state = _state()
    state.add_leader(LeaderState(5, 97, "Prometeo", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.HUMAN, None, HOME))

    tesawa = _province(2, 3, "Tesawa", Terrain.MTNS, Race.HUMAN, owner=None, tax=1, t1=ArmyType.LEGION, t2=None, expl=1)
    marzuq = _province(3, 3, "Marzuq", Terrain.DESERT, Race.HUMAN, owner=97, tax=1, t1=ArmyType.CAMEL_CORPS, t2=None, expl=1)

    assert render_cell_dense(state, tesawa, viewing_kingdom_id=2) == [
        "^Tesawa(0203)",
        "^ ^Unowned^ ^",
        "^   Humans  ^",
        "^ ^   Le  ^ ^",
        "^   ^Poor   ^",
        "^^^1%^Expl.^^",
    ]
    assert render_cell_dense(state, marzuq, viewing_kingdom_id=2) == [
        ".Marzuq(0303)",
        ".Prometeo(5).",
        ".   Humans  .",
        ". .   CC  . .",
        ".   .Poor   .",
        "...1%.Expl...",
    ]


def test_render_cell_dense_matches_shastas_own_real_cell_with_no_recruit_row():
    # SE3__T5.K2 line 349-354, x=3 at y=4: Shasta, race Eagles -- the
    # recruit-skip mechanic (Phase 565) generalizes unchanged to the
    # dense layout's own row templates.
    state = _state()
    shasta = _province(3, 4, "Shasta", Terrain.MTNS, Race.EAGLES, owner=None, tax=1, t1=ArmyType.EAGLE_WING, t2=None, expl=8)
    assert render_cell_dense(state, shasta, viewing_kingdom_id=2) == [
        "^Shasta(0304)",
        "^ ^Unowned^ ^",
        "^   Eagles  ^",
        "^ ^  Poor ^ ^",
        "^  8% Expl. ^",
        "^^^^^^^^^^^^^",
    ]


def test_render_ascii_map_dense_matches_orielle_and_shasta_real_band():
    # SE3__T5.K2 line 349-354, columns 35 onward: Orielle (this
    # Kingdom's own, Tax: 10) and Shasta (unowned, recruit row skipped),
    # byte-for-byte for every row this phase models.
    state = _state()
    state.add_leader(LeaderState(2, 2, "Bradipo I", HOME, is_king=True))

    orielle = _province(2, 4, "Orielle", Terrain.PLAINS, Race.HUMAN, owner=2, tax=10, t1=ArmyType.LEGION, t2=ArmyType.CHARIOTS, expl=51)
    shasta = _province(3, 4, "Shasta", Terrain.MTNS, Race.EAGLES, owner=None, tax=1, t1=ArmyType.EAGLE_WING, t2=None, expl=8)
    state.add_province(orielle)
    state.add_province(shasta)

    lines = render_ascii_map_dense(state, 2)

    pad = " " * 35
    assert lines == [
        pad + "Orielle(0204) ^Shasta(0304)",
        pad + "_Bradipo I(2) ^ ^Unowned^ ^",
        pad + "_   Humans  _ ^   Eagles  ^",
        pad + "_ _ Le,Ch _ _ ^ ^  Poor ^ ^",
        pad + "_  Tax: 10  _ ^  8% Expl. ^",
        pad + "__51%_Expl.__ ^^^^^^^^^^^^^",
    ]


# -- Phase 569: the stride-12 layout (SE3__T3.K1) -- its own placement
# formula and its own 3 distinct row templates (row 2, row 4, and a
# shared row 3/5); see module docstring's own section.


def test_stride12_cell_pixel_column_matches_the_real_t3k1_report():
    # SE3__T3.K1's own real map: x_min=8 across the whole report (not
    # just one row), confirmed against all 5 of its own real bands with
    # zero residual -- odd row y=7's own leftmost cell (Third, x=8)
    # sits at column 0; the next cell over (x=9) at column 12.
    assert stride12_cell_pixel_column(HexCoord(8, 7), x_min=8) == 0
    assert stride12_cell_pixel_column(HexCoord(9, 7), x_min=8) == 12
    # y=4 (even) staggers by half a cell relative to y=7 (odd).
    assert stride12_cell_pixel_column(HexCoord(9, 4), x_min=8) == 18


def test_render_cell_stride12_matches_thirds_own_real_cell():
    # SE3__T3.K1 lines 476-481: Third, a fully clean (no name-wrap, no
    # ruler-wrap) cell -- the only one in this report's own map that
    # exercises every row's own real template without a cascade shift.
    state = _state()
    state.add_leader(LeaderState(73, 97, "Presto", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.ELVEN, None, HOME))
    province = _province(8, 7, "Third", Terrain.FOREST, Race.ELVEN, owner=97, tax=5, t1=ArmyType.AXEMEN, t2=None, expl=1)
    cell = render_cell_stride12(state, province, viewing_kingdom_id=2)
    assert cell == [
        "Third(0807)",
        "+Presto(73)",
        "+  Elves+ +",
        "+ +  Ax   +",
        "+Prosperous",
        "++1%+Expl.+",
    ]


def test_render_ascii_map_stride12_matches_thirds_own_real_band():
    # Same real cell, this time through the map-level renderer -- the
    # real report shows Third at column 0 (it's the row's own leftmost
    # and the whole report's own x_min), confirming the placement
    # formula and the content renderer agree end to end.
    state = _state()
    state.add_leader(LeaderState(73, 97, "Presto", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.ELVEN, None, HOME))
    state.add_province(_province(8, 7, "Third", Terrain.FOREST, Race.ELVEN, owner=97, tax=5, t1=ArmyType.AXEMEN, t2=None, expl=1))

    lines = render_ascii_map_stride12(state, 2)

    assert lines == [
        "Third(0807)",
        "+Presto(73)",
        "+  Elves+ +",
        "+ +  Ax   +",
        "+Prosperous",
        "++1%+Expl.+",
    ]


# -- Phase 570: the stride-10 layout (SE3__T4.K3) -- name and id are
# always split onto their own rows here (confirmed universal at this
# width, not an occasional long-name case), so `render_cell_stride10()`
# has its own dedicated structure; see module docstring's own section.


def test_stride10_cell_pixel_column_matches_the_real_t4k3_report():
    # SE3__T4.K3's own real map: x_min=4 across the whole report,
    # confirmed against all 6 of its own real bands with zero residual.
    assert stride10_cell_pixel_column(HexCoord(4, 4), x_min=4) == 5
    assert stride10_cell_pixel_column(HexCoord(7, 1), x_min=4) == 30
    assert stride10_cell_pixel_column(HexCoord(5, 3), x_min=4) == 10


def test_render_cell_stride10_matches_starhavens_own_real_cell():
    # SE3__T4.K3 lines 366-371: Starhaven, a real cell with all 4
    # middle fields present (no recruit-skip) -- the real corpus's own
    # id always wraps to its own row 2 here, and with 4 fields shown,
    # the real report's own status ("Rich") merges into row 6 with
    # Expl% dropped entirely, byte-for-byte confirmed.
    state = _state()
    state.add_leader(LeaderState(4, 97, "Hokuto", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.HUMAN, None, HOME))
    province = _province(7, 1, "Starhaven", Terrain.FOREST, Race.HUMAN, owner=97, tax=8, t1=ArmyType.LEGION, t2=ArmyType.CHARIOTS, expl=1)
    cell = render_cell_stride10(state, province, viewing_kingdom_id=2)
    assert cell == [
        "Starhaven",
        "+ (0701)+",
        "Hokuto(4)",
        "+ Humans+",
        "+ Le,Ch +",
        "+++Rich++",
    ]


def test_render_cell_stride10_matches_sixth_seas_own_real_cell():
    # SE3__T4.K3 lines 384-389: Sixth Sea, race Whales (non-humanoid,
    # recruit skipped -- Phase 565's own mechanic generalizes here too)
    # -- with only 3 middle fields, row 6 stays free for Expl% to merge
    # in as usual, matching the real corpus exactly (tax=1 here, not
    # the real sample's own unknown value, to keep the status word
    # short enough to avoid this tier's own known status-overflow gap
    # -- see module docstring).
    state = _state()
    province = _province(9, 4, "Sixth Sea", Terrain.SEA, Race.WHALES, owner=None, tax=1, t1=None, t2=None, expl=1)
    cell = render_cell_stride10(state, province, viewing_kingdom_id=2)
    assert cell == [
        "Sixth~Sea",
        "~ (0904)~",
        "~Unowned~",
        "~ Whales~",
        "~  Poor ~",
        "~1%~Expl.",
    ]


def test_render_ascii_map_stride10_matches_starhavens_own_real_band():
    # Same real cell, through the map-level renderer -- confirms the
    # placement formula and the content renderer agree end to end.
    state = _state()
    state.add_leader(LeaderState(4, 97, "Hokuto", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.HUMAN, None, HOME))
    state.add_province(_province(7, 1, "Starhaven", Terrain.FOREST, Race.HUMAN, owner=97, tax=8, t1=ArmyType.LEGION, t2=ArmyType.CHARIOTS, expl=1))

    lines = render_ascii_map_stride10(state, 2)

    assert lines == [
        "Starhaven",
        "+ (0701)+",
        "Hokuto(4)",
        "+ Humans+",
        "+ Le,Ch +",
        "+++Rich++",
    ]


# -- Phase 571: the stride-9 layout (SE3__T4.K8) -- like stride 10,
# name and id are always split; unlike stride 10, only 3 of up to 4
# middle fields ever get a row at all (a 4th, status, is dropped
# entirely, with no row-6-style merge); see module docstring's section.


def test_render_cell_stride9_matches_katangas_own_real_cell():
    # SE3__T4.K8 lines 552-556: Katanga, a real cell with all 4 middle
    # fields present (no recruit-skip). Real corpus: only the first 3
    # (ruler, race, recruit) get a row; status/Expl% are both dropped
    # entirely. "Le,El" is the real recruit text -- ELEPHANTS'
    # abbreviation was newly confirmed this phase (see
    # `_CONFIRMED_RECRUIT_ABBREVIATION`'s own comment).
    state = _state()
    state.add_leader(LeaderState(8, 97, "Circe", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.DWARVEN, None, HOME))
    province = _province(4, 4, "Katanga", Terrain.JUNGLE, Race.DWARVEN, owner=97, tax=1, t1=ArmyType.LEGION, t2=ArmyType.ELEPHANTS, expl=1)
    cell = render_cell_stride9(state, province, viewing_kingdom_id=2)
    assert cell == [
        "&Katanga",
        "&(0404)&",
        "Circe(8)",
        "&Dwarves",
        "&&Le,El&",
    ]


def test_render_cell_stride9_matches_shastas_own_real_cell():
    # SE3__T4.K8 lines 552-556: Shasta, race Eagles (non-humanoid,
    # recruit skipped -- Phase 565's own mechanic generalizes here too)
    # -- status takes recruit's own normal slot instead.
    state = _state()
    province = _province(3, 4, "Shasta", Terrain.MTNS, Race.EAGLES, owner=None, tax=1, t1=None, t2=None, expl=1)
    cell = render_cell_stride9(state, province, viewing_kingdom_id=2)
    assert cell == [
        "^Shasta^",
        "^(0304)^",
        "^Unowned",
        "^Eagles^",
        "^^Poor^^",
    ]


def test_stride9_cell_pixel_column_is_relative_to_x_min():
    # This tier's own real reports need a non-obvious x_min (see the
    # function's own docstring) -- test the RELATIVE shape instead
    # (stride 9, half-cell even-row stagger), which is what every
    # caller actually relies on.
    assert stride9_cell_pixel_column(HexCoord(5, 5), x_min=5) == 0
    assert stride9_cell_pixel_column(HexCoord(6, 5), x_min=5) == 9
    assert stride9_cell_pixel_column(HexCoord(5, 4), x_min=5) == 4


def test_render_ascii_map_stride9_matches_katangas_own_real_band():
    # Same real cell, through the map-level renderer -- confirms the
    # placement formula and the content renderer agree end to end.
    state = _state()
    state.add_leader(LeaderState(8, 97, "Circe", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.DWARVEN, None, HOME))
    state.add_province(_province(4, 4, "Katanga", Terrain.JUNGLE, Race.DWARVEN, owner=97, tax=1, t1=ArmyType.LEGION, t2=ArmyType.ELEPHANTS, expl=1))

    lines = render_ascii_map_stride9(state, 2)

    # 4 leading spaces: y=4 is even, so cell_pixel_column()'s own
    # confirmed half-cell stagger applies even to a single province.
    pad = "    "
    assert lines == [
        pad + "&Katanga",
        pad + "&(0404)&",
        pad + "Circe(8)",
        pad + "&Dwarves",
        pad + "&&Le,El&",
    ]


# -- Phase 572: the stride-8 layout (SE3__T5.K1) -- the floor tier:
# name and id are always split (like strides 10/9), and only ruler and
# race ever get a row at all -- recruit, status, and Expl% are never
# shown in any well-understood real cell at this width; see module
# docstring's own section.


def test_render_cell_stride8_matches_peachwoods_own_real_cell():
    # SE3__T5.K1 lines 758-761: Peachwood, race Ents (Race.ENTISH), an
    # unowned real cell. The real province name itself ("Peachwood", 9
    # chars) flushes in the real sample rather than truncating -- this
    # module's own truncation policy deliberately doesn't reproduce
    # that (same Phase 564 simplification the other layouts already
    # make), so a shorter synthetic name is used here to isolate the
    # id/ruler/race rows, which ARE confirmed byte-for-byte against the
    # real cell.
    state = _state()
    province = _province(12, 2, "Peach", Terrain.FOREST, Race.ENTISH, owner=None, tax=1, t1=None, t2=None, expl=1)
    cell = render_cell_stride8(state, province, viewing_kingdom_id=2)
    assert cell == [
        "+Peach+",
        "+(1202)",
        "Unowned",
        "++Ents+",
    ]


def test_render_cell_stride8_matches_sherwoods_own_real_cell():
    # SE3__T5.K1 lines 758-761: Sherwood, race Human -- confirms that
    # even a HUMANOID_RACES member still shows no recruit row at all at
    # this width (there simply isn't one).
    state = _state()
    state.add_leader(LeaderState(6, 97, "Kahn", HOME, is_king=True))
    state.add_kingdom(KingdomState(97, "K97", Race.HUMAN, None, HOME))
    province = _province(13, 2, "Sher", Terrain.FOREST, Race.HUMAN, owner=97, tax=1, t1=ArmyType.LEGION, t2=None, expl=1)
    cell = render_cell_stride8(state, province, viewing_kingdom_id=2)
    assert cell == [
        "++Sher+",
        "+(1302)",
        "Kahn(6)",
        "+Humans",
    ]


def test_stride8_cell_pixel_column_matches_the_real_t5k1_report():
    # SE3__T5.K1's own real map: x_min=6 across the whole report,
    # confirmed against all 7 of its own real bands with zero residual
    # -- unlike the dense and stride-9 layouts, no unexplained margin.
    assert stride8_cell_pixel_column(HexCoord(6, 3), x_min=6) == 0
    assert stride8_cell_pixel_column(HexCoord(7, 3), x_min=6) == 8
    assert stride8_cell_pixel_column(HexCoord(12, 2), x_min=6) == 52


def test_render_ascii_map_stride8_matches_peachwoods_own_real_band():
    # Same real cell, through the map-level renderer -- confirms the
    # placement formula and the content renderer agree end to end.
    state = _state()
    state.add_province(_province(12, 2, "Peach", Terrain.FOREST, Race.ENTISH, owner=None, tax=1, t1=None, t2=None, expl=1))

    lines = render_ascii_map_stride8(state, 2)

    # 4 leading spaces: y=2 is even, so cell_pixel_column()'s own
    # confirmed half-cell stagger applies even to a single province.
    pad = "    "
    assert lines == [
        pad + "+Peach+",
        pad + "+(1202)",
        pad + "Unowned",
        pad + "++Ents+",
    ]


# -- Phase 577: map_region_label() -- "Ice cap", confirmed to trigger
# exactly when the map's own topmost row is y == 1 (~10 real samples
# cross-checked, both with and without the label, zero exceptions).


def test_map_region_label_is_ice_cap_when_topmost_row_is_y_1():
    # Real shape: SE3__T1.K5's own map opens at y=1 (Alderwood(0101)).
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(1, 2, "Belladonna", Terrain.FOREST, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    assert map_region_label(state) == "Ice cap"


def test_map_region_label_is_none_when_topmost_row_is_below_y_1():
    # Real shape: SE3__T1.K1's own map opens at y=4 (Sixth Sea(0904)) --
    # no label, direct continuation of the intro sentence.
    state = _state()
    state.add_province(_province(9, 4, "Sixth Sea", Terrain.SEA, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    assert map_region_label(state) is None


def test_map_region_label_is_none_with_no_provinces():
    state = _state()

    assert map_region_label(state) is None


# -- Phase 624: "far side of the world" pagination -- see module
# docstring's own Phase 624 addendum for the full sourcing.


def test_max_columns_per_page_matches_the_6_real_tiers():
    assert max_columns_per_page(CELL_STRIDE) == 4
    assert max_columns_per_page(DENSE_CELL_STRIDE) == 5
    assert max_columns_per_page(STRIDE12_CELL_STRIDE) == 6
    assert max_columns_per_page(STRIDE10_CELL_STRIDE) == 7
    assert max_columns_per_page(STRIDE9_CELL_STRIDE) == 8
    assert max_columns_per_page(STRIDE8_CELL_STRIDE) == 9


def test_cylindrical_distance_wraps_at_board_width():
    assert _cylindrical_distance(17, 18, board_width=18) == 1
    assert _cylindrical_distance(18, 1, board_width=18) == 1
    assert _cylindrical_distance(1, 18, board_width=18) == 1
    assert _cylindrical_distance(5, 5, board_width=18) == 0
    assert _cylindrical_distance(1, 10, board_width=18) == 9


def test_contiguous_run_through_crosses_the_wrap():
    known = {16, 17, 18, 1, 2, 3}
    assert _contiguous_run_through(18, known, board_width=18) == [16, 17, 18, 1, 2, 3]


def test_contiguous_run_through_stops_at_a_gap():
    known = {5, 6, 7, 12, 13}
    assert _contiguous_run_through(6, known, board_width=18) == [5, 6, 7]
    assert _contiguous_run_through(12, known, board_width=18) == [12, 13]


def test_paginate_known_columns_k6_shaped_case():
    # Real corpus case (SE3__T4-9.K6): home x=14, full known run
    # 12-18,1 (8 cols) exceeds this tier's own 6-column cap -- the 2
    # columns farthest from home (18, 1) are dropped to page 2.
    known = set(range(12, 19)) | {1}
    pages = paginate_known_columns(known, home_x=14, max_cols=6, board_width=18)
    assert pages == [[12, 13, 14, 15, 16, 17], [1, 18]]


def test_paginate_known_columns_k9_shaped_case():
    # Real corpus case (SE3__T9-11.K9): home x=18, full known run
    # 12-18,1,2 (9 cols) exceeds this tier's own 8-column cap -- the 1
    # column farthest from home (12) is dropped to page 2.
    known = set(range(12, 19)) | {1, 2}
    pages = paginate_known_columns(known, home_x=18, max_cols=8, board_width=18)
    assert pages == [[1, 2, 13, 14, 15, 16, 17, 18], [12]]


def test_paginate_known_columns_fits_on_one_page_when_narrow_enough():
    known = {6, 7, 8, 9}
    pages = paginate_known_columns(known, home_x=7, max_cols=9, board_width=18)
    assert pages == [[6, 7, 8, 9]]


def test_paginate_known_columns_more_than_two_pages_terminates_and_covers_everything():
    # Synthetic: a known run wider than 2 pages' worth still terminates,
    # covers every column exactly once with no overlap, and never
    # exceeds max_cols per page -- page-2+ anchoring/tie-breaking is
    # documented as arbitrary (no real 3+-page sample exists), so this
    # doesn't assert an exact page count or shape, only the invariants
    # that must hold regardless.
    known = set(range(1, 19))  # the whole board, one contiguous run
    pages = paginate_known_columns(known, home_x=9, max_cols=6, board_width=18)
    assert len(pages) > 2
    covered = sorted(c for page in pages for c in page)
    assert covered == list(range(1, 19))
    assert all(len(page) <= 6 for page in pages)


def test_paginate_known_columns_home_not_known_falls_back_to_closest():
    # home_x itself has no known province -- page 1 anchors on the
    # closest known column instead of raising or picking arbitrarily.
    known = {10, 11, 12}
    pages = paginate_known_columns(known, home_x=9, max_cols=6, board_width=18)
    assert pages == [[10, 11, 12]]


def test_render_ascii_map_columns_filters_to_the_given_page():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map(state, 2)
    restricted = render_ascii_map(state, 2, columns={1})

    assert full != restricted
    assert "Alderwood" in "".join(restricted)
    assert "Farland" not in "".join(restricted)


def test_map_region_label_columns_checks_only_that_pages_own_rows():
    state = _state()
    # y=1 (Ice cap trigger) only on column 9; column 1 alone stays y=5.
    state.add_province(_province(1, 5, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    assert map_region_label(state, columns={1}) is None
    assert map_region_label(state, columns={9}) == "Ice cap"


# -- Phase 627: select_layout_tier() -- a labeled, 82%-accurate (81/99
# real corpus) best-effort approximation, not a solved formula; see
# that function's own docstring for the full account of why.


def test_select_layout_tier_small_cluster_stays_wide():
    assert select_layout_tier({6, 7, 8, 9}, home_x=7) == CELL_STRIDE


def test_select_layout_tier_picks_the_exact_fitting_tier():
    assert select_layout_tier({6, 7, 8, 9, 10}, home_x=8) == DENSE_CELL_STRIDE
    assert select_layout_tier({6, 7, 8, 9, 10, 11}, home_x=8) == STRIDE12_CELL_STRIDE
    assert select_layout_tier(set(range(6, 13)), home_x=9) == STRIDE10_CELL_STRIDE
    assert select_layout_tier(set(range(6, 14)), home_x=9) == STRIDE9_CELL_STRIDE
    assert select_layout_tier(set(range(6, 15)), home_x=9) == STRIDE8_CELL_STRIDE


def test_select_layout_tier_falls_back_to_the_floor_when_no_tier_fits():
    # 10 columns exceeds every real tier's own cap (stride8's own 9).
    assert select_layout_tier(set(range(1, 11)), home_x=5) == STRIDE8_CELL_STRIDE


def test_select_layout_tier_home_not_known_falls_back_to_closest():
    assert select_layout_tier({10, 11, 12}, home_x=9) == CELL_STRIDE


def test_select_layout_tier_picks_the_right_tier_for_a_real_primary_cluster_alone():
    # Real SE3__T*.K8-shaped primary cluster (1-6,17,18 -- 8 columns,
    # home x=5) in isolation resolves to stride9 (cap 8), matching that
    # real report's own actual tier.
    primary = {1, 2, 3, 4, 5, 6, 17, 18}
    assert select_layout_tier(primary, home_x=5) == STRIDE9_CELL_STRIDE


def test_select_layout_tier_known_limitation_a_geometrically_adjacent_far_cluster_still_widens_it():
    # Documented limitation (see the function's own docstring): this is
    # a purely geometric approximation, so a *further* cluster that's
    # merely adjacent to the real primary one -- even if it was
    # actually explored separately and belongs on a "far side" page in
    # the real game -- still gets merged in, over-predicting density.
    # The same SE3__T*.K8-shaped primary cluster (1-6,17,18) picks
    # stride9 alone (previous test), but picks the denser stride8 once
    # its own real, geometrically-touching far cluster (7,8,9) is
    # included too, even though the real report stays on stride9.
    primary_plus_adjacent_far = {1, 2, 3, 4, 5, 6, 17, 18, 7, 8, 9}
    assert select_layout_tier(primary_plus_adjacent_far, home_x=5) == STRIDE8_CELL_STRIDE


def test_render_ascii_map_dense_columns_filters_to_the_given_page():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_dense(state, 2)
    restricted = render_ascii_map_dense(state, 2, columns={1})

    assert full != restricted
    assert "Alderwood" in "".join(restricted)
    assert "Farland" not in "".join(restricted)


def test_render_ascii_map_stride12_columns_filters_to_the_given_page():
    # Narrower tiers truncate a 9-char name like "Alderwood" -- check
    # for the coordinate marker instead, which always survives.
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride12(state, 2)
    restricted = render_ascii_map_stride12(state, 2, columns={1})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)


def test_render_ascii_map_stride10_columns_filters_to_the_given_page():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride10(state, 2)
    restricted = render_ascii_map_stride10(state, 2, columns={1})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)


def test_render_ascii_map_stride9_columns_filters_to_the_given_page():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride9(state, 2)
    restricted = render_ascii_map_stride9(state, 2, columns={1})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)


def test_render_ascii_map_stride8_columns_filters_to_the_given_page():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride8(state, 2)
    restricted = render_ascii_map_stride8(state, 2, columns={1})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)


# -- Phase 628: `visible_provinces` -- the real per-Kingdom knowledge
# filter (`ProvinceState.known_to_kingdom()`, Phase 623), independent of
# `columns` (a page-column restriction). `None` (every test above)
# leaves every renderer/`map_region_label()` unfiltered, exactly the
# pre-Phase-628 behavior -- these tests cover the new, non-`None` case.


def test_render_ascii_map_visible_provinces_filters_by_knowledge():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map(state, 2)
    restricted = render_ascii_map(state, 2, visible_provinces={HexCoord(1, 1)})

    assert full != restricted
    assert "Alderwood" in "".join(restricted)
    assert "Farland" not in "".join(restricted)


def test_map_region_label_visible_provinces_checks_only_known_rows():
    state = _state()
    # y=1 (Ice cap trigger) only on the unknown province; the known one
    # alone stays y=5.
    state.add_province(_province(1, 5, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    assert map_region_label(state, visible_provinces={HexCoord(1, 5)}) is None
    assert map_region_label(state, visible_provinces={HexCoord(9, 1)}) == "Ice cap"


def test_render_ascii_map_dense_visible_provinces_filters_by_knowledge():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_dense(state, 2)
    restricted = render_ascii_map_dense(state, 2, visible_provinces={HexCoord(1, 1)})

    assert full != restricted
    assert "Alderwood" in "".join(restricted)
    assert "Farland" not in "".join(restricted)


def test_render_ascii_map_stride12_visible_provinces_filters_by_knowledge():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride12(state, 2)
    restricted = render_ascii_map_stride12(state, 2, visible_provinces={HexCoord(1, 1)})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)


def test_render_ascii_map_stride10_visible_provinces_filters_by_knowledge():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride10(state, 2)
    restricted = render_ascii_map_stride10(state, 2, visible_provinces={HexCoord(1, 1)})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)


def test_render_ascii_map_stride9_visible_provinces_filters_by_knowledge():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride9(state, 2)
    restricted = render_ascii_map_stride9(state, 2, visible_provinces={HexCoord(1, 1)})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)


def test_render_ascii_map_stride8_visible_provinces_filters_by_knowledge():
    state = _state()
    state.add_province(_province(1, 1, "Alderwood", Terrain.FOREST, Race.DRAGONS, owner=None, tax=1, t1=None, t2=None, expl=1))
    state.add_province(_province(9, 1, "Farland", Terrain.PLAINS, Race.HUMAN, owner=None, tax=1, t1=None, t2=None, expl=1))

    full = render_ascii_map_stride8(state, 2)
    restricted = render_ascii_map_stride8(state, 2, visible_provinces={HexCoord(1, 1)})

    assert full != restricted
    assert "0101" in "".join(restricted)
    assert "0901" not in "".join(restricted)
