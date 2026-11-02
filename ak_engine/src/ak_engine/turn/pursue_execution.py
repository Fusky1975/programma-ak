"""Executing a Pursue (rulebook [3.16]) order -- Phase 51, extended with a
real army-vs-army battle in Phase 53, and a standalone multi-phase
chase-step primitive in Phase 66 (``step_toward_target``/
``advance_pursuit``, auto-wired across phases since Phase 70 -- see
that section below).

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

**``execute_pursue`` itself is single-phase** -- it answers only "does
the pursuer catch up *this* phase, and if so what happens" (a single
Spy Table roll plus, for the armyless case, an immediate encounter
resolution), not a standing order that persists into later phases on
its own. **Phase 650 correction, kept for the record**: an earlier
version of this note framed the *persistent*, multi-phase chase the
rulebook describes ("chase... for the rest of the turn") as "a natural
follow-up, not attempted this phase" -- stale even when written:
``turn/turn_processor.py``'s own "PERSISTENT PURSUE/TRAIL CHASE"
mechanism (Phase 70) already re-invokes ``advance_pursuit`` across
phases via ``active_pursuits``, exactly the cross-phase wiring this
paragraph called unattempted.

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
tactics`` -- see ``turn/challenge_execution.py``'s own Phase 273 note
for the full reasoning (identical here, since Pursue's armyless combat
reuses that same core). ``_leader_combatant`` now also reads
``Ability.ARCHERY``. (Superseded by the Phase 290 addendum below: the
walk now goes through ``resolve_challenge_combat()``, not the old
``turn/encounter.py resolve_encounter_combat()``.)

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

**Phase 290 addendum -- Personal-Combat spells now wired in the armyless
case, via ``turn/challenge_execution.py resolve_challenge_combat()``.**
The armyless case already reused that module's ``has_combat_intent``/
``is_encounter_accepted`` directly (see the "armyless case" note
above); it now reuses its combat walk too, replacing the previous raw
``resolve_encounter_combat([tactic.maneuver for tactic in request.
tactics], ...)`` call the same way ``turn/challenge_execution.py``'s
own Phase 290 addendum describes for Challenge. See that module's own
addendum for the full design (leader-vs-leader spell dispatch, the
still-open Augur-Combat-cast-later gap, and why ``fled`` is a new,
separate outcome from an inconclusive draw).

**Phase 295 addendum -- round-per-round combat engine wiring confirmed.**
Because the armyless case already delegates its whole combat walk to
``turn/challenge_execution.py resolve_challenge_combat()`` (Phase 290,
above), it automatically inherited that function's own Phase 292 round-
based ``CombatRange`` engine (spell-range Cast disruption checks, Bow-
range Fire Arrow, a non-last Melee tactic fighting one round at a time
via ``resolve_one_melee_round()`` instead of an atomic
``resolve_melee_duel()``) and Phase 294's fix (``apply_temper_melee_setup``
now applied exactly once before that round-stepping starts) with zero
further production-code changes here. ``tests/test_pursue_execution.py``
adds direct verification of that inheritance through ``execute_pursue()``'s
own public API, mirroring the equivalent ``test_challenge_execution.py``
tests.

**Phase 743 -- ``Maneuver.FLEE`` inherited for free.** Same reasoning:
``turn/challenge_execution.py``'s own real [5.6] Flee mechanic reaches
the armyless case automatically through the shared ``resolve_challenge_
combat()`` call, no code change needed here.

**Phase 461 -- wires ``turn/experience.py add_experience()`` into
Pursue's own real "informational event" moment.**
``AKGEN_reverse_engineering_report (2).md`` SS3.3's own Spy row (base
10) and SS3.4's own explicit trigger set -- "Spy, Trail, Pursue e
attivita' informative pertinenti" -- name Pursue as one of three real
qualifying-event sources for ``Ability.SPY``; Phase 458 wired ASpy and
this same phase wires Trail (``turn/trail_execution.py``) alongside
Pursue, since both share the identical Spy Table catch-up shape Phase
458's own docstring deferred them for. Pursue's own moment is exactly
the successful catch-up roll immediately above, mirroring Trail's own
``spied_on=True`` gate -- ``add_experience(pursuer, Ability.SPY, 10,
rng)`` now fires there, before branching into an army battle, an
armyless encounter, or a bare "caught up, no combat intent" result --
catching up itself is the informational event this row names, not
whatever combat (if any) follows it, which stays the deliberately
separate Melee/Archery abilities' own still-unwired concern. A failed
catch-up never reaches this call. ``advance_pursuit`` needs no separate
wiring -- it always resolves through this same ``execute_pursue`` call
at its own tail, so every multi-phase chase step gets credit through
the identical single choke point.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.office import Office
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.turn.battle_orchestrator import BattleReport, fight_battle
from ak_engine.turn.sea_transport import apply_battle_carrier_destruction
from ak_engine.turn.challenge_execution import (
    is_encounter_accepted,
    plan_needs_combat_dispatch,
    resolve_challenge_combat,
    target_evades_via_sense_danger,
)
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.discovery_effects import (
    arcane_valor_hit_points_bonus,
    effective_skill_level,
    equipped_combat_weapon,
    holds_bow_of_elven_kings,
)
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    Combatant,
    CombatRange,
    FireArrowShot,
    MeleeSwing,
    archery_free_attack_bonus,
    bow_of_elven_kings_archery_damage_bonus,
    bow_of_elven_kings_archery_hit_multiplier,
    loot_defeated_leader,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    weapon_defensive_hit_multiplier,
    weapon_grants_auto_invisibility,
    weapon_melee_damage_bonus,
    weapon_offensive_hit_multiplier,
)
from ak_engine.turn.experience import add_experience
from ak_engine.turn.movement import MapBounds, hex_distance, neighbors
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.sep_decode import target_uses_special_encounter_plan
from ak_engine.turn.spy_table import pursue_catch_up_chance


def _spy_skill_of(state: GameState, leader: LeaderState) -> int:
    return effective_skill_level(state, leader, Ability.SPY)


def _leader_combatant(leader: LeaderState, state: GameState) -> Combatant:
    """Same construction as ``challenge_execution.py _leader_combatant`` (Phase 50),
    duplicated rather than shared -- established precedent in this project
    (see that function's own docstring) for small per-consumer lookups.

    **Phase 684 -- now wired with the same weapon/bow bonuses its
    ``challenge_execution.py`` counterpart already had** (Phase 535/536/
    682 had never reached Pursue's armyless personal combat, flagged
    during Phase 682's own audit; closed here alongside the identical
    gap in ``cast_execution.py``'s Augur-Combat retaliator and
    ``patrol_execution.py``'s own duplicate).

    **Bug fix**: ``arcane_valor_hit_points_bonus()`` (Phase 538, "Arcane's
    Valor" -- +5 combat hit points for personally holding the Scepter of
    Life, +2 more for the King's own whole Kingdom, active only under
    ``GameType.ARCANES``) was introduced independently of Phase 684's own
    weapon-bonus sweep and never propagated here (nor to ``patrol_
    execution.py``'s/``cast_execution.py``'s own identical duplicate
    builders, fixed alongside this one) even though ``challenge_
    execution.py``/``battle_orchestrator.py``/``search_execution.py``/
    ``turn/random_encounter_execution.py`` all already fold it into
    their own starting ``hit_points`` -- a real, silent inconsistency
    under the ARCANES game type specifically (0 for every other game,
    per that function's own docstring).
    """

    melee_skill = effective_skill_level(state, leader, Ability.MELEE)
    archery_skill = effective_skill_level(state, leader, Ability.ARCHERY)

    neutral_bonus = False
    if leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        neutral_bonus = kingdom is not None and kingdom.alignment is Alignment.NEUTRAL

    defender_office = resolve_office_holder(state, Office.DEFENDER)
    damage_reduction = 1 if defender_office is not None and defender_office.leader_id == leader.leader_id else 0
    illus_mage_office = resolve_office_holder(state, Office.ILLUS_MAGE)
    always_acts_first = illus_mage_office is not None and illus_mage_office.leader_id == leader.leader_id
    necro_mage_office = resolve_office_holder(state, Office.NECRO_MAGE)
    is_necro_mage = necro_mage_office is not None and necro_mage_office.leader_id == leader.leader_id
    has_melee_hit_points_ability = AdvancedAbility.MELEE_HIT_POINTS in leader.advanced_abilities
    effective_race = leader.race
    if effective_race is None and leader.kingdom_id is not None:
        leader_kingdom = state.kingdoms.get(leader.kingdom_id)
        effective_race = leader_kingdom.race if leader_kingdom is not None else None
    is_humanoid = effective_race in HUMANOID_RACES
    weapon = equipped_combat_weapon(state, leader.leader_id)
    holds_bow = holds_bow_of_elven_kings(state, leader.leader_id)

    return Combatant(
        name=leader.name,
        hit_points=CHARACTER_HIT_POINTS + arcane_valor_hit_points_bonus(state, leader),
        melee_skill=melee_skill,
        archery_skill=archery_skill,
        neutral_duelist_bonus=neutral_bonus,
        temper=leader.temper,
        damage_reduction=damage_reduction,
        has_melee_hit_points_ability=has_melee_hit_points_ability,
        offensive_hit_multiplier=(
            melee_mastery_offensive_hit_multiplier(leader.advanced_abilities) * weapon_offensive_hit_multiplier(weapon)
        ),
        melee_damage_dealt_bonus=(
            melee_mastery_damage_bonus(leader.advanced_abilities) + weapon_melee_damage_bonus(weapon)
        ),
        archery_hit_multiplier=bow_of_elven_kings_archery_hit_multiplier(holds_bow),
        missile_damage_dealt_bonus=bow_of_elven_kings_archery_damage_bonus(holds_bow),
        defensive_hit_multiplier=weapon_defensive_hit_multiplier(weapon),
        is_invisible=weapon_grants_auto_invisibility(weapon),
        equipped_weapon=weapon,
        is_undead_or_anti_holy=leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY),
        is_humanoid=is_humanoid,
        has_duellists_medal_ability=AdvancedAbility.MELEE_DUELLISTS_MEDAL in leader.advanced_abilities,
        has_control_temper_ability=AdvancedAbility.MELEE_CONTROL_TEMPER in leader.advanced_abilities,
        archery_free_attack_bonus=archery_free_attack_bonus(leader.advanced_abilities),
        always_acts_first=always_acts_first,
        regenerates_hp=(1 if is_necro_mage else 0),
        regenerates_hp_interval=(2 if is_necro_mage else 1),
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
    # Phase 290: a successful Charm, or Augur Combat cast first and
    # shirking -- see `turn/challenge_execution.py`'s own Phase 290
    # addendum, reused here since the armyless case shares that module's
    # combat core directly.
    fled: bool = False
    # Phase 213: the originating request, for a caller (report/turn_report.py
    # describe_turn_results()) that needs the target's own id to resolve a
    # display name -- set by plan_dispatch.py's own dispatcher, not by this
    # function itself (see that module's own Phase 213 note for why:
    # avoids touching every one of this function's own early-return sites).
    # None for any caller that invokes execute_pursue()/advance_pursuit()
    # directly, bypassing dispatch -- the same "not populated outside its
    # real consumer" convention already used elsewhere in this project.
    request: PursueRequest | None = None
    # Phase 306: same field, same reason as `turn/challenge_execution.py
    # ChallengeExecutionResult`'s own Phase 306 addendum -- copied
    # straight from `ChallengeCombatOutcome` for the armyless case, which
    # shares that module's combat core directly.
    steal_outcome: str | None = None
    steal_capture_range: CombatRange | None = None
    # Phase 702: same field/reason as `turn/challenge_execution.py
    # ChallengeExecutionResult`'s own Phase 702 addendum -- non-zero
    # only for a successful `AdvancedAbility.THIEF_TREASURY_RAIDS` raid
    # against a foreign King, set for the armyless-combat branch only,
    # which shares that module's combat core directly.
    gold_raided: int = 0
    # Phase 777: same field/reason as `turn/challenge_execution.py
    # ChallengeExecutionResult`'s own Phase 777 addendum -- the real item
    # ids an ordinary (non-Treasury-Raid) successful Steal actually
    # transferred, set for the armyless-combat branch only.
    stolen_item_ids: list[int] = field(default_factory=list)
    # Phase 313: same field/reason as `turn/challenge_execution.py
    # ChallengeExecutionResult`'s own Phase 313 addendum -- set for the
    # armyless-combat branch only, which shares that module's combat core
    # directly; the army-vs-army battle branch (`_fight_army_pursuit_battle`)
    # goes through `fight_battle()` instead, out of [5.9]'s own personal-
    # combat scope.
    looted_item_ids: list[int] = field(default_factory=list)
    # Phase 417: same field, same reason as `turn/challenge_execution.py
    # ChallengeExecutionResult`'s own Phase 417 addendum -- set for the
    # armyless-combat branch only, copied straight from `ChallengeCombat
    # Outcome`.
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    melee_swings: tuple[MeleeSwing, ...] = ()
    # Phase 858: same field, same reason as `turn/challenge_execution.py
    # ChallengeCombatOutcome.fizzled_spells`'s own docstring -- copied
    # straight through, set for the armyless-combat branch only, which
    # shares that module's combat core directly.
    fizzled_spells: tuple[tuple[str, Spell], ...] = ()
    # Phase 695: `AdvancedAbility.SPY_SUPER_SLEUTH`'s own real text --
    # "the Spy can also guess how far away the target is (the guess may
    # be off by one province)." Set only when the pursuer holds the
    # Advanced Ability and the catch-up (automatic, per that same text)
    # succeeds -- see `execute_pursue()`'s own Phase 695 addendum.
    guessed_distance: int | None = None


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

    # Phase 736: snapshot army types before fight_battle() removes any
    # of them -- see move_execution.py's own identical Phase 736 note.
    army_types_before_battle = {army.army_id: army.army_type for army in state.armies.values()}
    battle_report = fight_battle(
        state,
        pursuer.kingdom_id,
        target.location,
        pursuer_army_ids,
        attacker_origin=origin,
        apply_fanaticism=True,
        use_real_duel_combat=True,
        rng=rng,
    )
    # Phase 716: the cargo sinks with the carrier. `battle_report` is
    # never really None in production (fight_battle()'s own real return
    # type) -- the guard exists only because some existing tests mock
    # fight_battle() to return None as a test double for unrelated
    # branches.
    if battle_report is not None:
        apply_battle_carrier_destruction(
            state,
            battle_report.destroyed_army_ids,
            battle_report.disbanded_army_ids,
            battle_report.pursuit_destroyed_army_ids,
            coord=target.location,
            army_types_before_battle=army_types_before_battle,
        )
    return PursueExecutionResult(caught_up=True, combat_occurred=True, battle_report=battle_report)


def execute_pursue(
    state: GameState,
    pursuer_leader_id: int,
    request: PursueRequest,
    rng: random.Random | None = None,
    *,
    mutual_encounter: bool = False,
    has_spy_super_sleuth: bool = False,
) -> PursueExecutionResult:
    """Resolve one phase of a Pursue order: [3.16]'s army-leading-match check, a Spy
    Table catch-up roll, and either a real army battle or (armyless case
    only) an immediate Encounter resolution. See module docstring for the
    remaining multi-phase-chase gap and ``mutual_encounter``'s
    caller-supplied-only status.

    **Phase 695 -- `AdvancedAbility.SPY_SUPER_SLEUTH`**: "When the Spy
    uses the Trail or Pursue actions, success is automatic, and the Spy
    can also guess how far away the target is (the guess may be off by
    one province)." ``has_spy_super_sleuth`` bypasses the catch-up roll
    entirely (the Spy Table's own chance is never even consulted, let
    alone rolled against) and sets ``PursueExecutionResult.guessed_
    distance`` to the real distance perturbed by a documented, literal
    reading of "off by one" -- a uniformly random ``-1``/``0``/``+1``
    offset (mirrors ``turn/spy_table.py estimate_reported_value()``'s
    own "uniform, symmetric" documented-choice convention for an
    analogous unsourced-but-bounded margin of error), floored at 0
    (a negative distance has no meaning). **Phase 832**: `guessed_
    distance` is finally rendered into report text, via `report/
    turn_report.py describe_pursue_guessed_distance()`'s own project-
    original `render_guessed_distance()` (shared with Trail's own
    identical fact) -- computed here since this same phase, but never
    reaching the player before Phase 832.
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
    if not has_spy_super_sleuth and rng.random() >= chance:
        return PursueExecutionResult(caught_up=False, reason="did not catch up this phase")

    guessed_distance = max(0, distance + rng.choice((-1, 0, 1))) if has_spy_super_sleuth else None

    add_experience(pursuer, Ability.SPY, 10, rng)

    if target_leads_army:  # pursuer_leads_army matches, per the check above
        result = _fight_army_pursuit_battle(state, pursuer, target, rng)
        result.guessed_distance = guessed_distance
        return result

    # Phase 856 bug fix: the armyless case never actually relocated the
    # pursuer, contradicting this module's own docstring ("the same
    # abstraction level already used for the armyless case's encounter"
    # -- see the "Army-vs-army pursuit" section above). A real,
    # confirmed consequence: report/turn_report.py describe_pursue()
    # resolves the caught-up sentence's own province from the pursuer's
    # *current* location, which -- without this line -- still showed
    # wherever the pursuer started, not the province they supposedly
    # caught up with the target in. Mirrors _fight_army_pursuit_
    # battle()'s own relocation exactly, just without any armies to
    # bring along.
    pursuer.location = target.location

    if not plan_needs_combat_dispatch(request):
        return PursueExecutionResult(caught_up=True, combat_occurred=False, guessed_distance=guessed_distance)

    accepted = is_encounter_accepted(
        target_is_king=target.is_king,
        target_leads_army=False,
        challenger_is_king=pursuer.is_king,
        mutual_encounter=mutual_encounter,
        rng=rng,
        has_spy_assassinate=AdvancedAbility.SPY_ASSASSINATE in pursuer.advanced_abilities,
        has_sense_danger_evasion=target_evades_via_sense_danger(state, target, pursuer),
    )
    if not accepted:
        return PursueExecutionResult(caught_up=True, reason="encounter refused", guessed_distance=guessed_distance)

    pursuer_combatant = _leader_combatant(pursuer, state)
    target_combatant = _leader_combatant(target, state)
    # Phase 674: this branch is only ever reached after the `if target_
    # leads_army: return ...` early return above, so the target is
    # already structurally guaranteed armyless -- `target_uses_special_
    # encounter_plan()` still used here (rather than assuming it) for
    # the same real, testable eligibility check `execute_challenge()`
    # uses, matching rulebook [5.10]'s own literal condition.
    target_tactics = list(target.special_encounter_plan) if target_uses_special_encounter_plan(state, target) else None
    combat_result = resolve_challenge_combat(
        request.tactics,
        pursuer,
        pursuer_combatant,
        target,
        target_combatant,
        state,
        rng,
        target_tactics=target_tactics,
    )

    # Phase 686: AKGEN_reverse_engineering_report (2).md SS3.3's own
    # Melee/Archery rows -- "evento di mischia/duello qualificante"/
    # "evento di tiro riuscito" -- a landed hit, credited once per
    # encounter per side, independent of who ultimately wins.
    if any(s.hit for s in combat_result.melee_swings if s.attacker == "a"):
        add_experience(pursuer, Ability.MELEE, 10, rng)
    if any(s.hit for s in combat_result.melee_swings if s.attacker == "b"):
        add_experience(target, Ability.MELEE, 10, rng)
    if any(s.hit for s in combat_result.fire_arrow_shots if s.shooter == "a"):
        add_experience(pursuer, Ability.ARCHERY, 10, rng)
    if any(s.hit for s in combat_result.fire_arrow_shots if s.shooter == "b"):
        add_experience(target, Ability.ARCHERY, 10, rng)

    if combat_result.fled:
        return PursueExecutionResult(
            caught_up=True,
            combat_occurred=True,
            fled=True,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
            gold_raided=combat_result.gold_raided,
            stolen_item_ids=combat_result.stolen_item_ids,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            melee_swings=combat_result.melee_swings,
            fizzled_spells=combat_result.fizzled_spells,
            guessed_distance=guessed_distance,
        )
    if combat_result.winner is None:
        return PursueExecutionResult(
            caught_up=True,
            combat_occurred=True,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
            gold_raided=combat_result.gold_raided,
            stolen_item_ids=combat_result.stolen_item_ids,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            melee_swings=combat_result.melee_swings,
            fizzled_spells=combat_result.fizzled_spells,
            guessed_distance=guessed_distance,
        )

    winner_id, loser_id = (
        (pursuer_leader_id, request.target_character_id)
        if combat_result.winner == "a"
        else (request.target_character_id, pursuer_leader_id)
    )
    state.remove_leader(loser_id)
    looted_items = loot_defeated_leader(state, winner_id=winner_id, loser_id=loser_id)

    return PursueExecutionResult(
        caught_up=True,
        combat_occurred=True,
        winner_leader_id=winner_id,
        loser_leader_id=loser_id,
        loser_killed=True,
        looted_item_ids=[item.item_id for item in looted_items],
        steal_outcome=combat_result.steal_outcome,
        steal_capture_range=combat_result.steal_capture_range,
        gold_raided=combat_result.gold_raided,
        stolen_item_ids=combat_result.stolen_item_ids,
        fire_arrow_shots=combat_result.fire_arrow_shots,
        melee_swings=combat_result.melee_swings,
        fizzled_spells=combat_result.fizzled_spells,
        guessed_distance=guessed_distance,
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
    has_spy_super_sleuth: bool = False,
    board_width: int | None = None,
    board_height: int | None = None,
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

    ``board_width``/``board_height`` (Phase 780, default ``None``) fall
    back to ``state.board_width``/``.board_height``.
    """

    rng = rng if rng is not None else random.Random()
    board_width = board_width if board_width is not None else state.board_width
    board_height = board_height if board_height is not None else state.board_height

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

    return execute_pursue(
        state, pursuer_leader_id, request, rng, mutual_encounter=mutual_encounter, has_spy_super_sleuth=has_spy_super_sleuth
    )
