"""``Ldr_Near``/``Known_Loc`` primitives (``RUMORS.PAS``), Phase 636.

Sourced from ``LDRNEAR.md`` (Desktop/PROGRAMMA AK/LDRNEAR.md,
2026-08-25), a disassembly-level reverse-engineering report the user
supplied to close a "no source" blocker found while investigating the
CHARACTERS report's own "impulse 2" (wandering Heroes/other Kings'
leaders this kingdom happens to know the location of) and "impulse 3"
(Priest-office clairvoyance) passes.

**This module is primitives only -- nothing here is wired into any
report composer yet.** ``report/turn_report.py describe_characters_
report()`` still only models "impulse 1" (a kingdom's own leaders).
Wiring impulse 2/3 in needs the separate, much larger ``Was_Clairved``/
``Desc_Stranger`` prose pipeline (``REPORTS.PAS``, not modeled at all
here), plus a resolved real value for ``orig_turn`` (see below) -- both
left for a later phase, matching this project's own "primitive now,
wiring later" convention (e.g. Feature -> Power, Phase 616 vs. 622/623).

``leader_location_known_to_kingdom()`` takes ``orig_turn`` as an
explicit caller-supplied parameter rather than resolving it internally,
because the real Pascal ``Known_Loc`` reads it from a global the
function itself never derives. Its exact ak_engine mapping (plausibly
``GameState.turn_number``, but not confirmed against a real sample) is
deliberately left to whichever future phase does the report wiring.

Also deliberately out of scope: ``Known_Merc`` (``RUMORS.PAS``), a
*different* report's own mercenary-army-visibility check that reuses
``leader_near()`` at ``radius=1`` -- not touched here.
"""

from __future__ import annotations

import itertools

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import hex_distance_wrapped
from ak_engine.worldgen.place_map import DEFAULT_WIDTH


def leader_near(
    state: GameState,
    kingdom_id: int,
    coord: HexCoord,
    radius: int,
    *,
    board_width: int = DEFAULT_WIDTH,
) -> bool:
    """``Ldr_Near(kng,x,y,radius)`` -- LDRNEAR.md section 2.

    Existential test: at least one leader with ``LeaderState.kingdom_id
    == kingdom_id`` (the already-established ``LKing(ldr) = kng``
    mapping) within ``radius`` hexes of ``coord`` (inclusive, wraparound-
    aware via ``hex_distance_wrapped()``).

    Scans both ``state.leaders`` (living) and ``state.dead_leaders``
    (archived by ``GameState.remove_leader()``, Phase 59) -- the source
    confirms ``Ldr_Near`` has no ``Dead`` filter at all (LDRNEAR.md
    section 2.3, point 5: "Non controlla direttamente lstate[ldr] e non
    contiene un filtro esplicito contro Dead").
    """

    for leader in itertools.chain(state.leaders.values(), state.dead_leaders.values()):
        if leader.kingdom_id != kingdom_id:
            continue
        if hex_distance_wrapped(leader.location, coord, board_width) <= radius:
            return True
    return False


def leader_location_known_to_kingdom(
    state: GameState,
    target_leader_id: int,
    viewer_kingdom_id: int,
    *,
    orig_turn: int,
    board_width: int = DEFAULT_WIDTH,
) -> bool:
    """``Known_Loc(ln,kng,gtmod=0,advrep=true)`` -- LDRNEAR.md section
    6.2, the exact reduction ``REPORTS.PAS Rep_Leaders`` uses for the
    CHARACTERS report's impulse-2/3 passes.

    ``target_leader_id`` is looked up in ``state.leaders`` then
    ``state.dead_leaders`` -- an unknown id, or a target who belongs to
    the viewer's own kingdom, is never a "stranger" and returns
    ``False`` immediately, matching the real formula's own ``LKing(ln)
    != kng`` guard.
    """

    target = state.leaders.get(target_leader_id) or state.dead_leaders.get(target_leader_id)
    if target is None:
        return False
    if target.kingdom_id == viewer_kingdom_id:
        return False

    province = state.provinces.get(target.location)
    owner_kingdom_id = province.owner_kingdom_id if province is not None else None

    # ``powner[lx[ln],ly[ln]] <> ln`` (advrep=true, so the ``or (not
    # advrep)`` half of the real clause never applies): once LKing's own
    # "King index == Kingdom id" fact is applied, this is only ever
    # false when the target is a King sitting on his own kingdom's
    # throne province -- unconditionally true for any Hero target,
    # whose leader_id never lands in the Kingdom-id range.
    if target.is_king and target.kingdom_id is not None and owner_kingdom_id == target.kingdom_id:
        return False

    # cover_gate: ISpy_Cover(ln) is unconditionally 1.0 in the standard,
    # non-Moderator report engine (DEF2.PAS: the only two `cover[ldr]`
    # setters, lines 417/562, are both inside {$IFDEF Moderator}), so
    # Trunc(16*1.0)=16 is unconditionally greater than any (.. AND 15)
    # value (capped 0-15) -- this gate is always satisfied, and
    # `orig_turn`/`begvalkng` never actually matter for it.
    cover_gate = True

    location_gate = owner_kingdom_id == viewer_kingdom_id or (
        (target_leader_id + orig_turn) % 5 <= 1
        and leader_near(state, viewer_kingdom_id, target.location, 0, board_width=board_width)
    )

    return cover_gate and location_gate
