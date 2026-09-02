"""Island-province (Type 2 terrain, `pt2`) world-creation setup -- Phase 282.

**Phase 723 correction**: `pt2` is a real, parsed field, not absent from
the archive -- `parser/gw_world.py GWProvinceRecord.alternate_terrain`
has decoded it since Phase 373, and `parser/gw_world_bridge.py bridge_
gw_world_provinces()` now bridges it into `ProvinceState.is_island`
(Phase 723 addendum). This module's own opt-in, exact-count setup
helper below remains the right, separate tool for a hand-built or
synthetic Super-AK world -- one with no real `GWProvinceRecord` to
bridge `pt2` from in the first place -- so the two paths are
complementary, not redundant: whichever one a given `GameState` reaches
`is_island` through, the field and its one real gameplay consequence
(below) behave identically either way. Implemented per the user's own
explicit domain knowledge (2026-07-29), not a guess --

    "Questa parte si usa per le partite di super AK (una variante con
    massimo 24 giocatori). Lì ci sono le isole, province per metà terra
    e per metà mare. In queste province le unità hanno forza per metà
    come se fossero in mare e per metà come se fossero a terra. Le
    province volanti (draghi e aquile) non hanno nessuna variazione."

-- an optional Super AK variant rule (games up to 24 players), not part
of ordinary Adventurer-Kings play. `ProvinceState.is_island` (Phase 282,
`models/game_state.py`) is the flag this module sets; `turn/strength.py
compute_effective_strength()`'s own `is_island` parameter is the one
real gameplay consequence the user specified.

**"Optional, decided at world creation, exact island count instead of an
exact land-province count"** -- the user's own words. This project has
no full terrain-layout world generator at all (`turn/world_generation.py`
only ever populates *features* onto already-existing provinces -- see
its own docstring; the real `AKGEN.EXE` that would have laid out terrain
itself is compiled-only, no `.PAS` source survives). So "at world
creation" here means: after a `GameState`'s provinces are already
populated (bridged from a real `GW3` world file, or built by hand for a
Super AK setup), a moderator calls `apply_island_provinces()` once with
the exact number of Islands they want, and this function marks that many
-- chosen uniformly at random from the world's own eligible land
provinces -- rather than generating new terrain from nothing.
"""

from __future__ import annotations

import random

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord, Terrain

# Terrain kinds an Island's own "land half" can be -- every non-Sea,
# non-NO_TERRAIN member. A province already SEA doesn't need a half-Sea
# overlay (it already is one), and NO_TERRAIN isn't a real, ownable
# province at all (turn/world_generation.py's own module docstring
# already excludes it from feature placement for the same reason).
_ISLAND_ELIGIBLE_TERRAIN = frozenset(Terrain) - {Terrain.SEA, Terrain.NO_TERRAIN}


def apply_island_provinces(
    state: GameState, island_count: int, rng: random.Random | None = None
) -> list[HexCoord]:
    """Marks exactly ``island_count`` of ``state``'s own land provinces as
    Islands (``ProvinceState.is_island = True``) -- the moderator's own
    exact-count choice, per the user's own design (see module docstring).

    Chosen uniformly at random, without replacement, from every province
    whose ``terrain`` is land (not Sea, not ``NO_TERRAIN``) and not
    already an Island -- sorted by coordinate first so the same ``rng``
    seed always picks the same set, the same determinism precedent every
    other ``random.Random``-seeded chooser in this project already
    follows (e.g. ``turn/world_generation.py``'s own per-province rolls).

    Raises ``ValueError`` if ``island_count`` exceeds the number of
    eligible provinces -- an explicit refusal, not a silent clamp to
    however many are available (this project's own established
    validation style, e.g. ``turn/recruit_execution.py``'s per-turn
    limit checks) -- or if ``island_count`` is negative.

    Returns the list of coordinates newly marked, sorted the same way,
    so a caller can log or report exactly which provinces were chosen.
    """

    if island_count < 0:
        raise ValueError(f"island_count must not be negative, got {island_count}")

    eligible = sorted(
        (
            coord
            for coord, province in state.provinces.items()
            if province.terrain in _ISLAND_ELIGIBLE_TERRAIN and not province.is_island
        ),
        key=lambda coord: (coord.x, coord.y),
    )
    if island_count > len(eligible):
        raise ValueError(
            f"cannot place {island_count} islands: only {len(eligible)} eligible land "
            "provinces available"
        )

    rng = rng if rng is not None else random.Random()
    chosen = rng.sample(eligible, island_count)
    for coord in chosen:
        state.provinces[coord].is_island = True

    return sorted(chosen, key=lambda coord: (coord.x, coord.y))
