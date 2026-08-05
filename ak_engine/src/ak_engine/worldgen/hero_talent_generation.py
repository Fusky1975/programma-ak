"""Hero skill and aptitude generation (Phase 385): ``AKGEN.EXE``'s own
"Init Tr" stage -- rolls a starting ``Alignment``, ``Ability`` skill
levels, and ``Ability`` aptitude levels for every non-King leader slot in
the generated pool.

Source: ``world_generation.hero_talents_and_aptitudes``.

**Confirmed exactly** (formulas cross-checked self-consistently against
the source's own reported probabilities -- see below) and implemented
here:

- ``roll_alignment()``: "1 + trunc(Random*5)" -> `Alignment` ordinals
  1-5 (`GOOD`..`EVIL` on this project's own real `ALIGNMENT_ORDINAL`
  sequence, Phase 162) -- Divine/Undead are confirmed excluded from this
  ordinary roll (a King-only or special-event alignment).
- ``roll_primary_ability()``: "50% hero_id AND 15, 50% IRand AND 15;
  either branch rerolls uniformly over the 15 real abilities if it lands
  on the out-of-range 16th value". Verified self-consistent against all
  three of the source's own reported probabilities (8/15 when hero_id
  mod 16 equals the ability's own ordinal, 1/30 for every other ability,
  uniform 1/15 in the id_mod16==15 edge case) by hand-deriving each from
  the formula before writing it.
- ``primary_increment()``: "1 + trunc(Random*1.6)" -> 1 (62.5%) or 2
  (37.5%) -- the chosen primary ability's own starting skill level,
  except Druidism is unconditionally forced to exactly 1 regardless of
  the roll.
- ``roll_skill_table()``: Archery, Melee and Sageness each separately
  get their own 35%-chance +1 skill level, independent of (and additive
  with) the primary-ability roll above -- confirmed by the source's own
  stated "theoretical_mean_total_skill_levels" of 2.4: the primary
  roll's own mean (0.625*1 + 0.375*2 = 1.375) plus three independent
  0.35 draws (1.05) totals 2.425, matching within rounding.
- ``roll_aptitude()``: "min(5, skill[a] + trunc(U*V*5.7*Apt_Mod(hero,a)))",
  ``U``/``V`` independent ``Random()`` draws per ability, ``Apt_Mod`` = 2
  if the hero's own alignment matches that ability's own favored
  alignment, else 1. ``FAVORED_ALIGNMENT`` below transcribes the
  source's own 15-entry ``favored_alignment_table``, cross-checked two
  independent ways before use: (1) the 5 "never favored" abilities
  (Tactical/March/Naval/Archery/Melee) all carry the source's own
  sentinel raw value 9, which is ``Alignment.SPECIAL``'s own real
  ordinal (Phase 162) -- no hero is ever generated with that alignment
  via ``roll_alignment()`` above, so the sentinel correctly never
  matches; (2) the other 10 raw ordinals were individually decoded
  through this project's own ``ALIGNMENT_BY_ORDINAL`` and checked
  against the source's own separately-stated ``favored_pairs`` table
  (e.g. raw value 1 for ``Ability.WHITE`` decodes to ``Alignment.GOOD``,
  matching ``favored_pairs``' own "Good: [White Magic, Sageness]") --
  all 15 entries matched with zero discrepancies.

**Deliberately NOT implemented here**: the real DOS clock-word startup
seed (``world_generation.hero_talents_and_aptitudes.rng`` -- already
documented as unrecoverable in ``worldgen/pascal_random.py``'s own
docstring since Phase 352); ``post_generation_layers`` (historical-
country bonuses, Divine/Undead King alignment modifiers, the Valhalla
special Hero sheet, and later in-game places/items/discoveries/
experience) -- each a separate, later mechanic with its own real source
still needed. These functions take a ``PascalRandom`` the caller
supplies (any seed), matching this project's own established pattern
for formulas whose real seed is unrecoverable but whose formula is
confirmed (``internal_magical_locations.py``, Phase 361). The
``SkillTable``'s own 31st trailing value (Phase 21: "still unconfirmed"
even what it represents) is left at 0 -- not modeled here either.

**Verification**: ``roll_primary_ability()``'s own three probability
splits, and ``roll_aptitude()``'s own raw-increment distribution (the
source's own ``raw_increment_distribution_percent.normal_m1``/
``favored_m2`` tables), are Monte Carlo-checked in the test suite
against the source's own quoted percentages.
"""

from __future__ import annotations

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.kingdom import SkillTable
from ak_engine.worldgen.pascal_random import PascalRandom

# "1 + trunc(Random*5)", positional with the roll's own 1-5 range.
ORDINARY_ALIGNMENT_ROLL: tuple[Alignment, ...] = (
    Alignment.GOOD,
    Alignment.DRUID,
    Alignment.NEUTRAL,
    Alignment.PAGAN,
    Alignment.EVIL,
)

INDEPENDENT_TRAINING_ABILITIES: tuple[Ability, ...] = (
    Ability.ARCHERY,
    Ability.MELEE,
    Ability.SAGE,
)
INDEPENDENT_TRAINING_CHANCE = 0.35

# Alignment.SPECIAL's own real ordinal (Phase 162) -- the source's own
# "never favored" sentinel; no hero is ever generated with this
# alignment via roll_alignment(), so it correctly never matches.
_NEVER_FAVORED_SENTINEL = 9

# `favored_alignment_table`'s own raw values, verbatim, positional with
# `Ability`'s own real ordinals -- see module docstring for the two
# independent cross-checks performed before use.
_FAVORED_ALIGNMENT_RAW: tuple[int, ...] = (9, 9, 9, 9, 9, 1, 5, 4, 2, 3, 2, 5, 4, 3, 1)

FAVORED_ALIGNMENT: dict[Ability, Alignment | None] = {
    ability: (None if raw == _NEVER_FAVORED_SENTINEL else ALIGNMENT_BY_ORDINAL[raw])
    for ability, raw in zip(Ability, _FAVORED_ALIGNMENT_RAW, strict=True)
}


def roll_alignment(rng: PascalRandom) -> Alignment:
    """"1 + trunc(Random*5)" -- Good/Druidic/Neutral/Pagan/Evil, each 20%."""

    index = int(rng.random() * 5)
    return ORDINARY_ALIGNMENT_ROLL[index]


def roll_primary_ability(hero_id: int, rng: PascalRandom) -> Ability:
    """"50% hero_id AND 15, 50% IRand AND 15; 15 rerolls uniformly over
    the 15 real abilities" -- see module docstring for the probability
    cross-check (8/15 own-ordinal, 1/30 every other ability).
    """

    if rng.random() < 0.5:
        id_mod16 = hero_id & 15
        if id_mod16 <= 14:
            return Ability(id_mod16)
        return Ability(rng.irand() % 15)

    draw = rng.irand() & 15
    if draw == 15:
        return Ability(rng.irand() % 15)
    return Ability(draw)


def primary_increment(ability: Ability, rng: PascalRandom) -> int:
    """"1 + trunc(Random*1.6)", except Druidism is forced to exactly 1."""

    if ability is Ability.DRUID:
        return 1
    return 1 + int(rng.random() * 1.6)


def roll_skill_table(hero_id: int, rng: PascalRandom) -> SkillTable:
    """The full skill half of hero generation: independent Archery/Melee/
    Sageness training (additive with, not exclusive of) the primary-
    ability roll. Aptitude slots and the 31st trailing value are left 0
    -- fill aptitude with ``roll_aptitude()``/``roll_skill_and_aptitude_
    table()``.
    """

    levels = [0] * len(Ability)
    for ability in INDEPENDENT_TRAINING_ABILITIES:
        if rng.random() < INDEPENDENT_TRAINING_CHANCE:
            levels[ability.value] += 1

    primary = roll_primary_ability(hero_id, rng)
    levels[primary.value] += primary_increment(primary, rng)

    raw_values = [0] * 31
    for ability in Ability:
        raw_values[ability.value * 2] = levels[ability.value]
    return SkillTable(raw_values=raw_values)


def raw_aptitude_increment(apt_mod: int, rng: PascalRandom) -> int:
    """"trunc(U*V*5.7*Apt_Mod)" alone, before adding skill/capping at 5
    -- exposed separately so it can be Monte Carlo-checked against the
    source's own ``raw_increment_distribution_percent`` tables.
    """

    u = rng.random()
    v = rng.random()
    return int(u * v * 5.7 * apt_mod)


def roll_aptitude(ability: Ability, skill: int, alignment: Alignment, rng: PascalRandom) -> int:
    """"min(5, skill + trunc(U*V*5.7*Apt_Mod))", Apt_Mod=2 if favored else 1."""

    apt_mod = 2 if FAVORED_ALIGNMENT[ability] is alignment else 1
    return min(5, skill + raw_aptitude_increment(apt_mod, rng))


def roll_skill_and_aptitude_table(hero_id: int, alignment: Alignment, rng: PascalRandom) -> SkillTable:
    """Full generation: the skill table, then aptitude filled in for
    every ability from its own already-rolled skill level.
    """

    table = roll_skill_table(hero_id, rng)
    for ability in Ability:
        skill, _ = table.pair_for_ability(ability)
        aptitude = roll_aptitude(ability, skill, alignment, rng)
        table.set_pair_for_ability(ability, skill, aptitude)
    return table
