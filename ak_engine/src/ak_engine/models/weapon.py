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

~~**A confirmed structural gap, not an oversight**: the actual
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
modeled here.~~ **Fixed in Phase 94**: `mtrweap`/`mtweap1` are declared
in `CTME.PAS` (~line 60-88), not `CTBOTH.PAS` -- the check above simply
hadn't looked there yet (the same class of miss Phase 91's `Discovery`
and Phase 92's `MagicFeature` also found and fixed, both also declared
in `CTME.PAS`). Both arrays are declared for the *full* Pascal `monster`
type (71 slots: 61 real species + 10 unused `em1`-`em10` extension
slots) -- only the first 61 are transcribed below, matching
`models/monster.py Monster`'s own already-established range.
`MONSTER_RANGED_WEAPON`/`MONSTER_MELEE_WEAPON` below now connect every
`Monster` to a `Weapon`, closing the gap this docstring used to describe.

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

from ak_engine.models.monster import Monster


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

# CTME.PAS `mtrweap` (ranged weapon), verbatim, first 61 entries (the
# array's own trailing 10 slots are the unused `em1`-`em10` extension
# monsters, excluded here to match `Monster`'s own range). Confirmed
# real and used via RUMORS.PAS's own `Say(whit[mtrweap[_mtype]],
# spytype)` and `WW(wname[mtrweap[_mtype]])` -- see module docstring.
# `Weapon.NO_WEAP` here means "this monster has no ranged attack," not a
# missing/unresolved value -- most monsters fall into that case.
MONSTER_RANGED_WEAPON: dict[Monster, Weapon] = {
    Monster.ROC: Weapon.NO_WEAP,
    Monster.GRYPHON: Weapon.NO_WEAP,
    Monster.COUATL: Weapon.NO_WEAP,
    Monster.GI_EAGLE: Weapon.NO_WEAP,
    Monster.SPHINX: Weapon.NO_WEAP,
    Monster.R_DRAGON: Weapon.FLAME_BREATH,
    Monster.B_DRAGON: Weapon.SPIT_ACID,
    Monster.GR_DRAGON: Weapon.POIS_BREATH,
    Monster.S_DRAGON: Weapon.FLAME_BREATH,
    Monster.GO_DRAGON: Weapon.FLAME_BREATH,
    Monster.GI_WORM: Weapon.NO_WEAP,
    Monster.TITAN: Weapon.NO_WEAP,
    Monster.GIANT: Weapon.BOULDER,
    Monster.BIGFOOT: Weapon.NO_WEAP,
    Monster.ARCHER: Weapon.BOW,
    Monster.SWORDSMAN: Weapon.NO_WEAP,
    Monster.WHITE_MAGE: Weapon.NO_WEAP,
    Monster.NEC_MAGE: Weapon.NO_WEAP,
    Monster.ELE_MAGE: Weapon.NO_WEAP,
    Monster.PSY_MAGE: Weapon.NO_WEAP,
    Monster.ILL_MAGE: Weapon.NO_WEAP,
    Monster.WITCH: Weapon.NO_WEAP,
    Monster.DRYAD: Weapon.NO_WEAP,
    Monster.CENTAUR: Weapon.BOW,
    Monster.GENIE: Weapon.NO_WEAP,
    Monster.GOLEM: Weapon.NO_WEAP,
    Monster.GARGOYLE: Weapon.NO_WEAP,
    Monster.BASILISK: Weapon.GAZE,
    Monster.MEDUSA: Weapon.GAZE,
    Monster.BAL_DEMON: Weapon.NO_WEAP,
    Monster.MAR_DEMON: Weapon.NO_WEAP,
    Monster.SUCCUBUS: Weapon.NO_WEAP,
    Monster.RAKSHASHA: Weapon.NO_WEAP,
    Monster.ICE_DEVIL: Weapon.NO_WEAP,
    Monster.BONE_DEVIL: Weapon.NO_WEAP,
    Monster.IMP: Weapon.NO_WEAP,
    Monster.WEREWOLF: Weapon.NO_WEAP,
    Monster.CHIMERA: Weapon.FLAME_BREATH,
    Monster.HYDRA: Weapon.NO_WEAP,
    Monster.BEHOLDER: Weapon.NO_WEAP,
    Monster.TROLL: Weapon.NO_WEAP,
    Monster.MINOTAUR: Weapon.NO_WEAP,
    Monster.GI_WOLVERINE: Weapon.NO_WEAP,
    Monster.TREANT: Weapon.NO_WEAP,
    Monster.GI_AMOEBA: Weapon.NO_WEAP,
    Monster.GI_P_MANTIS: Weapon.NO_WEAP,
    Monster.GI_SCORPION: Weapon.NO_WEAP,
    Monster.GI_WASP: Weapon.NO_WEAP,
    Monster.GI_SPIDER: Weapon.NO_WEAP,
    Monster.GHOST: Weapon.NO_WEAP,
    Monster.VAMPIRE: Weapon.NO_WEAP,
    Monster.MUMMY: Weapon.NO_WEAP,
    Monster.BANSHEE: Weapon.B_SCREAM,
    Monster.LICH: Weapon.NO_WEAP,
    Monster.SPECTRE: Weapon.NO_WEAP,
    Monster.GI_OCTOPUS: Weapon.NO_WEAP,
    Monster.GI_CLAM: Weapon.NO_WEAP,
    Monster.ELASMOSAURUS: Weapon.NO_WEAP,
    Monster.GW_WHALE: Weapon.NO_WEAP,
    Monster.MERMAID: Weapon.NO_WEAP,
    Monster.NOMONSTER: Weapon.NO_WEAP,
}

# CTME.PAS `mtweap1` (melee weapon), verbatim, first 61 entries (same
# extension-slot exclusion as `MONSTER_RANGED_WEAPON` above). Confirmed
# real and used via the same RUMORS.PAS call sites, the `ELSE` branch of
# each: `Say(whit[mtweap1[_mtype]],spytype)` / `WW(wname[mtweap1[_mtype]])`.
MONSTER_MELEE_WEAPON: dict[Monster, Weapon] = {
    Monster.ROC: Weapon.TALONS,
    Monster.GRYPHON: Weapon.TALONS,
    Monster.COUATL: Weapon.FANGS,
    Monster.GI_EAGLE: Weapon.TALONS,
    Monster.SPHINX: Weapon.JAWS,
    Monster.R_DRAGON: Weapon.JAWS,
    Monster.B_DRAGON: Weapon.JAWS,
    Monster.GR_DRAGON: Weapon.JAWS,
    Monster.S_DRAGON: Weapon.JAWS,
    Monster.GO_DRAGON: Weapon.JAWS,
    Monster.GI_WORM: Weapon.MAW,
    Monster.TITAN: Weapon.SWORD,
    Monster.GIANT: Weapon.CLUB,
    Monster.BIGFOOT: Weapon.FISTS,
    Monster.ARCHER: Weapon.SWORD,
    Monster.SWORDSMAN: Weapon.SWORD,
    Monster.WHITE_MAGE: Weapon.STAFF,
    Monster.NEC_MAGE: Weapon.DAGGER,
    Monster.ELE_MAGE: Weapon.STAFF,
    Monster.PSY_MAGE: Weapon.DAGGER,
    Monster.ILL_MAGE: Weapon.STAFF,
    Monster.WITCH: Weapon.CLAWS,
    Monster.DRYAD: Weapon.DAGGER,
    Monster.CENTAUR: Weapon.HOOVES,
    Monster.GENIE: Weapon.FISTS,
    Monster.GOLEM: Weapon.FISTS,
    Monster.GARGOYLE: Weapon.CLAWS,
    Monster.BASILISK: Weapon.JAWS,
    Monster.MEDUSA: Weapon.DAGGER,
    Monster.BAL_DEMON: Weapon.CLAWS,
    Monster.MAR_DEMON: Weapon.SWORD,
    Monster.SUCCUBUS: Weapon.FANGS,
    Monster.RAKSHASHA: Weapon.FANGS,
    Monster.ICE_DEVIL: Weapon.CLAWS,
    Monster.BONE_DEVIL: Weapon.TALONS,
    Monster.IMP: Weapon.CLAWS,
    Monster.WEREWOLF: Weapon.JAWS,
    Monster.CHIMERA: Weapon.CHIM_HEADS,
    Monster.HYDRA: Weapon.JAWS,
    Monster.BEHOLDER: Weapon.FANGS,
    Monster.TROLL: Weapon.CLUB,
    Monster.MINOTAUR: Weapon.AXE,
    Monster.GI_WOLVERINE: Weapon.FANGS,
    Monster.TREANT: Weapon.LIMB,
    Monster.GI_AMOEBA: Weapon.ENDO_POD,
    Monster.GI_P_MANTIS: Weapon.MANDIBLE,
    Monster.GI_SCORPION: Weapon.STINGER,
    Monster.GI_WASP: Weapon.STINGER,
    Monster.GI_SPIDER: Weapon.FANGS,
    Monster.GHOST: Weapon.U_TOUCH,
    Monster.VAMPIRE: Weapon.FISTS,
    Monster.MUMMY: Weapon.FISTS,
    Monster.BANSHEE: Weapon.U_TOUCH,
    Monster.LICH: Weapon.U_TOUCH,
    Monster.SPECTRE: Weapon.U_TOUCH,
    Monster.GI_OCTOPUS: Weapon.TENTACLES,
    Monster.GI_CLAM: Weapon.JAWS,
    Monster.ELASMOSAURUS: Weapon.JAWS,
    Monster.GW_WHALE: Weapon.JAWS,
    Monster.MERMAID: Weapon.DAGGER,
    Monster.NOMONSTER: Weapon.NO_WEAP,
}
