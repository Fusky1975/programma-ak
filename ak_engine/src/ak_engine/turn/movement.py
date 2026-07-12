"""Hex adjacency and Move-action resolution (rulebook [3.1] and [6.2]).

**Reconstruction assumption, not sourced from the original program**: the
code that computed hex adjacency lived in the AK turn-processor's main
program, which is missing from the available Pascal source (only compiled
into ``AK.EXE``/``AK.OVR``). ``CTBOTH.PAS`` confirms a 6-neighbor hex grid
(direction names ``northeast, east, southeast, southwest, west, northwest``,
see ``dirname`` around line 526) but does not give the coordinate math.

This module implements the standard "odd-r" offset-coordinate hex grid
(each odd row shifted half a hex to the right), which produces exactly
those 6 neighbor directions. This is a reasonable, well-known scheme
consistent with the confirmed direction names -- but it is a guess about
the *exact* offset convention (odd-r vs even-r) that cannot be verified
without the lost source. If real game data ever contradicts it, this is
the first place to revisit.

Explicitly out of scope for this phase (rulebook [3.1]):
- ~~Moving to a *non-adjacent* target hex ("he will move towards it, through
  friendly hexes if possible", with tie-break priorities and a "stop
  chasing" condition) -- this needs a pathfinding algorithm, not just
  adjacency, and is deferred to a later phase.~~ **The one-hex-per-phase
  chase-step primitive now exists as of Phase 78** --
  ``step_toward_non_adjacent_target()`` below, deliberately following the
  exact same split ``turn/pursue_execution.py step_toward_target``/
  ``advance_pursuit`` already used (Phase 66 built the primitive alone,
  Phase 70 wired multi-phase persistence in separately, four phases
  later): `resolve_move()`/`execute_move()`/`plan_dispatch.py` still
  raise/reject a non-adjacent target exactly as before -- wiring the new
  primitive in needs `execute_move()` to resolve exploration/contested/
  battle checks against whichever *intermediate* hex the chase actually
  lands on this phase, not the ultimate target (`resolve_move()`'s
  current signature only ever describes one caller-supplied hex's
  terrain/exploration data), plus the rulebook's own multi-phase
  persistence rule ("The movement order will override orders in a
  subsequent phase only if the character is practicing in that phase")
  -- both left for a real follow-up phase, not attempted here.
- Resolving the battle that occurs when moving into an enemy-occupied
  province (rulebook [7.0]) -- this module only flags that a battle would
  be triggered, it does not fight it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.exploration import ExploreResult, resolve_explore

# Normal (non-Noble) map bounds, per CTBOTH.PAS `xcrange = 0..29`, `ycrange = 0..14`.
NORMAL_MAP_BOUNDS = (30, 15)


class Direction(IntEnum):
    """CTBOTH.PAS `dirname` (~line 526, 6 entries, no unused extension slots
    unlike most of this project's other transcribed enums) -- found
    continuing to mine `CTBOTH.PAS` the way Phases 79-84/86-88 found
    their own real data. Confirmed to be `PROSE.TXT`'s own documented
    `"*: Direction"` marker via `RUMORS.PAS`'s own
    `Say(dirname[_dir], spytype)`. Ordinal order matches
    `_EVEN_ROW_OFFSETS`/`_ODD_ROW_OFFSETS` below exactly -- this
    project's own comment already cited `dirname`'s ordering when those
    offset tuples were first written, but never transcribed the actual
    display strings until now.
    """

    NE = 0
    E = 1
    SE = 2
    SW = 3
    W = 4
    NW = 5


DIRECTION_NAME: dict[Direction, str] = {
    Direction.NE: "northeast",
    Direction.E: "east",
    Direction.SE: "southeast",
    Direction.SW: "southwest",
    Direction.W: "west",
    Direction.NW: "northwest",
}

# Neighbor offsets for an "odd-r" horizontal-offset hex grid, keyed by
# whether the row (y) is even or odd, in NE, E, SE, SW, W, NW order to match
# CTBOTH.PAS's `dirname` ordering (see `Direction` above).
_EVEN_ROW_OFFSETS = ((0, -1), (1, 0), (0, 1), (-1, 1), (-1, 0), (-1, -1))
_ODD_ROW_OFFSETS = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 0), (0, -1))


class NonAdjacentMoveError(NotImplementedError):
    """Raised when a move targets a hex that isn't adjacent to the origin.

    The rulebook allows this (the character moves *towards* the target
    through a multi-phase chase), but that pathfinding algorithm isn't
    implemented yet -- see the module docstring.
    """


@dataclass(frozen=True, slots=True)
class MapBounds:
    width: int
    height: int

    def contains(self, coord: HexCoord) -> bool:
        return 0 <= coord.x < self.width and 0 <= coord.y < self.height


@dataclass(slots=True)
class MoveResult:
    new_coord: HexCoord
    exploration: ExploreResult
    battle_expected: bool


def neighbors(coord: HexCoord, bounds: MapBounds) -> list[HexCoord]:
    """The up-to-6 in-bounds hexes adjacent to ``coord``."""

    offsets = _ODD_ROW_OFFSETS if coord.y % 2 else _EVEN_ROW_OFFSETS
    candidates = (HexCoord(coord.x + dx, coord.y + dy) for dx, dy in offsets)
    return [c for c in candidates if bounds.contains(c)]


def is_adjacent(a: HexCoord, b: HexCoord, bounds: MapBounds) -> bool:
    return b in neighbors(a, bounds)


def _to_cube(coord: HexCoord) -> tuple[int, int, int]:
    """Converts this module's "odd-r" offset coordinates to cube coordinates.

    Standard odd-r-to-cube conversion (redblobgames.com/grids/hexagons);
    confirmed to reproduce exactly the 6 neighbor offsets above (each at
    cube distance 1, for both even and odd rows) before use.
    """

    x = coord.x - (coord.y - (coord.y & 1)) // 2
    z = coord.y
    y = -x - z
    return x, y, z


def hex_distance(a: HexCoord, b: HexCoord) -> int:
    """Straight-line distance in hexes between two coordinates (0 if equal, 1 if adjacent).

    Not a pathfinding distance -- unlike Move's own "through friendly
    hexes if possible" chase algorithm ([3.1], still unimplemented, see
    module docstring), this ignores terrain, ownership, and unexplored
    hexes. Used by ``turn/spy_table.py``'s Pursue/Trail catch-up formula
    ([4.33]), which just says "distance (in number of provinces)" with
    no pathfinding rule attached.
    """

    ax, ay, az = _to_cube(a)
    bx, by, bz = _to_cube(b)
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))


class HexOwnershipTier(IntEnum):
    """Rulebook [3.1]'s own tie-break order (quoted in full) for a
    non-adjacent Move's chase step, when two candidate hexes are equally
    close to the target: "1) Owned or Allied-player hex; 2) Enemy-player
    hex; 3) Hero-owned hex; 4) Neutral-player hex." Ordinal order matches
    that priority list exactly (lower = preferred).

    Deliberately independent of this project's own ``GameState``/
    ``ProvinceState`` model -- callers classify each candidate hex
    however they can; see ``step_toward_non_adjacent_target``'s own
    docstring for the one distinction this project's data currently
    can't make (``HERO_OWNED`` vs ``NEUTRAL`` -- ``ProvinceState.
    owner_kingdom_id`` has no way to mark an unowned province as
    specifically Hero-ruled).
    """

    OWNED_OR_ALLIED = 0
    ENEMY = 1
    HERO_OWNED = 2
    NEUTRAL = 3


def step_toward_non_adjacent_target(
    current: HexCoord,
    target: HexCoord,
    bounds: MapBounds,
    tier_of: Callable[[HexCoord], HexOwnershipTier],
) -> HexCoord | None:
    """One hex-step from ``current`` toward a non-adjacent ``target`` (rulebook
    [3.1]): "If a character is ordered to move to a hex number, but is not
    adjacent to it, he will move towards it... If there are two possible
    provinces that are both closer to the target province," ``tier_of``'s
    ``HexOwnershipTier`` breaks the tie, exactly the quoted priority order.

    Only considers neighbors *strictly closer* (``hex_distance``, the same
    straight-line abstraction ``turn/pursue_execution.py step_toward_target``
    already uses -- not real terrain-aware pathfinding) than ``current`` is
    to ``target``. Returns ``None`` -- "stop chasing" -- when no such
    neighbor exists: "The character will stop chasing the province if he
    can't find a legal way to move closer to it in one phase," quoted
    verbatim. Returns ``current`` unchanged if already at ``target``.

    A same-tier, same-distance tie between two candidates is broken by
    Python's own stable ``min()`` (whichever ``neighbors()`` yields first)
    -- the rulebook doesn't specify anything further for that case, so no
    additional rule is invented here.
    """

    if current == target:
        return current
    current_distance = hex_distance(current, target)
    candidates = [c for c in neighbors(current, bounds) if hex_distance(c, target) < current_distance]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (tier_of(c), hex_distance(c, target)))


def resolve_move(
    current: HexCoord,
    target: HexCoord,
    bounds: MapBounds,
    *,
    target_terrain: Terrain,
    target_explored_percent: int,
    explorer_skill: int,
    occupied_by_enemy: bool = False,
) -> MoveResult:
    """Resolve a Move order (rulebook [3.1]) to an *adjacent* target hex.

    Raises ``NonAdjacentMoveError`` for non-adjacent targets -- the
    multi-phase chase-towards-target algorithm isn't implemented yet.

    Every Move also counts as a partial exploration of the destination
    ("half the effect of an Explore order"), computed via
    :func:`ak_engine.turn.exploration.resolve_explore`.
    """

    if not is_adjacent(current, target, bounds):
        raise NonAdjacentMoveError(
            f"{target} is not adjacent to {current}; chasing a non-adjacent "
            "target isn't implemented yet"
        )
    exploration = resolve_explore(target_explored_percent, target_terrain, explorer_skill, partial=True)
    return MoveResult(new_coord=target, exploration=exploration, battle_expected=occupied_by_enemy)
