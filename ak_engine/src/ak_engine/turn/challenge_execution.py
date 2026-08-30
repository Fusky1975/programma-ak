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
entirely. Cast's own personal-combat-spell nuance *is* checked (Phase
290 addendum below, once Search's own spell-effect system existed to
classify it). Steal is deliberately never checked here -- not because
it's unmodeled (Phase 305 built it), but because [3.12]'s own text
names "combat tactics or personal combat spells" and Steal is neither;
see this function's own ``has_combat_intent()`` docstring and the
Phase 305 addendum's own "one combination the [5.5] text doesn't
cover" paragraph below for the full sourcing (**Phase 526 addendum**:
corrects this paragraph's own earlier "Steal is a separate, unmodeled
tactic" claim, stale since Phase 305).

**Unlike Duel's own special case ([7.1], Phase 49), a Challenge loser
*is* killed**: personal combat's generic rule ([5.0]: "until one
combatant is killed") applies here in full -- Duel's "only demoralizes
armies, never kills the commander" rule is specific to [7.1] and
doesn't generalize to every Encounter. A decisive loser is removed from
``state`` via ``GameState.remove_leader()``, the same mechanism Cast's
own Kill_Enemy execution already uses (Phase 29).

**Wired into ``plan_dispatch.py``'s CHALLENGE dispatch since Phase 54**
(this paragraph's own earlier "stays decode-only" claim predates that
wiring, stale since): ``_dispatch_challenge()`` calls ``execute_
challenge()`` directly for every real CHALLENGE phase. ``mutual_
encounter`` still defaults to ``False`` at that single-leader dispatch
layer (a single leader's own dispatch has no visibility into whether
the target also ordered a Challenge back this same phase) -- Phase 56
closes that separately, one level up: ``turn/turn_processor.py
_dispatch_mutual_encounter()`` detects a real same-phase reciprocal
Challenge/Pursue pair before either leader is dispatched individually,
and resolves the pair as one shared encounter with ``mutual_encounter=
True``.

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
  always ``MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT`` (Medium
  Human, corrected from High Human by Phase 470 -- see that constant's
  own docstring in ``turn/encounter.py``) plus the caster's own Sage/
  Illusion-driven bonus -- the same branch Search already uses for its
  own leader-target case.
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
simplification at all -- Charm's "guaranteed Flee" (Phase 529 addendum:
unless the target's own Kingdom holds Discovery.ANALYTICAL_PSYCHOLOGY,
in which case the spell is simply ineffective -- see ``_resolve_
personal_combat_cast``'s own Phase 529 comment) and Words of Healing's
"heal to ``CHARACTER_HIT_POINTS``" already only ever reference the
caster.

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

**Phase 457 -- Add_Experience's own Thief call site.** ``AKGEN_reverse_
engineering_report (2).md`` SS3.3's own table gives Thief a fixed,
fully-sourced base value (15, unlike the "variable"/"contextual" entries
every other ability's own row carries) for "furto e azioni avanzate di
banditry/piracy" (theft and advanced banditry/piracy actions). Two real,
non-Practice-triggered "qualifying theft event" moments already exist in
this project, both already sitting next to the identical Phase 442
``MeritTally.successful_thefts`` credit the dossier's own Prince of
Thieves formula names as "two separate success paths" -- this module's
own ``_apply_successful_theft()`` (character-vs-character Steal) and
``turn/search_execution.py _resolve_steal()``'s own success branch
(guarded-feature Steal) -- so both now also call ``turn/experience.py
add_experience(thief, Ability.THIEF, 15, rng)``. **Not** wired here:
Practice's own Banditry/Piracy side effects (``turn/practice_execution.
py``'s own SS2.5 addendum) -- those fire only as a byproduct of a ``PR
TH`` session, whose own skill growth is already fully accounted for by
Practice's own credit mechanism (SS2's general rule); wiring Add_
Experience there too would double-credit the same session. Only the two
genuine Steal-tactic successes above are events *Practice never already
covers*, and are read here as the real, distinct trigger SS3.3's own
"furto" half of that table row refers to -- a documented interpretation
of a summary description, not a literal quote of the compiled call site
(the same category of judgment call this project's own "eligibility
lives in the formula, not the loop" and similar unsourced-but-documented
choices already fall into elsewhere).

**Phase 692 addendum**: Banditry/Piracy's own real gold-looting effect
(``turn/practice_execution.py _maybe_raid_as_bandit()``) is now wired,
but it credits ``Ability.SPY`` experience (Banditry/Piracy's own real
text: "This action also counts as a normal 'Spy' action in all
respects"), not ``Ability.THIEF`` -- a separate counter from the one
this addendum's own "don't double-credit THIEF" reasoning above is
about, so there is no conflict between the two.

**Phase 697 -- `AdvancedAbility.SPY_BRAINWASH`.** "When the spy uses
the Talk tactic on any hero, that character will move one step closer
in alignment to the Spy's alignment. Not usable on Kings." Wired the
same way, at the same two ``has_talk_tactic`` call sites, as
``_apply_bravest_talk_inspiration()`` right below the Phase 103 note
above -- see ``_apply_spy_brainwash_alignment_shift()``'s own docstring.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.monster import (
    HAND_OF_DEATH_ANTI_HOLY_MONSTERS,
    MONSTER_COMBAT_STATS,
    MONSTER_NAMES,
    SPIRITWRACK_UNDEAD_MONSTERS,
    MonsterSpeed,
    roll_gate_demon_type,
)
from ak_engine.models.office import Office
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.models.temper import raise_temper_one_level
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest
from ak_engine.turn.discovery_effects import (
    arcane_valor_hit_points_bonus,
    effective_skill_level,
    equipped_combat_weapon,
    holder_is_immune_to_spell,
    holds_bow_of_elven_kings,
)
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_DAMAGE_RANGE,
    INVISIBILITY_HIT_CHANCE_MULTIPLIER,
    MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT,
    STEAL_THIEF_MASTERY_ABILITIES,
    PERSONAL_COMBAT_SPELL_ABILITY,
    PERSONAL_COMBAT_SPELL_SELF_ONLY,
    Combatant,
    CombatRange,
    EncounterCombatResult,
    FireArrowShot,
    MeleeSwing,
    apply_temper_melee_setup,
    archery_free_attack_bonus,
    blocks_cast_and_archery,
    bow_of_elven_kings_archery_damage_bonus,
    bow_of_elven_kings_archery_hit_multiplier,
    control_undead_anti_holy_resist_chance,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    weapon_melee_damage_bonus,
    weapon_offensive_hit_multiplier,
    control_undead_failure_new_hit_points,
    weapon_defensive_hit_multiplier,
    holy_symbol_hit_chance,
    ice_suspension_is_frozen,
    ice_suspension_slowed_bonus_rounds,
    illusory_hero_alignments_are_implacably_hostile,
    loot_defeated_leader,
    mirror_image_leader_disbelief_bonus,
    resolve_augur_combat,
    weapon_grants_auto_invisibility,
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
    resolve_steal_character_item_transfer,
    resolve_steal_evasion,
    roll_fireball_damage,
    roll_holy_symbol_undead_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spiritwrack_melee_damage_reduction,
    steal_ransom_amount,
    words_of_healing_heal,
)
from ak_engine.turn.experience import add_experience
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.sep_decode import target_uses_special_encounter_plan

_COMBAT_MANEUVERS = frozenset({Maneuver.MELEE, Maneuver.SHOOT})

# Phase 290: same secret-spell skill-5+ gate `turn/search_execution.py`
# uses for Illusory Hero/Words of Healing, duplicated per this project's
# own "same shared fact, independent citation per consumer" convention.
ILLUS_HERO_KNOWN_ABILITY_LEVEL = 5
WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL = 5

# Office.NECRO_MAGE's own Imp familiar (Phase 666, `models/office.py
# OFFICE_TITLE_DESCRIPTION`): "25% magic resistance, meaning that 25% of
# the spells cast against <2 will fail."
NECROMANCER_MAGE_SPELL_RESIST_CHANCE = 0.25


def _necromancer_mage_resists_spell(state: GameState, target_leader_id: int, rng: random.Random) -> bool:
    """Same single checkpoint `holder_is_immune_to_spell()` already
    established (post-success, pre-effect, excluding `PERSONAL_COMBAT_
    SPELL_SELF_ONLY` and a `None` target) -- the caller checks the
    Anti-Magic Amulet first (a static, rng-free fact) and only calls
    this when it doesn't already explain the miss, so a non-titleholder
    never consumes a roll (every pre-Phase-666 caller/test unaffected).
    Duplicated in `turn/search_execution.py`, this project's own
    established "small per-consumer lookup" convention (see this
    module's own `_leader_combatant()` docstring).
    """

    holder = resolve_office_holder(state, Office.NECRO_MAGE)
    if holder is None or holder.leader_id != target_leader_id:
        return False
    return rng.random() < NECROMANCER_MAGE_SPELL_RESIST_CHANCE


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

    **Steal isn't checked here, deliberately -- not because it's
    unmodeled** (``Maneuver.STEAL`` has been a real, wired tactic since
    Phase 305), **but because [3.12]'s own English text scopes this
    check to "combat tactics or personal combat spells," and Steal is
    neither.** ``turn/challenge_execution.py``'s own module docstring
    (Phase 305 addendum, "one combination the [5.5] text doesn't cover")
    already establishes this reading in detail: Steal's ability to fire
    at all is never gated on ``has_combat_intent``, only its own success
    *chance* is (per [3.12]'s separate halving clause, itself still
    unaddressed -- see that same addendum). **Phase 526 addendum**:
    this paragraph itself used to read "a separate, still-unmodeled
    tactic," which stopped being true at Phase 305 -- corrected here
    rather than silently rewritten, matching this project's own
    "correct via addendum" convention.
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
    has_spy_assassinate: bool = False,
) -> bool:
    """Rulebook [3.12]'s King/Hero acceptance decision tree -- see module docstring
    for the full quoted text this implements branch-for-branch.

    Phase 698 -- `AdvancedAbility.SPY_ASSASSINATE`'s own real
    description: "The spy can encounter kings and army leaders even if
    he has an attacking encounter plan. Also, King characters can now
    encounter other characters freely, without being avoided half the
    time." Read as one unified override -- whoever holds this ability
    (a Spy targeting a King/army-leader, or a King challenger who'd
    otherwise be evaded half the time) always gets an accepted
    encounter, bypassing every restriction below unconditionally. The
    "attacking encounter plan" clause is descriptive context for why
    this override matters (this function's own `target_leads_army`
    check has no separate "was the plan aggressive" input to begin
    with), not a fourth, narrower condition -- the two named benefits
    unify cleanly into one early return.
    """

    if has_spy_assassinate:
        return True
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
        target_is_undead = target_leader is not None and target_leader.alignment is Alignment.UNDEAD
        # Phase 502: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS -- "'Control
        # Undead' will work against anti-holy creatures, in addition to
        # affecting the Undead (but... there is a percentage chance that
        # they will resist the spell, equal to half their current hit
        # points)." `control_undead_target_is_anti_holy_only` records
        # which eligibility branch let the target through, so the
        # resist roll below only applies to a genuinely anti-holy (not
        # also Undead) target -- an ordinary Undead one never resists.
        control_undead_target_is_anti_holy_only = (
            not target_is_undead
            and target_leader is not None
            and target_leader.alignment is Alignment.ANTI_HOLY
            and AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS in caster_leader.advanced_abilities
        )
        if not (target_is_undead or control_undead_target_is_anti_holy_only):
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

    # Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- a target
    # holding the Anti-Magic Amulet that personally blocks this exact
    # spell (models/treasure.py AMULET_BLOCKED_SPELLS -- e.g. Fireball is
    # blocked, but Ice Suspend, also Elemental, is not) negates it
    # outright, checked once here (before every per-spell branch,
    # including Control Undead's own early-return shape) rather than
    # duplicated per branch. Excludes the 3 Personal-Combat spells whose
    # entire effect is self-only and never reads or mutates `target` at
    # all (Augur_Combat's silent flee-simulation, Invisibility's own
    # defensive buff, Words of Healing) -- an amulet that protects its
    # wearer "from spells" has nothing to negate for a spell that was
    # never cast *at* them in the first place.
    if succeeded and spell not in PERSONAL_COMBAT_SPELL_SELF_ONLY and target_leader is not None:
        if holder_is_immune_to_spell(state, target_leader.leader_id, spell) or _necromancer_mage_resists_spell(
            state, target_leader.leader_id, rng
        ):
            return None

    if spell is Spell.CONTROL_UNDEAD:
        if succeeded:
            if control_undead_target_is_anti_holy_only and rng.random() < control_undead_anti_holy_resist_chance(
                target.hit_points
            ):
                return None
            return "a"
        target.hit_points = control_undead_failure_new_hit_points(target.hit_points, rng)
        return None

    if not succeeded:
        return None

    if spell is Spell.CHARM:
        # Phase 529: AKGEN_reverse_engineering_report (3).md SS8.3/SS10.1
        # (AK.OVR:0x18237-0x18251) -- Counter_Science(target, Charm) is
        # checked *before* Enhanced Charm's item transfer and the flee
        # itself. When the target's own Kingdom holds Discovery.
        # ANALYTICAL_PSYCHOLOGY, the spell is simply ineffective in
        # Personal Combat -- no flee, no item transfer, combat continues.
        # This genuinely diverges from the Action-Cast form (which still
        # succeeds and only reverts at end of turn) -- SS8.3 is explicit
        # the two branches differ: "Analytical Psychology contro un
        # Combat Charm equivale a nessun effetto operativo". A target
        # with no recorded Kingdom reads as not immune, the same
        # permissive-missing-data convention this function already uses
        # elsewhere (e.g. an unset alignment above).
        target_is_immune = (
            target_leader is not None
            and target_leader.kingdom_id is not None
            and Discovery.ANALYTICAL_PSYCHOLOGY in state.kingdoms[target_leader.kingdom_id].discoveries
        )
        if target_is_immune:
            return None
        # SS9.2 (AK.OVR:0x18254-0x182EE) -- Enhanced Charm's item
        # transfer applies to Personal-Combat Charm too, not only the
        # Action-Cast form (``cast_execution.py._execute_charm``'s own
        # Phase 499 addendum) -- same lowest-``item_id`` deterministic
        # pick, since the source names no selection rule here either.
        if (
            target_leader is not None
            and AdvancedAbility.ENHANCED_CHARM in caster_leader.advanced_abilities
        ):
            target_items = state.items_held_by(target_leader.leader_id)
            if target_items:
                state.transfer_item(target_items[0].item_id, caster_leader.leader_id)
        return "fled"

    if spell is Spell.HOLY_SYMBOL:
        # Phase 497: AdvancedAbility.ENHANCED_HOLY_SYMBOL -- "the Holy
        # Symbol spell now has the same effect against opponents who
        # have an Evil alignment as it does against Undead creatures."
        # Extending target_is_undead_or_anti_holy itself (rather than a
        # separate flag) widens both downstream effects it drives --
        # the higher hit-chance-reduction rate and the bonus damage roll.
        target_is_undead_or_anti_holy = target_leader is not None and (
            target_leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
            or (
                target_leader.alignment is Alignment.EVIL
                and AdvancedAbility.ENHANCED_HOLY_SYMBOL in caster_leader.advanced_abilities
            )
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
        # Phase 496: AdvancedAbility.WITCHSIGHT_TALENT -- "whenever an
        # opponent turns Invisible in combat, the Necromancer can still
        # see his opponent and is unaffected by the spell." The
        # Necromancer here is whoever is fighting the invisible caster,
        # i.e. this dispatcher's own target_leader, not the caster.
        opponent_has_witchsight = (
            target_leader is not None and AdvancedAbility.WITCHSIGHT_TALENT in target_leader.advanced_abilities
        )
        # Phase 532: same carve-out for a target_leader holding the
        # Crystal of True Seeing (models/treasure.py AMULET_BLOCKED_
        # SPELLS) -- "sees through" Invisibility the same way Witchsight
        # does, via the shared holder_is_immune_to_spell() primitive.
        opponent_sees_through_illusion = target_leader is not None and holder_is_immune_to_spell(
            state, target_leader.leader_id, spell
        )
        if not opponent_has_witchsight and not opponent_sees_through_illusion:
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
        # Phase 500: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS -- "'Hand
        # of Death' now works against all creatures." A leader-vs-leader
        # target is never Mechanical (no such alignment applies to a
        # LeaderState), so overriding the Undead/Anti-Holy check to
        # False is the whole widening here.
        if AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS in caster_leader.advanced_abilities:
            target_is_immune = False
        else:
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
        # Phase 494: same wiring as turn/search_execution.py's own Mirror-
        # Image branch -- see that call site's comment. Here both sides
        # can be a real leader (or None for a Duel-side garrison
        # commander, which can never hold an Advanced Ability), so each
        # is checked against its own LeaderState directly.
        duel_result = resolve_mirror_image_duel(
            caster,
            target,
            opponent_tier,
            level,
            rng,
            opponent_disbelief_bonus=opponent_disbelief_bonus,
            opponent_has_detect_illusions=(
                target_leader is not None and AdvancedAbility.DETECT_ILLUSIONS_TALENT in target_leader.advanced_abilities
            ),
            caster_has_detect_illusions=AdvancedAbility.DETECT_ILLUSIONS_TALENT in caster_leader.advanced_abilities,
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
        # Phase 494: same Detect Illusions wiring as the Mirror-Image branch above.
        duel_result = resolve_illusory_hero_duel(
            caster,
            target,
            hero_combatant,
            opponent_tier,
            level,
            rng,
            opponent_disbelief_bonus=opponent_disbelief_bonus,
            opponent_has_detect_illusions=(
                target_leader is not None and AdvancedAbility.DETECT_ILLUSIONS_TALENT in target_leader.advanced_abilities
            ),
            caster_has_detect_illusions=AdvancedAbility.DETECT_ILLUSIONS_TALENT in caster_leader.advanced_abilities,
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
            is_undead_or_anti_holy=demon_species in (HAND_OF_DEATH_ANTI_HOLY_MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS),
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
    own ``_consume_bonus_attacks()``). ``attacker``/``defender`` are
    generic, caller-supplied roles (not hardcoded to this module's own
    outer ``caster``/``target`` convention) -- Phase 674's own ``_
    resolve_target_cast()`` calls this with the target playing
    ``attacker`` when *its* own Cast granted the bonus, flipping the
    ``"a"`` result back to the outer convention itself.
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


def _apply_successful_theft(state: GameState, thief: LeaderState, victim: LeaderState, rng: random.Random) -> None:
    """The theft's own tangible effect -- Phase 305, superseded by
    Phase 506's own full item-scan-with-decay (``turn/encounter.py``'s
    own Phase 506 addendum, ``steal_character_item_transfer_chance()``):
    the victim's own eligible items are scanned in a randomly-shuffled
    order, each independently rolled against a threshold that starts at
    75% and is halved (integer right-shift) after every item *actually
    transferred* -- a hidden item does not itself halve the threshold,
    only a successful transfer does. Gold theft stays unmodeled (see
    module docstring's own Phase 305 addendum).

    **Phase 442**: also credits ``MeritTally.successful_thefts`` -- the
    other of the real compiled formula's own "two separate success paths
    that award the [Prince of Thieves] point" (`turn/merit_points.py
    thiefprince_merit_points()`'s own Phase 369 addendum), sibling to
    `turn/search_execution.py _resolve_steal()`'s own credit for a
    guarded-feature Steal. This one fires on every real theft ["success"]
    outcome, regardless of whether the victim held an item to actually
    take -- the rulebook's own "+1 per successful theft result" reads as
    "the Steal attempt itself succeeded," not "and something was
    physically stolen," matching the unconditional gold-or-item wording
    that already treats an empty-handed success as still a success.

    **Phase 457**: also awards the thief's own real ``Add_Experience``
    credit (`turn/experience.py`, `AKGEN_reverse_engineering_report
    (2).md` SS3.3's own Thief row -- base 15, "evento di furto
    qualificante"). See module docstring's own Phase 457 addendum for
    why this specific success branch (not Practice's own Banditry/
    Piracy side effects) is the real, non-Practice-triggered "qualifying
    theft event" this base-15 call site refers to.
    """

    thief.merit_tally.successful_thefts += 1
    items = list(state.items_held_by(victim.leader_id))
    # A manual Fisher-Yates over rng.random() rather than rng.shuffle():
    # shuffle() draws through _randbelow()/getrandbits() instead of
    # random(), which every other roll in this project (and the test
    # suite's own ScriptedRandom) doesn't script -- see this project's
    # standing RNG convention of only ever consuming .random()/.choice().
    for i in range(len(items) - 1, 0, -1):
        j = int(rng.random() * (i + 1))
        items[i], items[j] = items[j], items[i]
    items_already_stolen = 0
    for item in items:
        if resolve_steal_character_item_transfer(items_already_stolen, rng):
            state.transfer_item(item.item_id, thief.leader_id)
            items_already_stolen += 1
    add_experience(thief, Ability.THIEF, 15, rng)


def _resolve_steal_tactic(
    caster_leader: LeaderState | None,
    caster: Combatant,
    target_leader: LeaderState | None,
    state: GameState,
    rng: random.Random,
) -> str:
    """Steal [ST], rulebook [5.5] -- Phase 305, superseded by Phase 506
    with the real disassembly-sourced success/evasion formulas (see
    ``turn/encounter.py``'s own Phase 506 addendum) and a ransom-formula
    fix. See module docstring's own Phase 305 addendum for the full
    quoted rulebook text and the reasoning behind every branch below.

    Returns ``"success"`` (theft applied, plan continues), ``"evaded"``
    (failed but not caught, plan continues), ``"executed"`` (thief
    killed outright, no combat), ``"ransom"`` (King-thief captured by a
    King or an army-commanding Hero, nobody dies -- Phase 526 extended
    this beyond King-vs-King specifically, see module docstring's own
    Phase 526 addendum), ``"combat"`` (caller must resolve a forced
    personal-combat encounter at a freshly-rolled range), or
    ``"unresolved"`` (a garrison commander with no ``LeaderState``,
    below -- the one remaining case no sourced branch covers).

    A garrison commander (``caster_leader``/``target_leader`` is
    ``None``, Phase 291's own Duel reuse) can neither attempt nor be a
    Steal target -- no ``LeaderState`` exists to read a Thief skill,
    royal status, or army command from.
    """

    if caster_leader is None or target_leader is None:
        return "unresolved"

    level = effective_skill_level(state, caster_leader, Ability.THIEF)
    target_leads_army = bool(state.armies_commanded_by(target_leader.leader_id))
    target_leads_army_or_is_king = target_leader.is_king or target_leads_army
    has_thief_mastery = bool(caster_leader.advanced_abilities & STEAL_THIEF_MASTERY_ABILITIES)
    has_enhanced_invisibility = AdvancedAbility.ENHANCED_INVISIBILITY in caster_leader.advanced_abilities
    if resolve_steal_attempt(
        level,
        rng,
        has_thief_mastery=has_thief_mastery,
        is_invisible=caster.is_invisible,
        has_enhanced_invisibility=has_enhanced_invisibility,
        target_leads_army_or_is_king=target_leads_army_or_is_king,
    ):
        _apply_successful_theft(state, caster_leader, target_leader, rng)
        return "success"
    if resolve_steal_evasion(level, rng):
        return "evaded"

    if not target_leads_army_or_is_king:
        return "combat"
    if not caster_leader.is_king:
        return "executed"
    # Phase 526: AKGEN_reverse_engineering_report (3).md SS42's own capture
    # table/pseudocode pays ransom to "LKing(victim)" whenever the victim
    # is king_or_army_leader -- no separate branch for a King thief caught
    # by a King versus by a non-King army-commanding Hero. See module
    # docstring's own Phase 526 addendum for the full sourcing.
    thief_kingdom = state.kingdoms.get(caster_leader.kingdom_id) if caster_leader.kingdom_id is not None else None
    if thief_kingdom is None or thief_kingdom.treasury <= 0:
        return "executed"
    ransom = steal_ransom_amount(thief_kingdom.treasury)
    thief_kingdom.treasury -= ransom
    victim_kingdom = state.kingdoms.get(target_leader.kingdom_id) if target_leader.kingdom_id is not None else None
    if victim_kingdom is not None:
        victim_kingdom.treasury += ransom
    return "ransom"


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
    # Phase 417: per-shot/per-swing combat detail, mirroring `turn/
    # search_execution.py SearchExecutionResult`'s own `fire_arrow_shots`/
    # `melee_swings` fields (Phase 175/415/416) -- accumulated across
    # every real combat call site in `resolve_challenge_combat()` below,
    # not just whichever one happened to be decisive, so `report/
    # turn_report.py` can narrate the whole encounter, not only its
    # final blow.
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    melee_swings: tuple[MeleeSwing, ...] = ()


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
    *,
    target_tactics: list[SearchTactic] | None = None,
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

    **The three capture consequences, and one combination the [5.5] text
    doesn't cover.** ``_resolve_steal_tactic()`` below implements all
    three sourced branches directly off ``LeaderState.is_king`` and
    ``target_leads_army``: Hero-thief-vs-(King-or-army-Hero) is executed;
    King-thief-vs-King pays half the thief's own kingdom treasury as
    ransom (or is executed if that treasury is already empty); anyone
    (Hero or King) caught targeting a monster or a non-army-commanding
    Hero is moved to a freshly-rolled random combat range ("a una
    distanza scelta a caso") for the encounter to continue from. **A King
    caught robbing an army-commanding Hero who isn't also a King matched
    none of the three literal [5.5] branches** (the execution rule is
    scoped to a Hero thief, the ransom rule to a King *victim*) -- left
    genuinely unresolved (the thief is caught, nothing further happens)
    rather than borrowing an outcome from either neighboring branch on a
    guess.

    **Phase 526 addendum -- the dossier resolves this exact combination.**
    ``AKGEN_reverse_engineering_report (3).md`` SS42 ("Se STEAL fallisce")
    gives the real compiled capture table and pseudocode, disassembled
    from `AK.OVR:0x1AC8D-0x1AF99`. Its own capture table has a row this
    [5.5] text alone doesn't: "Re con tesoreria >0 | Eroe che conduce un
    esercito | stesso riscatto al Regno dell'Eroe" (a King thief with
    treasury > 0, caught by an army-commanding Hero, pays the very same
    ransom to the Hero's own Kingdom) and "Re con tesoreria =0 | Re/Eroe
    con esercito | esecuzione e confisca" (empty treasury -- executed,
    same as the King-vs-King case). The pseudocode makes this explicit --
    the real branch condition is only `IsKing(thief)` and `victim_is_
    king_or_army_leader(victim)`, paying ransom to `LKing(victim)` (the
    King of the victim's own Kingdom) unconditionally, with **no separate
    check for whether the victim personally is that King** -- a King
    thief and an army-commanding-Hero victim were never a genuinely
    unaddressed combination in the real engine, only in the [5.5] rulebook
    prose alone. ``_resolve_steal_tactic()`` below now merges the two
    branches: any King-thief capture (`target_leads_army_or_is_king`)
    pays ransom to the victim's own Kingdom treasury (already how this
    project models "the Hero's own Kingdom", since only ``KingdomState.
    treasury`` is a real gold pool here) or is executed if the thief's own
    treasury is already empty, regardless of whether the victim is
    personally the King or an army-commanding Hero. ``"unresolved"`` is
    now reserved solely for the pre-existing garrison-commander case (no
    ``LeaderState`` to read from at all), a structurally different,
    still-genuinely-unaddressed situation.

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

    **Phase 674 -- `target_tactics` (rulebook [5.10]'s own "used in
    every Encounter solicited by another character," for a target who
    commands no armies).** `None` (every pre-Phase-674 caller,
    including `turn/battle_orchestrator.py`'s own Duel reuse, which
    deliberately keeps the one-directional behavior this phase doesn't
    touch -- see `turn/sep_decode.py target_uses_special_encounter_
    plan()`) reproduces every existing behavior above byte-for-byte.
    When given, the target gets the exact same kind of mid-fight `CAST`-
    timing agency `turn/search_execution.py`'s own monster-plan engine
    already gives a Search guardian (Phase 293) -- a tactic cursor
    peeked/advanced via `_peek_target_cast()`/`_advance_target_tactic()`
    below, consulted by the `MELEE` branch (now `_resolve_melee_round()`)
    and the `CAST` branch. Deliberately NOT given: `Maneuver.FLEE`
    agency (unwired for *either* side in this module already, a
    separate, pre-existing gap -- see the STEAL addendum above) and any
    "does the target want to Shoot" gate (`resolve_fire_arrow_duel()`
    is already a fully mutual exchange in one call, regardless of
    either side's own plan).
    """

    current_range = CombatRange.SPELL_RANGE
    melee_setup_done = False
    target_tactic_index = 0
    # Phase 306: carried into every ``ChallengeCombatOutcome`` returned
    # below (not just a terminal STEAL branch) -- see that dataclass's own
    # Phase 306 addendum for why a non-terminal Steal outcome (success/
    # evaded/ransom/unresolved) still needs to reach the report layer even
    # when a later tactic decides the encounter's actual winner.
    steal_outcome: str | None = None
    steal_capture_range: CombatRange | None = None
    # Phase 417: accumulated across every real combat call site below,
    # regardless of whether that particular call ended the encounter --
    # mirrors `turn/search_execution.py`'s own `fire_arrow_shots`/
    # `melee_swings` nonlocal-accumulator pattern (Phase 175/415), just
    # as plain locals here since this function has no nested closures.
    fire_arrow_shots: list[FireArrowShot] = []
    melee_swings: list[MeleeSwing] = []

    def _outcome(
        *, winner: str | None = None, fled: bool = False
    ) -> ChallengeCombatOutcome:
        return ChallengeCombatOutcome(
            winner=winner,
            fled=fled,
            steal_outcome=steal_outcome,
            steal_capture_range=steal_capture_range,
            fire_arrow_shots=tuple(fire_arrow_shots),
            melee_swings=tuple(melee_swings),
        )

    def _peek_target_cast() -> SearchTactic | None:
        """Phase 674 -- mirrors `turn/search_execution.py _peek_monster_
        action()` exactly, just walking the target's own real
        `target_tactics` instead of a monster's canned plan: the next
        `CAST` tactic from `target_tactic_index` onward, skipping any
        `SHOOT` entry (Fire Arrow is already resolved bidirectionally in
        one call whenever the *caster's* own plan orders it -- see the
        docstring above), or `None` once the target's own plan calls for
        `MELEE` or has run out.
        """

        nonlocal target_tactic_index
        plan = target_tactics or ()
        while target_tactic_index < len(plan):
            current = plan[target_tactic_index]
            if current.maneuver is Maneuver.SHOOT:
                target_tactic_index += 1
                continue
            if current.maneuver is Maneuver.MELEE:
                return None
            if current.maneuver is Maneuver.CAST:
                return current
            target_tactic_index += 1  # unwired for the target's own side too -- skip defensively
        return None

    def _advance_target_tactic() -> None:
        nonlocal target_tactic_index
        if target_tactics is not None and target_tactic_index < len(target_tactics):
            target_tactic_index += 1

    def _target_has_more_casts_pending() -> bool:
        return any(t.maneuver is Maneuver.CAST for t in (target_tactics or ())[target_tactic_index:])

    def _resolve_target_cast(tactic: SearchTactic, *, is_first: bool) -> str | None:
        """Resolves the target's own queued `CAST`, roles swapped (the
        target plays `_resolve_personal_combat_cast()`'s own `caster`
        role here) -- flips the returned `"a"/"b"` back to this
        function's own outer `"a"=caster,"b"=target` convention.
        """

        outcome = _resolve_personal_combat_cast(
            target, target_leader, caster, caster_leader, tactic, state, rng, is_first_tactic=is_first
        )
        if outcome == "fled":
            return "fled"
        if outcome == "a":
            return "b"
        if outcome == "b":
            return "a"
        bonus_winner = _consume_bonus_attacks(target, caster, rng)
        return "b" if bonus_winner == "a" else None

    def _resolve_melee_round(*, is_last_tactic: bool) -> tuple[bool, str | None]:
        """One round of Melee at `MELEE_RANGE`, consulting the target's
        own peeked Cast -- mirrors `turn/search_execution.py _resolve_
        melee_range_round()`'s own Melee-vs-Melee/Melee-vs-Cast
        branches. Returns `(encounter_over, outcome)`: `outcome` is
        `"a"`/`"b"`/`"fled"`/`None`; `encounter_over` is `True` whenever
        nothing more should be walked -- including an atomic duel's own
        genuine draw (`outcome=None` there still means "no winner," not
        "round undecided, keep walking," unlike the round-stepped
        branch's own `None`, so this can't be collapsed into a single
        sentinel the way a first draft of this function tried).
        """

        nonlocal melee_setup_done
        target_cast = _peek_target_cast()
        if target_cast is None:
            if is_last_tactic and not _target_has_more_casts_pending():
                result = resolve_melee_duel(caster, target, rng, skip_temper_setup=melee_setup_done)
                melee_swings.extend(result.melee_swings)
                return True, result.winner
            if not melee_setup_done:
                apply_temper_melee_setup(caster, target, rng)
                melee_setup_done = True
            round_outcome = resolve_one_melee_round(caster, target, rng)
            melee_swings.extend(round_outcome.swings)
            # Phase 674: this Melee "entry" in the target's own plan (if
            # its current one really is Melee, not just an exhausted/
            # None plan) has now been "used" for this round -- advance
            # past it so a later Cast further down its own plan is
            # eventually reached, mirroring search_execution.py's own
            # identical `_advance_monster_tactic()` call here exactly
            # (otherwise the peek would land on this same entry forever).
            _advance_target_tactic()
            if round_outcome.result is not None:
                return True, round_outcome.result.winner
            return False, None
        # Phase 674: mirrors search_execution.py's own "Melee vs Cast"
        # branch -- [5.1]'s own melee-precedence rule still applies, so
        # the caster's own swing lands on the casting target first.
        swing_result = resolve_reactive_melee_swing(caster, target, rng)
        melee_swings.append(MeleeSwing(attacker="a", hit=swing_result.hit, damage=swing_result.damage))
        if target.hit_points <= 0:
            return True, "a"
        disrupted = (
            resolve_spell_disruption(swing_result.damage, rng)
            if swing_result.damage > 0
            else resolve_spell_disruption_from_missed_attack(rng)
        )
        is_first_target_tactic = target_tactic_index == 0
        _advance_target_tactic()
        if disrupted:
            return False, None
        target_outcome = _resolve_target_cast(target_cast, is_first=is_first_target_tactic)
        if target_outcome is None:
            return False, None
        return True, target_outcome

    def _resolve_target_casts() -> str | None:
        """Mirrors `turn/search_execution.py _resolve_monster_casts()`:
        burns through the target's own *leading* `CAST` tactics before
        any real combat phase begins (whatever the caster's own first
        tactic is), stopping without consuming at the target's own
        first `MELEE` or once its plan runs out. A no-op, no rng
        consumed, when `target_tactics` is `None`.
        """

        while True:
            tactic = _peek_target_cast()
            if tactic is None:
                return None
            is_first = target_tactic_index == 0
            _advance_target_tactic()
            outcome = _resolve_target_cast(tactic, is_first=is_first)
            if outcome is not None:
                return outcome

    target_cast_outcome = _resolve_target_casts()
    if target_cast_outcome == "fled":
        return _outcome(fled=True)
    if target_cast_outcome in ("a", "b"):
        return _outcome(winner=target_cast_outcome)

    for index, tactic in enumerate(tactics):
        if tactic.maneuver is Maneuver.SHOOT:
            if current_range is CombatRange.MELEE_RANGE:
                continue  # [5.0]: only spells or Melee are usable in the melee zone
            current_range = _close_to(CombatRange.BOW_RANGE, current_range)
            result = resolve_fire_arrow_duel(caster, target, rng)
            fire_arrow_shots.extend(result.shots)
            if result.winner is not None:
                return _outcome(winner=result.winner)
            continue
        if tactic.maneuver is Maneuver.MELEE:
            current_range = _close_to(CombatRange.MELEE_RANGE, current_range)
            encounter_over, round_result = _resolve_melee_round(is_last_tactic=(index == len(tactics) - 1))
            if encounter_over:
                return _outcome(fled=True) if round_result == "fled" else _outcome(winner=round_result)
            continue
        if tactic.maneuver is Maneuver.CAST:
            target_cast_at_melee = _peek_target_cast() if current_range is CombatRange.MELEE_RANGE else None
            if current_range is CombatRange.MELEE_RANGE and target_cast_at_melee is None:
                # Phase 417: the target's own reactive swing (attacker="b",
                # since the caster="a" is the one attempting to cast here)
                # is now logged into melee_swings too, reading .hit/.damage
                # off resolve_reactive_melee_swing()'s own Phase 416
                # ReactiveMeleeSwingResult -- disruption itself is
                # unchanged, still keyed off .damage > 0, not .hit.
                # Phase 674: only the target's own *reactive* swing here
                # -- if it has a Cast of its own queued instead, it casts
                # too (Cast-vs-Cast, below) rather than reactively swinging.
                swing_result = resolve_reactive_melee_swing(target, caster, rng)
                damage = swing_result.damage
                melee_swings.append(MeleeSwing(attacker="b", hit=swing_result.hit, damage=swing_result.damage))
                if caster.hit_points <= 0:
                    return _outcome(winner="b")
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
                return _outcome(fled=True)
            if outcome in ("a", "b"):
                return _outcome(winner=outcome)
            bonus_winner = _consume_bonus_attacks(caster, target, rng)
            if bonus_winner is not None:
                return _outcome(winner=bonus_winner)
            if target_cast_at_melee is not None:
                # Phase 674: Cast-vs-Cast -- both sides attempt their own
                # spell this round, no swings, no disruption (mirrors
                # search_execution.py's own Cast-vs-Cast branch).
                is_first_target_tactic = target_tactic_index == 0
                _advance_target_tactic()
                target_outcome = _resolve_target_cast(target_cast_at_melee, is_first=is_first_target_tactic)
                if target_outcome == "fled":
                    return _outcome(fled=True)
                if target_outcome in ("a", "b"):
                    return _outcome(winner=target_outcome)
            continue
        if tactic.maneuver is Maneuver.STEAL:
            steal_outcome = _resolve_steal_tactic(caster_leader, caster, target_leader, state, rng)
            if steal_outcome == "executed":
                return _outcome(winner="b")
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
    if not _target_has_more_casts_pending():
        result = resolve_melee_duel(caster, target, rng, skip_temper_setup=melee_setup_done)
        melee_swings.extend(result.melee_swings)
        return _outcome(winner=result.winner)
    # Phase 674: the exhausted tactic list still defaults to Melee, but
    # the target's own remaining Cast(s) must still get their own
    # agency -- mirrors search_execution.py's own "combat_attempted"
    # tail loop, round-stepping instead of jumping straight to the
    # atomic duel.
    while True:
        encounter_over, round_result = _resolve_melee_round(is_last_tactic=True)
        if encounter_over:
            return _outcome(fled=True) if round_result == "fled" else _outcome(winner=round_result)


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
    # Phase 417: same field, same reason as `ChallengeCombatOutcome`'s own
    # Phase 417 addendum -- copied straight through so `report/turn_
    # report.py` can narrate the whole encounter's combat, not only its
    # final blow.
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    melee_swings: tuple[MeleeSwing, ...] = ()
    # Phase 417: the originating request, so a caller (report/turn_report.py
    # describe_turn_results()) can resolve the target's own display name --
    # set by plan_dispatch.py's own dispatcher, not by execute_challenge()
    # itself, the same Phase 213 convention `PursueExecutionResult.request`/
    # `SearchExecutionResult.request` already established.
    request: ChallengeRequest | None = None


def _apply_bravest_talk_inspiration(state: GameState, challenger: LeaderState, target: LeaderState) -> None:
    """Report SS18.8: "Il titolare ispira gli altri personaggi: quando parla a un Hero,
    il temperamento di quel Hero sale di un livello, salvo che sia gia'
    al massimo." -- ``models/office.py OFFICE_PERK_DESCRIPTION[Office.
    BRAVEST]`` already names this exact effect ("Improve Temper, by
    using Talk tactic"), independently corroborating the report's own
    reading (that perk string predates this phase, Phase 103).

    No roll: SS18.8's own text states the effect plainly, with no
    associated success chance -- unlike Silver Tongue/King of Cowards
    (Phase 468), which also fire unconditionally once their own trigger
    condition is met.

    Only a Hero (``not target.is_king``) is inspired -- the source's own
    "Hero" wording. Fires at most once per ``execute_challenge()`` call
    regardless of how many TALK tactics the plan queues -- "la prosa del
    titolo... limita... a una sola tattica Talk utile nello stesso
    incontro" -- since the caller below checks ``Maneuver.TALK``
    *presence*, not per-tactic occurrence.

    **Scope: leader-vs-leader CHALLENGE only**, matching ``_apply_duel_
    encounter_merit()``'s own established precedent just below (Phase
    443) -- ``turn/pursue_execution.py execute_pursue()``'s own armyless-
    case Encounter resolution deliberately never calls that function
    either, the same "Challenge-only" scope this phase follows, not a new
    narrowing.
    """

    holder = resolve_office_holder(state, Office.BRAVEST)
    if holder is None or holder.leader_id != challenger.leader_id:
        return
    if target.is_king or target.temper is None:
        return
    target.temper = raise_temper_one_level(target.temper)


def _apply_spy_brainwash_alignment_shift(challenger: LeaderState, target: LeaderState) -> None:
    """`AdvancedAbility.SPY_BRAINWASH`'s own real description
    (`models/advanced_ability.py`): "When the spy uses the Talk tactic
    on any hero, that character will move one step closer in alignment
    to the Spy's alignment. Not usable on Kings."

    Same shape as `_apply_bravest_talk_inspiration()` right above --
    unconditional (no roll) once the trigger fires, "Hero" read literally
    (`not target.is_king`), scoped to leader-vs-leader CHALLENGE only,
    firing at most once per `execute_challenge()` call regardless of how
    many TALK tactics the plan queues (same `Maneuver.TALK` *presence*
    check both callers below already share with the Bravest hook).

    A no-op when either side's own `alignment` isn't recorded (nothing
    to move from or toward), or when they're already aligned the same
    way. "One step" is `models/alignment.py ALIGNMENT_ORDINAL`'s own
    real Pascal `outlook` ordinal sequence, moved toward the Spy's own
    ordinal by exactly 1 -- the sourced magnitude, not an interpretation.
    """

    if AdvancedAbility.SPY_BRAINWASH not in challenger.advanced_abilities:
        return
    if target.is_king or target.alignment is None or challenger.alignment is None:
        return
    target_ordinal = ALIGNMENT_ORDINAL[target.alignment]
    challenger_ordinal = ALIGNMENT_ORDINAL[challenger.alignment]
    if target_ordinal == challenger_ordinal:
        return
    step = 1 if challenger_ordinal > target_ordinal else -1
    target.alignment = ALIGNMENT_BY_ORDINAL[target_ordinal + step]


def _apply_duel_encounter_merit(
    challenger: LeaderState,
    target: LeaderState,
    *,
    accepted: bool,
    winner_leader: LeaderState | None,
    loser_leader: LeaderState | None,
    challenger_combatant: Combatant | None,
) -> None:
    """Phase 443: Duellist (id 44), Cravenest/King of Cowards (id 49), and
    Bravest of the Brave (id 50) merit, wired at the personal CHALLENGE
    encounter's own close point -- ``AKGEN_reverse_engineering_report
    (2).md`` SS17/SS18 give the exact, disassembly-sourced formulas (all
    three share the same real "close encounter" dispatcher). Scope:
    leader-vs-leader CHALLENGE only -- this project's ``execute_challenge``
    never faces a monster opponent (that path is ``search_execution.py``/
    ``turn/encounter.py``'s own wandering-encounter mechanics).

    ``accepted=False`` (ordinary refusal, ``_LAvoid``/``_LCow``) is the
    "avoided" case: stake is 1 rather than 2, and the *refusing* leader
    (``target``, since ``is_encounter_accepted`` decides whether the
    target accepts) is the Cravenest loser. A magical escape (``fled``)
    or an inconclusive draw (``winner is None``) are both excluded from
    all three titles -- the source's own "successful Cowardly bluff"
    exclusion (recoded result outside the +-1/+-2 range) is the closest
    real analogue for an exceptional non-ordinary outcome, so neither
    caller passes ``winner_leader``/``loser_leader`` for those cases and
    this function is simply not called for them.

    Cravenest's dispatcher deliberately skips the *winner's* branch --
    only the loser is ever credited (``-1``), which is exactly why the
    source shows ``King of Cowards`` as structurally unreachable in the
    real build (a positive ``minpts=5`` threshold a negative-only
    accumulator can never cross). That is replicated faithfully here, not
    "fixed".

    Bravest is not a transfer: only the *protagonist* (the challenger, in
    this project's framing -- the leader whose own CHALLENGE order is
    executing) is ever credited, and only when they win, for however many
    of their own starting hit points they never got back
    (``CHARACTER_HIT_POINTS - challenger_combatant.hit_points``). A
    challenger who wins unscathed is credited 0, not skipped -- the
    ``Inc_Tit`` triplet still gets created, per the source.
    """

    if not accepted:
        challenger.merit_tally.duel_merit_net += 1
        target.merit_tally.duel_merit_net -= 1
        target.merit_tally.courage_encounter_merit -= 1
        return

    if winner_leader is None or loser_leader is None:
        return

    winner_leader.merit_tally.duel_merit_net += 2
    loser_leader.merit_tally.duel_merit_net -= 2
    loser_leader.merit_tally.courage_encounter_merit -= 1

    if winner_leader is challenger and challenger_combatant is not None:
        bravery_gain = CHARACTER_HIT_POINTS - challenger_combatant.hit_points
        winner_leader.merit_tally.bravery_merit += bravery_gain


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

    has_talk_tactic = any(tactic.maneuver is Maneuver.TALK for tactic in request.tactics)

    if not has_combat_intent(request):
        if has_talk_tactic:
            _apply_bravest_talk_inspiration(state, challenger, target)
            _apply_spy_brainwash_alignment_shift(challenger, target)
        return ChallengeExecutionResult(accepted=True, combat_occurred=False)

    target_leads_army = bool(state.armies_commanded_by(target.leader_id))
    accepted = is_encounter_accepted(
        target_is_king=target.is_king,
        target_leads_army=target_leads_army,
        challenger_is_king=challenger.is_king,
        mutual_encounter=mutual_encounter,
        rng=rng,
        has_spy_assassinate=AdvancedAbility.SPY_ASSASSINATE in challenger.advanced_abilities,
    )
    if not accepted:
        _apply_duel_encounter_merit(
            challenger, target, accepted=False, winner_leader=None, loser_leader=None, challenger_combatant=None
        )
        return ChallengeExecutionResult(accepted=False, reason="encounter refused")

    if has_talk_tactic:
        _apply_bravest_talk_inspiration(state, challenger, target)
        _apply_spy_brainwash_alignment_shift(challenger, target)

    challenger_combatant = _leader_combatant(challenger, state)
    target_combatant = _leader_combatant(target, state)
    # Phase 674: rulebook [5.10]'s own "used in every Encounter
    # solicited by another character" (only when the target commands no
    # armies -- `target_leads_army` above already gives that answer).
    target_tactics = list(target.special_encounter_plan) if target_uses_special_encounter_plan(state, target) else None
    combat_result = resolve_challenge_combat(
        request.tactics,
        challenger,
        challenger_combatant,
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
        add_experience(challenger, Ability.MELEE, 10, rng)
    if any(s.hit for s in combat_result.melee_swings if s.attacker == "b"):
        add_experience(target, Ability.MELEE, 10, rng)
    if any(s.hit for s in combat_result.fire_arrow_shots if s.shooter == "a"):
        add_experience(challenger, Ability.ARCHERY, 10, rng)
    if any(s.hit for s in combat_result.fire_arrow_shots if s.shooter == "b"):
        add_experience(target, Ability.ARCHERY, 10, rng)

    if combat_result.fled:
        return ChallengeExecutionResult(
            accepted=True,
            combat_occurred=True,
            fled=True,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            melee_swings=combat_result.melee_swings,
        )
    if combat_result.winner is None:
        return ChallengeExecutionResult(
            accepted=True,
            combat_occurred=True,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            melee_swings=combat_result.melee_swings,
        )

    winner_id, loser_id = (
        (challenger_leader_id, request.target_character_id)
        if combat_result.winner == "a"
        else (request.target_character_id, challenger_leader_id)
    )
    winner_leader, loser_leader = (challenger, target) if combat_result.winner == "a" else (target, challenger)
    _apply_duel_encounter_merit(
        challenger,
        target,
        accepted=True,
        winner_leader=winner_leader,
        loser_leader=loser_leader,
        challenger_combatant=challenger_combatant,
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
        fire_arrow_shots=combat_result.fire_arrow_shots,
        melee_swings=combat_result.melee_swings,
    )
