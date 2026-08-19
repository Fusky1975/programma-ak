"""Executing a Use Magic Item order end-to-end (rulebook [3.11]) -- Phase 141.

``turn/use_mi_decode.py`` (Phase 24) could only decode ``UseMIRequest.
item_instance_id`` as an opaque global item-instance id, with no way to
resolve it to a real item: "this project has no way to build an
item-instance registry... there's no Pascal source describing how
instances come into existence." Phase 140's ``GameState.items``
registry (``models/item.py ItemInstance``) closes exactly that gap for
population; this module is the consumer that was blocked on it.

**Resolving the item, and rejecting a Use_MI on one the caster doesn't
hold**: ``request.item_instance_id`` is looked up in ``state.items``
directly (the same registry Trade/Give's own item path already reads,
Phase 140). A missing id, or one whose ``owner_leader_id`` isn't the
acting leader, fails outright -- the rulebook's own [3.11] wording
("specifying the ID number of the magic item") only makes sense for an
item the caster actually has.

**Only 35 of the 113 ``Treasure`` ordinals are legitimate Use_MI
targets** ([5.9], already established in ``turn/use_mi_decode.py``'s
own docstring and ``models/treasure.py USE_MI_TARGET_CATEGORIES``):

- **The 20 spell-casting wands** (``TreasureCategory.SPELL_WAND``)
  dispatch into ``turn/cast_execution.py execute_cast()`` for the
  matching ``Spell`` (``TREASURE_WAND_SPELL``). Two real mechanical
  differences from an ordinary Cast order, both sourced:

  - Rulebook [3.11]: "A spell cast from a magic item is automatically
    successful" -- no 15%+15%/level roll at all.
  - ``TREASAB.X2``'s own label for every one of the 20 wands reads
    ``"Cast '<Spell>' at skill-2"`` (``models/treasure.py
    TREASURE_LABEL``, transcribed verbatim in Phase 77) -- every
    level-dependent magnitude (Tornado's/Plague's per-unit destroy
    chance, Illus_Armies' strength bonus, Bless's graveyard-cleanup
    chance, Skeletal_Army's raised-army count) uses a fixed skill level
    of 2, regardless of what (if anything) the caster's own
    ``LeaderState.skills`` records.

  Both are implemented as ``execute_cast()``'s new ``wand_skill_level``
  parameter (Phase 141, see that module's own docstring) rather than
  duplicating any of Cast's 13 real spell-effect implementations here.

  **Charge consumption (Phase 172).** ``TREASURE.X2``'s own description,
  identical across all 20 wands (e.g. the Wand of Fire's own entry):
  "There is a certain number of charges in this item, and each time you
  cast the spell you use up a charge. When all charges are used up, the
  item becomes useless." Two rules follow directly:

  - An item at ``charges <= 0`` is rejected outright, *before* attempting
    the cast at all ("becomes useless") -- ``reason="item has no charges
    remaining"``.
  - A charge is spent only when the cast genuinely happens
    (``cast_result.applied is True``) -- not on a validation failure
    ("target not found", out of range, etc.), since those never reach
    the spell's own automatic-success rule in the first place and
    nothing was actually "cast." ``ItemInstance.charges`` (``trcharges``,
    Phase 140) is decremented by exactly 1 in that case.

- **The 15 one-shot skill books** (``TreasureCategory.SKILL_BOOK``):
  "a one-shot, self-consuming +1 to one Ability when read"
  (``models/treasure.py``'s own docstring, [5.9]). Applied directly to
  the reader's own ``LeaderState.skills`` (creating a fresh all-zero
  ``SkillTable`` first if none was recorded -- the same ``_get_or_create_
  skills`` convention ``turn/practice_execution.py`` already established
  for exactly this "no ability data at all" case), clamped to
  ``skillrange``'s own real ceiling of 9 (``CTBOTH.PAS``). The book
  itself is then removed from ``GameState.items`` entirely
  (``GameState.remove_item()``) -- "self-consuming" read literally, not
  left behind as a depleted-but-still-owned instance.

- **Every other category "operates automatically"** per [5.9] (passive
  ability items, combat weapons, leadership weapons, anti-magic
  amulets, monster-command items, gold hoards, quest items, the
  sentinel, named uniques, unused extension slots) -- never a Use_MI
  target at all. Attempting one fails with a clear, honest reason
  rather than silently doing nothing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.treasure import (
    TREASURE_BOOK_ABILITY,
    TREASURE_CATEGORY,
    TREASURE_WAND_SPELL,
    Treasure,
    TreasureCategory,
)
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult, execute_cast
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS
from ak_engine.turn.use_mi_decode import UseMIRequest

# TREASAB.X2: every one of the 20 wands' own label reads "Cast '<Spell>' at skill-2".
USE_MI_WAND_SKILL_LEVEL = 2

# CTBOTH.PAS: skillrange = 0..9.
MAX_SKILL_LEVEL = 9

# Phase 542: AKGEN_reverse_engineering_report (4).md SS6.2, RUMORS.PAS:839-857
# -- every charged item marks the caster's intent Melee EXCEPT these two.
USE_MI_NON_AGGRESSIVE_WANDS = frozenset({Treasure.WAND_CHARM, Treasure.WAND_INVISIBILITY})


@dataclass(slots=True)
class UseMIExecutionResult:
    applied: bool
    reason: str | None = None
    cast_result: CastExecutionResult | None = None  # set when a wand triggered a spell cast
    ability_boosted: Ability | None = None  # set when a book was read
    # Phase 542: sourced from the dossier's own intent-classification rule
    # (see USE_MI_NON_AGGRESSIVE_WANDS above), but this project has no
    # simulated monster/AI reaction system for ANY action type to consume
    # it with yet -- wandering encounters are pure report narrative
    # (models/local_encounter.py LocalEncounterEvent), never a decision
    # branch. Exposed anyway, the same "structure/primitive is sourced
    # even though automatic consumption isn't" split this project already
    # accepted for ItemInstance/GameState.add_item() (Phase 140).
    marks_aggressive_intent: bool = False


def execute_use_mi(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: UseMIRequest,
    rng: random.Random | None = None,
    *,
    board_width: int = NORMAL_MAP_BOUNDS[0],
) -> UseMIExecutionResult:
    """Apply a decoded Use_MI request to ``state``. See the module docstring for exactly
    which of the 113 ``Treasure`` ordinals this can resolve, and why the
    other 78 (all "operating automatically" per [5.9]) fail with a clear
    reason instead.
    """

    item = state.items.get(request.item_instance_id)
    if item is None:
        return UseMIExecutionResult(applied=False, reason="item not found")
    if item.owner_leader_id != leader_id:
        return UseMIExecutionResult(applied=False, reason="leader does not possess this item")

    category = TREASURE_CATEGORY.get(item.treasure)

    if category is TreasureCategory.SPELL_WAND:
        if item.charges <= 0:
            return UseMIExecutionResult(applied=False, reason="item has no charges remaining")

        spell = TREASURE_WAND_SPELL[item.treasure]
        cast_request = CastRequest(spell=spell, target=request.target, terrain=request.terrain)
        cast_result = execute_cast(
            state,
            kingdom_id,
            leader_id,
            cast_request,
            rng,
            board_width=board_width,
            wand_skill_level=USE_MI_WAND_SKILL_LEVEL,
        )
        if cast_result.applied:
            item.charges -= 1
        marks_aggressive_intent = cast_result.applied and item.treasure not in USE_MI_NON_AGGRESSIVE_WANDS
        return UseMIExecutionResult(
            applied=cast_result.applied,
            reason=cast_result.reason,
            cast_result=cast_result,
            marks_aggressive_intent=marks_aggressive_intent,
        )

    if category is TreasureCategory.SKILL_BOOK:
        ability = TREASURE_BOOK_ABILITY[item.treasure]
        leader = state.leaders[leader_id]
        if leader.skills is None:
            leader.skills = SkillTable([0] * 30)

        skill, aptitude = leader.skills.pair_for_ability(ability)
        leader.skills.set_pair_for_ability(ability, min(skill + 1, MAX_SKILL_LEVEL), aptitude)
        state.remove_item(item.item_id)
        return UseMIExecutionResult(applied=True, ability_boosted=ability)

    return UseMIExecutionResult(applied=False, reason="not a Use_MI target -- operates automatically")
