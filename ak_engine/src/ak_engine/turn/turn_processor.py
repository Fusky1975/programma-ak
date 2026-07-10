"""Multi-leader, phase-by-phase turn processing (Phase 45).

``turn/plan_dispatch.py run_leader_plan()`` processes *one* leader's
entire plan (every phase, in order) before moving to the next leader.
That per-leader-then-next-leader ordering means three already-built
mechanics can never actually trigger from it, because each needs
visibility into every leader's *same-phase* order before any of them
resolve:

- **Multiple Contingents** ([7.8], ``turn/battle_orchestrator.py
  fight_multi_attacker_battle``) -- several leaders attacking the same
  province in the same phase.
- **Practice's [3.13] multi-character coordination** (``turn/
  practice_execution.py resolve_practice_pair``/``_group``) -- 2+
  co-located characters practicing the same ability in the same phase.
- **``contested_province.py``'s forced-rebattle** "in the next phase"
  rule.

This module is a genuinely phase-by-phase orchestrator -- ``run_turn()``
iterates P0..P4 *across every leader's plan at once*, instead of
leader-by-leader -- and wires in the first of the three, Multiple
Contingents. The other two stay unwired this phase (fast follow-ups,
now unblocked structurally): see ``ak_engine/README.md``.

**Detection rule wired in this phase**: when 2+ leaders' LMOVE phases
at the *same* phase label decode to the *same* target province, and at
least 2 of them each independently see a non-allied defending army
there (the same "attacking" criterion ``turn/move_execution.py
execute_move()`` already uses -- a leader-only move, with no army,
never counts), their moves are routed through
``turn/battle_orchestrator.py fight_multi_attacker_battle()`` as one
united scenario instead of N independent solo battles.

**Explicitly out of scope this phase, to keep it tractable**:

- A "mixed" group (some movers see the target as friendly, others as
  hostile) only routes the *hostile* subset through Multiple
  Contingents; peaceful movers dispatch an ordinary independent move,
  unaffected. The rulebook doesn't address this mixed case, so no
  attempt is made to have a peaceful mover "witness" or join the battle.
- Every other action, every non-LMOVE phase, and every leader with no
  competing same-target LMOVE this phase, dispatches exactly the way
  ``turn/plan_dispatch.py`` already handles it -- this module doesn't
  reimplement or change that path, only detects the LMOVE-collision
  case *before* it and routes around it. Concretely, ``_dispatch_single``
  wraps a single ``PlanPhase`` in a throwaway one-segment ``ActionPlan``
  and calls the existing, fully-tested ``run_leader_plan()`` on it --
  reusing its dispatch and nested-plan logic verbatim rather than
  duplicating it, at the cost of every ``PhaseDispatchResult.
  segment_index`` reading ``0`` regardless of the real plan's own
  segment index (real move-file data confirms every leader has exactly
  one top-level segment anyway -- ``models/plan.py``'s own docstring --
  so this loses no real information).
- **Nested-plan dispatch** (Hire/Charm/Resurrection) is unaffected: a
  newly-joined character's own plan still dispatches immediately, in
  full, via ``turn/plan_dispatch.py``'s own nested-plan handling inside
  ``run_leader_plan``. A nested character's own LMOVE never participates
  in *this* phase's Multiple Contingents grouping -- an already-small,
  documented scope limitation (nested dispatch has always run "out of
  band" from the outer phase sequence, even before this module existed).
- **The partial-exploration side effect** for a united multi-attacker
  move is applied *once* per target province per phase (shared), not
  once per attacker -- the rulebook doesn't say whether simultaneous
  arrivals compound it; a documented, unsourced design choice, the same
  category as ``turn/multiple_contingents.py``'s own unite-chance
  constants.
- **Post-battle bookkeeping (movement cost, army/leader relocation) is
  duplicated from ``turn/move_execution.py execute_move()``**, not
  extracted into a shared helper -- deliberately, to avoid touching the
  heavily-tested single-attacker path for this phase.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.turn.battle_orchestrator import MultiAttackerBattle, MultiAttackerParty, fight_multi_attacker_battle
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.contested_province import is_illegal_move_from_contested
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, resolve_move
from ak_engine.turn.plan_dispatch import PhaseDispatchResult, run_leader_plan

PHASE_LABELS = ("P0", "P1", "P2", "P3", "P4")


@dataclass(slots=True)
class TurnLeader:
    leader: Leader
    kingdom_id: int


@dataclass(slots=True)
class MultiAttackerMoveResult:
    moved: bool
    battle: MultiAttackerBattle
    movement_points_spent: int
    new_location: HexCoord | None


def run_turn(
    turn_leaders: list[TurnLeader],
    state: GameState,
    *,
    board_width: int,
    explorer_skill: int = 0,
    rng: random.Random | None = None,
) -> list[PhaseDispatchResult]:
    """Dispatch every ``turn_leaders`` plan phase-by-phase (P0..P4), across all leaders.

    See the module docstring for the Multiple Contingents detection rule
    this enables and everything explicitly still out of scope. Never
    raises on its own (mirrors ``run_leader_plan``'s own convention) --
    a failing phase is recorded with ``error`` set, dispatch continues.
    """

    rng = rng if rng is not None else random.Random()
    results: list[PhaseDispatchResult] = []

    for label in PHASE_LABELS:
        entries = _collect_phase_entries(turn_leaders, label)

        move_targets: dict[int, HexCoord] = {}
        for index, (_tl, _segment_index, phase) in enumerate(entries):
            if phase.action is ActionCode.LMOVE:
                try:
                    move_targets[index] = decode_hex_number(phase.obj, board_width)
                except ValueError:
                    pass  # left for the ordinary per-leader path to raise/record consistently

        target_groups: dict[HexCoord, list[int]] = {}
        for index, target in move_targets.items():
            target_groups.setdefault(target, []).append(index)

        multi_attacker_groups: list[tuple[HexCoord, list[int]]] = []
        for target, indices in target_groups.items():
            if len(indices) < 2:
                continue
            attacking = [i for i in indices if _sees_nonallied_defender(entries[i], target, state)]
            if len(attacking) >= 2:
                multi_attacker_groups.append((target, attacking))

        consumed = {index for _target, indices in multi_attacker_groups for index in indices}

        for target, indices in multi_attacker_groups:
            movers = [entries[i] for i in indices]
            results.extend(_dispatch_multi_attacker_lmove(movers, target, state, board_width, explorer_skill, rng))

        for index, (tl, segment_index, phase) in enumerate(entries):
            if index in consumed:
                continue
            results.extend(_dispatch_single(tl, segment_index, phase, state, board_width, explorer_skill, rng))

    return results


def _collect_phase_entries(
    turn_leaders: list[TurnLeader], label: str
) -> list[tuple[TurnLeader, int, PlanPhase]]:
    entries = []
    for tl in turn_leaders:
        for segment_index, segment in enumerate(tl.leader.plan.segments):
            phase = segment.phases.get(label)
            if phase is not None:
                entries.append((tl, segment_index, phase))
    return entries


def _sees_nonallied_defender(
    entry: tuple[TurnLeader, int, PlanPhase], target: HexCoord, state: GameState
) -> bool:
    """Same "attacking" criterion ``execute_move`` uses: a mover with no army never
    triggers combat, regardless of what's at the target (rulebook [3.1]).
    """

    tl, _segment_index, _phase = entry
    if not state.armies_commanded_by(tl.leader.leader_id):
        return False
    return any(
        army.kingdom_id is not None and not state.is_allied(army.kingdom_id, tl.kingdom_id)
        for army in state.armies_at(target)
    )


def _dispatch_single(
    tl: TurnLeader,
    segment_index: int,
    phase: PlanPhase,
    state: GameState,
    board_width: int,
    explorer_skill: int,
    rng: random.Random,
) -> list[PhaseDispatchResult]:
    """Dispatch exactly one phase via the existing, fully-tested ``run_leader_plan`` --
    see module docstring for why this wraps rather than duplicates it.
    """

    wrapper = Leader(
        leader_id=tl.leader.leader_id,
        name=tl.leader.name,
        plan=ActionPlan(leader_id=tl.leader.leader_id, segments=[PlanSegment(0, 0, (), {phase.label: phase})]),
    )
    return run_leader_plan(wrapper, state, tl.kingdom_id, board_width=board_width, explorer_skill=explorer_skill, rng=rng)


def _dispatch_multi_attacker_lmove(
    movers: list[tuple[TurnLeader, int, PlanPhase]],
    target: HexCoord,
    state: GameState,
    board_width: int,
    explorer_skill: int,
    rng: random.Random,
) -> list[PhaseDispatchResult]:
    results: list[PhaseDispatchResult] = []
    target_province = state.provinces.get(target)
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)

    parties: list[MultiAttackerParty] = []
    valid: list[tuple[TurnLeader, int, PlanPhase, list[int], HexCoord]] = []
    exploration_new_percent: int | None = None

    for tl, segment_index, phase in movers:
        army_ids = [army.army_id for army in state.armies_commanded_by(tl.leader.leader_id)]
        armies = [state.armies[army_id] for army_id in army_ids]
        origin = armies[0].location if armies else state.leaders[tl.leader.leader_id].location

        try:
            if target_province is None:
                raise ValueError(f"no province data for {target}")
            origin_province = state.provinces.get(origin)
            origin_contested_by_mover = (
                origin_province is not None and origin_province.contested_by_kingdom_id == tl.kingdom_id
            )
            target_owner_is_enemy = target_province.owner_kingdom_id is not None and not state.is_allied(
                target_province.owner_kingdom_id, tl.kingdom_id
            )
            if is_illegal_move_from_contested(origin_contested_by_mover, target_owner_is_enemy):
                raise ValueError("illegal to move from a contested province to an adjacent enemy province")
            move_result = resolve_move(
                origin,
                target,
                bounds,
                target_terrain=target_province.terrain,
                target_explored_percent=target_province.explored_percent,
                explorer_skill=explorer_skill,
                occupied_by_enemy=True,
            )
            exploration_new_percent = move_result.exploration.new_percent
        except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
            results.append(PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, None, exc))
            continue

        parties.append(
            MultiAttackerParty(leader_id=tl.leader.leader_id, kingdom_id=tl.kingdom_id, army_ids=army_ids, origin_province=origin)
        )
        valid.append((tl, segment_index, phase, army_ids, origin))

    if target_province is not None and exploration_new_percent is not None:
        target_province.explored_percent = exploration_new_percent

    if len(parties) < 2:
        # Not enough survived validation to actually unite -- whoever's
        # left dispatches individually and normally instead.
        for tl, segment_index, phase, _army_ids, _origin in valid:
            results.extend(_dispatch_single(tl, segment_index, phase, state, board_width, explorer_skill, rng))
        return results

    battles = fight_multi_attacker_battle(state, target, parties, rng=rng)
    battle_by_leader = {leader_id: battle for battle in battles for leader_id in battle.leader_ids}

    for tl, segment_index, phase, army_ids, origin in valid:
        battle = battle_by_leader[tl.leader.leader_id]
        conquered = battle.report.conquered
        cost = movement_cost_for_move(
            is_sea_province=target_province.terrain == Terrain.SEA, battle_occurred=True, conquered=conquered
        )
        moved = conquered

        for army_id in army_ids:
            army = state.armies.get(army_id)
            if army is None:
                continue  # destroyed in the battle
            army.movement_points -= cost
            if moved and army.location == origin:
                army.location = target

        leader_state = state.leaders.get(tl.leader.leader_id)
        if moved and leader_state is not None and leader_state.location == origin:
            leader_state.location = target

        result = MultiAttackerMoveResult(
            moved=moved, battle=battle, movement_points_spent=cost, new_location=target if moved else None
        )
        results.append(PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, result, None))

    return results
