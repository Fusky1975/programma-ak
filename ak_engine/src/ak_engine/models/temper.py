"""Character temper (personality/disposition) model.

``HostAK/TP/CTBOTH.PAS``'s `temper` enum -- the `{$IFNDEF Noble}` branch
(active for AK; the `{$ELSE}` branch declares a different, 9-value
`temper` for a different, Noble-flagged game sharing this same library
file, not modeled here) -- found continuing to mine `CTBOTH.PAS` for
real, sourced data the same way Phases 79-81 found theirs.

**Confirmed real and actually used**, not just plausible-looking dead
code: `RUMORS.PAS`'s own `$`-prefixed marker dispatch (the same block
this project's `report/prose.py` docstring already partially quotes)
has ``'T': BEGIN  WW(tempername[_temper]); Inc(sp); END;`` -- an exact
match for `PROSE.TXT`'s own documented `"$T: Temper name ('Berserk',
'Cautious', etc.)"` marker, and both of PROSE.TXT's own example strings
are verbatim `TEMPER_NAME` entries here. The same file also prints
alignment and temper together in one character-description sentence
(``Say(Concat(' ', outname[_align], ', ', tempername[_temper], '
nature/Rcharacter'), spytype)``), confirming these two concepts
(`models/alignment.py Alignment`, Phase 80) are meant to describe a
character side by side, not independently.

**Directly relevant to two gaps this project had already flagged as
blocked on "unmodeled temper"**: Hire's own remaining gap (a Hero's
"required pay... depends on unmodeled per-Hero temper/race/alignment
compatibility") and Trail's own remaining gap (the spied-on
intelligence payload -- "Actions, race, temper, alignment, treasures,
armies led" -- isn't assembled, and temper doesn't exist on
`LeaderState` at all). This phase supplies the *enum*, closing the
"we don't even have the vocabulary" half of both gaps -- neither gap's
actual formula/logic is attempted here. **Trail's gap has since
narrowed** (`LeaderState.temper`, Phase 139; `turn/trail_execution.py`
now reports it on a successful spy, Phase 159). **Hire's own formula
turned out to have no surviving source at all** (Phase 161,
`turn/plan_dispatch.py`'s own note) -- confirmed absent, not merely
still unmodeled.

**A ruled-out, closely-related trap found while researching this**: the
same declaration block's `{$ELSE}` (Noble) branch also declares a
`trait` enum (`Virtue, Charisma, Intelligence, Willpower, Dexterity,
Strength, TX1-4`) and its own 9-value `temper` -- neither is modeled
here, since `{$IFNDEF Noble}` (not `{$ELSE}`) is this project's already-
established target branch (see `turn/movement.py`'s own "Normal
(non-Noble) map bounds" comment for the precedent).
"""

from __future__ import annotations

from enum import Enum


class Temper(Enum):
    COWARDLY = 0
    CAUTIOUS = 1
    BRAVE = 2
    BERSERK = 3


# CTBOTH.PAS `tempername`, verbatim, positional with the `Temper` ordinals above.
TEMPER_NAME: dict[Temper, str] = {
    Temper.COWARDLY: "Cowardly",
    Temper.CAUTIOUS: "Cautious",
    Temper.BRAVE: "Brave",
    Temper.BERSERK: "Berserk",
}

# CTBOTH.PAS `tempab: tempstrs = ('Cowrd','Caut','Brave','Bersk')`
# (~line 1670) -- the real CHARACTERS-table column abbreviation (width 6,
# `tempab[ltemper[ldr]]:6`, `REPORTS.PAS` ~line 858), distinct from
# `tempername`'s own full display word. Positionally verbatim against
# `Temper`'s own declared order above (both this module's declaration
# order and the Pascal ordinal order already match, unlike Alignment).
TEMPER_ABBREVIATION: dict[Temper, str] = {
    Temper.COWARDLY: "Cowrd",
    Temper.CAUTIOUS: "Caut",
    Temper.BRAVE: "Brave",
    Temper.BERSERK: "Bersk",
}
