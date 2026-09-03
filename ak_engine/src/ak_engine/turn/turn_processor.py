"""Multi-leader, phase-by-phase turn processing (Phase 45; Practice coordination
Phase 46; contested-province forced rebattle Phase 55; mutual Challenge/
Pursue detection Phase 56).

``turn/plan_dispatch.py run_leader_plan()`` processes *one* leader's
entire plan (every phase, in order) before moving to the next leader.
That per-leader-then-next-leader ordering means three already-built
mechanics can never actually trigger from it, because each needs
visibility into every leader's *same-phase* order before any of them
resolve:

- **Multiple Contingents** ([7.8], ``turn/battle_orchestrator.py
  fight_multi_attacker_battle``) -- several leaders attacking the same
  province in the same phase. Wired in as of Phase 45.
- **Practice's [3.13] multi-character coordination** (``turn/
  practice_execution.py resolve_practice_pair``/``_group``/
  ``execute_practice_group``) -- 2+ co-located characters practicing
  the same ability in the same phase. Wired in as of Phase 46.
- **``contested_province.py``'s forced-rebattle** "in the next phase"
  rule ([7.6]) -- needs to run at every phase *boundary*, independent of
  any leader's own order that phase. Wired in as of Phase 55, see
  ``_dispatch_contested_rebattles``'s own docstring.

A fourth mechanic needs the same same-phase, cross-leader visibility,
flagged when Challenge/Pursue execution itself was wired into
``plan_dispatch.py`` (Phase 54): a King target's own ``mutual_encounter``
requirement ([3.12]) can only be determined by seeing whether the target
*also* ordered a Challenge/Pursue back this same phase. Wired in as of
Phase 56, see ``_dispatch_mutual_encounter``'s own docstring.

This module is a genuinely phase-by-phase orchestrator -- ``run_turn()``
iterates P0..P4 *across every leader's plan at once*, instead of
leader-by-leader.

**LMOVE detection rule (Phase 45)**: when 2+ leaders' LMOVE phases
at the *same* phase label decode to the *same* target province, and at
least 2 of them each independently see a non-allied defending army
there (the same "attacking" criterion ``turn/move_execution.py
execute_move()`` already uses -- a leader-only move, with no army,
never counts), their moves are routed through
``turn/battle_orchestrator.py fight_multi_attacker_battle()`` as one
united scenario instead of N independent solo battles.

**PRACTICE detection rule (Phase 46)**: when 2+ leaders' PRACTICE
phases at the *same* phase label decode to the *same* ``Ability`` AND
those leaders' current locations (``LeaderState.location``, read before
any of this phase's actions run) are the *same* province, they're
routed through ``turn/practice_execution.py execute_practice_group()``
together instead of each resolving solo. **No alliance/kingdom
requirement** -- unlike Multiple Contingents, the rulebook's own text
("If 2 or more characters are in the same province...") never mentions
kingdom membership at all, so this groups purely by co-location, across
any kingdoms. ``Ability.TACTICAL`` groups the same as any other ability
(so ``execute_practice_group`` still sees the collision), but resolves
through the [6.1] army-pooling mechanic instead of the ordinary
skill-rise mechanic -- see that function's own Phase 304 note. An
undecoded raw (non-``Ability``) value still resolves to
``not_implemented_for_ability=True`` for the whole group, same as the
solo path.

**MUTUAL ENCOUNTER detection rule (Phase 56)**: when leader A's CHALLENGE
or PURSUE phase at a given phase label targets leader B, and leader B's
own CHALLENGE or PURSUE phase at that *same* label targets A back, the
pair is resolved as one shared encounter via ``_dispatch_mutual_encounter``
instead of each dispatching solo -- see that function's own docstring for
the single-shared-resolution design (confirmed with the user) and the
King-target initiator rule. A self-targeting Pursue (rulebook [3.16]
"Patrol") is never treated as a mutual pair with itself.

**DEFEND CANCELLATION rule (Phase 67)**: ``_apply_defend_cancellations``
removes a leader from ``active_defends`` the moment their own plan
reaches an LMOVE/PURSUE/TRAIL phase -- rulebook [3.15]: "If he receives
a Move, Pursue or Trail order, the Defend order is cancelled." Runs
before ``_apply_defend_reinforcements`` each phase, so a leader who's
moving/pursuing/trailing this phase no longer reacts to an invasion
this same phase either. **Phase 652 correction, kept for the record**:
an earlier version of this note called the rulebook's other trigger
("cancelled if he loses a battle") "a distinct, still-open gap" --
stale even when written, contradicted by ``_apply_defend_
cancellations``'s own docstring two paragraphs below it in this same
file: that trigger is handled separately (Phase 72, via the persistent
``defeated_while_defending`` set) -- see that function's own docstring
for the full account.

**PERSISTENT PURSUE/TRAIL CHASE (Phase 70)**: rulebook [3.16]: "A
character can be ordered to chase after another character for the
rest of the turn... You can specify other actions on phases 2 through
5 which will be attempted if the pursuit is resolved before the end
of the gameturn." An unresolved Pursue or Trail now genuinely preempts
that leader's own later-phase orders: at the start of each phase, any
leader still listed in ``active_pursuits`` has their real plan entry
for *this* phase dropped entirely from ``entries`` before any grouping
detection runs, and ``_continue_active_pursuits`` dispatches one
``turn/pursue_execution.py advance_pursuit``/``turn/trail_execution.py
advance_trail`` step for them instead (``segment_index=-1`` sentinel,
same convention as ``_dispatch_contested_rebattles``, since this
dispatch isn't tied to any real plan segment). The chase ends the
moment ``advance_pursuit``/``advance_trail`` reports resolution (any
``caught_up``/``spied_on`` outcome, including a refused encounter or a
terminal not-found/army-mismatch reason) -- only the exact "did not
catch up this phase"/"did not find the target this phase" reason keeps
it alive into the next phase. A freshly-dispatched PURSUE/TRAIL phase
(via the ordinary ``_dispatch_single`` path at the end of this
function) that comes back unresolved the same way is registered into
``active_pursuits`` for the *next* phase onward, via
``_register_pursuit_continuation``.

**A documented reading of "resolved... will be attempted", not a
rulebook quote**: resolution is checked once per phase, at that
phase's own start -- if the chase resolves *during* a phase's own
continuation dispatch, that same phase's original order is still lost
(it was already dropped from ``entries`` before the outcome was
known); only the *following* phase's order, if any, dispatches
normally. The rulebook doesn't disambiguate same-phase ordering here,
so this follows the same "process what's known at the start of the
phase" principle Defend cancellation and Defend reinforcement already
use.

**Explicitly still out of scope, confirmed with the user as a scoped
step rather than the whole approved ask**: "Characters On Patrol"
(self-targeting Pursue, [3.16]) is never registered for persistence --
a self-targeting Pursue's own detect-any-adjacent-enemy semantics are
structurally different from directed chase-toward-one-target and would
need a different implementation, not attempted here. Defend's other
cancellation trigger ("cancelled if he loses a battle") is handled via
the persistent ``defeated_while_defending`` set -- see ``_apply_
defend_cancellations``'s own docstring for the full account, not a
gap. A Pursue/Trail resolved via the *mutual-encounter* dispatch path
is
never registered for persistence either -- only the plain single-leader
``_dispatch_single`` path is, keeping continuation detection to the
common case (PURSUE never participates in the multi-attacker LMOVE
path in the first place). Continuation steps carry no movement-point
cost and never trigger Defend reinforcement (a continuing pursuer's
hex-step never appears in ``move_targets``), matching
``advance_pursuit``/``advance_trail``'s own already-documented scope.

**PERSISTENT MOVE CHASE (Phase 632)**: rulebook [3.1]: "The movement
order will override orders in a subsequent phase only if the character
is practicing in that phase." ``turn/move_execution.py execute_move()``
(Phase 85) already resolves a non-adjacent target as a chase, one
hex-step per call -- what was still missing was the *persistence*
itself. Two readings were laid out in that module's own docstring
(narrow: only a later Practice order is overridden; broad: blanket
preemption of every subsequent order, mirroring Pursue/Trail exactly)
-- **the user directly confirmed the broad reading**, so this reuses
the exact same mechanism as "PERSISTENT PURSUE/TRAIL CHASE" above, just
simpler: Move's own chase-stepping already lives inside
``execute_move()`` itself, so a continuation is just re-dispatching the
*same* ordinary LMOVE phase again (via ``_dispatch_single``) with the
same ultimate target -- no dedicated ``advance_*`` function needed the
way Pursue/Trail's own mechanics required. ``active_move_chases``
(leader_id -> ``_ActiveMoveChase``) is checked alongside
``active_pursuits`` in the same preemption filter and the same
continuation-dispatch call; ``_register_move_chase_continuation`` re-
registers a still-unresolved chase (``MoveExecutionResult.reached_
target`` and ``.stopped_chasing`` both ``False``) for the next phase,
mirroring ``_register_pursuit_continuation``'s own shape. Like Pursue/
Trail, this only ever registers from the plain single-leader
``_dispatch_single`` path -- ``_dispatch_multi_attacker_lmove()``'s own
grouped-battle path assumes an already-adjacent shared target and never
calls ``step_toward_non_adjacent_target()`` at all, so extending chase
persistence there is a separate, unattempted question.

**PLAGUE SPREAD rule (Phase 233, extended Phase 234)**: ``turn/plague_
spread.py resolve_plague_spread()`` runs at the same phase-boundary
point as ``_dispatch_contested_rebattles`` -- rulebook [4.25.3]'s own
"the next phase, there is a 15% chance per adjacent province that the
plague will spread" is, read literally, exactly this project's own
phase-by-phase loop boundary. Each newly-infected coordinate it returns
is wrapped into its own ``PhaseDispatchResult`` (``leader_id=0``,
``segment_index=-1``, ``phase_label="plague-spread"``, ``action=None``,
``result=<the HexCoord itself>``) -- the same "not tied to any leader's
own plan segment" sentinel convention ``_dispatch_contested_rebattles``
already established for its own ``"forced-rebattle"`` entries -- so
``report/turn_report.py record_plague_spread_world_events()`` (Phase
234) can find them in ``run_turn()``'s own return value exactly the way
``record_battle_world_events()``/``record_spell_world_events()``
already read `results` for their own sources.

**Explicitly out of scope, to keep this tractable**:

- A "mixed" LMOVE group (some movers see the target as friendly, others
  as hostile) only routes the *hostile* subset through Multiple
  Contingents; peaceful movers dispatch an ordinary independent move,
  unaffected. The rulebook doesn't address this mixed case, so no
  attempt is made to have a peaceful mover "witness" or join the battle.
- Every other action, every non-LMOVE/non-PRACTICE phase, and every
  leader with no competing same-target/same-ability collision this
  phase, dispatches exactly the way ``turn/plan_dispatch.py`` already
  handles it -- this module doesn't reimplement or change that path,
  only detects the two collision cases above *before* it and routes
  around them. Concretely, ``_dispatch_single``
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
  ``run_leader_plan``. A nested character's own LMOVE or PRACTICE never
  participates in *this* phase's Multiple Contingents/Practice grouping
  -- an already-small, documented scope limitation (nested dispatch has
  always run "out of band" from the outer phase sequence, even before
  this module existed).
- **The partial-exploration side effect** for a united multi-attacker
  move is applied *once* per target province per phase (shared), not
  once per attacker -- the rulebook doesn't say whether simultaneous
  arrivals compound it; a documented, unsourced design choice (unlike
  ``turn/multiple_contingents.py``'s own unite-chance formula, which is
  real, sourced MARCH TABLE data as of Phase 307, not an invented
  constant).
- **Post-battle bookkeeping (movement cost, army/leader relocation) is
  duplicated from ``turn/move_execution.py execute_move()``**, not
  extracted into a shared helper -- deliberately, to avoid touching the
  heavily-tested single-attacker path for this phase.

**Missed-deadline auto-fill (Phase 138)**: ``build_missed_deadline_turn_leaders()``
wires ``turn/missed_deadline.py build_missed_deadline_plan()`` (Phase
134) into this module's own ``TurnLeader`` shape -- a caller who
already knows a kingdom submitted no move file this turn builds that
kingdom's own ``Defend``/``Wait`` auto-fill leaders with it and merges
them into the ``turn_leaders`` list passed to ``run_turn()``, exactly
like any real, parsed plan. ``run_turn()`` itself has no "did this
kingdom submit a move file" detection built in (``GameState`` tracks
no such timestamp anywhere), so this stays a caller-invoked helper,
not automatic behavior inside ``run_turn()``.

**GATE ANGEL / VALHALLA VISIT (Phase 199)**: ``turn/valhalla_execution.py
finalize_gate_angel_visit()`` (Phase 196, deliberately left unwired at
the time) is now called exactly once, after the ``PHASE_LABELS`` loop
completes -- never inside it. Its own docstring requires this: a Gate
Angel cast can succeed on any of P0-P4, and a later same-turn,
same-due-alignment cast can still steal the reservoir-sampling win
(``turn/cast_execution.py``'s own "Phase 195 addendum") right up
through the last phase, so calling it any earlier risks spawning the
visitor for a kingdom that a later phase's own cast displaces. When a
visitor is spawned, one sentinel ``PhaseDispatchResult`` is appended
(``segment_index=-1``, ``phase_label="gate-angel-visit"``,
``action=None``, ``result`` the new ``LeaderState``) -- the same
not-tied-to-a-real-plan-segment convention ``_dispatch_contested_rebattles``
already uses for "forced-rebattle". No result is appended when no Gate
Angel cast succeeded this turn.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.army_type import ARMY_TABLE, ArmyType
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.turn.battle_orchestrator import (
    MultiAttackerBattle,
    MultiAttackerParty,
    fight_battle,
    fight_multi_attacker_battle,
)
from ak_engine.turn.aspy_defend_decode import decode_defend_phase
from ak_engine.turn.blackmail import advance_blackmail_claims
from ak_engine.turn.sea_transport import apply_battle_carrier_destruction
from ak_engine.turn.cast_execution import maybe_dissolve_illusory_terrain
from ak_engine.turn.challenge_execution import execute_challenge
from ak_engine.turn.challenge_pursue_decode import decode_challenge_phase, decode_pursue_phase
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.defend_execution import DefendCoverage, DefendReinforcement, defend_coverage_area, defend_radius_for_leader
from ak_engine.turn.expenses import apply_turn_maintenance
from ak_engine.turn.contested_province import (
    IllegalMoveFromContestedError,
    attacker_can_force_rebattle,
    contested_battle_movement_cost,
    is_illegal_move_from_contested,
)
from ak_engine.turn.hex_numbering import decode_hex_number, encode_hex_number
from ak_engine.turn.plague_spread import resolve_plague_spread
from ak_engine.turn.missed_deadline import build_missed_deadline_plan
from ak_engine.turn.move_execution import MoveExecutionResult, record_kingdom_exploration, reveal_adjacent_provinces
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, resolve_move
from ak_engine.turn.office_holder import apply_battle_fool_aptitude_escalation, apply_cravenest_temperament_escalation
from ak_engine.turn.plan_dispatch import PhaseDispatchResult, dispatch_phase, run_leader_plan
from ak_engine.turn.practice_decode import decode_practice_phase
from ak_engine.turn.practice_execution import execute_practice_group
from ak_engine.turn.patrol_execution import execute_patrol
from ak_engine.turn.pursue_execution import PursueExecutionResult, advance_pursuit, execute_pursue
from ak_engine.turn.sep_decode import decode_special_encounter_plan
from ak_engine.turn.skeletal_decay import decompose_graveyard
from ak_engine.turn.monster_raids import age_all_feature_guardians, maybe_dissipate_hidden_feature
from ak_engine.turn.tax_base import apply_turn_revenue
from ak_engine.turn.trail_decode import decode_trail_phase
from ak_engine.turn.trail_execution import TrailExecutionResult, advance_trail
from ak_engine.turn.valhalla_execution import finalize_gate_angel_visit, process_valhalla_departure

PHASE_LABELS = ("P0", "P1", "P2", "P3", "P4")


@dataclass(slots=True)
class TurnLeader:
    leader: Leader
    kingdom_id: int


def build_missed_deadline_turn_leaders(state: GameState, kingdom_id: int) -> list[TurnLeader]:
    """Build a ``TurnLeader`` for every leader belonging to ``kingdom_id``, using
    ``turn/missed_deadline.py build_missed_deadline_plan()`` -- the
    ``REPORTS.PAS Set_Defend`` auto-fill (Phase 134) for a King who
    missed the move-submission deadline entirely.

    ``kingdom_id`` is caller-supplied, not auto-detected: ``GameState``
    has no move-file-submission-timestamp concept anywhere (see ``turn/
    missed_deadline.py``'s own docstring), so a caller who already knows
    "no move file arrived for this kingdom this turn" merges this
    function's own output into the ``turn_leaders`` list passed to
    ``run_turn()``, exactly like any real, parsed plan.
    """

    turn_leaders: list[TurnLeader] = []
    for leader_id, leader_state in state.leaders.items():
        if leader_state.kingdom_id != kingdom_id:
            continue
        plan = build_missed_deadline_plan(state, leader_id)
        turn_leaders.append(TurnLeader(Leader(leader_id, leader_state.name, plan), kingdom_id))
    return turn_leaders


@dataclass(slots=True)
class _ActivePursuit:
    """One leader's still-unresolved Pursue/Trail, carried across phases -- see the
    module docstring's "PERSISTENT PURSUE/TRAIL CHASE" section.
    """

    kind: str  # "pursue" or "trail"
    request: object  # PursueRequest for "pursue", TrailRequest for "trail"


@dataclass(slots=True)
class _ActiveMoveChase:
    """One leader's still-unresolved Move-chase toward a non-adjacent
    target, carried across phases -- see the module docstring's
    "PERSISTENT MOVE CHASE" section. Deliberately minimal: ``army_ids``
    and every AdvancedAbility-derived dispatch flag are re-derived fresh
    from ``state`` on every continuation dispatch, the same way an
    ordinary fresh LMOVE already does, so there's nothing else to
    snapshot here.
    """

    kingdom_id: int
    target: HexCoord


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

    Ends with bare, unsurfaced once-per-turn housekeeping calls (no
    ``PhaseDispatchResult`` recorded for any of them): ``_revert_
    analytical_psychology_charms``, ``turn/skeletal_decay.py
    decompose_graveyard()`` (Phase 309, the world-wide 350-unit-cap
    graveyard decay), and, as of Phase 404, ``turn/expenses.py
    apply_turn_maintenance()`` -- the real per-turn treasury debit for
    every kingdom's own Expected Expenses (army + leader upkeep), now
    passed this function's own ``rng`` (Phase 527: unpaid Heroes roll for
    desertion/standby, see that module's own Phase 527 addendum). One
    call to ``run_turn()`` is the one unambiguous "once per game turn"
    boundary this phase-by-phase loop offers; see each function's own
    module docstring for why it lives here rather than per-phase.
    """

    rng = rng if rng is not None else random.Random()
    results: list[PhaseDispatchResult] = []
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    active_defends: dict[int, DefendCoverage] = {}  # defender leader_id -> origin + coverage area
    active_pursuits: dict[int, _ActivePursuit] = {}  # pursuer/trailer leader_id -> ongoing chase
    active_move_chases: dict[int, _ActiveMoveChase] = {}  # mover leader_id -> ongoing non-adjacent Move chase
    active_patrols: dict[int, object] = {}  # patroller leader_id -> its own PursueRequest (standing order)
    # Rulebook [3.15]'s other Defend-cancellation trigger ("cancelled if
    # he loses a battle"): once a leader loses the one battle their own
    # Defend order can ever draw them into (see
    # _apply_defend_cancellations's own docstring for why that's the
    # complete scenario space), they can never register into
    # active_defends again for the rest of this run_turn() call, even if
    # a later phase in their own plan re-issues DEFEND -- persistent
    # across phases, unlike active_defends itself.
    defeated_while_defending: set[int] = set()

    # Phase 713 -- AdvancedAbility.SPY_BLACKMAIL: promote every Kingdom's
    # own still-pending demand (delivered last turn) into "active" (due
    # this turn), before any phase dispatches -- mirrors the real parsed
    # `pending_blackmailer_king_id`/`active_blackmailer_king_id` field
    # pair exactly. See `turn/blackmail.py`'s own module docstring.
    advance_blackmail_claims(state)

    # Phase 669 -- rulebook [5.10]: each leader's own real, standing
    # Special Encounter Plan, decoded once here (before any phase
    # dispatches -- a battle can happen in P0 itself) from the real
    # `SP:` block their own move submission carried this turn (exactly
    # one top-level segment per leader, confirmed structurally against
    # every real sample -- `models/plan.py`'s own module docstring).
    # Feeds `battle_orchestrator.py _maybe_fight_duel()`'s own real
    # Duel-trigger check. A leader not present in this call's own
    # `turn_leaders` (or with no segments at all) is left untouched,
    # keeping whatever `LeaderState.special_encounter_plan` already
    # holds -- the safe `()` default for anyone never processed here.
    for tl in turn_leaders:
        leader_state = state.leaders.get(tl.leader.leader_id)
        if leader_state is None or not tl.leader.plan.segments:
            continue
        leader_state.special_encounter_plan = tuple(decode_special_encounter_plan(tl.leader.plan.segments[0]))

    for phase_index, label in enumerate(PHASE_LABELS):
        if phase_index > 0:
            results.extend(_dispatch_contested_rebattles(state, rng))
            newly_infected = resolve_plague_spread(state, rng, bounds)
            results.extend(
                PhaseDispatchResult(
                    leader_id=0, segment_index=-1, phase_label="plague-spread", action=None, result=coord, error=None
                )
                for coord in newly_infected
            )

        entries = _collect_phase_entries(turn_leaders, label)
        # Phase 252, [3.17] Trail's own "Actions" field: every leader's own
        # decoded action for this phase label, before any of the filtering
        # below removes entries -- a leader with no entry here (mid-chase,
        # or simply idle) has no action to report, the same "no data"
        # convention trail_execution.py's own module docstring already
        # uses for its other fields. See that docstring's Phase 252 note.
        action_this_phase_by_leader = {tl.leader.leader_id: phase.action for tl, _segment_index, phase in entries}
        # A leader still mid-chase (Pursue/Trail, or a Move chase toward
        # a non-adjacent target) has this phase's own order preempted
        # entirely -- see "PERSISTENT PURSUE/TRAIL CHASE"/"PERSISTENT
        # MOVE CHASE" in the module docstring for why this is checked
        # once, at the phase's start.
        entries = [
            entry
            for entry in entries
            if entry[0].leader.leader_id not in active_pursuits and entry[0].leader.leader_id not in active_move_chases
        ]
        results.extend(_continue_active_pursuits(active_pursuits, label, state, rng, action_this_phase_by_leader))
        results.extend(_continue_active_move_chases(active_move_chases, label, state, board_width, explorer_skill, rng))

        # A self-targeting PURSUE phase is a Patrol declaration ("Characters
        # On Patrol", see turn/patrol_execution.py's own docstring) -- it
        # never dispatches as an ordinary Pursue, so it's registered and
        # dropped from ``entries`` before anything else sees it.
        new_patrol_leader_ids = {
            tl.leader.leader_id
            for tl, _segment_index, phase in entries
            if phase.action is ActionCode.PURSUE and phase.obj == tl.leader.leader_id
        }
        for tl, _segment_index, phase in entries:
            if tl.leader.leader_id in new_patrol_leader_ids:
                active_patrols[tl.leader.leader_id] = decode_pursue_phase(phase)
        entries = [entry for entry in entries if entry[0].leader.leader_id not in new_patrol_leader_ids]

        _apply_patrol_cancellations(active_patrols, entries)
        patrol_results, patrol_preempted = _dispatch_active_patrols(active_patrols, label, state, rng, bounds)
        results.extend(patrol_results)
        entries = [entry for entry in entries if entry[0].leader.leader_id not in patrol_preempted]

        move_targets: dict[int, HexCoord] = {}
        for index, (_tl, _segment_index, phase) in enumerate(entries):
            if phase.action is ActionCode.LMOVE:
                try:
                    move_targets[index] = decode_hex_number(phase.obj, board_width)
                except ValueError:
                    pass  # left for the ordinary per-leader path to raise/record consistently

        _apply_defend_cancellations(active_defends, entries)
        reinforced = _apply_defend_reinforcements(active_defends, move_targets, entries, state)
        for defender_leader_id, reinforcement in reinforced.items():
            # Phase 422: a synthetic, action-less entry (same convention as
            # the "gate-angel-visit"/"forced-rebattle" sentinels below and
            # elsewhere in this module) -- narrating a Defend reinforcement
            # isn't tied to any real PlanPhase the reinforcing leader issued
            # this turn, so describe_turn_results() matches it by result
            # type instead of by ActionCode.
            results.append(
                PhaseDispatchResult(
                    leader_id=defender_leader_id,
                    segment_index=-1,
                    phase_label="defend-reinforcement",
                    action=None,
                    result=reinforcement,
                    error=None,
                )
            )

        for index, (tl, _segment_index, phase) in enumerate(entries):
            if phase.action is ActionCode.DEFEND:
                leader_state = state.leaders.get(tl.leader.leader_id)
                if leader_state is not None and tl.leader.leader_id not in defeated_while_defending:
                    # Registered for *next* phase's reinforcement check, not this
                    # one -- see turn/defend_execution.py's own docstring and
                    # _apply_defend_reinforcements's for why.
                    active_defends[tl.leader.leader_id] = DefendCoverage(
                        origin=leader_state.location,
                        area=defend_coverage_area(
                            leader_state.location,
                            bounds,
                            radius=defend_radius_for_leader(state, tl.leader.leader_id),
                        ),
                    )

        reinforced_by_target: dict[HexCoord, list[int]] = {}
        for defender_leader_id, reinforcement in reinforced.items():
            reinforced_by_target.setdefault(reinforcement.target, []).append(defender_leader_id)

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

        practice_keys: dict[int, tuple[HexCoord, Ability | int]] = {}
        for index, (tl, _segment_index, phase) in enumerate(entries):
            if phase.action is ActionCode.PRACTICE:
                leader_state = state.leaders.get(tl.leader.leader_id)
                if leader_state is None:
                    continue  # left for the ordinary per-leader path to raise/record consistently
                ability = decode_practice_phase(phase).ability
                practice_keys[index] = (leader_state.location, ability)

        practice_groups: dict[tuple[HexCoord, Ability | int], list[int]] = {}
        for index, key in practice_keys.items():
            practice_groups.setdefault(key, []).append(index)

        multi_practice_groups: list[tuple[Ability | int, list[int]]] = [
            (key[1], indices) for key, indices in practice_groups.items() if len(indices) >= 2
        ]

        encounter_targets: dict[int, int] = {}
        for index, (tl, _segment_index, phase) in enumerate(entries):
            if phase.action in (ActionCode.CHALLENGE, ActionCode.PURSUE):
                encounter_targets[index] = phase.obj  # obj is target_character_id directly, no decode needed

        leader_id_by_index = {index: entries[index][0].leader.leader_id for index in encounter_targets}
        index_by_leader_id = {leader_id: index for index, leader_id in leader_id_by_index.items()}

        mutual_encounter_pairs: list[tuple[int, int]] = []
        seen_pairs: set[frozenset[int]] = set()
        for index, target_character_id in encounter_targets.items():
            target_index = index_by_leader_id.get(target_character_id)
            if target_index is None or target_index == index:
                continue  # no reciprocal order this phase, or a self-targeting Patrol (unmodeled, see Pursue's own docstring)
            if encounter_targets.get(target_index) != leader_id_by_index[index]:
                continue  # target's own order doesn't point back at this leader
            pair_key = frozenset({index, target_index})
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            mutual_encounter_pairs.append((index, target_index))

        consumed = {index for _target, indices in multi_attacker_groups for index in indices}
        consumed |= {index for _ability, indices in multi_practice_groups for index in indices}
        consumed |= {index for pair in mutual_encounter_pairs for index in pair}

        for target, indices in multi_attacker_groups:
            movers = [entries[i] for i in indices]
            group_results = _dispatch_multi_attacker_lmove(movers, target, state, board_width, explorer_skill, rng)
            results.extend(group_results)
            _apply_defend_battle_loss(defeated_while_defending, reinforced_by_target, target, group_results)

        for ability, indices in multi_practice_groups:
            movers = [entries[i] for i in indices]
            results.extend(_dispatch_multi_practice(movers, ability, state, rng))

        for index_a, index_b in mutual_encounter_pairs:
            results.extend(_dispatch_mutual_encounter(entries[index_a], entries[index_b], state, rng))

        for index, (tl, segment_index, phase) in enumerate(entries):
            if index in consumed:
                continue
            dispatch_results = _dispatch_single(tl, segment_index, phase, state, board_width, explorer_skill, rng)
            results.extend(dispatch_results)
            if phase.action is ActionCode.TRAIL:
                _backfill_trail_actions(dispatch_results, action_this_phase_by_leader)
            if phase.action in (ActionCode.PURSUE, ActionCode.TRAIL):
                _register_pursuit_continuation(active_pursuits, tl.leader.leader_id, phase, dispatch_results)
            if phase.action is ActionCode.LMOVE:
                target = move_targets.get(index)
                if target is not None:
                    _apply_defend_battle_loss(defeated_while_defending, reinforced_by_target, target, dispatch_results)
                    _register_move_chase_continuation(
                        active_move_chases, tl.leader.leader_id, tl.kingdom_id, target, dispatch_results
                    )

        # Phase 670 -- rulebook's own Fall/Early-Winter-only guardian
        # maturation (THUNDERBIRD.md section 11). Season -> phase mapping
        # is the user's own direct confirmation: this project's 5 phases
        # per turn ARE Spring/Early Summer/Late Summer/Fall/Early Winter
        # in order, so Fall=P3/Early Winter=P4 is exactly `phase_index >=
        # 3` in this existing loop -- no new calendar concept needed.
        if phase_index >= 3:
            age_all_feature_guardians(state, rng)

    visitor = finalize_gate_angel_visit(state, rng, board_width=board_width)
    if visitor is not None:
        # Sentinel result, same convention as _dispatch_contested_rebattles:
        # not tied to any real plan segment. See module docstring's "GATE
        # ANGEL / VALHALLA VISIT" section for why this runs here, after
        # every phase, rather than inline with the CAST phase that
        # triggered it.
        results.append(
            PhaseDispatchResult(
                leader_id=visitor.leader_id,
                segment_index=-1,
                phase_label="gate-angel-visit",
                action=None,
                result=visitor,
                error=None,
            )
        )

    # Phase 548: the departing visitor's own army hand-off/item transfer
    # -- see turn/valhalla_execution.py process_valhalla_departure()'s
    # own docstring for why this runs immediately after the spawn call
    # above rather than being folded into it.
    process_valhalla_departure(state, board_width=board_width)

    _revert_analytical_psychology_charms(state)
    _apply_werebeast_transformations(state)
    decompose_graveyard(state)
    # Phase 670: Hide Feature's own genuinely new 10%-per-turn
    # dissipation roll (THUNDERBIRD.md section 12.3) -- once per real
    # turn, not per phase (no phase-specific trigger is named the way
    # the maturation routine's own "Season" gate has one).
    for feature in state.features.values():
        maybe_dissipate_hidden_feature(feature, rng)
    # Phase 724: Illusory Terrain's own real 15%/turn dissolve chance
    # (rulebook [4.23.1]) -- identical shape/placement to Hide Feature's
    # dissipation roll right above, just per-province instead of
    # per-feature.
    for province in state.provinces.values():
        maybe_dissolve_illusory_terrain(province, rng)
    apply_turn_revenue(state, rng)
    apply_turn_maintenance(state, rng)
    # Phase 468: King of Cowards' own real per-turn temperament rise
    # (AKGEN_reverse_engineering_report (2).md SS18.6) -- see that
    # function's own docstring for why this is a confirmed no-op under
    # real generated data.
    apply_cravenest_temperament_escalation(state)
    # Phase 660: Fool of Battles' own real per-turn Tactics aptitude rise.
    apply_battle_fool_aptitude_escalation(state)
    # Phase 573: the turn-boundary reset this project never had. Several
    # fields were long documented as "not auto-reset -- the caller's
    # job" (see `_replenish_turn_scoped_state()`'s own docstring for the
    # full list), but no caller anywhere ever actually did it, and
    # `state.turn_number` itself was never incremented anywhere in this
    # project either -- a real game moderated turn after turn via
    # `orchestrator.process_turn()` would exhaust every army's movement
    # pool on turn 1 and never recover it, permanently lose access to
    # Oratory/hiring/recruiting the first time each one's own per-turn
    # cap was hit, and every turn-gated mechanic (Valhalla scheduling,
    # Gate Angel, office-holder turn gates, diplomacy first-contact)
    # would stay frozen at turn-1 behavior forever. `run_turn()` is this
    # project's own confirmed "one unambiguous once-per-turn boundary"
    # (see this function's own docstring), so it's the right place to
    # prepare state for the turn that comes *after* this one -- run at
    # the end, not the start, so a fresh `GameState` from `worldgen.
    # generate_new_game()` (which now sets each army's own initial
    # `movement_points` itself) still needs no priming call before its
    # own first `run_turn()`.
    _replenish_turn_scoped_state(state)
    state.turn_number += 1

    return results


def _revert_analytical_psychology_charms(state: GameState) -> None:
    """Phase 302 (Discovery.ANALYTICAL_PSYCHOLOGY): the one end-of-turn
    revert this project's turn loop needs -- every other "persistent
    for the rest of the turn" flag (``oratory_boosted_this_turn``,
    ``mystic_winds_active``, ...) is a caller-clears-it boolean with no
    prior value to restore, but a protected Charm genuinely mutated
    ``kingdom_id`` and must put it back. Runs once, after every phase
    of ``run_turn()`` has already dispatched, so ``kingdom_id`` reads
    as the caster's kingdom for the rest of this turn (matching the
    source text's "the spell will work") and is restored to the
    target's own original kingdom before the next turn is ever
    processed.
    """

    for leader in state.leaders.values():
        if leader.analytical_psychology_revert_kingdom_id is not None:
            leader.kingdom_id = leader.analytical_psychology_revert_kingdom_id
            leader.analytical_psychology_revert_kingdom_id = None


def _replenish_turn_scoped_state(state: GameState) -> None:
    """Phase 573: resets every "not auto-reset -- the caller's job" field
    this project's own models ever documented that way, preparing
    ``state`` for the turn that comes after the one ``run_turn()`` just
    finished dispatching. See this function's own call site for why it
    belongs at the end of ``run_turn()``, not the start.

    - ``ArmyState.movement_points`` -> each army's own real per-turn rate
      (``ARMY_TABLE[army_type].speed``, RULES.AK [6.3]) -- an army that
      spent its whole pool this turn (or was created with none, before
      this phase) gets a full one back for the next.
    - ``ArmyState.march_bonus_applied_this_turn``/``naval_bonus_applied_
      this_turn`` -> ``False`` -- otherwise an army that ever drew its
      one-time March/Naval movement bonus once (``turn/move_execution.py
      execute_move()``) could never draw it again for the rest of the
      game.
    - ``ArmyState.unhireable_this_turn`` -> ``False`` -- otherwise an
      army `turn/battle_orchestrator.py` ever marked unhireable (e.g.
      after a battle) could never be hired/recruited again, ever
      (`turn/recruit_execution.py`'s own ``not unhireable_this_turn``
      gate).
    - ``LeaderState.oratory_boosted_this_turn`` -> ``False`` -- otherwise
      a leader who ever benefited from Oratory once could never benefit
      from it again for the rest of the game (`turn/cast_execution.py`'s
      own idempotency gate).
    - ``ProvinceState.recruited_this_turn`` -> ``{}`` -- otherwise a
      province that ever hit its per-type recruit limit once (rulebook
      [3.4]) could never recruit that type again, ever.
    - ``ProvinceState.recruit_locked_this_turn`` -> ``False`` (Phase 691)
      -- a province that ever hosted a successful Dinosaur recruit
      (``AdvancedAbility.DRUIDIC_DINOSAURS``'s own "no further units may
      be recruited in the province that turn") could otherwise never
      recruit anything there again, ever.
    - ``GameState.action_casts_used`` -> ``{}`` (Phase 575) -- otherwise a
      (leader, Ability) pair that ever exhausted its own per-turn
      Action-Cast slots (``turn/cast_execution.py action_cast_slots()``)
      could never cast that Ability again for the rest of the game --
      the identical "never reset, permanently blocks its own mechanic"
      bug already fixed for the fields above in Phase 573, just not
      audited yet at the time.
    - ``ProvinceState.illusory_fog_active`` -> ``False`` (Phase 576) --
      Illusory Fog's own quoted rule text is explicit that the spell
      "dissipates at the end of the gameturn" (``turn/cast_execution.py``'s
      own Phase 207 addendum), but the flag it sets is read by a real,
      live consumer (``turn/battle_orchestrator.py``/``turn/strength.py``,
      halving air-unit strength in every battle fought in that province)
      and had no clearing site anywhere -- a province hit by Illusory Fog
      stayed permanently fogged for the rest of the game, directly
      contradicting the sourced one-turn duration. Found by re-auditing
      every other "not auto-cleared -- caller's job" field this project's
      own comments still flagged after Phase 573/575, the same way
      ``action_casts_used`` itself was found.
    - ``KingdomState.treasury_raid_attempts_this_turn`` -> ``0`` (Phase
      702) -- ``AdvancedAbility.THIEF_TREASURY_RAIDS``'s own "the guard
      is doubled for that kingdom against further attempts in the same
      turn" deterrent would otherwise keep escalating forever, halving
      every future Treasury Raid attempt against that kingdom for the
      rest of the game instead of just for the turn it was raided.

    ``GameState.gate_angel_candidates_this_turn`` is deliberately NOT
    touched here despite its own name -- it's already self-resetting,
    gated on a direct ``state.turn_number`` comparison against its own
    ``gate_angel_due_alignment_turn`` cache (`turn/cast_execution.py`),
    which only works correctly now that ``turn_number`` itself actually
    advances (see this function's own call site).
    """

    for army in state.armies.values():
        army.movement_points = ARMY_TABLE[army.army_type].speed
        army.march_bonus_applied_this_turn = False
        army.naval_bonus_applied_this_turn = False
        army.unhireable_this_turn = False
    for province in state.provinces.values():
        province.recruited_this_turn = {}
        province.recruit_locked_this_turn = False
        province.illusory_fog_active = False
    for leader in state.leaders.values():
        leader.oratory_boosted_this_turn = False
    for kingdom in state.kingdoms.values():
        kingdom.treasury_raid_attempts_this_turn = 0
    state.action_casts_used = {}


def _apply_werebeast_transformations(state: GameState) -> None:
    """Phase 392: drains ``GameState.werebeast_bitten_army_ids`` -- the
    real end-of-turn half of AKGEN's own confirmed "Werebeasts defeat
    humanoids: bite and end-of-turn transformation" (`turn/battle_
    orchestrator.py _apply_werebeast_bites`'s own docstring covers the
    battle-time 40% roll that populates this set). "Transformation" is
    read as the bitten *army* becoming a Werebeasts unit outright
    (``ArmyType.WEREBEASTS``) rather than a Kingdom-wide race change --
    Race is a Kingdom-level attribute in this project (``KingdomState.
    race``), never per-army, so a literal "this army is now a
    Werebeasts army" reading is the only one that doesn't require
    inventing a per-army race override this project has no other use
    for. An army id that no longer exists (destroyed before this point,
    e.g. by the same battle's own clean-sweep) is silently skipped, the
    same permissive-missing-data convention this module uses everywhere
    else. Runs exactly once, at the very end of ``run_turn()`` --
    matching the source's own "end-of-turn" wording literally, not
    per-phase.
    """

    for army_id in state.werebeast_bitten_army_ids:
        army = state.armies.get(army_id)
        if army is not None:
            army.army_type = ArmyType.WEREBEASTS
    state.werebeast_bitten_army_ids.clear()


_DEFEND_CANCELLING_ACTIONS = frozenset({ActionCode.LMOVE, ActionCode.PURSUE, ActionCode.TRAIL})


def _apply_defend_cancellations(
    active_defends: dict[int, DefendCoverage], entries: list[tuple[TurnLeader, int, PlanPhase]]
) -> None:
    """Rulebook [3.15] (quoted in full, ``RULES.AK`` ~line 573-576): "A general with
    Defend orders may use the rest of his actions to practice, explore,
    etc. If he receives a Move, Pursue or Trail order, the Defend order
    is cancelled." Removes a leader from ``active_defends`` the moment
    their own plan reaches an LMOVE/PURSUE/TRAIL phase, *before* this
    same phase's own ``_apply_defend_reinforcements`` check runs -- a
    general who's off moving/pursuing/trailing this phase is no longer
    standing by to react to an invasion this phase either.

    The rulebook's other cancellation trigger, "a character's Defend
    order is cancelled if he loses a battle, to prevent further needless
    defeats" (Phase 72), is handled separately, later in ``run_turn()``,
    via a persistent ``defeated_while_defending`` set rather than here --
    see that variable's own inline comment for why. **Only the
    reinforcement-triggered battle is checked, a scope boundary, not an
    oversight**: a Defend leader's own commanded armies never enter any
    *other* battle in this project's simulation (they only move at all
    via ``_apply_defend_reinforcements``'s own relocation, since an
    LMOVE/PURSUE/TRAIL order of their own would already have cancelled
    Defend right here first) -- so this one path is the complete
    scenario space, not a narrow slice of a bigger one. Battles this
    leader's *armies* might separately be swept into by some other
    leader's own command (a scenario this project's data model doesn't
    allow -- ``ArmyState.commanded_by`` is single-owner) are out of
    scope for the same reason.
    """

    for tl, _segment_index, phase in entries:
        if phase.action in _DEFEND_CANCELLING_ACTIONS:
            active_defends.pop(tl.leader.leader_id, None)


def _apply_defend_reinforcements(
    active_defends: dict[int, DefendCoverage],
    move_targets: dict[int, HexCoord],
    entries: list[tuple[TurnLeader, int, PlanPhase]],
    state: GameState,
) -> dict[int, DefendReinforcement]:
    """Rulebook [3.15]: relocates a Defending leader's own armies to an invaded
    covered province, so the existing battle-dispatch machinery (solo or
    Multiple Contingents) picks them up as defenders automatically -- the
    same relocate-then-fight abstraction already used for Pursue's own
    army-vs-army catch-up (Phase 53). Runs against ``active_defends`` as
    it stood *before* this phase's own new DEFEND orders are registered
    (see ``run_turn``'s own call site) -- a Defend order reacts starting
    the *next* phase, not the one it's given in, sidestepping the
    Italian rulebook's own noted-but-unmodeled "Defend always resolves
    last in its phase" ordering nuance (``turn/aspy_defend_decode.py``'s
    docstring) rather than guessing at same-phase ordering semantics
    this project has no other precedent for.

    A defender only reinforces **friendly-owned ground** (the invaded
    province's owner is the defender's own Kingdom or an ally) against a
    **non-allied invader who actually brings an army** -- the same
    "attacking" criterion used throughout this module. Each defender's
    coverage is **consumed after its first reinforcement this
    ``run_turn()`` call**: once committed to one battle, they're no
    longer standing by to cover their original area for a second,
    unrelated invasion later in the turn (a documented simplification,
    not sourced -- the rulebook doesn't address a general reinforcing
    twice in the same turn).

    Returns ``{defender_leader_id: DefendReinforcement(origin, target)}``
    for every reinforcement performed this call -- ``run_turn()`` uses
    ``.target`` to look up that same battle's outcome once this phase's
    LMOVE dispatch resolves it, for rule [3.15]'s other cancellation
    trigger (see ``_apply_defend_cancellations``'s own docstring and
    ``_extract_battle_winner``). ``.origin`` (the defender's own province
    before relocating) exists solely for ``describe_defend_reinforcement()``
    (Phase 422, ``SAY.PAS _LHearInv``'s own ``@`` marker) -- captured here
    because ``defender_state.location`` is overwritten to ``target``
    a few lines below, before this function returns.
    """

    reinforced: dict[int, DefendReinforcement] = {}
    if not active_defends:
        return reinforced

    invaded_provinces: dict[HexCoord, list[int]] = {}
    for index, target in move_targets.items():
        invaded_provinces.setdefault(target, []).append(index)

    for defender_leader_id, coverage in list(active_defends.items()):
        defender_state = state.leaders.get(defender_leader_id)
        if defender_state is None or defender_state.kingdom_id is None:
            continue

        for target, indices in invaded_provinces.items():
            if target not in coverage.area:
                continue
            target_province = state.provinces.get(target)
            if target_province is None or target_province.owner_kingdom_id is None:
                continue
            owner = target_province.owner_kingdom_id
            if owner != defender_state.kingdom_id and not state.is_allied(owner, defender_state.kingdom_id):
                continue  # not friendly ground -- nothing to defend here

            invading = any(
                state.armies_commanded_by(entries[i][0].leader.leader_id)
                and not state.is_allied(entries[i][0].kingdom_id, defender_state.kingdom_id)
                for i in indices
            )
            if not invading:
                continue

            for army in state.armies_commanded_by(defender_leader_id):
                army.location = target
            origin = coverage.origin
            defender_state.location = target
            del active_defends[defender_leader_id]
            reinforced[defender_leader_id] = DefendReinforcement(origin=origin, target=target)
            break

    return reinforced


def _extract_battle_winner(result: object) -> str | None:
    """Reads ``BattleResult.winner`` ("attacker"/"defender"/"tie") out of whichever
    battle-bearing result shape a dispatch produced, or ``None`` if
    ``result`` carries no battle at all. See ``_apply_defend_cancellations``'s
    own docstring for why only this one, narrowly-scoped case (a
    Defend-reinforcement-triggered battle) is checked.
    """

    if isinstance(result, MoveExecutionResult):
        battle_report = result.battle_report
    elif isinstance(result, MultiAttackerMoveResult):
        battle_report = result.battle.report
    else:
        battle_report = None
    return battle_report.battle_result.winner if battle_report is not None else None


def _apply_defend_battle_loss(
    defeated_while_defending: set[int],
    reinforced_by_target: dict[HexCoord, list[int]],
    target: HexCoord,
    dispatch_results: list[PhaseDispatchResult],
) -> None:
    """Rulebook [3.15]'s other Defend-cancellation trigger, applied the moment this
    phase's own LMOVE dispatch resolves the exact battle a Defend
    reinforcement (``_apply_defend_reinforcements``) just drew ``target``'s
    defender(s) into. See ``_apply_defend_cancellations``'s own docstring
    for why this is the only battle that needs checking.

    Phase 299 fix (a real bug found in a dedicated bug-hunt audit):
    ``dispatch_results`` isn't always a single-entry list carrying the
    real battle at index 0 -- ``_dispatch_multi_attacker_lmove()`` can
    mix per-mover validation-error entries (an illegal move, no province
    data) in *before* the real ``MultiAttackerMoveResult`` entries for
    the movers that actually joined the battle, so a multi-attacker
    group with at least one invalid mover could have its own real battle
    result sitting at index 1 or later. Reading only index ``[0]`` then
    silently found no battle (an error entry carries none) and never
    cancelled the Defend order despite a genuine loss. Fixed by scanning
    every entry for the one real battle this call is ever looking for --
    at most one battle is ever produced for a single ``target``, so the
    first non-``None`` winner found is unambiguously the right one.
    """

    defender_leader_ids = reinforced_by_target.get(target)
    if not defender_leader_ids or not dispatch_results:
        return
    winner = next(
        (w for w in (_extract_battle_winner(r.result) for r in dispatch_results) if w is not None), None
    )
    if winner == "attacker":
        defeated_while_defending.update(defender_leader_ids)


_PURSUE_STILL_CHASING_REASON = "did not catch up this phase"
_TRAIL_STILL_CHASING_REASON = "did not find the target this phase"


def _continue_active_pursuits(
    active_pursuits: dict[int, _ActivePursuit],
    label: str,
    state: GameState,
    rng: random.Random,
    action_this_phase_by_leader: dict[int, ActionCode] | None = None,
) -> list[PhaseDispatchResult]:
    """Dispatches one ``advance_pursuit``/``advance_trail`` step for every leader still
    mid-chase, and drops resolved (or terminally-failed) chases from
    ``active_pursuits``. See the module docstring's "PERSISTENT PURSUE/
    TRAIL CHASE" section for the ``segment_index=-1`` sentinel and why
    resolution is checked once, here, at the phase's own start.

    ``action_this_phase_by_leader`` (Phase 252, default ``None`` -- every
    pre-Phase-252 caller/test is unaffected) backfills a successful
    Trail continuation's own ``TrailExecutionResult.actions`` from the
    target's own entry in that map -- see ``turn/trail_execution.py``'s
    own module docstring for why this is the only place that can.
    """

    action_this_phase_by_leader = action_this_phase_by_leader or {}
    results: list[PhaseDispatchResult] = []
    for leader_id, active in list(active_pursuits.items()):
        # Phase 695: same real-possession pattern as every other
        # AdvancedAbility-derived dispatch flag in this function -- see
        # its own module docstring note above.
        leader = state.leaders.get(leader_id)
        has_spy_super_sleuth = leader is not None and AdvancedAbility.SPY_SUPER_SLEUTH in leader.advanced_abilities
        if active.kind == "pursue":
            result = advance_pursuit(state, leader_id, active.request, rng, has_spy_super_sleuth=has_spy_super_sleuth)
            action = ActionCode.PURSUE
            still_chasing = not result.caught_up and result.reason == _PURSUE_STILL_CHASING_REASON
        else:
            # Phase 705: same real-possession pattern, for Spy Expanded Spying.
            caster_has_spy_expanded_spying = (
                leader is not None and AdvancedAbility.SPY_EXPANDED_SPYING in leader.advanced_abilities
            )
            # Phase 713: same real-possession pattern, for Spy Blackmail.
            caster_has_spy_blackmail = leader is not None and AdvancedAbility.SPY_BLACKMAIL in leader.advanced_abilities
            result = advance_trail(
                state,
                leader_id,
                active.request,
                rng,
                has_spy_super_sleuth=has_spy_super_sleuth,
                caster_has_spy_expanded_spying=caster_has_spy_expanded_spying,
                caster_has_spy_blackmail=caster_has_spy_blackmail,
            )
            action = ActionCode.TRAIL
            still_chasing = not result.spied_on and result.reason == _TRAIL_STILL_CHASING_REASON
            if result.spied_on:
                result.actions = action_this_phase_by_leader.get(active.request.target_character_id)

        if not still_chasing:
            del active_pursuits[leader_id]

        results.append(
            PhaseDispatchResult(
                leader_id=leader_id,
                segment_index=-1,  # sentinel: continuation, not tied to a real plan segment this phase
                phase_label=label,
                action=action,
                result=result,
                error=None,
            )
        )
    return results


def _backfill_trail_actions(
    dispatch_results: list[PhaseDispatchResult], action_this_phase_by_leader: dict[int, ActionCode]
) -> None:
    """Phase 252, [3.17] Trail's own "Actions" field: for a freshly-dispatched Trail
    order that caught its target, stamps the target's own entry in
    ``action_this_phase_by_leader`` onto ``TrailExecutionResult.actions``
    -- ``None`` if the target has no entry (idle, or itself mid-chase and
    excluded from this phase's own entries). See ``turn/trail_execution.py``'s
    own module docstring for why ``execute_trail()`` itself can't do this.
    """

    for entry in dispatch_results:
        result = entry.result
        if not isinstance(result, TrailExecutionResult) or not result.spied_on or result.request is None:
            continue
        result.actions = action_this_phase_by_leader.get(result.request.target_character_id)


def _register_pursuit_continuation(
    active_pursuits: dict[int, _ActivePursuit],
    leader_id: int,
    phase: PlanPhase,
    dispatch_results: list[PhaseDispatchResult],
) -> None:
    """After a freshly-dispatched PURSUE/TRAIL phase, registers the chase for
    continuation next phase if -- and only if -- it came back with the
    specific "still looking, try again next phase" outcome. Any other
    outcome (resolved, refused, or a terminal not-found/army-mismatch
    reason) needs no follow-up. See module docstring.
    """

    if not dispatch_results:
        return
    result = dispatch_results[-1].result

    if phase.action is ActionCode.PURSUE:
        if not isinstance(result, PursueExecutionResult):
            return
        if result.caught_up or result.reason != _PURSUE_STILL_CHASING_REASON:
            return
        request = decode_pursue_phase(phase)
        active_pursuits[leader_id] = _ActivePursuit(kind="pursue", request=request)
    else:
        if not isinstance(result, TrailExecutionResult):
            return
        if result.spied_on or result.reason != _TRAIL_STILL_CHASING_REASON:
            return
        request = decode_trail_phase(phase)
        active_pursuits[leader_id] = _ActivePursuit(kind="trail", request=request)


def _continue_active_move_chases(
    active_move_chases: dict[int, _ActiveMoveChase],
    label: str,
    state: GameState,
    board_width: int,
    explorer_skill: int,
    rng: random.Random,
) -> list[PhaseDispatchResult]:
    """Dispatches one more LMOVE hop toward each still-mid-chase leader's own
    ultimate target, and drops resolved (or stopped) chases from
    ``active_move_chases``. See the module docstring's "PERSISTENT MOVE
    CHASE" section for why this simply redispatches an ordinary LMOVE
    phase rather than needing a dedicated ``advance_*`` function --
    ``execute_move()`` itself already knows how to take one more chase
    step toward a non-adjacent target.

    Calls ``turn/plan_dispatch.py dispatch_phase()`` directly (not
    ``_dispatch_single()``, which always reports ``segment_index=0`` --
    its own synthetic one-segment wrapper has no other value to give):
    a continuation isn't tied to any real plan segment, so this builds
    its own ``PhaseDispatchResult`` with ``segment_index=-1``, the same
    sentinel ``_continue_active_pursuits`` already uses, with the same
    broad ``except Exception`` ``run_leader_plan()`` itself uses so one
    leader's own dispatch error can't crash the whole phase loop.
    """

    results: list[PhaseDispatchResult] = []
    for leader_id, chase in list(active_move_chases.items()):
        leader_state = state.leaders.get(leader_id)
        if leader_state is None:
            del active_move_chases[leader_id]
            continue
        phase = PlanPhase(label=label, action=ActionCode.LMOVE, obj=encode_hex_number(chase.target, board_width), extra=[])
        try:
            result = dispatch_phase(
                phase, state, chase.kingdom_id, leader_id, board_width=board_width, explorer_skill=explorer_skill, rng=rng
            )
            dispatch_result = PhaseDispatchResult(leader_id, -1, label, phase.action, result, None)
        except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
            dispatch_result = PhaseDispatchResult(leader_id, -1, label, phase.action, None, exc)
            result = None
        results.append(dispatch_result)
        still_chasing = isinstance(result, MoveExecutionResult) and not result.reached_target and not result.stopped_chasing
        if not still_chasing:
            del active_move_chases[leader_id]
    return results


def _register_move_chase_continuation(
    active_move_chases: dict[int, _ActiveMoveChase],
    leader_id: int,
    kingdom_id: int,
    target: HexCoord,
    dispatch_results: list[PhaseDispatchResult],
) -> None:
    """After a freshly-dispatched LMOVE phase, registers the chase for
    continuation next phase if -- and only if -- this hop didn't reach
    ``target`` and didn't stop chasing (no legal closer neighbor). An
    ordinary already-adjacent Move always has ``reached_target=True``
    and never registers here. See module docstring.
    """

    if not dispatch_results:
        return
    result = dispatch_results[-1].result
    if not isinstance(result, MoveExecutionResult):
        return
    if result.reached_target or result.stopped_chasing:
        return
    active_move_chases[leader_id] = _ActiveMoveChase(kingdom_id=kingdom_id, target=target)


def _apply_patrol_cancellations(
    active_patrols: dict[int, object], entries: list[tuple[TurnLeader, int, PlanPhase]]
) -> None:
    """Rule (d) (``turn/patrol_execution.py``'s own docstring, quoted in full):
    "The Patrol stays active until the next Move, Trail or Pursue order."
    Reuses ``_apply_defend_cancellations``'s identical LMOVE/PURSUE/TRAIL
    trigger set verbatim, since the rulebook uses the same wording for
    both Defend and Patrol cancellation. A brand-new Patrol declaration
    itself (this phase's own self-targeting Pursue) is already removed
    from ``entries`` before this runs, so it never immediately cancels
    itself.
    """

    for tl, _segment_index, phase in entries:
        if phase.action in _DEFEND_CANCELLING_ACTIONS:
            active_patrols.pop(tl.leader.leader_id, None)


def _dispatch_active_patrols(
    active_patrols: dict[int, object],
    label: str,
    state: GameState,
    rng: random.Random,
    bounds: MapBounds,
) -> tuple[list[PhaseDispatchResult], set[int]]:
    """Dispatches one ``execute_patrol`` check for every leader with a standing
    Patrol order. Rule (d): "other orders after the Patrol order are used
    if there is no current threat" -- when no intruder is found this
    phase, nothing is emitted and the leader's own real order (if any)
    proceeds completely normally; a dispatch result is only produced, and
    the leader's own real order for this phase preempted, when a threat
    actually is found (whether or not the interception itself succeeds).
    """

    results: list[PhaseDispatchResult] = []
    preempted: set[int] = set()
    for leader_id, request in list(active_patrols.items()):
        result = execute_patrol(state, leader_id, request, rng, board_width=bounds.width, board_height=bounds.height)
        if result.target_leader_id is None:
            continue
        preempted.add(leader_id)
        results.append(
            PhaseDispatchResult(
                leader_id=leader_id,
                segment_index=-1,  # sentinel: standing-order dispatch, not tied to a real plan segment
                phase_label=label,
                action=ActionCode.PURSUE,
                result=result,
                error=None,
            )
        )
    return results, preempted


def _dispatch_mutual_encounter(
    entry_a: tuple[TurnLeader, int, PlanPhase],
    entry_b: tuple[TurnLeader, int, PlanPhase],
    state: GameState,
    rng: random.Random,
) -> list[PhaseDispatchResult]:
    """Resolves a detected mutual Challenge/Pursue pair (rulebook [3.12]: "Kings only
    accept a non-peaceful encounter if both King and challenger attempt to
    Encounter each other in the same province in the same phase") as a
    **single shared encounter**, not two independent ones -- confirmed with
    the user before implementation (the rulebook only ever describes one
    encounter resulting from mutual orders, and resolving two would risk a
    second duel against a combatant the first duel already killed).

    **Initiator selection, a documented design choice**: if exactly one of
    the two leaders is a King, that King is always treated as the *target*
    (never the challenger) -- [3.12]'s ``mutual_encounter`` mechanism exists
    specifically to override a King *target's* own acceptance, so the King
    has to occupy that role for the rule to mean anything; picking the King
    as challenger instead would silently route through a completely
    different (and wrong) branch of ``is_encounter_accepted`` for a
    King-vs-armyless-Hero pair (a 50% evasion roll instead of guaranteed
    acceptance). If both or neither leader is a King, the outcome is
    otherwise symmetric for the King-acceptance branch, so the leader with
    the lower ``leader_id`` is used as challenger purely as a deterministic
    tiebreak -- an unsourced simplification for a case the rulebook doesn't
    disambiguate (e.g. it can still affect a non-King Challenge's own
    target-leads-an-army check), not a claim that this is the "correct"
    real-game resolution.

    The initiator's own action type (Challenge or Pursue) governs which
    resolver actually runs. **Phase 674 update**: the non-initiator's own
    ``LeaderState.special_encounter_plan`` IS now consulted -- not by
    this function directly, but automatically, the same way it already
    is for any real (non-mutual) solicited target: ``execute_challenge()``/
    ``execute_pursue()`` (called just below) resolve it themselves
    whenever the non-initiator commands no armies (rulebook [5.10]'s own
    "used in every Encounter solicited by another character"), so no
    change was needed here at all. Both ``PhaseDispatchResult`` entries
    still share the exact same result object, one per leader so each
    leader's own dispatch record still reflects that *their* order was
    the one that produced this outcome.
    """

    leader_a_id = entry_a[0].leader.leader_id
    leader_b_id = entry_b[0].leader.leader_id
    leader_a = state.leaders.get(leader_a_id)
    leader_b = state.leaders.get(leader_b_id)
    a_is_king = leader_a is not None and leader_a.is_king
    b_is_king = leader_b is not None and leader_b.is_king

    if b_is_king and not a_is_king:
        initiator = entry_a
    elif a_is_king and not b_is_king:
        initiator = entry_b
    else:
        initiator = entry_a if leader_a_id < leader_b_id else entry_b

    tl, _segment_index, phase = initiator
    if phase.action is ActionCode.CHALLENGE:
        request = decode_challenge_phase(phase)
        result = execute_challenge(state, tl.leader.leader_id, request, rng, mutual_encounter=True)
    else:
        request = decode_pursue_phase(phase)
        result = execute_pursue(state, tl.leader.leader_id, request, rng, mutual_encounter=True)

    return [
        PhaseDispatchResult(entry[0].leader.leader_id, entry[1], entry[2].label, entry[2].action, result, None)
        for entry in (entry_a, entry_b)
    ]


def _dispatch_contested_rebattles(state: GameState, rng: random.Random) -> list[PhaseDispatchResult]:
    """Rulebook [7.6]: "If the attackers still have at least 1 movement point for
    each army, they will be used to force another battle in the next
    phase... your armies will use up a movement point to fight a battle...
    If the province is conquered, the attacker uses another movement
    point." Runs once per phase boundary (before every phase after the
    first), scanning every province this ``GameState`` already knows to
    be contested (``ProvinceState.contested_by_kingdom_id``, set by an
    earlier mixed-result ``fight_battle`` call -- possibly from an
    earlier phase in this same ``run_turn()``, or already contested in
    the state the caller passed in).

    **Cross-turn carryover is out of scope, a documented boundary, not
    an oversight**: the rulebook separately describes a contested
    province still active "at the start of the next gameturn['s
    phase 1]" -- this project has no multi-turn/season loop
    (``run_turn()`` only ever processes one turn's P0-P4 at a time), so
    that case can't be distinguished here from an ordinary same-turn
    continuation; both are handled identically by this same check.

    A province stops auto-rebattling the moment ``attacker_can_force_
    rebattle`` returns ``False`` ("both armies will encamp") -- simply
    not being called again for that province on the next boundary, no
    special "encamped" state needs to be recorded anywhere.
    """

    results: list[PhaseDispatchResult] = []
    for coord, province in list(state.provinces.items()):
        attacker_kingdom_id = province.contested_by_kingdom_id
        if attacker_kingdom_id is None:
            continue

        armies_here = state.armies_at(coord)
        attacker_armies = [army for army in armies_here if army.kingdom_id == attacker_kingdom_id]
        movement_by_army = {army.army_id: army.movement_points for army in attacker_armies}
        if not attacker_can_force_rebattle(movement_by_army):
            continue  # "both armies will encamp" -- no more auto-rebattles this turn

        defenders_present = any(
            army.kingdom_id is not None and not state.is_allied(army.kingdom_id, attacker_kingdom_id)
            for army in armies_here
        )
        if not defenders_present:
            # Whatever the defenders were has left/been removed by some
            # other means since the province was last marked contested --
            # nothing left here to force a battle against.
            continue

        army_ids = [army.army_id for army in attacker_armies]
        # Phase 409: pass the original invasion origin through, when known,
        # so this rebattle still honors the real forced-attacker-retreat
        # rule (rulebook [7.4]) instead of falling back to the wrong
        # defender-style nearest-friendly-neighbor rule -- see
        # ProvinceState.contested_from_coord's own docstring.
        report = fight_battle(
            state, attacker_kingdom_id, coord, army_ids, attacker_origin=province.contested_from_coord, rng=rng
        )
        # Phase 716: the cargo sinks with the carrier.
        apply_battle_carrier_destruction(
            state, report.destroyed_army_ids, report.disbanded_army_ids, report.pursuit_destroyed_army_ids
        )

        cost = contested_battle_movement_cost(conquered=report.conquered)
        for army_id in army_ids:
            army = state.armies.get(army_id)
            if army is not None:
                army.movement_points -= cost

        results.append(
            PhaseDispatchResult(
                leader_id=report.attacker_commander_leader_id if report.attacker_commander_leader_id is not None else 0,
                segment_index=-1,  # sentinel: not tied to any leader's own plan segment, see module docstring
                phase_label="forced-rebattle",
                action=None,
                result=report,
                error=None,
            )
        )
    return results


def _dispatch_multi_practice(
    movers: list[tuple[TurnLeader, int, PlanPhase]],
    ability: Ability | int,
    state: GameState,
    rng: random.Random,
) -> list[PhaseDispatchResult]:
    """Rulebook [3.13] multi-character Practice case, via ``execute_practice_group`` (Phase 46)."""

    leader_ids = [tl.leader.leader_id for tl, _segment_index, _phase in movers]
    outcomes = execute_practice_group(state, leader_ids, ability, rng)
    return [
        PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, outcome, None)
        for (tl, segment_index, phase), outcome in zip(movers, outcomes)
    ]


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
                raise IllegalMoveFromContestedError("illegal to move from a contested province to an adjacent enemy province")
            move_result = resolve_move(
                origin,
                target,
                bounds,
                target_terrain=target_province.effective_terrain(),
                target_explored_percent=target_province.explored_percent,
                explorer_skill=explorer_skill,
                occupied_by_enemy=True,
            )
            exploration_new_percent = move_result.exploration.new_percent
            # Phase 69: each mover's own kingdom gets its own tracked
            # percentage here, unlike the single shared exploration_new_percent
            # scalar above (which only the last mover in this loop wins).
            record_kingdom_exploration(
                target_province, tl.kingdom_id, explorer_skill, partial=True, state=state, rng=rng, leader_id=tl.leader.leader_id
            )
            reveal_adjacent_provinces(state, target_province, tl.kingdom_id, bounds)
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
            is_sea_province=target_province.effective_terrain() == Terrain.SEA, battle_occurred=True, conquered=conquered
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
