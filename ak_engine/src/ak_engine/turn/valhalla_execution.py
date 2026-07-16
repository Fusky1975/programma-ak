"""Spawning the turn's Valhalla visitor, once Gate Angel's own reservoir-
sampling winner is final -- Phase 196.

``turn/cast_execution.py _execute_gate_angel`` (Phase 194, corrected
Phase 195) already resolves *who* gets this turn's Valhalla visit
(``GameState.last_gate_angel_kingdom``/``last_gate_angel_turn``,
possibly overwritten more than once within one turn as later same-
alignment candidates win the reservoir swap -- see that module's own
"Phase 195 addendum"). This module is the second, separate stage: once
that winner is truly final (i.e. every leader's Cast phase has been
dispatched for the turn), pick a real hero from ``models/valhalla.py
VALHALLA_ROSTER`` and materialize it as a genuine ``LeaderState``.

**Deliberately not wired into ``turn/turn_processor.py``'s own
``run_turn()`` yet.** ``finalize_gate_angel_visit()`` below is a
complete, independently testable function -- the caller is responsible
for invoking it exactly once per turn, after every leader's Cast phase
has been dispatched (calling it any earlier risks picking the wrong
kingdom's hero, since a later same-turn, same-due-alignment cast can
still steal the reservoir-sampling win). This mirrors the exact
"implement the execution function, wire it into the real dispatch loop
in a later phase" split this project already used for Cast execution
itself (Phase 172 implemented ``_execute_charm``/``_execute_kill_enemy``
as standalone, tested functions; Phase 173 wired them into
``plan_dispatch.py``) -- ``turn_processor.py`` is a large, heavily
tested orchestrator, and deciding exactly *where* "the end of a turn"
lives in its own phase loop is a distinct, scoped task of its own.

**The recipient is the winning Kingdom's own King** ("I personaggi
appariranno a fianco del Re" -- the visitor spawns at the King's own
current location), found via ``LeaderState.is_king``. If the winning
Kingdom genuinely has no King on record (a state this project's own
``LeaderState.is_king`` convention doesn't otherwise guard against),
the visitor spawns at the Kingdom's own ``home_province`` instead --
an unsourced but reasonable fallback location, not a documented rule.

**The fixed magic item** (rulebook: "un oggetto magico prefissato...
che non possono dare a nessuno") is created via ``GameState.add_item()``
-- ``models/treasure.py``'s own module docstring already flags this as
the *only* real Pascal call site ``Add_Tr`` (the routine
``GameState.add_item()`` mirrors) is confirmed to have, a narrow
Valhalla-visitor special case, not a general item-generation pipeline.
Skipped entirely for the two heroes whose own ``fixed_item`` is
``None`` (see ``models/valhalla.py``'s own docstring for the two
unresolved item names) -- no item is fabricated in their place.

**Not modeled here, confirmed but out of scope** (see ``turn/
cast_execution.py``'s own "Phase 195 addendum" for the full list and
citations): the escalating per-visit action allowance, the one-
Practice-phase-only limit, spell-immunity except Resurrection, the
non-transferable/disappears-on-death item lifecycle beyond its initial
grant, army hand-off on departure, and turn-deadline voiding. Every one
of these presupposes a real, already-spawned visitor with a real stay
duration -- which this function now provides -- but wiring any of them
in is deliberately left for whichever future phase actually builds
turn-scoped visitor lifecycle tracking.
"""

from __future__ import annotations

import random

from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.valhalla import VALHALLA_ROSTER, VALHALLA_VISITOR_LEADER_ID


def finalize_gate_angel_visit(state: GameState, rng: random.Random) -> LeaderState | None:
    """Spawns this turn's Valhalla visitor, if Gate Angel produced one.

    Returns ``None`` (no state mutation at all) when no Gate Angel cast
    succeeded this turn, or (defensively; shouldn't happen once all 5
    ``turn/cast_execution.py GATE_ANGEL_ELIGIBLE_ALIGNMENTS`` have a
    real roster, as they now do) the winning turn's due alignment has
    no roster entries.
    """

    if state.last_gate_angel_turn != state.turn_number:
        return None
    kingdom_id = state.last_gate_angel_kingdom
    if kingdom_id is None:
        return None

    roster = VALHALLA_ROSTER.get(state.gate_angel_due_alignment, ())
    if not roster:
        return None
    template = rng.choice(roster)

    kingdom = state.kingdoms[kingdom_id]
    king = next(
        (leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king),
        None,
    )
    location = king.location if king is not None else kingdom.home_province

    visitor = LeaderState(
        leader_id=VALHALLA_VISITOR_LEADER_ID,
        kingdom_id=kingdom_id,
        name=template.name,
        location=location,
        skills=template.skills,
        temper=template.temper,
        alignment=template.true_alignment,
        race=template.race,
    )
    state.leaders[visitor.leader_id] = visitor

    if template.fixed_item is not None:
        state.add_item(template.fixed_item, owner_leader_id=visitor.leader_id)

    return visitor
