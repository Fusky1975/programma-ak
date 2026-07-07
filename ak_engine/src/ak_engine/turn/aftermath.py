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
"""

from __future__ import annotations

import random

from ak_engine.turn.combat import Quality

BASE_QUALITY_CHANGE_CHANCE = 0.5

DRUID_LED_IMPROVE_MULTIPLIER: dict[Quality, float] = {
    Quality.GREEN: 0.60,
    Quality.DEPLETED: 0.20,
}


def improve_chance(quality: Quality) -> float:
    """Chance to rise one quality level; decreases as quality rises, zero at Elite."""

    if quality == Quality.ELITE:
        return 0.0
    return BASE_QUALITY_CHANGE_CHANCE * (1 - int(quality) / int(Quality.ELITE))


def decline_chance(quality: Quality) -> float:
    """Chance to fall one quality level; decreases as quality rises, zero at Depleted."""

    if quality == Quality.DEPLETED:
        return 0.0
    return BASE_QUALITY_CHANGE_CHANCE * (1 - int(quality) / int(Quality.ELITE))


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
) -> Quality:
    """Roll this unit's post-battle quality change.

    - Winners: may improve (chance reduced if ``led_by_insufficient_druid``
      and the unit fought as Green/Depleted).
    - Losers that retreated: may decline.
    - Losers that didn't retreat ("can either improve or decrease"): rolls
      both directions, decline checked first.
    """

    if is_winner:
        chance = improve_chance(quality)
        if led_by_insufficient_druid:
            chance *= DRUID_LED_IMPROVE_MULTIPLIER.get(quality, 1.0)
        return _step(quality, 1) if rng.random() < chance else quality

    if retreated:
        return _step(quality, -1) if rng.random() < decline_chance(quality) else quality

    roll = rng.random()
    if roll < decline_chance(quality) / 2:
        return _step(quality, -1)
    if roll < decline_chance(quality) / 2 + improve_chance(quality) / 2:
        return _step(quality, 1)
    return quality
