"""King Home province selection + second recruit slot (Phase 427).

**Project-original, sourced directly from the user's own play experience
with the real game (2026-08-07) -- not from the AKGEN disassembly.**
`AKGEN_reverse_engineering_report.md` confirms random-map King
placement is constrained ("nella mappa casuale la posizione deve essere
umanoide, libera e deve superare i controlli di distanza/giocabilità")
but never states what those "distance/playability checks" actually are
-- a genuine, confirmed-real, confirmed-undocumented gap (re-verified
directly against the report: no scan order, no distance formula, no
percentage table for any of this exists anywhere in the material). This
module fills that gap with the user's own domain knowledge instead of a
guess, the same "user-confirmed design choice" category this project
already used for the Island-province system (`turn/island_provinces.py`,
Phase 282) and `MeritTally` (Phase 277).

**The rules, exactly as given by the user, with their own follow-up
clarifications on the three genuinely ambiguous points:**

- Home provinces must be at least ``MIN_HOME_DISTANCE`` hexes apart --
  straight-line ``turn/movement.py hex_distance()``, not a pathfinding
  distance (the user confirmed this is the intended distance measure).
- Home terrain is **never** Sea and **never** Desert, in both branches
  below (the user confirmed "no Desert" is a global rule, not scoped to
  the non-Naval branch alone).
- **Naval branch**: if the King's own ``LeaderState.skills`` show a
  nonzero ``Ability.NAVAL`` skill level ("chose Naval as an initial
  talent" -- Kings don't roll random talents in this project the way
  non-King Heroes do via `worldgen/hero_talent_generation.py`, so this
  reads the caller-supplied skill table instead, per the user's own
  confirmed mapping), the Home province must have at least one Sea-
  adjacent neighbor, and its second recruit slot is ``FLEET``.
- **Non-Naval branch**: Home terrain is drawn uniformly among Plains/
  Jungle/Forest/Mtns. Jungle's second recruit slot is ``ELEPHANTS``;
  Plains/Forest/Mtns' second slot is drawn uniformly among Light
  Cavalry/Heavy Cavalry/Chariots -- no percentage split for this
  specific draw exists anywhere in the AKGEN material (checked
  directly), and the user confirmed an equal-probability (1/3 each)
  project-original default is acceptable here. **Orcish override
  (2026-10-25)**: regardless of terrain, an Orcish King's second
  recruit slot is always ``WARG_RIDERS`` -- see ``second_recruit_
  slot()``'s own docstring addendum for the full sourcing.

First-recruit-slot-by-race (Human->Legion, Elf->Bowmen, Dwarf->Axemen,
Orc->Phalanx) needed no new work here -- it was already fully
implemented and matches the user's own description exactly
(`worldgen/initial_armies.py BEST_ATYPE`/`home_first_slot()`, Phase 358).
"""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.movement import MapBounds, hex_distance, neighbors
from ak_engine.worldgen.pascal_random import PascalRandom

MIN_HOME_DISTANCE = 3

# 2026-11-20, project-original, user-confirmed from their own real-game
# play experience (same sourcing category as this module's other three
# rules -- see module docstring): a King's Home province always has
# exactly one neighboring "Rich" province. Mirrors `report/ascii_map.py
# _status_word()`'s own tax>=7 "Rich" tier threshold -- not imported
# from there (worldgen has no business depending on a report-layer
# helper), just the same project-original number.
RICH_PROVINCE_MIN_TAX = 7
# Rulebook [1.1]: Rich 7-10 tax, Prosperous 3-6, Poor 0-2.
PROSPEROUS_PROVINCE_MIN_TAX = 3
RICH_TAX_RANGE = (7, 10)
PROSPEROUS_TAX_RANGE = (3, 6)

_HUMANOID_RACES: frozenset[Race] = frozenset({Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH})
_HOME_CANDIDATE_TERRAINS: tuple[Terrain, ...] = (Terrain.PLAINS, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS)
_SECOND_SLOT_CAVALRY_OR_CHARIOTS: tuple[ArmyType, ...] = (ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY, ArmyType.CHARIOTS)


def king_is_naval(skills: SkillTable | None) -> bool:
    """"Chose NA (Naval) as an initial talent" -- a nonzero Naval skill level."""

    if skills is None:
        return False
    skill, _aptitude = skills.pair_for_ability(Ability.NAVAL)
    return skill > 0


def _has_sea_neighbor(coord: HexCoord, grid: dict[HexCoord, Terrain], bounds: MapBounds) -> bool:
    return any(grid.get(neighbor) is Terrain.SEA for neighbor in neighbors(coord, bounds))


def _has_exactly_one_rich_neighbor(coord: HexCoord, tax_grid: dict[HexCoord, int], bounds: MapBounds) -> bool:
    """See ``RICH_PROVINCE_MIN_TAX``'s own docstring for the sourcing."""

    rich_neighbors = sum(1 for neighbor in neighbors(coord, bounds) if tax_grid.get(neighbor, 0) >= RICH_PROVINCE_MIN_TAX)
    return rich_neighbors == 1


def _land_neighbors(coord: HexCoord, grid: dict[HexCoord, Terrain], bounds: MapBounds) -> list[HexCoord]:
    return [n for n in neighbors(coord, bounds) if grid.get(n) is not None and grid[n] is not Terrain.SEA]


def _neighbor_wealth(
    coord: HexCoord, grid: dict[HexCoord, Terrain], tax_grid: dict[HexCoord, int], bounds: MapBounds
) -> tuple[int, int]:
    """``(Rich, Prosperous)`` land neighbours of ``coord`` (user 2026-11-27: every King starts with at least one of each
    next to his Home)."""

    taxes = [tax_grid.get(n, 0) for n in _land_neighbors(coord, grid, bounds)]
    rich = sum(1 for tax in taxes if tax >= RICH_PROVINCE_MIN_TAX)
    prosperous = sum(1 for tax in taxes if PROSPEROUS_PROVINCE_MIN_TAX <= tax < RICH_PROVINCE_MIN_TAX)
    return rich, prosperous


def eligible_home_coords(
    grid: dict[HexCoord, Terrain],
    race_grid: dict[HexCoord, Race],
    bounds: MapBounds,
    taken_homes: list[HexCoord],
    *,
    naval: bool,
    tax_grid: dict[HexCoord, int] | None = None,
) -> list[HexCoord]:
    """Every coordinate satisfying terrain/race/distance/(sea-adjacency if
    Naval)/(exactly one Rich neighbor if ``tax_grid`` is given).

    ``tax_grid`` (2026-11-20) is optional and keyword-only so every
    pre-existing caller that doesn't have one yet (none real remain,
    but this keeps the function itself honest about the new
    constraint's own opt-in shape) keeps its prior behavior unchanged.
    When given, candidates are filtered to exactly one Rich neighbor
    first; if that leaves nothing, the caller (``choose_king_home()``)
    is the one that falls back, not this function -- it only ever
    returns the single, most-filtered list for whichever call it got.
    """

    result = []
    for coord, terrain in grid.items():
        if terrain not in _HOME_CANDIDATE_TERRAINS:
            continue
        if race_grid.get(coord) not in _HUMANOID_RACES:
            continue
        if any(hex_distance(coord, taken) < MIN_HOME_DISTANCE for taken in taken_homes):
            continue
        if naval and not _has_sea_neighbor(coord, grid, bounds):
            continue
        if tax_grid is not None and not _has_exactly_one_rich_neighbor(coord, tax_grid, bounds):
            continue
        result.append(coord)
    return result


def choose_king_home(
    grid: dict[HexCoord, Terrain],
    race_grid: dict[HexCoord, Race],
    bounds: MapBounds,
    taken_homes: list[HexCoord],
    rng: PascalRandom,
    *,
    naval: bool,
    tax_grid: dict[HexCoord, int] | None = None,
) -> HexCoord:
    """Uniform random draw among ``eligible_home_coords()``.

    ``tax_grid`` (2026-11-20, project-original, user-confirmed): when
    given, prefers a candidate with exactly one Rich (``tax >=
    RICH_PROVINCE_MIN_TAX``) neighbor -- falling back to the plain
    terrain/race/distance/(sea-adjacency) candidate list, user-
    confirmed, if no coordinate satisfies every constraint at once
    (rather than failing world generation outright over this one new,
    best-effort rule).
    """

    candidates = eligible_home_coords(grid, race_grid, bounds, taken_homes, naval=naval)
    if not candidates:
        raise ValueError(
            "No eligible King Home province found (terrain/race/distance"
            f"{'/sea-adjacency' if naval else ''} constraints) -- map too small or too crowded."
        )
    # A Home needs room for a Rich and a Prosperous neighbour: as many land neighbours as the map allows (4, else 3, else 2).
    for min_land in (4, 3, 2):
        roomy = [c for c in candidates if len(_land_neighbors(c, grid, bounds)) >= min_land]
        if roomy:
            candidates = roomy
            break
    if tax_grid is not None:
        # Preference ladder (best first), each rung only if it leaves a candidate: exactly one Rich neighbour and
        # at least one Prosperous (the earlier rule plus the 2026-11-27 one), at least one of each, exactly one Rich.
        rungs = (
            lambda c: (lambda w: w[0] == 1 and w[1] >= 1)(_neighbor_wealth(c, grid, tax_grid, bounds)),
            lambda c: (lambda w: w[0] >= 1 and w[1] >= 1)(_neighbor_wealth(c, grid, tax_grid, bounds)),
            lambda c: _has_exactly_one_rich_neighbor(c, tax_grid, bounds),
        )
        for accepts in rungs:
            preferred = [c for c in candidates if accepts(c)]
            if preferred:
                candidates = preferred
                break
    return candidates[rng.irand() % len(candidates)]


def ensure_home_wealth(
    homes: list[HexCoord],
    grid: dict[HexCoord, Terrain],
    tax_grid: dict[HexCoord, int],
    bounds: MapBounds,
    rng: PascalRandom,
    *,
    protected: frozenset[HexCoord] = frozenset(),
) -> list[HexCoord]:
    """Guarantees every King's Home at least one Rich and at least one Prosperous neighbouring province (user
    2026-11-27), whatever the later special-race placements did to the taxes the Home was chosen on: a Home still
    short of either gets the best-taxed ordinary neighbouring land province raised into it (a Rich tax 7-10, a
    Prosperous 3-6). Never touches a Home, a ``protected`` province (a special-race one: its tax sizes its army) or a
    province another Home already counts on (Homes are at least ``MIN_HOME_DISTANCE`` apart, so their neighbourhoods do
    not overlap). Returns the Homes that could not be satisfied (too few ordinary neighbours), normally none."""

    home_set = frozenset(homes)
    unsatisfied: list[HexCoord] = []

    def satisfied(taxes: list[int]) -> bool:
        return any(t >= RICH_PROVINCE_MIN_TAX for t in taxes) and any(
            PROSPEROUS_PROVINCE_MIN_TAX <= t < RICH_PROVINCE_MIN_TAX for t in taxes
        )

    def settle(counted: list[HexCoord], modifiable: list[HexCoord]) -> bool:
        """Raises/lowers the fewest, cheapest ``modifiable`` neighbours so the ``counted`` ones hold a Rich and a
        Prosperous; True if it could (or already did)."""

        if satisfied([tax_grid.get(n, 0) for n in counted]):
            return True
        moves: list[tuple[int, HexCoord, str, int]] = []  # (cost, coord, tier, nominal tax)
        for n in sorted(modifiable, key=lambda n: (-tax_grid.get(n, 0), n.x, n.y)):
            old = tax_grid.get(n, 0)
            if old < RICH_PROVINCE_MIN_TAX:
                moves.append((RICH_TAX_RANGE[0] - old, n, "rich", RICH_TAX_RANGE[0]))
            if old < PROSPEROUS_PROVINCE_MIN_TAX:
                moves.append((PROSPEROUS_TAX_RANGE[0] - old, n, "pros", PROSPEROUS_TAX_RANGE[0]))
            elif old >= RICH_PROVINCE_MIN_TAX:
                moves.append((old - PROSPEROUS_TAX_RANGE[1], n, "pros", PROSPEROUS_TAX_RANGE[1]))

        def outcome(changes: list[tuple[int, HexCoord, str, int]]) -> list[int]:
            taxes = {n: tax_grid.get(n, 0) for n in counted}
            for _cost, n, _tier, nominal in changes:
                taxes[n] = nominal
            return list(taxes.values())

        # The cheapest one change, else the cheapest two changes (on two different provinces), that settle the Home.
        singles = [[m] for m in moves if m[1] in counted and satisfied(outcome([m]))]
        pairs = [
            [a, b]
            for ai, a in enumerate(moves)
            for b in moves[ai + 1 :]
            if a[1] != b[1] and satisfied(outcome([a, b]))
        ]
        if singles:
            best = min(singles, key=lambda c: (c[0][0], c[0][1].x, c[0][1].y))
        elif pairs:
            best = min(pairs, key=lambda c: (c[0][0] + c[1][0], c[0][1].x, c[0][1].y, c[1][1].x, c[1][1].y))
        else:
            return False
        for _cost, n, tier, _nominal in best:
            low, high = RICH_TAX_RANGE if tier == "rich" else PROSPEROUS_TAX_RANGE
            tax_grid[n] = low + rng.irand() % (high - low + 1)
        return True

    for home in homes:
        land = _land_neighbors(home, grid, bounds)
        around = [n for n in neighbors(home, bounds) if n in grid]
        free_land = [n for n in land if n not in home_set and n not in protected]
        free_around = [n for n in around if n not in home_set and n not in protected]
        # Land first; then the sea around too; as a last resort a special-race province (its army grows with its tax).
        if (
            settle(land, free_land)
            or settle(around, free_around)
            or settle(around, [n for n in around if n not in home_set])
        ):
            continue
        unsatisfied.append(home)
    return unsatisfied


def second_recruit_slot(terrain: Terrain, rng: PascalRandom, *, naval: bool, king_race: Race | None = None) -> ArmyType:
    """The Home province's own second recruit slot, by the user's own confirmed rules.

    **Orcish override, sourced directly from the user (2026-10-25)**: an
    Orcish King's Home province always gets Warg Riders as its second
    recruit slot, regardless of terrain -- confirmed from the user's own
    observed bug report (a freshly-created Orc King's Home had no Warg
    Riders among its two recruit types). Takes priority over the Jungle
    -> Elephants and random-cavalry-or-chariots rules below (neither of
    which the user scoped this override away from), but not over the
    Naval branch above (a King's own chosen Naval talent is a deliberate
    build choice independent of race). `king_race` defaults to `None`
    for every pre-existing caller (ordinary, non-Home provinces have no
    such override and never call this function at all), so this is a
    pure addition, not a behavior change for any other caller.
    """

    if naval:
        return ArmyType.FLEET
    if king_race is Race.ORCISH:
        return ArmyType.WARG_RIDERS
    if terrain is Terrain.JUNGLE:
        return ArmyType.ELEPHANTS
    return _SECOND_SLOT_CAVALRY_OR_CHARIOTS[rng.irand() % 3]
