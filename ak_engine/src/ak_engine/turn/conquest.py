"""Movement-point cost of conquest (rulebook [7.7]).

"Conquering an enemy province slows an army down, counting as 1 province
entered for purposes of movement. For example, let's say an army with a
speed of 3 enters an enemy province. That army has used up 2/3 of its
movement. It can enter one more province that turn, even if it is an
enemy province, because the -1 movement deduction is applied after the
move is made (an army may wind up with negative movement points only as
a result of this rule). As happens for land provinces, entering a sea one
costs 1 additional Movement Point only if a battle takes place."

**Phase 915 -- the full `Regolamento AK.txt` [7.7] text (never fully
re-read for this specific question until now) resolves what this module
used to treat as "two separately-stated rules with no explicit
interaction."** The sea-province sentence isn't independent of the land
one -- it opens with "Come avviene nelle province di terra" ("as happens
for [in] land provinces"), explicitly tying the sea condition back to
land: **the same trigger -- a battle taking place -- governs both**, not
two different conditions (conquest for land, battle for sea) that could
ever stack. User-confirmed directly (2026-09-25): a battle merely
happening is enough to owe the extra point, on either terrain; winning
isn't required. This closes two real gaps at once:

1. **No stacking, ever**: the previous implementation added both
   `CONQUEST_EXTRA_COST` and `SEA_BATTLE_EXTRA_COST` for a *won* sea
   battle, charging 3 total instead of the correct 2 -- there is only
   ever one extra point, whatever the terrain or the number of
   conditions that would have triggered it.
2. **A lost land battle now also costs the extra point.** The previous
   implementation only charged it when `conquered` was `True` (i.e. the
   mover won), silently treating "conquered" and "a battle took place"
   as the same condition for land while treating them as genuinely
   different for sea (`battle_occurred`, win or lose) -- an asymmetry
   the rulebook's own text never actually draws. `turn/move_execution.py
   execute_move()`'s own Phase 410 addendum already established that an
   *uncontested* conquest (no battle at all, e.g. entering an
   unowned/undefended province) also owes the point -- that reading is
   untouched here, since "conquered" and "a battle took place" are
   simply two different ways to reach the same one-point surcharge, not
   two stacking conditions.

``is_sea_province`` is gone from the signature entirely -- once the
trigger is uniformly "a battle took place, or the mover otherwise
conquered the province," terrain no longer changes the answer, so
there's nothing left for it to gate.
"""

from __future__ import annotations

BASE_MOVE_COST = 1
EXTRA_MOVE_COST = 1


def movement_cost_for_move(*, battle_occurred: bool = False, conquered: bool = False) -> int:
    """Movement points a single province-entering move consumes.

    ``conquered`` means the move gained the mover the province, whether
    via a won battle or, since Phase 410, uncontested entry into an
    unowned/undefended-enemy province (``turn/move_execution.py
    execute_move()``'s own Phase 410 addendum) -- [7.7]'s own text
    frames this as a property of entering the province, not of winning a
    fight there. ``battle_occurred`` (Phase 915) is the *other* way to
    owe the same single extra point: a real battle took place, whether
    or not it was won. Never stacks -- at most one extra point applies
    per move, regardless of how many of these conditions hold.
    """

    cost = BASE_MOVE_COST
    if battle_occurred or conquered:
        cost += EXTRA_MOVE_COST
    return cost
