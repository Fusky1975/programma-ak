"""Effective-strength calculator (rulebook [6.3] "Summary of factors
affecting army strength").

The rulebook gives an exact, ordered pipeline:

    Strength of army type, modified by terrain:
      +1 if home terrain for race
      +1 if home terrain for army type
      Halve for adverse terrain
      (Illusory Terrain spell: averaged with real terrain -- SKIPPED, no
       spellcasting system exists yet)
    Multiply strength by modified unit quality:
      -1 if in desert without camels
      (-? insufficient Druidic ability -- SKIPPED, no "Druid Table" data)
      +1 if in home province
      +1 for fanatical units
      (+1 Oratory spell, +? magic items -- SKIPPED, no spell/item-effect
       system exists yet)
    Multiply result by special factors (multiplied together, not added):
      Defense: +25%
      Exploration: +25% (maximum)
      Tactical Ability +20%/level (or Naval in Sea provinces)
      (Phantasmal Armies +15%/level of caster -- SKIPPED, no spellcasting)
      Nemesis encounter: -33% (== the 2/3 multiplier already in
       turn/combat.py -- confirms it, doesn't change it)
      Random Event: +/-% (applied later, in turn/battle_luck.py -- NOT
       part of this function, to avoid double-applying it)

This resolves the "unspecified stacking order" gap flagged in earlier
phases: the order above is a direct rulebook quote, not a guess. What's
still skipped (Illusory Terrain, Druidic ability penalty, Oratory,
magic items, Phantasmal Armies) all depend on spellcasting/item-effect
systems this project hasn't built; they're omitted rather than guessed.
"""

from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import (
    ARMY_TABLE,
    BASE_STRENGTH,
    GARRISON_ATTACK_STRENGTH,
    GARRISON_DEFENSE_STRENGTH,
    RACE_TERRAIN_BONUS,
    RACE_TYPE_BONUS,
    ArmyType,
    is_nemesis_of,
)
from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import DEFENDER_BONUS, NEMESIS_PENALTY, Quality

# Rulebook: "Elephants are unpredictable in battle and can have a strength
# of anywhere between 2 and 5." No formula for the exact value -- rolled
# uniformly, a documented choice.
ELEPHANTS_STRENGTH_RANGE = (2, 5)

# Rulebook: "An army fighting for a Divine kingdom has a 50% chance of
# becoming fanatical... Good kingdom... 40%... Evil kingdom... 25%." Every
# other alignment has no stated chance (treated as 0, not guessed higher).
# "A Skeletal army fighting under an Undead character has will always be
# fanatical" is modeled as the separate ``always_fanatical`` override.
FANATICISM_CHANCE: dict[Alignment, float] = {
    Alignment.DIVINE: 0.50,
    Alignment.GOOD: 0.40,
    Alignment.EVIL: 0.25,
}

MAX_EXPLORATION_ADVANTAGE = 0.25
TACTICAL_BONUS_PER_LEVEL = 0.20


def roll_elephants_strength(rng: random.Random) -> int:
    return rng.randint(*ELEPHANTS_STRENGTH_RANGE)


def roll_fanaticism(alignment: Alignment, rng: random.Random, *, always_fanatical: bool = False) -> bool:
    if always_fanatical:
        return True
    return rng.random() < FANATICISM_CHANCE.get(alignment, 0.0)


def modified_quality(
    base_quality: Quality,
    *,
    desert_without_camels: bool = False,
    is_home_province: bool = False,
    is_fanatical: bool = False,
) -> Quality:
    """Shift a quality level per the rulebook's quality-modifier list, clamped to Quality's range."""

    level = int(base_quality)
    if desert_without_camels:
        level -= 1
    if is_home_province:
        level += 1
    if is_fanatical:
        level += 1
    level = max(int(Quality.DEPLETED), min(int(Quality.ELITE), level))
    return Quality(level)


def exploration_advantage_multiplier(own_explored_percent: int, enemy_explored_percent: int) -> float:
    """Rulebook: "the side with the better exploration... will also have up to a 25% advantage.

    Only the better-explored side gets a bonus (never a penalty for being
    behind); the rulebook's only concrete data point is the 100%-vs-0%
    case giving exactly +25%, so this scales linearly between 0% and that
    maximum by the exploration gap -- a documented interpolation, not a
    sourced formula (see ``ak_engine/README.md``).
    """

    gap = max(0, own_explored_percent - enemy_explored_percent) / 100
    return 1 + MAX_EXPLORATION_ADVANTAGE * min(1.0, gap)


def combat_ability_multiplier(ability_level: int) -> float:
    """Rulebook: "Tactical Ability +20% per level (or Naval ability in Sea provinces)".

    Caller picks which ability's level to pass in based on terrain.
    """

    return 1 + TACTICAL_BONUS_PER_LEVEL * ability_level


def _base_strength(army_type: ArmyType, *, is_defender: bool, base_strength_override: float | None) -> float:
    if base_strength_override is not None:
        return base_strength_override
    if army_type is ArmyType.GARRISON:
        return GARRISON_DEFENSE_STRENGTH if is_defender else GARRISON_ATTACK_STRENGTH
    if army_type is ArmyType.ELEPHANTS:
        raise ValueError(
            "Elephants have variable strength (2-5); roll it with roll_elephants_strength() "
            "and pass it as base_strength_override"
        )
    return BASE_STRENGTH[army_type]


def compute_effective_strength(
    army_type: ArmyType,
    race: Race,
    base_quality: Quality,
    terrain: Terrain,
    *,
    is_defender: bool = False,
    is_home_province: bool = False,
    is_fanatical: bool = False,
    desert_without_camels: bool = False,
    own_explored_percent: int = 0,
    enemy_explored_percent: int = 0,
    combat_ability_level: int = 0,
    opponent_army_type: ArmyType | None = None,
    base_strength_override: float | None = None,
) -> float:
    """Full effective-strength pipeline, in the rulebook's documented order.

    Does NOT apply the random-event factor -- that's rolled once per
    front-line unit / once per battle in ``turn/battle_luck.py`` and
    applied in ``turn/battle_resolution.py``, to keep randomness in one
    place.

    **Whales off-sea** (Phase 37): "Whales: When fighting in any terrain
    other than Sea, they have zero strength." An unconditional override,
    not the generic adverse-terrain halving ``ARMY_TABLE``'s own
    ``adverse_terrain`` entry for Whales would otherwise apply -- checked
    first and short-circuits the rest of this pipeline (quality,
    defender bonus, etc. would all still multiply a nonzero base by
    something, and the rule says exactly zero, not "reduced").
    """

    if army_type is ArmyType.WHALES and terrain is not Terrain.SEA:
        return 0.0

    strength = _base_strength(army_type, is_defender=is_defender, base_strength_override=base_strength_override)

    if RACE_TYPE_BONUS.get((race, army_type)):
        strength += 1
    if RACE_TERRAIN_BONUS.get((race, terrain)):
        strength += 1
    stats = ARMY_TABLE.get(army_type)
    if stats is not None and terrain in stats.home_terrain:
        strength += 1
    if stats is not None and terrain in stats.adverse_terrain:
        strength /= 2

    quality = modified_quality(
        base_quality,
        desert_without_camels=desert_without_camels,
        is_home_province=is_home_province,
        is_fanatical=is_fanatical,
    )
    strength *= int(quality)

    if is_defender:
        strength *= DEFENDER_BONUS
    strength *= exploration_advantage_multiplier(own_explored_percent, enemy_explored_percent)
    strength *= combat_ability_multiplier(combat_ability_level)
    if opponent_army_type is not None and is_nemesis_of(army_type, opponent_army_type):
        strength *= NEMESIS_PENALTY

    return strength
