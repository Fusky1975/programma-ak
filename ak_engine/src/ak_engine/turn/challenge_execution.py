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
  as Flee" branch is now wired too (Phase 743)**, via this module's own
  real ``Maneuver.FLEE`` mechanic below -- previously a genuine, sourced
  gap (no Flee tactic or [5.6] base-chance table existed anywhere in
  this module or ``turn/pursue_execution.py``).
- **``Maneuver.FLEE`` (Phase 743, rulebook [5.6])**: "The chance of
  fleeing from fast monsters is 20%, from medium-speed monsters or
  other characters 50%, and slow monsters can be escaped from 80% of
  the time." A leader-vs-leader Flee here always resolves against
  ``FLEE_CHANCE[MonsterSpeed.MEDIUM]`` ("... or other characters") --
  no per-unit speed lookup is needed, the same reading the Lava Pool
  branch above already established. ``FLEE_CHANCE``/``effective_flee_
  chance()``/``_has_air_elemental_familiar()`` are duplicated verbatim
  from ``turn/search_execution.py``'s own copies (Phase 169/286/312/
  515/665) -- this project's own established "small, duplicated per-
  consumer" convention between these two peer modules (neither imports
  from the other anywhere; only genuinely shared primitives like
  ``resolve_augur_combat()`` live in ``turn/encounter.py``). A failed
  roll falls through to the plan's next tactic, matching [11.3]'s own
  worked example ("CA-IN, ST, FL, ME"). **Deliberately still out of
  scope**: the *target's* own SEP-driven Flee agency (``target_
  tactics`` today only ever peeks for leading ``CAST`` tactics) --
  wiring Flee only for the primary walked ``tactics`` list matches
  every other tactic in this loop's own existing scope; a genuinely
  Flee-capable target SEP is a separate, larger follow-up.
  ``turn/pursue_execution.py``'s own armyless case inherits this for
  free via the shared ``resolve_challenge_combat()`` call, no code
  change needed there.

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

**Phase 700 -- `AdvancedAbility.LONG_RANGE_ARCHERY`.** Resolves a
"genuinely ambiguous" flag from Phase 520/later surveys: ``resolve_
challenge_combat()``'s own ``SHOOT`` branch now lets a caster holding
this ability fire from Spell Range itself (half accuracy, one-sided --
see ``turn/encounter.py resolve_fire_arrow_duel()``'s own Phase 700
addendum) instead of the ordinary unconditional close-to-Bow-Range.
``SHORT_RANGE_ARCHERY`` (fire at Melee Range) is untouched by this
phase -- see that same addendum. **Phase 719 -- ``turn/search_
execution.py``'s own separate, duplicated ``CombatRange`` engine now
wires both abilities too**, adapted for a real structural difference
(no intermediate Bow-Range step exists in that engine) -- see that
module's own Phase 719 addendum.
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
from ak_engine.models.temper import Temper, raise_temper_one_level
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
    INFRARED_GOGGLES_HIT_CHANCE_MULTIPLIER,
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
    hand_of_death_cast_and_archery_block,
    bow_of_elven_kings_archery_damage_bonus,
    bow_of_elven_kings_archery_hit_multiplier,
    control_undead_anti_holy_resist_chance,
    effective_melee_skill,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    weapon_melee_damage_bonus,
    weapon_offensive_hit_multiplier,
    resolve_refusal_to_meet,
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
    resolve_words_of_healing_disruption,
    resolve_words_of_healing_disruption_from_missed_attack,
    try_consume_combat_cast_slot,
    roll_fireball_damage,
    roll_holy_symbol_undead_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spiritwrack_melee_damage_reduction,
    steal_ransom_amount,
    treasury_raid_amount,
    words_of_healing_heal,
)
from ak_engine.turn.experience import add_experience
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.sep_decode import plan_intent, sep_accepts_challenge, target_uses_special_encounter_plan

_COMBAT_MANEUVERS = frozenset({Maneuver.MELEE, Maneuver.SHOOT})

# Phase 290: same secret-spell skill-5+ gate `turn/search_execution.py`
# uses for Illusory Hero/Words of Healing, duplicated per this project's
# own "same shared fact, independent citation per consumer" convention.
ILLUS_HERO_KNOWN_ABILITY_LEVEL = 5
WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL = 5

# Phase 761: the identical gate for the other 3 secret Personal-Combat
# spells this module dispatches -- see `turn/search_execution.py`'s own
# Phase 761 addendum for the full reasoning (this file never had them
# gated at all, only Illusory Hero/Words of Healing above).
GATE_DEMON_KNOWN_ABILITY_LEVEL = 5
LAVA_POOL_KNOWN_ABILITY_LEVEL = 5
AUGUR_COMBAT_KNOWN_ABILITY_LEVEL = 5

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


# Phase 743: rulebook [5.6] Flee, transcribed verbatim -- "The chance of
# fleeing from fast monsters is 20%, from medium-speed monsters or other
# characters 50%, and slow monsters can be escaped from 80% of the time."
# Duplicated from `turn/search_execution.py`'s own copy (Phase 169) --
# see that module's own docstring for the full sourcing of every bonus
# below. A leader-vs-leader Flee here always uses `MonsterSpeed.MEDIUM`
# ("... or other characters") -- no per-unit speed lookup is needed,
# the same reading `_resolve_personal_combat_cast()`'s own Lava Pool
# branch already uses for this exact reason.
FLEE_CHANCE: dict[MonsterSpeed, float] = {
    MonsterSpeed.FAST: 0.20,
    MonsterSpeed.MEDIUM: 0.50,
    MonsterSpeed.SLOW: 0.80,
}

# Rulebook [5.6] Weak-Temperament/Invisibility/Melee-Evasion flee bonuses
# -- see `turn/search_execution.py`'s own Phase 286/312/515 addenda for
# the full sourcing (including the Cowardly extension and the +30%-vs-
# +20% rulebook contradiction, resolved in favor of +30%).
WEAK_TEMPER_FLEE_CHANCE_BONUS = 0.30
WEAK_FLEE_TEMPERS = frozenset({Temper.CAUTIOUS, Temper.COWARDLY})
INVISIBILITY_FLEE_CHANCE_BONUS = 0.30
MELEE_EVASION_FLEE_CHANCE_BONUS = 0.30


def effective_flee_chance(
    base_chance: float,
    *,
    temper: Temper | None,
    is_invisible: bool,
    has_melee_evasion: bool = False,
    has_air_elemental_familiar: bool = False,
) -> float:
    """Phase 286 (via Phase 743): applies the Weak-Temperament,
    Invisibility, Melee Evasion, and Air Elemental flee bonuses to a
    base [5.6] chance. Duplicated verbatim from `turn/search_execution.
    py`'s own copy -- see that module's own Phase 286/515/665 addenda
    for the full sourcing, the additive-not-multiplicative reasoning,
    and the Cautious-plus-Cowardly extension. Clamped to 1.0.
    """

    if has_air_elemental_familiar:
        return 1.0
    bonus = WEAK_TEMPER_FLEE_CHANCE_BONUS if temper in WEAK_FLEE_TEMPERS else 0.0
    if is_invisible:
        bonus += INVISIBILITY_FLEE_CHANCE_BONUS
    if has_melee_evasion:
        bonus += MELEE_EVASION_FLEE_CHANCE_BONUS
    return min(1.0, base_chance + bonus)


def _has_air_elemental_familiar(state: GameState, leader_id: int) -> bool:
    """Office.ELE_MAGE's own Air Elemental familiar (Phase 665) -- "<2",
    the titleholder personally, not his whole Kingdom. Duplicated from
    `turn/search_execution.py`'s own copy, this project's own established
    "small per-consumer lookup" convention.
    """

    holder = resolve_office_holder(state, Office.ELE_MAGE)
    return holder is not None and holder.leader_id == leader_id


def _resolve_cast_disruption(pending_cast: SearchTactic | None, damage: int, rng: random.Random) -> bool:
    """Phase 730: rolls whether a queued ``CAST`` tactic is disrupted this
    round by damage (or a missed/dodged attack, ``damage <= 0``) --
    ``resolve_spell_disruption()``/``resolve_spell_disruption_from_
    missed_attack()`` for every spell except Words of Healing, whose own
    halved rate (``turn/encounter.py``'s Phase 200 addendum) was computed
    but never actually reached either roll here (Phase 655's own
    correction). Duplicated verbatim in `turn/search_execution.py`, this
    project's own established "small per-consumer lookup" convention.
    """

    is_words_of_healing = False
    if pending_cast is not None:
        try:
            is_words_of_healing = Spell(pending_cast.sub_object) is Spell.HEAL
        except ValueError:
            is_words_of_healing = False
    if is_words_of_healing:
        if damage > 0:
            return resolve_words_of_healing_disruption(damage, rng)
        return resolve_words_of_healing_disruption_from_missed_attack(rng)
    if damage > 0:
        return resolve_spell_disruption(damage, rng)
    return resolve_spell_disruption_from_missed_attack(rng)


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


def target_evades_via_sense_danger(state: GameState, target: LeaderState, challenger: LeaderState) -> bool:
    """Phase 706 -- ``AdvancedAbility.SENSE_DANGER_TALENT``'s own real
    description: "The Psychic is able to sense the approach of
    dangerous enemies... encounters with unfriendly characters can be
    avoided 50% of the time. It is used only when the Flee tactic is
    the first one in the special encounter plan." True only when the
    *target* holds the ability, the *challenger* isn't a friend (same
    Kingdom or formally allied, ``GameState.is_allied()``), and the
    target's own real Special Encounter Plan leads with ``Maneuver.
    FLEE`` -- ``sep_accepts_challenge()`` (Phase 669) already reduces
    to exactly that condition (``False`` iff Flee is the plan's own
    first tactic), the same primitive ``rulebook [5.10]``'s own Duel-
    trigger logic reuses. ``target_uses_special_encounter_plan()``
    (Phase 674, "used in every Encounter... only when the target
    commands no armies") gates whether the target's own SEP is even in
    play at all -- an army-commanding target's plan is never consulted
    here either, matching that same rulebook scoping rather than
    inventing a separate one.

    The "random encounters" half of this ability's own text has no
    consumer to gate -- this project has no monster/random-encounter-
    generation mechanism at all (confirmed by the SEP roadmap's own
    investigation) -- so only the "unfriendly characters" half is
    modeled here, deliberately, not silently.
    """

    if AdvancedAbility.SENSE_DANGER_TALENT not in target.advanced_abilities:
        return False
    if state.is_allied(target.kingdom_id, challenger.kingdom_id):
        return False
    target_sep = list(target.special_encounter_plan) if target_uses_special_encounter_plan(state, target) else []
    return not sep_accepts_challenge(target_sep, state)


def king_challenge_evasion_applies(
    state: GameState, challenger: LeaderState, target: LeaderState, request: ChallengeRequest
) -> bool:
    """Phase 793 -- `Desktop/LCHALL.md` (a disassembly of `ResolveChallenge`,
    `AK.EXE raw 0xD68C-0xDAB3`) shows [3.12]'s own "evade encounters from
    Kings 50% of the time" is not a coin flip in the real engine
    (`D89E-D8F4`). It's a deterministic alternation for this exact
    ``(turn, actor, target)`` triple, reached only when the challenger's
    own plan carries an *explicit* Melee tactic (`FindTacticPosition`,
    which -- unlike `Plan_Intent`'s own `CShoot`-inclusive Melee
    classification -- searches for `Maneuver.MELEE` specifically) whose
    overall classified intent is *also* Melee (`Plan_Intent`, already
    ported verbatim as `turn/sep_decode.py plan_intent()`, Phase 659):

        ((gameturn + target + actor + 1) AND 1) = 0
        AND FindTacticPosition(CMelee, plan) > 0
        AND Plan_Intent(plan) = CMelee

    Returns ``True`` iff the target evades (the encounter should be
    refused) -- ``False`` means either the gate's own precondition
    (explicit Melee + Melee intent) never applies, or it applies but the
    parity doesn't favor evasion this turn; both cases fall through to
    an accepted encounter, exactly like the real resolver's own "if
    condition is false, keep going" control flow.

    **Scoped to CHALLENGE only.** ``is_encounter_accepted()`` is also
    called by `turn/patrol_execution.py`/`turn/pursue_execution.py`,
    but LCHALL.md only resolves `ResolveChallenge`'s own resolver --
    those two callers keep the rulebook's plain 50% roll until/unless a
    comparable disassembly confirms they share this exact mechanism.
    """

    if not any(tactic.maneuver is Maneuver.MELEE for tactic in request.tactics):
        return False
    if plan_intent(request.tactics, state) is not Maneuver.MELEE:
        return False
    return (state.turn_number + target.leader_id + challenger.leader_id + 1) % 2 == 0


def is_encounter_accepted(
    *,
    target_is_king: bool,
    target_leads_army: bool,
    challenger_is_king: bool,
    mutual_encounter: bool,
    rng: random.Random,
    has_spy_assassinate: bool = False,
    is_treasury_raid_attempt: bool = False,
    has_sense_danger_evasion: bool = False,
    king_evasion_applies: bool | None = None,
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

    Phase 702 -- `AdvancedAbility.THIEF_TREASURY_RAIDS`'s own real
    description: "The Raid Treasury ability is activated by giving an
    order to Encounter that king number." Without a bypass, an ordinary
    one-sided Challenge against a King is refused unless `mutual_
    encounter` (rare) -- contradicting that plain framing. User-
    confirmed directly: `is_treasury_raid_attempt` (computed by the
    caller from the challenger's own real eligibility, not just from
    holding the ability -- see `execute_challenge()`'s own Phase 702
    addendum) is a second, independent unconditional-accept condition,
    the same shape as `has_spy_assassinate` -- holding both abilities
    at once is not a conflict, exactly like Phase 698's own precedent.

    Phase 706 -- `AdvancedAbility.SENSE_DANGER_TALENT`: "encounters with
    unfriendly characters can be avoided 50% of the time." Deliberately
    scoped to only the final, ordinary fallback below -- the King/army-
    leader/King-challenger branches above each already have their own
    real, more specific rule ([3.12]'s own text carves no exception into
    any of them for this Talent), so this Talent's own veto only ever
    replaces the unconditional "Heroes who don't lead armies can always
    be Encountered" default, matching the narrowest reading that
    doesn't invent a stacking interaction the source never describes.
    `has_sense_danger_evasion` (computed by the caller via `target_
    evades_via_sense_danger()`, which already folds in ability
    possession, the SEP's own Flee-first condition, and "unfriendly")
    is a single pre-combined eligibility flag, the same shape `is_
    treasury_raid_attempt` already established.

    Phase 793 -- `king_evasion_applies` (computed by the caller via
    `king_challenge_evasion_applies()`, CHALLENGE-only) replaces the
    plain 50% roll below with `Desktop/LCHALL.md`'s own confirmed
    deterministic formula when supplied. Left `None` (the default),
    every existing caller keeps the rulebook's own literal roll
    unchanged -- see `king_challenge_evasion_applies()`'s own docstring
    for why `turn/patrol_execution.py`/`turn/pursue_execution.py` stay
    on the old behavior.
    """

    if has_spy_assassinate or is_treasury_raid_attempt:
        return True
    if target_is_king:
        return mutual_encounter
    if target_leads_army:
        return False
    if challenger_is_king:
        if king_evasion_applies is not None:
            return not king_evasion_applies
        return rng.random() < 0.5  # "evade encounters from Kings 50% of the time"
    if has_sense_danger_evasion:
        return rng.random() < 0.5  # "avoided... 50% of the time"
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
    cast_slots_used: dict[Ability, int],
    cast_spells_attempted: set[Spell],
    fizzled_spells: list[tuple[str, Spell]] | None = None,
    is_defensive: bool = False,
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

    **``is_defensive`` (2026-10-31)**: ``True`` only when this call is
    the encounter's own *target* casting back in defense of itself --
    i.e. ``_resolve_target_cast()``'s own call below, where the overall
    target plays this function's ``caster`` role. ``False`` (default)
    for every other call site, including the overall caster's own
    ordinary offensive ``CAST`` tactic. The only consumer today is Kill
    Enemy's own [4.25.2] "un negromante non può usarlo per difendere sé
    stesso in un piano incontro" restriction -- every other spell is
    unaffected either way.
    """

    if caster.blocked_from_cast:
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

    if spell is Spell.KILL_ENEMY:
        # Kill Enemy's own eligibility preconditions, same "ineligible
        # means no roll at all" pattern as Control Undead above:
        # [4.25.2]'s "un negromante non può usarlo per difendere sé
        # stesso in un piano incontro" (checked first -- a defensive
        # cast never even reaches the King/Undead checks below), "I Re
        # sono immuni a questo incantesimo", and "inefficace contro
        # Non-Morti...". This module has no Monster-target concept
        # (leader-vs-leader only, per this function's own docstring),
        # so only the character-alignment half of the Undead clause
        # applies here.
        if is_defensive:
            return None
        if target_leader is not None and (target_leader.is_king or target_leader.alignment is Alignment.UNDEAD):
            return None

    if spell is Spell.ILLUS_HERO:
        level = effective_skill_level(state, caster_leader, ability)
        if level < ILLUS_HERO_KNOWN_ABILITY_LEVEL:
            return None
    elif spell is Spell.HEAL:
        level = effective_skill_level(state, caster_leader, ability)
        if level < WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL:
            return None
    elif spell is Spell.GATE_DEMON:
        level = effective_skill_level(state, caster_leader, ability)
        if level < GATE_DEMON_KNOWN_ABILITY_LEVEL:
            return None
    elif spell is Spell.LAVA_POOL:
        level = effective_skill_level(state, caster_leader, ability)
        if level < LAVA_POOL_KNOWN_ABILITY_LEVEL:
            return None
    elif spell is Spell.AUGUR_COMBAT:
        level = effective_skill_level(state, caster_leader, ability)
        if level < AUGUR_COMBAT_KNOWN_ABILITY_LEVEL:
            return None
    else:
        level = effective_skill_level(state, caster_leader, ability)

    kingdom = state.kingdoms.get(caster_leader.kingdom_id) if caster_leader.kingdom_id is not None else None
    caster_is_pagan = ability is not Ability.WHITE and kingdom is not None and kingdom.alignment is Alignment.PAGAN

    if spell is Spell.AUGUR_COMBAT and not is_first_tactic:
        # `turn/encounter.py`'s own Phase 205 addendum: "if it comes
        # later, then the result will be an attempt to flee." Phase 743:
        # now wired via this module's own real Flee formula -- mirrors
        # `turn/search_execution.py`'s own identical AUGUR_COMBAT branch.
        flee_chance = effective_flee_chance(
            FLEE_CHANCE[MonsterSpeed.MEDIUM],
            temper=caster_leader.temper,
            is_invisible=caster.is_invisible,
            has_melee_evasion=AdvancedAbility.MELEE_EVASION in caster_leader.advanced_abilities,
            has_air_elemental_familiar=_has_air_elemental_familiar(state, caster_leader.leader_id),
        )
        if rng.random() < flee_chance:
            return "fled"
        return None

    # Phase 732: no wand-cast/`forced_level` concept exists anywhere in
    # this module (confirmed by grep) -- every real attempt reaching
    # this point is a genuine Personal-Combat cast, so the slot check
    # applies unconditionally, right before the real success roll, once
    # every other precondition above has already passed.
    if not try_consume_combat_cast_slot(ability, spell, level, cast_slots_used, cast_spells_attempted):
        return None

    # Kill Enemy [4.25.2]: "la possibilità di riuscita è ridotta alla
    # metà in un incontro in un Luogo Speciale o contro un Eroe che
    # comanda unità militari" -- same two OR'd triggers as the Action-
    # Cast form (`cast_execution.py _execute_kill_enemy()`), reusing
    # its own "any Feature at the caster's own province" reading of
    # "Luogo Speciale" (this module has no Search-style guaranteed-at-
    # a-Feature context to make that half unconditionally true, unlike
    # `turn/search_execution.py`'s own Kill Enemy branch).
    kill_enemy_multiplier = 1.0
    if spell is Spell.KILL_ENEMY:
        halving_applies = bool(state.features_at(caster_leader.location)) or (
            target_leader is not None and bool(state.armies_commanded_by(target_leader.leader_id))
        )
        kill_enemy_multiplier = 0.5 if halving_applies else 1.0
    succeeded = resolve_personal_combat_spell_cast(
        level, rng, caster_is_pagan=caster_is_pagan, success_chance_multiplier=kill_enemy_multiplier
    )

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

    if spell is Spell.KILL_ENEMY:
        if succeeded:
            # Hidden Tattoos (Discovery.txt, Phase 270): "neutralize the
            # Kill Enemy spell of Necromancers... All characters of the
            # Kingdom are protected." Checked after the generic Anti-
            # Necromancy-Amulet immunity above (lines 910-914), same
            # order as `cast_execution.py _execute_kill_enemy()`'s own
            # True-Cross-then-Hidden-Tattoos sequence.
            target_has_hidden_tattoos = (
                target_leader is not None
                and target_leader.kingdom_id is not None
                and Discovery.HIDDEN_TATTOOS in state.kingdoms[target_leader.kingdom_id].discoveries
            )
            if target_has_hidden_tattoos:
                return None
            # "Se l'incantesimo riesce, la vittima viene uccisa" --
            # unlike the Action-Cast form's documented coma substitute,
            # a Personal-Combat success is the real kill.
            return "a"
        # "Se fallisce, la vittima designata attaccherà l'autore
        # dell'incantesimo assumendo per l'occasione un temperamento
        # Berserk, se necessario anche aggredendolo in quella stessa
        # fase" -- an immediate `resolve_melee_duel()` between the
        # designated victim (temper forced to Berserk "for the
        # occasion", mirroring `cast_execution.py
        # _kill_enemy_combatant()`'s own Action-Cast precedent) and the
        # caster, resolved inline. The retaliator (`target`) is passed
        # first (this sub-duel's own local "a"=retaliator/"b"=caster
        # convention), then translated back into this function's outer
        # "a"=caster/"b"=target convention.
        retaliator = replace(target, temper=Temper.BERSERK)
        duel_result = resolve_melee_duel(retaliator, caster, rng)
        if duel_result.winner == "a":  # the designated victim's Berserk retaliation kills the caster
            return "b"
        if duel_result.winner == "b":  # the caster survives and wins the retaliation
            return "a"
        return None  # the vanishingly rare max-rounds-exhausted draw -- the encounter continues

    if not succeeded:
        # Phase 858: SBUNGLE.X's own real "personal-combat Cast that just
        # fizzles" text -- see `ChallengeCombatOutcome.fizzled_spells`'s
        # own docstring for why this is the one precise, unambiguous
        # trigger point.
        if fizzled_spells is not None:
            fizzled_spells.append((caster.name, spell))
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
        target.blocked_from_cast = target.blocked_from_archery = blocks_cast_and_archery(target_is_immune=target_is_immune)
        return None

    if spell is Spell.PSYCHIC_BLAST:
        # Phase 883: Discovery.LEAD_LINED_HELMET -- narrows the free-
        # attack-round roll to 1-2 for a target whose own Kingdom
        # holds it.
        target_kingdom = state.kingdoms.get(target_leader.kingdom_id) if target_leader is not None else None
        target_has_lead_lined_helmet = target_kingdom is not None and Discovery.LEAD_LINED_HELMET in target_kingdom.discoveries
        caster.bonus_unanswered_attacks += roll_psychic_blast_stun_rounds(
            rng, target_has_lead_lined_helmet=target_has_lead_lined_helmet
        )
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
        # Phase 881: Discovery.INFRARED_GOGGLES -- a weaker, partial
        # carve-out for whoever's fighting the invisible caster (not a
        # full bypass like Witchsight/the Crystal above): "defensive
        # protection will be only 20%, not 50%."
        opponent_kingdom = state.kingdoms.get(target_leader.kingdom_id) if target_leader is not None else None
        opponent_has_infrared_goggles = (
            opponent_kingdom is not None and Discovery.INFRARED_GOGGLES in opponent_kingdom.discoveries
        )
        if not opponent_has_witchsight and not opponent_sees_through_illusion:
            multiplier = (
                INFRARED_GOGGLES_HIT_CHANCE_MULTIPLIER
                if opponent_has_infrared_goggles
                else INVISIBILITY_HIT_CHANCE_MULTIPLIER
            )
            caster.defensive_hit_multiplier *= multiplier
        caster.is_invisible = True
        return None

    if spell is Spell.FIREBALL:
        # Phase 882: Discovery.ASBESTOS_CLOTHING -- reduces the damage
        # by 67% for a target whose own Kingdom holds it.
        target_kingdom = state.kingdoms.get(target_leader.kingdom_id) if target_leader is not None else None
        target_has_asbestos_clothing = target_kingdom is not None and Discovery.ASBESTOS_CLOTHING in target_kingdom.discoveries
        target.hit_points -= roll_fireball_damage(
            level, rng, target_is_immune=False, target_has_asbestos_clothing=target_has_asbestos_clothing
        )
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
        # Phase 884: Discovery.ARTIFICIAL_ORGANS -- zeroes the caster's
        # own squeeze damage for a target whose own Kingdom holds it
        # (the channel itself still runs; see turn/encounter.py
        # roll_hand_of_death_damage()'s own Phase 884 addendum). Also
        # (Phase 889) relaxes the archery half of the baseline block
        # right below, per the Discovery's own real second clause.
        target_kingdom = state.kingdoms.get(target_leader.kingdom_id) if target_leader is not None else None
        target_has_artificial_organs = target_kingdom is not None and Discovery.ARTIFICIAL_ORGANS in target_kingdom.discoveries
        # Phase 887/889: Hand of Death's own baseline "victim cannot cast
        # spells nor shoot with a bow" restriction -- confirmed word-
        # for-word identical to Spiritwrack's own victim effect (turn/
        # encounter.py blocks_cast_and_archery()'s own Phase 190 rename/
        # citation) -- narrowed by Discovery.ARTIFICIAL_ORGANS's own
        # real "archery can be used (but not spells)" clause via
        # hand_of_death_cast_and_archery_block(). Reuses the exact same
        # target_is_immune value the channel's own damage effect uses
        # just above: a target ENHANCED_COMBAT_NE_SPELLS makes non-
        # immune to the squeeze is equally non-immune to this block.
        target.blocked_from_cast, target.blocked_from_archery = hand_of_death_cast_and_archery_block(
            target_is_immune, target_has_artificial_organs
        )
        channel_result = resolve_hand_of_death_channel(
            caster, target, level, rng, target_is_immune=target_is_immune, target_has_artificial_organs=target_has_artificial_organs
        )
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
            rng,
            damage_range=attacker.melee_damage_range,
            hit_chance_multiplier=defender.defensive_hit_multiplier,
            skill_difference_bonus=max(0, effective_melee_skill(attacker) - effective_melee_skill(defender)),
        )
        damage = max(0, damage - attacker.melee_damage_dealt_reduction)
        defender.hit_points -= damage
        if defender.hit_points <= 0:
            return "a"
    return None


def _apply_successful_theft(state: GameState, thief: LeaderState, victim: LeaderState, rng: random.Random) -> list[int]:
    """The theft's own tangible effect -- Phase 305, superseded by
    Phase 506's own full item-scan-with-decay (``turn/encounter.py``'s
    own Phase 506 addendum, ``steal_character_item_transfer_chance()``):
    the victim's own eligible items are scanned in a randomly-shuffled
    order, each independently rolled against a threshold that starts at
    75% and is halved (integer right-shift) after every item *actually
    transferred* -- a hidden item does not itself halve the threshold,
    only a successful transfer does. Gold theft stays unmodeled for an
    ordinary thief (see module docstring's own Phase 305 addendum) --
    [5.5]'s own "depends on how much he has in the treasury" clause
    never got a magnitude. **Phase 702**: `AdvancedAbility.THIEF_
    TREASURY_RAIDS`'s own text finally supplies one ("up to half of the
    treasury"), but only for a holder targeting a foreign King --
    `_resolve_steal_tactic()` below redirects that specific success case
    to `_apply_treasury_raid()` instead of calling this function at all
    (see that function's own docstring for why gold and items are
    alternatives, not cumulative, per [5.5]'s own "oro o... oggetti").

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

    **Phase 777**: returns the real item ids actually transferred (in
    shuffle order, possibly empty) -- backlog #19's own STEAL-family
    narration (`report/turn_report.py describe_steal()`) needs to know
    what was stolen, not just that the attempt succeeded.
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
    stolen_item_ids: list[int] = []
    for item in items:
        if resolve_steal_character_item_transfer(items_already_stolen, rng):
            state.transfer_item(item.item_id, thief.leader_id)
            items_already_stolen += 1
            stolen_item_ids.append(item.item_id)
    add_experience(thief, Ability.THIEF, 15, rng)
    return stolen_item_ids


def _apply_treasury_raid(state: GameState, thief: LeaderState, king: LeaderState, rng: random.Random) -> int:
    """``AdvancedAbility.THIEF_TREASURY_RAIDS``' own real effect (Phase
    702) -- a successful Steal against a foreign King's treasury
    *replaces* ``_apply_successful_theft()``'s own item transfer above,
    rather than adding to it: [5.5]'s own Italian text already frames
    "oro o uno o piu' oggetti magici" (gold OR one or more magic items)
    as alternatives, and only this ability's own text supplies a real
    magnitude for the gold half.

    Same merit/XP crediting as ``_apply_successful_theft()`` (the Steal
    attempt itself succeeded either way), but raids ``turn/encounter.py
    treasury_raid_amount()``'s own "up to half" cut of the King's
    kingdom treasury instead of scanning for items. Returns the amount
    raided.
    """

    thief.merit_tally.successful_thefts += 1
    kingdom = state.kingdoms[king.kingdom_id]
    amount = treasury_raid_amount(kingdom.treasury, rng)
    kingdom.treasury -= amount
    if thief.kingdom_id is not None:
        state.kingdoms[thief.kingdom_id].treasury += amount
    add_experience(thief, Ability.THIEF, 15, rng)
    return amount


def _resolve_steal_tactic(
    caster_leader: LeaderState | None,
    caster: Combatant,
    target_leader: LeaderState | None,
    state: GameState,
    rng: random.Random,
) -> tuple[str, int, list[int]]:
    """Steal [ST], rulebook [5.5] -- Phase 305, superseded by Phase 506
    with the real disassembly-sourced success/evasion formulas (see
    ``turn/encounter.py``'s own Phase 506 addendum) and a ransom-formula
    fix. See module docstring's own Phase 305 addendum for the full
    quoted rulebook text and the reasoning behind every branch below.

    Returns an ``(outcome, gold_raided, stolen_item_ids)`` triple.
    ``outcome`` is ``"success"`` (theft applied, plan continues),
    ``"evaded"`` (failed but not caught, plan continues), ``"executed"``
    (thief killed outright, no combat), ``"ransom"`` (King-thief
    captured by a King or an army-commanding Hero, nobody dies -- Phase
    526 extended this beyond King-vs-King specifically, see module
    docstring's own Phase 526 addendum), ``"combat"`` (caller must
    resolve a forced personal-combat encounter at a freshly-rolled
    range), or ``"unresolved"`` (a garrison commander with no
    ``LeaderState``, below -- the one remaining case no sourced branch
    covers). ``gold_raided`` (Phase 702) is non-zero only for a
    successful ``AdvancedAbility.THIEF_TREASURY_RAIDS`` raid against a
    foreign King -- see below. ``stolen_item_ids`` (Phase 777) is the
    real item ids `_apply_successful_theft()` actually transferred --
    non-empty only for an ordinary (non-Treasury-Raid) ``"success"``.

    A garrison commander (``caster_leader``/``target_leader`` is
    ``None``, Phase 291's own Duel reuse) can neither attempt nor be a
    Steal target -- no ``LeaderState`` exists to read a Thief skill,
    royal status, or army command from.
    """

    if caster_leader is None or target_leader is None:
        return "unresolved", 0, []

    level = effective_skill_level(state, caster_leader, Ability.THIEF)
    target_leads_army = bool(state.armies_commanded_by(target_leader.leader_id))
    target_leads_army_or_is_king = target_leader.is_king or target_leads_army
    has_thief_mastery = bool(caster_leader.advanced_abilities & STEAL_THIEF_MASTERY_ABILITIES)
    has_enhanced_invisibility = AdvancedAbility.ENHANCED_INVISIBILITY in caster_leader.advanced_abilities
    # Phase 702/786: AdvancedAbility.THIEF_TREASURY_RAIDS -- "targets the
    # treasury of a foreign king." Phase 786 (`AKGEN_reverse_engineering_
    # report (3).md` SS39.2, the same document already cited for Phase
    # 785's own amount formula) found the real, disassembled binary only
    # ever increments the guard counter after a SUCCESSFUL raid -- not
    # "in either case, success or failure alike" the way the manual's own
    # text (and Phase 702's own original reading of it) says. Per this
    # project's own standing "manual vs. AKGEN-report conflict -- ask the
    # user" rule, the user confirmed following the binary: the counter is
    # only read here (no increment), and incremented only inside the
    # `is_treasury_raid` success branch below.
    is_treasury_raid = (
        AdvancedAbility.THIEF_TREASURY_RAIDS in caster_leader.advanced_abilities
        and target_leader.is_king
        and target_leader.kingdom_id is not None
        and caster_leader.kingdom_id is not None
        and target_leader.kingdom_id != caster_leader.kingdom_id
    )
    treasury_raid_guard_counter = 0
    if is_treasury_raid:
        victim_kingdom = state.kingdoms.get(target_leader.kingdom_id)
        if victim_kingdom is not None:
            treasury_raid_guard_counter = victim_kingdom.treasury_raid_attempts_this_turn
    if resolve_steal_attempt(
        level,
        rng,
        has_thief_mastery=has_thief_mastery,
        is_invisible=caster.is_invisible,
        has_enhanced_invisibility=has_enhanced_invisibility,
        target_leads_army_or_is_king=target_leads_army_or_is_king,
        treasury_raid_guard_counter=treasury_raid_guard_counter,
    ):
        if is_treasury_raid:
            victim_kingdom = state.kingdoms.get(target_leader.kingdom_id)
            if victim_kingdom is not None:
                victim_kingdom.treasury_raid_attempts_this_turn += 1
            return "success", _apply_treasury_raid(state, caster_leader, target_leader, rng), []
        stolen_item_ids = _apply_successful_theft(state, caster_leader, target_leader, rng)
        return "success", 0, stolen_item_ids
    if resolve_steal_evasion(level, rng):
        return "evaded", 0, []

    if not target_leads_army_or_is_king:
        return "combat", 0, []
    if not caster_leader.is_king:
        return "executed", 0, []
    # Phase 526: AKGEN_reverse_engineering_report (3).md SS42's own capture
    # table/pseudocode pays ransom to "LKing(victim)" whenever the victim
    # is king_or_army_leader -- no separate branch for a King thief caught
    # by a King versus by a non-King army-commanding Hero. See module
    # docstring's own Phase 526 addendum for the full sourcing.
    thief_kingdom = state.kingdoms.get(caster_leader.kingdom_id) if caster_leader.kingdom_id is not None else None
    if thief_kingdom is None or thief_kingdom.treasury <= 0:
        return "executed", 0, []
    ransom = steal_ransom_amount(thief_kingdom.treasury)
    thief_kingdom.treasury -= ransom
    victim_kingdom = state.kingdoms.get(target_leader.kingdom_id) if target_leader.kingdom_id is not None else None
    if victim_kingdom is not None:
        victim_kingdom.treasury += ransom
    return "ransom", 0, []


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
    # Phase 702: non-zero only for a successful AdvancedAbility.THIEF_
    # TREASURY_RAIDS raid against a foreign King -- see `_apply_
    # treasury_raid()`'s own docstring for why this replaces, not adds
    # to, an ordinary item theft.
    gold_raided: int = 0
    # Phase 777: the real item ids `_apply_successful_theft()` actually
    # transferred -- non-empty only for an ordinary (non-Treasury-Raid)
    # successful Steal. Backlog #19's own STEAL-family narration
    # (`report/turn_report.py describe_steal()`) needs this to know what
    # was stolen, not just that the attempt succeeded.
    stolen_item_ids: list[int] = field(default_factory=list)
    # Phase 417: per-shot/per-swing combat detail, mirroring `turn/
    # search_execution.py SearchExecutionResult`'s own `fire_arrow_shots`/
    # `melee_swings` fields (Phase 175/415/416) -- accumulated across
    # every real combat call site in `resolve_challenge_combat()` below,
    # not just whichever one happened to be decisive, so `report/
    # turn_report.py` can narrate the whole encounter, not only its
    # final blow.
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    melee_swings: tuple[MeleeSwing, ...] = ()
    # Phase 858 (continuing the manual report-completeness sweep):
    # `turn/encounter.py resolve_personal_combat_spell_cast()` is a real,
    # sourced (AKGEN_reverse_engineering_report (2).md SS21.1) probabilistic
    # cast-success roll -- the module comment above `report/turn_report.py
    # render_spell_fizzled_in_combat()` (SBUNGLE.X) claimed "this project's
    # combat resolution has no probabilistic spell-fizzle roll of its own
    # either," which was stale: this roll IS exactly that, at both real
    # call sites (this module and `turn/search_execution.py`). One
    # `(caster_name, spell)` entry per `CAST` tactic whose roll came back
    # `False` with no other precondition failure -- excludes `CONTROL_
    # UNDEAD`'s own failure (a real, distinct, differently-narrated effect
    # via `control_undead_failure_new_hit_points()`, checked in its own
    # branch *before* the generic `if not succeeded: return None` this
    # list is populated from).
    fizzled_spells: tuple[tuple[str, Spell], ...] = ()


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

    ~~**Gold theft's own magnitude is still not modeled** -- ``turn/
    encounter.py``'s own Phase 239 addendum already confirmed this
    formula "confirmed absent" for the King-victim case specifically,
    noting "a future Challenge/Pursue-side Steal would still need it";
    this phase *is* that future consumer, and the text still gives no
    number to build against. Generalizing further: only a King's own
    ``KingdomState.treasury`` is a real gold pool in this project's
    model at all (an ordinary Hero holds no gold of his own), so gold
    theft stays unmodeled for every target, not just Kings.~~ --
    **partially closed as of Phase 702**: ``AdvancedAbility.THIEF_
    TREASURY_RAIDS``'s own text supplied a real magnitude after all
    ("up to half of the treasury"), for a holder targeting a foreign
    King specifically -- see ``_apply_successful_theft()``'s own Phase
    702 addendum just below and ``_apply_treasury_raid()``. Gold theft
    stays genuinely unmodeled only for the remaining case: an ordinary
    thief with no ``THIEF_TREASURY_RAIDS`` (or any thief targeting a
    non-King, who holds no gold pool to begin with).
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

    **Resolved (backlog #12, closed 2026-09-10, comment-only)**:
    [3.12]'s own English-only clause ("If the Steal tactic is used in
    such a restricted encounter, the chance of success is halved") and
    the Italian [5.5] target-leads-an-army halving are **the same rule**,
    not two independently stacking halvings -- confirmed by the exact
    same dossier already cited above for the success formula itself
    (``AKGEN_reverse_engineering_report (3).md`` SS35, the sentence
    immediately preceding the compiled formula): "Le normali
    restrizioni di incontro non impediscono il furto, ma lasciano un
    malus: contro un Re o contro un Eroe che conduce un esercito la
    probabilita' viene dimezzata" (the ordinary encounter-acceptance
    restrictions don't block Steal outright, but leave a malus --
    against a King or an army-leading Hero, the chance is halved). The
    compiled formula itself (``AK.OVR:0x1AADA-0x1AB94``, quoted in full
    two sections above) has exactly one halving term in its own
    divisor (``H``, "1 against a King/army-leading Hero, 0 otherwise")
    -- no second, independent term for "the plan also carries combat
    tactics" exists anywhere in it. Re-reading the full Italian [3.12]
    text directly (``Regolamento AK.txt`` lines 771-787) confirms why:
    "questi incontri 'limitati'" ("these 'restricted' encounters") is
    the rulebook's own paraphrase for exactly the encounters where the
    King/Hero acceptance restrictions apply in the first place -- i.e.
    targeting a King or an army-leading Hero -- not a separate condition
    about the plan's own tactic composition. ``target_leads_army_or_
    is_king`` (already wired above, unchanged by this fix) is already
    the complete, correct implementation of both clauses at once.

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
    whatever comes next. **Stale as of Phase 743** (this paragraph is
    frozen at the time it was written): ``Maneuver.FLEE`` is real and
    wired in this module now (`effective_flee_chance()`/`FLEE_CHANCE`,
    the caster's own main-loop branch) -- a following ``FLEE`` picks up
    from the rolled range exactly like the ``MELEE`` case this paragraph
    already describes; only the *target's* own reactive Flee agency
    stays unwired (Phase 743's own explicit scope boundary). No test exercised
    the old atomic path with a following tactic, so this is a correction
    caught before it shipped a wrong default, not a regression fix.

    **Phase 702 addendum -- a Steal-only plan now reaches this function.**
    Previously (Phase 305/306): ``execute_challenge()``'s own ``not has_
    combat_intent(request)`` short-circuit (Phase 50) returned before
    ever calling this function for a plan with no Melee/Fire-Arrow/
    decodable-Cast tactic alongside ``STEAL``, since [3.12]'s own text
    deliberately excludes Steal from "combat intent" -- a real, then-
    consciously-not-fixed gap, since no available real data attested a
    Steal-only plan (both of [11.3]'s own worked examples always pair
    ``ST`` with a real combat tactic). ``AdvancedAbility.THIEF_TREASURY_
    RAIDS``'s own text ("Of course, there must be a ST-eal tactic in the
    encounter plan" -- no mention of also needing a combat tactic) made
    this gap concretely block the ability's own most natural plan shape,
    so the user confirmed fixing it directly: ``execute_challenge()``'s
    guard now also passes through whenever the plan contains ``STEAL``,
    regardless of whether it's a treasury raid -- a small, generally-
    scoped fix, not narrowly gated to this one ability.

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
    agency for the *target's* own tactic list specifically (real and
    wired for the caster's own primary tactics since Phase 743, but
    this project has no mechanism anywhere for a target to react with
    its own Flee mid-fight -- a real, still-open, narrower gap than
    this paragraph originally claimed) and any "does the target want to
    Shoot" gate (`resolve_fire_arrow_duel()` is already a fully mutual
    exchange in one call, regardless of either side's own plan).
    """

    current_range = CombatRange.SPELL_RANGE
    melee_setup_done = False
    target_tactic_index = 0
    # Phase 732: this encounter's own Personal-Combat cast-slot trackers
    # (`turn/encounter.py try_consume_combat_cast_slot()`'s own docstring
    # has the full sourced rule) -- one pair per side, never persisted
    # beyond this one call. `turn/battle_orchestrator.py`'s own Duel
    # reuse of this function picks these up for free.
    caster_cast_slots_used: dict[Ability, int] = {}
    caster_cast_spells_attempted: set[Spell] = set()
    target_cast_slots_used: dict[Ability, int] = {}
    target_cast_spells_attempted: set[Spell] = set()
    # Phase 306: carried into every ``ChallengeCombatOutcome`` returned
    # below (not just a terminal STEAL branch) -- see that dataclass's own
    # Phase 306 addendum for why a non-terminal Steal outcome (success/
    # evaded/ransom/unresolved) still needs to reach the report layer even
    # when a later tactic decides the encounter's actual winner.
    steal_outcome: str | None = None
    steal_capture_range: CombatRange | None = None
    # Phase 702: non-zero only for a successful Treasury Raid -- see
    # `ChallengeCombatOutcome.gold_raided`'s own Phase 702 addendum.
    gold_raided: int = 0
    # Phase 777: the real item ids transferred by an ordinary (non-
    # Treasury-Raid) successful Steal -- see `ChallengeCombatOutcome.
    # stolen_item_ids`'s own Phase 777 addendum.
    stolen_item_ids: list[int] = []
    # Phase 417: accumulated across every real combat call site below,
    # regardless of whether that particular call ended the encounter --
    # mirrors `turn/search_execution.py`'s own `fire_arrow_shots`/
    # `melee_swings` nonlocal-accumulator pattern (Phase 175/415), just
    # as plain locals here since this function has no nested closures.
    fire_arrow_shots: list[FireArrowShot] = []
    melee_swings: list[MeleeSwing] = []
    # Phase 858: see `ChallengeCombatOutcome.fizzled_spells`'s own docstring.
    fizzled_spells: list[tuple[str, Spell]] = []

    def _outcome(
        *, winner: str | None = None, fled: bool = False
    ) -> ChallengeCombatOutcome:
        return ChallengeCombatOutcome(
            winner=winner,
            fled=fled,
            steal_outcome=steal_outcome,
            steal_capture_range=steal_capture_range,
            gold_raided=gold_raided,
            stolen_item_ids=list(stolen_item_ids),
            fire_arrow_shots=tuple(fire_arrow_shots),
            melee_swings=tuple(melee_swings),
            fizzled_spells=tuple(fizzled_spells),
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
            target,
            target_leader,
            caster,
            caster_leader,
            tactic,
            state,
            rng,
            is_first_tactic=is_first,
            cast_slots_used=target_cast_slots_used,
            cast_spells_attempted=target_cast_spells_attempted,
            fizzled_spells=fizzled_spells,
            is_defensive=True,
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
        melee_swings.append(
            MeleeSwing(
                attacker="a",
                hit=swing_result.hit,
                damage=swing_result.damage,
                weapon_proc=swing_result.weapon_proc,
                weapon_proc_hit_points=swing_result.weapon_proc_hit_points,
            )
        )
        if target.hit_points <= 0:
            return True, "a"
        disrupted = _resolve_cast_disruption(target_cast, swing_result.damage, rng)
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
        if tactic.maneuver is Maneuver.FLEE:
            # Phase 743: rulebook [5.6], "from ... other characters
            # [50%]" -- MonsterSpeed.MEDIUM needs no per-unit lookup
            # here, see this function's own module-docstring addendum.
            flee_chance = effective_flee_chance(
                FLEE_CHANCE[MonsterSpeed.MEDIUM],
                temper=caster_leader.temper if caster_leader is not None else None,
                is_invisible=caster.is_invisible,
                has_melee_evasion=caster_leader is not None and AdvancedAbility.MELEE_EVASION in caster_leader.advanced_abilities,
                has_air_elemental_familiar=caster_leader is not None and _has_air_elemental_familiar(state, caster_leader.leader_id),
            )
            if rng.random() < flee_chance:
                return _outcome(fled=True)
            continue
        if tactic.maneuver is Maneuver.SHOOT:
            if current_range is CombatRange.MELEE_RANGE:
                # Phase 701: AdvancedAbility.SHORT_RANGE_ARCHERY -- "may
                # now use the Fire tactic at Melee Range, with the
                # normal chance to hit." Unlike Long Range Archery, the
                # target stands right next to the archer, so -- mirroring
                # this same function's own existing Cast-at-Melee-Range
                # reactive-swing branch just below -- they get a free
                # reactive Melee swing against the archer first (the
                # user's own confirmed design choice, extending that
                # established pattern to this ability). Phase 887: gated
                # on `not caster.blocked_from_archery` too -- Spiritwrack/
                # Hand of Death's own "cannot ... shoot with a bow" victim
                # effect, mirroring turn/search_execution.py's own
                # equivalent branch exactly (a real, pre-existing gap in
                # this file found while wiring Hand of Death's own
                # archery block: this branch never consulted the flag at
                # all before this phase, so Spiritwrack's own already-
                # shipped restriction silently never blocked Short Range
                # Archery here).
                if (
                    not caster.blocked_from_archery
                    and caster_leader is not None
                    and AdvancedAbility.SHORT_RANGE_ARCHERY in caster_leader.advanced_abilities
                ):
                    swing_result = resolve_reactive_melee_swing(target, caster, rng)
                    melee_swings.append(
                        MeleeSwing(
                            attacker="b",
                            hit=swing_result.hit,
                            damage=swing_result.damage,
                            weapon_proc=swing_result.weapon_proc,
                            weapon_proc_hit_points=swing_result.weapon_proc_hit_points,
                        )
                    )
                    if caster.hit_points <= 0:
                        return _outcome(winner="b")
                    result = resolve_fire_arrow_duel(caster, target, rng, short_range_archer="a")
                    fire_arrow_shots.extend(result.shots)
                    if result.winner is not None:
                        return _outcome(winner=result.winner)
                    continue
                continue  # [5.0]: only spells or Melee are usable in the melee zone
            # Phase 887: the ordinary (non-Melee-Range) shot is refused
            # outright for a blocked caster too -- same real gap/fix as
            # the Melee-Range branch above, checked before Long Range
            # Archery's own eligibility so a blocked caster can't reach
            # that branch either.
            if caster.blocked_from_archery:
                continue
            # Phase 700: AdvancedAbility.LONG_RANGE_ARCHERY -- "may now
            # use the Fire tactic at Spell Range, with half the normal
            # chance to hit" -- fires from Spell Range itself instead of
            # the ordinary unconditional close-to-Bow-Range below. See
            # turn/encounter.py's own Phase 700 addendum for why this is
            # one-sided (the target gets no return fire and no melee
            # counter -- too far away -- only a Cast counter, already
            # resolved independently above via _resolve_target_casts()).
            if (
                current_range is CombatRange.SPELL_RANGE
                and caster_leader is not None
                and AdvancedAbility.LONG_RANGE_ARCHERY in caster_leader.advanced_abilities
            ):
                result = resolve_fire_arrow_duel(caster, target, rng, long_range_archer="a")
            else:
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
                melee_swings.append(
                    MeleeSwing(
                        attacker="b",
                        hit=swing_result.hit,
                        damage=swing_result.damage,
                        weapon_proc=swing_result.weapon_proc,
                        weapon_proc_hit_points=swing_result.weapon_proc_hit_points,
                    )
                )
                if caster.hit_points <= 0:
                    return _outcome(winner="b")
                disrupted = _resolve_cast_disruption(tactic, damage, rng)
                if disrupted:
                    continue
            outcome = _resolve_personal_combat_cast(
                caster,
                caster_leader,
                target,
                target_leader,
                tactic,
                state,
                rng,
                is_first_tactic=(index == 0),
                cast_slots_used=caster_cast_slots_used,
                cast_spells_attempted=caster_cast_spells_attempted,
                fizzled_spells=fizzled_spells,
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
            steal_outcome, gold_raided, stolen_item_ids = _resolve_steal_tactic(
                caster_leader, caster, target_leader, state, rng
            )
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
    # Phase 702: copied straight from `ChallengeCombatOutcome` -- non-
    # zero only for a successful `AdvancedAbility.THIEF_TREASURY_RAIDS`
    # raid against a foreign King.
    gold_raided: int = 0
    # Phase 777: copied straight from `ChallengeCombatOutcome` -- the
    # real item ids an ordinary (non-Treasury-Raid) successful Steal
    # actually transferred, for `report/turn_report.py describe_steal()`
    # to narrate.
    stolen_item_ids: list[int] = field(default_factory=list)
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
    # Phase 793: True only when `AdvancedAbility.SPY_ASSASSINATE`'s own
    # unconditional-accept bypass (Phase 698) is why this encounter was
    # accepted at all -- lets `report/turn_report.py describe_challenge()`
    # render SANOTE.X2 record 79 (`Desktop/LCHALL.md` section 9.2a)
    # right after the ENCATT.X search line.
    used_spy_assassinate: bool = False
    # Phase 858: copied straight from `ChallengeCombatOutcome` -- see that
    # dataclass's own `fizzled_spells` docstring.
    fizzled_spells: tuple[tuple[str, Spell], ...] = ()


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
    state: GameState,
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
    of their own starting hit points they never got back (their own real
    starting hit points -- ``CHARACTER_HIT_POINTS`` plus whatever
    ``arcane_valor_hit_points_bonus()`` gave them, the same total
    ``_leader_combatant()`` seeded them with -- minus ``challenger_
    combatant.hit_points``). **Bug fix**: this used to subtract from the
    bare ``CHARACTER_HIT_POINTS`` constant instead, crediting a negative
    ``bravery_merit`` to any Scepter-of-Life-boosted challenger who won
    cleanly. A challenger who wins unscathed is credited 0, not skipped
    -- the ``Inc_Tit`` triplet still gets created, per the source.
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
        # Bug fix: the challenger's own real starting hit points can
        # exceed the bare CHARACTER_HIT_POINTS constant (_leader_
        # combatant()'s own arcane_valor_hit_points_bonus() under
        # GameType.ARCANES, Phase 538) -- using the bare constant here
        # instead credited a negative bravery_gain for any such
        # challenger winning cleanly, contradicting this function's own
        # docstring ("a challenger who wins unscathed is credited 0,
        # not skipped").
        starting_hit_points = CHARACTER_HIT_POINTS + arcane_valor_hit_points_bonus(state, challenger)
        bravery_gain = starting_hit_points - challenger_combatant.hit_points
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

    Phase 702 -- ``AdvancedAbility.THIEF_TREASURY_RAIDS``: "the thief
    must be in either the hex where the king is located, or his home
    province, if he still owns it... Of course, there must be a ST-eal
    tactic in the encounter plan." A treasury-raid-eligible challenger
    (holds the ability, targeting a foreign King, plan contains
    ``STEAL``) may satisfy co-location by standing in the target
    King's own Kingdom's home province instead of the King's literal
    current hex, but only while that Kingdom still owns it -- both
    conditions the ability's own text states explicitly. See ``turn/
    challenge_execution.py``'s own module docstring for why this also
    widens the ``has_combat_intent`` gate below (a Steal-only plan
    otherwise never reaches ``resolve_challenge_combat()`` at all) and
    why it bypasses ``is_encounter_accepted()``'s own King-refusal via
    a new, dedicated parameter there.

    Phase 706 -- ``AdvancedAbility.SENSE_DANGER_TALENT``: "encounters
    with unfriendly characters can be avoided 50% of the time... used
    only when the Flee tactic is the first one in the special
    encounter plan." See ``target_evades_via_sense_danger()``'s own
    docstring for the full eligibility computation and why the
    "random encounters" half of this ability's own text stays
    unmodeled (this project has no random-encounter mechanism at all).

    Phase 793 -- ``Desktop/LCHALL.md`` (a disassembly of the real
    ``ResolveChallenge``) resolves three things at once: (1) ENCATT.X's
    own opening "searched for the target" sentence (``report/turn_
    report.py render_challenge_search()``) fires unconditionally, wired
    into ``describe_challenge()`` as its own first line regardless of
    outcome; (2) the King-challenges-Hero "50%" evasion is really a
    deterministic parity test, see ``king_challenge_evasion_applies()``;
    (3) ``AdvancedAbility.SPY_ASSASSINATE``'s own real accompanying
    sentence (SANOTE.X2 record 79) was never wired -- ``used_spy_
    assassinate`` on the result records whenever this encounter was
    accepted via that ability's own bypass, so the report layer can
    render it right after the search line.

    **Phase 898 addendum -- the Temper Table's own "refusal to Meet"
    gate ([5.6]).** A genuinely separate rule from [3.12]'s own King/
    Hero acceptance tree above: "I personaggi Codardi e Cauti che non
    siano Re possono... rifiutare l'ordine di Incontrare... a seconda
    della forza dell'avversario" -- see ``turn/encounter.py resolve_
    refusal_to_meet()``'s own module comment for the full quote and the
    percentage-range design choice. Checked once combat is actually
    intended (a peaceful plan already returned above, unaffected --
    [5.6] sits in the Flee/refusal cluster, the same combat-only scoping
    [3.12]'s own text already carves out for its King/Hero rules),
    keyed on the *target's* own Temper against whether the *challenger*
    leads an army (``challenger_leads_army`` -- the target's own "how
    strong is my opponent" signal). Deliberately skipped whenever
    ``has_spy_assassinate``/``is_treasury_raid_attempt`` already forced
    an accept above -- both abilities' own real text reads as an
    unconditional override ("King characters can now encounter other
    characters freely"), the same "bypasses every restriction below"
    framing ``is_encounter_accepted()``'s own docstring already gives
    them, not a narrower King-only carve-out this project should
    re-litigate here. A refusal here reuses the exact same ``reason=
    "encounter refused"``/merit-tally treatment as an ordinary [3.12]
    refusal -- [5.6] gives no separate consequence for this specific
    refusal path.
    """

    rng = rng if rng is not None else random.Random()

    challenger = state.leaders.get(challenger_leader_id)
    target = state.leaders.get(request.target_character_id)
    if challenger is None or target is None:
        return ChallengeExecutionResult(accepted=False, reason="challenger or target not found")

    has_steal_tactic = any(tactic.maneuver is Maneuver.STEAL for tactic in request.tactics)
    is_treasury_raid_attempt = (
        has_steal_tactic
        and target.is_king
        and target.kingdom_id is not None
        and challenger.kingdom_id is not None
        and challenger.kingdom_id != target.kingdom_id
        and AdvancedAbility.THIEF_TREASURY_RAIDS in challenger.advanced_abilities
    )

    co_located = challenger.location == target.location
    remote_treasury_raid = False
    if is_treasury_raid_attempt and not co_located:
        victim_kingdom = state.kingdoms.get(target.kingdom_id)
        if victim_kingdom is not None and challenger.location == victim_kingdom.home_province:
            home_province = state.provinces.get(victim_kingdom.home_province)
            remote_treasury_raid = home_province is not None and home_province.owner_kingdom_id == target.kingdom_id
    if not co_located and not remote_treasury_raid:
        return ChallengeExecutionResult(accepted=False, reason="not co-located")

    has_talk_tactic = any(tactic.maneuver is Maneuver.TALK for tactic in request.tactics)

    if not has_combat_intent(request) and not has_steal_tactic:
        if has_talk_tactic:
            _apply_bravest_talk_inspiration(state, challenger, target)
            _apply_spy_brainwash_alignment_shift(challenger, target)
        return ChallengeExecutionResult(accepted=True, combat_occurred=False)

    target_leads_army = bool(state.armies_commanded_by(target.leader_id))
    has_spy_assassinate = AdvancedAbility.SPY_ASSASSINATE in challenger.advanced_abilities
    accepted = is_encounter_accepted(
        target_is_king=target.is_king,
        target_leads_army=target_leads_army,
        challenger_is_king=challenger.is_king,
        mutual_encounter=mutual_encounter,
        rng=rng,
        has_spy_assassinate=has_spy_assassinate,
        is_treasury_raid_attempt=is_treasury_raid_attempt,
        has_sense_danger_evasion=target_evades_via_sense_danger(state, target, challenger),
        king_evasion_applies=king_challenge_evasion_applies(state, challenger, target, request),
    )
    # Phase 898: [5.6]'s own separate Temper-based refusal gate -- see
    # this function's own Phase 898 addendum above for why it's skipped
    # when an unconditional-accept ability already fired.
    if accepted and not has_spy_assassinate and not is_treasury_raid_attempt:
        challenger_leads_army = bool(state.armies_commanded_by(challenger.leader_id))
        if resolve_refusal_to_meet(
            target.temper, is_king=target.is_king, opponent_leads_army=challenger_leads_army, rng=rng
        ):
            accepted = False
    if not accepted:
        _apply_duel_encounter_merit(
            state, challenger, target, accepted=False, winner_leader=None, loser_leader=None, challenger_combatant=None
        )
        return ChallengeExecutionResult(accepted=False, reason="encounter refused")

    # Phase 793: only meaningful once `accepted` is True -- `SANOTE.X2`
    # record 79 accompanies a real, successful bypass, not a refusal.
    used_spy_assassinate = has_spy_assassinate

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
            gold_raided=combat_result.gold_raided,
            stolen_item_ids=combat_result.stolen_item_ids,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            melee_swings=combat_result.melee_swings,
            fizzled_spells=combat_result.fizzled_spells,
            used_spy_assassinate=used_spy_assassinate,
        )
    if combat_result.winner is None:
        return ChallengeExecutionResult(
            accepted=True,
            combat_occurred=True,
            steal_outcome=combat_result.steal_outcome,
            steal_capture_range=combat_result.steal_capture_range,
            gold_raided=combat_result.gold_raided,
            stolen_item_ids=combat_result.stolen_item_ids,
            fire_arrow_shots=combat_result.fire_arrow_shots,
            melee_swings=combat_result.melee_swings,
            fizzled_spells=combat_result.fizzled_spells,
            used_spy_assassinate=used_spy_assassinate,
        )

    winner_id, loser_id = (
        (challenger_leader_id, request.target_character_id)
        if combat_result.winner == "a"
        else (request.target_character_id, challenger_leader_id)
    )
    winner_leader, loser_leader = (challenger, target) if combat_result.winner == "a" else (target, challenger)
    _apply_duel_encounter_merit(
        state,
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
        gold_raided=combat_result.gold_raided,
        stolen_item_ids=combat_result.stolen_item_ids,
        fire_arrow_shots=combat_result.fire_arrow_shots,
        melee_swings=combat_result.melee_swings,
        fizzled_spells=combat_result.fizzled_spells,
        used_spy_assassinate=used_spy_assassinate,
    )
