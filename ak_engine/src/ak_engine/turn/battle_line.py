"""Battle line-up (rulebook [7.2]).

Builds on ``turn/combat.py``'s isolated formulas to answer "how do two
forces line up, and what's each column's total strength". It does NOT
decide who wins, eliminate armies, or handle duels/pursuit/retreat/
aftermath -- see ``turn/combat.py`` and ``ak_engine/README.md``.

Units arrive here with a pre-computed ``effective_strength`` -- see
``turn/strength.py`` for the race/terrain/quality/special-factors
calculator that produces it; this module only handles line-up and
column aggregation.

**Line-up algorithm**, from the rulebook text: "The length of the line is
limited to the line length of the smallest force... The two opposing
forces place their best armies in the front of the line. The weaker
armies usually line up behind the front line, and contribute 50% of their
strength... If there are enough armies for a third line, they are only
25%... and so on." Read literally, this is: sort each side's units
strongest-first, then deal them across ``line_length`` columns filling
the front line first, then the second line, etc. (a "snake draft").

**Terrain-based line-length shortening** ("The line may be shortened by
mountainous or wooded terrain on the flanks of the defender... see the
Terrain Table") is now sourced: the rulebook's Terrain Table [1.6] gives a
"Length of battle line (in #armies)" range per terrain (e.g. Mountain
1-3, Plains 5-10) -- see ``models.map.TERRAIN_LINE_LENGTH_RANGE`` and
``roll_terrain_line_length_cap`` below. The rulebook gives a range, not a
formula for picking within it, so that pick is a uniform random roll --
a documented choice, not a sourced rule.

Tactical-ability switching (``switch_chance``, ``maybe_switch_front_line``)
implements "The switch will only be made if the army strength of the
current front-line unit is less than the strength of a rearward unit,
after adjustments are made for all nemesis effects... the defender always
gets the last chance to switch" -- callers control switch order between
attacker and defender to reflect that. **Not currently called from
``resolve_battle``/``turn/battle_orchestrator.py`` -- a separate,
still-open gap from the nemesis penalty below (see
``ak_engine/README.md``).**

**Nemesis penalty across columns** (Phase 33, ``apply_nemesis_penalties``):
``turn/strength.py compute_effective_strength``'s own ``opponent_army_type``
parameter can only apply the rulebook [6.3] 2/3 nemesis penalty when a
single known opponent is given upfront (e.g. a 1v1 Duel/Pursuit check) --
the main battle line's actual pairings only exist here, after
``assign_battle_lines`` runs. ``apply_nemesis_penalties`` fills that gap
for stacked, multi-unit columns; see its own docstring for the pairing
interpretation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.army_type import ArmyType, is_overflight_unit, overflight_group
from ak_engine.models.map import TERRAIN_LINE_LENGTH_RANGE, Terrain
from ak_engine.turn.combat import apply_nemesis_penalty, line_contribution, win_probability


@dataclass(slots=True)
class BattleUnit:
    army_type: ArmyType
    effective_strength: float
    source_id: int | None = None  # opaque caller id (e.g. an ArmyState id), for post-battle bookkeeping


Column = list[BattleUnit]


def line_length_for_battle(
    attacker_count: int, defender_count: int, *, terrain_line_length_cap: int | None = None
) -> int:
    """Number of battle-line columns (rulebook: capped by the smaller force)."""

    if attacker_count < 0 or defender_count < 0:
        raise ValueError("unit counts must be >= 0")
    length = min(attacker_count, defender_count)
    if terrain_line_length_cap is not None:
        length = min(length, terrain_line_length_cap)
    return length


def roll_terrain_line_length_cap(terrain: Terrain, rng: random.Random) -> int | None:
    """Roll a terrain-based battle-line-length cap (rulebook [1.6] Terrain Table).

    Returns None for terrains with no entry in ``TERRAIN_LINE_LENGTH_RANGE``
    (currently only ``NO_TERRAIN``).
    """

    bounds = TERRAIN_LINE_LENGTH_RANGE.get(terrain)
    if bounds is None:
        return None
    low, high = bounds
    return rng.randint(low, high)


def assign_battle_lines(units: list[BattleUnit], line_length: int) -> list[Column]:
    """Deal ``units`` (strongest first) into ``line_length`` columns.

    Fills every column's front line before starting a second line, per the
    rulebook's "place their best armies in front" rule. Caller is
    responsible for sorting ``units`` strongest-first; this function only
    deals them out.
    """

    if line_length <= 0:
        raise ValueError(f"line_length must be > 0, got {line_length}")

    columns: list[Column] = [[] for _ in range(line_length)]
    for index, unit in enumerate(units):
        columns[index % line_length].append(unit)
    return columns


def apply_nemesis_penalties(attacker_columns: list[Column], defender_columns: list[Column]) -> None:
    """Apply the rulebook [6.3] nemesis penalty (2/3 strength) across paired columns.

    Mutates both column lists in place, replacing any nemesis-penalized
    unit with a copy at its reduced strength (same pattern as
    ``turn/battle_resolution.py``'s front-line luck: never mutate a
    ``BattleUnit`` in place, since it's the same object the caller's own
    ``attacker_units``/``defender_units`` lists still reference).

    **Pairing interpretation** (documented, not verbatim rulebook text):
    every unit in a column -- front line and any stacked rearward units --
    is checked against the *opposing* column's own front-line (depth 0)
    unit's ``ArmyType``, not a same-depth counterpart. The rulebook itself
    doesn't spell out column pairing for a multi-deep stack, but this
    reading is anchored in the one place nemesis and depth are discussed
    together: the Tactical-ability switch rule, "The switch will only be
    made if the army strength of the current front-line unit is less than
    the strength of a rearward unit, **after adjustments are made for all
    nemesis effects**" (``maybe_switch_front_line``'s docstring) -- which
    only makes sense if a rearward unit's nemesis-adjusted strength is
    evaluated against whoever is *currently at the front* of the opposing
    column, the same unit it would actually face if switched in. Applied
    here regardless of whether that switch mechanic itself runs (it isn't
    wired into ``resolve_battle`` yet -- see ``ak_engine/README.md``).

    Requires ``attacker_columns``/``defender_columns`` to be paired
    index-for-index (as ``resolve_battle`` produces); callers with a
    different pairing scheme need a different function.
    """

    for attacker_column, defender_column in zip(attacker_columns, defender_columns):
        _apply_nemesis_to_column(attacker_column, defender_column)
        _apply_nemesis_to_column(defender_column, attacker_column)


def _apply_nemesis_to_column(own_column: Column, opposing_column: Column) -> None:
    if not opposing_column:
        return
    opponent_type = opposing_column[0].army_type
    for index, unit in enumerate(own_column):
        adjusted_strength = apply_nemesis_penalty(unit.effective_strength, unit.army_type, opponent_type)
        if adjusted_strength != unit.effective_strength:
            own_column[index] = BattleUnit(unit.army_type, adjusted_strength, source_id=unit.source_id)


def column_strength(column: Column, *, outflank_second_line: bool = False) -> float:
    """Total effective strength contributed by one column.

    Ordinary (non-overflight) units halve per line depth (front=100%,
    second=50%, third=25%, ...), per ``line_contribution``. Overflight
    units (air/sea, see ``models.army_type.OVERFLIGHT_TYPES``) instead
    contribute 100% regardless of depth, halving only when stacked with
    another overflight unit of the *same* group (air or sea) in this
    column -- "Non-humanoid air units, non-humanoid sea units and humanoid
    units are considered three separate groups when halving strength."

    ``outflank_second_line=True`` reproduces "flanking second-line units
    of a force which is superior in numbers may outflank the enemy force.
    If they do that, they count as 100% strength instead of 50%" -- it
    only affects ordinary units at depth index 1 (the second line).
    Callers decide eligibility (numeric superiority and a shorter-than-
    terrain-allows line) since that depends on ``terrain_line_length_cap``,
    which this module can't derive -- see the module docstring.
    """

    overflight_group_counts: dict[str, int] = {}
    total = 0.0
    for depth, unit in enumerate(column):
        if is_overflight_unit(unit.army_type):
            group = overflight_group(unit.army_type)
            stack_index = overflight_group_counts.get(group, 0)
            total += unit.effective_strength * line_contribution(stack_index)
            overflight_group_counts[group] = stack_index + 1
        elif outflank_second_line and depth == 1:
            total += unit.effective_strength
        else:
            total += unit.effective_strength * line_contribution(depth)
    return total


def switch_chance(tactical_ability: int, line_length: int) -> float:
    """Probability of a Tactical-ability-based front/rear switch in a column.

    Rulebook: "The chance of being able to make a switch in any column is
    (Tactical-Ability / Line-Length)." Clamped to 1.0 since it's used as a
    probability and the rulebook doesn't address ability values large
    enough to exceed line length.
    """

    if line_length <= 0:
        raise ValueError(f"line_length must be > 0, got {line_length}")
    if tactical_ability < 0:
        raise ValueError(f"tactical_ability must be >= 0, got {tactical_ability}")
    return min(1.0, tactical_ability / line_length)


def maybe_switch_front_line(
    column: Column,
    line_length: int,
    tactical_ability: int,
    rng: random.Random,
    *,
    strength_key=lambda unit: unit.effective_strength,
) -> bool:
    """Maybe swap a column's front unit with its strongest eligible rearward unit.

    "The switch will only be made if the army strength of the current
    front-line unit is less than the strength of a rearward unit, after
    adjustments are made for all nemesis effects." Pass ``strength_key``
    to compare nemesis-adjusted strength instead of raw
    ``effective_strength`` when the opposing army type is known (nemesis
    is opponent-dependent, so this module can't compute it itself).

    Mutates ``column`` in place and returns True if a switch happened.
    """

    if len(column) < 2:
        return False
    front_strength = strength_key(column[0])
    best_index = max(range(1, len(column)), key=lambda i: strength_key(column[i]))
    if strength_key(column[best_index]) <= front_strength:
        return False
    if rng.random() >= switch_chance(tactical_ability, line_length):
        return False
    column[0], column[best_index] = column[best_index], column[0]
    return True


@dataclass(slots=True)
class ColumnContest:
    attacker_strength: float
    defender_strength: float
    attacker_win_probability: float


def estimate_win_probability(attacker_strength: float, defender_strength: float) -> float:
    """``win_probability`` with the zero-defender-strength edge case handled."""

    if defender_strength <= 0:
        return 1.0 if attacker_strength > 0 else 0.5
    return win_probability(attacker_strength / defender_strength)


def contest_columns(attacker_columns: list[Column], defender_columns: list[Column]) -> list[ColumnContest]:
    """Pair up columns and estimate each contest's attacker win probability.

    "There is then a number of contests equal to the length of the battle
    line." Does not pick a winner or eliminate anyone -- see
    ``turn/combat.py.win_probability`` for why this is an estimate, and
    the module docstring for what a full battle resolution still needs.
    """

    if len(attacker_columns) != len(defender_columns):
        raise ValueError("attacker and defender must have the same number of columns")

    contests = []
    for attacker_column, defender_column in zip(attacker_columns, defender_columns):
        attacker_strength = column_strength(attacker_column)
        defender_strength = column_strength(defender_column)
        contests.append(
            ColumnContest(
                attacker_strength=attacker_strength,
                defender_strength=defender_strength,
                attacker_win_probability=estimate_win_probability(attacker_strength, defender_strength),
            )
        )
    return contests
