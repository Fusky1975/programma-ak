"""Kingdom/character alignment.

Originally (Phase 4) transcribed from the tags used in the parent
project's game-design docs (`Mostri.md`: Anti-Holy, Evil, Pagan, Good,
Neutral, Divine, Druid) rather than `CTBOTH.PAS` directly. **Phase 80
confirms those 7 tags are, in fact, the real Pascal `outlook` enum's
own display strings** -- found while researching what else `CTBOTH.PAS`
still had to offer, the same way Phase 79's `MONSTER_GUARDED_FEATURE_TYPES`
was found.

**The real source, `CTBOTH.PAS`**: `outlook = (Heavenly, Good, Druidic,
Worldly, Animal, Evil, Hellish, Undead, Mechanical, Special)` (~line
454-459), with its own display-string table `outname: outstrs =
('Divine', 'Good', 'Druidic', 'Neutral', 'Pagan', 'Evil', 'Anti-Holy',
'Undead', 'Mechanical', 'Special')` (~line 1642-1643, positionally
verbatim). Confirmed to genuinely mean "leader/kingdom alignment" (not
some unrelated concept that happens to share the name) via
`REPORTS.PAS`'s own `lalign[ldran]: outlook` -- literally "leader
alignment", read and compared against office/rank thresholds there.

**The Pascal ordinal name and its own display string don't always
match**, which is easy to miss if only skimming the ordinal list:
`Heavenly` displays as **"Divine"**, `Worldly` displays as
**"Neutral"**, `Animal` displays as **"Pagan"**, `Hellish` displays as
**"Anti-Holy"** -- `Good`, `Druidic`, `Evil`, `Undead`, `Mechanical`,
and `Special` display as themselves. This module's own enum member
*names* were chosen (Phase 4, before this correspondence was known) to
match the **display strings**, not the Pascal ordinal identifiers --
now confirmed to be the right call, since the display string is what
every consumer of this project's own `Alignment` actually cares about
(fanaticism chance, prose rendering, etc.), not Pascal's own internal
symbol.

**One real discrepancy found and fixed**: `DRUID`'s own value was
`"Druid"`, but the confirmed Pascal `outname` string is **"Druidic"**
-- a one-word difference from `Mostri.md`'s own, less formal tag.
Corrected to the verbatim Pascal string; safe to change outright
(rather than just flag) since nothing in this project's source or
tests reads `Alignment.DRUID.value` or any other member's `.value`
anywhere -- confirmed by a direct grep before making the change.

**Not renamed to the Pascal ordinal identifiers**: `Alignment` is
consumed across a dozen modules and as many test files by this point
(kingdom/army fanaticism, battle orchestration, Challenge/Patrol/Pursue
execution); renaming `DIVINE`→`HEAVENLY`, `NEUTRAL`→`WORLDLY`,
`PAGAN`→`ANIMAL`, `ANTI_HOLY`→`HELLISH` to match Pascal's own ordinal
names would touch all of it for zero behavioral change (the string
*values*, which is what actually matters here, already matched before
this phase). Only the three real values this project was previously
missing -- `UNDEAD`, `MECHANICAL`, `SPECIAL` -- are added.

A full kingdom alignment model (multi-tag combinations, alignment
shifts, diplomacy effects, the `office`/rank-threshold system
`REPORTS.PAS`'s own `lalign` comparison feeds into) is still a
separate, much larger system this project hasn't built.

**Phase 162 adds `ALIGNMENT_ORDINAL`/`ALIGNMENT_BY_ORDINAL`**, the real
Pascal `outlook` ordinal sequence quoted above (`Heavenly=0, Good=1,
Druidic=2, Worldly=3, Animal=4, Evil=5, Hellish=6, Undead=7,
Mechanical=8, Special=9`) -- **deliberately NOT this module's own
declaration order** (`DIVINE, GOOD, NEUTRAL, EVIL, ANTI_HOLY, PAGAN,
DRUID, UNDEAD, MECHANICAL, SPECIAL`), which was chosen (Phase 4/80) to
match the *display strings*' own historical listing order, not the
real ordinal sequence. Found load-bearing while designing Hire's
required-pay formula ([3.16], user-supplied manual quote): "a Good King
generally cannot hire a Pagan Hero" only reproduces as ">2 ordinal
positions apart" using these REAL ordinals (Good=1, Pagan=4, distance
3) -- `tuple(Alignment)`'s declaration order gives a different (and, in
general, wrong) distance for most pairs. `turn/intelligence_estimate.py`
was discovered, while researching this, to have relied on
`tuple(Alignment)` for its own `Align_Est` ordinal-distance formula
since Phase 136 -- a genuine bug, fixed the same phase this mapping was
added, using this table instead.
"""

from __future__ import annotations

from enum import Enum


class Alignment(Enum):
    DIVINE = "Divine"
    GOOD = "Good"
    NEUTRAL = "Neutral"
    EVIL = "Evil"
    ANTI_HOLY = "Anti-Holy"
    PAGAN = "Pagan"
    DRUID = "Druidic"
    UNDEAD = "Undead"
    MECHANICAL = "Mechanical"
    SPECIAL = "Special"


# CTBOTH.PAS `outlook = (Heavenly, Good, Druidic, Worldly, Animal, Evil,
# Hellish, Undead, Mechanical, Special)` -- the real Pascal ordinal
# sequence, distinct from this module's own declaration order above.
ALIGNMENT_ORDINAL: dict[Alignment, int] = {
    Alignment.DIVINE: 0,
    Alignment.GOOD: 1,
    Alignment.DRUID: 2,
    Alignment.NEUTRAL: 3,
    Alignment.PAGAN: 4,
    Alignment.EVIL: 5,
    Alignment.ANTI_HOLY: 6,
    Alignment.UNDEAD: 7,
    Alignment.MECHANICAL: 8,
    Alignment.SPECIAL: 9,
}

ALIGNMENT_BY_ORDINAL: tuple[Alignment, ...] = tuple(
    sorted(ALIGNMENT_ORDINAL, key=lambda member: ALIGNMENT_ORDINAL[member])
)

# CTBOTH.PAS `outab: outstrs = ('Divin','Good','Druid','Neutr','Pagan',
# 'Evil','Hell','Undea','Mech','Spec')` (~line 1671-1672) -- the real
# CHARACTERS-table column abbreviation (width 6, `outab[lalign[ldr]]:6`,
# `REPORTS.PAS` ~line 858), distinct from `outname`'s own full display
# word. Positionally verbatim against the real Pascal ordinal sequence
# (`ALIGNMENT_ORDINAL` above), not this module's own declaration order --
# cross-checked entry-by-entry (e.g. ordinal 7 = 'Undea' = UNDEAD, matching
# `outname`'s own ordinal-7 = 'Undead').
ALIGNMENT_ABBREVIATION: dict[Alignment, str] = {
    Alignment.DIVINE: "Divin",
    Alignment.GOOD: "Good",
    Alignment.DRUID: "Druid",
    Alignment.NEUTRAL: "Neutr",
    Alignment.PAGAN: "Pagan",
    Alignment.EVIL: "Evil",
    Alignment.ANTI_HOLY: "Hell",
    Alignment.UNDEAD: "Undea",
    Alignment.MECHANICAL: "Mech",
    Alignment.SPECIAL: "Spec",
}
