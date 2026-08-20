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
   literal `Unowned` if `owner_kingdom_id is None` -- framed, tie-left
   (confirmed directly: `Shasta`'s own real "Unowned", 7 chars in a
   10-wide zone, 3 extra padding chars split 2-left/1-right in
   `SE3__T1.K2` -- the opposite tie direction from rows 3-5).
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
   table omits it). **This row is entirely omitted (Phase 565) when the
   province's own race is not one of `models/race.py HUMANOID_RACES`**
   -- a monster-guarded province has no recruitable army units to list,
   confirmed directly: `Shasta`'s own real race is `Eagles`
   (`SE3__T1.K2`), and its own cell has no recruit row at all -- the
   status word shifts up to fill physical row 4 (using row 4's own
   framed template, not row 3/5's -- confirmed by `Shasta`'s own real
   "Poor" padding, which matches row 4's tick pattern exactly, not row
   3/5's), and Expl% un-merges into its own physical row 5 (framed, not
   full-fill, since it no longer shares the row with the border) leaving
   row 6 a pure, content-less border line. See `_ROW_TEMPLATES`/
   `_middle_fields()` below for the general mechanism.
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

**Phase 566: a second, denser layout** (content width 13, stride 14),
confirmed real -- every band in `SE3__T5.K2`'s own map (a later-turn
report, more provinces known) uses this instead of the wide layout
above, matching the original AKGEN report's own claim of "a second,
denser layout from the mid-game corpus onward" (previously unverified
in this project). Reverse-engineered this phase against 5 clean bands
in `SE3__T5.K2` (`Tesawa`/`Marzuq`/`Cantia` at `y=3`; `Waterford Sea`/
`Orielle`/`Shasta`/`Katanga` at `y=4`; `Bam Yanga`/`Macondo`/`Mongu`/
`Moongard` at `y=5`; `Jadegate`/`Kiska`/`Kaluga` at `y=7`; `Katmai`/
`Khalturin` at `y=8`), using exact string-index anchors from each
province's own ID code, not by-eye alignment (the very mistake that
mis-cited `Tesawa`/`Marzuq` as ruler-skip examples earlier in this same
module's own history -- see the Phase 565 note above). Cells whose own
name (or ruler's own name) wraps onto a second row (`Bam Yanga`,
`Waterford Sea`, `Moongard`, `Khalturin`, `Abu Matariq`, `Transylvania`)
were excluded from sourcing the rules below, same reasoning as the wide
layout's own `Transylvania` exclusion.

- **Horizontal placement**: `dense_cell_pixel_column(coord) = coord.x *
  DENSE_CELL_STRIDE + (DENSE_CELL_STRIDE // 2 if coord.y % 2 == 0 else
  0)` -- confirmed via every cell in all 5 clean bands (multiple `x`
  values per band, confirming the intra-row stride; multiple `y`
  parities, confirming the stagger), zero contradictions. **Genuinely
  different from the wide layout's own formula**: no `(x - 1)` term --
  `x` multiplies the stride directly, not offset by one. One real cell
  (`Apurimac(1806)` at `y=6`) does not fit this formula at all (its
  own real ID implies `x=18`, far outside the row's other provinces at
  `x=1-3`, yet it renders immediately adjacent to them with no gap) --
  not modeled, most likely a second/distant-landmass province the
  renderer packs into a partially-empty row rather than a placement-
  formula exception; consistent with the already-deferred "multiple
  maps" gap above, not independently investigated further this phase.
- **Row 1 (name/id) and row 6 (border/Expl%, when nothing's skipped)**:
  same full-fill, tie-left, symbol-pad rule as the wide layout's own
  rows 1/6 (not independently re-confirmed against a short/padded dense
  example -- every dense name+id in the clean corpus fills 11-14 of the
  13 available characters, leaving no padding to inspect -- inferred by
  consistency with the wide layout and the absence of any contradicting
  data, same honesty level as the wide layout's own original row-2 tie
  direction before it was independently confirmed).
- **Rows 2 (ruler) and 4 (recruit) share one template; rows 3 (race) and
  5 (status/Expl%) share another** -- a different pairing from the wide
  layout (where every row had its own template). Both use the same
  underlying algorithm, confirmed via `_pad_overlay()` below: content is
  centered across the **full** 13-column cell (tie-left, no separate
  "zone" -- confirmed unambiguously via `Bradipo I(2)`, a 12-character,
  odd-padding case whose start position only matches a tie-left, not
  tie-right, full-width centering); the cell starts from a background
  canvas that is the terrain symbol at a fixed, row-dependent set of
  "tick" columns and a real space everywhere else; each content
  character then overlays that canvas at its own centered position --
  a **non-space** character always overwrites the canvas (tick or
  space, whichever's underneath), while a **space** character in the
  content is transparent and leaves the canvas showing through. Rows
  2/4's own tick columns are `{0, 2, 10, 12}` (confirmed via `Circe(8)`
  and `Unowned` in row 2, `Le`/`Le,Ch` in row 4 -- both leave columns
  3-9 as a clean 7-wide gap with no embedded tick); rows 3/5's own tick
  columns are `{0, 4, 8, 12}` (confirmed via `Orcs` in row 3 leaving
  column 4 visibly free; **directly confirmed at column 8 specifically
  by a genuine anomaly**: `Macondo`'s own real status `Tax: 4` shows a
  terrain-symbol tick, not a literal space, exactly where the content's
  own internal word-gap falls -- because `Tax: 4` is one character
  shorter than `Tax: 10`, its centered internal space lands squarely on
  column 8's tick, letting it show through, whereas `Tax: 10`'s own
  internal space lands one column earlier at a plain position and stays
  literal; both `Shasta`/`Kiska`'s own real unmerged `8% Expl.` row 5
  -- the shifted-Expl% case, see below -- independently corroborate the
  same tick set, their own internal space always landing on a plain,
  non-tick column). Confirmed tie-left (not tie-right, unlike the wide
  layout's own rows 3-5) via three independent odd-padding examples:
  `Bradipo I(2)` (row 2, 12 chars), `CC`/`Le` (row 4, 2 chars), `Orcs`
  (row 3, 4 chars) -- every one lands exactly where tie-left predicts,
  never tie-right.
- **The physical-row-indexed field-shift architecture generalizes
  unchanged**: `Cantia` (`y=3`) and `Katanga` (`y=4`) are two more
  confirmed real ruler-row-skip cells (in addition to the wide layout's
  own still-unexplained `Cantia`/`Tesawa` contrast) -- both show their
  race directly at physical row 2 using row 2's own template, recruit
  at physical row 3 using row 3's own template, status at physical row
  4 using row 4's own template, and Expl% unmerged at physical row 5
  using row 5's own template, byte-for-byte matching the same
  "`_ROW_TEMPLATES` tied to the physical row" model already established
  for the wide layout's own recruit-skip case -- reused verbatim here
  (`_middle_fields()` is layout-agnostic). `Kiska` (`y=7`, race
  `Eagles`) independently confirms the recruit-skip case (`HUMANOID_
  RACES`) in this layout too, matching `Shasta`. The ruler-skip
  trigger itself stays just as unimplemented here as in the wide layout
  (no data-model distinction exists to explain it) -- this module
  always prints "Unowned" for the dense layout too.
- **Name truncation reuses the wide layout's own constants** (`PROVINCE_
  NAME_TRUNCATION_TRIGGER`/`MAX_PROVINCE_NAME_LENGTH`, 9/8) rather than
  a dense-specific pair -- no real dense-layout sample confirms an exact
  "must stay whole" boundary the way `Bam Yanga` did for the wide
  layout (every short dense name in the clean corpus is well under any
  plausible threshold; every long one wraps), so there is no sourced
  dense-specific number to derive. Reusing the same constants is a safe
  simplification consistent with the user's own general preference
  (simplicity over exact wrap fidelity, Phase 564) -- 8 raw characters
  always fits comfortably within the dense cell's own 13-column width,
  it just truncates somewhat more eagerly than dense's own real wrap
  boundary (14 total, vs. wide's own higher real boundary) would
  strictly require.

**Explicitly NOT modeled this phase, confirmed real but not yet
reconciled with enough samples to state a rule with the same
confidence as the above** (see this module's own Phase 562 audit notes
in `README.md` for the full account):
- A province whose ruler is genuinely unknown (not just "no ruler")
  sometimes *skips* the ruler row entirely rather than printing
  "Unowned" -- confirmed real: `Cantia`'s own cell in `SE3__T5.K2`
  shows its race directly at physical row 2, skipping the ruler row,
  even though `Cantia`'s own race (Human) is a `HUMANOID_RACES` member
  and its cell is otherwise structurally unremarkable. Contrasted with
  `Tesawa`, an apparently-also-unowned province in the very same
  report's own band, which explicitly prints "Unowned". No data-model
  distinction currently exists in this project (`ProvinceState.owner_
  kingdom_id: int | None` only encodes a binary owned/unowned) to
  explain why one skips and the other doesn't -- this module always
  prints "Unowned" (never skips), the simpler, fully-confirmed-as-real
  of the two observed behaviors, rather than inventing an unsourced
  finer-grained knowledge tier to explain the real difference.
- The real game wraps a too-long province name onto its own second row,
  which then forces something else out of the fixed 6-row budget
  (observed: the Expl%/status row gets dropped entirely in favor of
  keeping the status word, `Transylvania` in `SE3__T1.K2`). **By the
  user's own explicit choice (Phase 564), this module does not
  reproduce that** -- a name longer than `PROVINCE_NAME_TRUNCATION_
  TRIGGER` (9 -- `Bam Yanga`'s own real, verified 9 characters stay
  whole) is cut to its own first `MAX_PROVINCE_NAME_LENGTH` (8) raw
  characters instead (e.g. "Marnus Sea" -> "Marnus S", the user's own
  worked example), keeping
  every cell at a uniform 6 lines with no row-budget juggling. This is
  a deliberate simplification, not an attempt to reproduce the real
  wrap-and-drop behavior.
- Multiple maps ("far side of the world") and region labels ("Ice
  cap") -- only a single, continuous map is rendered.
- **The real trigger for which layout (wide or dense, see below) a given
  report uses** -- `SE3__T1.K2` (early turn, few provinces known) uses
  wide; `SE3__T5.K2` (later turn, more known) uses dense; not enough
  samples across intermediate turns have been checked to state the
  exact threshold. `describe_map_report()` always calls the wide
  renderer; nothing currently picks the dense one automatically.
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
from ak_engine.models.race import HUMANOID_RACES, RACE_NAME, Race

CELL_WIDTH = 16
CELL_STRIDE = CELL_WIDTH + 1  # one real-space column separates every cell

# Phase 566: the second, denser layout used by later-turn reports (see
# module docstring) -- narrower cells, one real-space column between them.
DENSE_CELL_WIDTH = 13
DENSE_CELL_STRIDE = DENSE_CELL_WIDTH + 1

# Phase 564: confirmed directly by the user (project author) -- a
# province name longer than `PROVINCE_NAME_TRUNCATION_TRIGGER` is cut to
# its own first `MAX_PROVINCE_NAME_LENGTH` raw characters (before the
# space-replacement rule below), not wrapped onto its own second row the
# way the real game itself does (see module docstring's own deferred-
# gaps list for why that real behavior stays unmodeled). "Marnus Sea"
# (10 chars) -> "Marnus S" is the user's own worked example. The trigger
# is 10, not 8: "Bam Yanga" (9 chars) is confirmed to render in full,
# untruncated, in the same real, byte-for-byte-verified band this
# module's own docstring cites (`SE3__T1.K2` line 314) -- the user
# confirmed 9-character names stay whole once this conflict with
# already-verified data was flagged.
PROVINCE_NAME_TRUNCATION_TRIGGER = 9
MAX_PROVINCE_NAME_LENGTH = 8

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


def dense_cell_pixel_column(coord: HexCoord) -> int:
    """The dense layout's own horizontal pixel column -- see module
    docstring's own Phase 566 section. Confirmed against every cell in
    5 independent `SE3__T5.K2` bands: unlike `cell_pixel_column()`
    above, `x` multiplies the stride directly, with no `-1` offset.
    """

    stagger = DENSE_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return coord.x * DENSE_CELL_STRIDE + stagger


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


def _pad_overlay(content: str, *, tick_columns: frozenset[int], symbol: str, width: int = DENSE_CELL_WIDTH) -> str:
    """Build one dense-layout inner row (rows 2-5) -- see module
    docstring's own Phase 566 section. Unlike `_pad_framed()`'s flanking-
    template model, the dense layout centers `content` across the
    **full** cell width (tie-left, confirmed), starting from a
    background canvas that is the terrain `symbol` at `tick_columns`
    and a real space everywhere else; each content character then
    overlays that canvas at its own centered position -- a non-space
    character always overwrites the canvas, a space character is
    transparent and leaves the canvas showing through (confirmed
    directly via `Macondo`'s own real `Tax: 4`, whose internal space
    lands on a tick and shows the terrain symbol, vs. `Tax: 10`'s own
    internal space, which lands on a plain column and stays literal).
    """

    pad = max(0, width - len(content))
    start = (pad + 1) // 2  # tie-left, confirmed (see module docstring)
    canvas = [symbol if i in tick_columns else " " for i in range(width)]
    for i, ch in enumerate(content):
        if 0 <= start + i < width and ch != " ":
            canvas[start + i] = ch
    return "".join(canvas)


# Confirmed dense-layout tick columns -- rows 2/4 share one set, rows
# 3/5 share another (see module docstring's own Phase 566 section).
_DENSE_ROW24_TICKS = frozenset({0, 2, 10, 12})
_DENSE_ROW35_TICKS = frozenset({0, 4, 8, 12})


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


# The 4 "inner" row templates, in physical row order (row 2 through 5) --
# see module docstring's own Phase 565 note. A cell's own "middle"
# fields (ruler, race, recruit, status) always fill these consecutively
# starting at row 2, in this fixed template order -- confirmed directly:
# when the recruit-type field is skipped (see `_middle_fields()`), the
# status word that shifts up into physical row 4 renders using row 4's
# own template (not row 3/5's), not the field's usual one.
_ROW_TEMPLATES: list[tuple[str, int, str, bool]] = [
    (_ROW2_LEFT, _ROW2_ZONE, _ROW2_RIGHT, True),
    (_ROW35_LEFT, _ROW35_ZONE, _ROW35_RIGHT, False),
    (_ROW4_LEFT, _ROW4_ZONE, _ROW4_RIGHT, False),
    (_ROW35_LEFT, _ROW35_ZONE, _ROW35_RIGHT, False),
]


def _middle_fields(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The cell's own "middle" field values, in order, skipping any that
    this phase confirms get omitted -- see module docstring's own Phase
    565 note. Ruler is always included here (this project has no sourced
    trigger yet for the real game's own occasional ruler-row omission,
    e.g. `Cantia` in `SE3__T5.K2` -- a genuinely confirmed real case,
    deliberately left unmodeled rather than guessed at, see module
    docstring). Recruit is omitted for a non-`HUMANOID_RACES` province
    (`Shasta`'s own real `Eagles` race, `SE3__T1.K2`) -- a monster-
    guarded province has no recruitable army units to list.
    """

    if province.owner_kingdom_id is not None:
        ruler_text = _king_name_and_id(state, province.owner_kingdom_id) or "Unowned"
    else:
        ruler_text = "Unowned"

    race_text = _race_name_plural(province.race)

    if province.owner_kingdom_id == viewing_kingdom_id:
        status_text = f"Tax: {province.tax if province.tax is not None else 0}"
    else:
        status_text = _status_word(province.tax if province.tax is not None else 0)

    fields = [ruler_text, race_text]
    if province.race in HUMANOID_RACES:
        recruit_text = _recruit_abbreviation(province.recruit_type_1) if province.recruit_type_1 is not None else ""
        if province.recruit_type_2 is not None:
            recruit_text += f",{_recruit_abbreviation(province.recruit_type_2)}"
        fields.append(recruit_text)
    fields.append(status_text)
    return fields


def render_cell(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The 6 raw content lines (16 chars each, no separator) for one
    province's own map cell -- see module docstring for the full,
    sourced field-by-field derivation.
    """

    symbol = TERRAIN_SYMBOL[province.effective_terrain()]

    id_text = f"{province_code(province.coord):04d}"
    raw_name = province.name or ""
    if len(raw_name) > PROVINCE_NAME_TRUNCATION_TRIGGER:
        raw_name = raw_name[:MAX_PROVINCE_NAME_LENGTH]
    name = raw_name.replace(" ", symbol)
    line1 = _pad_center(f"{name}({id_text})", CELL_WIDTH, symbol)

    middle_fields = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)
    middle_lines = [
        _pad_framed(text, left_template=left, zone_width=zone, right_template=right, symbol=symbol, tie_left=tie_left)
        for text, (left, zone, right, tie_left) in zip(middle_fields, _ROW_TEMPLATES)
    ]

    if len(middle_lines) == len(_ROW_TEMPLATES):
        # Nothing skipped -- Expl% merges into the border row, matching
        # every field-complete cell already confirmed (Phase 562). Space
        # is replaced by the terrain symbol, like every other full-fill
        # row.
        expl_text = f"{province.explored_percent}%{symbol}Expl."
        last_line = _pad_center(expl_text, CELL_WIDTH, symbol)
    else:
        # A field was skipped -- Expl% gets its own row (the next
        # unused template slot), and the border row stays pure,
        # matching `Shasta`'s own real cell (`SE3__T1.K2`) exactly. As
        # an ordinary framed inner row now (not merged into the
        # border), it keeps its own real space, like every other inner
        # row's internal word gaps.
        expl_text = f"{province.explored_percent}% Expl."
        left, zone, right, tie_left = _ROW_TEMPLATES[len(middle_lines)]
        middle_lines.append(
            _pad_framed(expl_text, left_template=left, zone_width=zone, right_template=right, symbol=symbol, tie_left=tie_left)
        )
        last_line = symbol * CELL_WIDTH

    return [line1, *middle_lines, last_line]


# Dense-layout analogue of `_ROW_TEMPLATES` -- rows 2/4 share
# `_DENSE_ROW24_TICKS`, rows 3/5 share `_DENSE_ROW35_TICKS` (see module
# docstring's own Phase 566 section). The physical-row-indexed shift
# architecture is otherwise identical to the wide layout's own.
_DENSE_ROW_TEMPLATES: list[frozenset[int]] = [
    _DENSE_ROW24_TICKS,
    _DENSE_ROW35_TICKS,
    _DENSE_ROW24_TICKS,
    _DENSE_ROW35_TICKS,
]


def render_cell_dense(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The dense layout's own 6 raw content lines (13 chars each, no
    separator) for one province's own map cell -- see module docstring's
    own Phase 566 section for the full, sourced derivation.
    """

    symbol = TERRAIN_SYMBOL[province.effective_terrain()]

    id_text = f"{province_code(province.coord):04d}"
    raw_name = province.name or ""
    if len(raw_name) > PROVINCE_NAME_TRUNCATION_TRIGGER:
        raw_name = raw_name[:MAX_PROVINCE_NAME_LENGTH]
    name = raw_name.replace(" ", symbol)
    line1 = _pad_center(f"{name}({id_text})", DENSE_CELL_WIDTH, symbol)

    middle_fields = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)
    middle_lines = [
        _pad_overlay(text, tick_columns=ticks, symbol=symbol)
        for text, ticks in zip(middle_fields, _DENSE_ROW_TEMPLATES)
    ]

    if len(middle_lines) == len(_DENSE_ROW_TEMPLATES):
        expl_text = f"{province.explored_percent}%{symbol}Expl."
        last_line = _pad_center(expl_text, DENSE_CELL_WIDTH, symbol)
    else:
        expl_text = f"{province.explored_percent}% Expl."
        ticks = _DENSE_ROW_TEMPLATES[len(middle_lines)]
        middle_lines.append(_pad_overlay(expl_text, tick_columns=ticks, symbol=symbol))
        last_line = symbol * DENSE_CELL_WIDTH

    return [line1, *middle_lines, last_line]


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


def render_ascii_map_dense(state: GameState, kingdom_id: int) -> list[str]:
    """The dense layout's own analogue of `render_ascii_map()` -- see
    module docstring's own Phase 566 section. Nothing currently calls
    this: which layout a given report actually uses is still an open
    question (see module docstring's own deferred-gaps list), so
    `describe_map_report()` keeps calling the wide renderer above.
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
        cells = [render_cell_dense(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [dense_cell_pixel_column(p.coord) for p in row_provinces]

        for band_row in range(6):
            line = ""
            for cell, column in zip(cells, columns):
                if column > len(line):
                    line += " " * (column - len(line))
                elif column < len(line):
                    continue
                line += cell[band_row]
            lines.append(line.rstrip())

    return lines
