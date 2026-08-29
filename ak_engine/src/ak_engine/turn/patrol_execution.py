"""Executing "Characters On Patrol" (rulebook [3.16], self-targeting Pursue) -- Phase 71.

Patrol is written as a Pursue order whose target character id is the
character's own id -- ``turn/challenge_pursue_decode.py``'s own
docstring already flags this ("targeting one's own character id turns
a Pursue order into a standing 'Patrol'"), left unmodeled until now.
Unlike directed Pursue (``turn/pursue_execution.py``), which chases one
specific character until a Spy Table catch-up roll resolves it and then
stops, Patrol is a **standing order** -- like Defend ([3.15]), it stays
active indefinitely until cancelled by a later Move/Pursue/Trail order,
re-checking for a qualifying intruder every phase rather than resolving
once. ``turn/turn_processor.py`` owns that standing-order persistence
(mirroring ``active_defends``, reusing ``_apply_defend_cancellations``'s
identical LMOVE/PURSUE/TRAIL trigger set for cancellation, since the
rulebook uses the same wording for both) -- this module only answers
"is there a qualifying intruder to intercept this phase, and if so what
happens."

[3.16] "Characters On Patrol", quoted in full (``RULES.AK`` ~line
599-625): "This is like the Defend order, except whenever the character
hears of an intruding character, he chases him down. Write this order
by having the character 'Pursue' his own character number. This means
the character will track down any detected Enemy character who enters
a hex next to the character. The evasive skills of Thieves and Spies
still operate normally. The 'Patrol' order works differently in some
important respects from the Defend order, while in other respects they
are quite similar":

  a) "Only leaders not leading armies may Patrol, and they chase only
     characters not leading armies." -- an armied patroller's order is
     ignored entirely (same ignored-not-raised convention directed
     Pursue's own army-leading-mismatch check already uses); an armied
     candidate is never a valid intercept target.
  b) "They patrol the current hex they are in and all adjacent hexes."
  c) "They only intercept enemy characters." -- read the same way
     ``turn/turn_processor.py _sees_nonallied_defender`` already reads
     "attacking": a kingdomless character (independent Hero, or the
     patroller themself if independent) is never automatically hostile
     -- only a candidate who belongs to some Kingdom that isn't allied
     with the patroller's own counts as an enemy here.
  d) "The Patrol stays active until the next Move, Trail or Pursue
     order; other orders after the Patrol order are used if there is
     no current threat to be intercepted by the Patrol." -- persistence
     and cancellation live in ``turn/turn_processor.py``, not here.
  e) "A Patrol may be unable to detect an enemy character if he is
     using his Spy or Thief ability that gameturn." **Not modeled --
     a genuine data-model gap, not a choice.** This project's
     ``GameState`` has no field anywhere for per-turn ability-usage
     tracking (the same category of gap already declared for ASpy's
     own "Chance of Escaping Notice" column, ``turn/spy_table.py``'s
     own docstring).
  f) "A Patrol will only intercept in owned or Allied territory." --
     read here as the patroller's own current province (their "beat")
     needing to be owned by their own Kingdom or an ally, not the
     intruder's -- an unsourced but natural reading given (b)'s own
     province-plus-neighbors coverage mirrors Defend's home-centered
     coverage area, not the intruder's location.
  g) "A Patrol will only attempt to pursue intruders whose best skill
     in Archery, Melee or Magic is equal to or less than the Patrol's
     best such skill." -- this project's ``Ability`` enum has no single
     "Magic" entry (five separate schools: White, Necromancy,
     Elemental, Psychic, Illusion); "best skill in ... Magic" is read
     here as the highest of all five -- an unsourced but literal
     reading of "Magic" as the general category those five schools
     already form elsewhere in this project.
  h) "If there are more than one such intruders, the most threatening
     one is intercepted, by 'highest skill' as defined in point (7)."
     **Point (7) does not exist anywhere in the available ``RULES.AK``
     text** (confirmed: no numbered list item anywhere in the file is
     labelled "(7)") -- an orphaned cross-reference in the source
     rulebook itself, not something more reading can resolve. Falls
     back to the same "best skill in Archery/Melee/Magic" metric rule
     (g) itself already establishes, with the lower ``leader_id`` as a
     final deterministic tiebreak -- the same category of unsourced
     tiebreak ``turn/turn_processor.py _dispatch_mutual_encounter``
     already uses for its own King/challenger selection.
  i) "The 'Spy Table' is still used: When intercepting a character in
     an adjacent hex, if the Patrol has no Spy skill, there is a 50%
     chance that the character will wander into a random hex rather
     than intercept the intruder." -- modeled literally and only for
     this exact case: a same-hex intruder is always found (no roll,
     the same distance-0-is-certain convention ``turn/spy_table.py``
     already documents for directed Pursue/Trail), and a Spy skill of
     1+ is read as guaranteed interception -- the rule states only the
     skill-0 case explicitly, and no further Patrol-specific formula
     exists to interpolate from; an unsourced but conservative reading
     rather than inventing scaling the rule never states.

Combat resolution once a target is confirmed reuses the exact same
armyless-Encounter core ``turn/pursue_execution.py execute_pursue``
already uses (``has_combat_intent``/``is_encounter_accepted``/
``resolve_melee_duel``) -- duplicated rather than shared, the same
established small-per-consumer-duplication precedent ``_leader_combatant``
itself already uses across ``challenge_execution.py``/
``pursue_execution.py``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.office import Office
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.turn.challenge_execution import has_combat_intent, is_encounter_accepted
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    Combatant,
    archery_free_attack_bonus,
    loot_defeated_leader,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    resolve_melee_duel,
)
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.turn.office_holder import resolve_office_holder

_MAGIC_ABILITIES = (Ability.WHITE, Ability.NECROMANCY, Ability.ELEMENTAL, Ability.PSYCHIC, Ability.ILLUSION)


def _combat_skill_of(state: GameState, leader: LeaderState) -> int:
    """Rule (g)'s "best skill in Archery, Melee or Magic" -- see module docstring
    for why "Magic" is read as the max of all five magic schools.
    """

    archery = effective_skill_level(state, leader, Ability.ARCHERY)
    melee = effective_skill_level(state, leader, Ability.MELEE)
    magic = max(effective_skill_level(state, leader, ability) for ability in _MAGIC_ABILITIES)
    return max(archery, melee, magic)


def _spy_skill_of(state: GameState, leader: LeaderState) -> int:
    return effective_skill_level(state, leader, Ability.SPY)


def _is_enemy(patroller: LeaderState, candidate: LeaderState, state: GameState) -> bool:
    """Rule (c) -- see module docstring for why a kingdomless character (either
    side) is never automatically hostile, the same reading ``turn/
    turn_processor.py _sees_nonallied_defender`` already uses.
    """

    if patroller.kingdom_id is None or candidate.kingdom_id is None:
        return False
    return not state.is_allied(patroller.kingdom_id, candidate.kingdom_id)


def find_patrol_target(state: GameState, patroller_leader_id: int, bounds: MapBounds) -> LeaderState | None:
    """Rules (a)-(c), (f)-(h): the most threatening qualifying intruder to intercept
    this phase, or ``None`` if none qualify. See module docstring.
    """

    patroller = state.leaders.get(patroller_leader_id)
    if patroller is None or state.armies_commanded_by(patroller_leader_id):
        return None  # rule (a): an armied patroller's Patrol is ignored

    home_province = state.provinces.get(patroller.location)
    if home_province is None or home_province.owner_kingdom_id is None:
        return None  # rule (f): no owned/allied territory here to patrol from
    owner = home_province.owner_kingdom_id
    if owner != patroller.kingdom_id and not state.is_allied(owner, patroller.kingdom_id):
        return None

    watched_hexes = {patroller.location, *neighbors(patroller.location, bounds)}
    patroller_skill = _combat_skill_of(state, patroller)

    candidates: list[LeaderState] = []
    for candidate in state.leaders.values():
        if candidate.leader_id == patroller_leader_id or candidate.location not in watched_hexes:
            continue
        if state.armies_commanded_by(candidate.leader_id):
            continue  # rule (a): only armyless intruders are chased
        if not _is_enemy(patroller, candidate, state):
            continue  # rule (c)
        if _combat_skill_of(state, candidate) > patroller_skill:
            continue  # rule (g)
        candidates.append(candidate)

    if not candidates:
        return None

    # rule (h): most threatening by the same skill metric rule (g) uses --
    # point (7)'s own cross-reference doesn't resolve to anything in the
    # available rulebook text (see module docstring) -- lower leader_id
    # as a final deterministic tiebreak.
    candidates.sort(key=lambda c: (-_combat_skill_of(state, c), c.leader_id))
    return candidates[0]


def _leader_combatant(leader: LeaderState, state: GameState) -> Combatant:
    """Same construction as ``pursue_execution.py``/``challenge_execution.py``'s own
    ``_leader_combatant`` -- duplicated per this project's own established
    small-per-consumer-lookup precedent (see module docstring).

    **Unlike ``challenge_execution.py``'s own copy, this one never calls
    ``equipped_combat_weapon()``/``weapon_offensive_hit_multiplier()``/
    ``weapon_melee_damage_bonus()`` at all** -- a real, separate, pre-
    existing gap found while wiring Phase 682's Holy Sword vs-Undead
    bonus: Phase 535's own weapon-bonus wiring never reached Patrol
    encounters (same gap in ``cast_execution.py``'s Augur-Combat
    retaliator and ``pursue_execution.py``'s own duplicate). Not fixed
    here -- flagged for a future, separate phase.
    """

    melee_skill = effective_skill_level(state, leader, Ability.MELEE)

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

    return Combatant(
        name=leader.name,
        hit_points=CHARACTER_HIT_POINTS,
        melee_skill=melee_skill,
        neutral_duelist_bonus=neutral_bonus,
        temper=leader.temper,
        damage_reduction=damage_reduction,
        has_melee_hit_points_ability=has_melee_hit_points_ability,
        offensive_hit_multiplier=melee_mastery_offensive_hit_multiplier(leader.advanced_abilities),
        melee_damage_dealt_bonus=melee_mastery_damage_bonus(leader.advanced_abilities),
        is_humanoid=is_humanoid,
        has_duellists_medal_ability=AdvancedAbility.MELEE_DUELLISTS_MEDAL in leader.advanced_abilities,
        has_control_temper_ability=AdvancedAbility.MELEE_CONTROL_TEMPER in leader.advanced_abilities,
        archery_free_attack_bonus=archery_free_attack_bonus(leader.advanced_abilities),
        always_acts_first=always_acts_first,
        regenerates_hp=(1 if is_necro_mage else 0),
        regenerates_hp_interval=(2 if is_necro_mage else 1),
    )


@dataclass(slots=True)
class PatrolExecutionResult:
    intercepted: bool
    target_leader_id: int | None = None
    reason: str | None = None
    combat_occurred: bool = False
    winner_leader_id: int | None = None
    loser_leader_id: int | None = None
    loser_killed: bool = False
    # Phase 313: same field/reason as `turn/challenge_execution.py
    # ChallengeExecutionResult`'s own Phase 313 addendum.
    looted_item_ids: list[int] = field(default_factory=list)


def execute_patrol(
    state: GameState,
    patroller_leader_id: int,
    request: PursueRequest,
    rng: random.Random | None = None,
    *,
    board_width: int,
    board_height: int,
) -> PatrolExecutionResult:
    """Resolve one phase of a standing Patrol order: rules (a)-(c), (f)-(h)'s
    target detection, rule (i)'s Spy Table wander roll, and (once a target
    is confirmed) the same armyless-Encounter combat core directed Pursue
    uses. See module docstring for what isn't modeled and why.
    """

    rng = rng if rng is not None else random.Random()
    bounds = MapBounds(board_width, board_height)

    target = find_patrol_target(state, patroller_leader_id, bounds)
    if target is None:
        return PatrolExecutionResult(intercepted=False, reason="no intruder detected")

    patroller = state.leaders[patroller_leader_id]
    if target.location != patroller.location:  # adjacent, not same hex -- rule (i)
        if _spy_skill_of(state, patroller) == 0 and rng.random() < 0.5:
            return PatrolExecutionResult(
                intercepted=False, target_leader_id=target.leader_id, reason="wandered into a random hex"
            )

    if not has_combat_intent(request):
        return PatrolExecutionResult(intercepted=True, target_leader_id=target.leader_id, combat_occurred=False)

    accepted = is_encounter_accepted(
        target_is_king=target.is_king,
        target_leads_army=False,  # guaranteed by find_patrol_target's own rule (a) filter
        challenger_is_king=patroller.is_king,
        mutual_encounter=False,
        rng=rng,
    )
    if not accepted:
        return PatrolExecutionResult(intercepted=True, target_leader_id=target.leader_id, reason="encounter refused")

    patroller_combatant = _leader_combatant(patroller, state)
    target_combatant = _leader_combatant(target, state)
    combat_result = resolve_melee_duel(patroller_combatant, target_combatant, rng)

    if combat_result.winner is None:
        return PatrolExecutionResult(intercepted=True, target_leader_id=target.leader_id, combat_occurred=True)

    winner_id, loser_id = (
        (patroller_leader_id, target.leader_id)
        if combat_result.winner == "a"
        else (target.leader_id, patroller_leader_id)
    )
    state.remove_leader(loser_id)
    looted_items = loot_defeated_leader(state, winner_id=winner_id, loser_id=loser_id)

    return PatrolExecutionResult(
        intercepted=True,
        target_leader_id=target.leader_id,
        combat_occurred=True,
        winner_leader_id=winner_id,
        loser_leader_id=loser_id,
        loser_killed=True,
        looted_item_ids=[item.item_id for item in looted_items],
    )
