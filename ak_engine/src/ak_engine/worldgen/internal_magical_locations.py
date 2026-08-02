"""Internal magical locations (Phase 361): ``AKGEN.EXE``'s ``Set_Event``
per-feature magical-location and power selection (recomputed at feature
processing time, never stored in the GW file itself).

Ninth phase of the world-generation sub-plan. Source:
``world_generation.internal_magical_locations``.

**Confirmed exactly** and implemented here, both formulas fully
*deterministic* -- no RNG involved at all, unlike every other worldgen
phase so far:

- ``candidate_location()``: ``mf1[ftype] + ((feature_index + ftype) mod
  (mff[ftype] - mf1[ftype] + 1))``. The source's own per-``FeatureType``
  ``first``/``last`` location-name range converts directly onto this
  project's own pre-existing ``models.magic_feature.MagicFeature``
  enum (``CTME.PAS``'s own ``magfeat``, already 21 members at ordinals
  0..20 in exactly the source's own order) -- every one of the 32
  ``FeatureType`` ranges' own declared ``choices`` count was
  cross-checked programmatically against this ordinal arithmetic
  before the table was written, with zero mismatches.
- ``resolve_visible_location()``: "candidate is visible only when
  (feature_index + feature_x) is odd; Gastrap and Seal candidates are
  forced to MFNone" -- both confirmed rules realized literally: an
  even parity sum, or a Gastrap/Seal candidate regardless of parity,
  both resolve to ``MagicFeature.NONE``.
- ``candidate_power()`` / ``resolve_power()``: "``mfpow1[location] +
  ((tries + feature_index + feature_type + min(10,tries)*(feature_index
  + feature_type + min(20,tries))) mod (mfpowf[location]-mfpow1[location]
  +1))``", with "up to three deterministic candidates; stop early on
  CastSpell or AnsPrayer". ``tries`` is a plain incrementing counter
  (``0, 1, 2``), not a random draw. The source's own 21
  ``location_ranges`` (one per ``MagicFeature``, in ``Power`` terms)
  convert directly onto this project's own pre-existing
  ``models.power.Power`` enum (``CTME.PAS``'s own ``power``, already
  25 members in the source's own order) -- again cross-checked
  programmatically with zero mismatches before writing the table.

**Deliberately NOT implemented here**:

- ``test_game_999``: "cycles values 1..Itself and bypasses the normal
  selection formula" -- an explicit debug/test-mode override for one
  specific reserved game number, not part of real world generation.
- Wiring these formulas into any live feature/province processing --
  they need a real ``feature_index``/``feature_x`` sequence from an
  actually-generated map, the same spatial-integration gap already
  flagged for Phase 359/360.

**Verification**: `candidate_location()` and `candidate_power()` are
checked against hand-worked small examples (e.g. ``PYRAMID`` at
``feature_index=0`` -> ``CUP``, the very first candidate in its own
range) and for full-period coverage (cycling ``feature_index`` over an
entire range's span visits every member exactly once, confirming the
modular arithmetic). `resolve_power()`'s early-stop rule is checked
both ways: a ``tries=0`` hit on CastSpell/AnsPrayer returns
immediately without computing further tries, and a location whose
range never includes either of those two powers exhausts all three
tries and returns the ``tries=2`` result. The source's own real
``GW3__T1`` aggregate (128 features: 71 MFNone/55.47%, 57
visible/44.53%) is recorded here as context, not reproduced exactly --
that would need the real per-feature ``feature_x``/``feature_type``
sequence from an actual generated map, which isn't available
standalone.
"""

from __future__ import annotations

from ak_engine.models.feature import FeatureType
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.power import Power

# FeatureType -> (first, last) inclusive MagicFeature range for the
# location-candidate formula.
LOCATION_RANGE: dict[FeatureType, tuple[MagicFeature, MagicFeature]] = {
    FeatureType.PYRAMID: (MagicFeature.CUP, MagicFeature.SEALED_ENTRANCE),
    FeatureType.TOMB: (MagicFeature.CUP, MagicFeature.SEALED_ENTRANCE),
    FeatureType.CATACOMBS: (MagicFeature.ALTAR, MagicFeature.SEALED_ENTRANCE),
    FeatureType.CRYPT: (MagicFeature.INCENSE_BURNER, MagicFeature.SEALED_ENTRANCE),
    FeatureType.CAVE: (MagicFeature.INCENSE_BURNER, MagicFeature.PENTAGRAM),
    FeatureType.CAVERN: (MagicFeature.POOL, MagicFeature.HOURGLASS),
    FeatureType.VOLC_TUNNEL: (MagicFeature.BOOK, MagicFeature.GAS_TRAP),
    FeatureType.DUNGEON: (MagicFeature.POOL, MagicFeature.SEALED_ENTRANCE),
    FeatureType.MAZE: (MagicFeature.PAINTING, MagicFeature.SEALED_ENTRANCE),
    FeatureType.LABYRINTH: (MagicFeature.POOL, MagicFeature.SEALED_ENTRANCE),
    FeatureType.TOWER: (MagicFeature.FOUNTAIN, MagicFeature.GAS_TRAP),
    FeatureType.CASTLE: (MagicFeature.POOL, MagicFeature.SEALED_ENTRANCE),
    FeatureType.GREAT_HALL: (MagicFeature.FOUNTAIN, MagicFeature.GAS_TRAP),
    FeatureType.MONASTERY: (MagicFeature.POOL, MagicFeature.SEALED_ENTRANCE),
    FeatureType.TEMPLE: (MagicFeature.POOL, MagicFeature.SEALED_ENTRANCE),
    FeatureType.PET_FOREST: (MagicFeature.POOL, MagicFeature.IDOL),
    FeatureType.SACRED_ROCK: (MagicFeature.CUP, MagicFeature.THRONE),
    FeatureType.AS_MONUMENT: (MagicFeature.ALTAR, MagicFeature.PENTAGRAM),
    FeatureType.ALTAR: (MagicFeature.FOUNTAIN, MagicFeature.PEDESTAL),
    FeatureType.DES_RUINS: (MagicFeature.ALTAR, MagicFeature.THRONE),
    FeatureType.SUNK_CITY: (MagicFeature.ALTAR, MagicFeature.SEALED_ENTRANCE),
    FeatureType.LOST_CITY: (MagicFeature.POOL, MagicFeature.SEALED_ENTRANCE),
    FeatureType.LOST_TEMPLE: (MagicFeature.FOUNTAIN, MagicFeature.PAINTING),
    FeatureType.HOLLOW_TREE: (MagicFeature.PENTAGRAM, MagicFeature.HOURGLASS),
    FeatureType.GLADE: (MagicFeature.POOL, MagicFeature.FOUNTAIN),
    FeatureType.HANG_VALLEY: (MagicFeature.POOL, MagicFeature.FOUNTAIN),
    FeatureType.MOUNT_PEAK: (MagicFeature.ALTAR, MagicFeature.THRONE),
    FeatureType.MAG_POOL: (MagicFeature.POOL, MagicFeature.CUP),
    FeatureType.LOCH: (MagicFeature.FOUNTAIN, MagicFeature.FOUNTAIN),
    FeatureType.UND_CAVERN: (MagicFeature.POOL, MagicFeature.THRONE),
    FeatureType.MAELSTROM: (MagicFeature.NONE, MagicFeature.NONE),
    FeatureType.NOFTYPE: (MagicFeature.NONE, MagicFeature.NONE),
}

FORCED_NONE_CANDIDATES: frozenset[MagicFeature] = frozenset(
    {MagicFeature.GAS_TRAP, MagicFeature.SEALED_ENTRANCE}
)

# MagicFeature (location) -> (first, last) inclusive Power range for the
# power-selection formula.
POWER_RANGE: dict[MagicFeature, tuple[Power, Power]] = {
    MagicFeature.NONE: (Power.PNONE, Power.PNONE),
    MagicFeature.POOL: (Power.NEW_SEX, Power.DN_SKILL),
    MagicFeature.FOUNTAIN: (Power.NEW_SEX, Power.DN_SKILL),
    MagicFeature.CUP: (Power.NEW_SEX, Power.DN_SKILL),
    MagicFeature.ALTAR: (Power.NEW_SEX, Power.GRANT_WISH),
    MagicFeature.IDOL: (Power.NEW_SEX, Power.GAMBLE),
    MagicFeature.PEDESTAL: (Power.NEW_SEX, Power.RECHARGE),
    MagicFeature.THRONE: (Power.NEW_SEX, Power.RECHARGE),
    MagicFeature.INCENSE_BURNER: (Power.NEW_SEX, Power.RECHARGE),
    MagicFeature.LAMP: (Power.ORAC_ALIGN, Power.GAMBLE),
    MagicFeature.PENTAGRAM: (Power.NEW_SEX, Power.CHANCE),
    MagicFeature.CRYSTAL_BALL: (Power.CAST_SPELL, Power.SAGE_DISC),
    MagicFeature.HOURGLASS: (Power.DAMP_COLLEGE, Power.WARP_SPACE),
    MagicFeature.BELL: (Power.ORAC_ALIGN, Power.GAMBLE),
    MagicFeature.PAINTING: (Power.ORAC_ALIGN, Power.GAMBLE),
    MagicFeature.ROULETTE_WHEEL: (Power.GAMBLE, Power.CHANCE),
    MagicFeature.BOOK: (Power.CAST_SPELL, Power.SAGE_DISC),
    MagicFeature.PUZZLE: (Power.SAGE_DISC, Power.ORAC_TREAS),
    MagicFeature.GAS_TRAP: (Power.CAST_SPELL, Power.CAST_SPELL),
    MagicFeature.SEALED_ENTRANCE: (Power.ORAC_ALIGN, Power.GAMBLE),
    MagicFeature.ITSELF: (Power.DAMP_COLLEGE, Power.WARP_SPACE),
}

_EARLY_STOP_POWERS: frozenset[Power] = frozenset({Power.CAST_SPELL, Power.ANS_PRAYER})
MAX_POWER_TRIES = 3


def candidate_location(feature_type: FeatureType, feature_index: int) -> MagicFeature:
    """``mf1[ftype] + ((feature_index + ftype) mod (mff[ftype] - mf1[ftype] + 1))``."""

    first, last = LOCATION_RANGE[feature_type]
    span = last.value - first.value + 1
    offset = (feature_index + feature_type.value) % span
    return MagicFeature(first.value + offset)


def resolve_visible_location(
    feature_type: FeatureType, feature_index: int, feature_x: int
) -> MagicFeature:
    """The confirmed odd/even visibility gate plus the Gastrap/Seal forced-``MFNone`` rule."""

    if (feature_index + feature_x) % 2 == 0:
        return MagicFeature.NONE
    candidate = candidate_location(feature_type, feature_index)
    if candidate in FORCED_NONE_CANDIDATES:
        return MagicFeature.NONE
    return candidate


def candidate_power(
    location: MagicFeature, feature_index: int, feature_type: int, tries: int
) -> Power:
    """``mfpow1[location] + ((tries + feature_index + feature_type +
    min(10,tries)*(feature_index + feature_type + min(20,tries))) mod
    (mfpowf[location]-mfpow1[location]+1))``."""

    first, last = POWER_RANGE[location]
    span = last.value - first.value + 1
    inner = feature_index + feature_type + min(20, tries)
    offset = (tries + feature_index + feature_type + min(10, tries) * inner) % span
    return Power(first.value + offset)


def resolve_power(location: MagicFeature, feature_index: int, feature_type: int) -> Power:
    """Up to three deterministic candidates; stops early on CastSpell or AnsPrayer."""

    candidate = Power.PNONE
    for tries in range(MAX_POWER_TRIES):
        candidate = candidate_power(location, feature_index, feature_type, tries)
        if candidate in _EARLY_STOP_POWERS:
            return candidate
    return candidate
