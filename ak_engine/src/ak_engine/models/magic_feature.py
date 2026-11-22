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

**Stale-claim correction (Phase 895)**: this paragraph used to say
`mf1`/`mff`/`mfpow1` and their real wiring into a Feature's own actual
magic location/power were "left to a real follow-up phase" -- stale
since Phase 361, whose own `worldgen/internal_magical_locations.py`
already implements exactly this: `candidate_location()`/`resolve_
visible_location()` realize `mf1[ftype] + ((feature_index + ftype) mod
(mff[ftype] - mf1[ftype] + 1))` per `FeatureType` (`LOCATION_RANGE`,
one first/last `MagicFeature` pair per type -- `mf1`/`mff` collapsed
into a single inclusive range, not two independent assignments), and
`candidate_power()`/`resolve_power()` realize `mfpow1`'s own formula
against `models.power.Power` (`CTME.PAS`'s own `power` enum, already
ported in full). `worldgen/generate_new_game.py` calls both and stores
the result directly on `Feature.magic_location`/`.magic_power` for
every real generated Feature. `turn/feature_power_execution.py` (Phase
616-623) builds the full Feature -> Power system on top of that --
every real `Power`'s condition/cost/effect is wired, including
`MAP_PROV` (Phase 623, once `ProvinceState.known_to_kingdom()` gave it
a real "known provinces" concept to reveal into). See that module's own
docstring for the complete, closed picture.
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


def magic_feature_display_name(magic_feature: MagicFeature, feature_id: int | None = None, *, is_sea: bool = False) -> str:
    """The name a report shows for a magic feature: ``MAGIC_FEATURE_NAME``'s
    ``"Idol/FStatue"`` is a choice between two forms, resolved the way
    ``report/prose.py`` resolves any ``/F`` or ``/S`` choice -- ``/F`` by the
    parity of the containing Feature's number (even picks the second form, so a
    given Feature always shows the same one), ``/S`` by whether the place is at
    sea. Without a ``feature_id`` the first form is used. Underscores are
    spaces ("Crystal_Ball" -> "Crystal Ball")."""

    raw = MAGIC_FEATURE_NAME[magic_feature]
    if "/" not in raw:
        return raw.replace("_", " ")
    first, rest = raw.split("/", 1)
    marker, second = rest[0], rest[1:]
    if marker == "F":
        use_second = feature_id is not None and feature_id % 2 == 0
    else:  # "S"
        use_second = is_sea
    return (second if use_second else first).replace("_", " ")
