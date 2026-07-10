"""Executing a Move order end-to-end (rulebook [3.1], [6.2], [7.7]).

Wires together, in order:

1. **Contested-province check** (Phase 36, rulebook [7.6]): "The leader
   who invaded the contested province will execute his orders in the
   next phase, except that it's illegal to move from a contested
   province to an adjacent enemy province." Raises ``ValueError`` via
   ``turn/contested_province.py is_illegal_move_from_contested()`` when
   the mover's *origin* province is currently contested *by the mover's
   own kingdom* (``ProvinceState.contested_by_kingdom_id == kingdom_id``
   -- not merely contested by anyone, since the rule is specifically
   about "the leader who invaded," i.e. the attacker still stuck there,
   not some third kingdom's army passing through) and the *target*
   province is enemy-owned. ``contested_by_kingdom_id`` has been
   correctly set/cleared by ``turn/battle_orchestrator.py fight_battle()``
   since Phase 9 -- this only adds the read side that was missing. "You
   can, however, move from a province owned by a neutral player-King to
   an enemy province" needs no separate handling: that's just the
   `origin_contested_by_mover=False` case, already legal.
2. ``turn/movement.py resolve_move()`` -- adjacency check + the partial-
   exploration side effect.
3. **Battle trigger**: if the target province holds any army not allied
   with the mover, calls ``turn/battle_orchestrator.py fight_battle()``.
4. ``turn/conquest.py movement_cost_for_move()`` -- movement-point
   deduction, including the extra point for conquering and/or for a sea
   battle.
5. ``GameState`` mutation: army relocation (only if the move actually
   succeeds -- an unconquered, contested, or repelled battle leaves the
   mover's surviving armies where ``fight_battle()`` put them, not at the
   target) and the province's exploration-percent update.

Still out of scope, same as ``turn/movement.py``: chasing a *non-adjacent*
target (`resolve_move` still raises `NonAdjacentMoveError`). Also still
out of scope: ``turn/contested_province.py``'s other two functions --
``attacker_can_force_rebattle``/``contested_battle_movement_cost`` --
since automatically forcing a rebattle "in the next phase" without a new
player order needs a caller that tracks state across phases for a given
province. ``turn/turn_processor.py run_turn()`` (Phase 45) *is* now a
genuinely phase-by-phase, multi-leader orchestrator -- the structural
gap this note used to point at -- but it doesn't wire this specific
mechanic in yet either; see that module's own docstring for what it
does wire in (Multiple Contingents) and what's still deferred.

**Leader-only movement** (Phase 14): pass ``leader_id`` and an empty
``army_ids`` for a character moving without any army. Per rulebook [3.1]
("If the character has an army with him and the province is occupied by
a enemy army, combat occurs"), combat only triggers when the mover has
at least one army -- a lone character can walk into an enemy-held
province without a fight. Lone characters aren't subject to the
movement-point check either: that's an army property (rulebook [6.2],
"An army's speed determines how far it can move"), and this project
doesn't track a separate per-character movement budget.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.battle_orchestrator import BattleReport, fight_battle
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.contested_province import is_illegal_move_from_contested
from ak_engine.turn.exploration import ExploreResult
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, resolve_move


@dataclass(slots=True)
class MoveExecutionResult:
    moved: bool
    battle_report: BattleReport | None
    exploration: ExploreResult
    movement_points_spent: int
    new_location: HexCoord | None


def execute_move(
    state: GameState,
    kingdom_id: int,
    army_ids: list[int],
    target: HexCoord,
    *,
    leader_id: int | None = None,
    explorer_skill: int = 0,
    loser_retreats: bool = True,
    rng: random.Random | None = None,
) -> MoveExecutionResult:
    """Move ``army_ids`` (all from the same province) to an adjacent ``target``.

    ``army_ids`` may be empty if ``leader_id`` is given -- a character
    moving alone. Fights a battle automatically if ``target`` holds a
    non-allied army AND the mover brought at least one army of their own.
    Raises if the armies don't share a starting province, if any lacks a
    movement point, if neither ``army_ids`` nor ``leader_id`` is given, or
    if ``target`` isn't adjacent (via ``resolve_move``) or has no
    province data.
    """

    rng = rng if rng is not None else random.Random()
    if not army_ids and leader_id is None:
        raise ValueError("no armies and no leader given -- nothing to move")

    armies = [state.armies[army_id] for army_id in army_ids]
    if armies:
        current = armies[0].location
        if any(army.location != current for army in armies):
            raise ValueError("all armies must move together from the same province")
        if any(army.movement_points < 1 for army in armies):
            raise ValueError("an army with no movement points left this gameturn can't move")
    else:
        current = state.leaders[leader_id].location

    target_province = state.provinces.get(target)
    if target_province is None:
        raise ValueError(f"no province data for {target}")

    origin_province = state.provinces.get(current)
    origin_contested_by_mover = origin_province is not None and origin_province.contested_by_kingdom_id == kingdom_id
    target_owner_is_enemy = target_province.owner_kingdom_id is not None and not state.is_allied(
        target_province.owner_kingdom_id, kingdom_id
    )
    if is_illegal_move_from_contested(origin_contested_by_mover, target_owner_is_enemy):
        raise ValueError("illegal to move from a contested province to an adjacent enemy province")

    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    defenders_present = [
        army
        for army in state.armies_at(target)
        if army.kingdom_id is not None and not state.is_allied(army.kingdom_id, kingdom_id)
    ]
    occupied_by_enemy = bool(armies) and bool(defenders_present)

    move_result = resolve_move(
        current,
        target,
        bounds,
        target_terrain=target_province.terrain,
        target_explored_percent=target_province.explored_percent,
        explorer_skill=explorer_skill,
        occupied_by_enemy=occupied_by_enemy,
    )
    target_province.explored_percent = move_result.exploration.new_percent

    battle_report = None
    conquered = False
    if occupied_by_enemy:
        battle_report = fight_battle(
            state,
            kingdom_id,
            target,
            army_ids,
            loser_retreats=loser_retreats,
            attacker_origin=current,
            rng=rng,
        )
        conquered = battle_report.conquered
        moved = conquered
    else:
        moved = True

    cost = movement_cost_for_move(
        is_sea_province=target_province.terrain == Terrain.SEA,
        battle_occurred=occupied_by_enemy,
        conquered=conquered,
    )

    for army_id in army_ids:
        army = state.armies.get(army_id)
        if army is None:
            continue  # destroyed in the battle
        army.movement_points -= cost
        if moved and army.location == current:
            army.location = target

    if leader_id is not None and moved:
        leader = state.leaders.get(leader_id)
        if leader is not None and leader.location == current:
            leader.location = target

    return MoveExecutionResult(
        moved=moved,
        battle_report=battle_report,
        exploration=move_result.exploration,
        movement_points_spent=cost,
        new_location=target if moved else None,
    )
