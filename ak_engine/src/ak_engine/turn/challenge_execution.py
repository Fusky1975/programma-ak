"""Executing a Challenge (rulebook [3.12] "Encounter Character") order -- Phase 50.

Reuses ``turn/encounter.py``'s combat core (Phase 48), the same way
``turn/battle_orchestrator.py``'s Duel wiring did (Phase 49) -- built
once, reused by whichever consumer is ready for it next.

**Fire Arrow (Phase 273)**: combat resolution now walks ``request.
tactics`` via ``turn/encounter.py resolve_encounter_combat()`` instead
of always calling ``resolve_melee_duel()`` directly -- a ``SHOOT``
tactic listed before ``MELEE`` genuinely fires first now, per [5.10]'s
"Special Encounter Plan" (Talk/Fulfill/Steal excluded, but Fire Arrow
and Melee both real Encounter Plan tactics). Previously ``Maneuver.
SHOOT`` was only ever consulted by ``has_combat_intent`` to decide
*whether* the King/Hero acceptance restrictions apply -- the actual
duel always resolved as Melee regardless, a real, previously
undocumented gap this phase closes. ``_leader_combatant`` now also
reads ``Ability.ARCHERY`` (previously left at ``Combatant``'s own
default of 0, which would have made Fire Arrow a guaranteed 0-free-
attacks no-op even once wired).

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

**Phase 290 addendum -- Personal-Combat spells wired in, generalized for
a leader-vs-leader Encounter.** ``turn/search_execution.py``'s own
Phase 289 addendum flagged this module's own combat resolution as still
Melee/Fire-Arrow-only, with a stale docstring claim above ("classifying
which spells count as personal combat spells needs a spell-effect
system this project doesn't have") that predates Phase 209-238 actually
building that system for Search. ``ChallengeRequest.tactics`` already
decodes a ``CAST`` entry's own spell id via the shared ``SearchTactic``
type (``turn/challenge_pursue_decode.py``'s own ``_TACTICS_WITH_SUB_
OBJECT``) -- only the *effect* was never dispatched, since ``resolve_
encounter_combat()`` (the walk this module previously called) only
ever recognizes ``Maneuver.SHOOT``/``MELEE``, silently skipping every
other tactic including ``CAST``.

``_resolve_personal_combat_cast()`` below is **not** a straight reuse of
``turn/search_execution.py _resolve_cast_tactic()`` -- that function is
a private closure tied to Search's own concepts (a ``Feature``'s
guardian monster, ``MONSTER_MAGIC_ABILITIES``, a rolled monster combat
stat block). An Encounter/Pursue combatant is *always* another leader,
never a monster, so every one of that function's own "target is a
monster" branches is structurally unreachable here -- this is a
genuine simplification, re-derived branch-for-branch from Search's own
"target is a leader" branches (the ``else`` half of each ``if
target_is_monster: ... else: ...``), not a guess at new behavior:

- **Holy Symbol/Spiritwrack/Hand of Death's own Undead-or-Anti-Holy
  eligibility** reads straight off ``target_leader.alignment`` (no
  species lookup possible or needed).
- **Telekinetic Storm/Fireball's own submarine-monster immunity** never
  applies (no leader is ever "submarine") -- always ``target_is_immune=
  False``.
- **Ice Suspension's own ghost/demon-immune and flying-monster branches**
  never apply either -- a leader target always falls through to the
  freeze-or-slow HP-threshold branch.
- **Mirror-Image/Illusory Hero's own opponent-intelligence tier** is
  always ``MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT`` (High Human)
  plus the caster's own Sage/Illusion-driven bonus -- the same branch
  Search already uses for its own leader-target case.
- **Gate Demon** still summons a real monster ``Combatant`` (the demon
  itself, not the opponent) via ``MONSTER_COMBAT_STATS``/``roll_gate_
  demon_type()`` -- this part is identical to Search's own code, a
  monster stat lookup for the *summoned creature*, unrelated to the
  leader-vs-leader opponent classification above.
- **Lava Pool's own speed-keyed escape chance** defaults to
  ``MonsterSpeed.MEDIUM``, per [5.6]'s own text Search already reads
  this way for a leader target ("medium-speed monsters or other
  characters is a 50-50 proposition").
- **Augur Combat's "cast first" branch** (silent simulation -> courage-
  gated shirk) is wired identically to Search's own leader-caster case
  -- ``caster_is_leader`` is unconditionally true here (nothing but a
  leader ever initiates a Challenge/Pursue). **The "cast later -> acts
  as Flee" branch is deliberately left unwired**: it needs a real Flee
  *tactic* and [5.6]'s own base-chance table, and neither exists
  anywhere in this module or ``turn/pursue_execution.py`` today (unlike
  Search, which has both) -- a genuine, narrower gap than Words of
  Healing's own Phase 289 fix, not attempted here to avoid silently
  half-wiring a spell whose second branch would otherwise just look
  broken. Recorded as a confirmed, sourced gap.

**Charm and Words of Healing** both need no monster-related
simplification at all -- Charm's "guaranteed Flee" and Words of
Healing's "heal to ``CHARACTER_HIT_POINTS``" already only ever
reference the caster.

**A successful Charm/Augur-Combat-first flee needs a new outcome this
module's own result types never had**: ``ChallengeExecutionResult``/
``PursueExecutionResult`` (``turn/pursue_execution.py``) both gain a
new ``fled: bool = False`` field, the same "won, lost, or nobody died"
tri-state ``SearchExecutionResult.fled`` already models for Search --
default ``False`` keeps every existing caller and test unaffected.

**``resolve_challenge_combat()``** replaces the previous raw
``resolve_encounter_combat([tactic.maneuver for tactic in request.
tactics], ...)`` call in both ``execute_challenge`` (here) and
``execute_pursue`` (``turn/pursue_execution.py``, which imports this
function the same way it already imports ``has_combat_intent``/``is_
encounter_accepted``) -- it walks the *full* ``SearchTactic`` list
(not just each entry's own ``.maneuver``), dispatching ``CAST`` through
``_resolve_personal_combat_cast()`` and falling through to Melee/Fire
Arrow exactly as ``resolve_encounter_combat()`` already did for every
other tactic, including the same "exhausted list defaults to Melee"
rule. A stat-modifier spell (Spiritwrack, Invisibility, Holy Symbol
against a non-Undead target, etc.) that grants ``bonus_unanswered_
attacks`` (Psychic Blast, Ice Suspension's own "slowed" branch) has
those bonus swings resolved immediately via ``_consume_bonus_attacks()``
-- the same "resolved right after the CAST tactic that granted them"
rule Search's own docstring already establishes, simplified here since
the bonus attacker is always the caster and the bonus defender is
always the target (no monster-side complexity to thread through).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.monster import MONSTER_COMBAT_STATS, MONSTER_NAMES, MonsterSpeed, roll_gate_demon_type
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_DAMAGE_RANGE,
    INVISIBILITY_HIT_CHANCE_MULTIPLIER,
    MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT,
    PERSONAL_COMBAT_SPELL_ABILITY,
    Combatant,
    CombatRange,
    EncounterCombatResult,
    blocks_cast_and_archery,
    control_undead_failure_new_hit_points,
    holy_symbol_hit_chance,
    ice_suspension_is_frozen,
    ice_suspension_slowed_bonus_rounds,
    illusory_hero_alignments_are_implacably_hostile,
    mirror_image_leader_disbelief_bonus,
    resolve_augur_combat,
    resolve_fire_arrow_duel,
    resolve_gate_demon_refusal,
    resolve_hand_of_death_channel,
    resolve_illusory_hero_duel,
    resolve_lava_pool_escape,
    resolve_melee_duel,
    resolve_mirror_image_duel,
    resolve_personal_combat_spell_cast,
    roll_fireball_damage,
    roll_holy_symbol_undead_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spiritwrack_melee_damage_reduction,
    words_of_healing_heal,
)
from ak_engine.turn.search_decode import SearchTactic

_COMBAT_MANEUVERS = frozenset({Maneuver.MELEE, Maneuver.SHOOT})

# Phase 290: same secret-spell skill-5+ gate `turn/search_execution.py`
# uses for Illusory Hero/Words of Healing, duplicated per this project's
# own "same shared fact, independent citation per consumer" convention.
ILLUS_HERO_KNOWN_ABILITY_LEVEL = 5
WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL = 5


def has_combat_intent(request: ChallengeRequest) -> bool:
    """Rulebook [3.12]: "If the encounter plan has no combat tactics or personal combat
    spells (including Charm), these restrictions do not apply." True if
    any decoded tactic is Melee, Fire Arrow, or a ``CAST`` tactic whose
    own sub-object decodes to a real ``Spell`` -- see module docstring's
    own Phase 290 addendum for why *every* ``CAST`` tactic inside an
    Encounter Plan is necessarily attempting a Personal-Combat spell
    (Action-Cast spells never appear here, only as a top-level
    ``ActionCode.CAST`` phase, confirmed against all real sample data
    elsewhere in this project) -- no further classification is needed.
    Steal isn't checked here (a separate, still-unmodeled tactic).
    """

    for tactic in request.tactics:
        if tactic.maneuver in _COMBAT_MANEUVERS:
            return True
        if tactic.maneuver is Maneuver.CAST:
            try:
                Spell(tactic.sub_object)
            except (TypeError, ValueError):
                continue
            return True
    return False


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


def _resolve_personal_combat_cast(
    caster: Combatant,
    caster_leader: LeaderState,
    target: Combatant,
    target_leader: LeaderState,
    tactic: SearchTactic,
    state: GameState,
    rng: random.Random,
    *,
    is_first_tactic: bool,
) -> str | None:
    """Leader-vs-leader Personal-Combat spell dispatch -- see module
    docstring's own Phase 290 addendum for how this was re-derived
    branch-for-branch from ``turn/search_execution.py
    _resolve_cast_tactic()``'s own leader-target branches. Returns
    ``"a"`` (caster wins), ``"b"`` (target wins), ``"fled"`` (Charm, or
    Augur Combat cast first and shirking), or ``None`` if the encounter
    continues (a failed cast, a stat-modifier effect, or an ineligible
    target).
    """

    if caster.blocked_from_cast_and_archery:
        return None
    try:
        spell = Spell(tactic.sub_object)
    except (TypeError, ValueError):
        return None

    caster_is_undead = caster_leader.alignment is Alignment.UNDEAD
    if spell is Spell.CHARM:
        ability = Ability.NECROMANCY if caster_is_undead else Ability.PSYCHIC
    elif spell is Spell.ILLUS_HERO:
        ability = Ability.ILLUSION
    elif spell is Spell.GATE_DEMON:
        ability = Ability.NECROMANCY
    elif spell is Spell.LAVA_POOL:
        ability = Ability.ELEMENTAL
    elif spell is Spell.AUGUR_COMBAT:
        ability = Ability.PSYCHIC
    elif spell is Spell.HEAL:
        ability = Ability.WHITE
    elif spell in PERSONAL_COMBAT_SPELL_ABILITY:
        ability = PERSONAL_COMBAT_SPELL_ABILITY[spell]
    else:
        return None  # not modeled (any spell outside the 16 Personal-Combat spells)

    if spell is Spell.CONTROL_UNDEAD:
        if target_leader.alignment is not Alignment.UNDEAD:
            return None
    if spell is Spell.ILLUS_HERO:
        level = effective_skill_level(state, caster_leader, ability)
        if level < ILLUS_HERO_KNOWN_ABILITY_LEVEL:
            return None
    elif spell is Spell.HEAL:
        level = effective_skill_level(state, caster_leader, ability)
        if level < WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL:
            return None
    else:
        level = effective_skill_level(state, caster_leader, ability)

    kingdom = state.kingdoms.get(caster_leader.kingdom_id) if caster_leader.kingdom_id is not None else None
    caster_is_pagan = ability is not Ability.WHITE and kingdom is not None and kingdom.alignment is Alignment.PAGAN

    if spell is Spell.AUGUR_COMBAT and not is_first_tactic:
        # `turn/encounter.py`'s own Phase 205 addendum: "if it comes
        # later, then the result will be an attempt to flee." Unlike
        # Search, this module has no real Flee tactic or [5.6] base-
        # chance table wired -- module docstring's own Phase 290
        # addendum records this as a genuine, still-open gap rather than
        # guessing a formula.
        return None

    succeeded = resolve_personal_combat_spell_cast(level, rng, caster_is_pagan=caster_is_pagan)

    if spell is Spell.CONTROL_UNDEAD:
        if succeeded:
            return "a"
        target.hit_points = control_undead_failure_new_hit_points(target.hit_points, rng)
        return None

    if not succeeded:
        return None

    if spell is Spell.CHARM:
        return "fled"

    if spell is Spell.HOLY_SYMBOL:
        target_is_undead_or_anti_holy = target_leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
        caster.defensive_hit_multiplier *= holy_symbol_hit_chance(
            1.0, level, target_is_undead_or_anti_holy=target_is_undead_or_anti_holy
        )
        if target_is_undead_or_anti_holy:
            target.hit_points -= roll_holy_symbol_undead_damage(level, rng)
            if target.hit_points <= 0:
                return "a"
        return None

    if spell is Spell.SPIRITWRACK:
        target_is_immune = target_leader.alignment is Alignment.UNDEAD
        target.melee_damage_dealt_reduction += spiritwrack_melee_damage_reduction(
            level, rng, target_is_immune=target_is_immune, target_is_animal_intelligence=False
        )
        target.blocked_from_cast_and_archery = blocks_cast_and_archery(target_is_immune=target_is_immune)
        return None

    if spell is Spell.PSYCHIC_BLAST:
        caster.bonus_unanswered_attacks += roll_psychic_blast_stun_rounds(rng)
        return None

    if spell is Spell.TELEK_STORM:
        target.hit_points -= roll_telekinetic_storm_victim_damage(rng, target_is_immune=False)
        caster.hit_points -= roll_telekinetic_storm_caster_damage(CombatRange.SPELL_RANGE, rng, target_is_immune=False)
        if target.hit_points <= 0:
            return "a"
        if caster.hit_points <= 0:
            return "b"
        return None

    if spell is Spell.INVISIBILITY:
        caster.defensive_hit_multiplier *= INVISIBILITY_HIT_CHANCE_MULTIPLIER
        caster.is_invisible = True
        return None

    if spell is Spell.FIREBALL:
        target.hit_points -= roll_fireball_damage(level, rng, target_is_immune=False)
        if target.hit_points <= 0:
            return "a"
        return None

    if spell is Spell.ICE_SUSPEND:
        if ice_suspension_is_frozen(target.hit_points, level):
            return "a"
        caster.bonus_unanswered_attacks += ice_suspension_slowed_bonus_rounds(target.hit_points, level)
        return None

    if spell is Spell.HAND_OF_DEATH:
        target_is_immune = target_leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
        channel_result = resolve_hand_of_death_channel(caster, target, level, rng, target_is_immune=target_is_immune)
        if channel_result.winner is not None:
            # "a" in resolve_hand_of_death_channel's own convention always means the caster.
            return "a"
        return None

    if spell is Spell.MIRROR_IMAGE:
        opponent_tier = MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT
        sage_level = effective_skill_level(state, caster_leader, Ability.SAGE)
        illusion_level = effective_skill_level(state, caster_leader, Ability.ILLUSION)
        opponent_disbelief_bonus = mirror_image_leader_disbelief_bonus(sage_level, illusion_level)
        duel_result = resolve_mirror_image_duel(
            caster, target, opponent_tier, level, rng, opponent_disbelief_bonus=opponent_disbelief_bonus
        )
        if duel_result.winner == "a":
            return "a"
        if duel_result.winner == "b":
            return "b"
        return None

    if spell is Spell.ILLUS_HERO:
        hero = state.leaders.get(VALHALLA_VISITOR_LEADER_ID)
        if hero is None:
            return None
        hero_combatant = _leader_combatant(hero, state)
        opponent_tier = MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT
        sage_level = effective_skill_level(state, caster_leader, Ability.SAGE)
        illusion_level = effective_skill_level(state, caster_leader, Ability.ILLUSION)
        opponent_disbelief_bonus = mirror_image_leader_disbelief_bonus(sage_level, illusion_level)
        turns_on_master = (
            hero.alignment is not None
            and caster_leader.alignment is not None
            and illusory_hero_alignments_are_implacably_hostile(hero.alignment, caster_leader.alignment)
        )
        duel_result = resolve_illusory_hero_duel(
            caster,
            target,
            hero_combatant,
            opponent_tier,
            level,
            rng,
            opponent_disbelief_bonus=opponent_disbelief_bonus,
            turns_on_master=turns_on_master,
        )
        if duel_result.winner == "a":
            return "a"
        if duel_result.winner == "b":
            return "b"
        return None

    if spell is Spell.GATE_DEMON:
        target_alignment = target_leader.alignment
        opponent_eligible_for_refusal = (
            target_alignment is not None and ALIGNMENT_ORDINAL[target_alignment] >= ALIGNMENT_ORDINAL[Alignment.EVIL]
        )
        if opponent_eligible_for_refusal and resolve_gate_demon_refusal(rng):
            return None  # the gate opened, but the demon refused to fight
        demon_species = roll_gate_demon_type(rng)
        demon_stats = MONSTER_COMBAT_STATS.get(demon_species)
        if demon_stats is None:
            return None
        demon = Combatant(
            name=MONSTER_NAMES.get(demon_species, "demon"),
            hit_points=rng.randint(*demon_stats.hit_points_range),
            melee_skill=demon_stats.melee_skill,
            melee_damage_range=demon_stats.melee_damage,
            archery_skill=demon_stats.missile_skill,
            missile_damage_range=demon_stats.missile_damage if demon_stats.missile_damage is not None else FIRE_ARROW_DAMAGE_RANGE,
        )
        duel_result = resolve_melee_duel(demon, target, rng)
        if duel_result.winner == "a":
            return "a"
        return None

    if spell is Spell.LAVA_POOL:
        target_speed = MonsterSpeed.MEDIUM
        if resolve_lava_pool_escape(target_speed, rng):
            return None
        return "a"

    if spell is Spell.AUGUR_COMBAT:
        # is_first_tactic is guaranteed True here (the "cast later" case
        # already returned above, before the cast roll).
        if caster_leader.temper is None:
            return None
        simulated_caster = replace(caster)
        simulated_target = replace(target)
        simulated_result = resolve_melee_duel(simulated_caster, simulated_target, rng)
        would_lose_simulated_combat = simulated_result.winner == "b"
        if resolve_augur_combat(would_lose_simulated_combat, caster_leader.temper, rng):
            return "fled"
        return None

    if spell is Spell.HEAL:
        words_of_healing_heal(caster, CHARACTER_HIT_POINTS)
        return None

    return None


def _consume_bonus_attacks(attacker: Combatant, defender: Combatant, rng: random.Random) -> str | None:
    """Psychic Blast's/Ice Suspension's own "bonus attack rounds" -- free,
    unanswered Melee swings, resolved immediately after the CAST tactic
    that granted them (same convention as ``turn/search_execution.py``'s
    own ``_consume_bonus_attacks()``). The bonus attacker is always the
    caster and the bonus defender always the target here -- no monster-
    side branch to thread through, unlike Search's own version.
    """

    while attacker.bonus_unanswered_attacks > 0:
        attacker.bonus_unanswered_attacks -= 1
        damage = roll_melee_attack(
            rng, damage_range=attacker.melee_damage_range, hit_chance_multiplier=defender.defensive_hit_multiplier
        )
        damage = max(0, damage - attacker.melee_damage_dealt_reduction)
        defender.hit_points -= damage
        if defender.hit_points <= 0:
            return "a"
    return None


@dataclass(slots=True)
class ChallengeCombatOutcome:
    winner: str | None  # "a" (challenger/pursuer) / "b" (target) / None (inconclusive)
    fled: bool = False


def resolve_challenge_combat(
    tactics: list[SearchTactic],
    caster_leader: LeaderState,
    caster: Combatant,
    target_leader: LeaderState,
    target: Combatant,
    state: GameState,
    rng: random.Random,
) -> ChallengeCombatOutcome:
    """Walks an Encounter Plan's full ``SearchTactic`` list (not just each
    entry's own ``.maneuver``, unlike ``turn/encounter.py resolve_
    encounter_combat()``), dispatching ``Maneuver.CAST`` through
    ``_resolve_personal_combat_cast()`` in addition to the Fire-Arrow-
    then-Melee walk that function already implements. See module
    docstring's own Phase 290 addendum.
    """

    for index, tactic in enumerate(tactics):
        if tactic.maneuver is Maneuver.SHOOT:
            result = resolve_fire_arrow_duel(caster, target, rng)
            if result.winner is not None:
                return ChallengeCombatOutcome(winner=result.winner)
            continue
        if tactic.maneuver is Maneuver.MELEE:
            result = resolve_melee_duel(caster, target, rng)
            return ChallengeCombatOutcome(winner=result.winner)
        if tactic.maneuver is Maneuver.CAST:
            outcome = _resolve_personal_combat_cast(
                caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=(index == 0)
            )
            if outcome == "fled":
                return ChallengeCombatOutcome(winner=None, fled=True)
            if outcome in ("a", "b"):
                return ChallengeCombatOutcome(winner=outcome)
            bonus_winner = _consume_bonus_attacks(caster, target, rng)
            if bonus_winner is not None:
                return ChallengeCombatOutcome(winner=bonus_winner)
            continue
        # every other tactic is unwired -- skip it and keep walking
    result = resolve_melee_duel(caster, target, rng)
    return ChallengeCombatOutcome(winner=result.winner)


@dataclass(slots=True)
class ChallengeExecutionResult:
    accepted: bool
    reason: str | None = None
    combat_occurred: bool = False
    winner_leader_id: int | None = None
    loser_leader_id: int | None = None
    loser_killed: bool = False
    # Phase 290: a successful Charm, or Augur Combat cast first and
    # shirking -- the caster escapes unharmed, distinct from an
    # inconclusive draw (combat_occurred=True, winner_leader_id=None).
    fled: bool = False


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
    combat_result = resolve_challenge_combat(
        request.tactics, challenger, challenger_combatant, target, target_combatant, state, rng
    )

    if combat_result.fled:
        return ChallengeExecutionResult(accepted=True, combat_occurred=True, fled=True)
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
