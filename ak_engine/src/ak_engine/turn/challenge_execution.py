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

**Phase 292 addendum -- the real round-based range engine, and spell
disruption, both now wired.** ``turn/search_execution.py``'s own Phase
289 addendum (and this module's own docstring, until now) both flagged
disruption as structurally unwireable without "the same round-based,
three-``CombatRange`` state machine ``turn/encounter.py``'s own module
docstring has flagged as unbuilt since Phase 60/179/209-211/237-238."
**User direction, confirmed via ``AskUserQuestion``**: build that real
engine (rather than a documented approximation or leaving the gap open)
here in ``resolve_challenge_combat()`` specifically -- ``turn/
search_execution.py``'s own richer tactic set (Steal/Talk/Fulfill/
Scout/Use_MI/Beg, interleaved with Cast/Melee/Shoot) is explicitly
**out of scope**, a distinct future phase, not attempted alongside this
one. See ``resolve_challenge_combat()``'s own docstring for the full
range-tracking design, and ``turn/encounter.py``'s own Phase 292
addendum for the corrected disruption formula itself (RULES.AK [5.1]:
"3 hit points will disrupt your spell 50% of the time, while a missed
swing will disrupt you 30% of the time" -- **also user-confirmed via
``AskUserQuestion``** as a linear-on-damage rate, replacing this
project's own earlier "20% cumulative per hit" paraphrase, which did
not match the primary source once located and read directly).

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
from dataclasses import dataclass, field, replace

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
    apply_temper_melee_setup,
    blocks_cast_and_archery,
    control_undead_failure_new_hit_points,
    holy_symbol_hit_chance,
    ice_suspension_is_frozen,
    ice_suspension_slowed_bonus_rounds,
    illusory_hero_alignments_are_implacably_hostile,
    loot_defeated_leader,
    mirror_image_leader_disbelief_bonus,
    resolve_augur_combat,
    resolve_fire_arrow_duel,
    resolve_gate_demon_refusal,
    resolve_hand_of_death_channel,
    resolve_illusory_hero_duel,
    resolve_lava_pool_escape,
    resolve_melee_duel,
    resolve_mirror_image_duel,
    resolve_one_melee_round,
    resolve_personal_combat_spell_cast,
    resolve_reactive_melee_swing,
    resolve_spell_disruption,
    resolve_spell_disruption_from_missed_attack,
    resolve_steal_attempt,
    resolve_steal_evasion,
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
    caster_leader: LeaderState | None,
    target: Combatant,
    target_leader: LeaderState | None,
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

    **``caster_leader``/``target_leader`` are ``None``-able (Phase 291)**:
    ``turn/battle_orchestrator.py``'s own Duel wiring reuses this same
    dispatcher, and a Duel side can be the provincial garrison commander
    ([7.1]: "has no abilities") -- no real ``LeaderState`` exists for it
    at all. ``caster_leader is None`` makes any ``CAST`` tactic an
    immediate no-op (a commander with no abilities cannot cast a
    spell); ``target_leader is None`` is read as an ordinary,
    alignment-unrecorded target -- every branch below already treats an
    unset ``alignment`` as "not eligible/not immune," the same
    permissive-missing-data convention used everywhere else in this
    project.
    """

    if caster.blocked_from_cast_and_archery:
        return None
    if caster_leader is None:
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
        if target_leader is None or target_leader.alignment is not Alignment.UNDEAD:
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
        target_is_undead_or_anti_holy = target_leader is not None and target_leader.alignment in (
            Alignment.UNDEAD,
            Alignment.ANTI_HOLY,
        )
        caster.defensive_hit_multiplier *= holy_symbol_hit_chance(
            1.0, level, target_is_undead_or_anti_holy=target_is_undead_or_anti_holy
        )
        if target_is_undead_or_anti_holy:
            target.hit_points -= roll_holy_symbol_undead_damage(level, rng)
            if target.hit_points <= 0:
                return "a"
        return None

    if spell is Spell.SPIRITWRACK:
        target_is_immune = target_leader is not None and target_leader.alignment is Alignment.UNDEAD
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
        target_is_immune = target_leader is not None and target_leader.alignment in (
            Alignment.UNDEAD,
            Alignment.ANTI_HOLY,
        )
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
        target_alignment = target_leader.alignment if target_leader is not None else None
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


def _apply_successful_theft(state: GameState, thief: LeaderState, victim: LeaderState) -> None:
    """The theft's own tangible effect -- Phase 305: "oro o uno o piu'
    oggetti magici (sempre che siano presenti)", with no quantity formula
    for either resource. Gold theft stays unmodeled (see module
    docstring's own Phase 305 addendum). Item theft is modeled directly:
    the victim's first held item (if any) changes hands via ``GameState.
    transfer_item()`` (Phase 140) -- "how many" is read as exactly one,
    matching ``turn/trade_execution.py execute_give()``'s own established
    "one item per order" convention, this project's only other real
    item-transfer mechanic, rather than guessing at "all of them."
    """

    items = state.items_held_by(victim.leader_id)
    if items:
        state.transfer_item(items[0].item_id, thief.leader_id)


def _resolve_steal_tactic(
    caster_leader: LeaderState | None,
    target_leader: LeaderState | None,
    state: GameState,
    rng: random.Random,
) -> str:
    """Steal [ST], rulebook [5.5] -- Phase 305. See module docstring's own
    Phase 305 addendum for the full quoted text and the reasoning behind
    every branch below.

    Returns ``"success"`` (theft applied, plan continues), ``"evaded"``
    (failed but not caught, plan continues), ``"executed"`` (thief
    killed outright, no combat), ``"ransom"`` (King-vs-King capture,
    nobody dies), ``"combat"`` (caller must resolve a forced personal-
    combat encounter at a freshly-rolled range), or ``"unresolved"`` (a
    King caught robbing a non-King army-commanding Hero -- the one
    combination none of the three sourced capture branches covers).

    A garrison commander (``caster_leader``/``target_leader`` is
    ``None``, Phase 291's own Duel reuse) can neither attempt nor be a
    Steal target -- no ``LeaderState`` exists to read a Thief skill,
    royal status, or army command from.
    """

    if caster_leader is None or target_leader is None:
        return "unresolved"

    level = effective_skill_level(state, caster_leader, Ability.THIEF)
    target_leads_army = bool(state.armies_commanded_by(target_leader.leader_id))
    if resolve_steal_attempt(level, rng, target_leads_army=target_leads_army):
        _apply_successful_theft(state, caster_leader, target_leader)
        return "success"
    if resolve_steal_evasion(level, rng):
        return "evaded"

    target_is_protected = target_leader.is_king or target_leads_army
    if not target_is_protected:
        return "combat"
    if caster_leader.is_king and target_leader.is_king:
        kingdom = state.kingdoms.get(caster_leader.kingdom_id) if caster_leader.kingdom_id is not None else None
        if kingdom is None or kingdom.treasury <= 0:
            return "executed"
        kingdom.treasury -= kingdom.treasury // 2
        return "ransom"
    if not caster_leader.is_king:
        return "executed"
    return "unresolved"  # a King caught robbing a non-King army-commanding Hero


@dataclass(slots=True)
class ChallengeCombatOutcome:
    winner: str | None  # "a" (challenger/pursuer) / "b" (target) / None (inconclusive)
    fled: bool = False
    # Phase 306: whichever Steal outcome `_resolve_steal_tactic()` returned
    # ("success"/"evaded"/"executed"/"ransom"/"combat"/"unresolved"), if the
    # plan contained a STEAL tactic at all -- carried through to whatever
    # this function eventually returns (not just a terminal STEAL branch),
    # so `report/turn_report.py describe_steal()` can narrate it even when
    # the encounter's actual winner was decided by a later tactic.
    steal_outcome: str | None = None
    # Set only when steal_outcome == "combat" -- the freshly-rolled range
    # the capture-combat happened at, needed to pick the right `SNEAKUP_
    # RANGE_*` clause.
    steal_capture_range: CombatRange | None = None


def _close_to(target_range: CombatRange, current_range: CombatRange) -> CombatRange:
    """Phase 292: advance ``current_range`` one tier per (implicit,
    RNG-free) round until it reaches ``target_range`` -- closing the
    distance is pure movement, not a combat action, so it consumes no
    roll (the same "movement itself consumes no RNG" convention this
    project's own Move/Pursue/Trail chase-step primitives already
    established). Never widens the range back out -- there is no
    rulebook mechanic for retreating to a farther range mid-Encounter.
    """

    while current_range.value < target_range.value:
        current_range = CombatRange(current_range.value + 1)
    return current_range


def resolve_challenge_combat(
    tactics: list[SearchTactic],
    caster_leader: LeaderState | None,
    caster: Combatant,
    target_leader: LeaderState | None,
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

    ``caster_leader``/``target_leader`` accept ``None`` (Phase 291) for
    ``turn/battle_orchestrator.py``'s own Duel reuse, where a side can be
    the provincial garrison commander -- no real ``LeaderState`` exists
    for it. See ``_resolve_personal_combat_cast()``'s own docstring for
    what ``None`` means on each side.

    **Phase 292 -- the real round-based range engine.** Tracks a single
    ``current_range`` (``turn/encounter.py CombatRange``, starting at
    ``SPELL_RANGE`` per [5.0]'s own "Encounters usually begin at spell
    range" -- see ``turn/encounter.py``'s own Phase 179 addendum for the
    full quoted rulebook text this models):

    - **``CAST`` never needs to close range** -- "spell range... allows
      only the use of spells" through "melee zone[:] only spells or
      hand-to-hand attacks" confirms spells are usable at every range.
      At ``MELEE_RANGE`` specifically, [5.0]'s own "[melee attacks]
      will always have precedence" is modeled as a real *disruption*
      check: the target (which has no Encounter Plan of its own -- this
      project's established one-directional-target scoping) gets one
      reactive Melee swing at the caster (``resolve_reactive_melee_
      swing()``) *before* the cast is even attempted. A landed hit rolls
      ``resolve_spell_disruption()`` against the actual damage dealt; a
      miss rolls ``resolve_spell_disruption_from_missed_attack()``'s own
      flat 30% instead ([5.1], corrected formula -- see ``turn/
      encounter.py``'s own Phase 292 addendum). A disrupted cast never
      reaches ``_resolve_personal_combat_cast()`` at all -- "the caster
      loses a turn" is modeled as the tactic being consumed with no
      effect, the same outcome a failed cast-chance roll already
      produces, so no new outcome branch is needed. Disruption is
      deliberately **not** checked at ``SPELL_RANGE``/``BOW_RANGE``
      (module docstring's own established scope: the target has no
      reciprocal Fire Arrow of its own modeled here).
    - **``SHOOT`` closes ``SPELL_RANGE`` -> ``BOW_RANGE`` first** (one
      free round, per the helper above), then fires atomically via the
      existing ``resolve_fire_arrow_duel()`` -- unchanged from before
      this phase, still a whole self-contained duel in one call, not
      stepped round-by-round. **At ``MELEE_RANGE``, ``SHOOT`` is
      ignored outright** ("In the melee zone, only spells or hand-to-
      hand attacks") -- the tactic is skipped with no effect, exactly
      like an already-unwired tactic.
    - **``MELEE`` closes all the way to ``MELEE_RANGE``** (up to two
      free rounds from ``SPELL_RANGE``), then fights via ``turn/
      encounter.py resolve_one_melee_round()``/``resolve_melee_duel()``.
      **Which of the two depends on whether it is this Encounter Plan's
      own last tactic**: if more tactics follow it in the list (the
      real shape a plan needs to genuinely interleave "swing this
      round, cast next round" -- the Marzials/Ablamor worked example's
      own "mutual Melee exchanges" interrupted by disrupted casts), only
      **one round** is fought (``resolve_one_melee_round()``) before
      falling through to whatever tactic comes next -- a decisive kill
      still ends the encounter immediately, but an undecided round lets
      a following ``CAST`` genuinely see ``current_range is MELEE_
      RANGE`` and trigger the disruption check above. If it is the
      *last* tactic (or the only one), the full atomic ``resolve_melee_
      duel()`` still runs to its own conclusion in one call, exactly as
      before this phase -- **every real caller and test today only ever
      orders ``MELEE`` last**, so this preserves 100% of existing RNG-
      consumption sequences unchanged; only a genuinely new plan shape
      (``MELEE`` followed by more tactics) exercises the new one-round
      path at all.
    - **An exhausted tactic list still defaults to Melee** (unchanged
      from before this phase), forcing ``current_range`` to
      ``MELEE_RANGE`` first via the same closing helper, then fighting
      the same atomic ``resolve_melee_duel()`` to its own conclusion --
      this still runs even when a preceding non-last ``MELEE`` tactic
      already stepped some rounds without a decisive winner, simply
      continuing from wherever hit points currently stand.

    **Phase 294 addendum -- a real Temper-setup gap, found while building
    the analogous (correct) engine in ``turn/search_execution.py``
    (Phase 293), fixed here.** ``apply_temper_melee_setup()`` (Furia/
    Intimidazione/Slancio/Schivare, Phase 284) is normally applied
    exactly once, internally, by ``resolve_melee_duel()`` itself -- but
    the non-last-``MELEE`` round-stepping branch never went through that
    function at all, so a caster's/target's own Temper effects silently
    never applied for that one specific plan shape (a ``MELEE`` tactic
    followed by more tactics). A new one-shot ``melee_setup_done`` flag
    now calls ``apply_temper_melee_setup()`` directly, exactly once,
    right before the *first* ``resolve_one_melee_round()`` call. Every
    real caller/test today only ever orders ``MELEE`` last, so this fix
    is inert for all of them -- it only changes behavior for the same
    genuinely new plan shape Phase 292's own docstring already flagged
    as the only thing exercising the one-round path at all.

    **Phase 297 correction -- the "guarded so it never also runs" claim
    above was wrong, a real bug found in a dedicated bug-hunt audit.**
    Both places this function still calls the atomic ``resolve_melee_
    duel()`` (the last-tactic path just below, and the exhausted-
    tactic-list fallback at the end of this function) called it
    unconditionally -- and ``resolve_melee_duel()`` itself always applies
    Temper setup internally. So a plan like ``[MELEE, TALK, MELEE]``
    (a non-last ``MELEE`` that sets ``melee_setup_done`` via round-
    stepping, followed by a *second* ``MELEE`` that happens to be the
    plan's own last tactic) really did double-apply -- confirmed live,
    not just read: a Cautious combatant's own defensive multiplier
    compounded 1.0 -> 0.9 -> 0.81 instead of the intended single 0.9,
    and a Berserk combatant's own bonus hit points could apply twice.
    Fixed by giving ``resolve_melee_duel()`` a new ``skip_temper_setup``
    parameter (``turn/encounter.py``'s own Phase 297 addendum) and
    passing ``skip_temper_setup=melee_setup_done`` at both call sites --
    inert whenever ``melee_setup_done`` is still ``False`` (the setup
    genuinely hasn't run yet, so the atomic path should still do it
    itself), and skips exactly the redundant second call otherwise.

    **Phase 305 addendum -- character-vs-character Steal [ST], rulebook
    [5.5], generalizing ``turn/search_execution.py _resolve_steal()``'s
    own monster-target case (Phase 239) to a leader target.** Quoted in
    full: "Il personaggio tenta di rubare il suo avversario, Re, Eroe o
    mostro che sia. Ci sono due possibilita': o ci riesce oppure viene
    scoperto. Se la tattica Steal riesce il personaggio puo' portar via
    oro o uno o piu' oggetti magici (sempre che siano presenti). La
    probabilita' base di riuscita e' del 15% piu' 15% per livello di
    abilita', ma si applicano le seguenti modifiche. 1) Se il ladro
    prende di mira un personaggio che e' alla guida di un esercito le sue
    probabilita' di riuscita sono dimezzate. 2) Se la vittima e' un Re,
    c'e' la possibilita' di sottrargli una certa quantita' di oro (dipende
    da quanto ha nella tesoreria in quel momento). Se il ladro fallisce
    nei suoi tentativi di furto non verra' necessariamente arrestato: le
    probabilita' di evitare la cattura sono in funzione del livello di
    abilita' del ladro. In caso di cattura le possibilita' sono tre: se
    il ladro e' un Eroe che ha provato a derubare un Re o un altro Eroe
    che comanda unita' militari, viene giustiziato; se il ladro e' un
    personaggio che ha tentato di derubare un mostro o un Eroe che non
    comanda unita' militari, si ha un combattimento individuale, a una
    distanza scelta a caso; se il ladro e' un Re che ha tentato di
    derubare un altro Re, perde meta' dell'oro della sua tesoreria come
    prezzo del riscatto (se non ha oro verra' giustiziato)."

    Reuses ``turn/encounter.py``'s own ``steal_success_chance()``/
    ``resolve_steal_attempt()``/``resolve_steal_evasion()`` (Phase 239)
    unchanged -- the base 15%+15%/level success formula, the target-
    leads-an-army halving, and the evasion-after-failure roll are all
    already sourced primitives with no leader-vs-monster assumption
    baked in.

    **Gold theft's own magnitude is still not modeled** -- ``turn/
    encounter.py``'s own Phase 239 addendum already confirmed this
    formula "confirmed absent" for the King-victim case specifically,
    noting "a future Challenge/Pursue-side Steal would still need it";
    this phase *is* that future consumer, and the text still gives no
    number to build against. Generalizing further: only a King's own
    ``KingdomState.treasury`` is a real gold pool in this project's
    model at all (an ordinary Hero holds no gold of his own), so gold
    theft stays unmodeled for every target, not just Kings.
    ``_apply_successful_theft()`` below models the other half of "oro o
    uno o piu' oggetti magici" instead -- item theft, which has both a
    clean mechanism (``GameState.transfer_item()``, Phase 140) and no
    magnitude ambiguity once "how many" is read as one (see that
    function's own docstring for why).

    **The three capture consequences, and one combination the text
    doesn't cover.** ``_resolve_steal_tactic()`` below implements all
    three sourced branches directly off ``LeaderState.is_king`` and
    ``target_leads_army``: Hero-thief-vs-(King-or-army-Hero) is executed;
    King-thief-vs-King pays half the thief's own kingdom treasury as
    ransom (or is executed if that treasury is already empty); anyone
    (Hero or King) caught targeting a monster or a non-army-commanding
    Hero is moved to a freshly-rolled random combat range ("a una
    distanza scelta a caso") for the encounter to continue from. **A King
    caught robbing an army-commanding Hero who isn't also a King matches
    none of the three literal branches** (the execution rule is scoped to
    a Hero thief, the ransom rule to a King *victim*) -- left genuinely
    unresolved (the thief is caught, nothing further happens) rather than
    borrowing an outcome from either neighboring branch on a guess.

    **Not addressed here**: [3.12]'s own English-only clause ("If the
    Steal tactic is used in such a restricted encounter, the chance of
    success is halved") describes a second, textually distinct halving
    condition (tied to whether the encounter plan also carries combat
    tactics/personal-combat spells, triggering the King/Hero acceptance
    restrictions) from the Italian [5.5] target-leads-an-army halving
    already wired above. Whether the two describe the same underlying
    condition from different angles, or would genuinely stack, isn't
    resolved by either source read literally -- flagged here rather than
    guessed at, the same "confirmed but unresolved" treatment this
    project already gives Mirror-Image's double-dissipation rule and
    Ice Suspension's item-seizure mechanic.

    **Not wired for Search's own monster-target case** -- ``turn/
    search_execution.py _resolve_steal()`` keeps its own, narrower
    implementation unchanged (a guardian monster is never a King, never
    commands an army, and never holds an ``ItemInstance`` in this
    project's model), so nothing here replaces it.

    **Phase 306 correction -- capture no longer atomically resolves a
    duel.** Phase 305's original "combat" branch called ``resolve_melee_
    duel()``/``resolve_fire_arrow_duel()`` directly, self-contained,
    exactly mirroring Search's own ``_resolve_steal()``. A real worked
    example, [11.3]'s own "ESEMPI DI PIANI D'INCONTRO", reads: "CA-IN,
    ST, FL, ME. Lanciare l'incantesimo invisibilita' e tentare di rubare.
    Se scoperti tentare di fuggire e, se nel caso non riuscisse, lanciarsi
    in mischia." ("Cast Invisibility and attempt to steal. If discovered,
    try to Flee, and if that doesn't work, engage in Melee.") -- getting
    caught is meant to hand control back to the plan's *own next tactic*
    (Flee, then Melee), not short-circuit straight into an atomic duel
    that skips over it. The fix: the STEAL branch now sets ``current_
    range`` outright to the freshly-rolled range (not merely advanced via
    ``_close_to()`` -- "a randomly chosen distance" is a fresh
    confrontation, not a continuation) and ``continue``s the walk, the
    same way a SHOOT/MELEE tactic already leaves ``current_range`` for
    whatever comes next. ``Maneuver.FLEE`` is still unwired in this
    module (a separate, already-documented gap, Phase 290's own
    addendum), so it's silently skipped exactly like any other unwired
    tactic -- but a following ``MELEE`` (as in this very example) now
    correctly picks up from the rolled range via the existing MELEE
    branch, and an exhausted list still falls through to the existing
    "defaults to Melee" tail if nothing follows at all. No test exercised
    the old atomic path with a following tactic, so this is a correction
    caught before it shipped a wrong default, not a regression fix.

    **A Steal-only plan (no Melee/Fire-Arrow/decodable-Cast alongside it)
    never reaches this function at all**, a narrower, separate,
    consciously-not-fixed gap: ``execute_challenge()``'s own ``not has_
    combat_intent(request)`` short-circuit (Phase 50) returns before ever
    calling this function, since [3.12]'s own text deliberately excludes
    Steal from "combat intent" (only Steal's own success *chance* is
    affected by whether the encounter also has combat intent, per that
    same [3.12] clause already flagged above as unaddressed -- Steal's
    ability to fire *at all* isn't gated on it). Both of [11.3]'s own
    worked examples always pair ``ST`` with a real combat tactic (``CA-
    FI``/``ME`` or ``CA-IN``/``ME``), which already sets ``has_combat_
    intent`` `True` and reaches this function correctly -- a Steal-only
    plan isn't attested in any available real data, the same "don't fix
    an unattested shape" discipline this project already applies
    elsewhere (e.g. Search's own confirmed single-FI-order rule).
    """

    current_range = CombatRange.SPELL_RANGE
    melee_setup_done = False
    # Phase 306: carried into every ``ChallengeCombatOutcome`` returned
    # below (not just a terminal STEAL branch) -- see that dataclass's own
    # Phase 306 addendum for why a non-terminal Steal outcome (success/
    # evaded/ransom/unresolved) still needs to reach the report layer even
    # when a later tactic decides the encounter's actual winner.
    steal_outcome: str | None = None
    steal_capture_range: CombatRange | None = None

    for index, tactic in enumerate(tactics):
        if tactic.maneuver is Maneuver.SHOOT:
            if current_range is CombatRange.MELEE_RANGE:
                continue  # [5.0]: only spells or Melee are usable in the melee zone
            current_range = _close_to(CombatRange.BOW_RANGE, current_range)
            result = resolve_fire_arrow_duel(caster, target, rng)
            if result.winner is not None:
                return ChallengeCombatOutcome(
                    winner=result.winner, steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
                )
            continue
        if tactic.maneuver is Maneuver.MELEE:
            current_range = _close_to(CombatRange.MELEE_RANGE, current_range)
            if index == len(tactics) - 1:
                result = resolve_melee_duel(caster, target, rng, skip_temper_setup=melee_setup_done)
                return ChallengeCombatOutcome(
                    winner=result.winner, steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
                )
            if not melee_setup_done:
                apply_temper_melee_setup(caster, target, rng)
                melee_setup_done = True
            round_outcome = resolve_one_melee_round(caster, target, rng)
            if round_outcome.result is not None:
                return ChallengeCombatOutcome(
                    winner=round_outcome.result.winner,
                    steal_outcome=steal_outcome,
                    steal_capture_range=steal_capture_range,
                )
            continue
        if tactic.maneuver is Maneuver.CAST:
            if current_range is CombatRange.MELEE_RANGE:
                # Phase 416: resolve_reactive_melee_swing() now returns a
                # ReactiveMeleeSwingResult (hit + damage) instead of a bare
                # int, for turn/search_execution.py's own narration needs
                # -- Challenge has no per-swing narration of its own
                # (ChallengeCombatOutcome carries no melee_swings field),
                # so only .damage is used here, unchanged from before.
                damage = resolve_reactive_melee_swing(target, caster, rng).damage
                if caster.hit_points <= 0:
                    return ChallengeCombatOutcome(
                        winner="b", steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
                    )
                disrupted = (
                    resolve_spell_disruption(damage, rng)
                    if damage > 0
                    else resolve_spell_disruption_from_missed_attack(rng)
                )
                if disrupted:
                    continue
            outcome = _resolve_personal_combat_cast(
                caster, caster_leader, target, target_leader, tactic, state, rng, is_first_tactic=(index == 0)
            )
            if outcome == "fled":
                return ChallengeCombatOutcome(
                    winner=None, fled=True, steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
                )
            if outcome in ("a", "b"):
                return ChallengeCombatOutcome(
                    winner=outcome, steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
                )
            bonus_winner = _consume_bonus_attacks(caster, target, rng)
            if bonus_winner is not None:
                return ChallengeCombatOutcome(
                    winner=bonus_winner, steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
                )
            continue
        if tactic.maneuver is Maneuver.STEAL:
            steal_outcome = _resolve_steal_tactic(caster_leader, target_leader, state, rng)
            if steal_outcome == "executed":
                return ChallengeCombatOutcome(
                    winner="b", steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
                )
            if steal_outcome == "combat":
                # Phase 306 correction: a real worked example ([11.3] "CA-IN,
                # ST, FL, ME") confirms getting caught doesn't atomically
                # resolve a duel on its own -- it moves the encounter to the
                # rolled-random range ("a una distanza scelta a caso") and
                # the plan's own *next* tactic decides what happens from
                # there (here: try to Flee, and if that fails, Melee), the
                # same way a SHOOT/MELEE tactic already leaves `current_
                # range` for whatever tactic follows it. Only jumping
                # straight to an atomic duel (Phase 305's original design)
                # would skip that following tactic entirely -- wrong per
                # this example. `current_range` is set outright, not just
                # advanced via `_close_to`, since "a randomly chosen
                # distance" describes a fresh confrontation, not a
                # continuation of wherever the encounter previously stood.
                current_range = steal_capture_range = rng.choice(
                    (CombatRange.SPELL_RANGE, CombatRange.BOW_RANGE, CombatRange.MELEE_RANGE)
                )
                continue
            continue  # success / evaded / ransom / unresolved -- plan continues
        # every other tactic is unwired -- skip it and keep walking
    result = resolve_melee_duel(caster, target, rng, skip_temper_setup=melee_setup_done)
    return ChallengeCombatOutcome(
        winner=result.winner, steal_outcome=steal_outcome, steal_capture_range=steal_capture_range
    )


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
    # Phase 306: copied straight from `ChallengeCombatOutcome` when the
    # plan's own tactics included a STEAL -- lets `report/turn_report.py
    # describe_steal()` narrate the Steal sub-event even when the
    # encounter's overall winner (if any) was decided by a later tactic.
    steal_outcome: str | None = None
    steal_capture_range: CombatRange | None = None
    # Phase 313: item ids transferred from the loser to the winner via
    # `turn/encounter.py loot_defeated_leader()` -- [5.9]'s "looting a
    # vanquished foe's treasure, magic items changing hands". Empty (not
    # None) when `loser_killed` is True but the loser owned nothing; stays
    # `[]` when there's no death at all.
    looted_item_ids: list[int] = field(default_factory=list)


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
        return ChallengeExecutionResult(
            accepted=True,
            combat_occurred=True,
            fled=True,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
        )
    if combat_result.winner is None:
        return ChallengeExecutionResult(
            accepted=True,
            combat_occurred=True,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
        )

    winner_id, loser_id = (
        (challenger_leader_id, request.target_character_id)
        if combat_result.winner == "a"
        else (request.target_character_id, challenger_leader_id)
    )
    state.remove_leader(loser_id)
    looted_items = loot_defeated_leader(state, winner_id=winner_id, loser_id=loser_id)

    return ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=winner_id,
        loser_leader_id=loser_id,
        loser_killed=True,
        looted_item_ids=[item.item_id for item in looted_items],
        steal_outcome=combat_result.steal_outcome,
        steal_capture_range=combat_result.steal_capture_range,
    )
