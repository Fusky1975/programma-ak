"""Special-race province overwrite placement (Phase 362): fills the
spatial gap Phase 355 deliberately left open for
``province_races.py``'s own confirmed formulas -- at the user's
explicit request to close the world-generation integration gaps, the
same "turn the narrative into an algorithm, replace it outright if the
exact routine is ever recovered" treatment already given to `place_map`
(Phase 354).

First phase of the pipeline-integration sub-plan. Source:
``world_generation.province_races.special_race_calls_in_order`` /
``special_acceptance`` / ``special_race_multiplier``.

**Confirmed exactly** and implemented here:

- ``SPECIAL_RACE_BASE_COUNT``: Eagles 4, Ents 3, Mermen 4, Trolls 4,
  Dragons 4, Whales 7, Werefolk 3 -- each multiplied by
  ``special_race_multiplier`` (``1`` old rules, ``3`` new rules) to
  get the real placement count (verified against the source's own
  ``old_count``/``new_count`` pairs for all seven races, e.g. Whales
  ``7*1=7``/``7*3=21``).
- Per-race terrain eligibility: Eagles Mountains-only; Ents
  Jungle-or-Forest; Trolls Jungle-through-Mountains; Dragons
  Desert-through-Mountains; Werefolk any ordinary land; Whales
  Sea-only. Mermen are the one special case: Sea is always eligible,
  and Jungle is eligible only via the confirmed
  ``merman_jungle_rule`` -- "requires at least one Sea neighbor and
  accepts using a coast-count versus IRand AND 7 comparison; greater
  Sea adjacency raises acceptance", realized as ``coast_score(coord)
  > (rng.irand() & 7)`` (a literal reuse of Phase 356's own
  `province_tax.coast_score()`, and the same "count > IRand AND 7"
  shape as that phase's own confirmed `second_slot_gate`).
- The confirmed rejection-sampling accept/reject rules, applied in the
  source's own stated order and applied to every one of the seven
  races in the source's own stated call order (Eagles, Ents, Mermen,
  Trolls, Dragons, Whales, Werefolk): reject if the coordinate is a
  King's Home; reject if the coordinate already carries a special
  race; reject if any of the coordinate's own six hex neighbors
  already carries a special race (reusing this project's own
  real-data-confirmed hex adjacency, `turn/movement.py neighbors()`,
  the same reuse pattern as `place_map`'s hole-filling and
  `province_tax`'s own `coast_score`); reject if the coordinate's
  terrain isn't eligible for this race. ``ATTEMPT_CAP = 3000`` matches
  the source's own declared "approx" cap.
- ``recompute_tax()``: "on_accept: overwrite prace and recompute tax"
  -- since Phase 356's own confirmed tax formulas are purely
  terrain-driven (never race-driven), "recomputing" a province's tax
  after a special-race overwrite is exactly a fresh call to whichever
  of `province_tax.py`'s own confirmed formulas already matches that
  coordinate's (unchanged) terrain -- `true_sea_tax()` for Sea,
  `ordinary_land_tax()` otherwise. No new tax formula is introduced
  here; this function is a thin, direct reuse of Phase 356's own work.

**Deliberately NOT implemented here**: the exact spatial *order* in
which multiple simultaneous acceptance attempts might interleave
across races within a single real game (the source gives one call
order for the seven races, which this module follows exactly, but
says nothing about e.g. whether all of one race's placements happen
strictly before the next race starts within the real routine, versus
some other interleaving) -- this module places each race's full quota
before moving to the next, the most literal reading of "calls in
order".

**Verification**: `special_race_count()` is checked against all seven
of the source's own declared old/new count pairs directly.
Terrain-eligibility tables are checked per race. The rejection rules
are each exercised individually (existing special race, neighboring
special race, King Home, ineligible terrain) with a scenario
engineered so only the rule under test can block acceptance. The
Merman jungle rule is Monte Carlo-checked against its own `coast_score
> IRand AND 7` shape. The attempt cap is checked to terminate (return
``None``) rather than loop forever when no eligible coordinate exists
at all.
"""

from __future__ import annotations

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.province_tax import (
    coast_score,
    compute_edge_score,
    ordinary_land_tax,
    true_sea_tax,
)

SPECIAL_RACE_BASE_COUNT: dict[Race, int] = {
    Race.EAGLES: 4,
    Race.ENTISH: 3,
    Race.MERMISH: 4,
    Race.TROLLISH: 4,
    Race.DRAGONS: 4,
    Race.WHALES: 7,
    Race.WEREFOLK: 3,
}

# The source's own stated call order.
SPECIAL_RACE_ORDER: tuple[Race, ...] = (
    Race.EAGLES,
    Race.ENTISH,
    Race.MERMISH,
    Race.TROLLISH,
    Race.DRAGONS,
    Race.WHALES,
    Race.WEREFOLK,
)

OLD_RULES_MULTIPLIER = 1
NEW_RULES_MULTIPLIER = 3

ATTEMPT_CAP = 3000

_ORDINARY_LAND_TERRAINS: dict[Race, tuple[Terrain, ...]] = {
    Race.EAGLES: (Terrain.MTNS,),
    Race.ENTISH: (Terrain.JUNGLE, Terrain.FOREST),
    Race.TROLLISH: (Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS),
    Race.DRAGONS: (Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS),
    Race.WEREFOLK: (Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS),
    Race.WHALES: (Terrain.SEA,),
}


def special_race_count(race: Race, multiplier: int) -> int:
    """``base_count * multiplier`` (``1`` old rules, ``3`` new rules)."""

    return SPECIAL_RACE_BASE_COUNT[race] * multiplier


def is_terrain_eligible(
    race: Race,
    terrain: Terrain,
    coord: HexCoord,
    grid: dict[HexCoord, Terrain],
    bounds: MapBounds,
    rng: PascalRandom,
) -> bool:
    """Per-race terrain eligibility, including the Merman coastal-Jungle special case."""

    if race is Race.MERMISH:
        if terrain is Terrain.SEA:
            return True
        if terrain is Terrain.JUNGLE:
            coast = coast_score(coord, grid, bounds)
            if coast < 1:
                return False
            return coast > (rng.irand() & 7)
        return False
    return terrain in _ORDINARY_LAND_TERRAINS[race]


def _has_special_race(coord: HexCoord, race_grid: dict[HexCoord, Race]) -> bool:
    race = race_grid.get(coord)
    return race is not None and race in SPECIAL_RACE_BASE_COUNT


def place_special_race(
    race: Race,
    grid: dict[HexCoord, Terrain],
    race_grid: dict[HexCoord, Race],
    bounds: MapBounds,
    king_homes: frozenset[HexCoord],
    rng: PascalRandom,
) -> HexCoord | None:
    """One rejection-sampled placement attempt sequence; ``None`` if the attempt cap is exhausted."""

    for _ in range(ATTEMPT_CAP):
        coord = HexCoord(rng.irand() % bounds.width, rng.irand() % bounds.height)
        if coord in king_homes:
            continue
        if _has_special_race(coord, race_grid):
            continue
        if any(_has_special_race(n, race_grid) for n in neighbors(coord, bounds)):
            continue
        terrain = grid.get(coord)
        if terrain is None:
            continue
        if not is_terrain_eligible(race, terrain, coord, grid, bounds, rng):
            continue
        race_grid[coord] = race
        return coord
    return None


def place_all_special_races(
    grid: dict[HexCoord, Terrain],
    race_grid: dict[HexCoord, Race],
    bounds: MapBounds,
    king_homes: frozenset[HexCoord],
    rng: PascalRandom,
    *,
    new_rules: bool = True,
) -> dict[Race, list[HexCoord]]:
    """Places every special race's own full quota, in the source's own confirmed call order."""

    multiplier = NEW_RULES_MULTIPLIER if new_rules else OLD_RULES_MULTIPLIER
    placements: dict[Race, list[HexCoord]] = {}
    for race in SPECIAL_RACE_ORDER:
        count = special_race_count(race, multiplier)
        placed: list[HexCoord] = []
        for _ in range(count):
            coord = place_special_race(race, grid, race_grid, bounds, king_homes, rng)
            if coord is not None:
                placed.append(coord)
        placements[race] = placed
    return placements


def recompute_tax(
    coord: HexCoord,
    terrain: Terrain,
    grid: dict[HexCoord, Terrain],
    bounds: MapBounds,
    bottom_y: int,
    rng: PascalRandom,
) -> int:
    """"on_accept: ... recompute tax" -- reuses Phase 356's own confirmed terrain-driven formulas."""

    if terrain is Terrain.SEA:
        coast = coast_score(coord, grid, bounds)
        is_edge_row = coord.y in (0, bounds.height - 1)
        edge = compute_edge_score(coast, is_edge_row, rng)
        return true_sea_tax(edge, rng)
    return ordinary_land_tax(terrain, rng)
