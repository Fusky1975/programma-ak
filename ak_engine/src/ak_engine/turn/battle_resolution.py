"""Deciding who wins a battle (rulebook [7.2]: "There is then a number of
contests equal to the length of the battle line... The side that does
best in these contests wins the battle.").

Ties together ``turn/battle_line.py`` (line-up and column strength),
``turn/battle_luck.py`` (the two kinds of random event), and
``turn/combat.py`` (``win_probability``) into one call that produces a
concrete outcome -- unlike every earlier phase, this one needs an actual
random decision, not just a probability estimate, so it takes an
injectable ``random.Random`` (defaulting to a fresh one) to stay
testable: pass a seeded ``random.Random(seed)`` for reproducible results.

Still NOT handled here -- see ak_engine/README.md: eliminating or
demoting the losing side's armies, duels, pursuit, retreat, post-battle
quality changes, contested provinces, conquest movement cost, and
multiple contingents.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.turn.battle_line import (
    BattleUnit,
    Column,
    assign_battle_lines,
    column_strength,
    estimate_win_probability,
    line_length_for_battle,
)
from ak_engine.turn.battle_luck import BattleLuckEvent, ColumnLuckEvent, roll_battle_luck, roll_column_luck


@dataclass(slots=True)
class BattleColumnResult:
    attacker_strength: float
    defender_strength: float
    attacker_win_probability: float
    attacker_won: bool
    attacker_column_luck: ColumnLuckEvent | None
    defender_column_luck: ColumnLuckEvent | None


@dataclass(slots=True)
class BattleResult:
    columns: list[BattleColumnResult] = field(default_factory=list)
    battle_luck: BattleLuckEvent | None = None
    attacker_columns_won: int = 0
    defender_columns_won: int = 0
    winner: str = "tie"  # "attacker", "defender", or "tie"


def _apply_front_line_luck(column: Column, rng: random.Random) -> ColumnLuckEvent | None:
    if not column:
        return None
    event = roll_column_luck(rng)
    if event is not None:
        front = column[0]
        column[0] = BattleUnit(army_type=front.army_type, effective_strength=front.effective_strength * event.multiplier)
    return event


def resolve_battle(
    attacker_units: list[BattleUnit],
    defender_units: list[BattleUnit],
    *,
    terrain_line_length_cap: int | None = None,
    rng: random.Random | None = None,
) -> BattleResult:
    """Line up both sides, apply luck, and decide a winner column by column."""

    rng = rng if rng is not None else random.Random()

    line_length = line_length_for_battle(
        len(attacker_units), len(defender_units), terrain_line_length_cap=terrain_line_length_cap
    )
    if line_length <= 0:
        raise ValueError("cannot resolve a battle when either side has no units")

    attacker_columns = assign_battle_lines(
        sorted(attacker_units, key=lambda u: u.effective_strength, reverse=True), line_length
    )
    defender_columns = assign_battle_lines(
        sorted(defender_units, key=lambda u: u.effective_strength, reverse=True), line_length
    )

    attacker_luck = [_apply_front_line_luck(column, rng) for column in attacker_columns]
    defender_luck = [_apply_front_line_luck(column, rng) for column in defender_columns]

    attacker_strengths = [column_strength(column) for column in attacker_columns]
    defender_strengths = [column_strength(column) for column in defender_columns]

    battle_luck = roll_battle_luck(rng)
    if battle_luck is not None:
        if battle_luck.side == "attacker":
            attacker_strengths = [s * battle_luck.multiplier for s in attacker_strengths]
        else:
            defender_strengths = [s * battle_luck.multiplier for s in defender_strengths]

    columns: list[BattleColumnResult] = []
    attacker_wins = 0
    defender_wins = 0
    for a_strength, d_strength, a_luck, d_luck in zip(
        attacker_strengths, defender_strengths, attacker_luck, defender_luck
    ):
        probability = estimate_win_probability(a_strength, d_strength)
        attacker_won = rng.random() < probability
        attacker_wins += attacker_won
        defender_wins += not attacker_won
        columns.append(
            BattleColumnResult(
                attacker_strength=a_strength,
                defender_strength=d_strength,
                attacker_win_probability=probability,
                attacker_won=attacker_won,
                attacker_column_luck=a_luck,
                defender_column_luck=d_luck,
            )
        )

    if attacker_wins > defender_wins:
        winner = "attacker"
    elif defender_wins > attacker_wins:
        winner = "defender"
    else:
        winner = "tie"

    return BattleResult(
        columns=columns,
        battle_luck=battle_luck,
        attacker_columns_won=attacker_wins,
        defender_columns_won=defender_wins,
        winner=winner,
    )
