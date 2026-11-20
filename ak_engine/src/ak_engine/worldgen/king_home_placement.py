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
    if tax_grid is not None:
        rich_neighbor_candidates = eligible_home_coords(
            grid, race_grid, bounds, taken_homes, naval=naval, tax_grid=tax_grid
        )
        if rich_neighbor_candidates:
            candidates = rich_neighbor_candidates
    return candidates[rng.irand() % len(candidates)]


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
