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
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState


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
