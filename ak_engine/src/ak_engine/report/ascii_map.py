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
  **Phase 629 found the real explanation**: `Apurimac` isn't a distant
  landmass at all -- `x=18` is cylindrically adjacent to `x=1`
  (confirmed Phase 624), so it renders immediately adjacent for the
  same reason any two ordinary neighboring columns would. See this
  module's own Phase 629 addendum near the end of this docstring.
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

**Phase 570: a fourth, still-denser layout** (content width 9, stride
10), reverse-engineered against `SE3__T4.K3`'s own map (6 real bands,
`x_min = 4` confirmed across the whole report with zero residual, the
same formula shape as wide and stride-12). This tier's own real corpus
is different in kind from the 3 wider ones: **every single cell wraps
its own name onto row 1 with the id pushed to its own row 2** -- not
an occasional long-name case (as it is for every wider tier), but
universal, since even a 3-character name already leaves no room for a
6-character id in a 9-column cell. This phase reproduces that real
split directly (`render_cell_stride10()`'s own dedicated row-1/row-2
structure) instead of extending the truncate-to-fit policy to a case
this pervasive -- see `STRIDE10_MAX_PROVINCE_NAME_LENGTH`'s own comment
for why.
- **Row 2 (id) and the ruler/recruit rows share one border-only set**,
  `{0, 8}` -- confirmed via `Kilkenny`'s own real recruit "Le" (2
  characters, independently uncovering columns 1, 2, 3, 6, and 7, all
  plain space, no embedded tick anywhere). **The race row alone has an
  embedded tick**, `{0, 2, 8}` -- confirmed via `Daedalus`'s own real
  race "Orcs", column 2 uncovered and showing the tick.
- **The row budget is genuinely different from the 3 wider layouts**:
  because the id-wrap is mandatory here (not optional), the real
  corpus only ever frames 3 of the up to 4 middle fields (ruler, race,
  recruit-or-shifted-status); the 4th, when present (recruit shown),
  always merges into row 6 full-fill instead, with Expl% dropped
  entirely -- confirmed via `Starhaven`'s own real cell (`Rich` merges
  into row 6, no separate Expl% line at all), contrasted with `Sixth
  Sea`'s own real recruit-skip cell (only 3 fields, so row 6 stays
  free for Expl% to merge in as usual). `render_cell_stride10()`
  reproduces this real 3-framed-slot-plus-merge shape directly (unlike
  the other 3 layouts' own generalized 4-framed-slot-plus-merge
  architecture) -- the 4th slot's own canvas, when actually needed,
  reuses the border-only set by pattern consistency, not independent
  confirmation, since the real corpus never frames it (see
  `_STRIDE10_BORDER_TICKS`'s own comment).
- **A newly confirmed, real, but explicitly unmodeled anomaly**: two
  cells in this same report (`M Actium` and `Kabompo Sea`) skip BOTH
  race and recruit entirely, going straight from ruler to status --
  unlike `Sixth Sea`/`Valiant Sea` (also Whales-race, in the very same
  report), which only skip recruit and still show race normally. All
  four share the same terrain (Sea) and the same apparent ownership
  state (`Unowned`), so neither terrain nor ownership distinguishes
  them from this report's own text -- the same category of hidden,
  unprinted state already established for the ruler-skip case (`Cantia`
  vs. `Tesawa`, Phase 562/566) and the layout-selection trigger (Phase
  567). This module keeps showing race normally in every case (never
  skips it), the same "don't invent unsourced data" choice already
  made for the ruler-skip gap. **Phase 571 found this same anomaly a
  third and fourth time**, in a completely different report (`SE3__
  T4.K8`): `Terran Sea` and one other cell there also skip both race
  and recruit, landing status directly at physical row 4 and (unlike
  the stride-10 examples, which drop Expl% entirely) Expl% at row 5 --
  since this report's own well-understood cells never show Expl% at
  all otherwise, this specific anomaly is the only known real case
  where this layout's Expl% appears, reinforcing that it's a genuinely
  different, unmodeled cell state, not merely "race/recruit omitted."
- **A region label was found for the first time this phase**: `SE3__
  T4.K3`'s own map opens with `"Ice cap"` followed by a full-width
  dashed rule, before the first band -- confirmed real, matching the
  already-deferred "region labels" gap from Phase 562's own docstring
  (see below); still not implemented, now with a first concrete real
  example to work from whenever that gap is picked up.

**Phase 571: a fifth, still-denser layout** (content width 8, stride
9), reverse-engineered against `SE3__T4.K8`'s own map. Structurally
identical in kind to stride 10 (name/id always split), but with an even
tighter row budget: **only the first 3 of `_middle_fields()`'s own up
to 4 fields ever get a row at all** -- a genuine 4th field (status,
present only when recruit is shown) is dropped entirely, with no row-6-
style merge to fall back on (there is no 6th row here; every real cell
this phase confirmed is exactly 5 lines: name, id, and 3 framed middle
slots). Confirmed via `Katanga` (recruit shown -- no status or Expl%
anywhere in its own real cell) contrasted with `Shasta` (recruit
skipped, race Eagles -- status takes recruit's own normal slot
instead, still no Expl%).
- **The placement formula needed real cross-checking, not an assumed
  fit**: an initial derivation using this report's own visible `x_min`
  gave a *different*, nonzero residual on every single one of ~25
  independently measured `(x, y)` pairs across 6 of its own real bands
  -- re-solving directly from the raw data (rather than assuming the
  wide/stride-12/stride-10 layouts' own zero-residual convention just
  transfers) found the residual is a clean, constant 2 full strides,
  as if this specific report's own true `x_min` sits 2 columns left of
  its own visible minimum. This is a bigger version of the exact same
  unexplained-margin phenomenon Phase 568 already found for the dense
  layout (there, 1 stride, not 2) -- `stride9_cell_pixel_column()`
  still exposes the same clean, `x_min`-relative formula shape the 3
  already-fixed layouts use, but callers should not assume the right
  `x_min` to pass is simply "the smallest known `x`" the way they
  reasonably can for those three. **Closed by Phase 629**: the report's
  own real corpus has two known provinces at `x == 17`/`x == 18`,
  cylindrically adjacent to its own `x == 1` cluster -- exactly 2
  strides, matching the residual found here exactly.
- **Row 4 (race) and row 5 (recruit-or-shifted-status) each have their
  own distinct, real tick pattern**: row 4's is `{0, 6, 7}` (confirmed
  via `Moongard`'s own real "Orcs"). Row 5's is unusually tick-heavy
  for this project -- `{0, 1, 2, 5, 6, 7}`, leaving only 2 real columns
  of flexible zone -- confirmed directly via `Balmwood`'s own real
  2-character recruit "Bo" (independently uncovering all 6 of those
  columns as ticks, none as plain space), corroborated by `Shasta`'s
  own real shifted status "Poor" showing the identical pattern. Row 2
  (id) and row 3 (ruler) share the plain border-only set, `{0, 7}` --
  not independently confirmed beyond the universal border edges, since
  every real ruler name sampled in this report happened to be exactly
  8 characters long, filling the cell with no padding left to inspect.
- **A newly confirmed Army Type abbreviation**: `Katanga`'s own real
  recruit text, "Le,El", confirms `ArmyType.ELEPHANTS` follows the same
  single-word "first two letters, title-cased" rule as the other 9
  already-confirmed types (not its own raw `.value`, `"EL"`) -- added
  to `_CONFIRMED_RECRUIT_ABBREVIATION`.

**Phase 572: the sixth and narrowest layout** (content width 7, stride
8) -- the real floor Phase 567's own survey already identified (no
Kingdom's own map ever narrows past this, even at 100+ known
provinces). Reverse-engineered against `SE3__T5.K1`'s own map. This is
the simplest of all 6 layouts: **every real cell this phase confirmed
is exactly 4 lines** -- name, id, ruler, race, full stop. Recruit,
status, and Expl% are never shown at all, regardless of race or
ownership -- confirmed via `Sherwood` (race Human, a `HUMANOID_RACES`
member, still shows no recruit row; nothing to skip, since there's no
row for it to occupy in the first place).
- **The placement formula needed no correction this time**: `SE3__
  T5.K1`'s own true `x_min` matches its own visible minimum exactly,
  confirmed across ~50 independent `(x, y)` measurements spanning all 7
  of its own real bands, zero residual -- the clean shape, not the
  dense/stride-9 layouts' own unexplained-margin one.
- **Row 4 (race) has one embedded tick**, `{0, 1, 6}` -- confirmed via
  both `Peachwood`'s own real race "Ents" and `Limerick`'s own real
  "Orcs", independently showing the same tick at column 1. Row 3
  (ruler) stays border-only, `{0, 6}` -- not independently confirmed
  beyond the universal border edges, since every real ruler name
  sampled in this report was either exactly 7 characters (filling the
  cell) or long enough to flush past it.
- **The "both race and recruit skipped" anomaly recurs a fifth time**
  (`Mammoth`, `SE3__T5.K1`'s own report) -- at this tier it shows as
  status appearing directly at physical row 4 in place of race, the
  same unmodeled real behavior first found in Phase 570 and repeated
  in Phase 571 (this report's own "far side of the world" second map,
  see below, does NOT show it -- both of its own real cells, `Chaco`
  and `Kilkenny`, display race normally).
- **This phase closes the "how many real layouts exist" question**
  Phase 567 opened: all 6 real strides that survey found (17, 14, 12,
  10, 9, 8) are now implemented and byte-verified. What remains open
  is which of the 6 a given report actually uses (Phase 567's own
  unresolved trigger, later shipped as a labeled 82% approximation,
  Phase 627); the dense and stride-9 layouts' own placement-formula
  anomalies (Phase 568/571) were later closed too, by Phase 629 (see
  this docstring's own Phase 629 addendum).

**Phase 577: the "Ice cap" region label, previously deferred.** Cross-
checked against ~10 real samples spanning multiple turns/Kingdoms/
layout tiers (`SE3__T1.K4`/`K5`/`K6` present it; `SE3__T1.K1`/`K2`/`K3`/
`K7`/`K8`/`K9` and `SE3__T10.K2` don't; `SE3__T10.K1`/`K3`-`K7` present
it again), the real trigger turned out to be simple and exact, not
another unresolved contradiction like the layout-selection trigger
above: **the label (plus its own fixed 78-dash rule) appears exactly
when the map's own topmost rendered row sits at `y == 1`** -- the
world's own real northern edge, matching the label's own name. Every
labeled sample's first row shows province codes ending in `01`
(`Alderwood(0101)`, `Cretacia(0601)`, ...); every unlabeled sample's
first row starts at `y >= 2`. No other label text was ever found
preceding a 78-dash rule anywhere in this project's own ~90-sample
corpus -- "Ice cap" is the only real region label, not one member of an
unimplemented family. `map_region_label()` reuses the exact same
province set `render_ascii_map()` already iterates, so it always agrees
with what actually became this report's own topmost row.

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
- ~~Multiple maps ("far side of the world") -- only a single, continuous
  map is rendered. (The region label, "Ice cap", is implemented as of
  Phase 577 -- see that section above.)~~ -- **closed in Phase 624**
  (pagination itself, a pure print-width overflow trigger, 27/27 against
  every real sample with a second map) and **Phase 628** (per-Kingdom
  province visibility, the real gap Phase 624 found while building this).
  See those phases' own addenda below for the full derivation, including
  the two pieces Phase 624 deliberately left for later: the layout-tier
  *selection* trigger itself (Phase 627, shipped as an 82% best-effort
  approximation, not a discovered formula) and `paginate_known_columns()`'s
  own home-anchored windowing (a documented, user-approved interpretation,
  not fully provable without real per-turn discovery-order data).
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
  currently picks any of the 6 automatically -- all 4 narrower tiers
  this phase discovered (strides 12, 10, 9, 8) are now implemented
  (Phases 569/570/571/572, see below), closing the "how many layouts
  exist" question this phase opened, though not the selection-trigger
  one.
- `cell_pixel_column()` (and every sibling `*_cell_pixel_column()`)
  takes the `coord.x - x_min` offset modulo `board_width` (Phase 629)
  rather than letting it go negative or clamping at 0 -- defensive only
  in the sense that `x_min` is computed as the report's own true left
  edge (`_cylindrical_x_min()`), so no real province should ever fall
  outside `[0, board_width)` once offset this way; covers this
  project's own synthetic test fixtures more than any real,
  independently confirmed pixel position.
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
  stride-selection trigger (at the time). **Closed by Phase 629** -- see
  this docstring's own Phase 629 addendum below for the real
  explanation (the "extra stride" was cylindrical wraparound, not an
  unrelated per-report state).

**Phase 624 -- "far side of the world" pagination, solved.** The real
trigger for the dual map is a pure print-width overflow, not distance
or connectivity: `max_columns_per_page(cell_stride) = 78 //
cell_stride` (the same 78-char budget `MAP_REGION_LABEL_RULE` already
uses), verified 27/27 against every real `Desktop/PROGRAMMA AK/
SE3__T*.K*` sample with a second map. The board is confirmed
cylindrical (column 18 borders column 1 in that historical corpus,
matching `worldgen/place_map.py DEFAULT_WIDTH = 18` exactly) -- direct
visual proof, not inference: `SE3__T10.K1`'s own far-side map prints
columns 15-18 then 01-05 as one seamless row with its own "Ice cap"
header, no seam at the wrap. This also explains the earlier
"falsified" connected-components finding (module docstring's own
"Explicitly deferred" section below, kept for history): known,
ordinary hex-adjacent provinces (`SE3__T4.K6`'s x=17/x=18) can still
land on different pages, because the split is purely about which
page's own column budget they fall into, nothing about adjacency.
`paginate_known_columns()`'s own home-anchored windowing (which
*specific* columns land on page 1) is a documented, user-approved
interpretation checked against the 2 clean real cases found, not fully
provable without real per-turn discovery-order data this project
doesn't have -- see that function's own docstring. **Deliberately not
touched this phase**: the layout-tier *selection* trigger (`describe_
map_report()` still only ever calls the wide-tier renderer -- this
phase adds pagination within whichever tier is wired in, not tier
choice itself) and per-kingdom province visibility (`render_ascii_
map()` and its 5 siblings still render every province in `state.
provinces` unfiltered by kingdom knowledge, despite this function's own
docstring claiming an "any record of it" convention -- a real,
separate, pre-existing gap noticed while investigating this, deferred
rather than retrofitted into a large pre-existing test suite that
doesn't set `ProvinceState.explored_percent_by_kingdom` anywhere).

**Phase 627 -- the layout-tier selection trigger, a best-effort
approximation, not solved.** `select_layout_tier()` picks the least-
dense tier whose own `max_columns_per_page()` covers the Kingdom's
uncapped, home-anchored cylindrical column cluster -- **82% accurate
against the real corpus (81/99), the ceiling for what a single-
snapshot geometric analysis can achieve, not a discovered formula**.
Tracing individual Kingdoms turn-by-turn shows the real "main page"
region is a *historical* artifact -- it grows via real, ongoing
exploration (its own `Expl%` climbs well past the initial reveal, not
a flat one-time value) for a while, then stops for many turns even as
a *separate*, equally actively-explored "far side of the world"
region keeps growing right alongside it -- sometimes geometrically
*adjacent* to the primary region. A snapshot can measure geometry, not
history, so a purely geometric trigger can never fully separate "part
of the historically-primary region" from "happens to touch it now."
Several other candidates were tried and ruled out first: total known-
column count (fails for the same adjacency-conflation reason), widest
single print row (worse, ~65%), and per-province `Expl%` as a
"genuinely explored vs. merely revealed" discriminator (directly
refuted -- far-side provinces show real, substantial `Expl%` growth
too). Shipped anyway, at the user's own explicit request, as the best
available approximation -- see `select_layout_tier()`'s own docstring
for the full account.

**Phase 628 -- per-Kingdom province visibility, closed.** Every
renderer plus `map_region_label()` previously rendered *every* province
in `state.provinces`, unfiltered by what the requesting Kingdom
actually knows -- flagged as a real gap during Phase 624, left open
through Phase 627. `render_ascii_map()`'s own docstring additionally
claimed this reused `describe_provinces_report()`'s own "any record of
it" visibility convention; re-reading that report's own docstring
(quoting `REPORTS.PAS Rep_Provs` directly: `IF powner[px,py] = kng`)
shows it actually filters to provinces this Kingdom *owns* -- the
opposite claim, and one that can't be right for the map either way,
since this module's own byte-verified real samples show other
Kingdoms' provinces and `Unowned` provinces printing right alongside
this Kingdom's own. All 6 renderers and `map_region_label()` now take
an optional `visible_provinces: set[HexCoord] | None` parameter (same
`None`-means-unfiltered shape as the `columns` parameter Phase 624/627
already established); `describe_map_report()` computes the real set
via `ProvinceState.known_to_kingdom()` (Phase 623) and passes it
through, and also uses that same filtered set (not the raw unfiltered
`state.provinces`) to drive `select_layout_tier()`/`paginate_known_
columns()`, so tier selection and pagination reflect what will
actually be drawn, not merely what exists in `state`.

**Phase 629 -- the dense and stride-9 layouts' own "unexplained
margin," closed.** Phase 568 found `dense_cell_pixel_column()` needed a
full extra `DENSE_CELL_STRIDE` for `SE3__T4.K2`/`SE3__T5.K2` (`x_min ==
1`) but not for `SE3__T2.K1` (`x_min == 8`) -- two real reports that
directly contradicted each other under any single, non-relative
formula, left unresolved. Phase 571 found the same class of gap for
`stride9_cell_pixel_column()`, worse: `SE3__T4.K8`'s own true anchor
sat a full 2 strides left of its own visible minimum `x`.

Re-investigating directly against the real corpus (not guessed): both
"contradictions" are the exact same real mechanism Phase 624 already
confirmed for pagination -- **the board is cylindrical, column 18
borders column 1** -- just never applied to horizontal *placement*
before. `SE3__T4.K2`/`SE3__T5.K2` both have a real known province,
`Apurimac`, at `x == 18`, cylindrically adjacent to their own `x == 1`
cluster; `SE3__T4.K8` has TWO, at `x == 17` and `x == 18`, exactly 2
strides left of its own `x == 1` cluster. Once `x_min` is computed as
the *true* left edge of the report's own cylindrically-contiguous
column run (`_cylindrical_x_min()`, reusing `_contiguous_run_through()`
from Phase 624) rather than the raw numeric minimum, and the pixel
offset taken modulo `board_width` instead of assumed non-wrapping, all
3 previously-contradicting real reports match one uniform formula with
zero residual -- verified directly, character-column by character-
column, against every real band in `SE3__T2.K1`, `SE3__T4.K2`,
`SE3__T5.K2`, and `SE3__T4.K8` (not just the previously-checked
samples). `dense_cell_pixel_column()` gained the `x_min` parameter it
never had (Phase 568 left it hardcoded to an assumed `0`, the very gap
that hid this bug); every `*_cell_pixel_column()` function now shares
one identical formula shape, `((coord.x - x_min) % board_width) *
CELL_STRIDE + stagger`. `Apurimac`'s own "renders immediately adjacent
with no gap, not modeled" note (this docstring's own Phase 566 section)
is also now explained, not just tolerated: it isn't a distant landmass
packed in ad hoc -- it's an ordinary cylindrical neighbor of `x == 1`,
rendering exactly where any neighboring column would.

**Phase 871 -- every renderer's own `board_width` now threads through
from the real `GameState.board_width`, closing a real, previously-
shipped bug.** `DEFAULT_WIDTH` (18, `worldgen/place_map.py`'s own
"normale" board default) was hardcoded as the cylindrical-wraparound
width in all 6 renderers, `_cylindrical_x_min()`, and every real call
site in `report/turn_report.py describe_map_report()` -- with no path
anywhere to override it. But `models/game_state.py GameState.board_
width` defaults to **30**, the Super-AK size (Phase 780's own board-
size fix: `NORMAL_MAP_BOUNDS(30,15)` is real Super-AK, not "normale",
and `GameState` tracks its own real board size as the source of
truth). Every one of this module's own 6 renderers now takes an
explicit `board_width` parameter (default `DEFAULT_WIDTH`, preserving
every existing caller/test that never passes one), and `describe_map_
report()` passes the real `state.board_width` through to them, to
`select_layout_tier()`, and to `paginate_known_columns()`. Confirmed
this was live, not theoretical: `tests/test_turn_report.py`'s own
`test_describe_map_report_splits_into_a_far_side_page_when_too_wide`
deliberately places provinces at columns 14-18 and 1-4 to exercise
wraparound at column 18 -- passing only because its own `GameState`
(board_width defaulting to 30, never overridden) and the pre-fix code
shared the identical wrong 18-wide assumption, not because either was
actually correct for the board it claimed to describe.

**Phase 2027 -- the Expl% field itself, closed.** Phase 628 (above)
closed *which* provinces a Kingdom's own map shows, but every cell's
own Expl% text still read the plain, kingdom-neutral `ProvinceState.
explored_percent` scalar -- the one `models/game_state.py`'s own
Phase 69 docstring addendum explicitly calls out as *not* what "how
much has this Kingdom explored it" means (that's `explored_percent_
by_kingdom`). `turn/move_execution.py reveal_adjacent_provinces()`
(Phase 623) only ever writes the per-kingdom dict for a newly-known
neighbor, at the `KNOWN_PROVINCE_MIN_PERCENT` (1%) floor -- it
deliberately never bumps the shared scalar, which stays at whatever
a real Explore order last left it (commonly still 0 for a province
nobody has physically explored yet). Reading the shared scalar alone
therefore prints "0% Expl." for exactly the cells the real corpus
(`tests/fixtures/reports/G3/`, `/G6/`) never shows that way -- a
province known at all is *always* "1% Expl." or higher in every one
of the 100+ real samples checked, never "0% Expl." (the user's own
report correction, cross-checked against real turns from the
Pascal-era program). All 7 `expl_text` call sites across the 4
renderers that still show Expl% (stride9/stride8 never did, Phase
571/572) now read `max(explored_percent, explored_percent_by_
kingdom.get(viewing_kingdom_id, 0))` instead -- purely additive for
every existing real-sample test (none of them set the per-kingdom
dict, so the `max()` is a no-op there), while finally giving a
Kingdom's own correctly-100%-seeded home province (`webapp/kingdom_
create.py`) and any 1%-floor-known neighbor their own real reading.
"""

from __future__ import annotations

from collections.abc import Callable

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain, province_code
from ak_engine.models.race import HUMANOID_RACES, RACE_NAME, RACE_PLURAL_NAME, Race
from ak_engine.worldgen.place_map import DEFAULT_WIDTH

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

# Phase 570: the fourth, still-denser layout (see module docstring's own
# Phase 570 section) -- narrow enough that its own name+id combination
# is confirmed to ALWAYS wrap onto a second row in the real corpus (not
# an occasional long-name edge case the way it is for every wider tier),
# so this phase reproduces that real split (`render_cell_stride10()`'s
# own dedicated name-only row 1 / id-only row 2) instead of extending
# the truncate-to-fit policy to a case this universal. Truncation still
# applies to the name ALONE (no id budget needed, since the id always
# gets its own row here) -- `STRIDE10_MAX_PROVINCE_NAME_LENGTH` is set
# to the full cell width, `STRIDE10_PROVINCE_NAME_TRUNCATION_TRIGGER`
# one past it, matching `Waterford Sea`-style overlong single-cell names
# that would otherwise need a THIRD row for the name alone -- not
# independently confirmed against a real "must stay whole" boundary at
# this width (no such sample exists), same honesty gap already accepted
# for the wide layout's own analogous case before the user resolved it.
STRIDE10_CELL_WIDTH = 9
STRIDE10_CELL_STRIDE = STRIDE10_CELL_WIDTH + 1
STRIDE10_MAX_PROVINCE_NAME_LENGTH = STRIDE10_CELL_WIDTH
STRIDE10_PROVINCE_NAME_TRUNCATION_TRIGGER = STRIDE10_MAX_PROVINCE_NAME_LENGTH + 1

# Phase 571: the fifth, still-denser layout (see module docstring's own
# Phase 571 section) -- name/id always split, same real behavior as
# stride 10, just narrower still; same truncation approach for the same
# reason.
STRIDE9_CELL_WIDTH = 8
STRIDE9_CELL_STRIDE = STRIDE9_CELL_WIDTH + 1
STRIDE9_MAX_PROVINCE_NAME_LENGTH = STRIDE9_CELL_WIDTH
STRIDE9_PROVINCE_NAME_TRUNCATION_TRIGGER = STRIDE9_MAX_PROVINCE_NAME_LENGTH + 1

# Phase 572: the sixth and narrowest layout Phase 567's own survey
# found (a genuine floor -- no Kingdom's own map ever narrows past this
# even at 100+ known provinces, see module docstring's own Phase 567
# section) -- same name/id split as strides 10/9, same truncation
# approach.
STRIDE8_CELL_WIDTH = 7
STRIDE8_CELL_STRIDE = STRIDE8_CELL_WIDTH + 1
STRIDE8_MAX_PROVINCE_NAME_LENGTH = STRIDE8_CELL_WIDTH
STRIDE8_PROVINCE_NAME_TRUNCATION_TRIGGER = STRIDE8_MAX_PROVINCE_NAME_LENGTH + 1

class _TerrainSymbolTable(dict):
    """Falls back to ``"?"`` for a terrain with no real symbol, instead
    of raising ``KeyError`` on ``[...]``.

    Bug fix (defense-in-depth): ``Terrain.NO_TERRAIN`` is documented
    just below as never appearing on a real map cell, so this gap is
    not known to be reachable today -- but every renderer in this file
    indexes this dict unconditionally with no guard, and the same class
    of bug (a deliberately incomplete enum-keyed table read with a bare
    ``[...]``) was confirmed reachable via GM edit for several sibling
    tables elsewhere this session. "?" is an honest "unknown terrain"
    placeholder, not a guessed real symbol.
    """

    def __missing__(self, key):
        return "?"


# `_` Plains, `+` Forest, `&` Jungle, `^` Mountain, `.` Desert, `~` Sea --
# see this module's own docstring for the full sourcing. `NO_TERRAIN`
# never appears on a real map cell.
TERRAIN_SYMBOL: dict[Terrain, str] = _TerrainSymbolTable({
    Terrain.PLAINS: "_",
    Terrain.FOREST: "+",
    Terrain.JUNGLE: "&",
    Terrain.MTNS: "^",
    Terrain.DESERT: ".",
    Terrain.SEA: "~",
})

# Confirmed directly against real map cells this phase (see module
# docstring): single-word Army Types abbreviate to their own first two
# letters, title-cased; two-word ones to both words' own initials,
# capitalized. Only the 10 types this session's own samples actually
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
    # Phase 571: confirmed via SE3__T4.K8's own real Katanga cell
    # ("Le,El") -- follows the same single-word "first two letters,
    # title-cased" rule as the other 9, not just the raw `.value` ("EL").
    ArmyType.ELEPHANTS: "El",
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
    # Bug fix: for a race with no entry in RACE_NAME (Drow/Lizardman/
    # Goblin), RACE_NAME now falls back to a title-cased identifier
    # rather than crashing (see that dict's own fix), but "+s"-ing that
    # fallback would read oddly ("Lizardmans"). models/race.py's own
    # RACE_PLURAL_NAME is already complete and sourced for all 18 real
    # races, including these 3 ("Drow Elves"/"Lizardmen"/"Goblins") --
    # prefer it outright over this function's own override+"s" guess.
    if race in RACE_PLURAL_NAME:
        return RACE_PLURAL_NAME[race]
    return _RACE_NAME_PLURAL_OVERRIDE.get(race, f"{RACE_NAME[race]}s")


def _cylindrical_x_min(columns: set[int], board_width: int) -> int:
    """The report's own true left edge for pixel-column placement --
    **not** simply `min(columns)`, but the start of the cylindrically-
    contiguous run (`_contiguous_run_through()`, Phase 624) containing
    that naive minimum. Phase 629 finding: a province bordering the
    naive minimum from the *other* side of the wrap (column
    `board_width` borders column 1, confirmed Phase 624) renders to its
    own visual *left*, not off at some huge, unrelated `x` -- this is
    the real cause of the "unexplained margin" Phase 568/571 found and
    left open for the dense and stride-9 layouts (see module docstring
    for the full, real-corpus-verified account). Reduces to plain
    `min(columns)` whenever no such wrap-adjacent member exists, which
    is every already-verified non-wrapping real sample (wide/stride12/
    stride10/stride8's own byte-verified reports never included one).
    """

    naive_min = min(columns)
    return _contiguous_run_through(naive_min, columns, board_width)[0]


def cell_pixel_column(coord: HexCoord, x_min: int, board_width: int = DEFAULT_WIDTH) -> int:
    """The real horizontal pixel column a province's own cell starts at,
    relative to `x_min` -- the report's own true left edge (see
    `_cylindrical_x_min()`), not necessarily the raw numeric minimum
    (see module docstring's own Phase 568 note on why this is relative
    at all, not the fixed `x - 1` this phase-562 formula originally
    hardcoded). Even-`y` rows are staggered right by half a cell width
    relative to odd-`y` rows -- the same real hex offset `turn/
    movement.py neighbors()` already uses (`coord.y % 2`), just
    expressed here in pixel columns instead of neighbor deltas.

    Confirmed against 4 independent bands within a single report
    (`SE3__T1.K2`, `x_min=1`) at Phase 562, and re-confirmed this phase
    against `SE3__T1.K1` -- the *same real provinces*, same Kingdom,
    different turn, `x_min=9` there instead of 1 -- with zero
    contradictions once the formula is expressed relative to `x_min`
    rather than a hardcoded `1`. **Phase 629**: the offset is now
    computed modulo `board_width` (cylindrical), not floored at 0 --
    this layout's own real corpus never needed it (no verified sample
    wraps), but it keeps the formula uniform with the other 5 tiers,
    all of which share this exact function shape.
    """

    stagger = CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return ((coord.x - x_min) % board_width) * CELL_STRIDE + stagger


def dense_cell_pixel_column(coord: HexCoord, x_min: int, board_width: int = DEFAULT_WIDTH) -> int:
    """The dense layout's own horizontal pixel column -- see module
    docstring's own Phase 629 addendum. **Closes the real contradiction
    Phase 568 found and left open**: `SE3__T2.K1`'s own real map
    (`x_min == 8`, no wrap-adjacent province anywhere nearby) matches a
    plain `(x - x_min) * DENSE_CELL_STRIDE`, while `SE3__T4.K2`/
    `SE3__T5.K2` (`x_min == 1`) appeared to need a full extra stride --
    that "extra stride" is explained exactly by `Apurimac(1806)`, a
    real known province at `x == 18`, cylindrically adjacent to `x ==
    1` (column 18 borders column 1, confirmed Phase 624). Once `x_min`
    is computed via `_cylindrical_x_min()` (which finds Apurimac as the
    *true* left edge of the report's own contiguous run, not `1`) and
    the offset taken modulo `board_width`, both reports match the exact
    same formula with zero residual -- verified against every real band
    in both reports, not just the previously-checked ones. Now takes an
    explicit `x_min` (previously always assumed `0`, the very
    assumption that hid this bug -- see module docstring for the full,
    corrected account).
    """

    stagger = DENSE_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return ((coord.x - x_min) % board_width) * DENSE_CELL_STRIDE + stagger


def stride12_cell_pixel_column(coord: HexCoord, x_min: int, board_width: int = DEFAULT_WIDTH) -> int:
    """The stride-12 layout's own horizontal pixel column -- see module
    docstring's own Phase 569 section. Confirmed against every one of
    `SE3__T3.K1`'s own 5 real bands (`x_min = 8`, the true minimum
    across the whole report, not just the row being placed): a plain
    `(x - x_min) * STRIDE12_CELL_STRIDE + stagger`, zero residual --
    the same clean, `x_min`-relative shape `cell_pixel_column()` uses
    for the wide layout. **Phase 629**: offset now taken modulo
    `board_width`, matching every sibling tier -- this report's own
    corpus never wraps, so the result is unchanged.
    """

    stagger = STRIDE12_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return ((coord.x - x_min) % board_width) * STRIDE12_CELL_STRIDE + stagger


def stride10_cell_pixel_column(coord: HexCoord, x_min: int, board_width: int = DEFAULT_WIDTH) -> int:
    """The stride-10 layout's own horizontal pixel column -- see module
    docstring's own Phase 570 section. Confirmed against every one of
    `SE3__T4.K3`'s own 6 real bands (`x_min = 4`, the true minimum
    across the whole report): the same clean, `x_min`-relative shape as
    the wide and stride-12 layouts, zero residual. **Phase 629**:
    offset now taken modulo `board_width`, matching every sibling tier
    -- this report's own corpus never wraps, so the result is unchanged.
    """

    stagger = STRIDE10_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return ((coord.x - x_min) % board_width) * STRIDE10_CELL_STRIDE + stagger


def stride9_cell_pixel_column(coord: HexCoord, x_min: int, board_width: int = DEFAULT_WIDTH) -> int:
    """The stride-9 layout's own horizontal pixel column -- see module
    docstring's own Phase 571 section. Uses the same clean `x_min`-
    relative shape as the wide, stride-12, and stride-10 layouts,
    confirmed via `SE3__T4.K8`'s own real bands (~25 independent
    `(x, y)` data points, zero variance once the report's own true
    anchor is used). **Phase 629 closes the "2 strides left of the
    visible minimum" mystery Phase 571 left open**: `SE3__T4.K8`'s own
    real map has TWO known provinces at `x == 17` and `x == 18`,
    cylindrically adjacent to its own `x == 1` cluster (column 18
    borders column 1, confirmed Phase 624) -- `_cylindrical_x_min()`
    finds `x == 17` as the report's own true left edge (exactly 2
    strides left of the naive visible minimum, `x == 1`), and the
    modular offset then matches every real band with zero residual,
    including the wrap-adjacent provinces themselves.
    """

    stagger = STRIDE9_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return ((coord.x - x_min) % board_width) * STRIDE9_CELL_STRIDE + stagger


def stride8_cell_pixel_column(coord: HexCoord, x_min: int, board_width: int = DEFAULT_WIDTH) -> int:
    """The stride-8 layout's own horizontal pixel column -- see module
    docstring's own Phase 572 section. Confirmed against every one of
    `SE3__T5.K1`'s own 7 real bands (~50 independent `(x, y)` data
    points, zero variance): the clean, `x_min`-relative shape, with
    `x_min` genuinely equal to the report's own visible minimum `x`
    here -- unlike the dense and stride-9 layouts, this one needed no
    unexplained margin correction. **Phase 629**: offset now taken
    modulo `board_width`, matching every sibling tier -- this report's
    own corpus never wraps, so the result is unchanged.
    """

    stagger = STRIDE8_CELL_STRIDE // 2 if coord.y % 2 == 0 else 0
    return ((coord.x - x_min) % board_width) * STRIDE8_CELL_STRIDE + stagger


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

# Confirmed stride-10-layout tick columns (see module docstring's own
# Phase 570 section), derived from the REAL report's own physical rows
# 2 (id, always present at this width -- see the truncation-constants
# comment above), 3 (ruler), 4 (race), 5 (recruit) -- `render_cell_
# stride10()` re-maps these onto its own simplified row numbering
# (ruler/race/recruit/status each get a genuine framed slot instead of
# reproducing the real cascade's own row-6 merge-or-drop compression,
# since this phase already diverges from the real id-wrap-adjacent
# compression by choice, not by omission). Row 2's own tick columns
# (`{0, 8}`, the id's own framing) and the ruler/recruit rows' own
# (also `{0, 8}`, confirmed via `Kilkenny`'s real "Le" -- 2 characters,
# independently uncovering columns 1, 2, 3, 6, 7 as plain space, no
# embedded tick anywhere) all match; only the race row has an embedded
# tick, `{0, 2, 8}` (confirmed via `Daedalus`'s real "Orcs", column 2
# uncovered and showing the tick, plus columns 1 and 7 confirmed plain
# space). The 4th framed slot (status, only used when recruit is NOT
# skipped) reuses the border-only set by pattern consistency with the
# other 2 border-only slots -- not independently confirmed by a real
# framed (non-merged) example, since the real corpus never frames a
# 4-field cell's own status word (it always merges it into row 6
# instead, the specific real behavior this phase's own row budget no
# longer reproduces).
_STRIDE10_BORDER_TICKS = frozenset({0, 8})
_STRIDE10_ROW4_TICKS = frozenset({0, 2, 8})

# Confirmed stride-9-layout tick columns (see module docstring's own
# Phase 571 section), derived from `SE3__T4.K8`'s own real physical
# rows 3 (ruler), 4 (race), 5 (recruit-or-shifted-status). At this
# width the real corpus never frames a 4th middle field at all (unlike
# stride 10's own row-6 merge) -- a 4th field, when present, is simply
# dropped, and only 3 framed slots exist in total (see `render_cell_
# stride9()`'s own docstring). Row 3's own tick columns were never
# independently confirmed beyond the universal border (every real
# ruler name sampled happened to be exactly 8 characters, filling the
# whole cell) -- left at border-only, not assumed richer. Row 4's own
# are `{0, 6, 7}` (confirmed via `Moongard`'s real race "Orcs", column
# 6 uncovered and showing the tick, column 1 confirmed plain space).
# Row 5's own are unusually tick-heavy for this project, `{0, 1, 2, 5,
# 6, 7}` -- leaving only 2 real columns of flexible zone -- confirmed
# directly via `Balmwood`'s own real recruit "Bo" (2 characters,
# independently uncovering all 6 of those columns as ticks, none as
# plain space), corroborated by `Shasta`'s own real shifted status
# "Poor" showing the same tick pattern at columns 1 and 6.
_STRIDE9_BORDER_TICKS = frozenset({0, 7})
_STRIDE9_ROW4_TICKS = frozenset({0, 6, 7})
_STRIDE9_ROW5_TICKS = frozenset({0, 1, 2, 5, 6, 7})

# Confirmed stride-8-layout tick columns (see module docstring's own
# Phase 572 section), derived from `SE3__T5.K1`'s own real physical
# rows 3 (ruler) and 4 (race) -- this floor tier's own real cells never
# show recruit, status, or Expl% at all (see `render_cell_stride8()`'s
# own docstring), so there is no row 5 or 6 to derive a template for.
# Row 3's own tick columns were never independently confirmed beyond
# the universal border (every real ruler name sampled was either
# exactly 7 characters, filling the cell, or long enough to flush past
# it) -- left at border-only. Row 4's own are `{0, 1, 6}` (confirmed
# via both `Peachwood`'s real race "Ents" and `Limerick`'s real "Orcs",
# independently showing the same embedded tick at column 1).
_STRIDE8_BORDER_TICKS = frozenset({0, 6})
_STRIDE8_ROW4_TICKS = frozenset({0, 1, 6})


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

    expl_percent = max(province.explored_percent, province.explored_percent_by_kingdom.get(viewing_kingdom_id, 0))

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
        expl_text = f"{expl_percent}%{symbol}Expl."
        last_line = _pad_center(expl_text, CELL_WIDTH, symbol)
    else:
        # A field was skipped -- Expl% gets its own row (the next
        # unused template slot), and the border row stays pure,
        # matching `Shasta`'s own real cell (`SE3__T1.K2`) exactly. As
        # an ordinary framed inner row now (not merged into the
        # border), it keeps its own real space, like every other inner
        # row's internal word gaps.
        expl_text = f"{expl_percent}% Expl."
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

    expl_percent = max(province.explored_percent, province.explored_percent_by_kingdom.get(viewing_kingdom_id, 0))

    middle_fields = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)
    middle_lines = [
        _pad_overlay(text, tick_columns=ticks, symbol=symbol)
        for text, ticks in zip(middle_fields, _DENSE_ROW_TEMPLATES)
    ]

    if len(middle_lines) == len(_DENSE_ROW_TEMPLATES):
        expl_text = f"{expl_percent}%{symbol}Expl."
        last_line = _pad_center(expl_text, DENSE_CELL_WIDTH, symbol)
    else:
        expl_text = f"{expl_percent}% Expl."
        ticks = _DENSE_ROW_TEMPLATES[len(middle_lines)]
        middle_lines.append(_pad_overlay(expl_text, tick_columns=ticks, symbol=symbol))
        last_line = symbol * DENSE_CELL_WIDTH

    return [line1, *middle_lines, last_line]


# -- Phase 624: "far side of the world" pagination -- `Desktop/PROGRAMMA
# AK/SE3__T*.K*`'s own real second map (27 real samples cross-checked,
# zero exceptions), see this module's own Phase 624 addendum in the
# module docstring for the full derivation.

# The same 78-char page-width budget `MAP_REGION_LABEL_RULE`'s own
# 78-dash rule (Phase 577) already established -- confirmed to also be
# the real cap on how many province columns fit on one map page.
PAGE_WIDTH = 78


def max_columns_per_page(cell_stride: int) -> int:
    """How many province columns fit on one printed map page at a given
    tier's own real `CELL_STRIDE` -- `PAGE_WIDTH // cell_stride`.
    Verified 27/27 against real samples for all 6 of this module's own
    tiers (wide/dense/stride12/10/9/8 -> 4/5/6/7/8/9 columns) -- see
    module docstring's own Phase 624 addendum.
    """

    return PAGE_WIDTH // cell_stride


def _cylindrical_distance(a: int, b: int, board_width: int) -> int:
    """The shorter of the two directions around the wrap between columns
    `a` and `b` on a `board_width`-wide cylindrical board (column
    `board_width` borders column 1 -- confirmed real, see module
    docstring's own Phase 624 addendum).
    """

    diff = abs(a - b) % board_width
    return min(diff, board_width - diff)


def _contiguous_run_through(anchor: int, known_columns: set[int], board_width: int) -> list[int]:
    """The maximal cylindrically-contiguous run of `known_columns`
    containing `anchor` -- walks outward from `anchor` in both
    directions while the next column (wrapping at `board_width`) is
    still in `known_columns`. Returns the run in ascending walk order
    starting from its own lower end (not necessarily `anchor` itself).
    """

    def _wrap(x: int) -> int:
        return ((x - 1) % board_width) + 1

    ordered = [anchor]
    cursor = anchor
    while True:
        candidate = _wrap(cursor + 1)
        if candidate in known_columns and candidate not in ordered:
            cursor = candidate
            ordered.append(cursor)
        else:
            break
    cursor = anchor
    while True:
        candidate = _wrap(cursor - 1)
        if candidate in known_columns and candidate not in ordered:
            cursor = candidate
            ordered.insert(0, cursor)
        else:
            break
    return ordered


def paginate_known_columns(
    known_columns: set[int], home_x: int, max_cols: int, board_width: int = DEFAULT_WIDTH
) -> list[list[int]]:
    """Splits `known_columns` into pages of at most `max_cols` columns
    each, matching the real "far side of the world" second (and
    further) map -- see module docstring's own Phase 624 addendum for
    the full sourcing and the two real corpus cases this was checked
    against.

    Page 1 anchors on whichever known column is closest to `home_x`
    (`KingdomState.home_province.x` -- falls back cleanly if `home_x`
    itself isn't known, e.g. no record of the Kingdom's own home in
    this `GameState`). Each later page anchors on the smallest not-yet-
    placed column -- arbitrary but deterministic; no real 3-page sample
    exists in the corpus to confirm this tie-break against, unlike page
    1's own home-anchored rule (checked against 2 real cases, zero
    exceptions). When a page's own run is longer than `max_cols`, only
    the `max_cols` columns closest to that page's own anchor (by
    run-order cylindrical distance, ties toward the smaller column) are
    kept -- the rest stay unplaced for a later page.
    """

    remaining = set(known_columns)
    pages: list[list[int]] = []
    first_page = True
    while remaining:
        if first_page:
            anchor = min(remaining, key=lambda c: (_cylindrical_distance(c, home_x, board_width), c))
        else:
            anchor = min(remaining)
        run = _contiguous_run_through(anchor, remaining, board_width)
        if len(run) > max_cols:
            run = sorted(run, key=lambda c: (_cylindrical_distance(c, anchor, board_width), c))[:max_cols]
        pages.append(sorted(run))
        remaining -= set(run)
        first_page = False
    return pages


def render_ascii_map(
    state: GameState,
    kingdom_id: int,
    *,
    columns: set[int] | None = None,
    visible_provinces: set[HexCoord] | None = None,
    board_width: int = DEFAULT_WIDTH,
) -> list[str]:
    """Renders every province this Kingdom's own report shows on the map --
    see module docstring for the exact scope this phase covers (a single,
    continuous map; no name-wrap; "Unowned" always shown, never skipped).

    `columns` (Phase 624, default `None`): when given, only provinces
    whose `coord.x` is in this set are rendered -- one page of a multi-
    page "far side of the world" report (`describe_map_report()`'s own
    Phase 624 addendum). `None` renders everything, exactly this
    function's own pre-Phase-624 behavior.

    `visible_provinces` (Phase 628, default `None`): when given, only
    provinces whose `coord` is in this set are rendered -- the real
    per-Kingdom knowledge filter (`ProvinceState.known_to_kingdom()`,
    Phase 623), independent of `columns` (a known column can still
    contain a province at some `y` this Kingdom doesn't know about).
    `None` renders every province in `state.provinces` unfiltered by
    knowledge, exactly this function's own pre-Phase-628 behavior --
    this function's own earlier docstring claimed that was already
    "`describe_provinces_report()`'s own visibility convention," which
    turned out to be wrong once re-checked: that report filters to
    provinces this Kingdom *owns* (`REPORTS.PAS Rep_Provs`'s own
    `IF powner[px,py] = kng`), not "any record of it" -- and an
    ownership filter can't be right for the map either way, since this
    module's own byte-verified real samples show other Kingdoms'
    provinces and `Unowned` provinces printing right alongside this
    Kingdom's own. `describe_map_report()` is the real production
    caller and passes the real `known_to_kingdom()`-derived set here.

    `board_width` (Phase 871, default `DEFAULT_WIDTH`): the real
    cylindrical wraparound width -- see module docstring's own Phase
    871 addendum for why this must be `GameState.board_width`, not the
    "normale" 18-wide default, for any Super-AK (30-wide) game.
    """

    provinces = list(state.provinces.values())
    if columns is not None:
        provinces = [p for p in provinces if p.coord.x in columns]
    if visible_provinces is not None:
        provinces = [p for p in provinces if p.coord in visible_provinces]
    if not provinces:
        return []

    x_min = _cylindrical_x_min({p.coord.x for p in provinces}, board_width)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: (p.coord.x - x_min) % board_width)
        cells = [render_cell(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [cell_pixel_column(p.coord, x_min, board_width) for p in row_provinces]

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


# Phase 577: the real "Ice cap" region label -- a plain text line plus a
# 78-dash rule, printed between the map's own intro sentence and the
# grid itself, confirmed byte-identical (both the text and the rule's
# own fixed 78-char width) across every real sample that shows it
# (`SE3__T1.K4`/`K5`/`K6`, `SE3__T4.K6`, `SE3__T10.K1`/`K3`-`K7`, and
# others). **The trigger, cross-checked against 10+ real samples with
# zero exceptions**: it appears exactly when the map's own topmost
# rendered row is y == 1 -- the world's own real northern edge (`y`
# never goes below 1 anywhere in this project's coordinate system).
# Every sample whose topmost known province has y >= 2 shows no label
# at all, direct continuation of the map (`SE3__T1.K1`/`K2`/`K3`/`K7`/
# `K8`/`K9`, `SE3__T10.K2`). No other label text was ever found
# preceding the 78-dash rule anywhere across the full ~90-sample corpus
# -- "Ice cap" is the only real region label, not one case of several.
MAP_REGION_LABEL_RULE = "-" * 78


def map_region_label(state: GameState, *, columns: set[int] | None = None, visible_provinces: set[HexCoord] | None = None) -> str | None:
    """Returns ``"Ice cap"`` when this report's own map (see
    ``render_ascii_map()``, whose province set this reuses exactly) has
    a topmost row at ``y == 1``, else ``None`` -- see the module-level
    comment above ``MAP_REGION_LABEL_RULE`` for the sourced derivation.

    `columns` (Phase 624, default `None`): same restriction as
    `render_ascii_map()`'s own `columns` parameter -- the Ice-cap check
    runs per page (confirmed real: a "far side of the world" page can
    carry its own independent "Ice cap" header, see module docstring's
    own Phase 624 addendum), not once for the whole known set.

    `visible_provinces` (Phase 628, default `None`): same per-Kingdom
    knowledge restriction as `render_ascii_map()`'s own parameter of the
    same name -- the topmost row this checks must be the topmost row
    this Kingdom will actually see rendered, not the topmost row that
    merely exists in `state.provinces`.
    """

    provinces = list(state.provinces.values())
    if columns is not None:
        provinces = [p for p in provinces if p.coord.x in columns]
    if visible_provinces is not None:
        provinces = [p for p in provinces if p.coord in visible_provinces]
    if not provinces:
        return None
    if min(p.coord.y for p in provinces) == 1:
        return "Ice cap"
    return None


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

    expl_percent = max(province.explored_percent, province.explored_percent_by_kingdom.get(viewing_kingdom_id, 0))

    middle_fields = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)
    middle_lines = [
        _pad_overlay(text, tick_columns=ticks, symbol=symbol, width=STRIDE12_CELL_WIDTH)
        for text, ticks in zip(middle_fields, _STRIDE12_ROW_TEMPLATES)
    ]

    if len(middle_lines) == len(_STRIDE12_ROW_TEMPLATES):
        expl_text = f"{expl_percent}%{symbol}Expl."
        last_line = _pad_center(expl_text, STRIDE12_CELL_WIDTH, symbol)
    else:
        expl_text = f"{expl_percent}% Expl."
        ticks = _STRIDE12_ROW_TEMPLATES[len(middle_lines)]
        middle_lines.append(_pad_overlay(expl_text, tick_columns=ticks, symbol=symbol, width=STRIDE12_CELL_WIDTH))
        last_line = symbol * STRIDE12_CELL_WIDTH

    return [line1, *middle_lines, last_line]


def render_ascii_map_stride12(
    state: GameState,
    kingdom_id: int,
    *,
    columns: set[int] | None = None,
    visible_provinces: set[HexCoord] | None = None,
    board_width: int = DEFAULT_WIDTH,
) -> list[str]:
    """The stride-12 layout's own analogue of `render_ascii_map()` -- see
    module docstring's own Phase 569 section. Wired into `describe_map_
    report()` since Phase 627 -- `report/ascii_map.py select_layout_
    tier()` picks which of the 6 real layouts a given report uses.

    `columns` (Phase 627): same as `render_ascii_map()`'s own parameter
    of the same name -- restricts rendering to one page's own columns.

    `visible_provinces` (Phase 628): same as `render_ascii_map()`'s own
    parameter of the same name -- the real per-Kingdom knowledge filter.

    `board_width` (Phase 871): same as `render_ascii_map()`'s own
    parameter of the same name -- the real cylindrical wraparound width.
    """

    provinces = list(state.provinces.values())
    if columns is not None:
        provinces = [p for p in provinces if p.coord.x in columns]
    if visible_provinces is not None:
        provinces = [p for p in provinces if p.coord in visible_provinces]
    if not provinces:
        return []

    x_min = _cylindrical_x_min({p.coord.x for p in provinces}, board_width)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: (p.coord.x - x_min) % board_width)
        cells = [render_cell_stride12(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [stride12_cell_pixel_column(p.coord, x_min, board_width) for p in row_provinces]

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


# The stride-10 layout's own 3 framed "middle" slots (ruler/race/
# recruit -- or ruler/race/status when recruit is skipped), in physical
# row order (see module docstring's own Phase 570 section). Unlike the
# wider layouts, only 3 slots are framed here, not 4 -- the 4th
# middle field (status, only present when recruit is shown) instead
# reuses the border-only set, same as the module docstring's own
# comment on `_STRIDE10_BORDER_TICKS` explains.
_STRIDE10_MIDDLE_TEMPLATES: list[frozenset[int]] = [
    _STRIDE10_BORDER_TICKS,
    _STRIDE10_ROW4_TICKS,
    _STRIDE10_BORDER_TICKS,
]


def render_cell_stride10(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The stride-10 layout's own 6 raw content lines (9 chars each, no
    separator) for one province's own map cell -- see module docstring's
    own Phase 570 section for the full, sourced derivation.

    Unlike the 3 wider layouts, name and id are never combined onto one
    row here: the real corpus confirms id is ALWAYS on its own row 2 at
    this width (row 1 holds the name alone), not just for occasional
    long names. `_middle_fields()`'s own up-to-4 fields (ruler, race,
    recruit, status) then fill rows 3-5 (3 framed slots) plus row 6 --
    a 4th field there uses row 6 as a full-fill merge (matching the
    real corpus's own `Starhaven`, whose real `Rich` status merges into
    row 6 with Expl% dropped entirely); with only 3 fields (recruit
    skipped), row 6 is free for Expl% to merge in as usual (matching
    the real corpus's own `Sixth Sea`).
    """

    symbol = TERRAIN_SYMBOL[province.effective_terrain()]

    raw_name = province.name or ""
    if len(raw_name) > STRIDE10_PROVINCE_NAME_TRUNCATION_TRIGGER:
        raw_name = raw_name[:STRIDE10_MAX_PROVINCE_NAME_LENGTH]
    name = raw_name.replace(" ", symbol)
    line1 = _pad_center(name, STRIDE10_CELL_WIDTH, symbol)

    id_text = f"({province_code(province.coord):04d})"
    line2 = _pad_overlay(id_text, tick_columns=_STRIDE10_BORDER_TICKS, symbol=symbol, width=STRIDE10_CELL_WIDTH)

    middle_fields = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)
    lines = [line1, line2]
    for text, ticks in zip(middle_fields, _STRIDE10_MIDDLE_TEMPLATES):
        lines.append(_pad_overlay(text, tick_columns=ticks, symbol=symbol, width=STRIDE10_CELL_WIDTH))

    if len(middle_fields) > len(_STRIDE10_MIDDLE_TEMPLATES):
        # 4th field present (recruit shown) -- it merges into row 6,
        # full-fill, and Expl% is dropped entirely (matches Starhaven).
        lines.append(_pad_center(middle_fields[-1], STRIDE10_CELL_WIDTH, symbol))
    else:
        # Only 3 fields -- row 6 is free for Expl% to merge in as usual.
        expl_percent = max(province.explored_percent, province.explored_percent_by_kingdom.get(viewing_kingdom_id, 0))
        expl_text = f"{expl_percent}%{symbol}Expl."
        lines.append(_pad_center(expl_text, STRIDE10_CELL_WIDTH, symbol))

    return lines


def render_ascii_map_stride10(
    state: GameState,
    kingdom_id: int,
    *,
    columns: set[int] | None = None,
    visible_provinces: set[HexCoord] | None = None,
    board_width: int = DEFAULT_WIDTH,
) -> list[str]:
    """The stride-10 layout's own analogue of `render_ascii_map()` -- see
    module docstring's own Phase 570 section. Wired into `describe_map_
    report()` since Phase 627 -- `report/ascii_map.py select_layout_
    tier()` picks which of the 6 real layouts a given report uses.

    `columns` (Phase 627): same as `render_ascii_map()`'s own parameter
    of the same name -- restricts rendering to one page's own columns.

    `visible_provinces` (Phase 628): same as `render_ascii_map()`'s own
    parameter of the same name -- the real per-Kingdom knowledge filter.

    `board_width` (Phase 871): same as `render_ascii_map()`'s own
    parameter of the same name -- the real cylindrical wraparound width.
    """

    provinces = list(state.provinces.values())
    if columns is not None:
        provinces = [p for p in provinces if p.coord.x in columns]
    if visible_provinces is not None:
        provinces = [p for p in provinces if p.coord in visible_provinces]
    if not provinces:
        return []

    x_min = _cylindrical_x_min({p.coord.x for p in provinces}, board_width)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: (p.coord.x - x_min) % board_width)
        cells = [render_cell_stride10(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [stride10_cell_pixel_column(p.coord, x_min, board_width) for p in row_provinces]

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


# The stride-9 layout's own 3 framed "middle" slots (ruler/race/
# recruit -- or ruler/race/status when recruit is skipped), in physical
# row order (see module docstring's own Phase 571 section). Unlike
# every wider layout, a 4th middle field (status, when recruit is
# shown) is not given a row at all here -- the real corpus confirms it
# is simply dropped, with no row-6-style merge to fall back on.
_STRIDE9_MIDDLE_TEMPLATES: list[frozenset[int]] = [
    _STRIDE9_BORDER_TICKS,
    _STRIDE9_ROW4_TICKS,
    _STRIDE9_ROW5_TICKS,
]


def render_cell_stride9(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The stride-9 layout's own 5 raw content lines (8 chars each, no
    separator) for one province's own map cell -- see module docstring's
    own Phase 571 section for the full, sourced derivation.

    Like the stride-10 layout, name and id are never combined onto one
    row (id is always on its own row 2 at this width). Unlike stride
    10, only the first 3 of `_middle_fields()`'s own up-to-4 fields
    (ruler, race, recruit-or-status) get a row at all -- a genuine 4th
    field (status, only present when recruit is shown) is dropped
    entirely, matching the real corpus's own `Katanga` (recruit shown,
    no status or Expl% anywhere in its own real cell) contrasted with
    `Shasta` (recruit skipped, race Eagles, status shown in recruit's
    own normal slot instead). Expl% is never shown at all in either of
    these two well-understood real cases.
    """

    symbol = TERRAIN_SYMBOL[province.effective_terrain()]

    raw_name = province.name or ""
    if len(raw_name) > STRIDE9_PROVINCE_NAME_TRUNCATION_TRIGGER:
        raw_name = raw_name[:STRIDE9_MAX_PROVINCE_NAME_LENGTH]
    name = raw_name.replace(" ", symbol)
    line1 = _pad_center(name, STRIDE9_CELL_WIDTH, symbol)

    id_text = f"({province_code(province.coord):04d})"
    line2 = _pad_overlay(id_text, tick_columns=_STRIDE9_BORDER_TICKS, symbol=symbol, width=STRIDE9_CELL_WIDTH)

    middle_fields = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)
    lines = [line1, line2]
    for text, ticks in zip(middle_fields, _STRIDE9_MIDDLE_TEMPLATES):
        lines.append(_pad_overlay(text, tick_columns=ticks, symbol=symbol, width=STRIDE9_CELL_WIDTH))

    return lines


def render_ascii_map_stride9(
    state: GameState,
    kingdom_id: int,
    *,
    columns: set[int] | None = None,
    visible_provinces: set[HexCoord] | None = None,
    board_width: int = DEFAULT_WIDTH,
) -> list[str]:
    """The stride-9 layout's own analogue of `render_ascii_map()` -- see
    module docstring's own Phase 571 section. Wired into `describe_map_
    report()` since Phase 627 -- `report/ascii_map.py select_layout_
    tier()` picks which of the 6 real layouts a given report uses.

    `columns` (Phase 627): same as `render_ascii_map()`'s own parameter
    of the same name -- restricts rendering to one page's own columns.

    `visible_provinces` (Phase 628): same as `render_ascii_map()`'s own
    parameter of the same name -- the real per-Kingdom knowledge filter.

    `board_width` (Phase 871): same as `render_ascii_map()`'s own
    parameter of the same name -- the real cylindrical wraparound width.
    """

    provinces = list(state.provinces.values())
    if columns is not None:
        provinces = [p for p in provinces if p.coord.x in columns]
    if visible_provinces is not None:
        provinces = [p for p in provinces if p.coord in visible_provinces]
    if not provinces:
        return []

    x_min = _cylindrical_x_min({p.coord.x for p in provinces}, board_width)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: (p.coord.x - x_min) % board_width)
        cells = [render_cell_stride9(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [stride9_cell_pixel_column(p.coord, x_min, board_width) for p in row_provinces]

        for band_row in range(5):
            line = ""
            for cell, column in zip(cells, columns):
                if column > len(line):
                    line += " " * (column - len(line))
                elif column < len(line):
                    continue
                line += cell[band_row]
            lines.append(line.rstrip())

    return lines


def render_cell_stride8(state: GameState, province: ProvinceState, *, viewing_kingdom_id: int) -> list[str]:
    """The stride-8 layout's own 4 raw content lines (7 chars each, no
    separator) for one province's own map cell -- see module docstring's
    own Phase 572 section for the full, sourced derivation.

    The floor tier: name and id are always split (same real behavior as
    strides 10 and 9), and only the ruler and race -- the first 2 of
    `_middle_fields()`'s own up-to-4 fields -- ever get a row at all.
    Recruit, status, and Expl% are never shown in any of this report's
    own well-understood real cells, regardless of race or ownership --
    confirmed via `Sherwood` (race Humans, a `HUMANOID_RACES` member,
    still shows no recruit row).
    """

    symbol = TERRAIN_SYMBOL[province.effective_terrain()]

    raw_name = province.name or ""
    if len(raw_name) > STRIDE8_PROVINCE_NAME_TRUNCATION_TRIGGER:
        raw_name = raw_name[:STRIDE8_MAX_PROVINCE_NAME_LENGTH]
    name = raw_name.replace(" ", symbol)
    line1 = _pad_center(name, STRIDE8_CELL_WIDTH, symbol)

    id_text = f"({province_code(province.coord):04d})"
    line2 = _pad_overlay(id_text, tick_columns=_STRIDE8_BORDER_TICKS, symbol=symbol, width=STRIDE8_CELL_WIDTH)

    ruler_text, race_text = _middle_fields(state, province, viewing_kingdom_id=viewing_kingdom_id)[:2]
    line3 = _pad_overlay(ruler_text, tick_columns=_STRIDE8_BORDER_TICKS, symbol=symbol, width=STRIDE8_CELL_WIDTH)
    line4 = _pad_overlay(race_text, tick_columns=_STRIDE8_ROW4_TICKS, symbol=symbol, width=STRIDE8_CELL_WIDTH)

    return [line1, line2, line3, line4]


def render_ascii_map_stride8(
    state: GameState,
    kingdom_id: int,
    *,
    columns: set[int] | None = None,
    visible_provinces: set[HexCoord] | None = None,
    board_width: int = DEFAULT_WIDTH,
) -> list[str]:
    """The stride-8 layout's own analogue of `render_ascii_map()` -- see
    module docstring's own Phase 572 section. Wired into `describe_map_
    report()` since Phase 627 -- `report/ascii_map.py select_layout_
    tier()` picks which of the 6 real layouts a given report uses.

    `columns` (Phase 627): same as `render_ascii_map()`'s own parameter
    of the same name -- restricts rendering to one page's own columns.

    `visible_provinces` (Phase 628): same as `render_ascii_map()`'s own
    parameter of the same name -- the real per-Kingdom knowledge filter.

    `board_width` (Phase 871): same as `render_ascii_map()`'s own
    parameter of the same name -- the real cylindrical wraparound width.
    """

    provinces = list(state.provinces.values())
    if columns is not None:
        provinces = [p for p in provinces if p.coord.x in columns]
    if visible_provinces is not None:
        provinces = [p for p in provinces if p.coord in visible_provinces]
    if not provinces:
        return []

    x_min = _cylindrical_x_min({p.coord.x for p in provinces}, board_width)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: (p.coord.x - x_min) % board_width)
        cells = [render_cell_stride8(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [stride8_cell_pixel_column(p.coord, x_min, board_width) for p in row_provinces]

        for band_row in range(4):
            line = ""
            for cell, column in zip(cells, columns):
                if column > len(line):
                    line += " " * (column - len(line))
                elif column < len(line):
                    continue
                line += cell[band_row]
            lines.append(line.rstrip())

    return lines


def render_ascii_map_dense(
    state: GameState,
    kingdom_id: int,
    *,
    columns: set[int] | None = None,
    visible_provinces: set[HexCoord] | None = None,
    board_width: int = DEFAULT_WIDTH,
) -> list[str]:
    """The dense layout's own analogue of `render_ascii_map()` -- see
    module docstring's own Phase 566 section. Wired into `describe_map_
    report()` since Phase 627 -- `report/ascii_map.py select_layout_
    tier()` picks which of the 6 real layouts a given report uses.

    `columns` (Phase 627): same as `render_ascii_map()`'s own parameter
    of the same name -- restricts rendering to one page's own columns.

    `visible_provinces` (Phase 628): same as `render_ascii_map()`'s own
    parameter of the same name -- the real per-Kingdom knowledge filter.

    `board_width` (Phase 871): same as `render_ascii_map()`'s own
    parameter of the same name -- the real cylindrical wraparound width.
    """

    provinces = list(state.provinces.values())
    if columns is not None:
        provinces = [p for p in provinces if p.coord.x in columns]
    if visible_provinces is not None:
        provinces = [p for p in provinces if p.coord in visible_provinces]
    if not provinces:
        return []

    x_min = _cylindrical_x_min({p.coord.x for p in provinces}, board_width)

    rows_by_y: dict[int, list[ProvinceState]] = {}
    for province in provinces:
        rows_by_y.setdefault(province.coord.y, []).append(province)

    lines: list[str] = []
    for y in sorted(rows_by_y):
        row_provinces = sorted(rows_by_y[y], key=lambda p: (p.coord.x - x_min) % board_width)
        cells = [render_cell_dense(state, p, viewing_kingdom_id=kingdom_id) for p in row_provinces]
        columns = [dense_cell_pixel_column(p.coord, x_min, board_width) for p in row_provinces]

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


# -- Phase 627: layout-tier selection trigger -- see module docstring's
# own Phase 627 addendum for the full sourcing. Phase 1038 closed most
# of the original 82% real-corpus-match gap (see `select_layout_tier()`'s
# own docstring) by having callers feed it the Kingdom's own tracked
# primary exploration-region columns when available, rather than every
# known column at once.

# Least-dense first (fewest columns/page, biggest cells) to most-dense
# last (the stride8 floor) -- both `select_layout_tier()` and
# `describe_map_report()` share this one registry, defined here (after
# every renderer above) since `render_ascii_map_dense` is defined last
# in this file despite being the *second*-least-dense tier.
LAYOUT_TIERS: tuple[tuple[int, Callable[..., list[str]]], ...] = (
    (CELL_STRIDE, render_ascii_map),
    (DENSE_CELL_STRIDE, render_ascii_map_dense),
    (STRIDE12_CELL_STRIDE, render_ascii_map_stride12),
    (STRIDE10_CELL_STRIDE, render_ascii_map_stride10),
    (STRIDE9_CELL_STRIDE, render_ascii_map_stride9),
    (STRIDE8_CELL_STRIDE, render_ascii_map_stride8),
)


def select_layout_tier(known_columns: set[int], home_x: int, board_width: int = DEFAULT_WIDTH) -> int:
    """Picks which of the 6 real layout tiers a report should use --
    returns that tier's own `CELL_STRIDE` (look it up in `_LAYOUT_
    TIERS` for the matching renderer).

    The tier is the least-dense one whose own `max_columns_per_page()`
    exactly accommodates `known_columns`' own *uncapped* home-anchored
    cylindrical column cluster -- computed by finding whichever known
    column is closest to `home_x` (`KingdomState.home_province.x`,
    same fallback as `paginate_known_columns()`'s own page-1 anchor
    when `home_x` itself isn't known) and taking `_contiguous_run_
    through()` from there, with **no** page-size cap. Falls back to
    the floor tier (`stride8`) when even that can't hold the whole
    cluster.

    **This formula is 100% accurate against the real corpus (54/54,
    `tests/fixtures/reports/G3`) once `known_columns` is the Kingdom's
    own real, historically-primary ("main") region alone -- Phase
    1038.** The formula itself was never the gap (originally labeled
    "82% accurate, not a solved formula" at Phase 627): the gap was in
    *what to pass as `known_columns`*. Directly tracing individual
    Kingdoms turn-by-turn shows the real "main page" region grows
    incrementally over many turns via real, ongoing exploration, then
    *stops* growing for a stretch of turns even while a *separate* "far
    side of the world" region keeps actively growing right alongside
    it -- including cases confirmed directly against raw report text
    (`SE3__T10.K8`, `SE3__T6.K6`) where that separate region is
    geometrically *adjacent* to the primary one with **zero gap** (the
    primary cluster ends at column 6 while the far region starts at
    column 7, cylindrically contiguous, yet the real report still
    treats them as two separate regions sharing one tier chosen from
    the primary region's size alone). Passing the *full* known-column
    set (merging both regions whenever they happen to touch) is what
    produced the original 82%/54/70-ish accuracy figures in earlier
    analysis passes -- this function's own formula, unchanged, scores
    54/54 once fed only the real primary region.

    That real primary-region membership is historical (*which* region
    was first established as primary, not *where* it currently sits on
    the map) and cannot be recovered from a single end-of-turn
    snapshot's geometry alone -- tried and ruled out: total known-
    column count, widest single print row, and per-province `Expl%` as
    a "genuinely explored vs. merely revealed" discriminator (refuted
    directly: far-side provinces show real, substantial `Expl%` growth
    too, not a flat one-time reveal). `KingdomState.map_primary_region_
    columns` (Phase 1038) instead tracks it incrementally, live, as the
    real game is played turn by turn -- see that field's own docstring
    and `record_newly_known_column()`. For any `GameState` bridged cold
    from an existing `GW`/`XK` snapshot (no live turn history to
    replay), that field stays empty and callers fall back to passing
    the full known-column set here, reproducing this function's
    original, still-honest ~82%-accurate approximation for exactly
    that case -- a genuine, acknowledged remaining limitation, not a
    bug: a cold snapshot has no way to know which columns were
    historically primary, because the project has no replay of the
    turns that led up to it.
    """

    if known_columns:
        anchor = min(known_columns, key=lambda c: (_cylindrical_distance(c, home_x, board_width), c))
    else:
        anchor = home_x
    cluster_size = len(_contiguous_run_through(anchor, known_columns, board_width))
    for cell_stride, _renderer in LAYOUT_TIERS:
        if cluster_size <= max_columns_per_page(cell_stride):
            return cell_stride
    return LAYOUT_TIERS[-1][0]
