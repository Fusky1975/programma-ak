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
   number of columns won"), and an exact-zero sum is corrected away by
   ``turn/battle_luck.py apply_bres_tie_correction`` (Phase 933) --
   **not** a separate coin-flip-for-a-side decision (Phase 370's
   original ``break_bres_tie``, superseded outright once a user-supplied
   disassembly showed the real tie-break directly corrects the *last
   column's own `BRES` value*, not some abstract side choice -- see that
   function's own docstring for the full derivation) -- so
   ``resolve_battle`` never reports an exact-zero ``total_bres`` in
   practice. `resolve_battle` therefore never returns ``winner == "tie"``
   either; that value stays a valid ``BattleResult`` state only for
   manually-constructed instances (e.g. ``turn/battle_orchestrator.py``'s
   own instant-conquest shortcut), not something this function itself
   produces.

Everything upstream of the column-strength numbers -- line-up,
`apply_tactical_switches`, `apply_nemesis_penalties`, non-humanoid
rear-targeting, numeric-superiority outflanking -- is unchanged: none of
that was in question, only the luck and win-decision layers on top of
it. See each function's own docstring in ``turn/battle_line.py`` for
those still-correct derivations.

Still NOT handled here -- see ak_engine/README.md: eliminating or
demoting the losing side's armies (``turn/combat.py direct_destruction_
probability`` is now wired into ``turn/battle_orchestrator.py``'s own
per-army loop, Phase 371 -- but only for the "lost the battle without a
clean sweep" branch; a column loser on the overall-winning or
clean-swept side is still handled by that side's own existing path, not
by this formula -- see ``battle_orchestrator.py
_direct_destruction_probabilities``'s own docstring for why), duels,
pursuit (already wired, Phase 349), retreat, post-battle quality
changes (`turn/aftermath.py`'s own real formula -- **wired since Phase
372/423, corrected Phase 892's own survey**: this paragraph used to say
it was "standalone-only pending formation-depth/merit-score tracking
this project doesn't have yet," stale on both counts -- Phase 372 built
`battle_orchestrator.py _formation_divisors()` for the formation-depth
half, Phase 423 built `_column_bres_by_army_id()` for a first,
unconfirmed guess at the merit-score half (superseded outright by
Phase 932's `_qual_modfr_score_by_army_id()`, once a user-supplied
disassembly proved the real merit score is `Qual_Modfr`, not `BRES`),
and `roll_quality_change()` is called with both real values at 5
real call sites in that same module), contested provinces, conquest
movement cost, and multiple contingents.
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
    apply_bres_tie_correction,
    bluck_event_index,
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
    # ``turn/battle_luck.py cluck_event_index``'s own docstring. Wired
    # as of Phase 615 into ``report/turn_report.py describe_battle()``
    # via ``render_cluck_narration()``.
    cluck_index: int
    attacker_units: Column = field(default_factory=list)
    defender_units: Column = field(default_factory=list)
    attacker_switched: bool = False
    defender_switched: bool = False


@dataclass(slots=True)
class BattleResult:
    columns: list[BattleColumnResult] = field(default_factory=list)
    # The whole-battle BLUCK narration index (Phase 370) -- see
    # ``turn/battle_luck.py bluck_event_index``'s own docstring. Wired
    # as of Phase 615 into ``report/turn_report.py describe_battle()``
    # via ``render_bluck_narration()``. Default 9 (the formula's own
    # "neutral" value) for manually-constructed instances.
    bluck_index: int = 9
    # The real decision quantity (Phase 370): sum of every column's
    # signed BRES. Positive means the attacker won, negative the
    # defender -- an exact-zero sum from ``resolve_battle`` itself never
    # reaches here (Phase 933: ``apply_bres_tie_correction`` corrects the
    # last column's own BRES before this sum is ever finalized), so this
    # field is 0 only for a manually-constructed ``BattleResult``.
    total_bres: int = 0
    attacker_columns_won: int = 0
    defender_columns_won: int = 0
    winner: str = "tie"  # "attacker", "defender", or "tie" -- see module docstring


def _apply_duellist_bonus(columns: list[Column], strengths: list[float], rng: random.Random) -> None:
    """Duellist / "Captain of the Musketeers" (Phase 471, AKGEN_reverse_
    engineering_report (2).md SS17.7): "una sua unità casuale della
    prima linea riceve l'assistenza degli Imperial Musketeers e combatte
    come fanatica" -- picks one random front-line unit (column depth 0,
    the only place a genuine front line exists -- see ``turn/battle_
    orchestrator.py _build_battle_units()``'s own Phase 471 addendum for
    why this can't run any earlier) among this side's own columns and
    adds its own precomputed ``BattleUnit.duellist_bonus_if_selected``
    straight into that column's strength.

    Eligibility lives entirely on the unit (``duellist_bonus_if_
    selected is not None``, set for every unit of a side whose Supreme
    Commander currently holds ``Office.DUELLIST`` -- ``None`` for every
    other side), so this function needs no office/state lookup of its
    own. Consumes an ``rng.choice()`` call only when at least one
    eligible front-line unit exists -- an ineligible side (the
    overwhelming common case) never perturbs the caller's own scripted
    RNG sequence, the same short-circuit convention Phase 35's own
    ``apply_fanaticism`` opt-in established.

    Runs *after* tactical switches and nemesis penalties have already
    settled which unit occupies each column's own front line (same
    ordering as the Druidic monster-aid injection just above), and
    genuinely at random among every eligible column -- not weighted by
    the size of the delta, so a unit already at Elite (whose own delta
    is a real, computed ``0.0``) can still be the one selected, matching
    SS17.7's own plain "a random front-line unit," not "the most
    valuable eligible one."
    """

    eligible_indices = [
        index for index, column in enumerate(columns) if column and column[0].duellist_bonus_if_selected is not None
    ]
    if not eligible_indices:
        return
    chosen = rng.choice(eligible_indices)
    strengths[chosen] += columns[chosen][0].duellist_bonus_if_selected


def _apply_alignment_king_bonus(columns: list[Column], strengths: list[float], rng: random.Random) -> None:
    """The 7 alignment-King titles' own shared "supreme commander -> one
    random front-line unit becomes fanatic" bonus (Phase 661) --
    identical shape to ``_apply_duellist_bonus()`` above, just reading
    ``BattleUnit.alignment_king_bonus_if_selected`` instead (already
    ``None`` for a skeletal unit under Undead King -- see ``turn/battle_
    orchestrator.py _build_battle_units()``'s own Phase 661 addendum, so
    no extra filtering is needed here). Called as a genuinely separate
    ``rng.choice()`` from ``_apply_duellist_bonus()`` -- see ``turn/
    battle_line.py BattleUnit.alignment_king_bonus_if_selected``'s own
    docstring for why a side eligible for both grants independently
    rolls each one, rather than merging them into a single selection.
    """

    eligible_indices = [
        index
        for index, column in enumerate(columns)
        if column and column[0].alignment_king_bonus_if_selected is not None
    ]
    if not eligible_indices:
        return
    chosen = rng.choice(eligible_indices)
    strengths[chosen] += columns[chosen][0].alignment_king_bonus_if_selected


def resolve_battle(
    attacker_units: list[BattleUnit],
    defender_units: list[BattleUnit],
    *,
    terrain_line_length_cap: int | None = None,
    attacker_tactical_ability: int = 0,
    defender_tactical_ability: int = 0,
    is_first_turn: bool = True,
    attacker_column_bonus: dict[int, int] | None = None,
    defender_column_bonus: dict[int, int] | None = None,
    attacker_combined_arms: bool = False,
    defender_combined_arms: bool = False,
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

    ``attacker_column_bonus``/``defender_column_bonus`` (Phase 453):
    ``{column_index: strength_bonus}`` from ``turn/druidic_monster_aid.py
    find_druidic_monster_assistance()`` -- a Druidic side's own assisting
    Feature monsters, added directly into that side's own per-column
    strength (after ``column_strength()``'s own computation, before the
    luck/``column_bres`` loop) since columns don't exist as addressable
    objects until they're built inside this function -- no earlier seam
    exists for a caller to inject a per-column bonus. ``None``/an absent
    key both mean "no bonus for that column", the default for every
    caller that isn't fighting a Druidic side.

    ``attacker_combined_arms``/``defender_combined_arms`` (Advanced
    Ability, Phase 513): quoted from ``models/advanced_ability.py
    ADVANCED_ABILITY_DESCRIPTION[TACTICAL_COMBINED_ARMS]``: "This allows
    the first two units in a column, if they are different army types,
    to complement each other's fighting abilities. They both fight at
    100% strength." -- a third, independent trigger for exactly the
    same numeric effect ``column_strength()``'s own ``outflank_second_
    line`` already implements for numeric-superiority outflanking and
    non-humanoid rear-targeting: the ordinary (non-overflight) unit at
    column depth 1 counts at 100% instead of the usual 50%. Folded into
    the same ``outflank_second_line`` argument below via OR, gated
    per-column on that column's own first two units actually being
    different ``ArmyType``s -- the caller (``turn/battle_orchestrator.py
    fight_battle()``) resolves the side-level eligibility ("in supreme
    command at a **land** battle") once; this function only needs to
    know whether the *ability* is available for this side, not the
    terrain itself. Default ``False`` for every pre-Phase-513 caller.
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

    # Numeric-superiority outflanking (Phase 64, RULES.AK ~line 1362): see
    # this module's own pre-Phase-370 docstring history for the
    # eligibility rule and why a None cap makes it ineligible rather than
    # eligible. Unchanged by Phase 370. Moved before apply_nemesis_
    # penalties (Phase 905) so that function can also consult this same
    # eligibility for its own outflanking-widens-nemesis rule -- see its
    # own docstring. Purely a reordering: this computation depends only on
    # unit counts and the terrain cap, neither of which apply_nemesis_
    # penalties (which only adjusts effective_strength) can affect.
    line_shorter_than_terrain_allows = (
        terrain_line_length_cap is not None and line_length < terrain_line_length_cap
    )
    attacker_numerically_superior = len(attacker_units) > len(defender_units)
    defender_numerically_superior = len(defender_units) > len(attacker_units)
    attacker_outflank_eligible = attacker_numerically_superior and line_shorter_than_terrain_allows
    defender_outflank_eligible = defender_numerically_superior and line_shorter_than_terrain_allows

    apply_nemesis_penalties(
        attacker_columns,
        defender_columns,
        rng,
        attacker_outflank_eligible=attacker_outflank_eligible,
        defender_outflank_eligible=defender_outflank_eligible,
    )

    # Non-humanoid rear-targeting (Phase 39, rulebook [7.2]): an opposing
    # overflight unit boosts this column's own ordinary second-line unit
    # to 100% strength -- see column_strength's docstring. OR'd with the
    # numeric-superiority eligibility computed above. Unchanged by Phase 370.
    attacker_strengths = [
        column_strength(
            a_col,
            outflank_second_line=(
                attacker_outflank_eligible
                or column_has_overflight_unit(d_col)
                or (attacker_combined_arms and len(a_col) >= 2 and a_col[0].army_type != a_col[1].army_type)
            ),
        )
        for a_col, d_col in zip(attacker_columns, defender_columns)
    ]
    defender_strengths = [
        column_strength(
            d_col,
            outflank_second_line=(
                defender_outflank_eligible
                or column_has_overflight_unit(a_col)
                or (defender_combined_arms and len(d_col) >= 2 and d_col[0].army_type != d_col[1].army_type)
            ),
        )
        for a_col, d_col in zip(attacker_columns, defender_columns)
    ]

    # Druidic monster battle assistance (Phase 453) -- see this
    # function's own docstring for why the injection has to happen here.
    if attacker_column_bonus:
        for column_index, bonus in attacker_column_bonus.items():
            if 0 <= column_index < len(attacker_strengths):
                attacker_strengths[column_index] += bonus
    if defender_column_bonus:
        for column_index, bonus in defender_column_bonus.items():
            if 0 <= column_index < len(defender_strengths):
                defender_strengths[column_index] += bonus

    # Duellist / "Captain of the Musketeers" (Phase 471) -- see this
    # function's own docstring for why the real front-line unit only
    # exists here to draw from.
    _apply_duellist_bonus(attacker_columns, attacker_strengths, rng)
    _apply_duellist_bonus(defender_columns, defender_strengths, rng)

    # The 7 alignment-King titles' own shared fanatic-front-line-unit
    # bonus (Phase 661) -- same real front-line-only timing as Duellist
    # just above, a genuinely separate rng.choice() per side.
    _apply_alignment_king_bonus(attacker_columns, attacker_strengths, rng)
    _apply_alignment_king_bonus(defender_columns, defender_strengths, rng)

    # Real luck (Phase 370): one global draw per side, once per battle.
    g1, g2 = draw_global_luck(rng)
    bluck_index = bluck_event_index(g1, g2)

    columns: list[BattleColumnResult] = []
    attacker_wins = 0
    defender_wins = 0
    total_bres = 0
    for column_index, (a_strength, d_strength, a_units, d_units, a_switched, d_switched) in enumerate(
        zip(
            attacker_strengths,
            defender_strengths,
            attacker_columns,
            defender_columns,
            attacker_switched,
            defender_switched,
        )
    ):
        # One local draw per side, fresh for every column.
        l1, l2 = draw_local_luck(rng)
        r1 = luck_strength_multiplier(g1, l1, is_first_turn=is_first_turn)
        r2 = luck_strength_multiplier(g2, l2, is_first_turn=is_first_turn)
        bres = column_bres(a_strength, d_strength, r1, r2)
        if column_index == line_length - 1:
            # Phase 933: the real tie-break -- a correction of the last
            # column's own BRES, not a separate coin-flip-for-a-side
            # abstraction. See apply_bres_tie_correction's own docstring.
            bres = apply_bres_tie_correction(bres, total_bres, rng)
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

    # Phase 933: total_bres can never be exactly 0 here -- line_length is
    # always >= 1 (an empty side is rejected above), so the last column
    # always exists and always ran through apply_bres_tie_correction
    # above whenever it would have made this sum zero; that correction's
    # own while loop only ever exits once the sum is nonzero. See
    # apply_bres_tie_correction's own docstring for the full derivation.
    winner = "attacker" if total_bres > 0 else "defender"

    return BattleResult(
        columns=columns,
        bluck_index=bluck_index,
        total_bres=total_bres,
        attacker_columns_won=attacker_wins,
        defender_columns_won=defender_wins,
        winner=winner,
    )
