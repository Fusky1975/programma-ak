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

import math

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.feature import FeatureType
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.power import Power, PowerCondition
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper

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
    """The visibility gate plus the Gastrap/Seal forced-``MFNone`` rule.

    Phase 616: the polarity here was backwards (``== 0`` forced ``NONE``
    on *even* ``feature_index + feature_x``). Re-derived byte-for-byte
    against ``Special Features.md``'s own section 8 real-world catalog
    (``GW3__T1``'s 128 Features, user-supplied 2026-08-22) -- every one
    of 12 cross-checked rows (F#0,1,2,3,4,5,6,7,8,9,16,17), including
    the exact alternate-form display names (F#0 Tomb -> Altar/"Prayer
    Rug", F#8 Sacred Rock -> Throne/"Director's Chair"), only matches
    with *even* sum showing the candidate and *odd* forcing ``NONE`` --
    the opposite of what was coded. See ``tests/
    test_internal_magical_locations.py`` for the oracle rows.
    """

    if (feature_index + feature_x) % 2 != 0:
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


# -- Phase 616: Set_Abil's own three parameter formulas, plus DampCollege's
# own school-restricted variant -- ``Special Features.md`` (user-supplied
# 2026-08-22) section 3.1-3.4, ``modval = fn + ord(ftype[fn])`` throughout.


def power_ability_parameter(feature_type: FeatureType, feature_index: int) -> Ability:
    """UP_SKILL/UP_APT/DN_SKILL/DN_APT's own ``_abil``: ``ability((fn +
    ord(ftype[fn])) MOD 15)`` -- a deterministic rotation over all 15
    real abilities, no skill/aptitude/race/sex/King/hero/RNG input at
    all.
    """

    modval = feature_index + feature_type.value
    return Ability(modval % 15)


def damp_college_ability_parameter(feature_type: FeatureType, feature_index: int) -> Ability:
    """DAMP_COLLEGE's own restricted ``_abil``: ``ability(5 + (fn +
    ord(ftype[fn])) MOD 5)`` -- only the 5 real magic schools (White
    Magic .. Illusionist, ordinals 5-9), never a mundane ability.
    """

    modval = feature_index + feature_type.value
    return Ability(5 + modval % 5)


def power_temper_parameter(feature_type: FeatureType, feature_index: int) -> Temper:
    """NEW_TEMP's own parameter: ``temper(((fn + ord(ftype[fn])) MOD 3)
    + 1)`` -- only Cautious/Brave/Berserk (ordinals 1-3); Cowardly (0)
    can never be assigned by this power.
    """

    modval = feature_index + feature_type.value
    return Temper((modval % 3) + 1)


def power_race_parameter(feature_type: FeatureType, feature_index: int) -> Race:
    """NEW_RACE's own parameter: ``race((fn + ord(ftype[fn])) AND 3)``
    -- only Human/Elf/Dwarf/Orc (ordinals 0-3); the bitmask excludes
    every other real ``Race``.
    """

    modval = feature_index + feature_type.value
    return Race(modval & 3)


# -- Phase 616: Set_FCon -- ``Special Features.md`` section 4.1-4.3.
# ``(con1, con2, perc)`` per real ``Power`` that calls it -- the 5 real
# Oracles (``ORAC_ALIGN``..``ORAC_TREAS``) share one entry each, all
# identical (`Same Align | Pay | 20`), confirmed by the source's own
# "cinque Oracoli" row rather than spelled out five times. A `Power` not
# in this table never calls `Set_FCon` at all (`NEW_SEX`, `DN_SKILL`,
# `DN_APT`, `DAMP_COLLEGE`, `DAMP_MAGIC`, `WARP_SPACE`, `CHANCE`) --
# `resolve_power_condition()` returns `PC_NONE` for those, not a guess.
POWER_CONDITION_PAIRS: dict[Power, tuple[PowerCondition, PowerCondition, int]] = {
    Power.NEW_TEMP: (PowerCondition.PAY_UP, PowerCondition.SAME_ALIGN, 10),
    Power.NEW_RACE: (PowerCondition.PAY_UP, PowerCondition.SAME_ALIGN, 10),
    Power.UP_SKILL: (PowerCondition.PAY_UP, PowerCondition.DRAIN_COURAGE, 200),
    Power.UP_APT: (PowerCondition.PAY_UP, PowerCondition.DRAIN_COURAGE, 35),
    Power.CAST_SPELL: (PowerCondition.PAY_UP, PowerCondition.DRAIN_SKILL, 35),
    Power.ANS_PRAYER: (PowerCondition.SAME_ALIGN, PowerCondition.PAY_UP, 35),
    Power.MAP_FEAT: (PowerCondition.PAY_UP, PowerCondition.SAME_ALIGN, 20),
    Power.MAP_PROV: (PowerCondition.PAY_UP, PowerCondition.SAME_ALIGN, 10),
    Power.SAGE_DISC: (PowerCondition.PAY_UP, PowerCondition.DRAIN_COURAGE, 300),
    Power.ORAC_ALIGN: (PowerCondition.SAME_ALIGN, PowerCondition.PAY_UP, 20),
    Power.ORAC_POWER: (PowerCondition.SAME_ALIGN, PowerCondition.PAY_UP, 20),
    Power.ORAC_OFFICE: (PowerCondition.SAME_ALIGN, PowerCondition.PAY_UP, 20),
    Power.ORAC_GOLD: (PowerCondition.SAME_ALIGN, PowerCondition.PAY_UP, 20),
    Power.ORAC_TREAS: (PowerCondition.SAME_ALIGN, PowerCondition.PAY_UP, 20),
    Power.RECHARGE: (PowerCondition.PAY_UP, PowerCondition.SAME_ALIGN, 20),
    Power.GRANT_WISH: (PowerCondition.G_TURN, PowerCondition.DRAIN_SKILL, 70),
    Power.GAMBLE: (PowerCondition.NEED_KING, PowerCondition.SAME_ALIGN, 20),
}


def resolve_power_condition(
    power: Power, feature_type: FeatureType, feature_index: int, feature_x: int
) -> PowerCondition:
    """``Set_FCon``'s own two-branch formula (section 4.1): ``if
    Min(35,perc)*2 > ((fn+2)*ord(ftype[fn]) MOD 100) then fpowcon :=
    con1 else if perc > (((fn+5)*fx[fn] MOD 100) * (100-2*perc)) DIV
    100 then fpowcon := con2`` -- ``PC_NONE`` (the real Pascal default,
    left untouched by either branch) for any ``power`` this table
    doesn't cover, or when neither branch fires. Cross-checked by hand
    against 5 of ``Special Features.md``'s own section 8 real-world
    rows (F#5/7/27/85/113 across `UP_SKILL`/`ANS_PRAYER`/5-Oracles),
    every one an exact match including the resulting cost -- see
    ``tests/test_internal_magical_locations.py``.
    """

    pair = POWER_CONDITION_PAIRS.get(power)
    if pair is None:
        return PowerCondition.PC_NONE
    con1, con2, perc = pair
    ftype_ordinal = feature_type.value

    if min(35, perc) * 2 > ((feature_index + 2) * ftype_ordinal) % 100:
        return con1

    parity_term = ((feature_index + 5) * feature_x) % 100
    scaled = parity_term * (100 - 2 * perc)
    threshold = int(scaled / 100)  # Pascal DIV truncates toward zero, same as int() for these signs
    if perc > threshold:
        return con2

    return PowerCondition.PC_NONE


def power_condition_cost(power_condition: PowerCondition, perc: int) -> int:
    """The real gold/skill-drain magnitude (section 4.1): ``ceil(perc *
    0.05)`` gold for ``PAY_UP``, ``ceil(perc * 0.025)`` skill levels for
    ``DRAIN_SKILL``, ``0`` for every other condition (``DRAIN_COURAGE``'s
    own cost is a flat 1 temper step, not a ``perc``-scaled magnitude --
    applied directly by the caller, not through this function).
    """

    if power_condition is PowerCondition.PAY_UP:
        return math.ceil(perc * 0.05)
    if power_condition is PowerCondition.DRAIN_SKILL:
        return math.ceil(perc * 0.025)
    return 0


def resolve_required_alignment(feature_type: FeatureType, feature_index: int, feature_x: int) -> Alignment:
    """``SAME_ALIGN``'s own required ``Alignment`` (section 4.3): ``repeat
    powalign := outlook((fn + modval + tries) MOD ord(Mechanical)); Inc(
    tries); until powalign <> Hellish`` -- ``ALIGNMENT_BY_ORDINAL``
    (``models/alignment.py``, already the exact real ``outlook``
    ordinal sequence) resolves the enum lookup; ``ord(Mechanical) == 8``
    since ``Mechanical`` is ``ALIGNMENT_ORDINAL``'s own 9th entry
    (index 8). Advances past Hellish/Anti-Holy to the next ordinal
    (never lands on Mechanical/Special) -- cross-checked against
    ``Special Features.md``'s own F#27 (-> Undead) and F#62 (-> Pagan)
    rows.
    """

    modval = feature_index + feature_type.value
    tries = 0
    while True:
        ordinal = (feature_index + modval + tries) % 8
        candidate = ALIGNMENT_BY_ORDINAL[ordinal]
        tries += 1
        if candidate is not Alignment.ANTI_HOLY:
            return candidate
