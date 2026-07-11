"""Monster/character attack-weapon vocabulary.

``HostAK/TP/CTBOTH.PAS``'s `weapon` enum (~line 559, 29 members) plus
`RUMORS.PAS`'s own `wname` (weapon noun) and `whit` (attack verb)
tables, found continuing to mine `CTBOTH.PAS` the way Phases 79-82
found their own real data.

**Confirmed to be `PROSE.TXT`'s own documented `"$S"` marker**: "$S:
Attack method ('Slashed', 'Fired', 'Thrust', etc.)" -- `RUMORS.PAS`'s
own `$`-prefixed marker dispatch (the block `report/prose.py`'s own
docstring already partially quotes) resolves `'S'` by picking between
`whit[Bow]`/`whit[Sword]` (a *character* attacker, hardcoded to one of
these two) or `whit[mtrweap[_mtype]]`/`whit[mtweap1[_mtype]]` (a
*monster* attacker, looked up by its own weapon) depending on whether
the previous action was Fire Arrow (`_LFarr`) -- confirming `Weapon.BOW`
and `Weapon.SWORD` specifically as real, literally-referenced ordinals,
not just plausible-looking declared constants.

**A confirmed structural gap, not an oversight**: the actual
monster-to-weapon assignment tables `RUMORS.PAS` reads --
``mtrweap[_mtype]`` (ranged weapon) and ``mtweap1[_mtype]`` (melee
weapon), both presumably `array[monster] of weapon`, matching the
`mweaps` *type* `CTBOTH.PAS` itself declares at ~line 565 -- are used
but **never declared anywhere in this project's available source**
(checked `CTBOTH.PAS`, `RUMORS.PAS`, `REPORTS.PAS`, `DEF2.PAS`,
`SAY.PAS`). This is the same category of gap as the missing main
program: the actual per-species weapon assignment doesn't survive, so
this module cannot connect any `models/monster.py Monster` to a
`Weapon` -- only the weapon vocabulary itself (name + attack verb) is
modeled here.

**`whit`'s own strings are themselves prose templates, not plain
text**: several contain a live `/R` choice marker (e.g.
``"slashed/Rclawed at"``, rulebook `PROSE.TXT` [3.2]/`report/prose.py`
Phase 58) -- confirming they're meant to be run through
`report/prose.py render()`, not printed literally. Not resolved here;
this module only stores the raw template strings, matching how
`models/treasure.py TREASURE_LABEL` (Phase 77) also stores raw,
unrendered source text.
"""

from __future__ import annotations

from enum import Enum


class Weapon(Enum):
    TALONS = 0
    FANGS = 1
    CLAWS = 2
    MAW = 3
    JAWS = 4
    FISTS = 5
    SWORD = 6
    DAGGER = 7
    STAFF = 8
    HOOVES = 9
    MED_TEETH = 10
    CHIM_HEADS = 11
    CLUB = 12
    AXE = 13
    U_TOUCH = 14
    TENTACLES = 15
    BEAK = 16
    BOULDER = 17
    BOW = 18
    FLAME_BREATH = 19
    SPIT_ACID = 20
    POIS_BREATH = 21
    B_SCREAM = 22
    ENDO_POD = 23
    MANDIBLE = 24
    STINGER = 25
    LIMB = 26
    GAZE = 27
    NO_WEAP = 28


# RUMORS.PAS `wname`, verbatim, positional with the `Weapon` ordinals above.
WEAPON_NAME: dict[Weapon, str] = {
    Weapon.TALONS: "talons",
    Weapon.FANGS: "fangs",
    Weapon.CLAWS: "claws",
    Weapon.MAW: "maw",
    Weapon.JAWS: "jaws",
    Weapon.FISTS: "fists",
    Weapon.SWORD: "sword",
    Weapon.DAGGER: "dagger",
    Weapon.STAFF: "staff",
    Weapon.HOOVES: "hooves",
    Weapon.MED_TEETH: "teeth",
    Weapon.CHIM_HEADS: "jaws",
    Weapon.CLUB: "club",
    Weapon.AXE: "axe",
    Weapon.U_TOUCH: "deathly touch",
    Weapon.TENTACLES: "tentacles",
    Weapon.BEAK: "beak",
    Weapon.BOULDER: "boulder",
    Weapon.BOW: "arrow",
    Weapon.FLAME_BREATH: "flame breath",
    Weapon.SPIT_ACID: "acid stream",
    Weapon.POIS_BREATH: "poisonous breath",
    Weapon.B_SCREAM: "horrid scream",
    Weapon.ENDO_POD: "plasmic pseudopod",
    Weapon.MANDIBLE: "mandible",
    Weapon.STINGER: "stinger",
    Weapon.LIMB: "limb",
    Weapon.GAZE: "stony gaze",
    Weapon.NO_WEAP: "no weapon",
}

# RUMORS.PAS `whit` (attack verb), verbatim, positional with the `Weapon`
# ordinals above. These are raw, unrendered prose templates -- several
# contain a live "/R" choice marker (see module docstring).
WEAPON_HIT_VERB: dict[Weapon, str] = {
    Weapon.TALONS: "slashed/Rclawed at",
    Weapon.FANGS: "lunged/Rstruck at",
    Weapon.CLAWS: "slashed/Rswang at",
    Weapon.MAW: "lunged_at/Rattacked",
    Weapon.JAWS: "lunged/Rsnapped at",
    Weapon.FISTS: "punched/Rswung at",
    Weapon.SWORD: "swang/Rthrust at",
    Weapon.DAGGER: "thrust/Rlunged at",
    Weapon.STAFF: "swang/Rthrust at",
    Weapon.HOOVES: "kicked/Rthrust at",
    Weapon.MED_TEETH: "bit/Rsnapped at",
    Weapon.CHIM_HEADS: "snapped/Rlunged at",
    Weapon.CLUB: "swang/Rsmashed at",
    Weapon.AXE: "chopped/Rswang at",
    Weapon.U_TOUCH: "groped_for/Rlunged_at",
    Weapon.TENTACLES: "assailed/Rlashed_at",
    Weapon.BEAK: "pecked/Rstruck at",
    Weapon.BOULDER: "threw/Rhurled",
    Weapon.BOW: "fired/Rshot",
    Weapon.FLAME_BREATH: "breathed/Rexhaled",
    Weapon.SPIT_ACID: "spat/Rsprayed",
    Weapon.POIS_BREATH: "breathed/Rexhaled",
    Weapon.B_SCREAM: "voiced/Rsounded",
    Weapon.ENDO_POD: "oozed/Rgroped at",
    Weapon.MANDIBLE: "snapped/Rlunged at",
    Weapon.STINGER: "thrust/Rflipped at",
    Weapon.LIMB: "swang/Rclubbed at",
    Weapon.GAZE: "glared/Rglowered",
    Weapon.NO_WEAP: "swang at",
}
