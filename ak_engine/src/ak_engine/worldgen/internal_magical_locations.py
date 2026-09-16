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
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.feature import FeatureType
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import Terrain
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


def power_terrain_parameter(feature_type: FeatureType, feature_index: int) -> Terrain:
    """Phase 801 (`Desktop/POWMSG.md` choice 18, byte-verified): "As a
    demonstration, I will change the appearance of this province to
    `!" -- `CAST_SPELL`/`ANS_PRAYER` granting a derived `Spell.ILLUS_
    TERRAIN` needs a fake terrain to announce, but no player order ever
    supplies one for a Feature-granted cast (unlike an ordinary player-
    issued Illusory Terrain order, which always carries its own chosen
    terrain). POWMSG.md gives the real *text* and confirms a terrain
    parameter is genuinely needed, but no formula for *which* terrain
    survives anywhere in the document.

    **Project-original, clearly labeled as such** (confirmed directly
    with the user, no source, no guess at random): mirrors this same
    module's own `power_temper_parameter()`/`power_race_parameter()`
    shape exactly -- the identical `(feature_index + ftype) mod N`
    rotation already used for every other Set_Event parameter, `mod 6`
    to land on one of `Terrain`'s 6 real members (`PLAINS`..`SEA`,
    ordinals 0-5) -- `NO_TERRAIN` (6) is a sentinel, never a real
    terrain to feign, excluded the same way `power_race_parameter()`'s
    own `AND 3` excludes every non-humanoid `Race`.
    """

    modval = feature_index + feature_type.value
    return Terrain(modval % 6)


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


def _i16(n: int) -> int:
    """Reinterprets ``n`` as Turbo Pascal's own signed 16-bit
    ``Integer`` -- a 16x16 ``MUL`` followed by ``CWD`` (sign-extend
    ``AX`` into ``DX``) truncates the real 32-bit ``DX:AX`` product
    back to a signed word before every subsequent ``IDIV`` in the
    compiled ``Set_FCon``. Verified byte-for-byte against
    ``AK.EXE``/``AKGEN.EXE`` (``Desktop/PCCOND.md``, 2026-09-15) --
    this closes a real, confirmed bug in ``resolve_power_condition()``'s
    own prior unbounded-precision port, isolated to ``SAGE_DISC``
    (``perc=300``) specifically: every other real ``perc`` value
    already matched the naive/unbounded model exactly.
    """

    return (n + 32768) % 65536 - 32768


def _div0(a: int, b: int) -> int:
    """Pascal's own ``DIV`` -- truncates toward zero
    (``abs(a)//abs(b)``, signed), unlike Python's ``//`` (floors
    toward negative infinity)."""

    return (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)


def _mod0(a: int, b: int) -> int:
    """Pascal's own ``MOD``, paired with ``_div0()``: ``a - (a DIV b) * b``."""

    return a - _div0(a, b) * b


def resolve_power_condition(
    power: Power, feature_type: FeatureType, feature_index: int, feature_x: int
) -> PowerCondition:
    """``Set_FCon``'s own two-branch formula (section 4.1): ``if
    Min(35,perc)*2 > ((fn+2)*ord(ftype[fn]) MOD 100) then fpowcon :=
    con1 else if perc > (((fn+5)*fx[fn] MOD 100) * (100-2*perc)) DIV
    100 then fpowcon := con2`` -- ``PC_NONE`` (the real Pascal default,
    left untouched by either branch) for any ``power`` this table
    doesn't cover, or when neither branch fires.

    Every intermediate product is routed through ``_i16()`` first,
    matching the real compiled routine's own 16-bit-truncated
    arithmetic exactly (``Desktop/PCCOND.md``, byte-verified against
    both ``AK.OVR`` and ``AKGEN.EXE``) -- a real bug fix over the
    original, unbounded-precision port, isolated to ``SAGE_DISC``
    (``perc=300``) only. Worked example, byte-verified: ``fn=7,
    type=9, x=14`` -- the naive/unbounded model selects
    ``Drain_Courage``; the real, truncated compiled math selects
    ``PC_NONE`` (see ``tests/test_internal_magical_locations.py``).
    Cross-checked by hand against 5 of ``Special Features.md``'s own
    section 8 real-world rows (F#5/7/27/85/113 across
    `UP_SKILL`/`ANS_PRAYER`/5-Oracles), every one an exact match
    including the resulting cost -- unaffected by this fix, since
    none of them uses ``SAGE_DISC``'s own ``perc=300``.
    """

    pair = POWER_CONDITION_PAIRS.get(power)
    if pair is None:
        return PowerCondition.PC_NONE
    con1, con2, perc = pair
    ftype_ordinal = feature_type.value

    a_value = _mod0(_i16(_i16(feature_index + 2) * ftype_ordinal), 100)
    if a_value < _i16(2 * min(35, perc)):
        return con1

    b_value = _mod0(_i16(_i16(feature_index + 5) * feature_x), 100)
    factor = _i16(100 - _i16(2 * perc))
    threshold = _div0(_i16(b_value * factor), 100)
    if threshold < perc:
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


# Phase 620: `Set_Spell`'s own 12 "plus extra spells" (section 3.6),
# always excluded from `CastSpell`/`AnsPrayer`'s own candidate pool --
# `Resurrection, Charm, Holy_Symbol, Hand_of_Death, Fireball, Psychic_
# Blast, Invisibility, Spiritwrack, Control_Undead, Ice_Suspend, Telek_
# Storm, Mirror_Image`.
_SET_SPELL_EXCLUDED_EXTRAS = frozenset(
    {
        Spell.RESURRECTION,
        Spell.HOLY_SYMBOL,
        Spell.HAND_OF_DEATH,
        Spell.FIREBALL,
        Spell.CHARM,
        Spell.PSYCHIC_BLAST,
        Spell.INVISIBILITY,
        Spell.SPIRITWRACK,
        Spell.CONTROL_UNDEAD,
        Spell.ICE_SUSPEND,
        Spell.TELEK_STORM,
        Spell.MIRROR_IMAGE,
    }
)


# Phase 621: `Spell_College(spell, 0)`'s own real ordering -- `models/
# enums.py Spell`'s own docstring, cross-checked against every one of
# the 25 spells' already-confirmed `Ability` elsewhere in this project
# (see `spell_college()`'s own docstring below).
_SPELL_COLLEGE_ORDER = (Ability.WHITE, Ability.NECROMANCY, Ability.ELEMENTAL, Ability.PSYCHIC, Ability.ILLUSION)

# Phase 621: a defensive safety net only -- `resolve_spell_candidate()`'s
# own docstring proves the real loop always terminates within at most
# 25 outer iterations (a few more for `AnsPrayer`'s own inner skip);
# this is never actually reached.
_SET_SPELL_MAX_TRIES = 200


def spell_college(spell: Spell) -> Ability:
    """`Spell_College(spell, 0)` (`Set_Spell`'s own `AnsPrayer` White-
    Magic-favoring inner loop, Phase 621, `miscwrit.md` section 4.2) --
    derived, not guessed, from `models/enums.py Spell`'s own docstring
    ("25 base spells... four contiguous blocks (0-19, ability order
    White/Necromancy/Elemental/Psychic/Illusionist)... followed by one
    fifth-spell block (20-24, same order)"): ordinals 0-19 are 5 blocks
    of 4 spells each (one ability per block, in that order); 20-24 are
    each ability's own lone "fifth spell" (same order again). Cross-
    checked against every one of the 25 spells' own already-confirmed
    `Ability` elsewhere in this project (`turn/cast_execution.py
    _SPELL_ABILITY` for 19 of them, `turn/encounter.py PERSONAL_COMBAT_
    SPELL_ABILITY` for the other 10 secret/personal-combat-only ones)
    -- zero contradictions across all 25 real spells, so this reuses
    the project's own existing confirmed data rather than adding any.
    """

    index = spell.value // 4 if spell.value < 20 else spell.value - 20
    return _SPELL_COLLEGE_ORDER[index]


def resolve_spell_candidate(
    feature_type: FeatureType, feature_index: int, terrain: Terrain, power: Power, miscwrit: int
) -> Spell:
    """The real, complete `Set_Spell` (Phase 621 -- `miscwrit.md`,
    user-supplied 2026-08-22, section 4.2 quoting `YAK.PAS` verbatim):

    ```pascal
    REPEAT
      REPEAT
        setval:= (modval+tries) MOD ord(Gate_Angel);
        Inc(tries);
      UNTIL ((tries MOD 3 = 0) or
             (Spell_College(spell(setval),0) = White) or
             (fpower <> AnsPrayer));
      CASE spell(setval) OF
        Resurrection,Charm,Holy_Symbol,Hand_Of_Death,Fireball,
          Psychic_Blast,Invisibility,Spiritwrack,Control_Undead,
          Ice_Suspend,Telek_Storm,Mirror_Image: ;
        Part_Sea,Flood: IF pterr[fx[fn],fy[fn]] <> MTNS THEN found:= true;
        Earthquake: IF pterr[fx[fn],fy[fn]] <> SEA THEN found:= true;
        ELSE IF miscwrit and 2 = 2 THEN found:= true;
      END;
    UNTIL found;
    ```

    Replaces Phase 620's own `resolve_terrain_spell_candidate()`, which
    only implemented the ``tries = 0`` case because `miscwrit`'s own
    real value was unconfirmed -- `miscwrit.md`'s own section 7 gives
    the real observed values in this project's actual target data
    (`GW3__T1` = 6, `GW3__T2`-`T12` = 14, both with bit `0x0002` set),
    so the `ELSE` branch is now a real, resolvable case, not a guess.

    **Always terminates, proven not assumed**: `setval` cycles through
    all 25 residues as `tries` grows. For *any* terrain, at least one
    of `{Part_Sea, Flood valid}` (terrain != Mountains) or `{Earthquake
    valid}` (terrain != Sea) is always true -- a terrain can't be both
    Mountains and Sea simultaneously -- so the outer `REPEAT...UNTIL
    found` always finds a match within a bounded number of iterations
    regardless of `miscwrit`. `_SET_SPELL_MAX_TRIES` is a defensive cap
    only, never actually reached.
    """

    modval = feature_index + feature_type.value
    modulus = Spell.GATE_ANGEL.value
    tries = 0
    for _outer_iteration in range(_SET_SPELL_MAX_TRIES):
        while True:
            setval = (modval + tries) % modulus
            tries += 1
            if tries % 3 == 0 or spell_college(Spell(setval)) is Ability.WHITE or power is not Power.ANS_PRAYER:
                break
        spell = Spell(setval)
        if spell in _SET_SPELL_EXCLUDED_EXTRAS:
            found = False
        elif spell in (Spell.PART_SEA, Spell.FLOOD):
            found = terrain is not Terrain.MTNS
        elif spell is Spell.EARTHQUAKE:
            found = terrain is not Terrain.SEA
        else:
            found = (miscwrit & 2) == 2
        if found:
            return spell
    raise RuntimeError(
        "Set_Spell's own REPEAT...UNTIL found didn't terminate within "
        f"{_SET_SPELL_MAX_TRIES} outer iterations -- should be unreachable, see this function's own docstring proof"
    )


# -- Phase 622: Power.CHANCE's own sub-power roll -- `gdday.md` (user-
# supplied 2026-08-22), section 5.1 quoting YAK.PAS Set_Event's own
# Chance CASE branch verbatim, independently confirmed at 8086 level
# (section 5.2, AKGEN.EXE 0x51E5D-0x51F17): `(gameturn + gdday) AND 7`,
# no RNG before the CASE, always one of 6 already-implemented powers.
_CHANCE_SUB_POWER_BY_RESIDUE: dict[int, Power] = {
    0: Power.NEW_SEX,
    1: Power.NEW_TEMP,
    2: Power.UP_SKILL,
    3: Power.UP_SKILL,
    4: Power.CAST_SPELL,
    5: Power.CAST_SPELL,
    6: Power.SAGE_DISC,
    7: Power.DN_SKILL,
}

# `rspell` (section 5.1/6.5), indexed by `IRand AND 7` at resolution
# time (a fresh draw per evaluation, not stored -- section 6.5/7.2).
# All 8 are already real, fully-castable spells in this project (Phase
# 621's own 13-candidate `Set_Spell` scope already includes every one
# of them) -- 3 character-targeted, 1 no-target, 4 province-targeted,
# and critically none is `Kill_Enemy`, so `turn/feature_power_
# execution.py _resolve_terrain_spell()` (already handling exactly
# this targeting dispatch) can cast any of them unmodified.
CHANCE_SPELL_TABLE = (
    Spell.ORATORY,
    Spell.CLAIRVOYANCE,
    Spell.BLESS,
    Spell.SKELETAL_ARMY,
    Spell.EARTHQUAKE,
    Spell.PLAGUE,
    Spell.TORNADO,
    Spell.ILLUS_ARMIES,
)


def derive_chance_sub_power(gameturn: int, gdday: int) -> Power:
    """`Power.CHANCE`'s own sub-power selector: `(gameturn + gdday) AND
    7` indexes a fixed 8-residue table, deterministic and RNG-free (the
    real randomness -- which ability, which spell -- lives downstream,
    in each sub-power's own already-implemented effect). See this
    module's own Phase 622 addendum above for sourcing.
    """

    residue = (gameturn + gdday) & 7
    return _CHANCE_SUB_POWER_BY_RESIDUE[residue]
