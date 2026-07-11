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
any kingdoms. ``Ability.TACTICAL``/an undecoded raw ability value groups
the same as any other ability (so ``execute_practice_group`` still sees
the collision), but resolves to ``not_implemented_for_ability=True`` for
the whole group, same as the solo path already does for those cases.

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
this same phase either. Only this cancellation trigger is modeled; the
rulebook's other one ("cancelled if he loses a battle") stays a
distinct, still-open gap -- see ``_apply_defend_cancellations``'s own
docstring for why.

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
from ak_engine.turn.challenge_execution import execute_challenge
from ak_engine.turn.challenge_pursue_decode import decode_challenge_phase, decode_pursue_phase
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.defend_execution import defend_coverage_area
from ak_engine.turn.contested_province import (
    attacker_can_force_rebattle,
    contested_battle_movement_cost,
    is_illegal_move_from_contested,
)
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, resolve_move
from ak_engine.turn.plan_dispatch import PhaseDispatchResult, run_leader_plan
from ak_engine.turn.practice_decode import decode_practice_phase
from ak_engine.turn.practice_execution import execute_practice_group
from ak_engine.turn.pursue_execution import execute_pursue

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
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    active_defends: dict[int, set[HexCoord]] = {}  # defender leader_id -> coverage area

    for phase_index, label in enumerate(PHASE_LABELS):
        if phase_index > 0:
            results.extend(_dispatch_contested_rebattles(state, rng))

        entries = _collect_phase_entries(turn_leaders, label)

        move_targets: dict[int, HexCoord] = {}
        for index, (_tl, _segment_index, phase) in enumerate(entries):
            if phase.action is ActionCode.LMOVE:
                try:
                    move_targets[index] = decode_hex_number(phase.obj, board_width)
                except ValueError:
                    pass  # left for the ordinary per-leader path to raise/record consistently

        _apply_defend_cancellations(active_defends, entries)
        _apply_defend_reinforcements(active_defends, move_targets, entries, state)

        for index, (tl, _segment_index, phase) in enumerate(entries):
            if phase.action is ActionCode.DEFEND:
                leader_state = state.leaders.get(tl.leader.leader_id)
                if leader_state is not None:
                    # Registered for *next* phase's reinforcement check, not this
                    # one -- see turn/defend_execution.py's own docstring and
                    # _apply_defend_reinforcements's for why.
                    active_defends[tl.leader.leader_id] = defend_coverage_area(leader_state.location, bounds)

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
            results.extend(_dispatch_multi_attacker_lmove(movers, target, state, board_width, explorer_skill, rng))

        for ability, indices in multi_practice_groups:
            movers = [entries[i] for i in indices]
            results.extend(_dispatch_multi_practice(movers, ability, state, rng))

        for index_a, index_b in mutual_encounter_pairs:
            results.extend(_dispatch_mutual_encounter(entries[index_a], entries[index_b], state, rng))

        for index, (tl, segment_index, phase) in enumerate(entries):
            if index in consumed:
                continue
            results.extend(_dispatch_single(tl, segment_index, phase, state, board_width, explorer_skill, rng))

    return results


_DEFEND_CANCELLING_ACTIONS = frozenset({ActionCode.LMOVE, ActionCode.PURSUE, ActionCode.TRAIL})


def _apply_defend_cancellations(
    active_defends: dict[int, set[HexCoord]], entries: list[tuple[TurnLeader, int, PlanPhase]]
) -> None:
    """Rulebook [3.15] (quoted in full, ``RULES.AK`` ~line 573-576): "A general with
    Defend orders may use the rest of his actions to practice, explore,
    etc. If he receives a Move, Pursue or Trail order, the Defend order
    is cancelled." Removes a leader from ``active_defends`` the moment
    their own plan reaches an LMOVE/PURSUE/TRAIL phase, *before* this
    same phase's own ``_apply_defend_reinforcements`` check runs -- a
    general who's off moving/pursuing/trailing this phase is no longer
    standing by to react to an invasion this phase either.

    **Only this cancellation trigger is modeled here.** The rulebook's
    other cancellation condition, "a character's Defend order is
    cancelled if he loses a battle, to prevent further needless
    defeats," is a distinct, still-open gap -- it needs this leader's
    own battle outcome *this same phase*, which isn't available yet at
    this point in ``run_turn()`` (battles dispatch later in the phase,
    across several different code paths: solo, Multiple Contingents,
    contested-province rebattles, and Pursue's own army-vs-army catch-up
    each produce their own result shape) -- left unattempted rather than
    guessed at.
    """

    for tl, _segment_index, phase in entries:
        if phase.action in _DEFEND_CANCELLING_ACTIONS:
            active_defends.pop(tl.leader.leader_id, None)


def _apply_defend_reinforcements(
    active_defends: dict[int, set[HexCoord]],
    move_targets: dict[int, HexCoord],
    entries: list[tuple[TurnLeader, int, PlanPhase]],
    state: GameState,
) -> None:
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
    """

    if not active_defends:
        return

    invaded_provinces: dict[HexCoord, list[int]] = {}
    for index, target in move_targets.items():
        invaded_provinces.setdefault(target, []).append(index)

    for defender_leader_id, coverage in list(active_defends.items()):
        defender_state = state.leaders.get(defender_leader_id)
        if defender_state is None or defender_state.kingdom_id is None:
            continue

        for target, indices in invaded_provinces.items():
            if target not in coverage:
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
            defender_state.location = target
            del active_defends[defender_leader_id]
            break


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
    resolver actually runs; the other leader's own tactics/Encounter Plan
    are not modeled separately -- both ``PhaseDispatchResult`` entries
    share the exact same result object, one per leader so each leader's own
    dispatch record still reflects that *their* order was the one that
    produced this outcome.
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
        report = fight_battle(state, attacker_kingdom_id, coord, army_ids, rng=rng)

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
