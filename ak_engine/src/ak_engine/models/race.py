"""Race enum, transcribed from ``HostAK/TP/CTBOTH.PAS`` (``race`` type, line 573).

``HUMANOID_RACES`` matches the rulebook's explicit definition (``RULES.AK``
[3.4]): "humanoids being men, elves, orcs and dwarves."

**`RACE_NAME`/`RACE_ADJECTIVE` (Phase 87)**, found continuing to mine
`CTBOTH.PAS` the way Phases 79-84/86 found their own real data:
`CTBOTH.PAS`'s own `rname`/`radj` tables (`rstrs` type, 23 entries each
-- 15 real + 8 unused `er3`-`er10` extension slots, the same convention
already used for every other enum's own unused tail). `radj[_race]` is
confirmed to be `PROSE.TXT`'s own documented `"$R: Race name ('Elven',
'Dwarven' etc.)"` marker via `RUMORS.PAS`'s own `WW(radj[_race])` --
both example strings verbatim entries here. `rname[...]` is directly
referenced too (e.g. `Concat('(a ', rname[lrace[ldr]], ' ', ...)'` --
"a Human warrior"), matching `PROSE.TXT`'s separate `"^R (): Race
('Humans', 'Dragons', etc.)"` marker (this project models the singular
noun form `rname` actually stores, not a pluralized string). Both
tables line up exactly, positionally, with `Race`'s own 15 ordinals.

**`RACE_FANATICISM_TITLE` (Phase 100)**, found continuing to mine the
`PROSE/` `.X2` template files, the same way Phases 96-99 found their own
real data: `HostAK/TP/PROSE/RACE.X2` (header `"13 1"`), confirmed real
via `SAY.PAS`'s own `Check_BFace` procedure, the `_ARFan` branch:

```pascal
_ARFan: BEGIN
  trint:= Rint; tattl:= _attl; _attl:= prevchar[office(trint+ord(Humanking))];
  FD('c:\\tp\\prose\\race.x2',S_Batt,1001+trint); Say('they',S_Batt);
  _attl:= tattl;
 END;
```

`office(trint+ord(Humanking))` looks up that race's own "king" title in
`models/office.py Office` (`Humanking`, `Elvenking`, `Dwarvenking`,
`Orclord`, `Dragonlord`, `Eagleking`, `Whaleking`, ...,
`Mermanking`, `Entking`, `Trollking`, `Wereking`, all declared
consecutively) and `prevchar[...]` finds the character currently holding
it -- `trint` positionally matches `Race`'s own first 13 ordinals
(`HUMAN`-`SAURIAN`), confirmed both by the exact count and by each
entry's own content (e.g. `DWARVEN`: "King Under the Mountain",
`MERMISH`: "Holy King of Atlantis", `ENTISH`: "Tsar of the Trees").
`NO_RACE` (7) and `SAURIAN` (12) are blank -- no "king" `Office` exists
for either.

This is a **race-based** fanaticism narrative, distinct from (and not
wired to) the already-implemented **alignment-based** roll
(`turn/strength.py roll_fanaticism(kingdom.alignment, rng)`, Phase 35) --
`Check_BFace`'s own surrounding `CASE` shows they're two of (at least)
four sibling variants (`_AGFan`/`_AEFan` alignment-based via `Good_Fan`/
`Evil_Fan`, `_ATFan` title-based via `GANG.X2`, `_ARFan` race-based via
`RACE.X2`), selected by a story-code value this project doesn't decode.
Only the raw template data is transcribed here, matching how every other
`.X2`-sourced phase started; wiring `_ARFan`'s own selection condition
and `GANG.X2`'s sibling table are left to a real follow-up phase.

**`Race.DROW`/`LIZARDMAN`/`GOBLIN` (Phase 383)**, found continuing to
mine the AKGEN reverse-engineering material's own `tables.races` catalog
(a disassembly-derived table distinct from the `CTBOTH.PAS` source read
directly for Phases 87/100 above): 3 more real, named `rstrs` entries at
ordinals 15-17, previously undocumented here and left as unused `er3`-
`er5` extension slots (the module's own count of "15 real + 8 unused"
is now "18 real + 5 unused", `er6`-`er10`). The catalog's own
`adjectives_ds_offset` field is an exact, 15-for-15 match to this
module's own pre-existing `RACE_ADJECTIVE` for ordinals 0-14 -- the
same cross-check discipline as every prior phase here -- so its values
for the 3 new ordinals are trusted and added to `RACE_ADJECTIVE`
directly. The catalog's sibling `plural_names_ds_offset` field is
**not** the same table `RACE_NAME` already models (`rname`, the
singular noun `CTBOTH.PAS` itself stores): comparing the catalog's own
"plural" values against `RACE_NAME`'s existing 15 singular entries
shows most pairs differ only by regular English pluralization (`Elf`/
`Elves`, `Whale`/`Whales`), but two don't (`WEREFOLK`: `Were`/
`Werefolk`; `ROHAN`: `Rohan`/`Riders` -- a wholly different word), proving
the plural table is independently sourced, not a computed function of
`rname`. Since no confirmed singular form exists for the 3 new
ordinals in the available material, `RACE_NAME` is deliberately left
without entries for them (an honest gap, not a guess); the plural
table is instead transcribed whole, for all 18 real ordinals, as the
new `RACE_PLURAL_NAME`. `RACE_FANATICISM_TITLE` stays untouched --
`RACE.X2`'s own declared range is still only ordinals 0-12, so 15-17
join 13/14 as already-excluded, out-of-range members.
"""

from __future__ import annotations

from enum import Enum


class Race(Enum):
    HUMAN = 0
    ELVEN = 1
    DWARVEN = 2
    ORCISH = 3
    DRAGONS = 4
    EAGLES = 5
    WHALES = 6
    NO_RACE = 7
    MERMISH = 8
    ENTISH = 9
    TROLLISH = 10
    WEREFOLK = 11
    SAURIAN = 12
    VAMPISH = 13
    ROHAN = 14
    DROW = 15
    LIZARDMAN = 16
    GOBLIN = 17


HUMANOID_RACES = frozenset({Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH})

# CTBOTH.PAS `rname`, verbatim, positional with `Race`'s own ordinals above.
RACE_NAME: dict[Race, str] = {
    Race.HUMAN: "Human",
    Race.ELVEN: "Elf",
    Race.DWARVEN: "Dwarf",
    Race.ORCISH: "Orc",
    Race.DRAGONS: "Dragon",
    Race.EAGLES: "Eagle",
    Race.WHALES: "Whale",
    Race.NO_RACE: "no race",
    Race.MERMISH: "Merman",
    Race.ENTISH: "Ent",
    Race.TROLLISH: "Troll",
    Race.WEREFOLK: "Were",
    Race.SAURIAN: "Dinosaur",
    Race.VAMPISH: "Vampire",
    Race.ROHAN: "Rohan",
}

# CTBOTH.PAS `radj`, verbatim, positional with `Race`'s own ordinals above --
# confirmed to be the real "$R: Race name" prose marker (see module docstring).
RACE_ADJECTIVE: dict[Race, str] = {
    Race.HUMAN: "Human",
    Race.ELVEN: "Elven",
    Race.DWARVEN: "Dwarven",
    Race.ORCISH: "Orcish",
    Race.DRAGONS: "serpentine",
    Race.EAGLES: "feather-brained",
    Race.WHALES: "aquatic",
    Race.NO_RACE: "no race",
    Race.MERMISH: "Mermanic",
    Race.ENTISH: "forest-folk",
    Race.TROLLISH: "Trollish",
    Race.WEREFOLK: "shape-changing",
    Race.SAURIAN: "Saurian",
    Race.VAMPISH: "Vampiric",
    Race.ROHAN: "Rohan",
    Race.DROW: "Drow",
    Race.LIZARDMAN: "Lizardman",
    Race.GOBLIN: "Goblin",
}

# AKGEN reverse-engineering material's own `tables.races` catalog, the
# plural-name field sourced separately from `RACE_NAME`'s own singular
# `rname` (see module docstring's Phase 383 addendum -- the two are not
# interchangeable). Covers all 18 real ordinals; `NO_RACE`'s own entry
# is "no races", matching `RACE_NAME`'s own "no race" convention.
RACE_PLURAL_NAME: dict[Race, str] = {
    Race.HUMAN: "Humans",
    Race.ELVEN: "Elves",
    Race.DWARVEN: "Dwarves",
    Race.ORCISH: "Orcs",
    Race.DRAGONS: "Dragons",
    Race.EAGLES: "Eagles",
    Race.WHALES: "Whales",
    Race.NO_RACE: "no races",
    Race.MERMISH: "Mermen",
    Race.ENTISH: "Ents",
    Race.TROLLISH: "Trolls",
    Race.WEREFOLK: "Werefolk",
    Race.SAURIAN: "Dinosaurs",
    Race.VAMPISH: "Vampires",
    Race.ROHAN: "Riders",
    Race.DROW: "Drow Elves",
    Race.LIZARDMAN: "Lizardmen",
    Race.GOBLIN: "Goblins",
}

# HostAK/TP/PROSE/RACE.X2, verbatim, positional with `Race`'s own first
# 13 ordinals (HUMAN-SAURIAN) -- see module docstring's Phase 100
# addendum. `NO_RACE`/`SAURIAN` are the empty string (no "king" `Office`
# exists for either), not a missing value. `VAMPISH`/`ROHAN` have no
# entry at all -- outside the file's own declared 13-choice range.
# Raw, unrendered prose template, each meant to be appended directly
# after an army-name clause (leading space is part of the real text).
RACE_FANATICISM_TITLE: dict[Race, str] = {
    Race.HUMAN: (
        " were inspired/Rexhorted to fanaticism/Ra_fanatical_elan by <, "
        "their glorious/Rexalted Savior of Humankind."
    ),
    Race.ELVEN: (
        " were inspired/Rencouraged to {berserk/Rselfless }fanatiscm by "
        "<, their revered/Rheroic First Elder of Elvenkind."
    ),
    Race.DWARVEN: (
        " were impelled/Rurged to fanaticism/Rfanatical_determination by "
        "<, their esteemed/Rvalorous King Under the Mountain."
    ),
    Race.ORCISH: (
        " were whipped/Rprodded to a state of fanaticism/Rfanatical_rage "
        "by <, their High/Rfeared Khan of the Orcish Hordes."
    ),
    Race.DRAGONS: (
        " were excited_to/Rfired_into a state of "
        "fanaticism/Rfanatical_destructiveness by <, their "
        "mighty/Rtrusted Dragon Lord."
    ),
    Race.EAGLES: (
        " were lifted/Rencouraged to fanaticism/Rfanatical_anger by <, "
        "their honored/Rglorious Ace of Eagles."
    ),
    Race.WHALES: (
        " were encouraged/Ruplifted to a state of "
        "fanaticism/Rfanatical_ire by <, their glorious/Rgallant Whale "
        "League Commissioner."
    ),
    Race.NO_RACE: "",
    Race.MERMISH: (
        " were impelled/Rexcited to fanaticism/Ra_fanatical_charge by <, "
        "their revered/RHoly King of Atlantis."
    ),
    Race.ENTISH: (
        " were prodded/Rinspired to fanaticism/Ra_fanatical_fury by <, "
        "their beloved/Rrespected Tsar of the Trees."
    ),
    Race.TROLLISH: (
        " were admonished/Rtormented to fanaticism/Ra_towering_fanatical_rage "
        "by <, their dreaded/Rstern High Mucky-Muck of Trolls."
    ),
    Race.WEREFOLK: (
        " were exhorted/Rinspired to a howling/Rlunatic "
        "fanaticism/Rfanatical_charge by <, their exalted/Rfavorite Lord "
        "of Lycanthropes."
    ),
    Race.SAURIAN: "",
}
