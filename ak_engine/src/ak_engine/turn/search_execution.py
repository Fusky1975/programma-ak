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

- **Guardian combat stats.** ``models/monster.py MONSTER_STATS`` only
  covers 6 of 61 real monster species (the rulebook's own "Monster
  Table" is explicitly a "partial listing" -- see that module's
  docstring for why the other 55 aren't guessed at). A feature guarded
  by an unlisted species reports ``combat_resolved=False`` with a clear
  reason, rather than inventing stats.
- **Encounter Plan tactic.** ``turn/search_decode.py``'s own docstring
  found, empirically, that "every real Search order ends in Melee
  and/or Scout" across all 12 real Search phases in the sample files.
  Only ``Maneuver.MELEE`` is wired here to a real combat resolution --
  matching the empirically-dominant real case -- while Fire Arrow/Scout
  /Flee/Steal-only plans report ``combat_resolved=False`` rather than
  silently picking a tactic the plan didn't actually request. (Fire
  Arrow specifically is left out for another reason too: [5.2]'s "30% +
  10%/Archery level" hit-chance formula is written for a *character*
  wielding a bow, and nothing in any available source says a monster's
  own ``missile_skill`` drives an equivalent formula -- reusing it
  without a source would be a guess this project avoids, unlike Melee's
  flat, tactic-and-species-independent 50% rule.)
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
from ak_engine.models.monster import MONSTER_NAMES, MONSTER_STATS
from ak_engine.turn.encounter import CHARACTER_HIT_POINTS, Combatant, resolve_melee_duel
from ak_engine.turn.search_decode import SearchRequest


def _leader_combatant(leader: LeaderState) -> Combatant:
    """Same construction as ``challenge_execution.py``'s own private helper (Phase 50),
    duplicated rather than shared -- see that module's own docstring for
    why (a different concept that happens to need the same small lookup).
    Search doesn't have a "Neutral Kingdom" bonus concern the way a
    character-vs-character Encounter does (the bonus is about characters
    aiding each other, [5.0]'s "Order of Duelists" -- not sourced as
    applying against monsters), so it's omitted here rather than guessed.
    """

    melee_skill = 0
    if leader.skills is not None:
        melee_skill = leader.skills.pair_for_ability(Ability.MELEE)[0]
    return Combatant(name=leader.name, hit_points=CHARACTER_HIT_POINTS, melee_skill=melee_skill)


@dataclass(slots=True)
class SearchExecutionResult:
    accepted: bool
    reason: str | None = None
    combat_resolved: bool = False
    winner: str | None = None  # "leader" / "monster" / None (both survived)
    feature_looted: bool = False
    leader_killed: bool = False


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

    stats = MONSTER_STATS.get(feature.guardian_monster)
    if stats is None:
        monster_name = MONSTER_NAMES.get(feature.guardian_monster, "guardian")
        return SearchExecutionResult(
            accepted=True,
            combat_resolved=False,
            reason=f"no sourced combat stats for guardian ({monster_name}) -- see models/monster.py MONSTER_STATS",
        )

    if not any(tactic.maneuver is Maneuver.MELEE for tactic in request.tactics):
        return SearchExecutionResult(
            accepted=True,
            combat_resolved=False,
            reason="no Melee tactic in encounter plan -- only Melee is wired for Search combat (see module docstring)",
        )

    leader_combatant = _leader_combatant(leader)
    monster_combatant = Combatant(
        name=MONSTER_NAMES.get(feature.guardian_monster, "guardian"),
        hit_points=stats.hit_points,
        melee_skill=stats.melee_skill,
        melee_damage_range=stats.melee_damage,
    )

    combat_result = resolve_melee_duel(leader_combatant, monster_combatant, rng)

    if combat_result.winner == "a":
        feature.looted = True
        return SearchExecutionResult(accepted=True, combat_resolved=True, winner="leader", feature_looted=True)
    if combat_result.winner == "b":
        state.remove_leader(leader_id)
        return SearchExecutionResult(accepted=True, combat_resolved=True, winner="monster", leader_killed=True)
    return SearchExecutionResult(accepted=True, combat_resolved=True, winner=None)
