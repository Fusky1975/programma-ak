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

**Phase 98 addendum**: `HostAK/TP/PROSE/FPDESC.X2` and `SPDESC.X2`,
confirmed real and confirmed *together* via `SAY.PAS`'s own `_EDesc`
procedure:

```pascal
_EDesc: BEGIN
  IF needy THEN Say('The $\\ needs more information to perform its power.',S_PCom);
  FD('c:\\tp\\prose\\fpdesc.x2',S_PCom,1001+ord(fpower));
  IF ((fpower = AnsPrayer) or (fpower = CastSpell)) THEN
    FD('c:\\tp\\prose\\spdesc.x2',S_PCom,1001+setval);
  needy:= false;
 END;
```

- `POWER_DESCRIPTION` (`FPDESC.X2`, header `"25 1"`) is shown *every*
  time -- one full sentence per `Power` ordinal (1:1, confirmed by
  `ord(fpower)` indexing it directly), describing exactly what that
  power does in plain English.
- `CAST_SPELL_FEATURE_DESCRIPTION` (`SPDESC.X2`, also header `"25 1"`) is
  shown *additionally*, only when `fpower` is `CastSpell` or `AnsPrayer`
  -- 1:1 with `models/enums.py Spell`'s own first 25 ordinals (indexed by
  `setval`, confirmed the spell ordinal by every entry's own text: e.g.
  index 0 reads `"  -(Illegal: Resurrection)"`, matching
  `Spell.RESURRECTION`). 11 of the 25 spells are marked
  `"(Illegal: <name>)"` -- not a real description, but the game's own
  confirmation that this spell can never actually be granted as a Search
  Feature's Cast-Spell power; stored verbatim rather than filtered out,
  since the illegal markers are themselves real, sourced content.
- `MCOND.X2`'s own confirmed indexing (`FD('...mcond.x2',S_PCom,
  1001+ord(fpowcon))`, right after this same block in `SAY.PAS`) directly
  matches Phase 97's own `MCOND_TEMPLATE` -- independent confirmation
  that the Phase 97 positional mapping was correct.
- The `CastSpell` entry's own raw byte is `\x01` (Turbo Pascal's `chr(1)`
  compact-encoding for `^A`, "a"/"an" depending on the next word) --
  transcribed as `^A` per `report/turn_report.py`'s own established
  source-notation convention for this exact byte.

**Phase 790 addendum**: the `_EDesc` `needy` sentence quoted above
(`"The $\\ needs more information to perform its power."`) is now
wired -- `POWER_DESCRIPTION`'s own SA-argument-power half (the 5
Oracles/Recharge/GrantWish/Gamble) fires alongside it whenever a Scout
attempt reaches `turn/feature_power_execution.py resolve_feature_
power_attempt()`'s own `reason == "no SA argument given"` refusal (see
`report/turn_report.py describe_feature_power_needs_more_info()`).
`CAST_SPELL_FEATURE_DESCRIPTION` (`SPDESC.X2`) stays exactly as unwired
as before -- `CAST_SPELL`/`ANS_PRAYER` are resolved via a completely
different, non-SA-argument branch (`TERRAIN_SPELL_POWERS`, auto-derived
from `event.spell_parameter`) that can never reach this specific
refusal, so its own conditional `SPDESC.X2` half is structurally
unreachable through this trigger.

**Phase 101 addendum -- `POWMSG.X2` investigated, found not to map
cleanly, and abandoned; `SAY.PAS`'s own `_NoMeet` block used instead.**
`HostAK/TP/PROSE/POWMSG.X2` (header `"50 1"`) was the original target for
this phase, since `SAY.PAS`'s own `_PowMsg` dispatches it
(`FD('...powmsg.x2',S_PCom,1000+trint)`, `trint:= Rint`). Investigation
found the file does **not** correspond to any single enum this project
models: the header declares 50 choices, but only ~42 lines carry real
distinct text (one blank line, one `"REM: no lists in files like this!"`
comment line, and no consistent 1:1 fit against `Power`'s 25 members or
anything else) -- individual entries read as unrelated situational
messages (Oracle-of-Wealth errors, Gamble win/lose text, GrantWish
success, NewSex flavor, RECHARGE errors, ...), evidently each hardcoded
to its own specific `trint` value by call sites that live only in the
missing main program. Modeling this as a formal `dict` would mean
inventing an index scheme this project has no source for -- explicitly
not attempted, per this project's standing sourcing discipline, rather
than guessed.

**Phase 782 addendum -- mostly closed, not by finding the missing main-
program call sites (still don't exist), but because the user placed the
actual raw `POWMSG.X2`/`PCOND.X2` files on the Desktop and every one of
POWMSG.X2's 42 real message lines already has a byte-for-byte
correspondence to an already-wired `Power`/`PowerCondition` outcome from
Phases 616-623/688 -- the trigger *mapping* was solved twice over
already by `Special Features.md`'s own section 9.4 table; what Phase 782
adds is the verbatim primary text itself, closing the 4 generic
`PowerCondition` refusal messages that were never rendered at all, a
real DRAIN_SKILL-refusal mis-scoping bug (checked only inside `Power.
GRANT_WISH`'s own branch, not power-agnostically), a confirmed one-word
primary-source correction (`DN_SKILL_AT_LIMIT`: "aptitude," not
"skill"), and `ORAC_POWER`'s own real "has armies" text (superseding an
earlier project-original sentence). Three residual pieces are still
genuinely open, not guessed: POWMSG.X2 line 19 (plausibly a CAST_SPELL/
ANS_PRAYER-grants-Illusory-Terrain-specific success variant, unconfirmed,
plus a brand-new `` ` `` marker this project's prose engine has never
needed), line 31 (GRANT_WISH's own tutorial text, likely belonging to
this project's still-unbuilt "fdisc tier 2" Feature-discovery narration),
and line 43 (an unrelated Fulfill-flavored sentence with an unexplained
`0x04` control byte). `PCOND.X2`'s own remaining 5 lines describe a
Feature's power "terms" *before* an attempt -- a real, separate
narration opportunity this project has no established report-layer
placement for yet, left for a future phase.

What *is* real and cleanly citable: the same `_EDesc`/`_MCond` block's
neighboring `_NoMeet` procedure (~line 1266-1275), an inline (not
`.X2`-sourced) `CASE fpowcon OF` dispatch with literal `Say(...)`
messages for exactly 3 of `PowerCondition`'s 6 non-`PC_NONE` members
(`SameAlign`, `NeedKing`, `GTurn`) -- `PayUp`/`DrainSkill`/
`DrainCourage` have no case at all, correctly excluded rather than
guessed at. `POWER_CONDITION_REJECTION_MESSAGE` transcribes these three;
`POWER_CONDITION_REJECTION_INTRO` transcribes the one generic line said
first regardless of which condition failed
(`"You don't meet the conditions for using the $\\."`).
"""

from __future__ import annotations

from enum import Enum

from ak_engine.models.enums import Spell


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

# HostAK/TP/PROSE/FPDESC.X2 (header "25 1"), verbatim, positional with
# `Power`'s own ordinals above -- shown every time a magic feature's
# power is described (see module docstring's Phase 98 addendum).
POWER_DESCRIPTION: dict[Power, str] = {
    Power.PNONE: "This feature has no power.",
    Power.NEW_SEX: "The $\\ changes your sex from male to female (or vice versa.)",
    Power.NEW_TEMP: "The $\\ changes your temper to $T, if you are not already $T.",
    Power.NEW_RACE: (
        "The $\\ changes your race to $R, if you are not already of this "
        "fine and superior race."
    ),
    Power.UP_SKILL: (
        "The $\\ will try to increase your skill in ^ by 1 point per visit, "
        "up to a maximum of 4.If you have low aptitude, your chance of "
        "success is halved for every aptitude-level you are deficient in ^."
    ),
    Power.UP_APT: (
        "The $\\ increases your aptitude in ^ by 1 point per visit, up to "
        "a maximum of 4."
    ),
    Power.DN_SKILL: "The $\\ decreases your skill in ^ by 1 point, if it isn't zero already.",
    Power.DN_APT: "The $\\ decreases your aptitude in ^ by 1 point, if it isn't zero already.",
    Power.DAMP_COLLEGE: (
        "The $\\ emits an anti-magic field which prevents the casting of any ^ spell."
    ),
    Power.DAMP_MAGIC: (
        "The $\\ emits an anti-magic field which halves the chance of "
        "casting any magic spell."
    ),
    Power.WARP_SPACE: (
        "The $\\ generates a space-warp field which causes 75% of all "
        "arrows to miss their mark, as well as 50% of all swings in Melee."
    ),
    Power.CAST_SPELL: "The $\\ gives you the magic power to cast ^A ~ spell.",
    Power.ANS_PRAYER: (
        "The $\\ will cast a ~ spell for a character who kneels before "
        "the $\\ in prayer."
    ),
    Power.MAP_FEAT: (
        "The $\\ will tell you of one previously unknown feature in your "
        "Kingdom each time you scout it (but it will not give you any "
        "points for the Chancellor office)."
    ),
    Power.MAP_PROV: (
        "The $\\ helps you map unknown lands.Each time you scout it, it "
        "will tell you of some unknown lands, it's inhabitants, location and ruler."
    ),
    Power.SAGE_DISC: (
        "The $\\ knows every Sage Discovery!Each time it is scouted, it "
        "will reveal one discovery which will benefit your Kingdom (but "
        "it will not give you any points for the Chancellor office)."
        "Usually, a lesser discovery will be revealed to you."
    ),
    Power.ORAC_ALIGN: (
        "The $\\ is an Oracle of Alignment.When you scout it, just SA-y "
        'the character number (not the name; e.g., "SA Tell me about '
        'character 1.") and the character\'s alignment will become known to you.'
    ),
    Power.ORAC_POWER: (
        "The $\\ is an Oracle of Power.When you scout it, just SA-y the "
        'character number (not the name; e.g., "SA Tell what leader 1 '
        'has.") and the Oracle will tell you the number and type of all '
        "armies led by that character (but not the location)."
    ),
    Power.ORAC_OFFICE: (
        "The $\\ is an Oracle of Office.When you scout it, just SA-y the "
        'Office number (not the name; e.g., "SA Tell me who holds office '
        '1.") and the leader for that office will be pronounced (0-Emp, '
        "1-Chanc, 2-Treas, 3-Marsh, 4-Adm, 5-Def, 6-Priest, 7-Mage)."
    ),
    Power.ORAC_GOLD: (
        "The $\\ is an Oracle of Wealth.When you scout it, just SA-y the "
        'Kingdom number (not the King\'s name; e.g., "SA Tell me the '
        'treasury of King 1.") and the Oracle will tell you the wealth '
        "of the Kingdom's treasury."
    ),
    Power.ORAC_TREAS: (
        "The $\\ is an Oracle of Treasure.Just SA-y a feature number (not "
        'the feature name; e.g., "SA Tell me what\'s in feature 1.") and '
        "the Oracle will tell you what treasure is hidden there."
    ),
    Power.RECHARGE: (
        "The $\\ will recharge any magic item that can be used to cast a "
        "spell.When you scout it, one charge will be restored to any "
        'magic item in your position when you SA-y the item number (not '
        'the item name; e.g., "SA Recharge item 1.").'
    ),
    Power.GRANT_WISH: (
        "The $\\ will grant a minor Wish.When you scout it, you may "
        "increase any ability by one, if your unmodified skill level is "
        "less than your aptitude (maximum 4).SA-y the ability number "
        "(0=Tactics, 1=March etc., the order is shown in your Character List)."
    ),
    Power.GAMBLE: (
        "The $\\ will gamble with you for any amount of gold you have in "
        "your Kingdom's treasury.When you scout it, SA-y how much you "
        "wish to gamble, and whoever rolls the highest number with two "
        "dice takes the gold.In case of a tie, the $\\ wins!"
    ),
    Power.CHANCE: (
        "The effects of the $\\ are both good and bad!Chance will "
        "determine the fate of <, good or ill.Care to take a chance?"
    ),
}

# HostAK/TP/PROSE/SPDESC.X2 (header "25 1"), verbatim, positional with
# `Spell`'s own first 25 ordinals -- shown additionally, alongside
# `POWER_DESCRIPTION`, only when a magic feature's `Power` is
# `CAST_SPELL` or `ANS_PRAYER` (see module docstring's Phase 98
# addendum). 11 of the 25 entries read `"(Illegal: <name>)"` -- the
# game's own confirmation that spell can never actually be granted this
# way, kept verbatim rather than filtered out.
CAST_SPELL_FEATURE_DESCRIPTION: dict[Spell, str] = {
    Spell.RESURRECTION: "  -(Illegal: Resurrection)",
    Spell.PART_SEA: (
        'The "Part Sea" will take effect on this province (for a land '
        "province, it can be used to cancel a Flood spell.)"
    ),
    Spell.BLESS: "The Bless spell will take effect on this province.",
    Spell.HOLY_SYMBOL: "The spell takes effect as if a level-2 White Magician had cast it.",
    Spell.SKELETAL_ARMY: "Skeletal armies will be raised for <2 if they exist in this province.",
    Spell.KILL_ENEMY: (
        "Name the character number (not the character name), and he "
        "will be struck down if he is in this province."
    ),
    Spell.PLAGUE: (
        "The Plague spell will take effect on this province as if a "
        "level-2 Necromancer had cast it."
    ),
    Spell.HAND_OF_DEATH: "  (Illegal: Hand-of-Death.)",
    Spell.FLOOD: "The Flood spell will take effect on this province.",
    Spell.TORNADO: (
        "The Tornado spell will take effect on this province as if a "
        "level-2 Elemental Mage had cast it."
    ),
    Spell.EARTHQUAKE: "The Earthquake spell will take effect on this province.",
    Spell.FIREBALL: "  (Illegal: Fireball)",
    Spell.CHARM: "  (Illegal: Charm)",
    Spell.ORATORY: "The Oratory spell will take effect on the character Searching the feature.",
    Spell.CLAIRVOYANCE: (
        "Name the character number (not the character name), and "
        "everything he does for the rest of the turn will be known to you."
    ),
    Spell.PSYCHIC_BLAST: "  (Illegal: Psychic_Blast)",
    Spell.ILLUS_TERRAIN: (
        "The terrain of this province will appear as the terrain number "
        "you SA-y (do not the terrain name):  0-Plains, 1-Desert, "
        "2-Jungle, 3-Forest, 4-Mountains, 5-Sea."
    ),
    Spell.ILLUS_ARMIES: (
        "Illusory armies will be formed for the Searching character "
        "(the spell takes effect at level 2)."
    ),
    Spell.HIDE_FEATURE: "This feature will become magically hidden.",
    Spell.INVISIBILITY: "  (Illegal: Invisibility)",
    Spell.SPIRITWRACK: "  (Illegal: Spiritwrack)",
    Spell.CONTROL_UNDEAD: "  (Illegal: Control_Undead)",
    Spell.ICE_SUSPEND: "  (Illegal: Ice_Suspend)",
    Spell.TELEK_STORM: "  (Illegal: Telek_Storm)",
    Spell.MIRROR_IMAGE: "  (Illegal: Mirror_Image)",
}

# SAY.PAS's own literal Say(...) message, said unconditionally before the
# per-condition CASE below (see module docstring's Phase 101 addendum).
POWER_CONDITION_REJECTION_INTRO = "You don't meet the conditions for using the $\\."

# SAY.PAS `_NoMeet`'s own `CASE fpowcon OF` (~line 1270-1274), verbatim --
# only 3 of `PowerCondition`'s 6 non-`PC_NONE` members have a case at all;
# `PAY_UP`/`DRAIN_SKILL`/`DRAIN_COURAGE` are correctly excluded rather
# than guessed at.
POWER_CONDITION_REJECTION_MESSAGE: dict[PowerCondition, str] = {
    PowerCondition.SAME_ALIGN: "You are not $o, so begone/Rgo_away!",
    PowerCondition.NEED_KING: (
        "You're just  lowly/Rirrelevant hero/Rlackey, so get out of "
        "here/Rthis_&!"
    ),
    PowerCondition.G_TURN: "The power has already been used this turn, so go away!",
}
