"""Archery Ability Level Schedule (Phase 899): ``AKGEN.EXE``'s own build
of ``spabord[Archery]`` -- which Advanced Ability an Archery character is
granted at each of skill levels 5-10, per game.

One of 7 categories closing **backlog item #6** in this same phase --
see ``tactical_ability_level_schedule.py``'s own module docstring for
the full source (``SANAMEDUMP.md``), the ``cumulative``/32000 algorithm
derivation and its empirical cross-check against Naval/Explorer, and the
honest confidence-level caveat (one worked example per new category,
not two). Duplicated here per this project's own "small, duplicated
per-consumer" convention, not re-derived.

**Archery's own real template, source order 1-6** (``SANAMEDUMP.md``'s
own "Prosa associata" table): ``ARCHERY_FREE_ATTACK, SHORT_RANGE_
ARCHERY, ARCHERY_FREE_ATTACK, LONG_RANGE_ARCHERY, ARCHERY_FREE_ATTACK,
ARCHERY_FREE_ATTACK`` in raw content -- "Bonus Archery Shot" recurs 4
times (source positions 1/3/5/6), always the *same* SANAME row, never
textually distinguished the way Tactical's/Naval's own repeated tiers
aren't either. Unlike those two, this project's own sourced pool
(``models/advanced_ability.py``) already carries 3 distinct ordinals
sharing this exact tagline (``ARCHERY_FREE_ATTACK``/``_MASTERY``/
``_TRUE_MASTERY``) -- assigned here to 3 of the 4 real occurrences
(source positions 1/3/5), with the 4th (position 6) reusing the base
member rather than inventing a 4th ordinal this project's own sourced
pool never gave Archery. Which specific occurrence maps to which named
ordinal is this phase's own arbitrary, documented choice -- the source
data itself never distinguishes them beyond "the same repeatable grant".
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

IRAND_RANGE_ORDINARY = 32000

ARCHERY_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.ARCHERY_FREE_ATTACK,
    AdvancedAbility.SHORT_RANGE_ARCHERY,
    AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY,
    AdvancedAbility.LONG_RANGE_ARCHERY,
    AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY,
    AdvancedAbility.ARCHERY_FREE_ATTACK,
)

# TACTICAL, NAVAL -- the 2 ordinary categories built before ARCHERY
# (Ability ordinal 3), MARCH excluded (confirmed zero-cost).
_ABILITIES_BEFORE_ARCHERY_COUNT = 2


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


def build_archery_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Archery]`` level
    assignment -- ``{level (5..10): AdvancedAbility}``. See
    ``tactical_ability_level_schedule.py``'s own module docstring for
    the confidence level (one worked example, not two).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in range(_ABILITIES_BEFORE_ARCHERY_COUNT):
        _run_cumulative_selection(rng)

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: ARCHERY_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
