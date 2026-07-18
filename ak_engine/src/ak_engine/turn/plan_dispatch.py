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
  (rulebook [3.4]). **King-vs-Hero co-location is enforced as of Phase
  40** (rulebook [3.6]: "A King may Disband any army at any time. A
  character can Disband an army only if he is in the same province.") --
  ``LeaderState.is_king`` bypasses the check; a Hero must be co-located
  with each target army or it's silently skipped (left undisbanded),
  same convention as an unknown army id.
- **HIRE** and **FIRE** actually execute (Phase 17), operating on
  independent *Heroes* (``LeaderState.kingdom_id is None``) rather than
  armies -- a different concept from Recruit's mercenary-army hiring, see
  ``turn/hire_fire_decode.py``. Hire requires the target Hero to be
  independent and co-located with the acting leader, then debits the
  gold offer from the kingdom's treasury and assigns the Hero to
  ``kingdom_id`` (rulebook [3.5]); **also rejects a target with
  ``is_king=True``, "You can't Hire a Hero who rules his own province"
  (Phase 40)**. Fire releases a Hero back to ``kingdom_id = None``
  (rulebook [3.7]); **King-vs-Hero co-location is enforced as of Phase
  40**, same pattern as Disband (a King bypasses it; a Hero must be
  co-located with the target -- which also naturally covers "firing
  himself," since he's always in his own province). **Phase 161
  confirmed the rulebook's own "required pay" mechanic genuinely
  absent from the surviving Pascal source, not merely unsearched**:
  `LCost` (the one Pascal identifier tied to a Hero's per-turn/required
  pay, cited at four separate sites in `REPORTS.PAS` -- the FINANCES
  section total, the CHARACTERS section's own "who, we hear, desires to
  enter thy Majesty's service for # gold per annum" mercenary-mention
  line, and the per-leader ARMIES listing) is called but never
  *defined* anywhere in the 13 available `.PAS` files -- the same
  missing-main-program category already confirmed for
  `ACost`/`Tax_Base`/`Inv_Bonus` (Phase 158's own README note). No
  separate `Hire`-specific procedure survives either; only `_LHire`'s
  own narrative dispatch code (`SAY.PAS` -> `acchire.x`, already
  modeled as `render_hire_accepted()`, Phase 114) exists in the
  archive. **Phase 162 supplies a formula anyway**, not transcribed
  from Pascal source (none survives) but designed from the player's
  manual text the user quoted directly plus one real, hard data point
  ("a Good King generally cannot hire a Pagan Hero") -- see
  ``turn/hire_pay.py``'s own docstring for the full derivation.
  ``_dispatch_hire`` now looks up the kingdom's own King
  (``LeaderState.is_king``), computes ``required_pay(hero, king)``, and
  charges *that* amount (not the raw offer) -- refusing outright when
  the alignment gap is too wide (``pay >= 5``, unreachable via any
  legal <=4-gold offer) or when the offer is below the computed pay
  (a genuine, narratable price counter-offer). Recurring per-turn pay
  (only the one-time hiring charge is modeled, matching Recruit's own
  established simplification) remains unmodeled -- no sourced formula
  for it exists either. See ``README.md`` for the full research trail.
  **Phase 143**: ``_dispatch_fire`` returns a real
  ``FireExecutionResult`` (``fired``/``reason``) instead of a bare
  ``FireRequest`` -- the caller previously had no signal at all for
  whether the Fire actually happened; see ``report/turn_report.py
  describe_hire()``/``describe_fire()`` for the new consumers this
  unblocks. **A successful
  Hire also dispatches the hired Hero's own embedded plan the same turn**
  (Phase 32, ``run_leader_plan``'s nested-plan handling -- see below).
- **SEARCH** actually executes (decoded Phase 19, executed Phase 132):
  ``turn/search_decode.py`` decodes ``obj``/``extra`` to a target feature
  id plus an Encounter Plan tactic list; ``turn/search_execution.py
  execute_search()`` (Phase 132, once ``turn/encounter.py``'s personal-
  combat core existed to resolve it against) validates co-location and
  runs a real Melee duel against the feature's guardian monster (rulebook
  [3.3], [5.0]) *when* the guardian's combat stats are sourced
  (``models/monster.py MONSTER_STATS`` only covers 6 of 61 real species)
  *and* the decoded Encounter Plan actually contains a Melee tactic
  (empirically the dominant real case -- see that module's own
  docstring); otherwise it honestly reports ``combat_resolved=False``
  with a reason rather than guessing. A win sets the feature's own
  ``looted`` flag; a loss kills the searching leader (personal combat's
  generic [5.0] rule, no Duel-style carve-out).
- **TRADE now actually executes (Phase 133)**: ``ActionCode.TRADE`` is
  the Pascal engine's internal name for the rulebook's Give order
  ([3.18], [5.7]). Phase 132 had left this decode-only because two
  fields were unconfirmed -- ``obj``'s item-id/gold-amount ambiguity,
  and (the harder gap) no recipient field decoded at all. **Both are
  now resolved**, from real domain knowledge the user supplied directly
  (2026-07-13) plus an independent structural cross-check against
  ``HostAK/TP/DEF2.PAS`` -- see ``turn/trade_decode.py``'s own
  docstring for the full quoted source and citations. ``obj`` is
  disambiguated by checking whether the giver actually possesses an
  item with that id (item takes priority if so); the recipient is
  ``TradeRequest.target_leader_id`` (``extra[1]``/``n1``), required to
  be co-located. ``turn/trade_execution.py execute_give()`` (Phase 133)
  enforces co-location, that both giver *and* recipient are Kings for
  the gold path (rulebook: "give... to *other Kings*"), and [3.18]'s
  10% treasury cap. **Phase 140 closes the item path too**: ``obj`` is
  now checked against the real ``GameState.items`` ownership registry
  (``models/item.py ItemInstance``, sourced from ``RUMORS.PAS``'s
  ``Add_Tr``/``treaslist``/``trowner``/``trcharges``) and, when the
  giver genuinely owns it, transferred via ``GameState.transfer_item()``
  with no King/kingdom requirement on either side -- see that module's
  own docstring for the full mechanic.
- **PRACTICE** actually executes (Phase 44): ``obj`` decodes to an
  ``Ability`` via ``turn/practice_decode.py``, then
  ``turn/practice_execution.py execute_practice()`` rolls the rulebook
  [3.13] skill/aptitude-rise mechanic and mutates the acting leader's
  ``LeaderState.skills`` (creating a fresh all-zero ``SkillTable`` first
  if none was recorded -- the common case for Heroes). **Always resolved
  as if practicing alone** (5%, the smallest of the rulebook's three base
  chances) -- true multi-character coordination ("2+ co-located
  characters practicing the same ability in the same phase") would need
  visibility into every other leader's same-phase order, which this
  per-leader dispatch doesn't have (same structural gap as Multiple
  Contingents not being auto-invoked here); see
  ``turn/practice_execution.py``'s module docstring for the full
  citation and the documented, never-overstating direction of this
  approximation. ``Ability.TACTICAL`` is recognized but deliberately not
  resolved (it trains armies, not personal skill, an unbuilt separate
  mechanic); Sage's own skill rise runs normally here, but its
  rulebook-additional "device discovery" side roll isn't modeled (no
  item/device data model exists at all).
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
  (phase 0) then Wait (phases 1-4) (``REPORTS.PAS Set_Defend``) --
  **Phase 134 correction**: only if the leader actually commands an
  army (``AA_Led(l2) > 0``); an armyless leader gets Wait in every
  phase, phase 0 included. See ``turn/missed_deadline.py
  build_missed_deadline_plan()``, which now implements this for real.
  Initializes/pads every unused phase slot outside a plan's
  ``planstart..planend`` range to No_Action (``DEF2.PAS Clear_M``) --
  neither looks like a routine player-typed order. Move_Abort is the
  most speculative of the three: declared in the ``action`` enum purely
  for abbreviation-table symmetry (``'MA'``), but never assigned to or
  compared against anywhere else in the entire available source tree --
  effectively vestigial as far as this project's source access goes.
- **CAST** decodes every spell (``turn/cast_decode.py``, Phase 23) and
  now *executes* 13 of the 25 base spells (``turn/cast_execution.py``,
  Phases 29, 59, and 60): **Charm**/**Kill_Enemy** (Phase 29, unchanged)
  plus **Resurrect, Part_Sea, Bless, Flood, Tornado, Earthquake, Oratory,
  Plague, Illus_Terrain, Illus_Armies** (Phase 59, once Regolamento
  AK.txt supplied the exact numbers/targeting rules ``RULES.AK``/
  ``ADDEND.AK`` never gave) plus **Skeletal_Army** and Bless's own
  addendum (Phase 60, once ``GameState.battle_graveyard`` gave both
  something to read/clear). Province-targeted spells decode their raw
  hex-number target via ``turn/hex_numbering.py`` using this dispatcher's
  own ``board_width`` -- the same value Move's own LMOVE decoding
  already uses. **Hide_Feature, Clairvoyance**, and all 10
  Personal-Combat-only spells stay unexecuted, each for its own
  documented reason -- see ``turn/cast_execution.py``'s docstring. The
  success/failure roll itself (rulebook [3.10]) is real when the caster
  has ``LeaderState.skills`` recorded, falling back to always-succeeds
  otherwise (Phase 30). Not to be confused with ``Maneuver.CAST``, the
  *encounter-plan* tactic already decoded by ``turn/search_decode.py`` --
  a different Pascal reading path entirely, with no top-level
  ``ActionCode`` of its own. **A successful Charm or Resurrection also
  dispatches the (re-)joined character's own embedded plan the same
  turn** (Phase 32, see below) -- Resurrection's own embedded plans (real
  samples have some) now dispatch too whenever the revival actually
  succeeds, no longer unconditionally suppressed.
- **USE_MI now actually executes (decoded Phase 24, executed Phase
  141)**: ``obj`` decodes to a global item-*instance* id via ``turn/
  use_mi_decode.py`` -- structurally different from Cast's ``obj``,
  which is a self-describing ``Spell`` ordinal. Phase 140's
  ``GameState.items`` registry (``models/item.py ItemInstance``) closed
  the "can't reconstruct which item this is" gap this paragraph used to
  describe; ``turn/use_mi_execution.py execute_use_mi()`` resolves the
  id against that registry, requires the acting leader to actually own
  it, and dispatches the 20 spell-wand ordinals into ``turn/
  cast_execution.py execute_cast()`` (automatically successful, cast
  "at skill-2" per rulebook [3.11] and ``TREASAB.X2``'s own wand
  labels) or the 15 skill-book ordinals into a direct, self-consuming
  ``LeaderState.skills`` +1 -- see that module's own docstring for the
  full mechanic. Zero real Use_MI phases exist in any of the 10 sample
  files, so this stays unvalidated against real data (same situation as
  Fire and Trade before their own executors landed).
- **CHALLENGE** and **PURSUE** actually execute (decoded Phase 25,
  executed Phase 54): ``turn/challenge_pursue_decode.py`` decodes both
  from the exact same wire format as Search (``DEF2.PAS``'s shared
  ``Search,Challenge,Pursue: W_List(...,Tac_Bytes)`` branch), except
  ``obj`` is a target *character* id rather than a feature id.
  ``ActionCode.CHALLENGE`` is the Pascal engine's internal name for the
  rulebook's **Encounter Character (EN)** order ([3.12]) -- same kind
  of naming mismatch as Trade/Give; ``turn/challenge_execution.py``
  (Phase 50) resolves the King/Hero acceptance decision tree and a real
  Melee duel. ``ActionCode.PURSUE`` ([3.16]) is a player-issued "chase
  this character across the map" order, entirely unrelated to ``turn/
  pursuit.py``'s separate automatic post-battle retreat-chasing
  mechanic ([7.3]) -- confirmed no overlap; ``turn/pursue_execution.py``
  (Phases 51/53) resolves one phase's Spy Table catch-up roll and
  either a real army battle or an armyless Encounter, reusing Challenge's
  own combat core. **``mutual_encounter`` (a King target's own
  acceptance requirement) defaults to ``False`` at this single-leader
  dispatch layer** -- detecting a real mutual Challenge/Pursue pair
  (both leaders targeting each other the same phase) needs the same
  cross-leader, same-phase visibility Multiple Contingents and
  Practice's own multi-character coordination needed
  (``turn/turn_processor.py``, Phases 45/46); wiring that detection in
  here is a declared, natural follow-up, not attempted this phase. Zero
  real phases exist for either action in the 10 sample files.
- **ASPY** now executes (decoded Phase 26, executed Phase 62):
  ``turn/aspy_defend_decode.py`` decodes it to a raw ``target_province``
  int -- a bare triple in ``DEF2.PAS`` (no dedicated ``CASE`` branch), but
  ``obj`` is confirmed to be a real, engine-consulted province reference
  rather than dead data (``RUMORS.PAS``'s ``Set_Intel`` reads it).
  ``turn/aspy_execution.py execute_aspy()`` builds the rulebook [3.14]
  intelligence report (owner, adjacent owners, recruitable army types,
  capital status) for the caster's *own* current province -- "a
  character may only Spy on a province he is actually in" is read
  literally, so the raw ``target_province`` int is decoded but
  deliberately never trusted or cross-checked (see that module's own
  docstring for why: no confirmed numbering scheme for it exists).
  **DEFEND** is decode-only still (Phase 26); its own reactive
  battle-joining is separately wired into ``turn/turn_processor.py``
  (Phase 57), not here. ``ActionCode.ASPY`` is rulebook [3.14] Spy
  Province; ``ActionCode.DEFEND`` is [3.15] Defend -- neither has a
  Trade/Challenge-style naming mismatch. Zero real phases exist for
  either action in the 10 sample files.
- **TRAIL** actually executes (decoded Phase 27, executed Phase 54):
  ``turn/trail_decode.py`` decodes ``obj`` as a target character id,
  matching Pursue/Challenge's target shape but confirmed -- by the
  Italian rulebook explicitly ("il primo non genera un Piano
  d'Incontro, il secondo invece sì") and by ``DEF2.PAS`` structurally --
  to carry **no** Encounter Plan tactic list, unlike Pursue/Challenge/
  Search. Rulebook [3.17]; ``turn/trail_execution.py`` (Phase 52)
  resolves one phase's Spy Table catch-up roll and reports only
  ``spied_on: bool`` (no intelligence payload -- see that module's own
  docstring for why). Zero real phases exist in the 10 sample files.

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

**Nested-plan dispatch (Phase 32)**: ``run_leader_plan()`` now looks at
``PlanPhase.nested_plan`` (parsed since Phase 18, but never dispatched
until now). Per ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``Read_More`` (the
move-file *reader*: ``Hire: BEGIN ... Read_HPlan; END`` and
``Read_More``'s ``Charm,Resurrection: Read_HPlan``), a move file embeds a
newly-joined character's own complete plan at exactly two trigger
points: a successful **Hire**, and a **Cast** of **Charm** or
**Resurrection**. After a phase's own dispatch succeeds, if it set
``nested_plan`` and really did bring a character into the kingdom this
turn (``_nested_plan_triggered`` -- ``HireExecutionResult.hired`` /
``CastExecutionResult.applied``), the nested character's plan is
recursively dispatched the same way, via the same recursive call to
``run_leader_plan`` (so a nested character's own Hire/Charm can nest
again -- confirmed to happen in real data, e.g. turn 9's leader 72 in
``AK3__T9.K1``). Checking ``applied`` rather than the spell itself is
what keeps Resurrection's own real embedded plans (present in several
samples) from ever dispatching: ``execute_cast`` never executes
Resurrection, so it never reports ``applied=True``, regardless of
whether the file happened to embed a plan for it. A nested character
with no existing ``LeaderState`` in ``state`` (nobody set one up) is
silently skipped -- same "can't act on what doesn't exist yet" rule as
``turn/kingdom_bridge.py`` (Phase 31). ``PhaseDispatchResult`` gained a
``leader_id`` field so a flattened, multi-leader results list (outer
leader's phases interleaved with any nested characters') stays
traceable to who actually issued each phase.

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
from ak_engine.models.plan import ActionPlan, PlanPhase
from ak_engine.turn.army_list_decode import ArmyListRequest, decode_army_list_phase
from ak_engine.turn.aspy_defend_decode import decode_aspy_phase, decode_defend_phase
from ak_engine.turn.aspy_execution import SpyReport, execute_aspy
from ak_engine.turn.cast_decode import decode_cast_phase
from ak_engine.turn.cast_execution import CastExecutionResult, execute_cast
from ak_engine.turn.challenge_execution import ChallengeExecutionResult, execute_challenge
from ak_engine.turn.challenge_pursue_decode import decode_challenge_phase, decode_pursue_phase
from ak_engine.turn.exploration import resolve_explore
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest, decode_fire_phase, decode_hire_phase
from ak_engine.turn.hire_pay import required_pay
from ak_engine.turn.move_execution import execute_move, record_kingdom_exploration
from ak_engine.turn.practice_decode import decode_practice_phase
from ak_engine.turn.practice_execution import PracticeExecutionResult, execute_practice
from ak_engine.turn.pursue_execution import PursueExecutionResult, execute_pursue
from ak_engine.turn.recruit_decode import decode_recruit_phase
from ak_engine.turn.recruit_execution import RecruitExecutionResult, execute_recruit
from ak_engine.turn.search_decode import decode_search_phase
from ak_engine.turn.search_execution import SearchExecutionResult, execute_search
from ak_engine.turn.trade_decode import decode_trade_phase
from ak_engine.turn.trade_execution import TradeExecutionResult, execute_give
from ak_engine.turn.trail_decode import decode_trail_phase
from ak_engine.turn.trail_execution import TrailExecutionResult, execute_trail
from ak_engine.turn.use_mi_decode import decode_use_mi_phase
from ak_engine.turn.use_mi_execution import UseMIExecutionResult, execute_use_mi

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
    # Phase 162: the Hero's own real required pay (``turn/hire_pay.py
    # required_pay()``), set whenever it was actually computed -- i.e.
    # every case that reaches the co-location/treasury checks, hired or
    # not. ``None`` for the earlier administrative failures (hero not
    # found/is a King/already employed/not co-located), which never
    # reach the pay computation.
    minimum_gold: int | None = None


@dataclass(slots=True)
class FireExecutionResult:
    """Phase 143: replaces ``_dispatch_fire()``'s previous bare ``FireRequest`` return, which
    gave a caller no way to know whether the Fire actually happened --
    see that function's own docstring.
    """

    request: FireRequest
    fired: bool
    reason: str | None = None  # set when fired is False


@dataclass(slots=True)
class PhaseDispatchResult:
    leader_id: int
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
    ``resolve_explore`` themselves raise (e.g. a ``KeyError`` for an
    unknown province or leader). A non-adjacent LMOVE target no longer
    raises ``NonAdjacentMoveError`` as of Phase 85 -- ``execute_move``
    resolves it as a chase step instead; see that function's own
    docstring.
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
        result = resolve_explore(province.explored_percent, province.effective_terrain(), explorer_skill)
        province.explored_percent = result.new_percent
        record_kingdom_exploration(province, kingdom_id, explorer_skill, partial=False)
        return result

    if action is ActionCode.SEARCH:
        return _dispatch_search(phase, state, leader_id, rng)

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
        return _dispatch_fire(phase, state, leader_id)

    if action is ActionCode.TRADE:
        return _dispatch_trade(phase, state, leader_id)

    if action is ActionCode.PRACTICE:
        return _dispatch_practice(phase, state, leader_id, rng)

    if action in (ActionCode.WAIT, ActionCode.NO_ACTION, ActionCode.MOVE_ABORT):
        return NoOpResult(action=action)

    if action is ActionCode.CAST:
        return _dispatch_cast(phase, state, kingdom_id, leader_id, rng, board_width)

    if action is ActionCode.USE_MI:
        return _dispatch_use_mi(phase, state, kingdom_id, leader_id, rng, board_width)

    if action is ActionCode.CHALLENGE:
        return _dispatch_challenge(phase, state, leader_id, rng)

    if action is ActionCode.PURSUE:
        return _dispatch_pursue(phase, state, leader_id, rng)

    if action is ActionCode.ASPY:
        return _dispatch_aspy(phase, state, leader_id)

    if action is ActionCode.DEFEND:
        return decode_defend_phase(phase)

    if action is ActionCode.TRAIL:
        return _dispatch_trail(phase, state, leader_id, rng)

    raise AssertionError("unreachable: action was checked against SUPPORTED_ACTIONS above")


def _dispatch_aspy(phase: PlanPhase, state: GameState, leader_id: int) -> SpyReport | None:
    request = decode_aspy_phase(phase)
    return execute_aspy(state, leader_id, request)


def _dispatch_practice(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None
) -> PracticeExecutionResult:
    request = decode_practice_phase(phase)
    return execute_practice(state, leader_id, request.ability, rng)


def _dispatch_recruit(phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int) -> RecruitExecutionResult:
    request = decode_recruit_phase(phase)
    return execute_recruit(state, kingdom_id, leader_id, request)


def _dispatch_cast(
    phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int, rng: random.Random | None, board_width: int
) -> CastExecutionResult:
    request = decode_cast_phase(phase)
    return execute_cast(state, kingdom_id, leader_id, request, rng, board_width=board_width)


def _dispatch_use_mi(
    phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int, rng: random.Random | None, board_width: int
) -> UseMIExecutionResult:
    request = decode_use_mi_phase(phase)
    return execute_use_mi(state, kingdom_id, leader_id, request, rng, board_width=board_width)


def _dispatch_challenge(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None
) -> ChallengeExecutionResult:
    """``mutual_encounter`` defaults to ``False`` here -- a single-leader dispatch has
    no visibility into whether the target King also ordered a Challenge
    back this same phase (see ``turn/challenge_execution.py``'s own
    docstring). Detecting real mutual Challenge/Pursue pairs would need
    the same cross-leader, same-phase visibility Multiple Contingents and
    Practice's own multi-character coordination needed -- a declared
    follow-up for ``turn/turn_processor.py``, not attempted here.
    """

    request = decode_challenge_phase(phase)
    return execute_challenge(state, leader_id, request, rng)


def _dispatch_pursue(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None
) -> PursueExecutionResult:
    """Same ``mutual_encounter=False`` default and reasoning as ``_dispatch_challenge``.

    Phase 213: stamps the decoded ``request`` onto the returned result
    here, at the dispatcher, rather than inside ``execute_pursue()``
    itself -- ``report/turn_report.py describe_turn_results()`` needs
    the target's own id to resolve a display name, and this is the one
    real call site every actual turn passes through, without touching
    ``execute_pursue()``'s own dozen internal early-return sites. Any
    caller invoking ``execute_pursue()``/``advance_pursuit()`` directly
    (every existing unit test included) still gets ``request=None``.
    """

    request = decode_pursue_phase(phase)
    result = execute_pursue(state, leader_id, request, rng)
    result.request = request
    return result


def _dispatch_trade(phase: PlanPhase, state: GameState, leader_id: int) -> TradeExecutionResult:
    """Phase 133: TRADE now executes for real via ``turn/trade_execution.py
    execute_give()``. As of Phase 140, ``execute_give()`` checks
    ``obj`` against the real ``GameState.items`` registry itself, so
    this dispatcher needs no extra wiring for the item-vs-gold
    disambiguation to work -- see that module's own docstring for the
    full reasoning.

    Phase 214: stamps ``request`` onto the result here, same reasoning
    as ``_dispatch_pursue``'s own Phase 213 note.
    """

    request = decode_trade_phase(phase)
    result = execute_give(state, leader_id, request)
    result.request = request
    return result


def _dispatch_search(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None
) -> SearchExecutionResult:
    """Phase 132: SEARCH now executes for real -- see ``turn/search_execution.py``'s
    own docstring for exactly which cases resolve real Melee combat
    (guardian stats sourced, Melee tactic present) versus honestly report
    ``combat_resolved=False``.

    Phase 213: stamps ``request`` onto the result here, same reasoning
    as ``_dispatch_pursue``'s own Phase 213 note.
    """

    request = decode_search_phase(phase)
    result = execute_search(state, leader_id, request, rng)
    result.request = request
    return result


def _dispatch_trail(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None
) -> TrailExecutionResult:
    """Phase 213: stamps ``request`` onto the result here, same reasoning
    as ``_dispatch_pursue``'s own Phase 213 note.
    """

    request = decode_trail_phase(phase)
    result = execute_trail(state, leader_id, request, rng)
    result.request = request
    return result


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
    acting_leader = state.leaders.get(leader_id)
    is_king = acting_leader is not None and acting_leader.is_king

    for army_id in target_ids:
        army = state.armies.get(army_id)
        if army is None:
            continue
        # "Releases the army(s) into mercenary status" (rulebook [3.6]:
        # "A King may Disband any army at any time. A character can
        # Disband an army only if he is in the same province.") --
        # ownerless and unled, available to be hired later. A Hero must
        # be co-located with the army; a King (Phase 40) bypasses that.
        if not is_king and (acting_leader is None or army.location != acting_leader.location):
            continue
        army.kingdom_id = None
        army.commanded_by = None

    return request


def _dispatch_hire(phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int) -> HireExecutionResult:
    request = decode_hire_phase(phase)
    hero = state.leaders.get(request.hero_id)
    acting_leader = state.leaders[leader_id]

    if hero is None:
        return HireExecutionResult(request, hired=False, reason="hero not found")
    if hero.is_king:
        # rulebook [3.5]: "You can't Hire a Hero who rules his own
        # province." Checked explicitly (Phase 40) rather than relying
        # on the "already in service" check below to catch every King
        # as a side effect -- that only works if the King happens to
        # have a kingdom_id set, which isn't guaranteed by is_king alone.
        return HireExecutionResult(request, hired=False, reason="cannot hire a King")
    if hero.kingdom_id is not None:
        return HireExecutionResult(request, hired=False, reason="hero already in service")
    if hero.location != acting_leader.location:
        # rulebook [3.5]: "Any character can attempt to Hire a Hero in the
        # same province."
        return HireExecutionResult(request, hired=False, reason="not co-located")

    king = next(
        (leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king),
        None,
    )
    pay = required_pay(hero, king)

    if pay >= 5:
        # rulebook: "a Good King generally cannot hire a Pagan Hero" --
        # an alignment gap this wide is refused outright, not merely
        # priced out of reach (see turn/hire_pay.py's own docstring for
        # why 5 is unreachable via a normal <=4-gold offer at all).
        return HireExecutionResult(request, hired=False, reason="alignment gap too wide", minimum_gold=pay)
    if request.gold_offer < pay:
        return HireExecutionResult(request, hired=False, reason="offer below required pay", minimum_gold=pay)

    kingdom = state.kingdoms[kingdom_id]
    if kingdom.treasury < pay:
        return HireExecutionResult(request, hired=False, reason="insufficient treasury", minimum_gold=pay)

    kingdom.treasury -= pay
    hero.kingdom_id = kingdom_id

    return HireExecutionResult(request, hired=True, minimum_gold=pay)


def _dispatch_fire(phase: PlanPhase, state: GameState, leader_id: int) -> FireExecutionResult:
    """Phase 143: returns a real ``FireExecutionResult`` instead of the previous bare
    ``FireRequest`` -- the caller now has a genuine ``fired``/``reason``
    signal to build a report sentence from (``report/turn_report.py
    describe_fire()``), where before it had no way to tell whether the
    Fire actually happened at all.
    """

    request = decode_fire_phase(phase)
    hero = state.leaders.get(request.hero_id)
    if hero is None:
        return FireExecutionResult(request, fired=False, reason="hero not found")

    acting_leader = state.leaders.get(leader_id)
    # "Releases the Hero into private life... will wander around until
    # hired by another King." (rulebook [3.7]: "A King may Fire a Hero
    # at any time. A character can Fire a Hero only if he is in the
    # same province.") A Hero must be co-located with the target (this
    # also naturally covers "firing himself" -- he's always in his own
    # province); a King (Phase 40) bypasses that, same as Disband.
    is_king = acting_leader is not None and acting_leader.is_king
    co_located = acting_leader is not None and acting_leader.location == hero.location
    if not (is_king or co_located):
        return FireExecutionResult(request, fired=False, reason="not co-located")

    hero.kingdom_id = None
    return FireExecutionResult(request, fired=True)


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
                results.append(PhaseDispatchResult(leader.leader_id, segment_index, label, phase.action, result, None))
            except Exception as exc:  # noqa: BLE001 -- intentionally broad, see docstring
                results.append(PhaseDispatchResult(leader.leader_id, segment_index, label, phase.action, None, exc))
                continue

            if phase.nested_plan is not None and _nested_plan_triggered(phase.action, result):
                results.extend(_dispatch_nested_plan(phase.nested_plan, state, kingdom_id, board_width, explorer_skill, rng))
    return results


def _nested_plan_triggered(action: Any, result: Any) -> bool:
    """Rulebook-independent, ``DEF2.PAS``-sourced check: does this phase's own
    successful result mean a real character joined the kingdom this turn?

    ``DEF2.PAS``'s ``R_HPlan``/``Read_More`` (the move-file *reader*) embeds
    a nested plan exactly for Hire and for Cast-ing Charm or Resurrection --
    see ``models/plan.py``'s module docstring. As of Phase 59,
    ``turn/cast_execution.py`` executes Resurrection too, so a successful
    revival now also dispatches its target's own embedded plan the same
    way a successful Charm always has -- both are "a character (re-)joins
    the kingdom this turn," the same underlying condition ``applied=True``
    already captures without needing to inspect which spell it was.
    """

    if action is ActionCode.HIRE:
        return isinstance(result, HireExecutionResult) and result.hired
    if action is ActionCode.CAST:
        return isinstance(result, CastExecutionResult) and result.applied
    return False


def _dispatch_nested_plan(
    nested_plan: ActionPlan,
    state: GameState,
    kingdom_id: int,
    board_width: int,
    explorer_skill: int,
    rng: random.Random | None,
) -> list[PhaseDispatchResult]:
    """Dispatch a newly-joined character's own embedded plan (see module docstring).

    Silently skipped (empty list) if the nested plan has no resolved
    ``leader_id`` or that character has no existing ``LeaderState`` in
    ``state`` -- there's nothing to enrich, same "can't create from
    nothing" rule as ``turn/kingdom_bridge.py`` (Phase 31). Never pins
    ``army_ids``: a freshly Hired/Charmed character's own commanded armies
    (if any) are re-derived fresh, independent of whatever the triggering
    leader's own dispatch was pinned to.
    """

    nested_leader_id = nested_plan.leader_id
    if nested_leader_id is None or nested_leader_id not in state.leaders:
        return []

    nested_leader = Leader(leader_id=nested_leader_id, name=state.leaders[nested_leader_id].name, plan=nested_plan)
    return run_leader_plan(
        nested_leader, state, kingdom_id, board_width=board_width, explorer_skill=explorer_skill, rng=rng
    )
