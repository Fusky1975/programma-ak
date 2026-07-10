"""Executing a Trail (rulebook [3.17]) order, single phase only -- Phase 52.

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
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.turn.movement import hex_distance
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
