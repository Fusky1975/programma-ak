"""Thief Ability Level Schedule (Phase 899): ``AKGEN.EXE``'s own build of
``spabord[Thief]`` -- which Advanced Ability a Thief character is
granted at each of skill levels 5-10, per game.

One of 7 categories closing **backlog item #6** in this same phase --
see ``tactical_ability_level_schedule.py``'s own module docstring for
the full source (``SANAMEDUMP.md``), the ``cumulative``/32000 algorithm
derivation and its empirical cross-check against Naval/Explorer, and the
honest confidence-level caveat (one worked example per new category,
not two). Duplicated here per this project's own "small, duplicated
per-consumer" convention, not re-derived.

**Thief's own real template, source order 1-6** (``SANAMEDUMP.md``'s own
"Prosa associata" table): ``THIEF_BANDITRY, [mastery], THIEF_PIRACY,
[mastery], THIEF_TREASURY_RAIDS, [mastery]`` -- "15% Stealing Bonus"
(the ``THIEF_MASTERY_*`` tagline every one of ``models/advanced_
ability.py``'s own 5 pre-existing ``THIEF_MASTERY_I``..``_V`` ordinals
shares identically) recurs 3 times (source positions 2/4/6), always the
identical SANAME row. Assigned here to ``THIEF_MASTERY_I``/``_II``/
``_III`` respectively -- an arbitrary, documented choice among 5
textually-interchangeable, already-sourced ordinals (the source data
itself never distinguishes which numbered tier goes with which build
position); ``THIEF_MASTERY_IV``/``_V`` are correctly left unused by this
template.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

IRAND_RANGE_ORDINARY = 32000

THIEF_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.THIEF_BANDITRY,
    AdvancedAbility.THIEF_MASTERY_I,
    AdvancedAbility.THIEF_PIRACY,
    AdvancedAbility.THIEF_MASTERY_II,
    AdvancedAbility.THIEF_TREASURY_RAIDS,
    AdvancedAbility.THIEF_MASTERY_III,
)

# TACTICAL, NAVAL, ARCHERY, MELEE, WHITE, NECROMANCY, ELEMENTAL, PSYCHIC,
# ILLUSION, DRUID -- the 10 categories built before THIEF (Ability
# ordinal 11), MARCH excluded (confirmed zero-cost).
_ABILITIES_BEFORE_THIEF_COUNT = 10


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


def build_thief_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Thief]`` level assignment
    -- ``{level (5..10): AdvancedAbility}``. See ``tactical_ability_
    level_schedule.py``'s own module docstring for the confidence level
    (one worked example, not two).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in range(_ABILITIES_BEFORE_THIEF_COUNT):
        _run_cumulative_selection(rng)

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: THIEF_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
