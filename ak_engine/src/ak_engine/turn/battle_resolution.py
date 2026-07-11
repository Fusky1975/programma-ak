"""Deciding who wins a battle (rulebook [7.2]: "There is then a number of
contests equal to the length of the battle line... The side that does
best in these contests wins the battle.").

Ties together ``turn/battle_line.py`` (line-up, tactical switches,
nemesis penalties, and column strength), ``turn/battle_luck.py`` (the
two kinds of random event), and ``turn/combat.py`` (``win_probability``)
into one call that produces a concrete outcome -- unlike every earlier
phase, this one needs an actual random decision, not just a probability
estimate, so it takes an injectable ``random.Random`` (defaulting to a
fresh one) to stay testable: pass a seeded ``random.Random(seed)`` for
reproducible results.

**Order right after line-up (Phase 34), before front-line luck:**
``turn/battle_line.py apply_tactical_switches`` (rulebook: attacker
attempts a per-column front/rear switch first, defender gets "the last
chance"), *then* ``apply_nemesis_penalties`` (Phase 33) against the
resulting -- possibly just-switched -- lineup. Switching itself defaults
to a no-op (``attacker_tactical_ability``/``defender_tactical_ability``
default to 0, giving ``switch_chance`` 0) unless the caller passes real
ability levels, so every downstream strength read (luck multipliers,
column contests, and whatever ``BattleUnit`` list the caller keeps using
afterward, e.g. for pursuit) reflects both the final lineup and its
nemesis-adjusted strength.

**Non-humanoid rear-targeting** (Phase 39, rulebook [7.2]): each side's
own column strength is computed with ``column_strength``'s
``outflank_second_line`` driven by whether the *opposing* column
contains an overflight unit (``column_has_overflight_unit``) -- "it will
attack the rear unit instead (the non-human unit and the rearward unit
will both be at 100% strength in this case.)" See ``column_strength``'s
own docstring for the Druidic-ability held-back carve-out (Phase 43).

**Numeric-superiority outflanking** (Phase 64, ``RULES.AK`` ~line 1362,
quoted in full): "If a battle line is shorter than the terrain allows,
the flanking second-line units of a force which is superior in numbers
may outflank the enemy force. If they do that, they count as 100%
strength instead of 50%." -- the *other* rulebook trigger
``column_strength``'s ``outflank_second_line`` parameter was originally
built for (see its own docstring), left unwired from Phase 6 through
Phase 63. Eligibility is computed once per side, not per column: this
side's own unit count must exceed the opposing side's (numeric
superiority), *and* ``line_length`` must be strictly less than
``terrain_line_length_cap`` (a ``None`` cap -- unknown terrain -- makes
this condition false, not true; "shorter than the terrain allows" is
unanswerable without knowing what the terrain allows). Deterministic,
no ``rng`` involved -- the rulebook's own worked example (~line 1770:
two second-line Legions "will not be penalized 50% because they will be
able to outflank the enemy") applies the boost unconditionally once
eligible, not as a chance roll, matching ``column_strength``'s existing
non-probabilistic contract. OR'd together with the rear-targeting
driver above (a column can be eligible for either reason, or both; the
100% effect itself doesn't stack, matching ``column_strength``'s own
"only affects... at depth index 1" note). **Not modeled**: the related
nemesis-selection sentence a few paragraphs later ("If more than one of
your units are eligible to be a nemesis due to overflight or
outflanking, one of them is chosen at random") -- a separate mechanic
about *which* unit receives nemesis targeting when several qualify, not
this rule's own 100%-strength effect; `turn/battle_line.py
apply_nemesis_penalties`'s own documented column-pairing interpretation
doesn't yet account for outflanking eligibility specifically. Left as a
distinct, still-open gap rather than folded into this phase.

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
    apply_nemesis_penalties,
    apply_tactical_switches,
    assign_battle_lines,
    column_has_overflight_unit,
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
    attacker_units: Column = field(default_factory=list)
    defender_units: Column = field(default_factory=list)
    attacker_switched: bool = False
    defender_switched: bool = False


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
        column[0] = BattleUnit(
            army_type=front.army_type,
            effective_strength=front.effective_strength * event.multiplier,
            source_id=front.source_id,
            druidic_rear_targeting_blocked=front.druidic_rear_targeting_blocked,
        )
    return event


def resolve_battle(
    attacker_units: list[BattleUnit],
    defender_units: list[BattleUnit],
    *,
    terrain_line_length_cap: int | None = None,
    attacker_tactical_ability: int = 0,
    defender_tactical_ability: int = 0,
    rng: random.Random | None = None,
) -> BattleResult:
    """Line up both sides, apply luck, and decide a winner column by column.

    ``attacker_tactical_ability``/``defender_tactical_ability`` (Phase 34)
    are each side's Tactical (or Naval, in Sea provinces) skill level --
    the same terrain-aware value ``turn/battle_orchestrator.py`` already
    derives for the [6.3] strength bonus (Phase 30) and the Duel tiebreak
    (rulebook [7.1]), reused here for the [7.2] front/rear switch chance
    too. The rulebook's switch-chance sentence just says "Tactical-
    Ability" without a Sea-battle exception, so extending the same
    terrain-aware value to it is a documented consistency choice, not a
    separately sourced rule. Default 0 for both -- ``switch_chance(0,
    ...)`` is 0, matching this function's pre-Phase-34 behavior exactly.
    """

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

    attacker_switched, defender_switched = apply_tactical_switches(
        attacker_columns, defender_columns, line_length, attacker_tactical_ability, defender_tactical_ability, rng
    )

    apply_nemesis_penalties(attacker_columns, defender_columns, rng)

    attacker_luck = [_apply_front_line_luck(column, rng) for column in attacker_columns]
    defender_luck = [_apply_front_line_luck(column, rng) for column in defender_columns]

    # Numeric-superiority outflanking (Phase 64, RULES.AK ~line 1362): see
    # this module's own docstring for the eligibility rule and why a
    # None cap makes it ineligible rather than eligible.
    line_shorter_than_terrain_allows = (
        terrain_line_length_cap is not None and line_length < terrain_line_length_cap
    )
    attacker_numerically_superior = len(attacker_units) > len(defender_units)
    defender_numerically_superior = len(defender_units) > len(attacker_units)
    attacker_outflank_eligible = attacker_numerically_superior and line_shorter_than_terrain_allows
    defender_outflank_eligible = defender_numerically_superior and line_shorter_than_terrain_allows

    # Non-humanoid rear-targeting (Phase 39, rulebook [7.2]): an opposing
    # overflight unit boosts this column's own ordinary second-line unit
    # to 100% strength -- see column_strength's docstring. OR'd with the
    # numeric-superiority eligibility computed above.
    attacker_strengths = [
        column_strength(a_col, outflank_second_line=attacker_outflank_eligible or column_has_overflight_unit(d_col))
        for a_col, d_col in zip(attacker_columns, defender_columns)
    ]
    defender_strengths = [
        column_strength(d_col, outflank_second_line=defender_outflank_eligible or column_has_overflight_unit(a_col))
        for a_col, d_col in zip(attacker_columns, defender_columns)
    ]

    battle_luck = roll_battle_luck(rng)
    if battle_luck is not None:
        if battle_luck.side == "attacker":
            attacker_strengths = [s * battle_luck.multiplier for s in attacker_strengths]
        else:
            defender_strengths = [s * battle_luck.multiplier for s in defender_strengths]

    columns: list[BattleColumnResult] = []
    attacker_wins = 0
    defender_wins = 0
    for a_strength, d_strength, a_luck, d_luck, a_units, d_units, a_switched, d_switched in zip(
        attacker_strengths,
        defender_strengths,
        attacker_luck,
        defender_luck,
        attacker_columns,
        defender_columns,
        attacker_switched,
        defender_switched,
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
                attacker_units=a_units,
                defender_units=d_units,
                attacker_switched=a_switched,
                defender_switched=d_switched,
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
