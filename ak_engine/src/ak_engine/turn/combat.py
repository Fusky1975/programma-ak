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
    """

    if strength_ratio < 0:
        raise ValueError(f"strength_ratio must be >= 0, got {strength_ratio}")
    return strength_ratio / (strength_ratio + 1)
