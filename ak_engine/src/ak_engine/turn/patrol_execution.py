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
     using his Spy or Thief ability that gameturn." Modeled via
     ``LeaderState.cover_ability`` (``turn/spy_cover.py``): an intruder
     whose plan has a Spy/Trail order or a Steal tactic is only noticed
     with the Spy Table's chance of being noticed (100/50/25/12/5% by
     level of the covering Talent).
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
already uses (``is_encounter_accepted``/``resolve_challenge_combat``) --
duplicated rather than shared, the same established small-per-consumer-
duplication precedent ``_leader_combatant`` itself already uses across
``challenge_execution.py``/``pursue_execution.py``.

**2026-11-06 -- real Steal/Give (and Fire Arrow/Cast/Flee) dispatch,
closing a real gap.** Until now, ``execute_patrol()``'s own combat
resolution used ``has_combat_intent`` as its dispatch gate and a bare
``resolve_melee_duel()`` call once past it -- so a Patrol's own
Encounter Plan tactics beyond a plain Melee/Fire-Arrow/Cast mix were
silently never walked at all: a Steal- or Give-only plan never even
reached combat (``has_combat_intent`` doesn't count either as "combat
intent" -- see ``challenge_execution.py has_combat_intent()``'s own
docstring), and even a plan that *did* pass the gate (because it also
had a Melee/Shoot/Cast tactic) still never actually ran its own Steal
or Give tactic, since the old code path went straight to an atomic
duel, skipping the tactic walk entirely. [3.16]'s own text that a
Patrol "is written... having the character 'Pursue' his own character
number" means Patrol *is* a Pursue order, so the same "All rules
listed under the Encounter action apply" scope ``turn/pursue_
execution.py``'s own module docstring already reads literally for
directed Pursue's armyless case applies here too -- there was never a
rulebook basis for Patrol's own Encounter Plan to support a narrower
tactic set than Pursue's. Fixed by switching to the exact same gate
(``challenge_execution.py plan_needs_combat_dispatch``) and the exact
same tactic-walking combat core (``resolve_challenge_combat``) Pursue's
own armyless case already uses, including the same ``target_tactics``
Special-Encounter-Plan lookup -- Patrol now genuinely inherits Fire
Arrow, Cast, Steal, Give, and Flee for free, the same way Pursue's own
Phase 290/743 addenda describe inheriting them from this exact same
core. The three stale "Patrol has no Fire Arrow at all" comments this
module and ``report/turn_report.py describe_patrol_combat()`` used to
carry are corrected alongside this fix, not left as a dangling false
claim.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.office import Office
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.turn.challenge_execution import (
    award_combat_cast_experience,
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
    resolve_refusal_to_meet,
    weapon_defensive_hit_multiplier,
    weapon_grants_auto_invisibility,
    weapon_melee_damage_bonus,
    weapon_offensive_hit_multiplier,
)
from ak_engine.turn.experience import add_experience
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.turn.office_holder import cached_office_holder_leader_id
from ak_engine.turn.sep_decode import target_uses_special_encounter_plan
from ak_engine.turn.spy_cover import notice_chance_of

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


def find_patrol_target(
    state: GameState, patroller_leader_id: int, bounds: MapBounds, rng: random.Random | None = None
) -> LeaderState | None:
    """Rules (a)-(c), (e), (f)-(h): the most threatening qualifying intruder to intercept
    this phase, or ``None`` if none qualify. See module docstring.

    Rule (e): an intruder using Spy or Thief that game turn (``LeaderState.cover_ability``)
    is only noticed with the Spy Table's own chance of being noticed (``turn/spy_cover.py``);
    rolled with ``rng`` (no roll, so no cover effect, when none is supplied).
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
        if rng is not None and candidate.cover_ability is not None:
            if rng.random() >= notice_chance_of(state, candidate):
                continue  # rule (e): slipped past the Patrol under Spy/Thief cover
        candidates.append(candidate)

    if not candidates:
        return None

    # rule (h): most threatening by the same skill metric rule (g) uses --
    # point (7)'s own cross-reference doesn't resolve to anything in the
    # available rulebook text (see module docstring) -- lower leader_id
    # as a final deterministic tiebreak.
    candidates.sort(key=lambda c: (-_combat_skill_of(state, c), c.leader_id))
    return candidates[0]


def _leader_combatant(
    leader: LeaderState, state: GameState, *, office_cache: dict[Office, int | None] | None = None
) -> Combatant:
    """Same construction as ``pursue_execution.py``/``challenge_execution.py``'s own
    ``_leader_combatant`` -- duplicated per this project's own established
    small-per-consumer-lookup precedent (see module docstring).

    **Phase 684 -- now wired with the same weapon/bow bonuses its
    ``challenge_execution.py`` counterpart already had** (Phase 535/536/
    682 had never reached Patrol encounters, flagged during Phase 682's
    own audit; closed here alongside the identical gap in
    ``cast_execution.py``'s Augur-Combat retaliator and ``pursue_
    execution.py``'s own duplicate).

    **Bug fix**: ``arcane_valor_hit_points_bonus()`` (Phase 538, "Arcane's
    Valor" -- +5 combat hit points for personally holding the Scepter of
    Life, +2 more for the King's own whole Kingdom, active only under
    ``GameType.ARCANES``) was introduced independently of Phase 684's own
    weapon-bonus sweep and never propagated here (nor to ``pursue_
    execution.py``'s/``cast_execution.py``'s own identical duplicate
    builders, fixed alongside this one) even though ``challenge_
    execution.py``/``battle_orchestrator.py``/``search_execution.py``/
    ``turn/random_encounter_execution.py`` all already fold it into
    their own starting ``hit_points`` -- a real, silent inconsistency
    under the ARCANES game type specifically (0 for every other game,
    per that function's own docstring).

    **Phase 894 -- a second drift found the same way**: this builder
    never computed/passed ``archery_skill`` at all (silently leaving it
    at the dataclass's own ``0`` default), unlike every one of its 5
    sibling copies (``challenge_execution.py``, ``pursue_execution.py``,
    ``cast_execution.py``, ``search_execution.py``, ``battle_
    orchestrator.py``). **Was a no-op at the time, not a live bug**:
    ``execute_patrol()``'s own combat resolution at that point called
    only ``resolve_melee_duel()`` -- Patrol had no Fire Arrow dispatch of
    any kind yet -- and ``archery_skill`` is read nowhere outside the
    Fire-Arrow-specific helpers in ``turn/encounter.py`` (``effective_
    archery_skill()``/``fire_arrow_hit_chance()``/``fire_arrow_free_
    attacks()``). Fixed anyway, matching this project's own established
    precedent (Phase 682/684) of closing a duplicate-builder field gap
    the moment it's found rather than leaving a correctly-computable
    field silently wrong for whenever a future caller does start reading
    it off this same ``Combatant`` -- which is exactly what the
    2026-11-06 addendum above does: ``execute_patrol()`` now reuses the
    same ``resolve_challenge_combat()`` core Pursue's armyless case
    does, so this ``archery_skill`` really is read, for real Fire Arrow
    dispatch, from this point on.
    """

    melee_skill = effective_skill_level(state, leader, Ability.MELEE)
    archery_skill = effective_skill_level(state, leader, Ability.ARCHERY)

    neutral_bonus = False
    if leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        neutral_bonus = kingdom is not None and kingdom.alignment is Alignment.NEUTRAL

    defender_leader_id = cached_office_holder_leader_id(state, Office.DEFENDER, office_cache)
    damage_reduction = 1 if defender_leader_id == leader.leader_id else 0
    illus_mage_leader_id = cached_office_holder_leader_id(state, Office.ILLUS_MAGE, office_cache)
    always_acts_first = illus_mage_leader_id == leader.leader_id
    necro_mage_leader_id = cached_office_holder_leader_id(state, Office.NECRO_MAGE, office_cache)
    is_necro_mage = necro_mage_leader_id == leader.leader_id
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
    # Phase 733: real per-swing detail -- lets `report/turn_report.py
    # describe_patrol_combat()` narrate the whole duel, not just its own
    # final blow. Same shape/reason as `turn/challenge_execution.py
    # ChallengeExecutionResult`'s own Phase 417 addendum.
    melee_swings: tuple[MeleeSwing, ...] = ()
    # 2026-11-06: the remaining fields `ChallengeExecutionResult`/
    # `PursueExecutionResult` already carry from `resolve_challenge_
    # combat()`'s own `ChallengeCombatOutcome` -- see module docstring's
    # own 2026-11-06 addendum for why Patrol now shares that exact same
    # combat core (and therefore the exact same shape) rather than its
    # own narrower bare-melee-duel result. Same field names, deliberately
    # -- `report/turn_report.py describe_steal()`/`describe_encounter_
    # combat()` already reuse `ChallengeExecutionResult`/`PursueExecutionResult`
    # by shared field name, no `isinstance` check; this widening lets
    # `PatrolExecutionResult` join that same reuse.
    fled: bool = False
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    steal_outcome: str | None = None
    steal_capture_range: CombatRange | None = None
    gold_raided: int = 0
    stolen_item_ids: list[int] = field(default_factory=list)
    fizzled_spells: tuple[tuple[str, Spell], ...] = ()
    # 2026-11-21: every Hand of Death channel this encounter ran, one
    # ``(caster_name, target_name, squeeze_hits, interrupt_damage, ending)``
    # entry each; ``ending`` is "won" / "interrupted" / "caster_killed" /
    # "immune" (the spell never engaged). Previously none of it reached the
    # report -- not even a winning channel -- so a real cast looked like it
    # was never carried out.
    hand_of_death_channels: tuple[tuple[str, str, tuple[int, ...], int | None, str], ...] = ()


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
    uses -- including that core's own Steal/Give/Fire-Arrow/Cast/Flee
    dispatch, not just a bare Melee duel (2026-11-06, see module
    docstring). See module docstring for what isn't modeled and why.
    """

    rng = rng if rng is not None else random.Random()
    bounds = MapBounds(board_width, board_height)

    target = find_patrol_target(state, patroller_leader_id, bounds, rng)
    if target is None:
        return PatrolExecutionResult(intercepted=False, reason="no intruder detected")

    patroller = state.leaders[patroller_leader_id]
    if target.location != patroller.location:  # adjacent, not same hex -- rule (i)
        if _spy_skill_of(state, patroller) == 0 and rng.random() < 0.5:
            return PatrolExecutionResult(
                intercepted=False, target_leader_id=target.leader_id, reason="wandered into a random hex"
            )

    if not plan_needs_combat_dispatch(request):
        return PatrolExecutionResult(intercepted=True, target_leader_id=target.leader_id, combat_occurred=False)

    has_spy_assassinate = AdvancedAbility.SPY_ASSASSINATE in patroller.advanced_abilities
    accepted = is_encounter_accepted(
        target_is_king=target.is_king,
        target_leads_army=False,  # guaranteed by find_patrol_target's own rule (a) filter
        challenger_is_king=patroller.is_king,
        mutual_encounter=False,
        rng=rng,
        has_spy_assassinate=has_spy_assassinate,
        has_sense_danger_evasion=target_evades_via_sense_danger(state, target, patroller),
    )
    # Phase 1041 bug fix -- [5.6]'s own Temper-based "Refusal to Meet"
    # gate (challenge_execution.py execute_challenge()'s own Phase 898
    # addendum), the same gap pursue_execution.py execute_pursue()'s own
    # Phase 1041 fix closes -- see that fix's own note for the full
    # sourcing. opponent_leads_army is always False here: find_patrol_
    # target()'s own rule (a) filter already guarantees an armied
    # patroller never reaches this point.
    if accepted and not has_spy_assassinate:
        if resolve_refusal_to_meet(target.temper, is_king=target.is_king, opponent_leads_army=False, rng=rng):
            accepted = False
    if not accepted:
        return PatrolExecutionResult(intercepted=True, target_leader_id=target.leader_id, reason="encounter refused")

    # Efficiency (Phase 1193): one shared office-holder cache for both
    # sibling Combatants built in this one call -- see
    # cached_office_holder_leader_id()'s own docstring.
    office_cache: dict[Office, int | None] = {}
    patroller_combatant = _leader_combatant(patroller, state, office_cache=office_cache)
    target_combatant = _leader_combatant(target, state, office_cache=office_cache)
    # Same target_tactics lookup as pursue_execution.py execute_pursue()'s
    # own armyless case -- the target is structurally armyless here too
    # (find_patrol_target()'s own rule (a) filter), so [5.10]'s own
    # Special Encounter Plan eligibility check applies identically.
    target_tactics = list(target.special_encounter_plan) if target_uses_special_encounter_plan(state, target) else None
    combat_result = resolve_challenge_combat(
        request.tactics,
        patroller,
        patroller_combatant,
        target,
        target_combatant,
        state,
        rng,
        target_tactics=target_tactics,
    )

    # Phase 686: AKGEN_reverse_engineering_report (2).md SS3.3's own
    # Melee/Archery rows -- "evento di mischia/duello qualificante"/
    # "evento di tiro riuscito" -- Melee: a landed hit; Archery: an attempted shot, a miss counts too (rulebook [3.13] "per tattica tentata", user decision 2026-11-23, Archery only), credited once per
    # encounter per side, independent of who ultimately wins.
    if any(s.hit for s in combat_result.melee_swings if s.attacker == "a"):
        add_experience(patroller, Ability.MELEE, 10, rng)
    if any(s.hit for s in combat_result.melee_swings if s.attacker == "b"):
        add_experience(target, Ability.MELEE, 10, rng)
    if any(s.shooter == "a" for s in combat_result.fire_arrow_shots):
        add_experience(patroller, Ability.ARCHERY, 10, rng)
    if any(s.shooter == "b" for s in combat_result.fire_arrow_shots):
        add_experience(target, Ability.ARCHERY, 10, rng)
    award_combat_cast_experience(state, combat_result.cast_successes, rng)

    if combat_result.fled:
        return PatrolExecutionResult(
            intercepted=True,
            target_leader_id=target.leader_id,
            combat_occurred=True,
            fled=True,
            melee_swings=combat_result.melee_swings,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
            gold_raided=combat_result.gold_raided,
            stolen_item_ids=combat_result.stolen_item_ids,
            fizzled_spells=combat_result.fizzled_spells,
            hand_of_death_channels=combat_result.hand_of_death_channels,
        )

    if combat_result.winner is None:
        return PatrolExecutionResult(
            intercepted=True,
            target_leader_id=target.leader_id,
            combat_occurred=True,
            melee_swings=combat_result.melee_swings,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
            gold_raided=combat_result.gold_raided,
            stolen_item_ids=combat_result.stolen_item_ids,
            fizzled_spells=combat_result.fizzled_spells,
            hand_of_death_channels=combat_result.hand_of_death_channels,
        )

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
        melee_swings=combat_result.melee_swings,
        fire_arrow_shots=combat_result.fire_arrow_shots,
        loser_killed=True,
        looted_item_ids=[item.item_id for item in looted_items],
        steal_outcome=combat_result.steal_outcome,
        steal_capture_range=combat_result.steal_capture_range,
        gold_raided=combat_result.gold_raided,
        stolen_item_ids=combat_result.stolen_item_ids,
        fizzled_spells=combat_result.fizzled_spells,
        hand_of_death_channels=combat_result.hand_of_death_channels,
    )
