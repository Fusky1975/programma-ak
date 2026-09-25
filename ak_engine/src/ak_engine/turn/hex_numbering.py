"""Decoding the raw "hex/feature number" used in move files for Move-order targets.

**Phase 753 (`Desktop/MOVE.md`, 2026-09-05): the formula's own shape is
now CERTO, not just empirically inferred.** This user-supplied
disassembly quotes the real Pascal source directly -- `REPORTS.PAS`:
``lobjects[phase] := x * XMULT + y`` (encode); `SAY.PAS`: ``_px := _prov
DIV XMULT; _py := _prov MOD XMULT`` (decode). This is exactly the
"quotient/remainder against one multiplier" shape already implemented
below, with the two axes swapped relative to this module's own naming:
Pascal's multiplied term (``x``) is this module's ``y`` (the ``//``
side), Pascal's remainder term (``y``) is this module's ``x`` (the ``%``
side), and Pascal's ``XMULT`` is this module's ``board_width`` --  a
pure labeling difference, not a formula difference. `MOVE.md` is
explicit that ``XMULT`` "is a build/map constant... not to be fixed at
10, 20, or 100 in a remake" -- it does not supply a numeric value, so
the ``EMPIRICAL_AK3_BOARD_WIDTH = 10`` measurement below remains exactly
that: a real, well-corroborated measurement for this project's own AK3
sample data, now with a confirmed real mechanism behind it, not a
universal constant. What follows is that original empirical derivation,
kept for its own methodological value (a real per-turn adjacency cross-
check, useful evidence a future reader can re-verify independently of
this new source).

To recover it, every consecutive pair of LMOVE targets within a leader's
*final* plan segment across all 10 `AK3__T*.K1` files was decoded under
several `(row_width, offset)` hypotheses and checked for hex-adjacency
(reusing `turn/movement.py`'s adjacency formula, ignoring map-edge
bounds). Row-major decoding with **width 10** matched on 78-84% of the 93
pairs originally tested, far above the ~1-2% expected by chance (each hex
has only 6 neighbors); every other width tried (9, 11, 15, 20, 29, 30)
scored 20-62%.

Phase 315 re-derived this from scratch using the project's own parser
(`parser/k1_moves.py`) instead of the original ad-hoc script, yielding a
stricter set of 59 pairs (only strictly-consecutive LMOVE phases within
one run, rather than any two LMOVE targets anywhere in a segment) and
re-checked it two ways:
- Against `turn/movement.py`'s real-data-sourced adjacency parity (Phase
  314's confirmed convention): **50/59 = 84.7%** -- consistent with, and
  slightly above, the original 78-84% figure, despite the stricter pair
  selection. This is meaningful because Phase 314's parity was fixed
  *after* the original 93-pair validation ran (against the old, since-
  corrected parity) -- the hypothesis survives being re-checked against
  ground truth it wasn't originally tuned against.
- An exhaustive width sweep from 2 to 200 (not just the handful tried
  originally) found **no other width comes close**: width 9 scores 57.6%,
  width 11 scores 55.9%, and every other width scores under 33%. Width 10
  is decisively the best fit, not just the best of a small handful tried.

Also tested and **ruled out**: the `row*100+col` scheme confirmed for SE3
report-file province numbers (see `turn/movement.py`'s own docstring,
e.g. Mongu = #305) does not describe AK3 LMOVE targets -- despite both
filename families sharing a "3", they are different, incompatible
numbering schemes. `row*100+col` scores only 23.7% (14/59) against real
AK3 adjacency pairs, i.e. AK3 move files are NOT report-style province
numbers. Recorded here so this plausible-looking hypothesis isn't
re-tried.

Unresolved even after `MOVE.md` (none of the three is addressed there --
it confirms the formula's shape, not these per-map specifics):
- The exact board height (real data includes y values past 17, taller
  than `turn/movement.py`'s `NORMAL_MAP_BOUNDS` height of 15 -- this
  game series evidently used a different, narrower-but-taller board than
  the "normal"/"Noble" sizes named in `CTBOTH.PAS`). Board dimensions are
  therefore a caller-supplied parameter here, not a constant.
- Whether row-parity (which of the two 6-neighbor offset sets applies to
  even vs. odd rows) matches `turn/movement.py`'s convention or its
  opposite -- genuinely still too close to call from AK3 data alone (50
  vs. 52 of 59 under Phase 314's corrected vs. old parity). Every one of
  the 8 non-sentinel mismatches under the corrected parity happens to be
  a diagonal (dx, dy) = (±1, ∓1) step that the *old* parity table would
  have caught -- but the old table also breaks pairs the corrected one
  gets right, netting out lower overall (52 vs 50). This dataset can't
  settle parity on its own; `turn/movement.py`'s convention is kept here
  too, since it is sourced from real narrative prose naming actual
  provinces and directions, not a statistical curve fit.
- The ~15% of pairs that DON'T decode as adjacent: some are plausibly
  legitimate non-adjacent situations (a leader chasing a distant target
  across a phase gap, or another action in between moving them
  elsewhere by other means); one shows a suspiciously round jump (differs
  by exactly 170) that might be a distinct sentinel/reset value rather
  than an ordinary hex number.

**A second, independent game's real move files (2026-09-12): the formula's
shape reproduces cleanly, but its own ``XMULT`` is confirmed NOT tied to
the real board width -- not just "unconfirmed," now positively
contradicted by a real, known-width board.** The user found `Desktop/
PROGRAMMA AK/AK6__T1.K3` and `AK6__T2.K{3,7,12,16,17,22}` (7 real move
files from game 6) alongside that game's own `GW6`/`GW6__T2..T4` world
saves. `parse_gw_header()` on `GW6` gives `map_left_x=0, map_right_x=29,
map_top_y=0, map_bottom_y=14` -- a real, ground-truth 30x15 board (the
Super-AK size the rulebook names at [12.1], already independently
confirmed as `NORMAL_MAP_BOUNDS` by Phase 780). Extracting every
strictly-consecutive within-segment LMOVE pair from these 7 files via
`parser/k1_moves.py` (15 pairs total) and sweeping `board_width` 2-60
with `turn/movement.py hex_distance()` (the same "ignore bounds, ignore
wraparound" adjacency check the AK3 sweep above used) finds **width 20
scores 12/15 (80%)** -- decisively best, matching the AK3 sweep's own
78-84% ceiling almost exactly -- while the *real* board width, 30,
scores only 3/15 (20%, indistinguishable from chance). This is the same
"quotient/remainder" formula (`MOVE.md`'s own `x*XMULT+y`) working
correctly on a second, wholly independent game, but with an empirically
different `XMULT` (20, not 10) that is *also* not the real board width
(30) -- exactly mirroring AK3's own situation (empirical 10 vs. real 18,
per `GW3__T1`'s 162 provinces / 9 height). Two independent games now
each show `XMULT != real board width`, strongly reinforcing `MOVE.md`'s
own warning that `XMULT` is "a build/map constant... not to be fixed at
10, 20, or 100 in a remake" -- it is some other, still-unidentified
per-build or per-game quantity, not the map's own visible dimensions.
This does NOT resolve AK3's own board-height/parity questions above
(game 6's board is a different size than game 3's, so its own width-20
fit doesn't transfer) -- but it does mean a future "which real quantity
is XMULT" investigation should not assume it will ever equal the real
`map_right_x - map_left_x + 1`.

**Phase 916 -- a third and fourth game's real move files (`AK7__T1.K2`/
`AK7__T2.K2`, `AK900T1.K0` + its own `GW900T1` world-save), already
supplied for an earlier, unrelated question (Phase 907's own skill-line
investigation) but never checked against this one until now.** Neither
game gave the kind of multi-pair dataset AK3/AK6 did:

- `AK7__T2.K2` has no plan phases at all for either leader (a
  no-orders-submitted turn). `AK7__T1.K2`'s own 2 leaders (Ldr-2,
  Adhemar) each issue exactly one LMOVE, both to the *same* target
  (90) -- no second, different target to pair it against, and (as
  already noted) this game has no matching world-save to supply a real
  "from" coordinate either. Still unusable, for a new, more specific
  reason than "no world-save" alone.
- `AK900T1.K0`'s own 3 leaders (Legolas, Ashley, Negumba) likewise each
  issue exactly one LMOVE, all to the *same* target (61) -- but this
  game *does* have a matching world-save (`GW900T1`), which gives all
  3 leaders' real starting coordinate directly: `(6, 2)`. That's a
  genuine, if singular, real (origin, target) pair to test -- a
  different kind of evidence than a within-file "consecutive pair" (a
  ground-truth coordinate from the world-save, not an inferred one).
  Sweeping `board_width` 2-200 the same way finds exactly 5 widths
  where `decode_hex_number(61, width)` lands adjacent to `(6, 2)`: 18,
  27, 28, 54, 55. **`GW900T1`'s own header gives this game's real board
  as 18x9** (`map_right_x=17, map_bottom_y=8`) -- width 18 is real. For
  the first time across 3 real games checked, a real board width is
  among the widths consistent with an actual LMOVE pair.

**Read this cautiously, not as a reversal of the AK3/AK6 finding.** A
single pair can't rank candidate widths the way AK3's 59 pairs or AK6's
15 did -- 18 is merely *consistent* here, tied with 4 other candidates
that have no known significance, not picked out as a decisive best fit.
It does mean the previous framing ("two independent games now each show
`XMULT != real board width`... it is some other, still-unidentified
per-build or per-game quantity") overreached slightly by generalizing
from exactly 2 same-direction data points: a third game's own (weaker)
evidence doesn't continue that pattern. The honest position is simply
that `XMULT` varies per game/build and isn't reliably predictable from
the map's own visible dimensions in either direction -- sometimes
different (AK3, AK6), sometimes not distinguishable from equal to it
(AK900, with only one pair to go on). This still doesn't resolve any of
AK3's own 3 open questions above (a different game's board, real or
matched width, doesn't transfer to AK3's own data) -- closing that
would need a second AK3-*like* multi-turn dataset (several turns of the
same game, the way the original 10 `AK3__T*.K1` files were used), not
just any third game's single pair.

**Phase 917 -- the "second AK3-like dataset" the paragraph above asked
for turns out to already exist inside AK3 itself, via a completely
different real anchor: `GW3__T1`-`T12`'s own leader coordinates
(`parser/gw_world.py parse_gw_leaders()`), matched by name against each
turn's own `AK3__T*.K1`.** Unlike Phase 315's own within-file
consecutive-pair method (both ends of every pair are themselves
*decoded*, never independently verified), this gives a genuine
ground-truth "from": whenever a leader's very first phase this turn is
already an LMOVE (nothing earlier in their plan -- Practice, Recruit,
Cast, etc. -- changes location), the real-world-save coordinate *is*
their position at the moment that LMOVE target applies, with zero
decoding involved on that side. Across all 10 turns this finds **85
such (real coordinate, LMOVE target) pairs** -- 44% more than the
original 59, and the first AK3 dataset with one real, undecoded
endpoint.

Naively comparing these coordinates against `decode_hex_number()`
output scores near zero at every width from 2 to 200 -- not noisy, a
flat, decisive failure, the kind that means "wrong basis," not "weak
fit." **The fix is a straightforward x/y transpose**: comparing
`HexCoord(leader_coord.y, leader_coord.x)` (not the coordinate as
recorded) against the decoded target immediately restores the expected
signal -- **width 10 scores 74/85 (87.1%)**, decisively the best fit
across the full 2-200 sweep (next closest: 13/85, 15.3%), matching (and
slightly exceeding) Phase 315's own 84.7% on a dataset with no shared
pairs and a genuinely independent kind of ground truth. This isn't a
bug in `GWLeaderRecord.coord`'s own parsing -- cross-checking each
leader's *unswapped* coordinate against `parser/gw_world_bridge.py
bridge_gw_world_provinces()`'s own column-major province grid lands
every single one (15/15 sampled) on a province whose race matches the
leader's own race exactly, while the swapped reading lands on
race-mismatched or out-of-bounds provinces almost every time -- GW's
own coordinate system (leaders and provinces alike) is internally
self-consistent and correctly parsed as-is. The transpose is real, but
it sits squarely *between* two independent, each-internally-correct
real coordinate systems -- the GW world-save format's own native (x,
y) (column, row) convention, and this module's own K1-LMOVE row-major
decode -- which nothing before this ever had reason to compare
numerically against each other (every prior cross-reference in this
project matched GW leaders/Kings by *name*, never by raw coordinate
arithmetic against a separately-decoded hex number).

**This closes the board-height puzzle for AK3 outright, not just
narrows it.** "Real data includes y values past 17, taller than the
assumed 15-row height" (the very first open question above) dissolves
once the transpose is accounted for: this module's own `y` (the `//
board_width` term) is the axis that reaches past 17 in real LMOVE
data -- and that is exactly `GW3__T1`'s own real, already-confirmed
*width* axis (18 columns, `parser/gw_world_bridge.py
CONFIRMED_BOARD_HEIGHT`'s own sibling constant), not a taller-than-
expected height at all. This module's own `x` (the `% board_width`
term, bounded by `EMPIRICAL_AK3_BOARD_WIDTH`) is the axis that
corresponds to the real, already-confirmed *height* (9 rows) -- and
`10` sits suspiciously close to that real `9`, close enough to notice,
not close enough to call exact (off by one, and not confirmed as a
general law: AK6's own empirical `20` vs. its own real height `15` is a
looser fit, and wasn't re-checked with this same ground-truth technique
since `GW6` isn't available in this repo/session to redo the leader
cross-reference on). Recorded as a real, suggestive pattern worth a
future check, not promoted to "XMULT is secretly board height."

**Row-parity itself is untouched by this new dataset -- a genuine,
confirmed dead end for this specific technique, not just an unlucky
sample.** `_EVEN_ROW_OFFSETS`/`_ODD_ROW_OFFSETS` (`turn/movement.py`)
share 4 of their 6 offset vectors as a set (`(1, 0)`, `(-1, 0)`, `(0,
1)`, `(0, -1)` appear in both tables, just reassigned) -- only the two
"far" diagonal offsets differ between them, so any move whose real
delta lands on one of the 4 shared vectors is parity-*insensitive* by
construction. Checked directly, not assumed: every one of the 85 pairs'
matched/unmatched status is byte-for-byte identical whether `neighbors()`
uses the real (Phase 314-confirmed) convention or the discredited,
reversed one -- zero pairs land on a parity-sensitive delta. A future
dataset would need real moves whose *unswapped* deltas happen to land
on one of the 4 diagonal offsets that differ between the two tables
(`(1, 1)`, `(-1, -1)`, `(1, -1)`, `(-1, 1)`) to ever discriminate this
question; nothing currently available (AK3, AK6, AK7, AK900) offers
one.
"""

from __future__ import annotations

from ak_engine.models.map import HexCoord

# The width found to best fit the AK3__T*.K1 sample data (see module
# docstring for the validation methodology). Not claimed to be universal
# across every game series/board size -- pass the right width for your data.
EMPIRICAL_AK3_BOARD_WIDTH = 10


def decode_hex_number(number: int, board_width: int) -> HexCoord:
    """Row-major decode: ``HexCoord(number % board_width, number // board_width)``."""

    if board_width <= 0:
        raise ValueError(f"board_width must be > 0, got {board_width}")
    if number < 0:
        raise ValueError(f"number must be >= 0, got {number}")
    return HexCoord(number % board_width, number // board_width)


def encode_hex_number(coord: HexCoord, board_width: int) -> int:
    """Inverse of :func:`decode_hex_number`."""

    if board_width <= 0:
        raise ValueError(f"board_width must be > 0, got {board_width}")
    return coord.y * board_width + coord.x
