"""Magic feature vocabulary -- the smaller magical landmark found inside a
geographic ``Feature`` (Pyramid, Tomb, Cave, etc.).

``HostAK/TP/CTME.PAS``'s own ``magfeat`` enum (~line 448, 21 members) and
``mfname`` table (~line 549) -- found the same way Phase 91's
``models/discovery.py`` was: continuing to mine the wider Pascal source
(not just ``CTBOTH.PAS``) the way Phases 79-91 found their own real data.

**Confirmed to be `PROSE.TXT`'s own documented `"$\\"` marker**: `$\\:
Magic feature name ("crystal ball", "magic bell", etc.)` -- `RUMORS.PAS`'s
own `$`-prefixed marker dispatch resolves it via `Say(mfname[_magfeat],
spytype)`. Also referenced in `REPORTS.PAS` and `SAY.PAS`.

**`MAGIC_FEATURE_NAME`'s own strings are raw, unresolved compound
templates, not plain text** -- every entry (except the sentinel `NONE`
and the quirky final `ITSELF`) is `"<name>/F<alternate>"` or
`"<name>/S<alternate>"` (e.g. `"Pool/FStream"`,
`"Gas_Trap/SElectric_Trap"`). The `F`/`S` prefix convention here is
distinct from the already-confirmed `/R` choice marker
(`report/prose.py`/`models/weapon.py` WEAPON_HIT_VERB) and is not
resolved by any source read so far -- stored verbatim, matching how
`models/weapon.py WEAPON_HIT_VERB` and `models/treasure.py TREASURE_LABEL`
(Phases 77/83) already store their own raw, unrendered template strings
rather than guessing at resolution.

`ITSELF`'s own entry is the literal string `'&'`, not a normal name --
apparently a marker meaning "the containing geographic ``Feature`` counts
as its own magic feature" (visiting the Feature itself *is* the magic
landmark, no separate object to name), kept verbatim rather than guessed.

**Confirmed real but deliberately out of scope for this phase**: `CTME.PAS`
also declares `mf1`/`mff` (both `array[FeatureType] of magfeat` -- two
separate per-``FeatureType`` magic-feature assignments, presumably a
primary and a "false"/decoy choice used by the Search mechanic) and
`mfpow1` (`array[magfeat] of power`, where `power` is `CTME.PAS`'s own
rich effect-type enum: `NewSex, NewTemp, NewRace, UpSkill, UpApt, DnSkill,
DnApt, DampCollege, DampMagic, WarpSpace, CastSpell, AnsPrayer, MapFeat,
MapProv, SageDisc, ...`). Wiring any of this -- which magic feature a
given `Feature` actually has, and what visiting it actually does -- needs
real design work and is left to a real follow-up phase, matching how
`models/discovery.py` (Phase 91) also stopped at vocabulary alone.
"""

from __future__ import annotations

from enum import Enum


class MagicFeature(Enum):
    """``CTME.PAS``'s own ``magfeat`` enum, verbatim order. Member names
    are derived from ``MAGIC_FEATURE_NAME``'s own display strings (the
    part before the ``/``), matching this project's ``Weapon``/
    ``Discovery`` precedent, not the Pascal source's own internal
    identifiers (``MAlter``, ``CrysBall``, ``Machine``, ``Gastrap``,
    ``Seal`` -- none of which read as real names on their own).
    """

    NONE = 0
    POOL = 1
    FOUNTAIN = 2
    CUP = 3
    ALTAR = 4
    IDOL = 5
    PEDESTAL = 6
    THRONE = 7
    INCENSE_BURNER = 8
    LAMP = 9
    PENTAGRAM = 10
    CRYSTAL_BALL = 11
    HOURGLASS = 12
    BELL = 13
    PAINTING = 14
    ROULETTE_WHEEL = 15
    BOOK = 16
    PUZZLE = 17
    GAS_TRAP = 18
    SEALED_ENTRANCE = 19
    ITSELF = 20


# CTME.PAS `mfname`, verbatim (including the embedded `/F.../S...`
# alternate-form suffixes -- see module docstring), positional with
# `MagicFeature`'s own ordinals above.
MAGIC_FEATURE_NAME: dict[MagicFeature, str] = {
    MagicFeature.NONE: "None/FNone",
    MagicFeature.POOL: "Pool/FStream",
    MagicFeature.FOUNTAIN: "Fountain/FFount",
    MagicFeature.CUP: "Cup/FDecanter",
    MagicFeature.ALTAR: "Altar/FPrayer_Rug",
    MagicFeature.IDOL: "Idol/FStatue",
    MagicFeature.PEDESTAL: "Pedestal/FDais",
    MagicFeature.THRONE: "Throne/FDirector's_Chair",
    MagicFeature.INCENSE_BURNER: "Incense_Burner/FEverlit_Candle",
    MagicFeature.LAMP: "Lamp/FCrucible",
    MagicFeature.PENTAGRAM: "Pentagram/FMagic_Circle",
    MagicFeature.CRYSTAL_BALL: "Crystal_Ball/FMagic_Mirror",
    MagicFeature.HOURGLASS: "Hourglass/FCuckoo_Clock",
    MagicFeature.BELL: "Bell/FGong",
    MagicFeature.PAINTING: "Painting/FTapestry",
    MagicFeature.ROULETTE_WHEEL: "Roulette_Wheel/FSlot_Machine",
    MagicFeature.BOOK: "Book/FTome",
    MagicFeature.PUZZLE: "Puzzle/FEnigma",
    MagicFeature.GAS_TRAP: "Gas_Trap/SElectric_Trap",
    MagicFeature.SEALED_ENTRANCE: "Sealed_Entrance/FSealed_Room",
    MagicFeature.ITSELF: "&",
}
