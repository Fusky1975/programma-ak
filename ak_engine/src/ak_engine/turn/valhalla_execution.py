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

**Wired into ``turn/turn_processor.py``'s own ``run_turn()`` as of
Phase 199** (its own "GATE ANGEL / VALHALLA VISIT" docstring section):
``finalize_gate_angel_visit()`` below is called exactly once per turn,
after every leader's Cast phase has been dispatched -- calling it any
earlier would risk picking the wrong kingdom's hero, since a later
same-turn, same-due-alignment cast can still steal the reservoir-
sampling win. This mirrors the "implement the execution function, wire
it into the real dispatch loop in a later phase" split this project
already used for Cast execution itself (Phase 172 implemented
``_execute_charm``/``_execute_kill_enemy`` as standalone, tested
functions; Phase 173 wired them into ``plan_dispatch.py``).

**Phase 386 correction**: "reservoir sampling" above is legacy
terminology -- ``turn/cast_execution.py _gate_angel_register_candidate``
no longer does that (see its own docstring for the real, non-uniform
contention rule); the *shape* described here (later same-turn candidates
can still overwrite the current winner, so this module must run last)
is unchanged. This phase also replaces this module's own ``rng.choice(
roster)`` hero pick with the real ``visitor_selection`` algorithm --
see ``_select_visitor_template()`` below.

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

**Phase 546**: a monster/Valhalla audit re-found this module's own
prior "not modeled" list -- the escalating per-visit phase allowance
and the fixed item's own tracked ``item_id`` are now recorded at spawn
time (``LeaderState.valhalla_active_turn``/``valhalla_allowed_phase_
count``/``valhalla_fixed_item_id`` -- see ``models/valhalla.py
_valhalla_stay_phase_count()`` for the escalating table itself). **Not
yet enforced** (Phase 547/548's own scope): ``turn/plan_dispatch.py``
doesn't cap phases at dispatch yet, ``turn/cast_execution.py`` doesn't
grant spell-immunity except Resurrection yet, ``turn/trade_execution.py``
doesn't block Give on the fixed item yet, and no departure/army-hand-
off/loot-routing processing runs at all yet -- this leader is still
dispatched exactly like any other for now. **Turn-deadline voiding
stays confirmed out of scope entirely**: this codebase has no in-engine
"did this Kingdom miss the deadline" detector at all (``turn/missed_
deadline.py``'s own module docstring -- it's an external, caller-level
fact nothing in ``GameState`` tracks), so there's no hook to attach
this rule to without inventing an external contract this project
doesn't otherwise have.
"""

from __future__ import annotations

import math
import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.valhalla import (
    VALHALLA_ROSTER,
    VALHALLA_VISITOR_LEADER_ID,
    ValhallaHero,
    _valhalla_stay_phase_count,
)


def _select_visitor_template(
    state: GameState, alignment: Alignment, roster: tuple[ValhallaHero, ...], rng: random.Random
) -> ValhallaHero:
    """AKGEN's own confirmed ``visitor_selection`` (Phase 386, replacing
    the earlier ``rng.choice(roster)`` placeholder): "turns 1-5 always
    [use the] final roster record" -- confirmed by name, not just shape:
    every one of this project's own 5 ``VALHALLA_ROSTER`` alignment
    lists already ends with exactly the hero the source's own
    ``distributed_defaults`` names for that alignment (Good/Quintilian,
    Druidic/Bo, Neutral/Kitralus, Pagan/Kelderek, Evil/Dietrich) -- a
    5-for-5 exact match. From turn 6 on: "(IRand MOD choices)+1 on first
    invocation," then "advance with a randomly signed coprime stride,
    producing a full permutation before repetition" -- the stride is
    drawn once (uniformly among the roster-size's own coprime residues)
    the first time this alignment is selected after turn 5, then reused
    every later call, guaranteeing (by the standard modular-arithmetic
    fact that a coprime step cycles through every residue before
    repeating) that no hero repeats until the whole roster has been
    visited. The source doesn't pin down exactly *how* the coprime
    stride itself is chosen among the valid candidates -- picked
    uniformly among them here, an honest, undocumented parameter choice
    in an otherwise exactly-confirmed algorithm shape.
    """

    if state.turn_number <= 5:
        return roster[-1]

    n = len(roster)
    if n == 1:
        return roster[0]

    sequence = state.valhalla_visitor_sequence.get(alignment)
    if sequence is None:
        index = rng.randrange(n)
        coprime_strides = [s for s in range(1, n) if math.gcd(s, n) == 1]
        stride = rng.choice(coprime_strides) if coprime_strides else 1
        step = rng.choice((1, -1)) * stride
    else:
        previous_index, step = sequence
        index = (previous_index + step) % n

    state.valhalla_visitor_sequence[alignment] = (index, step)
    return roster[index]


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
    template = _select_visitor_template(state, state.gate_angel_due_alignment, roster, rng)

    kingdom = state.kingdoms[kingdom_id]
    king = next(
        (leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king),
        None,
    )
    location = king.location if king is not None else kingdom.home_province

    # Phase 546 -- the visitor's own one active turn is the turn *after*
    # this one: this function runs in run_turn()'s own end-of-turn tail,
    # after this turn's own phase-dispatch loop already ran, so the
    # visitor genuinely can't act until state.turn_number + 1. See
    # models/valhalla.py _valhalla_stay_phase_count()'s own docstring
    # for the escalating phase-count table this turn number drives.
    active_turn = state.turn_number + 1
    visitor = LeaderState(
        leader_id=VALHALLA_VISITOR_LEADER_ID,
        kingdom_id=kingdom_id,
        name=template.name,
        location=location,
        skills=template.skills,
        temper=template.temper,
        alignment=template.true_alignment,
        race=template.race,
        valhalla_active_turn=active_turn,
        valhalla_allowed_phase_count=_valhalla_stay_phase_count(active_turn),
    )
    state.leaders[visitor.leader_id] = visitor

    if template.fixed_item is not None:
        item = state.add_item(template.fixed_item, owner_leader_id=visitor.leader_id)
        visitor.valhalla_fixed_item_id = item.item_id

    return visitor
