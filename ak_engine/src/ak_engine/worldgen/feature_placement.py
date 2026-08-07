"""Feature spatial placement loop (Phase 364): fills the spatial gap
Phase 359 deliberately left open for its own confirmed feature-
generation formulas -- the third phase of the pipeline-integration
sub-plan, the same "turn the narrative into an algorithm, replace it
outright if the exact routine is ever recovered" treatment already
given to `place_map` (Phase 354), `special_race_placement` (Phase 362)
and `mercenary_band` (Phase 363).

Source: ``world_generation.features`` -- ``first_2k_placement``,
``later_placement``, ``rejection_rule``, combined with Phase 359's own
already-confirmed ``propose_monster()``/``propose_feature_type()``/
``is_terrain_compatible()``/``first_2k_home_index()``.

**Confirmed exactly** and implemented here:

- The first ``2*king_count`` features use a King Home coordinate
  (``first_2k_home_index()``, already implemented in Phase 359) --
  never a random draw.
- Every later feature ("``later_placement``"): "random coordinates
  with all king Home provinces rejected; duplicate non-Home
  coordinates are allowed" -- a plain reject-and-redraw loop with no
  occupancy tracking at all (unlike Phase 362's own special-race pass,
  which does track occupancy).
- ``rejection_rule``: "monster, feature type and coordinate are all
  proposed again when the selected coordinate terrain is
  incompatible" -- realized as one combined retry cycle re-drawing
  every value the rejection can plausibly apply to: for a first-2K
  feature the coordinate is fixed (a King Home can't be "redrawn"), so
  only monster/type are re-proposed; for a later feature all three
  (coordinate included) are re-proposed together, exactly as the
  source states.

**Deliberately NOT sourced, an engineering safeguard only**: neither
``first_2k_placement`` nor ``later_placement`` states a retry cap for
this rejection loop (unlike Phase 362's own confirmed
``ATTEMPT_CAP = 3000``). ``MAX_ATTEMPTS = 10_000`` here is a plain
defensive bound against a pathological caller-supplied map with no
compatible terrain anywhere for some feature type, not a sourced game
value -- raises ``RuntimeError`` rather than looping forever if it is
ever actually exhausted, which shouldn't happen against any real
generated map (`place_map`'s own maps always carry every land terrain
type, and every ``FeatureType``'s own confirmed terrain range from
Phase 359 covers at least one of them).

**Verification**: `place_feature()` is checked to return a King Home
coordinate for every first-2K feature index and a non-Home coordinate
for every later index (with King Homes engineered to be otherwise
terrain-incompatible, forcing the rejection loop to actually retry
before landing on a valid non-Home cell). `place_all_features()` is
checked to produce exactly ``feature_count(gamevers)`` placements and
to never place any feature on a King Home coordinate once past the
first ``2*king_count`` indices. **Phase 430 addendum**: also checked
that no King Home coordinate's own first-2K features ever share a
guardian monster (`excluded_monsters` correctly threaded through), and
that `place_feature()` still honors a non-empty `excluded_monsters` set
directly (redraws until landing on an unexcluded monster).
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.feature import FeatureType
from ak_engine.models.monster import Monster
from ak_engine.turn.movement import MapBounds
from ak_engine.worldgen.feature_generation import (
    feature_count,
    first_2k_home_index,
    is_terrain_compatible,
    propose_feature_type,
    propose_monster,
)
from ak_engine.worldgen.pascal_random import PascalRandom

MAX_ATTEMPTS = 10_000


@dataclass(frozen=True, slots=True)
class FeaturePlacement:
    """One placed feature: its map coordinate, guardian monster and type."""

    feature_index: int
    coord: HexCoord
    monster: Monster
    feature_type: FeatureType


def place_feature(
    feature_index: int,
    king_homes: list[HexCoord],
    king_count: int,
    grid: dict[HexCoord, Terrain],
    bounds: MapBounds,
    rng: PascalRandom,
    *,
    excluded_monsters: frozenset[Monster] = frozenset(),
) -> FeaturePlacement:
    """One feature's full propose/reject cycle -- fixed Home coordinate for the first 2K indexes,
    a rejected-and-redrawn random coordinate otherwise.

    **``excluded_monsters`` (Phase 430)**: project-original, not sourced
    from ``later_placement``'s own confirmed "duplicate non-Home
    coordinates are allowed" text -- that text only ever describes
    *later* (non-King-Home) features, and says nothing about whether two
    of a King Home's own first-2K features can share the same guardian
    monster. Real Turn-0 reports confirmed the opposite ever happens (a
    generated playtest produced the same monster guarding both of one
    King Home's own features, which the user's own real-game experience
    confirmed never happens in practice) -- the same "fill the
    confirmed-silent gap with the user's own domain knowledge" category
    already used for ``worldgen/king_home_placement.py``'s distance/
    terrain rules. ``place_all_features()`` only ever passes a non-empty
    set for a first-2K feature (the monster(s) already placed at that
    same King Home), never for a later-placement one -- unchanged there.
    """

    is_first_2k = feature_index < 2 * king_count

    if is_first_2k:
        coord = king_homes[first_2k_home_index(feature_index, king_count)]
        for _ in range(MAX_ATTEMPTS):
            monster = propose_monster(rng)
            if monster in excluded_monsters:
                continue
            feature_type = propose_feature_type(monster, rng)
            terrain = grid[coord]
            if is_terrain_compatible(feature_type, terrain, rng):
                return FeaturePlacement(feature_index, coord, monster, feature_type)
        raise RuntimeError(f"no compatible feature type found for King Home {coord!r}")

    king_home_set = frozenset(king_homes)
    for _ in range(MAX_ATTEMPTS):
        coord = HexCoord(rng.irand() % bounds.width, rng.irand() % bounds.height)
        if coord in king_home_set:
            continue
        monster = propose_monster(rng)
        feature_type = propose_feature_type(monster, rng)
        terrain = grid[coord]
        if is_terrain_compatible(feature_type, terrain, rng):
            return FeaturePlacement(feature_index, coord, monster, feature_type)
    raise RuntimeError("no compatible coordinate found for a later-placement feature")


def place_all_features(
    king_homes: list[HexCoord],
    king_count: int,
    grid: dict[HexCoord, Terrain],
    bounds: MapBounds,
    rng: PascalRandom,
    *,
    gamevers: int,
) -> list[FeaturePlacement]:
    """Places every one of ``feature_count(gamevers)`` features, in feature-index order.

    **Phase 430**: tracks which guardian monsters have already been used
    at each King Home coordinate (first-2K features only) and excludes
    them from that Home's remaining draws -- see ``place_feature()``'s
    own Phase 430 note for why this is project-original, not sourced.
    """

    count = feature_count(gamevers)
    king_count_local = king_count
    used_monsters_by_home: dict[HexCoord, set[Monster]] = {}
    placements: list[FeaturePlacement] = []
    for feature_index in range(count):
        is_first_2k = feature_index < 2 * king_count_local
        excluded: frozenset[Monster] = frozenset()
        if is_first_2k:
            coord = king_homes[first_2k_home_index(feature_index, king_count_local)]
            excluded = frozenset(used_monsters_by_home.get(coord, set()))
        placement = place_feature(
            feature_index, king_homes, king_count, grid, bounds, rng, excluded_monsters=excluded
        )
        if is_first_2k:
            used_monsters_by_home.setdefault(placement.coord, set()).add(placement.monster)
        placements.append(placement)
    return placements
