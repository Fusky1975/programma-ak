"""Contested provinces (rulebook [7.6]).

"If an attacker invades a province but fails to destroy the defenders or
make them retreat, the province still belongs to the defender, and is
called a 'contested' province. If the attackers still have at least 1
movement point for each army, they will be used to force another battle
in the next phase. If not, both armies will encamp and wait for spring of
the next gameturn... The defending Kingdom can't force a battle in a
contested province even if all its armies can move, nor is a battle
caused by reinforcements sent to the defenders... The leader who invaded
the contested province will execute his orders in the next phase, except
that it's illegal to move from a contested province to an adjacent enemy
province. You can, however, move from a province owned by a neutral
player-King to an enemy province."

This module answers the specific yes/no questions the rulebook poses as
pure predicates; the actual per-province state machine across turns
lives elsewhere, on ``models/game_state.py ProvinceState.contested_by_
kingdom_id``/``.contested_from_coord`` (Phase 409) -- set by ``turn/
battle_orchestrator.py fight_battle()``'s own [7.6] "mixed result"
branch, cleared by the same two branches, and consumed by ``turn/
turn_processor.py _dispatch_contested_rebattles()`` to decide whether a
still-eligible attacker forces another battle next phase. **Stale as of
Phase 409** -- this paragraph used to say no such persistent state
existed anywhere in the project; it has, for a while.
"""

from __future__ import annotations


def attacker_can_force_rebattle(attacker_movement_points: dict[int, int]) -> bool:
    """"the attackers still have at least 1 movement point for each army" -- keyed by army id."""

    if not attacker_movement_points:
        return False
    return all(points >= 1 for points in attacker_movement_points.values())


class IllegalMoveFromContestedError(ValueError):
    """Raised by `turn/move_execution.py execute_move()` and `turn/
    turn_processor.py _dispatch_multi_attacker_lmove()` when `is_
    illegal_move_from_contested()` refuses a move -- a dedicated
    subclass (not a bare `ValueError`, which both real raise sites also
    use for an unrelated "no province data" case) so `report/turn_
    report.py describe_turn_results()` can narrate this one specific,
    sourced scenario (Phase 718, SAY.PAS code 32501's own generic
    prefix, `render_illegal_move_attempted()`) without narrating every
    other exception type too.
    """


def is_illegal_move_from_contested(origin_is_contested: bool, target_owner_is_enemy: bool) -> bool:
    """"illegal to move from a contested province to an adjacent enemy province."

    Moving from a merely-neutral-owned (non-contested) province to an
    enemy province is ordinary movement and always allowed -- this
    function only restricts moves whose *origin* is itself contested.
    """

    return origin_is_contested and target_owner_is_enemy


def contested_battle_movement_cost(*, conquered: bool) -> int:
    """"your armies will use up a movement point to fight a battle... If the
    province is conquered, the attacker uses another movement point." """

    return 2 if conquered else 1
