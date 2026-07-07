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
