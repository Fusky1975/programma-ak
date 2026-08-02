"""Extra mercenary band radial search (Phase 363): fills the spatial
gap Phase 358 deliberately left open for one confirmed-but-unwired
per-King mercenary unit (``extra_mercenary_band``, 0x14CF6) -- the
second phase of the pipeline-integration sub-plan, the same "turn the
narrative into an algorithm, replace it outright if the exact routine
is ever recovered" treatment as `place_map` (Phase 354) and
`special_race_placement` (Phase 362).

Source: ``world_generation.initial_armies.extra_mercenary_band``.

**Confirmed exactly** and implemented here:

- One extra mercenary band per King (``count: "one per King"``).
- ``quality``: Average (2) -- reuses Phase 358's own confirmed
  ``initial_armies.INITIAL_ARMY_QUALITY``.
- ``commander``: 255 -- reuses Phase 358's own confirmed
  ``initial_armies.COMMANDER_NONE``.
- ``state``: Mercenary (2) -- ``ARMY_STATE_MERCENARY = 2``, alongside
  ``ARMY_STATE_HIRED = 1`` (the same value Phase 358's own docstring
  already named for ordinary initial armies -- "defaults: ... state:
  Hired (1)" -- but never turned into a constant, since no function
  there needed it yet). This project has no dedicated army/leader
  "state" enum; these are kept as plain confirmed integers rather than
  inventing one prematurely.
- ``search``: "from Home through radii 1..6 for a compatible recruit
  type, up to 100 retries before fallback" -- realized as an
  increasing radial sweep (``radius = 1, 2, ..., 6``) using this
  project's own pre-existing, already-validated
  ``turn/movement.py hex_distance()`` (already relied on by Phase 51's
  own Spy Table catch-up formula), drawing candidate coordinates from
  each radius's own ring in random order via ``PascalRandom`` and
  testing each with a caller-supplied compatibility predicate, capped
  at a single shared budget of ``MAX_RETRIES = 100`` across the whole
  sweep -- the most literal reading of "up to 100 retries before
  fallback" as one overall budget, not six separate per-radius ones.

**Deliberately left as an honest, documented gap rather than
invented**: the source never states what makes a recruit type
"compatible" for this search, so ``find_mercenary_recruit_type()``
takes that test as a caller-supplied predicate instead of guessing a
specific compatibility rule (race match? terrain match? any non-empty
slot?); likewise the exact "fallback" army type isn't given by the
source, so it's a caller-supplied parameter too -- callers wiring this
into a real pipeline would naturally reuse Phase 358's own confirmed
``home_first_slot()``/``BEST_ATYPE[king_race]`` as a defensible
fallback, but this module doesn't hard-code that choice for them.

**Verification**: ``hex_ring()`` is checked against ``hex_distance()``
itself for several radii (every cell it returns really is at that
exact distance, and every in-bounds cell at that distance is
included). ``find_mercenary_recruit_type()`` is checked to find a
compatible coordinate placed at each of the six confirmed radii in
turn, to respect the shared 100-attempt budget (never exceeding it
even when no compatible coordinate exists anywhere), and to fall back
to the caller-supplied default when the whole sweep is exhausted.
"""

from __future__ import annotations

from collections.abc import Callable

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import MapBounds, hex_distance
from ak_engine.worldgen.pascal_random import PascalRandom

ARMY_STATE_HIRED = 1
ARMY_STATE_MERCENARY = 2

MAX_RADIUS = 6
MAX_RETRIES = 100


def hex_ring(center: HexCoord, radius: int, bounds: MapBounds) -> list[HexCoord]:
    """Every in-bounds coordinate at exactly ``radius`` hexes from ``center``."""

    ring: list[HexCoord] = []
    for x in range(bounds.width):
        for y in range(bounds.height):
            candidate = HexCoord(x, y)
            if hex_distance(center, candidate) == radius:
                ring.append(candidate)
    return ring


def find_mercenary_recruit_type(
    king_home: HexCoord,
    bounds: MapBounds,
    is_compatible: Callable[[HexCoord], ArmyType | None],
    fallback: ArmyType,
    rng: PascalRandom,
) -> ArmyType:
    """"search from Home through radii 1..6 for a compatible recruit type, up to 100 retries before fallback"."""

    retries = 0
    for radius in range(1, MAX_RADIUS + 1):
        ring = hex_ring(king_home, radius, bounds)
        remaining = list(range(len(ring)))
        while remaining and retries < MAX_RETRIES:
            pick = rng.irand() % len(remaining)
            coord = ring[remaining.pop(pick)]
            retries += 1
            result = is_compatible(coord)
            if result is not None:
                return result
        if retries >= MAX_RETRIES:
            break
    return fallback
