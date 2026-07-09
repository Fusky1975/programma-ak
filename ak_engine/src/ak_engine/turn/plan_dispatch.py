"""Dispatching a parsed Leader's ActionPlan phases to turn/* resolvers.

Bridges Phase 1's parsed move-file model (``models.kingdom.Kingdom`` ->
``Leader`` -> ``ActionPlan`` -> ``PlanSegment`` -> ``PlanPhase(action, obj,
extra)``) to the turn-resolution functions built in later phases -- the
integration step flagged as the single largest remaining gap after Phase
10.

Several ``ActionCode``s have recovered enough of their target semantics
to dispatch automatically:

- **LMOVE**: ``obj`` is the move's target hex number, decoded via
  ``turn/hex_numbering.py`` (an empirical inference, not a certainty --
  see that module's docstring).
- **EXPLORE**: no target decoding needed -- explores the mover's current
  province.
- **RECRUIT** actually executes (Phase 15): ``obj``/``extra`` decoded via
  ``turn/recruit_decode.py``, priced per requested type via
  ``turn/recruit.py resolve_recruit()``, then ``turn/recruit_execution.py
  execute_recruit()`` debits ``KingdomState.treasury`` (crediting an
  ally's treasury too, if recruiting in allied territory) and creates a
  new ``ArmyState`` per successfully recruited unit, enforcing the
  per-type per-turn limit via ``ProvinceState.recruited_this_turn``.
  ``is_native_to_province`` is approximated as race-compatibility
  (``turn/recruit.py is_army_type_compatible_with_race``) since
  ``GameState`` doesn't track the rulebook's more specific "1-2
  recruitable types per province" data -- a documented simplification,
  not the literal rule. See ``turn/recruit_execution.py``'s docstring for
  the cost-table verification done before writing this.
- **LEAVE** and **PICK_UP** actually mutate ``ArmyState.commanded_by``
  (Phase 14's leader-army command model, ``models.game_state.LeaderState``)
  -- Leave transfers command to the requested leader (or clears it, for
  the garrison), also transferring ``kingdom_id`` if left in an ally's
  province ("the army then belongs to the ally", rulebook [3.8]); Pick_Up
  attaches co-located armies (or, for "Pick Up All", every *unled*
  co-located army) to the acting leader.
- **DISBAND** actually executes (Phase 16): releases the targeted armies
  into mercenary status by clearing ``ArmyState.kingdom_id`` and
  ``commanded_by`` (see ``models/game_state.py``'s nullable-``kingdom_id``
  convention). Recruit, in turn, checks ``GameState.mercenaries_at()``
  before levying a fresh unit, so a disbanded army can be re-hired later
  (rulebook [3.4]).
- **HIRE** and **FIRE** actually execute (Phase 17), operating on
  independent *Heroes* (``LeaderState.kingdom_id is None``) rather than
  armies -- a different concept from Recruit's mercenary-army hiring, see
  ``turn/hire_fire_decode.py``. Hire requires the target Hero to be
  independent and co-located with the acting leader, then debits the
  gold offer from the kingdom's treasury and assigns the Hero to
  ``kingdom_id`` (rulebook [3.5]). Fire releases a Hero back to
  ``kingdom_id = None`` (rulebook [3.7]); like Disband, co-location isn't
  enforced (same King-vs-Hero authority gap, see ``_dispatch_disband``'s
  docstring). Neither models the rulebook's finer unsourced/undata-able
  details: a Hero's own "required pay" (may be less than the offer),
  recurring per-turn pay, alignment-based hire refusal, or "can't Hire a
  Hero who rules his own province" -- see ``README.md``.
- **SEARCH** is decode-only (Phase 19), same status Recruit had before
  Phase 15: ``obj``/``extra`` decode to a target feature id plus an
  Encounter Plan tactic list via ``turn/search_decode.py``, but nothing
  is applied to ``GameState`` -- Search resolves as personal combat
  against a feature's guardian monster (rulebook [3.3], [5.0]), and this
  project has no non-army Encounter resolver yet.
- **TRADE** is decode-only (Phase 20) and, unlike every other decoded
  action here, the decode itself stays deliberately raw --
  ``turn/trade_decode.py`` exposes ``obj``/``extra`` uninterpreted rather
  than naming fields it can't confirm. ``ActionCode.TRADE`` is the
  Pascal engine's internal name for the rulebook's Give order ([3.18],
  [5.7]); see that module's docstring for why its field mapping is this
  project's least-confirmed (no real Trade phases in any sample file, no
  turn-execution engine present in the available Pascal source, and the
  rulebook itself flags an unresolved item-id/gold-amount ambiguity in
  ``obj``).
- **PRACTICE** is decode-only (Phase 21): ``obj`` decodes directly to an
  ``Ability`` via ``turn/practice_decode.py``, but nothing is applied to
  ``GameState`` -- resolving what practicing an ability actually does
  (rulebook [3.13]) needs a per-leader skill/aptitude table this project
  doesn't have yet (the move file only exposes the *King's* pairs, not
  each Hero's), a province-level view of every co-located character's
  same-phase action (the core mechanic is multi-character, not
  resolvable from one leader's plan alone), and a dice-roll procedure
  not present in the available Pascal source.
- **WAIT**, **NO_ACTION**, and **MOVE_ABORT** dispatch as bare no-ops
  (Phase 22): no ``turn/*_decode.py`` module exists for any of the
  three, and none is needed -- an exhaustive grep of every
  ``lactions[...]`` read/write site in the available Pascal source (all
  14 ``.PAS`` files) confirms none of the three has a ``CASE`` branch in
  ``DEF2.PAS``'s ``R_HPlan``/``W_HPlan``, so there's no extra payload to
  decode, and none has a single real example in the 10 sample
  ``AK3__T*.K1`` files to validate against even if there were. None is a
  documented rulebook order either (zero mentions anywhere in
  ``RULES.AK``/``AKMAN.TXT``/``ADDEND.AK``/``INFO.AK``). Wait and
  No_Action are, however, confirmed **engine-internal** values: the
  Pascal source auto-fills a missed-deadline king's leaders with Defend
  (phase 0) then Wait (phases 1-4) (``REPORTS.PAS Set_Defend``), and
  initializes/pads every unused phase slot outside a plan's
  ``planstart..planend`` range to No_Action (``DEF2.PAS Clear_M``) --
  neither looks like a routine player-typed order. Move_Abort is the
  most speculative of the three: declared in the ``action`` enum purely
  for abbreviation-table symmetry (``'MA'``), but never assigned to or
  compared against anywhere else in the entire available source tree --
  effectively vestigial as far as this project's source access goes.
- **CAST** decodes every spell (``turn/cast_decode.py``, Phase 23) but
  only *executes* two of the 12 real spells observed in sample data
  (``turn/cast_execution.py``, Phase 29): **Charm** assigns a co-located
  target character to the caster's kingdom (the same
  ``LeaderState.kingdom_id`` mechanism Hire uses, but without Hire's
  "must already be independent" requirement -- Charm plausibly steals
  allegiance from *any* co-located character, a documented
  interpretation); **Kill_Enemy** removes a co-located target character
  from ``GameState`` entirely. Every other spell (Resurrection, Bless,
  Plague, Flood, Tornado, Illus_Armies, Oratory, Part_Sea,
  Illus_Terrain, Skeletal_Army) stays unexecuted, each for its own
  documented reason -- see ``turn/cast_execution.py``'s docstring, most
  notably Resurrection, which can't be executed even conceptually since
  ``GameState`` has no "dead leader" registry to revive from. The
  success/failure roll itself (rulebook [3.10]) also isn't modeled --
  needs per-leader ability data ``GameState`` doesn't have yet (same gap
  Practice hit); a valid Charm/Kill_Enemy attempt always succeeds for
  now. Not to be confused with ``Maneuver.CAST``, the *encounter-plan*
  tactic already decoded by ``turn/search_decode.py`` -- a different
  Pascal reading path entirely, with no top-level ``ActionCode`` of its
  own.
- **USE_MI** is decode-only (Phase 24): ``obj`` decodes to a global
  item-*instance* id via ``turn/use_mi_decode.py`` -- structurally
  different from Cast's ``obj``, which is a self-describing ``Spell``
  ordinal. Use_MI's ``obj`` can't be resolved to "what item this is"
  from the move file alone: it's a lookup key into a per-game item
  registry (which type each instance is, who holds it, its remaining
  charges) that this project has no way to reconstruct, since the
  Pascal source describing how item instances come into existence
  (loot/world generation) isn't in the available source tree. Zero real
  Use_MI phases exist in any of the 10 sample files either -- see that
  module's docstring for the full reasoning.
- **CHALLENGE** and **PURSUE** are decode-only (Phase 25):
  ``turn/challenge_pursue_decode.py`` decodes both from the exact same
  wire format as Search (``DEF2.PAS``'s shared ``Search,Challenge,
  Pursue: W_List(...,Tac_Bytes)`` branch), except ``obj`` is a target
  *character* id rather than a feature id. ``ActionCode.CHALLENGE`` is
  the Pascal engine's internal name for the rulebook's **Encounter
  Character (EN)** order ([3.12]) -- same kind of naming mismatch as
  Trade/Give. ``ActionCode.PURSUE`` ([3.16]) is a player-issued "chase
  this character across the map" order, entirely unrelated to
  ``turn/pursuit.py``'s separate automatic post-battle retreat-chasing
  mechanic ([7.3]) -- confirmed no overlap. Zero real phases exist for
  either action in the 10 sample files.
- **ASPY** and **DEFEND** are decode-only (Phase 26):
  ``turn/aspy_defend_decode.py`` decodes both to a raw ``target_province``
  int -- bare triples in ``DEF2.PAS`` (no dedicated ``CASE`` branch), but
  ``obj`` is confirmed to be a real, engine-consulted province reference
  rather than dead data (``RUMORS.PAS``'s ``Set_Intel`` reads it for
  ASpy; ``REPORTS.PAS``'s ``Set_Defend`` missed-deadline auto-fill
  writes it for Defend). ``ActionCode.ASPY`` is rulebook [3.14] Spy
  Province; ``ActionCode.DEFEND`` is [3.15] Defend -- neither has a
  Trade/Challenge-style naming mismatch. Zero real phases exist for
  either action in the 10 sample files.
- **TRAIL** is decode-only (Phase 27): ``turn/trail_decode.py`` decodes
  ``obj`` as a target character id, matching Pursue/Challenge's target
  shape but confirmed -- by the Italian rulebook explicitly ("il primo
  non genera un Piano d'Incontro, il secondo invece sì") and by
  ``DEF2.PAS`` structurally -- to carry **no** Encounter Plan tactic
  list, unlike Pursue/Challenge/Search. Rulebook [3.17]. Zero real
  phases exist in the 10 sample files.

**``ActionCode.SUCC_TRAIL`` is deliberately excluded from
``SUPPORTED_ACTIONS`` -- not a gap, a considered exclusion.** Unlike
every other action ever left unsupported in this project, the evidence
here points to it being **structurally impossible to receive** in a
player move-submission file, not merely undecoded:

- No rulebook section describes it as a player order (no ``[3.x]``
  entry, no ``AKMOVES.TXT`` example, no player-facing 2-letter mnemonic
  beyond the internal ``actab`` table).
- ``HostAK/TP/DEF2.PAS``'s ``W_HPlan`` (the move-file *writer*) has no
  path that ever emits ``Succ_Trail`` -- confirmed by reading its full
  ``CASE lactions[m] OF`` dispatch, which has no arm for it at all.
- An exhaustive search of every ``lactions[...] :=`` assignment in the
  entire available Pascal source (all 14 ``.PAS`` files) found exactly
  two ``Succ_Trail`` references total: the enum declaration itself
  (``CTBOTH.PAS``) and a single **read** site, ``RUMORS.PAS``'s
  ``Set_Intel`` (``IF lactions[_rphase] = Succ_Trail THEN ... Add_Spy(1)``).
  No assignment site exists anywhere in the source that would ever set
  a phase's action to ``Succ_Trail``.
- That read site consumes the moderator's own **post-turn-simulation
  in-memory plan state** (after a Trail phase has already been resolved
  by the engine, presumably rewriting that phase's action in memory from
  ``Trail`` to ``Succ_Trail`` as a resolution marker) -- not anything
  parsed from a player-submitted move file. The code that would perform
  that in-memory rewrite isn't present in the available source at all
  (this project's Pascal archive has no main turn-simulation unit,
  only the library/plan-I-O/report-generation layers -- the actual
  turn engine exists only as the compiled ``AK.EXE``/``AK.OVR``).
- Zero real occurrences in the 10 sample ``AK3__T*.K1`` files, consistent
  with all of the above.

Given this, decoding it would mean inventing a shape for a value this
project can neither observe in real data nor verify against any source
logic -- worse than every other high-uncertainty module already built
here (Trade, Use_MI), which at least decode a *real wire triple* a
player genuinely could have written. Raising ``UnsupportedActionError``
for it is the honest choice, and doubles as a loud signal if it were
ever to appear in real input (e.g. a corrupted or hand-edited file) --
exactly the situation where a clear failure beats a guessed-at decode.
This closes out ``ActionCode`` coverage at its practical maximum: 21 of
22, with the 22nd excluded by design rather than left as an open gap.

Every dispatch call takes an explicit ``leader_id`` -- the acting
character -- and ``army_ids`` defaults to whatever that leader currently
commands (``GameState.armies_commanded_by``) unless the caller overrides
it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.leader import Leader
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.army_list_decode import ArmyListRequest, decode_army_list_phase
from ak_engine.turn.aspy_defend_decode import decode_aspy_phase, decode_defend_phase
from ak_engine.turn.cast_decode import decode_cast_phase
from ak_engine.turn.cast_execution import CastExecutionResult, execute_cast
from ak_engine.turn.challenge_pursue_decode import decode_challenge_phase, decode_pursue_phase
from ak_engine.turn.exploration import resolve_explore
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest, decode_fire_phase, decode_hire_phase
from ak_engine.turn.move_execution import execute_move
from ak_engine.turn.practice_decode import decode_practice_phase
from ak_engine.turn.recruit_decode import decode_recruit_phase
from ak_engine.turn.recruit_execution import RecruitExecutionResult, execute_recruit
from ak_engine.turn.search_decode import decode_search_phase
from ak_engine.turn.trade_decode import decode_trade_phase
from ak_engine.turn.trail_decode import decode_trail_phase
from ak_engine.turn.use_mi_decode import decode_use_mi_phase

SUPPORTED_ACTIONS = frozenset(
    {
        ActionCode.LMOVE,
        ActionCode.EXPLORE,
        ActionCode.SEARCH,
        ActionCode.CAST,
        ActionCode.USE_MI,
        ActionCode.CHALLENGE,
        ActionCode.PURSUE,
        ActionCode.ASPY,
        ActionCode.DEFEND,
        ActionCode.TRAIL,
        ActionCode.RECRUIT,
        ActionCode.DISBAND,
        ActionCode.LEAVE,
        ActionCode.PICK_UP,
        ActionCode.HIRE,
        ActionCode.TRADE,
        ActionCode.FIRE,
        ActionCode.PRACTICE,
        ActionCode.WAIT,
        ActionCode.NO_ACTION,
        ActionCode.MOVE_ABORT,
    }
)


class UnsupportedActionError(NotImplementedError):
    """Raised for a PlanPhase whose action has no turn/* resolver wired up yet."""


@dataclass(slots=True)
class NoOpResult:
    """The result of dispatching a Wait/No_Action/Move_Abort phase -- see module docstring."""

    action: ActionCode


@dataclass(slots=True)
class HireExecutionResult:
    request: HireRequest
    hired: bool
    reason: str | None = None  # set when hired is False


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

    if action is ActionCode.SEARCH:
        return decode_search_phase(phase)

    if action is ActionCode.RECRUIT:
        return _dispatch_recruit(phase, state, kingdom_id, leader_id)

    if action is ActionCode.LEAVE:
        return _dispatch_leave(phase, state, leader_id)

    if action is ActionCode.PICK_UP:
        return _dispatch_pick_up(phase, state, leader_id)

    if action is ActionCode.DISBAND:
        return _dispatch_disband(phase, state, leader_id)

    if action is ActionCode.HIRE:
        return _dispatch_hire(phase, state, kingdom_id, leader_id)

    if action is ActionCode.FIRE:
        return _dispatch_fire(phase, state)

    if action is ActionCode.TRADE:
        return decode_trade_phase(phase)

    if action is ActionCode.PRACTICE:
        return decode_practice_phase(phase)

    if action in (ActionCode.WAIT, ActionCode.NO_ACTION, ActionCode.MOVE_ABORT):
        return NoOpResult(action=action)

    if action is ActionCode.CAST:
        return _dispatch_cast(phase, state, kingdom_id, leader_id)

    if action is ActionCode.USE_MI:
        return decode_use_mi_phase(phase)

    if action is ActionCode.CHALLENGE:
        return decode_challenge_phase(phase)

    if action is ActionCode.PURSUE:
        return decode_pursue_phase(phase)

    if action is ActionCode.ASPY:
        return decode_aspy_phase(phase)

    if action is ActionCode.DEFEND:
        return decode_defend_phase(phase)

    if action is ActionCode.TRAIL:
        return decode_trail_phase(phase)

    raise AssertionError("unreachable: action was checked against SUPPORTED_ACTIONS above")


def _dispatch_recruit(phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int) -> RecruitExecutionResult:
    request = decode_recruit_phase(phase)
    return execute_recruit(state, kingdom_id, leader_id, request)


def _dispatch_cast(phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int) -> CastExecutionResult:
    request = decode_cast_phase(phase)
    return execute_cast(state, kingdom_id, leader_id, request)


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


def _dispatch_disband(phase: PlanPhase, state: GameState, leader_id: int) -> ArmyListRequest:
    request = decode_army_list_phase(phase)
    target_ids = (
        [army.army_id for army in state.armies_commanded_by(leader_id)] if request.all_armies else request.army_ids
    )

    for army_id in target_ids:
        army = state.armies.get(army_id)
        if army is None:
            continue
        # "Releases the army(s) into mercenary status" (rulebook [3.6]) --
        # ownerless and unled, available to be hired later. Unlike Pick_Up,
        # co-location with the acting leader is NOT enforced here: the
        # rulebook grants Kings a broader disband authority than Heroes
        # (who need to be with the army), and LeaderState doesn't yet track
        # which is which -- a documented simplification, not a guess at
        # which restriction applies.
        army.kingdom_id = None
        army.commanded_by = None

    return request


def _dispatch_hire(phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int) -> HireExecutionResult:
    request = decode_hire_phase(phase)
    hero = state.leaders.get(request.hero_id)
    acting_leader = state.leaders[leader_id]

    if hero is None:
        return HireExecutionResult(request, hired=False, reason="hero not found")
    if hero.kingdom_id is not None:
        return HireExecutionResult(request, hired=False, reason="hero already in service")
    if hero.location != acting_leader.location:
        # rulebook [3.5]: "Any character can attempt to Hire a Hero in the
        # same province."
        return HireExecutionResult(request, hired=False, reason="not co-located")

    kingdom = state.kingdoms[kingdom_id]
    if kingdom.treasury < request.gold_offer:
        return HireExecutionResult(request, hired=False, reason="insufficient treasury")

    # Simplification: the rulebook's Hero "pay required" (which may be
    # lower than the offer, and unrelated to ability -- see module
    # docstring) isn't modeled, so the full offer is always charged and
    # the Hero always accepts if co-located and affordable.
    kingdom.treasury -= request.gold_offer
    hero.kingdom_id = kingdom_id

    return HireExecutionResult(request, hired=True)


def _dispatch_fire(phase: PlanPhase, state: GameState) -> FireRequest:
    request = decode_fire_phase(phase)
    hero = state.leaders.get(request.hero_id)
    if hero is not None:
        # "Releases the Hero into private life... will wander around
        # until hired by another King." (rulebook [3.7]) Co-location is
        # NOT enforced here, same simplification as Disband (see
        # `_dispatch_disband`'s docstring): a King may Fire "at any
        # time", and a Hero "can always fire himself", but `LeaderState`
        # doesn't track King-vs-Hero status to distinguish the cases.
        hero.kingdom_id = None
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
