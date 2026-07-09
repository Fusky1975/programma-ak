"""Executing a Cast order end-to-end, for the small subset of spells this
project can actually apply to ``GameState`` (rulebook [3.10]/[4.21]-[4.25]).

Of the 12 real ``Spell``s observed across the 10 sample ``AK3__T*.K1``
files (see ``turn/cast_decode.py``'s docstring), only two get real
execution here:

- **Charm**: rulebook [4.22] describes its target as "a Hero in same
  province". Executed by assigning the co-located target character to
  the caster's kingdom -- the same ``LeaderState.kingdom_id`` mechanism
  Hire uses (rulebook [3.5], ``turn/hire_fire_decode.py``). **Unlike
  Hire, the target is not required to already be independent first**:
  nothing in the rulebook text available to this project restricts
  Charm to unemployed Heroes the way Hire's own section explicitly
  does, and "Charm" as a spell plausibly means *stealing* a
  co-located character's allegiance regardless of who currently employs
  them -- a documented interpretation, not a sourced distinction. No
  gold cost (a spell, not a payment).
- **Kill_Enemy**: removes the co-located target character from
  ``GameState`` entirely (``GameState.remove_leader()``), mirroring how
  a destroyed army is removed from ``GameState.armies``.

Both require the acting leader (the caster) and the target character to
be co-located, per each spell's own rulebook targeting text (Charm: "in
same province"; Kill_Enemy: "victim, must be co-located").

**Every other real spell stays unexecuted**, each for its own documented
reason:

- **Resurrection** can't be executed even conceptually with today's
  data model, not just "not modeled yet": its target is specifically "a
  deceased character" (rulebook), but ``GameState`` has no registry of
  dead/removed leaders to revive from -- once ``Kill_Enemy`` (or any
  other removal) deletes a ``LeaderState``, that character's name,
  location, and history are gone, not archived. There is nothing to
  "resurrect" from.
- **Skeletal_Army, Bless, Plague, Flood, Tornado, Illus_Armies
  (Phantasmal Armies), Oratory, Part_Sea, Illus_Terrain**: rulebook
  [4.21]-[4.25] confirms *what* each spell conceptually does (in broad
  strokes -- e.g. Bless a province, flood/storm-damage an enemy
  province, boost a character via Oratory) but gives **no numeric
  effect magnitude for any of them**, and no Pascal source for their
  execution exists in this project's available archive either (see
  ``turn/cast_decode.py``'s docstring -- the same "engine logic missing"
  situation already flagged for Search's encounter resolution and
  Practice's dice-roll procedure). Inventing tax/army/quality numbers
  for these would violate this project's own sourcing standard; they
  stay decode-only until real data or source turns up.

**The success/failure roll itself is also not modeled this phase**
(rulebook [3.10]: "15% plus 15% per level"): resolving it needs the
caster's own skill level in the spell's Magical ability, and
``GameState`` doesn't carry per-leader ability data yet (the move file
only exposes the *King's* own skill pairs, and even those aren't
persisted into ``GameState`` -- the same blocking gap already flagged
for Practice, Phase 21). Every Charm/Kill_Enemy attempt that passes the
co-location/target-exists checks currently always succeeds -- a
deliberate, incremental simplification, the same shape as Recruit
executing without its per-turn limits before a later phase added them
(Phase 12 -> Phase 15).
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.enums import Spell
from ak_engine.models.game_state import GameState
from ak_engine.turn.cast_decode import CastRequest


@dataclass(slots=True)
class CastExecutionResult:
    request: CastRequest
    applied: bool
    reason: str | None = None  # set when applied is False


def execute_cast(state: GameState, kingdom_id: int, leader_id: int, request: CastRequest) -> CastExecutionResult:
    """Apply a decoded Cast request to ``state``, for the spells this project can execute.

    See the module docstring for exactly which spells that is and why.
    """

    if request.spell is Spell.CHARM:
        return _execute_charm(state, kingdom_id, leader_id, request)
    if request.spell is Spell.KILL_ENEMY:
        return _execute_kill_enemy(state, leader_id, request)
    return CastExecutionResult(request, applied=False, reason="spell effect not modeled")


def _execute_charm(state: GameState, kingdom_id: int, leader_id: int, request: CastRequest) -> CastExecutionResult:
    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    target.kingdom_id = kingdom_id
    return CastExecutionResult(request, applied=True)


def _execute_kill_enemy(state: GameState, leader_id: int, request: CastRequest) -> CastExecutionResult:
    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    state.remove_leader(request.target)
    return CastExecutionResult(request, applied=True)
