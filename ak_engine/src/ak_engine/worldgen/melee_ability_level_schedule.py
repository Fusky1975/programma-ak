"""Melee Ability Level Schedule (Phase 899): ``AKGEN.EXE``'s own build of
``spabord[Melee]`` -- which Advanced Ability a Melee character is
granted at each of skill levels 5-10, per game.

One of 7 categories closing **backlog item #6** in this same phase --
see ``tactical_ability_level_schedule.py``'s own module docstring for
the full source (``SANAMEDUMP.md``), the ``cumulative``/32000 algorithm
derivation and its empirical cross-check against Naval/Explorer, and the
honest confidence-level caveat (one worked example per new category,
not two). Duplicated here per this project's own "small, duplicated
per-consumer" convention, not re-derived.

**Melee's own real template, source order 1-6** (``SANAMEDUMP.md``'s own
"Prosa associata" table): ``MELEE_EVASION, MELEE_MASTERY, MELEE_CONTROL_
TEMPER, MELEE_MASTERY, MELEE_HIT_POINTS, MELEE_MASTERY`` -- "10% Bonus,
Plus 1 Damage" (``MELEE_MASTERY``'s own real row) recurs 3 times (source
positions 2/4/6), always the identical SANAME row. **Deliberately not
using ``AdvancedAbility.MELEE_TRUE_MASTERY`` for any of these 3
repeats**, unlike Archery's own same-shaped case: ``MELEE_TRUE_MASTERY``'s
own sourced tagline ("Plus 2 Damage") is materially different from
``MELEE_MASTERY``'s own ("10% Bonus, Plus 1 Damage"), not a same-text
alternate ordinal the way Archery's 3 Free-Attack tiers are -- using it
here would assert a stronger, textually distinct grant the source data
never actually shows at any of these 3 real slots. ``MELEE_DUELLISTS_
MEDAL`` and ``MELEE_TRUE_MASTERY`` both stay outside this template
entirely: the former is one of ``SANAMEDUMP.md``'s own confirmed
structurally-unreachable rows ("Cinque descrizioni non raggiunte da
questa tabella iniziale"), the latter simply never appears in the
initial-values table for Melee at all -- if it has a real basis
anywhere, it is a separate, not-yet-understood mechanism, not this one.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

IRAND_RANGE_ORDINARY = 32000

MELEE_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.MELEE_EVASION,
    AdvancedAbility.MELEE_MASTERY,
    AdvancedAbility.MELEE_CONTROL_TEMPER,
    AdvancedAbility.MELEE_MASTERY,
    AdvancedAbility.MELEE_HIT_POINTS,
    AdvancedAbility.MELEE_MASTERY,
)

# TACTICAL, NAVAL, ARCHERY -- the 3 ordinary categories built before
# MELEE (Ability ordinal 4), MARCH excluded (confirmed zero-cost).
_ABILITIES_BEFORE_MELEE_COUNT = 3


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


def build_melee_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Melee]`` level assignment
    -- ``{level (5..10): AdvancedAbility}``. See ``tactical_ability_
    level_schedule.py``'s own module docstring for the confidence level
    (one worked example, not two).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in range(_ABILITIES_BEFORE_MELEE_COUNT):
        _run_cumulative_selection(rng)

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: MELEE_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
