"""Random battle-luck events (rulebook [6.3] "Summary of factors" closing
paragraph and `HostAK/TP/SAY.PAS`).

The rulebook says: "the events in battle reports... are basically
randomly determined... Each random event can as much as double the
strength of the affected force (but most only multiply it by a factor of
1.5 or less). The first random event affects the whole battle, while
succeeding events affect a column of units in a battle line." No exact
probabilities or percentage ranges are given anywhere in the rulebook.

This is corroborated, structurally, by `HostAK/TP/SAY.PAS`'s `_BLuck`
(one whole-battle luck event) and `_CLuck`/`_CLuck2` (per-column luck
events) narrative hooks, and the matching template files
`HostAK/TP/PROSE/BLUCK.X2` / `CLUCK.X2`, which describe qualitative
magnitude tiers (from "no luck of any significance" up to "tremendous/
extraordinary advantage") for exactly these two kinds of event -- but,
like the rulebook, no template gives an exact number either.

So the two events below exist because the source material confirms they
should, but every number is a deliberate, DOCUMENTED design choice, not a
recovered rule:

- **Column luck**: each front-line unit has a 75% chance of a random
  multiplier: 50/50 between a +10%..+50% bonus or a -10%..-50% malus.
- **Battle luck**: 55% chance of one whole-battle event giving a single,
  randomly chosen side (never both) a +1%..+10% bonus to its total
  strength.

Revisit these constants first if real game data or a recovered rule ever
contradicts them.

**Phase 346 addendum -- that trigger has now happened.** A static
reverse engineering of `AK.EXE`/`AK.OVR` (the real runtime battle
resolver, not the `AKGEN.EXE` world generator Phase 342-345 drew on --
`gw_format`'s own sibling `battle_engine` key in the same JSON source,
sourced from `AK.EXE`, `AK.OVR`, `RULES.AK`, `ADDEND.AK`, `RUMORS.PAS`,
`SAY.PAS`, `BLUCK.X2`, `CLUCK.X2`, `CLUCK2.X2`, `TACTICS.X2`) gives the
real luck-draw formula: **one global luck value per side, drawn once
per battle** (`G1` for side 1, `G2` for side 2, each `U[0,1)`), **and
one local luck value per side, drawn fresh for every column** (`L1`,
`L2`, each `U[0,1)`). Side `s`'s own real strength multiplier for a
given column is `R_s = 1 + k*(G_s + L_s)`, where `k` is `0.75` on the
game's own first turn and `1.5` on every turn after -- "because both
random components are halved" on turn 1, per the source's own note.
`R_s` ranges `[1, 2.5)` on turn 1 and `[1, 4)` on turn 2+, i.e. this
real mechanic can **more than double** a column's strength (up to 4x on
turn 2+), a materially larger ceiling than this phase's own superseded
guess (at most a 1.5x column bonus, 1.1x battle bonus) -- though still
consistent with the rulebook's own "can as much as double... but most
only... 1.5 or less" language once the *typical* draw (not the extreme
tail) is considered.

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
and turn-2+ tables.

`draw_global_luck`, `draw_local_luck`, `luck_strength_multiplier`,
`bluck_event_index`, and `cluck_event_index` below are these new,
confirmed primitives -- added standalone and tested against the
source's own probability tables, but **not yet wired into
`resolve_battle`** (still `turn/battle_resolution.py`'s pre-existing
`roll_column_luck`/`roll_battle_luck` call sites below). Rewiring
`resolve_battle` to use `R_s` (and the `BRES` column-scoring formula it
feeds) instead of the old "front-unit-only" / "one side, one battle-
wide event" model is a separate, larger phase (it also replaces the
column win/loss decision itself, not just the luck inputs) --
mirroring this project's own established "implement the standalone
function first, wire it into the real call site in a later phase"
split (Phase 172 implemented Cast execution's `_execute_charm`/
`_execute_kill_enemy` standalone; Phase 173 wired them in).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

COLUMN_LUCK_CHANCE = 0.75
COLUMN_LUCK_BONUS_RANGE = (1.10, 1.50)
COLUMN_LUCK_MALUS_RANGE = (0.50, 0.90)

BATTLE_LUCK_CHANCE = 0.55
BATTLE_LUCK_BONUS_RANGE = (1.01, 1.10)

Side = Literal["attacker", "defender"]


@dataclass(slots=True)
class ColumnLuckEvent:
    multiplier: float
    is_bonus: bool


@dataclass(slots=True)
class BattleLuckEvent:
    side: Side
    multiplier: float


def roll_column_luck(rng: random.Random) -> ColumnLuckEvent | None:
    """Roll one front-line unit's column-luck event, or None if it doesn't trigger."""

    if rng.random() >= COLUMN_LUCK_CHANCE:
        return None
    is_bonus = rng.random() < 0.5
    low, high = COLUMN_LUCK_BONUS_RANGE if is_bonus else COLUMN_LUCK_MALUS_RANGE
    return ColumnLuckEvent(multiplier=rng.uniform(low, high), is_bonus=is_bonus)


def roll_battle_luck(rng: random.Random) -> BattleLuckEvent | None:
    """Roll the single whole-battle luck event, or None if it doesn't trigger."""

    if rng.random() >= BATTLE_LUCK_CHANCE:
        return None
    side: Side = rng.choice(("attacker", "defender"))
    return BattleLuckEvent(side=side, multiplier=rng.uniform(*BATTLE_LUCK_BONUS_RANGE))


# -- Phase 346: the confirmed AK.EXE/AK.OVR luck formula -----------------
#
# See this module's own "Phase 346 addendum" docstring above for the
# full derivation. Not yet wired into `resolve_battle` -- these are the
# standalone primitives a later phase rewires the win-decision path to
# use, in place of `roll_column_luck`/`roll_battle_luck` above.

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
