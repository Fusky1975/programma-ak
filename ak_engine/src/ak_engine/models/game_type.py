"""``GameType`` -- the world header's own `gametyp` enum (header field 22).

Moved here from `parser/gw_world.py` (Phase 538) so `models/game_state.py`
can read `GameState.game_type` without `models/` importing from `parser/`
-- this project's own established import direction is parser depends on
models, never the reverse. `parser/gw_world.py` re-imports it from here,
so every existing `from ak_engine.parser.gw_world import GameType` call
site keeps working unchanged.
"""

from __future__ import annotations

from enum import Enum


class GameType(Enum):
    """Confirmed directly from a static reverse engineering of AKGEN.EXE
    (see `parser/gw_world.py`'s own module docstring, Phase 342 addendum),
    not inferred from real letters. Every one of the real `GW3__T1`-
    `GW3__T12` files reads `NORMAL`.
    """

    TRIAL = 0
    NORMAL = 1
    EUROPE = 2
    EARTH = 3
    VALHALLA = 4
    ARCANES = 10
