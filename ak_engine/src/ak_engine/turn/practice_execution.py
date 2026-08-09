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
  rolling each army's quality tier upward. **Phase 167 implemented two
  transitions** off an incomplete illustrative "e.g." quote in
  ``turn/practice_decode.py`` ("Green->Average 25%, Crack->Elite
  0.2%"), leaving the other three deliberately unmodeled for lack of a
  source. **Phase 263 supplies the missing source**: RULES.AK's own
  [6.1] "Types of Armies" section gives the complete five-tier table
  directly, quoted here in full --

      When an army leader Practices Tactics, he is taking his armies
      on training maneuvers. Those armies may have a chance to rise in
      quality: Depleted => Green: 100%, Green => Average: 25%, Average
      => Veteran: 5%, Veteran => Crack: 1%, Crack => Elite: 0.2%. In
      order for an army to rise to a higher quality, an existing army
      of that quality must be there to train and inspire it. [...] The
      [inspiring] army need not be of the same type as the [training]
      armies. If two leaders Practice Tactics together, their armies
      are pooled into the same training maneuvers.

  ``TACTICAL_TRAINING_CHANCE`` now has all five entries; the existing
  ``execute_practice_tactical()`` gating logic (any *other* army under
  the same leader's command with a strictly higher *original* Quality
  tier, snapshotted before any rolls this call) needed no change at
  all -- it was already generic over whichever tiers the chance table
  happens to list, so the two previously-modeled tiers keep their
  exact prior behavior and the newly-added three simply slot into the
  same mechanism. **Deliberately still out of scope**: the *separate*,
  unconditional "Green and Depleted armies always improve to the next
  level at the end of a turn" rule from the same [6.1] section, a
  turn-boundary rule with no Practice/inspiration precondition at all
  -- distinct from this training-maneuvers table (which requires both
  a Tactical Practice order *and* an inspiring army present even for
  its own Depleted=>Green 100% entry) and confirmed by grep to have no
  existing turn-boundary hook anywhere in this project to attach to,
  the same "no general per-turn reset mechanism yet" situation already
  documented for ``recruited_this_turn``/``ArmyState.movement_points``.
  **Multi-leader army pooling -- closed as of Phase 304**:
  ``execute_practice_tactical_group()`` implements the quoted "if two
  leaders Practice Tactics together, their armies are pooled into the
  same training maneuvers" clause directly -- every army commanded by
  any of the co-practicing leaders (as detected by ``turn/
  turn_processor.py run_turn()``'s own co-location/same-phase grouping,
  Phase 46) is merged into one shared training-and-inspiration pool
  before the per-army roll, instead of each leader's own command being
  gated in isolation. ``execute_practice_group`` now special-cases
  ``Ability.TACTICAL`` to call it instead of returning
  ``not_implemented_for_ability=True`` -- previously, two or more
  co-located leaders who both ordered Practice Tactical the same phase
  got grouped by ``run_turn()``'s general same-ability/same-location
  rule (which doesn't distinguish Tactical from any other ability) and
  then silently trained *nobody at all*, since the group path
  unconditionally refused Tactical while the (bypassed) solo path was
  the only one that ever actually rolled -- worse than the
  single-leader case it was meant to generalize, not just narrower than
  it. Each co-practicer's own ``PracticeExecutionResult.
  trained_army_ids`` still reports only their own armies that trained,
  matching the solo case's own reporting shape -- see that function's
  own docstring for the full design.
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
  **Phase 266 closes the acquisition half of this gap**: when the roll
  succeeds, ``execute_practice()`` now actually grants the practicing
  leader's kingdom a real ``Discovery`` -- ``KingdomState.discoveries``
  (a plain ``set[Discovery]``, matching ``CTBOTH.PAS``'s own ``dknow``
  boolean array exactly, see ``models/game_state.py``). *Which* specific
  Discovery gets granted has no surviving source anywhere (the same
  "missing compiled unit" gap ``turn/merit_points.py``'s own module
  docstring already documents for this exact mechanic) -- the rulebook's
  own worked examples ("You might discover the compass... or create a
  mighty war engine") are flavor text, not a selection rule, and
  ``models/discovery.py``'s own confirmed data (``discval`` is a pure
  *display-order* key, not a difficulty/weight) gives no basis for
  weighting one of the 64 discoveries over another. ``_select_discovery_
  to_grant()`` originally picked uniformly at random among the kingdom's
  not-yet-owned discoveries -- an explicit, unsourced design choice in
  the same category as ``turn/spy_table.py estimate_reported_value()``'s
  own uniform perturbation shape (Phase 265): no information favors any
  other distribution. **Phase 448 supersedes this** with the real
  engine's own selection rule, now sourced via
  ``AKGEN_reverse_engineering_report (2).md`` SS4.2.1 -- see
  ``_select_discovery_to_grant()``'s own docstring for the diffusion-bias
  and permanent-exclusion details. A kingdom that has somehow already
  collected all 64 (exhausted) or a leader with no ``kingdom_id`` (an
  independent Hero -- nowhere to grant a *kingdom*-level Discovery to)
  both leave ``discovery_granted`` at ``None`` while ``device_discovered``
  still reports the roll's own outcome honestly. The discovered device's own
  mechanical effect (``models/discovery.py``'s ability-bonus/anti-spell/
  revenue-bonus data) is now wired into real gameplay too -- see
  ``turn/discovery_effects.py`` (Phase 269, ability bonuses) and ``turn/
  cast_execution.py``'s own Phase 270 addendum (7 of the 16 anti-spell
  Discoveries; the rest documented as blocked at their own call sites).

  **Phase 271 (Chancellor Merit Points, user-specified)**: a successful
  grant here also credits the practicing leader's own ``MeritTally``:
  3 points if ``discovery_granted`` is the very first time *any*
  Kingdom in the game has ever owned it (``GameState.discoveries_
  first_found_by``, written once, permanently), 2 points otherwise --
  see that field's own docstring and ``turn/merit_points.py``'s own
  module docstring for why this figure supersedes the rulebook's own
  printed "+2 per Invention found first."

  **Extended to ``execute_practice_group`` (Phase 396)**: the
  multi-character pooling path resolves a *shared* skill-rise outcome
  across co-practicers via ``resolve_practice_group``, but Sageness's
  own device-discovery roll is a genuinely independent per-*character*
  mechanic -- [4.3.1]'s own text (confirmed directly against
  `Regolamento AK.txt`, not just the Pascal-derived summary above) never
  conditions the 5%-per-level chance on solo-vs-group practice at all,
  only on the practicing character's own current skill level. Rather
  than a guess, this is the same formula already trusted for the solo
  case (extracted into the shared ``_roll_sage_device_discovery()``
  helper both paths now call), applied once per co-practicer off their
  own pre-attempt skill level -- exactly as if each practiced alone. A
  comatose co-practicer's own skill/aptitude and device roll both stay
  untouched (same short-circuit ``execute_practice()`` already applies).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.office import Office
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

# RULES.AK [6.1] "Types of Armies", quoted in full in the module
# docstring's Phase 263 note: the complete training-maneuvers table for
# all five upward Quality transitions.
TACTICAL_TRAINING_CHANCE: dict[Quality, float] = {
    Quality.DEPLETED: 1.0,
    Quality.GREEN: 0.25,
    Quality.AVERAGE: 0.05,
    Quality.VETERAN: 0.01,
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
    # Phase 266: the specific Discovery granted when device_discovered
    # is True and the leader belongs to a kingdom that didn't already
    # own every Discovery -- see module docstring. None whenever
    # device_discovered is False, and also (honestly) when it's True but
    # nothing could be granted (no kingdom, or kingdom already complete).
    discovery_granted: Discovery | None = None


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


DISCOVERY_WORLD_DIFFUSION_KEEP_CHANCE = 0.05

# AKGEN_reverse_engineering_report (2).md SS4.2.1: these two ordinals are
# never selected by ordinary Sage-device research in the real engine --
# only obtainable via starting equipment or trade.
DISCOVERY_RESEARCH_EXCLUDED = (Discovery.HIEROGLYPHIC_TRANSLATION, Discovery.SCIENTIFIC_METHOD)

# Defensive, non-authoritative bound guaranteeing _select_discovery_to_grant
# terminates: the real diffusion-bias reroll loop has no documented cap, but
# every retry independently has at least a 5% keep chance, so 200 attempts
# is astronomically more than enough while still being a hard stop.
_DISCOVERY_SELECTION_MAX_ATTEMPTS = 200


def _select_discovery_to_grant(state: GameState, kingdom: KingdomState, rng: random.Random) -> Discovery | None:
    """Picks a ``Discovery`` the kingdom doesn't already own, per the real engine's
    diffusion-biased selection (AKGEN_reverse_engineering_report (2).md
    SS4.2.1, Phase 448) -- supersedes Phase 266's original uniform-random
    design choice now that a real source is available. Ordinals 18/19
    (``DISCOVERY_RESEARCH_EXCLUDED``) are permanently excluded from ordinary
    research. Among the remaining not-yet-owned discoveries, a candidate
    already owned by *some* Kingdom in the world (``GameState.discoveries_
    first_found_by``) is always kept; a candidate no Kingdom has ever owned
    is kept only 5% of the time (``DISCOVERY_WORLD_DIFFUSION_KEEP_CHANCE``),
    biasing the world toward discoveries that already exist somewhere.
    Returns ``None`` if no eligible discovery remains (kingdom owns
    everything eligible) or the retry bound is exhausted."""

    available = [d for d in Discovery if d not in kingdom.discoveries and d not in DISCOVERY_RESEARCH_EXCLUDED]
    if not available:
        return None

    for _ in range(_DISCOVERY_SELECTION_MAX_ATTEMPTS):
        candidate = rng.choice(available)
        if candidate in state.discoveries_first_found_by:
            return candidate
        if rng.random() < DISCOVERY_WORLD_DIFFUSION_KEEP_CHANCE:
            return candidate
    return None


def _roll_sage_device_discovery(
    state: GameState, leader: LeaderState, current_skill: int, rng: random.Random
) -> tuple[bool, Discovery | None]:
    """Sage's own device-discovery roll ([4.3.1]), independent of the
    ordinary [3.13] skill-rise roll ("on top of, not instead of") --
    ``current_skill`` is the *pre*-attempt level, same reasoning as
    ``execute_practice()``'s own original Phase 171/266 note. Extracted
    (Phase 396) so ``execute_practice_group()`` can reuse it verbatim --
    nothing in the rulebook's own [4.3.1] text conditions this roll on
    solo-vs-group practice at all: the 5%-per-level chance is a pure
    function of the practicing character's own skill level, so each
    co-practicer gets their own independent roll off their own
    pre-attempt level, exactly as if practicing alone. See module
    docstring's own Phase 396 addendum.
    """

    device_discovered = rng.random() < current_skill * SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL
    discovery_granted: Discovery | None = None
    if device_discovered and leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        if kingdom is not None:
            discovery_granted = _select_discovery_to_grant(state, kingdom, rng)
            if discovery_granted is not None:
                kingdom.discoveries.add(discovery_granted)
                # Phase 271 (Chancellor Merit Points, user-specified
                # scoring): see execute_practice()'s own identical note.
                if discovery_granted not in state.discoveries_first_found_by:
                    state.discoveries_first_found_by[discovery_granted] = leader.kingdom_id
                    leader.merit_tally.discoveries_found_first += 1
                else:
                    leader.merit_tally.discoveries_found_not_first += 1
    return device_discovered, discovery_granted


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


def execute_practice_tactical_group(
    state: GameState, leader_ids: list[int], rng: random.Random | None = None
) -> dict[int, tuple[int, ...]]:
    """[6.1]'s own "If two leaders Practice Tactics together, their armies are pooled
    into the same training maneuvers" (Phase 304) -- pools every army
    commanded by *any* of ``leader_ids`` into one shared training-and-
    inspiration pool, instead of gating each leader's own command alone
    the way the single-leader ``execute_practice_tactical()`` does. An
    army is training-eligible under the pooled gate the same way the
    solo case gates it -- some *other* pooled army, regardless of which
    of the co-practicing leaders commands it, sitting at a strictly
    higher *original* (pre-roll, snapshotted once before any roll this
    call) Quality tier -- then rolls independently at its own tier's
    ``TACTICAL_TRAINING_CHANCE``, exactly as the solo case.

    Returns ``{leader_id: trained_army_ids}`` (only that leader's own
    armies) so each co-practicer's own ``PracticeExecutionResult.
    trained_army_ids`` keeps the same "my own commanded armies that
    trained" shape the solo case already reports -- callers never see a
    pooled list mixing another leader's army ids into their own result.
    """

    rng = rng if rng is not None else random.Random()

    armies_by_leader = {leader_id: state.armies_commanded_by(leader_id) for leader_id in leader_ids}
    pooled_armies = [army for armies in armies_by_leader.values() for army in armies]
    original_qualities = {army.army_id: army.quality for army in pooled_armies}

    trained_army_ids: set[int] = set()
    for army in pooled_armies:
        chance = TACTICAL_TRAINING_CHANCE.get(army.quality)
        if chance is None:
            continue
        has_higher_quality_army = any(
            original_qualities[other.army_id] > army.quality for other in pooled_armies if other.army_id != army.army_id
        )
        if not has_higher_quality_army:
            continue
        if rng.random() < chance:
            army.quality = Quality(army.quality + 1)
            trained_army_ids.add(army.army_id)

    return {
        leader_id: tuple(army.army_id for army in armies if army.army_id in trained_army_ids)
        for leader_id, armies in armies_by_leader.items()
    }


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
    if leader.is_comatose:
        # Phase 310: Kill_Enemy's own coma variant ([4.25.2]) -- "non
        # potrà aumentare i talenti con l'esperienza" (cannot raise
        # Talents through experience). Only this direct-storage-read
        # path needs an explicit gate: every other skill-dependent
        # consumer already reads 0 through ``effective_skill_level()``'s
        # own comatose short-circuit -- see LeaderState.is_comatose's
        # own docstring. Ability.TACTICAL never reaches this branch (it
        # returns above), and rightly so -- training the leader's own
        # *armies* doesn't depend on the leader's own ability.
        return PracticeExecutionResult(ability=ability)

    skills = _get_or_create_skills(leader)

    current_skill, aptitude = skills.pair_for_ability(ability)
    outcome = resolve_practice_solo(current_skill, aptitude, rng)
    skills.set_pair_for_ability(ability, outcome.new_skill, outcome.new_aptitude)
    if outcome.skill_rose or outcome.aptitude_rose:
        # Phase 259: RULES.AK [4.21.1] -- a Royal Heir loses the
        # Resurrection-restores-the-old-King option the instant Practice
        # actually raises any of his abilities. See LeaderState.
        # is_royal_heir's own docstring for the full quote and the other
        # (Resurrection-based) way this flag gets consumed.
        leader.is_royal_heir = False

    device_discovered = False
    discovery_granted: Discovery | None = None
    if ability is Ability.SAGE:
        # Independent of the skill-rise roll above ("on top of, not
        # instead of") -- see _roll_sage_device_discovery()'s own
        # docstring for why current_skill (pre-attempt) drives the
        # chance, not outcome.new_skill.
        device_discovered, discovery_granted = _roll_sage_device_discovery(state, leader, current_skill, rng)

    return PracticeExecutionResult(
        ability=ability,
        skill_rose=outcome.skill_rose,
        aptitude_rose=outcome.aptitude_rose,
        new_skill=outcome.new_skill,
        new_aptitude=outcome.new_aptitude,
        device_discovered=device_discovered,
        discovery_granted=discovery_granted,
    )


def _select_teacher(
    state: GameState, leader_ids: list[int], pairs: list[tuple[int, int]], student_index: int
) -> int | None:
    """Phase 446: Professor Whizdumb (Office.TEACHER, id 42) merit's own
    "selected teacher" -- AKGEN_reverse_engineering_report (2).md
    SS20.2. Among this practice group's *other* co-practicers with
    strictly higher *pre-attempt* skill than the student at ``student_
    index``, picks the current Teacher officeholder if they qualify
    (the source's own documented priority), otherwise the candidate with
    the highest pre-attempt skill (ties broken by lowest ``leader_id``,
    an unsourced-but-immaterial tie-break like others in this project).
    Returns ``None`` when no co-practicer has strictly higher skill --
    including the tied-skill case, since no candidate then qualifies at
    all, matching the source's "no teacher when tied" rule without
    needing a special case.

    Deliberately **not** implemented here: the source's own temporary
    ``+1`` effective-aptitude bonus the Teacher officeholder grants their
    own selected session (SS20.2) -- a separate effect on the roll
    itself, not the merit formula, left for a future phase.
    """

    student_skill = pairs[student_index][0]
    candidates = [
        (leader_ids[i], pairs[i][0]) for i in range(len(leader_ids)) if i != student_index and pairs[i][0] > student_skill
    ]
    if not candidates:
        return None

    # Deferred import (same convention as turn/tax_base.py's own resolve_
    # office_holder use): office_holder.py -> merit_points.py -> discovery_
    # effects.py -> practice_execution.py (for MAX_SKILL_LEVEL) is a real
    # circular import at module-load time; a top-level import here breaks it.
    from ak_engine.turn.office_holder import resolve_office_holder

    holder = resolve_office_holder(state, Office.TEACHER)
    if holder is not None:
        for candidate_id, _ in candidates:
            if candidate_id == holder.leader_id:
                return candidate_id

    return max(candidates, key=lambda c: (c[1], -c[0]))[0]


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

    if not isinstance(ability, Ability):
        return [PracticeExecutionResult(ability=ability, not_implemented_for_ability=True) for _ in leader_ids]

    if ability is Ability.TACTICAL:
        # Phase 304: army pooling, via execute_practice_tactical_group() --
        # see that function's own docstring.
        if len(leader_ids) < 2:
            raise ValueError("execute_practice_group needs at least 2 leaders; use execute_practice for 1")
        trained_by_leader = execute_practice_tactical_group(state, leader_ids, rng)
        return [
            PracticeExecutionResult(ability=ability, trained_army_ids=trained_by_leader[leader_id])
            for leader_id in leader_ids
        ]

    if len(leader_ids) < 2:
        raise ValueError("execute_practice_group needs at least 2 leaders; use execute_practice for 1")

    skills_tables = [_get_or_create_skills(state.leaders[leader_id]) for leader_id in leader_ids]
    pairs = [table.pair_for_ability(ability) for table in skills_tables]

    outcomes = resolve_practice_group(pairs, rng)

    results = []
    for index, (leader_id, table, outcome, (current_skill, _current_aptitude)) in enumerate(
        zip(leader_ids, skills_tables, outcomes, pairs)
    ):
        leader = state.leaders[leader_id]
        if leader.is_comatose:
            # Phase 310: same comatose gate as execute_practice()'s own --
            # this leader's own real stored skill/aptitude never changes,
            # regardless of what resolve_practice_group() computed for
            # them; the other co-practicers' own outcomes are unaffected
            # (a documented, unsourced choice -- nothing in [3.13] covers
            # a comatose participant, and there's no reason a partner's
            # own experience should suffer for it). No Sage device roll
            # either, matching execute_practice()'s own comatose short-
            # circuit (it returns before ever reaching that roll).
            results.append(PracticeExecutionResult(ability=ability))
            continue
        table.set_pair_for_ability(ability, outcome.new_skill, outcome.new_aptitude)
        if outcome.skill_rose or outcome.aptitude_rose:
            # Phase 259: same is_royal_heir-clearing rule as execute_practice()'s own.
            leader.is_royal_heir = False

        if outcome.skill_rose:
            # Phase 446: Teacher merit -- +1 to the selected teacher per
            # real natural skill level gained (never for an aptitude-only
            # rise) -- see _select_teacher()'s own docstring.
            teacher_id = _select_teacher(state, leader_ids, pairs, index)
            if teacher_id is not None:
                state.leaders[teacher_id].merit_tally.teaching_interactions += 1

        # Phase 396: Sage's own device-discovery roll, extended to group
        # practice -- see _roll_sage_device_discovery()'s own docstring
        # for why each co-practicer gets an independent roll off their
        # own pre-attempt skill level, the same as if practicing alone.
        device_discovered = False
        discovery_granted: Discovery | None = None
        if ability is Ability.SAGE:
            device_discovered, discovery_granted = _roll_sage_device_discovery(state, leader, current_skill, rng)

        results.append(
            PracticeExecutionResult(
                ability=ability,
                skill_rose=outcome.skill_rose,
                aptitude_rose=outcome.aptitude_rose,
                new_skill=outcome.new_skill,
                new_aptitude=outcome.new_aptitude,
                device_discovered=device_discovered,
                discovery_granted=discovery_granted,
            )
        )
    return results
