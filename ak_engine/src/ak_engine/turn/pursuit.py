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
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.army_type import ARMY_TABLE, OVERFLIGHT_AIR, ArmyType
from ak_engine.turn.battle_line import BattleUnit, estimate_win_probability

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


def resolve_pursuit(
    pursuers: list[BattleUnit], retreating_units: list[BattleUnit], rng: random.Random
) -> list[PursuitOutcome]:
    """Pair pursuers with the slowest retreating units first, then roll each standstill check.

    Retreating units beyond the number of available pursuers escape
    unengaged; pursuers beyond the number of retreating units find no
    target.
    """

    targets = sorted(retreating_units, key=lambda u: ARMY_TABLE[u.army_type].speed)
    outcomes = []
    for pursuer, target in zip(pursuers, targets):
        probability = estimate_win_probability(pursuer.effective_strength, target.effective_strength)
        destroyed = rng.random() < probability
        outcomes.append(PursuitOutcome(pursuer=pursuer, target=target, target_destroyed=destroyed))
    return outcomes
