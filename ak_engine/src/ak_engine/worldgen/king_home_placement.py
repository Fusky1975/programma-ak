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


def eligible_home_coords(
    grid: dict[HexCoord, Terrain],
    race_grid: dict[HexCoord, Race],
    bounds: MapBounds,
    taken_homes: list[HexCoord],
    *,
    naval: bool,
) -> list[HexCoord]:
    """Every coordinate satisfying terrain/race/distance/(sea-adjacency if Naval)."""

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
) -> HexCoord:
    """Uniform random draw among ``eligible_home_coords()``."""

    candidates = eligible_home_coords(grid, race_grid, bounds, taken_homes, naval=naval)
    if not candidates:
        raise ValueError(
            "No eligible King Home province found (terrain/race/distance"
            f"{'/sea-adjacency' if naval else ''} constraints) -- map too small or too crowded."
        )
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
