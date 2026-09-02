"""Executing a Move order end-to-end (rulebook [3.1], [6.2], [7.7]).

Wires together, in order:

1. **Contested-province check** (Phase 36, rulebook [7.6]): "The leader
   who invaded the contested province will execute his orders in the
   next phase, except that it's illegal to move from a contested
   province to an adjacent enemy province." Raises ``ValueError`` via
   ``turn/contested_province.py is_illegal_move_from_contested()`` when
   the mover's *origin* province is currently contested *by the mover's
   own kingdom* (``ProvinceState.contested_by_kingdom_id == kingdom_id``
   -- not merely contested by anyone, since the rule is specifically
   about "the leader who invaded," i.e. the attacker still stuck there,
   not some third kingdom's army passing through) and the *target*
   province is enemy-owned. ``contested_by_kingdom_id`` has been
   correctly set/cleared by ``turn/battle_orchestrator.py fight_battle()``
   since Phase 9 -- this only adds the read side that was missing. "You
   can, however, move from a province owned by a neutral player-King to
   an enemy province" needs no separate handling: that's just the
   `origin_contested_by_mover=False` case, already legal.
2. ``turn/movement.py resolve_move()`` -- adjacency check + the partial-
   exploration side effect.
3. **Battle trigger**: if the target province holds any army not allied
   with the mover, calls ``turn/battle_orchestrator.py fight_battle()``.
4. ``turn/conquest.py movement_cost_for_move()`` -- movement-point
   deduction, including the extra point for conquering and/or for a sea
   battle. **Phase 651 addendum**: a separate, per-army-type deduction
   right alongside it for Illusory Fog's own "must expend 1 additional
   movement point when entering or leaving" the affected province
   (``turn/cast_execution.py ILLUSORY_FOG_EXTRA_MOVEMENT_COST``/``is_
   illusory_fog_affected_air_unit()``) -- see the call site's own
   comment for why this stays separate from ``movement_cost_for_move()``
   itself (it targets specific army types, not the whole moving party).
   The spell's own end-of-gameturn dissipation
   (``ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN``) is still not
   modeled -- see ``turn/cast_execution.py``'s own Phase 207 addendum
   for why (no end-of-turn cleanup pass exists for any persistent
   province-level spell flag in this project yet, not just this one).
5. ``GameState`` mutation: army relocation (only if the move actually
   succeeds -- an unconquered, contested, or repelled battle leaves the
   mover's surviving armies where ``fight_battle()`` put them, not at the
   target) and the province's exploration-percent update.

**Phase 410 addendum -- uncontested conquest was never wired in until
now.** Steps 3-4 above describe the battle-driven path only
(``fight_battle()``'s own ``defender_clean_swept`` branch was, until
this phase, the *only* place in this project that ever set
``ProvinceState.owner_kingdom_id``). Rulebook [7.7] (quoted in the
module docstring's own citation) frames "conquering an enemy province"
as a property of *entering* it, not of winning a fight there -- and
``report/turn_report.py``'s own ``render_uncontested_conquest()``
(``HostAK/TP/PROSE/CONQ.X``, Phase 63, "a Move that conquers an
undefended enemy province -- no ``_BClash``/``_BWinner`` battle dispatch
involved at all") had been fully built and tested since Phase 63 with
nothing to actually feed it: no code path ever produced a real
uncontested conquest to render. Now, when the target holds no defenders
at all (the ``else`` branch below, not ``occupied_by_enemy``) and the
mover brought at least one army, entering an unowned or enemy-owned
province transfers ownership immediately, matching the same "own it the
instant you're standing in it unopposed" rule a battle-won conquest
already implements. ``turn/conquest.py movement_cost_for_move()``'s own
``conquered`` extra-cost point -- previously unreachable outside a
battle, despite its own module docstring's "conquering an enemy
province slows an army down" text never mentioning a fight as a
precondition -- now applies correctly here too, since it reads this
same ``conquered`` fact regardless of path.

Still out of scope: ``turn/contested_province.py``'s other two functions
-- ``attacker_can_force_rebattle``/``contested_battle_movement_cost`` --
since automatically forcing a rebattle "in the next phase" without a new
player order needs a caller that tracks state across phases for a given
province. ``turn/turn_processor.py run_turn()`` (Phase 45) *is* now a
genuinely phase-by-phase, multi-leader orchestrator -- the structural
gap this note used to point at -- but it doesn't wire this specific
mechanic in yet either; see that module's own docstring for what it
does wire in (Multiple Contingents) and what's still deferred.

**Chasing a non-adjacent target (Phase 85, rulebook [3.1])**: when
``target`` isn't adjacent to the mover's own ``current`` location,
``execute_move()`` no longer raises -- it computes one hex-step toward
``target`` via ``turn/movement.py step_toward_non_adjacent_target()``
(the pure pathfinding primitive Phase 78 built but didn't wire in),
classifying each candidate neighbor's ownership tier from real
``GameState`` data via ``_classify_hex_ownership()`` (Owned/Allied,
via ``state.is_allied()``; Enemy, an owned non-ally; otherwise
Neutral -- ``HexOwnershipTier.HERO_OWNED`` is never produced, the same
documented limitation Phase 78 already flagged: ``ProvinceState``
can't distinguish a Hero-ruled province from a genuinely wild one).

The chosen intermediate hex is, by construction, always adjacent to
``current`` (it's one of `current`'s own neighbors) -- so
``resolve_move()`` itself needed **no changes at all**: it's simply
called with the intermediate hex as its own target, exactly as if that
had been the player's own literal order this phase. This is what makes
exploration correct for a chase step: it's resolved against the
*intermediate* hex's own real province data, never the ultimate
target's (a wrong-terrain bug this design deliberately avoids, per
Phase 78's own note on why this couldn't be a `resolve_move()`-only
fix). If no neighbor is strictly closer than `current` already is --
rulebook: "The character will stop chasing the province if he can't
find a legal way to move closer to it in one phase" --
``MoveExecutionResult.stopped_chasing`` is `True`, `exploration` is
`None`, and nothing else happens (no cost, no relocation).

``MoveExecutionResult.reached_target`` is a purely geometric fact
(``actual_target == target``, i.e. "was this phase's own hop the final
one"), independent of whether the hop itself actually succeeds this
phase (a lost/contested battle at the intermediate hex still leaves
`reached_target=False` if the ultimate target was still further away,
or conversely `True` even for a repelled hop onto an already-adjacent
target -- callers that care whether the mover is *actually* there now
should check `moved` and `new_location` together with
`reached_target`, not `reached_target` alone). A chase step's
enemy-occupied intermediate hex triggers a battle exactly like any
ordinary Move -- the rulebook's chase-toward-target text doesn't
address this case explicitly, so this project treats a chase step as
mechanically identical to a directly-ordered Move to that same hex, a
documented consistency choice rather than a sourced special case.

**Cross-phase persistence -- closed, Phase 632.** The rulebook's own
multi-phase persistence rule -- "The movement order will override
orders in a subsequent phase only if the character is practicing in
that phase" -- has two grammatically plausible readings this project
couldn't disambiguate from the available source alone (narrow: only a
later Practice order is overridden, any other order type runs as
written and the chase doesn't auto-continue without a fresh Move
order; broad: blanket preemption of every subsequent order, mirroring
Pursue/Trail's own "for the rest of the turn" persistence, Phase 70,
exactly). **The user directly confirmed the broad reading.**
``turn/turn_processor.py run_turn()`` now wires it in, reusing the
exact same "PERSISTENT PURSUE/TRAIL CHASE" mechanism (see that
module's own "PERSISTENT MOVE CHASE" docstring section) -- genuinely
simpler than Pursue/Trail's own mirror, since Move's own chase-
stepping already lives entirely inside ``execute_move()`` itself: a
continuation is just redispatching the same ordinary LMOVE phase again
with the same ultimate target, no dedicated ``advance_*`` function
needed.

**Leader-only movement** (Phase 14): pass ``leader_id`` and an empty
``army_ids`` for a character moving without any army. Per rulebook [3.1]
("If the character has an army with him and the province is occupied by
a enemy army, combat occurs"), combat only triggers when the mover has
at least one army -- a lone character can walk into an enemy-held
province without a fight. Lone characters aren't subject to the
movement-point check either: that's an army property (rulebook [6.2],
"An army's speed determines how far it can move"), and this project
doesn't track a separate per-character movement budget.

**Mystic Winds wind-walking notice trigger -- closed, Phase 634.**
``report/turn_report.py record_move_world_events()`` had left `SAY.PAS`
``_LWWalk`` (the sibling of the already-wired ``_LFly`` "flew" notice)
unwired: its own real trigger, ``LeaderState.mystic_winds_active``, is
a single per-leader flag with no record of *which* move it was set
during, and the effect lasts until the leader's own next real battle
(``turn/battle_orchestrator.py fight_battle()``'s own Phase 250
clearing), not just one move -- so reading the flag's *current* value
post-turn can miss an earlier move that happened before an intervening
same-turn battle cleared it. ``MoveExecutionResult.wind_walking`` now
snapshots the flag at the *start* of each ``execute_move()`` call,
before that same call's own ``fight_battle()`` (if any) can clear it --
correct even when the move that triggers the notice is the very one
that ends the spell. Deliberately not extended to `turn/turn_
processor.py`'s own multi-attacker LMOVE path (a separate `resolve_
move()`/`fight_multi_attacker_battle()` route that never calls
``execute_move()`` at all).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.army_type import ARMY_TABLE, SEA_ARMY_TYPES, ArmyType, is_land_army
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import KNOWN_PROVINCE_MIN_PERCENT, ArmyState, GameState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.treasure import Treasure
from ak_engine.turn.battle_orchestrator import BattleReport, fight_battle, mystic_winds_active_for
from ak_engine.turn.cast_execution import ILLUSORY_FOG_EXTRA_MOVEMENT_COST, is_illusory_fog_affected_air_unit
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.contested_province import IllegalMoveFromContestedError, is_illegal_move_from_contested
from ak_engine.turn.exploration import ExploreResult, discover_features, resolve_explore, resolve_find_mines
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.sea_transport import apply_battle_carrier_destruction, board_army, cargo_aboard, disembark_army
from ak_engine.turn.movement import (
    NORMAL_MAP_BOUNDS,
    HexOwnershipTier,
    MapBounds,
    is_adjacent,
    neighbors,
    resolve_move,
    step_toward_non_adjacent_target,
)


# Phase 521: AdvancedAbility.MARCH_CAVALRY/_INFANTRY (+ Mastery tiers) --
# see module docstring's own Phase 521 addendum for the full sourced
# quotes and the split between what's modeled here and what isn't.
MARCH_CAVALRY_MIN_MOVEMENT_POINTS = 3
MARCH_INFANTRY_MOVEMENT_POINTS_RANGE = (1, 2)
MARCH_ABILITY_BONUS = 1
MARCH_MASTERY_ABILITY_BONUS = 2


def march_movement_point_bonus(
    current_movement_points: int,
    *,
    has_march_cavalry: bool = False,
    has_march_cavalry_mastery: bool = False,
    has_march_infantry: bool = False,
    has_march_infantry_mastery: bool = False,
) -> int:
    """The flat movement-point bonus a land army qualifies for right now.

    ``current_movement_points`` is the army's own pool *before* this
    bonus -- Cavalry/Cavalry Mastery only ever apply at 3+, Infantry/
    Infantry Mastery only at 1-2 (rulebook's own two disjoint bands). A
    leader only ever holds one Advanced Ability per category (Phase
    128), so the Mastery tier's own kwarg is read as the ability's
    total, self-contained effect (+2), not "+1 on top of the base tier
    you don't hold" -- the same convention Melee Mastery/True Mastery
    (Phase 517) already established.
    """

    if has_march_cavalry_mastery and current_movement_points >= MARCH_CAVALRY_MIN_MOVEMENT_POINTS:
        return MARCH_MASTERY_ABILITY_BONUS
    if has_march_cavalry and current_movement_points >= MARCH_CAVALRY_MIN_MOVEMENT_POINTS:
        return MARCH_ABILITY_BONUS
    low, high = MARCH_INFANTRY_MOVEMENT_POINTS_RANGE
    if has_march_infantry_mastery and low <= current_movement_points <= high:
        return MARCH_MASTERY_ABILITY_BONUS
    if has_march_infantry and low <= current_movement_points <= high:
        return MARCH_ABILITY_BONUS
    return 0


# Phase 693: AdvancedAbility.MARCH_THROUGH_FLOODS's own real text --
# "One movement point is deducted from all units which have to use
# this ability, after they have moved." See module docstring's own
# Phase 693 addendum for the full reasoning.
MARCH_THROUGH_FLOODS_EXTRA_MOVEMENT_COST = 1


def is_flooded_province(province: ProvinceState) -> bool:
    """True when ``province``'s own current terrain was overridden to Sea by
    Flood (``turn/cast_execution.py _execute_flood()``), not because it's
    naturally Sea terrain. Unambiguous: Part Sea sets the opposite
    direction (``terrain_override = Terrain.PLAINS``), and ``_execute_
    flood()`` only ever succeeds starting from a non-Sea terrain
    (``_FLOOD_ELIGIBLE_TERRAIN``), so a real Sea-terrain province is
    never itself the target of a Flood cast.
    """

    return province.terrain_override is Terrain.SEA


def naval_movement_point_bonus(naval_skill_level: int) -> int:
    """AKGEN_reverse_engineering_report (3).md SS99 (`AKE.EXE:0x21F6A-
    0x22080 MovementBonus`): for Whale League/Fleet/Mermen (`models/
    army_type.py SEA_ARMY_TYPES`), the Naval movement bonus is simply the
    leader's own effective Naval skill level, added straight to whatever
    movement points the army already has -- "Non compare min(4,NA) nel
    ramo navale" (no cap here, unlike the battle-strength bonus's own
    ``min(4, NA)`` cap in ``turn/battle_orchestrator.py``). Unlike March's
    own ``march_movement_point_bonus()``, there's no movement-point band
    to qualify for and no separate Mastery tier -- the raw skill level
    *is* the bonus. Clamped at 0 defensively (``effective_skill_level()``
    should never return negative, but this keeps a stray direct caller
    from ever subtracting movement points here).
    """

    return max(0, naval_skill_level)


def _naval_hug_coastline_move_is_legal(
    state: GameState, origin: HexCoord, target: HexCoord, bounds: MapBounds
) -> bool:
    """AKGEN_reverse_engineering_report (3).md SS106 (`AdvancedAbility.
    NAVAL_HUG_COASTLINE`, `SA.X2:47-49`, `AKE.EXE:0x22153-0x222D0`):

    ```pascal
    if Has_SA(leader,Hug_Coast) and
       origin_is_land and destination_is_land and
       exists sea_hex adjacent_to(origin) and adjacent_to(destination)
    then
       allow_direct_coastal_move;
    ```

    True when ``origin`` and ``target`` are both land provinces (not
    ``Terrain.SEA``, and real province data exists for both -- an
    unexplored/unknown hex, ``Terrain.NO_TERRAIN``, never qualifies)
    that share at least one common neighbor whose own terrain is
    ``Terrain.SEA``. "The two land hexes must share a coastal adjacency
    through a sea hex" -- not a teleport and not an arbitrary route, so
    this is a direct neighbor-set intersection, not a pathfinding search.

    The dossier's own second paragraph, quoted in full: "Se accompagnano
    il leader sia Fleet sia unità terrestri, il motore assegna il
    trasporto al maggior numero possibile di unità" -- deterministic
    priority (speed 1-2 units first, tiebroken by lowest army
    designation) -- "Le unità trasportate restano soggette al divieto di
    usare anche movimento terrestre proprio nello stesso turno; quelle
    non imbarcate percorrono il normale passo terrestre, se legale e con
    punti sufficienti." The real engine genuinely splits a mixed group's
    fate: the carrier(s) plus whatever they manage to board make the
    coastal hop; land stragglers left without a slot travel separately,
    by the ordinary route.

    **Phase 720 -- the priority-allocation rule itself is now reused
    directly** (it's the identical rule already built and tested as
    ``turn/move_execution.py _auto_board_transport_group()``/
    ``_boarding_priority_tier()``, Phase 715) **via an all-or-nothing
    simplification, user-confirmed**: this function's own caller
    (``execute_move()``'s ``is_hug_coastline_hop``) now grants the whole
    group the hop together only when *every* land-type army present
    ends up boarded (``ArmyState.transported_by is not None``, read
    straight off whatever boarding the same call's own earlier ``auto_
    board`` pass already performed -- no separate/duplicate boarding
    logic here); if even one land army is left without a carrier slot,
    the shortcut is denied for the entire group, exactly as before this
    phase. **Deliberately still not modeled**: the real engine's own
    "un-boarded stragglers still travel separately, by the ordinary
    route, while the rest hops" split -- doing that faithfully would
    need ``MoveExecutionResult`` to represent more than one outcome for
    a single ``execute_move()`` call (today it has one ``new_location``
    for the whole group), a real architectural change touching ``report/
    turn_report.py``/``turn/plan_dispatch.py`` too, judged out of scope
    for this phase.
    """

    origin_province = state.provinces.get(origin)
    target_province = state.provinces.get(target)
    if origin_province is None or target_province is None:
        return False
    if origin_province.effective_terrain() in (Terrain.SEA, Terrain.NO_TERRAIN):
        return False
    if target_province.effective_terrain() in (Terrain.SEA, Terrain.NO_TERRAIN):
        return False
    shared_neighbors = set(neighbors(origin, bounds)) & set(neighbors(target, bounds))
    return any(
        (province := state.provinces.get(coord)) is not None and province.effective_terrain() is Terrain.SEA
        for coord in shared_neighbors
    )


@dataclass(slots=True)
class MoveExecutionResult:
    moved: bool
    battle_report: BattleReport | None
    exploration: ExploreResult | None
    movement_points_spent: int
    new_location: HexCoord | None
    reached_target: bool = True
    stopped_chasing: bool = False
    # Phase 410 -- True for *either* a battle-won conquest
    # (``battle_report.conquered``, mirrored here for a single flag
    # callers can check regardless of path) or a real, uncontested one
    # (``battle_report is None``, no defenders were present at all) --
    # see ``execute_move()``'s own Phase 410 addendum.
    conquered: bool = False
    # Phase 490 -- Arch-Mage's own "Sense Magic Items in Province" perk.
    # Never set by ``execute_move()`` itself (this function has no Office
    # context) -- ``None`` for every caller until ``turn/plan_dispatch.py``'s
    # own LMOVE branch fills it in via ``turn/sense_magic_items.py`` after a
    # successful move, the same "assign into the result after the fact"
    # convention the EXPLORE branch already uses for ``discovered_features``.
    sensed_magic_items: list[Treasure] | None = None
    # Phase 634: SAY.PAS `_LWWalk`'s own real trigger -- was the mover's
    # own leader under Mystic Winds (`LeaderState.mystic_winds_active`)
    # at the *start* of this specific `execute_move()` call, snapshotted
    # before this same call's own `fight_battle()` (if any) can clear it
    # -- see `report/turn_report.py record_move_world_events()`'s own
    # Phase 634 addendum for why the caller can't safely reconstruct
    # this after the fact from the leader's own current flag value.
    wind_walking: bool = False
    # Phase 715 -- Fleet/Whale cargo-capacity subsystem's own Phase B:
    # every army id `_auto_board_transport_group()` actually boarded
    # this call (empty when `auto_board` is `False`, the default).
    # Observability for tests and a future report-narration phase --
    # nothing renders this yet. See `turn/sea_transport.py`'s own
    # module docstring for the full mechanic.
    boarded_army_ids: list[int] = field(default_factory=list)


def _classify_hex_ownership(state: GameState, kingdom_id: int, coord: HexCoord) -> HexOwnershipTier:
    """Rulebook [3.1]'s tie-break tiers, from real ``GameState`` data (Phase 85).

    ``HERO_OWNED`` is never produced -- ``ProvinceState`` has no way to
    mark an unowned province as specifically Hero-ruled versus
    genuinely wild, the same documented limitation
    ``turn/movement.py HexOwnershipTier``'s own docstring already
    flagged (Phase 78). An unowned or unknown (no province data) hex
    is classified ``NEUTRAL``.
    """

    province = state.provinces.get(coord)
    if province is None or province.owner_kingdom_id is None:
        return HexOwnershipTier.NEUTRAL
    if province.owner_kingdom_id == kingdom_id or state.is_allied(province.owner_kingdom_id, kingdom_id):
        return HexOwnershipTier.OWNED_OR_ALLIED
    return HexOwnershipTier.ENEMY


@dataclass(slots=True)
class KingdomExplorationResult:
    new_percent: int
    discovered_features: list[Feature]


# Phase 630: the 6 terrain-King royal titles' own MeritTally field
# (`models/game_state.py`, Phase 379) -- `AKGEN_embedded_catalogs.
# json.txt gw_format.royal_title_system` entries 30-35 (Ranger of the
# Plains/Desert Rat/Lord of the Jungle/Warden of the Forests/Mountain
# Man/Ruler of the Waves). Same 6-member `Terrain` set `report/
# ascii_map.py TERRAIN_SYMBOL` already uses -- no 7th real terrain.
_TERRAIN_KING_FIELD: dict[Terrain, str] = {
    Terrain.PLAINS: "plains_explorations",
    Terrain.DESERT: "desert_explorations",
    Terrain.JUNGLE: "jungle_explorations",
    Terrain.FOREST: "forest_explorations",
    Terrain.MTNS: "mountain_explorations",
    Terrain.SEA: "sea_explorations",
}

# Phase 660: the same 6 terrain-King titles' own real "effect_while_held"
# bonus (`models/office.py OFFICE_TITLE_DESCRIPTION`: "can now explore
# [terrain] provinces at double [their] normal rate") -- same 6-member
# Terrain set as _TERRAIN_KING_FIELD above.
_TERRAIN_KING_OFFICE: dict[Terrain, Office] = {
    Terrain.PLAINS: Office.PLAINS_KING,
    Terrain.DESERT: Office.DESERT_KING,
    Terrain.JUNGLE: Office.JUNGLE_KING,
    Terrain.FOREST: Office.FOREST_KING,
    Terrain.MTNS: Office.MOUNTAIN_KING,
    Terrain.SEA: Office.SEA_KING,
}


def record_kingdom_exploration(
    province: ProvinceState,
    kingdom_id: int,
    explorer_skill: int,
    *,
    partial: bool,
    state: GameState | None = None,
    rng: random.Random | None = None,
    has_military_maps: bool = False,
    has_difficult_terrain: bool = False,
    has_find_mines: bool = False,
    leader_id: int | None = None,
) -> KingdomExplorationResult:
    """Advances ``kingdom_id``'s own cumulative exploration of ``province`` (Phase 69) --
    see ``models/game_state.py``'s own module docstring for why this is a
    separate, per-kingdom tracker from ``ProvinceState.explored_percent``.
    Seeded from that kingdom's own prior entry (0 if never recorded before),
    not the shared scalar.

    Phase 242: passing ``state`` also rolls feature discovery for this
    province/kingdom (``turn/exploration.py discover_features()``) using
    the newly-updated percentage. ``state=None`` (the default) skips
    this entirely, preserving every pre-Phase-242 caller's exact
    behavior -- discovery is opt-in, not silently added everywhere.

    Phase 245: returns ``KingdomExplorationResult`` (``new_percent`` plus
    ``discovered_features``, empty when ``state`` is ``None``) instead of
    a bare ``int`` -- previously ``discover_features()``'s own return
    value was computed and thrown away, leaving no way for a caller to
    know *which* features were just found in order to narrate them
    (``report/turn_report.py describe_feature_discovery()``, same phase).

    ``has_military_maps``/``has_difficult_terrain`` (Phase 507) pass
    straight through to ``resolve_explore()`` -- see that function's
    own docstring.

    ``has_find_mines`` (Phase 509): rolls ``turn/exploration.py
    resolve_find_mines()`` once, same ``state``-gated opt-in as feature
    discovery above (the "when exploring an enemy province, this ability
    is not used" check needs real ``GameState`` ownership data). Skipped
    entirely when ``province``'s owner is an enemy of ``kingdom_id`` --
    neutral/unowned and owned-or-allied provinces are both eligible, only
    ``HexOwnershipTier.ENEMY`` is excluded, matching the rulebook text
    exactly. A successful roll mutates ``province.mine_gold_bonus``/
    ``mine_find_attempts`` directly (both province-global, not per-
    kingdom -- see that field's own docstring).

    ``leader_id`` (Phase 630, default ``None``): when given alongside
    ``state``, credits the acting leader's own ``MeritTally`` terrain-
    King royal-title counter (`_TERRAIN_KING_FIELD`) for `province`'s
    own `effective_terrain()` -- "+1 cumulative point when an Explore
    result is recorded in [terrain] terrain" (`royal_title_system`
    entries 30-35). Applies unconditionally on every call this
    parameter is given for (partial or full explore alike, regardless
    of whether the percentage actually changed) -- the real source text
    names no such distinction, so none is invented here. ``None``
    (every pre-Phase-630 caller) leaves this function's prior behavior
    unchanged.

    Phase 660: the same ``state``/``leader_id`` pair also resolves
    whether the acting leader currently *holds* the matching terrain-
    King title (`_TERRAIN_KING_OFFICE`) -- if so, ``resolve_explore()``
    is called with ``has_terrain_king_title=True``, doubling this
    call's own exploration rate (see that function's own Phase 660
    docstring). The exact same gate as the merit credit above, so every
    caller that already passes `state`/`leader_id` for the counter gets
    this for free, no new plumbing needed.
    """

    terrain = province.effective_terrain()
    has_terrain_king_title = False
    if state is not None and leader_id is not None:
        office = _TERRAIN_KING_OFFICE.get(terrain)
        if office is not None:
            holder = resolve_office_holder(state, office)
            has_terrain_king_title = holder is not None and holder.leader_id == leader_id

    prior = province.explored_percent_by_kingdom.get(kingdom_id, 0)
    result = resolve_explore(
        prior,
        terrain,
        explorer_skill,
        partial=partial,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
        has_terrain_king_title=has_terrain_king_title,
    )
    province.explored_percent_by_kingdom[kingdom_id] = result.new_percent
    if state is not None and leader_id is not None:
        leader = state.leaders.get(leader_id)
        field = _TERRAIN_KING_FIELD.get(terrain)
        if leader is not None and field is not None:
            setattr(leader.merit_tally, field, getattr(leader.merit_tally, field) + 1)
    discovered: list[Feature] = []
    if state is not None:
        rng = rng if rng is not None else random.Random()
        if has_find_mines and _classify_hex_ownership(state, kingdom_id, province.coord) is not HexOwnershipTier.ENEMY:
            gold = resolve_find_mines(
                province.effective_terrain(), province.mine_find_attempts, province.mine_gold_bonus, rng
            )
            province.mine_find_attempts += 1
            province.mine_gold_bonus += gold
        discovered = discover_features(state, province.coord, kingdom_id, result.new_percent, rng)
    return KingdomExplorationResult(result.new_percent, discovered)


def reveal_adjacent_provinces(state: GameState, province: ProvinceState, kingdom_id: int, bounds: MapBounds) -> None:
    """"Known provinces" (Phase 623, `models/game_state.py`'s own
    module docstring addendum): entering `province` also reveals each
    of its own real neighbors to `kingdom_id` at the flat `KNOWN_
    PROVINCE_MIN_PERCENT` floor, if not already known -- the user's own
    example, "passing by way of an adjacent province." Never *lowers* a
    neighbor's own recorded percentage (`known_to_kingdom()` is already
    `True` for anything at or above the floor, so this only ever writes
    a neighbor that was still fully unknown). Called at every site that
    already calls `record_kingdom_exploration()` for a real province
    entry -- see this module's own Phase 623 addendum in each caller.
    """

    for neighbor in neighbors(province.coord, bounds):
        neighbor_province = state.provinces.get(neighbor)
        if neighbor_province is not None and not neighbor_province.known_to_kingdom(kingdom_id):
            neighbor_province.explored_percent_by_kingdom[kingdom_id] = KNOWN_PROVINCE_MIN_PERCENT


# Phase 715 -- the one real, sourced allocation-priority order found for
# this whole subsystem (`AKGEN_reverse_engineering_report (3).md` SS106,
# scoped there to `AdvancedAbility.NAVAL_HUG_COASTLINE` specifically):
# "prima unità con velocità base 1 o 2, a parità designazione/ID di
# armata più basso" -- reused directly here as the one real, documented
# priority, since no other source gives a different one for ordinary
# transport.
# Phase 717: Dragon Wing/Eagle Wing join as carriers too -- `Regolamento
# AK.txt`'s own "Possono trasportare un'unità di fanteria ciascuna,"
# an unconditional base rule (no Advanced Ability gate).
_CARRIER_ARMY_TYPES = (ArmyType.FLEET, ArmyType.WHALES, ArmyType.DRAGON_WING, ArmyType.EAGLE_WING)


def _boarding_priority_tier(army_type: ArmyType) -> int:
    """0 = "speed 1 or 2" (boards first); 1 = everything else, including
    the handful of `ArmyType` members with no `ARMY_TABLE` entry at all
    (Vampires, Marauders, Shamans, Crossbow, Javelins, Artillery,
    Spiders, D Turtle -- a real, pre-existing gap, confirmed by direct
    check) -- a safe, conservative fallback (never wrongly claims the
    high-priority tier for a type whose real speed isn't recorded),
    not a crash.
    """

    stats = ARMY_TABLE.get(army_type)
    return 0 if stats is not None and stats.speed <= 2 else 1


def _auto_board_transport_group(
    state: GameState,
    armies: list[ArmyState],
    *,
    caster_has_druidic_whale_transport: bool = False,
    caster_has_druidic_transport: bool = False,
) -> list[int]:
    """Automatically boards as many eligible land armies as fit onto
    whichever Fleet/Whale carriers are moving in the same group -- see
    ``execute_move()``'s own Phase 715 addendum. Returns every army id
    actually boarded this call.
    """

    carriers = sorted((army for army in armies if army.army_type in _CARRIER_ARMY_TYPES), key=lambda army: army.army_id)
    if not carriers:
        return []

    candidates = sorted(
        (army for army in armies if army.army_type not in _CARRIER_ARMY_TYPES and army.transported_by is None),
        key=lambda army: (_boarding_priority_tier(army.army_type), army.army_id),
    )

    boarded_army_ids: list[int] = []
    for candidate in candidates:
        for carrier in carriers:
            if board_army(
                state,
                candidate.army_id,
                carrier.army_id,
                caster_has_druidic_whale_transport=caster_has_druidic_whale_transport,
                caster_has_druidic_transport=caster_has_druidic_transport,
            ):
                boarded_army_ids.append(candidate.army_id)
                break
    return boarded_army_ids


def execute_move(
    state: GameState,
    kingdom_id: int,
    army_ids: list[int],
    target: HexCoord,
    *,
    leader_id: int | None = None,
    explorer_skill: int = 0,
    loser_retreats: bool = True,
    rng: random.Random | None = None,
    has_military_maps: bool = False,
    has_difficult_terrain: bool = False,
    has_find_mines: bool = False,
    has_march_cavalry: bool = False,
    has_march_cavalry_mastery: bool = False,
    has_march_infantry: bool = False,
    has_march_infantry_mastery: bool = False,
    has_march_through_floods: bool = False,
    naval_skill_level: int = 0,
    has_naval_hug_coastline: bool = False,
    auto_board: bool = False,
    caster_has_druidic_whale_transport: bool = False,
    caster_has_druidic_transport: bool = False,
) -> MoveExecutionResult:
    """Move ``army_ids`` (all from the same province) toward ``target``.

    ``army_ids`` may be empty if ``leader_id`` is given -- a character
    moving alone. Fights a battle automatically if the hex actually
    entered this phase holds a non-allied army AND the mover brought at
    least one army of their own. Raises if the armies don't share a
    starting province, if any lacks a movement point, if neither
    ``army_ids`` nor ``leader_id`` is given, or if the hex actually
    entered this phase has no province data.

    **Phase 521 -- March category, `AdvancedAbility.MARCH_CAVALRY`/
    `_INFANTRY` (+ Mastery tiers).** `models/advanced_ability.py`'s own
    sourced text: Cavalry "adds one to the movement rate of land armies
    which start with 3 or more movement points"; Infantry, the same for
    "1-2 movement points"; each Mastery tier "adds one more" to its own
    band. Rulebook [6.2] itself frames this as dynamic, not a pre-turn
    recompute: "The increased army-movement allowed by the March and
    Naval abilities is always calculated at the moment an army moves."
    Rather than fold the bonus into a precomputed base rate, this phase
    reads the sourced quote literally:
    `execute_move()` grants the bonus as a one-time addition to the
    army's own *current* pool, right before this move's own cost is
    deducted, gated on `ArmyState.march_bonus_applied_this_turn` so a
    multi-phase turn (several Move orders) can't re-grant it. A leader
    only ever holds one Advanced Ability per category (Phase 128), so a
    Mastery tier's own "adds one more" is read as its own total,
    self-contained effect (+2), not "+1 on top of the base tier you
    don't hold" -- the same convention Melee Mastery/True Mastery
    (Phase 517) already established. "Land armies" excludes the three
    purely sea-going types (`models/army_type.py SEA_ARMY_TYPES` --
    Fleet, Whales, Mermen); air units (Dragon Wing/Eagle Wing) were
    originally left land-eligible here too, since no source at the time
    narrowed the wording to exclude them -- **corrected in Phase 523**,
    see that addendum below.

    **Phase 693 -- `AdvancedAbility.MARCH_THROUGH_FLOODS`, closing the
    stale blocker directly above (kept for history, corrected here).**
    That note claimed this project's own `_execute_flood()` "never
    sets" a persistent per-province "currently flooded" flag -- stale
    since Phase 225/226, over 166 phases before this note was written:
    `_execute_flood()` (`turn/cast_execution.py`) sets `ProvinceState.
    terrain_override = Terrain.SEA`, and `effective_terrain()` has read
    it ever since. That override is unambiguously Flood's own signal --
    Part Sea sets the opposite direction (`terrain_override = Terrain.
    PLAINS`), and every real Flood target starts from `_FLOOD_ELIGIBLE_
    TERRAIN` (never a province already Sea) -- see `is_flooded_
    province()` below. The sourced text itself -- "it becomes possible
    for armies to enter or leave any province affected by the Flood
    spell. One movement point is deducted from all units which have to
    use this ability, after they have moved" -- is read the same way
    Phase 651 (Illusory Fog's own "must expend 1 additional movement
    point when entering or leaving it") already read an analogous
    clause: this project has no general terrain-movement-legality gate
    anywhere (no code blocks a land army from entering a Sea-terrain
    province, flooded or naturally Sea, at all), so "becomes possible"
    is modeled as a movement-point surcharge for land armies making
    such a move, not as an invented blocking mechanic for a restriction
    this project doesn't otherwise model. Naval's own movement-point
    bonus is closed in Phase 523, and both remaining Naval members
    (`NAVAL_LONG_DEFEND`, `NAVAL_HUG_COASTLINE`) are closed in Phase
    524 -- see the addenda below.

    **Phase 523 -- Naval movement bonus + air-unit correction.**
    `AKGEN_reverse_engineering_report (3).md` SS97-99 (disassembly of
    `AKE.EXE:0x21F6A-0x22080 MovementBonus`) gives the real per-army-
    type dispatcher this project never had a source for before:

    ```pascal
    case at of
      Dragonwing, Eaglewing: MovementBonus := 0;
      WhaleLeague, Fleet, Mermen: MovementBonus := M_Skill(leader, Naval);
      else: MovementBonus := MarchBonus(army_id, leader);
    end;
    ```

    Two consequences: (1) Whale League/Fleet/Mermen (`SEA_ARMY_TYPES`)
    get a movement bonus equal to the leader's own effective Naval skill
    level, uncapped ("Non compare min(4,NA) nel ramo navale") -- wired
    exactly like March's own bonus, a one-time addition right before
    this move's cost is deducted, gated on the new `ArmyState.naval_
    bonus_applied_this_turn` flag; (2) Dragon Wing/Eagle Wing get a flat
    zero from *either* ability -- a real, sourced correction to the
    Phase 521 paragraph above, which had assumed air units stayed
    March-eligible for lack of a narrowing source. `models/army_type.py
    is_land_army()` now excludes `OVERFLIGHT_AIR` too, so this also
    quietly fixes March for air units at the same time. `naval_skill_
    level` (default 0, the acting leader's `effective_skill_level(state,
    leader, Ability.NAVAL)`, threaded in by `turn/plan_dispatch.py`)
    isn't itself Advanced-Ability-gated -- unlike March, Naval's
    movement bonus is a plain function of raw skill, no Mastery tier or
    band-of-current-movement-points qualifier involved.

    **Phase 524 -- `AdvancedAbility.NAVAL_HUG_COASTLINE`, the last
    Naval member.** (`NAVAL_LONG_DEFEND`, the other one, is closed the
    same phase but lives entirely in `turn/defend_execution.py` -- see
    that module's own Phase 524 addendum, not this one.) SS106's own
    compiled gate (`SA.X2:47-49`, `AKE.EXE:0x22153-0x222D0`): a leader
    holding this ability can hop directly between two land provinces
    that share a common sea-hex neighbor, "slipping in and out of
    shallows along the coast," without a separate order into that sea
    hex. `has_naval_hug_coastline=True` extends the adjacency check this
    function already makes before falling back to a multi-phase chase:
    if the target isn't geometrically adjacent but the hop is Hug-
    Coastline-legal (`_naval_hug_coastline_move_is_legal()`), it's
    resolved as an ordinary one-hex move to the real target instead of
    a chase step -- same cost formula, same battle trigger, same
    exploration update, no special-casing needed anywhere else in this
    function. Deliberately excluded (see that helper's own docstring):
    when a Fleet/Whale/Mermen unit travels in the same stack, the real
    engine's own transport-capacity allocation sub-mechanic would apply
    instead -- **Phase 715** built that capacity model (`turn/sea_
    transport.py`), but this specific shortcut still isn't wired to it
    (a different, more specific priority rule, see that helper's own
    docstring); the shortcut is still only granted when every
    accompanying army is land-based.

    If ``target`` isn't adjacent to the mover's own current location,
    this is a chase (Phase 85, rulebook [3.1]): one hex-step toward
    ``target`` is computed and resolved instead, and
    ``MoveExecutionResult.reached_target``/``stopped_chasing`` report
    how it went -- see this module's own docstring for the full
    behavior and what's still not wired in (multi-phase persistence).

    Phase 521: ``has_march_cavalry``/``has_march_cavalry_mastery``/
    ``has_march_infantry``/``has_march_infantry_mastery`` (default
    False) grant ``march_movement_point_bonus()`` to a qualifying land
    army, at most once per gameturn per army (``ArmyState.march_bonus_
    applied_this_turn``) -- see module docstring's own Phase 521
    addendum.

    Phase 523: ``naval_skill_level`` (default 0) grants ``naval_
    movement_point_bonus()`` to a Whale League/Fleet/Mermen army, at
    most once per gameturn per army (``ArmyState.naval_bonus_applied_
    this_turn``) -- see module docstring's own Phase 523 addendum.

    Phase 524: ``has_naval_hug_coastline`` (default False) lets a
    non-adjacent land-to-land hop that shares a coastal sea-hex
    neighbor resolve as an ordinary move instead of a chase step -- see
    module docstring's own Phase 524 addendum.

    **Phase 715 -- Fleet/Whale cargo-capacity subsystem, Phase B.**
    ``auto_board`` (default False) turns on automatic boarding: when the
    moving party contains a Fleet/Whale alongside eligible land armies,
    as many as fit are boarded onto it (``turn/sea_transport.py
    can_board()``'s own real capacity rules, ``caster_has_druidic_
    whale_transport``/``caster_has_druidic_transport`` gating the two
    Advanced-Ability extensions) before movement points are ever
    touched -- see ``_auto_board_transport_group()`` below. A boarded
    army spends none of its own movement points this call (rulebook:
    "cannot use a land movement point and be transported... in the same
    turn") -- only its carrier pays the ordinary cost. An army that was
    already boarded, moving without its own carrier this call (in
    either direction -- the cargo moving alone, or the carrier moving
    without some of its cargo), is disembarked first/left behind --
    see the real code for both checks, right below and near the end of
    this function. **Deliberately not enforced here**: the real
    rulebook restriction that land units can *only* move via sea when
    transported -- this project has no general terrain-movement-
    legality gate anywhere (Phase 693's own note above still applies),
    and several existing tests for unrelated features (Illusory Fog,
    March Through Floods, sea-conquest surcharges) depend on that
    permissiveness -- adding a real legality gate is a deliberately
    separate, larger, not-yet-attempted follow-up. ``auto_board``
    itself defaults False, so every pre-Phase-715 caller (including
    every direct test call) is completely unaffected; only ``turn/
    plan_dispatch.py dispatch_phase()``'s own real LMOVE dispatch passes
    ``True``.
    """

    rng = rng if rng is not None else random.Random()
    if not army_ids and leader_id is None:
        raise ValueError("no armies and no leader given -- nothing to move")

    armies = [state.armies[army_id] for army_id in army_ids]
    if armies:
        current = armies[0].location
        if any(army.location != current for army in armies):
            raise ValueError("all armies must move together from the same province")
        if any(army.movement_points < 1 for army in armies):
            raise ValueError("an army with no movement points left this gameturn can't move")
    else:
        current = state.leaders[leader_id].location

    # Phase 715 -- an army moving without its own current carrier (the
    # carrier's own id isn't part of this same move) naturally leaves
    # it. Unconditional (not gated on auto_board) -- a correctness fix,
    # not a new mechanic; a no-op for every army whose transported_by
    # is already None. See the docstring's own Phase 715 addendum.
    for army in armies:
        if army.transported_by is not None and army.transported_by not in army_ids:
            disembark_army(state, army.army_id)

    boarded_army_ids: list[int] = []
    if auto_board:
        boarded_army_ids = _auto_board_transport_group(
            state,
            armies,
            caster_has_druidic_whale_transport=caster_has_druidic_whale_transport,
            caster_has_druidic_transport=caster_has_druidic_transport,
        )

    # Phase 634: snapshotted here, before this same call's own
    # fight_battle() (below) can clear it -- see MoveExecutionResult.
    # wind_walking's own docstring for why this must happen now, not
    # read from the leader after the fact.
    leader_snapshot = state.leaders.get(leader_id) if leader_id is not None else None
    wind_walking = leader_snapshot is not None and leader_snapshot.mystic_winds_active

    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    # Phase 720: a mixed stack (a sea-going carrier present alongside
    # land units) still qualifies for the whole-group hop when every
    # land-type army in it ended up boarded by the auto_board pass
    # above (SS106's own capacity-allocation rule, all-or-nothing --
    # see _naval_hug_coastline_move_is_legal()'s own Phase 720
    # addendum). A pure land stack has no army needing transported_by
    # at all, so this is vacuously satisfied, unchanged from before.
    is_hug_coastline_hop = (
        has_naval_hug_coastline
        and current != target
        and not is_adjacent(current, target, bounds)
        and (
            not any(army.army_type in SEA_ARMY_TYPES for army in armies)
            or all(army.transported_by is not None for army in armies if is_land_army(army.army_type))
        )
        and _naval_hug_coastline_move_is_legal(state, current, target, bounds)
    )
    if current != target and not is_adjacent(current, target, bounds) and not is_hug_coastline_hop:
        next_hex = step_toward_non_adjacent_target(
            current, target, bounds, lambda c: _classify_hex_ownership(state, kingdom_id, c)
        )
        if next_hex is None or next_hex == current:
            return MoveExecutionResult(
                moved=False,
                battle_report=None,
                exploration=None,
                movement_points_spent=0,
                new_location=None,
                reached_target=False,
                stopped_chasing=True,
                wind_walking=wind_walking,
            )
        actual_target = next_hex
        reached_target = False
    else:
        actual_target = target
        reached_target = True

    target_province = state.provinces.get(actual_target)
    if target_province is None:
        raise ValueError(f"no province data for {actual_target}")

    origin_province = state.provinces.get(current)
    origin_contested_by_mover = origin_province is not None and origin_province.contested_by_kingdom_id == kingdom_id
    target_owner_is_enemy = target_province.owner_kingdom_id is not None and not state.is_allied(
        target_province.owner_kingdom_id, kingdom_id
    )
    if is_illegal_move_from_contested(origin_contested_by_mover, target_owner_is_enemy):
        raise IllegalMoveFromContestedError("illegal to move from a contested province to an adjacent enemy province")

    defenders_present = [
        army
        for army in state.armies_at(actual_target)
        if army.kingdom_id is not None and not state.is_allied(army.kingdom_id, kingdom_id)
    ]
    occupied_by_enemy = bool(armies) and bool(defenders_present)

    move_result = resolve_move(
        current,
        actual_target,
        bounds,
        target_terrain=target_province.effective_terrain(),
        target_explored_percent=target_province.explored_percent,
        explorer_skill=explorer_skill,
        occupied_by_enemy=occupied_by_enemy,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
        require_adjacent=not is_hug_coastline_hop,
    )
    target_province.explored_percent = move_result.exploration.new_percent
    record_kingdom_exploration(
        target_province,
        kingdom_id,
        explorer_skill,
        partial=True,
        state=state,
        rng=rng,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
        has_find_mines=has_find_mines,
        leader_id=leader_id,
    )
    reveal_adjacent_provinces(state, target_province, kingdom_id, bounds)

    # Phase 541 -- Map of the Marauders "+1 hex to sea vision during
    # movement" (AKGEN_reverse_engineering_report (4).md SS11), a
    # **declared-original** mechanic, not reverse-engineered: this
    # project has no hex-radius vision/scouting concept anywhere to hook
    # a literal "+1 hex vision" into (exploration is purely a per-
    # province cumulative percentage). The closest honest mechanical
    # translation, reusing existing infrastructure rather than inventing
    # a new "visible hex" registry: a leader holding the item who just
    # entered a sea province also extends their own kingdom's partial-
    # exploration credit one hex further, to whichever sea neighbor of
    # the entered hex isn't the one just left (an approximation of
    # "continuing the same direction of travel" -- this call site has no
    # clean direction vector available, only the two endpoints).
    if leader_id is not None and target_province.effective_terrain() is Terrain.SEA:
        leader = state.leaders.get(leader_id)
        if leader is not None and any(
            item.treasure is Treasure.NAMED_UNIQUE_MAP_MARAUDERS for item in state.items_held_by(leader_id)
        ):
            for further_hex in neighbors(actual_target, bounds):
                if further_hex == current:
                    continue
                further_province = state.provinces.get(further_hex)
                if further_province is not None and further_province.effective_terrain() is Terrain.SEA:
                    record_kingdom_exploration(
                        further_province,
                        kingdom_id,
                        explorer_skill,
                        partial=True,
                        state=state,
                        rng=rng,
                        has_military_maps=has_military_maps,
                        has_difficult_terrain=has_difficult_terrain,
                        has_find_mines=has_find_mines,
                        leader_id=leader_id,
                    )
                    reveal_adjacent_provinces(state, further_province, kingdom_id, bounds)
                    break

    battle_report = None
    conquered = False
    if occupied_by_enemy:
        battle_report = fight_battle(
            state,
            kingdom_id,
            actual_target,
            army_ids,
            loser_retreats=loser_retreats,
            attacker_origin=current,
            rng=rng,
        )
        # Phase 716: the cargo sinks with the carrier.
        apply_battle_carrier_destruction(
            state,
            battle_report.destroyed_army_ids,
            battle_report.disbanded_army_ids,
            battle_report.pursuit_destroyed_army_ids,
        )
        conquered = battle_report.conquered
        moved = conquered
    else:
        moved = True
        # Phase 410 -- rulebook [7.7]: entering an enemy or unowned
        # province, uncontested (no defenders present at all -- a real
        # battle is handled above), still conquers it. `armies` (not
        # `army_ids`) gates this on a genuine military presence, matching
        # [7.7]'s own framing ("a military unit... enters an enemy
        # province") -- a leader moving alone conquers nothing.
        needs_conquest = target_province.owner_kingdom_id is None or (
            target_province.owner_kingdom_id != kingdom_id
            and not state.is_allied(target_province.owner_kingdom_id, kingdom_id)
        )
        if armies and needs_conquest:
            target_province.owner_kingdom_id = kingdom_id
            conquered = True

    cost = movement_cost_for_move(
        is_sea_province=target_province.effective_terrain() == Terrain.SEA,
        battle_occurred=occupied_by_enemy,
        conquered=conquered,
    )

    # Phase 651, Illusory Fog's own [3.11]-addendum text: "must expend 1
    # additional movement point when entering or leaving it" -- either
    # province being fogged triggers the surcharge (origin_province is
    # already resolved above); "the movement point is deducted after the
    # unit(s) have already moved," the same "may wind up with negative
    # movement points" convention turn/conquest.py's own module docstring
    # already established for the conquest/sea-battle surcharges -- kept
    # as a separate, per-army-type deduction rather than folded into
    # `cost` above, since (unlike those two) it applies only to affected
    # units (`turn/cast_execution.py is_illusory_fog_affected_air_unit()`),
    # not the whole moving party uniformly.
    fog_affected_move = (origin_province is not None and origin_province.illusory_fog_active) or (
        target_province.illusory_fog_active
    )

    # Phase 693: AdvancedAbility.MARCH_THROUGH_FLOODS -- see module
    # docstring's own Phase 693 addendum. Gated on the acting leader's
    # own Advanced Ability, applied to every land army in the moving
    # party (this project has no per-army-type gate for it, unlike
    # Illusory Fog's own air-unit-only scope above).
    flood_affected_move = has_march_through_floods and (
        (origin_province is not None and is_flooded_province(origin_province)) or is_flooded_province(target_province)
    )

    for army_id in army_ids:
        army = state.armies.get(army_id)
        if army is None:
            continue  # destroyed in the battle
        # Phase 715: an army actually being carried this move (boarded,
        # by this call or an earlier one, onto a carrier also part of
        # this same move) spends none of its own movement points --
        # rulebook: "cannot use a land movement point and be
        # transported... in the same turn" -- only its carrier pays.
        carried_this_move = army.transported_by is not None and army.transported_by in army_ids
        if not carried_this_move:
            if not army.march_bonus_applied_this_turn and is_land_army(army.army_type):
                bonus = march_movement_point_bonus(
                    army.movement_points,
                    has_march_cavalry=has_march_cavalry,
                    has_march_cavalry_mastery=has_march_cavalry_mastery,
                    has_march_infantry=has_march_infantry,
                    has_march_infantry_mastery=has_march_infantry_mastery,
                )
                if bonus:
                    army.movement_points += bonus
                    army.march_bonus_applied_this_turn = True
            if not army.naval_bonus_applied_this_turn and army.army_type in SEA_ARMY_TYPES:
                naval_bonus = naval_movement_point_bonus(naval_skill_level)
                if naval_bonus:
                    army.movement_points += naval_bonus
                    army.naval_bonus_applied_this_turn = True
            army.movement_points -= cost
            if fog_affected_move and is_illusory_fog_affected_air_unit(army.army_type, mystic_winds_active_for(army, state)):
                army.movement_points -= ILLUSORY_FOG_EXTRA_MOVEMENT_COST
            if flood_affected_move and is_land_army(army.army_type):
                army.movement_points -= MARCH_THROUGH_FLOODS_EXTRA_MOVEMENT_COST
        if moved and army.location == current:
            army.location = actual_target

    if leader_id is not None and moved:
        leader = state.leaders.get(leader_id)
        if leader is not None and leader.location == current:
            leader.location = actual_target

    # Phase 715: cargo left behind when its carrier moves without it
    # this same call (the carrier's own id is in army_ids, but the
    # cargo's own isn't) -- disembarked, not silently left "aboard" a
    # carrier that's now elsewhere.
    for army_id in army_ids:
        carrier = state.armies.get(army_id)
        if carrier is None or carrier.army_type not in _CARRIER_ARMY_TYPES:
            continue
        for cargo in cargo_aboard(state, army_id):
            if cargo.army_id not in army_ids:
                disembark_army(state, cargo.army_id)

    return MoveExecutionResult(
        moved=moved,
        battle_report=battle_report,
        exploration=move_result.exploration,
        movement_points_spent=cost,
        new_location=actual_target if moved else None,
        reached_target=reached_target,
        stopped_chasing=False,
        conquered=conquered,
        wind_walking=wind_walking,
        boarded_army_ids=boarded_army_ids,
    )
