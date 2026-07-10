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

**Multi-character coordination -- only partially resolved**:
``resolve_practice_pair`` implements the fully-sourced two-character
case (guaranteed-if-lower / 10%-each-if-tied) exactly as the rulebook
states it, and is available for a caller that already has two
co-located same-phase practicers in hand. It is **not** reachable from
``plan_dispatch.py``'s per-leader dispatch, for the same structural
reason ``battle_orchestrator.py fight_multi_attacker_battle`` isn't
auto-invoked from the single-leader execution path: ``run_leader_plan``
resolves one leader's plan at a time against a shared ``GameState``, with
no notion of "wait for every other leader's same-phase order before
resolving this one" -- the rulebook's own core mechanic here needs
exactly that. **``execute_practice`` (the function actually wired into
dispatch) therefore always treats the acting leader as practicing
alone** -- a documented, deliberately conservative approximation: 5% is
the *smallest* of the three base chances the rulebook gives (100%/10%/
5%), so this never overstates a rise chance, only potentially
understates one whenever two+ leaders are genuinely co-practicing.

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
  rolling each army's quality tier upward. A completely different
  mechanic (touches ``ArmyState.quality`` across a leader's whole
  command, with its own "needs an existing higher-tier army present to
  train against" condition and multi-leader pooling) -- **out of scope
  this phase**, flagged as its own future execution phase.
  ``execute_practice`` recognizes ``Ability.TACTICAL`` and returns
  ``PracticeExecutionResult(..., not_implemented_for_ability=True)``
  rather than silently (and wrongly) running the generic skill-rise
  roll against it.
- **Sage** ([4.31]): practicing Sage rolls an *additional*, independent
  "~5% per level of inventing/discovering a device" chance, "on top of
  (not instead of)" the normal [3.13] skill-rise roll -- so Sage's own
  skill *does* rise through the ordinary path here, but the extra
  device-discovery roll is **not** implemented: this project has no
  data model at all for what a discovered device even is or does
  (no item/inventory/effect system exists anywhere in this codebase).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import SkillTable

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


def execute_practice(
    state: GameState, leader_id: int, ability: Ability | int, rng: random.Random | None = None
) -> PracticeExecutionResult:
    """Apply a Practice order to ``state``, mutating the acting leader's ``LeaderState.skills``.

    Always resolves as ``resolve_practice_solo`` -- see module docstring
    for why (multi-character coordination isn't reachable here, and solo
    is a documented, never-overstating lower bound on the real chance).

    ``leader.skills is None`` (no ability data recorded at all -- the
    common case for Heroes, whose starting pairs the move file never
    exposes) is treated as a fresh all-zero ``SkillTable``, the same
    "0 if unrecorded" placeholder convention already used everywhere
    else in this project for missing per-leader ability data (Tactical/
    Naval strength bonus, Druidic shortfall, Cast's success roll). A
    fresh ``SkillTable`` is attached to the leader so this and later
    Practice attempts build on it, rather than staying stuck at the
    placeholder forever.

    ``Ability.TACTICAL`` (and any raw out-of-range ability value that
    failed to decode to a real ``Ability``) is not resolved here -- see
    module docstring -- and returns ``not_implemented_for_ability=True``
    without mutating ``state``.
    """

    rng = rng if rng is not None else random.Random()

    if not isinstance(ability, Ability) or ability is Ability.TACTICAL:
        return PracticeExecutionResult(ability=ability, not_implemented_for_ability=True)

    leader: LeaderState = state.leaders[leader_id]
    if leader.skills is None:
        leader.skills = SkillTable([0] * 30)

    current_skill, aptitude = leader.skills.pair_for_ability(ability)
    outcome = resolve_practice_solo(current_skill, aptitude, rng)
    leader.skills.set_pair_for_ability(ability, outcome.new_skill, outcome.new_aptitude)

    return PracticeExecutionResult(
        ability=ability,
        skill_rose=outcome.skill_rose,
        aptitude_rose=outcome.aptitude_rose,
        new_skill=outcome.new_skill,
        new_aptitude=outcome.new_aptitude,
    )
