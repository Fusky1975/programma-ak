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

**Phase 756**: when no Gate Angel cast succeeded this turn,
``turn/valhalla_execution.py finalize_ordinary_valhalla_visit()`` is
tried next, in the same tail spot -- the real, ``Desktop/VALHALLA.txt``
rule-1-sourced automatic visit every alignment receives once every 5
turns, independent of any spell. A visit spawned this way appends the
same shape of sentinel, with ``phase_label="valhalla-visit"`` instead
(a distinct label, since it wasn't spell-triggered). Both sentinel
labels are handled identically by ``report/turn_report.py describe_
valhalla_visit_announcement()``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.army_type import ARMY_TABLE, BASE_STRENGTH, GARRISON_DEFENSE_STRENGTH, ArmyType
from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.turn.combat import Quality
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.turn.battle_orchestrator import (
    MultiAttackerBattle,
    MultiAttackerParty,
    fight_battle,
    fight_multi_attacker_battle,
    snapshot_army_types,
)
from ak_engine.turn.army_list_decode import ArmyListRequest, decode_army_list_phase
from ak_engine.turn.aspy_defend_decode import decode_defend_phase
from ak_engine.turn.blackmail import advance_blackmail_claims
from ak_engine.turn.cast_decode import CHARACTER_TARGET_SPELLS, decode_cast_phase
from ak_engine.turn.diplomacy import advance_pending_diplomacy, apply_treat_orders, is_attackable_at
from ak_engine.turn.initiative import character_initiative
from ak_engine.turn.recruit_decode import decode_recruit_phase
from ak_engine.turn.sea_transport import apply_battle_carrier_destruction
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.aspy_execution import execute_aspy
from ak_engine.turn.cast_execution import maybe_dissolve_illusory_terrain
from ak_engine.turn.challenge_execution import execute_challenge
from ak_engine.turn.trade_decode import decode_trade_phase
from ak_engine.turn.battle_line import estimate_win_probability
from ak_engine.turn.challenge_pursue_decode import PursueRequest, decode_challenge_phase, decode_pursue_phase
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.defend_execution import DefendCoverage, DefendReinforcement, defend_coverage_area, defend_radius_for_leader
from ak_engine.turn.diplomatic_merit import apply_diplomatic_merit
from ak_engine.turn.expenses import apply_turn_maintenance
from ak_engine.turn.contested_province import (
    IllegalMoveFromContestedError,
    attacker_can_force_rebattle,
    is_illegal_move_from_contested,
)
from ak_engine.turn.hex_numbering import decode_hex_number, encode_hex_number
from ak_engine.turn.plague_spread import resolve_plague_spread
from ak_engine.turn.missed_deadline import build_missed_deadline_plan
from ak_engine.turn.move_execution import (
    MoveExecutionResult,
    TransportIllegalMoveError,
    apply_pending_mercenary_follows,
    find_transport_illegality,
    record_kingdom_exploration,
    reveal_adjacent_provinces,
)
from ak_engine.turn.movement import MapBounds, resolve_move
from ak_engine.turn.office_holder import apply_battle_fool_aptitude_escalation, apply_cravenest_temperament_escalation
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.plan_dispatch import PhaseDispatchResult, _has_spy_super_sleuth, dispatch_phase, run_leader_plan
from ak_engine.turn.practice_decode import decode_practice_phase
from ak_engine.turn.command_experience import award_sage_practice_experience
from ak_engine.turn.practice_execution import commit_pending_skill_advancements, execute_practice_group
from ak_engine.turn.patrol_execution import execute_patrol
from ak_engine.turn.pursue_execution import PursueExecutionResult, advance_pursuit, execute_pursue
from ak_engine.turn.scientific_treaty import execute_scientific_treaties
from ak_engine.turn.sep_decode import decode_special_encounter_plan
from ak_engine.turn.skeletal_decay import decompose_graveyard
from ak_engine.turn.monster_raids import age_all_feature_guardians, maybe_dissipate_hidden_feature
from ak_engine.turn.tax_base import apply_turn_revenue
from ak_engine.turn.wandering_units import resolve_wandering
from ak_engine.turn.trail_decode import decode_trail_phase
from ak_engine.turn.trail_execution import TrailExecutionResult, advance_trail
from ak_engine.turn.valhalla_execution import (
    finalize_gate_angel_visit,
    finalize_ordinary_valhalla_visit,
    process_valhalla_departure,
)

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
    board_width: int | None = None,
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
    desertion/standby, see that module's own Phase 527 addendum), and, as
    of Phase 869, ``turn/scientific_treaty.py execute_scientific_
    treaties()`` immediately followed by ``turn/diplomatic_merit.py
    apply_diplomatic_merit()`` -- [8.4]'s own "after finances are
    computed" exchange plus the Silver Tongue merit it feeds, previously
    built (Phase 445/474/511/643/714/738) but never actually called from
    anywhere; see both modules' own docstrings for the full sourcing. One
    call to ``run_turn()`` is the one unambiguous "once per game turn"
    boundary this phase-by-phase loop offers; see each function's own
    module docstring for why it lives here rather than per-phase.

    ``board_width`` (Phase 780, default ``None``) is now optional --
    when omitted, falls back to ``state.board_width``, the real value
    the world was actually built at (``worldgen/generate_new_game.py``/
    ``parser/gw_world_bridge.py``). An explicit value still overrides it
    (every existing caller that already supplies one keeps working
    unchanged). ``state.board_height`` is used directly for this
    function's own ``bounds`` -- before this phase there was no way to
    supply a real height here at all; it was silently always
    ``NORMAL_MAP_BOUNDS[1]`` (confirmed the *Super-AK* size, `Regolamento
    AK.txt` 12.1, not the "normale" 18x9 default).
    """

    rng = rng if rng is not None else random.Random()
    board_width = board_width if board_width is not None else state.board_width
    results: list[PhaseDispatchResult] = []
    bounds = MapBounds(board_width, state.board_height)
    active_defends: dict[int, DefendCoverage] = {}  # defender leader_id -> origin + coverage area
    active_pursuits: dict[int, _ActivePursuit] = {}  # pursuer/trailer leader_id -> ongoing chase
    active_move_chases: dict[int, _ActiveMoveChase] = {}  # mover leader_id -> ongoing non-adjacent Move chase
    # Phase 1041 bug fix -- now the real, persistent `GameState.active_
    # patrols` (mutated in place throughout this call), not a local dict
    # recreated empty on every `run_turn()` call -- see that field's own
    # docstring for why Patrol, unlike Defend/Pursue/Trail, must survive
    # the turn boundary.
    active_patrols = state.active_patrols
    # Rulebook [3.15]'s other Defend-cancellation trigger ("cancelled if
    # he loses a battle"): once a leader loses the one battle their own
    # Defend order can ever draw them into (see
    # _apply_defend_cancellations's own docstring for why that's the
    # complete scenario space), they can never register into
    # active_defends again for the rest of this run_turn() call, even if
    # a later phase in their own plan re-issues DEFEND -- persistent
    # across phases, unlike active_defends itself.
    defeated_while_defending: set[int] = set()

    # 2026-11-04 -- RULES.AK [3.18]'s own "treasury at the start of the
    # gameturn" basis for the Give Gold 10% cap -- taken before anything
    # else in this call can touch any Kingdom's own treasury. See
    # `KingdomState.treasury_at_turn_start`'s own docstring.
    for kingdom in state.kingdoms.values():
        kingdom.treasury_at_turn_start = kingdom.treasury
        kingdom.gold_given_this_turn = 0

    # Phase 713 -- AdvancedAbility.SPY_BLACKMAIL: promote every Kingdom's
    # own still-pending demand (delivered last turn) into "active" (due
    # this turn), before any phase dispatches -- mirrors the real parsed
    # `pending_blackmailer_king_id`/`active_blackmailer_king_id` field
    # pair exactly. See `turn/blackmail.py`'s own module docstring.
    advance_blackmail_claims(state)

    # 2026-11-03 -- freshly populated this call, read only after this
    # same `run_turn()` call returns (`orchestrator.py process_turn()`'s
    # own `compose_letter_report()` pass, strictly later) -- cleared here
    # rather than by `_replenish_turn_scoped_state()` at this call's own
    # end, which would wipe it before that later read ever happens. See
    # `GameState.diplomacy_relation_change_notices`'s own docstring.
    state.diplomacy_relation_change_notices = []

    # 2026-11-03 -- promotes any ordinary King's own Break Treat order
    # deferred last turn (RULES.AK [8.3]'s "alla fine del turno" timing,
    # as opposed to Evil/Undead's own same-turn exception) into a real
    # relation change, visible to *this* turn's own combat -- must run
    # before this same turn's own fresh `apply_treat_orders()` call
    # below, mirroring `advance_blackmail_claims()`'s own placement one
    # call up. See `turn/diplomacy.py`'s own module docstring.
    advance_pending_diplomacy(state)

    # Phase 1026 -- RULES.AK [8.2]/[8.3]'s own Treat/Break Treat orders,
    # resolved into real `diplomatic_relations` transitions before any
    # phase dispatches -- see `turn/diplomacy.py`'s own module docstring
    # for why this single early call (rather than a separate end-of-turn
    # pass) is this project's own documented timing simplification for
    # Treat; Break Treat's own timing is modeled for real as of
    # 2026-11-03 (see `advance_pending_diplomacy()` right above).
    apply_treat_orders(state)

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
        # [3.13]: a Practice skill/aptitude rise earned last phase (or,
        # carried across the turn boundary, last turn's own P4) takes
        # effect starting now -- before anything else this phase reads
        # a skill level. See LeaderState.pending_skill_advancement's own
        # docstring and commit_pending_skill_advancements()'s.
        commit_pending_skill_advancements(state)

        if phase_index > 0:
            results.extend(_dispatch_contested_rebattles(state, rng))
            newly_infected = resolve_plague_spread(state, rng, bounds)
            results.extend(
                PhaseDispatchResult(
                    leader_id=0, segment_index=-1, phase_label="plague-spread", action=None, result=coord, error=None
                )
                for coord in newly_infected
            )

        entries = _collect_phase_entries(turn_leaders, label, state)
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
        # [3.16]'s own same-Realm/same-starting-province Pursue ordering
        # rule (see "SAME-KINGDOM PURSUE ORDERING" below) needs each
        # leader's own location at the very start of this phase, before
        # any of this phase's own dispatches (including the ones below
        # this point, like active-chase continuations/Patrol/multi-
        # attacker groups) can mutate it.
        phase_start_location_by_leader_id: dict[int, HexCoord] = {}
        for tl, _segment_index, _phase in entries:
            leader_state = state.leaders.get(tl.leader.leader_id)
            if leader_state is not None:
                phase_start_location_by_leader_id[tl.leader.leader_id] = leader_state.location
        # Phase 252, [3.17] Trail's own "Actions" field: every leader's own
        # decoded action for this phase label, computed AFTER the mid-chase
        # filter above (Phase 817 fix -- this used to be built from the
        # unfiltered `entries`, so a target who was itself mid-chase but
        # still had a real, now-preempted order queued for this same phase
        # leaked that never-dispatched order into a Trail report instead of
        # the documented `None`). A leader with no entry here (mid-chase, or
        # simply idle) has no real order this phase to report, the same
        # "no data" convention trail_execution.py's own module docstring
        # already uses for its other fields. See that docstring's Phase 252
        # note. This snapshot is still taken BEFORE Patrol cancellation/
        # preemption below, so it's pruned again once `patrol_preempted` is
        # known (Phase 817 follow-up fix, same leaked-order failure mode but
        # for a leader's own standing Patrol intercepting their own queued
        # order this phase instead of a mid-chase filter).
        action_this_phase_by_leader = {tl.leader.leader_id: phase.action for tl, _segment_index, phase in entries}
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
        # Phase 1041 bug fix -- a self-targeting PURSUE is still a PURSUE
        # order for rulebook [3.15]'s own Defend-cancellation purposes
        # ("If he receives a Move, Pursue or Trail order, the Defend
        # order is cancelled"), but it's already stripped out of
        # ``entries`` above, before ``_apply_defend_cancellations()``
        # ever runs -- so declaring a Patrol used to never cancel that
        # same leader's own active Defend order. Cancelled directly here
        # instead, the same ``.pop(leader_id, None)`` convention
        # ``_apply_defend_cancellations()`` itself uses.
        for leader_id in new_patrol_leader_ids:
            active_defends.pop(leader_id, None)

        _apply_patrol_cancellations(active_patrols, entries)
        patrol_results, patrol_preempted = _dispatch_active_patrols(active_patrols, label, state, rng, bounds)
        results.extend(patrol_results)
        entries = [entry for entry in entries if entry[0].leader.leader_id not in patrol_preempted]
        # Phase 817 follow-up fix: `action_this_phase_by_leader` was snapshotted
        # above before this Patrol preemption was known, so a leader whose
        # queued order this phase was just preempted by their own standing
        # Patrol interception (`patrol_preempted`) still has that
        # never-dispatched order in the map. Drop it here, before
        # `_backfill_trail_actions` (and any other later consumer) reads it,
        # so a Trail targeting that leader reports `None` instead of the
        # preempted order's own ActionCode.
        action_this_phase_by_leader = {
            leader_id: action for leader_id, action in action_this_phase_by_leader.items() if leader_id not in patrol_preempted
        }

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
            # Phase 1041 bug fix -- unlike every ordinary single-leader
            # phase (dispatched through `run_leader_plan()`, whose own
            # broad `except Exception` keeps one leader's dispatch error
            # from crashing the whole turn), this grouped dispatch had no
            # isolation of its own: an exception here used to propagate
            # straight out of `run_turn()`, discarding every already-
            # computed `PhaseDispatchResult` for every other kingdom/
            # leader processed earlier this same call.
            try:
                group_results = _dispatch_multi_attacker_lmove(movers, target, state, board_width, explorer_skill, rng)
            except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
                group_results = [
                    PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, None, exc)
                    for tl, segment_index, phase in movers
                ]
            results.extend(group_results)
            _apply_defend_battle_loss(defeated_while_defending, reinforced_by_target, target, group_results)
            _apply_defend_battle_win(active_pursuits, reinforced_by_target, target, group_results)

        for ability, indices in multi_practice_groups:
            movers = [entries[i] for i in indices]
            # Phase 1041 bug fix -- see the identical note above.
            try:
                group_results = _dispatch_multi_practice(movers, ability, state, rng)
            except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
                group_results = [
                    PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, None, exc)
                    for tl, segment_index, phase in movers
                ]
            results.extend(group_results)

        for index_a, index_b in mutual_encounter_pairs:
            # Phase 1041 bug fix -- see the identical note above.
            try:
                pair_results = _dispatch_mutual_encounter(entries[index_a], entries[index_b], state, rng)
            except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
                pair_results = [
                    PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, None, exc)
                    for tl, segment_index, phase in (entries[index_a], entries[index_b])
                ]
            results.extend(pair_results)

        eligible_indices = [index for index in range(len(entries)) if index not in consumed]
        dispatch_order = _order_same_kingdom_pursuits_after_their_target(
            entries, eligible_indices, phase_start_location_by_leader_id
        )
        for index in dispatch_order:
            tl, segment_index, phase = entries[index]
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
                    _apply_defend_battle_win(active_pursuits, reinforced_by_target, target, dispatch_results)
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
    else:
        # Phase 756: the ordinary, per-turn automatic visit -- only ever
        # reached when Gate Angel didn't already claim this turn's one
        # visit. A distinct sentinel label ("valhalla-visit", not
        # "gate-angel-visit") since this spawn wasn't spell-triggered --
        # see turn/valhalla_execution.py's own Phase 756 addendum.
        visitor = finalize_ordinary_valhalla_visit(state, rng, board_width=board_width)
        if visitor is not None:
            results.append(
                PhaseDispatchResult(
                    leader_id=visitor.leader_id,
                    segment_index=-1,
                    phase_label="valhalla-visit",
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
    # Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT -- "at the end of the
    # Spy's last action, you will gain spy reports on the province he
    # occupies and the surrounding provinces, if they belong to the
    # hiring king." Every leader's own phases are already fully resolved
    # by this point in run_turn(), so the Spy's "last action" and "the
    # end of the turn" are the same real moment for the province the
    # Spy occupies -- reading it here, at this already-established
    # once-per-turn checkpoint, needs no new per-leader completion
    # tracking. `double_agent_hired_by_kingdom_id` is set by `turn/
    # plan_dispatch.py _dispatch_hire()`'s own Double Agent bypass, read
    # and cleared here (fully resolved within this same call, no
    # `_replenish_turn_scoped_state()` involvement needed). "If they
    # belong to the hiring king" is read as one precondition on the
    # whole grant (the Spy's own current province must be owned by the
    # hiring Kingdom), not a per-province filter inside the returned
    # SpyReport -- no source describes stripping out other provinces'
    # own real neighbor data. Deliberately doesn't thread the Spy's own
    # other Detect-Align/Psychic-Mage/Druidic-Animal-Spies/Spy-Expanded-
    # Spying flags into this automatic grant (defaults to False, same
    # as execute_aspy()'s own defaults) -- a rare ability combination
    # the source text doesn't describe interacting with this one.
    for spy in state.leaders.values():
        hiring_kingdom_id = spy.double_agent_hired_by_kingdom_id
        if hiring_kingdom_id is None:
            continue
        spy.double_agent_hired_by_kingdom_id = None
        spy_province = state.provinces.get(spy.location)
        if spy_province is None or spy_province.owner_kingdom_id != hiring_kingdom_id:
            continue
        # Bug fix: same isolation convention as run_leader_plan()'s own
        # per-phase try/except -- an exception for one Double Agent spy
        # used to propagate straight out of run_turn(), discarding every
        # already-computed PhaseDispatchResult for every other kingdom/
        # leader processed earlier this same call.
        try:
            double_agent_report = execute_aspy(
                state,
                spy.leader_id,
                SpyProvinceRequest(target_province=0, unconfirmed_extra0=0),
                board_width=state.board_width,
                board_height=state.board_height,
                rng=rng,
            )
        except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
            results.append(
                PhaseDispatchResult(
                    leader_id=spy.leader_id,
                    segment_index=-1,
                    phase_label="double-agent-report",
                    action=None,
                    result=None,
                    error=exc,
                )
            )
            continue
        if double_agent_report is not None:
            results.append(
                PhaseDispatchResult(
                    leader_id=spy.leader_id,
                    segment_index=-1,
                    phase_label="double-agent-report",
                    action=None,
                    result=double_agent_report,
                    error=None,
                )
            )
    # Phase 781: MERCHERO.md's own autonomous wandering of unemployed
    # Heroes and mercenary armies (AK.OVR:0xD6C5, backlog #20) -- once
    # per real turn, at this same "everything else has resolved" tail
    # position, matching the confirmed real call-site timing (section
    # 12.1: "phase counter already at 5"). The King-orders-flag gate is
    # resolved once here and threaded into every eligibility check.
    apply_pending_mercenary_follows(state)
    orders_flag = _kingdom_submitted_real_orders(turn_leaders, state)
    for relocation in resolve_wandering(state, orders_flag, rng):
        results.append(
            PhaseDispatchResult(
                leader_id=relocation.entity_id,
                segment_index=-1,
                phase_label="hero-wander" if relocation.kind == "hero" else "army-wander",
                action=None,
                result=relocation,
                error=None,
            )
        )
    # Oratory's one-rank boost lasts "for the rest of the turn" ([4.22.2]) --
    # taken back before the end-of-turn pay/upgrade step sees the armies.
    _revert_oratory_boosts(state)
    apply_turn_revenue(state, rng)
    apply_turn_maintenance(state, rng)
    # Phase 869: [8.4] Scientific Treaties -- "the exchange takes place
    # after finances are computed" (`turn/scientific_treaty.py`'s own
    # module docstring), placed after both real financial steps above.
    # `apply_diplomatic_merit()` (Silver Tongue, `Office.DIPLOMAT`)
    # consumes this same call's own result -- see both modules' own
    # docstrings for the full sourcing and why this call was missing
    # from `run_turn()` entirely until now.
    treaty_results = execute_scientific_treaties(
        state, board_width=board_width, board_height=state.board_height, rng=rng
    )
    apply_diplomatic_merit(state, treaty_results, board_width=board_width, board_height=state.board_height)
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
    # 2026-11-18 bug fix, user-confirmed: a King who died this turn must
    # stay genuinely gone from state.leaders for the rest of it (exactly
    # like an ordinary Hero) -- the Royal Heir only takes the throne
    # for the turn that comes after, hence installing it here, at this
    # same real turn boundary, rather than synchronously inside
    # GameState.remove_leader() itself. See that method's own docstring
    # for the full reasoning.
    state.install_pending_royal_heirs()
    state.turn_number += 1

    return results


def _kingdom_submitted_real_orders(turn_leaders: list[TurnLeader], state: GameState) -> dict[int, bool]:
    """``DS:8B52`` -- "did this King's own Kingdom submit any real order
    this turn" (MERCHERO.md, Phase 781, user-confirmed to implement
    faithfully). MERCHERO's own 4-row table (pending-vs-submitted
    leaders) collapses to "does at least one leader of this King have a
    real first action" -- the "mixed empty/non-empty" and "all
    non-empty" rows both resolve ``True``, and only "none" or "all
    empty" resolve ``False``.

    Computed once, here, from data ``run_turn()`` already has in scope
    -- ``turn_leaders`` (this turn's real submitted plans) and ``state.
    leaders`` (every leader who currently belongs to a Kingdom).
    """

    turn_leader_by_id = {tl.leader.leader_id: tl for tl in turn_leaders}
    kingdom_ids = {leader.kingdom_id for leader in state.leaders.values() if leader.kingdom_id is not None}
    submitted_by_kingdom: dict[int, bool] = {}
    for kingdom_id in kingdom_ids:
        submitted = False
        for leader_id, leader in state.leaders.items():
            if leader.kingdom_id != kingdom_id:
                continue
            turn_leader = turn_leader_by_id.get(leader_id)
            if turn_leader is None or not turn_leader.leader.plan.segments:
                continue
            phase0 = turn_leader.leader.plan.segments[0].phases.get("P0")
            if phase0 is not None and phase0.action is not ActionCode.NO_ACTION:
                submitted = True
                break
        submitted_by_kingdom[kingdom_id] = submitted
    return submitted_by_kingdom


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


def _revert_oratory_boosts(state: GameState) -> None:
    """Takes back the rank Oratory added to each army for the turn."""

    for army in state.armies.values():
        levels = getattr(army, "oratory_boost_levels", 0)
        if levels:
            army.quality = Quality(max(int(army.quality) - levels, min(int(member) for member in Quality)))
            army.oratory_boost_levels = 0


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
    - ``ArmyState.recruited_this_turn`` -> ``False`` (2026-10-29) --
      rulebook [3.9]'s own "can't Pick Up a freshly recruited unit this
      same turn" is scoped to the turn the unit was recruited in, not
      forever; otherwise a freshly levied army would stay permanently
      un-Pick-Up-able for the rest of the game (`turn/plan_dispatch.py
      _dispatch_pick_up()`'s own real consumer).
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
    - ``GameState.treat_permissions`` -> ``set()`` (Phase 874) -- rulebook
      [3.4]'s own quoted text scopes a Treat grant to "this gameturn"; the
      field's own docstring had explicitly flagged it as the one field in
      this family still "the caller's job to clear," since no in-project
      Treat-order decoder exists yet to populate it in production. Closed
      proactively (no live game currently sets this field, so this is a
      real, sourced correctness fix with zero observable behavior change
      today) rather than leaving it to silently repeat the exact same
      "field forgotten, permission never expires" bug the moment a future
      phase wires a real Treat-order decoder in.
    - ``GameState.break_treat_orders`` -> ``set()`` (Phase 1026) -- same
      "this gameturn only" scope and same "caller's job, no decoder
      exists" category as ``treat_permissions`` right above; see
      ``turn/diplomacy.py`` for the one real reader (called before this
      reset, early in ``run_turn()``).
    - ``ArmyState.flood_dams_exempt_at`` -> ``None`` (Phase 888) --
      Discovery.FLOOD_DAMS's own rest-of-turn exemption from the
      Flooded-province movement block (`turn/move_execution.py
      _land_crossing_blocked()`) is scoped to "this turn," per its own
      already-charged one-time toll being a per-cast event -- otherwise
      an army once excused at a given coord would stay excused there
      forever, for the rest of the game.
    - ``ProvinceState.terrain_override`` -> ``None`` (Phase 1046) --
      Part Sea's own quoted rule ([4.21.2], "transformed into a Plain
      for the rest of the turn") and Flood's own analogous "for the
      rest of the turn" framing both say this is turn-scoped, but
      `models/game_state.py`'s own module docstring had flagged this
      field as "not auto-cleared at a turn boundary... still has no
      reset call anywhere" ever since Phase 59 -- the exact same
      "sourced one-turn duration, never actually cleared" bug Phase 576
      already fixed for ``illusory_fog_active`` right above, just not
      yet audited here. A province Part Sea'd or Flooded stayed
      permanently transformed for the rest of the game.
    - ``ProvinceState.tax_modifier_percent``/``earthquake_flat_
      reduction`` -> ``0`` (Phase 1046) -- Bless ([4.21.3], "+60% for
      one turn") and Earthquake ([4.24.3], "-100%"/a flat Reinforced-
      Concrete-defended reduction, "for one turn") are both explicitly
      one-turn effects, but neither field had a reset call either --
      the same unresolved gap `tax_modifier_percent`'s own module
      docstring entry already flagged, and `earthquake_flat_reduction`'s
      own field comment explicitly cross-references as sharing it
      ("the caller resets it the same 'no auto-clear yet' way"). A
      Blessed or Earthquake-struck province kept the modified tax rate
      forever instead of for the one documented turn.

    ``GameState.gate_angel_candidates_this_turn`` is deliberately NOT
    touched here despite its own name -- it's already self-resetting,
    gated on a direct ``state.turn_number`` comparison against its own
    ``gate_angel_due_alignment_turn`` cache (`turn/cast_execution.py`),
    which only works correctly now that ``turn_number`` itself actually
    advances (see this function's own call site).

    **Phase 820 bug fix**: ``ARMY_TABLE[army.army_type]`` used to be a
    bare lookup. 8 real, catalog-named ``ArmyType`` members (Vampires,
    Marauders, Shamans, Crossbow, Javelins, Artillery, Spiders, D-Turtle
    -- ``models/army_type.py``'s own Phase 383 addendum: "none of these
    9 appear in the rulebook's Army Type Table [6.3]... get no
    ArmyTypeStats... entry", Dinosaurs being the 9th, now the one
    exception with a real entry since Phase 691) have no ``ARMY_TABLE``
    entry at all -- confirmed no current world-generation code path
    ever actually constructs one of these 8 (``Race.VAMPISH`` in
    particular is only ever *mapped* to ``ArmyType.VAMPIRES`` via
    ``worldgen/initial_armies.py NATIVE_ARMY_TYPE``, never *placed* by
    ``generate_new_game()``, since it was never added to ``worldgen/
    special_race_placement.py SPECIAL_RACE_BASE_COUNT``), but this
    function is the *one* unconditional, unguarded step at the tail of
    every ``run_turn()`` call -- reached for every real turn, with no
    ``try``/``except`` anywhere between it and ``run_turn()``'s own
    caller. A single such army anywhere on the map (via ``GameState.
    add_army()``, a fully public API any moderator tool, test fixture,
    or future world-gen phase can call directly) would raise
    ``KeyError`` here and crash the *entire* turn's processing for
    *every* kingdom, silently discarding every already-computed
    ``PhaseDispatchResult`` -- the same class of "bare lookup into an
    ArmyType-keyed table with known gaps" bug this project already
    fixed once for real (Phase 799, ``build_initial_armies()``'s own
    missing ``BASE_STRENGTH`` entry for Elephants), and the exact same
    known gap ``_boarding_priority_tier()`` (this module) already
    handles safely via ``ARMY_TABLE.get(...)``. Fixed the same way: an
    army whose own type has no ``ARMY_TABLE`` entry keeps whatever
    ``movement_points`` it already had -- no invented value, matching
    this project's own "no source, no guess" convention, and no crash.
    """

    for army in state.armies.values():
        stats = ARMY_TABLE.get(army.army_type)
        if stats is not None:
            army.movement_points = stats.speed
        army.march_bonus_applied_this_turn = False
        army.naval_bonus_applied_this_turn = False
        army.march_table_bonus_applied_this_turn = False
        army.unhireable_this_turn = False
        army.recruited_this_turn = False
        army.flood_dams_exempt_at = None
        army.mystic_winds_prior_movement = None
    for province in state.provinces.values():
        province.recruited_this_turn = {}
        province.recruit_locked_this_turn = False
        province.illusory_fog_active = False
        province.terrain_override = None
        province.tax_modifier_percent = 0
        province.earthquake_flat_reduction = 0
        # Plague ([4.25.3]) spreads "each phase" of the turn it was cast in;
        # the real reports show no spread in the turn after (SE3__T10 -> T11).
        province.plague_active = False
    for leader in state.leaders.values():
        leader.oratory_boosted_this_turn = False
        # Mystic Winds: the spell ends with the turn.
        leader.mystic_winds_active = False
        # Phantasmal Armies ([4.23.2]): "for the rest of the turn".
        leader.phantasmal_armies_level = 0
    for kingdom in state.kingdoms.values():
        kingdom.treasury_raid_attempts_this_turn = 0
    state.action_casts_used = {}
    state.treat_permissions = set()
    state.break_treat_orders = set()


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


def _army_strength(army) -> float:
    """A cheap, real-data-backed combat-strength estimate for one army --
    ``BASE_STRENGTH[army_type] * int(quality)``, the same "base x
    quality" starting point ``turn/strength.py compute_effective_
    strength()`` itself multiplies onward from, before any terrain/
    defender/tactical bonus is layered on (2026-11-01, no dedicated
    "is force A strong enough vs force B" function exists anywhere in
    this project -- this is the cheapest honest reuse of real existing
    numbers rather than an invented one). Garrison isn't in
    ``BASE_STRENGTH`` at all (``models/army_type.py``'s own module
    docstring: handled as two named constants instead, one per combat
    role) -- a Defend reinforcement always fights on the defending side
    of whatever battle it joins (rulebook: "le sue truppe
    combatteranno a fianco dei difensori"), so ``GARRISON_DEFENSE_
    STRENGTH`` is the one of the two that applies here. Used only by
    ``_apply_defend_reinforcements()``'s own "intelligent reinforcement"
    heuristic below -- not a new canonical strength formula.
    """

    if army.army_type is ArmyType.GARRISON:
        return GARRISON_DEFENSE_STRENGTH * int(army.quality)
    return BASE_STRENGTH.get(army.army_type, 0) * int(army.quality)


_DEFEND_REINFORCEMENT_WIN_PROBABILITY_FLOOR = 0.5


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
    coverage is **consumed only once a reinforcement actually happens**
    this ``run_turn()`` call: once committed to one battle, they're no
    longer standing by to cover their original area for a second,
    unrelated invasion later in the turn (a documented simplification,
    not sourced -- the rulebook doesn't address a general reinforcing
    twice in the same turn). A phase where this defender's force can't
    react at all, or deliberately stays home (see below), leaves the
    coverage untouched for a later phase to still draw on.

    **2026-11-01 additions, sourced directly from the user's own full
    Italian [3.15] text, closing four previously-undocumented gaps**:

    1. **Terrain/transport legality**: each of the defender's own armies
       is checked individually via ``find_transport_illegality()`` (the
       same pure legality gate ordinary Move already uses) against the
       hop from this leader's own current province to the chosen
       target -- "un generale non reagirà all'invasione se la sua
       unità militare non può muovere nella zona invasa." An army that
       fails this check (e.g. a land unit a Fleet can't carry, or a
       Fleet trying a land-to-land hop) is simply excluded from the
       pool of armies that can react, exactly like a wrong-terrain Move
       would refuse that army. If no army passes, this defender can't
       react to this invasion at all this phase.
    2. **Movement Point cost**: "questi movimenti costano Punti
       Movimento, e quindi un'unità che ha speso tutti i suoi Punti
       Movimento non può più reagire." Each candidate army must have
       ``movement_points >= movement_cost_for_move(battle_occurred=True)``
       (the real per-hex-entered cost, always the "+1, a battle
       happened" variant here since joining a defended province's own
       fight is the entire premise) and is charged that same cost on
       departure -- the same formula and field ordinary LMOVE already
       uses, replenished only once per turn by ``_replenish_turn_
       scoped_state()``, same semantics. **Deliberately not modeled**:
       the rulebook's own "3 moves for a full defend-then-return trip"
       (speed >= 3, or a good March Talent) -- this project's Defend
       reinforcement has no "return home" leg at all (the general
       simply relocates, permanently, same as before this round, modulo
       the new pursuit-on-win addendum below), so there is no return
       trip to charge a second/third move for; only the one real,
       modeled leg (arriving to fight) is charged. March Talent's own
       movement-point bonuses (``march_movement_point_bonus()``/
       ``march_table_extra_movement()``) are also not threaded in here
       -- a further, orthogonal refinement on top of the base cost
       charged above, left for later rather than this round.
    3. **"Intelligent" splitting**: only reachable when the defender's
       own *current* province is **also** invaded this same phase (the
       rulebook's own example: "invia unità militari in una provincia
       difesa E in due province adiacenti" -- a genuine competing claim
       on this general's forces). With no such competing claim (every
       pre-existing test fixture, and surely the overwhelmingly common
       case), the general still takes his *whole* eligible force to the
       one covered province under attack, exactly as before this round.
       When home *is* also under threat, the minimal prefix of the
       defender's own armies (strongest first) whose summed strength
       clears a 50% ``estimate_win_probability()`` against the chosen
       invader is sent, **provided** the armies left behind still clear
       that same 50% floor against the home invader; if no such split
       exists (even the full force doesn't clear 50% at the target, or
       any split that does leaves home with nothing or an indefensible
       remainder), the general sends nobody -- "rimanere a difendere la
       provincia." The 50% floor and the "strongest-first, minimal
       sufficient prefix" selection are both documented interpretations,
       not sourced formulas -- the rulebook names no numbers here, only
       this project's own existing win_probability curve (anchored at
       the rulebook's own real "1:1 -> 50%" Battle Odds data point) as
       the least-invented building block to reuse. Strength per army is
       ``_army_strength()``, above.
    4. **Among 2+ simultaneously-invaded *covered* provinces** (as
       distinct from (3)'s home-vs-neighbor split): "andrà in aiuto di
       una provincia adiacente" (singular) is read as the single
       biggest threat by summed invading strength, not the first one
       encountered in iteration order -- also a documented judgment
       call, the rulebook names no tiebreak. Ties keep the first-
       encountered order, matching this function's own pre-existing,
       untouched behavior when strength doesn't distinguish the choice.

    Returns ``{defender_leader_id: DefendReinforcement(origin, target)}``
    for every reinforcement performed this call -- ``run_turn()`` uses
    ``.target`` to look up that same battle's outcome once this phase's
    LMOVE dispatch resolves it, for rule [3.15]'s own two reactive
    cancellation/pursuit triggers (see ``_apply_defend_cancellations``'s
    own docstring, ``_apply_defend_battle_loss``, and ``_apply_defend_
    battle_win``). ``.origin`` (the defender's own province before
    relocating) exists solely for ``describe_defend_reinforcement()``
    (Phase 422, ``SAY.PAS _LHearInv``'s own ``@`` marker) -- captured
    here because ``defender_state.location`` is overwritten to
    ``target`` a few lines below, before this function returns.
    """

    reinforced: dict[int, DefendReinforcement] = {}
    if not active_defends:
        return reinforced

    invaded_provinces: dict[HexCoord, list[int]] = {}
    for index, target in move_targets.items():
        invaded_provinces.setdefault(target, []).append(index)

    def _invading_strength(defender_kingdom_id: int, indices: list[int]) -> float | None:
        total = 0.0
        saw_invader = False
        for i in indices:
            mover_tl = entries[i][0]
            mover_armies = state.armies_commanded_by(mover_tl.leader.leader_id)
            if not mover_armies or state.is_allied(mover_tl.kingdom_id, defender_kingdom_id):
                continue
            saw_invader = True
            total += sum(_army_strength(army) for army in mover_armies)
        return total if saw_invader else None

    for defender_leader_id, coverage in list(active_defends.items()):
        defender_state = state.leaders.get(defender_leader_id)
        if defender_state is None or defender_state.kingdom_id is None:
            continue

        candidates: list[tuple[HexCoord, float]] = []
        for target, indices in invaded_provinces.items():
            if target not in coverage.area:
                continue
            target_province = state.provinces.get(target)
            if target_province is None or target_province.owner_kingdom_id is None:
                continue
            owner = target_province.owner_kingdom_id
            if owner != defender_state.kingdom_id and not state.is_allied(owner, defender_state.kingdom_id):
                continue  # not friendly ground -- nothing to defend here
            strength = _invading_strength(defender_state.kingdom_id, indices)
            if strength is None:
                continue  # no real invader among this phase's movers into target
            candidates.append((target, strength))

        if not candidates:
            continue

        target, invading_strength = max(candidates, key=lambda pair: pair[1])
        target_province = state.provinces[target]

        home_location = defender_state.location
        home_invading_strength: float | None = None
        home_province = state.provinces.get(home_location)
        if home_province is not None and home_province.owner_kingdom_id == defender_state.kingdom_id:
            home_indices = invaded_provinces.get(home_location)
            if home_indices is not None:
                home_invading_strength = _invading_strength(defender_state.kingdom_id, home_indices)

        origin_province = state.provinces.get(home_location)
        eligible_armies = []
        for army in state.armies_commanded_by(defender_leader_id):
            if army.movement_points < movement_cost_for_move(battle_occurred=True):
                continue
            if find_transport_illegality([army], [army.army_id], origin_province, target_province) is not None:
                continue
            eligible_armies.append(army)

        if not eligible_armies:
            continue  # can't physically/logistically react at all this phase

        eligible_armies.sort(key=_army_strength, reverse=True)

        if home_invading_strength is None:
            armies_to_send = eligible_armies
        else:
            armies_to_send = None
            running_strength = 0.0
            for count, army in enumerate(eligible_armies, start=1):
                running_strength += _army_strength(army)
                if (
                    estimate_win_probability(running_strength, invading_strength)
                    < _DEFEND_REINFORCEMENT_WIN_PROBABILITY_FLOOR
                ):
                    continue
                remaining = eligible_armies[count:]
                if not remaining:
                    continue  # would leave home with nothing while home is itself under threat
                remaining_strength = sum(_army_strength(army) for army in remaining)
                if (
                    estimate_win_probability(remaining_strength, home_invading_strength)
                    < _DEFEND_REINFORCEMENT_WIN_PROBABILITY_FLOOR
                ):
                    continue  # this split leaves home too exposed -- keep looking
                armies_to_send = eligible_armies[:count]
                break
            if armies_to_send is None:
                continue  # not strong enough to split safely -- stays to defend the home province

        for army in armies_to_send:
            army.location = target
        origin = coverage.origin
        defender_state.location = target
        del active_defends[defender_leader_id]
        reinforced[defender_leader_id] = DefendReinforcement(origin=origin, target=target)

    return reinforced


def _extract_battle_report(result: object):
    """Reads whichever ``BattleReport`` a dispatch result actually carries (``Move
    ExecutionResult``/``MultiAttackerMoveResult`` are the only two battle-
    bearing shapes this module's own Defend machinery ever dispatches
    into), or ``None`` if ``result`` carries no battle at all. Shared by
    ``_extract_battle_winner``/``_apply_defend_battle_win`` so both read
    the exact same report.
    """

    if isinstance(result, MoveExecutionResult):
        return result.battle_report
    if isinstance(result, MultiAttackerMoveResult):
        return result.battle.report
    return None


def _extract_battle_winner(result: object) -> str | None:
    """Reads ``BattleResult.winner`` ("attacker"/"defender"/"tie") out of whichever
    battle-bearing result shape a dispatch produced, or ``None`` if
    ``result`` carries no battle at all. See ``_apply_defend_cancellations``'s
    own docstring for why only this one, narrowly-scoped case (a
    Defend-reinforcement-triggered battle) is checked.
    """

    battle_report = _extract_battle_report(result)
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


def _apply_defend_battle_win(
    active_pursuits: dict[int, _ActivePursuit],
    reinforced_by_target: dict[HexCoord, list[int]],
    target: HexCoord,
    dispatch_results: list[PhaseDispatchResult],
) -> None:
    """Rulebook [3.15] (2026-11-01, previously unmodeled): "Se vince la
    battaglia, inseguirà il generale che ha invaso la provincia
    adiacente." Mirrors ``_apply_defend_battle_loss``'s own single-
    battle-per-``target`` scan, but registers a brand-new chase instead
    of cancelling one, the moment this phase's own LMOVE dispatch
    resolves the exact battle a Defend reinforcement just drew
    ``target``'s defender(s) into.

    Constructs a synthetic ``_ActivePursuit`` directly rather than via
    ``_register_pursuit_continuation()`` -- that function only ever re-
    registers a *real*, already-decoded PURSUE phase this same leader
    themselves issued and dispatched; a Defend-reinforcement win was
    never such a phase, so there's no ``PlanPhase`` to re-decode.
    ``PursueRequest.unconfirmed_extra0``/``.tactics`` carry no real wire
    data for this synthetic case either way (``tactics=[]`` is also
    functionally identical to any real combat tactic here, since the
    one real consumer -- an army-leading loser next phase -- dispatches
    through ``advance_pursuit()``'s own pure army-vs-army rebattle
    branch, which never reads ``tactics`` at all). If the loser's own
    armies were destroyed outright in this same battle (not merely
    defeated), ``advance_pursuit()``'s own [3.16] army-leading-mismatch
    check will find nothing left to chase and silently end the pursuit
    next phase -- a real, pre-existing rule this registration simply
    inherits, not a bug.

    Reads the winning battle's own attacker commander off ``BattleReport.
    attacker_commander_leader_id`` (falling back to the first entry of
    ``.attacker_commanding_leader_ids`` for a Multiple-Contingents group
    with no single elected duel commander) -- see ``turn/battle_
    orchestrator.py BattleReport``'s own fields.
    """

    defender_leader_ids = reinforced_by_target.get(target)
    if not defender_leader_ids or not dispatch_results:
        return
    for result in dispatch_results:
        battle_report = _extract_battle_report(result.result)
        if battle_report is None:
            continue
        if battle_report.battle_result.winner != "defender":
            return
        attacker_leader_id = battle_report.attacker_commander_leader_id
        if attacker_leader_id is None and battle_report.attacker_commanding_leader_ids:
            attacker_leader_id = battle_report.attacker_commanding_leader_ids[0]
        if attacker_leader_id is None:
            return
        for defender_leader_id in defender_leader_ids:
            active_pursuits[defender_leader_id] = _ActivePursuit(
                kind="pursue",
                request=PursueRequest(target_character_id=attacker_leader_id, unconfirmed_extra0=0, tactics=[]),
            )
        return


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
            result = advance_pursuit(
                state,
                leader_id,
                active.request,
                rng,
                has_spy_super_sleuth=has_spy_super_sleuth,
                board_width=state.board_width,
                board_height=state.board_height,
            )
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
                board_width=state.board_width,
                board_height=state.board_height,
            )
            action = ActionCode.TRAIL
            still_chasing = not result.spied_on and result.reason == _TRAIL_STILL_CHASING_REASON
            if result.spied_on:
                result.actions = action_this_phase_by_leader.get(active.request.target_character_id)

        # Phase 1041 bug fix -- the first-phase dispatch (plan_dispatch.py's
        # own `_dispatch_pursue()`/`_dispatch_trail()`) always stamps
        # `result.request` right after dispatching; this continuation path
        # never did, so a real catch-up resolved here (a kill, loot, an
        # intelligence report -- fully applied to `state`) had its
        # `.request` left `None`, and `report/turn_report.py`'s own
        # `describe_turn_results()` unconditionally skips narration
        # whenever `.request` is `None` -- silently dropping the whole
        # event from the player's turn report.
        result.request = active.request

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
    -- ``None`` if the target has no entry (idle, itself mid-chase and
    excluded from this phase's own entries, or had this phase's own queued
    order preempted by their own standing Patrol interception -- see the
    Phase 817 follow-up fix where ``action_this_phase_by_leader`` is pruned
    by ``patrol_preempted``). See ``turn/trail_execution.py``'s own module
    docstring for why ``execute_trail()`` itself can't do this.
    """

    for entry in dispatch_results:
        result = entry.result
        if not isinstance(result, TrailExecutionResult) or not result.spied_on or result.request is None:
            continue
        result.actions = action_this_phase_by_leader.get(result.request.target_character_id)


def _main_dispatch_result(dispatch_results: list[PhaseDispatchResult], action: ActionCode) -> object | None:
    """Finds this phase's own real dispatch result among ``dispatch_results``
    -- by matching ``action``, not by assuming it's ``dispatch_results[-1]``.

    **Phase 1041 bug fix**: a single dispatched phase can produce more than
    one ``PhaseDispatchResult`` -- ``run_leader_plan()`` appends a trailing
    random-encounter sentinel after an LMOVE/PURSUE/TRAIL phase whenever one
    fires (``turn/random_encounter_execution.py``'s own ``_TRIGGERING_
    ACTIONS``), and an LMOVE can additionally append its own Naval Hug
    Coastline "unboarded stragglers" sentinel (Phase 766) -- and *both*
    sentinel kinds are always recorded with ``action=None``, never the real
    dispatched ``ActionCode`` (see each one's own append site). Blindly
    indexing ``[-1]`` can therefore grab a sentinel instead of the real
    result -- wrongly treating a dispatch that said "still chasing" as if it
    had ended, which is exactly what used to make a persistent chase stop
    one phase early whenever a random encounter fired on the same phase.
    Matching on ``action`` instead finds the one real entry every time,
    since a sentinel's own ``action`` is never the real dispatched one and
    there is always exactly one real entry per dispatched phase.
    """

    for entry in dispatch_results:
        if entry.action is action:
            return entry.result
    return None


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

    result = _main_dispatch_result(dispatch_results, phase.action)

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
        # Phase 766 -- mirrors run_leader_plan()'s own identical Phase 766
        # addendum: a chase-continuation LMOVE can trigger the Naval Hug
        # Coastline stragglers split too, so it needs the same sentinel.
        if isinstance(result, MoveExecutionResult) and result.straggler_result is not None:
            results.append(PhaseDispatchResult(leader_id, -1, label, None, result.straggler_result, None))
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

    # Phase 1041 bug fix -- see ``_main_dispatch_result()``'s own
    # docstring: ``dispatch_results[-1]`` can be a trailing sentinel (a
    # random encounter, or this same LMOVE's own Naval Hug Coastline
    # straggler split) instead of the real move result, and both
    # sentinel kinds are themselves ``MoveExecutionResult`` instances
    # too, so an ``isinstance`` check alone can't tell them apart from
    # the real one the way it can for Pursue/Trail.
    result = _main_dispatch_result(dispatch_results, ActionCode.LMOVE)
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
        # Phase 1041 bug fix -- the ordinary single-leader path
        # (plan_dispatch.py's own `_dispatch_pursue()`) always computes
        # and passes `has_spy_super_sleuth`; this mutual-encounter path
        # used to silently omit it, defaulting to `False` regardless of
        # whether the initiator actually holds the ability -- losing its
        # documented "the catch-up roll is bypassed, success is
        # automatic" guarantee (and the resulting `guessed_distance`)
        # whenever a Spy-Super-Sleuth leader's own Pursue happened to
        # form a same-phase mutual-encounter pair.
        result = execute_pursue(
            state,
            tl.leader.leader_id,
            request,
            rng,
            mutual_encounter=True,
            has_spy_super_sleuth=_has_spy_super_sleuth(state, tl.leader.leader_id),
        )

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

        # Phase 1192 bug fix: this used to be a bare `not state.is_allied(...)`
        # check, missing diplomacy.py is_attackable_at()'s own [8.1]
        # "triangle" rule -- an army physically present can still be
        # shielded from this attacker because the *province's owner* (a
        # third Kingdom) is Allied with the attacker, not just because
        # the army's own Kingdom is. Without this, a province could stay
        # "contested" with no genuinely attackable defender actually
        # present, and fight_battle()'s own correct is_attackable_at()-
        # based defender derivation below would then find zero real
        # defenders and raise -- uncaught here, unlike the per-leader
        # dispatch paths (see module docstring's own Phase 1041 note).
        # 2026-11-19 bug fix, user-confirmed -- see turn/move_execution.py's
        # own matching 2026-11-19 addendum: excludes actual recruitable
        # mercenaries (`ArmyState.is_mercenary`), not every `kingdom_id
        # is None` army (an independent Hero's own personally-led army
        # is a real defender too).
        defenders_present = any(
            not army.is_mercenary and is_attackable_at(state, army.kingdom_id, attacker_kingdom_id, province)
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
        army_types_before_battle = snapshot_army_types(state)
        # Phase 1192 bug fix: isolate one contested province's own
        # fight_battle() failure from poisoning every other contested
        # province's own already-computed result this same call -- the
        # same "one bad entity shouldn't discard the whole batch" fix
        # Phase 1041 already applied to the other grouped dispatch loops
        # a few hundred lines above. The defenders_present fix just above
        # already prevents the one known real trigger (a stale "ally
        # shields every army here" gap), but this keeps that guarantee
        # even if some other, not-yet-identified edge case lets
        # fight_battle() raise.
        try:
            report = fight_battle(
                state,
                attacker_kingdom_id,
                coord,
                army_ids,
                attacker_origin=province.contested_from_coord,
                apply_fanaticism=True,
                use_real_duel_combat=True,
                rng=rng,
            )
        except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
            results.append(
                PhaseDispatchResult(
                    leader_id=0,
                    segment_index=-1,
                    phase_label="forced-rebattle",
                    action=None,
                    result=None,
                    error=exc,
                )
            )
            continue
        # Phase 716: the cargo sinks with the carrier.
        apply_battle_carrier_destruction(
            state,
            report.destroyed_army_ids,
            report.disbanded_army_ids,
            report.pursuit_destroyed_army_ids,
            coord=coord,
            army_types_before_battle=army_types_before_battle,
        )

        # Phase 1192 bug fix: a battle has unconditionally just occurred
        # above, so the real [7.7] extra-movement-point trigger always
        # applies here (Phase 915, turn/conquest.py's own docstring) --
        # reuse that shared, already-corrected formula directly instead
        # of the removed contested_battle_movement_cost()'s stale
        # "conquered-only" reading.
        cost = movement_cost_for_move(battle_occurred=True, conquered=report.conquered)
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
    if ability is Ability.SAGE:
        for tl, _segment_index, phase in movers:
            award_sage_practice_experience(state, tl.leader.leader_id, phase.label)
    return [
        PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, outcome, None)
        for (tl, segment_index, phase), outcome in zip(movers, outcomes)
    ]


def _collect_phase_entries(
    turn_leaders: list[TurnLeader], label: str, state: GameState
) -> list[tuple[TurnLeader, int, PlanPhase]]:
    entries = []
    for tl in turn_leaders:
        for segment_index, segment in enumerate(tl.leader.plan.segments):
            phase = segment.phases.get(label)
            if phase is not None:
                entries.append((tl, segment_index, phase))
    return _order_phase_entries_by_initiative(entries, state)


def _same_side(state: GameState, kingdom_a: int, kingdom_b: int) -> bool:
    return kingdom_a == kingdom_b or state.is_allied(kingdom_a, kingdom_b)


def _dropped_unled_army_locations(
    request: ArmyListRequest, acting_leader_id: int, state: GameState
) -> list[tuple[HexCoord, int]]:
    """For a Leave order with no named target (``target_leader_id is
    None`` -- dropped to the Garrison Commander), the ``(location,
    kingdom_id)`` of every army it will actually set ``commanded_by =
    None`` on. Mirrors ``plan_dispatch.py _dispatch_leave()``'s own
    per-army eligibility check (``owns_or_may_pass_along``) exactly, so
    this never invents a same-phase dependency for an army the real
    dispatch would skip anyway (not already commanded by the acting
    leader, not unled-and-co-located, or not that Kingdom's own) --
    see ``_pick_up_beneficiary_for_untargeted_leave()``'s own docstring
    for why this helper exists. Pure (no mutation), like every other
    helper in this ordering pass -- it runs before any real dispatch.
    """

    acting_leader = state.leaders.get(acting_leader_id)
    if acting_leader is None:
        return []
    army_ids = (
        [army.army_id for army in state.armies_commanded_by(acting_leader_id)]
        if request.all_armies
        else request.army_ids
    )
    dropped: list[tuple[HexCoord, int]] = []
    for army_id in army_ids:
        army = state.armies.get(army_id)
        if army is None or army.kingdom_id != acting_leader.kingdom_id:
            continue
        owns_or_may_pass_along = army.commanded_by == acting_leader_id or (
            army.commanded_by is None and army.location == acting_leader.location
        )
        if owns_or_may_pass_along:
            dropped.append((army.location, army.kingdom_id))
    return dropped


def _pick_up_beneficiary_for_untargeted_leave(
    request: ArmyListRequest,
    tl: TurnLeader,
    state: GameState,
    pick_up_all_armies_leaders: dict[int, tuple[HexCoord, int]],
) -> int | None:
    """RULES.AK [3]'s own "Prendere Unità Militari" case, left out of
    `_same_phase_beneficiary_leader_id()`'s own ordinary named-target
    handling by `_order_phase_entries_by_initiative()`'s own pre-
    existing docstring addendum ("needs resolving which *army*, not
    which *leader*, the dependency is keyed on"). An ordinary Leave with
    a named target already has a leader to key the wait on; one with no
    named target (dropped to the Garrison Commander) has none -- the
    dependency here is instead on whichever *other* same-phase leader
    has queued a "Pick Up all unled armies in the province" order
    (``ArmyListRequest.all_armies``, ``plan_dispatch.py _dispatch_
    pick_up()``'s own rulebook-quoted branch) and is standing exactly
    where one of this Leave's own dropped armies will land, of the
    exact same Kingdom (not merely allied -- `_dispatch_pick_up()`'s own
    per-army check is ``army.kingdom_id == acting_leader.kingdom_id``,
    not `_same_side()`'s looser ally-inclusive reading, so a same-
    Kingdom match here is what actually determines whether that Pick_Up
    would even succeed in claiming the army).

    **Deliberately single-match, not a list**: two different same-
    Kingdom Pick_Up(all_armies) leaders both standing at the same
    dropped-army location in the same phase is a real but unsourced
    corner case this project's own `ArmyListRequest`/rulebook text has
    nothing to say about how to arbitrate between -- the first match in
    ``pick_up_all_armies_leaders``' own (``base_order``-derived,
    therefore deterministic) iteration order wins, the same "no source,
    no guess, pick a deterministic tiebreak" stance `turn/patrol_
    execution.py find_patrol_target()`'s own rule (h) already takes for
    an analogous multi-candidate ambiguity.

    **Only the ``all_armies`` Pick_Up form is timing-sensitive at all**:
    a Pick_Up naming a specific army id never checks ``commanded_by`` in
    ``_dispatch_pick_up()``, so it already succeeds regardless of
    dispatch order -- no dependency needed for that form, and none is
    computed here.
    """

    dropped = _dropped_unled_army_locations(request, tl.leader.leader_id, state)
    if not dropped:
        return None
    for pick_up_leader_id, (location, kingdom_id) in pick_up_all_armies_leaders.items():
        if pick_up_leader_id == tl.leader.leader_id:
            continue
        if any(location == d_location and kingdom_id == d_kingdom_id for d_location, d_kingdom_id in dropped):
            return pick_up_leader_id
    return None


def _same_phase_beneficiary_leader_id(
    tl: TurnLeader,
    phase: PlanPhase,
    state: GameState,
    acting_leader_ids_this_phase: set[int],
    pick_up_all_armies_leaders: dict[int, tuple[HexCoord, int]],
) -> int | None:
    """RULES.AK [3]'s own "un personaggio può attendere se un altro deve
    fare qualcosa per lui" -- the leader_id of another, same-phase-
    acting leader of ``tl``'s own or an allied Kingdom that this
    entry's own order benefits, if any. See `_order_phase_entries_by_
    initiative()`'s own docstring for the full rule, scope, and the
    cases deliberately left out.

    Each decode call here is pure (no mutation, no execution) -- this
    runs *before* any real dispatch, purely to compute ordering.
    """

    target_leader_id: int | None = None
    if phase.action is ActionCode.LEAVE:
        request = decode_army_list_phase(phase)
        target_leader_id = request.target_leader_id
        if target_leader_id is None:
            # 2026-11-06: the "Prendere Unità Militari" case this
            # function's own docstring used to leave entirely out --
            # see `_pick_up_beneficiary_for_untargeted_leave()`.
            return _pick_up_beneficiary_for_untargeted_leave(request, tl, state, pick_up_all_armies_leaders)
    elif phase.action is ActionCode.RECRUIT:
        target_leader_id = decode_recruit_phase(phase).leader_id
    elif phase.action is ActionCode.TRADE:
        target_leader_id = decode_trade_phase(phase).target_leader_id
    elif phase.action is ActionCode.CAST:
        request = decode_cast_phase(phase)
        if request.spell in CHARACTER_TARGET_SPELLS:
            target_leader_id = request.target

    if target_leader_id is None or target_leader_id == tl.leader.leader_id:
        return None
    if target_leader_id not in acting_leader_ids_this_phase:
        # The target has no order of their own this phase -- idle, or
        # (e.g. Resurrection's own target) dead -- so there is nothing
        # to reorder against.
        return None
    target_leader = state.leaders.get(target_leader_id)
    if target_leader is None or not _same_side(state, tl.kingdom_id, target_leader.kingdom_id):
        return None
    return target_leader_id


def _order_phase_entries_by_initiative(
    entries: list[tuple[TurnLeader, int, PlanPhase]], state: GameState
) -> list[tuple[TurnLeader, int, PlanPhase]]:
    """RULES.AK [3] AZIONI E INIZIATIVA, quoted in full (2026-11-03;
    `turn/initiative.py`'s own module docstring already covers the
    Initiative *score* formula -- this is its first real consumer for
    *general* cross-leader sequencing, Phase 311's own narrower
    neutral-province-invasion-priority use being the only prior one):

        "Nell'elaborare le mosse, il computer esegue innanzitutto la
        prima azione di ciascun personaggio, poi la seconda di
        ciascuno e così via. Se due personaggi hanno la stessa
        Iniziativa, è quello con il numero d'ordine più basso ad avere
        la precedenza."

        "Un personaggio può attendere se un altro deve fare qualcosa
        per lui. Esempio: due personaggi sono nella stessa provincia e
        il personaggio A vuole uscirne mentre quello B dello stesso
        reame vuole, poniamo, reclutare delle unità militari per lui.
        In una situazione del genere il personaggio A aspetterà che il
        personaggio B abbia agito, anche se A ha un coefficiente
        d'iniziativa superiore. Questa regola vale non soltanto per
        Reclutare, ma anche per Abbandonare e Prendere Unità Militari,
        Lanciare Incantesimi favorevoli, Dare oggetti magici e per gli
        Incontri."

        "Il personaggio che riceve l'ordine Defend è sempre l'ultimo
        ad agire (perché deve reagire a tutti gli attacchi)."

    Confirmed absent until now (`plan_dispatch.py _dispatch_leave()`'s
    own 2026-10-29 addendum, `webapp/moves_compose.py`'s own matching
    note): `_collect_phase_entries()` used to return ``entries`` in
    bare ``turn_leaders`` order (this project's own K1-file-arrival
    order) with no Initiative-based reordering or cross-leader
    dependency mechanism at all.

    **Base order**: every entry sorts by ``-character_initiative()``
    (higher first), tie-broken by its original ``turn_leaders`` index
    -- the user's own confirmed reading of "numero d'ordine" as K1-file
    arrival order, since no other per-character ordinal exists anywhere
    in this project's own data model. A leader not found in
    ``state.leaders`` reads Initiative 0, the same permissive-missing-
    data fallback every other Initiative-adjacent consumer already uses
    (``multiple_contingents.py``'s own march_level=0, etc.). A `DEFEND`
    entry sorts after every non-`DEFEND` entry regardless of Initiative
    (the quoted "sempre l'ultimo" line), tied among themselves the same
    Initiative/arrival-order way.

    **Same-phase "waits for" override**: `_same_phase_beneficiary_
    leader_id()` detects, per entry, whether this order benefits
    another same-phase-acting leader of the same or an allied Kingdom
    -- `LEAVE`'s own named target, `RECRUIT`'s own named leader,
    `TRADE`'s own recipient (this project's only top-level "Dare"
    action -- Steal is never decoded as `ActionCode.TRADE`, only as an
    Encounter-tactic `Maneuver`, so every `TRADE` entry reaching here is
    a real Give, gold or item alike -- the quoted text's own "oggetti
    magici" example doesn't call out gold specifically, and there's no
    principled reason a received gift of gold wouldn't enable the same
    same-phase follow-on action an item would), and `CAST`'s own target
    when the spell is one of `cast_decode.CHARACTER_TARGET_SPELLS` --
    the same-or-allied-Kingdom filter alone is what separates a
    "favorevole" cast (Oratory/Clairvoyance/Illus_Armies/Mystic_Winds on
    one's own side) from a hostile one (Kill_Enemy/Charm on a real
    enemy) without needing a second, separate "which spells count as
    beneficial" table -- this project has no mechanism for a same-side
    *hostile* cast anyway. Resurrection's own target is a dead leader
    with no entry of their own this phase, so it never creates a
    dependency edge either, with no special-casing needed.

    Every detected edge becomes a "benefactor before beneficiary"
    constraint, resolved via a stable topological sort seeded by the
    base order above (Kahn's algorithm, always picking the earliest-
    base-order entry whose constraints are already satisfied) -- this
    is what makes a beneficiary wait exactly until its benefactor has
    gone, not further, and never disturbs `DEFEND`'s own "always last"
    position (a `DEFEND` entry's own action never matches any trigger
    above, so it can only ever be a beneficiary, never a benefactor,
    and the scan order keeps every non-`DEFEND` entry ahead of it
    regardless of degree). A same-phase dependency cycle (e.g. a mutual
    Give) has no source backing it and has never been seen -- rather
    than loop forever or raise, it's broken by falling back to the base
    order for whichever entries remain.

    **2026-11-06 -- `PICK_UP`'s own more complex case closed too.**
    Until now this paragraph flagged it as deliberately out of scope:
    waiting for a same-phase `LEAVE` that drops an army to *no* named
    leader, which this `PICK_UP` then separately claims, needs
    resolving which *army*, not which *leader*, the dependency is keyed
    on -- a structurally different lookup from the four named-target
    cases above. `_pick_up_beneficiary_for_untargeted_leave()` (called
    from `_same_phase_beneficiary_leader_id()`'s own `LEAVE` branch when
    its target is `None`) closes this: it resolves which armies that
    untargeted Leave actually drops (mirroring `plan_dispatch.py
    _dispatch_leave()`'s own eligibility checks) and matches their
    `(location, kingdom_id)` against every other same-phase leader who
    has queued a same-Kingdom "Pick Up all unled armies in the
    province" order -- the only Pick_Up form that's timing-sensitive at
    all (a Pick_Up naming a specific army id never checks `commanded_by`
    in `_dispatch_pick_up()`, so dispatch order never affects it). See
    that function's own docstring for the deliberate single-match
    tiebreak this still leaves for the (unsourced, real but rare) case
    of two same-spot Pick_Up(all_armies) leaders.

    "...e per gli Incontri" (Encounters) is still left out -- Challenge/
    Pursue already has its own dedicated same-phase pairing/sequencing
    machinery (mutual-encounter resolution, and [3.16]'s own separate
    "inseguitore dopo l'inseguito" rule, `_order_same_kingdom_pursuits_
    after_their_target()` right below), and no further, distinct gap
    was found there beyond what those already cover.
    """

    def _initiative_sort_key(indexed_entry: tuple[int, tuple[TurnLeader, int, PlanPhase]]) -> tuple[bool, int, int]:
        original_index, (tl, _segment_index, phase) = indexed_entry
        leader_state = state.leaders.get(tl.leader.leader_id)
        initiative = character_initiative(state, leader_state) if leader_state is not None else 0
        return (phase.action is ActionCode.DEFEND, -initiative, original_index)

    base_order = [entry for _original_index, entry in sorted(enumerate(entries), key=_initiative_sort_key)]

    acting_leader_ids_this_phase = {tl.leader.leader_id for tl, _segment_index, _phase in entries}
    position_by_leader_id = {tl.leader.leader_id: i for i, (tl, _segment_index, _phase) in enumerate(base_order)}

    # 2026-11-06: every acting leader with a Pick_Up(all_armies) order
    # this phase, by (location, kingdom_id) -- see
    # _pick_up_beneficiary_for_untargeted_leave()'s own docstring. Built
    # once, in base_order's own deterministic iteration order (that
    # function's own documented single-match tiebreak relies on this).
    pick_up_all_armies_leaders: dict[int, tuple[HexCoord, int]] = {}
    for tl, _segment_index, phase in base_order:
        if phase.action is not ActionCode.PICK_UP:
            continue
        if not decode_army_list_phase(phase).all_armies:
            continue
        pick_up_leader = state.leaders.get(tl.leader.leader_id)
        if pick_up_leader is not None:
            pick_up_all_armies_leaders[tl.leader.leader_id] = (pick_up_leader.location, pick_up_leader.kingdom_id)

    must_precede: dict[int, set[int]] = {}
    for i, (tl, _segment_index, phase) in enumerate(base_order):
        beneficiary_id = _same_phase_beneficiary_leader_id(
            tl, phase, state, acting_leader_ids_this_phase, pick_up_all_armies_leaders
        )
        if beneficiary_id is None:
            continue
        j = position_by_leader_id[beneficiary_id]
        if j != i:
            must_precede.setdefault(i, set()).add(j)

    if not must_precede:
        return base_order

    n = len(base_order)
    remaining_in_degree = [0] * n
    for successors in must_precede.values():
        for j in successors:
            remaining_in_degree[j] += 1

    placed = [False] * n
    ordered_positions: list[int] = []
    while len(ordered_positions) < n:
        picked = next((i for i in range(n) if not placed[i] and remaining_in_degree[i] == 0), None)
        if picked is None:
            picked = next(i for i in range(n) if not placed[i])
        placed[picked] = True
        ordered_positions.append(picked)
        for j in must_precede.get(picked, ()):
            remaining_in_degree[j] -= 1

    return [base_order[i] for i in ordered_positions]


def _order_same_kingdom_pursuits_after_their_target(
    entries: list[tuple[TurnLeader, int, PlanPhase]],
    eligible_indices: list[int],
    phase_start_location_by_leader_id: dict[int, HexCoord],
) -> list[int]:
    """[3.16]: "Se il personaggio ne insegue o pedina un altro che
    appartiene al proprio Reame ed entrambi partono dalla stessa
    provincia, l'inseguitore eseguirà l'azione dopo l'inseguito." --
    confirmed never cross-checked anywhere in this project before
    (2026-11-01, user-pasted rulebook text); the two existing "[3.16]
    quoted in full" docstrings in ``turn/pursue_execution.py``/``turn/
    challenge_pursue_decode.py`` both silently omit this sentence.

    Only reorders among ``eligible_indices`` (the entries reaching the
    ordinary, single-leader ``_dispatch_single`` path this phase, i.e.
    not already consumed by a multi-attacker/multi-practice group or a
    mutual Challenge/Pursue pair) -- a one-directional Pursue whose own
    target isn't dispatched here too (idle this phase, pre-empted by
    its own active chase/Patrol, or already consumed by one of those
    other group dispatches, all of which run *before* this function is
    even called) has nothing to reorder against, since that target's
    own state is already settled by the time this phase's ordinary
    dispatch loop runs anyway.

    ``phase_start_location_by_leader_id`` must be captured once, at the
    very start of the phase, before any of this phase's own dispatches
    -- "partono dalla stessa provincia" ("they start from the same
    province") is a precondition on the phase's own beginning, not a
    live value this function could safely recompute mid-loop.

    Implementation: for each one-directional Pursue entry (not already
    part of a mutual pair, which is excluded by never appearing in
    ``eligible_indices`` to begin with -- mutual pairs are consumed and
    resolved separately, before this function runs) whose caster and
    target share both ``TurnLeader.kingdom_id`` and their phase-start
    location, the pursuer is moved to immediately after its target in
    the returned order. A simple move-after, not a general topological
    sort -- the rulebook never specifies a resolution order for a
    layered chain of such pairs (A pursuing B, B pursuing C, all same
    Realm/province) beyond "each pursuer follows its own target," which
    this already guarantees one pair at a time.
    """

    order = list(eligible_indices)
    index_by_leader_id = {entries[i][0].leader.leader_id: i for i in eligible_indices}
    for index in eligible_indices:
        tl, _segment_index, phase = entries[index]
        if phase.action is not ActionCode.PURSUE:
            continue
        target_index = index_by_leader_id.get(phase.obj)
        if target_index is None or target_index == index:
            continue
        target_tl = entries[target_index][0]
        if tl.kingdom_id != target_tl.kingdom_id:
            continue
        pursuer_start = phase_start_location_by_leader_id.get(tl.leader.leader_id)
        target_start = phase_start_location_by_leader_id.get(target_tl.leader.leader_id)
        if pursuer_start is None or pursuer_start != target_start:
            continue
        if order.index(index) < order.index(target_index):
            order.remove(index)
            order.insert(order.index(target_index) + 1, index)
    return order


def _sees_nonallied_defender(
    entry: tuple[TurnLeader, int, PlanPhase], target: HexCoord, state: GameState
) -> bool:
    """Same "attacking" criterion ``execute_move`` uses: a mover with no army never
    triggers combat, regardless of what's at the target (rulebook [3.1]).

    Phase 1044 bug fix -- this used to apply only half of ``turn/
    diplomacy.py is_attackable_at()``'s own [8.1] "triangle" rule (not
    allied with the defender), never the other half (a third Kingdom's
    own Allied-owned territory shields every army present there,
    regardless of that army's own alliance with the mover). Every other
    defender-gathering call site (``turn/move_execution.py``, ``turn/
    battle_orchestrator.py``) already calls the shared primitive
    precisely so these two project-wide "who's a legitimate target
    here" checks never drift apart -- this LMOVE-grouping detector is
    now a third, consistent caller of it instead of a narrower,
    independently-reimplemented copy.
    """

    tl, _segment_index, _phase = entry
    if not state.armies_commanded_by(tl.leader.leader_id):
        return False
    target_province = state.provinces.get(target)
    # 2026-11-19 bug fix, user-confirmed -- see turn/move_execution.py's
    # own matching 2026-11-19 addendum: excludes actual recruitable
    # mercenaries (`ArmyState.is_mercenary`), not every `kingdom_id is
    # None` army (an independent Hero's own personally-led army is a
    # real defender too).
    if target_province is None:
        # Every in-bounds hex gets a real ProvinceState at worldgen time
        # (confirmed in the Batch 2b review of battle_orchestrator.py),
        # so this is not expected to be reachable -- kept as a graceful
        # fallback to the old, narrower check rather than a crash.
        return any(
            not army.is_mercenary and not state.is_allied(army.kingdom_id, tl.kingdom_id)
            for army in state.armies_at(target)
        )
    return any(
        not army.is_mercenary and is_attackable_at(state, army.kingdom_id, tl.kingdom_id, target_province)
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


def _leader_explorer_skill(state: GameState, leader_id: int, base: int) -> int:
    """The Explorer level a mover explores with: their own effective level
    (Discoveries and items included), raised never lowered by ``base``."""

    leader = state.leaders.get(leader_id)
    if leader is None:
        return base
    return max(base, effective_skill_level(state, leader, Ability.EXPLORER))


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
    # Phase 780: previously ignored the real `board_width` this function
    # already receives from `run_turn()`, always using the wrong
    # (Super-AK) constant for `resolve_move()`/`reveal_adjacent_
    # provinces()` below.
    bounds = MapBounds(board_width, state.board_height)

    parties: list[MultiAttackerParty] = []
    # Bug fix: `exploration_new_percent` (per mover) used to carry over
    # into `record_kingdom_exploration()`/`reveal_adjacent_provinces()`/
    # the `target_province.explored_percent` write below, called
    # unconditionally inside this same loop for every mover that passed
    # validation -- before this function yet knew whether it would go
    # on to actually unite them into a real multi-attacker battle. When
    # fewer than 2 parties survive validation, every surviving mover is
    # instead re-dispatched through the ordinary `_dispatch_single()` ->
    # `execute_move()` pipeline just below, which performs the exact
    # same real move resolution (including these same three calls) a
    # second time for the same province entry -- double-crediting this
    # mover's own exploration percentage, merit tally, and discovered
    # features, and re-revealing already-revealed neighbors (harmless on
    # its own, but a symptom of the same double-dispatch). Each mover's
    # own `exploration_new_percent` is now carried in `valid` instead of
    # a function-level scalar, and the three mutating calls are deferred
    # until after the `len(parties) < 2` fallback has already returned.
    valid: list[tuple[TurnLeader, int, PlanPhase, list[int], HexCoord, int | None]] = []

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
            # Phase 1041 bug fix -- this function's own separate movement
            # logic (see the Phase 737 note just below) never had the
            # single-attacker path's own movement-points gate
            # (move_execution.py execute_move(): "an army with no
            # movement points left this gameturn can't move", raised
            # *before* the move proceeds). find_transport_illegality()
            # just below is a pure terrain/transport legality check and
            # never looks at movement_points either, so an army already
            # at (or below) 0 used to be let into the battle and then
            # have `movement_points -= cost` applied unconditionally,
            # driving it further negative with no recorded error.
            if armies and any(army.movement_points < 1 for army in armies):
                raise ValueError("an army with no movement points left this gameturn can't move")
            # Phase 737: this function has its own separate movement
            # logic (never calls execute_move()), so it needs its own
            # copy of the same real transport-legality gate -- see
            # move_execution.py's own Phase 737 addendum for the full
            # sourcing/design. has_march_through_floods is derived the
            # same real-possession pattern turn/plan_dispatch.py already
            # uses for the single-leader path -- this function doesn't
            # otherwise model March Through Floods' own movement-point
            # surcharge at all, only the legality-relaxing half of it.
            mover_leader = state.leaders.get(tl.leader.leader_id)
            has_march_through_floods = (
                mover_leader is not None and AdvancedAbility.MARCH_THROUGH_FLOODS in mover_leader.advanced_abilities
            )
            transport_reason = find_transport_illegality(
                armies, army_ids, origin_province, target_province, has_march_through_floods=has_march_through_floods
            )
            if transport_reason is not None:
                raise TransportIllegalMoveError(transport_reason, origin_coord=origin, destination_coord=target)
            move_result = resolve_move(
                origin,
                target,
                bounds,
                target_terrain=target_province.effective_terrain(),
                target_explored_percent=target_province.explored_percent,
                explorer_skill=_leader_explorer_skill(state, tl.leader.leader_id, explorer_skill),
                occupied_by_enemy=True,
            )
            exploration_new_percent = move_result.exploration.new_percent
        except Exception as exc:  # noqa: BLE001 -- same broad-catch convention as run_leader_plan
            results.append(PhaseDispatchResult(tl.leader.leader_id, segment_index, phase.label, phase.action, None, exc))
            continue

        parties.append(
            MultiAttackerParty(leader_id=tl.leader.leader_id, kingdom_id=tl.kingdom_id, army_ids=army_ids, origin_province=origin)
        )
        valid.append((tl, segment_index, phase, army_ids, origin, exploration_new_percent))

    if len(parties) < 2:
        # Not enough survived validation to actually unite -- whoever's
        # left dispatches individually and normally instead, through the
        # ordinary single-mover pipeline that applies its own real
        # exploration-discovery side effects exactly once.
        for tl, segment_index, phase, _army_ids, _origin, _exploration_new_percent in valid:
            results.extend(_dispatch_single(tl, segment_index, phase, state, board_width, explorer_skill, rng))
        return results

    # Only now, having committed to a genuine united multi-attacker
    # battle, apply each surviving mover's own exploration-discovery side
    # effects -- see this function's own Bug fix note above for why this
    # can't run inside the validation loop above.
    for tl, segment_index, phase, _army_ids, _origin, exploration_new_percent in valid:
        if target_province is not None and exploration_new_percent is not None:
            # Phase 69: each mover's own kingdom gets its own tracked
            # percentage via record_kingdom_exploration() below, unlike this
            # single shared scalar (which only the last mover in this loop wins).
            target_province.explored_percent = exploration_new_percent
        record_kingdom_exploration(
            target_province,
            tl.kingdom_id,
            _leader_explorer_skill(state, tl.leader.leader_id, explorer_skill),
            partial=True,
            state=state,
            rng=rng,
            leader_id=tl.leader.leader_id,
        )
        reveal_adjacent_provinces(state, target_province, tl.kingdom_id, bounds)

    battles = fight_multi_attacker_battle(state, target, parties, apply_fanaticism=True, use_real_duel_combat=True, rng=rng)
    battle_by_leader = {leader_id: battle for battle in battles for leader_id in battle.leader_ids}

    for tl, segment_index, phase, army_ids, origin, _exploration_new_percent in valid:
        battle = battle_by_leader[tl.leader.leader_id]
        conquered = battle.report.conquered
        cost = movement_cost_for_move(battle_occurred=True, conquered=conquered)
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
