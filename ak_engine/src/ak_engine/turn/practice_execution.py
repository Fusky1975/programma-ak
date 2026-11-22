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

**Roll sequencing -- rewritten with a real source (Phase 449)**:
``AKGEN_reverse_engineering_report (2).md`` SS2/SS6 gives the real,
disassembly-confirmed two-stage model, superseding this module's
original "one threshold roll per attempt" design choice (Phase 44) --
this section previously stated no Pascal source showed the actual
dice-roll site; SS2 does. Every attempt (guaranteed / tied / solo alike)
first rolls the **same** aptitude gate, ``roll_practice_aptitude_gate()``:
``P = 2^-max(0, target_skill - aptitude)``, ``target_skill =
current_skill + 1`` -- identical to this module's own original halving
curve, just no longer scaled by a separate "base chance" first (the real
engine has no such per-context base chance at the gate itself). On gate
**failure**, the existing ``APT_RISE_CHANCE[current_skill]`` aptitude-
increase roll fires (unconditionally, not gated on "aptitude actually
constrained the chance" the way Phase 44's design guessed -- SS2's own
text ties it to "due to rise... but can't", which this module still
reads as requiring ``levels_beyond_aptitude > 0``, so that condition is
kept). On gate **success**, the outcome depends on context: a strictly-
higher-skilled co-practicer present -> the skill rises *immediately*, no
credit involved; otherwise the attempt earns **persistent credit** --
``PRACTICE_CREDIT_TIED_GAIN`` (10) if tied with at least one co-
practicer this phase, ``PRACTICE_CREDIT_SOLO_GAIN`` (5) if practicing
alone -- stored in ``LeaderState.experience_credit``, **one shared
counter per leader, not one per ability** (Phase 456 corrects Phase
449's own per-ability-dict model -- see that field's own docstring for
the exact source quote). Once the leader's own shared credit reaches
``PRACTICE_CREDIT_RISE_THRESHOLD`` (100), *the ability whose attempt
crossed the threshold* rises immediately and 100 is subtracted -- no
second gate roll needed for the threshold-crossing attempt itself.

**Multi-character coordination -- resolved Phase 46, credit model
Phase 449/456**: ``resolve_practice_pair``/``resolve_practice_group``
implement the rulebook's multi-character case (immediate-rise-if-lower /
credit-if-tied, generalized to N >= 2 -- see "Extending to N > 2"
below); ``execute_practice_group`` wraps that with the same
``LeaderState.skills``/``experience_credit`` read/write plumbing
``execute_practice`` uses. **Reachable as of Phase 46** via ``turn/
turn_processor.py run_turn()``, which detects 2+ leaders co-located
(same current province) and Practicing the same ability in the same
phase, and routes them through ``execute_practice_group`` instead of
each dispatching solo -- ``plan_dispatch.py``'s own per-leader
``dispatch_phase`` still can't see this (it has no visibility into
other leaders' same-phase orders), so ``execute_practice`` (wired there)
keeps resolving solo-only when driven directly, same as before -- a
caller going through `run_leader_plan` alone (bypassing `run_turn`)
still gets the conservative solo-only approximation.

**Extending to N > 2 co-practicers** (only relevant to
``resolve_practice_group``, itself only reachable the same way
``resolve_practice_pair`` is): the rulebook's own examples only ever
describe exactly two characters. Generalized here as: if every
practicer shares the same skill level, the tied-credit rule applies to
the whole group; otherwise, whoever sits at the group's *minimum* skill
level gets the immediate-rise-subject-to-aptitude-gate attempt, and
everyone above that minimum gets nothing this phase (no gate roll, no
credit) -- a natural but **undsourced** extension of the two-character
rule, flagged as an interpretation, not a quote; unchanged by Phase 449,
which only replaced *what a successful gate does*, not *who gets to
roll*.

**Why resolvers still take raw ``(skill, aptitude, credit)`` values,
not ``LeaderState`` directly (a deliberate Phase 449 deviation from an
earlier draft of this design)**: ``execute_practice_group()``'s own
comatose gate (Phase 310) must leave a comatose co-practicer's stored
state completely untouched -- skill, aptitude, *and now credit* -- even
though that practicer's *pre-attempt* skill still has to participate in
the group's own tied/minimum comparison. Keeping the resolvers pure
functions of frozen input values (as Phase 46 originally designed them)
lets the comatose gate skip persisting a resolver's output for exactly
one practicer without the resolver ever touching ``LeaderState`` itself
-- writing ``experience_credit`` *inside* the resolver would leak a
comatose practicer's credit mutation before the caller ever gets a
chance to gate it, since the group resolver runs before that gate is
even checked (it needs everyone's frozen pre-attempt skill first).

**The "(unmodified by magic items)" clause is already satisfied, not a
remaining gap** -- stale as of Phase 534 (``turn/discovery_effects.py
ability_bonus_from_items()``/``effective_skill_level()``, item-derived
skill bonuses), which this section predates. Re-checked directly: every
comparison in this module (``execute_practice()``'s solo path,
``execute_practice_group()``'s pairs/triples) reads ``LeaderState.
skills.pair_for_ability()`` -- the raw stored table value -- and never
``effective_skill_level()``. So "one character has a higher skill in
the ability (unmodified by magic items)" is already true by
construction: Practice's own tie/lower comparison was never item-
inclusive in the first place, needing no special-cased override to
strip a magic-item bonus back out. This is unrelated to ``turn/
strength.py``'s own, genuinely different "no magic-item quality
modifier" gap (a *combat*-strength concept, not a skill-comparison
one).

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
  **Phase 644 -- Naval reaches the identical mechanic**: [6.1]'s own
  text, quoted above only in part until now, actually reads "può far
  pratica in Tattica **o Navale** (entrambi i metodi avranno **lo
  stesso effetto** su tutti i tipi di unità militari)" -- Practicing
  Naval triggers this exact same army-training roll, not a parallel
  one, and (like Tactical) no longer raises the leader's own personal
  Naval skill via the ordinary [3.13] path. ``_ARMY_TRAINING_ABILITIES``
  below is the shared trigger set both ``execute_practice()``/
  ``execute_practice_group()`` read; ``execute_practice_tactical()``/
  ``_group()`` keep their own names unchanged.
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

**Phase 449 (persistent credit accumulator, real source)**: rewrites the
skill-rise mechanic itself off ``AKGEN_reverse_engineering_report
(2).md`` SS2/SS6 -- see "Roll sequencing" above for the full formula and
"Why resolvers still take raw values" for why ``LeaderState.
experience_credit`` is written by the ``execute_practice*`` callers, not
by ``resolve_practice_solo``/``_pair``/``_group`` themselves.
``GUARANTEED_PRACTICE_CHANCE``/``TIED_SKILL_PRACTICE_CHANCE``/``SOLO_
PRACTICE_CHANCE`` are removed (the real gate has no such per-context
base chance); ``APT_RISE_CHANCE``/``MAX_SKILL_LEVEL`` are unchanged.

**Phase 456 (corrects the credit field's own shape, real source)**:
``LeaderState.practice_credit`` (a ``dict[int, int]`` keyed by
``Ability.value``) is renamed to ``LeaderState.experience_credit`` (a
bare ``int``) -- AKGEN_reverse_engineering_report (2).md SS2.2's own
words are explicit: "un singolo byte per personaggio, condiviso con
l'esperienza" (a single byte per character, shared with experience),
not one byte per ability. Every credit read/write below now goes
through that one shared counter regardless of which ability the current
Practice attempt is on; see ``turn/experience.py`` (new this phase) for
the other real contributor to this same counter, Add_Experience's own
triangular-distribution gain from non-Practice actions.

**Phase 473 (Professor Whizdumb's own aptitude-gate bonus, real
source)**: ``_select_teacher()`` (Phase 446) deliberately left one piece
of SS20.2/SS2.5 unimplemented -- the Teacher officeholder's own
temporary ``+1`` effective-aptitude bonus to a qualifying student's gate
roll, as opposed to the *merit* credit ``_select_teacher()`` already
handles. This phase closes that gap: ``roll_practice_aptitude_gate()``
and ``_resolve_practice_attempt()`` gain an ``aptitude_bonus`` parameter
(added only to the gate roll's own ``a_eff``, per the source's own
explicit "the natural aptitude byte is never permanently incremented");
``resolve_practice_group()`` gains a parallel ``aptitude_bonuses`` list;
``execute_practice_group()`` computes it via the new
``_teacher_aptitude_bonus()`` helper, off the same pre-attempt ``pairs``
``_select_teacher()`` already builds. Solo Practice (``execute_
practice()``) and the unreachable ``resolve_practice_pair()`` are
untouched -- solo practice has no co-practicer at all, so the
titleholder-presence condition can never fire there.

**Phase 692 (Thief Banditry/Piracy)**: two more magic-college-style
Advanced Abilities with a real, sourced per-Practice-attempt side
effect wired via ``_maybe_raid_as_bandit()`` -- see that function's own
docstring. Fires only from ``execute_practice()`` (solo), never
``execute_practice_group()``, since "no other character is practicing
with him" is exactly what this project's own existing solo/group
dispatch split (``turn/turn_processor.py``) already tells apart.

**Phase 699 (`AdvancedAbility.SUPER_SAGE_I`-`V`)**: a flat +5
percentage-point bonus to ``_roll_sage_device_discovery()``'s own
per-level chance when the practicing Sage is physically at their own
real birth province (``LeaderState.birth_x``/``birth_y``, Phase 505) --
see that function's own Phase 699 addendum. Corrects an earlier
survey's own "needs a new LeaderState field" verdict: the birth
coordinate already existed, just never connected to this ability.

**Phase 770 (`AdvancedAbility.TACTICAL_WARGAMES_MASTERY`)**: corrects a
real mis-wiring from Phase 513, which doubled `turn/aftermath.py
roll_quality_change()`'s own *post-battle* improve chance instead --
the ability's own text says "when Practicing Tactics (or Naval)," and
its own worked example (an Average unit's chance rising to 10%) only
matches doubling `TACTICAL_TRAINING_CHANCE[Quality.AVERAGE] = 0.05`
here, not that other mechanic's own 30% base. See `_wargames_mastery_
multiplier()`'s own citation for the full numeric proof.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from collections.abc import Callable

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.army_type import OVERFLIGHT_AIR, OVERFLIGHT_SEA, ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.office import Office
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.combat import Quality
from ak_engine.turn.exploration import SOCIETY_MAPS_PRACTICE_COUNT_RANGE, receive_society_maps
from ak_engine.turn.tax_base import province_tax_yield
from ak_engine.worldgen.archery_ability_level_schedule import build_archery_ability_level_schedule
from ak_engine.worldgen.druid_ability_level_schedule import build_druid_ability_level_schedule
from ak_engine.worldgen.explorer_ability_level_schedule import build_explorer_ability_level_schedule
from ak_engine.worldgen.melee_ability_level_schedule import build_melee_ability_level_schedule
from ak_engine.worldgen.sage_ability_level_schedule import build_sage_ability_level_schedule
from ak_engine.worldgen.special_ability_level_schedule import MAGIC_COLLEGES, build_magic_ability_level_schedule
from ak_engine.worldgen.spy_ability_level_schedule import build_spy_ability_level_schedule
from ak_engine.worldgen.tactical_ability_level_schedule import build_tactical_ability_level_schedule
from ak_engine.worldgen.thief_ability_level_schedule import build_thief_ability_level_schedule

# CTME.PAS: apt_rise: array[0..10] OF byte = (0,10,25,50,100,80,60,40,20,0,0);
# Indexed by *current* skill level (0-9); indices 9-10 are unreachable
# padding (skill can't exceed 9, CTBOTH.PAS's skillrange = 0..9) but kept
# for an exact, unmodified transcription of the Pascal array.
APT_RISE_CHANCE: tuple[float, ...] = (0.0, 0.10, 0.25, 0.50, 1.0, 0.80, 0.60, 0.40, 0.20, 0.0, 0.0)

# SkillTable's documented range (Phase 21): each pair value is 0-9.
MAX_SKILL_LEVEL = 9

# Phase 449 (AKGEN_reverse_engineering_report (2).md SS2/SS6): a
# successful aptitude-gate roll earns persistent credit toward the same
# ability instead of an immediate rise, unless a strictly-higher-skilled
# co-practicer is present (that case still rises immediately -- no
# credit involved). See module docstring's "Roll sequencing" section.
PRACTICE_CREDIT_SOLO_GAIN = 5
PRACTICE_CREDIT_TIED_GAIN = 10
PRACTICE_CREDIT_RISE_THRESHOLD = 100

# Rulebook [4.3.1] Sageness: "un 5% di probabilita per livello di
# inventare o scoprire qualcosa di utile" -- see module docstring.
SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL = 0.05

# Phase 699: `AdvancedAbility.SUPER_SAGE_I`-`V`'s own real, identical
# text (`models/advanced_ability.py`): "an additional plus 5 when
# researching inventions if he is at his University... the starting
# province of the hero or king." A leader only ever holds one Advanced
# Ability per category (Phase 128), so holding any one of the 5
# mutually-exclusive tiers grants the identical flat bonus -- there is
# no magnitude difference between tiers to model.
SUPER_SAGE_UNIVERSITY_BONUS = 0.05
SUPER_SAGE_ABILITIES = frozenset(
    {
        AdvancedAbility.SUPER_SAGE_I,
        AdvancedAbility.SUPER_SAGE_II,
        AdvancedAbility.SUPER_SAGE_III,
        AdvancedAbility.SUPER_SAGE_IV,
        AdvancedAbility.SUPER_SAGE_V,
    }
)

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

# Phase 770 -- `AdvancedAbility.TACTICAL_WARGAMES_MASTERY`'s own real
# text (`models/advanced_ability.py ADVANCED_ABILITY_DESCRIPTION`):
# "The chance for a unit to increase in quality when Practicing Tactics
# (or Naval) is increased by 100% (example: an Average unit now has a
# 10% chance to improve per phase)." Phase 513 mis-wired this to `turn/
# aftermath.py roll_quality_change()`'s own *post-battle* improve
# chance instead -- for a front-line Average unit that mechanic gives
# 30% (Phase 350's own `60 >> max(0,quality+formation_divisor-2)`
# formula), doubled = 60%, no match to the ability's own worked
# example. Doubling *this* module's own `TACTICAL_TRAINING_CHANCE[
# Quality.AVERAGE] = 0.05` gives exactly 0.10 -- an exact match, and
# this mechanic really is triggered by Practicing Tactics or Naval
# (`_ARMY_TRAINING_ABILITIES` below), the literal phrase in the
# ability's own text. See `turn/aftermath.py roll_quality_change()`'s
# own Phase 770 addendum for the removal on that side.
TACTICAL_WARGAMES_MASTERY_MULTIPLIER = 2.0


def _wargames_mastery_multiplier(state: GameState, leader_id: int) -> float:
    """`TACTICAL_WARGAMES_MASTERY_MULTIPLIER` if the practicing leader
    (``leader_id`` -- the one who issued this Practice order, not an
    army's own commander) holds ``AdvancedAbility.TACTICAL_WARGAMES_
    MASTERY``, else ``1.0``. A personal ability ("The chance... is
    increased"), not a Kingdom- or army-wide one, so this is resolved
    per practicing leader, composed multiplicatively with ``_improved_
    training_multiplier()``'s own per-army title bonus at each call
    site below (a single combined ``min(1.0, ...)`` cap).
    """

    leader = state.leaders.get(leader_id)
    if leader is not None and AdvancedAbility.TACTICAL_WARGAMES_MASTERY in leader.advanced_abilities:
        return TACTICAL_WARGAMES_MASTERY_MULTIPLIER
    return 1.0


# Phase 644 -- [6.1]'s own text: "può far pratica in Tattica o Navale
# (entrambi i metodi avranno lo stesso effetto su tutti i tipi di
# unità militari)" -- Practicing *either* ability triggers the exact
# same army-quality-training mechanic above, not two separate ones.
# Read by both `execute_practice()`/`execute_practice_group()` below;
# `execute_practice_tactical()`/`_group()` keep their own names (the
# one existing, already-tested, already-imported-by-name public entry
# point for this mechanic) even though Naval now reaches them too.
_ARMY_TRAINING_ABILITIES = frozenset({Ability.TACTICAL, Ability.NAVAL})

# Phase 641 -- Royal titles' "Improved Training" bonus (AIR_FORCE/
# PRAETOR/FLAGSHIP, `models/office.py OFFICE_TITLE_DESCRIPTION`,
# verbatim: "when = trains other flying units, their chance to improve
# in quality is doubled, and the chance for non-flying units is
# increased by half" -- identical text for "land"/"naval (Mermen,
# Fleet, Whales)"). `OVERFLIGHT_SEA | {FLEET}` is the exact same
# "naval" category `turn/recruit_execution.py`'s own `is_naval_type`
# already uses; PRAETOR's own "land" is the complement of both.
_TRAINING_TITLE_MATCH: dict[Office, Callable[[ArmyType], bool]] = {
    Office.AIR_FORCE: lambda t: t in OVERFLIGHT_AIR,
    Office.FLAGSHIP: lambda t: t in OVERFLIGHT_SEA or t is ArmyType.FLEET,
    Office.PRAETOR: lambda t: t not in OVERFLIGHT_AIR and t not in OVERFLIGHT_SEA and t is not ArmyType.FLEET,
}


def _improved_training_multiplier(state: GameState, army: ArmyState, pool: list[ArmyState]) -> float:
    """The [6.1] training-chance multiplier for `army`, from whichever of
    the 3 army-scoped Royal Titles (`turn/office_holder.py resolve_army_
    office_holder()`, Phase 394/633) currently has an army present in
    this same training `pool` -- `2.0` if `army`'s own type matches that
    title's category, `1.5` if not, `1.0` if no qualifying title-holder
    is present. The titled army never boosts its own roll ("trains
    *other* ... units"), and a title-holder not part of this pool grants
    nothing (it isn't training *these* armies). Resolved fresh here
    (not `state.army_office_holders`, only a tie-break input, not a
    source of truth -- mirrors `turn/victory_points.py army_office_
    victory_points()`'s own precedent). Takes the best of all 3 offices
    when more than one qualifies, not the first match or an additive
    stack.

    Deferred import (not at module load time) to break a real circular
    import: `turn/office_holder.py` -> `turn/merit_points.py` ->
    `turn/discovery_effects.py` -> this module (for `MAX_SKILL_LEVEL`).
    """

    from ak_engine.turn.office_holder import resolve_army_office_holder

    pool_army_ids = {other.army_id for other in pool}
    best = 1.0
    for office, matches in _TRAINING_TITLE_MATCH.items():
        holder = resolve_army_office_holder(state, office)
        if holder is None or holder.army_id == army.army_id or holder.army_id not in pool_army_ids:
            continue
        best = max(best, 2.0 if matches(army.army_type) else 1.5)
    return best


@dataclass(slots=True)
class PracticeOutcome:
    skill_rose: bool
    aptitude_rose: bool
    new_skill: int
    new_aptitude: int
    # Phase 449/456: the leader's own post-attempt shared experience_
    # credit total, whenever the credit path was actually exercised (a
    # successful gate that wasn't an immediate rise) -- None means the
    # counter is untouched this attempt (immediate rise, failed gate,
    # already-maxed skill, or "not this call's turn to roll" in a group).
    # The caller (execute_practice/execute_practice_group) persists this
    # into LeaderState.experience_credit itself -- see module docstring's
    # "Why resolvers still take raw values" for why the resolvers below
    # never write LeaderState directly.
    new_credit: int | None = None


def roll_practice_aptitude_gate(
    current_skill: int, aptitude: int, rng: random.Random, *, aptitude_bonus: int = 0
) -> bool:
    """The real per-PR aptitude gate (AKGEN_reverse_engineering_report (2).md SS2):
    ``P = 2^-max(0, target_skill - aptitude)``, ``target_skill = current_skill + 1``.

    Rulebook [3.13]: "chance of rising 1 level is halved for each level
    beyond his natural aptitude" -- halved relative to the *target*
    level, per the rulebook's own worked example (aptitude 1: level 1
    unaffected, level 2 halved once, level 3 halved twice, ...). Unlike
    this module's original design (Phase 44), the real gate has no
    separate per-context "base chance" to halve -- every attempt (solo,
    tied, guaranteed-if-lower) rolls against this exact same gate; see
    module docstring's "Roll sequencing" section for what differs by
    context (what a *successful* gate does next).

    ``aptitude_bonus`` (Phase 473): SS2.5's own Professor Whizdumb side
    effect -- "chi pratica con il titolare riceve +1 all'aptitude
    effettiva del gate di quella sessione" (whoever practices with the
    titleholder gets +1 to that session's own effective gate aptitude).
    Applied only to this roll's own ``a_eff`` -- the source is explicit
    that "il byte di aptitude naturale non viene incrementato
    permanentemente" (the natural aptitude byte is never permanently
    incremented), so ``aptitude`` itself, and every other consumer of it
    (the separate SS2.4 aptitude-rise-on-failure check, and the returned
    outcome's own ``new_aptitude``), stay keyed to the unboosted natural
    value -- see ``_teacher_aptitude_bonus()`` for who actually qualifies.
    """

    target_level = current_skill + 1
    levels_beyond_aptitude = max(0, target_level - (aptitude + aptitude_bonus))
    return rng.random() < 1.0 / (2**levels_beyond_aptitude)


def _maybe_raise_aptitude(current_skill: int, aptitude: int, rng: random.Random) -> bool:
    if aptitude >= MAX_SKILL_LEVEL:
        return False
    chance = APT_RISE_CHANCE[min(current_skill, len(APT_RISE_CHANCE) - 1)]
    return rng.random() < chance


def _resolve_practice_attempt(
    current_skill: int,
    aptitude: int,
    credit: int,
    rng: random.Random,
    *,
    immediate_rise: bool,
    credit_delta: int,
    aptitude_bonus: int = 0,
) -> PracticeOutcome:
    """Core per-practicer attempt: aptitude gate, then either an immediate rise,
    persistent credit accumulation (with a threshold-crossing rise), or
    (on gate failure) an aptitude-rise attempt.

    Shared by every practice context (guaranteed-if-lower / tied / solo)
    -- see module docstring's "Roll sequencing" section for the full
    AKGEN-sourced formula this implements. ``aptitude_bonus`` (Phase 473)
    is forwarded to the gate roll only -- see ``roll_practice_aptitude_
    gate()``'s own docstring for why every other use of ``aptitude``
    below stays unboosted.

    **Phase 1189 bug fix**: an already-maxed ability used to short-
    circuit this entire function before ever touching ``credit``, so a
    leader who kept Practicing a skill-9 ability earned *zero* shared
    credit from those attempts -- credit that, per the documented
    shared-``experience_credit``-pool design (Phase 456, this module's
    own docstring), should still be available to push a *different*,
    non-maxed ability over the threshold. The gate still rolls and
    ``credit_delta``/threshold-crossing still apply at max skill, same
    as any other attempt; only the resulting *skill* increment is
    capped (mirroring ``turn/experience.py add_experience()``'s own
    "consume the threshold crossing, but don't raise an already-maxed
    skill" treatment of the identical real cap). The gate-failure
    aptitude-rise attempt stays skipped at max skill, unchanged from
    before -- that part of the original guard was never the bug.
    """

    at_max_skill = current_skill >= MAX_SKILL_LEVEL

    if roll_practice_aptitude_gate(current_skill, aptitude, rng, aptitude_bonus=aptitude_bonus):
        if immediate_rise:
            if at_max_skill:
                return PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude)
            return PracticeOutcome(
                skill_rose=True, aptitude_rose=False, new_skill=current_skill + 1, new_aptitude=aptitude
            )
        new_credit = credit + credit_delta
        if new_credit >= PRACTICE_CREDIT_RISE_THRESHOLD:
            remaining_credit = new_credit - PRACTICE_CREDIT_RISE_THRESHOLD
            if at_max_skill:
                return PracticeOutcome(
                    skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude,
                    new_credit=remaining_credit,
                )
            return PracticeOutcome(
                skill_rose=True,
                aptitude_rose=False,
                new_skill=current_skill + 1,
                new_aptitude=aptitude,
                new_credit=remaining_credit,
            )
        return PracticeOutcome(
            skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude, new_credit=new_credit
        )

    if at_max_skill:
        return PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude)

    levels_beyond_aptitude = max(0, (current_skill + 1) - aptitude)
    if levels_beyond_aptitude > 0 and _maybe_raise_aptitude(current_skill, aptitude, rng):
        return PracticeOutcome(
            skill_rose=False, aptitude_rose=True, new_skill=current_skill, new_aptitude=aptitude + 1
        )

    return PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=current_skill, new_aptitude=aptitude)


def resolve_practice_solo(current_skill: int, aptitude: int, credit: int, rng: random.Random) -> PracticeOutcome:
    """Rulebook [3.13]: "A character who Practices alone has a 5% chance of rising 1 level" --
    Phase 449: real formula is the aptitude gate + PRACTICE_CREDIT_SOLO_GAIN,
    not a flat 5%. See module docstring.
    """

    return _resolve_practice_attempt(current_skill, aptitude, credit, rng, immediate_rise=False, credit_delta=PRACTICE_CREDIT_SOLO_GAIN)


def resolve_practice_pair(
    skill_a: int, aptitude_a: int, credit_a: int, skill_b: int, aptitude_b: int, credit_b: int, rng: random.Random
) -> tuple[PracticeOutcome, PracticeOutcome]:
    """Rulebook [3.13]'s fully-sourced two-character case.

    Not reachable from ``plan_dispatch.py`` -- see module docstring.
    """

    if skill_a == skill_b:
        return (
            _resolve_practice_attempt(skill_a, aptitude_a, credit_a, rng, immediate_rise=False, credit_delta=PRACTICE_CREDIT_TIED_GAIN),
            _resolve_practice_attempt(skill_b, aptitude_b, credit_b, rng, immediate_rise=False, credit_delta=PRACTICE_CREDIT_TIED_GAIN),
        )
    if skill_a < skill_b:
        return (
            _resolve_practice_attempt(skill_a, aptitude_a, credit_a, rng, immediate_rise=True, credit_delta=0),
            PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=skill_b, new_aptitude=aptitude_b),
        )
    return (
        PracticeOutcome(skill_rose=False, aptitude_rose=False, new_skill=skill_a, new_aptitude=aptitude_a),
        _resolve_practice_attempt(skill_b, aptitude_b, credit_b, rng, immediate_rise=True, credit_delta=0),
    )


def resolve_practice_group(
    skills_aptitudes_credits: list[tuple[int, int, int]],
    rng: random.Random,
    *,
    aptitude_bonuses: list[int] | None = None,
) -> list[PracticeOutcome]:
    """Generalizes ``resolve_practice_pair`` to N >= 2 co-practicers -- see module docstring's
    "Extending to N > 2" section for the undsourced generalization this applies.

    Not reachable from ``plan_dispatch.py`` -- see module docstring.

    ``aptitude_bonuses`` (Phase 473, optional, parallel to
    ``skills_aptitudes_credits``): per-practicer ``aptitude_bonus`` for
    ``roll_practice_aptitude_gate()`` -- see ``_teacher_aptitude_bonus()``
    for how ``execute_practice_group()`` computes these from Professor
    Whizdumb's own SS2.5 side effect. Defaults to no bonus for anyone.
    Only ever consumed for a practicer who actually rolls this call (the
    tied branch, or the minimum-skill practicer(s) in the lower-skill
    branch) -- a bonus entry for anyone else is harmless and unused,
    since they get a no-op outcome regardless.
    """

    if len(skills_aptitudes_credits) < 2:
        raise ValueError("resolve_practice_group needs at least 2 co-practicers; use resolve_practice_solo for 1")

    bonuses = aptitude_bonuses if aptitude_bonuses is not None else [0] * len(skills_aptitudes_credits)
    if len(bonuses) != len(skills_aptitudes_credits):
        raise ValueError("aptitude_bonuses must be the same length as skills_aptitudes_credits")

    skills = [skill for skill, _, _ in skills_aptitudes_credits]
    if len(set(skills)) == 1:
        return [
            _resolve_practice_attempt(
                skill, aptitude, credit, rng, immediate_rise=False, credit_delta=PRACTICE_CREDIT_TIED_GAIN, aptitude_bonus=bonus
            )
            for (skill, aptitude, credit), bonus in zip(skills_aptitudes_credits, bonuses)
        ]

    minimum_skill = min(skills)
    outcomes = []
    for (skill, aptitude, credit), bonus in zip(skills_aptitudes_credits, bonuses):
        if skill == minimum_skill:
            outcomes.append(
                _resolve_practice_attempt(skill, aptitude, credit, rng, immediate_rise=True, credit_delta=0, aptitude_bonus=bonus)
            )
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
    # Phase 493: the Advanced Ability (Phase 128) granted this call, if
    # any -- see _maybe_grant_advanced_ability()'s own docstring for the
    # narrow scope (5 of 15 categories currently wired).
    advanced_ability_granted: AdvancedAbility | None = None
    # Phase 510: Society Maps's own "each time he Practices Exploration"
    # trigger -- see _maybe_receive_society_maps()'s own docstring.
    # Empty for every ability other than EXPLORER, and for an EXPLORER
    # practicer who doesn't already own the Advanced Ability.
    society_maps_revealed: tuple[HexCoord, ...] = ()
    # Phase 690: Make Gems Talent's own "each time he practices
    # elemental ability" trigger -- see _maybe_make_gems()'s own
    # docstring. 0 for every ability other than ELEMENTAL, and for an
    # ELEMENTAL practicer who doesn't already own the Advanced Ability.
    gems_gold_gained: int = 0
    # Phase 692: Thief Banditry/Piracy's own "rake in about 15%/50% of
    # the province's tax base for each phase he acts as a bandit/pirate"
    # trigger -- see _maybe_raid_as_bandit()'s own docstring. 0 for
    # every ability other than THIEF, and whenever the conditions
    # (foreign province, matching Advanced Ability, real loot) don't
    # all hold.
    gold_looted_as_bandit: int = 0
    # Phase 853: the real, already-computed "selected teacher" for a
    # genuine group-practice skill rise (`_select_teacher()`, Phase 446,
    # `AKGEN_reverse_engineering_report (2).md` SS20.2) -- previously
    # computed only to credit `Office.TEACHER`'s own merit tally, then
    # discarded before it could also feed `report/turn_report.py
    # render_practice_tutored()`'s own already-sourced, already-tested
    # `_LTeach` narration ("< was tutored by ["), which needs exactly
    # this fact and has never had a real caller supply it. `None` for a
    # solo Practice (`execute_practice()` never sets this field at all),
    # an aptitude-only rise, or a group rise where no co-practicer had
    # strictly higher pre-attempt skill (matching `_select_teacher()`'s
    # own "no teacher when tied" rule).
    teacher_leader_id: int | None = None


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


def commit_pending_skill_advancements(state: GameState) -> None:
    """Applies every leader's ``LeaderState.pending_skill_advancement``
    (set by ``execute_practice()``/``execute_practice_group()``/``turn/
    experience.py add_experience()`` when an attempt raised a skill or
    aptitude) into their real ``SkillTable``, then clears it.

    Sourced from [3.13]: "L'avanzamento avrà effetto fin dalla fase
    successiva" -- a rise earned in phase N must stay invisible to
    anything reading that leader's skill level during phase N itself,
    and only take effect starting phase N+1. ``turn/turn_processor.py
    run_turn()`` calls this once, as the very first statement of its
    phase loop, before that phase dispatches anything -- so a rise
    earned last phase (including the previous turn's own P4, carried
    across the turn boundary by this field deliberately surviving
    ``_replenish_turn_scoped_state()``) is already committed by the time
    anything in the new phase runs. The field is a dict keyed by
    ``Ability`` (Phase 1189) since more than one ability can earn a
    same-phase rise now that Add_Experience also feeds it; every pending
    entry is applied.
    """

    for leader in state.leaders.values():
        if not leader.pending_skill_advancement:
            continue
        skills = _get_or_create_skills(leader)
        for ability, (new_skill, new_aptitude) in leader.pending_skill_advancement.items():
            skills.set_pair_for_ability(ability, new_skill, new_aptitude)
        leader.pending_skill_advancement = {}


def _maybe_grant_advanced_ability(
    state: GameState, leader: LeaderState, ability: Ability, skill_rose: bool, new_skill: int | None
) -> AdvancedAbility | None:
    """Grants the real ``spabord`` Advanced Ability (Phase 128) for a natural skill
    rise. Covers 13 of the 15 ``Ability`` categories now: the 5 magic colleges
    (``MAGIC_COLLEGES``, ``worldgen/special_ability_level_schedule.py``, Phase
    384) and, since Phase 899, Explorer/Tactical/Archery/Melee/Druid/Thief/
    Spy/Sage (``worldgen/explorer_``/``tactical_``/``archery_``/``melee_``/
    ``druid_``/``thief_``/``spy_``/``sage_ability_level_schedule.py``, Phases
    508/899) -- see those modules' own docstrings for each one's real
    ``spabord`` template and, for the 7 Phase 899 categories, the shared
    confidence-level caveat (one worked example each, not independently
    double-anchored the way Explorer/Naval are). ``Ability.MARCH`` has no
    real content to grant (a confirmed zero-cost, no-``IRand`` category) and
    ``Ability.NAVAL`` is granted from a different real trigger entirely
    (``turn/move_execution.py``, not an ordinary Practice skill rise) -- both
    deliberately excluded here, not an oversight.

    Fires only on an actual skill rise (never for an aptitude-only rise --
    ``spabord`` is keyed by natural skill level, and an aptitude rise alone
    never changes it) and only when ``new_skill`` lands on one of the
    schedule's own reachable slots (5-9 in this engine -- ``LEVEL_SLOTS``
    also includes 10, but ``MAX_SKILL_LEVEL`` makes that slot unreachable
    here). Already-granted abilities are added again idempotently (``set``),
    matching every other ``LeaderState.advanced_abilities`` write path.
    """

    if not skill_rose or new_skill is None:
        return None

    if ability in MAGIC_COLLEGES:
        schedule = build_magic_ability_level_schedule(state.game_number)
        granted = schedule[ability].get(new_skill)
    elif ability is Ability.EXPLORER:
        granted = build_explorer_ability_level_schedule(state.game_number).get(new_skill)
    elif ability is Ability.TACTICAL:
        granted = build_tactical_ability_level_schedule(state.game_number).get(new_skill)
    elif ability is Ability.ARCHERY:
        granted = build_archery_ability_level_schedule(state.game_number).get(new_skill)
    elif ability is Ability.MELEE:
        granted = build_melee_ability_level_schedule(state.game_number).get(new_skill)
    elif ability is Ability.DRUID:
        granted = build_druid_ability_level_schedule(state.game_number).get(new_skill)
    elif ability is Ability.THIEF:
        granted = build_thief_ability_level_schedule(state.game_number).get(new_skill)
    elif ability is Ability.SPY:
        granted = build_spy_ability_level_schedule(state.game_number).get(new_skill)
    elif ability is Ability.SAGE:
        granted = build_sage_ability_level_schedule(state.game_number).get(new_skill)
    else:
        return None

    if granted is not None:
        leader.advanced_abilities.add(granted)
    return granted


def _maybe_receive_society_maps(
    state: GameState, leader: LeaderState, ability: Ability, rng: random.Random
) -> tuple[HexCoord, ...]:
    """Society Maps (Advanced Ability -- ``models/advanced_ability.py
    ADVANCED_ABILITY_DESCRIPTION[EXPLORERS_SOCIETY_MAPS]``, Phase 510):
    "Each time he Practices Exploration, he receives 1-3 maps telling
    about new provinces not yet found by your kingdom."

    Fires once per Practice attempt on the Explorer ability specifically
    -- unconditional on whether the skill roll itself succeeds, unlike
    ``_maybe_grant_advanced_ability()`` above, since the rulebook text
    ties this to *practicing*, not to *improving*. Returns ``()``
    immediately for any other ability, for a practicer who doesn't
    already own the Advanced Ability, or for a kingdom-less Hero (no
    "your kingdom" to reveal provinces to). See ``turn/exploration.py
    receive_society_maps()`` for what a "map" actually does to state.
    """

    if ability is not Ability.EXPLORER or AdvancedAbility.EXPLORERS_SOCIETY_MAPS not in leader.advanced_abilities:
        return ()
    if leader.kingdom_id is None:
        return ()

    count = rng.randint(*SOCIETY_MAPS_PRACTICE_COUNT_RANGE)
    return tuple(receive_society_maps(state, leader.kingdom_id, count, rng))


# Phase 690: Make Gems Talent (``models/advanced_ability.py ADVANCED_
# ABILITY_DESCRIPTION[MAKE_GEMS_TALENT]``): "worth between 1-3 gold per
# practice session."
MAKE_GEMS_GOLD_RANGE = (1, 3)


def _maybe_make_gems(state: GameState, leader: LeaderState, ability: Ability, rng: random.Random) -> int:
    """Make Gems Talent (Advanced Ability, Phase 690): "each time the mage
    practices elemental ability (PR EL), he makes gems as a natural
    byproduct of his researches, worth between 1-3 gold per practice
    session."

    Same shape as ``_maybe_receive_society_maps()`` above: fires once per
    Practice attempt on the Elemental ability specifically, unconditional
    on whether the skill roll itself succeeds (the rulebook text ties this
    to *practicing*, not *improving*), for a practicer who already owns
    the Advanced Ability and belongs to a real kingdom (no "byproduct of
    his researches" treasury to credit otherwise). Returns the real gold
    amount credited, or ``0`` when none of those conditions hold.
    """

    if ability is not Ability.ELEMENTAL or AdvancedAbility.MAKE_GEMS_TALENT not in leader.advanced_abilities:
        return 0
    if leader.kingdom_id is None:
        return 0

    amount = rng.randint(*MAKE_GEMS_GOLD_RANGE)
    state.kingdoms[leader.kingdom_id].treasury += amount
    return amount


# Phase 692: Thief Banditry/Piracy (``models/advanced_ability.py
# ADVANCED_ABILITY_DESCRIPTION[THIEF_BANDITRY]``/``[THIEF_PIRACY]``):
# "rake in about 15% of the province's tax base for each phase he acts
# as a bandit" (land) / "snare about 50% of the province's tax value
# for each phase he acts as a pirate" (sea). PIRACY's own "will still
# often loot 1 gold from the treasury of the province owner" in a
# zero-taxation province is treated as unconditional (no formula/chance
# given -- the same "no formula, take the plain reading" convention
# used elsewhere, e.g. turn/skeletal_decay.py) and applies only to
# PIRACY -- BANDITRY's own paragraph never mentions a floor.
BANDITRY_TAX_PERCENT = 0.15
PIRACY_TAX_PERCENT = 0.50
PIRACY_ZERO_TAX_GOLD_FLOOR = 1


def _maybe_raid_as_bandit(state: GameState, leader: LeaderState, ability: Ability, rng: random.Random) -> int:
    """Thief Banditry/Piracy (Advanced Ability, Phase 692): "Whenever he
    practices thievery (the '(PR) TH' action) in another king's land
    province, and no other character is practicing with him, he will
    ravage the countryside as a bandit, robbing and looting the
    population... This action also counts as a normal 'Spy' action in
    all respects." Piracy is the identical mechanic for "another king's
    sea province."

    Same shape as ``_maybe_make_gems()`` above -- fires once per solo
    Practice attempt on the Thief ability specifically, unconditional
    on whether the skill roll itself succeeds. Called only from
    ``execute_practice()`` (never ``execute_practice_group()``), which
    reuses ``turn/turn_processor.py``'s own existing co-location-based
    solo/group split as this project's already-established, "conservative
    solo-only approximation" (see ``turn/practice_execution.py``'s own
    module docstring) for "no other character is practicing with him".

    Re-reading the source text precisely, both paragraphs describe
    looting directly from "the treasury of the province owner" -- an
    immediate Kingdom-to-Kingdom treasury transfer at Practice-time,
    the identical shape already shipped for Make Gems Talent above, not
    a turn-scoped accumulator bridging into ``turn/tax_base.py
    apply_turn_revenue()``'s own once-per-turn credit pass.

    Deliberately narrow reading of "counts as a normal Spy action in
    all respects": credits ``Ability.SPY`` experience on a real loot
    (the fourth member of the real ``Add_Experience`` Spy/Trail/Pursue
    trigger set, ``AKGEN_reverse_engineering_report (2).md`` SS3.4;
    Trail/Pursue are already wired identically) -- does NOT generate a
    full ``SpyReport`` (``turn/aspy_execution.py execute_aspy()``'s own
    much larger scope), a deliberate, documented scope boundary, not a
    silently-dropped feature.

    Looted amount is capped at the victim kingdom's own current
    treasury (never driven negative), the same guard every comparable
    gold-transfer mechanic in this project already applies (e.g.
    ``turn/trade_execution.py``'s own giver/recipient transfer).
    Returns the real amount looted (``0`` when nothing qualifies).
    """

    if ability is not Ability.THIEF or leader.kingdom_id is None:
        return 0

    province = state.provinces.get(leader.location)
    if province is None or province.owner_kingdom_id is None or province.owner_kingdom_id == leader.kingdom_id:
        return 0

    is_sea = province.effective_terrain() is Terrain.SEA
    if is_sea and AdvancedAbility.THIEF_PIRACY not in leader.advanced_abilities:
        return 0
    if not is_sea and AdvancedAbility.THIEF_BANDITRY not in leader.advanced_abilities:
        return 0

    base = province_tax_yield(province) or 0
    amount = round(base * (PIRACY_TAX_PERCENT if is_sea else BANDITRY_TAX_PERCENT))
    if is_sea and amount == 0:
        amount = PIRACY_ZERO_TAX_GOLD_FLOOR

    victim_kingdom = state.kingdoms[province.owner_kingdom_id]
    looted = min(amount, victim_kingdom.treasury)
    victim_kingdom.treasury -= looted
    state.kingdoms[leader.kingdom_id].treasury += looted
    if looted > 0:
        from ak_engine.turn.experience import add_experience

        add_experience(leader, Ability.SPY, 10, rng)
    return looted


DISCOVERY_WORLD_DIFFUSION_KEEP_CHANCE = 0.05

# AKGEN_reverse_engineering_report (2).md SS4.2.1: these two ordinals are
# never selected by ordinary Sage-device research in the real engine --
# only obtainable via starting equipment or trade. Independently
# re-confirmed by ``Desktop/DISCVAL.md`` (2026-09-13, section 4.6): the
# real ``ResearchDiscovery`` resolver (``AK.OVR`` raw ``0x1B18-0x1DE1``)
# jumps straight back to re-proposing whenever candidate=18 or 19, before
# ever reaching the assignment step -- these two are permanently
# unreachable via this resolver, exactly as already modeled here.
DISCOVERY_RESEARCH_EXCLUDED = (Discovery.HIEROGLYPHIC_TRANSLATION, Discovery.SCIENTIFIC_METHOD)

# Defensive, non-authoritative bound guaranteeing _select_discovery_to_grant
# terminates: the real diffusion-bias reroll loop has no documented cap, but
# every retry independently has at least a 5% keep chance, so 200 attempts
# is astronomically more than enough while still being a hard stop.
_DISCOVERY_SELECTION_MAX_ATTEMPTS = 200


def _select_discovery_to_grant(
    state: GameState, kingdom: KingdomState, leader: LeaderState, rng: random.Random
) -> Discovery | None:
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
    everything eligible) or the retry bound is exhausted.

    **Phase 795 addition** (``Desktop/DISCVAL.md`` sections 4.2/15.2-15.3,
    2026-09-13): the real resolver forces its *first* proposal toward
    ``Discovery.ANALYTICAL_PSYCHOLOGY`` (index 28, only when the kingdom
    doesn't already own it) with escalating probability -- 25%/50%/75%/
    100% -- driven by a per-*character* counter (``ldiscp[actor]`` in the
    source), confirmed via ``REPORTS.PAS``'s own Chancellor formula
    (``+2*lfdisc+ldiscp``) cross-referenced against the compiled ``Ofc_
    Pts`` routine. ``ldiscp`` itself is confirmed to increment by 2 on a
    genuine world-first Discovery credited to this same character, and by
    1 on a diffusion/espionage success credited to this same character --
    exactly the two events ``leader.merit_tally.discoveries_found_first``/
    ``.discoveries_via_espionage`` (both already live, per-leader, Phase
    271/267) already track, so ``ldiscp`` is *derived* from them rather
    than stored as a new field -- both counters were already scoped 1:1
    to the same real events DISCVAL independently confirms feed ``ldiscp``.
    ``IRand and 3`` is realized as ``int(rng.random() * 4)`` -- an ordinary
    ``random.Random`` reduction, not ``rng.randrange()`` (whose own
    ``_randbelow`` fallback isn't controllable by this project's own
    ``ScriptedRandom`` test helper, the same fix Phase 656 already made
    for an unrelated formula). Forcing the proposal does **not** bypass the ordinary filters below --
    per section 4.2, Analytical Psychology still has to pass the same
    "already known elsewhere"/``DISCOVERY_WORLD_DIFFUSION_KEEP_CHANCE``
    gate as any other candidate; only which candidate is tried *first*
    changes. Deliberately NOT reproduced: ``ldiscp``'s own reduction on
    death/execution (DISCVAL sections 15.4/16.6/17.4 -- confirmed for at
    least one real trigger, an execution/gallows event this project has
    no matching mechanic for, with other trigger paths left unidentified
    even in the source document itself) and the ``preferExisting`` gate's
    own ``gamevers``-conditional on/off toggle (section 15.1 -- ``gamevers``
    is a global game-version setting this project has never modeled;
    ``DISCOVERY_WORLD_DIFFUSION_KEEP_CHANCE`` applying unconditionally
    already matches the real ``gamevers=5`` case, kept as the documented
    default rather than an unstated one).
    """

    available = [d for d in Discovery if d not in kingdom.discoveries and d not in DISCOVERY_RESEARCH_EXCLUDED]
    if not available:
        return None

    ldiscp = 2 * leader.merit_tally.discoveries_found_first + leader.merit_tally.discoveries_via_espionage
    forced_first: Discovery | None = None
    if Discovery.ANALYTICAL_PSYCHOLOGY in available and ldiscp >= int(rng.random() * 4):
        forced_first = Discovery.ANALYTICAL_PSYCHOLOGY

    for attempt in range(_DISCOVERY_SELECTION_MAX_ATTEMPTS):
        candidate = forced_first if attempt == 0 and forced_first is not None else rng.choice(available)
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

    Phase 699: `SUPER_SAGE_UNIVERSITY_BONUS` (+0.05, "all percentage
    bonuses are cumulative") is added flat when the leader currently
    holds any `SUPER_SAGE_ABILITIES` tier and is physically at their
    own real birth province (`LeaderState.birth_x`/`birth_y`, Phase
    505 -- "the starting province of the hero or king... at Turn 0"),
    the same `HexCoord(leader.birth_x, leader.birth_y)` lookup shape
    `turn/hire_pay.py required_pay()` already established. No new
    state or caller-side plumbing needed -- both the ability and the
    birth coordinate already live on `leader` itself.
    """

    at_university = (
        bool(leader.advanced_abilities & SUPER_SAGE_ABILITIES)
        and leader.birth_x is not None
        and leader.birth_y is not None
        and leader.location == HexCoord(leader.birth_x, leader.birth_y)
    )
    university_bonus = SUPER_SAGE_UNIVERSITY_BONUS if at_university else 0.0
    # The 5% is per level of the Talent as the character really has it: the two
    # Sage Discoveries (Hieroglyphic Translation, Scientific Method) and a held
    # Sage item each add a level, which is their whole purpose.
    from ak_engine.turn.discovery_effects import effective_skill_level

    sage_level = max(current_skill, effective_skill_level(state, leader, Ability.SAGE))
    device_discovered = rng.random() < sage_level * SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL + university_bonus
    discovery_granted: Discovery | None = None
    if device_discovered and leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        if kingdom is not None:
            discovery_granted = _select_discovery_to_grant(state, kingdom, leader, rng)
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

    Phase 770: ``leader_id``'s own ``AdvancedAbility.TACTICAL_WARGAMES_
    MASTERY`` doubles every army's own chance this call (``_wargames_
    mastery_multiplier()``), composed with ``_improved_training_
    multiplier()``'s own per-army title bonus under one combined cap.
    """

    rng = rng if rng is not None else random.Random()

    armies = state.armies_commanded_by(leader_id)
    original_qualities = {army.army_id: army.quality for army in armies}
    wargames_mastery_multiplier = _wargames_mastery_multiplier(state, leader_id)

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
        chance = min(1.0, chance * _improved_training_multiplier(state, army, armies) * wargames_mastery_multiplier)
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

    Phase 770: each army's own chance is doubled only if *that army's
    own practicing leader* (via ``armies_by_leader``, not the wider
    pool) holds ``AdvancedAbility.TACTICAL_WARGAMES_MASTERY`` -- a
    personal ability, not a pool-wide one, so one co-practicer's own
    Mastery doesn't boost another co-practicer's armies.
    """

    rng = rng if rng is not None else random.Random()

    armies_by_leader = {leader_id: state.armies_commanded_by(leader_id) for leader_id in leader_ids}
    pooled_armies = [army for armies in armies_by_leader.values() for army in armies]
    original_qualities = {army.army_id: army.quality for army in pooled_armies}
    practicing_leader_id_by_army_id = {
        army.army_id: leader_id for leader_id, armies in armies_by_leader.items() for army in armies
    }
    wargames_mastery_multiplier_by_leader_id = {
        leader_id: _wargames_mastery_multiplier(state, leader_id) for leader_id in leader_ids
    }

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
        wargames_mastery_multiplier = wargames_mastery_multiplier_by_leader_id[practicing_leader_id_by_army_id[army.army_id]]
        chance = min(1.0, chance * _improved_training_multiplier(state, army, pooled_armies) * wargames_mastery_multiplier)
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
    ``Ability.TACTICAL``/``Ability.NAVAL`` (``_ARMY_TRAINING_ABILITIES``,
    Phase 644) instead route to ``execute_practice_tactical`` -- see
    module docstring for its own, narrower scope.

    **Phase 822 bug fix**: ``turn/plan_dispatch.py``'s own ``_dispatch_
    practice()`` calls this function with no leader-liveness check of
    its own -- the same "a leader who died earlier in the same turn can
    still have a later phase dispatched" gap already fixed for Leave/
    Pick_Up in that module (Phase 821). Previously this had two distinct
    live consequences here, both now closed by one guard: for the
    ``TACTICAL``/``NAVAL`` branch, ``execute_practice_tactical()`` needs
    no ``LeaderState`` at all (only ``state.armies_commanded_by(leader_
    id)``, which doesn't care whether ``leader_id`` still resolves) --
    so a dead leader's own queued Practice order would silently keep
    training their own commanded armies from beyond the grave; for
    every other ability, the acting leader was resolved via a bare
    ``state.leaders[leader_id]`` lookup, raising an unhandled ``KeyError``
    instead (caught by ``run_leader_plan()``'s own top-level ``try``/
    ``except``, so it doesn't crash the whole turn, but still an opaque
    exception rather than the same clean no-op every other dead-leader
    order now produces). Both are now the identical, single "no acting
    leader, nothing happens" result already used for the comatose case
    a few lines below (every field at its own default).
    """

    rng = rng if rng is not None else random.Random()

    if not isinstance(ability, Ability):
        return PracticeExecutionResult(ability=ability, not_implemented_for_ability=True)

    leader = state.leaders.get(leader_id)
    if leader is None:
        return PracticeExecutionResult(ability=ability)

    # 2026-11-21, user-confirmed: Practicing Tactical/Naval trains the
    # leader's armies ([6.1]) AND, like every other Talent, is a [3.13]
    # skill-advancement attempt -- it used to stop after the army training.
    trained_army_ids: tuple[int, ...] = ()
    if ability in _ARMY_TRAINING_ABILITIES:
        trained_army_ids = execute_practice_tactical(state, leader_id, rng)

    if leader.is_comatose:
        # Phase 310: Kill_Enemy's own coma variant ([4.25.2]) -- "non
        # potrà aumentare i talenti con l'esperienza" (cannot raise
        # Talents through experience). Only this direct-storage-read
        # path needs an explicit gate: every other skill-dependent
        # consumer already reads 0 through ``effective_skill_level()``'s
        # own comatose short-circuit -- see LeaderState.is_comatose's
        # own docstring. Ability.TACTICAL/NAVAL never reach this branch
        # (they return above), and rightly so -- training the leader's
        # own *armies* doesn't depend on the leader's own ability.
        return PracticeExecutionResult(ability=ability, trained_army_ids=trained_army_ids)

    skills = _get_or_create_skills(leader)

    current_skill, aptitude = skills.pair_for_ability(ability)
    credit = leader.experience_credit
    outcome = resolve_practice_solo(current_skill, aptitude, credit, rng)
    if outcome.skill_rose or outcome.aptitude_rose:
        # [3.13]: "L'avanzamento avrà effetto fin dalla fase successiva" --
        # deferred to LeaderState.pending_skill_advancement, applied by
        # commit_pending_skill_advancements() at the start of the next
        # phase. See that field's own docstring for the full citation.
        leader.pending_skill_advancement[ability] = (outcome.new_skill, outcome.new_aptitude)
    else:
        skills.set_pair_for_ability(ability, outcome.new_skill, outcome.new_aptitude)
    if outcome.new_credit is not None:
        leader.experience_credit = outcome.new_credit
    # Phase 553 correction: this call site used to clear is_royal_heir
    # the instant any skill/aptitude rise happened here (a project-
    # original reading of RULES.AK [4.21.1]'s "as soon as you... improve
    # any of his abilities by practice"). AKGEN_reverse_engineering_
    # report (5).md SS6.2/SS11.1 shows the real engine instead checks a
    # numeric Total_USkill(leader) < 7 threshold every time it matters
    # (turn/cast_execution.py is_unfinalized_royal_heir()) -- a Heir who
    # trains one ability while still under the threshold stays eligible.
    # No flag mutation belongs here any more; see LeaderState.
    # is_royal_heir's own docstring for the corrected semantics.

    advanced_ability_granted = _maybe_grant_advanced_ability(state, leader, ability, outcome.skill_rose, outcome.new_skill)
    society_maps_revealed = _maybe_receive_society_maps(state, leader, ability, rng)
    gems_gold_gained = _maybe_make_gems(state, leader, ability, rng)
    gold_looted_as_bandit = _maybe_raid_as_bandit(state, leader, ability, rng)

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
        advanced_ability_granted=advanced_ability_granted,
        society_maps_revealed=society_maps_revealed,
        gems_gold_gained=gems_gold_gained,
        gold_looted_as_bandit=gold_looted_as_bandit,
        trained_army_ids=trained_army_ids,
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

    The source's own temporary ``+1`` effective-aptitude bonus the
    Teacher officeholder grants their own qualifying students (SS2.5) --
    a separate effect on the gate roll itself, not this merit formula --
    is implemented in ``_teacher_aptitude_bonus()`` (Phase 473), not
    here: that effect keys off the officeholder simply *qualifying* as a
    candidate for a given student (strictly higher skill), independent
    of who this function ultimately selects as *the* credited teacher
    when several candidates qualify.
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


def _teacher_aptitude_bonus(state: GameState, leader_ids: list[int], pairs: list[tuple[int, int]]) -> list[int]:
    """Phase 473: Professor Whizdumb's (Office.TEACHER) own SS2.5 side effect --

        "Professor Whizdumb: chi pratica con il titolare riceve +1
        all'aptitude effettiva del gate di quella sessione. Il byte di
        aptitude naturale non viene incrementato permanentemente."

    ("whoever practices with the titleholder gets +1 to that session's
    own effective gate aptitude. The natural aptitude byte is never
    permanently incremented.") Returns one ``aptitude_bonus`` entry per
    ``leader_ids``, in order, for ``execute_practice_group()`` to pass
    straight into ``resolve_practice_group()``.

    A practicer at index ``i`` qualifies (bonus ``1``) iff the current
    Office.TEACHER holder is *also* one of this same practice group's
    co-practicers and has strictly higher pre-attempt skill than that
    practicer -- the same "qualifies as a candidate teacher" test
    ``_select_teacher()`` already uses for Merit Points, reused here
    since the source ties both effects to "practicing with a genuinely
    superior titleholder." Deliberately independent of which candidate
    ``_select_teacher()`` ultimately credits for merit when several
    qualify -- the aptitude bonus is a session-wide effect of the
    titleholder's mere qualifying presence, not of being the one
    selected for Merit Points. A titleholder present but *not* strictly
    higher-skilled than a given student (tied or lower) grants that
    student nothing, matching ``_select_teacher()``'s own "no teacher
    when tied" rule. The titleholder never grants themselves a bonus.
    """

    # Deferred import -- see _select_teacher()'s own identical note.
    from ak_engine.turn.office_holder import resolve_office_holder

    holder = resolve_office_holder(state, Office.TEACHER)
    if holder is None or holder.leader_id not in leader_ids:
        return [0] * len(leader_ids)

    holder_index = leader_ids.index(holder.leader_id)
    holder_skill = pairs[holder_index][0]
    return [1 if i != holder_index and holder_skill > pairs[i][0] else 0 for i in range(len(leader_ids))]


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

    if len(leader_ids) < 2:
        raise ValueError("execute_practice_group needs at least 2 leaders; use execute_practice for 1")

    # Phase 1189 bug fix, mirroring Phase 822's identical fix for the solo
    # path above: a co-practicer in this same-phase group can have died
    # earlier this same phase (e.g. a multi-attacker LMOVE battle dispatched
    # before this group's own Practice dispatch, turn/turn_processor.py
    # run_turn()). A bare state.leaders[leader_id] lookup below would raise
    # an unhandled KeyError for the whole call, discarding every surviving
    # co-practicer's own valid outcome too -- not just the dead leader's.
    # Mirror execute_practice()'s own "no acting leader, nothing happens"
    # result for exactly that leader_id, and re-resolve the rest (as a
    # smaller group, or solo if only one survives) instead.
    live_leader_ids = [leader_id for leader_id in leader_ids if leader_id in state.leaders]
    if len(live_leader_ids) < len(leader_ids):
        if len(live_leader_ids) >= 2:
            live_results = execute_practice_group(state, live_leader_ids, ability, rng)
        elif len(live_leader_ids) == 1:
            live_results = [execute_practice(state, live_leader_ids[0], ability, rng)]
        else:
            live_results = []
        live_results_by_id = dict(zip(live_leader_ids, live_results))
        return [live_results_by_id.get(leader_id, PracticeExecutionResult(ability=ability)) for leader_id in leader_ids]

    # Phase 304: army pooling, via execute_practice_tactical_group() -- see
    # that function's own docstring. Phase 644: Naval reaches this same
    # branch too, per [6.1]'s own "same effect" text. 2026-11-21,
    # user-confirmed: this no longer stops here -- every co-practicer also
    # gets the ordinary [3.13] skill-advancement attempt below.
    trained_by_leader: dict[int, tuple[int, ...]] = {}
    if ability in _ARMY_TRAINING_ABILITIES:
        trained_by_leader = execute_practice_tactical_group(state, leader_ids, rng)

    skills_tables = [_get_or_create_skills(state.leaders[leader_id]) for leader_id in leader_ids]
    pairs = [table.pair_for_ability(ability) for table in skills_tables]
    triples = [
        (skill, aptitude, state.leaders[leader_id].experience_credit)
        for leader_id, (skill, aptitude) in zip(leader_ids, pairs)
    ]

    # Phase 473: Professor Whizdumb's +1 effective-aptitude side effect
    # (SS2.5) -- computed off the same pre-attempt pairs _select_teacher()
    # uses for its own, separate merit-crediting decision below.
    aptitude_bonuses = _teacher_aptitude_bonus(state, leader_ids, pairs)
    outcomes = resolve_practice_group(triples, rng, aptitude_bonuses=aptitude_bonuses)

    results = []
    for index, (leader_id, table, outcome, (current_skill, _current_aptitude)) in enumerate(
        zip(leader_ids, skills_tables, outcomes, pairs)
    ):
        leader = state.leaders[leader_id]
        if leader.is_comatose:
            # Phase 310: same comatose gate as execute_practice()'s own --
            # this leader's own real stored skill/aptitude (and, as of
            # Phase 449/456, experience_credit) never changes, regardless of
            # what resolve_practice_group() computed for them; the other
            # co-practicers' own outcomes are unaffected (a documented,
            # unsourced choice -- nothing in [3.13] covers a comatose
            # participant, and there's no reason a partner's own
            # experience should suffer for it). No Sage device roll
            # either, matching execute_practice()'s own comatose short-
            # circuit (it returns before ever reaching that roll).
            results.append(PracticeExecutionResult(ability=ability, trained_army_ids=trained_by_leader.get(leader_id, ())))
            continue
        if outcome.skill_rose or outcome.aptitude_rose:
            # [3.13] "effetto fin dalla fase successiva" -- same deferral
            # as execute_practice()'s own; see that call site's comment.
            leader.pending_skill_advancement[ability] = (outcome.new_skill, outcome.new_aptitude)
        else:
            table.set_pair_for_ability(ability, outcome.new_skill, outcome.new_aptitude)
        if outcome.new_credit is not None:
            leader.experience_credit = outcome.new_credit
        # Phase 553: same removal as execute_practice()'s own -- see that
        # call site's comment for the sourced correction.

        advanced_ability_granted = _maybe_grant_advanced_ability(state, leader, ability, outcome.skill_rose, outcome.new_skill)
        society_maps_revealed = _maybe_receive_society_maps(state, leader, ability, rng)
        gems_gold_gained = _maybe_make_gems(state, leader, ability, rng)

        teacher_id: int | None = None
        if outcome.skill_rose:
            # Phase 446: Teacher merit -- +1 to the selected teacher per
            # real natural skill level gained (never for an aptitude-only
            # rise) -- see _select_teacher()'s own docstring. Phase 853:
            # the same `teacher_id` is now also carried onto this
            # student's own `PracticeExecutionResult` (below), for
            # `report/turn_report.py render_practice_tutored()`'s own
            # real narration -- a second, independent consumer of this
            # one already-computed fact, not a second computation.
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
                advanced_ability_granted=advanced_ability_granted,
                society_maps_revealed=society_maps_revealed,
                gems_gold_gained=gems_gold_gained,
                teacher_leader_id=teacher_id,
                trained_army_ids=trained_by_leader.get(leader_id, ()),
            )
        )
    return results
