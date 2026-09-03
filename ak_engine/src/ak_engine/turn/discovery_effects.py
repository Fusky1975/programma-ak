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

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import DISCOVERY_ABILITY_BONUS
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.game_type import GameType
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import (
    AMULET_BLOCKED_SPELLS,
    ANTI_MAGIC_AMULET_BY_ABILITY,
    COMBAT_WEAPON_SLOT_TREASURES,
    MONSTER_COMMAND_RACE,
    MONSTER_SUMMONING_TREASURE,
    TREASURE_ABILITY_ITEM,
    Treasure,
)
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

    Phase 538: ``arcane_valor_artifact_bonus()`` folds in the same way --
    0 for every game outside ``GameType.ARCANES``, so this is a no-op for
    every existing game/test.
    """

    if leader.is_comatose:
        return 0
    stored = leader.skills.pair_for_ability(ability)[0] if leader.skills is not None else 0
    bonus = (
        ability_bonus_from_discoveries(state, leader, ability)
        + ability_bonus_from_items(state, leader, ability)
        + arcane_valor_artifact_bonus(state, leader, ability)
    )
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

    **Phase 725**: this boolean is no longer fed into an arithmetic
    multiplier anywhere -- see ``resolve_province_protection_block()``
    right below, which reuses this function purely as its own cheap
    "does the protection even exist here" first check, then implements
    the real coin-flip-then-ownership gate (``SCAR.md`` 5.3/15.5) on top.
    This function's own name/return value stay accurate either way: "does
    this province's protection apply" is still exactly what it answers.
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


def resolve_province_protection_block(
    state: GameState, province_coord: HexCoord, ability: Ability, caster_kingdom_id: int | None, rng: random.Random
) -> bool:
    """Phase 725: ``SCAR.md`` 5.3/15.5 -- the real gate a province's own
    protective amulet applies, disassembled directly at `AK.EXE raw
    0xEBAA-0xEC85` ("protezione antim magia della provincia," a shared
    routine, not Scar-Terrain-specific -- its own entry-points table lists
    it generically, and its own internal call to `0x35eb:0x79cf` derives
    the protective treasure from the spell's college, the exact same
    5-item table ``ANTI_MAGIC_AMULET_BY_ABILITY``/``province_halves_spell_
    chance()`` above already model, independently cross-confirmed against
    `AKGEN_reverse_engineering_report (4).md` line 331's own item-catalog
    text for the same table):

        blocked := false;
        if OwnerHasProtection(powner[x,y], <spell's college>) then
          if Rand2 = 1 then                      { 50% coin, Trunc(2*Random) }
            if powner[x,y] <> LKing(caster) then
              blocked := true;

    **Not arithmetic halving.** A 50% coin is drawn first; only on a hit
    does the block actually apply, and only against a province owned by a
    *different* Kingdom than the caster's own -- if not blocked, the
    ordinary cast proceeds at its full, un-multiplied chance. In aggregate
    this reproduces the same expected success rate as `chance/2` against a
    foreign protected province (matching the item's own "dimezza la
    chance" catalog text), but the real RNG-consumption shape is a fixed
    coin draw (only when protection is present) plus a conditional
    full-chance roll -- not one draw at a halved chance.

    **A real, separate own-kingdom exemption**, missing before this
    phase: the province's own owning Kingdom can never be blocked from
    casting on its own province (`powner = LKing(caster)` keeps `blocked`
    `False` regardless of the coin) -- e.g. a Kingdom Blessing its own
    White-protected province is never halved/blocked by its own amulet.

    **RNG-ordering detail, replicated faithfully** (SCAR.md's own
    "Dettaglio RNG"): the coin is drawn unconditionally whenever
    protection exists, *before* the ownership comparison -- even for an
    own-kingdom cast that can never actually be blocked, the coin still
    consumes one `rng.random()` call. Do not reorder the ownership check
    ahead of the coin in any future change here; SCAR.md explicitly warns
    against it for deterministic-replay fidelity.
    """

    if not province_halves_spell_chance(state, province_coord, ability):
        return False
    coin = int(rng.random() * 2)
    if coin != 1:
        return False
    province = state.provinces[province_coord]
    return province.owner_kingdom_id != caster_kingdom_id


def equipped_combat_weapon(state: GameState, leader_id: int) -> Treasure | None:
    """Phase 535: which of the 8 mutually-exclusive "equipped weapon" slot
    items (``models/treasure.py COMBAT_WEAPON_SLOT_TREASURES``)
    ``leader_id`` is currently wielding, or ``None`` if they hold none.

    This project has no ``Use_MI``/order-level "equip this weapon"
    concept (AKGEN_reverse_engineering_report (4).md SS7.3 confirms the
    real engine applies/removes the equipped state automatically on
    possession change, event ``_LWield``, not a separate command) and no
    persistent "currently equipped item" field anywhere -- so a leader
    holding more than one of these 8 weapons at once is an unmodeled edge
    case the dossier gives no tie-break for. The lowest-``item_id`` held
    instance wins, the same tie-break convention this project's own
    Enhanced Charm item selection already uses -- a documented
    simplification, not a guess at a real priority rule.
    """

    candidates = [
        item for item in state.items_held_by(leader_id) if item.treasure in COMBAT_WEAPON_SLOT_TREASURES
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item.item_id).treasure


def holds_bow_of_elven_kings(state: GameState, leader_id: int) -> bool:
    """Phase 535: does ``leader_id`` hold at least one Bow of the Elven
    Kings (``Treasure.LEADERSHIP_ELVEN``)? SS7.1 point 5/SS7.2's own
    ``if attack_is_archery and NT_Owned(...)>0`` branch -- checked by mere
    possession (``>0``), independent of ``equipped_combat_weapon()``'s
    own slot (the Bow never occupies it), and multiple copies don't
    stack the bonus (a plain boolean, not a count).
    """

    return any(item.treasure is Treasure.LEADERSHIP_ELVEN for item in state.items_held_by(leader_id))


def holds_monster_command_item_for(state: GameState, leader_id: int, guardian_species: Monster) -> bool:
    """Phase 537: AKGEN_reverse_engineering_report (4).md SS9 -- does
    ``leader_id`` hold the one racial-command item (``models/treasure.py
    MONSTER_COMMAND_RACE``/``MONSTER_SUMMONING_TREASURE``) matching
    ``guardian_species``'s own Dragon/Eagle/Whale family? ``False`` for
    every other species (no matching item exists) and for a species with
    no matching item held.
    """

    race = MONSTER_COMMAND_RACE.get(guardian_species)
    if race is None:
        return False
    treasure = MONSTER_SUMMONING_TREASURE.get(race)
    if treasure is None:
        return False
    return any(item.treasure is treasure for item in state.items_held_by(leader_id))


def _king_of_kingdom(state: GameState, kingdom_id: int) -> LeaderState | None:
    for candidate in state.leaders.values():
        if candidate.kingdom_id == kingdom_id and candidate.is_king:
            return candidate
    return None


def _item_count(state: GameState, leader_id: int, treasure: Treasure) -> int:
    return sum(1 for item in state.items_held_by(leader_id) if item.treasure is treasure)


def arcane_valor_artifact_bonus(state: GameState, leader: LeaderState, ability: Ability) -> int:
    """Phase 538: AKGEN_reverse_engineering_report (4).md SS11.1's own
    exact pseudocode for the 6 Arcane's Valor artifacts (93-98) -- active
    only when ``state.game_type is GameType.ARCANES``. Every other game
    (``state.game_type`` is ``None`` for every existing game/test) returns
    0 unconditionally, per the user's own explicit instruction that this
    variant isn't currently played.

    Each artifact grants its own per-copy bonus to specific abilities
    (``NT_Owned`` -- copies stack, same convention ``ability_bonus_from_
    items()`` already established); Fang of the Vampire Lord (97) and
    Hammer of Power (98) both feed ``Ability.MELEE`` unconditionally, plus
    their own race/alignment-gated second ability (Necromancy for an
    Undead holder, Druid for a Dwarf holder). Three King-only combo
    bonuses require the *King's own personal* possession of both named
    artifacts (not merely two Heroes of that King each holding one) --
    every leader whose own King matches gets the point, per the source's
    own "tutti i personaggi il cui LKing e' quel Re ricevono il bonus."
    """

    if state.game_type is not GameType.ARCANES:
        return 0

    n = 0
    if ability in (Ability.TACTICAL, Ability.MARCH):
        n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_CROWN_ROHAN)
    elif ability in (Ability.WHITE, Ability.ELEMENTAL, Ability.PSYCHIC):
        n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_AMULET_POWER)
    elif ability is Ability.SAGE:
        n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_SCEPTER_LIFE)
    elif ability is Ability.NAVAL:
        n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_MAP_MARAUDERS)
    elif ability is Ability.MELEE:
        n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_FANG_VAMPIRE)
        n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_HAMMER_POWER)
    elif ability is Ability.DRUID:
        effective_race = leader.race
        if effective_race is None and leader.kingdom_id is not None:
            kingdom = state.kingdoms.get(leader.kingdom_id)
            effective_race = kingdom.race if kingdom is not None else None
        if effective_race is Race.DWARVEN:
            n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_HAMMER_POWER)
    elif ability is Ability.NECROMANCY:
        if leader.alignment is Alignment.UNDEAD:
            n += _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_FANG_VAMPIRE)

    king = _king_of_kingdom(state, leader.kingdom_id) if leader.kingdom_id is not None else None
    if king is not None:
        king_holds_crown = _item_count(state, king.leader_id, Treasure.NAMED_UNIQUE_CROWN_ROHAN) > 0
        king_holds_amulet = _item_count(state, king.leader_id, Treasure.NAMED_UNIQUE_AMULET_POWER) > 0
        king_holds_scepter = _item_count(state, king.leader_id, Treasure.NAMED_UNIQUE_SCEPTER_LIFE) > 0
        if ability is Ability.TACTICAL and king_holds_crown and king_holds_amulet:
            n += 1
        elif ability is Ability.ILLUSION and king_holds_crown and king_holds_scepter:
            n += 1
        elif ability is Ability.MELEE and king_holds_amulet and king_holds_scepter:
            n += 1

    return n


ARCANE_VALOR_SCEPTER_PERSONAL_HIT_POINTS_BONUS = 5
ARCANE_VALOR_SCEPTER_KINGDOM_HIT_POINTS_BONUS = 2


def arcane_valor_hit_points_bonus(state: GameState, leader: LeaderState) -> int:
    """Phase 538: AKGEN_reverse_engineering_report (4).md SS11.2 -- +5
    combat hit points for personally holding the Scepter of Life (95),
    +2 more for the Kingdom whose King personally holds it (both stack
    if the King himself holds it: +5 for himself personally, +2 for
    every Kingdom member including himself). Active only under
    ``GameType.ARCANES`` -- 0 for every existing game/test.

    **Bug-compatible with the compiled runtime, not ``TREASURE.X2``'s own
    flavor text**: the dossier confirms the compiled Kingdom-wide check
    never consults the Amulet of Power (94) despite the manual's own
    "Amulet+Scepter" combo description -- replicated here as the King's
    own Scepter possession alone, the same "runtime over flavor text"
    convention this project already applies elsewhere.
    """

    if state.game_type is not GameType.ARCANES:
        return 0
    n = 0
    if _item_count(state, leader.leader_id, Treasure.NAMED_UNIQUE_SCEPTER_LIFE) > 0:
        n += ARCANE_VALOR_SCEPTER_PERSONAL_HIT_POINTS_BONUS
    if leader.kingdom_id is not None:
        king = _king_of_kingdom(state, leader.kingdom_id)
        if king is not None and _item_count(state, king.leader_id, Treasure.NAMED_UNIQUE_SCEPTER_LIFE) > 0:
            n += ARCANE_VALOR_SCEPTER_KINGDOM_HIT_POINTS_BONUS
    return n


ARCANE_VALOR_UNIFICATION_ITEM_COUNT_THRESHOLD = 3


def emperor_holds_arcanes_valor_unification(state: GameState) -> bool:
    """Phase 543: AKGEN_reverse_engineering_report (4).md SS11.3 --
    ``REPORTS.PAS:1510-1517``'s own ``NT_Owned(emperor,Crown_Rohan,
    Scepter_Life,trdex) >= 3`` check. ``NT_Owned`` counts *instances*
    across the ordinal range 93-95 (Crown of Rohan/Amulet of Power/
    Scepter of Life), not "one of each distinct type" -- the dossier's
    own explicit caveat, replicated literally here rather than the more
    intuitive "all three types" reading a name like "unification" might
    suggest.

    Resolves the Emperor the same way ``turn/office_holder.py resolve_
    office_holder(state, Office.EMPEROR)`` does for its own special-cased
    Emperor branch (``state.emperor_kingdom_id``'s own King) -- reusing
    ``_king_of_kingdom`` directly instead of importing that module, which
    would otherwise cycle back here through ``turn/merit_points.py``'s
    own ``effective_skill_level`` import.

    Gated on ``state.game_type is GameType.ARCANES`` like every other
    Arcane's Valor mechanic in this project -- ``False`` for every
    existing game/test.
    """

    if state.game_type is not GameType.ARCANES:
        return False
    if state.emperor_kingdom_id is None:
        return False
    emperor = _king_of_kingdom(state, state.emperor_kingdom_id)
    if emperor is None:
        return False

    count = (
        _item_count(state, emperor.leader_id, Treasure.NAMED_UNIQUE_CROWN_ROHAN)
        + _item_count(state, emperor.leader_id, Treasure.NAMED_UNIQUE_AMULET_POWER)
        + _item_count(state, emperor.leader_id, Treasure.NAMED_UNIQUE_SCEPTER_LIFE)
    )
    return count >= ARCANE_VALOR_UNIFICATION_ITEM_COUNT_THRESHOLD
