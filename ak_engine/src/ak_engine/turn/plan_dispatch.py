"""Dispatching a parsed Leader's ActionPlan phases to turn/* resolvers.

Bridges Phase 1's parsed move-file model (``models.kingdom.Kingdom`` ->
``Leader`` -> ``ActionPlan`` -> ``PlanSegment`` -> ``PlanPhase(action, obj,
extra)``) to the turn-resolution functions built in later phases -- the
integration step flagged as the single largest remaining gap after Phase
10.

Three ``ActionCode``s have recovered enough of their target semantics to
dispatch automatically:

- **LMOVE**: ``obj`` is the move's target hex number, decoded via
  ``turn/hex_numbering.py`` (an empirical inference, not a certainty --
  see that module's docstring).
- **EXPLORE**: no target decoding needed -- explores the mover's current
  province.
- **RECRUIT**: ``obj``/``extra`` decoded via ``turn/recruit_decode.py``
  into a target leader id and a list of requested ``ArmyType``s, then
  priced per type via ``turn/recruit.py resolve_recruit()``. This only
  *prices* the request (limits and gold cost) -- it does NOT create new
  armies or debit a treasury, since ``GameState`` has no treasury balance
  or "recruit executed" bookkeeping yet (see ``ak_engine/README.md``).
  ``is_native_to_province`` is approximated as race-compatibility
  (``turn/recruit.py is_army_type_compatible_with_race``) since
  ``GameState`` doesn't track the rulebook's more specific "1-2
  recruitable types per province" data -- a documented simplification,
  not the literal rule.

- **RECRUIT** priced via ``turn/recruit.py resolve_recruit()`` per
  requested type -- but only *prices* it (limits and gold cost); it does
  NOT create new armies or debit a treasury, since ``GameState`` has no
  treasury balance or "recruit executed" bookkeeping yet (see
  ``ak_engine/README.md``). ``is_native_to_province`` is approximated as
  race-compatibility (``turn/recruit.py is_army_type_compatible_with_race``)
  since ``GameState`` doesn't track the rulebook's more specific "1-2
  recruitable types per province" data -- a documented simplification,
  not the literal rule.
- **LEAVE** and **PICK_UP** actually mutate ``ArmyState.commanded_by``
  (Phase 14's leader-army command model, ``models.game_state.LeaderState``)
  -- Leave transfers command to the requested leader (or clears it, for
  the garrison), also transferring ``kingdom_id`` if left in an ally's
  province ("the army then belongs to the ally", rulebook [3.8]); Pick_Up
  attaches co-located armies (or, for "Pick Up All", every *unled*
  co-located army) to the acting leader.
- **DISBAND** still decode-only: releasing an army "into mercenary
  status" (rulebook [3.6]) needs a way to represent an unowned army,
  which needs a nullable ``ArmyState.kingdom_id`` (or a separate
  mercenary pool) -- neither exists yet, so Disband is decoded but not
  applied.

Every other ``ActionCode`` raises ``UnsupportedActionError``.

Every dispatch call takes an explicit ``leader_id`` -- the acting
character -- and ``army_ids`` defaults to whatever that leader currently
commands (``GameState.armies_commanded_by``) unless the caller overrides
it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.leader import Leader
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.army_list_decode import ArmyListRequest, decode_army_list_phase
from ak_engine.turn.exploration import resolve_explore
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.move_execution import execute_move
from ak_engine.turn.recruit import IncompatibleRaceError, RecruitResolution, is_army_type_compatible_with_race, resolve_recruit
from ak_engine.turn.recruit_decode import RecruitRequest, decode_recruit_phase

SUPPORTED_ACTIONS = frozenset(
    {
        ActionCode.LMOVE,
        ActionCode.EXPLORE,
        ActionCode.RECRUIT,
        ActionCode.DISBAND,
        ActionCode.LEAVE,
        ActionCode.PICK_UP,
    }
)


@dataclass(slots=True)
class RecruitDispatchResult:
    request: RecruitRequest
    resolutions: list[tuple[Any, RecruitResolution | IncompatibleRaceError]] = field(default_factory=list)


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
    leader_id: int,
    army_ids: list[int] | None = None,
    *,
    board_width: int,
    explorer_skill: int = 0,
    rng: random.Random | None = None,
):
    """Execute one PlanPhase's action against ``state``, as commanded by ``leader_id``.

    ``army_ids`` defaults to whatever ``leader_id`` currently commands
    (``state.armies_commanded_by``); pass an explicit list to override.

    Raises ``UnsupportedActionError`` for anything outside
    ``SUPPORTED_ACTIONS``, and propagates whatever ``execute_move``/
    ``resolve_explore`` themselves raise (e.g. ``NonAdjacentMoveError``,
    a ``KeyError`` for an unknown province or leader).
    """

    action = phase.action
    if action not in SUPPORTED_ACTIONS:
        label = action.name if isinstance(action, ActionCode) else repr(action)
        raise UnsupportedActionError(f"no turn/* resolver implemented yet for action {label}")

    if army_ids is None:
        army_ids = [army.army_id for army in state.armies_commanded_by(leader_id)]

    if action is ActionCode.LMOVE:
        target = decode_hex_number(phase.obj, board_width)
        return execute_move(
            state, kingdom_id, army_ids, target, leader_id=leader_id, explorer_skill=explorer_skill, rng=rng
        )

    if action is ActionCode.EXPLORE:
        province = state.provinces[state.leaders[leader_id].location]
        result = resolve_explore(province.explored_percent, province.terrain, explorer_skill)
        province.explored_percent = result.new_percent
        return result

    if action is ActionCode.RECRUIT:
        return _dispatch_recruit(phase, state, kingdom_id, leader_id)

    if action is ActionCode.LEAVE:
        return _dispatch_leave(phase, state, leader_id)

    if action is ActionCode.PICK_UP:
        return _dispatch_pick_up(phase, state, leader_id)

    if action is ActionCode.DISBAND:
        return decode_army_list_phase(phase)

    raise AssertionError("unreachable: action was checked against SUPPORTED_ACTIONS above")


def _dispatch_recruit(phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int) -> RecruitDispatchResult:
    request = decode_recruit_phase(phase)
    location = state.leaders[leader_id].location
    province = state.provinces[location]
    kingdom = state.kingdoms[kingdom_id]

    is_home_province = location == kingdom.home_province
    in_ally_territory = (
        province.owner_kingdom_id is not None
        and province.owner_kingdom_id != kingdom_id
        and state.is_allied(province.owner_kingdom_id, kingdom_id)
    )

    resolutions: list[tuple[Any, RecruitResolution | IncompatibleRaceError]] = []
    for army_type in request.army_types:
        is_native = is_army_type_compatible_with_race(army_type, province.race)
        try:
            resolution = resolve_recruit(
                army_type,
                province.race,
                is_home_province=is_home_province,
                is_native_to_province=is_native,
                in_ally_territory=in_ally_territory,
            )
        except IncompatibleRaceError as exc:
            resolution = exc
        resolutions.append((army_type, resolution))

    return RecruitDispatchResult(request=request, resolutions=resolutions)


def _dispatch_leave(phase: PlanPhase, state: GameState, leader_id: int) -> ArmyListRequest:
    request = decode_army_list_phase(phase)
    target_ids = (
        [army.army_id for army in state.armies_commanded_by(leader_id)] if request.all_armies else request.army_ids
    )

    for army_id in target_ids:
        army = state.armies.get(army_id)
        if army is None:
            continue
        army.commanded_by = request.target_leader_id
        province = state.provinces.get(army.location)
        if (
            province is not None
            and province.owner_kingdom_id is not None
            and province.owner_kingdom_id != army.kingdom_id
            and state.is_allied(province.owner_kingdom_id, army.kingdom_id)
        ):
            # "If you Leave an army in an ally's province, the army then
            # belongs to the ally." (rulebook [3.8])
            army.kingdom_id = province.owner_kingdom_id

    return request


def _dispatch_pick_up(phase: PlanPhase, state: GameState, leader_id: int) -> ArmyListRequest:
    request = decode_army_list_phase(phase)
    acting_leader = state.leaders[leader_id]

    if request.all_armies:
        # "Pick Up All UNLED armies (with Garrison Commander) in the province."
        target_ids = [
            army.army_id for army in state.armies_at(acting_leader.location) if army.commanded_by is None
        ]
    else:
        target_ids = request.army_ids

    for army_id in target_ids:
        army = state.armies.get(army_id)
        if army is None or army.location != acting_leader.location:
            continue  # rulebook: can only pick up a co-located army
        army.commanded_by = leader_id

    return request


def run_leader_plan(
    leader: Leader,
    state: GameState,
    kingdom_id: int,
    army_ids: list[int] | None = None,
    *,
    board_width: int,
    explorer_skill: int = 0,
    rng: random.Random | None = None,
) -> list[PhaseDispatchResult]:
    """Attempt every phase (in order, across all segments) of ``leader``'s plan.

    ``army_ids`` defaults to whatever ``leader.leader_id`` currently
    commands in ``state`` (re-evaluated fresh for each phase, so a
    Pick_Up/Leave earlier in the plan changes what a later LMOVE brings
    along); pass an explicit list to pin it instead.

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
                    leader.leader_id,
                    army_ids,
                    board_width=board_width,
                    explorer_skill=explorer_skill,
                    rng=rng,
                )
                results.append(PhaseDispatchResult(segment_index, label, phase.action, result, None))
            except Exception as exc:  # noqa: BLE001 -- intentionally broad, see docstring
                results.append(PhaseDispatchResult(segment_index, label, phase.action, None, exc))
    return results
