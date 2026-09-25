"""Sage Ability Level Schedule (Phase 899): ``AKGEN.EXE``'s own build of
``spabord[Sage]`` -- which Advanced Ability a Sage character is granted
at each of skill levels 5-10, per game.

One of 7 categories closing **backlog item #6** in this same phase --
see ``tactical_ability_level_schedule.py``'s own module docstring for
the full source (``SANAMEDUMP.md``), the ``cumulative``/32000 algorithm
derivation and its empirical cross-check against Naval/Explorer, and the
honest confidence-level caveat (one worked example per new category,
not two). Duplicated here per this project's own "small, duplicated
per-consumer" convention, not re-derived.

**Sage's own real template is degenerate**: ``SANAMEDUMP.md``'s own
"Tutti i valori iniziali" table gives the *identical* raw row (84,
"SUPER SAGE, University of <0x13>: plus 1 level when researching
there") for all 6 of Sage's own insertion slots -- unlike every other
category here, there is no real content ambiguity at all, only "the
same grant, 6 times over." ``models/advanced_ability.py``'s own 5
pre-existing ``SUPER_SAGE_I``..``_V`` ordinals (all sharing this exact
tagline, "plus 5% probability when researching there") cover only 5 of
the 6 needed slots -- ``SUPER_SAGE_I`` is reused for the 6th (source
position 6) rather than inventing a 6th ordinal this project's own
sourced pool never gave Sage. Which position gets which ordinal is
arbitrary and undocumented by the source; only the reuse itself is a
real, flagged choice.

**A second, genuine and separate open question ``SANAMEDUMP.md`` itself
raises, not resolved here**: its own real ``REPORTS.PAS`` read loop
(the only known consumer of this table) only ever reads slots 1-5
(levels 5-9) -- "non è provata... l'esposizione dello slot 6 come
livello 10." Level 10's own grant is therefore computed here (for
completeness and API uniformity with every sibling module) but its own
real in-game exposure is unconfirmed.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

IRAND_RANGE_ORDINARY = 32000

SAGE_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.SUPER_SAGE_I,
    AdvancedAbility.SUPER_SAGE_II,
    AdvancedAbility.SUPER_SAGE_III,
    AdvancedAbility.SUPER_SAGE_IV,
    AdvancedAbility.SUPER_SAGE_V,
    AdvancedAbility.SUPER_SAGE_I,
)

# TACTICAL, NAVAL, ARCHERY, MELEE, WHITE, NECROMANCY, ELEMENTAL, PSYCHIC,
# ILLUSION, DRUID, THIEF, EXPLORER, SPY -- the 13 categories built before
# SAGE (Ability ordinal 14), MARCH excluded (confirmed zero-cost).
_ABILITIES_BEFORE_SAGE_COUNT = 13


def _irand_ordinary(rng: PascalRandom) -> int:
    return int(rng.random() * IRAND_RANGE_ORDINARY)


def _run_cumulative_selection(rng: PascalRandom) -> dict[int, int]:
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


def build_sage_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Sage]`` level assignment
    -- ``{level (5..10): AdvancedAbility}``. See ``tactical_ability_
    level_schedule.py``'s own module docstring for the confidence level
    (one worked example, not two), and this module's own docstring for
    level 10's own unconfirmed real exposure.
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in range(_ABILITIES_BEFORE_SAGE_COUNT):
        _run_cumulative_selection(rng)

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: SAGE_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
