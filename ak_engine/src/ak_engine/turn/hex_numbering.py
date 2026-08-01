"""Decoding the raw "hex/feature number" used in move files for Move-order targets.

**This is an empirical inference from real game data, not a sourced
rule.** Player move-submission files (e.g. `AK3__T1.K1`) encode an LMOVE
phase's target as a single integer (`PlanPhase.obj`) -- e.g. `P0 : 0 104
0` targets hex number 104. Nothing in the rulebook or the available
Pascal source explains this encoding (it would have lived in the missing
main turn-processor, like hex adjacency itself -- see
`turn/movement.py`).

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

Unresolved even under this hypothesis:
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
