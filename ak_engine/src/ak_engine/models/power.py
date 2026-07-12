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

**Phase 97 addendum**: `HostAK/TP/PROSE/MCOND.X2` and `PCOND.X2` (both
header `"7 1"`), found continuing to mine the `PROSE/` `.X2` template
files directly, the same way Phase 96's `report/turn_report.py
render_magic_feature_discovery()` found `MAGFEAT.X2`. Both map exactly
1:1 to `PowerCondition`'s own 7 members: `MCOND_TEMPLATE` is the
in-character message an NPC/feature "speaks" once the condition is
satisfied; `PCOND_TEMPLATE` is the out-of-character description of what
the condition requires. Both raw, unrendered prose templates -- matching
how `WEAPON_HIT_VERB`/`TREASURE_LABEL`/`MAGIC_FEATURE_NAME` already store
their own raw template text.
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


# HostAK/TP/PROSE/MCOND.X2 (header "7 1"), verbatim, positional with
# `PowerCondition`'s own ordinals above -- found continuing to mine the
# `PROSE/` `.X2` template files directly, the same way Phase 96's
# `report/turn_report.py render_magic_feature_discovery()` found
# `MAGFEAT.X2`. The in-character message an NPC/feature "speaks" once
# the condition is actually satisfied (contrast `PCOND_TEMPLATE` below,
# the out-of-character description of what the condition *requires*).
# Raw, unrendered prose templates -- matching how `WEAPON_HIT_VERB`/
# `TREASURE_LABEL`/`MAGIC_FEATURE_NAME` already store their own raw
# template text rather than a pre-resolved sentence.
MCOND_TEMPLATE: dict[PowerCondition, str] = {
    PowerCondition.PC_NONE: "(No condition here.)",
    PowerCondition.PAY_UP: (
        "< plunked_down/Roffered_up the gold/Rpayment.Spake/RSayeth <, "
        '"I have brought_you/Rdelivered_the # gold, as you_have_asked"/Rwe_agreed", '
        "and the gold immediately/Rmysteriously disappeared/Rvanished."
    ),
    PowerCondition.SAME_ALIGN: (
        "I welcome/Rsalute you, my $o friend.Our_kind/Rthose_of_our_alignment "
        "should_stick_together/Rare_the_noblest_of_beings."
    ),
    PowerCondition.DRAIN_SKILL: (
        'Spake/RSayeth <, "I am_willing/Rhave_decided to give_up/Raccept_the_loss_of '
        'the # skill/Rability levels{ you asked_for/Rrequested}".'
    ),
    PowerCondition.NEED_KING: (
        "Greetings/Rwelcome, my Kingly/RRoyal friend/Rguest.You honor me by "
        "your coming/Rpresence."
    ),
    PowerCondition.G_TURN: (
        "Greetings/RHello, my_friend/Radventurer.You shall/Rwill now "
        "{be the one to }receive/Rbe_blessed_with my favor/Rpower {for }this year."
    ),
    PowerCondition.DRAIN_COURAGE: (
        'Spake/RSayeth <, "I agree/Ram_willing to lose/Rgive_you some of my '
        'courage/Rtemper in exchange_for/Rorder_to_gain your favor"/Rhelp".'
        "{Almost }immediately, < felt less_hot-tempered/Ra_drain_of_courage."
    ),
}

# HostAK/TP/PROSE/PCOND.X2 (header "7 1"), verbatim, positional with
# `PowerCondition`'s own ordinals above. The out-of-character description
# of what the condition requires (e.g. printed once, up front, alongside
# a magic feature's own power description) -- distinct from
# `MCOND_TEMPLATE`'s in-character "it happened" message.
PCOND_TEMPLATE: dict[PowerCondition, str] = {
    PowerCondition.PC_NONE: "(No condition here.)",
    PowerCondition.PAY_UP: (
        "You must pay # gold each time the $\\ is used (to show that you accept "
        "these terms, a character must give two Scout orders when he Searches "
        "this feature.)"
    ),
    PowerCondition.SAME_ALIGN: (
        "A character must be $o to use the $\\ (the Kingdom alignment does not matter.)"
    ),
    PowerCondition.DRAIN_SKILL: (
        "# skill level(s), chosen at random, will be drained from the character "
        "if the $\\ is scouted.You MUST have enough skill levels to meet the "
        "$\\'s demand (to accept these terms, a character must give two Scout "
        "orders when Searching this feature."
    ),
    PowerCondition.NEED_KING: "Only a King may use the power of the $\\.",
    PowerCondition.G_TURN: (
        "After the power of the $\\ is used in a gameturn, it may not be used "
        "again until the next gameturn."
    ),
    PowerCondition.DRAIN_COURAGE: (
        "When you use the $\\, it will drain away one level of courage (Brave "
        "men become Cautious, etc.)A Coward may not use this feature!To accept "
        "these terms, a character must give two Scout orders when Searching "
        "this feature."
    ),
}
