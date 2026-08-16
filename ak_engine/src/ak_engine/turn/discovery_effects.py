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
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.treasure import AMULET_BLOCKED_SPELLS, ANTI_MAGIC_AMULET_BY_ABILITY, TREASURE_ABILITY_ITEM
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


def ability_bonus_from_items(state: GameState, leader: LeaderState, ability: Ability) -> int:
    """Phase 534: AKGEN_reverse_engineering_report (4).md SS5 -- ``M_Skill``
    sums the stored skill with ``NT_Owned(leader, item_type, item_type)``,
    i.e. each of the 15 ability items (``Treasure`` ordinals 0-14,
    ``models/treasure.py TREASURE_ABILITY_ITEM``) grants ``+1`` to its own
    matching ``Ability`` *per copy held* -- unlike Discoveries (capped at
    2 matching entries by the Pascal enum itself), there's no such cap
    here, so every held copy counts. Sibling to ``ability_bonus_from_
    discoveries()`` above; 0 for a leader holding no items in ``ability``'s
    own item.
    """

    return sum(1 for item in state.items_held_by(leader.leader_id) if TREASURE_ABILITY_ITEM.get(item.treasure) is ability)


def effective_skill_level(state: GameState, leader: LeaderState, ability: Ability) -> int:
    """``leader``'s own real skill in ``ability`` (0 if ``leader.skills`` was
    never recorded, the same placeholder convention every consumer already
    used) plus any ability-bonus Discoveries their kingdom owns and any
    ability items they personally hold, capped at ``MAX_SKILL_LEVEL`` --
    see module docstring.

    Phase 310: a comatose leader (``LeaderState.is_comatose``, Kill_Enemy's
    own [4.25.2] coma variant) reads 0 here unconditionally, before
    ``leader.skills`` or any Discovery bonus is even consulted -- "tutti i
    suoi Talenti sono ridotti a livello zero" (all his Talents are reduced
    to level zero), a flat floor, not "0 plus whatever bonuses would
    otherwise apply." The real stored values are never touched, so nothing
    needs restoring once the coma is cured -- see that field's own
    docstring.

    Phase 534: item bonuses stack with Discovery bonuses *before* the
    combined total is capped at ``MAX_SKILL_LEVEL`` -- SS5's own "le copie
    si sommano prima dei limiti" (copies sum before the limits), and
    nothing in either source suggests item and Discovery bonuses cap
    independently of one another.
    """

    if leader.is_comatose:
        return 0
    stored = leader.skills.pair_for_ability(ability)[0] if leader.skills is not None else 0
    bonus = ability_bonus_from_discoveries(state, leader, ability) + ability_bonus_from_items(state, leader, ability)
    return min(MAX_SKILL_LEVEL, stored + bonus)


def holder_is_immune_to_spell(state: GameState, target_leader_id: int, spell: Spell) -> bool:
    """Phase 531: does ``target_leader_id`` currently hold an Anti-Magic
    Amulet that personally blocks ``spell`` (``models/treasure.py
    AMULET_BLOCKED_SPELLS``)?

    **Replaces Phase 530's ``holds_anti_magic_amulet()``**, which treated
    each of the 5 amulets as blocking *any* spell of the matching magic
    college -- a guess made because the only source available at the time
    (``AKGEN_reverse_engineering_report (3).md`` SS3.4) gave detail for
    just one item (Helm of Psychic Dampening: "annulla Charm e Psychic
    Blast"). ``AKGEN_reverse_engineering_report (4).md`` SS8 is a
    dedicated magic-item dossier that gives the real, narrower per-item
    table: each amulet blocks only 1-2 *named* spells (``AMULET_BLOCKED_
    SPELLS``'s own docstring in ``models/treasure.py`` has the full
    table and citations) -- e.g. the White amulet (Shrunken-Head Amulet)
    blocks Holy Symbol but *not* Spiritwrack, even though both are White
    college. Confirms Phase 530's one hard-sourced case (Charm + Psychic
    Blast) was already exactly right; the other 4 amulets were the
    over-guessed part.

    **Phase 532**: ``AMULET_ANTI_ILLUSION`` (Crystal of True Seeing) now
    joins ``AMULET_BLOCKED_SPELLS`` too, for Invisibility -- wired into
    ``challenge_execution.py``/``search_execution.py``'s own Invisibility
    branches, right alongside their existing ``AdvancedAbility.
    WITCHSIGHT_TALENT`` carve-out. Illusory Terrain and Hide Feature are
    also in the amulet's blocked set (the dossier's "sees through"
    wording covers all three), but neither has a real consumer yet to
    wire the check into -- both are pure ``cast_execution.py`` province-
    state writes with "no consuming Explore/Search discovery-roll reads it
    yet" already documented on ``_execute_illus_terrain``/``_execute_
    hide_feature`` themselves (this predates Phase 532; see those
    functions' own docstrings). ``holder_is_immune_to_spell()`` already
    returns the right answer for both spells the moment such a consumer
    exists -- no further change needed here when it does. Phantasmal
    Armies is deliberately absent from the amulet's blocked set -- SS8
    point 3 treats it as a separate, battle-wide strength-bonus halving,
    not a personal spell immunity; see ``turn/battle_orchestrator.py``'s
    own Phase 532 addendum for that half.
    """

    for amulet, blocked in AMULET_BLOCKED_SPELLS.items():
        if spell not in blocked:
            continue
        if any(item.treasure is amulet for item in state.items_held_by(target_leader_id)):
            return True
    return False


def province_halves_spell_chance(state: GameState, province_coord: HexCoord, ability: Ability) -> bool:
    """Phase 533: ``AKGEN_reverse_engineering_report (4).md`` SS8 -- the
    second, separate effect each of the 5 protection amulets grants: any
    spell of the matching magic college targeted *at a province the
    amulet holder owns* has its cast-success chance halved, regardless of
    whether that particular spell is in the amulet's own personal
    ``AMULET_BLOCKED_SPELLS`` set (this is genuinely whole-college, unlike
    the personal immunity above -- reuses ``ANTI_MAGIC_AMULET_BY_ABILITY``,
    Phase 530's own ability-keyed table, kept in ``models/treasure.py``
    for exactly this purpose).

    "The amulet holder owns the province" is read as: the province's own
    ``ProvinceState.owner_kingdom_id`` matches any leader of that Kingdom
    currently holding the matching amulet -- the holder need not be
    physically present, matching the personal-immunity check's own
    "state.items_held_by" possession-only shape.
    """

    province = state.provinces.get(province_coord)
    if province is None or province.owner_kingdom_id is None:
        return False
    amulet = ANTI_MAGIC_AMULET_BY_ABILITY.get(ability)
    if amulet is None:
        return False
    return any(
        leader.kingdom_id == province.owner_kingdom_id
        and any(item.treasure is amulet for item in state.items_held_by(leader.leader_id))
        for leader in state.leaders.values()
    )
