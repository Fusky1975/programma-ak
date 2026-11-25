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
  province. **Phase 256**: when this reveals a feature no other kingdom
  had discovered yet (``Feature.discovered_by_kingdom`` holds only this
  kingdom's own fresh entry), the acting leader's own ``MeritTally.
  features_discovered_first`` (Chancellor formula, ``turn/merit_points.py``)
  is credited -- see the dispatch branch below for why this is the one
  clean, reachable wiring point.
- **RECRUIT** actually executes (Phase 15): ``obj``/``extra`` decoded via
  ``turn/recruit_decode.py``, priced per requested type via
  ``turn/recruit.py resolve_recruit()``, then ``turn/recruit_execution.py
  execute_recruit()`` debits ``KingdomState.treasury`` (crediting an
  ally's treasury too, if recruiting in allied territory) and creates a
  new ``ArmyState`` per successfully recruited unit, enforcing the
  per-type per-turn limit via ``ProvinceState.recruited_this_turn``.
  ``is_native_to_province`` reads the real per-province "1-2 recruitable
  types" list (``ProvinceState.recruit_type_1``/``recruit_type_2``,
  Phase 278) when the province was bridged from a real world file
  (Phase 407); it falls back to the race-compatibility approximation
  (``turn/recruit.py is_army_type_compatible_with_race``) only for a
  ``GameState`` never bridged that way. See
  ``turn/recruit_execution.py``'s docstring for the cost-table
  verification done before writing this and the Phase 407 addendum for
  the real-data wiring.
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
  archive. ~~**Phase 162 supplies a formula anyway**, not transcribed
  from Pascal source (none survives) but designed from the player's
  manual text the user quoted directly plus one real, hard data point
  ("a Good King generally cannot hire a Pagan Hero")~~ -- **superseded
  by Phase 505**: a disassembly-based reverse-engineering pass the user
  supplied directly (``AKGEN.EXE``/``AK.OVR``) recovered the real,
  sourced ``LCost`` formula after all -- see ``turn/hire_pay.py``'s own
  docstring for the full derivation and why the Phase 162
  manual-derived approximation is no longer what runs. ``_dispatch_hire``
  now looks up the kingdom's own King
  (``LeaderState.is_king``), computes ``required_pay(hero, king)``, and
  charges *that* amount (not the raw offer) -- refusing outright when
  the alignment gap is too wide (``pay >= 5``, unreachable via any
  legal <=4-gold offer) or when the offer is below the computed pay
  (a genuine, narratable price counter-offer). ~~Recurring per-turn pay
  (only the one-time hiring charge is modeled, matching Recruit's own
  established simplification) remains unmodeled -- no sourced formula
  for it exists either.~~ -- **closed as of Phase 280**:
  ``turn/expenses.py leader_pay()`` reuses this same ``required_pay()``
  for a Hero's real recurring per-turn pay ("Ini" in the real CHARACTERS
  table), summed into ``compute_leader_maintenance()`` (``LCost``) and
  actually debited by ``apply_turn_maintenance()`` (Phase 404/527) --
  only the one-time hiring *charge* and the per-turn upkeep *pay* were
  ever distinct concepts; both are modeled now. See ``README.md`` for
  the full research trail.
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
  approximation. **Phase 644 correction, kept for the record**: an
  earlier version of this note called ``Ability.TACTICAL`` "recognized
  but deliberately not resolved... an unbuilt separate mechanic" --
  stale, and already stale when written: this dispatch site just calls
  ``execute_practice()`` directly, which has special-cased Tactical
  (training armies via [6.1], not personal skill) since Phase 167, long
  before this note's own last edit -- see
  [[feedback_stale_known_gap_claims]]. As of Phase 644, ``Ability.NAVAL``
  routes through the identical mechanic too ([6.1]'s own "both methods,
  same effect" text). **Stale as of Phase 266** -- this note used to say
  Sage's own rulebook-additional "device discovery" side roll wasn't
  modeled at all (no item/device data model). It has been for a while:
  ``execute_practice()``/``execute_practice_group()`` both roll it via
  the shared ``_roll_sage_device_discovery()`` (real per-level chance,
  a genuine ``Discovery`` grant via ``KingdomState.discoveries``, first-
  discoverer Chancellor-merit credit) -- see that function's own
  docstring for the full, disassembly-confirmed formula.
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
  Practice's own multi-character coordination needed. **``turn/turn_
  processor.py``'s own ``_dispatch_mutual_encounter()`` (Phase 56)
  wires that detection**, one level up from this single-leader dispatch
  layer: it scans each phase's own entries for a same-phase reciprocal
  CHALLENGE/PURSUE pair before this module ever dispatches either
  leader individually, and resolves the pair as one shared encounter
  with ``mutual_encounter=True``. Zero real phases exist for either
  action in the 10 sample files.
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

**Phase 1039 addendum**: a Charm/Resurrection cast from a wand
(``ActionCode.USE_MI``, not an ordinary ``ActionCode.CAST``) nests and
dispatches a joined character's plan the same way -- see
``_nested_plan_triggered()``/``_resolve_nested_plan_leader_id()``'s own
docstrings for why that needed splitting into two separate checks
(trigger vs. identity) instead of just adding one more ``elif`` branch
the way Hire/Cast share.

Every dispatch call takes an explicit ``leader_id`` -- the acting
character -- and ``army_ids`` defaults to whatever that leader currently
commands (``GameState.armies_commanded_by``) unless the caller overrides
it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.turn.sickness import apply_sickness
from ak_engine.turn.spy_watch import note_spy_watch
from ak_engine.turn.command_experience import (
    award_explore_experience,
    award_pick_up_leave_experience,
    award_recruit_hire_experience,
    award_sage_practice_experience,
)
from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.game_state import GameState
from ak_engine.models.leader import Leader
from ak_engine.models.office import Office
from ak_engine.models.plan import ActionPlan, PlanPhase
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.army_list_decode import ArmyListRequest, decode_army_list_phase
from ak_engine.turn.aspy_defend_decode import decode_aspy_phase, decode_defend_phase
from ak_engine.turn.aspy_execution import SpyReport, execute_aspy
from ak_engine.turn.cast_decode import decode_cast_phase
from ak_engine.turn.cast_execution import CastExecutionResult, execute_cast
from ak_engine.turn.challenge_execution import ChallengeExecutionResult, execute_challenge
from ak_engine.turn.challenge_pursue_decode import decode_challenge_phase, decode_pursue_phase
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.exploration import (
    EXPLORATION_CAP,
    SOCIETY_MAPS_EXPLORE_COUNT_RANGE,
    ExploreResult,
    discover_battlefield,
    receive_society_maps,
    resolve_explore,
)
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest, decode_fire_phase, decode_hire_phase
from ak_engine.turn.hire_pay import RARE_ALIGNMENT_EXCEPTION_PAY, required_pay, roll_rare_alignment_exception
from ak_engine.models.map import Terrain
from ak_engine.turn.leader_queries import find_king_of_kingdom, release_armies_to_garrison
from ak_engine.turn.sea_transport import cargo_aboard
from ak_engine.turn.battle_orchestrator import fight_battle, snapshot_army_types
from ak_engine.turn.diplomacy import is_attackable_at
from ak_engine.turn.sea_transport import apply_battle_carrier_destruction
from ak_engine.turn.move_execution import (
    MoveExecutionResult,
    execute_move,
    record_kingdom_exploration,
    reveal_adjacent_provinces,
)
from ak_engine.turn.movement import MapBounds
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.practice_decode import decode_practice_phase
from ak_engine.turn.practice_execution import PracticeExecutionResult, execute_practice
from ak_engine.turn.pursue_execution import PursueExecutionResult, execute_pursue
from ak_engine.turn.random_encounter_execution import dispatch_random_encounter_after_phase
from ak_engine.turn.recruit_decode import decode_recruit_phase
from ak_engine.turn.recruit_execution import RecruitExecutionResult, execute_recruit
from ak_engine.turn.rumor import RUMOR_CHANCE_BY_ACTION, resolve_rumor_generation
from ak_engine.turn.search_decode import decode_search_phase
from ak_engine.turn.search_execution import SearchExecutionResult, execute_search
from ak_engine.turn.sense_magic_items import sense_magic_items_in_province
from ak_engine.turn.trade_decode import decode_trade_phase, rewrite_trade_as_secret_spell_cast
from ak_engine.turn.trade_execution import CuratorResearchResult, TradeExecutionResult, execute_curator_research, execute_give
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
    # Phase 264: True when the Hero was hired only because the "rare
    # exception" bypass (turn/hire_pay.py roll_rare_alignment_exception())
    # succeeded for an otherwise-refused alignment gap. Always False
    # otherwise, including every ordinary hire and every outright refusal.
    rare_alignment_exception: bool = False


@dataclass(slots=True)
class FireExecutionResult:
    """Phase 143: replaces ``_dispatch_fire()``'s previous bare ``FireRequest`` return, which
    gave a caller no way to know whether the Fire actually happened --
    see that function's own docstring.
    """

    request: FireRequest
    fired: bool
    reason: str | None = None  # set when fired is False
    # Phase 614: set instead of an ordinary Fire when the order-giver
    # holds Office.ASSASSIN and `request.hero_id` is a non-King leader
    # in a different Kingdom -- see `_dispatch_fire()`'s own Phase 614
    # addendum for the real, disassembly-confirmed interception this
    # reuses the FIRE order's own decoded data for. `fired` stays
    # `False` here (no ordinary Fire happened, the Hero's own
    # `kingdom_id` is untouched) -- `guild_assassination_queued` is the
    # real, distinct outcome a caller should check first.
    guild_assassination_queued: bool = False


@dataclass(slots=True)
class ArmyListExecutionResult:
    """Phase 420: replaces ``_dispatch_leave()``/``_dispatch_pick_up()``/
    ``_dispatch_disband()``'s previous bare ``ArmyListRequest`` return,
    which gave a caller no way to know which of the requested armies
    were actually affected versus silently skipped (not found / not
    co-located) -- the same gap ``FireExecutionResult`` (Phase 143)
    already closed for Fire. One shared type for all three actions:
    each already iterates the same decoded ``target_ids`` list and
    either mutates or skips each army by id, with no other per-action
    outcome data to track (no sourced narrative exists for a skip
    reason either, so none is recorded).
    """

    request: ArmyListRequest
    succeeded: list[int] = field(default_factory=list)  # army_ids actually affected
    skipped: list[int] = field(default_factory=list)  # requested but not found/not co-located
    # Phase 647: Leave-only -- a Skeletal Army left uncommanded or handed
    # to anyone but an Undead King "digs its own grave" instead of
    # actually being left/reassigned ([4.2.5]) -- captured as (army_id,
    # army_type) since the army is removed from `GameState.armies`
    # before `report/turn_report.py describe_leave()` ever sees it.
    skeletal_army_lost: list[tuple[int, ArmyType]] = field(default_factory=list)
    # Disband-only (2026-11-24 audit): why a requested army was not disbanded, army id -> reason, so
    # the report can say so instead of the order silently doing nothing.
    skipped_reasons: dict[int, str] = field(default_factory=dict)


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
    board_width: int | None = None,
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

    ``board_width`` (Phase 780, default ``None``) falls back to
    ``state.board_width`` when omitted -- the real value the world was
    actually built at, instead of always the wrong (Super-AK) constant
    a few of this function's own branches used to fall back to silently.
    """

    board_width = board_width if board_width is not None else state.board_width
    action = phase.action
    if action not in SUPPORTED_ACTIONS:
        label = action.name if isinstance(action, ActionCode) else repr(action)
        raise UnsupportedActionError(f"no turn/* resolver implemented yet for action {label}")

    if army_ids is None:
        army_ids = [army.army_id for army in state.armies_commanded_by(leader_id)]

    # Phase 243: rumor generation, resolved before the order's own real
    # effect (uses the leader's pre-order location, same as the order's
    # own real effect would for a stationary action -- see turn/rumor.py's
    # own docstring for why "before" vs. "after" doesn't matter for any
    # of the 7 eligible order types except Move/Pursue/Trail, where it's
    # a documented choice). A no-op, consuming no randomness, for every
    # action outside RUMOR_CHANCE_BY_ACTION or when GameState has no
    # eligible feature nearby -- i.e. every pre-Phase-243 caller.
    leader = state.leaders.get(leader_id)
    if leader is not None:
        # Exploration speed follows the acting character's own Explorer level
        # (Compass, Telescope and a held Explorer item included); a caller's
        # explicit value only ever raises it.
        explorer_skill = max(explorer_skill, effective_skill_level(state, leader, Ability.EXPLORER))
    if leader is not None and action in RUMOR_CHANCE_BY_ACTION:
        rumor_rng = rng if rng is not None else random.Random()
        rumor = resolve_rumor_generation(state, kingdom_id, leader_id, leader.location, action, rumor_rng)
        if rumor is not None:
            state.add_rumor(rumor)

    # Phase 507: the acting leader's own real Explorer Advanced Ability
    # possession -- see turn/exploration.py's own Phase 507 addendum for
    # the real formula each feeds. `leader` is already fetched above for
    # rumor generation; both default False when there's no leader.
    has_military_maps = leader is not None and AdvancedAbility.EXPLORER_MILITARY_MAPS in leader.advanced_abilities
    has_difficult_terrain = (
        leader is not None and AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN in leader.advanced_abilities
    )
    # Phase 509: same real-possession pattern, for Find Mines.
    has_find_mines = leader is not None and AdvancedAbility.EXPLORER_FIND_MINES in leader.advanced_abilities

    # Phase 521: same real-possession pattern, for March.
    has_march_cavalry = leader is not None and AdvancedAbility.MARCH_CAVALRY in leader.advanced_abilities
    has_march_cavalry_mastery = (
        leader is not None and AdvancedAbility.MARCH_CAVALRY_MASTERY in leader.advanced_abilities
    )
    # Phase 768: same real-possession pattern, for Cavalry's own 3rd
    # stacking tier.
    has_march_cavalry_true_mastery = (
        leader is not None and AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY in leader.advanced_abilities
    )
    has_march_infantry = leader is not None and AdvancedAbility.MARCH_INFANTRY in leader.advanced_abilities
    has_march_infantry_mastery = (
        leader is not None and AdvancedAbility.MARCH_INFANTRY_MASTERY in leader.advanced_abilities
    )
    # Phase 693: same real-possession pattern, for March Through Floods.
    has_march_through_floods = leader is not None and AdvancedAbility.MARCH_THROUGH_FLOODS in leader.advanced_abilities

    # Phase 523: the leader's own real effective Naval skill level, not an
    # AdvancedAbility flag -- see move_execution.py's own Phase 523
    # addendum for why Naval's movement bonus is a plain function of raw
    # skill rather than a gated Advanced Ability.
    naval_skill_level = effective_skill_level(state, leader, Ability.NAVAL) if leader is not None else 0
    # Phase 764: same real-effective-skill-level pattern, for [4.12] MARCH
    # TABLE's own separate, raw-skill-level movement bonus -- see
    # move_execution.py's own Phase 764 addendum (march_table_extra_
    # movement()) for why this is distinct from the Advanced-Ability-gated
    # has_march_cavalry/_infantry flags above.
    march_skill_level = effective_skill_level(state, leader, Ability.MARCH) if leader is not None else 0
    # Phase 524: same real-possession pattern, for Naval Hug Coastline.
    has_naval_hug_coastline = leader is not None and AdvancedAbility.NAVAL_HUG_COASTLINE in leader.advanced_abilities
    # Phase 715: same real-possession pattern, for the Fleet/Whale
    # cargo-capacity subsystem's own two Advanced Abilities.
    caster_has_druidic_whale_transport = (
        leader is not None and AdvancedAbility.DRUIDIC_WHALE_TRANSPORT in leader.advanced_abilities
    )
    caster_has_druidic_transport = leader is not None and AdvancedAbility.DRUIDIC_TRANSPORT in leader.advanced_abilities

    if action is ActionCode.LMOVE:
        target = decode_hex_number(phase.obj, board_width)
        result = execute_move(
            state,
            kingdom_id,
            army_ids,
            target,
            leader_id=leader_id,
            explorer_skill=explorer_skill,
            rng=rng,
            has_military_maps=has_military_maps,
            has_difficult_terrain=has_difficult_terrain,
            has_find_mines=has_find_mines,
            has_march_cavalry=has_march_cavalry,
            has_march_cavalry_mastery=has_march_cavalry_mastery,
            has_march_cavalry_true_mastery=has_march_cavalry_true_mastery,
            has_march_infantry=has_march_infantry,
            has_march_infantry_mastery=has_march_infantry_mastery,
            has_march_through_floods=has_march_through_floods,
            march_skill_level=march_skill_level,
            naval_skill_level=naval_skill_level,
            has_naval_hug_coastline=has_naval_hug_coastline,
            auto_board=True,
            caster_has_druidic_whale_transport=caster_has_druidic_whale_transport,
            caster_has_druidic_transport=caster_has_druidic_transport,
            enforce_transport_legality=True,
        )
        # Phase 490 -- Arch-Mage's own "Sense Magic Items in Province"
        # perk: only meaningful once the mover actually arrived somewhere
        # (a repelled/contested battle can leave ``new_location`` unset).
        if result.moved and result.new_location is not None:
            result.sensed_magic_items = sense_magic_items_in_province(state, leader_id, result.new_location)
        if leader is not None:
            # Chancellor Merit ("+2 per Special Place discovered first"), same credit as an Explore.
            for feature in result.discovered_features:
                if len(feature.discovered_by_kingdom) == 1:
                    leader.merit_tally.features_discovered_first += 1
        return result

    if action is ActionCode.EXPLORE:
        # Phase 1041 bug fix -- `leader` is already fetched (`.get()`,
        # None-safe) a few lines up for rumor generation, but this
        # branch used to re-fetch it via a bare `state.leaders[leader_id]`
        # subscript instead of reusing it, missing the "acting leader may
        # have died earlier in the same turn" guard LEAVE/PICK_UP/
        # DISBAND/HIRE/FIRE all already got (each via `.get()` + a clean
        # no-op, not a raise). A leader removed from `state.leaders`
        # earlier this turn (e.g. lost a Challenge/Search/Pursue duel)
        # but with a stale EXPLORE still queued for a later phase used to
        # raise an uncaught `KeyError` here instead of degrading like its
        # sibling actions.
        if leader is None:
            return NoOpResult(action=action)
        province = state.provinces[leader.location]
        # The shared scalar (`explored_percent`) keeps its own bookkeeping, but what this Explore
        # *reports* -- the level reached, whether it explored anything, the experience earned -- is
        # the exploring Kingdom's own cumulative exploration of the province: another Kingdom having
        # explored it first must not make this one's order read "already fully explored".
        shared = resolve_explore(
            province.explored_percent,
            province.effective_terrain(),
            explorer_skill,
            has_military_maps=has_military_maps,
            has_difficult_terrain=has_difficult_terrain,
        )
        province.explored_percent = shared.new_percent
        prior_percent = province.explored_percent_by_kingdom.get(kingdom_id, 0)
        exploration = record_kingdom_exploration(
            province,
            kingdom_id,
            explorer_skill,
            partial=False,
            state=state,
            rng=rng,
            has_military_maps=has_military_maps,
            has_difficult_terrain=has_difficult_terrain,
            has_find_mines=has_find_mines,
            leader_id=leader_id,
        )
        result = ExploreResult(
            new_percent=exploration.new_percent,
            delta_applied=exploration.new_percent - prior_percent,
            fully_explored=exploration.new_percent >= EXPLORATION_CAP,
        )
        if result.delta_applied > 0:
            award_explore_experience(state, leader_id)
        result.battlefield_fallen = discover_battlefield(
            state, province.coord, exploration.new_percent, rng if rng is not None else random.Random()
        )
        reveal_adjacent_provinces(state, province, kingdom_id, MapBounds(board_width, state.board_height))
        result.discovered_features = exploration.discovered_features
        # Phase 256: Chancellor Merit Points ("+2 per Special Place
        # discovered first", turn/merit_points.py) -- a feature just
        # entered discover_features()'s returned list means kingdom_id's
        # own entry was *just* added to Feature.discovered_by_kingdom; if
        # that's still the only entry, no other kingdom got there first.
        # Move's own partial-exploration discovery path (execute_move()'s
        # record_kingdom_exploration(..., partial=True) call) isn't
        # credited here -- that call site discards its own return value
        # entirely today, a separate, pre-existing gap this phase doesn't
        # attempt to close.
        for feature in exploration.discovered_features:
            if len(feature.discovered_by_kingdom) == 1:
                leader.merit_tally.features_discovered_first += 1

        # Phase 510: Society Maps's own "If he Explores a province, 0-2
        # maps are received" trigger -- deliberately EXPLORE-only, not
        # threaded into LMOVE's partial-exploration branch above (see
        # turn/exploration.py's own module docstring for why this one
        # differs from Find Mines' broader "whenever explored" wiring).
        if leader is not None and AdvancedAbility.EXPLORERS_SOCIETY_MAPS in leader.advanced_abilities:
            maps_rng = rng if rng is not None else random.Random()
            maps_count = maps_rng.randint(*SOCIETY_MAPS_EXPLORE_COUNT_RANGE)
            result.society_maps_revealed = receive_society_maps(state, kingdom_id, maps_count, maps_rng)
        return result

    if action is ActionCode.SEARCH:
        return _dispatch_search(phase, state, leader_id, rng)

    if action is ActionCode.RECRUIT:
        recruit_result = _dispatch_recruit(phase, state, kingdom_id, leader_id)
        if recruit_result.recruited:
            award_recruit_hire_experience(state, leader_id, "recruit", len(recruit_result.recruited))
        return recruit_result

    if action is ActionCode.LEAVE:
        leave_result = _dispatch_leave(phase, state, leader_id)
        award_pick_up_leave_experience(state, leader_id, leave_result.succeeded)
        return leave_result

    if action is ActionCode.PICK_UP:
        pick_up_result = _dispatch_pick_up(phase, state, leader_id)
        award_pick_up_leave_experience(state, leader_id, pick_up_result.succeeded)
        return pick_up_result

    if action is ActionCode.DISBAND:
        return _dispatch_disband(phase, state, leader_id)

    if action is ActionCode.HIRE:
        hire_result = _dispatch_hire(phase, state, kingdom_id, leader_id, rng)
        if hire_result.hired:
            award_recruit_hire_experience(state, leader_id, "hire", hire_result.request.hero_id)
        return hire_result

    if action is ActionCode.FIRE:
        return _dispatch_fire(phase, state, leader_id)

    if action is ActionCode.TRADE:
        # Phase 397: DEF2.PAS's own Trade branch reclassifies a self-
        # targeted Give of a secret-spell ordinal (25-34) into a Cast --
        # see turn/trade_decode.py's module docstring for the full
        # decoded mechanic. Checked ahead of the ordinary Trade dispatch,
        # exactly mirroring R_HPlan's own read-time rewrite order.
        rewritten_cast = rewrite_trade_as_secret_spell_cast(phase, leader_id)
        if rewritten_cast is not None:
            return execute_cast(state, kingdom_id, leader_id, rewritten_cast, rng, board_width=board_width)
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
        return _dispatch_aspy(phase, state, leader_id, rng)

    if action is ActionCode.DEFEND:
        return decode_defend_phase(phase)

    if action is ActionCode.TRAIL:
        return _dispatch_trail(phase, state, leader_id, rng)

    raise AssertionError("unreachable: action was checked against SUPPORTED_ACTIONS above")


def _dispatch_aspy(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None = None
) -> SpyReport | None:
    request = decode_aspy_phase(phase)
    # Phase 495: AdvancedAbility.KNOW_ALIGNMENT_TALENT ([REPORTS.PAS]
    # Align_Est's own "Has_SA(agent,Detect_Align)" branch) grants perfect
    # alignment detection here -- see execute_aspy()'s own docstring for
    # why this is one of two separate flags. Phase 660 wires the other:
    # Office.PSYCHIC_MAGE's own real "knows their exact alignment and
    # temper" title text.
    leader = state.leaders.get(leader_id)
    caster_has_detect_align = leader is not None and AdvancedAbility.KNOW_ALIGNMENT_TALENT in leader.advanced_abilities
    psychic_mage_holder = resolve_office_holder(state, Office.PSYCHIC_MAGE)
    caster_holds_psychic_mage_office = psychic_mage_holder is not None and psychic_mage_holder.leader_id == leader_id
    # Phase 694: same real-possession pattern, for Druidic Animal Spies.
    caster_has_druidic_animal_spies = (
        leader is not None and AdvancedAbility.DRUIDIC_ANIMAL_SPIES in leader.advanced_abilities
    )
    # Phase 705: same real-possession pattern, for Spy Expanded Spying.
    caster_has_spy_expanded_spying = (
        leader is not None and AdvancedAbility.SPY_EXPANDED_SPYING in leader.advanced_abilities
    )
    return execute_aspy(
        state,
        leader_id,
        request,
        board_width=state.board_width,
        board_height=state.board_height,
        caster_has_detect_align=caster_has_detect_align,
        caster_holds_psychic_mage_office=caster_holds_psychic_mage_office,
        caster_has_druidic_animal_spies=caster_has_druidic_animal_spies,
        caster_has_spy_expanded_spying=caster_has_spy_expanded_spying,
        rng=rng,
    )


def _dispatch_practice(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None
) -> PracticeExecutionResult:
    request = decode_practice_phase(phase)
    result = execute_practice(state, leader_id, request.ability, rng)
    if request.ability is Ability.SAGE:
        award_sage_practice_experience(state, leader_id, phase.label)
    return result


def _dispatch_recruit(phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int) -> RecruitExecutionResult:
    request = decode_recruit_phase(phase)
    return execute_recruit(state, kingdom_id, leader_id, request)


def _fight_for_raised_skeletons(
    state: GameState, kingdom_id: int, result: CastExecutionResult | None, rng: random.Random | None
) -> None:
    """[4.2.5]: "Un Esercito di Scheletri può essere evocato in una provincia controllata da un
    nemico e quindi, se un'unità sta difendendo la provincia, ci sarà una battaglia." Fights it
    right after the cast and stores the report on ``result.battle_report``."""

    if result is None or not result.skeletal_army_raised:
        return
    raised_ids = [army.army_id for army in result.skeletal_army_raised if army.army_id in state.armies]
    if not raised_ids:
        return
    coord = state.armies[raised_ids[0]].location
    province = state.provinces.get(coord)
    if province is None:
        return
    defenders_present = any(
        not army.is_mercenary and army.army_id not in raised_ids and is_attackable_at(state, army.kingdom_id, kingdom_id, province)
        for army in state.armies_at(coord)
    )
    if not defenders_present:
        return
    army_types_before_battle = snapshot_army_types(state)
    report = fight_battle(
        state,
        kingdom_id,
        coord,
        raised_ids,
        apply_fanaticism=True,
        use_real_duel_combat=True,
        rng=rng if rng is not None else random.Random(),
    )
    apply_battle_carrier_destruction(
        state,
        report.destroyed_army_ids,
        report.disbanded_army_ids,
        report.pursuit_destroyed_army_ids,
        coord=coord,
        army_types_before_battle=army_types_before_battle,
    )
    result.battle_report = report


def _dispatch_cast(
    phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int, rng: random.Random | None, board_width: int
) -> CastExecutionResult:
    request = decode_cast_phase(phase)
    result = execute_cast(state, kingdom_id, leader_id, request, rng, board_width=board_width)
    _fight_for_raised_skeletons(state, kingdom_id, result, rng)
    return result


def _dispatch_use_mi(
    phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int, rng: random.Random | None, board_width: int
) -> UseMIExecutionResult:
    request = decode_use_mi_phase(phase)
    result = execute_use_mi(state, kingdom_id, leader_id, request, rng, board_width=board_width)
    _fight_for_raised_skeletons(state, kingdom_id, result.cast_result, rng)
    if result.cast_result is not None:
        result.battle_report = result.cast_result.battle_report
    return result


def _dispatch_challenge(
    phase: PlanPhase, state: GameState, leader_id: int, rng: random.Random | None
) -> ChallengeExecutionResult:
    """``mutual_encounter`` defaults to ``False`` here -- a single-leader dispatch has
    no visibility into whether the target King also ordered a Challenge
    back this same phase (see ``turn/challenge_execution.py``'s own
    docstring). ``turn/turn_processor.py _dispatch_mutual_encounter()``
    (Phase 56) detects a real same-phase reciprocal Challenge/Pursue
    pair one level up, before either leader reaches this dispatcher
    individually, and resolves the pair as one shared encounter with
    ``mutual_encounter=True`` instead.

    Phase 417: stamps the decoded ``request`` onto the returned result
    here, at the dispatcher, the same "one real call site, don't touch
    every internal early-return" reasoning ``_dispatch_pursue()``'s own
    Phase 213 addendum already established for its own sibling result
    type.
    """

    request = decode_challenge_phase(phase)
    result = execute_challenge(state, leader_id, request, rng)
    result.request = request
    return result


def _has_spy_super_sleuth(state: GameState, leader_id: int) -> bool:
    """Phase 695: same real-possession pattern as `has_march_cavalry`
    et al. -- `AdvancedAbility.SPY_SUPER_SLEUTH` gates the acting
    leader's own Trail/Pursue catch-up roll, resolved fresh at each of
    the two real dispatch sites below.
    """

    leader = state.leaders.get(leader_id)
    return leader is not None and AdvancedAbility.SPY_SUPER_SLEUTH in leader.advanced_abilities


def _has_spy_expanded_spying(state: GameState, leader_id: int) -> bool:
    """Phase 705: same real-possession pattern as `_has_spy_super_sleuth`
    -- `AdvancedAbility.SPY_EXPANDED_SPYING` gates `_dispatch_trail()`'s
    own offices-held intelligence, resolved fresh at each real dispatch
    site (Trail's own initial dispatch here, plus `turn_processor.py`'s
    own persistent chase continuation loop).
    """

    leader = state.leaders.get(leader_id)
    return leader is not None and AdvancedAbility.SPY_EXPANDED_SPYING in leader.advanced_abilities


def _has_spy_blackmail(state: GameState, leader_id: int) -> bool:
    """Phase 713: same real-possession pattern as `_has_spy_super_sleuth`
    -- `AdvancedAbility.SPY_BLACKMAIL` gates `_dispatch_trail()`'s own
    per-phase blackmail-detection roll, resolved fresh at each real
    dispatch site (Trail's own initial dispatch here, plus `turn_
    processor.py`'s own persistent chase continuation loop).
    """

    leader = state.leaders.get(leader_id)
    return leader is not None and AdvancedAbility.SPY_BLACKMAIL in leader.advanced_abilities


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
    result = execute_pursue(state, leader_id, request, rng, has_spy_super_sleuth=_has_spy_super_sleuth(state, leader_id))
    result.request = request
    return result


def _dispatch_trade(phase: PlanPhase, state: GameState, leader_id: int) -> TradeExecutionResult | CuratorResearchResult:
    """Phase 133: TRADE now executes for real via ``turn/trade_execution.py
    execute_give()``. As of Phase 140, ``execute_give()`` checks
    ``obj`` against the real ``GameState.items`` registry itself, so
    this dispatcher needs no extra wiring for the item-vs-gold
    disambiguation to work -- see that module's own docstring for the
    full reasoning.

    Phase 214: stamps ``request`` onto the result here, same reasoning
    as ``_dispatch_pursue``'s own Phase 213 note.

    Phase 667: Office.CURATOR's own real perk -- "the character must
    have an order to give the magic item number to himself." A self-
    targeted Give (``request.target_leader_id == leader_id``) from the
    current CURATOR titleholder is rerouted to ``execute_curator_
    research()`` instead of the ordinary ``execute_give()`` -- checked
    *after* ``dispatch_phase()``'s own existing secret-spell rewrite
    (``rewrite_trade_as_secret_spell_cast()``, Phase 397), matching the
    real ``DEF2.PAS R_HPlan``'s own read-time order (that rewrite is
    tried first, before this dispatcher is even called). A self-
    targeted Give from anyone else (or from the titleholder without a
    real item number decoded) falls through to the ordinary Give path
    unchanged -- self-Give was already a real, if unusual, case
    ``execute_give()`` handles on its own before this phase.
    """

    request = decode_trade_phase(phase)
    if request.target_leader_id == leader_id:
        curator_holder = resolve_office_holder(state, Office.CURATOR)
        if curator_holder is not None and curator_holder.leader_id == leader_id:
            research_result = execute_curator_research(state, request.obj)
            research_result.request = request
            return research_result
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
    result = execute_trail(
        state,
        leader_id,
        request,
        rng,
        has_spy_super_sleuth=_has_spy_super_sleuth(state, leader_id),
        caster_has_spy_expanded_spying=_has_spy_expanded_spying(state, leader_id),
        caster_has_spy_blackmail=_has_spy_blackmail(state, leader_id),
    )
    result.request = request
    return result


def _is_undead_king(state: GameState, leader_id: int | None) -> bool:
    """"Re Non-Morto" ([4.2.5]) -- a King whose own Kingdom's `Alignment`
    is `UNDEAD`. Kingdom-alignment-based, not the King's own personal
    `LeaderState.alignment` -- the same eligibility gate `turn/merit_
    points.py _king_of_alignment()` already uses for the (differently-
    scoped) Office.UNDEAD_KING title, reused here for consistency with
    this project's own established "Undead King" concept rather than
    re-deriving a possibly-different reading.
    """

    if leader_id is None:
        return False
    leader = state.leaders.get(leader_id)
    if leader is None or not leader.is_king or leader.kingdom_id is None:
        return False
    return state.kingdoms[leader.kingdom_id].alignment is Alignment.UNDEAD


def _dispatch_leave(phase: PlanPhase, state: GameState, leader_id: int) -> ArmyListExecutionResult:
    """Phase 420: returns a real ``ArmyListExecutionResult`` instead of the
    bare ``ArmyListRequest`` this used to hand back -- see that type's
    own docstring for why (``describe_turn_results()`` needs to know
    which armies actually left, not just what was requested).

    **Phase 647 -- Skeletal Army "digs its own grave"** ([4.2.5],
    quoted in full): "Se chi lancia l'incantesimo cerca di abbandonare
    l'Esercito di Scheletri o di affidarlo a un altro personaggio, che
    non sia un Re Non-Morto, gli scheletri soldati si scaveranno da
    soli la tomba e riprenderanno il loro sonno interrotto." Both
    halves (leaving uncommanded, ``request.target_leader_id is None``,
    and reassigning to anyone but an Undead King) collapse to one
    check: ``ArmyState.is_skeletal`` and the new commander isn't an
    Undead King (``_is_undead_king()`` -- ``None`` fails it too, so
    "abandon" and "reassign to a non-Undead-King" share the same
    branch). The army is removed outright (``GameState.remove_army()``)
    rather than becoming an ordinary mercenary the way Disband does --
    "riprenderanno il loro sonno interrotto" (resume their interrupted
    sleep) describes the army ceasing to exist, not changing hands.
    Whether the underlying units re-enter ``GameState.battle_graveyard``
    (available to a future Skeletal Army cast) is genuinely unresolved
    by this text and deliberately not guessed here -- see ``turn/
    skeletal_decay.py``'s own module docstring for the graveyard's real
    scope.

    **Phase 690 -- `AdvancedAbility.ENHANCED_SKELETAL_UNITS`'s own
    exemption**: "The necromancer may now Leave skeletal armies to
    another character or the garrison commander, even if there is no
    Undead leader to control the armies" -- the *acting* leader (the
    one issuing this Leave order) holding this ability bypasses the
    grave-digging check entirely, checked alongside the existing
    Undead-King check below. The sourced text's own "may also Pick Up
    skeletal armies freely" half needs no code change at all --
    ``_dispatch_pick_up()`` already has no skeletal-specific
    restriction for anyone to bypass.

    **Phase 821 bug fix**: a real turn can dispatch this phase for a
    leader who already died earlier in the *same* turn (e.g. lost a
    Challenge in an earlier phase, with a Leave order still queued for
    a later one) -- `run_leader_plan()` has no per-phase liveness gate
    of its own, matching every other action dispatch in this module.
    Previously this function never checked whether the acting leader
    still existed at all: it happily reassigned command of every
    listed army regardless (a dead leader silently executing a real
    order), and, for a skeletal army specifically, crashed outright on
    a bare `state.leaders[leader_id]` lookup once it got to the
    Enhanced-Skeletal-Units check. Both are now the same, single
    `acting_leader is None` guard -- mirroring `_dispatch_disband()`'s
    own already-correct "a missing acting leader can't act at all"
    stance -- so a dead leader's Leave order now skips every listed
    army cleanly, the same as it already does for Disband.

    **Three bug fixes, sourced directly from the user (2026-10-29), the
    fuller rulebook [3.8] text they pasted while designing this
    Action's own move-composer UI**:

    (1) A *specific* army-id list (``request.all_armies`` is ``False``)
    used to reassign command of *any* ``army_id`` present in ``state.
    armies``, with no check that the acting leader actually commands
    it, is co-located with it, or that it belongs to his own Kingdom at
    all. Every target now must be either already commanded by the
    acting leader (``army.commanded_by == leader_id``), or -- the
    rulebook's own "novità" ("con questo comando si potranno passare
    unità dal Comando di Guarnigione a un Eroe") -- unled and co-located
    with the acting leader (``army.commanded_by is None and army.
    location == acting_leader.location``); either way the army must
    belong to the acting leader's own Kingdom.

    **2026-11-20 bug fix, user-confirmed via a live playtest ("LEAVE
    ALL non ha dato alcuna unità dal garrison commander al Re
    Vitello")**: ``request.all_armies`` used to resolve to plain
    ``armies_commanded_by(leader_id)`` only, on the reasoning that this
    already trivially satisfies rule (1) above -- true, but it also
    made "ALL" *narrower* than the specific-list case right above it:
    the move-composer's own army-target dropdown (``webapp/moves_
    compose.py leave_army_target_options()``) already lists a co-located
    Garrison-commanded army as something this leader can Leave by
    number, right next to the same dropdown's own "ALL" pseudo-option
    -- so a Hero whose only real military presence at his own location
    was a Garrison-commanded army, with nothing personally commanded at
    all, saw "ALL" give away nothing. ``request.all_armies`` now
    resolves to the exact same eligibility rule (1) spells out for a
    specific list -- every army of the acting leader's own Kingdom that
    he either commands or (Garrison-commanded, co-located) may pass
    along -- so "ALL" can never give away less than picking every one
    of the dropdown's own real choices by hand would.

    (2) Leaving to a named Hero (``request.target_leader_id is not
    None``) now requires that Hero to be of the acting leader's own
    Kingdom or an allied one (``GameState.is_allied()``) -- "si può
    lasciare... ad un altro Eroe, anche di un altro Reame, basta che sia
    alleato." A target leader id that doesn't resolve to a real
    ``LeaderState``, or belongs to a hostile/unrelated Kingdom, now
    blocks the *whole* order (every requested army skipped) rather than
    silently reassigning command to an invalid or hostile target --
    there is no sourced "partial order" behavior for this case, so
    skipping outright is the same conservative "no source, no guess"
    choice `_dispatch_leave()`'s own pre-existing checks already make
    elsewhere.

    (3) "Un'unità lasciata a un generale... di un altro Reame diventa di
    proprietà di quest'ultimo" is a *second*, independent Kingdom-
    transfer trigger from the pre-existing "left in an ally's province"
    one right below -- leaving directly to a named, allied-Kingdom Hero
    (now guaranteed allied by check (2) above) transfers the army to
    that Hero's own Kingdom, regardless of which Kingdom currently owns
    the province the army happens to be standing in. The two triggers
    are mutually exclusive by construction here (a named-Hero target
    always takes the Hero's own Kingdom; only a Garrison target
    (``target_leader_id is None``) ever falls back to the province-
    ownership rule), avoiding an unsourced tie-break between the two
    for the case where they'd otherwise disagree.

    **2026-11-03 -- the gap this paragraph used to flag here is closed.**
    "quello che ha iniziativa più alta aspetta quello che ha iniziativa
    più bassa" -- when an order targets another leader of the same (or
    an allied) Kingdom, the rulebook's own fuller text says the higher-
    ``character_initiative()`` leader's own same-phase action waits for
    the lower-Initiative leader's targeting order to actually resolve
    first, even out of the ordinary Initiative order (worked example:
    Hero #13, Initiative 20, Leaves all his armies to Hero #14,
    Initiative 40, in P2; Hero #14's own P2 Move waits for that Leave to
    land first, despite his higher Initiative). `turn/turn_processor.py
    run_turn()`'s own per-phase dispatch loop now does exactly this --
    see `_order_phase_entries_by_initiative()`'s own docstring there for
    the full mechanism (Initiative-based base ordering plus this same
    "waits for" override, covering Leave/Recruit/Give/a character-
    targeted Cast alike, not just Leave).
    """

    request = decode_army_list_phase(phase)
    acting_leader = state.leaders.get(leader_id)
    result = ArmyListExecutionResult(request=request)
    if acting_leader is None:
        result.skipped.extend(request.army_ids)
        return result

    target_ids = (
        [
            army.army_id
            for army in state.armies.values()
            if army.kingdom_id == acting_leader.kingdom_id
            and (
                army.commanded_by == leader_id
                or (army.commanded_by is None and army.location == acting_leader.location)
            )
        ]
        if request.all_armies
        else request.army_ids
    )

    target_leader = state.leaders.get(request.target_leader_id) if request.target_leader_id is not None else None
    if request.target_leader_id is not None and (
        target_leader is None or not state.is_allied(acting_leader.kingdom_id, target_leader.kingdom_id)
    ):
        result.skipped.extend(target_ids)
        return result

    for army_id in target_ids:
        army = state.armies.get(army_id)
        if army is None:
            result.skipped.append(army_id)
            continue
        owns_or_may_pass_along = army.kingdom_id == acting_leader.kingdom_id and (
            army.commanded_by == leader_id
            or (army.commanded_by is None and army.location == acting_leader.location)
        )
        if not owns_or_may_pass_along:
            result.skipped.append(army_id)
            continue
        if (
            army.is_skeletal
            and not _is_undead_king(state, request.target_leader_id)
            and AdvancedAbility.ENHANCED_SKELETAL_UNITS not in acting_leader.advanced_abilities
        ):
            result.skeletal_army_lost.append((army_id, army.army_type))
            _skeletal_army_returns_to_its_grave(state, army)
            continue
        army.commanded_by = request.target_leader_id
        if target_leader is not None:
            if target_leader.kingdom_id != army.kingdom_id:
                # "An army left to a general of another Realm becomes
                # that Realm's property" (rulebook [3.8]) -- already
                # confirmed allied above.
                army.kingdom_id = target_leader.kingdom_id
        else:
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
        result.succeeded.append(army_id)

    return result


def _skeletal_army_returns_to_its_grave(state: GameState, army: ArmyState) -> None:
    """[4.2.5]: a Skeletal Army given up by its commander "si scaverà da sola la tomba": it leaves
    play and goes back to the province's graveyard (user ruling 2026-11-24), where another
    successful Skeletal Armies spell can raise it again."""

    state.record_battle_death(army.location, army.army_type, army.quality, army.kingdom_id)
    # It goes back to a grave it already left: not a fresh battle death, so it can be raised again at
    # once (the "units that died this very turn" wait only applies to battle casualties).
    state.battle_graveyard[army.location][-1].death_turn = -1
    state.remove_army(army.army_id)


def _dispatch_pick_up(phase: PlanPhase, state: GameState, leader_id: int) -> ArmyListExecutionResult:
    """Phase 420: returns a real ``ArmyListExecutionResult`` -- see
    ``_dispatch_leave()``'s own note above.

    **Phase 821 bug fix**: the acting leader was previously resolved via
    a bare ``state.leaders[leader_id]`` lookup, which crashed with an
    unhandled ``KeyError`` for a leader who already died earlier in the
    same turn (a Pick_Up order queued for a later phase than the one
    that killed them) -- the same class of "dead leader, stale queued
    order" gap already fixed for `_dispatch_leave()` in this same phase.
    Resolved via `.get()` instead, matching `_dispatch_disband()`'s own
    established "a missing acting leader can't act at all" stance: with
    no leader to resolve a location from, every explicitly-listed army
    is skipped and an ``all_armies`` request finds nothing to pick up.

    **Two bug fixes, sourced directly from the user (2026-10-29), the
    fuller rulebook [3.9] text they pasted while designing this
    Action's own move-composer UI**:

    (1) A specific army-id list used to only check co-location, with no
    check at all that the targeted army belongs to the acting leader's
    own Kingdom. Investigated with the user whether a specific list
    should instead be restricted to *unled* armies only (mirroring
    ``all_armies``'s own restriction) -- their own call: no, a specific
    Pick Up can still take over an army actively commanded by *anyone*
    co-located, but only within the acting leader's own Kingdom (e.g.
    reorganizing command among one's own Heroes) -- never a different
    Kingdom's army, allied or not. Every target, whether from
    ``all_armies`` or a specific list, now requires ``army.kingdom_id
    == acting_leader.kingdom_id``.

    (2) "Non è invece possibile usare questo ordine nello stesso turno
    in cui un'unità militare viene reclutata... ad eccezione delle
    unità mercenarie" -- a real precondition this project never
    enforced at all: nothing previously tracked "this specific army was
    freshly levied this turn" (``ProvinceState.recruited_this_turn`` is
    a per-type *count* for the Recruit per-turn limit, not an identity
    marker), so a move file listing Recruit in an earlier phase and
    Pick Up (naming the newly assigned id) in a later phase of the
    *same* turn could actually succeed -- a real, confirmed exploit
    this project's own deterministic, sequential ``GameState.new_
    army_id()`` makes the new id straightforwardly predictable for,
    especially when the GM composer itself already shows the live
    state. ``ArmyState.recruited_this_turn`` (new field, reset to
    ``False`` alongside ``unhireable_this_turn`` in ``turn/turn_
    processor.py _replenish_turn_scoped_state()``) is set ``True`` only
    by a fresh levy (``turn/recruit_execution.py``'s own non-mercenary
    branch) -- a hired mercenary is explicitly exempted by the
    rulebook's own text ("already constituted, with their own id"), so
    ``execute_recruit()`` never sets it there. A target carrying this
    flag is skipped here, same as any other ineligible target.
    """

    request = decode_army_list_phase(phase)
    acting_leader = state.leaders.get(leader_id)
    result = ArmyListExecutionResult(request=request)
    if acting_leader is None:
        result.skipped.extend(request.army_ids)
        return result

    if request.all_armies:
        # "Pick Up All UNLED armies (with Garrison Commander) in the province."
        target_ids = [
            army.army_id for army in state.armies_at(acting_leader.location) if army.commanded_by is None
        ]
    else:
        target_ids = request.army_ids

    for army_id in target_ids:
        army = state.armies.get(army_id)
        if (
            army is None
            or army.location != acting_leader.location  # rulebook: can only pick up a co-located army
            or army.kingdom_id != acting_leader.kingdom_id
            or (army.recruited_this_turn and not army.is_mercenary)
        ):
            result.skipped.append(army_id)
            continue
        army.commanded_by = leader_id
        result.succeeded.append(army_id)

    return result


def _dispatch_disband(phase: PlanPhase, state: GameState, leader_id: int) -> ArmyListExecutionResult:
    """Phase 420: returns a real ``ArmyListExecutionResult`` -- see
    ``_dispatch_leave()``'s own note above.

    **Two bug fixes, sourced directly from the user (2026-10-29), the
    fuller rulebook [3.6] text they pasted while designing this
    Action's own move-composer UI**: (1) a King's own bypass used to
    check co-location only, never that the targeted army actually
    belongs to his own Kingdom -- "Se il comando lo fa il RE può
    sciogliere qualsiasi unità militare del regno anche quelle al
    garrison commander... o comandate da un altro eroe (sempre di
    quel regno)" names the Kingdom boundary explicitly; a King could
    previously target *any* ``army_id`` anywhere on the map, including
    another Kingdom's. (2) An ordinary Hero's own co-location check had
    the same gap -- the rulebook text only ever discusses disbanding
    one's own forces, so a Hero merely standing in the same province as
    a foreign army could disband it too, confirmed with the user as
    unintended rather than a real mechanic. Both branches now also
    require ``army.kingdom_id == acting_leader.kingdom_id``; the King's
    own Phase 40 bypass still only ever waives *co-location*, never
    this Kingdom-ownership check.

    (3) The disbanded army now also gets ``is_mercenary = True`` -- the
    rulebook text's own "i suoi soldati si trasformano in mercenari"
    ("its soldiers turn into mercenaries"), and the real, dedicated flag
    the rest of the engine already keys "is this army an ownerless,
    hireable mercenary band" on (``GameState.mercenaries_at()``, read by
    both ``turn/recruit_execution.py`` and ``turn/move_execution.py
    resolve_wandering_mercenary_following()`` -- the latter is this
    same rulebook paragraph's own "mercenaries in a province a general
    passes through may follow him instead of staying put," the
    mechanic the user's text says exists specifically to close the
    disband-to-dodge-then-rehire loophole). Clearing ``kingdom_id``/
    ``commanded_by`` alone was never a safe proxy for this (an unowned
    native garrison also has ``kingdom_id=None`` but isn't a
    mercenary) -- without this flag, a freshly-disbanded army silently
    couldn't be followed or re-hired, exactly the loophole this
    mechanic exists to close.
    """

    request = decode_army_list_phase(phase)
    target_ids = (
        [army.army_id for army in state.armies_commanded_by(leader_id)] if request.all_armies else request.army_ids
    )
    acting_leader = state.leaders.get(leader_id)
    is_king = acting_leader is not None and acting_leader.is_king

    result = ArmyListExecutionResult(request=request)

    def refuse(army_id: int, reason: str) -> None:
        result.skipped.append(army_id)
        result.skipped_reasons[army_id] = reason

    for army_id in target_ids:
        army = state.armies.get(army_id)
        if army is None:
            refuse(army_id, "there is no such army")
            continue
        # "Releases the army(s) into mercenary status" (rulebook [3.6]:
        # "A King may Disband any army of his Kingdom at any time. A
        # character can Disband an army of his Kingdom only if he is in
        # the same province.") -- ownerless and unled, available to be
        # hired later. Every target must belong to the acting leader's
        # own Kingdom; a Hero must additionally be co-located with the
        # army, a King (Phase 40) bypasses only that co-location check.
        if acting_leader is None or army.kingdom_id != acting_leader.kingdom_id:
            refuse(army_id, "it is not an army of their Kingdom")
            continue
        if not is_king and army.location != acting_leader.location:
            refuse(army_id, "it is not in the same province")
            continue
        # A carrier cannot be released with units still aboard (they would sail off with a
        # wandering mercenary ship), and a unit carried at sea has no land to go home to.
        if cargo_aboard(state, army_id):
            refuse(army_id, "units are still aboard it")
            continue
        if army.transported_by is not None:
            province = state.provinces.get(army.location)
            if province is None or province.effective_terrain() is Terrain.SEA:
                refuse(army_id, "it is at sea aboard a ship")
                continue
            army.transported_by = None
        if army.is_skeletal:
            # [4.2.5]: skeletons whose commander gives them up "si scaveranno da soli la tomba" --
            # released, they return to their sleep rather than wander as hireable mercenaries.
            result.skeletal_army_lost.append((army_id, army.army_type))
            _skeletal_army_returns_to_its_grave(state, army)
            continue
        army.kingdom_id = None
        army.commanded_by = None
        army.is_mercenary = True
        result.succeeded.append(army_id)

    return result


def _dispatch_hire(
    phase: PlanPhase, state: GameState, kingdom_id: int, leader_id: int, rng: random.Random | None = None
) -> HireExecutionResult:
    """Phase 40/264/729: returns a real ``HireExecutionResult`` -- see
    ``_dispatch_leave()``'s own note above for the family shape.

    **Phase 823 bug fix**: the acting leader (whoever is issuing this
    Hire order) was resolved via a bare ``state.leaders[leader_id]``
    lookup, unconditionally, before even the ``hero is None`` check --
    the same "a leader who died earlier in the same turn can still have
    a later phase dispatched" gap already fixed for Leave/Pick_Up/
    Practice (Phase 821/822), and a genuine miss during Phase 821's own
    review of this exact file: every other sibling in this dispatch
    cluster (`_dispatch_disband()` right above) already resolves the
    acting leader via `.get()`, this one didn't. Resolved via `.get()`
    instead, refusing with the same "not co-located" reason the hero's
    own co-location check below already uses -- a dead acting leader
    has no real location to be co-located with anyone at.
    """

    request = decode_hire_phase(phase)
    hero = state.leaders.get(request.hero_id)
    acting_leader = state.leaders.get(leader_id)
    if acting_leader is None:
        return HireExecutionResult(request, hired=False, reason="not co-located")

    if hero is None:
        return HireExecutionResult(request, hired=False, reason="hero not found")
    if hero.is_king:
        # rulebook [3.5]: "You can't Hire a Hero who rules his own
        # province." Checked explicitly (Phase 40) rather than relying
        # on the "already in service" check below to catch every King
        # as a side effect -- that only works if the King happens to
        # have a kingdom_id set, which isn't guaranteed by is_king alone.
        return HireExecutionResult(request, hired=False, reason="cannot hire a King")
    if hero.kingdom_id is None and state.armies_commanded_by(hero.leader_id):
        # rulebook [3.5]: "Un Eroe che governa la propria provincia non può essere assoldato" -- an
        # independent lord governs his province through the armies he commands there (the model's
        # own convention, `worldgen/generate_new_game.py`); a lord whose province was conquered
        # lost them and is an ordinary, dearer to hire, free Hero again ([7.6]).
        return HireExecutionResult(request, hired=False, reason="hero rules his own province")
    # Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT -- "If a foreign king
    # tries to hire the Spy, the hiring will appear to be successful,
    # but the spy will continue to execute the orders you give him."
    # Only a genuinely foreign Kingdom's own hire attempt qualifies --
    # the Spy's own real employer re-issuing a Hire order against their
    # own already-employed Spy still hits the ordinary refusal below.
    is_double_agent_hire = (
        AdvancedAbility.SPY_DOUBLE_AGENT in hero.advanced_abilities
        and hero.kingdom_id is not None
        and hero.kingdom_id != kingdom_id
    )
    if hero.kingdom_id is not None and not is_double_agent_hire:
        return HireExecutionResult(request, hired=False, reason="hero already in service")
    if hero.location != acting_leader.location:
        # rulebook [3.5]: "Any character can attempt to Hire a Hero in the
        # same province."
        return HireExecutionResult(request, hired=False, reason="not co-located")

    king = find_king_of_kingdom(state, kingdom_id)
    pay = required_pay(state, hero, king)
    rare_exception = False

    if pay >= 5:
        # rulebook: "a Good King generally cannot hire a Pagan Hero" --
        # refused outright, unless the "rare exception" bypass (Phase
        # 264, turn/hire_pay.py roll_rare_alignment_exception()) fires;
        # on success the price drops to the Hire ceiling (4) instead of
        # staying unreachable. See that module's own docstring.
        if roll_rare_alignment_exception(rng if rng is not None else random.Random()):
            pay = RARE_ALIGNMENT_EXCEPTION_PAY
            rare_exception = True
        else:
            return HireExecutionResult(request, hired=False, reason="alignment gap too wide", minimum_gold=pay)
    if request.gold_offer < pay:
        return HireExecutionResult(request, hired=False, reason="offer below required pay", minimum_gold=pay)

    kingdom = state.kingdoms[kingdom_id]
    if kingdom.treasury < pay:
        return HireExecutionResult(request, hired=False, reason="insufficient treasury", minimum_gold=pay)

    kingdom.treasury -= pay
    if is_double_agent_hire:
        # The whole point: hero.kingdom_id never changes, so this
        # Kingdom's own real orders (submitted separately, under the
        # Spy's own true kingdom_id) keep driving this leader exactly as
        # before -- see turn/turn_processor.py run_turn()'s own Phase
        # 729 end-of-turn hook for the resulting intel grant.
        hero.double_agent_hired_by_kingdom_id = kingdom_id
    else:
        hero.kingdom_id = kingdom_id
        hero.hire_turn = state.turn_number

    return HireExecutionResult(request, hired=True, minimum_gold=pay, rare_alignment_exception=rare_exception)


def _dispatch_fire(phase: PlanPhase, state: GameState, leader_id: int) -> FireExecutionResult:
    """Phase 143: returns a real ``FireExecutionResult`` instead of the previous bare
    ``FireRequest`` -- the caller now has a genuine ``fired``/``reason``
    signal to build a report sentence from (``report/turn_report.py
    describe_fire()``), where before it had no way to tell whether the
    Fire actually happened at all.

    **Phase 614**: before any of the ordinary Fire logic below runs,
    checks a real, disassembly-confirmed reinterpretation of this same
    order (`AK.EXE:0xCD0D-0xCD39`, user-supplied 2026-08-22): a FIRE
    order becomes a free Grandfather of Assassins attempt instead of an
    ordinary Fire when the order-giver currently holds ``Office.
    ASSASSIN``, the target isn't a King, and the target belongs to a
    different Kingdom than the order-giver's own (``LKing(target) <>
    LKing(order_giver)`` -- "if the Grandfather Fires his own character,
    the two ``LKing``s coincide and the order stays an ordinary Fire,"
    per the manual's own note). See ``turn/assassin_guild.py``'s own
    module docstring for the full mechanic this queues into ``state.
    pending_guild_target`` for.

    **2026-11-01, two bug fixes sourced directly from the user, found
    while designing this Action's own GM composer** -- neither is in
    the pasted [3.7] rulebook text itself, both confirmed as the user's
    own deliberate choice via an explicit follow-up question rather
    than assumed from phrasing:

    - **Can't Fire a King.** Symmetric with Hire's own explicit "can't
      Hire a King" guard (``_dispatch_hire()``, rulebook [3.5]) --
      nothing in [3.7] suggests Fire should be able to "dekingdom" a
      ruling King, and nothing elsewhere in this project models what a
      Kingdom with no King at all would even mean. Checked immediately
      after the "hero not found" guard, before anything else.
    - **Same-Kingdom requirement for an ordinary Fire.** The pasted
      [3.7] text, read literally ("un personaggio può congedare un
      Eroe... se si trova nella stessa provincia"), doesn't restrict
      *whose* Hero can be Fired -- unlike Disband, which operates on a
      Kingdom's own owned property (an army) and was given this exact
      same fix earlier (``_dispatch_disband()``'s own King-co-location-
      bypass-isn't-a-Kingdom-bypass correction), a Hero is an
      independent character whose service relationship a plain reading
      of [3.7] arguably lets *any* co-located character interrupt, not
      just their own Kingdom's. The user was asked this exact question
      directly and chose to apply the same Kingdom-ownership
      requirement anyway -- a King's or a co-located Hero's own Fire
      order now only ever succeeds against a Hero of their *own*
      Kingdom (or themself, trivially always same-Kingdom). This still
      correctly leaves room for the Phase 614 Grandfather-of-Assassins
      interception immediately below, which specifically exists for the
      cross-Kingdom case.
    """

    request = decode_fire_phase(phase)
    hero = state.leaders.get(request.hero_id)
    if hero is None:
        return FireExecutionResult(request, fired=False, reason="hero not found")
    if hero.is_king:
        return FireExecutionResult(request, fired=False, reason="cannot fire a King")

    acting_leader = state.leaders.get(leader_id)

    if acting_leader is not None and acting_leader.kingdom_id != hero.kingdom_id:
        titleholder = resolve_office_holder(state, Office.ASSASSIN)
        if titleholder is not None and titleholder.leader_id == leader_id:
            state.pending_guild_target = request.hero_id
            return FireExecutionResult(request, fired=False, guild_assassination_queued=True)
        return FireExecutionResult(request, fired=False, reason="not this Kingdom's Hero")

    # "Releases the Hero into private life... will wander around until
    # hired by another King." (rulebook [3.7]: "A King may Fire a Hero
    # at any time. A character can Fire a Hero only if he is in the
    # same province.") A Hero must be co-located with the target (this
    # also naturally covers "firing himself" -- he's always in his own
    # province, and his own kingdom_id trivially matches itself above);
    # a King (Phase 40) bypasses that, same as Disband.
    is_king = acting_leader is not None and acting_leader.is_king
    co_located = acting_leader is not None and acting_leader.location == hero.location
    if not (is_king or co_located):
        return FireExecutionResult(request, fired=False, reason="not co-located")

    if hero.race is None and hero.kingdom_id in state.kingdoms:
        hero.race = state.kingdoms[hero.kingdom_id].race  # a hero with no kingdom keeps the race he served under
    hero.kingdom_id = None
    release_armies_to_garrison(state, hero.leader_id)  # the Kingdom keeps his armies, under the Garrison Commander
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
    deferred_nested_plans: list[tuple[int, ActionPlan]] | None = None,
) -> list[PhaseDispatchResult]:
    """Attempt every phase (in order, across all segments) of ``leader``'s plan.

    ``deferred_nested_plans`` (2026-11-24): by default a newly Hired/Charmed character's own
    embedded plan is dispatched here, at once and in full. A caller that sequences the turn phase
    by phase (``turn/turn_processor.py run_turn()``) passes a list instead: each triggered plan is
    appended to it as ``(character id, plan)`` and *not* dispatched, so the caller can start the
    character's orders from the next phase ("non potete dare ordini nella stessa fase in cui sono
    assoldati, ma a partire da quella successiva").

    ``army_ids`` defaults to whatever ``leader.leader_id`` currently
    commands in ``state`` (re-evaluated fresh for each phase, so a
    Pick_Up/Leave earlier in the plan changes what a later LMOVE brings
    along); pass an explicit list to pin it instead.

    Never raises: an unsupported or failing phase is recorded in the
    returned list (``error`` set, ``result`` None) so the run continues
    through the rest of the plan instead of stopping at the first gap --
    the whole point of this function is to produce a full report against
    a real parsed turn, where most actions are still unsupported.

    **Phase 547** -- the Valhalla visitor's own per-visit phase cap
    (``VALHALLA.txt``'s own escalating action table, ``LeaderState.
    valhalla_allowed_phase_count``, set at spawn by ``turn/valhalla_
    execution.py finalize_gate_angel_visit()``) is enforced here, since
    this is the one real call site that walks a leader's own phases in
    order across a whole turn. Only active on the visitor's own
    ``valhalla_active_turn`` -- every other leader, and the visitor on
    any other turn, is completely unaffected. Real (non-Wait/No_Action/
    Move_Abort) phases beyond the allowed count are forced to a no-op
    instead of dispatched, same as an ordinary Wait would produce; at
    most one of the allowed phases may be Practice (rule 6/English rule
    3's own "only enough patience... for one of the phases"), any later
    Practice attempt is forced to a no-op too even if the phase budget
    itself has room left.
    """

    results: list[PhaseDispatchResult] = []
    visitor = state.leaders.get(leader.leader_id) if leader.leader_id == VALHALLA_VISITOR_LEADER_ID else None
    valhalla_cap_active = visitor is not None and visitor.valhalla_active_turn == state.turn_number
    valhalla_phases_used = 0
    valhalla_practice_used = False
    for segment_index, segment in enumerate(leader.plan.segments):
        for label in ("P0", "P1", "P2", "P3", "P4"):
            phase = segment.phases.get(label)
            if phase is None:
                continue
            # A character made sick by Hidden Tattoos carries out Practice orders only.
            phase = apply_sickness(state, leader.leader_id, phase)
            if valhalla_cap_active and phase.action not in (ActionCode.WAIT, ActionCode.NO_ACTION, ActionCode.MOVE_ABORT):
                allowed = visitor.valhalla_allowed_phase_count or 0
                is_over_budget = valhalla_phases_used >= allowed
                is_extra_practice = phase.action is ActionCode.PRACTICE and valhalla_practice_used
                if is_over_budget or is_extra_practice:
                    results.append(
                        PhaseDispatchResult(leader.leader_id, segment_index, label, phase.action, NoOpResult(action=phase.action), None)
                    )
                    continue
                valhalla_phases_used += 1
                if phase.action is ActionCode.PRACTICE:
                    valhalla_practice_used = True
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
                note_spy_watch(state, leader.leader_id, phase, result)
            except Exception as exc:  # noqa: BLE001 -- intentionally broad, see docstring
                results.append(PhaseDispatchResult(leader.leader_id, segment_index, label, phase.action, None, exc))
                continue

            # Phase 766 -- Naval Hug Coastline's own real "unboarded
            # stragglers" split (Phase 763) produces a second, genuinely
            # independent `MoveExecutionResult` that `execute_move()`
            # itself has no way to surface on its own (it returns exactly
            # one result per call). Appended here as its own sentinel
            # `PhaseDispatchResult` -- `segment_index=-1`/`action=None`,
            # the same convention the random-encounter sentinel right
            # below already established -- so every existing consumer
            # that scans `results` for real consequences (battle
            # narration via `_battle_reports_from_results()`, which
            # duck-types any `.battle_report` attribute) picks up the
            # stragglers' own battle/exploration/conquest for free, with
            # zero changes needed to that machinery. See `report/
            # turn_report.py describe_naval_hug_coastline_stragglers()`
            # for the one new, explicitly project-original narration line
            # this session adds on top of that free reuse.
            if isinstance(result, MoveExecutionResult) and result.straggler_result is not None:
                results.append(PhaseDispatchResult(leader.leader_id, -1, label, None, result.straggler_result, None))

            # Phase 708 -- CASUALENCOUNTER.md's own random-encounter roll,
            # attempted right after this phase's own ordinary dispatch,
            # for exactly the 5 real triggering action types. `rng is
            # None` (a handful of deterministic/no-dice callers) means no
            # random encounter can be attempted at all -- skipped, not an
            # error.
            if rng is not None:
                random_encounter_result = dispatch_random_encounter_after_phase(state, leader, phase, rng)
                if random_encounter_result is not None:
                    results.append(PhaseDispatchResult(leader.leader_id, -1, label, None, random_encounter_result, None))

            if phase.nested_plan is not None and _nested_plan_triggered(phase.action, result):
                nested_leader_id = _resolve_nested_plan_leader_id(phase.action, phase.nested_plan, result)
                if deferred_nested_plans is not None:
                    if nested_leader_id is not None and nested_leader_id in state.leaders:
                        deferred_nested_plans.append((nested_leader_id, phase.nested_plan))
                else:
                    results.extend(
                        _dispatch_nested_plan(
                            phase.nested_plan, nested_leader_id, state, kingdom_id, board_width, explorer_skill, rng
                        )
                    )
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

    **Phase 1039**: a wand's Use_MI can cast Charm/Resurrection exactly
    the same way an ordinary Cast order can (``turn/use_mi_execution.py
    execute_use_mi()``'s own ``SPELL_WAND`` branch dispatches into the
    very same ``execute_cast()``) -- ``UseMIExecutionResult.cast_result``
    is set (and mirrors ``CastExecutionResult`` exactly) whenever that
    happened, so the same "did it apply" check extends here unchanged.
    Which spell it actually was is deliberately not checked in this
    trigger -- the real spell/target gating happens in
    ``_resolve_nested_plan_leader_id()`` below instead, the same split
    the existing Cast branch already relies on (a successful Cast of any
    *other* spell also reaches this branch and returns ``True``, but
    never carries a resolvable ``nested_plan.leader_id``, so ``_dispatch_
    nested_plan`` below silently no-ops for it).
    """

    if action is ActionCode.HIRE:
        return isinstance(result, HireExecutionResult) and result.hired
    if action is ActionCode.CAST:
        return isinstance(result, CastExecutionResult) and result.applied
    if action is ActionCode.USE_MI:
        return isinstance(result, UseMIExecutionResult) and result.applied
    return False


def _resolve_nested_plan_leader_id(action: Any, nested_plan: ActionPlan, result: Any) -> int | None:
    """The newly-joined (or re-joined) character's own ``leader_id`` for a
    nested plan that ``_nested_plan_triggered()`` just approved for
    dispatch.

    Hire and an ordinary Cast of Charm/Resurrection already have this
    baked into ``nested_plan.leader_id`` at *parse* time
    (``parser/k1_moves.py _maybe_parse_nested_plan``, Phase 23) -- the
    move file's own tokens are self-describing enough there (``obj`` is
    directly the target id for Hire, ``extra[0]`` directly the target id
    for a Cast of Charm/Resurrection), no ``GameState`` needed.

    **Phase 1039**: a Use_MI-triggered Charm/Resurrection cannot be
    resolved that way -- ``turn/use_mi_decode.py``'s own docstring:
    Use_MI's own ``obj`` is an opaque item-instance id, not a ``Spell``
    ordinal, until ``state.items`` resolves which wand it is, which the
    parser has no access to. So it's resolved here instead, after
    execution, from ``UseMIExecutionResult.cast_result.request`` -- the
    exact same ``CastRequest`` shape (``target``: "character id...
    depending on spell") the ordinary Cast path already reads at parse
    time, just reached one step later. Returns ``None`` (silently
    skipping dispatch, same as an unresolvable Cast above) for any wand
    that cast something other than Charm/Resurrection -- the structural
    nesting condition in ``parser/k1_moves.py`` can in principle follow
    *any* Use_MI phase, not just a Charm/Resurrection wand's own, the
    same "nested_plan present, but not really this kind of trigger" case
    the Cast branch already has to tolerate.
    """

    if action is ActionCode.USE_MI:
        if (
            isinstance(result, UseMIExecutionResult)
            and result.cast_result is not None
            and result.cast_result.request.spell in (Spell.CHARM, Spell.RESURRECTION)
        ):
            return result.cast_result.request.target
        return None
    return nested_plan.leader_id


def _dispatch_nested_plan(
    nested_plan: ActionPlan,
    nested_leader_id: int | None,
    state: GameState,
    kingdom_id: int,
    board_width: int,
    explorer_skill: int,
    rng: random.Random | None,
) -> list[PhaseDispatchResult]:
    """Dispatch a newly-joined character's own embedded plan (see module docstring).

    Silently skipped (empty list) if ``nested_leader_id`` (``_resolve_
    nested_plan_leader_id()``'s own result, Phase 1039 -- previously
    always just ``nested_plan.leader_id``) couldn't be resolved, or that
    character has no existing ``LeaderState`` in ``state`` -- there's
    nothing to enrich, same "can't create from nothing" rule as
    ``turn/kingdom_bridge.py`` (Phase 31). Never pins ``army_ids``: a
    freshly Hired/Charmed character's own commanded armies (if any) are
    re-derived fresh, independent of whatever the triggering leader's own
    dispatch was pinned to.
    """

    if nested_leader_id is None or nested_leader_id not in state.leaders:
        return []

    nested_leader = Leader(leader_id=nested_leader_id, name=state.leaders[nested_leader_id].name, plan=nested_plan)
    return run_leader_plan(
        nested_leader, state, kingdom_id, board_width=board_width, explorer_skill=explorer_skill, rng=rng
    )
