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

**Gate: only once the 350 cap is actually exceeded.** The rulebook's
own two sentences read together: the first states the cap and its
consequence causally ("perciò" -- therefore) in general terms ("dopo le
prime fasi", once the world has been running long enough to matter);
the second gives the literal trigger condition in the clearest terms
this text offers ("quando si supera il limite di 350"). That second
sentence is what `decompose_graveyard()` implements as its gate -- a
documented reading, not the only grammatically possible one, but the
more literal of the two available.

**Rate: ~10% of the graveyard's own size, rounded, each qualifying
call.** "Un 10% circa" (about 10%) of the *previously-destroyed* pool
-- not 10% of the excess over 350, and not stochastic (no roll is
described): `round(total_dead * GRAVEYARD_DECAY_FRACTION)`, the same
"round() for an approximate rulebook percentage" precedent `turn/
spy_table.py`'s own Spy Table formula already established. No invented
minimum-of-1 floor: a small graveyard can legitimately round to 0 removed
even while the world is over cap.

**Priority: oldest-destroyed first.** Since no turn-stamp exists
anywhere in this project (``GraveyardEntry``'s own Phase 60 note),
``GraveyardEntry.death_seq`` (Phase 309, a monotonic insertion-order
counter `GameState.record_battle_death()` stamps) stands in for real
recency, exactly precise enough for "which died longest ago" without
inventing a broader turn-history log.

**Wired once per game turn**, at the same end-of-`run_turn()` point
`turn/turn_processor.py`'s own Gate Angel visit and Analytical
Psychology revert already run -- the one unambiguous "once per turn"
boundary this project's phase-by-phase loop offers.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState

WORLD_UNIT_CAP = 350
GRAVEYARD_DECAY_FRACTION = 0.10


def decompose_graveyard(state: GameState) -> int:
    """Prunes the oldest ``battle_graveyard`` entries once the world's
    total living+dead unit count exceeds ``WORLD_UNIT_CAP`` -- see module
    docstring for the gate/rate/priority reasoning. Returns how many
    entries were removed (0 if under the cap, or if the graveyard is too
    small for ~10% to round up to at least 1).
    """

    total_dead = sum(len(entries) for entries in state.battle_graveyard.values())
    total_world_units = len(state.armies) + total_dead
    if total_world_units <= WORLD_UNIT_CAP:
        return 0

    decay_count = round(total_dead * GRAVEYARD_DECAY_FRACTION)
    if decay_count <= 0:
        return 0

    oldest_first = sorted(
        ((coord, entry) for coord, entries in state.battle_graveyard.items() for entry in entries),
        key=lambda pair: pair[1].death_seq,
    )
    for coord, entry in oldest_first[:decay_count]:
        remaining = state.battle_graveyard[coord]
        remaining.remove(entry)
        if not remaining:
            del state.battle_graveyard[coord]

    return decay_count
