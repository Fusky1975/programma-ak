"""Tactical Ability Level Schedule (Phase 899): ``AKGEN.EXE``'s own build
of ``spabord[Tactical]`` (``CTBOTH.PAS``, ``array[Ability, 1..6] of
AdvancedAbility``) -- which Advanced Ability a Tactical character is
granted at each of skill levels 5-10, per game.

**Closes backlog item #6** ("contenuto template ``spabord`` per
Tattica/Arceria/Mischia/Druidismo/Ladro/Saggezza/Spia"): the 7 categories
whose own real ``spabord`` template content ``special_ability_level_
schedule.py``'s own docstring names as "not in the available material" --
``NAVAL``/``EXPLORER`` (the other two non-magic, non-``MARCH`` categories
in that same bucket) were already closed separately (Phases 508/787).
This phase and its 6 siblings (``archery_``/``melee_``/``druid_``/
``thief_``/``sage_``/``spy_ability_level_schedule.py``) close the
remaining 7 at once, from one shared source document.

**Source: ``SANAMEDUMP.md``** (user-supplied reverse-engineering
document, 2026-09-24, a full static dump/disassembly of ``SANAME.X2``
cross-referenced against ``AKGEN.EXE``). Its own "Secondo
approfondimento" section reconstructs, byte-for-byte:

- The real per-``game_number`` seed: ``RandSeed := LongInt(SmallInt(Word(
  50 * game_number)))`` -- a *signed* 16-bit truncation, matching this
  project's own already-established ``(50 * game_number) % 2**32``
  convention (``PascalRandom``'s own modular arithmetic already produces
  the same result: a negative product wraps to the same value a signed
  16-bit truncation would).
- 3 discarded ``IRand`` calls before any real construction begins.
- The 90-byte "initial values" table for all 15 abilities (6 raw slots
  each, in insertion order ``j=1..6`` -- **not** the final level order),
  transcribed directly from the document's own "Tutti i valori iniziali"
  table below.
- The redistribution algorithm itself: for each ability, ``retryCounter``
  starts at 3 **once** (not reset per source) and grows on every
  rejected draw; ``ForcedMarch`` (``Ability.MARCH``) alone skips the
  draw entirely (``slot := j``, zero-cost, already known).

**Which algorithm variant, empirically resolved, not taken on the
document's own word.** ``SANAMEDUMP.md`` itself claims ``IRand = Trunc(
Random * 32000)`` for this exact routine -- the same claim a separate,
earlier document made and this project's own ``pascal_random.py``
(Phase 755) already investigated and *rejected*, because it broke the
already-verified real GW900 magic-college schedule under the alternative
(``special_ability_level_schedule.py``'s own ``reset-per-source``/32768
convention). Re-investigated here rather than assumed either way, by
testing both candidate algorithms against every already-independently-
verified real anchor this project has:

- The 5 magic colleges (``game_number=900``, ``special_ability_level_
  schedule.py``'s own ``GAME_900_EXPECTED``) reproduce **exactly** under
  ``reset-per-source``/32768 -- confirms Phase 755 was right to keep
  that constant for the magic-college call site specifically.
- ``NAVAL_TEMPLATE``'s and ``EXPLORER_TEMPLATE``'s own already-shipped,
  dual-anchored real schedules (``game_number`` 3 **and** 900 each --
  ``naval_ability_level_schedule.py``/``explorer_ability_level_
  schedule.py``, Phases 787/508) reproduce **exactly**, for all 4
  worked examples, only under ``cumulative``/32000 (``tries`` never
  reset within an ability's own 6-source build) -- the same algorithm
  ``SANAMEDUMP.md`` describes, just confirmed against real anchors
  ``SANAMEDUMP.md`` itself never cites (GW900 for both Naval and
  Explorer came from this project's own prior, independent sourcing,
  not from this document).
- Running ``SANAMEDUMP.md``'s own ``cumulative``/32000 procedure
  uniformly from ``TACTICAL`` through ``SAGE`` reproduces its own
  published ``game_number=3`` table for all 15 categories in one pass,
  *and* independently reproduces the real GW900 Naval/Explorer results
  above -- a genuine, non-circular cross-check.

**Conclusion**: two real, genuinely different algorithms exist at the
Pascal source level for this one conceptual "build a 6-slot spabord
category" operation -- ``reset-per-source``/32768 for the 5 magic
colleges, ``cumulative``/32000 for every ordinary (non-magic,
non-``MARCH``) category, matching ``naval_ability_level_schedule.py``'s
own already-accepted "two distinct behaviors, documented, not silently
smoothed over" finding. This module (and its 6 siblings) use
``cumulative``/32000, matching Naval/Explorer's own established real
call-site behavior -- not a guess re-litigated per category, but the
same convention proven correct for the 2 other ordinary categories
already checked against real data.

**Honesty about the confidence level, per the user's own explicit
request to proceed despite it**: unlike Naval/Explorer, this project has
only **one** worked example per new category here --
``SANAMEDUMP.md``'s own ``game_number=3`` table, itself computed with
this same ``cumulative``/32000 procedure (so it is *internally
consistent*, not independent confirmation the way a second, real
save-file-derived anchor would be). Backlog item #6 named exactly this
gap ("un esempio lavorato... per queste categorie", plural, "like the
ones already had for GW3/GW900"). Shipped anyway, on the strength of the
algorithm-uniformity argument above (a real algorithm applies to a
category or it doesn't -- there's no reason ``TACTICAL`` specifically
would behave differently from ``NAVAL``/``EXPLORER``, its own immediate
neighbors in the exact same "ordinary category" bucket), not silently
presented as equally certain. Revisit if a second, independently-sourced
worked example for any of these 7 categories ever surfaces.

**Tactical's own real template, source order 1-6** (``SANAMEDUMP.md``'s
own "Prosa associata a ogni inserimento" table, Tactical rows):
``TACTICAL_WARGAMES_MASTERY, TACTICAL_MASTERY_15, ADAPT_TACTICS_TO_
TERRAIN, TACTICAL_MASTERY_15, TACTICAL_COMBINED_ARMS, TACTICAL_MASTERY_
15`` -- the 15%-tier repeats 3 times (source positions 2/4/6), while
``TACTICAL_MASTERY_10``/``_20`` never appear in the initial-values table
at all. ``SANAMEDUMP.md``'s own "Cinque descrizioni non raggiunte da
questa tabella iniziale" section confirms this structurally: those two
specific rows are **never** selected by this construction, for *any*
``game_number`` -- not merely rare, genuinely unreachable. The repeated
15%-tier reuses the single existing ``AdvancedAbility.TACTICAL_MASTERY_
15`` member 3 times, the same ``set``-collapse Naval's own real template
already accepts (``NAVAL_MASTERY_GREAT_15`` repeated 3 times) rather
than inventing a distinguishing ordinal this project's own sourced pool
never gave Tactical.

``TACTICAL`` is ``Ability`` ordinal 0 -- the very first category built,
right after the 3 discarded ``IRand`` calls, with no preceding category
to skip past.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

# Confirmed for every ordinary (non-magic, non-MARCH) category -- see
# module docstring's own empirical cross-check against Naval/Explorer.
IRAND_RANGE_ORDINARY = 32000

# `SANAMEDUMP.md`'s own real `spabord[Tactical]` template, source order
# 1-6. `TACTICAL_MASTERY_10`/`_20` never appear (confirmed structurally
# unreachable) -- only the 15% tier, repeated.
TACTICAL_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.TACTICAL_WARGAMES_MASTERY,
    AdvancedAbility.TACTICAL_MASTERY_15,
    AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN,
    AdvancedAbility.TACTICAL_MASTERY_15,
    AdvancedAbility.TACTICAL_COMBINED_ARMS,
    AdvancedAbility.TACTICAL_MASTERY_15,
)


def _irand_ordinary(rng: PascalRandom) -> int:
    """An ordinary (non-magic, non-``MARCH``) category's own call site:
    ``Trunc(Random * 32000)`` -- see module docstring."""

    return int(rng.random() * IRAND_RANGE_ORDINARY)


def _run_cumulative_selection(rng: PascalRandom) -> dict[int, int]:
    """The confirmed ordinary-category algorithm: ``tries`` starts at 3
    once per *ability* (not reset per source) and grows cumulatively
    across all 6 sources' own collisions/retries -- identical shape to
    ``naval_``/``explorer_ability_level_schedule.py``'s own copies,
    duplicated here per this project's own "small, duplicated
    per-consumer" convention.
    """

    occupied: set[int] = set()
    dest_of_s: dict[int, int] = {}
    tries = 3
    for s in range(1, 7):
        while True:
            n = min(20, tries // 2 + (s + 1) // 2)
            dest = 1 + _irand_ordinary(rng) % n
            if dest > 6 or dest in occupied:
                tries += 1
                continue
            break
        occupied.add(dest)
        dest_of_s[s] = dest
    return dest_of_s


def build_tactical_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Tactical]`` level
    assignment -- ``{level (5..10): AdvancedAbility}``. See module
    docstring for the confidence level (one worked example, not two).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: TACTICAL_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
