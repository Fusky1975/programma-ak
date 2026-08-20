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

**Phase 569: a third, still-denser layout** (content width 11, stride
12), one of the 4 additional real strides Phase 567's own survey found
but left unimplemented. Reverse-engineered against `SE3__T3.K1`'s own
map (5 real bands, `x_min = 8` confirmed across the whole report with
zero residual using the same `x_min`-relative formula `cell_pixel_
column()` now uses -- see `stride12_cell_pixel_column()`). This tier's
own real names are short enough to fit inline (name + id, no wrap) far
less often than the wider tiers -- most cells in the sample corpus
have either the province's own name, or the ruler's own name, or both,
wrap onto a second row (the same real mechanic Phase 564 already chose
not to reproduce, applied here too). Only one cell in the whole report,
`Third` (`SE3__T3.K1` lines 476-481), is fully clean (no wrap at all),
providing the primary byte-for-byte source; a second cell, `Shark`,
wraps its own ruler name but its later rows (race/recruit/status,
shifted by the wrap the same way `_middle_fields()` already models)
independently corroborate rows 4 and 5's own tick columns.

- **Row 1/row 6**: same full-fill, tie-left, symbol-pad rule as the
  other two layouts (not independently re-confirmed against a short
  example here either, same honesty caveat as the dense layout's own).
- **Rows 2, 3/5, and 4 each have their own distinct template** -- a
  third distinct pairing, different from both the wide layout (every
  row unique) and the dense layout (2+4 paired, 3+5 paired). Row 2's
  own tick columns are `{0, 10}` -- confirmed via `Kumasi`'s own real
  "Unowned", whose own uncovered column 1 is a plain space, not a tick;
  column 2 was never independently uncovered by any real sample in this
  report (every clean row-2 content found was long enough to cover it),
  so a tick there is neither confirmed nor assumed. Row 4's own tick
  columns are `{0, 2, 10}` -- confirmed via both `Third`'s own real
  "Ax" and `Shark`'s own real "Orcs" (shifted into row 4 by `Shark`'s
  own ruler-name wrap), independently showing the same embedded tick
  at column 2 and no tick at column 8. Rows 3 and 5 share `{0, 8, 10}`
  -- confirmed via `Third`'s own real "Elves" (row 3) and `Shark`'s own
  real "Ph,WR" (row 5, shifted), both independently showing the same
  embedded tick at column 8.
- **Name truncation uses its own tier-specific constants**
  (`STRIDE12_PROVINCE_NAME_TRUNCATION_TRIGGER`/`STRIDE12_MAX_PROVINCE_
  NAME_LENGTH`), not the wide layout's reused 9/8 pair the way the
  dense layout uses -- reusing 9/8 here would still let a truncated
  name overflow this tier's own much narrower cell (8 + 6 = 14, past
  even this tier's own real flush ceiling of 12). No real sample gives
  a sourced "must stay whole" boundary at this width either, so this
  phase computed the narrowest defensible value instead of guessing
  one: truncate down to whatever leaves name + id exactly at this
  tier's own real flush ceiling (`STRIDE12_CELL_STRIDE - 6`).
- **The physical-row-indexed field-shift architecture generalizes
  unchanged** (`_middle_fields()` reused verbatim) -- `Shark`'s own
  real cell (ruler name too long, wraps to its own second row) shows
  the same cascade shape already established: rulername/rulerid split
  across rows 2-3, race/recruit pushed down to rows 4-5, and status
  merges into the border row 6 with Expl% dropped entirely, matching
  the wide layout's own `Transylvania`-style cascade exactly.

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
- **The real trigger for which of the (at least) 6 distinct cell-width
  layouts a given report uses.** Phase 567 surveyed every one of this
  project's own 107 real `Desktop/SE3__T*.K*` samples (turns 1-11,
  9 Kingdoms) by measuring each report's own real cell stride directly
  (the column delta between consecutive `(dddd)` ID codes on the same
  map line) rather than guessing: **the wide/dense split this module
  implements is only 2 of at least 6 real strides actually observed**
  -- 17 (wide, implemented), 14 (dense, implemented), 12, 10, 9, and 8
  (a real floor: several Kingdoms' own maps stay at stride 8 for many
  turns straight even as their own known-province count keeps growing
  into the hundreds -- it never gets narrower than that). Correlating
  each report's own stride against the largest *contiguous* cluster of
  known provinces in its own widest single row (excluding isolated,
  far-flung outliers like `Apurimac` above) narrows this down a lot:
  every one of the 9 Kingdoms' own stride sequences across turns 1-11
  is confirmed **strictly non-increasing** (a real map layout never
  gets wider again once it has narrowed, even though a Kingdom's own
  known-province count only ever grows) -- and the two extremes are
  unambiguous (cluster size <= 4 always means stride 17; cluster size
  >= 10 always means the stride-8 floor). **But the middle bands
  (strides 9/10/12/14, cluster sizes 4-8) do not resolve to a single-
  variable formula, and this was checked, not just left unresolved
  from insufficient effort**: `SE3__T4.K3` at turn 4 (cluster size 6,
  26 known provinces) uses stride 10, while `SE3__T4.K6` at turns 4-6
  (cluster size 7 -- larger -- and 28-38 known provinces -- also
  higher) uses stride 12 -- **wider**, not narrower, despite both of
  its own comparison metrics being higher than `K3`'s own. A real
  Kingdom-to-Kingdom counter-example, not sampling noise (re-verified
  directly against the real files, and the clustering result is stable
  across every gap-tolerance value tried from 1 to 5). This rules out
  every content-visible metric tried (total known provinces, largest
  contiguous cluster at any gap tolerance, average provinces per row,
  max row span) as the sole driver -- some Kingdom-internal state not
  printed anywhere in the report text itself must also be involved.
  The Pascal source for this specific routine was checked directly in
  `Programma Pascal.zip` (see `HostAK/TP/REPORTS.PAS` and the other 13
  `.PAS` files there) and confirmed absent -- the routine's own intro
  text ("Sire, our royal scribe...") only exists inside the compiled
  `AK.EXE`/`AKGEN.EXE` binaries, not in any available source file, so
  disassembly would be the only way to get a definitive answer, well
  outside this project's own reverse-engineering approach.
  `describe_map_report()` always calls the wide renderer; nothing
  currently picks any of the narrower ones automatically. Of the 4
  narrower tiers this phase newly discovered (strides 12, 10, 9, 8),
  stride 12 is now implemented (Phase 569, see below); strides 10, 9,
  and 8 remain entirely unimplemented -- their own row templates have
  not been derived at all.
- `cell_pixel_column()` clamps a coordinate below `x_min` to `x_min`
  itself rather than letting it go negative -- defensive only (`x_min`
  is computed as the true minimum of whatever's being rendered, so no
  real province should ever trigger this in practice), covering this
  project's own test fixtures more than any real, independently
  confirmed pixel position.
- **Phase 568: the wide layout's own horizontal-placement formula had a
  real bug, now fixed** -- `cell_pixel_column()` originally hardcoded
  `(x - 1) * CELL_STRIDE`, silently assuming every map's own leftmost
  known province sits at `x == 1`. That assumption only held because
  the one real sample this formula was originally verified against
  (`SE3__T1.K2`) happened to have `x_min == 1`. Cross-checking the
  *same real provinces* (`Sixth Sea`/`Kildare`/`M Ionium`, the same
  Kingdom) in `SE3__T1.K1` -- a different turn, `x_min == 9` there --
  showed the real report renders them starting near column 8, not
  column ~136 as the hardcoded formula would predict. Confirmed
  correct across 4 independent rows in `SE3__T1.K1` once expressed
  relative to the map's own real `x_min` instead of a hardcoded `1`:
  `cell_pixel_column()` now takes `x_min` explicitly, and `render_
  ascii_map()` computes it as `min(p.coord.x for p in provinces)`
  before rendering. This matters in practice, not just for historical
  samples: `worldgen/place_map.py DEFAULT_WIDTH = 18` means a freshly
  generated Kingdom's own home province can legitimately sit anywhere
  in that range, not just near `x == 1`. **The dense layout's own
  `dense_cell_pixel_column()` almost certainly has the same class of
  bug, but this phase could NOT determine its correct general form**:
  `SE3__T2.K1` (dense, `x_min == 8`) needs a plain `(x - x_min) *
  DENSE_CELL_STRIDE`, while `SE3__T4.K2`/`SE3__T5.K2` (dense, `x_min ==
  1`, the samples this layout was originally byte-verified against)
  need `(x - x_min + 1) * DENSE_CELL_STRIDE` -- a whole extra stride --
  to match their own real data. These two real reports directly
  contradict each other under any single formula tried; some Kingdom-
  or report-specific state not printed in the text itself must be
  involved, the same category of unresolved finding as Phase 567's own
  stride-selection trigger. `dense_cell_pixel_column()` is left
  unchanged (still only verified correct for `x_min == 1` maps) rather
  than "fixed" with an unverified guess in either direction.
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

# Phase 569: the third, still-denser layout (see module docstring's own
# Phase 567 survey -- this is the "stride 12" tier).
STRIDE12_CELL_WIDTH = 11
STRIDE12_CELL_STRIDE = STRIDE12_CELL_WIDTH + 1

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

# Phase 569: reusing the wide layout's own 9/8 pair (as Phase 566 already
# did for the dense layout) would still let a truncated name overflow
# this tier's own much narrower cell -- 8 raw characters + the 6-char
# `(dddd)` id is 14, past even this tier's own real "flush, no gap"
# ceiling of `STRIDE12_CELL_STRIDE` (12). No real sample gives a sourced
# "must stay whole" boundary at this width (same gap Phase 566 already
# had for the dense layout), so this phase picks the narrowest defensible
# option instead of an arbitrary one: truncate down to whatever leaves
# the name+id pair exactly at this tier's own flush ceiling, the same
# real boundary already confirmed for name+id rows in every layout.
STRIDE12_MAX_PROVINCE_NAME_LENGTH = STRIDE12_CELL_STRIDE - 6
STRIDE12_PROVINCE_NAME_TRUNCATION_TRIGGER = STRIDE12_MAX_PROVINCE_NAME_LENGTH + 1

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


def cell_pixel_column(coord: HexCoord, x_min: int) -> int:
    """The real horizontal pixel column a province's own cell starts at,
    relative to `x_min` -- the leftmost `x` among every province the
    map actually renders (see module docstring's own Phase 568 note on
    why this is relative, not the fixed `x - 1` this phase-562 formula
    originally hardcoded). Even-`y` rows are staggered right by half a
    cell width relative to odd-`y` rows -- the same real hex offset
    `turn/movement.py neighbors()` already uses (`coord.y % 2`), just
    expressed here in pixel columns instead of neighbor deltas.

    Confirmed against 4 independent bands within a single report
    (`SE3__T1.K2`, `x_min=1`) at Phase 562, and re-confirmed this phase
    against `SE3__T1.K1` -- the *same real provinces*, same Kingdom,
    different turn, `x_min=9` there instead of 1 -- with zero
    contradictions once the formula is expressed relative to `x_min`
    rather than a hardcoded `1`.
    """

    stagger = CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return max(0, coord.x - x_min) * CELL_STRIDE + stagger


def dense_cell_pixel_column(coord: HexCoord) -> int:
    """The dense layout's own horizontal pixel column -- see module
    docstring's own Phase 568 note. Matches every real `SE3__T4.K2`/
    `SE3__T5.K2` band this module was byte-verified against (both
    reports' own maps have `x_min == 1`, where this reduces to
    `x * DENSE_CELL_STRIDE`) -- **but Phase 568 found this does NOT
    generalize the way `cell_pixel_column()`'s own wide-layout formula
    does**: `SE3__T2.K1` (a *different* dense-layout report, `x_min ==
    8`) needs a plain `(x - x_min) * DENSE_CELL_STRIDE`, with no extra
    offset, to match its own real leading whitespace -- directly
    contradicting the `+1 stride` that `SE3__T4.K2`/`SE3__T5.K2` need.
    Left unchanged (not "fixed" with an unverified guess in either
    direction) pending more samples or the user's own knowledge of the
    real rule -- see the module docstring for the full account.
    """

    stagger = DENSE_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return coord.x * DENSE_CELL_STRIDE + stagger


def stride12_cell_pixel_column(coord: HexCoord, x_min: int) -> int:
    """The stride-12 layout's own horizontal pixel column -- see module
    docstring's own Phase 569 note. Confirmed against every one of
    `SE3__T3.K1`'s own 5 real bands (`x_min = 8`, the true minimum
    across the whole report, not just the row being placed): a plain
    `(x - x_min) * STRIDE12_CELL_STRIDE + stagger`, zero residual --
    the same clean, `x_min`-relative shape `cell_pixel_column()` uses
    for the wide layout, not `dense_cell_pixel_column()`'s own
    unresolved one.
    """

    stagger = STRIDE12_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return max(0, coord.x - x_min) * STRIDE12_CELL_STRIDE + stagger


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

# Confirmed stride-12-layout tick columns (see module docstring's own
# Phase 569 section) -- unlike the dense layout, rows 2 and 4 do NOT
# share a template here: row 2's own tick columns are `{0, 10}` (no
# embedded tick -- confirmed via `Kumasi`'s own real "Unowned", whose
# own uncovered column 1 shows a plain space, not a tick; column 2 was
# never independently uncovered by any real sample, so a tick there is
# neither confirmed nor ruled out, and none is assumed); row 4's own
# are `{0, 2, 10}` (confirmed via both `Third`'s own real "Ax" and
# `Shark`'s own real "Orcs", independently showing the same embedded
# tick at column 2, and no tick at column 8). Rows 3 and 5 DO share one
# set, `{0, 8, 10}` (confirmed via `Third`'s own real "Elves" at row 3
# and `Shark`'s own real "Ph,WR" at row 5, both independently showing
# the same embedded tick at column 8).
_STRIDE12_ROW2_TICKS = frozenset({0, 10})
_STRIDE12_ROW35_TICKS = frozenset({0, 8, 10})
_STRIDE12_ROW4_TICKS = frozenset({0, 2, 10})


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

    x_min = min(p.coord.x for p in provinces)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: p.coord.x)
        cells = [render_cell(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [cell_pixel_column(p.coord, x_min) for p in row_provinces]

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


# Stride-12-layout analogue of `_ROW_TEMPLATES` -- row 2 has its own
# template, rows 3/5 share `_STRIDE12_ROW35_TICKS`, row 4 has its own
# (see module docstring's own Phase 569 section) -- a different pairing
# from both the wide and dense layouts. The physical-row-indexed shift
# architecture is otherwise identical.
_STRIDE12_ROW_TEMPLATES: list[frozenset[int]] = [
    _STRIDE12_ROW2_TICKS,
    _STRIDE12_ROW35_TICKS,
    _STRIDE12_ROW4_TICKS,
    _STRIDE12_ROW35_TICKS,
]


def render_cell_stride12(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The stride-12 layout's own 6 raw content lines (11 chars each, no
    separator) for one province's own map cell -- see module docstring's
    own Phase 569 section for the full, sourced derivation.
    """

    symbol = TERRAIN_SYMBOL[province.effective_terrain()]

    id_text = f"{province_code(province.coord):04d}"
    raw_name = province.name or ""
    if len(raw_name) > STRIDE12_PROVINCE_NAME_TRUNCATION_TRIGGER:
        raw_name = raw_name[:STRIDE12_MAX_PROVINCE_NAME_LENGTH]
    name = raw_name.replace(" ", symbol)
    line1 = _pad_center(f"{name}({id_text})", STRIDE12_CELL_WIDTH, symbol)

    middle_fields = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)
    middle_lines = [
        _pad_overlay(text, tick_columns=ticks, symbol=symbol, width=STRIDE12_CELL_WIDTH)
        for text, ticks in zip(middle_fields, _STRIDE12_ROW_TEMPLATES)
    ]

    if len(middle_lines) == len(_STRIDE12_ROW_TEMPLATES):
        expl_text = f"{province.explored_percent}%{symbol}Expl."
        last_line = _pad_center(expl_text, STRIDE12_CELL_WIDTH, symbol)
    else:
        expl_text = f"{province.explored_percent}% Expl."
        ticks = _STRIDE12_ROW_TEMPLATES[len(middle_lines)]
        middle_lines.append(_pad_overlay(expl_text, tick_columns=ticks, symbol=symbol, width=STRIDE12_CELL_WIDTH))
        last_line = symbol * STRIDE12_CELL_WIDTH

    return [line1, *middle_lines, last_line]


def render_ascii_map_stride12(state: GameState, kingdom_id: int) -> list[str]:
    """The stride-12 layout's own analogue of `render_ascii_map()` -- see
    module docstring's own Phase 569 section. Nothing currently calls
    this: which layout a given report actually uses is still an open
    question (see module docstring's own deferred-gaps list), so
    `describe_map_report()` keeps calling the wide renderer above.
    """

    provinces = list(state.provinces.values())
    if not provinces:
        return []

    x_min = min(p.coord.x for p in provinces)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: p.coord.x)
        cells = [render_cell_stride12(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [stride12_cell_pixel_column(p.coord, x_min) for p in row_provinces]

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
