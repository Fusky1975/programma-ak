"""Army display-name generation (rulebook example: "the 231st Bowmen") -- Phase 149.

Closes the exact gap `report/turn_report.py`'s own module docstring
flags: "'Army name' ... is never synthesized here -- there is no
ordinal-numbering/naming system anywhere in this project (LNAMES.PAS/
PRNAMES.PAS territory, a separate, entirely unbuilt subsystem)." That
citation turned out to misidentify the source: `LNAMES.PAS`/`PRNAMES.PAS`
are flat, one-name-per-line word-pool text files (leader names and
province/geographic names respectively -- confirmed by `HostAK/MS/
AKMAN.TXT` lines 525-526), consumed only by `AKGEN.EXE`, a separate
offline world-generator whose own source isn't present in the archive.
Neither file has anything to do with army naming.

The real mechanism lives in `HostAK/TP/YAK.PAS` lines 49-85, two
routines, both fully present in source (not compiled-unit territory):

```pascal
PROCEDURE Make_Des(n: integer; VAR s: Str30);
BEGIN
  Str(n,s);
    CASE n MOD 10 OF
      1: s:= Concat(s,'st');
      2: s:= Concat(s,'nd');
      3: s:= Concat(s,'rd');
      ELSE s:= Concat(s,'th');
     END;
 END;

PROCEDURE Make_AName(an: integer; VAR s: Str30; caller: byte);
BEGIN
  Make_Des(an,s);
  r:= Mod_ARace(an);
  IF Noid_Race(r) THEN
    IF caller = 2 THEN s:= Concat(s,' ',radj[r])
      ELSE IF caller <> 0 THEN IF rab3[r] <> '' THEN s:= Concat(s,' ',rab3[r]);
  IF caller = 1 THEN s:= Concat(s,' ',atdesig[Mod_AType(an)]);
 END;
```

**`Make_Des` has two conditionally-compiled bodies** -- the one quoted
above is the `{$ELSE}` (non-Moderator) branch; a separate `{$IFDEF
Moderator}` branch adds an 11th/12th/13th exception (`n MOD 100 <> 11`
etc.) plus an unrelated `Company = Roland` French-suffix variant. This
project already established, confirming it again here, that `{$IFDEF
Moderator}` marks the game-master/world-generation-side build, never
the player-facing host/turn-processor this project reconstructs (see
`models/feature.py MONSTER_GUARDED_FEATURE_TYPES`'s own Phase 79 note).
`ordinal_suffix()` below is therefore the plain `{$ELSE}` branch --
which has a real, confirmed quirk of its own: **no 11/12/13 exception
at all**, so army 11 is genuinely "11st", not "11th", in the real host
engine. Transcribed as-is, the same "don't silently fix a confirmed
source oddity" stance already taken for `CONTROL_UNDEAD`'s truncation
(Phase 122) and the Mermen "air-transport" wording (Phase 127).

**`an` is the army's own array-slot index**, not a per-kingdom or
per-race counter -- confirmed by `Make_AName`'s own body indexing
straight off it (`Mod_ARace(an)`/`Mod_AType(an)`), with no visible
kingdom- or race-scoping anywhere in the routine. This lines up exactly
with `GameState.new_army_id()`'s own monotonic, game-wide counter
(Phase 15) -- `ArmyState.army_id` is the direct real-world equivalent
of `an`, needing no translation.

**Only `caller=1` is ever actually invoked** -- confirmed via
`REPORTS.PAS` lines 1652 and 1716 (`IF Army_Office(ofc) THEN
Make_AName(...,1)`), the only two call sites in the archive. `caller=1`
is also the one shape `PROSE.TXT`'s own documented examples match
("the 231st Bowmen", "241st Axemen, 34th Legion and 145th Fleet" --
no full race adjective anywhere, only the short tag and the army-type
designation). `caller=0`/`caller=2` (a bare name, and a full-race-
adjective variant respectively) have no real caller anywhere in this
archive, so `make_army_name()` below only ever builds the `caller=1`
shape -- the same "only build what's actually reachable" discipline
this project's `describe_*` composers already follow.

**`Noid_Race(r)` -- a reconstruction assumption, not a directly-quoted
source**: like `End_Punct` before Phase 131's discovery, `Noid_Race`
is used (`YAK.PAS` line 81, also `SAY.PAS` line 744) but never defined
anywhere in the available archive -- compiled-unit territory. Read
literally ("no-[race-]id"), and consistent with every real example
never showing a race tag on what's presumably a Human/default army,
this project takes `Noid_Race(r)` to mean `r <> Human` -- "does this
race need marking at all." If real game data ever contradicts this,
this is the first place to revisit (the same caveat `turn/movement.py`'s
own hex-adjacency assumption already carries).

**`RACE_SHORT_TAG` -- a genuine source oddity, transcribed as-is, not
corrected**: `CTBOTH.PAS` line 588's own `rab3` array literal has one
fewer non-Rohan blank entry than `rname`/`radj`/`rpname`'s own
confirmed-correct positional alignment (`RACE_NAME`/`RACE_ADJECTIVE`,
Phase 87). Parsing the literal by exact position (verified against the
file's own raw bytes, not just eyeballed) puts `'Roh'` -- unmistakably
meant as Rohan's own short tag, given `'Elf'`/`'Dwf'`/`'Orc'` sit
correctly at `Race.ELVEN`/`Race.DWARVEN`/`Race.ORCISH`'s own indices
1/2/3 -- one slot late, landing on ordinal 15 (the unused `er3`
extension race) instead of `Race.ROHAN`'s own ordinal 14. `Race` has no
`er3` member to even receive it, so under strict positional
transcription `RACE_SHORT_TAG[Race.ROHAN]` is empty: a Rohan army gets
no short race tag at all from this table, matching the source exactly,
not what was evidently intended.
"""

from __future__ import annotations

from ak_engine.models.army_type import ARMY_TYPE_DESIGNATION, ArmyType
from ak_engine.models.race import Race

# CTBOTH.PAS `rab3` (line 588), verbatim by exact array position -- see
# module docstring for the confirmed off-by-one oddity affecting Rohan.
RACE_SHORT_TAG: dict[Race, str] = {
    Race.HUMAN: "",
    Race.ELVEN: "Elf",
    Race.DWARVEN: "Dwf",
    Race.ORCISH: "Orc",
    Race.DRAGONS: "",
    Race.EAGLES: "",
    Race.WHALES: "",
    Race.NO_RACE: "",
    Race.MERMISH: "",
    Race.ENTISH: "",
    Race.TROLLISH: "",
    Race.WEREFOLK: "",
    Race.SAURIAN: "",
    Race.VAMPISH: "",
    Race.ROHAN: "",
}


def ordinal_suffix(n: int) -> str:
    """Renders ``YAK.PAS Make_Des``'s own non-Moderator (real host-engine) body:
    ``n`` followed by 'st'/'nd'/'rd'/'th' keyed purely on ``n MOD 10`` --
    see the module docstring for the confirmed "no 11/12/13 exception"
    quirk this carries into values like 11, 111, 211...
    """

    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def make_army_name(army_id: int, army_type: ArmyType, race: Race) -> str:
    """Renders ``YAK.PAS Make_AName(army_id, s, caller=1)`` -- the one real,
    reachable shape (see module docstring): an ordinal army id, an
    optional short race tag (omitted for ``Race.HUMAN`` -- the
    ``Noid_Race`` reconstruction -- and whenever ``RACE_SHORT_TAG``
    itself is empty for that race), and the army type's own designation
    (``ARMY_TYPE_DESIGNATION``, Phase 90).
    """

    name = ordinal_suffix(army_id)
    if race is not Race.HUMAN:
        tag = RACE_SHORT_TAG[race]
        if tag:
            name = f"{name} {tag}"
    return f"{name} {ARMY_TYPE_DESIGNATION[army_type]}"
