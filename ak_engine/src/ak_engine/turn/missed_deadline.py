"""Missed-deadline auto-fill: a King's own leaders default to Defend/Wait -- Phase 134.

Rulebook (quoted by ``turn/plan_dispatch.py``'s own docstring, background
for why Wait/No_Action are "engine-internal" values a player never
types): "the computer ordered Defend actions for your generals" when a
King misses the move-submission deadline. ``HostAK/TP/REPORTS.PAS``'s
own ``Set_Defend`` (~lines 2201-2211), quoted in full:

    PROCEDURE Set_Defend(l2: integer);
    VAR ph: integer;
    BEGIN
      IF AA_Led(l2) > 0 THEN
        WITH lplan^[l2] DO BEGIN
          planstart:= 0; planend:= 4;
          FOR ph:= 0 TO 4 DO IF ((ph = 0) and (AA_Led(l2) > 0)) THEN
              lactions[ph]:= Defend
            ELSE lactions[ph]:= Wait;
          lobjects[0]:= lx[l2]*XMULT+ly[l2];
         END;
     END;

**Phase 134 finding, not previously captured**: the outer ``IF AA_Led(l2)
> 0`` guard means Defend is only ever assigned when the leader actually
commands at least one army (``AA_Led`` = "Army/Armies Led") -- an
armyless leader gets **Wait in every phase, phase 0 included**, not
Defend. (The inner, always-true-when-``ph=0`` condition is dead
structurally once the outer guard already required ``AA_Led(l2) > 0``,
but is transcribed as-is for fidelity.) Previously, this project's own
docstrings (``turn/plan_dispatch.py``, ``turn/aspy_defend_decode.py``)
only cited "Defend (phase 0) then Wait (phases 1-4)" unconditionally --
correct for the common case, but silently wrong for an armyless King's
Hero-only leader.

**``lobjects[0]:= lx[l2]*XMULT+ly[l2]`` needs no numeric encoding
here**: ``turn/defend_execution.py defend_coverage_area()`` (Phase 57)
and ``turn/turn_processor.py run_turn()``'s own DEFEND handling already
compute reactive coverage directly from ``LeaderState.location`` (a
real ``HexCoord``), never from a dispatched Defend phase's own ``obj``
-- so a synthetic phase's ``obj`` is inert placeholder data, the same
as it already effectively is for every real, player-submitted Defend
order this project processes (see ``turn/aspy_defend_decode.py``'s own
docstring on why ``target_province`` stays raw/unconverted and
``turn/defend_execution.py``'s own docstring on why coverage is
computed from the leader's live location instead).

**Not itself a "missed deadline" detector**: this project has no
concept of "did this King's move file arrive by the deadline" (no
move-file-submission timestamp anywhere in ``GameState``) -- that's a
caller-level fact (e.g. "no ``AK3__T12.K1`` exists for kingdom 7 this
turn"), the same "caller supplies what decode/state can't determine"
pattern already used by ``turn/trade_execution.py execute_gold_give()``
(recipient) and ``turn/search_execution.py`` (guardian combat stats).
``build_missed_deadline_plan()`` only builds the *plan* Set_Defend
would have generated once a caller has already established the
precondition; dispatch it exactly like any other parsed
``ActionPlan``, via ``turn/plan_dispatch.py run_leader_plan()``.
"""

from __future__ import annotations

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment

_PHASE_LABELS = ("P0", "P1", "P2", "P3", "P4")


def build_missed_deadline_plan(state: GameState, leader_id: int) -> ActionPlan:
    """Build the Defend/Wait plan ``REPORTS.PAS Set_Defend`` auto-assigns to a King's
    leader who missed the move-submission deadline.

    Phase 0 is ``Defend`` only if ``leader_id`` currently commands at
    least one army (``GameState.armies_commanded_by``, this project's
    own ``AA_Led(l2) > 0``); every other phase -- and phase 0 too, for
    an armyless leader -- is ``Wait``. See module docstring for why
    ``obj``/``extra`` stay at inert placeholder values.
    """

    commands_army = bool(state.armies_commanded_by(leader_id))
    phase0_action = ActionCode.DEFEND if commands_army else ActionCode.WAIT

    phases = {"P0": PlanPhase(label="P0", action=phase0_action, obj=0, extra=[])}
    for label in _PHASE_LABELS[1:]:
        phases[label] = PlanPhase(label=label, action=ActionCode.WAIT, obj=0, extra=[])

    segment = PlanSegment(plan_start=0, plan_end=4, sp=(), phases=phases)
    return ActionPlan(leader_id=leader_id, segments=[segment])
