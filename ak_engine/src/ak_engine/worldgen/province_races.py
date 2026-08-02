"""Province base race assignment (Phase 355): ``AKGEN.EXE``'s ``base_race_and_tax``.

Third phase of the world-generation sub-plan. Source:
``world_generation.province_races`` (routine ``base_race_and_tax``
0B57:9575).

**Confirmed exactly** and implemented here -- the ordinary (non-Sea,
non-special-overwrite) per-province race draw, a two-stage process:

1. A **provisional race draw**, terrain-specific. Only two terrains
   have their pre-mix split stated directly in the source
   (``pre_common_rule``): Forest is 60% Human/40% Elf; Mountains is
   30% Dwarf, then (of the remaining 70%) 15% Orc/85% Human, i.e. 30%
   Dwarf / 10.5% Orc / 59.5% Human. Plains/Desert/Jungle have no
   stated pre-mix split, but back-solving the confirmed final
   percentages against the mix formula below (step 2) shows they are
   100% provisional Human -- their entire 77.5/7.5/7.5/7.5 split comes
   purely from the mix layer, confirmed by exact arithmetic match (see
   module tests). Sea (and ``noterr``) provisionally draw 100% Norace,
   untouched by the mix layer below.
2. The **common humanoid mix**: "Only while the provisional race is
   Human: probability 0.30 to replace it with a uniform ``IRand AND
   3`` result among Human, Elf, Dwarf and Orc." ``IRand AND 3``'s four
   equally-likely outcomes 0..3 line up exactly with this project's
   own ``Race`` ordinals (``HUMAN=0, ELVEN=1, DWARVEN=2, ORCISH=3``,
   ``models/race.py``) -- realized here as ``rng.irand() & 3`` (a
   literal bitwise AND, matching the source's own stated operation,
   not just an equivalent ``% 4``). Net effect: 70% + 30%*25% = 77.5%
   of provisional-Human stays/rerolls-to Human, 7.5% each to
   Elf/Dwarf/Orc -- reproducing Plains/Desert/Jungle's confirmed table
   outright, and combining with each terrain's own provisional split
   to reproduce Forest's and Mountains's tables exactly (verified in
   this module's own tests, matching every value in
   ``base_percent_before_special_overwrites`` to within floating-point
   tolerance).

No new ``Race`` members were needed: this project's pre-existing
``models/race.py Race`` enum (Phase 20, extended through Phase 87)
already has every race this table references (``HUMAN``, ``ELVEN``,
``DWARVEN``, ``ORCISH``, ``NO_RACE``) plus every *special*-race name
the source's own ``special_race_calls_in_order`` names (``EAGLES``,
``ENTISH``, ``MERMISH``, ``TROLLISH``, ``DRAGONS``, ``WHALES``,
``WEREFOLK``) -- another exact cross-validation, zero correction
needed.

**Deliberately NOT implemented here**: the *special-race overwrite*
pass (Eagles/Ents/Mermen/Trolls/Dragons/Whales/Werefolk get placed
onto random provinces of the right terrain *after* this base draw,
overwriting whatever race landed there). Unlike the base draw above,
that pass needs the whole generated map plus per-province six-neighbor
adjacency rejection sampling (an attempt-capped rejection loop much
like Phase 354's own hole-filling pass) -- a separate spatial
algorithm in its own right, scoped out to its own follow-up phase
rather than folded in here, the same way Phase 353 (formulas) and
Phase 354 (spatial assembly) were kept as two separate phases for
``place_map``.

**Verification**: `draw_base_race()` is exercised by a 200,000-draw
Monte Carlo per terrain, matching every terrain's confirmed final
percentage in ``base_percent_before_special_overwrites`` to within
0.4 percentage points -- the same empirical bar this project's other
weighted-draw formulas (e.g. `map_shape.draw_terrain`) already meet.
"""

from __future__ import annotations

from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.worldgen.pascal_random import PascalRandom

HUMANOID_MIX_CHANCE = 0.30

# IRand AND 3 -> 0..3, lined up with Race's own real ordinals (HUMAN=0,
# ELVEN=1, DWARVEN=2, ORCISH=3).
_HUMANOID_MIX_RACES: tuple[Race, ...] = (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH)

# Provisional (pre-mix) race weights per terrain, scaled x10 to stay
# integral for an exact IRand-modulo draw (Mountains' 10.5%/59.5% need
# the extra digit of precision).
_PROVISIONAL_WEIGHTS_X10: dict[Terrain, dict[Race, int]] = {
    Terrain.PLAINS: {Race.HUMAN: 1000},
    Terrain.DESERT: {Race.HUMAN: 1000},
    Terrain.JUNGLE: {Race.HUMAN: 1000},
    Terrain.FOREST: {Race.HUMAN: 600, Race.ELVEN: 400},
    Terrain.MTNS: {Race.DWARVEN: 300, Race.ORCISH: 105, Race.HUMAN: 595},
}

_SEA_PROVISIONAL = Race.NO_RACE


def _draw_provisional_race(terrain: Terrain, rng: PascalRandom) -> Race:
    weights = _PROVISIONAL_WEIGHTS_X10.get(terrain)
    if weights is None:
        return _SEA_PROVISIONAL
    total = sum(weights.values())
    roll = rng.irand() % total
    cumulative = 0
    for race, weight in weights.items():
        cumulative += weight
        if roll < cumulative:
            return race
    return next(iter(weights))


def draw_base_race(terrain: Terrain, rng: PascalRandom) -> Race:
    """The ordinary per-province race draw, before any special-race overwrite."""

    provisional = _draw_provisional_race(terrain, rng)
    if provisional is not Race.HUMAN:
        return provisional
    if rng.random() < HUMANOID_MIX_CHANCE:
        return _HUMANOID_MIX_RACES[rng.irand() & 3]
    return Race.HUMAN
