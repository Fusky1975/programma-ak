"""Druid Ability Level Schedule (Phase 899): ``AKGEN.EXE``'s own build of
``spabord[Druid]`` -- which Advanced Ability a Druid character is
granted at each of skill levels 5-10, per game.

One of 7 categories closing **backlog item #6** in this same phase --
see ``tactical_ability_level_schedule.py``'s own module docstring for
the full source (``SANAMEDUMP.md``), the ``cumulative``/32000 algorithm
derivation and its empirical cross-check against Naval/Explorer, and the
honest confidence-level caveat (one worked example per new category,
not two). Duplicated here per this project's own "small, duplicated
per-consumer" convention, not re-derived.

**Druid's own real template, source order 1-6** (``SANAMEDUMP.md``'s own
"Prosa associata" table): ``DRUIDIC_HORSE_CONTROL, DRUIDIC_WHALE_
TRANSPORT, DRUIDIC_TRADES, DRUIDIC_ANIMAL_SPIES, DRUIDIC_DINOSAURS,
DRUIDIC_TRANSPORT`` -- the only one of these 7 categories whose real
template uses **all 6** of its own sourced pool members exactly once
each, no repeats and no unreachable rows.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

IRAND_RANGE_ORDINARY = 32000

DRUID_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.DRUIDIC_HORSE_CONTROL,
    AdvancedAbility.DRUIDIC_WHALE_TRANSPORT,
    AdvancedAbility.DRUIDIC_TRADES,
    AdvancedAbility.DRUIDIC_ANIMAL_SPIES,
    AdvancedAbility.DRUIDIC_DINOSAURS,
    AdvancedAbility.DRUIDIC_TRANSPORT,
)

# TACTICAL, NAVAL, ARCHERY, MELEE, WHITE, NECROMANCY, ELEMENTAL, PSYCHIC,
# ILLUSION -- the 9 categories built before DRUID (Ability ordinal 10),
# MARCH excluded (confirmed zero-cost).
_ABILITIES_BEFORE_DRUID_COUNT = 9


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


def build_druid_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Druid]`` level assignment
    -- ``{level (5..10): AdvancedAbility}``. See ``tactical_ability_
    level_schedule.py``'s own module docstring for the confidence level
    (one worked example, not two).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in range(_ABILITIES_BEFORE_DRUID_COUNT):
        _run_cumulative_selection(rng)

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: DRUID_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
