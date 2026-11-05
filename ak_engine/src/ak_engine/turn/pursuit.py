"""Pursuit of retreating armies (rulebook [7.3]).

"After the battle, the faster units in the victorious army can pursue and
possibly destroy some of the losing armies. In this pursuit, army speed
is the most important factor in catching the defenders or evading the
pursuers... Generally speaking, about 25% of the victorious infantry and
75% of the cavalry will attempt to pursue the retreating armies.
Especially fast units such as light cavalry and air wings can attempt
more than one pursuit. If a retreating army is unable to fight the
pursuing unit to a standstill in a one-on-one battle, it is destroyed."

**Phase 906 -- full replacement, ``PURSUIT.md`` (2026-09-25, a byte-level
disassembly of the real post-battle pursuit routine: container routine
``AK.OVR`` raw ``0x62B1-0x7A79``, the pursuit loop itself at
``0x6754-0x6C35``).** Supersedes both this module's own original
``select_pursuers()`` (a per-unit probability roll gated by a
project-original ``CAVALRY_TYPES`` classification) and Phase 349's own
``pursuit_destruction_probability(r_p)`` piecewise curve -- neither
survives against the compiled routine, which the user asked be checked
specifically to resolve the open "which army types count as cavalry"
backlog item.

**The premise itself was wrong.** Phase 349 claimed
``INFANTRY_PURSUIT_CHANCE``/``CAVALRY_PURSUIT_CHANCE`` (25%/75%) matched
a compiled constant, "``manual_average_attempt_rate``", from the same
``AK.EXE``/``AK.OVR`` source. ``PURSUIT.md`` traced the real routine from
its own container's prologue to its ``retf`` and found **no such
constant anywhere in it, and no recoverable address for one** -- the
25%/75% figures are RULES.AK's own descriptive, "generally speaking"
manual prose, never a Pascal symbol identified in the binary. There is
no "cavalry" classification in the compiled game at all.

**The real mechanism is a speed comparison, not a probability roll.**
For every unit of the winning side, in the real formation's own position
order (front line of every column first, then every column's second
line, and so on -- ``PURSUIT.md``'s own ``for pos in range(1,71)``
walk), the game makes up to ``max_pursuit_attempts()`` attempts, each
drawing one random unit from the losing side and testing:

    ``r01() + pursuit_effective_speed(pursuer) - front_line_penalty
    - attempt_index > pursuit_effective_speed(target)``

-- ``r01()`` a single fair coin (raw ``0x3B0AD``, ``Trunc(2*Random)``),
``front_line_penalty`` 1 for a front-line pursuer, 0 otherwise, and
``attempt_index`` the number of attempts this same pursuer has already
made this pursuit (0-based). ``pursuit_effective_speed`` is the real
``atspeed`` table (raw ``DS:397E``, ``AK.EXE`` raw ``0x4EDFE-0x4EE26``,
41 bytes, matching ``CTBOTH.PAS`` verbatim) -- see ``PURSUIT_SPEED``
below. A failed attempt (target not caught) simply continues to the next
attempt if the budget allows; a caught target (whether it's then
destroyed or resists, see below) always ends this pursuer's own search.

**Attempt budget, derived and cross-checked against all 41 of
``PURSUIT.md``'s own table rows exactly**: ``max(1, speed -
front_line_penalty - 1)``. E.g. Light Cavalry (speed 4): 2 attempts from
the front line, 3 from the rear; Dragon/Eagle Wing (speed 5): 3/4;
ordinary speed-2 infantry: always exactly 1, front or rear alike. There
is no dedicated "attempts twice" set (this module's old
``MULTI_PURSUIT_TYPES``) -- Light Cavalry and air wings happen to
satisfy the rulebook's own prose ("especially fast units... can attempt
more than one pursuit") only because their real speed is high enough,
not because of a hardcoded list; several other types (Whale League,
Vampires at speed 4; Heavy Cavalry, Chariots, Camels, Warg Riders and
others at speed 3) can also repeat from the rear under this same real
rule.

**Elephants (speed 2) is not cavalry, but Camel Corps and Warg Riders
share the exact same speed (3) as Heavy Cavalry and Chariots** -- there
is no clean 5-item set separating "cavalry" from everything else; it is
all one continuous speed-driven rule. This directly answers the user's
original question.

**Target selection is a documented simplification, not the exact
compiled formula.** The real routine draws a candidate from the losing
side's own fixed-size formation array (`` IRand mod ((IRand mod
bound_from_battle_frame)+1)*W)) )``, redrawing at no attempt cost only
when the drawn slot is empty (a padded-array artifact this project's own
``Column`` lists -- which only ever hold real units -- have no
equivalent of). ``bound_from_battle_frame`` is itself an unnamed,
unconfirmed external field ("la sua definizione semantica non è
necessaria per identificare il confronto", ``PURSUIT.md`` section 3) --
reproducing its exact non-uniform distribution isn't possible without
guessing what it is. This module instead draws uniformly, with
replacement, from the losing side's own still-alive retreating units --
the same category of honest, documented approximation this module's
pre-Phase-906 "how catching is decided" gap already used, just now for a
narrower piece of the mechanism (only the *target draw itself* is
approximated; the catch test, attempt budget and speed table above are
all byte-confirmed).

**An ineligible drawn target still consumes an attempt (no redraw), per
the real routine.** The one target-eligibility rule this project can
actually model -- Whale League can never be pursued outside Sea terrain
(``PURSUIT.md`` section 3, "il tipo grezzo WhaleLeague (13) è escluso
come bersaglio se il terreno esterno non è SEA") -- is checked *after*
the draw; an ineligible draw burns the attempt with no ``r01()`` call,
exactly like the real routine (the other real eligibility bytes --
state flags for "already dead"/an unconfirmed second state value, and a
separate "battle mode 2" unit-type filter -- have no equivalent concept
in this project's own retreat/battle-mode model, so they are not
reachable here; "already destroyed this pursuit sequence" is handled by
simply removing a target from the pool once it's actually destroyed).

**Post-catch combat: a real strength comparison, not a probability
curve.** ``PURSUIT.md`` section 7 traces the block right after a
successful catch (raw ``0x692F-0x6B61``): each side's strength is
computed via the game's own core ``Army_Str`` (the target with the
defender flag and one quality level down, the pursuer with neither --
exactly what this module's own caller, ``turn/battle_orchestrator.py
_apply_pursuit()``, already arranges via ``compute_effective_strength
(..., is_defender=True, base_quality=<one down>)`` for the retreating
side), each then scaled by its own **independent** ``1 + Random``
draw -- not just the pursuer's, correcting this module's own pre-906
assumption that only the pursuer's strength was randomized. The decisive
comparison (raw ``0x6B58/0x6B5D``, ``ja`` on the compare result) is a
plain strict greater-than: the target is destroyed only if the
pursuer's own randomized strength is *strictly* greater than the
target's -- a tie or a stronger target means the target merely resists
(a "standstill"), matching this whole document's own consistent
"strict-greater-than favors the acting/faster side" convention (the
speed catch-test above uses the identical convention). This replaces
Phase 349's ``pursuit_destruction_probability(r_p)`` piecewise curve
entirely -- that curve's own claimed source citation has the same
"never actually recoverable" status as the 25%/75% rates above.

**Deliberately NOT implemented here**, each a genuine, separately
documented gap:

- ``Mod_AType``'s own Fleet(14)->Mermen(16) reclassification for a
  Fleet-type unit owned by a Whales-race (``Race.WHALES``, ordinal 6)
  Kingdom, before the speed lookup (``PURSUIT.md`` section 4/Appendix
  E) -- ``BattleUnit`` carries no owning-Kingdom-race field to test
  against (unlike, say, ``is_humanoid_race``, computed once at
  ``_build_battle_units()`` time for a different, already-wired
  purpose); wiring a new one in for this single narrow case is left for
  a future phase if a Whales-race Fleet-in-pursuit scenario ever turns
  out to matter in practice. ``pursuit_effective_speed()`` always uses
  the unit's own raw ``army_type`` unconverted.
- The "battle mode 2" unit-type filter (``PURSUIT.md`` Appendix F, a
  distinct ``11 <= type <= 16 or type == 21`` gate applied to *both*
  pursuer and target when an external mode field is 2) -- this project
  has no concept of a second battle mode anywhere in its own model;
  every battle here is implicitly the ordinary (mode != 2) case, the
  same "structurally inapplicable" status this project already gives
  Swamp terrain or the Rohan race elsewhere.
- ``Army_Str``'s own internal nemesis check (``models/army_type.py
  NEMESIS``/``is_nemesis_of``, called from inside the real ``Army_Str.
  Str`` per ``NEMESIS.md``'s own citation of the identical function) is
  not reapplied a second time during this module's own post-catch
  combat step -- the pursuer/target strengths reused here are each
  side's already-computed real battle ``effective_strength`` (nemesis
  already resolved once, during the main battle line-up, for whichever
  unit these values came from), not a fresh, pursuit-specific
  pursuer-vs-target ``Army_Str`` recomputation. Reproducing that exactly
  would mean a second, narrower reimplementation of ``turn/strength.py
  compute_effective_strength`` wired specifically to this one-on-one
  pairing; left as a documented simplification rather than expanding
  this phase's own scope further.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.turn.battle_line import BattleUnit, Column

# PURSUIT.md Appendix H (AK.EXE raw 0x4EDFE-0x4EE26, DS:397E, 41 bytes) --
# the real `atspeed` table, matching CTBOTH.PAS. Deliberately its own
# table, not a reuse of `models.army_type.ARMY_TABLE[...].speed` (a
# separate, project-original field for ordinary movement): every value
# below happens to coincide with `ARMY_TABLE`'s own speed for the types
# `ARMY_TABLE` actually covers (a real, independent cross-validation of
# both tables, not a coincidence this module relies on), but `ARMY_TABLE`
# has no entry at all for several real, reachable types this project can
# still put in a battle (`VAMPIRES`, the Vampish special race's own
# native unit -- see `models.army_type.MONSTROUS_ARMY_RACE`), so a direct
# `PURSUIT_SPEED` table, covering every `ArmyType` member this project
# has, is the only complete, dependency-free option.
PURSUIT_SPEED: dict[ArmyType, int] = {
    ArmyType.GARRISON: 1,
    ArmyType.BOWMEN: 2,
    ArmyType.AXEMEN: 2,
    ArmyType.PHALANX: 2,
    ArmyType.LEGION: 2,
    ArmyType.LT_CAVALRY: 4,
    ArmyType.HVY_CAVALRY: 3,
    ArmyType.CHARIOTS: 3,
    ArmyType.ELEPHANTS: 2,
    ArmyType.CAMEL_CORPS: 3,
    ArmyType.WARG_RIDERS: 3,
    ArmyType.DRAGON_WING: 5,
    ArmyType.EAGLE_WING: 5,
    ArmyType.WHALES: 4,
    ArmyType.FLEET: 2,
    ArmyType.MERMEN: 3,
    ArmyType.ENTS: 1,
    ArmyType.TROLLS: 2,
    ArmyType.WEREBEASTS: 3,
    ArmyType.DINOSAURS: 3,
    ArmyType.VAMPIRES: 4,
    ArmyType.MARAUDERS: 3,
    # Ordinals 23-28: catalog-only types this project's own generators
    # never actually create (see `models/army_type.py ARMY_TYPE_
    # BY_ORDINAL`'s own docstring) -- included anyway for a complete,
    # crash-proof table, matching `PURSUIT.md`'s own "Extra" rows (all
    # speed 3) and its own explicit disclaimer that their presence
    # "documenta il binario; non modifica le scelte del progetto".
    ArmyType.SHAMANS: 3,
    ArmyType.CROSSBOW: 3,
    ArmyType.JAVELINS: 3,
    ArmyType.ARTILLERY: 3,
    ArmyType.SPIDERS: 3,
    ArmyType.D_TURTLE: 3,
}


def pursuit_effective_speed(army_type: ArmyType) -> int:
    """The real ``atspeed`` lookup -- see ``PURSUIT_SPEED``'s own docstring."""

    return PURSUIT_SPEED[army_type]


def max_pursuit_attempts(army_type: ArmyType, *, is_front_line: bool) -> int:
    """``max(1, speed - front_line_penalty - 1)`` -- see module docstring's
    own derivation, cross-checked against all 41 of ``PURSUIT.md``'s own
    table rows exactly.
    """

    front_line_penalty = 1 if is_front_line else 0
    return max(1, pursuit_effective_speed(army_type) - front_line_penalty - 1)


def draw_pursuit_r01(rng: random.Random) -> int:
    """``R01``: a single fair coin, ``Trunc(2*Random)`` (``PURSUIT.md``
    Appendix G, ``AK.EXE`` raw ``0x3B0AD``) -- 0 or 1, equiprobable.
    """

    return int(2 * rng.random())


def pursuit_catch_succeeds(
    pursuer_type: ArmyType, attempt_index: int, target_type: ArmyType, rng: random.Random, *, is_front_line: bool
) -> bool:
    """The real catch test (``PURSUIT.md`` section 3, raw ``0x6916-0x692C``):
    ``r01() + speed(pursuer) - front_line_penalty - attempt_index >
    speed(target)``. Always consumes exactly one ``r01()`` draw -- callers
    only reach this once a target has already been drawn and found
    eligible (see ``resolve_pursuit``).
    """

    front_line_penalty = 1 if is_front_line else 0
    s = pursuit_effective_speed(pursuer_type) - front_line_penalty - attempt_index
    return draw_pursuit_r01(rng) + s > pursuit_effective_speed(target_type)


def pursuit_target_eligible(target_type: ArmyType, terrain: Terrain) -> bool:
    """The one real target-eligibility rule this project can model
    (``PURSUIT.md`` section 3): Whale League can never be pursued outside
    Sea terrain. See module docstring for the other real filters this
    project has no equivalent concept for.
    """

    return not (target_type is ArmyType.WHALES and terrain is not Terrain.SEA)


def draw_pursuit_random_multiplier(rng: random.Random) -> float:
    """The real ``1 + Random`` post-catch strength scaling (``PURSUIT.md``
    section 7, an independent draw per side): ``U[1,2)``.
    """

    return rng.uniform(1.0, 2.0)


@dataclass(slots=True)
class PursuitOutcome:
    pursuer: BattleUnit
    target: BattleUnit
    target_destroyed: bool


def _resolve_pursuit_combat(pursuer: BattleUnit, target: BattleUnit, rng: random.Random) -> bool:
    """The real post-catch destroy-or-resist decision (``PURSUIT.md``
    section 7, raw ``0x6B58/0x6B5D``): each side's own already-computed
    real battle strength, independently scaled by ``draw_pursuit_random_
    multiplier``, then a strict greater-than -- see module docstring for
    why this replaces Phase 349's own ``pursuit_destruction_probability``
    curve entirely, and for the one real detail (a fresh, pursuit-
    specific nemesis check inside the real ``Army_Str``) this doesn't
    reproduce.
    """

    pursuer_strength = pursuer.effective_strength * draw_pursuit_random_multiplier(rng)
    target_strength = target.effective_strength * draw_pursuit_random_multiplier(rng)
    return pursuer_strength > target_strength


def _iter_winner_units_in_position_order(winner_columns: list[Column]) -> Iterator[tuple[BattleUnit, bool]]:
    """Yields ``(unit, is_front_line)`` for every unit of the winning
    side, in the same order the real formation array's own ``pos`` walk
    visits them: every column's own front-line unit first, then every
    column's own second line, and so on (``PURSUIT.md``'s own ``for pos
    in range(1,71)``, where ``pos = depth*W + column_index`` -- row-major
    by depth, not column-by-column).
    """

    max_depth = max((len(column) for column in winner_columns), default=0)
    for depth in range(max_depth):
        for column in winner_columns:
            if depth < len(column):
                yield column[depth], depth == 0


def resolve_pursuit(
    winner_columns: list[Column], retreating_units: list[BattleUnit], terrain: Terrain, rng: random.Random
) -> list[PursuitOutcome]:
    """Chase down some of the losing side's retreating units -- see module
    docstring for the full, byte-confirmed mechanism (``PURSUIT.md``,
    Phase 906).

    For every winning-side unit, in real formation position order: draw a
    random still-alive retreater (uniform, with replacement -- a
    documented simplification of the real, unconfirmed-bound formula,
    see module docstring); an ineligible draw (``pursuit_target_
    eligible``) burns the attempt with no further roll; an eligible draw
    is checked against ``pursuit_catch_succeeds``, and if caught, resolved
    by ``_resolve_pursuit_combat`` -- destroyed or not, a catch always
    ends this pursuer's own search. Stops earlier if the losing side runs
    out of retreaters entirely.
    """

    remaining_targets = list(retreating_units)
    outcomes: list[PursuitOutcome] = []

    for pursuer, is_front_line in _iter_winner_units_in_position_order(winner_columns):
        max_attempts = max_pursuit_attempts(pursuer.army_type, is_front_line=is_front_line)
        for attempt_index in range(max_attempts):
            if not remaining_targets:
                break
            target = rng.choice(remaining_targets)
            if not pursuit_target_eligible(target.army_type, terrain):
                continue
            if pursuit_catch_succeeds(
                pursuer.army_type, attempt_index, target.army_type, rng, is_front_line=is_front_line
            ):
                destroyed = _resolve_pursuit_combat(pursuer, target, rng)
                outcomes.append(PursuitOutcome(pursuer=pursuer, target=target, target_destroyed=destroyed))
                if destroyed:
                    # Phase 1041 bug fix -- `BattleUnit` is a plain
                    # dataclass with value-based equality, so two
                    # retreating units that happen to share identical
                    # field values (plausible when same-type/quality
                    # armies retreat together) made `remaining_targets.
                    # remove(target)` delete the FIRST value-equal entry
                    # in the list, not necessarily the actual object just
                    # drawn and destroyed -- silently keeping the truly-
                    # destroyed unit eligible for a later draw while
                    # dropping an untouched survivor instead. Removed by
                    # identity instead (`is`, not `==`), not by index: the
                    # draw itself still goes through the real `rng.choice()`
                    # call (unchanged), so every existing seeded/scripted
                    # test's own rng consumption is unaffected -- only the
                    # removal target-finding changed.
                    index = next(i for i, t in enumerate(remaining_targets) if t is target)
                    del remaining_targets[index]
                break

    return outcomes
