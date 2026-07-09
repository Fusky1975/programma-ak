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
  gold cost (a spell, not a payment). Grouped under the **Psychic**
  Magical ability, per the Spell-to-Ability grouping established while
  researching Cast (Phase 23).
- **Kill_Enemy**: removes the co-located target character from
  ``GameState`` entirely (``GameState.remove_leader()``), mirroring how
  a destroyed army is removed from ``GameState.armies``. Grouped under
  **Necromancy**.

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

**The success/failure roll (Phase 30)**: rulebook [3.10], "The chance
that an action spell will succeed is 15% plus 15% per level," and "A
character may cast a spell in a Magical ability only if he has a skill
level of 1 or higher in that ability." Resolved via
``LeaderState.skills`` (``models/kingdom.py SkillTable``,
Phase 30) when the caster has it recorded: below skill 1, the cast fails
outright ("insufficient skill"); at skill 1+, a real ``15% + 15%*level``
roll decides it. **If the caster has no ``skills`` data at all**
(``None`` -- the default, and true for every leader this project hasn't
explicitly given ability data, since no real parsed-move-file-to-
``GameState`` pipeline exists yet -- see ``models/game_state.py``'s
module docstring), the precondition can't be checked and the chance
can't be computed, so casting always succeeds -- the exact placeholder
behavior this project used for every Charm/Kill_Enemy attempt before
Phase 30, preserved for backward compatibility rather than silently
becoming impossible to cast without ability data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.turn.cast_decode import CastRequest

ACTION_SPELL_BASE_CHANCE = 0.15
ACTION_SPELL_CHANCE_PER_LEVEL = 0.15

_SPELL_ABILITY: dict[Spell, Ability] = {
    Spell.CHARM: Ability.PSYCHIC,
    Spell.KILL_ENEMY: Ability.NECROMANCY,
}


@dataclass(slots=True)
class CastExecutionResult:
    request: CastRequest
    applied: bool
    reason: str | None = None  # set when applied is False


def execute_cast(
    state: GameState, kingdom_id: int, leader_id: int, request: CastRequest, rng: random.Random | None = None
) -> CastExecutionResult:
    """Apply a decoded Cast request to ``state``, for the spells this project can execute.

    See the module docstring for exactly which spells that is and why.
    ``rng`` is only ever consumed when the caster has real ``skills``
    data recorded (see the module docstring's success-roll section) --
    every existing caller/test that doesn't set it is unaffected.
    """

    rng = rng if rng is not None else random.Random()
    if request.spell is Spell.CHARM:
        return _execute_charm(state, kingdom_id, leader_id, request, rng)
    if request.spell is Spell.KILL_ENEMY:
        return _execute_kill_enemy(state, leader_id, request, rng)
    return CastExecutionResult(request, applied=False, reason="spell effect not modeled")


def _roll_cast_success(caster: LeaderState, spell: Spell, rng: random.Random) -> tuple[bool, str | None]:
    """Rulebook [3.10]: 15% + 15%/level, requiring skill >= 1. See module docstring for the ``skills is None`` fallback."""

    if caster.skills is None:
        return True, None

    level = caster.skills.pair_for_ability(_SPELL_ABILITY[spell])[0]
    if level < 1:
        return False, "insufficient skill"

    chance = ACTION_SPELL_BASE_CHANCE + ACTION_SPELL_CHANCE_PER_LEVEL * level
    if rng.random() < chance:
        return True, None
    return False, "spell failed"


def _execute_charm(
    state: GameState, kingdom_id: int, leader_id: int, request: CastRequest, rng: random.Random
) -> CastExecutionResult:
    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    target.kingdom_id = kingdom_id
    return CastExecutionResult(request, applied=True)


def _execute_kill_enemy(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random
) -> CastExecutionResult:
    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    state.remove_leader(request.target)
    return CastExecutionResult(request, applied=True)
