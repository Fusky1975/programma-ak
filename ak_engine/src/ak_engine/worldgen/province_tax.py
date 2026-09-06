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
  here as ``rng.irand() < 7000``, not an equivalent float threshold --
  **Phase 755 note**: ``Desktop/AKGEN 0xEB8A.md`` proposed a 32000 base
  here (``21.875%``), but this project's own ``IRAND_RANGE`` stays
  32768 -- see ``pascal_random.py``'s own module docstring for why that
  correction was investigated and rejected against real GW900 data),
  else 0;
  otherwise tax is ``min(6, trunc(1.8 * (7 - edge_score) * U1 * U2))``,
  two independent draws multiplied together as the source's own
  ``U1*U2`` states.
- **Phase 755** -- ``sea_race_tax_bonus`` (``Desktop/AKGEN 0xEB8A.md``,
  raw ``0xF05E-0xF12A``, calling ``Mod_PRace`` at raw ``0x4A65B``): a
  true-Sea province (``pterr=Sea``, ``pt2=noterr``) whose race is
  ``Race.WHALES`` gets ``+1`` after the ``true_sea_tax`` roll above;
  ``Race.MERMISH`` gets ``+2``; every other race (including an ordinary
  coastal province with no aquatic race) gets no bonus at all -- the
  coast's own effect is already fully captured by ``true_sea_tax``'s
  own ``edge_score`` term. This closes backlog item #5's own
  "geometry_bonuses" note in full: **the earlier "two special neighbor
  configurations add +1/+2" reading was wrong** -- the bonus is race-
  based, not geometric, and lives outside ``true_sea_tax`` entirely, as
  a separate step applied by the caller (see ``worldgen/special_race_
  placement.py recompute_tax()``). The compiled routine reconstructs
  Whale-vs-Merman via ``Mod_PRace`` because the binary's own ``prace``
  array uses one shared legacy code (``6``) for all aquatic population,
  disambiguated at read time by checking the province's first recruit
  slot against ``Whaleleague``; this project's own ``models/race.py``
  already stores ``Race.WHALES``/``Race.MERMISH`` as two distinct,
  directly-assigned values (see ``worldgen/special_race_placement.py``),
  so ``sea_race_tax_bonus()`` is a direct lookup with no reconstruction
  needed.
- **Phase 755** -- ``island_tax`` (the ``island_or_alternate_terrain``
  branch, now fully resolved): both real call sites normalize a Sea
  province with a real secondary ``pt2`` terrain to ``effective_terrain
  = pt2`` *before* the tax ``case`` runs (in the adjacency helper, raw
  ``0xE986``), so an island reaches the *ordinary land* branch with a
  single draw -- ``1 + trunc(U*M[pt2])`` -- not the two-draw formula
  (``1 + trunc(U1*U2*M[pt2])``) the earlier catalog guessed. A genuine
  two-draw branch does exist in the compiled binary (raw
  ``0xED48-0xEDFB``) but is confirmed dead code: both real callers
  already redirect ``effective_terrain`` to ``pt2`` beforehand, so that
  branch is never reached in practice. This closes the *formula*
  question in full; ``island_tax()`` is shipped here as a standalone,
  tested primitive, still deliberately unwired -- see the "Deliberately
  NOT implemented" note below for the separate, still-open blocker.
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

- ``island_tax()``'s own wiring: the *formula* is fully resolved (see
  above), but ``place_map`` (Phase 354) only ever assigns one terrain
  per cell at world-*creation* time -- this generator still has no
  ``pt2`` input to feed the function. A real, separate, still-open gap
  in world *generation* (this module), distinct from the world-
  *loading* ``pt2`` bridge Phase 723 already built (``ProvinceState.
  is_island``, ``parser/gw_world_bridge.py bridge_gw_world_provinces()``).
- The interactive ``+``/``-`` placement override (bounded 0..10) --
  this is a human game-master UI action during map setup, not part of
  automatic generation; this project has no interactive placement
  step to hang it on.
- Recruit-slot ("`pat`") seeding for ordinary Sea provinces: ``Desktop/
  AKGEN 0xEB8A.md`` reveals that the same tax routine also calls
  ``0B57:9CD8`` (with the already-computed ``effective_sea_neighbors``)
  to seed the province's own two recruit slots, including a real
  probability table (0%/0%/50%/70%/100%/50%/70% for ``effective_sea_
  neighbors=0..6``) for placing a Fleet in the second slot. This is a
  genuinely separate, larger mechanism -- ``worldgen/initial_armies.py``
  already flags its own land-side sibling gap (the terrain-weighted
  infantry table for the *first* slot) as separately unsourced/
  unbuildable; building only the Sea half here would leave an
  inconsistent, half-finished pipeline. Not attempted this phase.

The special-race tax recompute (Phase 355's own note that special-race
placement would need to "recompute the accepted province tax") is
**no longer a gap** -- stale since Phase 362 built exactly that
(``worldgen/special_race_placement.py recompute_tax()``, wired from
``worldgen/generate_new_game.py``), including, as of Phase 755, the
real ``sea_race_tax_bonus()`` addition above.

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
run through the same ``PascalRandom`` stream). `sea_race_tax_bonus()`
and `island_tax()` are checked directly against their own confirmed
formulas.
"""

from __future__ import annotations

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
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

SEA_RACE_TAX_BONUS: dict[Race, int] = {
    Race.WHALES: 1,
    Race.MERMISH: 2,
}


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


def sea_race_tax_bonus(race: Race | None) -> int:
    """"``Mod_PRace``: +1 for Whales, +2 for Mermish, else 0 (Phase 755).

    Applied by the caller *after* ``true_sea_tax()``'s own roll, and
    only for a true-Sea province (``pterr=Sea``, ``pt2=noterr``) --
    never for an island. See ``worldgen/special_race_placement.py
    recompute_tax()`` for the real call site.
    """

    return SEA_RACE_TAX_BONUS.get(race, 0)


def island_tax(pt2_terrain: Terrain, rng: PascalRandom) -> int:
    """"``island_or_alternate_terrain``: ``1 + trunc(U*M[pt2])`` (Phase 755).

    A single draw against the secondary terrain's own confirmed
    ``ORDINARY_LAND_MAX`` -- see the module docstring's own Phase 755
    addendum for why the earlier two-draw guess was wrong, and why
    this remains unwired (no ``pt2`` input exists at generation time).
    """

    return 1 + int(rng.random() * ORDINARY_LAND_MAX[pt2_terrain])
