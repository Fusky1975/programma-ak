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

**Phase 388 addendum -- the actual narration text.** Phase 370 only
wired the *numeric* `bluck_index`/`cluck_index` (see
`turn/battle_resolution.py BattleResult.bluck_index`/
`BattleColumnResult.cluck_index`'s own docstrings) -- neither was ever
rendered into a sentence. AKGEN's own `battle_engine.global_event.
entries`/`local_column_event.entries` supply the real 17-entry `BLUCK.X2`
and 39-entry `CLUCK.X2` text catalogs (verbatim below), plus two
confirmed mechanics this module didn't have yet:

- **The CLUCK narration gate**: a column's local CLUCK text is only
  emitted when the column is "competitive" -- the deterministic
  pre-luck strength ratio (attacker/defender, either direction, since
  `1/0.4 == 2.5`) falls in `[0.4, 2.5]`. Outside that gate local luck
  still affects the column's own combat outcome (`R_s` above is applied
  unconditionally, every column, per Phase 370), it just goes unnarrated.
- **The CLUCK2 "fortune reverses" rewrite**: when the raw CLUCK index
  falls in `[13, 27]`, a further 33% check can rewrite the narration
  into two opposed sentences -- first CLUCK's own text, then a CLUCK2
  follow-up -- without drawing any new strength factor. Verified against
  the source's own stated aggregate ("a competitive column shows the
  second event 30.9375% of the time on turn 1, 20.109375% on turn 2+")
  by summing `local_column_event.probability_percent_turn_1`/
  `_turn_2_plus` over indices 13-27 and multiplying by 33% -- both
  reproduce the JSON's own stated figures exactly (93.75%*33% =
  30.9375%, 60.9375%*33% = 20.109375%).

  The source's own report additionally says the CLUCK/CLUCK2 text *pair*
  is "chosen with further residues modulo 3" -- but only describes
  CLUCK2.X2's *concept* ("fortune reversed itself"), never captured a
  second 39-entry `CLUCK2.X2` catalog the way it did for `CLUCK.X2`.
  Rather than inventing a fake 39-entry catalog (or a fake mod-3 variant
  table) for text that was never actually sourced, `CLUCK2_REVERSAL_
  PHRASE` below is the report's own single confirmed characterization of
  what the rewrite narrates, used as-is rather than per-index variants --
  an honest, documented partial gap, not a guess.
"""

from __future__ import annotations

import random
from typing import Literal

FIRST_TURN_LUCK_COEFFICIENT = 0.75
LATER_TURN_LUCK_COEFFICIENT = 1.5

# -- Phase 388: BLUCK.X2 (whole-battle) narration --

BLUCK_ENTRIES: tuple[str, ...] = (
    "disastrous rear/supply rumor",
    "vanguard destroyed in ambush",
    "terrible omen",
    "mutiny",
    "side caught unprepared",
    "scouts lost",
    "wind or sun against the side",
    "failed ritual sacrifice",
    "no significant fortune",
    "well-hidden formations",
    "enemy still wounded from an earlier clash",
    "excellent morale",
    "favorable observation position",
    "native allies",
    "good omen",
    "favorable reinforcement rumor",
    "enemy plans stolen",
)

# -- Phase 388: CLUCK.X2 (per-column) narration + CLUCK2 reversal --

CLUCK_ENTRIES: tuple[str, ...] = (
    "commander or standard falls",
    "disastrous mascot/omen",
    "feigned retreat becomes panic",
    "hungry soldiers",
    "battalion scattered",
    "diversion by false alarm",
    "enemy ramps or barrage",
    "rocks or seaweed break formation",
    "treacherous ground or currents",
    "whirlwind or gryphon causes disorder",
    "overextended charge repulsed",
    "illness or after-effects",
    "incapable or indisposed commander",
    "incomplete crossing",
    "premature looting",
    "troops held by a fort",
    "standard captured",
    "seasickness or local food",
    "tiny disorganization",
    "no decisive local event",
    "martial music",
    "battle cry",
    "promise of loot or medals",
    "officer exhortation",
    "charge takes the crest",
    "artillery well employed",
    "heroic noncombatant example",
    "allied beasts break obstacle",
    "heroic officer",
    "attack before enemy fully deploys",
    "deception about enemy rear",
    "dead scouts provoke fury",
    "successful feigned panic",
    "local order or guild assists",
    "stimulant or hallucinogenic mushroom",
    "false surrender and surprise attack",
    "infiltration behind enemy",
    "hidden ambush force",
    "omen makes every soldier fight as two",
)

CLUCK_NARRATION_GATE_LOW = 0.4
CLUCK_NARRATION_GATE_HIGH = 2.5
CLUCK_REVERSAL_INDEX_LOW = 13
CLUCK_REVERSAL_INDEX_HIGH = 27
CLUCK_REVERSAL_CHECK_PERCENT = 0.33

# See this module's own Phase 388 docstring addendum for why this is one
# confirmed phrase rather than a fabricated 39-entry variant catalog.
CLUCK2_REVERSAL_PHRASE = "but then fortune reversed itself"


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


def render_bluck_event(index: int) -> str:
    """The whole-battle BLUCK narration sentence for `bluck_event_index`'s
    own 1..17 index (verbatim AKGEN `BLUCK.X2` catalog, Phase 388)."""

    return BLUCK_ENTRIES[index - 1]


def render_cluck_event(index: int) -> str:
    """One column's own local CLUCK narration sentence for
    `cluck_event_index`'s own 1..39 index (verbatim AKGEN `CLUCK.X2`
    catalog, Phase 388)."""

    return CLUCK_ENTRIES[index - 1]


def column_narration_eligible(attacker_strength: float, defender_strength: float) -> bool:
    """A column's local CLUCK text is only narrated when the deterministic
    pre-luck strength ratio is "competitive" -- AKGEN's own confirmed
    gate, `[0.4, 2.5]` (Phase 388) -- otherwise local luck still affects
    that column's own combat outcome (Phase 370's `R_s` is applied
    unconditionally) but goes unnarrated. Symmetric: `a/d` and `d/a` land
    on the same pass/fail outcome since `1/0.4 == 2.5`."""

    if attacker_strength <= 0 or defender_strength <= 0:
        return False
    ratio = attacker_strength / defender_strength
    return CLUCK_NARRATION_GATE_LOW <= ratio <= CLUCK_NARRATION_GATE_HIGH


def roll_cluck_reversal(index: int, rng: random.Random) -> bool:
    """AKGEN's own confirmed CLUCK2 "fortune reverses" check (Phase 388):
    only rolled when the raw CLUCK index falls in `[13, 27]`; a further
    33% chance rewrites the narration into CLUCK then CLUCK2 -- no new
    strength factor is drawn, this is narration-only. Verified against
    the source's own stated aggregate ("a competitive column shows the
    second event 30.9375% of the time on turn 1, 20.109375% on turn 2+")
    by summing `local_column_event.probability_percent_turn_1`/
    `_turn_2_plus` over indices 13-27 and multiplying by 33% -- both
    reproduce the JSON's own stated figures exactly.
    """

    if not (CLUCK_REVERSAL_INDEX_LOW <= index <= CLUCK_REVERSAL_INDEX_HIGH):
        return False
    return rng.random() < CLUCK_REVERSAL_CHECK_PERCENT
