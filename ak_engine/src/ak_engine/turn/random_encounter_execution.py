"""Phase 708 -- random-encounter dispatch wiring, synthetic monster,
combat integration, and ``AdvancedAbility.SENSE_DANGER_TALENT``'s own
"random encounters" closure.

Sourced from ``Desktop\\CASUALENCOUNTER.md`` (see ``turn/random_
encounter.py``'s own module docstring for the full citation and the
generator primitives this module wires up). This module is the
"execution" half of that decode/primitive split -- mirrors this
project's own established ``*_decode.py``/``*_execution.py`` pairing
(e.g. ``search_decode.py``/``search_execution.py``).

**Combat-engine integration, resolved by direct investigation (not
guessed)**: no monster-side plan generator is needed for this
mechanic. `turn/challenge_execution.py resolve_challenge_combat()`
already fully supports a synthetic, no-real-``LeaderState`` opponent
-- `target_leader: LeaderState | None` and a bare `target: Combatant`
are already a real, exercised production path (`turn/battle_
orchestrator.py`'s own Duel/garrison-commander reuse). With
``target_tactics`` omitted, the target never independently initiates
CAST/SHOOT -- it only ever reacts via forced Melee rounds and the
already-mutual `resolve_fire_arrow_duel()` for SHOOT, exactly a
"passive opponent" framing. This matches the document's own text
directly: "Il combattimento stesso è il motore comune... sono incluse
invece tutte le diramazioni che esistono soltanto perché l'avversario
è sintetico" -- the base engine is the ordinary shared one; nothing in
the document gives the monster its own independent combat initiative
for *this* mechanic (unlike `search_execution.py`'s own, separate,
richer guardian-monster system with its own sourced `monster_plan`
generator -- not reused here). The **human** side is driven by the
leader's own real `LeaderState.special_encounter_plan` (already a
decoded `tuple[SearchTactic, ...]`, Phase 669 -- no re-decoding needed).

**The synthetic monster needs no ``Feature`` at all.** `monster_
combatant()` below is a standalone port of `search_execution.py`'s own
guardian-`Combatant` construction, reading only `MONSTER_COMBAT_STATS`
(confirmed to cover all 60 real species, zero gaps) plus `rng` and
static tables -- no `Feature` parameter.

**Sense Danger Talent's own random-encounter clause** (document SS11):
the same "is Flee the first tactic of the SEP" check `turn/sep_
decode.py sep_accepts_challenge()` (Phase 669) already computes, at a
fixed 100% (not the ordinary 50%) because the opponent is synthetic --
the document's own text: "Per un incontro casuale l'ultima condizione
è sempre vera... Sense Danger evita il combattimento al 100%."

**Permanently deferred, not silently skipped**: the document's own
SS12 pre-combat social-outcome decision tree (`approach_score` and the
8 named branches -- pass-by/befriend/teach-a-skill/donate-gold/reveal-
a-feature/nice-chat/friendly-greeting) is not modeled here. Phase 709
investigated inserting the real `approach_score` gate between the
Sense-Danger check and the combat call and found no recoverable
selection formula survives for it anywhere in the source -- a
permanently genuinely-blocked gap, not a deferred one. **This means
every encounter that isn't safely resolved via patrol diplomacy or
Sense Danger goes straight to combat** -- more often than the real
game would, a real, permanent, documented simplification. Report-layer
narration (`report/turn_report.py describe_random_encounter()`,
calling `render_wandering_encounter()`/`render_patrol_release()`/
`render_patrol_encounter()`, Phase 106/107) was wired in full by Phase
709.

**Death handling** mirrors `challenge_execution.py execute_challenge()`'s
own established pattern: `resolve_challenge_combat()` itself never
touches `state.leaders` -- this module checks the outcome's `winner`
and calls `state.remove_leader(...)` itself when the real leader loses.
A leader win grants no loot -- the synthetic opponent's own real data
(the document's own `treaslist[maxfeatures]:=notreasure`) confirms it
carries no treasure, so there is nothing to loot either way.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.monster import (
    HAND_OF_DEATH_ANTI_HOLY_MONSTERS,
    HUMANOID_MONSTERS,
    MONSTER_ALIGNMENT_DISTRIBUTION,
    MONSTER_COMBAT_STATS,
    MONSTER_MAGIC_ABILITIES,
    MONSTER_NAMES,
    MONSTER_RUNTIME_PROFILE,
    SPIRITWRACK_UNDEAD_MONSTERS,
    Monster,
    roll_monster_alignment,
)
from ak_engine.models.monster_encounter_plan import roll_monster_encounter_plan
from ak_engine.models.enums import Maneuver
from ak_engine.turn.legendary_item_rescue import RescuedItem, rescue_legendary_items
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.models.office import Office
from ak_engine.models.plan import ActionPlan, PlanPhase
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.turn.challenge_execution import resolve_challenge_combat
from ak_engine.turn.discovery_effects import (
    arcane_valor_hit_points_bonus,
    effective_skill_level,
    equipped_combat_weapon,
    holds_bow_of_elven_kings,
)
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_DAMAGE_RANGE,
    Combatant,
    FireArrowShot,
    MeleeSwing,
    archery_free_attack_bonus,
    bow_of_elven_kings_archery_damage_bonus,
    bow_of_elven_kings_archery_hit_multiplier,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    weapon_defensive_hit_multiplier,
    weapon_grants_auto_invisibility,
    weapon_melee_damage_bonus,
    weapon_offensive_hit_multiplier,
)
from ak_engine.turn.experience import add_experience
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.random_encounter import (
    is_leader_eligible_for_random_encounter,
    is_patrol_framing,
    patrol_evades_via_diplomacy,
    random_encounter_gate_open,
    select_random_monster,
    terrain_roll,
)
from ak_engine.turn.sep_decode import sep_accepts_challenge

# Phase 685 (search_execution.py)'s own sourced value, cited directly
# rather than imported -- a small, deliberate duplication matching this
# project's own established "small, duplicated per-consumer" precedent
# for `_leader_combatant()`-style lookups (see that function's own
# docstring below).
_TROLL_REGENERATION_PER_COMBAT_ROUND = 1

# CASUALENCOUNTER.md SS3: Move/Pursue/Trail = random_mode 1 (escort-
# travel checked); Explore/Search = random_mode 2 (not checked).
_TRIGGERING_ACTIONS = frozenset(
    {ActionCode.LMOVE, ActionCode.EXPLORE, ActionCode.SEARCH, ActionCode.PURSUE, ActionCode.TRAIL}
)
_ESCORT_CHECKED_ACTIONS = frozenset({ActionCode.LMOVE, ActionCode.PURSUE, ActionCode.TRAIL})


def monster_combatant(monster: Monster, rng: random.Random) -> Combatant:
    """Standalone port of ``search_execution.py``'s own guardian-`Combatant`
    construction -- reads only ``MONSTER_COMBAT_STATS`` (confirmed to cover
    all 60 real species) plus ``rng``, no ``Feature`` needed.
    """

    stats = MONSTER_COMBAT_STATS[monster]
    return Combatant(
        name=MONSTER_NAMES.get(monster, "wandering monster"),
        hit_points=rng.randint(*stats.hit_points_range),
        melee_skill=stats.melee_skill,
        melee_damage_range=stats.melee_damage,
        archery_skill=stats.missile_skill,
        missile_damage_range=stats.missile_damage if stats.missile_damage is not None else FIRE_ARROW_DAMAGE_RANGE,
        regenerates_hp=_TROLL_REGENERATION_PER_COMBAT_ROUND if monster is Monster.TROLL else 0,
        is_undead_or_anti_holy=monster in (HAND_OF_DEATH_ANTI_HOLY_MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS),
        is_humanoid=monster in HUMANOID_MONSTERS,
        temper=MONSTER_RUNTIME_PROFILE[monster].temper,  # Furia/Intimidazione, Slancio, Schivare
    )


# A negative id can never clash with a real leader.
WANDERING_MONSTER_LEADER_ID = -1000

# A monster met on the road is caught away from its lair and its preparations: only this share of the
# plans that contain spells is played with its magic, the others are fought with the plan's melee,
# missiles and retreat alone.
WANDERING_MAGIC_PLAN_CHANCE = 0.3

# The purse a defeated (or routed) wandering monster leaves behind: 2 to 10 gold, 10 very rare.
WANDERING_TREASURE_RANGE = (2, 9)
WANDERING_TREASURE_JACKPOT = 10
WANDERING_TREASURE_JACKPOT_CHANCE = 0.02


def wandering_monster_treasure(rng: random.Random) -> int:
    if rng.random() < WANDERING_TREASURE_JACKPOT_CHANCE:
        return WANDERING_TREASURE_JACKPOT
    return rng.randint(*WANDERING_TREASURE_RANGE)


def _without_magic_most_of_the_time(plan: tuple[SearchTactic, ...] | None, rng: random.Random) -> tuple[SearchTactic, ...] | None:
    if plan is None or not any(t.maneuver is Maneuver.CAST for t in plan):
        return plan
    if rng.random() < WANDERING_MAGIC_PLAN_CHANCE:
        return plan
    return tuple(t for t in plan if t.maneuver is not Maneuver.CAST) or None


def wandering_monster_leader(monster: Monster, coord: HexCoord, alignment_rng: random.Random | None = None) -> LeaderState:
    """A stand-in "character" for a wandering monster -- never registered in ``GameState`` -- carrying the
    monster's own magic talents, temper and alignment, so that it can cast the spells of its plan and so
    that the spells the hero casts at it see what it is (undead, anti-holy...). A species with several
    alignments ("Neutral 50% / Pagan 50%") gets one rolled from ``alignment_rng`` (the first one without)."""

    raw_values = [0] * 31
    for ability, level in MONSTER_MAGIC_ABILITIES.get(monster, {}).items():
        raw_values[ability.value * 2] = level
    options = MONSTER_ALIGNMENT_DISTRIBUTION.get(monster)
    if alignment_rng is not None:
        alignment = roll_monster_alignment(monster, alignment_rng)
    else:
        alignment = options[0].alignment if options else None
    if monster in SPIRITWRACK_UNDEAD_MONSTERS:
        alignment = Alignment.UNDEAD
    profile = MONSTER_RUNTIME_PROFILE.get(monster)
    return LeaderState(
        WANDERING_MONSTER_LEADER_ID,
        None,
        MONSTER_NAMES.get(monster, "wandering monster"),
        coord,
        skills=SkillTable(raw_values=raw_values),
        temper=profile.temper if profile is not None else None,
        alignment=alignment,
    )


def _leader_combatant(leader: LeaderState, state: GameState) -> Combatant:
    """Same construction as ``challenge_execution.py``'s own function of the
    same name -- duplicated deliberately, matching this project's own
    established "small, duplicated per-consumer" precedent (that
    function's own docstring cites ``battle_orchestrator.py _commander_
    combatant`` for the identical reasoning). **Drift risk, documented
    directly**: this exact builder has drifted out of sync across its
    other 5-6 copies before (Phase 535/682/684 all found and fixed real
    gaps where one copy gained a bonus the others didn't) -- if a future
    phase adds a new weapon/office/ability bonus to ``challenge_
    execution.py``'s own copy, check this one too.
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
        is_humanoid=is_humanoid,
        has_duellists_medal_ability=AdvancedAbility.MELEE_DUELLISTS_MEDAL in leader.advanced_abilities,
        has_control_temper_ability=AdvancedAbility.MELEE_CONTROL_TEMPER in leader.advanced_abilities,
        archery_free_attack_bonus=archery_free_attack_bonus(leader.advanced_abilities),
        defensive_hit_multiplier=weapon_defensive_hit_multiplier(weapon),
        is_invisible=weapon_grants_auto_invisibility(weapon),
        equipped_weapon=weapon,
        always_acts_first=always_acts_first,
        regenerates_hp=(1 if is_necro_mage else 0),
        regenerates_hp_interval=(2 if is_necro_mage else 1),
        is_undead_or_anti_holy=leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY),
    )


@dataclass(slots=True)
class RandomEncounterResult:
    """Every fact Phase 709's own report layer will need -- gathered here,
    not rendered here (this module does not touch ``report/``).
    """

    leader_id: int
    coord: HexCoord
    terrain_roll_succeeded: bool
    monster: Monster | None = None
    is_patrol: bool = False
    evaded_via_diplomacy: bool = False
    evaded_via_sense_danger: bool = False
    combat_occurred: bool = False
    winner: str | None = None  # "a" = leader, "b" = monster, None = inconclusive
    leader_died: bool = False
    monster_fled: bool = False  # the wandering monster ran away wounded (its plan's FLEE)
    gold_found: int = 0  # the monster's purse, paid into the hero's Kingdom treasury
    rescued_items: tuple[RescuedItem, ...] = ()  # legendary items of a fallen hero (turn/legendary_item_rescue.py)
    melee_swings: tuple[MeleeSwing, ...] = ()
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()


def resolve_random_encounter(
    state: GameState,
    leader_id: int,
    coord: HexCoord,
    plan: ActionPlan,
    *,
    check_escort: bool,
    rng: random.Random,
) -> RandomEncounterResult | None:
    """The real per-attempt entry point. Returns ``None`` for the turn-
    number gate, a missing leader, or any of Phase 707's own silent
    eligibility exclusions -- matching the document's own "these
    exclusions exit in silence" framing (no result, nothing for Phase
    709 to narrate). A failed terrain roll still returns a real result
    (``terrain_roll_succeeded=False``) -- that *is* narrated (``_
    LNoRand``) in the real game.
    """

    if not random_encounter_gate_open(state):
        return None
    leader = state.leaders.get(leader_id)
    if leader is None:
        return None
    if not is_leader_eligible_for_random_encounter(state, leader, plan, coord, check_escort=check_escort):
        return None

    province = state.provinces.get(coord)
    terrain = province.effective_terrain() if province is not None else Terrain.NO_TERRAIN
    if not terrain_roll(terrain, rng):
        return RandomEncounterResult(leader_id, coord, terrain_roll_succeeded=False)

    monster = select_random_monster(terrain, rng)
    is_patrol = is_patrol_framing(leader_id, state.turn_number, monster)

    if is_patrol:
        owner_kingdom_id = province.owner_kingdom_id if province is not None else None
        if owner_kingdom_id is not None and patrol_evades_via_diplomacy(state, leader.kingdom_id, owner_kingdom_id, rng):
            return RandomEncounterResult(
                leader_id, coord, terrain_roll_succeeded=True, monster=monster, is_patrol=True, evaded_via_diplomacy=True
            )

    decoded_sep = list(leader.special_encounter_plan)
    if AdvancedAbility.SENSE_DANGER_TALENT in leader.advanced_abilities and not sep_accepts_challenge(decoded_sep):
        return RandomEncounterResult(
            leader_id,
            coord,
            terrain_roll_succeeded=True,
            monster=monster,
            is_patrol=is_patrol,
            evaded_via_sense_danger=True,
        )

    leader_combatant = _leader_combatant(leader, state)
    opponent = monster_combatant(monster, rng)
    # [5.0]: the Order of Duelists' +1 only counts "negli scontri con Eroi o mostri umanoidi".
    leader_combatant.neutral_duelist_bonus = leader_combatant.neutral_duelist_bonus and opponent.is_humanoid
    # The monster's own plan (the tables, or a varied plan for an intelligent one -- see models/monster_
    # encounter_plan.py) comes from its own stream, so the encounter's dice keep their sequence.
    variety_rng = random.Random(
        f"wandering-plan:{state.game_number}:{state.turn_number}:{leader_id}:{coord.x},{coord.y}:"
        f"{leader.experience_credit}:{monster.name}"
    )
    # A patrol is the King's own men, not a monster: no talents, no plan, no purse, no Defender points.
    monster_plan = None
    if not is_patrol:
        monster_plan = _without_magic_most_of_the_time(
            roll_monster_encounter_plan(
                monster, variety_rng, attacker_is_undead=leader.alignment is Alignment.UNDEAD, variety_rng=variety_rng
            ),
            variety_rng,
        )
    monster_starting_hit_points = opponent.hit_points
    outcome = resolve_challenge_combat(
        decoded_sep,
        leader,
        leader_combatant,
        None if is_patrol else wandering_monster_leader(monster, coord, variety_rng),
        opponent,
        state,
        rng,
        target_tactics=list(monster_plan) if monster_plan else None,
        target_retreats_when_wounded=not is_patrol,
        target_opens_with_missiles=monster_plan is not None and any(t.maneuver is Maneuver.SHOOT for t in monster_plan),
        target_monster=None if is_patrol else monster,
    )

    if any(swing.hit for swing in outcome.melee_swings if swing.attacker == "a"):
        add_experience(leader, Ability.MELEE, 10, rng)
    if any(shot.shooter == "a" for shot in outcome.fire_arrow_shots):
        add_experience(leader, Ability.ARCHERY, 10, rng)

    leader_died = False
    gold_found = 0
    rescued: list[RescuedItem] = []
    if outcome.winner == "b":
        state.remove_leader(leader_id)
        leader_died = True
        rescued = rescue_legendary_items(state, leader_id, leader.kingdom_id, coord)
    elif outcome.winner == "a" and not is_patrol:
        if not outcome.target_fled:
            # The Lord High Defender's merit: the monster's own starting hit points (see
            # `turn/merit_points.py defender_merit_points()`); a monster that merely ran away was not defeated.
            leader.merit_tally.monster_hp_defeated += monster_starting_hit_points
        if leader.kingdom_id is not None:
            gold_found = wandering_monster_treasure(variety_rng)
            state.kingdoms[leader.kingdom_id].treasury += gold_found

    return RandomEncounterResult(
        leader_id,
        coord,
        terrain_roll_succeeded=True,
        monster=monster,
        is_patrol=is_patrol,
        combat_occurred=True,
        winner=outcome.winner,
        leader_died=leader_died,
        monster_fled=outcome.target_fled,
        gold_found=gold_found,
        rescued_items=tuple(rescued),
        melee_swings=outcome.melee_swings,
        fire_arrow_shots=outcome.fire_arrow_shots,
    )


def dispatch_random_encounter_after_phase(
    state: GameState, leader: Leader, phase: PlanPhase, rng: random.Random
) -> RandomEncounterResult | None:
    """The real dispatch-loop entry point -- called once, right after a
    phase's own ordinary dispatch resolves, for exactly the 5 real
    triggering action types (CASUALENCOUNTER.md SS3). ``leader.plan`` is
    the leader's own full annual plan (every segment/phase), needed for
    the forbidden-plan-action exclusion; ``state.leaders[leader.leader_
    id].location`` is read fresh here (after the phase's own dispatch
    already ran), matching the document's own "at the end of the
    action" framing.
    """

    if phase.action not in _TRIGGERING_ACTIONS:
        return None
    leader_state = state.leaders.get(leader.leader_id)
    if leader_state is None:
        return None
    return resolve_random_encounter(
        state,
        leader.leader_id,
        leader_state.location,
        leader.plan,
        check_escort=phase.action in _ESCORT_CHECKED_ACTIONS,
        rng=rng,
    )
