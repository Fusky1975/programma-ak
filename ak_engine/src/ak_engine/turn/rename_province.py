"""Turn-1 home-province rename (rulebook-adjacent, `DEF2.PAS Read_T1Names`) -- Phase 150.

`report/turn_report.py`'s own module docstring, and `models/army_naming.py`'s
own Phase 149 research, both confirmed province names are never
*generated* at runtime by the real host engine -- they're baked into the
world-generated map by `AKGEN.EXE` (a separate offline tool whose own
source isn't present in `Programma Pascal.zip`), read once from disk
into the global `pname^[x,y]` array. `ProvinceState.name` (Phase 150)
models that array slot directly and starts `None`, matching the same
"no name-synthesis system, `None` until a caller sets it" convention
this project already uses for every other unmodeled naming gap.

**The one real, sourced runtime exception**: `HostAK/TP/DEF2.PAS`'s
`Read_T1Names` (~lines 706-737, present in both a `{$IFDEF Moderator}`
and a `{$ELSE}` body -- the `{$ELSE}` one is the real player-facing host
engine this project reconstructs, per the same `{$IFDEF Moderator}`
resolution already established, Phase 79/149). Quoted in full (the
`{$ELSE}` body):

```pascal
PROCEDURE Read_T1Names;
VAR ctoname,ndex: integer;
    tc: char;
BEGIN
  FOR ndex:= 1 TO 3 DO WITH t1names[ndex] DO BEGIN
    READ(miscfile,tc,tc);
    Bit_Read(lptoname);
    READLN(miscfile,tmp);
    Delete(tmp,Length(tmp),1);
    namefor:= tmp;
    CASE ndex OF
      1: pname^[bornx[playkg],borny[playkg]]:= tmp;
      ELSE lname^[lptoname]:= tmp;
     END;
   END;
 END;
```

On turn 1, a player may submit up to 3 rename entries: `ndex=1` renames
their own home/capital province (`bornx[playkg],borny[playkg]` --
this project's own `KingdomState.home_province`); `ndex=2,3` rename up
to 2 starting leaders (`LeaderState.name` is already a free-form string
field, so no new modeling is needed for that half -- it's a plain
assignment a caller can already do directly).

**Confirmed out of scope for this phase, not guessed at**: `Read_T1Names`
reads from `miscfile`, a *separate* input stream from the `AK3__T*.K1`
move files this project's own `parser/k1_moves.py` already handles --
no sample of `miscfile`'s own format exists anywhere in this project's
data, and nothing in the available archive documents it further. This
module therefore only implements the *mechanism* (given an
already-known new name, apply it) -- not a parser that could trigger it
from a real submitted file. Wiring a real trigger is blocked on finding
or acquiring real `miscfile`-format sample data; until then, callers
supply the new name directly, the same "caller supplies what state/
parsing can't determine" convention `report/turn_report.py`'s own
`describe_*` composers already establish.

**Phase 152 addendum**: ``assign_province_name`` below covers the other
half of the naming gap -- every non-capital province, for which no
``Read_T1Names``-style mechanism exists at all in the real host engine
(the rulebook only ever lets a player rename their own capital). At the
time, the real world-generation source (``AKGEN.EXE``) that would have
picked these names wasn't known to survive in the archive, so this
project drew from a project-original name pool the user supplied
directly, organized by terrain -- not a Pascal transcription, and not a
reconstruction of ``AKGEN.EXE``'s own selection algorithm. Picking "an
unused name from the matching terrain's pool" was this project's own,
undocumented-in-any-source design choice for turning that static list
into per-province names on demand.

**Phase 366 addendum**: ``models/province_names.py``'s own underlying
pools were rewritten from a real recovered Pascal source
(``PRNAMES.PAS``, found by a later reverse-engineering pass over
``AKGEN.EXE``) -- see that module's own docstring for the full
correction writeup. The real source's own confirmed selection rule --
"uniform random source index inside the terrain pool; source indices
already used are rejected and redrawn" -- turns out to already match
this function's own "prefer an unused name, reject and redraw on
collision" design almost exactly, so ``assign_province_name`` itself
needed no logic change, only the data underneath it.
"""

from __future__ import annotations

import random

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.models.province_names import PROVINCE_NAME_POOLS


def rename_home_province(state: GameState, kingdom_id: int, new_name: str) -> None:
    """Renames ``kingdom_id``'s own home/capital province -- ``Read_T1Names``'s
    ``ndex=1`` branch (``pname^[bornx[playkg],borny[playkg]]:= tmp``).
    Raises ``KeyError`` if ``kingdom_id`` isn't in ``state.kingdoms`` or its
    ``home_province`` coordinate isn't in ``state.provinces`` -- both are
    real modeling invariants this project already relies on elsewhere,
    not conditions this function should silently ignore.
    """

    kingdom = state.kingdoms[kingdom_id]
    province = state.provinces[kingdom.home_province]
    province.name = new_name


def assign_province_name(state: GameState, coord: HexCoord, rng: random.Random) -> str:
    """Assigns ``coord``'s province a name drawn from its terrain's
    project-original name pool (``models/province_names.py``), if it
    doesn't already have one -- idempotent, so calling this again on an
    already-named province just returns the existing name unchanged
    rather than re-rolling it.

    Prefers a name not already in use anywhere in ``state.provinces``,
    falling back to allowing reuse only once a terrain's own pool is
    fully exhausted (no real source documents how the original engine
    avoided collisions, since it never generated names at runtime at
    all -- this is this project's own tie-breaking choice, not a
    transcription).

    Raises ``KeyError`` if ``coord`` isn't in ``state.provinces``, and
    ``ValueError`` if that province's terrain has no name pool (i.e.
    ``Terrain.NO_TERRAIN``) -- both real modeling invariants, not
    conditions to silently ignore.
    """

    province = state.provinces[coord]
    if province.name is not None:
        return province.name

    pool = PROVINCE_NAME_POOLS.get(province.terrain)
    if not pool:
        raise ValueError(f"no province name pool for terrain {province.terrain!r}")

    used = {p.name for p in state.provinces.values() if p.name is not None}
    candidates = [name for name in pool if name not in used]
    if not candidates:
        candidates = list(pool)

    name = rng.choice(candidates)
    province.name = name
    return name
