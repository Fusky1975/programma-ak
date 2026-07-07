"""Battle line-up (rulebook [7.2]).

Builds on ``turn/combat.py``'s isolated formulas to answer "how do two
forces line up, and what's each column's total strength". It does NOT
decide who wins, eliminate armies, or handle duels/pursuit/retreat/
aftermath -- see ``turn/combat.py`` and ``ak_engine/README.md``.

Units arrive here with a pre-computed ``effective_strength`` (quality
multiplier already applied). Race/terrain strength bonuses ([6.3] "ARMY
STRENGTH NOTES") are NOT computed by this module -- the rulebook doesn't
specify how they stack with quality and nemesis, so folding them in here
would be guessing an interaction, not just filling a missing number (see
README).

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
Terrain Table") has no numbers anywhere in the available rulebook text or
Pascal source -- the only trace is ``SAY.PAS``'s ``_linelen``, which is
populated from already-computed battle data (for report formatting), not
derived here. So ``terrain_line_length_cap`` is left as an optional,
externally-supplied parameter with no default derivation; when omitted,
line length is purely `min(attacker_count, defender_count)` and
outflanking (which depends on the terrain cap) never triggers.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.army_type import ArmyType, is_overflight_unit, overflight_group
from ak_engine.turn.combat import line_contribution, win_probability


@dataclass(slots=True)
class BattleUnit:
    army_type: ArmyType
    effective_strength: float


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
