"""Post-battle quality changes (rulebook [7.5]).

"Armies of the winning force that did well in the battle may have their
quality increased by 1 level, although most troops will never become
Crack and very few will ever become Elite. Some armies in the losing
force will probably have their quality level decreased by 1 level,
although a defeated force that does not retreat can either improve or
decrease in quality. The chance of rising or falling in quality decreases
as armies gain in quality. A unit has less than the normal chance to
improve in quality if it is inadequately led. If it fought as a Green or
Depleted unit because of insufficient Druidic ability, it has 60% and 20%
(respectively) of the normal chance to improve."

**No numbers at all are given here** -- unlike ``win_probability``
(which at least has two anchor points), this rule is entirely
qualitative. Every constant in this module is therefore a deliberate,
unsourced design choice made to have *some* deterministic, testable
behavior, not a recovered or even approximated rule. Revisit freely;
there's nothing here to contradict.

**Phase 350 addendum**: real data has now arrived, from the same
`AK.EXE`/`AK.OVR` source as Phase 346-349's own battle-resolution
corrections. Its own confirmed formula: `base_percent = 60 >>
max(0, quality + formation_divisor - 2)` (an integer right-shift, not a
division), where `formation_divisor` is `1`/`2`/`4`/`8` for front/
second/third/fourth-and-later formation depth (`FORMATION_DIVISOR`
below) and `quality` is `Quality`'s own `0`-`5` ordinal -- verified
exactly against the source's own 4x6 worked table (e.g. front-line
Average, `60 >> max(0,2+1-2) = 60 >> 1 = 30`; third-line Elite,
`60 >> max(0,5+4-2) = 60 >> 7 = 0`). A losing, selected front-line unit
falls one level at exactly this `base_percent` (Depleted excluded --
"Depleted cannot fall"). A winning, selected unit rises one level at
`base_percent * merit_multiplier` (`MERIT_MULTIPLIER` below, keyed by
the unit's own battle-performance "score"; Elite excluded -- "Elite
cannot gain").

**Phase 372: wired into `roll_quality_change`/`turn/battle_orchestrator.py`'s
call sites.** Formation depth turned out to already be available, not
missing: `turn/battle_resolution.py BattleColumnResult.attacker_units`/
`defender_units` are ordered front-to-back lists (Phase 6's own
`assign_battle_lines`), so an army's own index in its column's list
*is* its formation depth -- `battle_orchestrator._formation_divisors()`
reads exactly that, no new state needed. `improve_chance`/
`decline_chance` below now take that `formation_divisor` and use
`base_quality_change_percent` instead of the old flat, unsourced
`BASE_QUALITY_CHANGE_CHANCE` formula -- that constant is removed
outright, not kept dead, since nothing else in the project ever needs a
from-scratch flat rate again.

The other real input, a unit's own per-unit "merit" battle-performance
`score` (used only by the *gain* side's `quality_gain_merit_multiplier`)
genuinely is still missing, and unlike formation depth there's no
already-computed real number sitting in this project's battle-line data
that the source confirms is the right substitute -- `column_bres` is
tempting (it *is* a real, per-column performance number), but the
source never says the engine's own "score" reuses `BRES`, and guessing
that mapping would misrepresent an unconfirmed interpretation as a
recovered formula. `roll_quality_change`'s new `score` parameter
defaults to `0` -- the gain formula's own documented "score >= 0 -->
multiplier 1.0" case, i.e. *no* reduction -- the same "missing data
defaults to a neutral, not a guessed, value" convention this project
already uses elsewhere (see `turn/battle_orchestrator.py
_build_battle_units`'s own exploration-advantage default). A future
phase can source and wire a real `score` the moment a source confirms
one; nothing here forecloses that.
"""

from __future__ import annotations

import random

from ak_engine.turn.combat import Quality

# -- Phase 350: the confirmed AK.EXE/AK.OVR quality-change formula --------

FORMATION_DIVISOR = {
    "front": 1,
    "second": 2,
    "third": 4,
    "fourth_and_later": 8,
}

MERIT_MULTIPLIER = {
    0: 1.0,
    -1: 0.6,
    -2: 0.2,
}


def base_quality_change_percent(quality: Quality, formation_divisor: int) -> float:
    """`60 >> max(0, quality + formation_divisor - 2)`, as a `0.0`-`0.6`
    fraction -- see this module's own "Phase 350 addendum" for the full
    derivation and its source. `formation_divisor` is one of
    `FORMATION_DIVISOR`'s own four values, not an arbitrary int."""

    shift = max(0, int(quality) + formation_divisor - 2)
    return (60 >> shift) / 100


def quality_gain_merit_multiplier(score: int) -> float:
    """The source's own `gain_merit_multiplier`: `1.0` for a
    non-negative battle-performance score, `0.6`/`0.2` for `-1`/`-2`,
    and `0.0` (no gain at all) for `-3` or worse."""

    return MERIT_MULTIPLIER.get(min(score, 0), 0.0)

DRUID_LED_IMPROVE_MULTIPLIER: dict[Quality, float] = {
    Quality.GREEN: 0.60,
    Quality.DEPLETED: 0.20,
}


def improve_chance(quality: Quality, formation_divisor: int = FORMATION_DIVISOR["front"], *, score: int = 0) -> float:
    """Chance to rise one quality level: `base_quality_change_percent`
    scaled by `quality_gain_merit_multiplier(score)` -- zero at Elite
    ("Elite cannot gain"), regardless of `score`."""

    if quality == Quality.ELITE:
        return 0.0
    return base_quality_change_percent(quality, formation_divisor) * quality_gain_merit_multiplier(score)


def decline_chance(quality: Quality, formation_divisor: int = FORMATION_DIVISOR["front"]) -> float:
    """Chance to fall one quality level: `base_quality_change_percent`
    directly -- zero at Depleted ("Depleted cannot fall")."""

    if quality == Quality.DEPLETED:
        return 0.0
    return base_quality_change_percent(quality, formation_divisor)


def _step(quality: Quality, delta: int) -> Quality:
    level = max(int(Quality.DEPLETED), min(int(Quality.ELITE), int(quality) + delta))
    return Quality(level)


def roll_quality_change(
    quality: Quality,
    rng: random.Random,
    *,
    is_winner: bool,
    retreated: bool = False,
    led_by_insufficient_druid: bool = False,
    formation_divisor: int = FORMATION_DIVISOR["front"],
    score: int = 0,
) -> Quality:
    """Roll this unit's post-battle quality change.

    - Winners: may improve (chance reduced if ``led_by_insufficient_druid``
      and the unit fought as Green/Depleted).
    - Losers that retreated: may decline.
    - Losers that didn't retreat ("can either improve or decrease"): rolls
      both directions, decline checked first.

    ``formation_divisor`` (Phase 372) is one of ``FORMATION_DIVISOR``'s
    own four values -- which formation depth this unit fought at,
    defaulting to front-line for a caller that doesn't track it.
    ``score`` (Phase 372) only affects the *improve* side (see
    ``improve_chance``'s own docstring) -- defaulting to `0`, the
    formula's own "no reduction" case, since no real source gives this
    project a per-unit merit score to compute (see this module's own
    docstring).
    """

    if is_winner:
        chance = improve_chance(quality, formation_divisor, score=score)
        if led_by_insufficient_druid:
            chance *= DRUID_LED_IMPROVE_MULTIPLIER.get(quality, 1.0)
        return _step(quality, 1) if rng.random() < chance else quality

    if retreated:
        return _step(quality, -1) if rng.random() < decline_chance(quality, formation_divisor) else quality

    decline = decline_chance(quality, formation_divisor)
    improve = improve_chance(quality, formation_divisor, score=score)
    roll = rng.random()
    if roll < decline / 2:
        return _step(quality, -1)
    if roll < decline / 2 + improve / 2:
        return _step(quality, 1)
    return quality
