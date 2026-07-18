"""Bridges `parser/gw_world.py`'s own file-order `GWProvinceRecord`s into
real `HexCoord`-keyed `ProvinceState`s (Phase 223).

**The coordinate mapping is empirically confirmed, not a guess.** A GW
world file's own province record carries no coordinate field (see
`gw_world.py`'s own module docstring) -- but real King's own turn-report
letters (`SE3__T1.K*`) print each province's real coordinate in their
ASCII map legend, as `"<Name>(<XXYY>)"` (e.g. `"Macondo(0205)"`, meaning
x=02, y=05, both 1-indexed). Collecting every such `(name, x, y)` triple
findable across all 9 of game 3's real turn-1 letters (63 provinces'
worth, after de-duplicating name variants) and checking each one against
its own position in `GW3__T1`'s own on-disk record order gives a **100%
exact match, zero mismatches**, under the hypothesis:

    x (1-indexed) = record_index // 9 + 1
    y (1-indexed) = record_index %  9 + 1

i.e. the file's own record order is column-major -- outer loop over `x`
(18 values, 1..18), inner loop over `y` (9 values, 1..9), 18 x 9 = 162,
matching the confirmed real province count exactly. This mirrors
`REPORTS.PAS Rep_Provs`'s own real iteration order verbatim (`FOR px:=
left TO right DO FOR py:= top TO bottom DO`, px/x outer, py/y inner) --
strong corroborating evidence the world file itself was written by the
same nested-loop traversal Rep_Provs later reads it with.

Converting to this project's own 0-indexed `HexCoord`, this collapses to
`HexCoord(record_index // 9, record_index % 9)` directly -- no offset
arithmetic needed.

**Not claimed to be a universal board size for every possible world** --
confirmed specifically for `GW3__T1` (this project's one available real
fixture). The 162-province total is stated to be a fixed rule (the
user's own words), and 18 x 9 = 162 exactly, so a fixed board size across
every world is plausible, but this hasn't been cross-checked against a
second real `GW*` file (e.g. `GW6`) -- a `height` parameter is exposed
below rather than hardcoding this as an unconditional constant.

**Phase 224 adds `resolve_province_owners()`**: `GWProvinceRecord.
governor_leader_id` is a leader id, not a kingdom id (see `gw_world.py`'s
own "Philo(70)" cross-check). Resolving it needs a `GameState` whose
`leaders` dict is already populated (e.g. via `turn/kingdom_bridge.py
sync_leaders_from_kingdom()` from the matching `AK3__T*.K1` files) --
this project's own already-established real King's-own-leader_id-equals-
kingdom_id convention means a King-governed province resolves directly,
while a Hero-governed province resolves via that Hero's own `LeaderState.
kingdom_id` (or stays unresolved if that Hero is an independent
Valhalla visitor with no kingdom, or simply isn't in `state.leaders` at
all -- e.g. because only a subset of kingdoms' move files were ever
bridged). Unresolvable records are left at `owner_kingdom_id = None`
rather than raising -- a partially-bridged `GameState` (not every
kingdom's `AK3__T*.K1` available) is an expected, ordinary case, not an
error condition.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import GWProvinceRecord

# Rows per column, confirmed for GW3__T1 (see module docstring). 18
# columns x 9 rows = 162, the confirmed real province count.
CONFIRMED_BOARD_HEIGHT = 9


def _coord_for_index(index: int, height: int) -> HexCoord:
    return HexCoord(index // height, index % height)


def bridge_gw_world_provinces(
    records: list[GWProvinceRecord], *, height: int = CONFIRMED_BOARD_HEIGHT
) -> dict[HexCoord, ProvinceState]:
    """Assigns each record its real, column-major `HexCoord` and builds a
    `GameState.provinces`-ready dict.

    Raises `ValueError` if `records` isn't an exact multiple of `height`
    long, the same sanity check `Rep_Provs`'s own confirmed rectangular
    board shape implies -- a partial last column would mean either a
    wrong `height` or a truncated/corrupted `records` list, not a
    silently-mappable state.
    """

    if height <= 0:
        raise ValueError(f"height must be > 0, got {height}")
    if len(records) % height != 0:
        raise ValueError(
            f"{len(records)} records isn't an exact multiple of height={height} "
            "-- wrong height, or a truncated/corrupted records list"
        )

    provinces: dict[HexCoord, ProvinceState] = {}
    for index, record in enumerate(records):
        coord = _coord_for_index(index, height)
        provinces[coord] = ProvinceState(
            coord=coord,
            terrain=record.terrain,
            race=record.race,
            name=record.name,
            tax=record.tax,
        )
    return provinces


def resolve_province_owners(
    provinces: dict[HexCoord, ProvinceState],
    records: list[GWProvinceRecord],
    state: GameState,
    *,
    height: int = CONFIRMED_BOARD_HEIGHT,
) -> int:
    """Sets each bridged province's real `owner_kingdom_id`, resolved
    from its own `GWProvinceRecord.governor_leader_id` via `state.
    leaders` (see module docstring for exactly what "resolved" means for
    a King vs. a Hero vs. an unknown leader id).

    Mutates `provinces` in place (the same dict `bridge_gw_world_provinces()`
    returned, keyed the same way via `records`' own index order) and
    returns the count of provinces whose owner was actually resolved
    (found in `state.leaders`) -- not the count set to a non-`None`
    kingdom id, since a resolved independent Hero legitimately resolves
    to `None`.
    """

    resolved = 0
    for index, record in enumerate(records):
        if record.governor_leader_id is None:
            continue
        leader = state.leaders.get(record.governor_leader_id)
        if leader is None:
            continue
        province = provinces.get(_coord_for_index(index, height))
        if province is None:
            continue
        province.owner_kingdom_id = leader.kingdom_id
        resolved += 1
    return resolved
