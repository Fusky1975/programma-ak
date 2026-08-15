"""Applying Sage Discovery bonuses to real gameplay -- Phase 269 (ability
skill bonus).

``models/discovery.py``'s own module docstring left this half of the
Discoveries system explicitly deferred: "Applying any of these bonuses to
actual gameplay (how the ability bonus stacks with ``LeaderState.skills``...)
is still deliberately left to a real follow-up phase." This module closes
exactly that gap for the ability-bonus group (``fix0``-``fix9``,
``wreck0``-``wreck9``, ``DISCOVERY_ABILITY_BONUS``): "+1 skill in <ability>"
per Discovery owned, applied at every real skill-level read this project has
(combat strength, Duel/Encounter combatant construction, Cast's success
roll and level-dependent magnitudes, Steal/Talk gate checks, Patrol AI
thresholds, and the live Imperial Office Merit Point formulas) -- see
``effective_skill_level()`` below.

**Stacking**: a kingdom can own *two* different Discoveries that both bonus
the same ``Ability`` (e.g. ``LAND_SHIP`` and ``SCYTHED_CHARIOTS`` both give
Tactical). REPORTS.PAS's own report loop (``models/discovery.py``'s own
Phase 268 quote) prints each owned Discovery as its own independent "+1
skill in..." line -- nothing in the available source suggests the second
one is redundant or capped at +1 total, so this module sums every matching
Discovery the kingdom owns (0, +1, or +2, since exactly two Discoveries
exist per bonused Ability) rather than treating "has at least one" as a
flat, non-stacking flag. This is the same "no formula survives, only the
natural reading of the data does" category as prior unsourced-but-
documented design choices this project has made (Phase 265's uniform
perturbation shape, Phase 266's uniform Discovery selection).

**Capped at ``MAX_SKILL_LEVEL`` (9)**: ``CTBOTH.PAS``'s own ``skillrange``
is ``0..9`` -- a byte-range constraint on the *stored* skill, not
explicitly stated to apply to a computed effective level too, but nothing
in the available source describes what a level above 9 would even mean
(every skill-indexed table/formula this project has assumes the 0-9
range). Capping here is the same conservative, documented choice, not a
guess dressed up as a fact.

**Deliberately NOT touched by this module** (see call sites' own comments
for why, not repeated here): ``turn/practice_execution.py``'s own Practice
roll (uses the *stored*, pre-bonus skill as its own baseline -- a
Discovery is a permanent kingdom-wide effect layered on top of personal
training, not part of the training curve itself); ``turn/use_mi_execution.py``'s
own skill-raising Magic Item effect (mutates the persisted ``SkillTable``
directly, same reasoning); ``turn/succession.py``'s own "abilities the dead
King started with" overlap check (a genealogical/narrative concept about
personal training history, not a kingdom-wide magic/technology bonus); and
``report/turn_report.py``'s own CHARACTERS-section skill display (no
source either way on whether the displayed number includes Discovery
bonuses -- left as the raw stored value rather than guessed).
"""

from __future__ import annotations

from ak_engine.models.discovery import DISCOVERY_ABILITY_BONUS
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.treasure import ANTI_MAGIC_AMULET_BY_ABILITY
from ak_engine.turn.practice_execution import MAX_SKILL_LEVEL


def ability_bonus_from_discoveries(state: GameState, leader: LeaderState, ability: Ability) -> int:
    """How many ``+1``s ``leader``'s own kingdom contributes to ``ability`` via
    owned Discoveries -- 0, 1, or 2 (see module docstring for the stacking
    rationale). 0 for an independent Hero (``kingdom_id is None``) -- no
    kingdom to own a Discovery in the first place.
    """

    if leader.kingdom_id is None:
        return 0
    kingdom = state.kingdoms.get(leader.kingdom_id)
    if kingdom is None:
        return 0
    return sum(1 for discovery in kingdom.discoveries if DISCOVERY_ABILITY_BONUS.get(discovery) is ability)


def effective_skill_level(state: GameState, leader: LeaderState, ability: Ability) -> int:
    """``leader``'s own real skill in ``ability`` (0 if ``leader.skills`` was
    never recorded, the same placeholder convention every consumer already
    used) plus any ability-bonus Discoveries their kingdom owns, capped at
    ``MAX_SKILL_LEVEL`` -- see module docstring.

    Phase 310: a comatose leader (``LeaderState.is_comatose``, Kill_Enemy's
    own [4.25.2] coma variant) reads 0 here unconditionally, before
    ``leader.skills`` or any Discovery bonus is even consulted -- "tutti i
    suoi Talenti sono ridotti a livello zero" (all his Talents are reduced
    to level zero), a flat floor, not "0 plus whatever bonuses would
    otherwise apply." The real stored values are never touched, so nothing
    needs restoring once the coma is cured -- see that field's own
    docstring.
    """

    if leader.is_comatose:
        return 0
    stored = leader.skills.pair_for_ability(ability)[0] if leader.skills is not None else 0
    bonus = ability_bonus_from_discoveries(state, leader, ability)
    return min(MAX_SKILL_LEVEL, stored + bonus)


def holds_anti_magic_amulet(state: GameState, target_leader_id: int, ability: Ability) -> bool:
    """Phase 530: does ``target_leader_id`` currently hold the Anti-Magic
    Amulet matching ``ability`` (``models/treasure.py TREASAB.X2``'s own
    "immunity to one Magical Ability's spells" family -- ``AMULET_ANTI_
    WHITE``..``AMULET_ANTI_ILLUSION``, catalog ordinals 44-48)?

    **Scope, honestly labeled**: the family's *only* item-by-item detail
    beyond the generic catalog description comes from ``AKGEN_reverse_
    engineering_report (3).md`` SS3.4, which names the Psychic amulet
    (Helm of Psychic Dampening) specifically: "annulla Charm e Psychic
    Blast sul possessore; dimezza gli altri effetti Psychic pertinenti"
    (negates Charm and Psychic Blast on the holder; *halves* the other
    relevant Psychic effects). This function -- and every call site that
    uses it -- treats all 5 amulets uniformly as a full negation of any
    target-affecting spell of the matching college, which is at least as
    protective as the source's own weaker "halves" wording for the
    non-Charm/Psychic-Blast Psychic case: no fractional-magnitude formula
    is invented for a nuance this project has no other confirmed
    parameter for, and full negation can never under-protect relative to
    what the source actually describes. The other 4 amulets (White,
    Necromancy, Elemental, Illusion) have no per-item source at all beyond
    "immunity to one Magical Ability's spells" -- full negation is simply
    the plain reading of that phrase.

    Call sites decide for themselves which spells count as "affecting the
    target" (see each one's own comment) -- this function only answers
    the item-possession question.
    """

    amulet = ANTI_MAGIC_AMULET_BY_ABILITY.get(ability)
    if amulet is None:
        return False
    return any(item.treasure is amulet for item in state.items_held_by(target_leader_id))
