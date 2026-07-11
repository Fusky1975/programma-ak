"""Executing a Trail (rulebook [3.17]) order -- Phase 52, extended with a
standalone multi-phase chase-step primitive in Phase 68 (``advance_trail``,
not auto-wired anywhere yet -- see that section below).

**[3.17] Trail, quoted in full** (also quoted in ``turn/trail_decode.py``'s
own docstring):

    The character follows and spies on a character, gaining information
    on the character's Actions, race, temper, alignment, treasures
    owned and armies led. If the character is a King, some information
    may be gained concerning the finances, alliances, enemies and
    controlled provinces of the Kingdom. Like the Pursue order, the
    Trail order ends when the character finds and has spied on the
    character for one phase. Further Trail orders would be needed to
    maintain the spying. A character leading an army may not be ordered
    to Trail.

Trail's own catch-up mechanic is [4.33]'s Spy Table, the same shared
"Chance to Pursue **or** Trail" column ``turn/pursue_execution.py``
(Phase 51) already wired up -- ``execute_trail`` reuses ``turn/
spy_table.py``'s ``pursue_catch_up_chance`` and ``turn/movement.py``'s
``hex_distance`` directly, no new formula needed.

**"A character leading an army may not be ordered to Trail" is treated
the same way as Pursue's own army-leading-mismatch rule ([3.16],
Phase 51)**: the order is ignored (``TrailExecutionResult(spied_on=
False, reason=...)``, not an exception -- consistent with this
project's existing convention that an invalid-per-rulebook order
reports itself rather than crashing.

**Deliberately narrow scope: catch-up only, no intelligence payload.**
This function answers only "does the trail succeed in finding and
spying on the target this phase" (``spied_on: bool``) -- it does *not*
attempt to construct the actual "Actions, race, temper, alignment,
treasures owned and armies led" (or, for a King target, "finances,
alliances, enemies and controlled provinces") intelligence report.
Two independent reasons, both already-declared project-wide gaps, not
new ones invented for Trail specifically:

1. This project has no report-generation system at all yet (see
   ``ak_engine/README.md``'s own "Not yet implemented" list, and
   ASpy's ([3.14]) identical "intelligence-report generation... needs
   `GameState`/battle-orchestrator logic that doesn't exist yet" note)
   -- there is nowhere to route a spied-on payload even if one were
   assembled here.
2. Several of the rulebook's own named fields don't exist anywhere in
   this project's data model to report on in the first place:
   ``LeaderState`` has no ``race``, ``temper``, ``alignment``, or
   per-leader treasure/magic-item ownership field (``Temper`` has no
   model in this project at all, confirmed in ``turn/encounter.py``'s
   own docstring). Fabricating a payload shape for data this project
   doesn't track would be guessing, not reconstruction.

A future report-generation phase that adds those fields is the natural
place to extend ``TrailExecutionResult`` with the actual intelligence
payload -- not attempted here.

**Phase 68 -- the same scoped multi-phase chase step Phase 66 added for
Pursue.** [3.17] itself draws the parallel explicitly: "Like the Pursue
order, the Trail order ends when the character finds and has spied on
the character for one phase." ``advance_trail`` mirrors ``turn/
pursue_execution.py advance_pursuit`` exactly, reusing that module's
``step_toward_target`` primitive rather than duplicating hex-stepping
logic -- one greedy hex step toward the target's current location, then
a fresh ``execute_trail`` catch-up attempt at the new, shorter distance.
Simpler than Pursue's own version in exactly one respect: a Trail order
never has armies to move alongside the leader ("a character leading an
army may not be ordered to Trail" is already enforced by
``execute_trail`` itself). Same scope boundary as Phase 66, confirmed
with the user for Pursue and carried over unchanged here: not
auto-wired into ``turn/turn_processor.py``'s phase loop, no
movement-point cost, a standalone explicitly-invoked primitive.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, hex_distance
from ak_engine.turn.pursue_execution import step_toward_target
from ak_engine.turn.spy_table import pursue_catch_up_chance
from ak_engine.turn.trail_decode import TrailRequest


def _spy_skill_of(leader: LeaderState) -> int:
    if leader.skills is None:
        return 0
    return leader.skills.pair_for_ability(Ability.SPY)[0]


@dataclass(slots=True)
class TrailExecutionResult:
    spied_on: bool
    reason: str | None = None


def execute_trail(
    state: GameState, trailer_leader_id: int, request: TrailRequest, rng: random.Random | None = None
) -> TrailExecutionResult:
    """Resolve one phase of a Trail order: [3.17]'s no-army restriction, then a Spy
    Table catch-up roll. See module docstring for why no intelligence
    payload is assembled on success.
    """

    rng = rng if rng is not None else random.Random()

    trailer = state.leaders.get(trailer_leader_id)
    target = state.leaders.get(request.target_character_id)
    if trailer is None or target is None:
        return TrailExecutionResult(spied_on=False, reason="trailer or target not found")

    if state.armies_commanded_by(trailer.leader_id):
        return TrailExecutionResult(
            spied_on=False, reason="a character leading an army may not be ordered to Trail"
        )

    target_leads_army = bool(state.armies_commanded_by(target.leader_id))
    same_kingdom = trailer.kingdom_id is not None and trailer.kingdom_id == target.kingdom_id
    distance = hex_distance(trailer.location, target.location)
    chance = pursue_catch_up_chance(
        _spy_skill_of(trailer),
        target_leads_army=target_leads_army,
        distance_provinces=distance,
        same_kingdom=same_kingdom,
    )
    if rng.random() >= chance:
        return TrailExecutionResult(spied_on=False, reason="did not find the target this phase")

    return TrailExecutionResult(spied_on=True)


def advance_trail(
    state: GameState,
    trailer_leader_id: int,
    request: TrailRequest,
    rng: random.Random | None = None,
    *,
    board_width: int = NORMAL_MAP_BOUNDS[0],
    board_height: int = NORMAL_MAP_BOUNDS[1],
) -> TrailExecutionResult:
    """Resolve a further phase of an *already-ongoing* Trail: one
    ``turn/pursue_execution.py step_toward_target`` hex-step for the trailer
    (never any armies -- [3.17]'s no-army restriction), then a fresh
    ``execute_trail`` catch-up attempt at the new, shorter distance. See
    module docstring for what's not wired around this (mirrors
    ``advance_pursuit``'s own documented scope exactly).
    """

    rng = rng if rng is not None else random.Random()

    trailer = state.leaders.get(trailer_leader_id)
    target = state.leaders.get(request.target_character_id)
    if trailer is None or target is None:
        return TrailExecutionResult(spied_on=False, reason="trailer or target not found")

    bounds = MapBounds(board_width, board_height)
    trailer.location = step_toward_target(trailer.location, target.location, bounds)

    return execute_trail(state, trailer_leader_id, request, rng)
