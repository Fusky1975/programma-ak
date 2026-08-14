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
   battle.
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

**Still explicitly out of scope**: the rulebook's own multi-phase
persistence rule -- "The movement order will override orders in a
subsequent phase only if the character is practicing in that phase" --
isn't wired into ``turn/turn_processor.py`` this phase. This project
reads that sentence narrowly (a documented interpretation, not the only
possible one): the ongoing chase overrides *specifically* a later
Practice order (letting the character keep chasing instead of stopping
to practice), not every other order type the way Pursue/Trail's own
"for the rest of the turn" persistence (Phase 70) blanket-preempts a
leader's entire remaining plan. Under this reading, any other explicit
later-phase order (another Move, a Search, ...) simply runs as written,
and the chase doesn't auto-continue that phase without a fresh
non-adjacent Move order from the player. The alternative, broader
reading (blanket preemption, mirroring Pursue/Trail exactly) is also
grammatically plausible from the rulebook's own wording alone; this
project didn't find a way to disambiguate it further from the
available source, so wiring *either* interpretation into the
phase-by-phase orchestrator is deferred to a real follow-up phase --
mirroring the same primitive-now/wiring-later split Phase 66 and 70
already used for Pursue/Trail.

**Leader-only movement** (Phase 14): pass ``leader_id`` and an empty
``army_ids`` for a character moving without any army. Per rulebook [3.1]
("If the character has an army with him and the province is occupied by
a enemy army, combat occurs"), combat only triggers when the mover has
at least one army -- a lone character can walk into an enemy-held
province without a fight. Lone characters aren't subject to the
movement-point check either: that's an army property (rulebook [6.2],
"An army's speed determines how far it can move"), and this project
doesn't track a separate per-character movement budget.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.army_type import SEA_ARMY_TYPES, is_land_army
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.treasure import Treasure
from ak_engine.turn.battle_orchestrator import BattleReport, fight_battle
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.contested_province import is_illegal_move_from_contested
from ak_engine.turn.exploration import ExploreResult, discover_features, resolve_explore, resolve_find_mines
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

    **Deliberately not modeled here** (the dossier's own second
    paragraph): when both Fleets and land units accompany the leader,
    the real engine allocates the Fleets' own limited transport capacity
    among the land units by a deterministic priority (speed 1-2 units
    first, tiebroken by lowest army designation) and only the
    land-walking survivors take the ordinary land route instead. This
    project has no Fleet cargo-capacity model at all (no `ArmyState`
    field for it), so that sub-mechanic can't be reproduced without
    inventing one -- ``execute_move()``'s own caller instead requires
    the moving stack to contain no sea-going unit at all
    (``models/army_type.py SEA_ARMY_TYPES``) before granting this
    shortcut, falling back to the ordinary chase-step Move otherwise (a
    safe, conservative default: never wrongly grants the hop, only ever
    withholds it in the one case this project can't fully model).
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
    """

    prior = province.explored_percent_by_kingdom.get(kingdom_id, 0)
    result = resolve_explore(
        prior,
        province.effective_terrain(),
        explorer_skill,
        partial=partial,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
    )
    province.explored_percent_by_kingdom[kingdom_id] = result.new_percent
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
    naval_skill_level: int = 0,
    has_naval_hug_coastline: bool = False,
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
    This project has never derived `ArmyState.movement_points` from a
    base-rate formula (`ArmyState`'s own field comment: "Not auto-reset
    at turn start and not derived from ARMY_TABLE speed + March/Naval
    ability -- the caller sets it") -- rather than invent that missing
    per-turn pipeline, this phase reads the sourced quote literally:
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

    Deliberately **not** addressed this phase: `AdvancedAbility.MARCH_
    THROUGH_FLOODS` (needs a persistent per-province "currently
    flooded" flag this project's own `_execute_flood()` never sets --
    it only ever applies a one-time movement deduction to armies
    present at cast time, nothing a later Move order could consult).
    Left undone and documented here rather than guessed, the same "no
    source, no guess" boundary Melee Control Temper's and Archery's own
    residuals (Phases 519-520) already used. Naval's own movement-point
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
    instead, which this project has no data model for -- the shortcut
    is only granted when every accompanying army is land-based.

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

    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    is_hug_coastline_hop = (
        has_naval_hug_coastline
        and current != target
        and not is_adjacent(current, target, bounds)
        and not any(army.army_type in SEA_ARMY_TYPES for army in armies)
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
        raise ValueError("illegal to move from a contested province to an adjacent enemy province")

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
    )

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

    for army_id in army_ids:
        army = state.armies.get(army_id)
        if army is None:
            continue  # destroyed in the battle
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
        if moved and army.location == current:
            army.location = actual_target

    if leader_id is not None and moved:
        leader = state.leaders.get(leader_id)
        if leader is not None and leader.location == current:
            leader.location = actual_target

    return MoveExecutionResult(
        moved=moved,
        battle_report=battle_report,
        exploration=move_result.exploration,
        movement_points_spent=cost,
        new_location=actual_target if moved else None,
        reached_target=reached_target,
        stopped_chasing=False,
        conquered=conquered,
    )
