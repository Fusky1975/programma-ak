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
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.monster import MONSTER_COMBAT_STATS, MONSTER_NAMES, Monster, MonsterSpeed
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_DAMAGE_RANGE,
    Combatant,
    EncounterCombatResult,
    resolve_fire_arrow_duel,
    resolve_melee_duel,
)
from ak_engine.turn.search_decode import SearchRequest

# Desktop/MOSTRI con statistiche.txt footnote (*): "The Troll regenerates
# 1 hit point every combat round." See turn/encounter.py's own Phase 155
# addendum for the full quote and Combatant.regenerates_hp's own mechanics.
TROLL_REGENERATION_PER_COMBAT_ROUND = 1

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

    def _outcome_from(combat_result: EncounterCombatResult) -> SearchExecutionResult | None:
        """Translate a resolved duel into a terminal result, or None if the
        encounter isn't over yet (only possible for Fire Arrow -- Melee
        always ends in a winner, see resolve_melee_duel's own docstring).
        """

        if combat_result.winner == "a":
            feature.looted = True
            return SearchExecutionResult(accepted=True, combat_resolved=True, winner="leader", feature_looted=True)
        if combat_result.winner == "b":
            state.remove_leader(leader_id)
            return SearchExecutionResult(accepted=True, combat_resolved=True, winner="monster", leader_killed=True)
        return None

    combat_attempted = False
    for tactic in request.tactics:
        if tactic.maneuver is Maneuver.FLEE:
            if rng.random() < FLEE_CHANCE[stats.speed]:
                return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
            continue
        if tactic.maneuver is Maneuver.SHOOT:
            combat_attempted = True
            outcome = _outcome_from(resolve_fire_arrow_duel(leader_combatant, monster_combatant, rng))
            if outcome is not None:
                return outcome
            continue  # free attacks exhausted, nobody dead -- fall through
        if tactic.maneuver is Maneuver.MELEE:
            combat_attempted = True
            outcome = _outcome_from(resolve_melee_duel(leader_combatant, monster_combatant, rng))
            # Melee always ends in a winner (max_rounds is only a defensive
            # engineering cap), so `outcome` is never None here in practice.
            return outcome if outcome is not None else SearchExecutionResult(
                accepted=True, combat_resolved=True, winner=None
            )
        # Every other maneuver (Steal, Talk, Say, Give, Fulfill, Scout,
        # Cast, Use_MI, Beg) isn't wired -- skip it and keep walking the
        # plan, matching how real Encounter Plans mix wired and unwired
        # tactics (module docstring's own quoted examples).

    if combat_attempted:
        return SearchExecutionResult(accepted=True, combat_resolved=True, winner=None)
    return SearchExecutionResult(
        accepted=True,
        combat_resolved=False,
        reason="no Melee or Fire Arrow tactic in encounter plan -- see module docstring for what's wired",
    )
