"""Army display-name builder for the real Army List table, Phase 236.

Ported from `HostAK/TP/REPORTS.PAS:986-992`, the exact line the Army List
table's own name column comes from:

```pascal
Make_Des(an,s);
IF astate[an] = Zomboid THEN strx:= Concat(s,' Skel ',atdesig[Mod_AType(an)])
  ELSE strx:= Concat(s,' ',atname[Mod_AType(an)]);
```

`Make_Des` itself (`HostAK/TP/YAK.PAS:66-75`, the real `{$IFDEF Moderator}`
branch -- `HostAK` is the Moderator/Host build, already established by
`turn/office_holder.py`'s own citations of `SAY.PAS`/`RUMORS.PAS`'s own
`{$IFDEF Moderator}` sections) just ordinal-suffixes `an`, the army's own
numeric index -- English only: the sibling `Company = Roland` branch is a
French localization variant (`REPORTS.PAS`'s many `IF Company = Roland
THEN WRITE(playfile,...)` French-text sites) this project's own real
letter data (`SE3__T*.K*`, always English) never exercises.

**Race is NOT part of the name string.** `REPORTS.PAS:996` prints
`rname[Mod_ARace(an)]` in its own, separate table column right after the
name -- confirmed by real letter data: `SE3__T0.K1:135-137`'s own Army
List table shows `"108th Skel Bowmen       Elf  Average  Veteran"` /
`"110th Bowmen            Elf  Average  Veteran"`, i.e. the race ("Elf")
never appears inside the name itself even for a non-Human army, matching
`atname`/`atdesig` here needing no race parameter at all.

**This function is a second, distinct naming routine from `models/
army_naming.py make_army_name()` (`YAK.PAS Make_AName`, Phase 149) --
they are not duplicates.** `make_army_name()`'s own docstring already
correctly narrowed its one *directly* confirmed real Pascal call site to
an Imperial-Office-holder display line (`REPORTS.PAS:1652,1716`, the
`Army_Office(ofc)` case for the Praetor/Flagship/Airforce offices this
project's own `turn/office_holder.py` doesn't model) -- but this project
had already adopted it as the general-purpose per-army-naming utility
for any report needing one (Phase 212's `_army_display_name()`/
`_trail_army_name()`), and `report/turn_report.py describe_battle()`
does the same as of Phase 236 (`build_battle_army_names()`). This
module's own `make_army_display_name()` is deliberately kept separate
rather than folded into that one, real, sourced formula for a different
table -- see `report/turn_report.py`'s own module docstring for the
full Phase 236 correction.

**`is_skeletal` (Zomboid).** `CTBOTH.PAS:1260`'s own `astate` enum
(`Dead,Hired,Mercenary,Zomboid,Bold,Sold,Loser,Calm`) has no real
`astate[an]:= Zomboid` assignment site anywhere in the extracted source --
another "lost with the missing main driver" gap. `Zomboid`'s own name,
the literal "Skel" text this function ties to it, and `RUMORS.PAS:354`'s
own `lalign[armykng] = Undead` check alongside it all agree it marks an
army raised via the Skeletal_Army spell, so `ArmyState.is_skeletal`
(`models/game_state.py`, Phase 236) is set by `turn/cast_execution.py
_execute_skeletal_army()` and threaded straight through here.
"""

from __future__ import annotations

from ak_engine.models.army_type import ARMY_TYPE_DESIGNATION, ARMY_TYPE_NAME, ArmyType


def make_army_ordinal(army_number: int) -> str:
    """`YAK.PAS Make_Des`'s own real `{$IFDEF Moderator}` English branch --
    see module docstring. Suffixes `army_number` with 'st'/'nd'/'rd'/'th',
    with the standard 11th/12th/13th exception (`n MOD 100 = 11/12/13`
    always gets 'th', even though `n MOD 10` alone would say 1/2/3).
    """

    text = str(army_number)
    last_two = army_number % 100
    if last_two not in (11, 12, 13):
        last_one = army_number % 10
        if last_one == 1:
            return f"{text}st"
        if last_one == 2:
            return f"{text}nd"
        if last_one == 3:
            return f"{text}rd"
    return f"{text}th"


def make_army_display_name(army_number: int, army_type: ArmyType, *, is_skeletal: bool = False) -> str:
    """`REPORTS.PAS:986-992`'s own real Army List table name-column
    builder -- see module docstring, including why `is_skeletal` (real
    `Zomboid` state) is the only branch, and why race is never part of
    this string.
    """

    ordinal = make_army_ordinal(army_number)
    if is_skeletal:
        return f"{ordinal} Skel {ARMY_TYPE_DESIGNATION[army_type]}"
    return f"{ordinal} {ARMY_TYPE_NAME[army_type]}"
