"""Personal combat resolution core (rulebook [5.0]-[5.3], [5.9]) -- Phase 48.

Encounters (Search vs. a feature's monster, Challenge/Pursue between
characters, or a battle's own Duel) all bottom out in the same personal
combat system: "two combatants alternately attack each other in combat
rounds, inflicting damage points with each attack, until one combatant
is killed because the damage points he sustains equals or exceeds his
hit points" ([5.0]). This module builds *only* that core -- the
two best-sourced tactics, Melee and Fire Arrow -- as a first, narrow
slice, the same incremental approach this project already used for the
army-battle system (Phase 5's combat primitives, built up over several
more phases before Phase 9 wired a full `fight_battle()`). **Not yet
wired into Search/Challenge/Pursue/Duel** -- those still resolve
combat the way they always have (Duel via `estimate_win_probability`
approximation; Search/Challenge/Pursue decode-only) until a later phase
connects them.

**[5.0] core resolved here**:
- "In combat, all characters have 10 hit points." (`CHARACTER_HIT_POINTS`)
- "The character with the greater skill level relevant to the tactic he
  is using generally goes first in the combat round... If the skill is
  the same, the characters go in random order." (`_acts_first`)
- "Neutral Kingdoms are aided by an Order of Duelists. All Neutral
  characters... fight with a +1 modifier to their Melee and Archery
  abilities." (`Combatant.neutral_duelist_bonus`)

**[5.3] Melee**: "You can enter melee even if you have no skill in melee
combat... A character has a base chance to hit of 50%, and does 1-6
damage points per swing." -- flat 50%, **not** skill-scaled (unlike Fire
Arrow); the Melee `Ability` level still matters for initiative ordering
per [5.0]'s generic rule, just not for the hit chance itself.

**[5.2] Fire Arrow**: "You can have a number of free attacks equal to
the level of archery skill... The base chance to hit is 30%, plus 10%
per Archery level, and the damage is 1-6 hit points." Each combatant
gets exactly that many attacks this module's own duel resolver, then
stops (see "Explicitly out of scope" below for what real combat would
do next).

**Phase 132 addendum -- monster-specific melee damage.** Wiring this
core into Search (rulebook [3.3], guardian-monster combat) needs a
*monster* combatant, not just a character one. The rulebook's own
Monster Table (quoted above) gives each species its own melee damage
die -- Giant `1-7`, Elasmosaurus `1-7`, vs. the character-only `1-6`
from [5.3] -- so a monster combatant can't just reuse
`MELEE_DAMAGE_RANGE` unmodified without silently flattening real,
sourced per-species data. `Combatant.melee_damage_range` (default
`MELEE_DAMAGE_RANGE`, so every existing character-vs-character caller
-- Duel, Challenge, Pursue -- is unaffected) lets `turn/
search_execution.py` populate a monster's own die from `models/monster
.py MONSTER_STATS`. The hit-chance formula itself (flat 50%) stays the
single sourced rule from [5.3], applied symmetrically to both
combatants -- no monster-specific hit-chance alternative exists in any
available source, so inventing one would be exactly the kind of guess
this project avoids; reusing the only sourced formula, for both sides,
is the documented, narrower choice.

**Explicitly out of scope this phase** (each is a real, sourced
rulebook mechanic, just not attempted yet):
- **Steal, Negotiate/Talk/Say/Fulfill, Flee, Scout, Give** ([5.4]-[5.8])
  -- every tactic except Melee and Fire Arrow.
- **Casting spells / using magic items in combat** ([5.1]) -- no
  spell-effect or magic-item system exists anywhere in this project.
- **Mixed-tactic range transitions**: real combat starts at Spell range
  and both combatants' *different* preferred tactics can force closing
  through Bow range to Melee range, each closing move consuming a round
  for whoever orders it. This module's two duel resolvers each assume
  *both* combatants use the *same* tactic for the whole encounter (a
  Melee duel or a Fire Arrow duel), sidestepping the range-transition
  state machine entirely -- a documented scope-narrowing choice, not a
  claim that mixed tactics don't matter.
- **"About double" free attacks when both combatants have Archery
  skill** ([5.2]): "if two characters with archery skill fight each
  other, they will both get about double their usual number of free
  attacks. However, there is some random chance involved" -- no
  concrete formula given ("about double", "some random chance"), so
  `resolve_fire_arrow_duel` always uses the plain `archery_skill` free-
  attack count, never doubled.
- **What happens after Fire Arrow's free attacks run out with nobody
  dead**: real combat would presumably continue at Melee range;
  `resolve_fire_arrow_duel` just stops and reports no winner
  (`winner=None`) -- see its own docstring.
- **Temper's effect on Melee** ("A character's Temper affects melee
  according to the Temper Table"): this project has no `Temper` model
  anywhere (no enum, no per-leader field) -- an entirely separate,
  unstarted piece of character data, not merely an unwired mechanic.
- **Victory and Death's aftermath** ([5.9]): looting a vanquished foe's
  treasure, magic items changing hands, and (for a slain King) his
  eldest son taking over with *player-chosen* starting ability levels --
  the last of these needs interactive player choice this automated
  engine has no channel for at all, not just missing game-state logic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# [5.0]: "In combat, all characters have 10 hit points. Monsters may
# have anywhere from 7 to 50 hit points." -- this module's own
# Combatant.hit_points defaults to the character value; a monster
# combatant supplies its own value explicitly.
CHARACTER_HIT_POINTS = 10

# [5.3] Melee: flat 50% base chance, 1-6 damage -- not skill-scaled.
MELEE_HIT_CHANCE = 0.50
MELEE_DAMAGE_RANGE = (1, 6)

# [5.2] Fire Arrow: 30% + 10%/Archery level, 1-6 damage.
FIRE_ARROW_BASE_HIT_CHANCE = 0.30
FIRE_ARROW_HIT_CHANCE_PER_LEVEL = 0.10
FIRE_ARROW_DAMAGE_RANGE = (1, 6)

# [5.0]: Neutral Kingdom characters' "Order of Duelists" +1 Melee/Archery.
NEUTRAL_DUELIST_BONUS = 1


@dataclass(slots=True)
class Combatant:
    name: str
    hit_points: int = CHARACTER_HIT_POINTS
    # Ability.MELEE level -- only feeds initiative ordering ([5.0]), not
    # the flat 50% Melee hit chance itself ([5.3]).
    melee_skill: int = 0
    # Ability.ARCHERY level -- feeds both Fire Arrow's hit chance and its
    # free-attack count ([5.2]).
    archery_skill: int = 0
    neutral_duelist_bonus: bool = False
    # This combatant's own Melee damage die -- defaults to the character
    # rule ([5.3]: "does 1-6 damage points per swing"). A monster
    # combatant overrides it with its own species die from
    # `models/monster.py MONSTER_STATS` -- see Phase 132 addendum above.
    melee_damage_range: tuple[int, int] = MELEE_DAMAGE_RANGE


def effective_melee_skill(combatant: Combatant) -> int:
    return combatant.melee_skill + (NEUTRAL_DUELIST_BONUS if combatant.neutral_duelist_bonus else 0)


def effective_archery_skill(combatant: Combatant) -> int:
    return combatant.archery_skill + (NEUTRAL_DUELIST_BONUS if combatant.neutral_duelist_bonus else 0)


def fire_arrow_hit_chance(archery_skill: int) -> float:
    """Rulebook [5.2]: "The base chance to hit is 30%, plus 10% per Archery level."."""

    return FIRE_ARROW_BASE_HIT_CHANCE + FIRE_ARROW_HIT_CHANCE_PER_LEVEL * archery_skill


def fire_arrow_free_attacks(archery_skill: int) -> int:
    """Rulebook [5.2]: "a number of free attacks equal to the level of archery skill."."""

    return archery_skill


def roll_melee_attack(rng: random.Random, damage_range: tuple[int, int] = MELEE_DAMAGE_RANGE) -> int:
    """Rulebook [5.3]: one Melee swing. Returns damage dealt (0 on a miss).

    ``damage_range`` defaults to the character rule; pass an attacker's
    own ``Combatant.melee_damage_range`` for a species-specific die
    (Phase 132 addendum, module docstring).
    """

    if rng.random() < MELEE_HIT_CHANCE:
        return rng.randint(*damage_range)
    return 0


def roll_fire_arrow_attack(archery_skill: int, rng: random.Random) -> int:
    """Rulebook [5.2]: one Fire Arrow shot. Returns damage dealt (0 on a miss)."""

    if rng.random() < fire_arrow_hit_chance(archery_skill):
        return rng.randint(*FIRE_ARROW_DAMAGE_RANGE)
    return 0


def _acts_first(skill_a: int, skill_b: int, rng: random.Random) -> bool:
    """Rulebook [5.0]: "The character with the greater skill level relevant to the
    tactic he is using generally goes first in the combat round... If
    the skill is the same, the characters go in random order." Returns
    True if the first combatant (by caller's own ordering) acts first.
    """

    if skill_a > skill_b:
        return True
    if skill_b > skill_a:
        return False
    return rng.random() < 0.5


@dataclass(slots=True)
class EncounterCombatResult:
    winner: str | None  # "a" / "b" / None (both survived -- see each resolver's docstring)
    rounds: int


def resolve_melee_duel(
    a: Combatant, b: Combatant, rng: random.Random, *, max_rounds: int = 1000
) -> EncounterCombatResult:
    """Rulebook [5.3]: repeated Melee rounds until one combatant's hit points reach 0.

    Mutates ``a``/``b`` in place (``hit_points`` decreases as damage
    lands, using each attacker's own ``melee_damage_range`` -- Phase 132
    addendum). Both combatants are assumed to fight with Melee only for
    the whole encounter -- see module docstring for why mixed tactics and
    range transitions aren't modeled. ``max_rounds`` is a defensive
    engineering cap, not a rulebook rule -- with a 50% hit chance and
    1-6 damage against 10 hit points, a real duel ends in a handful of
    rounds; 1000 only guards against a pathological caller-supplied
    ``rng`` that never lands a hit.
    """

    skill_a, skill_b = effective_melee_skill(a), effective_melee_skill(b)
    for round_number in range(1, max_rounds + 1):
        first, second = (a, b) if _acts_first(skill_a, skill_b, rng) else (b, a)
        for attacker, defender in ((first, second), (second, first)):
            if attacker.hit_points <= 0 or defender.hit_points <= 0:
                continue
            defender.hit_points -= roll_melee_attack(rng, damage_range=attacker.melee_damage_range)
            if defender.hit_points <= 0:
                return EncounterCombatResult(winner=("a" if defender is b else "b"), rounds=round_number)
    return EncounterCombatResult(winner=None, rounds=max_rounds)


def resolve_fire_arrow_duel(a: Combatant, b: Combatant, rng: random.Random) -> EncounterCombatResult:
    """Rulebook [5.2]: each combatant fires up to ``fire_arrow_free_attacks(archery_skill)``
    shots, interleaved round-by-round by initiative (higher Archery
    skill first, tie random -- see ``_acts_first``). Stops once one
    combatant dies, or once both have exhausted their free attacks with
    neither dead (``winner=None`` -- real combat would presumably
    continue at Melee range; not modeled here, see module docstring).

    Mutates ``a``/``b`` in place. The round-by-round interleaving for
    *unequal* free-attack counts is itself a documented design choice
    (the rulebook gives each combatant's total count, not how two
    different counts interleave against each other) -- implemented as
    "whoever still has shots left fires this round, in initiative
    order," which naturally lets the higher-Archery combatant keep
    firing solo once the other runs out.
    """

    skill_a, skill_b = effective_archery_skill(a), effective_archery_skill(b)
    shots_a, shots_b = fire_arrow_free_attacks(skill_a), fire_arrow_free_attacks(skill_b)
    used_a = used_b = 0
    total_rounds = max(shots_a, shots_b)

    round_number = 0
    for round_number in range(1, total_rounds + 1):
        order = (a, b) if _acts_first(skill_a, skill_b, rng) else (b, a)
        for combatant in order:
            if a.hit_points <= 0 or b.hit_points <= 0:
                break
            if combatant is a:
                if used_a >= shots_a:
                    continue
                used_a += 1
                b.hit_points -= roll_fire_arrow_attack(skill_a, rng)
            else:
                if used_b >= shots_b:
                    continue
                used_b += 1
                a.hit_points -= roll_fire_arrow_attack(skill_b, rng)
        if a.hit_points <= 0 or b.hit_points <= 0:
            break

    if b.hit_points <= 0:
        return EncounterCombatResult(winner="a", rounds=round_number)
    if a.hit_points <= 0:
        return EncounterCombatResult(winner="b", rounds=round_number)
    return EncounterCombatResult(winner=None, rounds=round_number)
