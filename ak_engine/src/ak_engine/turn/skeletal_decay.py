"""World-wide unit cap and graveyard decomposition -- rulebook
(``Regolamento AK.txt`` [4.2.5], quoted in full): "Il numero totale di
unità militari consentito nel gioco (sia viventi che morte) è di 350,
perciò dopo le prime fasi, a ogni turno un 10% circa delle unità
distrutte in precedenza è destinato alla decomposizione. Quando si
supera il limite di 350, le unità distrutte da più lungo tempo si
decompongono automaticamente."

Phase 60's own Skeletal Army implementation (``turn/cast_execution.py
_execute_skeletal_army()``) left this half of the rule explicitly
unenforced -- see that function's own docstring and ``models/game_state.py
GameState.battle_graveyard``'s own Phase 60 note. This closes that gap.

**Only ``GameState.battle_graveyard`` entries -- destroyed armies not yet
raised -- ever decompose.** An already-risen Skeletal Army (a real,
live ``ArmyState`` with ``is_skeletal=True``) is alive, not a graveyard
entry, regardless of whether it currently has a commander -- the
rulebook's "unità distrutte" (destroyed units) names the dead pool
specifically, and this project's own "leaving/reassigning a Skeletal
Army makes it dig its own grave" mechanic ([4.2.5]'s own next
paragraph, now wired -- ``turn/plan_dispatch.py _dispatch_leave()``,
Phase 647 -- a *different*, uncommanded-army rule, not this one) is
the only sourced way a risen Skeletal Army stops existing.
Decomposition here never touches ``state.armies``.

**"Sia viventi che morte" (both living and dead)**: the 350-unit world
total is every currently-live army (``len(state.armies)``, which already
includes any risen, still-commanded Skeletal Army) plus every not-yet-
raised graveyard entry (``sum(len(v) for v in state.battle_graveyard.
values())``) -- summed across the whole world, not per-kingdom; the
source names one shared pool.

**Two mechanisms, both applied (user ruling 2026-11-25)**: the rulebook's two
sentences are read as independent rules -- (1) "dopo le prime fasi, a ogni turno un
10% circa delle unità distrutte in precedenza è destinato alla decomposizione": from
``GRAVEYARD_DECAY_FIRST_TURN`` on, each army destroyed in an *earlier* turn rots with a
10% chance every turn; (2) "quando si supera il limite di 350, le unità distrutte da più
lungo tempo si decompongono automaticamente": whenever living + dead exceed 350, the
oldest dead rot until the total is back at 350 (priority by ``GraveyardEntry.death_seq``,
a monotonic insertion order that stands in for "which died longest ago").

**Wired once per game turn**, at the same end-of-`run_turn()` point
`turn/turn_processor.py`'s own Gate Angel visit and Analytical
Psychology revert already run -- the one unambiguous "once per turn"
boundary this project's phase-by-phase loop offers.
"""

from __future__ import annotations

import random

from ak_engine.models.game_state import GameState

WORLD_UNIT_CAP = 350
GRAVEYARD_DECAY_FRACTION = 0.10
# "dopo le prime fasi": no decomposition during the first turns of a game (project-original: 3).
GRAVEYARD_DECAY_FIRST_TURN = 4


def decompose_graveyard(state: GameState, rng: random.Random | None = None) -> int:
    """Rots away graveyard entries, returning how many were removed. Two independent mechanisms
    ([4.2.5], user ruling 2026-11-25: they both apply):

    1. From ``GRAVEYARD_DECAY_FIRST_TURN`` on, every turn each army destroyed in a *previous* turn
       has a ``GRAVEYARD_DECAY_FRACTION`` (10%) chance of decomposing (needs ``rng``).
    2. Whenever the world total (living + dead) exceeds ``WORLD_UNIT_CAP``, the dead that fell
       longest ago decompose until the total is back at the cap.
    """

    removed = 0
    if rng is not None and state.turn_number >= GRAVEYARD_DECAY_FIRST_TURN:
        for coord in sorted(state.battle_graveyard, key=lambda c: (c.x, c.y)):
            kept = []
            for entry in state.battle_graveyard[coord]:
                if entry.death_turn < state.turn_number and rng.random() < GRAVEYARD_DECAY_FRACTION:
                    removed += 1
                else:
                    kept.append(entry)
            if kept:
                state.battle_graveyard[coord] = kept
            else:
                del state.battle_graveyard[coord]

    total_dead = sum(len(entries) for entries in state.battle_graveyard.values())
    excess = len(state.armies) + total_dead - WORLD_UNIT_CAP
    if excess > 0:
        oldest_first = sorted(
            ((coord, entry) for coord, entries in state.battle_graveyard.items() for entry in entries),
            key=lambda pair: pair[1].death_seq,
        )
        for coord, entry in oldest_first[:excess]:
            remaining = state.battle_graveyard[coord]
            remaining.remove(entry)
            removed += 1
            if not remaining:
                del state.battle_graveyard[coord]
    return removed
