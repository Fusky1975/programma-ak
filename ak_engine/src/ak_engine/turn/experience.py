"""Add_Experience -- the real engine's own non-Practice skill-growth
routine, AKGEN_reverse_engineering_report (2).md SS3, Phase 456.

See ``turn/practice_execution.py``'s own Phase 456 addendum for why
this shares ``LeaderState.experience_credit`` with Practice's own
credit path rather than a separate counter -- SS2.2's own words are
explicit: "un singolo byte per personaggio, condiviso con l'esperienza"
(a single byte per character, shared with experience).

**Core formula** (SS3.3, the compiled ``Add_Experience(leader, ability,
base_points)`` routine at ``104A:1877``):

    if base_points == 100:
        raise_skill_directly_unless_at_max(leader, ability)
        return

    gain = round(base_points * (1 + RandomReal() - RandomReal()))
    experience_credit[leader] += gain
    if experience_credit[leader] >= 100:
        deficit = max(0, skill[leader,ability] + 1 - aptitude[leader,ability])
        if IRand mod (1 << deficit) == 0:
            skill[leader,ability] += 1
        else:
            try_raise_aptitude(leader, ability)
        experience_credit[leader] -= 100

``base_points == 100`` is a sentinel that bypasses the credit counter
entirely and raises the named ability's natural skill directly (unless
already at ``MAX_SKILL_LEVEL``) -- no aptitude gate, no credit change.
Every other ``base_points`` value (SS3.3's own table: 5, 10, or 15 for
the real call sites this project hasn't wired yet, see below) instead
perturbs that base value through **two independent uniform draws**,
``round(base_points * (1 + U1 - U2))`` -- a triangular distribution
centered on ``base_points`` itself, ranging roughly 0 to just under
``2 * base_points`` before rounding -- and adds the result to the
leader's own shared ``experience_credit``, **unconditionally**, no gate
roll gating whether the gain is earned at all (unlike Practice's own
per-attempt gate-first sequencing, SS2.2/SS2.3 -- the two mechanisms
share the same counter and the same two sub-rolls, but in a different
order: Practice gates *before* crediting, Add_Experience credits first
and only gates *at* the threshold crossing).

Once the shared counter reaches >= 100, the *same* aptitude gate
Practice uses (``turn/practice_execution.py roll_practice_aptitude_
gate()``, ``P = 2^-max(0, target_skill - aptitude)``) is rolled once
for the ability whose own attempt crossed the threshold: on success the
skill rises by 1; on failure, the same ``APT_RISE_CHANCE``-driven
aptitude-increase attempt Practice's own gate failure triggers fires
here too (``turn/practice_execution.py _maybe_raise_aptitude()``, reused
directly rather than duplicated). 100 is subtracted from the credit
either way, and -- matching the source's own "non risolve più di una
soglia per chiamata" (never resolves more than one threshold per call)
-- this happens exactly once regardless of how far past 100 a single
call's own gain pushed the counter (in practice this never matters:
``base_points`` tops out at 15 per SS3.3's own observed call sites, so
even the largest possible triangular gain can't cross two full
thresholds in one call).

**A real, documented "occult rule"** (SS3.3's own words): "L'abilità che
riceve il livello è quella dell'evento che porta il contatore a 100...
[e] può far sì che esperienza accumulata in una materia produca il
livello nella successiva materia praticata/usata" (the ability that
receives the level is whichever event's own action pushes the counter
to 100 -- credit earned practicing one ability can produce a level in a
completely different ability practiced/used next). ``turn/practice_
execution.py``'s own Phase 456 test suite already proves this end to
end for two Practice-only abilities; this module's own contribution is
the *other* real source of credit into that same shared counter.

**Stale as of Phase 686 -- wiring status of the ~11 real call sites
SS3.3/SS3.4 name.** This used to frame wiring as entirely "a separate,
considerably larger follow-up." Since then: Spy (Phase 458/461), Thief
(Phase 457), Druid, and all 5 spell schools (Phase 460, ``turn/cast_
execution.py _award_cast_experience()``) were wired; Phase 686 adds
Melee and Archery (both sourced with a clean, unambiguous base of 10 --
see that phase's own README entry for the 6 real call sites); Phase
768 (``MARCH.md`` SS11) adds March and Naval, credited from a
successful Move (``turn/move_execution.py``). **2026-11-22**: the
rulebook's own table ([3.13]) gives the remaining Tactical/Naval and
March/Naval sources outright -- commanding in battle (15% Supreme
Commander, 10% any other commander, Tactical on land / Naval at sea) and
taking or leaving units (5%) -- wired in ``turn/command_experience.py``.
Explorer and Sage remain unwired -- SS3.3's own table marks them
"variabile"/"contestuale," not a clean fixed value, so they stay a real,
separate, still-open item.

**Also deliberately out of scope**: any Royal-Heir/comatose eligibility
gating -- ``turn/practice_execution.py execute_practice()`` applies
those checks at its own call site before ever calling into the shared
gate/credit machinery, and the source names no such gate inside
``Add_Experience`` itself. Every real call site this function will
eventually be wired into (a future phase) sits inside its own action
executor, exactly where that kind of eligibility check belongs -- not
duplicated into this shared formula.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import LeaderState
from ak_engine.turn.practice_execution import (
    MAX_SKILL_LEVEL,
    _get_or_create_skills,
    _maybe_raise_aptitude,
    roll_practice_aptitude_gate,
)

# SS3.3: "sottrae 100 anche dopo un fallimento" -- the same real
# threshold Practice's own PRACTICE_CREDIT_RISE_THRESHOLD names, kept as
# its own constant here since the two modules document two independent
# real call sites into the one shared LeaderState.experience_credit
# counter, not a shared Python symbol.
EXPERIENCE_CREDIT_RISE_THRESHOLD = 100


@dataclass(slots=True)
class ExperienceOutcome:
    skill_rose: bool
    aptitude_rose: bool
    new_skill: int
    new_aptitude: int
    # The leader's own post-call shared experience_credit -- always
    # populated (unlike PracticeOutcome.new_credit's own None-means-
    # untouched convention), since Add_Experience always either touches
    # the counter (non-sentinel path) or bypasses it outright (the
    # base_points==100 sentinel, where the caller's pre-call credit is
    # simply unchanged and reported back here verbatim for a uniform
    # return shape).
    new_credit: int


def add_experience(leader: LeaderState, ability: Ability, base_points: int, rng: random.Random) -> ExperienceOutcome:
    """Applies one real ``Add_Experience`` call to ``leader``'s own
    ``ability`` -- see module docstring for the full sourced formula.

    **Phase 1189 bug fix**: a skill/aptitude rise is deferred into
    ``LeaderState.pending_skill_advancement`` (committed next phase by
    ``turn/practice_execution.py commit_pending_skill_advancements()``)
    rather than written straight into ``leader.skills``, mirroring the
    identical fix ``turn/practice_execution.py execute_practice()`` got
    for the same real rule ([3.13]/SS3.3: a rise "avrà effetto fin dalla
    fase successiva," takes effect starting next phase, not this one).
    Add_Experience shares that same rule and that same field -- several
    real call sites (e.g. ``turn/battle_orchestrator.py``'s own Melee/
    Archery awards from the same battle round) call this repeatedly
    within one phase, and a same-phase rise here was just as visible to
    ``effective_skill_level()`` combat-strength lookups for the rest of
    that phase as the Practice-only gap Phase 822^W1189 (``LeaderState.
    pending_skill_advancement``'s own docstring) already closed.
    ``leader.experience_credit`` is still written immediately -- that
    counter has no "next phase" rule of its own, only the skill/aptitude
    pair it can eventually trigger a rise in.
    """

    skills = _get_or_create_skills(leader)
    current_skill, aptitude = skills.pair_for_ability(ability)

    if base_points == 100:
        if current_skill >= MAX_SKILL_LEVEL:
            return ExperienceOutcome(
                skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude,
                new_credit=leader.experience_credit,
            )
        leader.pending_skill_advancement[ability] = (current_skill + 1, aptitude)
        return ExperienceOutcome(
            skill_rose=True, aptitude_rose=False, new_skill=current_skill + 1, new_aptitude=aptitude,
            new_credit=leader.experience_credit,
        )

    gain = round(base_points * (1 + rng.random() - rng.random()))
    new_credit = leader.experience_credit + gain

    if new_credit < EXPERIENCE_CREDIT_RISE_THRESHOLD:
        leader.experience_credit = new_credit
        return ExperienceOutcome(
            skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude,
            new_credit=new_credit,
        )

    leader.experience_credit = new_credit - EXPERIENCE_CREDIT_RISE_THRESHOLD

    if current_skill >= MAX_SKILL_LEVEL:
        return ExperienceOutcome(
            skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude,
            new_credit=leader.experience_credit,
        )

    if roll_practice_aptitude_gate(current_skill, aptitude, rng):
        leader.pending_skill_advancement[ability] = (current_skill + 1, aptitude)
        return ExperienceOutcome(
            skill_rose=True, aptitude_rose=False, new_skill=current_skill + 1, new_aptitude=aptitude,
            new_credit=leader.experience_credit,
        )

    levels_beyond_aptitude = max(0, (current_skill + 1) - aptitude)
    if levels_beyond_aptitude > 0 and _maybe_raise_aptitude(current_skill, aptitude, rng):
        leader.pending_skill_advancement[ability] = (current_skill, aptitude + 1)
        return ExperienceOutcome(
            skill_rose=False, aptitude_rose=True, new_skill=current_skill, new_aptitude=aptitude + 1,
            new_credit=leader.experience_credit,
        )

    return ExperienceOutcome(
        skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude,
        new_credit=leader.experience_credit,
    )
