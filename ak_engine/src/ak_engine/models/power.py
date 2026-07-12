"""The magical effect a "Magic Feature" (``models/magic_feature.py``) can
trigger, and the condition gating whether it does.

``HostAK/TP/CTME.PAS``'s own ``power`` enum (~line 434, 25 members) and
``powco`` enum (~line 543, 7 members), plus ``HostAK/TP/YAK.PAS``'s own
``powname``/``coname`` display-name tables (~line 420-439) -- found
continuing to mine the wider Pascal source the way Phases 91-94 found
their own real data. This resolves the ``power`` enum
``models/magic_feature.py`` (Phase 92) had already found and named in its
own docstring but deliberately left undefined.

**Confirmed real and player-facing** via ``YAK.PAS``'s own ``Set_Event``
procedure -- the actual code that fires a magic feature's effect when a
character visits it -- which writes both display strings straight to the
player's report file: ``WRITE(playfile,powname[fpower])`` and (inside the
nested ``Set_FCon`` condition-check) ``WRITE(playfile,coname[fpowcon])``.

**`POWER_NAME`'s own strings read as compact, abbreviated labels, not full
prose** (`"+"`, `"-"`, `"Cast "`, `"Pray "`, `"Orac/Align"`, all capped at
17 characters) -- most likely a column header or inline tag printed
alongside other computed values (`Set_Event`'s own logic computes things
like a skill delta or gold amount that would need its own number appended
after one of these labels), unlike the full-sentence prose strings this
project's other ``*_NAME`` dicts usually hold. Stored verbatim rather than
expanded into guessed full sentences.

**Confirmed real but deliberately out of scope for this phase**:
`CTME.PAS` also declares `mfpow1`/`mfpowf` (both `array[MagicFeature] of
power` -- a primary and a "false"/decoy power per magic feature, mirroring
`mf1`/`mff`'s own primary/decoy split already noted in
`models/magic_feature.py`) and an entirely separate `comfeat` enum (27
members: `CFNone, Seaweed, Whirlpool, Trees, Cliff, LavaPool, Stalacs,
Mine, Quicksand, Corner, Pit, CPool, Stairs, Table, Gametable, Hammock,
Rug, Fireplace, Piano, Chandelier, CWindow, HiWindow, Passages, Coffin,
Gong, Pillar, Well`) with its own three `array[FeatureType] of comfeat`
tables (`cfs`, `cf1`, `cff`) -- mundane, non-magical decorative/hazard
landmarks inside a `Feature`, parallel in structure to `MagicFeature` but
never magical. Both are real findings for a future phase, not attempted
here -- this phase only closes the specific `power`/`powco` vocabulary
gap `models/magic_feature.py` had already flagged.
"""

from __future__ import annotations

from enum import Enum


class Power(Enum):
    """``CTME.PAS``'s own ``power`` enum, verbatim order."""

    PNONE = 0
    NEW_SEX = 1
    NEW_TEMP = 2
    NEW_RACE = 3
    UP_SKILL = 4
    UP_APT = 5
    DN_SKILL = 6
    DN_APT = 7
    DAMP_COLLEGE = 8
    DAMP_MAGIC = 9
    WARP_SPACE = 10
    CAST_SPELL = 11
    ANS_PRAYER = 12
    MAP_FEAT = 13
    MAP_PROV = 14
    SAGE_DISC = 15
    ORAC_ALIGN = 16
    ORAC_POWER = 17
    ORAC_OFFICE = 18
    ORAC_GOLD = 19
    ORAC_TREAS = 20
    RECHARGE = 21
    GRANT_WISH = 22
    GAMBLE = 23
    CHANCE = 24


# YAK.PAS `powname`, verbatim, positional with `Power`'s own ordinals above.
POWER_NAME: dict[Power, str] = {
    Power.PNONE: "Nothing",
    Power.NEW_SEX: "Change Sex",
    Power.NEW_TEMP: "New Temper",
    Power.NEW_RACE: "New Race",
    Power.UP_SKILL: "+",
    Power.UP_APT: "+",
    Power.DN_SKILL: "-",
    Power.DN_APT: "-",
    Power.DAMP_COLLEGE: "Anti-Magic",
    Power.DAMP_MAGIC: "Anti-",
    Power.WARP_SPACE: "Warp Space",
    Power.CAST_SPELL: "Cast ",
    Power.ANS_PRAYER: "Pray ",
    Power.MAP_FEAT: "Map Feat.",
    Power.MAP_PROV: "Map Prov.",
    Power.SAGE_DISC: "Sage Disc.",
    Power.ORAC_ALIGN: "Orac/Align",
    Power.ORAC_POWER: "Orac/Power",
    Power.ORAC_OFFICE: "Orac/Ofc.",
    Power.ORAC_GOLD: "Orac/Gold",
    Power.ORAC_TREAS: "Orac/Trea.",
    Power.RECHARGE: "Recharge",
    Power.GRANT_WISH: "Wish",
    Power.GAMBLE: "Gamble",
    Power.CHANCE: "Chance",
}


class PowerCondition(Enum):
    """``CTME.PAS``'s own ``powco`` enum, verbatim order -- the condition
    gating whether/how much a ``Power`` effect actually applies (computed
    by ``YAK.PAS``'s own ``Set_FCon`` procedure).
    """

    PC_NONE = 0
    PAY_UP = 1
    SAME_ALIGN = 2
    DRAIN_SKILL = 3
    NEED_KING = 4
    G_TURN = 5
    DRAIN_COURAGE = 6


# YAK.PAS `coname`, verbatim, positional with `PowerCondition`'s own
# ordinals above. `PC_NONE`'s own entry is the empty string (no condition
# text needed when there's no condition), not a missing value.
POWER_CONDITION_NAME: dict[PowerCondition, str] = {
    PowerCondition.PC_NONE: "",
    PowerCondition.PAY_UP: "g",
    PowerCondition.SAME_ALIGN: "=",
    PowerCondition.DRAIN_SKILL: "-Skill",
    PowerCondition.NEED_KING: "King",
    PowerCondition.G_TURN: "1/Turn",
    PowerCondition.DRAIN_COURAGE: "-Cour.",
}
