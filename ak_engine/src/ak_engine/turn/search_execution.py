"""Executing a Search order (rulebook [3.3] Search feature) -- Phase 132.

**Rulebook [3.3], quoted in full** (also quoted in ``turn/search_decode
.py``'s own docstring): "A character may Search any feature that has
been discovered by his kingdom, or that he hears about from another
King. When a character Searches a feature, he must face the guardian
monster first. He specifies an Encounter Plan. If he defeats the
monster, the treasure in the feature is his... Characters must Search
features as individuals; it is a point of honor to defeat a monster in
single combat."

This module closes the gap ``turn/search_decode.py`` and ``models/
feature.py`` both flagged as blocking Search's own resolution: "needs a
personal, non-army Encounter/combat resolver... that this project
doesn't have yet." ``turn/encounter.py`` (Phase 48) built exactly that
core, and Phase 132 extends it (``Combatant.melee_damage_range``) so a
guardian monster can fight with its own species-specific damage die
instead of the character-only one.

**Scope, and why it stays narrower than "every Search always
resolves"**:

- **Guardian combat stats.** Draws from ``models/monster.py
  MONSTER_COMBAT_STATS`` (Phase 154), a project-original, user-compiled
  table covering all 60 real monster species -- see that module's own
  Phase 154 addendum for full provenance. Hit points are rolled per
  encounter via ``rng.randint(*stats.hit_points_range)``, since the
  source gives a range (not a fixed value) for every species. A feature
  guarded by ``Monster.NOMONSTER`` (the sentinel, not a real species)
  still reports ``combat_resolved=False`` rather than inventing stats.
- **Encounter Plan tactics execute in strict list order (Phase 170
  correction).** Regolamento AK.txt's own worked examples ([11.3],
  "ESEMPI DI PIANI D'INCONTRO") settle this precisely: "FI, FL.
  Significato: Tirare con l'Arco, poi fuggire" ("Shoot with the bow,
  then flee") -- Fire Arrow is attempted *first*, and Flee is only
  attempted if it doesn't end the fight. Phase 169 originally rolled a
  ``Maneuver.FLEE`` tactic unconditionally *before* Melee regardless of
  its position in the plan; this real example proves that was wrong in
  general (it only ever matched by coincidence, since every tested plan
  happened to list Flee before Melee already). ``execute_search()`` now
  walks ``request.tactics`` in order, running each wired tactic until
  one resolves the encounter (or, for Fire Arrow, exhausts its free
  attacks with nobody dead) before moving to the next.
  ``turn/search_decode.py``'s own docstring found, empirically, that
  "every real Search order ends in Melee and/or Scout" across all 12
  real Search phases in the sample files -- ``Maneuver.MELEE``,
  ``Maneuver.FLEE``, and (as of this phase) ``Maneuver.SHOOT`` (Fire
  Arrow) are wired to a real resolution; unwired tactics (Steal, Talk,
  Say, Give, Fulfill, Scout, Cast, Use_MI, Beg) are silently skipped in
  the walk rather than aborting it, since a plan mixing a wired and an
  unwired tactic is exactly what the real examples above show
  ("ST, CA-FI, ME, SC" mixes Steal and Cast, both unwired, with Melee).
  If no wired tactic is present at all, or the walk finishes without
  resolving (Fire Arrow's shots ran out and nothing else followed),
  ``combat_resolved`` reflects that honestly (see ``execute_search()``'s
  own body). **Confirmed directly by the user (Phase 173, project
  author)**: only a single Fire Arrow order can ever appear in an
  Encounter Plan, and once its shots are exhausted "i combattenti
  passano alla fase successiva che dipende dall'elenco di ordini messi
  nel piano d'incontro" ("combatants move to the next phase, determined
  by the tactic list in the Encounter Plan") -- exactly this walk's own
  design, now sourced rather than inferred solely from [11.3]'s worked
  examples. See ``turn/encounter.py``'s own Phase 173 addendum for the
  full quote.
- **Fire Arrow (Phase 170, rulebook [5.2]).** "The base chance to hit is
  30%, plus 10% per Archery level, and the damage is 1-6 hit points."
  Previously left unwired specifically because "nothing in any available
  source says a monster's own ``missile_skill`` drives an equivalent
  formula" -- but ``models/monster.py``'s own Monster Table quote sits
  directly beneath [5.2]'s formula and gives every species an explicit
  Missile Skill/Damage column (e.g. Giant `1/1-7`), which *is* the
  source for exactly that: a monster's ``missile_skill`` plugs into the
  same [5.2] formula a character's Archery level does, and its own
  ``missile_damage`` (``models/monster.py MonsterCombatStats
  .missile_damage``) feeds ``Combatant.missile_damage_range`` (``turn/
  encounter.py``'s own Phase 170 addendum) the same way melee damage
  already did (Phase 132). A monster with ``missile_skill=0`` (no
  ranged attack at all) simply gets zero free attacks
  (``fire_arrow_free_attacks(0) == 0``) -- a natural consequence of the
  formula, not a special-cased exclusion.
- **Flee (Phase 169, rulebook [5.6]).** "The character can declare to
  prefer flight over combat. The chance of fleeing from fast monsters is
  20%, from medium-speed monsters or other characters 50%, and slow
  monsters can be escaped from 80% of the time." Sourced verbatim,
  including all three percentages, in ``models/monster.py``'s own [5.6]
  quote (``FLEE_CHANCE`` below is keyed by the same ``MonsterSpeed`` tier
  already sourced there). A successful roll ends the Search with no
  combat and no loot; a failed roll falls through to the plan's next
  wired tactic, per the ordering correction above. **Deliberately
  excluded, not guessed**: the Cauto/Codardo temperament's "+30% chance
  to flee" bonus ([5.6]'s own "(NOVITA')" addendum, keyed off ``models/
  temper.py``) and Invisibility's "+30% chance to flee" bonus (``turn/
  cast_execution.py``'s own docstring, already flagged unmodeled since it
  needs the not-yet-built Cast-tactic combat engine) -- both are real,
  sourced modifiers to this same roll, but adding either now would be an
  under-tested compound change; flagged here as a natural follow-up
  phase instead.
- **Victory's own aftermath is minimal, by design**: rulebook [5.9]
  ("looting a vanquished foe's treasure, magic items changing hands")
  needs a treasure-*instance* and magic-item-ownership model this
  project doesn't have (``models/feature.py``'s own docstring: "a
  feature's own treasure instance... is still unmodeled -- world
  generation itself remains the blocking gap"; ``models/item.py`` is a
  never-populated stub). A win only sets ``Feature.looted = True``
  (``fstate[fn] = Dead``, "sacked & looted") -- the one confirmed,
  modeled consequence.
- **A loss kills the searching leader**, no special carve-out: personal
  combat's generic rule ([5.0]: "until one combatant is killed") applies
  in full here, the same reasoning ``turn/challenge_execution.py``'s own
  docstring already gives for why a Challenge loser (unlike a Duel
  commander, [7.1]'s own special case) dies for real.
- **Troll regeneration** (Phase 155, ``turn/encounter.py``'s own
  addendum): a Troll's own monster combatant gets
  ``regenerates_hp=TROLL_REGENERATION_PER_COMBAT_ROUND``, so
  ``resolve_melee_duel()`` heals it 1 hit point at the end of every
  round it survives. The FIREBALL-negates-regeneration clause stays
  unwired here too, for the same reason ``turn/encounter.py``'s own
  addendum gives (blocked on the Cast-tactic-spell-id gap).
- **Co-location is enforced** (``leader.location == feature.coord``):
  not literally quoted in [3.3] (which is about *knowledge* of a
  feature's location/number, not physical presence), but single combat
  against a guardian monster obviously needs the searcher to actually be
  there -- the same "must be co-located to act in person" pattern this
  project already enforces for Challenge, Hire/Fire, and Recruit's
  target-leader check.

**Not wired into ``plan_dispatch.py``'s existing scripted-rng test
suite as a silent behavior change without review**: unlike Challenge/
Pursue (opt-in only at the caller's choice, Phase 49/50), Search's own
dispatch *is* switched to real execution this phase (see ``turn/
plan_dispatch.py``'s own updated docstring) -- there is no legacy
decode-only consumer left to preserve, since Search was never wired to
mutate ``GameState`` before.

**Phase 175 addendum -- carrying the Fire Arrow shot log out to the
report layer.** ``turn/encounter.py``'s own Phase 175 addendum gives
``resolve_fire_arrow_duel()`` a per-shot log (``EncounterCombatResult
.shots``) so ``report/turn_report.py`` can narrate each shot
individually, including the dragon-breath/boulder-throw/petrifying-gaze
flavor variants from ``Desktop/MOSTRI con statistiche.txt``'s own
footnotes. ``SearchExecutionResult`` gains ``fire_arrow_shots`` (that
same log, copied out of whichever ``EncounterCombatResult`` a Shoot
tactic produced -- empty if the plan never fires an arrow) and
``guardian_monster`` (the species fought, needed by the report layer to
look up ``models/weapon.py MONSTER_RANGED_WEAPON`` and dispatch to a
flavored renderer or the generic one). Both are attached to whichever
``SearchExecutionResult`` this walk eventually returns, whether that's
the Shoot tactic's own terminal outcome, a later Melee tactic's outcome
(if Fire Arrow's shots ran out first without a winner), or the
walk-exhausted fallback -- a shot fired earlier in the plan is still
worth narrating even if it didn't end the fight.

**Phase 178 addendum -- the guardian gets its own Special Encounter
Plan too, and an exhausted tactic list now correctly defaults to
Melee.** Two corrections, both confirmed directly by the user (project
author) before ``models/monster_encounter_plan.py`` was even supplied:

- **"When the list runs out, default to Melee until someone dies."**
  Quoted in full: "Quando finiscono le azioni che vengono messe nel
  piano d'incontro il personaggio inizia a usare automaticamente il
  comando ME ... Il personaggio di default continua a usare il comando
  ME a mischia finche' muore lui o il mostro." Previously, if the
  leader's own plan resolved a ``SHOOT`` tactic that ran out of arrows
  with nobody dead and had no further tactic afterward, the walk fell
  through to the end-of-loop fallback and reported ``winner=None``
  ("inconclusive") -- contradicting this confirmed default. The
  fallback now resolves one full ``resolve_melee_duel()`` call (which
  already fights to the death in a single call, Phase 48) instead of
  reporting an inconclusive draw. This only changes behavior for a plan
  that resolves *some* wired tactic (``combat_attempted=True``) without
  ever reaching an explicit ``MELEE`` tactic of its own -- a plan with
  no wired tactic at all still reports honestly unresolved, since no
  combat was ever attempted in the first place.
- **The guardian's own plan is independent of the leader's.** Per the
  user's own confirmation, each side follows its own Special Encounter
  Plan -- so ``models/monster_encounter_plan.py roll_monster_encounter_
  plan()`` is rolled for the guardian (using ``leader.alignment is
  Alignment.UNDEAD`` for the "attacker is Undead" override condition)
  purely to answer one question: does the guardian's own plan contain a
  bare ``SHOOT`` tactic before its own terminal Melee? If so, a Fire
  Arrow phase happens even when the *leader's* own submitted plan never
  lists ``SHOOT`` at all (previously, Fire Arrow only ever happened if
  the leader's plan asked for it -- meaning species like Titan or Red
  Dragon, whose entire identity is "shoots/breathes before closing to
  melee," never got to use that attack unless the human player happened
  to also write `FI` into their own plan). This still resolves through
  the same single, symmetric ``resolve_fire_arrow_duel()`` call (Phase
  170) -- at most one Fire Arrow phase per encounter either way, so the
  already-confirmed "only a single FI order can ever appear" rule
  (Phase 173) still holds; it's now triggered by *either* side wanting
  it rather than only the leader's own plan. The guardian's own ``CAST``
  entries (most species' plans open with 0-3 of them) are rolled but
  never inspected here -- they remain exactly as unwired as a leader's
  own ``CAST`` tactic always has been, per the user's own explicit
  scoping decision this phase (no personal-combat spell-effect engine
  exists yet for any of the 11 spells these plans reference).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ak_engine.models.advanced_ability import LAVA_POOL_IMMUNE_MONSTERS
from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.monster import (
    HAND_OF_DEATH_ANTI_HOLY_MONSTERS,
    HAND_OF_DEATH_IMMUNE_MONSTERS,
    ICE_SUSPENSION_FLYING_MONSTERS,
    ICE_SUSPENSION_IMMUNE_MONSTERS,
    MONSTER_COMBAT_STATS,
    MONSTER_MAGIC_ABILITIES,
    MONSTER_NAMES,
    SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS,
    SPIRITWRACK_MECHANICAL_MONSTERS,
    SPIRITWRACK_UNDEAD_MONSTERS,
    SUBMARINE_MONSTERS,
    Monster,
    MonsterSpeed,
    roll_gate_demon_type,
    roll_monster_alignment,
)
from ak_engine.models.monster_encounter_plan import roll_monster_encounter_plan
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.encounter import (
    BEG_MERCY_CHANCE,
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_DAMAGE_RANGE,
    INVISIBILITY_HIT_CHANCE_MULTIPLIER,
    MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT,
    MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER,
    MONSTER_STEAL_CUNNING,
    PERSONAL_COMBAT_SPELL_ABILITY,
    Combatant,
    CombatRange,
    EncounterCombatResult,
    FireArrowShot,
    MirrorImageIntelligenceTier,
    StealTargetCunning,
    TalkReaction,
    blocks_cast_and_archery,
    can_talk_to_monster,
    control_undead_failure_new_hit_points,
    holy_symbol_hit_chance,
    ice_suspension_is_frozen,
    ice_suspension_slowed_bonus_rounds,
    illusory_hero_alignments_are_implacably_hostile,
    mirror_image_leader_disbelief_bonus,
    resolve_augur_combat,
    resolve_beg_for_mercy,
    resolve_fire_arrow_duel,
    resolve_gate_demon_refusal,
    resolve_hand_of_death_channel,
    resolve_illusory_hero_duel,
    resolve_lava_pool_escape,
    resolve_melee_duel,
    resolve_mirror_image_duel,
    resolve_monster_hides_treasure,
    resolve_personal_combat_spell_cast,
    resolve_steal_attempt,
    resolve_steal_evasion,
    resolve_talk_reaction,
    roll_fireball_damage,
    roll_holy_symbol_undead_damage,
    roll_ice_suspension_flying_bonus_rounds,
    roll_ice_suspension_flying_crash_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spiritwrack_melee_damage_reduction,
)
from ak_engine.turn.search_decode import SearchRequest

# Desktop/MOSTRI con statistiche.txt footnote (*): "The Troll regenerates
# 1 hit point every combat round." See turn/encounter.py's own Phase 155
# addendum for the full quote and Combatant.regenerates_hp's own mechanics.
TROLL_REGENERATION_PER_COMBAT_ROUND = 1

# Phase 211: secret spells (ordinals 25-34) are granted once a caster
# reaches skill 5+ in their own base Ability -- `turn/cast_execution.py`'s
# own docstring and `models/advanced_ability.py
# AdvancedAbility.ILLUSORY_HERO_SPELL` confirm this for Illusory Hero
# specifically. Below this threshold, the leader simply doesn't know the
# spell yet -- casting it has no effect at all, no roll consumed.
ILLUS_HERO_KNOWN_ABILITY_LEVEL = 5

# Rulebook [5.6] Flee, transcribed verbatim -- see this module's own
# docstring addendum and models/monster.py's own [5.6] quote.
FLEE_CHANCE: dict[MonsterSpeed, float] = {
    MonsterSpeed.FAST: 0.20,
    MonsterSpeed.MEDIUM: 0.50,
    MonsterSpeed.SLOW: 0.80,
}


def _leader_combatant(leader: LeaderState) -> Combatant:
    """Same construction as ``challenge_execution.py``'s own private helper (Phase 50),
    duplicated rather than shared -- see that module's own docstring for
    why (a different concept that happens to need the same small lookup).
    Search doesn't have a "Neutral Kingdom" bonus concern the way a
    character-vs-character Encounter does (the bonus is about characters
    aiding each other, [5.0]'s "Order of Duelists" -- not sourced as
    applying against monsters), so it's omitted here rather than guessed.
    """

    melee_skill = archery_skill = 0
    if leader.skills is not None:
        melee_skill = leader.skills.pair_for_ability(Ability.MELEE)[0]
        archery_skill = leader.skills.pair_for_ability(Ability.ARCHERY)[0]
    return Combatant(
        name=leader.name, hit_points=CHARACTER_HIT_POINTS, melee_skill=melee_skill, archery_skill=archery_skill
    )


@dataclass(slots=True)
class SearchExecutionResult:
    accepted: bool
    reason: str | None = None
    combat_resolved: bool = False
    winner: str | None = None  # "leader" / "monster" / None (both survived)
    feature_looted: bool = False
    leader_killed: bool = False
    fled: bool = False
    # Phase 175: per-shot Fire Arrow detail (empty unless a Shoot tactic
    # actually fired), plus the guardian's own species -- both needed by
    # report/turn_report.py's own Phase 175 addendum to dispatch each shot
    # to the right narrative renderer (species-flavored or generic).
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    guardian_monster: Monster | None = None
    # Phase 213: the originating request, so a caller (report/turn_report.py
    # describe_turn_results()) can resolve the searched feature's own id.
    # Set by plan_dispatch.py's own dispatcher, not by execute_search()
    # itself -- same convention/reasoning as PursueExecutionResult.request's
    # own Phase 213 note.
    request: SearchRequest | None = None


def execute_search(
    state: GameState,
    leader_id: int,
    request: SearchRequest,
    rng: random.Random | None = None,
) -> SearchExecutionResult:
    """Resolve a Search order end-to-end where the available sources allow it.

    See module docstring for exactly which cases resolve real combat
    and which honestly report ``combat_resolved=False`` instead.
    """

    rng = rng if rng is not None else random.Random()

    leader = state.leaders.get(leader_id)
    if leader is None:
        return SearchExecutionResult(accepted=False, reason="leader not found")

    feature = state.features.get(request.feature_id)
    if feature is None:
        return SearchExecutionResult(accepted=False, reason="feature not found")

    if feature.looted:
        return SearchExecutionResult(accepted=False, reason="feature already looted")

    if feature.guardian_monster is None:
        return SearchExecutionResult(accepted=False, reason="feature has no guardian recorded")

    if leader.location != feature.coord:
        return SearchExecutionResult(accepted=False, reason="not co-located with feature")

    stats = MONSTER_COMBAT_STATS.get(feature.guardian_monster)
    if stats is None:
        monster_name = MONSTER_NAMES.get(feature.guardian_monster, "guardian")
        return SearchExecutionResult(
            accepted=True,
            combat_resolved=False,
            reason=f"no combat stats for guardian ({monster_name}) -- see models/monster.py MONSTER_COMBAT_STATS",
        )

    leader_combatant = _leader_combatant(leader)
    monster_combatant = Combatant(
        name=MONSTER_NAMES.get(feature.guardian_monster, "guardian"),
        hit_points=rng.randint(*stats.hit_points_range),
        melee_skill=stats.melee_skill,
        melee_damage_range=stats.melee_damage,
        archery_skill=stats.missile_skill,
        missile_damage_range=stats.missile_damage if stats.missile_damage is not None else FIRE_ARROW_DAMAGE_RANGE,
        regenerates_hp=TROLL_REGENERATION_PER_COMBAT_ROUND if feature.guardian_monster is Monster.TROLL else 0,
    )

    # Phase 178: the guardian's own Special Encounter Plan, independent
    # of the leader's -- only consulted for whether it wants to Shoot
    # before Melee (its own CAST entries stay unwired). See module
    # docstring's own Phase 178 addendum.
    monster_plan = roll_monster_encounter_plan(
        feature.guardian_monster, rng, attacker_is_undead=leader.alignment is Alignment.UNDEAD
    )
    monster_wants_shoot = monster_plan is not None and any(t.maneuver is Maneuver.SHOOT for t in monster_plan)
    # Phase 209: the guardian's own CAST entries, resolved once, right
    # before the first real combat phase -- same injection point already
    # established for `monster_wants_shoot` above (Phase 178). See module
    # docstring's own Phase 209 addendum. `_resolve_monster_casts()`
    # below walks `monster_plan` directly (Phase 238) rather than a
    # pre-filtered tuple, so Augur Combat can see its own true position.

    def _outcome_from(combat_result: EncounterCombatResult) -> SearchExecutionResult | None:
        """Translate a resolved duel into a terminal result, or None if the
        encounter isn't over yet (only possible for Fire Arrow -- Melee
        always ends in a winner, see resolve_melee_duel's own docstring).
        """

        if combat_result.winner == "a":
            feature.looted = True
            # Phase 242: grant the feature's own treasure (if world
            # generation set one -- `None` for features created outside
            # that pipeline, e.g. most existing tests) to the winning
            # leader via the existing item registry (Phase 140).
            if feature.treasure is not None:
                state.add_item(feature.treasure, leader_id)
            return SearchExecutionResult(accepted=True, combat_resolved=True, winner="leader", feature_looted=True)
        if combat_result.winner == "b":
            state.remove_leader(leader_id)
            return SearchExecutionResult(accepted=True, combat_resolved=True, winner="monster", leader_killed=True)
        return None

    def _resolve_cast_tactic(tactic, *, caster_is_leader: bool, is_first_tactic: bool = False) -> SearchExecutionResult | None:
        """Applies one of the ten Personal-Combat-only spells (or Charm's
        combat form) to the encounter: the 8 non-channeled, one-roll
        spells from Phase 209 (see that phase's own module docstring
        addendum for the full per-spell design and the rulebook citations
        behind ``PERSONAL_COMBAT_SPELL_ABILITY``), Hand of Death and
        Mirror-Image Phantasm from Phase 210 (both of which delegate their
        own round-based sub-loop to ``resolve_hand_of_death_channel()``/
        ``resolve_mirror_image_duel()``, ``turn/encounter.py``'s own
        Phase 210 addendum), and Illusory Hero from Phase 211 (``resolve_
        illusory_hero_duel()`` -- Mirror-Image's own duel shape, but the
        illusion is built from whichever hero is currently visiting
        Valhalla, ``models/valhalla.py VALHALLA_VISITOR_LEADER_ID``,
        rather than a clone of the opponent, and Stage 2 only fires when
        the hero's and caster's own alignments are confirmed "implacably
        hostile"), Gate Demon/Lava Pool from Phase 237 (a summoned
        demon fights the opponent in Gate Demon's own place via a fresh
        ``resolve_melee_duel()``; Lava Pool is a flat, speed-keyed
        instant-kill-or-escape roll), and Augur Combat from Phase 238
        (``is_first_tactic`` -- true position within the caster's own
        full plan, not just among its own ``CAST`` entries -- decides
        whether this runs the real "silent simulation" (a throwaway
        ``resolve_melee_duel()`` on cloned combatants, discarded after
        reading only its winner) or acts as an attempted Flee, per
        ``turn/encounter.py``'s own Phase 205 addendum). Returns a terminal
        ``SearchExecutionResult`` (a kill, a neutralization, or Charm's
        own guaranteed Flee), or ``None`` if the encounter continues (a
        failed cast, a stat-modifier effect, or a spell whose target
        isn't eligible).
        """

        caster = leader_combatant if caster_is_leader else monster_combatant
        target = monster_combatant if caster_is_leader else leader_combatant
        if caster.blocked_from_cast_and_archery:
            return None
        try:
            spell = Spell(tactic.sub_object)
        except ValueError:
            return None

        target_is_monster = caster_is_leader
        monster_species = feature.guardian_monster

        # Charm's own Phase 183 addendum: an Undead caster draws on
        # Necromancy instead of Psychic. Replicated here rather than
        # imported from `cast_execution.py._spell_ability` (private, tied
        # to `LeaderState`) -- same "duplicate the small lookup" precedent
        # as `_leader_combatant()` above. For a monster caster, "Undead"
        # means its own species is in `SPIRITWRACK_UNDEAD_MONSTERS`
        # (monsters have no `alignment` field to check).
        caster_is_undead = (
            (leader.alignment is Alignment.UNDEAD)
            if caster_is_leader
            else (monster_species in SPIRITWRACK_UNDEAD_MONSTERS)
        )
        if spell is Spell.CHARM:
            ability = Ability.NECROMANCY if caster_is_undead else Ability.PSYCHIC
        elif spell is Spell.ILLUS_HERO:
            # Phase 211: not in PERSONAL_COMBAT_SPELL_ABILITY (that table
            # is only the ten base Personal-Combat spells) -- Illusory
            # Hero is one of the ten secret spells, tied to Ability.
            # ILLUSION (module docstring's own Phase 208/211 addenda).
            ability = Ability.ILLUSION
        elif spell is Spell.GATE_DEMON:
            # Phase 237: secret spell, tied to Ability.NECROMANCY
            # (`turn/encounter.py`'s own Phase 202 addendum).
            ability = Ability.NECROMANCY
        elif spell is Spell.LAVA_POOL:
            # Phase 237: secret spell, tied to Ability.ELEMENTAL
            # (`turn/encounter.py`'s own Phase 203 addendum).
            ability = Ability.ELEMENTAL
        elif spell is Spell.AUGUR_COMBAT:
            # Phase 238: secret spell, tied to Ability.PSYCHIC
            # (`turn/encounter.py`'s own Phase 205 addendum).
            ability = Ability.PSYCHIC
        elif spell in PERSONAL_COMBAT_SPELL_ABILITY:
            ability = PERSONAL_COMBAT_SPELL_ABILITY[spell]
        else:
            return None  # not modeled (any spell outside the 13 named above)

        # Control Undead's own eligibility precondition -- checked before
        # any roll, same as every other spell's `target_is_immune` guard,
        # except here an ineligible target means no roll at all rather
        # than a roll that simply has no effect.
        if spell is Spell.CONTROL_UNDEAD:
            eligible = (
                (monster_species in SPIRITWRACK_UNDEAD_MONSTERS) if target_is_monster else (leader.alignment is Alignment.UNDEAD)
            )
            if not eligible:
                return None

        if caster_is_leader:
            level = leader.skills.pair_for_ability(ability)[0] if leader.skills is not None else 0
            kingdom = state.kingdoms.get(leader.kingdom_id) if leader.kingdom_id is not None else None
            # White Magic never gets the Pagan-Realm bonus (Phase 192).
            caster_is_pagan = (
                ability is not Ability.WHITE and kingdom is not None and kingdom.alignment is Alignment.PAGAN
            )
        else:
            level = MONSTER_MAGIC_ABILITIES.get(monster_species, {}).get(ability, 0)
            caster_is_pagan = False  # a monster has no Kingdom

        # Illusory Hero is exclusively leader-cast (never appears in any
        # real monster_encounter_plan.py species plan) and requires
        # ILLUS_HERO_KNOWN_ABILITY_LEVEL -- checked before the roll, same
        # "ineligible means no roll at all" pattern as Control Undead.
        if spell is Spell.ILLUS_HERO and level < ILLUS_HERO_KNOWN_ABILITY_LEVEL:
            return None

        succeeded = resolve_personal_combat_spell_cast(level, rng, caster_is_pagan=caster_is_pagan)

        if spell is Spell.CONTROL_UNDEAD:
            if succeeded:
                # Confirmed by the user: "neutralizes" equals a win.
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            target.hit_points = control_undead_failure_new_hit_points(target.hit_points, rng)
            return None

        if not succeeded:
            return None

        if spell is Spell.CHARM:
            # Confirmed by the user: the *caster* flees, same outcome as a
            # successful Maneuver.FLEE.
            return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)

        if spell is Spell.HOLY_SYMBOL:
            if target_is_monster:
                target_is_undead_or_anti_holy = monster_species in (HAND_OF_DEATH_ANTI_HOLY_MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS)
            else:
                target_is_undead_or_anti_holy = leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
            caster.defensive_hit_multiplier *= holy_symbol_hit_chance(
                1.0, level, target_is_undead_or_anti_holy=target_is_undead_or_anti_holy
            )
            if target_is_undead_or_anti_holy:
                target.hit_points -= roll_holy_symbol_undead_damage(level, rng)
                if target.hit_points <= 0:
                    return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            return None

        if spell is Spell.SPIRITWRACK:
            if target_is_monster:
                target_is_immune = monster_species in (SPIRITWRACK_UNDEAD_MONSTERS | SPIRITWRACK_MECHANICAL_MONSTERS)
                target_is_animal = monster_species in SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS
            else:
                target_is_immune = leader.alignment is Alignment.UNDEAD
                target_is_animal = False
            target.melee_damage_dealt_reduction += spiritwrack_melee_damage_reduction(
                level, rng, target_is_immune=target_is_immune, target_is_animal_intelligence=target_is_animal
            )
            target.blocked_from_cast_and_archery = blocks_cast_and_archery(target_is_immune=target_is_immune)
            return None

        if spell is Spell.PSYCHIC_BLAST:
            caster.bonus_unanswered_attacks += roll_psychic_blast_stun_rounds(rng)
            return None

        if spell is Spell.TELEK_STORM:
            target_is_immune = target_is_monster and monster_species in SUBMARINE_MONSTERS
            target.hit_points -= roll_telekinetic_storm_victim_damage(rng, target_is_immune=target_is_immune)
            caster.hit_points -= roll_telekinetic_storm_caster_damage(
                CombatRange.SPELL_RANGE, rng, target_is_immune=target_is_immune
            )
            if target.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if caster.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("b" if target_is_monster else "a"), rounds=0))
            return None

        if spell is Spell.INVISIBILITY:
            caster.defensive_hit_multiplier *= INVISIBILITY_HIT_CHANCE_MULTIPLIER
            return None

        if spell is Spell.FIREBALL:
            target_is_immune = target_is_monster and monster_species in SUBMARINE_MONSTERS
            target.hit_points -= roll_fireball_damage(level, rng, target_is_immune=target_is_immune)
            if target.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            return None

        if spell is Spell.ICE_SUSPEND:
            if target_is_monster and monster_species in ICE_SUSPENSION_IMMUNE_MONSTERS:
                return None
            if ice_suspension_is_frozen(target.hit_points, level):
                # Confirmed by the user: the frozen branch simplifies to a win.
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if target_is_monster and monster_species in ICE_SUSPENSION_FLYING_MONSTERS:
                target.hit_points -= roll_ice_suspension_flying_crash_damage(rng)
                caster.bonus_unanswered_attacks += roll_ice_suspension_flying_bonus_rounds(rng)
                if target.hit_points <= 0:
                    return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
                return None
            caster.bonus_unanswered_attacks += ice_suspension_slowed_bonus_rounds(target.hit_points, level)
            return None

        if spell is Spell.HAND_OF_DEATH:
            if target_is_monster:
                target_is_immune = monster_species in HAND_OF_DEATH_IMMUNE_MONSTERS
            else:
                target_is_immune = leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
            channel_result = resolve_hand_of_death_channel(caster, target, level, rng, target_is_immune=target_is_immune)
            if channel_result.winner is not None:
                # "a" in resolve_hand_of_death_channel's own convention always
                # means the caster -- translate to the leader/monster "a"/"b"
                # convention _outcome_from() expects.
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            return None

        if spell is Spell.MIRROR_IMAGE:
            if target_is_monster:
                opponent_tier = MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER[monster_species]
                opponent_disbelief_bonus = 0.0
            else:
                # Confirmed by the user: a King/Hero opponent is always
                # High Human, plus a further +2%/Sage level + +1%/Illusion
                # level bonus on top of the table -- monster opponents
                # don't get this bonus.
                opponent_tier = MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT
                sage_level = leader.skills.pair_for_ability(Ability.SAGE)[0] if leader.skills is not None else 0
                illusion_level = (
                    leader.skills.pair_for_ability(Ability.ILLUSION)[0] if leader.skills is not None else 0
                )
                opponent_disbelief_bonus = mirror_image_leader_disbelief_bonus(sage_level, illusion_level)
            duel_result = resolve_mirror_image_duel(
                caster, target, opponent_tier, level, rng, opponent_disbelief_bonus=opponent_disbelief_bonus
            )
            if duel_result.winner == "a":
                # The caster disbelieves/slays their own illusion and
                # finishes off the already-mentally-slain opponent.
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if duel_result.winner == "b":
                # The illusion kills the caster; the opponent "revives".
                return _outcome_from(EncounterCombatResult(winner=("b" if target_is_monster else "a"), rounds=0))
            return None

        if spell is Spell.ILLUS_HERO:
            hero = state.leaders.get(VALHALLA_VISITOR_LEADER_ID)
            if hero is None:
                # No confirmed rule for casting this with nobody currently
                # visiting Valhalla -- no effect, same "precondition can't
                # be met" convention as every other spell above.
                return None
            hero_combatant = _leader_combatant(hero)
            if target_is_monster:
                opponent_tier = MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER[monster_species]
                opponent_disbelief_bonus = 0.0
            else:
                opponent_tier = MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT
                sage_level = leader.skills.pair_for_ability(Ability.SAGE)[0] if leader.skills is not None else 0
                illusion_level = (
                    leader.skills.pair_for_ability(Ability.ILLUSION)[0] if leader.skills is not None else 0
                )
                opponent_disbelief_bonus = mirror_image_leader_disbelief_bonus(sage_level, illusion_level)
            # "Unless the alignments of the illusion and the spellcaster
            # are implacably hostile" -- both alignments must be recorded
            # for the check to ever fire; unrecorded (None) defaults to
            # not-hostile, same as every other alignment gate above.
            turns_on_master = (
                hero.alignment is not None
                and leader.alignment is not None
                and illusory_hero_alignments_are_implacably_hostile(hero.alignment, leader.alignment)
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
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if duel_result.winner == "b":
                return _outcome_from(EncounterCombatResult(winner=("b" if target_is_monster else "a"), rounds=0))
            return None

        if spell is Spell.GATE_DEMON:
            # "A Demon may refuse to fight an opponent of Evil to Undead
            # alignment" -- the refusal roll is only even attempted
            # against an eligible opponent (Alignment.EVIL/ANTI_HOLY/
            # UNDEAD, ALIGNMENT_ORDINAL 5-7). A monster target has no
            # persisted alignment anywhere in this project (`models/
            # feature.py Feature` carries none) -- rolled fresh here via
            # `roll_monster_alignment()`, the same real, sourced
            # per-species distribution `models/monster.py` already uses
            # for world generation, rather than guessed or left unusable.
            target_alignment = (
                roll_monster_alignment(monster_species, rng) if target_is_monster else leader.alignment
            )
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
                missile_damage_range=demon_stats.missile_damage
                if demon_stats.missile_damage is not None
                else FIRE_ARROW_DAMAGE_RANGE,
            )
            # "The Demon fights in place of the spellcaster" -- Melee
            # only, the same "mixed tactics/range transitions aren't
            # modeled" scope every duel in this module already carries
            # (`resolve_melee_duel`'s own docstring). The demon's own
            # spellcasting (real per the `SE3__T11.K1` worked example)
            # would need this same CAST-tactic engine recursively --
            # explicitly out of scope, the same "confirmed but not
            # modeled" stance `turn/encounter.py`'s own Phase 202
            # addendum already takes.
            duel_result = resolve_melee_duel(demon, target, rng)
            if duel_result.winner == "a":
                # GATE_DEMON_WINNER_RETURNS_TO_ABYSS -- the caster is
                # credited with the win, same as every other spell above.
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            # GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE -- no
            # direct penalty on the caster; the plan simply continues.
            return None

        if spell is Spell.LAVA_POOL:
            if target_is_monster and monster_species in LAVA_POOL_IMMUNE_MONSTERS:
                return None
            if target_is_monster:
                target_speed = MONSTER_COMBAT_STATS[monster_species].speed
            else:
                # Rulebook [5.6] (already quoted in `turn/encounter.py`'s
                # own module docstring): "medium-speed monsters OR OTHER
                # CHARACTERS is a 50-50 proposition" -- a character
                # target defaults to MEDIUM, the same tier the rulebook's
                # own Flee text already groups characters into.
                target_speed = MonsterSpeed.MEDIUM
            if resolve_lava_pool_escape(target_speed, rng):
                return None  # escaped
            # LAVA_POOL_KILLS_INSTANTLY -- a failed escape is a full kill.
            return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))

        if spell is Spell.AUGUR_COMBAT:
            if not caster_is_leader:
                # Never appears in any real `monster_encounter_plan.py`
                # species plan (the same "not reachable" situation
                # Illusory Hero's own docstring already documents), and
                # no monster has a `Temper` to shirk with -- a documented
                # no-effect, not a guess.
                return None
            if not is_first_tactic:
                # AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER -- "if it
                # comes later, then the result will be an attempt to
                # flee," reusing the exact real Flee mechanic
                # `Maneuver.FLEE` itself already uses.
                if rng.random() < FLEE_CHANCE[stats.speed]:
                    return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
                return None
            if leader.temper is None:
                # No recorded Temper -- no basis to model the courage-
                # gated shirk roll, so (the same "insufficient data, no
                # effect" convention every spell above uses) nothing
                # happens.
                return None
            # "The computer will estimate the percentage chance of
            # victory, if combat were to occur" -- the user's own
            # clarification confirms this is a silent, binary outcome,
            # not a displayed percentage (module docstring's own Phase
            # 205 addendum). Modeled here as one real, throwaway
            # `resolve_melee_duel()` on cloned combatants -- reusing the
            # exact mechanic that would actually decide the encounter,
            # rather than inventing a separate estimator formula. The
            # clones are discarded after reading only the winner; the
            # real `caster`/`target` are untouched.
            simulated_caster = replace(caster)
            simulated_target = replace(target)
            simulated_result = resolve_melee_duel(simulated_caster, simulated_target, rng)
            would_lose_simulated_combat = simulated_result.winner == "b"
            if resolve_augur_combat(would_lose_simulated_combat, leader.temper, rng):
                return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
            return None

        return None

    def _consume_bonus_attacks(attacker: Combatant, defender: Combatant, *, defender_is_monster: bool) -> SearchExecutionResult | None:
        """Phase 209: Psychic Blast's/Ice Suspension's own "bonus attack
        rounds" -- free, unanswered Melee swings, resolved immediately
        after the CAST tactic that granted them. Interpretation, not a
        literal citation: the source text says only "supplementary attack
        rounds," not Melee specifically -- Melee is the natural fit since
        each bonus swing is immediate, unlike Fire Arrow's own separate
        free-attack-count cycle. See module docstring's own Phase 209
        addendum.
        """

        while attacker.bonus_unanswered_attacks > 0:
            attacker.bonus_unanswered_attacks -= 1
            damage = roll_melee_attack(
                rng, damage_range=attacker.melee_damage_range, hit_chance_multiplier=defender.defensive_hit_multiplier
            )
            damage = max(0, damage - attacker.melee_damage_dealt_reduction)
            defender.hit_points -= damage
            if defender.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("a" if defender_is_monster else "b"), rounds=0))
        return None

    def _resolve_cast(tactic, *, caster_is_leader: bool, is_first_tactic: bool = False) -> SearchExecutionResult | None:
        outcome = _resolve_cast_tactic(tactic, caster_is_leader=caster_is_leader, is_first_tactic=is_first_tactic)
        if outcome is not None:
            return outcome
        caster = leader_combatant if caster_is_leader else monster_combatant
        target = monster_combatant if caster_is_leader else leader_combatant
        return _consume_bonus_attacks(caster, target, defender_is_monster=caster_is_leader)

    monster_cast_resolved = False

    def _resolve_monster_casts() -> SearchExecutionResult | None:
        nonlocal monster_cast_resolved
        if monster_cast_resolved:
            return None
        monster_cast_resolved = True
        if monster_plan is None:
            return None
        # Phase 238: walks the guardian's own *full* plan (not the
        # pre-filtered `monster_cast_tactics`) so Augur Combat can know
        # its own true position -- `AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_
        # LATER` needs the real index within the whole plan, not just
        # among its own CAST entries.
        for plan_index, plan_tactic in enumerate(monster_plan):
            if plan_tactic.maneuver is not Maneuver.CAST:
                continue
            outcome = _resolve_cast(plan_tactic, caster_is_leader=False, is_first_tactic=(plan_index == 0))
            if outcome is not None:
                return outcome
        return None

    combat_attempted = False
    fire_arrow_resolved = False
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()

    def _resolve_fire_arrow_phase() -> SearchExecutionResult | None:
        nonlocal fire_arrow_shots, fire_arrow_resolved
        fire_arrow_resolved = True
        outcome = _resolve_monster_casts()
        if outcome is not None:
            return outcome
        duel_result = resolve_fire_arrow_duel(leader_combatant, monster_combatant, rng)
        fire_arrow_shots = duel_result.shots
        outcome = _outcome_from(duel_result)
        if outcome is not None:
            outcome.fire_arrow_shots = fire_arrow_shots
            outcome.guardian_monster = feature.guardian_monster
        return outcome

    def _resolve_steal() -> SearchExecutionResult | None:
        """Steal [ST], rulebook [5.4] -- Phase 239 (``turn/encounter.py``'s
        own Phase 239 addendum has the full quoted rulebook text and every
        formula this calls). Search's target is always the guardian
        monster, never a King/Hero, so only one of the rulebook's three
        caught-thief consequences ever applies here: "si ha un
        combattimento individuale, a una distanza scelta a caso" (personal
        combat at a random range) -- and no ``target_leads_army`` halving
        either, since a guardian monster never commands an army in this
        project's model.
        """

        nonlocal combat_attempted
        cunning = MONSTER_STEAL_CUNNING.get(feature.guardian_monster, StealTargetCunning.AVERAGE)
        if resolve_monster_hides_treasure(cunning, rng):
            return None  # this attempt found nothing -- plan continues
        level = leader.skills.pair_for_ability(Ability.THIEF)[0] if leader.skills is not None else 0
        if resolve_steal_attempt(level, rng):
            return _outcome_from(EncounterCombatResult(winner="a", rounds=0))
        if resolve_steal_evasion(level, rng):
            return None  # failed, but not caught -- plan continues
        # Caught. Spell range has no resolvable outcome (no spell-effect
        # system exists anywhere in this project) -- a documented
        # no-effect, not a silent substitution for one of the other two
        # ranges, the same "unresolvable roll outcome, no guess"
        # convention `_resolve_cast_tactic()`'s own AUGUR_COMBAT branch
        # already uses above.
        combat_range = rng.choice((CombatRange.SPELL_RANGE, CombatRange.BOW_RANGE, CombatRange.MELEE_RANGE))
        if combat_range is CombatRange.SPELL_RANGE:
            return None
        combat_attempted = True
        outcome = _resolve_monster_casts()
        if outcome is not None:
            return outcome
        if combat_range is CombatRange.MELEE_RANGE:
            return _outcome_from(resolve_melee_duel(leader_combatant, monster_combatant, rng))
        duel_result = resolve_fire_arrow_duel(leader_combatant, monster_combatant, rng)
        outcome = _outcome_from(duel_result)
        if outcome is not None:
            outcome.fire_arrow_shots = duel_result.shots
            outcome.guardian_monster = feature.guardian_monster
        return outcome

    def _resolve_talk() -> SearchExecutionResult | None:
        """Talk [TA], rulebook [5.5] -- Phase 240 (``turn/encounter.py``'s
        own Phase 240 addendum has the full quoted rulebook text, the DR
        gate table, and the Attack/Ignore/Deal reaction roll). If the
        leader's own Druid skill doesn't meet the guardian's own
        ``talkdiff`` requirement, no effect -- the character simply can't
        communicate with this species. Attack/Ignore both leave the
        encounter unresolved (the plan's own next tactic decides what
        happens next, same as any other no-effect tactic); Deal ends the
        Search honestly unresolved rather than as a combat win/loss --
        Fulfill's own persistence this would need doesn't exist yet (see
        ``turn/encounter.py``'s own Fulfill addendum).
        """

        druid_level = leader.skills.pair_for_ability(Ability.DRUID)[0] if leader.skills is not None else 0
        if not can_talk_to_monster(feature.guardian_monster, druid_level):
            return None
        caster_is_druidic = leader.alignment is Alignment.DRUID
        reaction = resolve_talk_reaction(rng, caster_is_druidic=caster_is_druidic)
        if reaction is TalkReaction.DEAL:
            return SearchExecutionResult(
                accepted=True,
                combat_resolved=False,
                reason="the guardian proposes a deal -- Fulfill isn't wired yet (see module docstring)",
            )
        return None  # Attack/Ignore -- no special effect, the plan continues

    def _resolve_beg() -> SearchExecutionResult | None:
        """Beg [BE] -- Phase 241, project-original (no Pascal source, no
        rulebook text -- ``turn/encounter.py``'s own Phase 241 addendum
        has the full "why nothing survives" account and the three design
        decisions confirmed directly by the user/project author). Only
        meaningful once the leader has already taken damage this same
        encounter (``leader_combatant.hit_points < CHARACTER_HIT_POINTS``
        -- every combatant starts at the flat rulebook value, so this
        needs no new field); an undamaged leader has nothing to beg
        about, a documented no-effect rather than an oversight. Only
        monsters intelligent enough to understand a plea can grant mercy
        -- reuses ``MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER`` (Phase 187)
        directly, defaulting to ``ANIMAL`` (zero mercy) for any species
        missing from that table, same "can't grant it" treatment as a
        species explicitly mapped there. A successful plea ends the
        Search exactly like a successful Flee.
        """

        if leader_combatant.hit_points >= CHARACTER_HIT_POINTS:
            return None  # undamaged -- nothing to beg about yet
        tier = MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER.get(
            feature.guardian_monster, MirrorImageIntelligenceTier.ANIMAL
        )
        if resolve_beg_for_mercy(tier, rng):
            return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
        return None

    for tactic_index, tactic in enumerate(request.tactics):
        if tactic.maneuver is Maneuver.FLEE:
            if rng.random() < FLEE_CHANCE[stats.speed]:
                return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
            continue
        if tactic.maneuver is Maneuver.CAST:
            outcome = _resolve_cast(tactic, caster_is_leader=True, is_first_tactic=(tactic_index == 0))
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.SHOOT:
            if leader_combatant.blocked_from_cast_and_archery:
                continue
            combat_attempted = True
            outcome = _resolve_fire_arrow_phase()
            if outcome is not None:
                return outcome
            continue  # free attacks exhausted, nobody dead -- fall through
        if tactic.maneuver is Maneuver.MELEE:
            combat_attempted = True
            if monster_wants_shoot and not fire_arrow_resolved:
                outcome = _resolve_fire_arrow_phase()
                if outcome is not None:
                    return outcome
                # nobody died from the guardian's own shots -- fall through to melee
            outcome = _resolve_monster_casts()
            if outcome is not None:
                return outcome
            outcome = _outcome_from(resolve_melee_duel(leader_combatant, monster_combatant, rng))
            # Melee always ends in a winner (max_rounds is only a defensive
            # engineering cap), so `outcome` is never None here in practice.
            result = (
                outcome
                if outcome is not None
                else SearchExecutionResult(accepted=True, combat_resolved=True, winner=None)
            )
            result.fire_arrow_shots = fire_arrow_shots
            result.guardian_monster = feature.guardian_monster
            return result
        if tactic.maneuver is Maneuver.STEAL:
            outcome = _resolve_steal()
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.TALK:
            outcome = _resolve_talk()
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.SAY:
            # Phase 240: "non fa consumare tempo di combattimento" --
            # a documented no-op, not an oversight (see `turn/
            # encounter.py`'s own Phase 240 addendum).
            continue
        if tactic.maneuver is Maneuver.BEG:
            outcome = _resolve_beg()
            if outcome is not None:
                return outcome
            continue
        # Every other maneuver isn't wired -- skip it and keep walking
        # the plan, matching how real Encounter Plans mix wired and
        # unwired tactics (module docstring's own quoted examples). Per
        # spell/reason, confirmed directly by the user (project author):
        # - **Give**: has exactly one real use -- passing an item to
        #   another Hero or King (any realm), never to a monster.
        #   Search's own target is always the guardian monster, so
        #   Give is structurally inapplicable here, not merely
        #   unresearched (Fulfill is the monster-facing counterpart --
        #   see `turn/encounter.py`'s own Phase 240 addendum for why
        #   that stays unwired too).
        # - **Scout**: "non esiste" as a distinct mechanic -- the
        #   pre-combat information-gathering role its own name suggests
        #   is actually served by Talk (Phase 240), not a separate
        #   tactic. Confirmed, not unresearched.
        # - **Use_MI**: needs a magic-item-instance -> spell-effect
        #   mapping this project doesn't model (the same gap
        #   `turn/search_decode.py`'s own docstring already flags for
        #   Cast's sub-object). Confirmed absent, skipped for now on
        #   the user's own direction.

    if combat_attempted:
        # Phase 178: the plan's own tactic list ran out without a winner
        # (only reachable when Fire Arrow exhausted its shots and no
        # further tactic followed) -- default to Melee until someone
        # dies, per the user's own confirmed default. See module
        # docstring's own Phase 178 addendum.
        outcome = _resolve_monster_casts()
        if outcome is not None:
            return outcome
        outcome = _outcome_from(resolve_melee_duel(leader_combatant, monster_combatant, rng))
        result = (
            outcome if outcome is not None else SearchExecutionResult(accepted=True, combat_resolved=True, winner=None)
        )
        result.fire_arrow_shots = fire_arrow_shots
        result.guardian_monster = feature.guardian_monster
        return result
    return SearchExecutionResult(
        accepted=True,
        combat_resolved=False,
        reason="no Melee or Fire Arrow tactic in encounter plan -- see module docstring for what's wired",
    )
