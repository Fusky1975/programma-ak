"""Hex adjacency and Move-action resolution (rulebook [3.1] and [6.2]).

The code that originally computed hex adjacency lived in the AK
turn-processor's main program, which is missing from the available
Pascal source (only compiled into ``AK.EXE``/``AK.OVR``). ``CTBOTH.PAS``
confirms a 6-neighbor hex grid (direction names ``northeast, east,
southeast, southwest, west, northwest``, see ``dirname`` around line
526) but does not give the coordinate math.

This module implements the standard "odd-r" offset-coordinate hex grid
(each odd row shifted half a hex to the right), which produces exactly
those 6 neighbor directions -- a reasonable, well-known scheme
consistent with the confirmed direction names.

**Phase 314 -- the exact offset convention is now confirmed from real
game data, not guessed.** `Desktop/SE3__T*.K*` turn-report narrative
text (per-kingdom "STATE OF THE NATION" reports; per this project's own
established precedent of treating a confirmed-original real-data corpus
as a legitimate source, e.g. `models/monster.py`'s own `MOSTRI con
statistiche.txt` note) explicitly names each home province's 6 real
neighbors by direction and hex number, e.g. (Kingdom 2, Turn 0):
"The province of Mongu belongs to thee. Looking to the northeast, one
can see... Shasta (#304)... To the east lies... Moongard (#405)...
Southeast of here lies... Big Sky (#306)... southwestern horizon...
Transylvania (#206)... To the west there lies... Macondo (#205)...
Northwest of here is Orielle (#204)" -- Mongu's own number, 305, is
independently confirmed by five *other* kingdoms' own reports each
separately naming it "Mongu (#305)" as their own neighbor.

Splitting each of these real hex numbers as ``(number // 100, number %
100)`` and comparing the resulting coordinate deltas against this
module's own `_EVEN_ROW_OFFSETS`/`_ODD_ROW_OFFSETS` (unchanged below --
the six offset *vectors* were always right, matching CTBOTH.PAS's own
confirmed 6-direction shape) revealed the deltas exactly reproduce
those two tables' own values -- but keyed to the *opposite* parity of
`coord.y % 2` from what `neighbors()` previously checked. Confirmed
independently across 5 separate real provinces (Mongu, Maplehaven,
Limerick, Flying Fish Sea, Moonshine Sea -- spanning turns 0/1/4/9 and
4 different kingdoms, 15 individual direction observations total, zero
contradictions): `neighbors()` below now reads `_EVEN_ROW_OFFSETS` when
`coord.y` is odd and `_ODD_ROW_OFFSETS` when even -- the reverse of the
prior guess. (This also resolves the previously-flagged "board reaches
y=17, taller than the assumed 15-row height" puzzle from `turn/
hex_numbering.py`'s own docstring: under this same real numbering, the
*leading* digit group -- which reaches into the teens in the sample
above -- lines up with `HexCoord.x`, not `.y`, so it's bounded by this
project's own `width=30`, not `height=15`, all along.)

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

# Phase 780 correction: despite this constant's own name (kept as-is --
# widely referenced by this exact identifier -- but no longer described
# as "Normal" below), (30, 15) is the confirmed **Super-AK** map size,
# not the "normale" one. `Regolamento AK.txt` 12.1, quoted verbatim:
# "La mappa comprende 30x15 province, rispetto al numero normale che e'
# di 18x9." The real "normale" default (18, 9) is independently
# confirmed twice elsewhere: `worldgen/place_map.py DEFAULT_WIDTH/
# HEIGHT` (a 500-map Monte Carlo) and `parser/gw_world_bridge.py
# CONFIRMED_BOARD_HEIGHT` against real `GW3__T1` data (162 records / 9
# = 18). `CTBOTH.PAS`'s own `xcrange = 0..29`/`ycrange = 0..14` is real,
# just describes the Super-AK variant, not this project's own default.
# `GameState.board_width`/`.board_height` (Phase 780) are now the real
# source of truth for a given world's own actual size -- every function
# that used to fall back to this constant now falls back to those
# fields instead; this tuple remains only `GameState`'s own default
# value (so every pre-existing test/fixture that never sets the new
# fields keeps its current, already-established effective board size).
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
    """The up-to-6 in-bounds hexes adjacent to ``coord``.

    Phase 314: which offset table applies to which ``coord.y`` parity is
    now sourced from real game data (see module docstring) -- previously
    the reverse of this.
    """

    offsets = _EVEN_ROW_OFFSETS if coord.y % 2 else _ODD_ROW_OFFSETS
    candidates = (HexCoord(coord.x + dx, coord.y + dy) for dx, dy in offsets)
    return [c for c in candidates if bounds.contains(c)]


def is_adjacent(a: HexCoord, b: HexCoord, bounds: MapBounds) -> bool:
    return b in neighbors(a, bounds)


def neighbor_in_direction(coord: HexCoord, direction: Direction, bounds: MapBounds) -> HexCoord | None:
    """The one real neighbor of ``coord`` lying in ``direction``, or
    ``None`` if that hex would fall outside ``bounds`` -- Phase 704
    (``AdvancedAbility.ENHANCED_EARTHQUAKE``'s own Tidal Wave, "moving
    generally in the opposite direction from the spellcaster"), the
    first real consumer of a single-direction lookup rather than
    ``neighbors()``'s own "all 6 at once."
    """

    offsets = _EVEN_ROW_OFFSETS if coord.y % 2 else _ODD_ROW_OFFSETS
    dx, dy = offsets[direction.value]
    candidate = HexCoord(coord.x + dx, coord.y + dy)
    return candidate if bounds.contains(candidate) else None


def neighbor_in_direction_wrapped(
    coord: HexCoord, direction: Direction, board_width: int, board_height: int
) -> HexCoord | None:
    """Like ``neighbor_in_direction()``, but ``x`` wraps around the real
    horizontal cylindrical board instead of being treated as a hard edge
    -- the same wraparound ``hex_distance_wrapped()`` already applies to
    distance, now needed by Phase 981's own per-direction neighbor
    narrative (``report/turn_report.py describe_home_province_
    neighbors()``). Unlike ``x``, ``y`` genuinely has no wraparound on
    this board (every citation ``hex_distance_wrapped()`` itself already
    makes) -- running off the top/bottom is a real absence, returned as
    ``None`` here exactly like ``neighbor_in_direction()``'s own edge
    case, and confirmed by a real sample: a home province on the board's
    own top row (``y == 0``) has its report replace both its NE and NW
    neighbor sentences with one "To the north lay an icy expanse..."
    line (see that composer's own docstring) rather than naming a real
    neighbor in either direction.
    """

    offsets = _EVEN_ROW_OFFSETS if coord.y % 2 else _ODD_ROW_OFFSETS
    dx, dy = offsets[direction.value]
    y = coord.y + dy
    if not (0 <= y < board_height):
        return None
    return HexCoord((coord.x + dx) % board_width, y)


def direction_between(a: HexCoord, b: HexCoord) -> Direction | None:
    """Which ``Direction`` value's own offset (from ``a``'s own row-
    parity table) produces ``b``, or ``None`` if ``b`` isn't one of
    ``a``'s 6 real neighbors -- the inverse of ``neighbor_in_
    direction()``. Phase 704's own "direction from the caster to the
    Sea target" lookup, before the Tidal Wave continues stepping
    further in that same fixed direction.
    """

    offsets = _EVEN_ROW_OFFSETS if a.y % 2 else _ODD_ROW_OFFSETS
    delta = (b.x - a.x, b.y - a.y)
    for direction, offset in zip(Direction, offsets):
        if offset == delta:
            return direction
    return None


def _to_cube(coord: HexCoord) -> tuple[int, int, int]:
    """Converts this module's offset coordinates to cube coordinates.

    Standard "even-r"-to-cube conversion (redblobgames.com/grids/hexagons)
    -- confirmed to reproduce exactly the 6 neighbor offsets above (each
    at cube distance 1, for both even and odd rows) before use. Phase
    314: switched from "odd-r" to match `neighbors()`'s own real-data-
    sourced parity fix (see module docstring) -- the two offset tables
    themselves are unchanged, only which ``coord.y`` parity each one
    applies to, which flips which of the two textbook conversions
    actually matches.
    """

    x = coord.x - (coord.y + (coord.y & 1)) // 2
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


_DEFAULT_BOARD_WIDTH = 18
# Duplicated from ``worldgen/place_map.py DEFAULT_WIDTH`` (same value,
# Phase 624) rather than imported: that module already imports
# ``neighbors``/``MapBounds`` from *this* one, so an import the other
# way would be circular.


def hex_distance_wrapped(a: HexCoord, b: HexCoord, board_width: int = _DEFAULT_BOARD_WIDTH) -> int:
    """``Dist(x1,y1,x2,y2)`` -- LDRNEAR.md section 5.1 (Phase 636), the
    real offset-hex distance formula used by ``Ldr_Near``/``Known_Loc``
    (``turn/leader_visibility.py``), independent of ``hex_distance()``
    above (which is NOT wraparound-aware and stays that way -- still
    only used by Pursue/Trail's own catch-up formula, a separate, out-
    of-scope inconsistency noted since Phase 624).

    Applies the same horizontal cylindrical wraparound Phase 624 already
    confirmed for the ASCII map (column ``board_width - 1`` borders
    column ``0``) unconditionally -- the real Pascal only skips it for
    the ``Europe_V`` game-type variant, which ``ak_engine`` doesn't
    model anywhere, so there is no non-wrapping case to preserve.
    """

    dy = abs(b.y - a.y)
    dx2 = abs((2 * b.x + (b.y & 1)) - (2 * a.x + (a.y & 1)))
    dx2 = min(dx2, 2 * board_width - dx2)
    return dy if dy >= dx2 else dy + abs(dx2 - dy) // 2


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
    has_military_maps: bool = False,
    has_difficult_terrain: bool = False,
    require_adjacent: bool = True,
) -> MoveResult:
    """Resolve a Move order (rulebook [3.1]) to an *adjacent* target hex.

    Raises ``NonAdjacentMoveError`` for non-adjacent targets -- the
    multi-phase chase-towards-target algorithm isn't implemented yet.

    Every Move also counts as a partial exploration of the destination
    ("half the effect of an Explore order"), computed via
    :func:`ak_engine.turn.exploration.resolve_explore`. ``has_military_
    maps``/``has_difficult_terrain`` (Phase 507) pass straight through --
    see that function's own docstring.

    ``require_adjacent`` (Phase 524, default True): set False only by
    ``turn/move_execution.py execute_move()``'s own Naval Hug Coastline
    branch, whose whole real-world premise (`AdvancedAbility.NAVAL_HUG_
    COASTLINE`) is that the two land hexes *aren't* geometrically
    adjacent but the move is legal anyway -- the caller has already
    verified that itself (`_naval_hug_coastline_move_is_legal()`) before
    reaching here, so this function's own guard would otherwise reject a
    move it has no other reason to know is legal.
    """

    if require_adjacent and not is_adjacent(current, target, bounds):
        raise NonAdjacentMoveError(
            f"{target} is not adjacent to {current}; chasing a non-adjacent "
            "target isn't implemented yet"
        )
    exploration = resolve_explore(
        target_explored_percent,
        target_terrain,
        explorer_skill,
        partial=True,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
    )
    return MoveResult(new_coord=target, exploration=exploration, battle_expected=occupied_by_enemy)
