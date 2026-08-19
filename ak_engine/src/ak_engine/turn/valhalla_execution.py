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
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors


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


def finalize_gate_angel_visit(state: GameState, rng: random.Random, *, board_width: int = NORMAL_MAP_BOUNDS[0]) -> LeaderState | None:
    """Spawns this turn's Valhalla visitor, if Gate Angel produced one.

    Returns ``None`` (no state mutation at all) when no Gate Angel cast
    succeeded this turn, or (defensively; shouldn't happen once all 5
    ``turn/cast_execution.py GATE_ANGEL_ELIGIBLE_ALIGNMENTS`` have a
    real roster, as they now do) the winning turn's due alignment has
    no roster entries.

    **Phase 548 bug fix**: this function used to overwrite ``state.
    leaders[VALHALLA_VISITOR_LEADER_ID]`` unconditionally -- if a prior
    visitor was still present (their own ``valhalla_active_turn`` hasn't
    been reached/processed yet this same turn), their identity was
    silently clobbered while any items/armies still referencing leader
    199 kept pointing at it, now misattributed to the new hero. A stale
    occupant is now sent through ``process_valhalla_departure()`` first
    -- the same army hand-off/item transfer a normal on-schedule
    departure gets -- before the new hero is ever assigned.
    ``board_width`` defaults to the normal board's own width (every
    existing caller/test) since departure processing only needs it for
    the adjacent-province leg of that hand-off chain.
    """

    if state.last_gate_angel_turn != state.turn_number:
        return None
    kingdom_id = state.last_gate_angel_kingdom
    if kingdom_id is None:
        return None

    roster = VALHALLA_ROSTER.get(state.gate_angel_due_alignment, ())
    if not roster:
        return None

    if VALHALLA_VISITOR_LEADER_ID in state.leaders:
        process_valhalla_departure(state, board_width=board_width)

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


def _reassign_visitor_armies(state: GameState, kingdom_id: int, location, board_width: int) -> None:
    """Phase 548 -- ``VALHALLA.txt`` rule 5: "Vahlalla visitor can lead
    armies, but when Vahlalla visitor returns to Valhalla, the armies
    will normally be left leaderless... transferred to your lowest-
    numbered leader in the same province, or at last resort, the
    garrison commander in an adjacent province owned by you. If no
    leader is available, the armies will be disbanded." No existing
    helper implements this chain (confirmed by research) -- this
    project has no modeled "garrison commander" attribute at all
    (``models/game_state.py ArmyState.commanded_by``'s own comment:
    "an army may also be unled, under the rulebook's 'garrison
    commander'" -- a concept, not a field), so "an adjacent province's
    own garrison commander" is read the same honest way as ``LeaderState.
    is_king``-first ordering below: the lowest-``leader_id`` same-
    Kingdom leader physically present there. Rule 5's own King-first
    wording isn't explicit, but every other departure rule already
    routes to the King first (rule 2's item hand-off) -- reused here for
    consistency rather than treating "lowest-numbered leader" as if it
    always meant a non-King.
    """

    armies = state.armies_commanded_by(VALHALLA_VISITOR_LEADER_ID)
    if not armies:
        return

    king = next((leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king), None)
    new_commander_id = king.leader_id if king is not None else None

    if new_commander_id is None:
        co_located = sorted(
            (leader for leader in state.leaders_at(location) if leader.leader_id != VALHALLA_VISITOR_LEADER_ID),
            key=lambda leader: leader.leader_id,
        )
        if co_located:
            new_commander_id = co_located[0].leader_id

    if new_commander_id is None:
        bounds = MapBounds(board_width, NORMAL_MAP_BOUNDS[1])
        for neighbor_coord in neighbors(location, bounds):
            province = state.provinces.get(neighbor_coord)
            if province is None or province.owner_kingdom_id != kingdom_id:
                continue
            candidates = sorted(
                (leader for leader in state.leaders_at(neighbor_coord) if leader.kingdom_id == kingdom_id),
                key=lambda leader: leader.leader_id,
            )
            if candidates:
                new_commander_id = candidates[0].leader_id
                break

    for army in armies:
        if new_commander_id is not None:
            army.commanded_by = new_commander_id
        else:
            # "the armies will be disbanded" -- same mutation turn/
            # plan_dispatch.py _dispatch_disband() itself performs.
            army.kingdom_id = None
            army.commanded_by = None


def process_valhalla_departure(state: GameState, *, board_width: int = NORMAL_MAP_BOUNDS[0]) -> None:
    """Phase 548 -- resolves the Valhalla visitor's own departure, once
    their one active turn (``LeaderState.valhalla_active_turn``, Phase
    546) has passed. Called from ``run_turn()``'s own end-of-turn tail,
    immediately after ``finalize_gate_angel_visit()`` -- see that
    function's own Phase 548 addendum for why a stale occupant is also
    routed through here before a new visitor is ever spawned.

    **Peaceful departure** (the visitor is still alive in ``state.
    leaders``): rule 5's army hand-off (``_reassign_visitor_armies()``)
    plus rule 2's own item hand-off -- every item still held by the
    visitor (their own fixed item, and any Search-loot magic item not
    already Given away -- rule 2 covers both the same way) transfers to
    the Kingdom's own King. No King on record: the items simply stay
    with the now-removed leader id, an honest edge case (this project
    has no alternative recipient named by any source for this specific
    case, unlike the army hand-off's own documented fallback chain).
    Leader 199 is then removed from ``state.leaders`` entirely -- a
    fresh hero only replaces them on the next successful Gate Angel
    cast.

    **Death departure** (the visitor died this turn -- ``GameState.
    remove_leader()`` already popped them into ``state.dead_leaders``,
    which preserves the full archived ``LeaderState``, Valhalla fields
    included, before this tail even runs): rule 7's own "l'oggetto
    sparisce" -- only the fixed item specifically is dropped (removed
    from ``state.items`` outright, given to nobody). Any other item the
    visitor happened to hold is left alone -- a real Search/Challenge/
    Pursue combat death already runs ``turn/encounter.py loot_defeated_
    leader()``, which transfers everything to the winner before this
    tail ever sees it, and Kill_Enemy (this project's other real leader-
    death spell) is itself blocked by Phase 547's own spell immunity --
    so no other death path exists to invent handling for. Armies still
    ``commanded_by`` the now-dead visitor are reassigned exactly like
    the peaceful case (death doesn't release army command on its own --
    confirmed via ``GameState.remove_leader()``'s own docstring, which
    never touches ``ArmyState``).
    """

    visitor = state.leaders.get(VALHALLA_VISITOR_LEADER_ID)
    if visitor is not None and visitor.valhalla_active_turn == state.turn_number:
        _reassign_visitor_armies(state, visitor.kingdom_id, visitor.location, board_width)
        king = next(
            (leader for leader in state.leaders.values() if leader.kingdom_id == visitor.kingdom_id and leader.is_king),
            None,
        )
        if king is not None:
            for item in state.items_held_by(VALHALLA_VISITOR_LEADER_ID):
                state.transfer_item(item.item_id, king.leader_id)
        del state.leaders[VALHALLA_VISITOR_LEADER_ID]
        return

    dead = state.dead_leaders.get(VALHALLA_VISITOR_LEADER_ID)
    if dead is not None and dead.valhalla_active_turn == state.turn_number:
        if dead.kingdom_id is not None:
            _reassign_visitor_armies(state, dead.kingdom_id, dead.location, board_width)
        if dead.valhalla_fixed_item_id is not None:
            state.items.pop(dead.valhalla_fixed_item_id, None)
