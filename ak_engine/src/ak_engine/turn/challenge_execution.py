"""Executing a Challenge (rulebook [3.12] "Encounter Character") order -- Phase 50.

Reuses ``turn/encounter.py``'s Melee combat core (Phase 48), the same
way ``turn/battle_orchestrator.py``'s Duel wiring did (Phase 49) --
built once, reused by whichever consumer is ready for it next.

**[3.12] Encounter Character, quoted in full** (also quoted in
``turn/challenge_pursue_decode.py``'s own docstring):

    The character attempts to Encounter another character in the same
    province, to talk to him, steal from him or engage in personal
    combat. If a character wants to Encounter another character with
    combat in mind, there are some limitations. Heroes who don't lead
    armies can always be Encountered by other Heroes, but evade
    encounters from Kings 50% of the time. Kings only accept a
    non-peaceful encounter if both King and challenger attempt to
    Encounter each other in the same province in the same phase. Heroes
    who lead armies also do not accept encounters. If the encounter
    plan has no combat tactics or personal combat spells (including
    Charm), these restrictions do not apply.

``is_encounter_accepted`` implements that decision tree directly, no
guessing needed -- every branch has a concrete rulebook answer.

**``mutual_encounter`` is caller-supplied, not auto-detected**: knowing
whether the *target* King also ordered a Challenge back at the
challenger this same phase needs visibility into another leader's own
order, which ``turn/plan_dispatch.py``'s single-leader dispatch doesn't
have -- the same structural gap ``turn/turn_processor.py`` (Phase 45)
was built to close for Multiple Contingents and Practice's own
multi-character coordination (Phase 46). Wiring Challenge's mutual-
encounter detection into ``run_turn()`` is a natural follow-up, not
attempted this phase; ``execute_challenge`` defaults ``mutual_encounter``
to ``False`` when driven directly -- a documented, conservative choice
(a King target is never wrongly accepted when the caller can't actually
confirm mutuality).

**Combat-intent detection**: ``ChallengeRequest.tactics`` (already
decoded, ``turn/challenge_pursue_decode.py``) is checked for
``Maneuver.MELEE``/``Maneuver.SHOOT`` -- "If the encounter plan has no
combat tactics or personal combat spells (including Charm), these
restrictions do not apply" -- a peaceful plan (no combat tactics
present) always succeeds, skipping the King/Hero acceptance checks
entirely. Steal and Cast's own personal-combat-spell nuance aren't
checked here (Steal is a separate, unmodeled tactic per ``turn/
encounter.py``'s own docstring; classifying *which* spells count as
"personal combat spells" needs a spell-effect system this project
doesn't have) -- a documented narrowing, not a claim that Steal/Cast
encounters are always peaceful.

**Unlike Duel's own special case ([7.1], Phase 49), a Challenge loser
*is* killed**: personal combat's generic rule ([5.0]: "until one
combatant is killed") applies here in full -- Duel's "only demoralizes
armies, never kills the commander" rule is specific to [7.1] and
doesn't generalize to every Encounter. A decisive loser is removed from
``state`` via ``GameState.remove_leader()``, the same mechanism Cast's
own Kill_Enemy execution already uses (Phase 29).

**Not wired into ``plan_dispatch.py``'s CHALLENGE dispatch**, which
stays decode-only exactly as it was -- the same "built but not
auto-invoked" precedent as ``fight_multi_attacker_battle`` (Phase 28)
and ``execute_practice_group`` (Phase 46), both because
``mutual_encounter`` can't be determined from a single-leader dispatch
and because real combat's variable rng consumption would perturb this
project's existing scripted-``rng`` test sequences if wired in as the
unconditional default (the same reasoning behind Duel's own opt-in
flag, Phase 49).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.encounter import CHARACTER_HIT_POINTS, Combatant, resolve_melee_duel

_COMBAT_MANEUVERS = frozenset({Maneuver.MELEE, Maneuver.SHOOT})


def has_combat_intent(request: ChallengeRequest) -> bool:
    """Rulebook [3.12]: "If the encounter plan has no combat tactics... these restrictions
    do not apply." True if any decoded tactic is Melee or Fire Arrow --
    see module docstring for why Steal/Cast aren't checked here.
    """

    return any(tactic.maneuver in _COMBAT_MANEUVERS for tactic in request.tactics)


def is_encounter_accepted(
    *,
    target_is_king: bool,
    target_leads_army: bool,
    challenger_is_king: bool,
    mutual_encounter: bool,
    rng: random.Random,
) -> bool:
    """Rulebook [3.12]'s King/Hero acceptance decision tree -- see module docstring
    for the full quoted text this implements branch-for-branch.
    """

    if target_is_king:
        return mutual_encounter
    if target_leads_army:
        return False
    if challenger_is_king:
        return rng.random() < 0.5  # "evade encounters from Kings 50% of the time"
    return True  # "Heroes who don't lead armies can always be Encountered by other Heroes"


def _leader_combatant(leader: LeaderState, state: GameState) -> Combatant:
    """Same construction as ``battle_orchestrator.py _commander_combatant`` (Phase 49),
    duplicated rather than shared -- a Duel commander and an Encounter
    participant are different concepts that happen to need the same
    small lookup, not worth a cross-module dependency for.
    """

    melee_skill = effective_skill_level(state, leader, Ability.MELEE)

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
class ChallengeExecutionResult:
    accepted: bool
    reason: str | None = None
    combat_occurred: bool = False
    winner_leader_id: int | None = None
    loser_leader_id: int | None = None
    loser_killed: bool = False


def execute_challenge(
    state: GameState,
    challenger_leader_id: int,
    request: ChallengeRequest,
    rng: random.Random | None = None,
    *,
    mutual_encounter: bool = False,
) -> ChallengeExecutionResult:
    """Resolve a Challenge order end-to-end: co-location, acceptance, and (if accepted
    and combat is intended) a real Melee duel. See module docstring for
    ``mutual_encounter``'s caller-supplied-only status and why a
    decisive loser is removed from ``state`` (unlike Duel's own rule).
    """

    rng = rng if rng is not None else random.Random()

    challenger = state.leaders.get(challenger_leader_id)
    target = state.leaders.get(request.target_character_id)
    if challenger is None or target is None:
        return ChallengeExecutionResult(accepted=False, reason="challenger or target not found")
    if challenger.location != target.location:
        return ChallengeExecutionResult(accepted=False, reason="not co-located")

    if not has_combat_intent(request):
        return ChallengeExecutionResult(accepted=True, combat_occurred=False)

    target_leads_army = bool(state.armies_commanded_by(target.leader_id))
    accepted = is_encounter_accepted(
        target_is_king=target.is_king,
        target_leads_army=target_leads_army,
        challenger_is_king=challenger.is_king,
        mutual_encounter=mutual_encounter,
        rng=rng,
    )
    if not accepted:
        return ChallengeExecutionResult(accepted=False, reason="encounter refused")

    challenger_combatant = _leader_combatant(challenger, state)
    target_combatant = _leader_combatant(target, state)
    combat_result = resolve_melee_duel(challenger_combatant, target_combatant, rng)

    if combat_result.winner is None:
        return ChallengeExecutionResult(accepted=True, combat_occurred=True)

    winner_id, loser_id = (
        (challenger_leader_id, request.target_character_id)
        if combat_result.winner == "a"
        else (request.target_character_id, challenger_leader_id)
    )
    state.remove_leader(loser_id)

    return ChallengeExecutionResult(
        accepted=True, combat_occurred=True, winner_leader_id=winner_id, loser_leader_id=loser_id, loser_killed=True
    )
