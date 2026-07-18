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

**Deliberately not attempted here**: `GWProvinceRecord.governor_leader_id`
is not resolved to an owning kingdom id -- doing so needs a `GameState`-
level leader/kingdom lookup this pure bridging function doesn't have
(and doesn't need, for the coordinate-only work this phase covers). The
returned `ProvinceState.owner_kingdom_id` is always `None`.
"""

from __future__ import annotations

from ak_engine.models.game_state import ProvinceState
from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import GWProvinceRecord

# Rows per column, confirmed for GW3__T1 (see module docstring). 18
# columns x 9 rows = 162, the confirmed real province count.
CONFIRMED_BOARD_HEIGHT = 9


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
        coord = HexCoord(index // height, index % height)
        provinces[coord] = ProvinceState(
            coord=coord,
            terrain=record.terrain,
            race=record.race,
            name=record.name,
            tax=record.tax,
        )
    return provinces
