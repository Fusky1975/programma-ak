"""Executing a Practice order (rulebook [3.13] Practice Ability), verbatim quoted below.

Unlike most of this project's other "decode-only" gaps, [3.13] is
unusually well-specified -- the rulebook gives exact percentages, and
``HostAK/TP/CTME.PAS`` gives the exact aptitude-rise table as data. What
was actually missing, per ``turn/practice_decode.py``'s own docstring,
was (1) per-leader skill data (resolved by Phase 30's ``LeaderState.
skills``), (2) province-level multi-character coordination, and (3) a
concrete roll-sequencing procedure. This phase resolves (1) fully and
(3) as a documented design choice; (2) is only partially resolved -- see
below.

**[3.13] Practice Ability, quoted in full** (also quoted in
``ak_engine/README.md``):

    If 2 or more characters are in the same province and all characters
    Practice the same ability in a phase, and one character has a
    higher skill in the ability (unmodified by magic items he
    possesses), the character(s) with the lower skill in the ability
    will rise in skill 1 level (provided he has sufficient aptitude,
    explained below.) If the characters have the same skill level,
    there is a 10% chance of rising 1 level for each character. A
    character who Practices alone has a 5% chance of rising 1 level.
    [...] A character's chance of rising 1 level is halved for each
    level beyond his natural aptitude. [...] This applies even when the
    character is learning from a character with a higher level. [...]
    Aptitude may increase if a character is due to rise in level,
    (either from practicing or experience), but can't because of low
    aptitude. The chance of an aptitude increase depends on the current
    skill level: 0: 0%, 1: 10%, 2: 25%, 3: 50%, 4: 100%, 5: 80%, 6: 60%,
    7: 40%, 8: 20%.

That last table matches ``CTME.PAS``'s ``apt_rise: array[0..10] OF byte
= (0,10,25,50,100,80,60,40,20,0,0);`` exactly (indices 9-10 unused --
skill can't exceed 9, ``CTBOTH.PAS``'s ``skillrange = 0..9``).

**Roll sequencing** (design choice, since no Pascal source shows the
actual dice-roll site): for a given attempt at ``base_chance`` (100% /
10% / 5%, before aptitude), compute ``levels_beyond_aptitude =
max(0, (current_skill + 1) - aptitude)``, halve ``base_chance`` that
many times, and roll once against the result -- the same "one threshold
roll per attempt" pattern already used everywhere else in this project
(fanaticism, luck events, Cast's success roll). On failure, **only if
aptitude actually constrained the chance** (``levels_beyond_aptitude >
0`` -- i.e. the character really was "due to rise... but can't because
of low aptitude", not just unlucky on an unconstrained roll), roll a
second time against ``APT_RISE_CHANCE[current_skill]`` for an aptitude
increase instead.

**Multi-character coordination -- now resolved (Phase 46)**:
``resolve_practice_pair``/``resolve_practice_group`` implement the
rulebook's multi-character case (guaranteed-if-lower / 10%-each-if-tied,
generalized to N >= 2 -- see "Extending to N > 2" below);
``execute_practice_group`` wraps that with the same ``LeaderState.
skills`` read/write plumbing ``execute_practice`` uses. **Reachable as
of Phase 46** via ``turn/turn_processor.py run_turn()``, which detects
2+ leaders co-located (same current province) and Practicing the same
ability in the same phase, and routes them through
``execute_practice_group`` instead of each dispatching solo --
``plan_dispatch.py``'s own per-leader ``dispatch_phase`` still can't see
this (it has no visibility into other leaders' same-phase orders), so
``execute_practice`` (wired there) keeps resolving solo-only when driven
directly, same as before -- a caller going through `run_leader_plan`
alone (bypassing `run_turn`) still gets the conservative solo-only
approximation.

**Extending to N > 2 co-practicers** (only relevant to
``resolve_practice_group``, itself only reachable the same way
``resolve_practice_pair`` is): the rulebook's own examples only ever
describe exactly two characters. Generalized here as: if every
practicer shares the same skill level, the 10%-each rule applies to the
whole group; otherwise, whoever sits at the group's *minimum* skill
level gets the guaranteed-subject-to-aptitude roll, and everyone above
that minimum gets nothing this phase -- a natural but **undsourced**
extension of the two-character rule, flagged as an interpretation, not
a quote.

**The magic-item override is not modeled**: "if one character has
higher skill only because of a magic item, both characters have only a
10% chance" can't be evaluated since this project tracks no per-leader
magic-item inventory or skill modifiers at all (the same gap already
flagged wherever magic items come up elsewhere in this project, e.g.
``turn/strength.py``'s quality-modifier list). Every comparison here
uses ``LeaderState.skills``' raw current level, unconditionally.

**Two abilities need special handling** per the rulebook, and this
phase's scope for each:

- **Tactical** ([6.1]): Practicing Tactical does *not* raise personal
  skill via [3.13] at all -- it trains the leader's *armies* instead,
  rolling each army's quality tier upward. **Phase 167 implements the
  two sourced transitions** (``turn/practice_decode.py``'s own quote:
  "Green->Average 25%, Crack->Elite 0.2%") for a single leader's own
  commanded armies (``GameState.armies_commanded_by``), gated on the
  rulebook's own "if a higher-quality army is present to 'train and
  inspire' it" condition -- interpreted here as *any other army under
  that same leader's command* having a strictly higher original
  ``Quality`` tier than the training candidate (checked against a
  snapshot taken before any rolls this call, so results don't depend
  on iteration order). **The other three transitions
  (Depleted->Green, Average->Veteran, Veteran->Crack) are deliberately
  left unmodeled** -- the rulebook gives only these two anchor
  percentages, at opposite ends of a five-step tier ladder, and this
  project's own convention (``win_probability``,
  ``exploration_advantage_multiplier``) only interpolates *between* two
  anchors describing the *same* underlying curve; inventing three more
  percentages for three structurally distinct transitions from two
  unrelated data points would be a materially larger, far less
  constrained guess than any interpolation already accepted elsewhere
  in this project. ``TACTICAL_TRAINING_CHANCE`` only has entries for
  ``Quality.GREEN``/``Quality.CRACK``; an army at any other tier is
  left untouched, honestly, rather than guessed at. **Multi-leader army
  pooling stays out of scope**, same as before: this only trains the
  single dispatching leader's own command, not co-located leaders'
  combined forces the way the generic skill-rise mechanic pools
  co-located *characters* -- flagged as a further future phase, not
  silently expanded into this one. ``execute_practice_group`` (Phase
  46's multi-character pooling entry point) still returns
  ``not_implemented_for_ability=True`` for Tactical unchanged, since
  its own pooling concept (co-located *characters* sharing one
  skill-rise roll) doesn't apply to Tactical's *army*-training
  mechanic at all.
- **Sage / Sageness** ([4.3.1], rulebook's own heading "CONOSCENZA --
  Sageness [SA]"), quoted in full: "Permette la scoperta di nuovi
  strumenti o conoscenze. Quando si fa pratica in questo Talento
  (Practice Sageness) c'e un 5% di probabilita per livello di inventare
  o scoprire qualcosa di utile... Se un personaggio con un livello di
  abilita 4 pratica il Talento Sageness tutte le fasi, in media fara una
  scoperta ogni turno." ("Allows the discovery of new tools or
  knowledge. When practicing this Talent there is a 5% chance per level
  of inventing or discovering something useful... A level-4 character
  Practicing Sageness every phase will average one discovery per turn.")
  This is an *additional*, independent roll -- "on top of (not instead
  of)" the ordinary [3.13] skill-rise roll this module already resolves
  for every ability, Sageness included. **Phase 171 wires the roll
  itself**: ``execute_practice()`` rolls
  ``current_skill * SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL`` (the
  *pre*-attempt skill level -- the rulebook's own worked example uses a
  fixed "level 4" throughout, giving no basis for whether a same-phase
  rise should count towards this roll, so the more conservative,
  already-established level is used) against a fresh
  ``PracticeExecutionResult.device_discovered`` flag, rolled *after* the
  ordinary skill-rise attempt (an unsourced but inconsequential
  ordering choice, since the two rolls are independent either way).
  **What the roll doesn't do**: the discovered *device itself* stays
  entirely unmodeled -- this project has no item/inventory/effect system
  anywhere (the rulebook's own examples, a compass or a war machine,
  need a treasure/magic-item instance this codebase doesn't have --
  same gap ``turn/search_execution.py``'s own [5.9] addendum already
  documents). ``device_discovered=True`` is therefore a flag with no
  further consequence yet, honestly reported rather than silently
  dropped. **Not extended to ``execute_practice_group``**: the
  multi-character pooling path resolves a *shared* skill-rise outcome
  across co-practicers, but Sageness's own device-discovery roll is a
  per-*character* mechanic with no stated interaction with group
  practice at all -- flagged as a further future phase rather than
  guessed at here, the same "don't silently expand scope" precedent
  Phase 167 set for Tactical's own group-pooling gap.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.turn.combat import Quality

# Rulebook [3.13].
SOLO_PRACTICE_CHANCE = 0.05
TIED_SKILL_PRACTICE_CHANCE = 0.10
GUARANTEED_PRACTICE_CHANCE = 1.0

# CTME.PAS: apt_rise: array[0..10] OF byte = (0,10,25,50,100,80,60,40,20,0,0);
# Indexed by *current* skill level (0-9); indices 9-10 are unreachable
# padding (skill can't exceed 9, CTBOTH.PAS's skillrange = 0..9) but kept
# for an exact, unmodified transcription of the Pascal array.
APT_RISE_CHANCE: tuple[float, ...] = (0.0, 0.10, 0.25, 0.50, 1.0, 0.80, 0.60, 0.40, 0.20, 0.0, 0.0)

# SkillTable's documented range (Phase 21): each pair value is 0-9.
MAX_SKILL_LEVEL = 9

# Rulebook [4.3.1] Sageness: "un 5% di probabilita per livello di
# inventare o scoprire qualcosa di utile" -- see module docstring.
SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL = 0.05

# turn/practice_decode.py's own [6.1] quote: "Green->Average 25%,
# Crack->Elite 0.2%" -- the only two of Quality's five upward
# transitions with a real sourced percentage. See module docstring's
# Phase 167 note for why the other three aren't guessed at.
TACTICAL_TRAINING_CHANCE: dict[Quality, float] = {
    Quality.GREEN: 0.25,
    Quality.CRACK: 0.002,
}


@dataclass(slots=True)
class PracticeOutcome:
    skill_rose: bool
    aptitude_rose: bool
    new_skill: int
    new_aptitude: int


def _chance_after_aptitude_halving(base_chance: float, current_skill: int, aptitude: int) -> float:
    """Rulebook: "chance of rising 1 level is halved for each level beyond his natural aptitude."

    Halved relative to the *target* level (``current_skill + 1``), per
    the rulebook's own worked example (aptitude 1: level 1 unaffected,
    level 2 halved once, level 3 halved twice, ...).
    """

    target_level = current_skill + 1
    levels_beyond_aptitude = max(0, target_level - aptitude)
    return base_chance / (2**levels_beyond_aptitude)


def _maybe_raise_aptitude(current_skill: int, aptitude: int, rng: random.Random) -> bool:
    if aptitude >= MAX_SKILL_LEVEL:
        return False
    chance = APT_RISE_CHANCE[min(current_skill, len(APT_RISE_CHANCE) - 1)]
    return rng.random() < chance


def attempt_skill_rise(current_skill: int, aptitude: int, base_chance: float, rng: random.Random) -> PracticeOutcome:
    """Core per-attempt roll: try to rise 1 skill level at ``base_chance`` (aptitude-halved);
    on failure caused by insufficient aptitude, try an aptitude rise instead.

    Shared by every base-chance case (guaranteed / tied / solo) -- see
    module docstring for the full rulebook citation and roll-sequencing
    rationale.
    """

    if current_skill >= MAX_SKILL_LEVEL:
        return PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude)

    levels_beyond_aptitude = max(0, (current_skill + 1) - aptitude)
    final_chance = _chance_after_aptitude_halving(base_chance, current_skill, aptitude)

    if rng.random() < final_chance:
        return PracticeOutcome(
            skill_rose=True, aptitude_rose=False, new_skill=current_skill + 1, new_aptitude=aptitude
        )

    if levels_beyond_aptitude > 0 and _maybe_raise_aptitude(current_skill, aptitude, rng):
        return PracticeOutcome(
            skill_rose=False, aptitude_rose=True, new_skill=current_skill, new_aptitude=aptitude + 1
        )

    return PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude)


def resolve_practice_solo(current_skill: int, aptitude: int, rng: random.Random) -> PracticeOutcome:
    """Rulebook [3.13]: "A character who Practices alone has a 5% chance of rising 1 level."."""

    return attempt_skill_rise(current_skill, aptitude, SOLO_PRACTICE_CHANCE, rng)


def resolve_practice_pair(
    skill_a: int, aptitude_a: int, skill_b: int, aptitude_b: int, rng: random.Random
) -> tuple[PracticeOutcome, PracticeOutcome]:
    """Rulebook [3.13]'s fully-sourced two-character case.

    Not reachable from ``plan_dispatch.py`` -- see module docstring.
    """

    if skill_a == skill_b:
        return (
            attempt_skill_rise(skill_a, aptitude_a, TIED_SKILL_PRACTICE_CHANCE, rng),
            attempt_skill_rise(skill_b, aptitude_b, TIED_SKILL_PRACTICE_CHANCE, rng),
        )
    if skill_a < skill_b:
        return (
            attempt_skill_rise(skill_a, aptitude_a, GUARANTEED_PRACTICE_CHANCE, rng),
            PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=skill_b, new_aptitude=aptitude_b),
        )
    return (
        PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=skill_a, new_aptitude=aptitude_a),
        attempt_skill_rise(skill_b, aptitude_b, GUARANTEED_PRACTICE_CHANCE, rng),
    )


def resolve_practice_group(
    skills_and_aptitudes: list[tuple[int, int]], rng: random.Random
) -> list[PracticeOutcome]:
    """Generalizes ``resolve_practice_pair`` to N >= 2 co-practicers -- see module docstring's
    "Extending to N > 2" section for the undsourced generalization this applies.

    Not reachable from ``plan_dispatch.py`` -- see module docstring.
    """

    if len(skills_and_aptitudes) < 2:
        raise ValueError("resolve_practice_group needs at least 2 co-practicers; use resolve_practice_solo for 1")

    skills = [skill for skill, _ in skills_and_aptitudes]
    if len(set(skills)) == 1:
        return [
            attempt_skill_rise(skill, aptitude, TIED_SKILL_PRACTICE_CHANCE, rng)
            for skill, aptitude in skills_and_aptitudes
        ]

    minimum_skill = min(skills)
    outcomes = []
    for skill, aptitude in skills_and_aptitudes:
        if skill == minimum_skill:
            outcomes.append(attempt_skill_rise(skill, aptitude, GUARANTEED_PRACTICE_CHANCE, rng))
        else:
            outcomes.append(PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=skill, new_aptitude=aptitude))
    return outcomes


@dataclass(slots=True)
class PracticeExecutionResult:
    ability: Ability | int
    skill_rose: bool = False
    aptitude_rose: bool = False
    new_skill: int | None = None
    new_aptitude: int | None = None
    not_implemented_for_ability: bool = False
    # Phase 167: Ability.TACTICAL's own army-training mechanic -- the
    # ids of the practicing leader's own commanded armies whose
    # Quality tier rose this call. Empty (not None) whenever ability
    # isn't TACTICAL, or TACTICAL trained nothing this call.
    trained_army_ids: tuple[int, ...] = ()
    # Phase 171: Ability.SAGE's own device-discovery roll ([4.3.1]) --
    # True only when that independent roll succeeds. Always False for
    # every other ability, and for TACTICAL (which never reaches the
    # skill-rise branch this flag is set in).
    device_discovered: bool = False


def _get_or_create_skills(leader: LeaderState) -> SkillTable:
    """``leader.skills is None`` (no ability data recorded at all -- the common case for
    Heroes, whose starting pairs the move file never exposes) is treated as a
    fresh all-zero ``SkillTable``, the same "0 if unrecorded" placeholder
    convention already used everywhere else in this project for missing
    per-leader ability data (Tactical/Naval strength bonus, Druidic
    shortfall, Cast's success roll). Attached to the leader so this and
    later Practice attempts build on it, rather than staying stuck at the
    placeholder forever.
    """

    if leader.skills is None:
        leader.skills = SkillTable([0] * 30)
    return leader.skills


def execute_practice_tactical(state: GameState, leader_id: int, rng: random.Random | None = None) -> tuple[int, ...]:
    """[6.1]'s army-training mechanic for a single leader's own commanded armies.

    Rolls each ``Quality.GREEN``/``Quality.CRACK`` army under
    ``leader_id``'s command upward, gated on another of that leader's
    armies having a strictly higher *original* (pre-roll) ``Quality``
    tier -- see module docstring for the "train and inspire" condition
    and why the other three tier transitions aren't attempted. Returns
    the ids of every army that actually trained up.
    """

    rng = rng if rng is not None else random.Random()

    armies = state.armies_commanded_by(leader_id)
    original_qualities = {army.army_id: army.quality for army in armies}

    trained_army_ids: list[int] = []
    for army in armies:
        chance = TACTICAL_TRAINING_CHANCE.get(army.quality)
        if chance is None:
            continue
        has_higher_quality_army = any(
            original_qualities[other.army_id] > army.quality for other in armies if other.army_id != army.army_id
        )
        if not has_higher_quality_army:
            continue
        if rng.random() < chance:
            army.quality = Quality(army.quality + 1)
            trained_army_ids.append(army.army_id)

    return tuple(trained_army_ids)


def execute_practice(
    state: GameState, leader_id: int, ability: Ability | int, rng: random.Random | None = None
) -> PracticeExecutionResult:
    """Apply a Practice order to ``state``, mutating the acting leader's ``LeaderState.skills``.

    Always resolves as ``resolve_practice_solo`` -- for the multi-
    character case, see ``execute_practice_group`` (Phase 46), reachable
    from ``turn/turn_processor.py run_turn()`` rather than from this
    single-leader entry point.

    Any raw out-of-range ability value that failed to decode to a real
    ``Ability`` is not resolved here and returns
    ``not_implemented_for_ability=True`` without mutating ``state``.
    ``Ability.TACTICAL`` instead routes to ``execute_practice_tactical``
    -- see module docstring for its own, narrower scope.
    """

    rng = rng if rng is not None else random.Random()

    if not isinstance(ability, Ability):
        return PracticeExecutionResult(ability=ability, not_implemented_for_ability=True)

    if ability is Ability.TACTICAL:
        trained_army_ids = execute_practice_tactical(state, leader_id, rng)
        return PracticeExecutionResult(ability=ability, trained_army_ids=trained_army_ids)

    leader: LeaderState = state.leaders[leader_id]
    skills = _get_or_create_skills(leader)

    current_skill, aptitude = skills.pair_for_ability(ability)
    outcome = resolve_practice_solo(current_skill, aptitude, rng)
    skills.set_pair_for_ability(ability, outcome.new_skill, outcome.new_aptitude)

    device_discovered = False
    if ability is Ability.SAGE:
        # Independent of the skill-rise roll above ("on top of, not
        # instead of") -- see module docstring for why current_skill
        # (pre-attempt) drives the chance, not outcome.new_skill.
        device_discovered = rng.random() < current_skill * SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL

    return PracticeExecutionResult(
        ability=ability,
        skill_rose=outcome.skill_rose,
        aptitude_rose=outcome.aptitude_rose,
        new_skill=outcome.new_skill,
        new_aptitude=outcome.new_aptitude,
        device_discovered=device_discovered,
    )


def execute_practice_group(
    state: GameState, leader_ids: list[int], ability: Ability | int, rng: random.Random | None = None
) -> list[PracticeExecutionResult]:
    """Apply a co-located, same-phase, same-ability Practice order to 2+ leaders at once
    (Phase 46) -- rulebook [3.13]'s fully-sourced/documented-generalized
    multi-character case, via ``resolve_practice_group``.

    Reachable only from a caller that has already verified co-location
    and phase-simultaneity itself -- ``turn/turn_processor.py run_turn()``
    -- this function doesn't check either, only that ``len(leader_ids) >=
    2`` (raises ``ValueError`` otherwise; use ``execute_practice`` for a
    lone practicer). Results are returned in the same order as
    ``leader_ids``.
    """

    rng = rng if rng is not None else random.Random()

    if not isinstance(ability, Ability) or ability is Ability.TACTICAL:
        return [PracticeExecutionResult(ability=ability, not_implemented_for_ability=True) for _ in leader_ids]

    if len(leader_ids) < 2:
        raise ValueError("execute_practice_group needs at least 2 leaders; use execute_practice for 1")

    skills_tables = [_get_or_create_skills(state.leaders[leader_id]) for leader_id in leader_ids]
    pairs = [table.pair_for_ability(ability) for table in skills_tables]

    outcomes = resolve_practice_group(pairs, rng)

    results = []
    for table, outcome in zip(skills_tables, outcomes):
        table.set_pair_for_ability(ability, outcome.new_skill, outcome.new_aptitude)
        results.append(
            PracticeExecutionResult(
                ability=ability,
                skill_rose=outcome.skill_rose,
                aptitude_rose=outcome.aptitude_rose,
                new_skill=outcome.new_skill,
                new_aptitude=outcome.new_aptitude,
            )
        )
    return results
