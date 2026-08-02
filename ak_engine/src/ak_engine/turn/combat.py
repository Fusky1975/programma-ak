"""Battle math primitives (rulebook [6.3] "ARMY STRENGTH NOTES" and [7.0]-[7.2]).

This is deliberately **not** a full battle simulator. It implements the
individually well-specified formulas the rulebook gives numbers for, as
small composable pieces:

- ``Quality`` multiplier (explicit table in the rulebook).
- ``line_contribution`` -- the halving-per-line-depth rule shared by both
  the humanoid battle-line rule [7.2] ("front line 100%, second line 50%,
  third line 25%, and so on") and the non-humanoid overflight-stacking
  rule ("a second non-humanoid unit attacking an enemy unit is at 1/2
  strength, a third at 1/4") -- these are the same halving law applied at
  two different call sites, so one function covers both.
- ``DEFENDER_BONUS`` (an explicit x1.25 multiplier).
- ``NEMESIS_PENALTY`` (an explicit 2/3 multiplier), via
  ``ak_engine.models.army_type.is_nemesis_of``.
- ``win_probability`` -- the rulebook gives exactly two anchor points
  ("A 4:1 ratio is needed to assure victory, while a 1:1 ratio gives a 50%
  chance of winning"); see its docstring for how the curve in between is
  (not) sourced.

Explicitly NOT implemented here -- see ak_engine/README.md:
- The battle line-up algorithm itself (who ends up in which line/column,
  terrain-based line-length shortening, Tactical-ability-based switching).
- Race/terrain strength bonuses ([6.3] "ARMY STRENGTH NOTES" first
  paragraph) -- the stacking order with quality and nemesis isn't given.
- Duels, pursuit, retreat, post-battle quality changes, contested
  provinces, conquest movement cost, multiple contingents.
"""

from __future__ import annotations

from enum import IntEnum

from ak_engine.models.army_type import ArmyType, is_nemesis_of

DEFENDER_BONUS = 1.25
NEMESIS_PENALTY = 2 / 3


class Quality(IntEnum):
    """Rulebook [6.3] quality-level strength multipliers.

    ``Sub-Depleted`` and ``Super-Elite`` are mentioned in the rulebook as
    existing beyond this range ("units still have a small intrinsic
    strength" even at multiplier zero, and "Super-Elite signifies a
    strength multiplier of 6+"), but neither is given a precise numeric
    rule, so only the 6 core levels are modeled.
    """

    DEPLETED = 0
    GREEN = 1
    AVERAGE = 2
    VETERAN = 3
    CRACK = 4
    ELITE = 5


# CTBOTH.PAS `qname` (~line 1283), verbatim, positional with `Quality`'s own
# ordinals above (Phase 86, found continuing to mine CTBOTH.PAS the way
# Phases 79-84 found their own real data). Confirmed to be `PROSE.TXT`'s own
# documented "^Q: Quality ('Average', 'Elite' etc.)" marker via `RUMORS.PAS`'s
# own `WW(qname[_qual])`/`Say(qname[_qual], spytype)`.
QUALITY_NAME: dict[Quality, str] = {
    Quality.DEPLETED: "Depleted",
    Quality.GREEN: "Green",
    Quality.AVERAGE: "Average",
    Quality.VETERAN: "Veteran",
    Quality.CRACK: "Crack",
    Quality.ELITE: "Elite",
}


def line_contribution(depth_index: int) -> float:
    """Strength fraction contributed from battle-line depth ``depth_index``.

    ``depth_index`` is 0 for the front line, 1 for the second line, etc.
    Front line = 100%, each successive line halves ("the weaker armies...
    contribute 50% of their strength... If there are enough armies for a
    third line, they are only 25%... and so on").

    The same halving law applies to stacked non-humanoid units attacking
    the same target ("a second non-humanoid unit attacking an enemy unit
    is at 1/2 strength, a third is at 1/4 strength") -- pass the 0-based
    stack index (0 for the first such unit) for that case.

    **Phase 351 addendum**: the same `AK.EXE`/`AK.OVR` static reverse
    engineering as Phase 346-350 independently confirms this exact
    formula from the compiled battle engine's own code, not just the
    rulebook's text -- `gw_format`'s own sibling `battle_engine.
    formation.strength_by_rank` is `[1.0, 0.5, 0.25, 0.125, 0.0625]`
    ("each further rank is halved"), and its own `same_nonhumanoid_
    group` note describes the identical halving law for stacked
    non-humanoid attackers. Zero correction needed here -- this is the
    rare case in the same sub-plan where the earlier, rulebook-derived
    implementation already matched the compiled engine exactly.
    """

    if depth_index < 0:
        raise ValueError(f"depth_index must be >= 0, got {depth_index}")
    return 1.0 / (2**depth_index)


def apply_defender_bonus(strength: float) -> float:
    return strength * DEFENDER_BONUS


def apply_nemesis_penalty(strength: float, attacker_type: ArmyType, opponent_type: ArmyType) -> float:
    """Apply the 2/3 nemesis penalty if ``opponent_type`` is ``attacker_type``'s nemesis."""

    if is_nemesis_of(attacker_type, opponent_type):
        return strength * NEMESIS_PENALTY
    return strength


def win_probability(strength_ratio: float) -> float:
    """Estimate win probability from a strength ratio (attacker / defender).

    The rulebook gives exactly two data points: "A 4:1 ratio is needed to
    assure victory, while a 1:1 ratio gives a 50% chance of winning." It
    does not give a formula for ratios in between, or say precisely what
    "assure" means numerically.

    This implements ``ratio / (ratio + 1)``, the standard odds-to-
    probability curve, which hits the 1:1 -> 50% anchor exactly. It does
    NOT hit "assured" at 4:1 (it gives 80%): no formula in the rulebook or
    source reproduces a sharper curve, so this is a documented
    approximation, not a sourced rule. Treat any output as directional,
    not exact, until real game data can calibrate it.

    **Phase 347 addendum**: that "real game data" now exists --
    ``column_bres`` below is the real engine's own confirmed column-
    winner formula (a static reverse engineering of `AK.EXE`/`AK.OVR`),
    and it decides winners by a deterministic `BRES` score's sign, not
    a probability draw at all. This function is kept as-is (nothing
    here yet consumes ``column_bres``) rather than deleted, since
    ``estimate_win_probability``/``resolve_battle`` haven't been
    rewired to the real formula yet -- see ``column_bres``'s own
    docstring and ``turn/battle_luck.py``'s "Phase 346 addendum" for
    why that rewire is a distinct, later phase.
    """

    if strength_ratio < 0:
        raise ValueError(f"strength_ratio must be >= 0, got {strength_ratio}")
    return strength_ratio / (strength_ratio + 1)


def column_bres(side1_strength: float, side2_strength: float, r1: float, r2: float) -> int:
    """The real, confirmed per-column resolution score (`BRES`) from a
    static reverse engineering of `AK.EXE`/`AK.OVR` -- see
    `turn/battle_luck.py`'s own "Phase 346 addendum" for the same
    source and its own `r1`/`r2` luck-multiplier primitives
    (`luck_strength_multiplier`), which this function's own `r1`/`r2`
    parameters are meant to be.

    `BRES = clamp(-5,5, round(R1*sqrt(r) - R2/sqrt(r)))`, where
    `r = side1_strength / side2_strength` is the *deterministic*
    strength ratio (every non-luck modifier already applied -- quality,
    nemesis, defender bonus, terrain, and so on -- but not luck). This
    is what `turn/combat.py win_probability`'s own docstring already
    flagged as "a documented approximation, not a sourced rule" for the
    win-decision curve in between the rulebook's own two anchor points
    -- `BRES`'s own sign (not `win_probability`'s output) is the real
    engine's own column-winner decision, and its magnitude (not just a
    yes/no) is what `turn/battle_luck.py`'s own source calls out
    directly: "the engine weighs the size of each column result, not
    merely the number of columns won."

    Zero-strength edge cases mirror `turn/battle_line.py
    estimate_win_probability`'s own handling (neither side's real
    strength can be genuinely negative, so `<= 0` is the actual "no
    strength" case, not just literal zero): a strengthless side 1 against
    a real side 2 is the worst possible outcome (`-5`), the mirror image
    for side 2 is `+5`, and both sides strengthless is a true no-op
    (`0`) rather than an undefined `0/0` ratio.
    """

    if side1_strength <= 0 and side2_strength <= 0:
        return 0
    if side2_strength <= 0:
        return 5
    if side1_strength <= 0:
        return -5

    ratio = side1_strength / side2_strength
    sqrt_ratio = ratio**0.5
    raw = round(r1 * sqrt_ratio - r2 / sqrt_ratio)
    return max(-5, min(5, raw))


def direct_destruction_probability(bres: int, winner_speed: int, loser_speed: int) -> float:
    """The real, confirmed probability that a column's own first-line
    loser is destroyed outright, from the same `AK.EXE`/`AK.OVR` source
    as `column_bres` (Phase 347/348): `clamp(0,1, 0.25*(abs(BRES) +
    speed_delta))`, where `speed_delta = clamp(-1,1, winner_speed -
    loser_speed)` (`ArmyType`'s own `ARMY_TABLE[...].speed`, Phase 4).

    This is only the *direct* contest check -- the source's own explicit
    warning: a survivor of this roll may still be destroyed later in
    pursuit, or removed for want of a retreat destination, neither of
    which this function models. Eligibility (alive, first-line, the
    losing side of its own column, not already eliminated by an earlier
    step; "special unit types may divert the result") is the caller's
    own responsibility to check before calling this -- the source
    doesn't give a formula for eligibility itself, only for the roll
    once a unit is eligible.

    Verified against the source's own worked table (`bres`=1..5,
    `speed_delta`=-1/0/+1): e.g. `bres`=4, `speed_delta`=+1 computes
    `0.25*5=1.25`, clamped to the table's own `100%` rather than an
    impossible `125%`.
    """

    speed_delta = max(-1, min(1, winner_speed - loser_speed))
    return max(0.0, min(1.0, 0.25 * (abs(bres) + speed_delta)))
