"""Executing a Pursue (rulebook [3.16]) order -- Phase 51, extended with a
real army-vs-army battle in Phase 53, and a standalone multi-phase
chase-step primitive in Phase 66 (``step_toward_target``/
``advance_pursuit``, not auto-wired anywhere yet -- see that section
below).

**[3.16] Pursue, quoted in full** (also quoted in ``turn/
challenge_pursue_decode.py``'s own docstring):

    A character can be ordered to chase after another character for the
    rest of the turn... You can specify other actions on phases 2
    through 5 which will be attempted if the pursuit is resolved before
    the end of the gameturn. All rules listed under the Encounter
    action apply to Pursuit encounters.
    If both characters lead armies, the pursuing character will attempt
    to run him down and defeat him in battle. If the Pursuing character
    does not lead any armies, then an encounter plan must be specified
    which will be executed if they meet... If the Pursuing character
    leads an army and the pursued character doesn't, or visa versa, the
    Pursue order is ignored.

**Explicitly single-phase, not the persistent multi-phase chase the
rulebook describes** ("chase... for the rest of the turn", "if the
pursuit is resolved before the end of the gameturn"): tracking a Pursue
order's state *across* phases needs the same cross-phase, cross-leader
visibility ``turn/turn_processor.py`` (Phase 45) exists to provide, and
wiring that in is a natural follow-up, not attempted this phase.
``execute_pursue`` answers only "does the pursuer catch up *this*
phase, and if so what happens" -- a single Spy Table roll plus (for the
armyless case) an immediate encounter resolution, not a standing order
that persists into later phases on its own.

**Army-vs-army pursuit now fights a real battle** (Phase 53): "the
pursuing character will attempt to run him down and defeat him in
battle" is resolved by relocating the pursuer's leader and every army
they command to the target's location, then calling ``turn/
battle_orchestrator.py fight_battle`` there. **The relocation-on-
catch-up is a documented design choice, not a rulebook quote**: this
project's single-phase abstraction (see above) has no multi-province
chase path to walk the pursuer's armies along, so "catches up" is
modeled as the pursuer's whole force converging on the target's
province the instant the Spy Table roll succeeds -- the same
abstraction level already used for the armyless case's encounter (no
travel time modeled there either). Two narrow, explicitly-guarded
carve-outs, both falling back to ``caught_up=True`` with a ``reason``
rather than fighting: a pursuer with no Kingdom (``fight_battle``
needs a concrete ``attacker_kingdom_id``, and an independent Hero
leading an army has none), and a target location with no
``ProvinceState`` recorded (``fight_battle`` needs terrain/ownership
data that doesn't exist for an unexplored or out-of-map hex).

**The armyless case reuses ``turn/challenge_execution.py``'s combat
core directly** (``has_combat_intent``, ``is_encounter_accepted``,
Phase 50): "All rules listed under the Encounter action apply to
Pursuit encounters" is read literally here -- a caught-up Pursue target
goes through the exact same [3.12] King/Hero acceptance decision tree
and combat resolution as a Challenge, including a King target's own
``mutual_encounter`` requirement (caller-supplied only, defaulting to
``False``, same documented conservative choice as Phase 50 -- Pursue
gives no more visibility into the target's own orders than Challenge
does). A decisive loser is removed from ``state`` via
``GameState.remove_leader()``, the same generic-Encounter [5.0] "until
one combatant is killed" rule Challenge already applies -- Duel's own
[7.1] no-death special case still doesn't generalize here either.

**Fire Arrow (Phase 273)**: combat resolution now walks ``request.
tactics`` via ``turn/encounter.py resolve_encounter_combat()`` -- see
``turn/challenge_execution.py``'s own Phase 273 note for the full
reasoning (identical here, since Pursue's armyless combat reuses that
same core). ``_leader_combatant`` now also reads ``Ability.ARCHERY``.

**Catch-up chance**: ``turn/spy_table.py``'s ``pursue_catch_up_chance``
([4.33]), driven by the pursuer's real ``Ability.SPY`` skill (0 if
``LeaderState.skills`` is unrecorded, the same placeholder convention
used everywhere else in this project), whether the target leads an army
(always ``False`` in the armyless branch, by construction -- the
army-leading-mismatch check above already guarantees both sides match),
whether pursuer and target share a Kingdom, and ``turn/movement.py``'s
new ``hex_distance`` helper (straight-line hex distance, not
pathfinding -- see that function's own docstring for why).

**Phase 66 -- one scoped step toward the multi-phase chase, confirmed
with the user before implementation as deliberately narrow.** [3.16],
quoted in full above, describes real movement: "he will keep moving
from province to province until he arrives in the province occupied by
the targeted character" -- not just a repeated catch-up roll at a fixed
distance. ``step_toward_target``/``advance_pursuit`` add exactly that
mechanical piece: a greedy hex-distance-minimizing step toward the
target's *current* location (reusing ``turn/movement.py``'s own
``neighbors``/``hex_distance``, the same "not pathfinding, just
straight-line" abstraction ``execute_pursue`` already accepts), then a
fresh ``execute_pursue`` call at the new, shorter distance.

**Explicitly still out of scope, confirmed with the user** (a
substantially larger undertaking, deferred rather than guessed at):

- **Not auto-wired into ``turn/turn_processor.py``'s phase loop.**
  Doing so would require resolving exactly what the rulebook leaves
  ambiguous and this project doesn't attempt here: whether an ongoing,
  uncaught Pursue *preempts* the pursuer's own later-phase orders (the
  rulebook's "other actions... will be attempted if the pursuit is
  resolved before the end of the gameturn" implies yes), how that
  interacts with Multiple Contingents/mutual-encounter detection, and
  how "Characters On Patrol" (self-targeting Pursue, [3.16]) and
  Defend's own "if he receives a Move, Pursue or Trail order, the
  Defend order is cancelled" fit in. ``advance_pursuit`` is a
  standalone, explicitly-invoked primitive a future integration phase
  can call, not automatic behavior today.
- **No movement-point cost.** A normal Move deducts
  ``ArmyState.movement_points``; this step doesn't, since enforcing
  insufficient-movement-to-continue-chasing is part of the same
  larger, deferred integration.
- **Patrol, Defend-cancellation, and catch-conditional later actions**:
  none of these are modeled by this addition.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.turn.battle_orchestrator import BattleReport, fight_battle
from ak_engine.turn.challenge_execution import has_combat_intent, is_encounter_accepted
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.encounter import CHARACTER_HIT_POINTS, Combatant, resolve_encounter_combat
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, hex_distance, neighbors
from ak_engine.turn.spy_table import pursue_catch_up_chance


def _spy_skill_of(state: GameState, leader: LeaderState) -> int:
    return effective_skill_level(state, leader, Ability.SPY)


def _leader_combatant(leader: LeaderState, state: GameState) -> Combatant:
    """Same construction as ``challenge_execution.py _leader_combatant`` (Phase 50),
    duplicated rather than shared -- established precedent in this project
    (see that function's own docstring) for small per-consumer lookups.
    """

    melee_skill = effective_skill_level(state, leader, Ability.MELEE)
    archery_skill = effective_skill_level(state, leader, Ability.ARCHERY)

    neutral_bonus = False
    if leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        neutral_bonus = kingdom is not None and kingdom.alignment is Alignment.NEUTRAL

    return Combatant(
        name=leader.name,
        hit_points=CHARACTER_HIT_POINTS,
        melee_skill=melee_skill,
        archery_skill=archery_skill,
        neutral_duelist_bonus=neutral_bonus,
        temper=leader.temper,
    )


@dataclass(slots=True)
class PursueExecutionResult:
    caught_up: bool
    reason: str | None = None
    combat_occurred: bool = False
    winner_leader_id: int | None = None
    loser_leader_id: int | None = None
    loser_killed: bool = False
    battle_report: BattleReport | None = None
    # Phase 213: the originating request, for a caller (report/turn_report.py
    # describe_turn_results()) that needs the target's own id to resolve a
    # display name -- set by plan_dispatch.py's own dispatcher, not by this
    # function itself (see that module's own Phase 213 note for why:
    # avoids touching every one of this function's own early-return sites).
    # None for any caller that invokes execute_pursue()/advance_pursuit()
    # directly, bypassing dispatch -- the same "not populated outside its
    # real consumer" convention already used elsewhere in this project.
    request: PursueRequest | None = None


def _fight_army_pursuit_battle(
    state: GameState, pursuer: LeaderState, target: LeaderState, rng: random.Random
) -> PursueExecutionResult:
    """Relocates the pursuer's whole force to the target's province and fights a real
    battle there. See module docstring for why relocation-on-catch-up is a
    documented design choice and what the two carve-outs guard against.
    """

    if pursuer.kingdom_id is None:
        return PursueExecutionResult(caught_up=True, reason="pursuer has no Kingdom to fight the battle under")
    if target.location not in state.provinces:
        return PursueExecutionResult(caught_up=True, reason="no province data recorded at the target's location")

    pursuer_armies = state.armies_commanded_by(pursuer.leader_id)
    pursuer_army_ids = [army.army_id for army in pursuer_armies]
    origin = pursuer.location

    pursuer.location = target.location
    for army in pursuer_armies:
        army.location = target.location

    battle_report = fight_battle(
        state, pursuer.kingdom_id, target.location, pursuer_army_ids, attacker_origin=origin, rng=rng,
    )
    return PursueExecutionResult(caught_up=True, combat_occurred=True, battle_report=battle_report)


def execute_pursue(
    state: GameState,
    pursuer_leader_id: int,
    request: PursueRequest,
    rng: random.Random | None = None,
    *,
    mutual_encounter: bool = False,
) -> PursueExecutionResult:
    """Resolve one phase of a Pursue order: [3.16]'s army-leading-match check, a Spy
    Table catch-up roll, and either a real army battle or (armyless case
    only) an immediate Encounter resolution. See module docstring for the
    remaining multi-phase-chase gap and ``mutual_encounter``'s
    caller-supplied-only status.
    """

    rng = rng if rng is not None else random.Random()

    pursuer = state.leaders.get(pursuer_leader_id)
    target = state.leaders.get(request.target_character_id)
    if pursuer is None or target is None:
        return PursueExecutionResult(caught_up=False, reason="pursuer or target not found")

    pursuer_leads_army = bool(state.armies_commanded_by(pursuer.leader_id))
    target_leads_army = bool(state.armies_commanded_by(target.leader_id))
    if pursuer_leads_army != target_leads_army:
        return PursueExecutionResult(caught_up=False, reason="army-leading mismatch, order ignored")

    same_kingdom = pursuer.kingdom_id is not None and pursuer.kingdom_id == target.kingdom_id
    distance = hex_distance(pursuer.location, target.location)
    chance = pursue_catch_up_chance(
        _spy_skill_of(state, pursuer),
        target_leads_army=target_leads_army,
        distance_provinces=distance,
        same_kingdom=same_kingdom,
    )
    if rng.random() >= chance:
        return PursueExecutionResult(caught_up=False, reason="did not catch up this phase")

    if target_leads_army:  # pursuer_leads_army matches, per the check above
        return _fight_army_pursuit_battle(state, pursuer, target, rng)

    if not has_combat_intent(request):
        return PursueExecutionResult(caught_up=True, combat_occurred=False)

    accepted = is_encounter_accepted(
        target_is_king=target.is_king,
        target_leads_army=False,
        challenger_is_king=pursuer.is_king,
        mutual_encounter=mutual_encounter,
        rng=rng,
    )
    if not accepted:
        return PursueExecutionResult(caught_up=True, reason="encounter refused")

    pursuer_combatant = _leader_combatant(pursuer, state)
    target_combatant = _leader_combatant(target, state)
    combat_result = resolve_encounter_combat(
        [tactic.maneuver for tactic in request.tactics], pursuer_combatant, target_combatant, rng
    )

    if combat_result.winner is None:
        return PursueExecutionResult(caught_up=True, combat_occurred=True)

    winner_id, loser_id = (
        (pursuer_leader_id, request.target_character_id)
        if combat_result.winner == "a"
        else (request.target_character_id, pursuer_leader_id)
    )
    state.remove_leader(loser_id)

    return PursueExecutionResult(
        caught_up=True, combat_occurred=True, winner_leader_id=winner_id, loser_leader_id=loser_id, loser_killed=True
    )


def step_toward_target(pursuer_location: HexCoord, target_location: HexCoord, bounds: MapBounds) -> HexCoord:
    """One greedy hex step from ``pursuer_location`` toward ``target_location`` -- [3.16]'s
    "keep moving from province to province until he arrives", reduced to its
    mechanical piece (see module docstring for what's still not wired around
    it). Picks whichever neighbor minimizes ``hex_distance`` to the target,
    the same straight-line abstraction ``execute_pursue`` itself already
    uses -- not real pathfinding (no terrain/ownership avoidance).

    Returns ``pursuer_location`` unchanged if already there, or if
    (degenerate, off-map) there are no neighbors to step to.
    """

    if pursuer_location == target_location:
        return pursuer_location
    candidates = neighbors(pursuer_location, bounds)
    if not candidates:
        return pursuer_location
    return min(candidates, key=lambda candidate: hex_distance(candidate, target_location))


def advance_pursuit(
    state: GameState,
    pursuer_leader_id: int,
    request: PursueRequest,
    rng: random.Random | None = None,
    *,
    mutual_encounter: bool = False,
    board_width: int = NORMAL_MAP_BOUNDS[0],
    board_height: int = NORMAL_MAP_BOUNDS[1],
) -> PursueExecutionResult:
    """Resolve a further phase of an *already-ongoing* Pursue: one ``step_toward_target``
    hex-step for the pursuer (and every army they command, moving together --
    the same leader-plus-armies convention ``turn/move_execution.py`` already
    uses), then a fresh ``execute_pursue`` catch-up attempt at the new,
    shorter distance.

    Callers are responsible for deciding *when* to invoke this across
    phases and for not re-invoking ``execute_pursue`` itself for the same
    (already-advanced) pair -- see module docstring for what's not wired
    automatically yet.
    """

    rng = rng if rng is not None else random.Random()

    pursuer = state.leaders.get(pursuer_leader_id)
    target = state.leaders.get(request.target_character_id)
    if pursuer is None or target is None:
        return PursueExecutionResult(caught_up=False, reason="pursuer or target not found")

    bounds = MapBounds(board_width, board_height)
    new_location = step_toward_target(pursuer.location, target.location, bounds)
    if new_location != pursuer.location:
        pursuer.location = new_location
        for army in state.armies_commanded_by(pursuer_leader_id):
            army.location = new_location

    return execute_pursue(state, pursuer_leader_id, request, rng, mutual_encounter=mutual_encounter)
