"""Dispatching a parsed Leader's ActionPlan phases to turn/* resolvers.

Bridges Phase 1's parsed move-file model (``models.kingdom.Kingdom`` ->
``Leader`` -> ``ActionPlan`` -> ``PlanSegment`` -> ``PlanPhase(action, obj,
extra)``) to the turn-resolution functions built in later phases -- the
integration step flagged as the single largest remaining gap after Phase
10.

Only two ``ActionCode``s have recovered enough of their target semantics
to dispatch automatically:

- **LMOVE**: ``obj`` is the move's target hex number, decoded via
  ``turn/hex_numbering.py`` (an empirical inference, not a certainty --
  see that module's docstring).
- **EXPLORE**: no target decoding needed -- explores the mover's current
  province.

Every other ``ActionCode`` raises ``UnsupportedActionError``. Some are
partially understood structurally (the rulebook plus
``HostAK/TP/DEF2.PAS``'s ``Read_HPlan`` show Recruit's targets are a
``-1``-terminated army-type list in ``PlanPhase.extra``, and
Leave/Disband/Pick_Up's are an army-id list the same way) but decoding
them needs the original army-type enum's *ordinal* order from
``CTBOTH.PAS``, which this project's ``ArmyType`` enum (string-valued,
reordered for readability) doesn't preserve -- fixing that is future
work, not done here.

This module also does not know which armies a leader commands --
``models.game_state.ArmyState`` has no leader-to-army link yet (same gap
noted in Phase 10's README for ``execute_move``/``fight_battle``) -- so
``army_ids`` is always an explicit, caller-supplied parameter.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.leader import Leader
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.exploration import resolve_explore
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.move_execution import execute_move

SUPPORTED_ACTIONS = frozenset({ActionCode.LMOVE, ActionCode.EXPLORE})


class UnsupportedActionError(NotImplementedError):
    """Raised for a PlanPhase whose action has no turn/* resolver wired up yet."""


@dataclass(slots=True)
class PhaseDispatchResult:
    segment_index: int
    phase_label: str
    action: Any
    result: Any | None
    error: Exception | None


def dispatch_phase(
    phase: PlanPhase,
    state: GameState,
    kingdom_id: int,
    army_ids: list[int],
    *,
    board_width: int,
    explorer_skill: int = 0,
    rng: random.Random | None = None,
):
    """Execute one PlanPhase's action against ``state``.

    Raises ``UnsupportedActionError`` for anything outside
    ``SUPPORTED_ACTIONS``, and propagates whatever ``execute_move``/
    ``resolve_explore`` themselves raise (e.g. ``NonAdjacentMoveError``,
    a ``KeyError`` for an unknown province).
    """

    action = phase.action
    if action not in SUPPORTED_ACTIONS:
        label = action.name if isinstance(action, ActionCode) else repr(action)
        raise UnsupportedActionError(f"no turn/* resolver implemented yet for action {label}")

    if action is ActionCode.LMOVE:
        target = decode_hex_number(phase.obj, board_width)
        return execute_move(state, kingdom_id, army_ids, target, explorer_skill=explorer_skill, rng=rng)

    if action is ActionCode.EXPLORE:
        army = state.armies[army_ids[0]]
        province = state.provinces[army.location]
        result = resolve_explore(province.explored_percent, province.terrain, explorer_skill)
        province.explored_percent = result.new_percent
        return result

    raise AssertionError("unreachable: action was checked against SUPPORTED_ACTIONS above")


def run_leader_plan(
    leader: Leader,
    state: GameState,
    kingdom_id: int,
    army_ids: list[int],
    *,
    board_width: int,
    explorer_skill: int = 0,
    rng: random.Random | None = None,
) -> list[PhaseDispatchResult]:
    """Attempt every phase (in order, across all segments) of ``leader``'s plan.

    Never raises: an unsupported or failing phase is recorded in the
    returned list (``error`` set, ``result`` None) so the run continues
    through the rest of the plan instead of stopping at the first gap --
    the whole point of this function is to produce a full report against
    a real parsed turn, where most actions are still unsupported.
    """

    results: list[PhaseDispatchResult] = []
    for segment_index, segment in enumerate(leader.plan.segments):
        for label in ("P0", "P1", "P2", "P3", "P4"):
            phase = segment.phases.get(label)
            if phase is None:
                continue
            try:
                result = dispatch_phase(
                    phase,
                    state,
                    kingdom_id,
                    army_ids,
                    board_width=board_width,
                    explorer_skill=explorer_skill,
                    rng=rng,
                )
                results.append(PhaseDispatchResult(segment_index, label, phase.action, result, None))
            except Exception as exc:  # noqa: BLE001 -- intentionally broad, see docstring
                results.append(PhaseDispatchResult(segment_index, label, phase.action, None, exc))
    return results
