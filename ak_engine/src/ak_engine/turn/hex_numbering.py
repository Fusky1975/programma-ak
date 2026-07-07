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
pairs tested, far above the ~1-2% expected by chance (each hex has only 6
neighbors); every other width tried (9, 11, 15, 20, 29, 30) scored 20-62%.
This is strong circumstantial evidence for "hex number = y * width + x",
not proof -- treat it as a working hypothesis to revisit if it ever
contradicts real gameplay outcomes.

Unresolved even under this hypothesis:
- The exact board height (real data includes y values past 17, taller
  than `turn/movement.py`'s `NORMAL_MAP_BOUNDS` height of 15 -- this
  game series evidently used a different, narrower-but-taller board than
  the "normal"/"Noble" sizes named in `CTBOTH.PAS`). Board dimensions are
  therefore a caller-supplied parameter here, not a constant.
- Whether row-parity (which of the two 6-neighbor offset sets applies to
  even vs. odd rows) matches `turn/movement.py`'s convention or its
  opposite -- the validation score barely changed either way (77 vs 78
  of 93), too close to call from this sample.
- The ~16-22% of pairs that DON'T decode as adjacent: some are plausibly
  legitimate non-adjacent situations (a leader chasing a distant target
  across a phase gap, or another action in between moving them
  elsewhere by other means); a few show suspiciously round jumps (e.g.
  differing by exactly 170) that might be a distinct sentinel/reset value
  rather than an ordinary hex number.
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
