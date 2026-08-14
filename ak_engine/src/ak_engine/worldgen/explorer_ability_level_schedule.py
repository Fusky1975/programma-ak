"""Explorer Ability Level Schedule (Phase 508): ``AKGEN.EXE``'s own build of
``spabord[Explorer]`` (``CTBOTH.PAS``, ``array[Ability, 1..6] of
AdvancedAbility``) -- which Advanced Ability an Explorer character is
granted at each of skill levels 5-10, per game.

Source: ``AKGEN_reverse_engineering_report (3).md`` Part IV, section 48
("Algoritmo ``SRnts``: assegnazione occulta 5-10"), quoting the
disassembled pseudocode literally::

    RandSeed := 50 * game_number;
    IRand; IRand; IRand;                 {tre estrazioni scartate}
    for ab := Tactical to Sage do begin
      tries := 3;                        {una volta per talento}
      for source := 1 to 6 do begin
        n := Min(20, (tries div 2) + ((source + 1) div 2));
        dest := 1 + (IRand mod n);
        {... reject dest>6 or already occupied, else claim it ...}
        Inc(tries);
      end;
    end;

with ``IRand = Trunc(Random * 32000)`` -- the source's own explicit claim,
distinct from the 32768 range confirmed elsewhere (see below).

**Why this module doesn't reuse ``special_ability_level_schedule.py``'s own
``_run_generic_selection``**: that function's own tries-reset-per-source
and 32768 ``IRand`` range is independently verified exactly against all 5
magic colleges (see that module's own docstring -- 5-for-5 match,
including exact ``IRand`` call counts). Taking this dossier's own textual
claims (``tries`` cumulative *per ability*, not per source; ``IRand``
scaled by 32000, not 32768) at face value for the magic colleges was tried
and definitively fails there (breaks the already-verified White Magic
result). But taken literally for *Explorer specifically* -- reseeding
once, discarding 3, then running this same cumulative/32000 algorithm
continuously through 11 preceding builds (``TACTICAL, NAVAL, ARCHERY,
MELEE, WHITE, NECROMANCY, ELEMENTAL, PSYCHIC, ILLUSION, DRUID, THIEF`` --
``MARCH`` excluded, zero-cost; Explorer's own real ordinal position,
``Ability`` index 12) before capturing Explorer's own result -- reproduces
BOTH of the dossier's own worked examples exactly:

- **GW3** (``game_number=3``, independently confirmed real via the local
  ``GW3__T1`` world file's own parsed header): L5 Difficult Terrain, L6
  Find Water, L7 Military Maps, L8 Society Maps, L9 Find Mines, L10
  Long-Range Trade Routes.
- **GW900** (``game_number=900``, not independently confirmed via a local
  file, taken as literal from the dossier's own worked example): L5
  Military Maps, L6 Difficult Terrain, L7 Find Mines, L8 Society Maps, L9
  Find Water, L10 Long-Range Trade Routes.

A brute-force sweep across {reset, cumulative} tries x {32768, 32000}
``IRand`` range x discard offsets 0-4 x pre-Explorer build counts 0-15
(320 combinations) found exactly **one** combination matching both worked
examples simultaneously -- this one. That two independent real games both
land on the same unique combination is strong evidence this is the real
algorithm for Explorer's own build, not a coincidental match.

**Unresolved but accepted**: why Explorer's own real call site would use a
different ``tries``-reset convention and ``IRand`` scale than the magic
colleges', despite the dossier's own pseudocode presenting ``for ab :=
Tactical to Sage`` as one uniform loop. Turbo Pascal 6 does not guarantee
identical inlined code at every call site of a shared routine, and without
further disassembly this project has no way to resolve *why* -- only
*that* the empirical evidence (5-for-5 magic colleges under one
convention, 2-for-2 Explorer under another) points to two distinct
behaviors. Documented, not silently smoothed over.

**Deliberately still out of scope**: ``TACTICAL``/``NAVAL``/``ARCHERY``/
``MELEE``/``DRUID``/``THIEF``'s own real template content isn't in the
available material (same gap ``special_ability_level_schedule.py``
documents) -- they're still correctly *consumed* here (needed to reach
Explorer's own build) without their concrete level-by-level result being
exposed.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.enums import Ability
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

# Explorer's own call site: `Trunc(Random * 32000)`, not the standard
# 32768-range `IRand` used by the magic-college routine -- see module
# docstring.
IRAND_RANGE_EXPLORER = 32000

# `runtime_mechanics.special_ability_level_schedule`'s real spabord[Explorer]
# template, source order 1-6 (dossier file offset 0x6053C).
EXPLORER_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN,
    AdvancedAbility.EXPLORER_MILITARY_MAPS,
    AdvancedAbility.EXPLORERS_SOCIETY_MAPS,
    AdvancedAbility.EXPLORER_FIND_WATER,
    AdvancedAbility.EXPLORER_FIND_MINES,
    AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES,
)

# The 11 abilities built (and so consuming real IRand calls) before
# EXPLORER in `Ability`'s own real CTBOTH.PAS declaration order --
# `MARCH` excluded (confirmed zero-cost, see special_ability_level_
# schedule.py). Their own content is unknown and irrelevant to this
# phase; only how many IRand calls their own builds consume matters.
_ABILITIES_BEFORE_EXPLORER: tuple[Ability, ...] = tuple(
    ability
    for ability in tuple(Ability)[: tuple(Ability).index(Ability.EXPLORER)]
    if ability is not Ability.MARCH
)


def _irand_32000(rng: PascalRandom) -> int:
    """Explorer's own call site: ``Trunc(Random * 32000)`` -- distinct
    from the standard 32768-range ``IRand`` (see module docstring)."""

    return int(rng.random() * IRAND_RANGE_EXPLORER)


def _run_cumulative_selection(rng: PascalRandom) -> dict[int, int]:
    """Explorer's own build algorithm: ``tries`` starts at 3 once per
    *ability* (not reset per source, unlike the magic-college routine) and
    grows cumulatively across all 6 sources' own collisions/retries."""

    occupied: set[int] = set()
    dest_of_s: dict[int, int] = {}
    tries = 3
    for s in range(1, 7):
        while True:
            n = min(20, tries // 2 + (s + 1) // 2)
            dest = 1 + _irand_32000(rng) % n
            if dest > 6 or dest in occupied:
                tries += 1
                continue
            break
        occupied.add(dest)
        dest_of_s[s] = dest
    return dest_of_s


def build_explorer_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Explorer]`` level assignment
    -- ``{level (5..10): AdvancedAbility}``. Verified exactly against both
    the GW3 and GW900 worked examples (see module docstring).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in _ABILITIES_BEFORE_EXPLORER:
        _run_cumulative_selection(rng)

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: EXPLORER_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
