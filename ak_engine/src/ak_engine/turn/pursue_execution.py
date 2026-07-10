"""Executing a Pursue (rulebook [3.16]) order, single phase only -- Phase 51,
extended with a real army-vs-army battle in Phase 53.

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
and Melee duel as a Challenge, including a King target's own
``mutual_encounter`` requirement (caller-supplied only, defaulting to
``False``, same documented conservative choice as Phase 50 -- Pursue
gives no more visibility into the target's own orders than Challenge
does). A decisive loser is removed from ``state`` via
``GameState.remove_leader()``, the same generic-Encounter [5.0] "until
one combatant is killed" rule Challenge already applies -- Duel's own
[7.1] no-death special case still doesn't generalize here either.

**Catch-up chance**: ``turn/spy_table.py``'s ``pursue_catch_up_chance``
([4.33]), driven by the pursuer's real ``Ability.SPY`` skill (0 if
``LeaderState.skills`` is unrecorded, the same placeholder convention
used everywhere else in this project), whether the target leads an army
(always ``False`` in the armyless branch, by construction -- the
army-leading-mismatch check above already guarantees both sides match),
whether pursuer and target share a Kingdom, and ``turn/movement.py``'s
new ``hex_distance`` helper (straight-line hex distance, not
pathfinding -- see that function's own docstring for why).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.turn.battle_orchestrator import BattleReport, fight_battle
from ak_engine.turn.challenge_execution import has_combat_intent, is_encounter_accepted
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.encounter import CHARACTER_HIT_POINTS, Combatant, resolve_melee_duel
from ak_engine.turn.movement import hex_distance
from ak_engine.turn.spy_table import pursue_catch_up_chance


def _spy_skill_of(leader: LeaderState) -> int:
    if leader.skills is None:
        return 0
    return leader.skills.pair_for_ability(Ability.SPY)[0]


def _leader_combatant(leader: LeaderState, state: GameState) -> Combatant:
    """Same construction as ``challenge_execution.py _leader_combatant`` (Phase 50),
    duplicated rather than shared -- established precedent in this project
    (see that function's own docstring) for small per-consumer lookups.
    """

    melee_skill = 0
    if leader.skills is not None:
        melee_skill = leader.skills.pair_for_ability(Ability.MELEE)[0]

    neutral_bonus = False
    if leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        neutral_bonus = kingdom is not None and kingdom.alignment is Alignment.NEUTRAL

    return Combatant(
        name=leader.name,
        hit_points=CHARACTER_HIT_POINTS,
        melee_skill=melee_skill,
        neutral_duelist_bonus=neutral_bonus,
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
        _spy_skill_of(pursuer),
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
    combat_result = resolve_melee_duel(pursuer_combatant, target_combatant, rng)

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
