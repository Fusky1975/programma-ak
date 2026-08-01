"""Parser for the original engine's "world file" format (e.g. ``GW3``,
``GW3__T1``).

**No surviving Pascal source declares this file's format** -- the same
"missing main program" situation as most of this project's other gaps
(`turn/movement.py`'s hex adjacency, `models/office.py`'s `Ofc_Pts`/`Rank`).
Unlike those, this format was recovered empirically (Phase 222), by
cross-referencing known real per-province values -- Tax, Race, Terrain --
quoted verbatim in a real King's own generated turn-report letter
(``SE3__T1.K2``'s "PROVINCES" section, e.g. Macondo: Tax 4, Orc, Jungle)
against the raw integers in the corresponding real world-file snapshot
(``GW3__T1``, the same game). This is the exact "real sourced evidence
substituting for a lost driver" precedent `report/turn_report.py
compose_letter_report()`'s own docstring already established for the
letter-report section order.

**Confirmed record shape**, one per province, four consecutive lines
(quoted verbatim from ``GW3__T1``, Macondo's own real record):

```
Macondo
4 2 0 3 0 6
 3 0  15 0
255
```

- Line 1: the province's own name (`ProvinceState.name`'s own `pname`
  source -- see that field's docstring in `models/game_state.py`).
- Line 2: six space-separated integers, `<tax> <terrain> 0 <race> 0 6`.
  `tax` is the real `ptax[px,py]` this project has needed since Phase 220
  (`report/turn_report.py describe_provinces_report()`'s own documented
  gap). `terrain` and `race` are the *exact* ordinal values this
  project's own `models/map.py Terrain` and `models/race.py Race` enums
  already use (confirmed across 20+ real records: Macondo `terrain=2`/
  Jungle, Transylvania `terrain=4`/Mountain, Kaluga `race=1`/Elf,
  Kerry `race=2`/Dwarf -- no new ordinal-mapping table is needed here,
  unlike e.g. `models/alignment.py`'s own `ALIGNMENT_ORDINAL`). The two
  literal `0`s and the trailing literal `6` are a fixed structural
  marker at this position in every one of the 162 confirmed records, not
  a data field -- do not confuse the trailing `6` with `Terrain.
  NO_TERRAIN`'s own ordinal value (unrelated, a different slot).
- Line 3: **the real `Mod_PAT(px,py,0)`/`Mod_PAT(px,py,1)` Recruiting
  Types pair, decoded, Phase 278** -- four space-separated integers,
  `<type1_ord> 0  <type2_ord> 0` (e.g. `3 0  15 0` for Macondo, `4 0  7 0`
  for the neighboring Orielle). The first and third integers are each a
  real `ArmyType` ordinal (or the `15` "no second type" sentinel, see
  `MOD_PAT_ORDINAL_TO_ARMY_TYPE` below); the second and fourth are always
  literal `0` in every one of 701 real cross-checked records (Phase 278's
  own recovery evidence), an unused/reserved slot, not a data field.
- Line 4: **the governing leader's own leader id**, or the sentinel
  `255` for an unowned province -- NOT directly a kingdom id, a real
  correction made after cross-checking against `SE3__T1.K2`'s own ASCII
  map legend (that letter's "Key" section prints each province as
  `"<Name>(<coord>)"` over `"<RulerName>(<RulerID>)"`): Transylvania's
  own real ruler is printed as `"Philo(70)"` -- Philo is a Hero, not a
  King, confirmed by his own leader id (70) being far outside the
  King-numbering range this project's own fixtures already use (Kings
  own low single-digit ids matching their kingdom id, e.g. `LeaderState(
  1, 1, "Aldric", ..., is_king=True)`). `GW3__T1`'s own Transylvania
  record trails `70`, matching Philo's id exactly -- not a kingdom id at
  all. For a province the King governs directly, this id happens to
  equal the kingdom id (the same "King's own leader_id == kingdom_id"
  convention already established project-wide), e.g. Mongu/Macondo are
  both governed by "Bradipo I(2)" in the letter and both trail `2` in
  `GW3__T1` once owned (Macondo trails `255` in this specific pre-turn-1
  snapshot -- see the note on snapshot timing below). Resolving a
  `governor_leader_id` to its true owning kingdom needs `GameState.
  leaders`/`LKing()`-equivalent lookup, not attempted by this parser.

**Recruiting Types (`Mod_PAT`), Phase 278.** `report/turn_report.py
describe_provinces_report()`'s own "Recruiting Types" columns (Type 1 /
Type 2) were confirmed absent as of Phase 220/275 for the same reason
`ptax` originally was: no surviving `.PAS` file declares `Mod_PAT`. That
audit only ever asked whether a *formula* survives (it doesn't) -- it
never re-checked whether the *data* was recoverable the same way `ptax`
itself was (Phase 222, this same file). It was: cross-referencing every
real "PROVINCES" table row across all 12 available `SE3__T*.K*` turns
(701 rows with a matching `GW3__T<n>` record, by province name) against
that turn's own `GW3__T<n>` file's line-3 tokens gives a **100% exact,
zero-conflict decode** for all 19 distinct ordinals actually observed:

```
 0  Garrison   (inferred by elimination -- see note below)
 1  Bowmen          8  Elephants        15  None (no 2nd type)
 2  Axemen          9  Camels           16  Mermen
 3  Phalanx        10  Wargs            17  Ents
 4  Legion         11  Dragons          18  Trolls
 5  Lt Cav         12  Eagles           19  Weres
 6  Hvy Cav        13  League (Whales)
 7  Chariots       14  Fleet
```

Ordinals 0-14 line up exactly, positionally, with this project's own
`models/army_type.py ArmyType` enum declaration order (`GARRISON`
through `FLEET`) -- but 16-19 (`MERMEN`/`ENTS`/`TROLLS`/`WEREBEASTS`) are
each **one higher** than this project's own enum ordinals for those same
four members (15/16/17/18). The real Pascal `ArmyType`-equivalent enum
therefore has one more member than this project's own model does,
sitting at ordinal 15 between `FLEET` and `MERMEN` -- confirmed
functionally (it always renders as "None," the real table's own way of
saying "no second recruit type here," e.g. every `Terrain.SEA`/
`Race.NO_RACE` record) even though its real Pascal *name* is unknown.
`MOD_PAT_ORDINAL_TO_ARMY_TYPE` below encodes this shift directly, not as
an "off by one" workaround, so callers never see raw ordinals.

**`0`/`Garrison` was never directly observed** in any of the 701
cross-checked rows -- inferred by elimination (it's the one ordinal in
the confirmed 0-14 run with no conflicting alternative) and because
Garrison, uniquely, is recruitable in *any* humanoid province regardless
of race (rulebook [3.4]/`turn/recruit.py is_army_type_compatible_with_
race()`), so a province-specific "which types recruit here" table
plausibly never needs to name it at all -- a plausible explanation, not
independently confirmed.

**Per-province, not a race/terrain formula.** The same `(race, terrain)`
pair maps to many different `(type1, type2)` combinations across the 701
rows (e.g. `Human`/`Forest` alone spans five different Type 2 values) --
confirming this, like `ptax`, is baked into the map at world-generation
time, not runtime-derivable, and must be read per-province the same way.

**A bonus discovery, not consumed by this parser**: the same map legend
prints each province's own real coordinate, `"<Name>(<XXYY>)"` -- e.g.
`"Macondo(0205)"` (x=02, y=05), `"Mongu(0305)"`, `"Transylvania(0206)"`.
Cross-referencing the letter's own row layout (Bam Yanga/Macondo/Mongu/
Moongard all share y=05, x=1..4 left to right) against `GW3__T1`'s own
on-disk record order (those exact 4 provinces appear consecutive,
followed immediately by the next row's Abu Matariq/Transylvania/Big Sky,
y=06) strongly suggests the world file's own record order is row-major
over (x, y) -- but this is only a promising lead, not independently
confirmed or implemented here (see "Known gaps" below).

**Known gaps, deliberately not attempted here**:
- **No coordinate field exists in a province's own 4-line record**, and
  while the row-major ordering lead above is promising, it isn't
  confirmed. This means `parse_gw_world()` returns records in the
  file's own on-disk order, not keyed by `HexCoord` -- bridging a
  `GWProvinceRecord` into `GameState.provinces` (a `dict[HexCoord,
  ProvinceState]`) is deferred to a future phase.
- Line 3's own two integers are unresolved (population? garrison
  strength? a resource id?) -- out of scope for this phase, which only
  needed `ptax`/terrain/race/`governor_leader_id`. **Resolved, Phase
  278** -- see the module's own "Recruiting Types" section below;
  this note is kept for its original historical context.
- `governor_leader_id` isn't resolved to an owning kingdom id here (see
  above) -- that needs a `GameState`-level leader/kingdom lookup this
  pure file parser deliberately doesn't perform.
- `GW3__T1` is a pre-turn-1 snapshot: some provinces the corresponding
  `SE3__T1.K*` letters show as already conquered/settled (e.g. Macondo,
  ruled by "Bradipo I(2)" per the letter) still read `255` (unowned)
  here -- plausible turn-1-processing timing, not independently
  confirmed against a still-earlier snapshot (none exists to check).
- This module only parses the province-record block. A `GW3` file also
  has substantial content before and after that block (kingdom headers,
  a differently-shaped record format after line ~2066 in the confirmed
  `GW3__T1` sample) that isn't touched here.

**Phase 316 addendum -- what's actually in the post-province-block
content, an initial research pass (not implemented, no new parser
code).** The content after the province-record block (`GW3__T1` lines
~2067-2415) splits into three sub-parts, separated by a 2-line marker
(`"0 255 0"` / `"35 99 0"`) and closed by a fixed-length `"255 0 0"` x 52
padding/terminator row:

- **128 rows, 9 space-separated integers each** (e.g. `"11 7 67 256 4
  51 1 0 2"`). **Tested and falsified**: this looked like a plausible
  Feature/Monster instance roster (`models/feature.py`'s own `fx`/`fy`/
  `ftype`/`fmonst`/`fn` shape) -- fields 1-2 are valid 0-indexed
  `HexCoord`s on the confirmed 18x9 board, and 230 is the right order of
  magnitude for `featrange`. Directly falsified against real ground
  truth: `SE3__T1.K2`'s own "ADVENTURE" section names 3 real feature
  instances with real `F#`s (Macondo's Monastery `F#114`/Genie;
  Mongu's Cave `F#2`/Swordsman and Crypt `F#17`/Gargoyle) -- **none of
  114, and no isolated 17, ever appears anywhere in `GW3__T1`**. Field 4
  (which looked like a sequential instance id, `256, 257, 258...`) is
  actually trivial: exactly `255 + row_number`, a file-position counter,
  not game data. Field 3's own distribution (64 distinct low values,
  0-25 and 29-66 skipping 26-28, each appearing exactly once, mixed with
  64 filler rows at value 67 or 68) doesn't correlate cleanly with
  coordinate or row order either. This 9-field block's real meaning is
  still unknown; the Feature/Monster-roster hypothesis is ruled out, not
  just unconfirmed.
- **218 rows, 10 space-separated integers each** (e.g. `"70 1 5 2 2 2 1
  2 0 0"`). **Confirmed, not just a lead**: field 1 is a governing
  Hero's own `leader_id` (`255` = empty slot, 104 of the 218 rows),
  fields 2-3 are that Hero's current `HexCoord` -- verified two ways:
  (a) the complete set of distinct real field-1 values (`10, 11, 12,
  14...97`) matches this same file's own confirmed
  `GWProvinceRecord.governor_leader_id` set *exactly*, except every
  single-digit id (0-9, this project's own "King's `leader_id` ==
  `kingdom_id`" range for a 9-kingdom game) is systematically absent --
  i.e. this table excludes Kings, Heroes only; (b) Philo (`leader_id`
  70, confirmed governing Transylvania at `HexCoord(1, 5)` since Phase
  222's own "Philo(70)" cross-check) appears at exactly `"70 1 5 ..."`,
  twice (duplicate rows, same trailing fields). Fields 4-10 (7 more
  integers) are still unresolved -- items carried, personal stats, or
  commanded units are all plausible given the duplicate-row pattern, but
  none is confirmed. Not implemented as a parser here; a future phase
  could extend this module with a `GWHeroRecord`-equivalent once the
  trailing fields are decoded.
- The 2-line marker between the two blocks (`"0 255 0"` / `"35 99 0"`)
  and the fixed 52-triple `"255 0 0"` terminator row are both unresolved
  structural boundaries, not data.

None of this is implemented in `parse_gw_world()` -- this addendum
records a research pass only, so a future phase doesn't re-walk the
already-falsified Feature/Monster hypothesis from scratch.

**Phase 317 addendum -- the 218-row block is per-army, not per-Hero
(refines Phase 316, still a research pass, no new parser code).** All
12 real `GW3__T1..T12` snapshots are now available (not just `T1`), and
comparing the same `leader_id` across turns overturns Phase 316's
"one row per Hero" reading:

- **A Hero can have *many* rows in the same turn, not one.** Guerin
  (`leader_id` 18) has 6 rows in `GW3__T3`, 9 in `GW3__T4`, 9 in `T5`...
  -- all sharing his own current `HexCoord` for that turn (which itself
  moves turn over turn, e.g. `(10,6)` at `T3` to `(11,5)` at `T4`,
  tracking his real LMOVE orders) -- so fields 2-3 are still "this
  Hero's current position," but field 1 is better read as "commanded
  by," not "this Hero's own single record."
- **Row count changes correlate directly with real Recruit orders.**
  Guerin's row count jumps from 6 (`T3`) to 9 (`T4`), a net +3; his own
  real `AK3__T4.K1` move file shows exactly 2 `ActionCode.RECRUIT`
  phases that turn (`P2`, `P4`). This is a genuine, sourced correlation
  (not a coordinate-format coincidence like Phase 316's own
  now-falsified lead) -- recruiting under a Hero adds row(s) to his own
  group in this table.
- **Working hypothesis, not yet fully confirmed**: one row per *army*
  (or army-like unit) under that Hero's command -- fields 4-10 would
  then hold that army's own type, size, and/or quality, echoing
  `models/army_type.py ArmyType`'s own already-confirmed 0-19 ordinal
  range (`MOD_PAT_ORDINAL_TO_ARMY_TYPE` above) and this project's own
  `ArmyState` shape. Not confirmed field-by-field: in the small samples
  checked, field 4 skews heavily toward `1` (`ArmyType.BOWMEN`'s own
  ordinal) rather than spanning the range enough to be confident yet.
- Philo's own earlier "two identical duplicate rows" (Phase 316) is
  consistent with this reading too -- a Hero governing a province
  directly (rather than actively commanding a field army) still shows
  up with >=1 row here, not necessarily tied to Recruiting specifically.

Still not implemented as a parser -- decoding fields 4-10 individually
(which field is `ArmyType`, which is quantity/quality) needs a larger,
systematic cross-check (in the style of Phase 278's own 701-row
`Mod_PAT` recovery) before any code is written against this shape.

**Phase 318 addendum -- the kingdom/leader header block before the
province-record block (research pass only, no new parser code).**
`GW3__T1` lines 1 to ~1419 (before the province block starts) hold one
record per kingdom, each a King's own record followed by his Heroes'
records back to back. A leader record's own shape (`GW3__T1`, King
Babba Sissoko / leader id 0): a numeric header line, then a long
numeric line, then **Title** (`"Lord"`), **Epithet** (`"Master of the
s"` -- see below), **real player name** (`"Andrea Ferrigno"`), then one
or more `"Action Plans:"` blocks in the *exact same grammar*
`parser/k1_moves.py` already parses (`SP:`, `P0 :`, ...). 101 total
`"Action Plans:"` blocks in `GW3__T1` across 9 kingdoms and their
Heroes.

- **Kingdom identity confirmed against real letters.** `"Babba
  Sissoko"` (the kingdom name printed on its own line, right before the
  King's own record) and King Babba Sissoko's own in-game character
  name, `"Uga-Buga Makumb"`, and his real player name, `"Andrea
  Ferrigno"`, all independently match `SE3__T1.K1`/`SE3__T2.K1`'s own
  real narrative and move-sheet text (`"#0, Andrea Ferrigno, ... a
  Orcish, Undead ruler"`) -- confirming Kingdom name and King's own
  character name are two distinct fields, matching this project's own
  existing `KingdomState`/`LeaderState` split.
- **"Master of the s" is a real, independently-reproduced truncation**,
  not a parsing artifact: it appears cut at the exact same point in
  both the raw world file and `SE3__T1.K1`'s own separately-generated
  narrative text (`"Lord Babba Sissoko Master of the s (#0)"`) -- a
  genuine fixed-width truncation bug/feature of the original engine.
- **A leader record's own numeric header line starts with that
  leader's current `HexCoord`, confirmed by cross-check**: King Babba
  Sissoko's own header line begins `"11 7 ..."`, matching Piratum
  `HexCoord(11, 7)`, his own real capital confirmed via
  `GWProvinceRecord.governor_leader_id == 0` in the same file's
  province block. Position 4 on that same line is `0`, matching his
  own `leader_id` too.
- **The kingdom-level header line (33 integers, one per kingdom,
  shared by the King and all his Heroes) yields a confirmed, verified
  in-game calendar**, found by comparing the same kingdom's own header
  line across all 12 real `GW3__T1..T12` snapshots: position 3 (and,
  redundantly, position 20) is the **turn number**, counting 1 through
  12 exactly; positions 14/15/16 are **day/month/year** of the in-game
  date, progressing monotonically and plausibly from `19/12/2006`
  (`T1`) to `25/5/2007` (`T12`) -- corroborated independently by
  `AK3__T1.K1`'s own real move-sheet footer, `"Due: Jan. 2, 2007"`,
  shortly after `T1`'s own in-game date. Most of the remaining 33
  positions are constant across all 12 turns (structural markers, not
  data); a few grow then plateau (candidate object/record counters);
  position 29 grows near-monotonically (`0` at `T1` to `434` at `T12`)
  and looked like treasury, but **direct comparison against
  `SE3__T1.K1`/`SE3__T2.K1`'s own real "Gold in treasury" lines (11,
  then 22) rules that out** -- the real treasury is far smaller and
  doesn't grow anywhere near that fast. A cumulative-revenue-style
  running total is a plausible alternative, not confirmed.
- **A real dynastic succession, independently confirmed**: by `T12`,
  Kingdom Babba Sissoko's own King is no longer Andrea Ferrigno/Uga-
  Buga Makumb but `"Brian Gruber"` (title `"Lord"`, epithet `"Master
  orango"`) -- the kingdom name persists across a change of ruler, and
  the new King's own record reuses `leader_id` 0 (this project's own
  "King's `leader_id` == `kingdom_id`" convention holding even across
  a succession).

Not implemented as a parser here -- this is a promising lead for a
future phase that could close the README's own "populating a brand-new
`GameState` from nothing at turn 0" gap (`turn/kingdom_bridge.py`'s own
Phase 31 note), since a leader's own starting coordinate and an
embedded, already-parseable Action Plan are both present in this block.
Fields still unresolved: the long second numeric line per leader, most
of the 33-field kingdom header, and everything in a leader's own
25-ish-field header line past the confirmed coordinate/id.

**Phase 319 addendum -- a leader header field confirmed, and two
Phase 318 claims corrected (research pass only, no new parser code).**
Comparing the same 25-ish-field leader header line across *different*
leaders in the same turn (not just the same leader across turns, Phase
318's own method) both confirms a new field and overturns two of that
phase's own claims:

- **Corrected: position 4 is *not* `leader_id`.** Phase 318 read King
  Babba Sissoko's own position 4 (`0`) as matching his own `leader_id`
  (`0`). It doesn't generalize: King Bradipo I's own real `leader_id`
  is `2` (confirmed via `SE3__T1.K1`'s own "Bradipo I (#2)"), but his
  header line's position 4 is also `0` -- the same value as a
  different leader with a different real id. Babba Sissoko's own match
  was coincidental. No field in this line has been found to hold the
  raw `leader_id` literally; it's only recoverable positionally (which
  `"Action Plans:"` block follows which name).
- **Corrected: there is no separate "Kingdom name" field distinct from
  a leader's own name.** Phase 318 read `"Babba Sissoko"` as a Kingdom
  name and `"Uga-Buga Makumb"` as King Babba Sissoko's own *alternate*
  in-game character name, based on a diplomatic-contact narrative
  paragraph that turned out to describe two different people making
  contact with each other, not one person's two names. Direct
  cross-check: `"Uga-Buga Makumb"` has its *own*, separate leader
  record later in the very same kingdom's block in `GW3__T1` (own
  numeric header, own `"Action Plans:"`), making him a second,
  subordinate leader (a Hero) under King Babba Sissoko, not the King
  himself under another name. Every name found in this block --
  `"Babba Sissoko"`, `"Bradipo I"`, `"Kwoth"`, `"Uga-Buga Makumb"`,
  ... -- is simply *a leader's own name* (King or Hero alike); a
  Kingdom's first leader record (its King) happens to open that
  kingdom's contiguous run, which is what made it look like a
  distinct "Kingdom name" field.
- **Confirmed, 3-for-3 against real letters: leader header position 3
  is the `Race` ordinal** (`models/race.py Race`, the same enum the
  province block's own `race` field already uses). King Babba Sissoko
  (position 3 = `3`) is confirmed `Race.ORCISH` (`= 3`) via
  `SE3__T1.K1`'s own "a Orcish, Undead ruler" -- already known from
  Phase 318. Newly cross-checked here: King Bradipo I (position 3 =
  `0`) is confirmed `Race.HUMAN` (`= 0`) via `SE3__T10.K1`'s own
  "Bradipo I is King #2, ..., a Human ruler"; King Kwoth (position 3 =
  `0`) is confirmed `Race.HUMAN` too, via `SE3__T6.K1`'s own "Kwoth is
  King #3, ..., a Human ruler". Three real, independent kings, three
  exact matches.

Not implemented as a parser here. `Race` decoding is solid enough to
act on in a future phase; `leader_id` recovery and the kingdom/leader
naming structure still need the positional (name-follows-record)
approach described above, not a dedicated id field.

**Phase 320 addendum -- the leader's own long numeric line starts with
a confirmed Gender marker (research pass only, no new parser code).**
The long ~140-integer line that immediately follows a leader's 25-ish-
field header line (Phase 318's own "long numeric line, still
unresolved") itself starts with a single letter token, `"M"` or
`"F"`, followed by a constant `10` (a structural marker, not data --
identical across every leader checked, both genders). Confirmed
against real character names, not just plausible: in `GW3__T1`, 8 of
10 leaders are tagged `"M"` and exactly 2 are tagged `"F"` -- and those
2 are **`"Giovanna d'Arco"`** (Joan of Arc, under male player Alberto
Clerici) and **`"Circe"`** (the Odyssey's sorceress, under male player
Marco Calabresi, already confirmed as King #8's own kingdom in Phase
318's own addendum) -- both unambiguously female in-game character
names, chosen by male real-world players, matching the `"F"` tag
exactly. Every `"M"`-tagged leader (Babba Sissoko, Bradipo I, Kwoth,
...) has a male or gender-neutral name. Not yet given a project enum --
this project doesn't currently model character gender anywhere, so
adding one is deferred to whichever future phase actually consumes it.

The long line's own third token (right after `"<M|F> 10 "`) varies
leader to leader with no obvious pattern yet (`2` for Babba Sissoko,
`0` for Bradipo I, `1012` for Kwoth, `892` for Giovanna d'Arco, `764`
for Circe) -- large values for some Heroes, small/zero for these
particular Kings, no real-letter cross-check found for it. Left
unresolved rather than guessed.

**Phase 321 addendum -- an open, unconfirmed structural lead on the
kingdom-level "doubled 30-value list" (research pass only, no new
parser code, no confirmed finding).** The 30-integer line that appears
once per kingdom, immediately after that kingdom's own name and before
its King's numeric header (e.g. Babba Sissoko's own `"0 3 2 4 0 2 1 3 1
3 0 0 3 5 0 2 0 2 0 2 2 4 0 2 0 2 0 2 1 3"`, doubled to 60 tokens with
only the first 4 differing between the two copies) splits cleanly into
**15 `(min, max)`-shaped pairs** -- suggestively the same count as this
project's own `models/race.py Race` enum (15 members, ordinals 0-14),
with most pairs spanning a gap of ~2. **Tested and NOT confirmed**: if
this were a fixed universal per-`Race` table, it would be identical
across every kingdom's own file. It isn't -- Bradipo I's own list
(`"1 3 0 2 0 2 1 3 1 3 0 4 1 3 1 3 0 2 0 2 1 3 0 2 0 2 0 2 1 5"`) is
completely different from Babba Sissoko's, so whatever this is, it's
kingdom-specific, not a universal race-indexed constant table. No real
letter data found specific enough to test an alternative hypothesis
(e.g. a per-race relationship or exploration-range value scoped to
that one kingdom). Recorded here as an open structural lead only --
the "15 pairs" shape is real and reproducible, but its meaning isn't,
so no code should be written against it yet.

**Phase 322 addendum -- a leader's own trailing ~128-token line is
confirmed dynamic per-turn state, meaning still unresolved (research
pass only, no new parser code, no confirmed field).** Each leader's
record ends with a trailing block -- a ~128-token line, then a longer
one -- appearing after that leader's own `"Action Plans:"` section and
before the *next* leader's name. Comparing King Babba Sissoko's own
128-token line across `GW3__T1..T6` shows it is **not a static
template duplicated per leader**: position 16 moves `1` (`T1`) ->
`2` (`T2`), then plateaus; several further positions switch on from
`T4` onward (e.g. 39, 64, 91, 99, 121, 128), and at least two (38, 42)
keep climbing turn over turn, reaching `3` by `T6` -- real, small,
targeted accumulation, not noise or a coincidental re-render. This
confirms the block is genuine per-leader-per-turn tracked state.
**Not confirmed**: which of the ~128 slots means what. `128` doesn't
match the confirmed 162-province board (Phase 223), so a direct
per-province index is unlikely; no confirmed project enum has 128
members either. Correlating specific slot indices against specific
real per-turn events (which real order, on which turn, causes exactly
that slot to increment) would need substantially more cross-
referencing than this pass attempted -- recorded as an open lead only.

**Phase 323 addendum -- corrects Phases 320/322: the M/F line and
trailing ~128-token block are King-only, not universal to every
leader (research pass only, no new parser code).** Both earlier
addenda implicitly described these fields as belonging to "a leader"
in general, because every example checked so far happened to be a
King. A Hero's own record is leaner and lacks both fields entirely:
`name` / 30-value list / 25-field header / (blank) / `"Action Plans:"`
-- no `M`/`F` line, no Title/Epithet/player-name lines, and no
trailing ~128-token block before the next leader's name. Confirmed
3-for-3 each way in `GW3__T3`: Kings Babba Sissoko, Bradipo I, and
Kwoth all have the full block (`M`/`F` line through the trailing
~128-token line); Heroes Guerin, Arnulf, and Clarambald all have the
lean form, going straight from their own 25-field header to their own
`"Action Plans:"` with nothing in between. This means Gender (Phase
320) and the dynamic per-turn tracked state (Phase 322) are both
King-specific fields, not general leader attributes -- relevant for
any future phase that tries to model this block, since a `GWLeader
Record`-equivalent parser would need two distinct shapes (King vs
Hero), not one.

**Phase 324 addendum -- the King/Hero distinction (Phase 323) also
governs the "doubled 30-value list"'s own length (research pass only,
no new parser code).** Phase 321's own "15 `(min, max)` pairs" reading
assumed a 60-token doubled list for every leader, because every
example checked was a King. Heroes carry a **single, un-doubled
30-token list** instead -- e.g. Guerin's own list is exactly 30 tokens
(`"0 0 2 2 1 1 0 0 0 0 2 5 3 4 0 2 0 0 0 0 1 2 0 0 0 4 0 0 1 3"`), not
60. Confirmed on a larger sample than Phase 323's own check: across
`GW3__T3`, all 7 Kings found (Babba Sissoko, Bradipo I, Kwoth, Hokuto,
Kahn, Circe, Agesilao) have the 60-token doubled list; all 11 Heroes
found immediately after them (Guerin, Arnulf, Clarambald, Kokocala,
Lallipugh, Alexius, Ningarl, Saladin, Girard, Everard, Stonebrick) have
the 30-token single list -- 18 for 18, no exceptions. Still unresolved:
what the 30 (or 60) values themselves mean (Phase 321's own "15 pairs"
shape is unaffected by this -- it's still real for Kings, still
unconfirmed semantically, and now known not to generalize to Heroes at
all in its doubled form).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.parser.errors import K1ParseError

_PROVINCE_HEADER_RE = re.compile(r"^(\d+) (\d+) 0 (\d+) 0 6$")

# Line 3's own two real ordinals, decoded (Phase 278) -- see the module
# docstring's "Recruiting Types (Mod_PAT)" section for the full
# derivation. `None` at ordinal 15 is the real "no second recruit type"
# sentinel (renders as "None" in the real table), not a missing mapping.
MOD_PAT_ORDINAL_TO_ARMY_TYPE: dict[int, ArmyType | None] = {
    0: ArmyType.GARRISON,
    1: ArmyType.BOWMEN,
    2: ArmyType.AXEMEN,
    3: ArmyType.PHALANX,
    4: ArmyType.LEGION,
    5: ArmyType.LT_CAVALRY,
    6: ArmyType.HVY_CAVALRY,
    7: ArmyType.CHARIOTS,
    8: ArmyType.ELEPHANTS,
    9: ArmyType.CAMEL_CORPS,
    10: ArmyType.WARG_RIDERS,
    11: ArmyType.DRAGON_WING,
    12: ArmyType.EAGLE_WING,
    13: ArmyType.WHALES,
    14: ArmyType.FLEET,
    15: None,
    16: ArmyType.MERMEN,
    17: ArmyType.ENTS,
    18: ArmyType.TROLLS,
    19: ArmyType.WEREBEASTS,
}


class GWParseError(K1ParseError):
    """Raised when a world file doesn't match the expected shape."""


@dataclass(slots=True)
class GWProvinceRecord:
    name: str
    tax: int
    terrain: Terrain
    race: Race
    # The governing leader's own leader id (`None` for the `255`
    # unowned sentinel) -- NOT a kingdom id; see the module docstring's
    # "Philo(70)" cross-check. Resolving this to an owning kingdom needs
    # a `GameState`-level leader/kingdom lookup this parser doesn't do.
    governor_leader_id: int | None
    # Mod_PAT(px,py,0)/Mod_PAT(px,py,1), decoded via
    # MOD_PAT_ORDINAL_TO_ARMY_TYPE (Phase 278). recruit_type_2 is `None`
    # for the real "no second recruit type" sentinel -- see the module
    # docstring; every real province observed so far has a genuine
    # recruit_type_1.
    recruit_type_1: ArmyType | None
    recruit_type_2: ArmyType | None


def parse_gw_world(path: Path) -> list[GWProvinceRecord]:
    """Parses every province record out of a world file.

    Scans the whole file for the province-header line's own fixed shape
    (`"<tax> <terrain> 0 <race> 0 6"`) rather than assuming a fixed byte
    offset, since that shape is confirmed unique to the province block
    (a file-wide regex scan against the real `GW3__T1` sample returns
    exactly 162 matches -- the real, user-confirmed province count per
    world -- with no false positives from the file's other, differently-
    shaped record blocks).
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    records: list[GWProvinceRecord] = []
    i = 1
    while i < len(lines):
        match = _PROVINCE_HEADER_RE.match(lines[i].strip())
        if match is None:
            i += 1
            continue

        name_idx = i - 1
        line3_idx = i + 1
        owner_idx = i + 2
        if owner_idx >= len(lines):
            raise GWParseError(
                "province record truncated before its owner line",
                line_number=i + 1,
                line=lines[i],
            )

        name = lines[name_idx].strip()
        tax, terrain_ordinal, race_ordinal = (int(g) for g in match.groups())
        recruit_type_1, recruit_type_2 = _parse_recruit_types(lines[line3_idx], line3_idx)
        governor_raw = lines[owner_idx].strip()
        if not governor_raw.lstrip("-").isdigit():
            raise GWParseError(
                "expected an integer governor id after the province record",
                line_number=owner_idx + 1,
                line=lines[owner_idx],
            )
        governor = int(governor_raw)

        records.append(
            GWProvinceRecord(
                name=name,
                tax=tax,
                terrain=Terrain(terrain_ordinal),
                race=Race(race_ordinal),
                governor_leader_id=None if governor == 255 else governor,
                recruit_type_1=recruit_type_1,
                recruit_type_2=recruit_type_2,
            )
        )
        i = owner_idx + 1

    return records


def _parse_recruit_types(line3: str, line_number: int) -> tuple[ArmyType | None, ArmyType | None]:
    """Decodes a province record's own line 3 (`"<t1> 0  <t2> 0"`) into
    `Mod_PAT(px,py,0)`/`Mod_PAT(px,py,1)` -- see the module docstring's
    "Recruiting Types (Mod_PAT)" section for the full derivation.
    """

    tokens = line3.split()
    if len(tokens) != 4 or not all(t.lstrip("-").isdigit() for t in tokens):
        raise GWParseError(
            "expected four integers on the recruiting-types line "
            '("<type1_ord> 0  <type2_ord> 0")',
            line_number=line_number + 1,
            line=line3,
        )

    type1_ord, type2_ord = int(tokens[0]), int(tokens[2])
    for ordv in (type1_ord, type2_ord):
        if ordv not in MOD_PAT_ORDINAL_TO_ARMY_TYPE:
            raise GWParseError(
                f"unrecognized Mod_PAT ordinal {ordv} (expected 0-19)",
                line_number=line_number + 1,
                line=line3,
            )

    return MOD_PAT_ORDINAL_TO_ARMY_TYPE[type1_ord], MOD_PAT_ORDINAL_TO_ARMY_TYPE[type2_ord]
