"""Deciding who wins a battle -- the real, confirmed `AK.EXE`/`AK.OVR`
resolution pipeline (rulebook [7.2]: "There is then a number of contests
equal to the length of the battle line... The side that does best in
these contests wins the battle.").

Ties together ``turn/battle_line.py`` (line-up, tactical switches,
nemesis penalties, and column strength), ``turn/battle_luck.py`` (the
real luck-draw formula), and ``turn/combat.py`` (``column_bres``) into
one call that produces a concrete outcome -- unlike every earlier
phase, this one needs an actual random decision, not just a probability
estimate, so it takes an injectable ``random.Random`` (defaulting to a
fresh one) to stay testable: pass a seeded ``random.Random(seed)`` for
reproducible results.

**Phase 370: rewired to the real, confirmed formula.** Phases 346-349
found and standalone-tested the real `AK.EXE`/`AK.OVR` battle-resolution
primitives (`turn/battle_luck.py`'s `draw_global_luck`/`draw_local_luck`/
`luck_strength_multiplier`/`bluck_event_index`/`cluck_event_index`/
`break_bres_tie`, `turn/combat.py`'s `column_bres`) but left them
unwired, since rewiring meant replacing this module's own entire
win-decision path, not swapping one formula for another. This phase is
that rewire. Two structural changes from the pre-Phase-370 version:

1. **Luck is no longer a triggered event with a chance to occur.** The
   old model rolled a 75%-chance column event and a 55%-chance
   battle-wide event, each producing an optional ``ColumnLuckEvent``/
   ``BattleLuckEvent`` that multiplied strength *if* it fired. The real
   mechanic has no trigger chance at all: one global luck draw per side
   (`G1`/`G2`, once per battle) and one local luck draw per side (`L1`/
   `L2`, fresh per column) combine into `R_s = 1 + k*(G_s+L_s)` --
   **always applied**, every column, every battle (see
   ``turn/battle_luck.py``'s own Phase 370 addendum for `k`'s two
   values). `ColumnLuckEvent`/`BattleLuckEvent` and their roll functions
   are gone; nothing replaces their "did an event fire" shape because
   the real mechanic never had one.
2. **The column winner is now a deterministic sign, not a probability
   draw.** ``column_bres`` computes a real, confirmed `BRES` score
   (`-5..+5`) per column from each side's deterministic strength (post
   line-up/switches/nemesis/rear-targeting/outflanking, still computed
   exactly as before) and the two sides' own `R_s` multipliers -- its
   *sign* decides that column's winner, with no further random draw.
   **The overall battle winner is decided by the sum of every column's
   signed `BRES`** (not by counting how many columns each side won --
   "the engine weighs the size of each column result, not merely the
   number of columns won"), and an exact-zero sum is broken by
   ``break_bres_tie``'s own repeated-coin-differences rule rather than
   ever being reported as a genuine tie. `resolve_battle` therefore
   never returns ``winner == "tie"`` in practice; that value stays a
   valid ``BattleResult`` state only for manually-constructed instances
   (e.g. ``turn/battle_orchestrator.py``'s own instant-conquest
   shortcut), not something this function itself produces.

Everything upstream of the column-strength numbers -- line-up,
`apply_tactical_switches`, `apply_nemesis_penalties`, non-humanoid
rear-targeting, numeric-superiority outflanking -- is unchanged: none of
that was in question, only the luck and win-decision layers on top of
it. See each function's own docstring in ``turn/battle_line.py`` for
those still-correct derivations.

Still NOT handled here -- see ak_engine/README.md: eliminating or
demoting the losing side's armies (though ``turn/combat.py
direct_destruction_probability`` is now a real, confirmed formula for
part of that -- not yet wired into ``turn/battle_orchestrator.py``'s own
destruction logic, a separate follow-up), duels, pursuit (already wired,
Phase 349), retreat, post-battle quality changes (`turn/aftermath.py`'s
own real formula is likewise standalone-only pending formation-depth/
merit-score tracking this project doesn't have yet), contested
provinces, conquest movement cost, and multiple contingents.
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
    line_length_for_battle,
)
from ak_engine.turn.battle_luck import (
    bluck_event_index,
    break_bres_tie,
    cluck_event_index,
    draw_global_luck,
    draw_local_luck,
    luck_strength_multiplier,
)
from ak_engine.turn.combat import column_bres


@dataclass(slots=True)
class BattleColumnResult:
    attacker_strength: float
    defender_strength: float
    # The real, confirmed per-column BRES score (-5..+5, Phase 347) --
    # positive favors the attacker, negative the defender, zero a
    # genuine per-column tie (contributes to neither side's own column
    # count, but still counts in the battle-wide summed BRES).
    bres: int
    attacker_won: bool  # bres > 0 -- False for both a defender win and a per-column tie
    # This column's own local CLUCK narration index (Phase 370), from
    # the attacker's own L1/L2 perspective -- see
    # ``turn/battle_luck.py cluck_event_index``'s own docstring. Not
    # consumed by any report renderer yet.
    cluck_index: int
    attacker_units: Column = field(default_factory=list)
    defender_units: Column = field(default_factory=list)
    attacker_switched: bool = False
    defender_switched: bool = False


@dataclass(slots=True)
class BattleResult:
    columns: list[BattleColumnResult] = field(default_factory=list)
    # The whole-battle BLUCK narration index (Phase 370) -- see
    # ``turn/battle_luck.py bluck_event_index``'s own docstring. Not
    # consumed by any report renderer yet. Default 9 (the formula's own
    # "neutral" value) for manually-constructed instances.
    bluck_index: int = 9
    # The real decision quantity (Phase 370): sum of every column's
    # signed BRES. Positive means the attacker won, negative the
    # defender, exact zero means ``winner`` was resolved by
    # ``break_bres_tie`` instead.
    total_bres: int = 0
    attacker_columns_won: int = 0
    defender_columns_won: int = 0
    winner: str = "tie"  # "attacker", "defender", or "tie" -- see module docstring


def resolve_battle(
    attacker_units: list[BattleUnit],
    defender_units: list[BattleUnit],
    *,
    terrain_line_length_cap: int | None = None,
    attacker_tactical_ability: int = 0,
    defender_tactical_ability: int = 0,
    is_first_turn: bool = True,
    rng: random.Random | None = None,
) -> BattleResult:
    """Line up both sides, apply the real luck formula, and decide a
    winner from the summed real `BRES` score -- see module docstring for
    the full Phase 370 derivation.

    ``attacker_tactical_ability``/``defender_tactical_ability`` (Phase 34)
    are each side's Tactical (or Naval, in Sea provinces) skill level --
    the same terrain-aware value ``turn/battle_orchestrator.py`` already
    derives for the [6.3] strength bonus (Phase 30) and the Duel tiebreak
    (rulebook [7.1]), reused here for the [7.2] front/rear switch chance
    too. Default 0 for both -- ``switch_chance(0, ...)`` is 0.

    ``is_first_turn`` (Phase 370) selects the real luck formula's own two
    coefficients (see ``turn/battle_luck.py luck_strength_multiplier``'s
    own docstring) -- "because both random components are halved" on the
    game's own actual first turn. Defaults to ``True`` (the smaller,
    turn-1 luck range) since most of this project's own existing callers
    predate turn-number tracking and a caller that doesn't pass real turn
    state shouldn't silently get the larger turn-2+ range instead.
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

    # Numeric-superiority outflanking (Phase 64, RULES.AK ~line 1362): see
    # this module's own pre-Phase-370 docstring history for the
    # eligibility rule and why a None cap makes it ineligible rather than
    # eligible. Unchanged by Phase 370.
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
    # numeric-superiority eligibility computed above. Unchanged by Phase 370.
    attacker_strengths = [
        column_strength(a_col, outflank_second_line=attacker_outflank_eligible or column_has_overflight_unit(d_col))
        for a_col, d_col in zip(attacker_columns, defender_columns)
    ]
    defender_strengths = [
        column_strength(d_col, outflank_second_line=defender_outflank_eligible or column_has_overflight_unit(a_col))
        for a_col, d_col in zip(attacker_columns, defender_columns)
    ]

    # Real luck (Phase 370): one global draw per side, once per battle.
    g1, g2 = draw_global_luck(rng)
    bluck_index = bluck_event_index(g1, g2)

    columns: list[BattleColumnResult] = []
    attacker_wins = 0
    defender_wins = 0
    total_bres = 0
    for a_strength, d_strength, a_units, d_units, a_switched, d_switched in zip(
        attacker_strengths,
        defender_strengths,
        attacker_columns,
        defender_columns,
        attacker_switched,
        defender_switched,
    ):
        # One local draw per side, fresh for every column.
        l1, l2 = draw_local_luck(rng)
        r1 = luck_strength_multiplier(g1, l1, is_first_turn=is_first_turn)
        r2 = luck_strength_multiplier(g2, l2, is_first_turn=is_first_turn)
        bres = column_bres(a_strength, d_strength, r1, r2)
        total_bres += bres
        if bres > 0:
            attacker_wins += 1
        elif bres < 0:
            defender_wins += 1

        columns.append(
            BattleColumnResult(
                attacker_strength=a_strength,
                defender_strength=d_strength,
                bres=bres,
                attacker_won=bres > 0,
                cluck_index=cluck_event_index(l1, l2),
                attacker_units=a_units,
                defender_units=d_units,
                attacker_switched=a_switched,
                defender_switched=d_switched,
            )
        )

    if total_bres > 0:
        winner = "attacker"
    elif total_bres < 0:
        winner = "defender"
    else:
        winner = "attacker" if break_bres_tie(rng) == "side1" else "defender"

    return BattleResult(
        columns=columns,
        bluck_index=bluck_index,
        total_bres=total_bres,
        attacker_columns_won=attacker_wins,
        defender_columns_won=defender_wins,
        winner=winner,
    )
