"""The Spy Table (rulebook [4.33]) -- Pursue/Trail catch-up chance.

Quoted in full, ``RULES.AK`` ~line 2370::

     Spy   Chance of        Margin of Error  Chance to Pursue
    Level  Escaping Notice  of Spy Reports      or Trail
      0       0%               70%                 50%
      1      50%               55%                100%
      2      75%               40%                150%
      3      88%               28%                200%
      4      95%               15%                250%

    Note:  The chance to Pursue or Trail is multiplied by two if the target
    leads an army.  The chance to pursue is then divided by the distance (in
    number of provinces) between the two characters.  If the pursued
    character is of the same Kingdom as the pursuer, then the chance of
    success is 100%.

Two of the three columns are modeled here. **"Chance to Pursue or
Trail"** (``pursue_catch_up_chance``) was the original, Phase 51 scope.
**"Margin of Error of Spy Reports"** (``margin_of_error_fraction``/
``estimate_reported_value``, Phase 265) closes ASpy's own [3.14] line
-- "taxation values and army types are subject to a margin of error
which decreases with increasing skill in Spy ability." The percentages
themselves are the sourced part of this table; **how a percentage
becomes a perturbed reported number is not stated anywhere and is this
module's own documented design choice**: ``estimate_reported_value()``
applies a uniform random offset in ``[-margin, +margin]`` (as a
fraction of the true value), floored at 0 -- the same "no negative
report" floor ``turn/tax_base.py province_tax_yield()`` already applies
to the true value itself. **"Chance of Escaping Notice"** is modeled in ``turn/spy_cover.py``: a character using Spy,
Trail or a Steal tactic in a turn is only noticed with the complementary chance (100/50/25/12/5%
by level) by a Patrol and in the other Kings' CHARACTERS report. The military figures of a Spy
report (armies per type) also go through the "Margin of Error" column
(``turn/aspy_execution.py _estimate_forces()``).

**Distance-0 (same-province) special case, a documented design choice,
not a rulebook quote**: the table's own formula ("divided by the
distance") is undefined at distance 0. Being in the same province is at
least as good a starting position as being 1 province away (itself a
100%-or-better roll at every Spy level), so this module treats distance
0 the same as the table's own "same Kingdom" full-certainty carve-out:
guaranteed catch-up, no division by zero.
"""

from __future__ import annotations

import random

# (escaping_notice_pct, margin_of_error_pct, pursue_or_trail_base_pct) by Spy skill level 0-4.
# escaping_notice_pct (index 0) is applied by turn/spy_cover.py (as its complement, 100/50/25/12/5).
_SPY_TABLE: dict[int, tuple[int, int, int]] = {
    0: (0, 70, 50),
    1: (50, 55, 100),
    2: (75, 40, 150),
    3: (88, 28, 200),
    4: (95, 15, 250),
}


def pursue_catch_up_chance(
    spy_skill: int, *, target_leads_army: bool, distance_provinces: int, same_kingdom: bool
) -> float:
    """Rulebook [4.33]'s "Chance to Pursue or Trail" formula, as a probability in [0, 1].

    ``spy_skill`` is clamped to the table's own 0-4 range (skill levels
    above 4 aren't modeled anywhere else in this project either).
    """

    if same_kingdom:
        return 1.0
    if distance_provinces <= 0:
        return 1.0  # see module docstring: same-province is undefined by the raw formula

    level = max(0, min(spy_skill, 4))
    base_percent = _SPY_TABLE[level][2]
    if target_leads_army:
        base_percent *= 2

    chance = (base_percent / 100) / distance_provinces
    return min(chance, 1.0)


def margin_of_error_fraction(spy_skill: int) -> float:
    """Rulebook [4.33]'s "Margin of Error of Spy Reports" column, as a fraction (0.70 at
    skill 0, down to 0.15 at skill 4). ``spy_skill`` is clamped to the
    table's own 0-4 range, same as ``pursue_catch_up_chance``.
    """

    level = max(0, min(spy_skill, 4))
    return _SPY_TABLE[level][1] / 100


def estimate_reported_value(true_value: int, spy_skill: int, rng: random.Random) -> int:
    """Perturbs ``true_value`` by ``margin_of_error_fraction(spy_skill)`` -- see module
    docstring for why the exact perturbation shape (uniform, symmetric,
    floored at 0) is a documented design choice, not a sourced formula.
    """

    margin = margin_of_error_fraction(spy_skill)
    offset_fraction = rng.uniform(-margin, margin)
    return max(0, round(true_value * (1 + offset_fraction)))
