"""Pursuit of retreating armies (rulebook [7.3]).

"After the battle, the faster units in the victorious army can pursue and
possibly destroy some of the losing armies. In this pursuit, army speed
is the most important factor in catching the defenders or evading the
pursuers... Generally speaking, about 25% of the victorious infantry and
75% of the cavalry will attempt to pursue the retreating armies.
Especially fast units such as light cavalry and air wings can attempt
more than one pursuit. If a retreating army is unable to fight the
pursuing unit to a standstill in a one-on-one battle, it is destroyed."

Two gaps the rulebook doesn't cover, resolved here as documented choices
rather than sourced rules:

- **Which army types count as "cavalry"**: the rulebook never lists them.
  ``CAVALRY_TYPES`` below is the table's mounted/fast-moving land types
  (Lt/Hvy Cavalry, Chariots, Camel Corps, Warg Riders); everything else
  (including overflight/naval types) uses the infantry rate.
- **How catching is decided**: no formula for "army speed is the most
  important factor". This pairs pursuers with retreating units by
  matching against the *slowest* retreaters first (easiest to catch),
  using each unit's ``ARMY_TABLE`` speed -- a directionally-correct,
  deterministic simplification, not a probability model.

The "retreating units fight with the 25% defender bonus but suffer a -1
quality penalty" adjustment is NOT computed here -- pass retreating units
whose ``effective_strength`` was already computed that way via
``turn/strength.py compute_effective_strength(..., is_defender=True,
base_quality=<one level down>)``. This module only decides who gets
caught and whether the one-on-one standstill holds, via
``turn/combat.py win_probability`` (through
``turn/battle_line.estimate_win_probability``).

**Phase 349 addendum**: the standstill check above used the same
"documented approximation, not a sourced rule" logistic curve Phase 347
already found a real replacement for. The same `AK.EXE`/`AK.OVR` static
reverse engineering as Phase 346-348 also covers pursuit directly, and
confirms two of this module's own pre-existing constants exactly:
`INFANTRY_PURSUIT_CHANCE`/`CAVALRY_PURSUIT_CHANCE` (25%/75%) match the
source's own `manual_average_attempt_rate` verbatim -- another instance
of an earlier, undocumented guess turning out correct once real data
arrived (same pattern as Phase 347's `DEFENDER_BONUS`/`NEMESIS_PENALTY`
confirmation).

What the source corrects is the standstill formula itself:
`resolve_pursuit` now uses `pursuit_destruction_probability(r_p)` (a
real, confirmed piecewise curve in `r_p` = pursuer strength / retreater
strength, verified against the source's own five worked examples --
`r_p`=0.8/1.0/1.25/1.5/2.0 -> 22.5%/50%/77.5%/91.667%/100%) in place of
the old `win_probability`/`estimate_win_probability` logistic curve, and
draws `draw_pursuit_random_multiplier` (an independent `U[1,2)` per
pairing, the source's own `random_multiplier_each_unit`) to turn the
"deterministic pursuer strength" the source's own `ratio` field
describes into a realized one before computing `r_p`. The source's own
wording doesn't say which side the multiplier lands on -- read literally
("deterministic pursuer strength" is what becomes non-deterministic),
it's applied to the pursuer here, not the retreater, a documented
reading rather than a silently-assumed alternative.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.army_type import ARMY_TABLE, OVERFLIGHT_AIR, ArmyType
from ak_engine.turn.battle_line import BattleUnit

CAVALRY_TYPES = frozenset(
    {ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY, ArmyType.CHARIOTS, ArmyType.CAMEL_CORPS, ArmyType.WARG_RIDERS}
)
MULTI_PURSUIT_TYPES = frozenset({ArmyType.LT_CAVALRY}) | OVERFLIGHT_AIR

INFANTRY_PURSUIT_CHANCE = 0.25
CAVALRY_PURSUIT_CHANCE = 0.75


def select_pursuers(victor_units: list[BattleUnit], rng: random.Random) -> list[BattleUnit]:
    """Roll, per unit, whether it attempts pursuit.

    Light Cavalry and air-wing units that succeed appear twice in the
    result (two pursuit attempts), per "can attempt more than one
    pursuit".
    """

    pursuers: list[BattleUnit] = []
    for unit in victor_units:
        chance = CAVALRY_PURSUIT_CHANCE if unit.army_type in CAVALRY_TYPES else INFANTRY_PURSUIT_CHANCE
        if rng.random() < chance:
            pursuers.append(unit)
            if unit.army_type in MULTI_PURSUIT_TYPES:
                pursuers.append(unit)
    return pursuers


@dataclass(slots=True)
class PursuitOutcome:
    pursuer: BattleUnit
    target: BattleUnit
    target_destroyed: bool


def draw_pursuit_random_multiplier(rng: random.Random) -> float:
    """The source's own `random_multiplier_each_unit`: an independent
    `U[1,2)` draw applied to the pursuer's own strength before computing
    `r_p` -- see this module's "Phase 349 addendum" for why the pursuer
    (not the retreater) is the documented reading here."""

    return rng.uniform(1.0, 2.0)


def _pursuit_strength_ratio(pursuer_strength: float, target_strength: float) -> float:
    """`r_p` with the same zero-strength edge-case handling
    `turn/battle_line.py estimate_win_probability`/`turn/combat.py
    column_bres` already use: a strengthless target is trivially caught
    (an effectively infinite ratio), a strengthless pursuer against a
    real target trivially fails to catch it (ratio `0`), and both
    strengthless is a true no-op (ratio `0`, not an undefined `0/0`)."""

    if pursuer_strength <= 0:
        return 0.0
    if target_strength <= 0:
        return float("inf")
    return pursuer_strength / target_strength


def pursuit_destruction_probability(r_p: float) -> float:
    """The real, confirmed probability that a caught retreater is
    destroyed, from the same `AK.EXE`/`AK.OVR` source as
    `turn/combat.py column_bres`/`direct_destruction_probability`
    (Phase 346-348): a piecewise curve in `r_p` (pursuer strength /
    modified retreater strength), verified against the source's own
    five worked examples (see this module's "Phase 349 addendum").
    """

    if r_p <= 0.5:
        return 0.0
    if r_p <= 1.0:
        return 2 * r_p - 2 + 1 / (2 * r_p)
    if r_p < 2.0:
        return 3 - 2 / r_p - r_p / 2
    return 1.0


def resolve_pursuit(
    pursuers: list[BattleUnit], retreating_units: list[BattleUnit], rng: random.Random
) -> list[PursuitOutcome]:
    """Pair pursuers with the slowest retreating units first, then roll each standstill check.

    Retreating units beyond the number of available pursuers escape
    unengaged; pursuers beyond the number of retreating units find no
    target. The standstill check itself is the real, confirmed
    `pursuit_destruction_probability` curve (Phase 349), not the
    generic logistic `estimate_win_probability` curve this function
    used before.
    """

    targets = sorted(retreating_units, key=lambda u: ARMY_TABLE[u.army_type].speed)
    outcomes = []
    for pursuer, target in zip(pursuers, targets):
        random_multiplier = draw_pursuit_random_multiplier(rng)
        r_p = _pursuit_strength_ratio(pursuer.effective_strength * random_multiplier, target.effective_strength)
        probability = pursuit_destruction_probability(r_p)
        destroyed = rng.random() < probability
        outcomes.append(PursuitOutcome(pursuer=pursuer, target=target, target_destroyed=destroyed))
    return outcomes
