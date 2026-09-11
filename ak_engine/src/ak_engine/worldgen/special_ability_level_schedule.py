"""Special Ability Level Schedule (Phase 384): ``AKGEN.EXE``'s own build
of ``spabord`` (``CTBOTH.PAS``, ``array[Ability, 1..6] of AdvancedAbility``
-- which Advanced Ability (Phase 128/131) a character is granted at each
of skill levels 5-10 within a category, per game).

Source: ``runtime_mechanics.special_ability_level_schedule``. This closes
a gap Phase 382 documented as an unreproduced negative result -- that
conclusion was wrong, not because the source data was insufficient, but
because of two mistaken assumptions in the earlier attempt (see below).
Corrected after being asked directly what the blocker was.

**The two mistakes the earlier attempt made**:

1. It reseeded ``RandSeed`` independently *per ability* (``50 *
   game_number`` fresh for each of the 5 magic colleges). The real
   routine reseeds **once** for the entire 15-ability ``spabord`` table,
   discards exactly 3 ``IRand`` calls once, and then builds all 15
   abilities' own 6-slot schedules back-to-back from that single
   continuous stream -- never reseeding between abilities.
2. It only tried discard offsets 0-40 looking for where the White Magic
   college's own worked example would start. Because the magic colleges
   are not the first abilities built, White Magic doesn't actually
   start until *99 further calls* have already been consumed by
   whatever precedes it -- far outside that window.

**What closes the gap**: this project's own pre-existing ``Ability``
enum (``models/enums.py``, real ``CTBOTH.PAS`` declaration order) lines
up exactly with ``spabord``'s own build order: ``TACTICAL, MARCH,
NAVAL, ARCHERY, MELEE, WHITE, NECROMANCY, ELEMENTAL, PSYCHIC, ILLUSION,
DRUID, THIEF, EXPLORER, SPY, SAGE``. The algorithm's own "March alone
uses dest=s" exception (see below) is a direct, confirmed match for
``Ability.MARCH`` sitting at ordinal 1 -- the 2nd ability built, and the
only one of the first 5 (before ``WHITE``) that consumes zero ``IRand``
calls. The other 4 (``TACTICAL``, ``NAVAL``, ``ARCHERY``, ``MELEE``)
consume the ordinary algorithm. Their own real 6-item template content
is **not** available anywhere in this project's material -- but it
doesn't need to be: the algorithm's own ``IRand`` consumption is a pure
function of the numeric destinations drawn and which destinations are
already occupied *within that one ability's own 6-slot build* -- never
a function of what the items are named. So 4 back-to-back runs of the
same generic build loop reproduce the real RNG-state handoff into
``WHITE`` exactly, without needing to know what ``TACTICAL``/``NAVAL``/
``ARCHERY``/``MELEE`` actually contain.

**Verified, not just plausible**: reseeding for game 900, discarding 3,
then running the generic build loop 4 times and continuing the *same*
stream into the 5 real magic-college templates reproduces
``game_900_magic_schedule``'s own real worked example **exactly, for
all 5 colleges in a row** -- both the resulting level assignment *and*
the exact number of ``IRand`` calls each college's own build consumed
(19/13/24/15/18). Five independent 6-item constrained permutations
matching in sequence, with call counts matching too, is not a chance
coincidence.

**The algorithm itself, as quoted by the source**: for each source
``s`` = 1..6 (in the college's own real template order), ``tries``
starts at 3; loop: ``n = min(20, tries//2 + (s+1)//2)``; draw
``dest = 1 + IRand() % n``; if ``dest > 6`` or ``dest`` is already
occupied by an earlier ``s`` in *this* ability's own build, increment
``tries`` and retry; otherwise ``s`` claims ``dest`` (mapping onto
``LEVEL_SLOTS[dest-1]``, i.e. character level ``4 + dest``).

**Real cross-check on the item identities themselves**: every one of
the 5 colleges' own 6 real template item names (``magic_templates``)
matches -- by meaning, not just count -- an existing
``models.advanced_ability.AdvancedAbility`` member already in this
project's own ``ADVANCED_ABILITY_POOL`` for that same ``Ability``
(sourced independently, from a user-supplied rulebook excerpt, not this
disassembly). Two labels differ cosmetically across the two sources
(``"White Places"`` here vs. ``HOLY_PLACES``'s own ``"Holy Places"``;
``"Necro Places"`` vs. ``DARK_PLACES``'s own ``"Dark Places"``;
``"Illusion Places"`` vs. ``ILLUSORY_PLACES``'s own ``"Illusory
Places"``) -- the same kind of cosmetic cross-source naming drift
already documented elsewhere in this project (e.g. ``ArmyType.WHALES``:
``"Whales"``/``"League"``), not a mismatch. ``MAGIC_ABILITY_TEMPLATE``
below uses this project's own ``AdvancedAbility`` vocabulary rather than
bare strings, confirmed unambiguous by this 1:1 meaning-match.

**Deliberately still out of scope**:

- ``Ability.MARCH`` itself: confirmed to use ``dest=s`` (no RNG at all,
  a pure identity mapping). **Phase 768 update**: ``ADVANCED_ABILITY_
  POOL[Ability.MARCH]`` now has the real 6 candidates in the confirmed
  real order (`Desktop/PROGRAMMA AK/MARCH.md`'s own byte-level template,
  raw ``0x604FA-0x604FF = 08 07 06 07 06 07``) -- Flood, Cavalry,
  Infantry, Cavalry Mastery, Infantry Mastery, Cavalry True Mastery.
  This module still doesn't build a concrete per-level March schedule,
  though -- how ``AdvancedAbility`` grants actually reach a live leader
  at *runtime* (as opposed to this module's own narrower world-gen-
  byte-fidelity scope) remains a separate, unresolved question, not
  attempted here.
- ``TACTICAL``/``ARCHERY``/``MELEE`` (ordinals 0, 3, 4) and
  ``DRUID``/``THIEF``/``EXPLORER``/``SPY``/``SAGE`` (ordinals 10-14):
  their own real template content isn't in the available material.
  These are still correctly *consumed* (see above) since that's needed
  to reach the magic colleges; the last 5 aren't touched at all since
  nothing downstream of ``ILLUSION`` is needed here. **``NAVAL``
  (ordinal 2) is no longer in this bucket** -- its own real template
  content and build algorithm are now known, see
  ``worldgen/naval_ability_level_schedule.py`` (Phase 787).
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.enums import Ability
from ak_engine.worldgen.pascal_random import PascalRandom

LEVEL_SLOTS: tuple[int, ...] = (5, 6, 7, 8, 9, 10)

INITIAL_DISCARDED_IRAND_CALLS = 3

# `Ability`'s own real CTBOTH.PAS declaration order (ordinals 0-14).
# `MARCH` (ordinal 1) is the confirmed zero-cost exception; every other
# member here consumes the ordinary algorithm when its own build runs.
ABILITY_BUILD_ORDER: tuple[Ability, ...] = tuple(Ability)

# The 4 abilities built (and so consuming real IRand calls) before the
# first magic college (`WHITE`) in `ABILITY_BUILD_ORDER` -- see module
# docstring. Their own content is unknown and irrelevant to this phase.
_ABILITIES_BEFORE_FIRST_MAGIC_COLLEGE = tuple(
    ability
    for ability in ABILITY_BUILD_ORDER[: ABILITY_BUILD_ORDER.index(Ability.WHITE)]
    if ability is not Ability.MARCH
)

# `runtime_mechanics.special_ability_level_schedule.magic_templates`,
# mapped onto this project's own `AdvancedAbility` vocabulary (see
# module docstring's cross-check) -- the real per-college source order
# (s=1..6) the selection algorithm draws destinations for.
MAGIC_ABILITY_TEMPLATE: dict[Ability, tuple[AdvancedAbility, ...]] = {
    Ability.WHITE: (
        AdvancedAbility.HOLY_PLACES,
        AdvancedAbility.WORDS_OF_HEALING_SPELL,
        AdvancedAbility.KNOW_ALIGNMENT_TALENT,
        AdvancedAbility.ENHANCED_HOLY_SYMBOL,
        AdvancedAbility.ENHANCED_RESURRECTION,
        AdvancedAbility.GATE_ANGEL_SPELL,
    ),
    Ability.NECROMANCY: (
        AdvancedAbility.DARK_PLACES,
        AdvancedAbility.GATE_DEMON_SPELL,
        AdvancedAbility.WITCHSIGHT_TALENT,
        AdvancedAbility.ENHANCED_SKELETAL_UNITS,
        AdvancedAbility.SCAR_TERRAIN_SPELL,
        AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS,
    ),
    Ability.ELEMENTAL: (
        AdvancedAbility.ELEMENTAL_PLACES,
        AdvancedAbility.LAVA_POOL_SPELL,
        AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS,
        AdvancedAbility.ENHANCED_EARTHQUAKE,
        AdvancedAbility.MAKE_GEMS_TALENT,
        AdvancedAbility.MYSTIC_WINDS_SPELL,
    ),
    Ability.PSYCHIC: (
        AdvancedAbility.PSYCHIC_PLACES,
        AdvancedAbility.AUGUR_COMBAT_SPELL,
        AdvancedAbility.SENSE_DANGER_TALENT,
        AdvancedAbility.ENHANCED_CHARM,
        AdvancedAbility.LOCATE_OBJECT_SPELL,
        AdvancedAbility.ENHANCED_CLAIRVOYANCE,
    ),
    Ability.ILLUSION: (
        AdvancedAbility.ILLUSORY_PLACES,
        AdvancedAbility.ILLUSORY_HERO_SPELL,
        AdvancedAbility.DETECT_ILLUSIONS_TALENT,
        AdvancedAbility.ENHANCED_INVISIBILITY,
        AdvancedAbility.ILLUSORY_FOG_SPELL,
        AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN,
    ),
}

MAGIC_COLLEGES: tuple[Ability, ...] = tuple(MAGIC_ABILITY_TEMPLATE)


def _run_generic_selection(rng: PascalRandom) -> dict[int, int]:
    """The confirmed algorithm: for each source ``s``=1..6, draw a
    destination 1..6 (rejecting duplicates/out-of-range), consuming
    real ``IRand`` calls along the way. Content-independent -- used
    both to build a real college's schedule and to correctly advance
    the RNG stream past an ability whose own template isn't known.
    """

    occupied: set[int] = set()
    dest_of_s: dict[int, int] = {}
    for s in range(1, 7):
        tries = 3
        while True:
            n = min(20, tries // 2 + (s + 1) // 2)
            dest = 1 + rng.irand() % n
            if dest > 6 or dest in occupied:
                tries += 1
                continue
            break
        occupied.add(dest)
        dest_of_s[s] = dest
    return dest_of_s


def build_magic_ability_level_schedule(
    game_number: int,
) -> dict[Ability, dict[int, AdvancedAbility]]:
    """The real, per-``game_number`` ``spabord`` level assignment for the
    5 magic colleges -- ``{level (5..10): AdvancedAbility}`` per college.
    Verified exactly against ``game_900_magic_schedule``'s own real
    worked example (see module docstring).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in _ABILITIES_BEFORE_FIRST_MAGIC_COLLEGE:
        _run_generic_selection(rng)

    schedule: dict[Ability, dict[int, AdvancedAbility]] = {}
    for ability in MAGIC_COLLEGES:
        dest_of_s = _run_generic_selection(rng)
        template = MAGIC_ABILITY_TEMPLATE[ability]
        schedule[ability] = {
            LEVEL_SLOTS[dest - 1]: template[s - 1] for s, dest in dest_of_s.items()
        }
    return schedule
