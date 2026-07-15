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

**Phase 159 -- corrects a stale claim in this docstring and closes part
of the intelligence-payload gap.** This module previously claimed
``LeaderState`` had no ``race``, ``temper``, ``alignment``, or
per-leader treasure/magic-item ownership field, and that ``Temper``
itself had no model in this project at all -- both wrong as of this
phase: ``Temper`` has had a real model since Phase 82
(``models/temper.py``), ``LeaderState.temper`` has stored real
per-leader values since Phase 139, and the leader-held item-ownership
registry (``GameState.items_held_by()``) has existed since Phase 140.
Left uncorrected, a future reader would have trusted a doc comment
over the actual code -- the same self-correction policy Phase 55/153
already established elsewhere in this project.

``TrailExecutionResult`` now carries three of [3.17]'s six named
fields on a successful spy: ``temper`` (``target.temper``, ``None`` if
never recorded for that leader -- the same "no data" convention the
field itself already uses), ``treasures_owned``
(``GameState.items_held_by(target.leader_id)``), and ``armies_led``
(``GameState.armies_commanded_by(target.leader_id)``, already computed
once for the catch-up-chance roll and reused here rather than queried
twice).

**Phase 164 closes the alignment field too.** ``LeaderState.alignment``
(Phase 162, added for ``turn/hire_pay.py``'s required-pay formula) is
now a real, stored per-leader value -- not the kingdom-level-only
``KingdomState.alignment``, and not Phase 136's own ``Align_Est``
*estimate* formula (a Trail spy learns the target's true alignment,
not a fuzzy guess; ``turn/intelligence_estimate.py``'s imperfect-
information model is a different, ASpy-only mechanic, not reused
here). ``TrailExecutionResult.alignment`` mirrors ``temper``'s own
"``None`` if never recorded" convention exactly.

**Phase 165 closes the race field too, per direct user instruction
("continua con la razza in Trail").** `LeaderState` still has no
per-leader race field, and none is added here -- there is no source
distinguishing an individual character's race from their Kingdom's own
(the rulebook's own [3.5] Hire text even treats a Hero's race as
something that can coincidentally match or differ from the hiring
King's, but never as separately recorded data this project's Pascal
archive tracks per-character). ``TrailExecutionResult.race`` is instead
sourced the same way `report/turn_report.py
describe_armies_report()`'s own Phase 158 note already established for
`MONSTROUS_ARMY_RACE`-less army types: `KingdomState.race`, looked up
via the target's own `kingdom_id`. An **independent Hero
(`kingdom_id is None`) genuinely has no kingdom to infer a race
from** -- reported as `None`, the same "no data" convention every
other field here already uses, rather than guessing. This does leave
exactly the case [3.17] itself calls out most ("if the character is a
King...") with real data, and the case this project can't source
(an independent Hero) honestly reporting nothing, instead of a
half-correct payload for one target type only.

**Still genuinely open, not attempted here**: [3.17]'s remaining
field --

- **Actions**: the target's own decoded orders for this phase.
  ``PhaseDispatchResult`` (``turn/plan_dispatch.py``) discards the
  original decoded request before storing a result (the same
  structural gap Phase 151's own `describe_turn_results()` docstring
  already names for PURSUE/TRAIL/TRADE/SEARCH) -- there is nothing to
  read the target's Actions from without a separate, larger change.

The King-target aggregate case ("finances, alliances, enemies and
controlled provinces of the Kingdom") is also not attempted here --
its own underlying data (`KingdomState.treasury`, `GameState.
allied_kingdoms`, `ProvinceState.owner_kingdom_id`) does now exist,
unlike when this docstring first scoped Trail out, but assembling and
routing that aggregate view is a distinct, larger follow-up the user
didn't ask for this phase -- flagged here for a future phase, not
silently expanded into this one.

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

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.item import ItemInstance
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
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
    # Phase 159 (temper/treasures_owned/armies_led) + Phase 164
    # (alignment) + Phase 165 (race): five of [3.17]'s six named
    # intelligence fields, only populated when spied_on is True. See
    # module docstring for why the remaining one (Actions) still isn't.
    temper: Temper | None = None
    alignment: Alignment | None = None
    # Phase 165: sourced from the target's own KingdomState.race (there
    # is no per-leader race field) -- None for an independent Hero,
    # who has no kingdom to infer a race from. See module docstring.
    race: Race | None = None
    treasures_owned: tuple[ItemInstance, ...] = ()
    armies_led: tuple[ArmyState, ...] = ()


def execute_trail(
    state: GameState, trailer_leader_id: int, request: TrailRequest, rng: random.Random | None = None
) -> TrailExecutionResult:
    """Resolve one phase of a Trail order: [3.17]'s no-army restriction, then a Spy
    Table catch-up roll. On success, populates the ``temper``/
    ``alignment``/``race``/``treasures_owned``/``armies_led`` slice of
    [3.17]'s intelligence payload this project can source today -- see
    module docstring for why the remaining named field (Actions) still
    isn't attempted.
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

    target_armies = state.armies_commanded_by(target.leader_id)
    same_kingdom = trailer.kingdom_id is not None and trailer.kingdom_id == target.kingdom_id
    distance = hex_distance(trailer.location, target.location)
    chance = pursue_catch_up_chance(
        _spy_skill_of(trailer),
        target_leads_army=bool(target_armies),
        distance_provinces=distance,
        same_kingdom=same_kingdom,
    )
    if rng.random() >= chance:
        return TrailExecutionResult(spied_on=False, reason="did not find the target this phase")

    race = state.kingdoms[target.kingdom_id].race if target.kingdom_id is not None else None

    return TrailExecutionResult(
        spied_on=True,
        temper=target.temper,
        alignment=target.alignment,
        race=race,
        treasures_owned=tuple(state.items_held_by(target.leader_id)),
        armies_led=tuple(target_armies),
    )


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
