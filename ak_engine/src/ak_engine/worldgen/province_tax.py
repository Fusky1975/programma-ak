"""Province tax assignment (Phase 356): ``AKGEN.EXE``'s ``province_tax`` (0xEB8A).

Fourth phase of the world-generation sub-plan. Source:
``world_generation.province_tax``.

**Confirmed exactly** and implemented here:

- ``coast_score``: the number of Sea cells among a province's six hex
  neighbors -- realized via this project's own already-validated,
  real-data-confirmed 6-neighbor hex adjacency (``turn/movement.py
  neighbors()``, Phase 314), the same reuse pattern Phase 354's
  hole-filling and this same phase's own edge-row logic depend on.
- ``edge_score``: on the map's top/bottom rows, ``trunc(1.5 *
  coast_score * U)``; on every other row, ``coast_score`` unchanged.
- ``ordinary_land_tax`` (Plains/Desert/Jungle/Forest/Mountains):
  ``1 + trunc(U * M)`` where ``M`` is the terrain's own confirmed
  maximum (Plains 9, Desert 2, Jungle 6, Forest 7, Mountains 8) --
  uniform over ``1..M`` before the floor rule below. **Low floor**:
  "if tax < round(0.24*M), increment tax by one" -- for Plains/Forest/
  Mountains this bumps a raw ``tax == 1`` up to ``2`` (``round(0.24*M)
  == 2`` for all three), roughly doubling ``2``'s share and removing
  ``1`` entirely; for Desert/Jungle ``round(0.24*M) <= 1`` so the rule
  never actually fires (verified by direct calculation before writing
  any code: 2.16/0.48/1.44/1.68/1.92 round to 2/0/1/2/2 respectively).
- ``NOTERR_TAX = 0``: the ``noterr`` terrain always taxes zero.
- ``true_sea_tax`` (ordinary Sea provinces, i.e. no secondary ``pt2``
  terrain -- see the scoped-out branch below): a 10%/90% split. The
  10% branch draws ``trunc(5*U)``, uniform over ``0..4``. The 90%
  branch depends on ``edge_score``: when it's in ``6..9`` ("high
  coast"), tax is 1 with probability exactly ``7000/32768 ==
  21.3623046875%`` (a literal ``IRand < 7000`` comparison, realized
  here as ``rng.irand() < 7000``, not an equivalent float threshold),
  else 0; otherwise tax is ``min(6, trunc(1.8 * (7 - edge_score) * U1
  * U2))``, two independent draws multiplied together as the source's
  own ``U1*U2`` states.
- ``HOME_OVERRIDE_TAX = 10``: a King's home province always taxes 10,
  overriding every formula above.

The 10%/90% split itself and the true-Sea 21.36% "high coast" chance
are both realized with ``rng.random() < p`` (an exact float-threshold
comparison against the source's own stated probability), the same
choice this project already made for Phase 355's confirmed 30%
humanoid-mix chance -- reserved for percentages the source states as
plain probabilities rather than as an explicit ``IRand`` formula (the
``IRand < 7000`` comparison above, by contrast, *is* given as an exact
integer formula, so it's implemented literally rather than converted
to an equivalent float threshold).

**Deliberately NOT implemented here**, each a genuine, separately
documented gap:

- ``island_or_alternate_terrain`` (Sea provinces with a secondary
  ``pt2`` terrain: ``1 + trunc(U1*U2*M[pt2])``) -- this project has no
  ``pt2``/secondary-terrain concept anywhere (Phase 355's own
  docstring already flagged the same gap for ``effective_terrain``);
  ``place_map`` (Phase 354) only ever assigns one terrain per cell, so
  this branch has no input to act on.
- The true-Sea formula's own "geometry_bonuses" ("two special
  neighbor configurations add +1 or +2") -- the source names that
  these exist but never states what the two configurations are, so
  implementing them would mean inventing the missing rule.
- The interactive ``+``/``-`` placement override (bounded 0..10) --
  this is a human game-master UI action during map setup, not part of
  automatic generation; this project has no interactive placement
  step to hang it on.
- The special-race tax recompute ("special-race placement recomputes
  the accepted province tax") -- deferred together with the
  special-race placement pass itself, already scoped out of Phase 355
  for the same reason (needs the whole generated map plus adjacency
  rejection sampling).

**Verification**: `ordinary_land_tax()` is Monte Carlo-checked per
terrain against the confirmed ``1..M`` raw range and the low-floor
rule's exact effect (value ``1`` disappearing entirely for Plains/
Forest/Mountains, present for Desert/Jungle). `true_sea_tax()`'s
high-coast branch is checked against the exact combined probability
worked out by hand above (10% branch's own 1-in-5 contribution plus
90%'s ``7000/32768``); its non-high-coast branch has no source-given
worked example, so it's instead checked for internal consistency
(range ``0..6``, and its output distribution matches an independent
direct re-implementation of ``min(6, trunc(1.8*(7-edge_score)*U1*U2))``
run through the same ``PascalRandom`` stream).
"""

from __future__ import annotations

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.worldgen.pascal_random import PascalRandom

HOME_OVERRIDE_TAX = 10
NOTERR_TAX = 0

ORDINARY_LAND_MAX: dict[Terrain, int] = {
    Terrain.PLAINS: 9,
    Terrain.DESERT: 2,
    Terrain.JUNGLE: 6,
    Terrain.FOREST: 7,
    Terrain.MTNS: 8,
}

TRUE_SEA_LOW_BRANCH_CHANCE = 0.10
HIGH_COAST_TAX_ONE_THRESHOLD = 7000
HIGH_COAST_EDGE_SCORE_RANGE = range(6, 10)


def coast_score(coord: HexCoord, grid: dict[HexCoord, Terrain], bounds: MapBounds) -> int:
    """Number of Sea cells among ``coord``'s six hex neighbors."""

    return sum(1 for neighbor in neighbors(coord, bounds) if grid.get(neighbor) is Terrain.SEA)


def compute_edge_score(coast: int, is_edge_row: bool, rng: PascalRandom) -> int:
    """``trunc(1.5*coast*U)`` on the map's top/bottom rows, else ``coast`` unchanged."""

    if is_edge_row:
        return int(1.5 * coast * rng.random())
    return coast


def ordinary_land_tax(terrain: Terrain, rng: PascalRandom) -> int:
    """``1 + trunc(U*M)``, then the confirmed low-floor bump for provinces below ``round(0.24*M)``."""

    max_tax = ORDINARY_LAND_MAX[terrain]
    tax = 1 + int(rng.random() * max_tax)
    floor = round(0.24 * max_tax)
    if tax < floor:
        tax += 1
    return tax


def true_sea_tax(edge_score: int, rng: PascalRandom) -> int:
    """The ordinary (no ``pt2``) Sea-province tax draw: a 10%/90% branch split."""

    if rng.random() < TRUE_SEA_LOW_BRANCH_CHANCE:
        return int(5 * rng.random())
    if edge_score in HIGH_COAST_EDGE_SCORE_RANGE:
        return 1 if rng.irand() < HIGH_COAST_TAX_ONE_THRESHOLD else 0
    u1 = rng.random()
    u2 = rng.random()
    return min(6, int(1.8 * (7 - edge_score) * u1 * u2))
