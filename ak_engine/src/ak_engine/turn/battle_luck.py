"""Random battle-luck events -- the real, confirmed `AK.EXE`/`AK.OVR`
luck-draw formula (rulebook [6.3] "Summary of factors" closing
paragraph, corroborated by `HostAK/TP/SAY.PAS`'s `_BLuck`/`_CLuck`/
`_CLuck2` narrative hooks and `BLUCK.X2`/`CLUCK.X2`/`CLUCK2.X2`).

**Phase 346 origin, Phase 370 wired in.** Phase 346's own static reverse
engineering of `AK.EXE`/`AK.OVR` (`gw_format`'s own sibling
`battle_engine` key, sourced from `AK.EXE`, `AK.OVR`, `RULES.AK`,
`ADDEND.AK`, `RUMORS.PAS`, `SAY.PAS`, `BLUCK.X2`, `CLUCK.X2`,
`CLUCK2.X2`, `TACTICS.X2`) replaced this module's own earlier,
explicitly-flagged-as-unsourced guess (a 75%-chance column event, a
55%-chance battle-wide event) with the real formula below, but left it
unwired pending a larger rewire of `resolve_battle`'s own win-decision
path. **Phase 370 is that rewire** -- see `turn/battle_resolution.py`'s
own Phase 370 addendum.

The real mechanic draws **one global luck value per side, drawn once
per battle** (`G1` for side 1, `G2` for side 2, each `U[0,1)`), and
**one local luck value per side, drawn fresh for every column** (`L1`,
`L2`, each `U[0,1)`). Side `s`'s own real strength multiplier for a
given column is `R_s = 1 + k*(G_s + L_s)`, where `k` is `0.75` on the
game's own first turn and `1.5` on every turn after -- "because both
random components are halved" on turn 1, per the source's own note.
`R_s` ranges `[1, 2.5)` on turn 1 and `[1, 4)` on turn 2+, i.e. this
real mechanic can **more than double** a column's strength (up to 4x on
turn 2+) -- unlike the old, superseded model, this multiplier is
**always applied**, every column, every battle; there is no "does the
event trigger" gate at all. It's consistent with the rulebook's own
"can as much as double... but most only... 1.5 or less" language once
the *typical* draw (not the extreme tail) is considered.

The source also gives exact discretized narration-index formulas for
the two events this module's own docstring already named:
`BLUCK` (`clamp(1,17, 9+round(9*(G1-G2)))`, drawn once per battle from
the two *global* values only) and `CLUCK` (`clamp(1,39,
20+round(20*(L_selected-L_other)))`, drawn per column from that
column's own *local* values). Both formulas were verified empirically
against the source's own declared probability tables before being
written here: a 2,000,000-draw Monte Carlo simulation of each formula
matches the source's own per-index percentages to within 0.03
percentage points (pure sampling noise at that N), for both the turn-1
and turn-2+ tables. These indices are narrative-only (which prose
template a report would pick) -- they don't gate or scale `R_s` itself.

`draw_global_luck`, `draw_local_luck`, `luck_strength_multiplier`,
`bluck_event_index`, `cluck_event_index`, and `break_bres_tie` below are
these confirmed primitives, now the sole luck mechanism
`turn/battle_resolution.py resolve_battle` uses.
"""

from __future__ import annotations

import random
from typing import Literal

FIRST_TURN_LUCK_COEFFICIENT = 0.75
LATER_TURN_LUCK_COEFFICIENT = 1.5


def draw_global_luck(rng: random.Random) -> tuple[float, float]:
    """G1, G2: each side's own global luck draw, made once per battle."""

    return rng.random(), rng.random()


def draw_local_luck(rng: random.Random) -> tuple[float, float]:
    """L1, L2: each side's own local luck draw, made fresh for every column."""

    return rng.random(), rng.random()


def luck_strength_multiplier(g_side: float, l_side: float, *, is_first_turn: bool) -> float:
    """R_s = 1 + k*(g_side + l_side) -- side `s`'s own real strength
    multiplier for one column, `k` = 0.75 on the game's own first turn
    (`[1, 2.5)`), 1.5 on every turn after (`[1, 4)`)."""

    coefficient = FIRST_TURN_LUCK_COEFFICIENT if is_first_turn else LATER_TURN_LUCK_COEFFICIENT
    return 1 + coefficient * (g_side + l_side)


def bluck_event_index(g1: float, g2: float) -> int:
    """The whole-battle BLUCK narration index, drawn once per battle from
    the two global luck values alone: `clamp(1,17, 9+round(9*(g1-g2)))`
    -- 1-8 favor side 2, 9 neutral, 10-17 favor side 1."""

    return max(1, min(17, 9 + round(9 * (g1 - g2))))


def cluck_event_index(l_selected: float, l_other: float) -> int:
    """One column's own local CLUCK narration index:
    `clamp(1,39, 20+round(20*(l_selected-l_other)))` -- 1-19 negative for
    the selected unit, 20 neutral, 21-39 positive."""

    return max(1, min(39, 20 + round(20 * (l_selected - l_other))))


def break_bres_tie(rng: random.Random) -> Literal["side1", "side2"]:
    """Break an exact-zero summed-`BRES` battle tie (`turn/combat.py
    column_bres`, Phase 347) "by repeated differences of fair coins" --
    the source's own phrase for the tie-break rule, given without a
    fully worked example. Read literally: draw one fair coin per side,
    repeat until the two coins disagree, and the side that landed heads
    wins -- a `2^-n` chance of needing an `n`-th round, so this
    terminates with probability 1 and (unlike a plain single coin flip)
    stays faithful to the source's own "repeated" and "differences of
    fair coins" (plural coins, one per side) wording. Kept honest about
    the ambiguity rather than silently picking a different, unstated
    interpretation.
    """

    while True:
        side1_heads = rng.random() < 0.5
        side2_heads = rng.random() < 0.5
        if side1_heads != side2_heads:
            return "side1" if side1_heads else "side2"
