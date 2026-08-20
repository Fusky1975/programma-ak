"""The real in-report ASCII map (Phase 562) -- `AKGEN_reverse_engineering_
report (5).md` SS38.2/SS44: "royal scribe has drawn up a map of all
neighboring lands", inserted right after PROVINCES and before CHARACTERS.
The report's own account leaves the exact rendering formula as HYPOTHESIS
("Rimane ignota... la formula completa che decide quale variante/campo
scegliere") -- everything in this module instead comes from this project's
own direct, character-by-character reverse engineering of six real
`Desktop/SE3__T*.K*` samples this same phase (`SE3__T1.K2` lines 300-325,
`SE3__T4.K6` lines 309-363, `SE3__T5.K2` lines 341-378), not the report's
own reconstructed pseudocode.

**Cell geometry, fully confirmed.** Each province renders as a 16-char-
wide, 6-line block. The two "cap" rows (name/id, and the status/Expl%
row) are entirely filled with the province's own `Terrain` symbol (`_`
Plains, `+` Forest, `&` Jungle, `^` Mountain, `.` Desert, `~` Sea) --
confirmed by cross-referencing the same province across the PROVINCES
table (its real Tax/Type1/Type2 columns) and the map in the same report,
for `Macondo`/`Mongu` (this Kingdom's own) and `Bam Yanga`/`Moongard`
(another Kingdom's) in `SE3__T1.K2`'s single band at lines 314-319:
content is centered within the 16 chars using the terrain symbol as the
pad character (ties favor the left when the padding is odd), and any
space *inside* the content itself (a two-word province name) is also
replaced by the terrain symbol -- e.g. "Bam Yanga" prints as
"Bam.Yanga". The four inner rows (ruler, race, recruit types, status)
instead keep real spaces for their own internal word gaps (a King's
name like "Bradipo I" keeps its literal space) and use a small, fixed
number of terrain-symbol "corner ticks" at positions that are the same
for every cell regardless of content -- verified identical across many
cells with different text lengths in the same band, and confirmed with
overflow: an inner row's content that's longer than its own nominal
"framed zone" grows outward into the adjacent tick position(s), always
starting on the left (`Row4`'s "Poor" needs 1 more slot than "CC"/"Ph"
and grows into the tick immediately left of the zone;
`Row5`'s "1% Expl." needs 1 more than "Tax: N" and does the same).

**Row-by-row template** (`_ROW_TEMPLATES` below encodes this precisely):
1. Name/ID: `<Name>(<ID>)` (`ID` is `models/map.py province_code()`'s
   own `x*100+y`, zero-padded to 4 digits) -- full-fill, tie-left.
2. Ruler: the owning Kingdom's own King's `<Name>(<leader_id>)`, or the
   literal `Unowned` if `owner_kingdom_id is None` -- framed, tie-right
   (inferred by consistency with rows 3-5 below; not independently
   confirmed on its own, since this project's own available samples
   never show an odd amount of row-2 padding to distinguish the tie
   direction).
3. Race: `models/race.py RACE_NAME[province.race]` -- framed, tie-right.
   (`Race.EAGLES`/`WHALES`/etc. are real, ordinary `Race` members, not a
   special "unowned province shows its guardian monster" substitution --
   confirmed directly: `Shasta`'s own real race in `SE3__T1.K2` prints
   "Eagles", matching `RACE_NAME[Race.EAGLES]` exactly, with nothing
   monster-specific about the rendering itself.)
4. Recruit types: `Type1[,Type2]` abbreviated (`RECRUIT_ABBREVIATION`
   below), `Type2` omitted only when it's genuinely `None` -- **this is
   the province's own real recruit data, regardless of who owns it**
   (corrected from an earlier working theory that only this report's own
   Kingdom saw both types: `Moongard`, owned by a different King in the
   same `SE3__T1.K2` band, shows both "Ax,HC" just as freely as this
   Kingdom's own `Mongu` shows "Le,LC" -- the single-type cells in the
   same corpus, e.g. `Bam Yanga`'s "CC", simply have a real `Type2 is
   None`, the same reason `describe_provinces_report()`'s own PROVINCES
   table omits it).
5. Status: `Tax: <N>` for a province owned by *this report's own*
   Kingdom (matches the PROVINCES table's own Tax column exactly, in
   every case checked); for anyone else's or an unowned province, a
   qualitative descriptor instead of the real number -- **`Poor`
   (`tax` 0-2), `Prosperous` (`tax` 3-6), or `Rich` (`tax` 7-10, Phase
   563), confirmed directly by the user (project author, drawing on
   first-hand game knowledge, the same "explicitly flagged domain-
   knowledge" sourcing category already used elsewhere in this project,
   e.g. `worldgen/king_home_placement.py`'s distance/terrain rules) --
   not derivable from the report samples alone, since a province's own
   real tax figure is never independently visible for someone else's
   territory in this project's own available corpus. (`SE3__T1.K2`'s
   own `Orielle` cell shows `Rich`; its own real tax, unknown from this
   project's own available data at Phase 562, is now understood to sit
   somewhere in 7-10.)**
6. Expl%/border: `<N>% Expl.` -- full-fill, tie-left (same rule as row
   1), with `N` from `ProvinceState.explored_percent`.

**Byte-for-byte verified** against two full real bands from `SE3__T1.K2`
(`Bam Yanga`/`Macondo`/`Mongu`/`Moongard`, lines 314-319 -- this
Kingdom's own provinces and another Kingdom's, side by side, exact
match; `Orielle`/`Shasta`, lines 308-313 -- another Kingdom's own
`Rich` province and an unowned one, exact match including the `Rich`
status word once Phase 563 closed its own threshold, for every row
this phase actually models).

**Explicitly NOT modeled this phase, confirmed real but not yet
reconciled with enough samples to state a rule with the same
confidence as the above** (see this module's own Phase 562 audit notes
in `README.md` for the full account):
- A province whose ruler is genuinely unknown (not just "no ruler")
  sometimes *skips* the ruler row entirely rather than printing
  "Unowned" (`Tesawa`/`Marzuq` in `SE3__T5.K2`, contrasted with
  `Shasta` in the very same report explicitly printing "Unowned") --
  this module always prints "Unowned" (never skips), the simpler,
  fully-confirmed-as-real of the two observed behaviors.
- A genuinely unowned province's own recruit-type row (row 4) is
  sometimes entirely absent too, with the status row (row 5) shifting
  up to fill it (`Shasta` again, `SE3__T1.K2`) -- this module always
  shows a recruit-type row regardless of ownership.
- A province name too long to fit in 16 chars alongside its own ID
  wraps onto its own second row, which then forces something else out
  of the fixed 6-row budget (observed: the Expl%/status row gets
  dropped entirely in favor of keeping the status word, `Transylvania`
  in `SE3__T1.K2`) -- this module does not wrap; an overlong name/id
  combination is centered and silently clipped to 16 chars instead
  (`_pad_center()`'s own `[:width]` at the end), a known, documented
  simplification, not a crash.
- Multiple maps ("far side of the world") and region labels ("Ice
  cap") -- only a single, continuous map is rendered.
- The horizontal stagger/positioning formula below only covers `x >= 1`
  (every real sample cross-checked this phase happens to have its
  leftmost known province at `x >= 1`); `cell_pixel_column()` clamps
  `x == 0` to the same column `x == 1` would use rather than letting it
  go negative, a defensive fallback for this project's own test
  fixtures (which commonly place a lone province at `HexCoord(0, 0)`),
  not an independently confirmed real pixel position.
"""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain, province_code
from ak_engine.models.race import RACE_NAME, Race

CELL_WIDTH = 16
CELL_STRIDE = CELL_WIDTH + 1  # one real-space column separates every cell

# `_` Plains, `+` Forest, `&` Jungle, `^` Mountain, `.` Desert, `~` Sea --
# see this module's own docstring for the full sourcing. `NO_TERRAIN`
# never appears on a real map cell.
TERRAIN_SYMBOL: dict[Terrain, str] = {
    Terrain.PLAINS: "_",
    Terrain.FOREST: "+",
    Terrain.JUNGLE: "&",
    Terrain.MTNS: "^",
    Terrain.DESERT: ".",
    Terrain.SEA: "~",
}

# Confirmed directly against real map cells this phase (see module
# docstring): single-word Army Types abbreviate to their own first two
# letters, title-cased; two-word ones to both words' own initials,
# capitalized. Only the 9 types this session's own samples actually
# showed are confirmed this way -- every other `ArmyType` falls back to
# its own `.value` (the general 2-letter code already used project-wide,
# e.g. CHARACTERS report abbreviations), the best available proxy, not
# independently confirmed for *this specific* map rendering.
_CONFIRMED_RECRUIT_ABBREVIATION: dict[ArmyType, str] = {
    ArmyType.LEGION: "Le",
    ArmyType.LT_CAVALRY: "LC",
    ArmyType.PHALANX: "Ph",
    ArmyType.CAMEL_CORPS: "CC",
    ArmyType.AXEMEN: "Ax",
    ArmyType.HVY_CAVALRY: "HC",
    ArmyType.CHARIOTS: "Ch",
    ArmyType.BOWMEN: "Bo",
    ArmyType.FLEET: "Fl",
}


def _recruit_abbreviation(army_type: ArmyType) -> str:
    return _CONFIRMED_RECRUIT_ABBREVIATION.get(army_type, army_type.value)


# The map's own race field is plural ("Humans", "Orcs", "Eagles" -- all
# 3 confirmed directly against real cells this phase), unlike `RACE_NAME`
# itself (singular, used elsewhere for prose). Simple "+s" reproduces all
# 3 confirmed cases exactly; the two standard-English-irregular plurals
# below (Elf/Dwarf) are applied on the same grammatical basis the game's
# own confirmed cases already establish (always plural), not independently
# seen in a real sample.
_RACE_NAME_PLURAL_OVERRIDE: dict[Race, str] = {
    Race.ELVEN: "Elves",
    Race.DWARVEN: "Dwarves",
}


def _race_name_plural(race: Race) -> str:
    return _RACE_NAME_PLURAL_OVERRIDE.get(race, f"{RACE_NAME[race]}s")


def cell_pixel_column(coord: HexCoord) -> int:
    """The real horizontal pixel column a province's own cell starts at --
    confirmed this phase against 4 independent bands (`SE3__T1.K2`'s own
    `Tesawa`/`Marzuq` band starting at `x=2,y=3`; `Waterford Sea`/
    `Orielle`/`Shasta` at `x=1,y=4`; `Bam Yanga`/.../`Moongard` at
    `x=1,y=5`; `Abu Matariq`/.../`Big Sky` at `x=1,y=6`), zero
    contradictions: even-`y` rows are staggered right by half a cell
    width relative to odd-`y` rows -- the same real hex offset
    `turn/movement.py neighbors()` already uses (`coord.y % 2`), just
    expressed here in pixel columns instead of neighbor deltas.
    """

    stagger = CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return max(0, coord.x - 1) * CELL_STRIDE + stagger


def _pad_center(content: str, width: int, pad: str) -> str:
    """Center `content` within `width` using `pad` as the fill character,
    the extra column (if the padding is odd) going to the left -- the
    real rows-1-and-6 rule, confirmed this phase (see module docstring).
    """

    total_pad = max(0, width - len(content))
    left = (total_pad + 1) // 2
    right = total_pad - left
    return (pad * left + content + pad * right)[:width]


def _pad_framed(content: str, *, left_template: str, zone_width: int, right_template: str, symbol: str, tie_left: bool) -> str:
    """Build one "inner" row (rows 2-5): `left_template`/`right_template`
    are strings of `T` (a fixed terrain-symbol tick) and ` ` (a fixed
    real space), always the same length regardless of content -- the
    real, content-independent tick positions confirmed this phase (see
    module docstring). `content` is centered within `zone_width` real
    spaces; `tie_left` picks which side gets the extra column when the
    padding is odd -- confirmed to differ by row: row 2's own "Unowned"
    (7 chars in a 10-wide zone, 3 extra) shows 2 left/1 right (tie
    left, matching rows 1/6's own rule); rows 3-5's own "Le" (2 chars
    in a 7-wide zone, 5 extra) shows 2 left/3 right (tie right) --
    two genuinely different conventions, not a copy-paste inconsistency.
    If `content` overflows `zone_width`, it grows outward starting from the left template's own rightmost
    (zone-adjacent) characters first, converting them from `T`/` ` into
    literal content characters -- confirmed from three independent
    overflow examples this phase (`Row4`'s "Poor" and `Row5`'s
    "1% Expl.", each 1 slot over their own nominal zone, growing only
    left; `Row2`'s "Loviatar(92)"/2-over and "Brunhilda(86)"/3-over,
    each growing exactly 1 slot left and dumping the remaining overflow
    entirely into the right side): **at most 1 position grows left, and
    every remaining overflow position grows right.**
    """

    width = len(left_template) + zone_width + len(right_template)
    overflow = max(0, len(content) - zone_width)

    left = left_template
    right = right_template
    if overflow > 0:
        eat_left = min(1, len(left))  # at most 1 position grows left...
        left = left[: len(left) - eat_left] if eat_left else left
        eat_right = min(overflow - eat_left, len(right))  # ...the rest grows right
        right = right[eat_right:]

    zone = max(0, width - len(left) - len(right))
    total_pad = max(0, zone - len(content))
    if tie_left:
        pad_left = (total_pad + 1) // 2
    else:
        pad_left = total_pad // 2
    pad_right = total_pad - pad_left
    middle = (" " * pad_left + content + " " * pad_right)[:zone]

    def render(template: str) -> str:
        return "".join(symbol if ch == "T" else ch for ch in template)

    return (render(left) + middle + render(right))[:width]


# Fixed tick/space templates for rows 2-5 -- see `_pad_framed()`'s own
# docstring and this module's own "Row-by-row template" section.
_ROW2_LEFT, _ROW2_ZONE, _ROW2_RIGHT = "T T", 10, " TT"
_ROW35_LEFT, _ROW35_ZONE, _ROW35_RIGHT = "T   T", 7, "T  T"
_ROW4_LEFT, _ROW4_ZONE, _ROW4_RIGHT = "T T   T", 3, "T   TT"


def _king_name_and_id(state: GameState, kingdom_id: int) -> str | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return f"{leader.name}({leader.leader_id})"
    return None


def _status_word(tax: int) -> str:
    """The qualitative status word row 5 shows for a province owned by
    anyone other than the viewing Kingdom -- see module docstring for
    the full sourcing (both thresholds confirmed directly by the user,
    project author, first-hand game knowledge)."""

    if tax <= 2:
        return "Poor"
    if tax <= 6:
        return "Prosperous"
    return "Rich"


def render_cell(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The 6 raw content lines (16 chars each, no separator) for one
    province's own map cell -- see module docstring for the full,
    sourced field-by-field derivation.
    """

    symbol = TERRAIN_SYMBOL[province.effective_terrain()]

    id_text = f"{province_code(province.coord):04d}"
    name = (province.name or "").replace(" ", symbol)
    line1 = _pad_center(f"{name}({id_text})", CELL_WIDTH, symbol)

    if province.owner_kingdom_id is not None:
        ruler_text = _king_name_and_id(state, province.owner_kingdom_id) or "Unowned"
    else:
        ruler_text = "Unowned"
    line2 = _pad_framed(
        ruler_text, left_template=_ROW2_LEFT, zone_width=_ROW2_ZONE, right_template=_ROW2_RIGHT, symbol=symbol, tie_left=True
    )

    race_text = _race_name_plural(province.race)
    line3 = _pad_framed(
        race_text, left_template=_ROW35_LEFT, zone_width=_ROW35_ZONE, right_template=_ROW35_RIGHT, symbol=symbol, tie_left=False
    )

    recruit_text = _recruit_abbreviation(province.recruit_type_1) if province.recruit_type_1 is not None else ""
    if province.recruit_type_2 is not None:
        recruit_text += f",{_recruit_abbreviation(province.recruit_type_2)}"
    line4 = _pad_framed(
        recruit_text, left_template=_ROW4_LEFT, zone_width=_ROW4_ZONE, right_template=_ROW4_RIGHT, symbol=symbol, tie_left=False
    )

    if province.owner_kingdom_id == viewing_kingdom_id:
        status_text = f"Tax: {province.tax if province.tax is not None else 0}"
    else:
        status_text = _status_word(province.tax if province.tax is not None else 0)
    line5 = _pad_framed(
        status_text, left_template=_ROW35_LEFT, zone_width=_ROW35_ZONE, right_template=_ROW35_RIGHT, symbol=symbol, tie_left=False
    )

    expl_text = f"{province.explored_percent}%{symbol}Expl."
    line6 = _pad_center(expl_text, CELL_WIDTH, symbol)

    return [line1, line2, line3, line4, line5, line6]


def render_ascii_map(state: GameState, kingdom_id: int) -> list[str]:
    """Renders every province this Kingdom's own report shows on the map --
    see module docstring for the exact scope this phase covers (a single,
    continuous map; no name-wrap; "Unowned" always shown, never skipped).

    Reuses `describe_provinces_report()`'s own visibility convention:
    every province this Kingdom currently has any record of at all
    (`state.provinces`, unfiltered by exploration tier -- the same
    "known enough to be worth listing" bar this project's own PROVINCES
    table already uses).
    """

    provinces = list(state.provinces.values())
    if not provinces:
        return []

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: p.coord.x)
        cells = [render_cell(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [cell_pixel_column(p.coord) for p in row_provinces]

        for band_row in range(6):
            line = ""
            for cell, column in zip(cells, columns):
                if column > len(line):
                    line += " " * (column - len(line))
                elif column < len(line):
                    # Two provinces in the same row landed on overlapping
                    # columns (shouldn't happen for real, non-adjacent
                    # x values) -- keep whichever was placed first rather
                    # than corrupting the line.
                    continue
                line += cell[band_row]
            lines.append(line.rstrip())

    return lines
