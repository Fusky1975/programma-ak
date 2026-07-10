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

Only the "Chance to Pursue or Trail" column is modeled here
(``pursue_catch_up_chance``) -- "Chance of Escaping Notice" belongs to
ASpy ([3.14]) and "Margin of Error of Spy Reports" belongs to ASpy's own
report-generation, neither of which has a resolver in this project yet
(``turn/aspy_defend_decode.py`` is decode-only). Both are left
unimplemented rather than guessed at partial relevance.

**Distance-0 (same-province) special case, a documented design choice,
not a rulebook quote**: the table's own formula ("divided by the
distance") is undefined at distance 0. Being in the same province is at
least as good a starting position as being 1 province away (itself a
100%-or-better roll at every Spy level), so this module treats distance
0 the same as the table's own "same Kingdom" full-certainty carve-out:
guaranteed catch-up, no division by zero.
"""

from __future__ import annotations

# (escaping_notice_pct, margin_of_error_pct, pursue_or_trail_base_pct) by Spy skill level 0-4.
# Only pursue_or_trail_base_pct (index 2) is used by this module -- see module docstring.
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
