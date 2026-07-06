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
- Moving to a *non-adjacent* target hex ("he will move towards it, through
  friendly hexes if possible", with tie-break priorities and a "stop
  chasing" condition) -- this needs a pathfinding algorithm, not just
  adjacency, and is deferred to a later phase.
- Resolving the battle that occurs when moving into an enemy-occupied
  province (rulebook [7.0]) -- this module only flags that a battle would
  be triggered, it does not fight it.
- The partial-exploration side effect of a Move (half the effect of an
  Explore action) -- deferred until the Explore action itself is built,
  since it depends on the same Basic Exploration Number formula.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.map import HexCoord

# Normal (non-Noble) map bounds, per CTBOTH.PAS `xcrange = 0..29`, `ycrange = 0..14`.
NORMAL_MAP_BOUNDS = (30, 15)

# Neighbor offsets for an "odd-r" horizontal-offset hex grid, keyed by
# whether the row (y) is even or odd, in NE, E, SE, SW, W, NW order to match
# CTBOTH.PAS's `dirname` ordering.
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
    partially_explored: bool
    battle_expected: bool


def neighbors(coord: HexCoord, bounds: MapBounds) -> list[HexCoord]:
    """The up-to-6 in-bounds hexes adjacent to ``coord``."""

    offsets = _ODD_ROW_OFFSETS if coord.y % 2 else _EVEN_ROW_OFFSETS
    candidates = (HexCoord(coord.x + dx, coord.y + dy) for dx, dy in offsets)
    return [c for c in candidates if bounds.contains(c)]


def is_adjacent(a: HexCoord, b: HexCoord, bounds: MapBounds) -> bool:
    return b in neighbors(a, bounds)


def resolve_move(current: HexCoord, target: HexCoord, bounds: MapBounds, *, occupied_by_enemy: bool = False) -> MoveResult:
    """Resolve a Move order (rulebook [3.1]) to an *adjacent* target hex.

    Raises ``NonAdjacentMoveError`` for non-adjacent targets -- the
    multi-phase chase-towards-target algorithm isn't implemented yet.
    """

    if not is_adjacent(current, target, bounds):
        raise NonAdjacentMoveError(
            f"{target} is not adjacent to {current}; chasing a non-adjacent "
            "target isn't implemented yet"
        )
    return MoveResult(new_coord=target, partially_explored=True, battle_expected=occupied_by_enemy)
