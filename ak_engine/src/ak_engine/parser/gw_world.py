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
  leaders`/`LKing()`-equivalent lookup -- this pure file parser
  deliberately doesn't perform it itself, but `parser/gw_world_bridge.
  py resolve_province_owners()` (Phase 224) already does, given a
  `GameState` whose `leaders` are populated -- see that function's own
  docstring, not an unresolved gap (the "Known gaps" section below was
  written before Phase 223/224 existed and was never updated once they
  closed it in the sibling bridge module).

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
y=06) strongly suggested the world file's own record order follows
`(x, y)` -- **fully confirmed, not just a lead, since Phase 223**: see
`parser/gw_world_bridge.py`'s own module docstring, which pinned the
exact shape down precisely (column-major -- outer loop over all 18 `x`
values, inner loop over all 9 `y` values, `HexCoord(record_index // 9,
record_index % 9)` 0-indexed) against 63 real provinces across all 9 of
game 3's own turn-1 letters, zero mismatches. Not consumed by *this*
module deliberately (a pure file-format parser has no business owning
`HexCoord` assignment or `GameState` construction) -- consumed by that
sibling bridge module instead, not left undone.

**Known gaps, deliberately not attempted here**:
- **No coordinate field exists in a province's own 4-line record** --
  `parse_gw_world()` itself still returns records in the file's own
  on-disk order, not keyed by `HexCoord`, by design (see above: that's
  `parser/gw_world_bridge.py bridge_gw_world_provinces()`'s own job,
  already implemented and tested since Phase 223, not "deferred to a
  future phase" the way this bullet used to read before that phase
  landed and this note was never revisited).
- Line 3's own two integers are unresolved (population? garrison
  strength? a resource id?) -- out of scope for this phase, which only
  needed `ptax`/terrain/race/`governor_leader_id`. **Resolved, Phase
  278** -- see the module's own "Recruiting Types" section below;
  this note is kept for its original historical context.
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

**Phase 325 addendum -- a leader's own doubled skill-list and 25-field
header, decoded from an original game-host document (research pass
only, no new parser code).** The user supplied a genuine original
game-host document ("FILE UTILE PER LEGGERE IL FILE GW.TXT") describing
the manual procedure for registering a champion King into the separate
`VALHALLA.txt` hall-of-fame archive, including a field-by-field legend
for a leader's own two numeric lines in the raw `GW*` file. This is a
**direct source, not an inference** -- the strongest evidence tier this
project uses -- and it resolves two long-open leads:

1. **The doubled/single 30-value list (Phase 316/321/324) is 15
   `(skill_level, aptitude)` pairs, one per `Ability`, in exact
   `models/enums.py Ability` enum order** (`TACTICAL, MARCH, NAVAL,
   ARCHERY, MELEE, WHITE, NECROMANCY, ELEMENTAL, PSYCHIC, ILLUSION,
   DRUID, THIEF, EXPLORER, SPY, SAGE`). This **supersedes Phase 321's
   own unconfirmed "possibly `Race`-indexed" speculation** (`Race` also
   happens to have 15 members, which was the coincidence that made that
   reading plausible) and directly matches this project's own prior
   Phase 127 resolution of the K1 move-file's own `SkillTable`
   pair-shape as `(skill, aptitude)`. Kings' own list is this 15-pair
   table written out twice back-to-back (still unexplained why it's
   doubled for Kings only); Heroes carry it once.

2. **Five previously-unlabeled positions in the leader's own 25-field
   numeric header (Phase 318/319) are named by the document**, using
   its own single-letter column headers:
   - position 4, `S` -- "Special effects." Meaning of the value itself
     is not given by the document and remains unconfirmed here.
   - positions 5 and 6, `L L` -- "Liege lord" (given as two columns in
     the source, both apparently carrying the same value in every
     example checked). `255` = no liege (the leader is themself a
     King); `0`-`11` = owned by the King with that id. This is a
     **candidate** for the leader-to-kingdom-ownership mapping this
     project has lacked since Phase 224, but is only partially checked
     against real `GW3__T3` data so far: every King sampled (Babba
     Sissoko, Bradipo I, Kwoth, Hokuto, Kahn, Circe, Agesilao) reads
     `255 255` as expected; Hero Clarambald reads `3 3`, matching King
     Kwoth's own real `leader_id` (`SE3__T1.K1`'s "Kwoth (#3)"); Hero
     Arnulf reads `255 255` rather than a real id, which is consistent
     with this project's own `LeaderState.kingdom_id` already being
     nullable for independent Heroes (Phase 104) rather than a
     contradiction. Not yet confirmed for enough Heroes to treat as
     settled -- flagged here as a strong open lead, not a closed one.
   - position 7, `C` -- "Condition": `0`=Dead, `1`=Hired, `2`=Mercenary.
     These three values match `models/monster.py`'s own
     `MonsterEngagementState` enum's first three members (`DEAD=0`,
     `HIRED=1`, `MERCENARY=2`) exactly, though that enum's further
     members (`ZOMBOID`, `BOLD`, `SOLD`, `LOSER`, `CALM`) go unmentioned
     by the document, which only needed the alive/dead/mercenary
     distinction for Valhalla registration -- whether leaders literally
     reuse the monster enum's own underlying Pascal type, or merely a
     numerically-identical one, is not confirmed.
   - position 10, `A` -- "Alignment": `1`=Good, `2`=Druidic,
     `3`=Neutral, `4`=Pagan, `5`=Evil. This is an **exact match** for
     `models/alignment.py`'s own `ALIGNMENT_ORDINAL` values `GOOD=1`
     through `EVIL=5`. That same dict's further, CTBOTH.PAS-sourced
     members (`DIVINE=0`, `ANTI_HOLY=6`, `UNDEAD=7`, `MECHANICAL=8`,
     `SPECIAL=9`) fall outside the document's own simplified `1`-`5`
     legend -- which also explains King Babba Sissoko's own real
     "Undead" alignment from `SE3__T1.K1`'s letter text
     (`Alignment.UNDEAD` = `7`).
   - position 11, `T` -- "Temper": `0`=Cowardly through `3`=Berserk.
     This is an **exact match** for `models/temper.py`'s own `Temper`
     enum (`COWARDLY=0`, `CAUTIOUS=1`, `BRAVE=2`, `BERSERK=3`).

   Positions 8-9 and 12-25 are not named by the document and remain
   unconfirmed.

The document also describes a **separate, distinct artifact**: the
`VALHALLA.txt` archive's own manually-authored third line ("`M` or `F`,
followed by a number for the character's favorite magic item") is
something the human registrar writes by hand during induction -- it is
**not** the same thing as the naturally-occurring `M`/`F` line already
documented in the live `GW*` file itself (Phase 320's Gender field,
followed by Phase 322's own dynamic ~128-token block, both King-only
per Phase 323). The two artifacts merely share a leading `M`/`F` token
by coincidence of both encoding gender. The document additionally
includes a 94-entry (`0`-`93`) "Magic Treasures" name catalog (e.g.
`0`=Standard of Command, `40`=Sword Excalibur, `58`=Necronomicon,
`93`=No treasure) used for that same manually-authored line -- noted
here for the record as a possible future resource, but out of scope for
this parser since it applies to the Valhalla archive format, not the
live world file.

**Phase 326 addendum -- Babba Sissoko and Uga-Buga Makumb are two
different Kings of two different kingdoms, correcting Phase 319's own
"Hero subordinate to a King" reading (research pass only, no new parser
code).** Phase 319 concluded that `"Uga-Buga Makumb"` is a Hero owned
by King Babba Sissoko, based on a diplomatic-contact paragraph in
`SE3__T1.K1` and on finding a separate leader record for Uga-Buga
Makumb later in the same kingdom's block. Both of those observations
were real, but the conclusion drawn from them was wrong. Direct
re-examination of `GW3__T3` and `SE3__T1.K1` shows:

- **Uga-Buga Makumb's own `GW3` record is King-shaped, not Hero-shaped**:
  a 60-token doubled skill list, an `M`/`F` line, and the trailing
  King-only ~128-token dynamic block (Phase 320/322/323's own King
  markers) -- the same shape as Babba Sissoko's own record, not the
  30-token undoubled Hero shape. Both also read Liege `255 255` (no
  liege), as expected for two Kings.
- **Their real players are different people**: Babba Sissoko's own
  record is followed by player name `"Andrea Ferrigno"`; Uga-Buga
  Makumb's own record is followed by player name `"Andrea Vitali"` --
  two separate human players, not one player under an alias.
- **`SE3__T1.K1`'s own `CHARACTERS` roster table is addressed to
  Uga-Buga Makumb as "My Lord"** and lists him first with `leader_id 1`
  (`"Uga-Buga Ma(1) ..."`), the same `Kx`-suffix-equals-King's-own-id
  pattern independently confirmed for `K2`/Bradipo I(`#2`) and
  `K3`/Kwoth(`#3`). Babba Sissoko does not appear anywhere in that
  roster -- he belongs to a different kingdom (`#0`, per his own
  `"(#0)"` references in the same letter's narrative text), which
  appears first in `GW3`'s own kingdom-block order but has no
  Heroes of its own and no corresponding `SE3__Tn.K0` letter file among
  this project's own fixtures (possibly a lightly-populated or
  NPC-adjacent kingdom, unconfirmed).
- **The "diplomatic contact" paragraph Phase 318/319 both read from is
  exactly what it says**: `"Uga-Buga Makumb asked Lord Babba Sissoko
  Master of the s (#0) to improve..."` describes two independent Kings
  of neighboring kingdoms interacting, not an internal command from a
  King to his own subordinate Hero.

Net correction: every one of Phase 318's own raw facts about Babba
Sissoko (coordinate, `Race.ORCISH`, Undead alignment, the "Master of
the s" truncation, player `Andrea Ferrigno`) remains accurate -- he is
simply the King of kingdom `#0`, a separate kingdom from Uga-Buga
Makumb's own kingdom `#1`, not entangled with Uga-Buga Makumb's own
identity at all. Phase 319's own "no separate Kingdom name field, every
name is just a leader's own name" observation also still holds -- it
was the *specific relationship* between these two named leaders (King
alongside King, not King alongside subordinate Hero) that was
misidentified.

Not implemented as a parser here. Kingdom `#0`'s own lack of a letter
file and lack of Heroes remains an open, unconfirmed detail rather than
a settled fact.

**Phase 327 addendum -- the Liege field (Phase 325) confirmed across 27
real Heroes, upgraded from open lead to confirmed (research pass only,
no new parser code).** Phase 325 read a leader header's positions 5-6
(`L L`) as "Liege lord id, `255`=none/`0`-`11`=owned by that King," but
flagged it as only spot-checked on a handful of examples. Using each
`SE3__T1.Kx` letter's own `CHARACTERS` roster as independent ground
truth (every Hero listed there under a King, plus separately-noted
"wandering Hero" / "buried in ..." entries for unaffiliated or dead
ones) and cross-referencing all 27 named Heroes found in `GW3__T3`
against their own real Liege value:

- **16 Heroes already affiliated with a King as of the turn-1 letter**
  show Liege equal to that King's own real id at turn 3, exactly:
  Guerin/Teleko -> `1` (Uga-Buga Makumb's kingdom, Phase 326), Clarambald/
  Garin -> `3` (Kwoth), Ningarl/Lexington -> `4` (Hokuto), Tarsus/Marlon
  -> `5` (Prometeo), Gladstone/Hume -> `6` (Kahn), Rolando/Hakim -> `7`
  (Giovanna d'Arco), Behemond/Duqaq -> `8` (Circe), Tancred/Negumba ->
  `9` (Agesilao) -- 16 for 16.
- **6 Heroes still unaffiliated or dead as of the turn-1 letter, and
  still so at turn 3**, correctly show Liege `255 255`: Eric, Lakes,
  Samantha, Odysseus ("a wandering Hero" at both turns), Reynald
  ("buried in Siouxhome," still dead), and Arnulf (narrated in
  `SE3__T2.K1` as ruling an independent Orcish region, consistent with
  having no liege at all) -- 6 for 6.
- **5 Heroes unaffiliated or dead as of the turn-1 letter show a real,
  non-`255` Liege by turn 3** (Melantheus, Tao-Li -> `1`; Helatia,
  Jamielle -> `8`; Tiffany -> `7`): not a contradiction but the expected
  effect of two mechanics this project already implements --
  `turn/hire_fire_decode.py`'s own Hire (a King picking up a wandering
  Hero) and Cast's own Resurrection (`turn/cast_decode.py`'s own nested-
  plan handling) -- both plausible between `T1` and `T3` and each one
  fully explaining a previously-`255` Hero acquiring a real liege.

27 for 27, zero unexplained mismatches. The Liege field is now
confirmed with high confidence, not merely a candidate; it remains,
however, a `research pass only` finding -- no `LeaderState`/`GameState`
field consumes it yet, so this doesn't change parser or model
behavior.

Not implemented as a parser here. A future phase could use this field
to close the leader-to-kingdom-ownership gap open since Phase 224 by
wiring it into `turn/kingdom_bridge.py`'s own Kingdom-to-`GameState`
sync.

**Phase 328 addendum -- tracking one Hero (Guerin) across all 12 real
turns isolates which remaining header positions are truly dynamic, one
falsified hypothesis, and two new candidate leads (research pass only,
no new parser code).** Comparing the same leader's own 25-field header
across `GW3__T1` through `GW3__T12` (rather than different leaders in
the same turn, the method used so far) cleanly separates constant
positions from genuinely time-varying ones:

- **Falsified: position 4 (`S`) is not the letter roster's own "Ini"
  column.** `SE3__T1.Kx`'s own `CHARACTERS` table has an unlabeled
  numeric column between `M/F Race` and the ability grid (plausibly
  Initiative) that varies per leader (Guerin `2`, Clarambald `1`, Uga-
  Buga Makumb `0`, ...). Position 4 was a candidate match since Phase
  325 left its meaning open. Checked across all 27 Heroes from Phase
  327's own dataset: position 4 reads `0` for every single one of
  them, never varying, so it cannot be encoding this per-leader
  "Ini" value. Its true meaning (the document's own "Special effects")
  remains unconfirmed.
- **Reconfirmed at scale: position 7 (Condition, Phase 325) matches
  perfectly across all 27 Heroes**, not just the earlier spot check --
  the 6 wandering/unaffiliated Heroes (Eric, Lakes, Samantha, Odysseus,
  Melantheus, Tao-Li at `T1`) all read `2` (Mercenary); the one dead
  Hero (Reynald, "buried in Siouxhome") reads `0` (Dead); every
  affiliated Hero reads `1` (Hired).
- **New lead: position 18 behaves like a non-decreasing counter.**
  Guerin's own value across `T1`..`T12`: `0, 0, 0, 0, 1, 1, 1, 2, 3, 5,
  5, 7` -- never decreases, sometimes plateaus for several turns, in
  line with a rank/level/seniority-style stat. Unconfirmed against any
  real letter text; no narrative "level up" language has been checked
  yet.
- **New lead: position 22 behaves like an accumulating bitmask.**
  Guerin's own value: `2, 6, 7, 7, 7, 71, 71, 71, 199, 199, 199, 199`.
  In binary, each jump adds exactly one new bit and never clears an
  existing one (`7` = bits 0,1,2; `71` = `7 + 64`, adding bit 6; `199`
  = `71 + 128`, adding bit 7). Consistent with a flags/unlocks-style
  field that only accumulates. Unconfirmed against any specific
  real-world trigger (item found, ability learned, province type
  visited, ...).
- **Ruled out as a candidate for either of the above: position 12
  fluctuates non-monotonically and goes negative** (`0, 0, 2, 4, 7, 12,
  13, 22, 22, 22, 3, -16` for Guerin) -- incompatible with an
  ever-growing counter or bitmask; more likely a spendable/lossable
  resource (gold, morale, supply) or a value relative to some baseline.
- **Position 19 shows no discernible trend turn to turn** (`87, 1, 39,
  88, 52, 8, 55, 30, 57, 93, 41, 11` for Guerin) -- possibly a
  per-turn-recomputed state (current strength, a random roll) rather
  than anything cumulative.
- **Position 8 is constant per leader but differs between leaders**
  (Guerin always `48`, Ningarl always `46`) -- a per-character constant,
  plausibly tied to identity or a fixed base stat, not yet cross-checked
  against anything in the letters.

Not implemented as a parser here. Positions 18 and 22 are the most
promising open leads for a future phase, given their clean, non-random
monotonic behavior; both would benefit from checking against explicit
narrative events (Practice results, item discoveries, battle
participation) in the same leader's own `SE3__Tn.Kx` letters turn by
turn, the same technique that resolved Liege (Phase 327).

**Phase 329 addendum -- both of Phase 328's own leading hypotheses for
positions 18 and 22 falsified against Guerin's own full narrative
record (research pass only, no new parser code).** Phase 328 flagged
position 22's bit pattern as suggestively `Ability`-indexed and
position 18 as a plausible battle/conquest counter, but only checked
them against the header's own numbers. Reading Guerin's own full
`SE3__T2..T10.K1` letters turn by turn falsifies both:

- **Position 22 is not an `Ability`-unlock bitmask.** Its `ELEMENTAL`
  bit (bit 7) turns on at `T9`, but Guerin's own Elemental skill level
  stays `0` across all 12 turns -- there's nothing to "unlock." Its
  `TACTICAL` bit (bit 0) turns on at `T3`, while Guerin's own Tactical
  skill level is still `0` at that point too (it only starts rising at
  `T5`). The bit positions happening to spell out real ability names
  (`Tac/Mar/Nav/Nec/Ele`) was coincidence, not signal.
- **Position 18 is not a battle-victory or conquest counter.** Cross-
  referencing every real conquest and battle mentioned in Guerin's own
  letters against the position-18 delta each turn shows no clean
  relationship: `T2` (2 conquests: Falkenheim, Mare Tarkium) -- no
  change; `T4` (2 conquests: the Ark Royal Sea, the Falkland Sea) -- no
  change; `T5` (1 conquest, plus the letter's own explicit "Guerin's
  experience improved my skill in Tactics") -- `+1`; `T6` (1 conquest:
  Bir Nzaran) -- no change; `T7` (2 conquests: Peachwood, Sherwood,
  plus the same "improved my skill in Tactics" phrase again) -- no
  change; `T8` (1 conquest: Quantara Roo) -- `+1`; `T9` (**no battle at
  all** -- a purely diplomatic letter) -- `+1` anyway; `T10` (1
  conquest: Rejaf) -- `+2`. Battles/conquests happen in turns with and
  without an increment, and the field increments in a turn with no
  battle at all -- ruling out both a simple win-counter and a
  skill-improvement counter.

Both fields remain confirmed dynamic and non-decreasing (from Phase
328's own cross-turn data), but their real trigger is unresolved.
Recording both falsified hypotheses here so a future pass doesn't
retrace them; the office-holder score tables in the same letters
(`"First Elder of Elvenkind Guerin 1 933 ..."`, matching this
project's own Ofc_Pts/Rank research from Phase 137) were spot-checked
too and don't line up with either position's own raw values either.

Not implemented as a parser here.

**Phase 330 -- ``parse_gw_leaders``/``GWLeaderRecord``, the first real
parser code for the kingdom/leader header block, closing the leader-to-
kingdom-ownership gap open since Phase 224.** Every phase from 316
through 329 was explicitly "research pass only, no new parser code" --
this one turns the confirmed subset of that research (King/Hero record
shape, Race, Alignment, Temper, Liege) into an actual parser function
plus a real ``GameState`` consumer
(``turn/kingdom_bridge.py sync_leaders_from_gw_world``, same phase). See
``GWLeaderRecord``'s own docstring for the field-by-field derivation
(including the new King-own-kingdom-id-by-file-order finding, confirmed
8-for-8 against real letter data) and ``turn/kingdom_bridge.py``'s own
Phase 330 addendum for exactly what the new bridge function does and
why it's additive to, not a replacement for, the existing K1-based
sync. Deliberately leaves untouched: positions 4/8/12/18/19/22 (still
unresolved, Phase 325/328/329), the kingdom-level 33-field header, and
Blocks A/B -- this phase only acts on the subset already confirmed with
high confidence.

**One further real-data nuance found while building this, not
previously documented**: Condition (position 7) does *not* always
imply a real Liege. Scanning every one of the 100 real leader records
in `GW3__T1` (not just the 27 named Heroes Phase 327 cross-referenced
against letters) turns up three Heroes -- Kokocala, Lallipugh, Alexius
-- who read Condition `1` (Hired) with Liege `255 255` (independent).
All three are independently confirmed in real letter text as
self-ruling local rulers (e.g. `SE3__T2.K1`: "populated by Humans and
Kokocala rules there," no King mentioned). This isn't a contradiction
of Phase 325/327's own Condition/Liege findings -- it clarifies that
Condition describes whether a *character* is alive and active
(Hired/Mercenary/Dead), independent of whether they currently serve a
King (Liege); Phase 327's own 16-for-16 "Hired implies a real Liege"
pattern held only because every Hero it checked happened to be an
actual player-kingdom subordinate, not because the two fields are
coupled in general.

**Phase 331 addendum -- three of the 218-row "per-army" Block B's own 7
unresolved trailing fields decoded: Race, ArmyType, Quality (research
pass only, no new parser code).** Phase 316/317 confirmed Block B's own
row shape (`leader_id, X, Y`, then 7 more integers) and that it's per-
army, not per-Hero, but left every one of those 7 trailing fields
unresolved. Cross-referencing a single leader's own Block B rows across
two turns against that leader's own real "Modified Quality" army table
in `SE3__Tn.K1` decodes three of them -- **but only after fixing a
turn-alignment error**: `GW3__Tn` reflects the game's state at the
*end of turn n-1* (start of turn n), not the end of turn n itself --
confirmed by matching `GW3__T3`'s own row count for Guerin (`leader_id`
18) exactly to `SE3__T2.K1`'s own 6-unit end-of-turn roster, not
`SE3__T3.K1`'s own (different) 9-unit one.

- **Field 4 = `Race`** (`models/race.py`, the same enum already used
  for province/leader race elsewhere in this file). For every
  "monstrous," race-locked `ArmyType` (`WARG_RIDERS`, `DRAGON_WING`,
  `EAGLE_WING`, `WHALES`, `MERMEN`, `ENTS`, `TROLLS`, `WEREBEASTS`),
  this field is a single fixed value across every row of that type in
  `GW3__T3`, and that value is exactly the type's own locked race
  ordinal (`WARG_RIDERS`->`3`=`ORCISH`, `DRAGON_WING`->`4`=`DRAGONS`,
  `EAGLE_WING`->`5`=`EAGLES`, `WHALES`->`6`=`WHALES`,
  `MERMEN`->`8`=`MERMISH`, `ENTS`->`9`=`ENTISH`,
  `TROLLS`->`10`=`TROLLISH`, `WEREBEASTS`->`11`=`WEREFOLK` -- 8 for 8,
  zero exceptions). For every "humanoid" `ArmyType` (recruitable by any
  of the 4 humanoid races), this field instead varies freely across
  `0`-`3` (`HUMAN`/`ELVEN`/`DWARVEN`/`ORCISH`) -- exactly the race
  diversity a humanoid unit can actually have. Directly confirmed
  against real per-unit race text too: Guerin's own Bowmen/Heavy
  Cavalry read "Elf" in `SE3__T2.K1`/`SE3__T4.K1` and this field reads
  `1`=`ELVEN`; his Warg Riders read "Orc" and this field reads
  `3`=`ORCISH`; his Dragons/Eagles read "Dragon"/"Eagle" and this field
  reads `4`/`5` to match.
- **Field 5 = `ArmyType` ordinal** (`models/army_type.py`, the same
  `MOD_PAT_ORDINAL_TO_ARMY_TYPE` table already used for province
  recruiting types). Tallying Guerin's own rows by this field exactly
  reproduces his own real army roster's type composition both turns
  checked: `GW3__T3` (6 rows) -> 4 Bowmen + 1 Heavy Cavalry + 1 Warg
  Riders, matching `SE3__T2.K1`'s own 6-unit list exactly; `GW3__T5` (9
  rows, scattered non-contiguously through the block rather than
  grouped by leader) -> 4 Bowmen + 1 Heavy Cavalry + 2 Dragon Wing + 1
  Warg Riders + 1 Eagle Wing, matching `SE3__T4.K1`'s own 9-unit list
  exactly.
- **Field 6 = `Quality`** (`turn/combat.py`, the same 0-5
  Depleted..Elite enum already used for battle strength). Matched as a
  multiset per `ArmyType` group rather than by row order (Block B
  carries no per-unit name/id to pin an exact row-to-named-unit
  correspondence): Guerin's own 4 real Bowmen qualities at end of `T2`
  are `{Veteran, Average, Crack, Veteran}` = `{3, 2, 4, 3}`, and his own
  4 Bowmen-type rows in `GW3__T3` read this field as exactly `{3, 2, 4,
  3}`; at end of `T4` his 4 real Bowmen qualities are `{Crack, Veteran,
  Crack, Crack}` = `{4, 3, 4, 4}`, matched exactly by `GW3__T5`. Every
  non-Bowmen type (Heavy Cavalry, Warg Riders, Dragon Wing, Eagle Wing)
  matched too, both turns. Uses each unit's own **base** Quality, not
  the letter's separate "Modified Quality" column (which factors in
  race/terrain penalties) -- confirmed by the two Dragon and one Eagle
  row, whose real *base* quality is Average (matching this field) even
  though their real *modified* quality is Sub-Depleted/Depleted.

15 of 15 individual (Race, ArmyType, Quality) values checked across the
two turns matched with zero exceptions.

**Field 8 checked and ruled out as `BASE_STRENGTH`**: it's constant per
`ArmyType` (never varies within a type, across any leader, in
`GW3__T3`), which looked promising, but the actual constant values
don't line up with `models/army_type.py BASE_STRENGTH`'s own Str
column for the majority of types (e.g. `PHALANX`'s own Str is `3`,
this field reads `2`; `ENTS`'s own Str is `6`, this field reads `1`) --
a real, per-type constant, but not that one. Fields 7, 9, and 10 remain
completely unexamined; 9 and 10 are `0` in nearly every row seen so
far (one lone exception, a `9`th field value of `251`, unexplained).

Not implemented as a parser here -- a future phase could extend
`GWLeaderRecord` (or a new `GWArmyRecord`) with `race`/`army_type`/
`quality` per Block B row now that all three are confirmed, once
fields 7/9/10 are resolved enough to decide what else such a record
should carry.

**Phase 332 addendum -- field 7 confirmed as a Skeletal-army marker;
partial structure found for its other values (research pass only, no
new parser code).** Across all 259 Block B rows in `GW3__T3`, field 7
(`0`-`3`) is `3` for exactly 3 rows, and every one of the 3 belongs to
an Undead-aligned leader or a leader serving an Undead King: `leader_id
72` (Teleko, serves King Uga-Buga Makumb, Undead), `leader_id 18`
(Guerin, same kingdom), and `leader_id 0` (Babba Sissoko, himself
Undead-aligned, Phase 318). **Directly confirmed against real letter
text, not just thematic plausibility**: Teleko's own `field7=3` row
reads Race `1`(Elven)/ArmyType `1`(Bowmen)/Quality `2`(Average), and
`SE3__T2.K1`'s own real army table lists exactly one such unit for
him -- `"96th Skel Bowmen -- Elf -- Average"` -- the literal "Skel"
prefix marking a Necromancy-raised Skeletal unit, matching this
project's own already-modeled `ArmyState.is_skeletal` concept (Phase
236) and the `Zomboid` member of `models/monster.py
MonsterEngagementState` (`DEAD=0, HIRED=1, MERCENARY=2, ZOMBOID=3,
...`) it was sourced from. Guerin's own single `field7=3` row is
likewise his own only real "Skel"-prefixed Bowmen (`108th Skel
Bowmen`) among four Bowmen units.

Field 7's other values show a real, structural split not yet fully
resolved: `field7 in {1, 3}` occurs **only** on rows with a real
leader (`field 1 != 255`); `field7 in {0, 2}` occurs **only** on
unled rows (`field 1 == 255`, "under the garrison commander" per this
project's own rulebook citation). Within the unled rows, `0` is common
(66 of 129) and `2` is rare (9 of 129) with a visibly different
Quality spread (`2` includes a `Depleted`-quality row, `0` never does)
-- suggestive of "still kingdom-owned, just unled" (`0`) versus
genuinely ownerless "mercenary" (`2`, matching this project's own
`ArmyState.kingdom_id == None` concept and `MonsterEngagementState`'s
own `MERCENARY=2`), but **not independently confirmed against real
letter data** the way `field7=3` was -- flagged as an open lead, not a
finding.

**Field 9's lone non-`{0,1,2}` value, `251`, is a strict subset of the
unled `field7=0` rows** (9 of the 66) -- every `field9=251` row also
has `field7=0`, but not vice versa. No further pattern found (spans
multiple `ArmyType`/`Race`/`Quality` combinations); still open.

**Field 10 remains unexamined beyond its own value range** (`0` or
`1`, only 4 of 259 rows non-zero, no correlation found yet with
`field7`, led/unled status, `ArmyType`, or `Quality`).

Not implemented as a parser here.

**Phase 333 addendum -- fields 9 and 10 pushed further, one real
structural fact found, both values' own specific meaning still open
(research pass only, no new parser code).** Continuing directly from
Phase 332's own open leads:

- **Field 9 is a genuine sub-field of `field7`, not an independent
  value**: across all 259 `GW3__T3` rows, field 9 reads exactly `0`
  whenever `field7` is `1`, `2`, or `3` (213 of 213 such rows, zero
  exceptions) -- it only ever varies (`1`, `2`, or `251`) on the 66
  rows where `field7=0` (unled, "under the garrison commander," not
  the rarer `field7=2` "mercenary" reading). This is a real, confirmed
  structural fact, distinct from Phase 332's own weaker "251 is a
  subset of field7=0" observation.
- **Tested and ruled out as an explanation for field 9's own `{1, 2,
  251}` split within that subset**: Quality (`field9=1` rows are all
  `Quality=2`/Average, but `field9=2` rows are *also* almost all
  `Quality=2`, so this doesn't cleanly separate the two); `ArmyType`;
  `field8`; and a same-province stacking/sequence-index reading (every
  province in `GW3__T3` holding more than one `field7=0` row was
  checked directly -- e.g. `HexCoord(9,4)`'s own two rows read `field9
  = 1` then `251`, `HexCoord(10,4)`'s own three rows read `1, 1, 251`
  -- no province shows a clean sequential/positional pattern). None of
  these distinguishes the three values.
- **Field 10 remains fully unresolved.** No further leads found beyond
  Phase 332's own "rare binary, no correlation" observation.

Cracking field 9's own specific values (beyond the `field7`-gated
structural fact above) likely needs a different technique than the
ones that worked for fields 4-7 -- those were all solved either by
cross-referencing a *specific, named* real unit against letter text,
or by tracking one real leader's own rows across turns. Neither
applies directly to unled, garrison rows, which carry no name and
whose own turn-to-turn identity can't be tracked the way a `leader_id`
already lets Block B rows be tracked for led armies.

**Phase 334 addendum -- tried tracking one province's own unled
garrison across turns instead of one leader; rules out a per-turn
counter reading for field 9, no further decode (research pass only,
no new parser code).** `HexCoord(10,4)`'s own 3 unled (`field7=0`)
rows are **byte-for-byte identical between `GW3__T2` and `GW3__T3`**,
including field 9's own exact values (`1, 1, 251` in the same order
both turns) -- this directly rules out any reading of field 9 as a
simple per-turn-incrementing counter, since it would have changed
between two consecutive real turns of true idleness. The same
coordinate's own led rows *did* change in that window (King Uga-Buga
Makumb's own led units, present at `T2`, are gone by `T3`), so the
snapshot mechanism itself is turn-sensitive -- the unled garrison's
own stability is a real fact about that data, not a sampling artifact.

By `GW3__T4` this same coordinate has **no Block B rows at all**
(neither led nor unled) -- consistent with a real letter event:
`SE3__T4.K1` describes this exact province (`#1105`, "Jellyfish Sea,"
previously ruled by the independent Hero Tao-Li per that same letter's
own roster line) being newly conquered, with a brand-new `"288th
Garrison"` unit formed there. This supports "unled Block B rows persist
unchanged while a province's ownership is undisturbed, and get wiped
and replaced on conquest" as the real underlying mechanic, though the
new garrison's own row wasn't located in a following turn's Block B to
directly compare against the old one's field 9 -- attempted in both
`GW3__T4` and `GW3__T5` at the same coordinate, found nothing at
either, suggesting the coordinate-to-file-position mapping used for
Block B may itself shift after a conquest (unconfirmed) or that the
new garrison hadn't yet been captured in either of those two
snapshots. Left open rather than forced.

Net result: field 9 is confirmed a **persistent per-unit state**, not
a counter, but its own specific values remain undeciphered.

**Phase 335 addendum -- field 10 pushed across all 12 real turns at
once (not just `GW3__T3`); a clean `ArmyType`-gated structural fact
found, one leading hypothesis tested and ruled out (research pass
only, no new parser code).** Phase 332's "rare binary, 4 of 259 rows
in `GW3__T3`" reading undersold both field 10's own range and its
real structure -- pulling every Block B row from all 12 real
`GW3__Tn` snapshots at once (218 rows at `T1` growing to 344 by `T7`
onward) changes the picture:

- **Field 10 is not binary.** `GW3__T12` has 3 rows reading `2` (all
  three sharing `field9=11`, all at the same `HexCoord`) alongside 27
  reading `1` and 314 reading `0` -- `2` never appears before `T12` in
  any of the 12 real snapshots. Phase 332's "`0` or `1`" was simply
  the full range visible in the one turn it checked.
- **A clean, zero-exception `ArmyType` gate**: field 10 is non-zero
  **only** for the 10 "humanoid"/conventional `ArmyType`s (`GARRISON`,
  `BOWMEN`, `AXEMEN`, `PHALANX`, `LEGION`, `LT_CAVALRY`, `HVY_CAVALRY`,
  `CHARIOTS`, `CAMEL_CORPS`, `FLEET`). Across all 12 turns combined,
  the "monstrous, race-locked" `ArmyType`s already identified in Phase
  331 (`DRAGON_WING`, `EAGLE_WING`, `WHALES`, `MERMEN`, `ENTS`,
  `TROLLS`, `WEREBEASTS` -- 780 rows total) show **zero** non-zero
  field 10 values, not one, across the whole 12-turn game. This is a
  real structural exclusion, not sampling noise -- at even a
  conservative 2% rate (the lowest rate any conventional type shows)
  780 independent rows would be expected to show over a dozen
  non-zero hits. `WARG_RIDERS` (also nominally race-locked per Phase
  331) is the one partial exception, but its 4 non-zero hits across
  129 rows trace back to essentially a single real, persistently-
  tracked unit (Guerin's own `209th Warg Riders`, followed T10-T12)
  plus one more instance at `T12` -- not a broad pattern the way the
  10 conventional types show. `ELEPHANTS` (0 of 19 rows) is too small
  a sample to judge either way.
- **Field 10 is `0` for every single row in `GW3__T1`** (the game's
  own turn-0 starting snapshot, 218 of 218 rows), and the count of
  non-zero rows then grows **monotonically** turn over turn (`0, 3, 4,
  4, 5, 5, 4, 13, 21, 27, 27, 30`, `T1`-`T12`) -- consistent with a
  per-unit flag that some in-game event sets and that is, once set,
  rarely if ever cleared (mirroring field 9's own Phase 334
  persistence finding, though the two fields are otherwise
  independent -- field 10 is `0` on the vast majority of `field7=0`
  unled rows that carry field 9's own non-zero values).
- **Tested and ruled out as the trigger: "this unit fought a battle
  this turn."** Three of Guerin's own led rows (`108th Skel Bowmen`,
  `110th Bowmen`, `209th Warg Riders`) flip field 10 from `0` (`T9`)
  to `1` (`T10`) together, a clean same-leader, same-province,
  led-both-turns transition. `SE3__T9.K1`'s own real letter for that
  exact turn reports **no battle or combat of any kind** for Guerin --
  only a failed illegal-move attempt, a failed Tactics practice roll,
  and a plague at Quantara Roo that destroyed three of his *other*
  units (`109th Heavy Cavalry` and two Bowmen) plus the garrison's own
  `292nd Legion`. Since the flip happens with zero combat in the
  source letter, "fought a battle" cannot be field 10's own trigger.
- **Open lead, not confirmed**: by `T12` the same general area (the
  province Guerin's own `209th Warg Riders` ends up in) accumulates a
  cluster of 8 unled rows sharing `field9 in {10, 11, 251}`, with
  field 10 reading `1` and `2` side by side within the same cluster --
  including a `Quality=0` (Depleted) `Warg Riders` row -- consistent
  with a chaotic post-battle scatter (many units suddenly reduced to
  unled garrison status at lowered quality) and suggestive of field 10
  as an incrementing count of some repeatable event rather than a
  one-shot flag, but not independently confirmed the way the
  `ArmyType` gate above is.

Net result: field 10 is confirmed `ArmyType`-gated (conventional
troop types only, monstrous types structurally excluded) and
confirmed not a simple "fought a battle" flag; its own specific
triggering event and its `0`/`1`/`2` value meaning remain open.

**Phase 336 addendum -- Block B finally gets real parser code:
``GWArmyRecord``/``parse_gw_armies`` (code phase, not research-only).**
Phases 316/317/331-335 confirmed enough of Block B's own row shape
(``leader_id, X, Y, Race, ArmyType, Quality`` plus a Skeletal marker in
field 7) to justify turning it into an actual parser, instead of only
ever re-deriving it ad hoc from raw file offsets each time a new phase
needs it.

Block B's own row is located the same way ``parse_gw_world`` and
``parse_gw_leaders`` already locate their own blocks: scan the whole
file for the row's own fixed shape (exactly 10 space-separated
integers) and take the one contiguous run of such lines -- verified
against all 12 real ``GW3__Tn`` samples that this run is **always
the single, unambiguous one** in the entire file (no second
false-positive run of any length, in any of the 12 turns), so no
byte-offset or marker-line assumption is needed.

``GWArmyRecord`` exposes only what's independently confirmed as typed
fields (``commanded_by_leader_id``, ``coord``, ``race``, ``army_type``,
``quality``, ``is_skeletal``) and keeps the three still-undeciphered
trailing fields as plain, undecoded ints (``raw_field8``,
``raw_field9``, ``raw_field10``) -- the same "keep it raw until it's
actually decoded" treatment ``GWLeaderRecord.condition`` already uses
above. ``is_skeletal`` is only ever set `True` for the confirmed
``field7 == 3`` case (Phase 332); the unconfirmed ``field7 in {0, 2}``
unled split (Phase 332/333's own open "kingdom-owned vs. mercenary"
lead) is preserved verbatim as ``raw_field7`` rather than being forced
into a guessed boolean or enum.

**Correction surfaced while testing against the real, committed
``GW3__T1`` fixture**: Phase 332's own "``field7 in {1, 3}`` occurs
only on rows with a real leader" claim was checked only against
`GW3__T3`. `GW3__T1` has two `field7 == 3` rows that are themselves
**unled** (`"255 9 5 1 1 2 3 2 0 0"`, `"255 11 7 3 3 2 3 2 0 0"`) --
so the Skeletal marker and the led/unled split are two independent
bits within field 7, not perfectly coupled the way Phase 332 read
them from its own single-turn sample. This doesn't weaken
``is_skeletal``'s own confirmation (still the same directly-verified
``field7 == 3`` reading either way); it only means the marker can
legitimately appear on an unled Skeletal garrison too, which
`GWArmyRecord.is_skeletal` already handles correctly since it never
looked at `commanded_by_leader_id` in the first place.

**Phase 337 addendum -- field 7's own unled `{0, 2}` split confirmed:
`2` is the "independent mercenary, available to Recruit" marker
(closes Phase 332/333's own open lead; code phase, `GWArmyRecord`
gains `is_mercenary`).** Real letters carry an "independent
mercenaries which you may Recruit" table (province, unit designation,
race, Modified Quality) whenever a mercenary army sits in or near a
kingdom's own territory. Cross-referencing **every one of the 85
distinct (real-turn, province) sightings of this table across every
`SE3__T0..T11.Kx` letter available** against the corresponding
`GW3__T(n+1)` snapshot's own Block B rows at that same coordinate
(the standard turn-alignment fix from Phase 331) gives **85 exact
matches, zero exceptions**: in every single case, the one row at that
coordinate with `field7 == 2` has the exact `Race`/`ArmyType`/`Quality`
the letter lists, and no `field7 == 0` row ever does. `field7 == 2`
rows total 132 across all 12 turns -- the other ~47 are mercenaries
outside any bordering kingdom's own visibility in the available
letters, not exceptions to the pattern (a kingdom's own letter only
lists mercenaries it can actually see).

This resolves field 7's own full range:

- `0` -- unled, this province's own kingdom-owned garrison.
- `1` -- led (normal, non-Skeletal).
- `2` -- unled, an **independent mercenary army available to Recruit**
  (confirmed above).
- `3` -- Skeletal-army marker (Phase 332), independent of led/unled
  status (Phase 336's own correction).

`GWArmyRecord` gains `is_mercenary: bool`, set `True` only for the
confirmed `field7 == 2` case -- the same "only derive what's actually
confirmed" treatment `is_skeletal` already got in Phase 336.

**Phase 340 addendum -- end-to-end validation against a real, non-T1
file (`GW3__T5`) surfaces and fixes a real province-header parsing bug.**
Every earlier phase's own claims about `parse_gw_world()`'s province
scan were checked only against the committed `GW3__T1` fixture. Running
the full chain (`parse_gw_leaders`/`parse_gw_world`/`parse_gw_armies` ->
`gw_world_bridge.bridge_new_game_state()`) against `GW3__T5` instead --
cross-checked against the real `SE3__T4.K1` letter for that same turn --
first failed outright: `GW3__T5` only yielded 159 of its 162 real
provinces (Katmai, Maplehaven, Khalturin missing, no duplicates and no
garbage names).

The cause: `_PROVINCE_HEADER_RE` hard-coded the header's 3rd token as a
literal `0` (`"<tax> <terrain> 0 <race> 0 6"`), since that token
happened to be `0` for all 162 provinces in `GW3__T1` -- the only file
this regex had ever been checked against. Loosening that one token to accept any integer, and re-scanning all 12
real `GW3__T1`-`GW3__T12` files, yields exactly 162 provinces from every
one of them, with no false positives
(the shape is still otherwise unique in the file). The token itself
takes on several distinct real values across the corpus (`0`, `48`,
`64`, `80`, `256`, `512`, `1280`, `1536`) -- most likely a per-province
bitmask of some kind (exploration-by-kingdom is one plausible guess,
consistent with it being `0` for every T1 province before anyone has
explored anything, and nonzero later) -- but its exact meaning is
undeciphered and deliberately not stored on `GWProvinceRecord` rather
than guessed at. The header's final `0` (before the trailing `6`
anchor) was checked across the same 12-file corpus and never observed
to be anything but `0`, so it stays a literal.

With the fix in place, the rest of the `GW3__T5` end-to-end run is a
clean, positive validation of everything built through Phase 339: all
162 provinces, 10 Kings, and 90 Heroes bridge; every single Block B
army row resolves (`unresolved_army_records` is empty at this turn);
Kingdom 1 (Uga-Buga Makumb)'s own name/race/alignment, Guerin's own
kingdom/race/alignment/sex/location, two independent "wandering Hero"
sightings (Kokocala, Dracona) with their own real ids/races/sexes/
locations, Guerin's own 9-army roster at the Falkland Sea (exact
`ArmyType`/`Quality` match against the letter's own "Normal Quality"
column -- confirming `GWArmyRecord.quality`/`ArmyState.quality` store
the base, unmodified Quality, not the letter's separately-tracked
"Modified Quality"), and province ownership (Falkland Sea, Ark Royal Sea
-> kingdom 1; Balearic Sea -> unowned) all match the real `SE3__T4.K1`
letter exactly. See `tests/test_gw3_t5_end_to_end.py` for the full,
letter-quoted assertions.

**Phase 342 addendum -- the world header's own 33 values, all decoded,
from a genuinely new source: a static reverse engineering of
`AKGEN.EXE` itself.** Every earlier phase in this module derived its
findings by testing hypotheses against real letters and real `GW3`
files -- inference, not access to the original engine's own compiled
logic. Phase 342 works from a direct disassembly of the original
world-generator executable (Turbo Pascal 6.0, DOS MZ, 1990), which
names every one of the header's 33 fields by its own Pascal data-
segment address and the code that reads/writes it -- not a guess, the
actual compiled program. Every field was then re-verified against all
12 real `GW3__T1`-`GW3__T12` files, not just asserted from the
disassembly: `army_count` (field 2) matches this project's own earlier,
independently-observed "218 to 345" growth across the 12 turns exactly;
`game_turn` (field 3) matches 1-12 exactly; `due_day`/`due_month`/
`due_year` (fields 14-16) match this module's own earlier Phase 318
calendar finding exactly (`19/12/2006` at `T1` through `25/5/2007` at
`T12`); `feature_count` (field 7) matches Block A's own confirmed
128-row count (Phase 316/341) on every turn.

`GWHeader`/`parse_gw_header()` expose all 33 fields. Fields 1-23 are
always present; fields 24-33 are only present when `header_revision`
(field 19) is greater than 17 -- every real file in this project's own
corpus reads `header_revision == 30`, so all ten extended fields are
populated in practice, but the parser still models the legacy case
(`None` for all ten) rather than assuming it never occurs. `game_type`
(field 22) is modeled as a new `GameType` enum (`TRIAL`, `NORMAL`,
`EUROPE`, `EARTH`, `VALHALLA`, `ARCANES`) -- every real file in this
project's own corpus reads `NORMAL`.

Two fields deserve a direct callout because they overturn this
project's own prior guesses rather than just filling a gap: field 22
was floated in an earlier phase as a possible "capacity selector" --
the disassembly identifies it directly as the Pascal `gametyp` enum
instead, unrelated to leader/army capacity. Field 31
(`compatibility_revision_31`) is more than a bare "armies version"
label -- besides gating Block B's own 10th field
(`GWArmyRecord.raw_field10`, Phase 335), it also triggers a legacy
leader/province migration before being normalized to `2`.

This is the first of several planned phases mining the same static
reverse-engineering source (a leader/King record extension, corrected
Block A field names, and an office/title block parser are queued
next) -- see `ak_engine/README.md`'s own Phase 342 entry for the
source material's full scope and this project's own priority order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.feature import FeatureType
from ak_engine.models.game_type import GameType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.parser.errors import K1ParseError
from ak_engine.turn.combat import Quality

_PROVINCE_HEADER_RE = re.compile(r"^(\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$")

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


# Phase 556: `termod`/`effects_bitmask`'s own bit-level meaning --
# `AKGEN_reverse_engineering_report (5).md` SS73.2 (machine-verified),
# closing the gap Phase 373's own `GWProvinceRecord.effects_bitmask`
# docstring left as "still undeciphered". Single-bit flags plus two
# 4-bit nibbles (`Plague_Eff`/`Illus_Eff`, presumably an effect-strength
# or turns-remaining level, not further decoded by the source) -- see
# `GWProvinceRecord`'s own decode properties below for the bit layout.
TERMOD_PART_EFF = 0x0001
TERMOD_BLESS_EFF = 0x0002
TERMOD_FLOOD_EFF = 0x0004
TERMOD_QUAKE_EFF = 0x0008
TERMOD_PLAGUE_EFF_MASK = 0x00F0
TERMOD_ILLUS_EFF_MASK = 0x0F00
TERMOD_ILLUS_EXP = 0x0800
TERMOD_FOG_EFF = 0x1000
TERMOD_RAID_EFF = 0x2000


class GWParseError(K1ParseError):
    """Raised when a world file doesn't match the expected shape."""


@dataclass(slots=True)
class GWProvinceRecord:
    """Phase 373 addendum -- the header line's own 3rd and 5th tokens,
    long treated as an undeciphered discard (`Phase 340`) and a fixed
    `0` literal, are real Pascal fields after all, per a static
    reverse engineering of `AKGEN.EXE`
    (`gw_format.records.province.ordered_stats_storage`): the header
    line stores 6 real values, `ptax, pterr, termod, prace, pex, pt2`
    (`tax, terrain, effects_bitmask, race, exploitation_percent,
    alternate_terrain`) -- not 4 real fields flanked by two structural
    anchors. `effects_bitmask` is exactly Phase 340's own "undeciphered
    per-province bitmask" (`termod`) -- **Phase 556**: its own bit-level
    meaning is now decoded too (`AKGEN_reverse_engineering_report
    (5).md` SS73.2, machine-verified) via the `TERMOD_*` module
    constants and this class's own decode properties below, closing the
    gap this docstring previously left open.
    `exploitation_percent` (`pex`) and `alternate_terrain` (`pt2`) were
    never even suspected to exist before this phase, since both read a
    constant value (`0`, `Terrain.NO_TERRAIN`) across every real
    `GW3__T1`-`GW3__T12` province row this project has ever checked --
    indistinguishable from a fixed anchor without the disassembly's own
    field list. `alternate_terrain` reuses this project's own `Terrain`
    enum directly: the real sentinel ordinal for "no alternate terrain"
    (`pt2 == 6`) is exactly `Terrain.NO_TERRAIN`'s own ordinal, already
    a real member.
    """

    name: str
    tax: int
    terrain: Terrain
    # Phase 373: `termod` -- a real, confirmed Pascal field (Phase 340's
    # own "undeciphered per-province bitmask", now correctly named and
    # stored instead of discarded). Phase 556: its own bit-level meaning
    # is now decoded too -- see the `TERMOD_*` module constants and this
    # class's own decode properties below.
    effects_bitmask: int
    race: Race
    # Phase 373: `pex` -- reads `0` for every province in this project's
    # own 12-turn corpus so far (no real nonzero example exists yet to
    # confirm the field's own effective range/rounding).
    exploitation_percent: int
    # Phase 373: `pt2` -- reads `Terrain.NO_TERRAIN` (the real "no
    # alternate terrain" sentinel) for every province in this project's
    # own 12-turn corpus so far.
    alternate_terrain: Terrain
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

    # Phase 556: `effects_bitmask` (`termod`) decode properties -- named
    # after the report's own `TERMOD_*` bit identifiers (SS73.2). These
    # read the parsed save-file bit pattern only; they are independent
    # of, and not wired into, this project's own live turn-processing
    # effect fields (`GameState.ProvinceState.terrain_override`/
    # `tax_modifier_percent`/`illusory_terrain`/`illusory_fog_active`/
    # plague fields), which are set directly by `turn/cast_execution.py`
    # during a running game and never read a parsed `GWProvinceRecord`.

    @property
    def part_sea_effect_active(self) -> bool:
        return bool(self.effects_bitmask & TERMOD_PART_EFF)

    @property
    def bless_effect_active(self) -> bool:
        return bool(self.effects_bitmask & TERMOD_BLESS_EFF)

    @property
    def flood_effect_active(self) -> bool:
        return bool(self.effects_bitmask & TERMOD_FLOOD_EFF)

    @property
    def quake_effect_active(self) -> bool:
        return bool(self.effects_bitmask & TERMOD_QUAKE_EFF)

    @property
    def plague_effect_level(self) -> int:
        return (self.effects_bitmask & TERMOD_PLAGUE_EFF_MASK) >> 4

    @property
    def illusion_effect_level(self) -> int:
        return (self.effects_bitmask & TERMOD_ILLUS_EFF_MASK) >> 8

    @property
    def illusion_effect_expanded(self) -> bool:
        return bool(self.effects_bitmask & TERMOD_ILLUS_EXP)

    @property
    def fog_effect_active(self) -> bool:
        return bool(self.effects_bitmask & TERMOD_FOG_EFF)

    @property
    def raid_effect_active(self) -> bool:
        return bool(self.effects_bitmask & TERMOD_RAID_EFF)


def parse_gw_world(path: Path) -> list[GWProvinceRecord]:
    """Parses every province record out of a world file.

    Scans the whole file for the province-header line's own fixed shape
    (6 space-separated integers: `"<tax> <terrain> <effects_bitmask>
    <race> <exploitation_percent> <alternate_terrain>"`) rather than
    assuming a fixed byte offset, since that shape is confirmed unique
    to the province block (a file-wide regex scan against every real
    `GW3__T1` through `GW3__T12` sample returns exactly 162 matches
    each -- the real, user-confirmed province count per world -- with
    no false positives from the file's other, differently-shaped record
    blocks).

    Phase 340 correction: the 3rd token (between terrain and race) was
    originally hard-coded as a literal `0`, since it happened to be `0`
    for every province in the `GW3__T1` sample this regex was first
    verified against. Real end-to-end validation against `GW3__T5`
    (Phase 340) proved that field is NOT always `0` -- it takes on
    several other observed values (48, 64, 80, 256, 512, 1280, 1536)
    across `GW3__T1`-`GW3__T12`, most likely a per-province bitmask
    (exploration-by-kingdom or similar) that changes as the game
    progresses, not a constant. Hard-coding it as `0` silently dropped
    any province whose bitmask happened to be nonzero at that turn --
    `GW3__T5` alone was missing 3 of its 162 real provinces (Katmai,
    Maplehaven, Khalturin) before this fix.

    Phase 373 correction: the same "hard-coded because it never varied
    in the sample checked" mistake applied to the header's own 5th and
    6th tokens too (`exploitation_percent`/`alternate_terrain`,
    real Pascal fields per `AKGEN.EXE` -- see `GWProvinceRecord`'s own
    docstring), not "0" and "6" structural anchors as the regex's own
    Phase 340 comment assumed. Loosening both to accept any integer and
    re-scanning all 12 real `GW3__T1`-`GW3__T12` files still yields
    exactly 162 matches per file with no false positives -- the row
    shape (6 space-separated integers on their own line, immediately
    preceded by a name line and followed by the 4-token recruiting-types
    line) stays unique in the file regardless of which specific values
    the trailing two tokens hold.
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
        tax_raw, terrain_raw, effects_raw, race_raw, exploitation_raw, alt_terrain_raw = match.groups()
        tax, terrain_ordinal, race_ordinal = int(tax_raw), int(terrain_raw), int(race_raw)
        effects_bitmask, exploitation_percent, alt_terrain_ordinal = (
            int(effects_raw),
            int(exploitation_raw),
            int(alt_terrain_raw),
        )
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
                effects_bitmask=effects_bitmask,
                race=Race(race_ordinal),
                exploitation_percent=exploitation_percent,
                alternate_terrain=Terrain(alt_terrain_ordinal),
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


# A leader record's own skill-list line is 30 tokens (Hero) or 60 (King,
# doubled) -- Phase 324/325.
_LEADER_SKILL_LIST_LENGTHS = (30, 60)


@dataclass(slots=True)
class GWLeaderRecord:
    """One King's or Hero's own record from the kingdom/leader header block
    that precedes the province block -- see the module docstring's Phase
    316-330 addenda for the full, evidence-based field derivation.

    ``kingdom_id`` is the kingdom this leader currently serves:

    - For a **Hero**, decoded directly from the header's own Liege field
      (Phase 325/327, confirmed 27-for-27 against real letter rosters):
      the owning King's own id, or ``None`` for an independent Hero
      (the ``255`` sentinel).
    - For a **King**, a King's own header always reads Liege ``255``
      (no liege above him) -- it cannot supply his own kingdom's id.
      Instead this uses the King-shaped records' own **file order**:
      the Nth King-shaped record encountered (0-indexed) is Kingdom N.
      Confirmed 8-for-8 against every King whose real id was already
      established from `SE3__T1.Kx` letters (Phase 319/326): Bradipo I
      (0-indexed position 2) = `#2`; Kwoth (position 3) = `#3`; Hokuto
      (position 4) = `#4`; Prometeo (position 5) = `#5`; Kahn (position
      6) = `#6`; Giovanna d'Arco (position 7) = `#7`; Circe (position 8)
      = `#8`; Agesilao (position 9) = `#9` -- every one of these 8 Kings
      matches its own 0-indexed file position exactly, strongly
      suggesting `GW3` simply stores kingdoms in id order starting from
      `#0` (Babba Sissoko, position 0) and `#1` (Uga-Buga Makumb,
      position 1) -- both consistent with, though not independently
      confirmed against, real letter data the way the other 8 are.

    **Phase 343 addendum -- the remaining 15 of the status line's own 22
    real values, from the same `AKGEN.EXE` static reverse engineering
    Phase 342 already draws on (see the module docstring's own Phase
    342 addendum for the source and its confidence level).** Every
    field below is named directly from the disassembly (Pascal field
    name, data-segment address, and the code that reads/writes it), not
    inferred from letters -- re-verified where the real `GW3__T1..T12`
    corpus offers a way to (e.g. `known_by_kings_mask` reads exactly
    `1023` (`2**10 - 1`) for all 10 Kings in this project's own 10-King
    corpus, exactly matching the disassembly's own "Kings start with
    every bit set" claim).

    - `birth_coord`: where this leader started the game. Matches this
      leader's own current `coord` for exactly 79 of `GW3__T1`'s own
      100 leaders (every King, plus every Hero who governs a province)
      -- expected, since nobody's moved yet at world creation. The
      other 21 all read a `birth_x` far outside any plausible map
      coordinate (`32`-`49`, past even the wider `0..29` compiled X
      range) except one (`Kitralus`, in-bounds but still not matching
      current position). 21 is exactly `2*K + 1` for this 10-King game
      (`K = 10`) -- the same reserve this module's own Phase 342
      addendum's world-generation section describes for each King's own
      two unlanded "companions" plus one further reserved roster slot,
      none of whom ever become a province's own governor. This is a
      real, structural correlation (companions never received a
      meaningful birth coordinate), not a parsing bug -- but the exact
      out-of-range values themselves aren't independently decoded here.
    - `original_liege_raw`: the Liege field's own *original* value
      (`lliege`/`liege0` are two separate Pascal fields, confirmed by
      the disassembly's own `liege0 := lliege` copy) -- always equal to
      the current Liege in this project's own corpus so far, but kept
      distinct rather than assumed identical, since a Hero switching
      allegiance is exactly the kind of event that would diverge them.
      Same `255` = "no liege" sentinel encoding as `kingdom_id`'s own
      raw Liege field, deliberately not converted to `None` here since
      no real-corpus example of divergence exists yet to interpret.
    - `hiring_turn`: the effective game turn a non-King leader was
      hired -- `0` for every leader in `GW3__T1` (nobody hired yet) and
      confirmed by the disassembly's own longitudinal note to track
      real hiring events turn over turn thereafter (not modeled by this
      parser beyond exposing the raw value).
    - `general_merit`/`admiral_merit`/`defender_merit`: this leader's
      own cumulative Imperial Office merit for Marshal/Admiral/Defender
      -- directly the missing data this project's own Phase 137
      research needed and didn't have a parser for.
    - `feature_discoveries`/`discovery_points`/`white_magic_service_
      points`: cumulative Imperial Office merit for Chancellor
      (features + Sage discoveries) and Priest (White Magic service).
    - `experience_progress`: a `0..99` fractional accumulator toward
      this leader's next ability increase (confirmed always nonzero and
      broadly changing turn over turn in the real 12-turn corpus).
    - `sex_raw`: the disassembly's own `sex` field (word storage) --
      reads `0` for all 100 leaders in every real file checked so far,
      including confirmed-female Heroes (Tao-Li, Dracona), so this
      field is *not* what actually determines a character's displayed
      sex under normal play (that's a separate, not-yet-parsed
      leader-id-band default the disassembly describes) -- kept raw
      rather than wired to `models.sex.Sex` since no real example of a
      nonzero value exists yet to confirm which value means which sex.
    - `sex_override_flag`: a moderator-toggled boolean that inverts a
      non-King leader's own default sex -- confirmed real and rare
      (2 of 1200 real Phase-342-source records) but never observed in
      this project's own committed `GW3__T1` fixture.
    - `unpaid_blackmail_penalty_exponent`: confirmed real (an unpaid-
      blackmail counter that halves the next demand each time it's
      incremented) but always `0` in this project's own corpus (no
      unpaid blackmail ever occurs in the available real games).
    - `known_by_kings_mask`: a bitmask of which Kingdoms know this
      leader -- Kings themselves always start with every bit set
      (`1023` for 10 Kings), confirmed exactly in this project's own
      corpus.
    """

    name: str
    is_king: bool
    race: Race
    alignment: Alignment
    temper: Temper
    # 0=Dead, 1=Hired, 2=Mercenary (Phase 325, matching
    # `models/monster.py MonsterEngagementState`'s first three members) --
    # kept as a raw int since whether leaders literally reuse that
    # monster-specific enum is unconfirmed.
    condition: int
    coord: HexCoord
    skills: SkillTable
    kingdom_id: int | None
    birth_coord: HexCoord
    original_liege_raw: int
    hiring_turn: int
    general_merit: int
    admiral_merit: int
    defender_merit: int
    feature_discoveries: int
    discovery_points: int
    white_magic_service_points: int
    experience_progress: int
    sex_raw: int
    sex_override_flag: bool
    unpaid_blackmail_penalty_exponent: int
    known_by_kings_mask: int


def _all_int(tokens: list[str]) -> bool:
    try:
        for token in tokens:
            int(token)
    except ValueError:
        return False
    return True


def parse_gw_leaders(path: Path) -> list[GWLeaderRecord]:
    """Parses every King's and Hero's own record out of a world file's
    kingdom/leader header block (before the province block).

    Scans for the leader-record shape itself (a name line, immediately
    followed by a 30- or 60-token all-integer skill-list line, immediately
    followed by a 25-token all-integer header line) rather than assuming a
    fixed byte offset -- the same "confirmed unique, no false positives"
    approach `parse_gw_world`'s own docstring already uses for the
    province block. Against the real `GW3__T1` fixture this finds exactly
    100 records (10 Kings, 90 Heroes), every name a real character name --
    no false positives from the file's differently-shaped blocks (the
    kingdom-level 33-field header, the per-leader ``"Action Plans:"``
    phase dumps, the King-only trailing ~128-token dynamic block).
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    records: list[GWLeaderRecord] = []
    kingdom_index = 0
    i = 0
    while i < len(lines) - 2:
        skill_tokens = lines[i + 1].split()
        if len(skill_tokens) not in _LEADER_SKILL_LIST_LENGTHS or not _all_int(skill_tokens):
            i += 1
            continue

        header_tokens = lines[i + 2].split()
        if len(header_tokens) != 25 or not _all_int(header_tokens):
            i += 1
            continue

        name = lines[i].strip()
        if not name or name[0].isdigit() or name[0] == "-":
            i += 1
            continue

        is_king = len(skill_tokens) == 60
        record = _build_leader_record(name, is_king, skill_tokens, header_tokens, kingdom_index, i)
        if is_king:
            kingdom_index += 1
        records.append(record)
        i += 1

    return records


def _build_leader_record(
    name: str,
    is_king: bool,
    skill_tokens: list[str],
    header_tokens: list[str],
    kingdom_index: int,
    line_number: int,
) -> GWLeaderRecord:
    values = [int(token) for token in header_tokens]
    x, y, race_ordinal = values[0], values[1], values[2]
    sex_raw = values[3]
    liege_raw = values[4]
    original_liege_raw = values[5]
    condition = values[6]
    birth_x, birth_y = values[7], values[8]
    alignment_ordinal = values[9]
    temper_ordinal = values[10]
    hiring_turn = values[11]
    general_merit, admiral_merit, defender_merit = values[12], values[13], values[14]
    feature_discoveries, discovery_points, white_magic_service_points = values[15], values[16], values[17]
    experience_progress = values[18]
    sex_override_flag = values[19] == 1
    unpaid_blackmail_penalty_exponent = values[20]
    known_by_kings_mask = values[21]

    if race_ordinal not in {member.value for member in Race}:
        raise GWParseError(
            f"unrecognized Race ordinal {race_ordinal} on a leader header line",
            line_number=line_number + 3,
            line=" ".join(header_tokens),
        )
    if not 0 <= alignment_ordinal < len(ALIGNMENT_BY_ORDINAL):
        raise GWParseError(
            f"unrecognized Alignment ordinal {alignment_ordinal} on a leader header line",
            line_number=line_number + 3,
            line=" ".join(header_tokens),
        )
    if temper_ordinal not in {member.value for member in Temper}:
        raise GWParseError(
            f"unrecognized Temper ordinal {temper_ordinal} on a leader header line",
            line_number=line_number + 3,
            line=" ".join(header_tokens),
        )

    return GWLeaderRecord(
        name=name,
        is_king=is_king,
        race=Race(race_ordinal),
        alignment=ALIGNMENT_BY_ORDINAL[alignment_ordinal],
        temper=Temper(temper_ordinal),
        condition=condition,
        coord=HexCoord(x, y),
        skills=SkillTable(raw_values=[int(token) for token in skill_tokens[:30]]),
        kingdom_id=kingdom_index if is_king else (None if liege_raw == 255 else liege_raw),
        birth_coord=HexCoord(birth_x, birth_y),
        original_liege_raw=original_liege_raw,
        hiring_turn=hiring_turn,
        general_merit=general_merit,
        admiral_merit=admiral_merit,
        defender_merit=defender_merit,
        feature_discoveries=feature_discoveries,
        discovery_points=discovery_points,
        white_magic_service_points=white_magic_service_points,
        experience_progress=experience_progress,
        sex_raw=sex_raw,
        sex_override_flag=sex_override_flag,
        unpaid_blackmail_penalty_exponent=unpaid_blackmail_penalty_exponent,
        known_by_kings_mask=known_by_kings_mask,
    )


# Phase 380 -- `AKGEN_embedded_catalogs.json.txt gw_format.records.
# king_extension` (a real static disassembly of `AKGEN.EXE`/`AK.EXE`)
# names, for the first time, every field of the King-only "M"/"F" line
# this module's own Phase 320/322/323 addenda (see `GWLeaderRecord`'s
# docstring above) had already found but left entirely unparsed --
# confirmed "genuine per-leader-per-turn tracked state" (Phase 322) of
# unknown shape until now. `KingSendMethod`'s real Pascal name is
# `ksendmeth`.
class KingSendMethod(Enum):
    FORUM = -1
    COMPUSERVE = 0
    GENIE = 1
    DISK = 2
    PRINTOUT = 3
    BOTH = 4


# `standby` -- a King's own standing request to be replaced.
class KingStandbyState(Enum):
    NO = 0
    INTERESTED = 1
    WAITING = 2
    START = 3
    RISING = 4


# `kallst` -- one King's own stored relation toward another King.
class DiplomaticRelation(Enum):
    ENEMY = 0
    NEUTRAL = 1
    ALLIED = 2
    TEAMED = 3


@dataclass(slots=True)
class GWKingExtension:
    """A King's own trailing dynamic-state line (the real shape of the
    "M"/"F" line Phase 320/322/323 found but never parsed) -- see this
    module's own Phase 380 addendum, right above `KingSendMethod`, for
    the full sourcing and the empirical verification against both real
    fixtures (`GW3__T1`/`GW3__T5`) that confirmed every field below,
    positionally, before this dataclass was written.

    `is_male` is Phase 320's own already-confirmed Gender field (`M`/
    `F`) -- included here now that this line is being parsed at all,
    even though nothing yet consumes it. `diplomatic_relations` has one
    entry per King in the game (`GWHeader.king_count`-long, king-id
    order, this King's own view of each King including itself).
    `discovered` is this King's own Kingdom's real `Discovery` set --
    the JSON's own 64-boolean `dknow` range is an exact match for
    `models/discovery.py Discovery`'s own 64 members (ordinals 0-63),
    confirmed by direct count before this field was added. The 5
    trailing `trailing_compatibility_zeros` are a literal Pascal short
    string (`" 0 0 0 0 0"`) the JSON calls certain to always be zero --
    stored rather than assumed so `write_gw_king_extension()` can
    reconstruct the line exactly either way.

    **`title_prefix`/`title_suffix`/`player_name`** (`AKGEN_reverse_
    engineering_report (5).md` SS71.2): three short-string lines
    immediately following the gender + numeric tail above, one King
    title/epithet/real-player-name -- e.g. `"Lord"` / `"Master of the
    s"` (a real, independently-reproduced fixed-width truncation, not a
    parsing artifact -- see this module's own Phase 318 addendum) /
    `"Andrea Ferrigno"` for `GW3__T1`'s own Babba Sissoko. Confirmed
    dynamic (Babba Sissoko's own `title_suffix` reads `"Master orango"`
    by `GW3__T5`, four turns later) -- not a static per-King template.
    Can be empty strings (7 of `GW3__T1`'s own 10 Kings have blank
    `title_prefix`/`title_suffix`), never absent -- the line itself
    always exists, even when its own content is `""`. Purely cosmetic
    text this project has no report composer or `LeaderState` field to
    render yet -- captured here as structured, round-trippable data
    (closing a real, previously undone parsing gap), not wired any
    further.
    """

    is_male: bool
    treasury: int
    alliance_requests_bitmask: int
    break_treaty_requests_bitmask: int
    account_number: int
    player_mode: int
    met_kings_bitmask: int
    send_method: KingSendMethod
    election_request_or_previous_choice: int
    payment_percent: int
    miscellaneous_fee: int
    turn_funds_received: int
    consecutive_missed_turns: int
    standby_state: KingStandbyState
    standby_max_percent: int
    prize_credit: int
    raw_administrative_flag: int
    moves_read_success: bool
    order_interpreter_version: int
    diplomatic_relations: tuple[DiplomaticRelation, ...]
    discovered: frozenset[Discovery]
    valhalla_visit_count: int
    king_information_flags: int
    disk_delivery_flags: int
    king_power_or_votes_cast: int
    moves_insurance: bool
    team_state: int
    active_blackmailer_king_id: int | None
    pending_blackmailer_king_id: int | None
    power_percent: int
    trailing_compatibility_zeros: tuple[int, int, int, int, int]
    title_prefix: str
    title_suffix: str
    player_name: str


_KING_SEND_METHOD_VALUES = {member.value for member in KingSendMethod}
_KING_STANDBY_STATE_VALUES = {member.value for member in KingStandbyState}
_DIPLOMATIC_RELATION_VALUES = {member.value for member in DiplomaticRelation}


def parse_gw_king_extensions(path: Path) -> list[GWKingExtension]:
    """Every King's own trailing dynamic-state line -- see
    `GWKingExtension`'s own docstring for the full field mapping.

    Reuses `parse_gw_leaders`'s own King-detection shape (a name line,
    then a 60-token doubled skill list, then a 25-token header line --
    only Kings carry the doubled list) to find each King's own record,
    then reads the very next line, which must be `"M"` or `"F"`
    followed by exactly `96 + GWHeader.king_count` more integers (the
    JSON's own `numeric_count_rule`) -- confirmed exactly 106 tokens for
    the real `GW3__T1`/`GW3__T5` fixtures (`king_count = 10`), then the
    3 short-string lines right after it (title/epithet/player name, SS71.2
    -- see `GWKingExtension`'s own docstring), raising if the file ends
    before all 3 are present (a real, always-present triplet, even when
    individually blank).
    """

    header = parse_gw_header(path)
    king_count = header.king_count
    expected_numeric_count = 96 + king_count

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    records: list[GWKingExtension] = []
    i = 0
    while i < len(lines) - 2:
        skill_tokens = lines[i + 1].split()
        if len(skill_tokens) != 60 or not _all_int(skill_tokens):
            i += 1
            continue

        header_tokens = lines[i + 2].split()
        if len(header_tokens) != 25 or not _all_int(header_tokens):
            i += 1
            continue

        name = lines[i].strip()
        if not name or name[0].isdigit() or name[0] == "-":
            i += 1
            continue

        m_line = lines[i + 3] if i + 3 < len(lines) else ""
        m_tokens = m_line.split()
        if (
            len(m_tokens) != expected_numeric_count + 1
            or m_tokens[0] not in ("M", "F")
            or not _all_int(m_tokens[1:])
        ):
            raise GWParseError(
                f"expected a King's own gender + {expected_numeric_count}-integer "
                "extension line here",
                line_number=i + 4,
                line=m_line,
            )

        if i + 6 >= len(lines):
            raise GWParseError(
                "expected 3 more lines (title prefix/suffix, player name) after a King's own extension line",
                line_number=i + 5,
                line=m_line,
            )
        title_prefix = lines[i + 4].strip()
        title_suffix = lines[i + 5].strip()
        player_name = lines[i + 6].strip()

        records.append(
            _build_king_extension(
                m_tokens, king_count, title_prefix, title_suffix, player_name, line_number=i + 4
            )
        )
        i += 1

    return records


def _build_king_extension(
    m_tokens: list[str],
    king_count: int,
    title_prefix: str,
    title_suffix: str,
    player_name: str,
    line_number: int,
) -> GWKingExtension:
    is_male = m_tokens[0] == "M"
    values = [int(token) for token in m_tokens[1:]]

    send_method_raw = values[6]
    standby_state_raw = values[12]
    relation_start = 18
    relation_end = relation_start + king_count
    discovery_start = relation_end
    discovery_end = discovery_start + 64
    b = discovery_end

    if send_method_raw not in _KING_SEND_METHOD_VALUES:
        raise GWParseError(
            f"unrecognized King send-method ordinal {send_method_raw}",
            line_number=line_number,
            line=" ".join(m_tokens),
        )
    if standby_state_raw not in _KING_STANDBY_STATE_VALUES:
        raise GWParseError(
            f"unrecognized King standby-state ordinal {standby_state_raw}",
            line_number=line_number,
            line=" ".join(m_tokens),
        )
    relation_tokens = values[relation_start:relation_end]
    for relation_raw in relation_tokens:
        if relation_raw not in _DIPLOMATIC_RELATION_VALUES:
            raise GWParseError(
                f"unrecognized diplomatic-relation ordinal {relation_raw}",
                line_number=line_number,
                line=" ".join(m_tokens),
            )

    active_blackmailer_raw = values[b + 6]
    pending_blackmailer_raw = values[b + 7]

    return GWKingExtension(
        is_male=is_male,
        treasury=values[0],
        alliance_requests_bitmask=values[1],
        break_treaty_requests_bitmask=values[2],
        account_number=values[3],
        player_mode=values[4],
        met_kings_bitmask=values[5],
        send_method=KingSendMethod(send_method_raw),
        election_request_or_previous_choice=values[7],
        payment_percent=values[8],
        miscellaneous_fee=values[9],
        turn_funds_received=values[10],
        consecutive_missed_turns=values[11],
        standby_state=KingStandbyState(standby_state_raw),
        standby_max_percent=values[13],
        prize_credit=values[14],
        raw_administrative_flag=values[15],
        moves_read_success=values[16] == 1,
        order_interpreter_version=values[17],
        diplomatic_relations=tuple(DiplomaticRelation(raw) for raw in relation_tokens),
        discovered=frozenset(Discovery(index) for index, flag in enumerate(values[discovery_start:discovery_end]) if flag),
        valhalla_visit_count=values[b + 0],
        king_information_flags=values[b + 1],
        disk_delivery_flags=values[b + 2],
        king_power_or_votes_cast=values[b + 3],
        moves_insurance=values[b + 4] == 1,
        team_state=values[b + 5],
        active_blackmailer_king_id=None if active_blackmailer_raw == 255 else active_blackmailer_raw,
        pending_blackmailer_king_id=None if pending_blackmailer_raw == 255 else pending_blackmailer_raw,
        power_percent=values[b + 8],
        trailing_compatibility_zeros=(
            values[b + 9],
            values[b + 10],
            values[b + 11],
            values[b + 12],
            values[b + 13],
        ),
        title_prefix=title_prefix,
        title_suffix=title_suffix,
        player_name=player_name,
    )


@dataclass(slots=True)
class GWArmyRecord:
    """One army's own row from Block B, the per-army block that follows
    the province block and Block A (`GWFeatureRecord`, mostly decoded as
    of Phase 341) -- see the module docstring's Phase 316/317/331-337
    addenda for the field-by-field empirical derivation that got this
    record type to 6 of its 10 fields.

    **Phase 376 addendum -- the 3 remaining fields (7-10) are real,
    named Pascal fields, not permanently undeciphered.** A static
    reverse engineering of `AKGEN.EXE` (`AKGEN_embedded_catalogs.json.txt`
    `gw_format.records.army.ordered_storage`) names every one of them
    directly, independent of this project's own empirical Phase 331-337
    work:

    - `state` (Pascal `astate`): a real 8-value engagement/state enum,
      not just the 2 values (`MERCENARY`=2, `ZOMBOID`=3) Phase 332/337
      already isolated as `is_mercenary`/`is_skeletal` -- the other 6
      values (`DEAD`=0, `HIRED`=1, `BOLD`=4, `SOLD`=5, `LOSER`=6,
      `CALM`=7) are exactly `models/monster.py MonsterEngagementState`'s
      own already-existing 8 members, in the same 0-7 order, confirmed
      by name in the disassembly's own `state_enum` table. Only
      `MERCENARY`/`ZOMBOID` (and, by the unled-row structural split
      Phase 332/333 already found, plausibly `HIRED`/`DEAD`) have real
      letter-text cross-checks; `BOLD`/`SOLD`/`LOSER`/`CALM` are typed
      here on the disassembly's own authority, not independently
      confirmed against a real fixture yet.
    - `movement_points` (Pascal `AMP`, "certain" confidence): a signed
      byte, this army's own current movement points.
    - `death_or_transformation_marker` (Pascal `adie`, "certain_as_role"):
      the disassembly's own observed role is that `250` triggers
      conversion to Weres/Werefolk, and other values are death-context
      codes including a `251` sentinel -- individual non-`250` codes
      aren't enumerated by the source, so this stays a raw `int` rather
      than an enum.
    - `plague_survival_count` ("certain_as_role"): positive values
      prevent a future plague death and allow a quality drop; the
      source's own observed role says it's incremented after surviving
      plague. Gated by header field 31 -- already parsed by this module
      as `GWHeader.compatibility_revision_31` -- so a legacy (23-token
      header) file may not carry this meaningfully; kept as a raw `int`
      with no gating logic here, since no legacy-header real fixture
      exists in this project's own corpus to test against.
    """

    # The commanding Hero's/King's own leader id, or `None` for the
    # `255` "under the garrison commander" unled sentinel (Phase 317).
    commanded_by_leader_id: int | None
    coord: HexCoord
    race: Race
    # `None` for the real "no type" sentinel ordinal (15) -- never
    # observed in Block B itself so far, but kept nullable to match
    # `MOD_PAT_ORDINAL_TO_ARMY_TYPE`'s own real shape.
    army_type: ArmyType | None
    quality: Quality
    # Phase 376: the real `astate` enum -- see docstring above.
    state: MonsterEngagementState
    # `True` only for the confirmed Skeletal-army marker (Phase 332,
    # `state is MonsterEngagementState.ZOMBOID`).
    is_skeletal: bool
    # `True` only for the confirmed "independent mercenary, available
    # to Recruit" marker (Phase 337, `state is MonsterEngagementState.
    # MERCENARY`) -- 85 of 85 real letter cross-checks matched, zero
    # exceptions.
    is_mercenary: bool
    movement_points: int
    death_or_transformation_marker: int
    plague_survival_count: int


def parse_gw_armies(path: Path) -> list[GWArmyRecord]:
    """Parses every army record out of a world file's own Block B.

    Locates Block B the same way `parse_gw_world`/`parse_gw_leaders`
    locate their own blocks: scan the whole file for the row's own
    fixed shape (exactly 10 space-separated integers) and take the one
    contiguous run of such lines. Verified against all 12 real
    `GW3__Tn` samples that this run is always the single, unambiguous
    one in the entire file -- no second run of any length ever appears
    in any of the 12 turns -- so no byte-offset or marker-line
    assumption is needed, the same "confirmed unique, no false
    positives" basis the sibling parsers already rely on.
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    candidate_indices = []
    for i, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) == 10 and _all_int(tokens):
            candidate_indices.append(i)
    if not candidate_indices:
        raise GWParseError("no 10-token Block B rows found in this world file", line_number=1, line="")

    runs: list[list[int]] = [[candidate_indices[0]]]
    for idx in candidate_indices[1:]:
        if idx == runs[-1][-1] + 1:
            runs[-1].append(idx)
        else:
            runs.append([idx])
    block_b = max(runs, key=len)

    records: list[GWArmyRecord] = []
    for line_index in block_b:
        values = [int(token) for token in lines[line_index].split()]
        (
            leader_id,
            x,
            y,
            race_ordinal,
            army_type_ordinal,
            quality_ordinal,
            state_ordinal,
            movement_points,
            death_or_transformation_marker,
            plague_survival_count,
        ) = values

        if race_ordinal not in {member.value for member in Race}:
            raise GWParseError(
                f"unrecognized Race ordinal {race_ordinal} on a Block B army row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        if army_type_ordinal not in MOD_PAT_ORDINAL_TO_ARMY_TYPE:
            raise GWParseError(
                f"unrecognized ArmyType ordinal {army_type_ordinal} on a Block B army row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        if quality_ordinal not in {member.value for member in Quality}:
            raise GWParseError(
                f"unrecognized Quality ordinal {quality_ordinal} on a Block B army row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        if state_ordinal not in {member.value for member in MonsterEngagementState}:
            raise GWParseError(
                f"unrecognized MonsterEngagementState ordinal {state_ordinal} on a Block B army row",
                line_number=line_index + 1,
                line=lines[line_index],
            )

        state = MonsterEngagementState(state_ordinal)
        records.append(
            GWArmyRecord(
                commanded_by_leader_id=None if leader_id == 255 else leader_id,
                coord=HexCoord(x, y),
                race=Race(race_ordinal),
                army_type=MOD_PAT_ORDINAL_TO_ARMY_TYPE[army_type_ordinal],
                quality=Quality(quality_ordinal),
                state=state,
                is_skeletal=state is MonsterEngagementState.ZOMBOID,
                is_mercenary=state is MonsterEngagementState.MERCENARY,
                movement_points=movement_points,
                death_or_transformation_marker=death_or_transformation_marker,
                plague_survival_count=plague_survival_count,
            )
        )

    return records


@dataclass(slots=True)
class GWFeatureRecord:
    """One Feature instance's own row from Block A, the 128-row block
    that precedes Block B in a world file -- see the module docstring's
    Phase 316/340 addenda for the full, evidence-based field derivation.

    Confirmed 14-for-14, zero exceptions, cross-checking every Feature
    named in 8 real provinces' own ADVENTURE-section letters (Dolphin,
    Ngara, Jerbilia, Birchwood, Pearlgate, Hollabrand, the Jellyfish
    Sea) against `GW3__T1`'s own Block A rows at that same coordinate:
    both the guarding ``Monster`` and the ``FeatureType`` match exactly
    every single time, and the row *count* per coordinate matches the
    real feature count there too (e.g. the Dolphin Sea's own 2 real
    features -> exactly 2 Block A rows at that coordinate).

    ``treasure`` is the guarded ``Treasure`` -- also confirmed, not
    guessed: the two "gold hoard" sentinels this project's own
    Phase 316 pass first read as meaningless filler (`67`/`68`, 64 of
    the 128 rows) are themselves real, valid ordinals
    (`Treasure.GOLD_HOARD_LARGE`/`GOLD_HOARD_HUGE`), and the two real
    *named* treasures spotted in the same letter sample (Birchwood's
    Temple/`Antennae of Psychic Blasting`, Pearlgate's Pyramid
    /`Reflector of Armies`) match their own `Treasure` ordinals exactly
    too.

    ``engagement_state`` is the guarding ``Monster``'s own
    ``MonsterEngagementState`` (Phase 130) -- constant `MERCENARY` for
    every one of `GW3__T1`'s 128 rows, but real, valid values
    (`DEAD`/`BOLD`/`CALM`) appear as the game progresses across
    `GW3__T2`-`GW3__T12`.

    **Phase 344 addendum -- the two fields this phase's own Phase 341
    treated as raw/unexplained (`raw_field5`, `raw_field8`) are real,
    named Pascal fields after all, per the same `AKGEN.EXE` static
    reverse engineering Phase 342/343 already draw on. What Phase 341
    called a discarded "trivial file-position counter" is real too --
    it's `trowner` (`treasure_owner_or_container`), not a throwaway
    value.** The confirmed field order is `fx, fy, treaslist, trowner,
    trcharges, fmonst, ftype, fdis, fstate` -- `treaslist`/`fmonst`/
    `ftype`/`fstate` are this record's own `treasure`/`monster`/
    `feature_type`/`engagement_state`, already correctly identified in
    Phase 341 by independent letter cross-checks.

    - `trowner_raw`: the Pascal source's own name is literally
      "treasure owner **or container**" -- acknowledging the same
      ambiguity this project already found empirically. For every
      still-unclaimed treasure in `GW3__T1`'s own 128 rows this reads
      `255 + row_number` == `256 + row_index` for a 0-indexed row
      (Phase 341's own "trivial counter" finding), *not* the plain
      `255` "no leader" sentinel every other real leader-id field in
      this module uses. `GW3__T5`'s fixture supplies the first two real
      *claimed*-treasure examples in this project's own corpus: of its
      128 rows, exactly 2 diverge from the `256 + row_index` sentinel
      (rows 15 and 111, reading `0` and `6`) and those are *exactly*
      the only 2 rows whose `engagement_state` is `DEAD` -- and `0`/`6`
      are themselves real, valid indices into that same file's own
      leader list, each landing on a King (`Babba Sissoko`/`Kahn`) of
      the matching `kingdom_id`. This is consistent with `trowner_raw`
      switching from the unclaimed-sentinel to the claiming leader's
      own (0-indexed) id once the guarding monster is killed -- but
      with only 2 real examples it's kept as a raw `int` rather than
      converted to `Optional[int]`, since a King index is a weak
      confirmation of a general "any leader can claim" rule.
    - `trcharges`: the treasure's own remaining charge count -- Phase
      341's own "stable `2`-`10` range, no correlation found" raw field
      is really this, an unsigned byte. Its own confirmed name doesn't
      make the specific `2`-`10` distribution self-explanatory (a
      magic item's own maximum charges presumably vary by item), so
      this parser exposes the count directly rather than guessing at a
      per-Treasure maximum.
    - `fdis_raw`: the Pascal source's own name is "discovery **or
      flags**" -- again ambiguous even at the source. Constant `0` on
      every one of `GW3__T1`'s 128 rows (and in fact every row in all
      12 real `GW3__T1`-`GW3__T12` turns checked), consistent with "no
      feature has been discovered by anyone yet" for a freshly
      generated world, but kept as a raw `word` rather than a `bool`
      since no real nonzero example exists yet to confirm that reading
      (word storage also suggests a bitmask, e.g. per-kingdom
      discovery flags, over a plain boolean).
    """

    coord: HexCoord
    treasure: Treasure
    monster: Monster
    feature_type: FeatureType
    engagement_state: MonsterEngagementState
    trowner_raw: int
    trcharges: int
    fdis_raw: int


def parse_gw_features(path: Path) -> list[GWFeatureRecord]:
    """Parses every Feature-instance record out of a world file's own
    Block A.

    Locates Block A the same way `parse_gw_world`/`parse_gw_leaders`/
    `parse_gw_armies` locate their own blocks: scan the whole file for
    the row's own fixed shape (exactly 9 space-separated integers) and
    take the one contiguous run of such lines. Verified against all 12
    real `GW3__Tn` samples that this run is always the single,
    unambiguous one in the entire file, always exactly 128 rows long --
    the same "confirmed unique, no false positives" basis every sibling
    parser in this module already relies on.
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    candidate_indices = []
    for i, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) == 9 and _all_int(tokens):
            candidate_indices.append(i)
    if not candidate_indices:
        raise GWParseError("no 9-token Block A rows found in this world file", line_number=1, line="")

    runs: list[list[int]] = [[candidate_indices[0]]]
    for idx in candidate_indices[1:]:
        if idx == runs[-1][-1] + 1:
            runs[-1].append(idx)
        else:
            runs.append([idx])
    block_a = max(runs, key=len)

    records: list[GWFeatureRecord] = []
    for line_index in block_a:
        values = [int(token) for token in lines[line_index].split()]
        x, y, treasure_ordinal, trowner_raw, trcharges, monster_ordinal, feature_type_ordinal, fdis_raw, engagement_ordinal = values

        if treasure_ordinal not in {member.value for member in Treasure}:
            raise GWParseError(
                f"unrecognized Treasure ordinal {treasure_ordinal} on a Block A feature row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        if monster_ordinal not in {member.value for member in Monster}:
            raise GWParseError(
                f"unrecognized Monster ordinal {monster_ordinal} on a Block A feature row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        if feature_type_ordinal not in {member.value for member in FeatureType}:
            raise GWParseError(
                f"unrecognized FeatureType ordinal {feature_type_ordinal} on a Block A feature row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        if engagement_ordinal not in {member.value for member in MonsterEngagementState}:
            raise GWParseError(
                f"unrecognized MonsterEngagementState ordinal {engagement_ordinal} on a Block A feature row",
                line_number=line_index + 1,
                line=lines[line_index],
            )

        records.append(
            GWFeatureRecord(
                coord=HexCoord(x, y),
                treasure=Treasure(treasure_ordinal),
                monster=Monster(monster_ordinal),
                feature_type=FeatureType(feature_type_ordinal),
                engagement_state=MonsterEngagementState(engagement_ordinal),
                trowner_raw=trowner_raw,
                trcharges=trcharges,
                fdis_raw=fdis_raw,
            )
        )

    return records


@dataclass(slots=True)
class GWTreasureOnlyRecord:
    """A "loose" treasure instance with no guarding Feature -- Phase 378,
    `AKGEN_embedded_catalogs.json.txt gw_format.records.treasure_only`
    (a real static disassembly of `AKGEN.EXE`/`AK.EXE`/`AK.OVR`): "fields
    3, 4 and 5 of the shared feature/treasure arrays" for `index_range
    feature_count through treasure_count - 1` -- the same underlying
    Pascal `treaslist`/`trowner`/`trcharges` arrays `GWFeatureRecord`
    already reads for its own first `feature_count` entries, but this
    record only ever carries those 3 of the 9 fields (no coordinate, no
    guarding Monster -- there's nothing there to guard the treasure, it
    isn't attached to any Feature at all).

    **This entire record type was previously misread as an "unresolved
    2-line structural boundary marker"** between Block A (`GWFeatureRecord`)
    and Block B (`GWArmyRecord`) -- this project's own earlier research
    (see the module docstring's Phase 316 addendum, `"0 255 0" / "35 99
    0"`) treated it as a fixed separator, since every real fixture this
    project owned at the time happened to show exactly 2 such lines.
    Cross-checking both real fixtures at once falsifies "fixed": `GW3__
    T1` has exactly 2 (`treasure_count - feature_count` = `130 - 128`),
    `GW3__T5` has exactly 4 (`132 - 128`) -- and `GW3__T5`'s own first and
    third rows are byte-identical to `GW3__T1`'s own two rows (`"0 255
    0"`, `"35 99 0"`, both real, valid `Treasure` ordinals -- `0` =
    `ABILITY_TACTICAL`, `35` = `WEAPON_1`/"Holy Sword"), while its own
    second and fourth rows (`"88 71 11"`, `"88 77 52"`, both `Treasure.
    QUEST_KILL_QUEST` = `88`) are new -- exactly the pattern of 2
    pre-existing unclaimed treasures persisting turn over turn plus 2
    freshly-generated ones, not a fixed marker at all.

    `owner_raw` mirrors `GWFeatureRecord.trowner_raw`'s own real ambiguity
    (the Pascal field's own name is literally "treasure owner **or
    container**") -- `255` is the real "unclaimed" sentinel (`GW3__T1`'s
    own first row), and a real, low id (`GW3__T1`'s own second row, `99`;
    `GW3__T5`'s own new rows, `71`/`77`) is a plausible claiming-leader id,
    consistent with `GWFeatureRecord.trowner_raw`'s own documented
    reading -- kept as a raw `int` for the same reason that field is: too
    few real examples to confirm which case applies when.
    """

    treasure: Treasure
    owner_raw: int
    charges: int


def parse_gw_treasures_only(path: Path) -> list[GWTreasureOnlyRecord]:
    """Parses the "loose" treasure block that immediately follows Block A
    (`GWFeatureRecord`, the confirmed 128-row run of 9-token lines) and
    immediately precedes Block B (`GWArmyRecord`) -- Phase 378.

    Unlike Block A/B (found by scanning for a unique row shape), a bare
    3-token line recurs incidentally elsewhere in a real world file (the
    same reason `parse_gw_offices`'s own office-merit block can't use a
    uniqueness scan either) -- so this locates Block A's own end the same
    way `parse_gw_features` does, then reads exactly `GWHeader.
    treasure_count - GWHeader.feature_count` further lines (the real
    Pascal `index_range`), each a 3-integer row.
    """

    header = parse_gw_header(path)
    count = header.treasure_count - header.feature_count

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    candidate_indices = []
    for i, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) == 9 and _all_int(tokens):
            candidate_indices.append(i)
    if not candidate_indices:
        raise GWParseError("no 9-token Block A rows found in this world file", line_number=1, line="")

    runs: list[list[int]] = [[candidate_indices[0]]]
    for idx in candidate_indices[1:]:
        if idx == runs[-1][-1] + 1:
            runs[-1].append(idx)
        else:
            runs.append([idx])
    block_a_end = max(runs, key=len)[-1]

    records: list[GWTreasureOnlyRecord] = []
    for line_index in range(block_a_end + 1, block_a_end + 1 + count):
        tokens = lines[line_index].split() if line_index < len(lines) else []
        if len(tokens) != 3 or not _all_int(tokens):
            raise GWParseError(
                "expected a 3-integer treasure-only row here",
                line_number=line_index + 1,
                line=lines[line_index] if line_index < len(lines) else "",
            )
        treasure_ordinal, owner_raw, charges = (int(token) for token in tokens)
        if treasure_ordinal not in {member.value for member in Treasure}:
            raise GWParseError(
                f"unrecognized Treasure ordinal {treasure_ordinal} on a treasure-only row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        records.append(GWTreasureOnlyRecord(treasure=Treasure(treasure_ordinal), owner_raw=owner_raw, charges=charges))

    return records


@dataclass(slots=True)
class GWHeader:
    """The world file's own 33-value header -- always its very first
    line. See the module docstring's Phase 342 addendum for the full,
    byte-level derivation: a static reverse engineering of AKGEN.EXE
    (not inference from real letters) identified every one of the 33
    fields by its own data-segment address and the Pascal code that
    reads/writes it, then the whole header was verified field-by-field
    against all 12 real `GW3__T1`-`GW3__T12` files (e.g. `army_count`
    matches this project's own earlier, independently-observed "218 to
    345" growth exactly; `game_turn` matches 1-12 exactly; `due_day`/
    `due_month`/`due_year` match the project's own earlier Phase 318
    calendar finding exactly).

    Fields 1-23 are always present. Fields 24-33 are only present when
    `header_revision > 17` -- AKGEN's own reader falls back to internal
    defaults for older saves lacking them; this parser leaves the
    corresponding attributes `None` in that case rather than guessing
    defaults it can't verify. Every real file in this project's own
    corpus has `header_revision == 30`, so all ten extended fields are
    always populated in practice.
    """

    king_count: int
    army_count: int
    game_turn: int
    # Initialized to -1; feeds a `game_turn`-modulo-3 selection with a
    # special case for `GameType.EARTH`. Real role beyond that is
    # unconfirmed -- kept raw rather than guessed.
    raw_04: int
    setup_fee_cents: int
    treasure_count: int
    feature_count: int
    map_left_x: int
    map_right_x: int
    map_top_y: int
    map_bottom_y: int
    game_version: int
    game_number: int
    due_day: int
    due_month: int
    due_year: int
    turn_length_days: int
    diplomacy_type: int
    header_revision: int
    original_turn: int
    turn_cost_cents: int
    game_type: GameType
    total_fees: int
    last_leader_index: int | None
    valhalla_alignment_rotation_mask: int | None
    visiting_king: int | None
    max_feature_index: int | None
    # First extra setup parameter; legacy administrative role, still
    # unnamed even in the static reverse engineering -- kept raw.
    setup_extra_1: int | None
    office_merit_record_count: int | None
    office_state_table_present: int | None
    # Gates Block B's own 10th field (`GWArmyRecord.raw_field10`,
    # Phase 335) and an unrelated legacy leader/province migration.
    compatibility_revision_31: int | None
    mine_write_flags: int | None
    misc_write_flags: int | None


def parse_gw_header(path: Path) -> GWHeader:
    """Parses a world file's own 33-value header, always its first
    line.

    Accepts a legacy 23-token line too (fields 24-33 absent, all
    reported as `None`) even though every real file in this project's
    own corpus writes the full 33 -- the module docstring's own Phase
    342 addendum documents this as a real, confirmed reader behavior,
    not a hypothetical.
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    first_line = text.splitlines()[0]
    tokens = first_line.split()
    if len(tokens) not in (23, 33) or not _all_int(tokens):
        raise GWParseError(
            "expected a 23- or 33-integer header line as the world file's first line",
            line_number=1,
            line=first_line,
        )

    values = [int(token) for token in tokens]
    game_type_ordinal = values[21]
    if game_type_ordinal not in {member.value for member in GameType}:
        raise GWParseError(
            f"unrecognized GameType ordinal {game_type_ordinal} in the world file header",
            line_number=1,
            line=first_line,
        )

    extended: list[int | None] = values[23:33] if len(values) == 33 else [None] * 10

    return GWHeader(
        king_count=values[0],
        army_count=values[1],
        game_turn=values[2],
        raw_04=values[3],
        setup_fee_cents=values[4],
        treasure_count=values[5],
        feature_count=values[6],
        map_left_x=values[7],
        map_right_x=values[8],
        map_top_y=values[9],
        map_bottom_y=values[10],
        game_version=values[11],
        game_number=values[12],
        due_day=values[13],
        due_month=values[14],
        due_year=values[15],
        turn_length_days=values[16],
        diplomacy_type=values[17],
        header_revision=values[18],
        original_turn=values[19],
        turn_cost_cents=values[20],
        game_type=GameType(game_type_ordinal),
        total_fees=values[22],
        last_leader_index=extended[0],
        valhalla_alignment_rotation_mask=extended[1],
        visiting_king=extended[2],
        max_feature_index=extended[3],
        setup_extra_1=extended[4],
        office_merit_record_count=extended[5],
        office_state_table_present=extended[6],
        compatibility_revision_31=extended[7],
        mine_write_flags=extended[8],
        misc_write_flags=extended[9],
    )


@dataclass(slots=True)
class GWOfficeMeritRecord:
    """One kingdom's own accumulated merit-points entry for a single
    Imperial/Royal office, from the variable-length office-merit-record
    block that immediately follows Block B (armies) -- see the module
    docstring's Phase 345 addendum. Confirmed via the same `AKGEN.EXE`
    static reverse engineering as Phase 342/343/344's own JSON source
    (`gw_format.records.office_merit`): 3 integers per line, `tityp,
    tildr, tipts` (`office_code`, `leader_or_army_id`, `merit_points`).
    Its own count is header field 29
    (`GWHeader.office_merit_record_count`), not inferred by scanning --
    `GW3__T1`'s freshly generated world has exactly 0 of these (no one
    has held an office yet), `GW3__T5`'s has 159, both matching the
    header's own count exactly. Every real `office_code` seen across
    both fixtures is a valid `Office` ordinal (0-51).

    `leader_or_army_id` is, per the source, either a leader id or an
    army id depending on `office_code`: 3 of the 52 office codes
    (`Office.AIR_FORCE`/`PRAETOR`/`FLAGSHIP` -- 38/45/47) are army
    offices, not leader offices, so this field's own real target type
    switches on `office_code` rather than being uniformly one or the
    other -- kept as a raw `int` rather than a leader/army union type.
    """

    office_code: Office
    leader_or_army_id: int
    merit_points: int


@dataclass(slots=True)
class GWOfficeStateEntry:
    """One office's own persistent state row, from the world file's
    final line -- a fixed 52-triplet (156-integer) table, one triplet
    per `Office` ordinal 0-51, always present right after the office-
    merit-record block. Confirmed via the same source's own
    `gw_format.records.office_state_entry`: `prevchar, knowit, <a
    literal 0>` (`previous_holder_raw`, `known_by_kings_mask`, and a
    third field this parser doesn't expose since every one of the real
    12-turn corpus's own 624 triplets reads a literal `0` there).

    `previous_holder_raw` uses the same `255` "nobody" sentinel this
    module's other leader-id fields already use -- confirmed: every
    office in `GW3__T1`'s freshly generated world reads exactly `255`
    here, since no one has ever held any office yet. `known_by_kings_
    mask` is a per-King bitmask, the same convention as
    `GWLeaderRecord.known_by_kings_mask` (Phase 343) -- `0` for every
    office in `GW3__T1`, real nonzero values (`2`, `256`, `513`, ...)
    once `GW3__T5`'s Kings have actually learned who holds what.
    """

    office: Office
    previous_holder_raw: int
    known_by_kings_mask: int


def parse_gw_offices(path: Path) -> tuple[list[GWOfficeMeritRecord], list[GWOfficeStateEntry]]:
    """Parses the office-merit-record block and the final office-state
    table out of a world file.

    Unlike Block A/B/features (found by scanning for a unique row
    shape), this block's own position is only found by *counting*:
    right after Block B's own army rows end (whichever contiguous run
    of 10-token rows is longest, the same rule `parse_gw_armies` uses),
    read exactly `GWHeader.office_merit_record_count` more lines --
    each must be exactly 3 tokens -- then the world file's own final
    line is the 156-token (52-triplet) office-state table. A pure
    uniqueness scan doesn't work here the way it does for Block A/B:
    unlike those blocks' own fixed 9-/10-token row shape, a bare
    3-token line shape recurs incidentally dozens of times elsewhere in
    a real world file (154 scattered singleton matches in `GW3__T1`
    alone, mostly leader/plan data that happens to tokenize to 3
    integers), so this parser leans on the header's own count and the
    file's own fixed block order instead.
    """

    header = parse_gw_header(path)
    if header.office_merit_record_count is None:
        raise GWParseError(
            "this world file's header has no office_merit_record_count (legacy 23-token header)",
            line_number=1,
            line="",
        )

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    candidate_indices = [i for i, line in enumerate(lines) if len(line.split()) == 10 and _all_int(line.split())]
    if not candidate_indices:
        raise GWParseError("no 10-token Block B rows found in this world file", line_number=1, line="")
    runs: list[list[int]] = [[candidate_indices[0]]]
    for idx in candidate_indices[1:]:
        if idx == runs[-1][-1] + 1:
            runs[-1].append(idx)
        else:
            runs.append([idx])
    block_b_end = max(runs, key=len)[-1]

    merit_start = block_b_end + 1
    merit_end = merit_start + header.office_merit_record_count

    merit_records: list[GWOfficeMeritRecord] = []
    for line_index in range(merit_start, merit_end):
        tokens = lines[line_index].split() if line_index < len(lines) else []
        if len(tokens) != 3 or not _all_int(tokens):
            raise GWParseError(
                "expected a 3-integer office-merit-record row here",
                line_number=line_index + 1,
                line=lines[line_index] if line_index < len(lines) else "",
            )
        office_ordinal, leader_or_army_id, merit_points = (int(token) for token in tokens)
        if office_ordinal not in {member.value for member in Office}:
            raise GWParseError(
                f"unrecognized Office ordinal {office_ordinal} on an office-merit-record row",
                line_number=line_index + 1,
                line=lines[line_index],
            )
        merit_records.append(
            GWOfficeMeritRecord(
                office_code=Office(office_ordinal),
                leader_or_army_id=leader_or_army_id,
                merit_points=merit_points,
            )
        )

    state_line_index = merit_end
    if state_line_index >= len(lines):
        raise GWParseError(
            "world file ends before its own office-state table",
            line_number=state_line_index + 1,
            line="",
        )
    state_tokens = lines[state_line_index].split()
    if len(state_tokens) != 156 or not _all_int(state_tokens):
        raise GWParseError(
            "expected a 156-integer office-state table on this world file's own final block line",
            line_number=state_line_index + 1,
            line=lines[state_line_index],
        )
    state_values = [int(token) for token in state_tokens]

    state_entries: list[GWOfficeStateEntry] = []
    for office_ordinal in range(52):
        prevchar, knowit, _compat_zero = state_values[office_ordinal * 3 : office_ordinal * 3 + 3]
        state_entries.append(
            GWOfficeStateEntry(
                office=Office(office_ordinal),
                previous_holder_raw=prevchar,
                known_by_kings_mask=knowit,
            )
        )

    return merit_records, state_entries
