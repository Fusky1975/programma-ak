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
first ``2*king_count`` indices.
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
) -> FeaturePlacement:
    """One feature's full propose/reject cycle -- fixed Home coordinate for the first 2K indexes,
    a rejected-and-redrawn random coordinate otherwise."""

    is_first_2k = feature_index < 2 * king_count

    if is_first_2k:
        coord = king_homes[first_2k_home_index(feature_index, king_count)]
        for _ in range(MAX_ATTEMPTS):
            monster = propose_monster(rng)
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
    """Places every one of ``feature_count(gamevers)`` features, in feature-index order."""

    count = feature_count(gamevers)
    return [
        place_feature(feature_index, king_homes, king_count, grid, bounds, rng)
        for feature_index in range(count)
    ]
