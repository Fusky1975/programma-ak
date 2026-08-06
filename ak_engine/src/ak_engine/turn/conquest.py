"""Movement-point cost of conquest (rulebook [7.7]).

"Conquering an enemy province slows an army down, counting as 1 province
entered for purposes of movement. For example, let's say an army with a
speed of 3 enters an enemy province. That army has used up 2/3 of its
movement. It can enter one more province that turn, even if it is an
enemy province, because the -1 movement deduction is applied after the
move is made (an army may wind up with negative movement points only as
a result of this rule). A move into a sea province uses up an extra
movement point only if there is a battle in the province."

These are two separately-stated rules with no explicit interaction given
for the case where both apply (conquering a sea province). This module
treats them as additive (both deductions apply) -- a documented
assumption, not a sourced interaction.
"""

from __future__ import annotations

BASE_MOVE_COST = 1
CONQUEST_EXTRA_COST = 1
SEA_BATTLE_EXTRA_COST = 1


def movement_cost_for_move(*, is_sea_province: bool = False, battle_occurred: bool = False, conquered: bool = False) -> int:
    """Movement points a single province-entering move consumes.

    ``conquered`` means the move gained the mover the province, whether
    via a won battle or, since Phase 410, uncontested entry into an
    unowned/undefended-enemy province (``turn/move_execution.py
    execute_move()``'s own Phase 410 addendum) -- [7.7]'s own text
    frames this as a property of entering the province, not of winning a
    fight there. The sea-battle surcharge is evaluated independently of
    ``conquered`` (see module docstring).
    """

    cost = BASE_MOVE_COST
    if conquered:
        cost += CONQUEST_EXTRA_COST
    if is_sea_province and battle_occurred:
        cost += SEA_BATTLE_EXTRA_COST
    return cost
