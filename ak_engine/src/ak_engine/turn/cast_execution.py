"""Executing a Cast order end-to-end (rulebook [3.10]/[4.21]-[4.25]).

Of the 25 base ``Spell``s, 12 get real execution here as of Phase 59:

- **Charm** and **Kill_Enemy** (Phase 29): see their own helpers below,
  unchanged from Phase 29.
- **Resurrect, Part_Sea, Bless, Flood, Tornado, Earthquake, Oratory,
  Plague, Illus_Terrain, Illus_Armies** (Phase 59): each spell's exact
  numeric mechanics were unavailable to this project until Regolamento
  AK.txt (a more detailed Italian-language rulebook the user supplied)
  spelled out precise percentages, ranges, and targeting rules that the
  English ``RULES.AK``/``ADDEND.AK`` sources never gave -- Phase 29's own
  docstring explicitly named this as the blocker for exactly these ten
  spells ("gives no numeric effect magnitude for any of them"). See each
  ``_execute_*`` helper below for its citation.

**Still unexecuted, each for its own documented reason** (13 of the 25):

- **Skeletal_Army** ([4.25.1]): needs a per-province "how many units of
  what type died here, and when" registry. No such registry exists --
  battle results remove/mutate ``ArmyState`` entries directly
  (``turn/battle_orchestrator.py``, ``turn/aftermath.py``) without
  archiving what was destroyed or where. Building that registry (and
  retrofitting every battle-resolution call site to populate it) is a
  distinct, larger future task, not attempted here.
- **Hide_Feature** ([4.23.3]): targets a "Special Location" in a
  province, but ``models/map.py``'s ``Feature`` is an unpopulated stub
  (Phase 1's own scope note) -- no per-province feature list exists to
  hide an entry from.
- **Clairvoyance** ([4.22.3]): "for the rest of the turn, the caster
  knows everything that happens to the target" needs a per-character
  event feed -- the "story event" model ``ak_engine/report/prose.py``'s
  own Phase 58 docstring already named as a distinct, not-yet-attempted
  future piece.
- **The 10 Personal-Combat-only spells** (Holy_Symbol, Spiritwrack,
  Psychic_Blast, Telek_Storm, Invisibility, Mirror_Image, Fireball,
  Ice_Suspend, Hand_of_Death, Control_Undead -- [4.21.4]-[4.21.5],
  [4.22.4]-[4.22.5], [4.23.4]-[4.23.5], [4.24.4]-[4.24.5],
  [4.25.4]-[4.25.5]): every one of these only ever appears inside an
  encounter's own tactic list (``Maneuver.CAST``, decoded by
  ``turn/search_decode.py`` -- never a top-level ``ActionCode.CAST``
  phase, confirmed by ``turn/cast_decode.py``'s own validation against
  all 108 real sample Cast phases), and casting them requires the
  general tactic-sequence combat engine ``turn/encounter.py``'s own
  docstring explicitly scopes out ("Casting spells / using magic items
  in combat -- no spell-effect or magic-item system exists anywhere in
  this project," plus the missing range-transition state machine and
  monster-HP model a real Piano d'Incontro needs). None of these ten can
  be attempted without building that engine first.

**Every province-targeted spell here shares one targeting mechanism**:
``CastRequest.target`` is a raw hex number (rulebook: "the province you
are in, or one adjacent to it," except Bless, which has no such
restriction). ``_resolve_province_target`` decodes it via
``turn/hex_numbering.py``'s empirically-derived scheme (Phase 11 -- not
100% validated against real adjacency, see that module's own docstring)
and enforces each spell's own same-or-adjacent rule. ``execute_cast``
now takes an optional ``board_width`` (default: the standard 30-wide
board, ``turn/movement.py NORMAL_MAP_BOUNDS``), the same value
``turn/plan_dispatch.py`` already threads through for Move's own hex
decoding.

**The success/failure roll (Phase 30, unchanged)**: rulebook [3.10],
"The chance that an action spell will succeed is 15% plus 15% per
level," and "A character may cast a spell in a Magical ability only if
he has a skill level of 1 or higher in that ability." Resolved via
``LeaderState.skills`` when the caster has it recorded; ``skills is
None`` (no ability data at all) makes every cast succeed outright, same
placeholder convention as Phase 29.

**Level-dependent magnitudes with no recorded caster skill** (Tornado's
per-unit destroy chance, Plague's per-unit destroy chance, Illus_Armies'
strength bonus): fall back to level 0 (no effect), the same "no data ->
no numeric effect" convention ``turn/battle_orchestrator.py``'s
``compute_druidic_shortfall`` already uses, not a guessed level -- see
``_caster_level``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import Terrain
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, is_adjacent

ACTION_SPELL_BASE_CHANCE = 0.15
ACTION_SPELL_CHANCE_PER_LEVEL = 0.15

# Regolamento AK.txt [4.25.3]: "10% di probabilita' di essere distrutte, piu'
# un 10% per livello dell'autore dell'incantesimo" (Plague).
PLAGUE_BASE_DESTROY_CHANCE = 0.10
PLAGUE_DESTROY_CHANCE_PER_LEVEL = 0.10

# [4.24.2]: "un 10% di probabilita' per livello del mago di essere distrutte" (Tornado).
TORNADO_DESTROY_CHANCE_PER_LEVEL = 0.10

# [4.22.1]: "+60% for one turn" (Bless) / [4.24.3]: zeroes revenue (Earthquake).
BLESS_TAX_BONUS_PERCENT = 60
EARTHQUAKE_TAX_MODIFIER_PERCENT = -100

# [4.24.1]: eligible for Flood -- land, non-mountain (Sea is already water;
# Mountain is explicitly excluded by the rulebook's own wording).
_FLOOD_ELIGIBLE_TERRAIN = frozenset({Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST})

_SPELL_ABILITY: dict[Spell, Ability] = {
    Spell.CHARM: Ability.PSYCHIC,
    Spell.KILL_ENEMY: Ability.NECROMANCY,
    Spell.RESURRECTION: Ability.WHITE,
    Spell.PART_SEA: Ability.WHITE,
    Spell.BLESS: Ability.WHITE,
    Spell.FLOOD: Ability.ELEMENTAL,
    Spell.TORNADO: Ability.ELEMENTAL,
    Spell.EARTHQUAKE: Ability.ELEMENTAL,
    Spell.ORATORY: Ability.PSYCHIC,
    Spell.PLAGUE: Ability.NECROMANCY,
    Spell.ILLUS_TERRAIN: Ability.ILLUSION,
    Spell.ILLUS_ARMIES: Ability.ILLUSION,
}


@dataclass(slots=True)
class CastExecutionResult:
    request: CastRequest
    applied: bool
    reason: str | None = None  # set when applied is False


def execute_cast(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: CastRequest,
    rng: random.Random | None = None,
    *,
    board_width: int = NORMAL_MAP_BOUNDS[0],
) -> CastExecutionResult:
    """Apply a decoded Cast request to ``state``, for the spells this project can execute.

    See the module docstring for exactly which spells that is and why.
    ``rng`` is only ever consumed when the caster has real ``skills``
    data recorded (see the module docstring's success-roll section) --
    every existing caller/test that doesn't set it is unaffected.
    ``board_width`` only matters for the province-targeted spells; every
    other spell ignores it.
    """

    rng = rng if rng is not None else random.Random()
    spell = request.spell

    if spell is Spell.CHARM:
        return _execute_charm(state, kingdom_id, leader_id, request, rng)
    if spell is Spell.KILL_ENEMY:
        return _execute_kill_enemy(state, leader_id, request, rng)
    if spell is Spell.RESURRECTION:
        return _execute_resurrection(state, kingdom_id, leader_id, request, rng)
    if spell is Spell.PART_SEA:
        return _execute_part_sea(state, leader_id, request, rng, board_width)
    if spell is Spell.FLOOD:
        return _execute_flood(state, leader_id, request, rng, board_width)
    if spell is Spell.TORNADO:
        return _execute_tornado(state, leader_id, request, rng, board_width)
    if spell is Spell.EARTHQUAKE:
        return _execute_earthquake(state, leader_id, request, rng, board_width)
    if spell is Spell.BLESS:
        return _execute_bless(state, leader_id, request, rng, board_width)
    if spell is Spell.ILLUS_TERRAIN:
        return _execute_illus_terrain(state, leader_id, request, rng, board_width)
    if spell is Spell.ILLUS_ARMIES:
        return _execute_illus_armies(state, leader_id, request, rng)
    if spell is Spell.ORATORY:
        return _execute_oratory(state, leader_id, request, rng)
    if spell is Spell.PLAGUE:
        return _execute_plague(state, leader_id, request, rng, board_width)

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


def _caster_level(caster: LeaderState, ability: Ability) -> int:
    """Real skill level if recorded, else 0 -- see module docstring's "level-dependent
    magnitudes" section.
    """

    if caster.skills is None:
        return 0
    return caster.skills.pair_for_ability(ability)[0]


def _resolve_province_target(state: GameState, caster: LeaderState, target_number: int, board_width: int, *, require_adjacent: bool = True):
    """Decodes+validates a province-targeted spell's raw target. See module docstring.

    Returns ``(None, None)`` if the decoded province is unknown to
    ``state`` or (when ``require_adjacent``) isn't the caster's own
    province or one adjacent to it.
    """

    coord = decode_hex_number(target_number, board_width)
    province = state.provinces.get(coord)
    if province is None:
        return None, None
    if require_adjacent and coord != caster.location:
        bounds = MapBounds(board_width, NORMAL_MAP_BOUNDS[1])
        if not is_adjacent(caster.location, coord, bounds):
            return None, None
    return coord, province


def _execute_charm(
    state: GameState, kingdom_id: int, leader_id: int, request: CastRequest, rng: random.Random
) -> CastExecutionResult:
    """Rulebook [4.22.1]: "a Hero in the same province" -- see module docstring for why
    this differs from Hire (no "must already be independent" requirement).
    """

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


def _execute_resurrection(
    state: GameState, kingdom_id: int, leader_id: int, request: CastRequest, rng: random.Random
) -> CastExecutionResult:
    """Rulebook [4.21.1]: "a character in the same province as a dead one can attempt to
    bring him back to life... with all his Talents but not the items he
    owned... and joins the service of the Kingdom that resurrected him."
    Only the ordinary-Hero case is modeled: the rulebook's separate
    King-via-Heir revival (the Heir must have zero Talents assigned, and
    a revived King resumes his own throne rather than joining the
    reviver's Kingdom) needs a throne/heir-succession model this project
    doesn't have -- out of scope here, not silently mishandled (a King
    in ``dead_leaders`` would incorrectly join the caster's Kingdom via
    this same path, a known, documented gap).
    """

    caster = state.leaders[leader_id]
    target = state.dead_leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    del state.dead_leaders[request.target]
    target.kingdom_id = kingdom_id
    state.leaders[request.target] = target
    return CastExecutionResult(request, applied=True)


def _execute_part_sea(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, board_width: int
) -> CastExecutionResult:
    """Rulebook [4.21.2]: "a Sea province is transformed into a Plain for the rest of
    the turn... only the caster's own province, or one adjacent to it,
    can be targeted."
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if province.terrain is not Terrain.SEA:
        return CastExecutionResult(request, applied=False, reason="target province is not Sea")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.terrain_override = Terrain.PLAINS
    return CastExecutionResult(request, applied=True)


def _execute_flood(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, board_width: int
) -> CastExecutionResult:
    """Rulebook [4.24.1]: "can only be cast on the non-mountain land province you're in,
    or one adjacent to it, turning it into Sea." The secondary "land
    units trapped there" effect is deliberately not modeled: this
    project has no first-class "is this a land unit" classification
    (only per-``ArmyType`` favorable/adverse terrain lists), and flying
    units' status under this specific rule is genuinely ambiguous in the
    rulebook text -- left for a later phase rather than guessed.
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if province.terrain not in _FLOOD_ELIGIBLE_TERRAIN:
        return CastExecutionResult(request, applied=False, reason="target province is not a non-mountain land province")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.terrain_override = Terrain.SEA
    return CastExecutionResult(request, applied=True)


def _execute_tornado(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, board_width: int
) -> CastExecutionResult:
    """Rulebook [4.24.2]: "cast on an enemy province you're in or adjacent to it: every
    unit present (even your own or allied ones) has a 10%-per-mage-level
    chance of being destroyed." No ownership/allegiance check on which
    units get caught in the blast -- the rulebook explicitly says own
    and allied units aren't exempt.
    """

    caster = state.leaders[leader_id]
    coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    chance = TORNADO_DESTROY_CHANCE_PER_LEVEL * _caster_level(caster, Ability.ELEMENTAL)
    for army in list(state.armies_at(coord)):
        if rng.random() < chance:
            state.remove_army(army.army_id)
    return CastExecutionResult(request, applied=True)


def _execute_earthquake(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, board_width: int
) -> CastExecutionResult:
    """Rulebook [4.24.3]: "zeroes the tax revenue of an enemy land province you're in or
    adjacent to it, for one turn." "Not cumulative" -- stored as a
    ``ProvinceState.tax_modifier_percent`` -100 (a set, not an add),
    same convention as Bless's +60.
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if province.terrain is Terrain.SEA:
        return CastExecutionResult(request, applied=False, reason="target province is not land")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.tax_modifier_percent = EARTHQUAKE_TAX_MODIFIER_PERCENT
    return CastExecutionResult(request, applied=True)


def _execute_bless(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, board_width: int
) -> CastExecutionResult:
    """Rulebook [4.21.3]: "the tax revenue of any province on the map (regardless of
    where the caster is) is increased 60% for one turn. Repeated casts
    aren't cumulative." Unlike every other province-targeted spell here,
    Bless has no same-or-adjacent restriction -- ``require_adjacent=False``.
    The addendum rule ("Bless now also removes dead units from a
    province, 10%+10%/level") stays unmodeled: it needs the same
    per-province death registry Skeletal_Army is blocked on (see module
    docstring).
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width, require_adjacent=False)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.tax_modifier_percent = BLESS_TAX_BONUS_PERCENT
    return CastExecutionResult(request, applied=True)


def _execute_illus_terrain(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, board_width: int
) -> CastExecutionResult:
    """Rulebook [4.23.1]: "makes the province you're in (or one adjacent) appear to be a
    different terrain type of your choosing, to anyone examining it from
    an adjacent province." Only the fake-terrain *record* is stored
    (``ProvinceState.illusory_terrain``) -- the "who currently believes
    the illusion," 15%/turn dissolve chance, and blended real/illusory
    combat strength all need exploration/movement-side consumers that
    don't exist yet (see ``models/game_state.py``'s field docstring).
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if not isinstance(request.terrain, Terrain):
        return CastExecutionResult(request, applied=False, reason="fake terrain not specified")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.illusory_terrain = request.terrain
    return CastExecutionResult(request, applied=True)


def _execute_illus_armies(state: GameState, leader_id: int, request: CastRequest, rng: random.Random) -> CastExecutionResult:
    """Rulebook [4.23.2] (Phantasmal Armies): "summons phantom armies that travel with
    him (or with a co-located character) for the rest of the turn,
    increasing the strength of the units he commands 15% per skill
    level. Not cumulative." Target may be the caster himself (the
    generic character-target decode already allows ``request.target ==
    leader_id``). See ``turn/strength.py phantasmal_armies_multiplier``
    for where the stored level is actually consumed in battle.
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    target.phantasmal_armies_level = _caster_level(caster, Ability.ILLUSION)
    return CastExecutionResult(request, applied=True)


def _execute_oratory(state: GameState, leader_id: int, request: CastRequest, rng: random.Random) -> CastExecutionResult:
    """Rulebook [4.22.2]: "cast on yourself or a co-located character: every unit he
    commands is heartened and its rank rises one level for the rest of
    the turn (Green becomes Average, Average becomes Veteran, and so
    on). Repeated casts aren't cumulative." Applied as a direct,
    persistent ``ArmyState.quality`` bump (capped at Elite) rather than a
    strength-pipeline multiplier -- see ``turn/strength.py``'s own module
    docstring for why that's the more faithful reading of "becomes"
    Average/Veteran/etc.
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    if not target.oratory_boosted_this_turn:
        for army in state.armies_commanded_by(request.target):
            army.quality = Quality(min(int(army.quality) + 1, Quality.ELITE))
        target.oratory_boosted_this_turn = True
    return CastExecutionResult(request, applied=True)


def _execute_plague(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, board_width: int
) -> CastExecutionResult:
    """Rulebook [4.25.3]: "cast on a province you're in or adjacent to it: every unit
    there has a 10%+10%/level chance of being destroyed. Only the four
    humanoid races can be infected." The 15%/phase spread to an adjacent
    province stays unmodeled: it needs the same per-phase scheduling
    ``turn/turn_processor.py`` already uses for Defend's reinforcement
    (Phase 57) -- a natural follow-up, not attempted this phase. Armies
    with no recorded ``kingdom_id`` (mercenaries) are skipped: this
    project has no way to know a mercenary army's race.
    """

    caster = state.leaders[leader_id]
    coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")

    succeeded, reason = _roll_cast_success(caster, request.spell, rng)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    chance = PLAGUE_BASE_DESTROY_CHANCE + PLAGUE_DESTROY_CHANCE_PER_LEVEL * _caster_level(caster, Ability.NECROMANCY)
    for army in list(state.armies_at(coord)):
        if army.kingdom_id is None:
            continue
        if state.kingdoms[army.kingdom_id].race not in HUMANOID_RACES:
            continue
        if rng.random() < chance:
            state.remove_army(army.army_id)
    return CastExecutionResult(request, applied=True)
